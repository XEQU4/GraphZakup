from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.companies.models import Supplier
from apps.ingestion.dto import ResultStatus, SourceResult
from apps.ingestion.errors import SourceError
from apps.ingestion.models import IngestionRun, SourceObservation
from apps.ingestion.observations import record_observation
from apps.ingestion.parsers.contracts import ContractPage
from apps.ingestion.services import IngestionFailure, run_pipeline
from .helpers import FakeProviders, contract_record


class BoundedEnrichmentTests(TestCase):
    def setUp(self):
        self.first = Supplier.objects.create(bin='000000000001', name='First')
        self.second = Supplier.objects.create(bin='000000000002', name='Second', is_supplier=False, is_customer=True)
        self.third = Supplier.objects.create(bin='000000000003', name='Third')
        self.ingestion_run = IngestionRun.objects.create(mode='enrich', status='succeeded')

    def observe(self, company, source='adata', status=ResultStatus.SUCCESS, when=None, version=FakeProviders.VERSION):
        return record_observation(self.ingestion_run, SourceResult(
            source, f'company:{company.bin}', status, parser_version=version,
            observed_at=when or timezone.now(),
            data={'bin': company.bin, 'name': company.name} if status == ResultStatus.SUCCESS else {},
        ), company)

    def execute(self, providers=None, **options):
        return run_pipeline(mode='enrich', providers=providers or FakeProviders(),
                            cluster_builder=lambda: {'synthetic': True}, **options)

    def test_total_bounds_ordered_companies_and_includes_customers(self):
        providers = FakeProviders()
        result = self.execute(providers, force=True, total=2)
        self.assertEqual(result.options['company_ids'], [self.first.pk, self.second.pk])
        self.assertEqual(result.options['company_sources'], list(providers.COMPANY_SOURCES))
        self.assertEqual(result.options['selection_parser_version'], providers.VERSION)
        self.assertEqual(providers.page_calls, [])
        self.assertEqual(providers.company_calls, [
            (source, company.bin) for company in (self.first, self.second) for source in providers.COMPANY_SOURCES
        ])
        self.assertEqual(result.counters['companies_checked'], 2)
        self.assertFalse(SourceObservation.objects.filter(run=result, supplier=self.third).exists())

    def test_freshness_filters_before_limit_and_ignores_aggregate_timestamp(self):
        self.observe(self.first)
        Supplier.objects.filter(pk=self.second.pk).update(adata_updated_at=timezone.now())
        providers = FakeProviders()
        result = self.execute(providers, total=1, company_sources=['adata'])
        self.assertEqual(result.options['company_ids'], [self.second.pk])
        self.assertEqual(providers.company_calls, [('adata', self.second.bin)])

    def test_bin_targets_one_existing_customer_and_force_overrides_freshness(self):
        self.observe(self.second)
        providers = FakeProviders()
        result = self.execute(providers, company_bin=self.second.bin, total=1, company_sources=['adata'])
        self.assertEqual(result.options['company_ids'], [])
        self.assertEqual(result.stage, 'complete')
        self.assertEqual(providers.company_calls, [])
        forced = self.execute(providers, force=True, company_bin=self.second.bin, total=1, company_sources=['adata'])
        self.assertEqual(forced.options['company_ids'], [self.second.pk])
        self.assertEqual(providers.company_calls, [('adata', self.second.bin)])

    def test_subset_success_does_not_freshen_unrequested_source(self):
        providers = FakeProviders(results={('adata', self.first.bin): {'name': 'Adata name'}})
        result = self.execute(providers, company_bin=self.first.bin, total=1, company_sources=['adata'])
        self.assertEqual(providers.company_calls, [('adata', self.first.bin)])
        self.assertEqual(set(result.observations.values_list('source', flat=True)), {'adata'})
        self.first.refresh_from_db()
        self.assertIsNone(self.first.adata_updated_at)
        fresh_providers = FakeProviders()
        skipped = self.execute(fresh_providers, company_bin=self.first.bin, total=1, company_sources=['adata'])
        self.assertEqual(skipped.options['company_ids'], [])
        self.assertEqual(fresh_providers.company_calls, [])
        other = FakeProviders()
        pending = self.execute(other, company_bin=self.first.bin, total=1, company_sources=['goszakup_supplier'])
        self.assertEqual(pending.options['company_ids'], [self.first.pk])
        self.assertEqual(other.company_calls, [('goszakup_supplier', self.first.bin)])

    def test_complete_source_selection_keeps_legacy_timestamp_semantics(self):
        providers = FakeProviders(results={('adata', self.first.bin): {'name': 'Saved name'}})
        self.execute(providers, company_bin=self.first.bin, total=1)
        self.first.refresh_from_db()
        self.assertIsNotNone(self.first.adata_updated_at)

    def test_latest_failure_supersedes_older_success_for_selection(self):
        self.observe(self.first, when=timezone.now() - timedelta(minutes=1))
        self.observe(self.first, status=ResultStatus.UNAVAILABLE)
        providers = FakeProviders()
        result = self.execute(providers, company_bin=self.first.bin, total=1, company_sources=['adata'])
        self.assertEqual(result.options['company_ids'], [self.first.pk])
        self.assertEqual(providers.company_calls, [('adata', self.first.bin)])

    def test_latest_incompatible_version_cannot_reuse_earlier_success(self):
        self.observe(self.first, when=timezone.now() - timedelta(minutes=1))
        self.observe(self.first, version='previous-parser')
        providers = FakeProviders()
        result = self.execute(providers, company_bin=self.first.bin, total=1, company_sources=['adata'])
        self.assertEqual(result.options['company_ids'], [self.first.pk])
        self.assertEqual(providers.company_calls, [('adata', self.first.bin)])

    def test_expired_and_old_version_observations_are_selected(self):
        self.observe(self.first, when=timezone.now() - timedelta(days=8))
        self.observe(self.second, version='previous-parser')
        providers = FakeProviders()
        result = self.execute(providers, total=2, company_sources=['adata'])
        self.assertEqual(result.options['company_ids'], [self.first.pk, self.second.pk])
        self.assertEqual(providers.company_calls, [('adata', self.first.bin), ('adata', self.second.bin)])

    def test_current_confirmed_absence_is_fresh_and_failure_is_not_absence(self):
        self.observe(self.first, status=ResultStatus.NOT_FOUND)
        self.observe(self.second, status=ResultStatus.NOT_CHECKED)
        providers = FakeProviders()
        result = self.execute(providers, total=1, company_sources=['adata'])
        self.assertEqual(result.options['company_ids'], [self.second.pk])
        self.assertEqual(providers.company_calls, [('adata', self.second.bin)])

    def test_foreign_supplier_or_subject_observation_does_not_freshen_company(self):
        # Corrupt legacy metadata is not an exact company observation.
        observation = self.observe(self.first)
        SourceObservation.objects.filter(pk=observation.pk).update(supplier=self.second)
        other = self.observe(self.first, source='goszakup_supplier')
        SourceObservation.objects.filter(pk=other.pk).update(subject_key='company:000000000099')
        providers = FakeProviders()
        result = self.execute(providers, company_bin=self.first.bin, total=1)
        self.assertEqual(result.options['company_ids'], [self.first.pk])
        self.assertEqual(providers.company_calls, [(source, self.first.bin) for source in providers.COMPANY_SOURCES])

    def test_resume_retains_company_ids_and_sources_despite_new_companies_and_parameters(self):
        providers = FakeProviders(results={('adata', self.first.bin): {'name': 'First enriched'},
                                           ('adata', self.second.bin): SourceError('offline')})
        with self.assertRaises(IngestionFailure) as failure:
            self.execute(providers, total=2, company_sources=['adata'])
        previous = IngestionRun.objects.get(uuid=failure.exception.run_id)
        self.assertEqual(previous.options['company_ids'], [self.first.pk, self.second.pk])
        fourth = Supplier.objects.create(bin='000000000004', name='New after selection')
        Supplier.objects.filter(pk=self.second.pk).update(adata_updated_at=timezone.now())
        fixed = FakeProviders(results={('adata', self.second.bin): {'name': 'Second recovered'}})
        result = run_pipeline(resume=previous.uuid, total=1000, force=True, company_bin=fourth.bin,
                              company_sources=['goszakup_supplier'], providers=fixed,
                              cluster_builder=lambda: {'synthetic': True})
        self.assertEqual(result.options, previous.options)
        self.assertEqual(fixed.company_calls, [('adata', self.second.bin)])
        self.assertEqual(fixed.page_calls, [])
        self.assertFalse(result.issues.filter(resolved=False).exists())
        self.assertEqual(result.attempts, 2)

    def test_invalid_bounded_options_create_no_run_and_make_no_source_call(self):
        invalid = [
            ({'total': 1001}, 'invalid_enrichment_options'),
            ({'start_page': 1}, 'invalid_enrichment_options'),
            ({'kgd_service': 'taxpayer'}, 'invalid_enrichment_options'),
            ({'company_sources': []}, 'invalid_company_sources'),
            ({'company_sources': ['adata', 'adata']}, 'invalid_company_sources'),
            ({'company_sources': ['other']}, 'invalid_company_sources'),
            ({'company_sources': 'adata'}, 'invalid_company_sources'),
            ({'company_bin': 'invalid'}, 'invalid_bin'),
            ({'company_bin': '000000000099'}, 'enrichment_company_not_found'),
        ]
        providers = FakeProviders()
        count = IngestionRun.objects.count()
        for options, code in invalid:
            with self.subTest(options=options), self.assertRaisesMessage(ValueError, code):
                self.execute(providers, **options)
            self.assertEqual(IngestionRun.objects.count(), count)
        self.assertEqual(providers.company_calls, [])
        self.assertEqual(providers.page_calls, [])

    def test_legacy_unbounded_incomplete_run_requires_new_selection(self):
        legacy = IngestionRun.objects.create(mode='enrich', stage='enrichment', status='partial',
                                            options={'total': 500, 'force': False, 'days': 7})
        providers = FakeProviders()
        with self.assertRaisesMessage(ValueError, 'unbounded_enrichment_run_requires_new_run'):
            run_pipeline(resume=legacy.uuid, providers=providers)
        legacy.status = 'succeeded'
        legacy.save(update_fields=['status'])
        self.assertEqual(run_pipeline(resume=legacy.uuid, providers=providers).pk, legacy.pk)
        self.assertEqual(providers.company_calls, [])

    def test_import_total_still_limits_contracts_without_bounding_automatic_enrichment(self):
        providers = FakeProviders([ContractPage(1, (contract_record(1),))])
        result = run_pipeline(mode='update', total=1, providers=providers,
                              cluster_builder=lambda: {'synthetic': True})
        self.assertEqual(result.counters['contracts'], 1)
        self.assertEqual(result.counters['companies_checked'], 3)
        self.assertEqual({company for _, company in providers.company_calls},
                         {self.first.bin, self.second.bin, self.third.bin})
        count = IngestionRun.objects.count()
        with self.assertRaisesMessage(ValueError, 'company_sources_require_enrich_mode'):
            run_pipeline(mode='update', company_sources=['adata'], providers=providers)
        self.assertEqual(IngestionRun.objects.count(), count)

    def test_cli_passes_explicit_source_and_bin_to_the_single_service(self):
        with patch('apps.ingestion.management.commands.ingest_data.run_pipeline',
                   return_value=self.ingestion_run) as service:
            call_command('ingest_data', '--mode', 'enrich', '--total', '1',
                         '--company-bin', self.second.bin, '--company-source', 'adata', stdout=StringIO())
        self.assertEqual(service.call_args.kwargs['mode'], 'enrich')
        self.assertEqual(service.call_args.kwargs['total'], 1)
        self.assertEqual(service.call_args.kwargs['company_bin'], self.second.bin)
        self.assertEqual(service.call_args.kwargs['company_sources'], ['adata'])
