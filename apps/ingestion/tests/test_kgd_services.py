from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from io import StringIO
import json
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection, IntegrityError
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.companies.models import Supplier
from apps.core.tasks import check_kgd
from apps.graph.models import RiskCluster
from apps.ingestion.dto import ResultStatus, SourceResult
from apps.ingestion.kgd import company_kgd_statuses, record_kgd_result
from apps.ingestion.leases import IngestionBusy, RunLease
from apps.ingestion.models import CompanyKgdState, IngestionRun, IngestionLease, SourceObservation
from apps.ingestion.observations import cached_company_result
from apps.ingestion.parsers.kgd import AMOUNT_FIELDS, DEBT_SOURCE, KgdParser, TAXPAYER_SOURCE, parse_tax_debt, parse_taxpayer
from apps.ingestion.services import IngestionFailure, run_pipeline
from apps.owners.models import Owner, TaxDebt, Directorship, Ownership
from .test_kgd_parser import BIN, fixture


def success(source, bin_number=BIN, when=None):
    payload = fixture('taxpayer' if source == TAXPAYER_SOURCE else 'tax_debt')
    if source == TAXPAYER_SOURCE:
        payload['taxpayerPortalSearchResponses'][0]['code'] = bin_number
        data, raw = parse_taxpayer(payload, bin_number)
    else:
        payload['iinBin'] = bin_number
        data, raw = parse_tax_debt(payload, bin_number)
    return SourceResult(source, f'company:{bin_number}', ResultStatus.SUCCESS, data=data, raw=raw,
                        observed_at=when or timezone.now(), parser_version=KgdParser.VERSION,
                        source_url=KgdParser.SOURCE_URLS[source])


class FakeKgd:
    kgd_ready = True

    def kgd_cache_allowed(self, source, bin_number):
        return self.kgd_ready

    def __init__(self, responses=None):
        self.responses, self.calls = responses or {}, []

    def kgd(self, source, bin_number, *, legal_entity_confirmed=False):
        self.calls.append((source, bin_number, legal_entity_confirmed))
        result = self.responses.get((source, bin_number))
        if isinstance(result, Exception):
            raise result
        return result or success(source, bin_number)


class KgdPipelineTests(TestCase):
    def setUp(self):
        self.company = Supplier.objects.create(bin=BIN, name='Original', risk_score=31)

    def collect(self, **options):
        return run_pipeline(mode='kgd', total=1, company_bin=BIN, **options)

    def failure(self, source=TAXPAYER_SOURCE, when=None, status=ResultStatus.UNAVAILABLE, code='kgd_access_denied'):
        return SourceResult(source, f'company:{BIN}', status, error_code=code,
                            observed_at=when or timezone.now(), parser_version=KgdParser.VERSION)

    def test_registration_is_bounded_and_does_not_mutate_company_graph_or_people(self):
        other = Supplier.objects.create(bin='000000000002', name='Other')
        cluster = RiskCluster.objects.create(name='Stored graph', ai_explanation='Stored explanation', risk_score=22)
        cluster.suppliers.add(self.company, other)
        owner = Owner.objects.create(full_name='Synthetic owner', has_tax_debt=False)
        before = (cluster.pk, cluster.uuid, cluster.ai_explanation, cluster.analysis_fingerprint,
                  list(cluster.suppliers.values_list('pk', flat=True)))
        providers = FakeKgd()
        with patch('apps.ingestion.services.rebuild_clusters', side_effect=AssertionError('unexpected graph write')):
            run = self.collect(providers=providers)
        self.assertEqual((run.status, run.stage), ('succeeded', 'complete'))
        self.assertEqual(providers.calls, [(TAXPAYER_SOURCE, BIN, False)])
        self.company.refresh_from_db()
        owner.refresh_from_db()
        cluster.refresh_from_db()
        self.assertEqual((self.company.name, self.company.risk_score), ('Original', 31))
        self.assertFalse(owner.has_tax_debt)
        self.assertEqual((TaxDebt.objects.count(), Directorship.objects.count(), Ownership.objects.count()), (0, 0, 0))
        self.assertEqual(before, (cluster.pk, cluster.uuid, cluster.ai_explanation, cluster.analysis_fingerprint,
                                 list(cluster.suppliers.values_list('pk', flat=True))))

    def test_repeat_uses_observation_cache_without_advancing_observation_date(self):
        providers = FakeKgd()
        first = self.collect(providers=providers)
        observed_at = CompanyKgdState.objects.get().latest_observation.observed_at
        second = self.collect(providers=providers)
        self.assertEqual(len(providers.calls), 1)
        self.assertEqual(CompanyKgdState.objects.count(), 1)
        cached = SourceObservation.objects.get(run=second)
        self.assertTrue(cached.from_cache)
        self.assertEqual(cached.observed_at, observed_at)
        self.assertEqual(run_pipeline(resume=first.uuid, providers=providers).pk, first.pk)
        self.assertEqual(len(providers.calls), 1)

    def test_debt_check_is_company_evidence_and_reporting_date_is_not_fetch_date(self):
        providers = FakeKgd()
        self.collect(providers=providers, kgd_service='tax_debt')
        self.assertEqual(providers.calls, [(TAXPAYER_SOURCE, BIN, False), (DEBT_SOURCE, BIN, True)])
        state = CompanyKgdState.objects.get(source=DEBT_SOURCE)
        data = state.latest_observation.normalized_values
        self.assertEqual(data['kgd_total_arrears'], '123456789012345.67')
        self.assertEqual(data['kgd_reporting_dates'], ['2026-10-01'])
        self.assertEqual(company_kgd_statuses(self.company)[1]['total_arrears'], Decimal('123456789012345.67'))
        self.assertEqual(TaxDebt.objects.count(), 0)

    def test_failure_preserves_last_success_and_resume_recovers_without_new_run(self):
        self.collect(providers=FakeKgd(), kgd_service='tax_debt')
        previous = CompanyKgdState.objects.get(source=DEBT_SOURCE).last_successful_observation
        failed = FakeKgd({(DEBT_SOURCE, BIN): self.failure(DEBT_SOURCE)})
        with self.assertRaises(IngestionFailure) as failure:
            self.collect(providers=failed, kgd_service='tax_debt', force=True)
        run = IngestionRun.objects.get(uuid=failure.exception.run_id)
        self.assertEqual(run.status, 'partial')
        state = CompanyKgdState.objects.get(source=DEBT_SOURCE)
        self.assertEqual(state.last_successful_observation, previous)
        self.assertEqual(state.latest_observation.status, 'unavailable')
        self.assertTrue(company_kgd_statuses(self.company)[1]['stale'])
        fixed = FakeKgd()
        result = run_pipeline(resume=run.uuid, providers=fixed)
        self.assertEqual((result.pk, result.status, result.attempts), (run.pk, 'succeeded', 2))
        self.assertEqual(fixed.calls, [(TAXPAYER_SOURCE, BIN, False), (DEBT_SOURCE, BIN, True)])
        self.assertFalse(result.issues.filter(resolved=False).exists())

    def test_resume_retries_only_failed_company_and_keeps_original_selection(self):
        second = Supplier.objects.create(bin='000000000002', name='Second')
        bad = replace(self.failure(), subject_key=f'company:{second.bin}')
        providers = FakeKgd({(TAXPAYER_SOURCE, second.bin): bad})
        with self.assertRaises(IngestionFailure) as failure:
            run_pipeline(mode='kgd', total=2, providers=providers)
        Supplier.objects.create(bin='000000000003', name='Added after start')
        fixed = FakeKgd()
        result = run_pipeline(resume=failure.exception.run_id, providers=fixed)
        self.assertEqual(fixed.calls, [(TAXPAYER_SOURCE, second.bin, False)])
        self.assertEqual(result.options['company_ids'], [self.company.pk, second.pk])

    def test_unconfirmed_taxpayer_blocks_debt_request(self):
        for status in (ResultStatus.NOT_FOUND, ResultStatus.UNAVAILABLE, ResultStatus.INVALID):
            providers = FakeKgd({(TAXPAYER_SOURCE, BIN): self.failure(status=status)})
            with self.subTest(status=status), self.assertRaises(IngestionFailure):
                self.collect(providers=providers, kgd_service='tax_debt', force=True)
            self.assertEqual(providers.calls, [(TAXPAYER_SOURCE, BIN, False)])
            self.assertEqual(CompanyKgdState.objects.get(source=DEBT_SOURCE).latest_observation.status, 'not_checked')

    def test_injected_mismatched_identity_and_debt_not_found_are_invalid(self):
        invalid = replace(success(TAXPAYER_SOURCE), data={**success(TAXPAYER_SOURCE).data, 'bin': '000000000002'})
        providers = FakeKgd({(TAXPAYER_SOURCE, BIN): invalid})
        with self.assertRaises(IngestionFailure):
            self.collect(providers=providers, kgd_service='tax_debt', force=True)
        self.assertEqual(CompanyKgdState.objects.get(source=TAXPAYER_SOURCE).latest_observation.status, 'invalid')
        self.assertEqual(len(providers.calls), 1)
        providers = FakeKgd({(DEBT_SOURCE, BIN): self.failure(DEBT_SOURCE, status=ResultStatus.NOT_FOUND)})
        with self.assertRaises(IngestionFailure):
            self.collect(providers=providers, kgd_service='tax_debt', force=True)
        self.assertEqual(CompanyKgdState.objects.get(source=DEBT_SOURCE).latest_observation.status, 'invalid')

    def test_disabled_checks_never_reuse_success_as_a_new_confirmed_attempt(self):
        self.collect(providers=FakeKgd())
        with patch('apps.ingestion.transport.HttpTransport.get_json', side_effect=AssertionError('live network')):
            with self.assertRaises(IngestionFailure):
                self.collect()
        state = CompanyKgdState.objects.get()
        self.assertEqual(state.latest_observation.status, 'not_checked')
        self.assertEqual(state.latest_observation.error_code, 'kgd_disabled')
        self.assertIsNotNone(state.last_successful_observation)

    def test_atomic_persistence_failure_does_not_publish_partial_projection(self):
        original = SourceObservation.objects.get_or_create
        def fail_debt(*args, **kwargs):
            if kwargs['source'] == DEBT_SOURCE:
                raise IntegrityError('synthetic-private-sql')
            return original(*args, **kwargs)
        with patch.object(SourceObservation.objects, 'get_or_create', side_effect=fail_debt):
            with self.assertRaises(IngestionFailure) as failure:
                self.collect(providers=FakeKgd(), kgd_service='tax_debt')
        self.assertEqual(CompanyKgdState.objects.count(), 0)
        self.assertEqual(SourceObservation.objects.count(), 0)
        self.assertNotIn('synthetic-private-sql', str(failure.exception))
        result = run_pipeline(resume=failure.exception.run_id, providers=FakeKgd())
        self.assertEqual(result.status, 'succeeded')
        self.assertEqual(CompanyKgdState.objects.count(), 2)

    @override_settings(ENABLE_KGD_CHECKS=True, KGD_PORTAL_TOKEN='synthetic-portal-token', KGD_ACCOUNT_TOKENS_JSON='{}')
    def test_debt_cache_cannot_bypass_missing_company_account_credential(self):
        self.collect(providers=FakeKgd(), kgd_service='tax_debt')
        previous = CompanyKgdState.objects.get(source=DEBT_SOURCE).last_successful_observation
        with patch('apps.ingestion.transport.HttpTransport.get_json', side_effect=AssertionError('live')):
            with self.assertRaises(IngestionFailure):
                self.collect(kgd_service='tax_debt')
        state = CompanyKgdState.objects.get(source=DEBT_SOURCE)
        self.assertEqual(state.latest_observation.status, 'not_checked')
        self.assertEqual(state.latest_observation.error_code, 'kgd_account_token_missing')
        self.assertEqual(state.last_successful_observation, previous)

    def test_lease_busy_and_lost_worker_cannot_publish_kgd_evidence(self):
        lease = RunLease.acquire()
        try:
            with self.assertRaises(IngestionBusy):
                self.collect(providers=FakeKgd())
        finally:
            lease.release()
        providers = FakeKgd()
        def steal(source, bin_number, **kwargs):
            IngestionLease.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
            RunLease.acquire().release()
            return success(source, bin_number)
        providers.kgd = steal
        with self.assertRaisesMessage(IngestionFailure, 'ingestion_lease_lost'):
            self.collect(providers=providers)
        self.assertEqual(CompanyKgdState.objects.count(), 0)
        self.assertEqual(SourceObservation.objects.count(), 0)

    def test_invalid_limits_and_unknown_company_do_not_create_run(self):
        before = IngestionRun.objects.count()
        for options in ({'total': 501}, {'total': 0}, {'company_bin': '000000000099'},
                        {'company_bin': '123'}, {'kgd_service': 'unknown'}, {'start_page': 2}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                run_pipeline(mode='kgd', providers=FakeKgd(), **options)
        self.assertEqual(IngestionRun.objects.count(), before)

    def test_cli_and_celery_share_pipeline_and_disabled_task_has_no_side_effects(self):
        run = IngestionRun.objects.create(mode='kgd', status='succeeded')
        with patch('apps.ingestion.management.commands.ingest_data.run_pipeline', return_value=run) as service:
            call_command('ingest_data', mode='kgd', company_bin=BIN, kgd_service='tax_debt', total=1, stdout=StringIO())
            self.assertEqual(service.call_args.kwargs['kgd_service'], 'tax_debt')
            self.assertEqual(service.call_args.kwargs['company_bin'], BIN)
        with patch('apps.core.tasks.run_pipeline', return_value=run) as service:
            self.assertEqual(check_kgd.run(company_bin=BIN), {'status': 'disabled'})
            service.assert_not_called()
            with override_settings(ENABLE_KGD_CHECKS=True):
                self.assertEqual(check_kgd.run(company_bin=BIN, service='tax_debt', resume=str(run.uuid))['status'], 'succeeded')
            service.assert_called_once_with(mode='kgd', company_bin=BIN, kgd_service='tax_debt', total=1, resume=str(run.uuid))


class KgdEvidenceTests(TestCase):
    def setUp(self):
        self.company = Supplier.objects.create(bin=BIN, name='Synthetic company')
        self.run_row = IngestionRun.objects.create(mode='kgd')

    def test_observation_idempotence_and_failure_with_equal_timestamp_invalidates_cache(self):
        value = success(TAXPAYER_SOURCE)
        first = record_kgd_result(self.run_row, value, self.company)
        self.assertEqual(record_kgd_result(self.run_row, value, self.company).pk, first.pk)
        failed = replace(value, status=ResultStatus.UNAVAILABLE, error_code='kgd_access_denied')
        record_kgd_result(self.run_row, failed, self.company)
        self.assertIsNone(cached_company_result(TAXPAYER_SOURCE, self.company, KgdParser.VERSION))
        self.assertEqual(CompanyKgdState.objects.get().last_successful_observation.pk, first.pk)

    def test_late_old_response_never_replaces_newer_current_result(self):
        newest = record_kgd_result(self.run_row, success(TAXPAYER_SOURCE), self.company)
        record_kgd_result(self.run_row, success(TAXPAYER_SOURCE, when=timezone.now() - timedelta(days=1)), self.company)
        state = CompanyKgdState.objects.get()
        self.assertEqual((state.latest_observation.pk, state.last_successful_observation.pk), (newest.pk, newest.pk))

    def test_success_ttl_and_parser_version_do_not_disguise_old_facts(self):
        record_kgd_result(self.run_row, success(DEBT_SOURCE, when=timezone.now() - timedelta(days=8)), self.company)
        self.assertTrue(company_kgd_statuses(self.company)[1]['stale'])
        self.assertIsNone(cached_company_result(DEBT_SOURCE, self.company, KgdParser.VERSION))
        record_kgd_result(self.run_row, success(TAXPAYER_SOURCE), self.company)
        self.assertIsNone(cached_company_result(TAXPAYER_SOURCE, self.company, 'future-parser'))

    def test_credentials_private_fields_and_unsafe_urls_are_not_persisted(self):
        value = success(DEBT_SOURCE)
        value = replace(value, source_url='https://portal.kgd.gov.kz/?personalAccountToken=synthetic-secret',
                        data={**value.data, 'owners': [{'iin': '000000000010'}], 'personalAccountToken': 'synthetic-secret'},
                        raw={**value.raw, 'taxOrgInfos': [{'taxpayerInfo': {'name': 'synthetic-private'}}]})
        observation = record_kgd_result(self.run_row, value, self.company)
        saved = json.dumps([observation.normalized_values, observation.raw_values, observation.source_url])
        self.assertNotIn('synthetic-secret', saved)
        self.assertNotIn('synthetic-private', saved)
        self.assertNotIn('owners', saved)
        failed = replace(value, status=ResultStatus.UNAVAILABLE, error_code='unsafe synthetic-secret')
        self.assertEqual(record_kgd_result(self.run_row, failed, self.company).error_code, 'kgd_source_failed')

    def test_unknown_debt_renders_no_amount_and_get_never_collects_or_writes(self):
        with (patch('apps.ingestion.providers.SourceProviders.kgd', side_effect=AssertionError('live')),
             patch('apps.ingestion.services.run_pipeline', side_effect=AssertionError('pipeline')),
             CaptureQueriesContext(connection) as queries):
            response = self.client.get(reverse('companies:detail', args=[self.company.pk]))
        self.assertContains(response, 'Not checked', count=2)
        self.assertNotContains(response, 'Overall arrears:')
        self.assertNotContains(response, 'Tax arrears: 0')
        self.assertTrue(all(query['sql'].lstrip().upper().startswith('SELECT') for query in queries))

    def test_confirmed_zero_retained_failure_and_untrusted_name_render_safely(self):
        registration = success(TAXPAYER_SOURCE)
        registration = replace(registration, data={**registration.data, 'kgd_taxpayer_name': '<img src=x onerror=alert(1)>'})
        record_kgd_result(self.run_row, registration, self.company)
        debt = success(DEBT_SOURCE)
        debt = replace(debt, data={**debt.data, **{field: '0.00' for field in AMOUNT_FIELDS.values()}})
        record_kgd_result(self.run_row, debt, self.company)
        record_kgd_result(self.run_row, replace(debt, status=ResultStatus.UNAVAILABLE, error_code='kgd_access_denied'), self.company)
        response = self.client.get(reverse('companies:detail', args=[self.company.pk]))
        self.assertContains(response, 'Overall arrears: 0.00 KZT')
        self.assertContains(response, 'Unavailable')
        self.assertContains(response, 'Retained result may be outdated')
        self.assertContains(response, '&lt;img')
        self.assertNotContains(response, '<img src=x')


class KgdMigrationTests(TransactionTestCase):
    def test_additive_migration_preserves_existing_facts_and_creates_no_false_checks(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        previous = ('ingestion', '0005_english_display_labels')
        executor.migrate([previous])
        old = executor.loader.project_state([previous]).apps
        company = old.get_model('companies', 'Supplier').objects.create(bin=BIN, name='Preserved')
        run = old.get_model('ingestion', 'IngestionRun').objects.create(mode='enrich')
        observation = old.get_model('ingestion', 'SourceObservation').objects.create(
            run=run, supplier=company, source='adata', subject_key=f'company:{BIN}', status='success',
            normalized_values={'bin': BIN, 'name': 'Preserved'}, fingerprint='a' * 64, observed_at=timezone.now())
        try:
            MigrationExecutor(connection).migrate(leaves)
            self.assertEqual(Supplier.objects.get(pk=company.pk).name, 'Preserved')
            self.assertEqual(SourceObservation.objects.get(pk=observation.pk).normalized_values, {'bin': BIN, 'name': 'Preserved'})
            self.assertEqual(CompanyKgdState.objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(leaves)
