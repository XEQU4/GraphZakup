"""Kazakhstan civil-day boundaries across saved evidence, API reads and jobs."""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.conf import settings
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone, translation

from apps.ai.jobs import request_analysis
from apps.ai.models import AnalysisSnapshot, Explanation
from apps.ai.services import collect_inputs, prepare_analysis
from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.graph.evidence import EvidenceIndex
from apps.graph.models import GraphSnapshot, RiskCluster
from apps.graph.services import load_graph_suppliers, rebuild_clusters
from apps.ingestion.models import CompanyKgdState, IngestionRun, SourceObservation
from apps.ingestion.quality import build_data_quality_report
from apps.ingestion.tests.helpers import verified_role
from apps.owners.models import Director, Directorship
from apps.owners.querysets import current_role_filter


UTC = datetime_timezone.utc
MIDNIGHT = datetime(2026, 10, 9, 19, tzinfo=UTC)
BEFORE_MIDNIGHT = MIDNIGHT - timedelta(microseconds=1)
DAY = date(2026, 10, 10)


class BusinessTimezoneSettingsTests(SimpleTestCase):
    def test_django_and_celery_share_explicit_business_timezone_and_utc_storage(self):
        from config.celery import app

        self.assertEqual(settings.TIME_ZONE, 'Asia/Qyzylorda')
        self.assertEqual(str(timezone.get_default_timezone()), 'Asia/Qyzylorda')
        self.assertEqual(settings.CELERY_TIMEZONE, settings.TIME_ZONE)
        self.assertEqual(app.conf.timezone, settings.TIME_ZONE)
        self.assertTrue(settings.USE_TZ)
        self.assertTrue(settings.CELERY_ENABLE_UTC)

    def test_local_midnight_utc_midnight_year_and_leap_day_boundaries(self):
        for instant, expected in (
            (BEFORE_MIDNIGHT, date(2026, 10, 9)),
            (MIDNIGHT, DAY),
            (datetime(2026, 10, 9, 23, 59, 59, tzinfo=UTC), DAY),
            (datetime(2026, 10, 10, tzinfo=UTC), DAY),
            (datetime(2026, 12, 31, 18, 59, 59, tzinfo=UTC), date(2026, 12, 31)),
            (datetime(2026, 12, 31, 19, tzinfo=UTC), date(2027, 1, 1)),
            (datetime(2028, 2, 28, 19, tzinfo=UTC), date(2028, 2, 29)),
            (datetime(2028, 2, 29, 19, tzinfo=UTC), date(2028, 3, 1)),
        ):
            for language in ('en', 'ru'):
                with self.subTest(instant=instant, language=language), translation.override(language):
                    self.assertEqual(timezone.localdate(instant), expected)


@override_settings(KGD_RESULT_MAX_AGE_DAYS=7)
class BusinessDateIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.companies = [Supplier.objects.create(bin=f'{number:012}',
            name=f'Synthetic boundary company {number}', address='Synthetic shared office')
            for number in (1, 2)]
        cls.ingestion_run = IngestionRun.objects.create(mode='kgd', status='succeeded')

    def debt(self, dates, *, observed_at=MIDNIGHT, status='success'):
        company = self.companies[0]
        observation = SourceObservation.objects.create(run=self.ingestion_run, supplier=company,
            source='kgd_tax_debt', subject_key=f'company:{company.bin}', status=status,
            observed_at=observed_at, fingerprint=f'{SourceObservation.objects.count() + 1:064}', normalized_values={
                'bin': company.bin, 'kgd_total_arrears': '0.00', 'kgd_tax_arrears': '0.00',
                'kgd_pension_arrears': '0.00', 'kgd_social_arrears': '0.00',
                'kgd_health_insurance_arrears': '0.00',
                'kgd_reporting_dates': [day.isoformat() for day in dates]})
        state, _ = CompanyKgdState.objects.get_or_create(supplier=company, source='kgd_tax_debt',
            defaults={'latest_observation': observation})
        state.latest_observation = observation
        if status == 'success':
            state.last_successful_observation = observation
        state.save()
        return observation

    def group(self):
        rebuild_clusters()
        return RiskCluster.objects.get(is_active=True)

    def api_debt(self):
        response = self.client.get(f'/api/v1/companies/{self.companies[0].pk}/')
        self.assertEqual(response.status_code, 200)
        return next(row for row in response.json()['kgd_checks'] if row['source'] == 'kgd_tax_debt')

    def test_current_roles_and_graph_api_share_start_inclusive_end_exclusive_dates(self):
        roles = {}
        for name, bounds in (
            ('ending', {'start_date': DAY - timedelta(days=1), 'end_date': DAY}),
            ('starting', {'start_date': DAY, 'end_date': DAY + timedelta(days=1)}),
            ('unknown', {}),
            ('inactive', {'is_current': False}),
        ):
            director = Director.objects.create(full_name=f'Synthetic {name} director')
            roles[name] = verified_role(self.companies[0], director, **bounds)
        for instant, active, legal in (
            (BEFORE_MIDNIGHT, {'ending', 'unknown'}, {'ending': True, 'starting': False}),
            (MIDNIGHT, {'starting', 'unknown'}, {'ending': False, 'starting': True}),
        ):
            with self.subTest(instant=instant), patch('django.utils.timezone.now', return_value=instant):
                self.assertEqual(set(Directorship.objects.filter(current_role_filter()).values_list('pk', flat=True)),
                    {roles[name].pk for name in active})
                index = EvidenceIndex(load_graph_suppliers())
                self.assertEqual(index.as_of, timezone.localdate(instant))
                self.assertEqual({edge['target'] for edge in index.edges.values() if edge['type'] == 'director'},
                    {f'person:{roles[name].person_identity_id}' for name in active})
                response = self.client.get('/api/v1/directorships/', {'company_id': self.companies[0].pk})
                self.assertEqual(response.status_code, 200)
                rows = {row['id']: row for row in response.json()['results']}
                for name, expected in {**legal, 'unknown': None, 'inactive': False}.items():
                    self.assertIs(rows[roles[name].pk]['currently_applicable'], expected)
                self.assertEqual(rows[roles['unknown'].pk]['temporal_status'], 'unknown')

    def test_same_day_source_date_becomes_valid_at_kazakhstan_midnight(self):
        self.debt([DAY], observed_at=BEFORE_MIDNIGHT)
        with patch('django.utils.timezone.now', return_value=BEFORE_MIDNIGHT):
            cluster = self.group()
            self.assertEqual(collect_inputs(cluster.current_snapshot)['company_checks'][0]['status'], 'invalid')
            self.assertEqual(self.api_debt()['status'], 'invalid')
        with patch('django.utils.timezone.now', return_value=MIDNIGHT):
            inputs = collect_inputs(cluster.current_snapshot)
            self.assertEqual(inputs['company_checks'][0]['status'], 'fresh')
            result = self.api_debt()
            self.assertEqual(result['status'], 'success')
            self.assertFalse(result['last_successful']['stale'])
            self.assertEqual(result['last_successful']['reporting_dates'], [DAY.isoformat()])
            self.assertEqual(inputs['company_checks'][1]['status'], 'not_checked')

    def test_reporting_date_freshness_boundary_and_future_date_remain_distinct(self):
        with patch('django.utils.timezone.now', return_value=MIDNIGHT):
            cluster = self.group()
            for days, expected, stale in ((0, 'fresh', False), (7, 'fresh', False),
                                          (8, 'stale', True), (-1, 'invalid', None)):
                with self.subTest(days=days):
                    self.debt([DAY - timedelta(days=days)])
                    self.assertEqual(collect_inputs(cluster.current_snapshot)['company_checks'][0]['status'], expected)
                    result = self.api_debt()
                    if stale is None:
                        self.assertEqual(result['status'], 'invalid')
                        self.assertIsNone(result['last_successful'])
                    else:
                        self.assertEqual(result['status'], 'success')
                        self.assertEqual(result['last_successful']['stale'], stale)
            self.debt([])
            self.assertEqual(collect_inputs(cluster.current_snapshot)['company_checks'][0]['status'], 'undated')
            self.assertTrue(self.api_debt()['last_successful']['stale'])

    def test_oldest_reporting_date_expires_on_business_day_rollover(self):
        self.debt([DAY - timedelta(days=8), DAY - timedelta(days=1)], observed_at=BEFORE_MIDNIGHT)
        with patch('django.utils.timezone.now', return_value=BEFORE_MIDNIGHT):
            cluster = self.group()
            self.assertEqual(collect_inputs(cluster.current_snapshot)['company_checks'][0]['status'], 'fresh')
            self.assertFalse(self.api_debt()['last_successful']['stale'])
        with patch('django.utils.timezone.now', return_value=MIDNIGHT):
            self.assertEqual(collect_inputs(cluster.current_snapshot)['company_checks'][0]['status'], 'stale')
            self.assertTrue(self.api_debt()['last_successful']['stale'])

    def test_retained_success_after_failure_does_not_become_current_zero(self):
        with patch('django.utils.timezone.now', return_value=MIDNIGHT):
            cluster = self.group()
            successful = self.debt([DAY])
            self.debt([], status='unavailable')
            self.assertEqual(collect_inputs(cluster.current_snapshot)['company_checks'][0]['status'], 'retained_fresh')
            result = self.api_debt()
            self.assertEqual(result['status'], 'unavailable')
            self.assertEqual(result['last_successful']['observation_id'], successful.pk)
            self.assertTrue(result['last_successful']['stale'])

    def test_aware_instants_round_trip_in_utc_and_retrieval_age_is_elapsed_time(self):
        with patch('django.utils.timezone.now', return_value=MIDNIGHT):
            exact_cutoff = MIDNIGHT - timedelta(days=7)
            observation = self.debt([DAY], observed_at=exact_cutoff)
            observation.refresh_from_db()
            self.assertTrue(timezone.is_aware(observation.observed_at))
            self.assertEqual(observation.observed_at.utcoffset(), timedelta(0))
            self.assertEqual(observation.observed_at, exact_cutoff)
            self.assertEqual(connection.timezone_name, 'UTC')
            self.assertFalse(self.api_debt()['last_successful']['stale'])
            self.debt([DAY], observed_at=exact_cutoff - timedelta(microseconds=1))
            self.assertTrue(self.api_debt()['last_successful']['stale'])

    def test_new_graph_analysis_and_jobs_use_business_day_without_rewriting_history(self):
        director = Director.objects.create(full_name='Synthetic midnight director')
        for company in self.companies:
            verified_role(company, director, start_date=DAY, end_date=DAY + timedelta(days=1))
        with patch('django.utils.timezone.now', return_value=BEFORE_MIDNIGHT):
            cluster = self.group()
            original_graph = cluster.current_snapshot
            original_analysis, _ = prepare_analysis(cluster.pk)
            original = deepcopy((original_graph.as_of, original_graph.payload,
                                 original_analysis.as_of, original_analysis.inputs))
            counts = (GraphSnapshot.objects.count(), AnalysisSnapshot.objects.count(), Explanation.objects.count())
        with patch('django.utils.timezone.now', return_value=MIDNIGHT):
            for endpoint in ('graph', 'analysis'):
                self.assertEqual(self.client.get(f'/api/v1/clusters/{cluster.uuid}/{endpoint}/').status_code, 200)
            self.assertEqual((GraphSnapshot.objects.count(), AnalysisSnapshot.objects.count(), Explanation.objects.count()), counts)
            rebuild_clusters()
            cluster.refresh_from_db()
            self.assertNotEqual(cluster.current_snapshot_id, original_graph.pk)
            self.assertEqual(cluster.current_snapshot.as_of, DAY)
            analysis, _ = prepare_analysis(cluster.pk)
            self.assertEqual(analysis.as_of, DAY)
            with self.captureOnCommitCallbacks(execute=False):
                job, created = request_analysis(None, cluster.pk, use_model=False)
            self.assertTrue(created)
            self.assertEqual(job.as_of, DAY)
            self.assertEqual(job.graph_snapshot_id, cluster.current_snapshot_id)
        original_graph.refresh_from_db()
        original_analysis.refresh_from_db()
        self.assertEqual((original_graph.as_of, original_graph.payload,
                          original_analysis.as_of, original_analysis.inputs), original)
        self.assertEqual(original_graph.as_of, DAY - timedelta(days=1))

    def test_quality_report_contract_and_role_dates_follow_the_same_business_day(self):
        director = Director.objects.create(full_name='Synthetic quality director')
        verified_role(self.companies[0], director, start_date=DAY, end_date=DAY + timedelta(days=1))
        for number, contract_day in enumerate((DAY, DAY + timedelta(days=1)), 1):
            Contract.objects.create(supplier=self.companies[0], contract_number=f'synthetic-boundary-{number}',
                title='Synthetic dated contract', amount='1.00', contract_date=contract_day)
        for instant, future_contracts, future_roles in ((BEFORE_MIDNIGHT, 2, 1), (MIDNIGHT, 1, 0)):
            with self.subTest(instant=instant):
                report = build_data_quality_report(now=instant)
                self.assertEqual(report['contracts']['future_contract_date'], future_contracts)
                self.assertEqual(report['roles']['directors']['expired_or_future_interval'], future_roles)
