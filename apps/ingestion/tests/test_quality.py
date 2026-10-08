from dataclasses import replace
from datetime import timedelta
from io import StringIO
import json
import re
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.companies.models import Supplier
from apps.ingestion.dto import ResultStatus, SourceResult
from apps.ingestion.models import IngestionRun, SelectedFact
from apps.ingestion.observations import cached_company_result, record_observation
from apps.ingestion.quality import build_data_quality_report
from apps.owners.models import PersonIdentity


class LatestObservationCacheTests(TestCase):
    def setUp(self):
        self.company = Supplier.objects.create(bin='000000000001', name='Synthetic company')
        self.run = IngestionRun.objects.create(mode='enrich')
        self.value = SourceResult('adata', f'company:{self.company.bin}', ResultStatus.SUCCESS,
                                  data={'bin': self.company.bin, 'name': 'Old'},
                                  observed_at=timezone.now() - timedelta(seconds=20))

    def test_newer_success_from_different_parser_prevents_old_version_cache(self):
        record_observation(self.run, self.value, self.company)
        later = replace(self.value, parser_version='2.1', observed_at=timezone.now(),
                        data={'bin': self.company.bin, 'name': 'New'})
        record_observation(self.run, later, self.company)
        self.assertIsNone(cached_company_result('adata', self.company, '2.0'))
        cached = cached_company_result('adata', self.company, '2.1')
        self.assertEqual(cached.data['name'], 'New')
        self.assertEqual(cached.observed_at, later.observed_at)
        self.assertTrue(cached.from_cache)

    def test_foreign_company_observation_cannot_be_reused(self):
        other = Supplier.objects.create(bin='000000000002', name='Other synthetic company')
        record_observation(self.run, self.value, other)
        self.assertIsNone(cached_company_result('adata', self.company))

    def test_newer_not_found_is_not_hidden_by_earlier_success(self):
        record_observation(self.run, self.value, self.company)
        record_observation(self.run, replace(self.value, status=ResultStatus.NOT_FOUND,
                                           observed_at=timezone.now(), data={}), self.company)
        self.assertIsNone(cached_company_result('adata', self.company))


class SavedQualityReportTests(TestCase):
    def setUp(self):
        self.company = Supplier.objects.create(bin='000000000001', name='Synthetic private company')
        self.run = IngestionRun.objects.create(mode='enrich')
        self.now = timezone.now()

    def save(self, source='adata', status=ResultStatus.SUCCESS, when=None):
        return record_observation(self.run, SourceResult(source, f'company:{self.company.bin}', status,
            data={'bin': self.company.bin, 'name': self.company.name},
            observed_at=when or self.now - timedelta(seconds=1)), self.company)

    def test_recent_legacy_migration_is_not_fresh_source_verification(self):
        observation = self.save('legacy', ResultStatus.NOT_CHECKED)
        SelectedFact.objects.create(supplier=self.company, field='name', observation=observation)
        report = build_data_quality_report(now=self.now)
        self.assertEqual(report['observations']['legacy'], 1)
        self.assertEqual(report['selected_facts']['legacy_or_unconfirmed'], 1)
        self.assertEqual(report['sources']['adata']['without_saved_attempt'], 1)
        self.assertEqual(report['sources']['adata']['recent_successful_latest_attempts'], 0)
        self.assertEqual(report['kgd']['states']['kgd_tax_debt']['without_saved_state'], 1)

    def test_retained_success_after_failure_and_missing_check_are_distinct(self):
        Supplier.objects.create(bin='000000000002', name='Never checked')
        self.save(when=self.now - timedelta(days=10))
        self.save(status=ResultStatus.UNAVAILABLE)
        report = build_data_quality_report(now=self.now)
        source = report['sources']['adata']
        self.assertEqual(source['without_saved_attempt'], 1)
        self.assertEqual(source['latest_statuses'], {'unavailable': 1})
        self.assertEqual(source['retained_success_after_unsuccessful_latest_attempt'], 1)
        self.assertEqual(source['recent_successful_latest_attempts'], 0)

    @override_settings(KGD_PORTAL_TOKEN='synthetic-private-credential',
        KGD_ACCOUNT_TOKENS_JSON='{"000000000001":"synthetic-account-secret"}')
    def test_report_has_counts_only_without_personal_values_or_credentials_and_no_writes(self):
        self.save()
        PersonIdentity.objects.create(scope_key='one', full_name='Synthetic private person')
        PersonIdentity.objects.create(scope_key='two', full_name='Synthetic private person')
        with (patch('requests.sessions.Session.request', side_effect=AssertionError('network')),
              CaptureQueriesContext(connection) as queries):
            report = build_data_quality_report(now=self.now)
        for query in queries:
            statement = query['sql'].lstrip().upper()
            # PostgreSQL streams QuerySet.iterator() using a SELECT cursor.
            readonly = statement.startswith('SELECT') or bool(re.match(
                r'DECLARE\s+.+\s+CURSOR\s+.+\s+FOR\s+SELECT\b', statement, re.DOTALL))
            self.assertTrue(readonly, statement.split(maxsplit=1)[0])
        self.assertEqual(report['people']['repeated_normalized_names'], {'groups': 1, 'records': 2})
        self.assertEqual(report['kgd']['configuration']['existing_companies_with_account_credential'], 1)
        text = json.dumps(report)
        for secret in (self.company.bin, self.company.name, 'Synthetic private person',
                       'synthetic-private-credential', 'synthetic-account-secret'):
            self.assertNotIn(secret, text)
        self.assertEqual(PersonIdentity.objects.count(), 2)

    @override_settings(KGD_ACCOUNT_TOKENS_JSON='invalid-private-configuration')
    def test_invalid_configuration_is_safe_and_does_not_prevent_data_audit(self):
        report = build_data_quality_report(now=self.now)
        self.assertFalse(report['kgd']['configuration']['account_configuration_valid'])
        self.assertNotIn('invalid-private-configuration', json.dumps(report))

    def test_command_emits_json_and_rejects_invalid_window(self):
        output = StringIO()
        call_command('audit_data_quality', stdout=output)
        self.assertEqual(json.loads(output.getvalue())['companies']['total'], 1)
        with self.assertRaises(CommandError):
            call_command('audit_data_quality', days=0, stdout=StringIO())
