from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.graph.models import RiskCluster
from apps.graph.services import rebuild_clusters, build_director_map
from apps.owners.models import Directorship, Ownership, PersonIdentity
from apps.core.tasks import update_all_data
from apps.ingestion.dto import SourceResult, ResultStatus
from apps.ingestion.errors import SourceError
from apps.ingestion.identities import synchronize_director, synchronize_owners
from apps.ingestion.leases import RunLease, IngestionBusy, LeaseLost
from apps.ingestion.models import (IngestionRun, IngestionLease, SourceCheckpoint, SourceObservation,
                                   SelectedFact, IdentityCandidate)
from apps.ingestion.observations import record_observation, apply_company_facts, cached_company_result
from apps.ingestion.parsers.contracts import ContractPage
from apps.ingestion.services import run_pipeline, IngestionFailure
from .helpers import FakeProviders, contract_record


class PipelineTests(TestCase):
    def page(self, number=1, ids=(1,)):
        return ContractPage(number, tuple(contract_record(i) for i in ids))

    def test_repeat_upserts_and_keeps_contract_observation_and_company_roles(self):
        providers = FakeProviders([self.page()])
        run = run_pipeline(mode='update', total=1, providers=providers)
        original = Contract.objects.get()
        run_pipeline(mode='update', total=1, providers=providers)
        contract = Contract.objects.get()
        self.assertEqual(contract.pk, original.pk)
        self.assertEqual(contract.amount, Decimal('100.01'))
        self.assertTrue(contract.customer.is_customer)
        self.assertFalse(contract.customer.is_supplier)
        self.assertTrue(contract.supplier.is_supplier)
        self.assertEqual(contract.source_observations.count(), 6)  # Contract + party facts for each run.
        self.assertTrue(SelectedFact.objects.filter(supplier=contract.customer, field='name').exists())
        providers.page_calls.clear()
        self.assertEqual(run_pipeline(resume=run.uuid, providers=providers).pk, run.pk)
        self.assertEqual(providers.page_calls, [])

    def test_customer_later_supplier_promotes_without_duplicate(self):
        first = self.page()
        second = ContractPage(1, (contract_record(2, supplier='000000000002', customer='000000000003'),))
        run_pipeline(total=1, providers=FakeProviders([first]))
        run_pipeline(mode='update', total=1, providers=FakeProviders([second]))
        company = Supplier.objects.get(bin='000000000002')
        self.assertTrue(company.is_supplier and company.is_customer)
        self.assertEqual(Supplier.objects.count(), 3)

    def test_failure_resume_retries_page_without_repeating_successful_page(self):
        providers = FakeProviders([self.page()])
        providers.pages[2] = SourceError('source_http_503')
        with self.assertRaises(IngestionFailure) as failure:
            run_pipeline(total=2, providers=providers)
        run = IngestionRun.objects.get(uuid=failure.exception.run_id)
        self.assertEqual((run.stage, run.next_page, run.status), ('contracts', 2, 'partial'))
        self.assertTrue(run.issues.filter(page=2, resolved=False).exists())
        fixed = FakeProviders([self.page(2, (2,))])
        result = run_pipeline(resume=run.uuid, providers=fixed)
        self.assertEqual(fixed.page_calls, [2])
        self.assertEqual(result.attempts, 2)
        self.assertFalse(result.issues.filter(resolved=False).exists())
        self.assertEqual(Contract.objects.count(), 2)

    def test_partial_page_unchanged_resumes_offset_changed_page_replays(self):
        page = self.page(ids=(1, 2, 3))
        run_pipeline(mode='initial', total=1, providers=FakeProviders([page]))
        checkpoint = SourceCheckpoint.objects.get(stream='initial')
        self.assertEqual((checkpoint.next_page, checkpoint.offset), (1, 1))
        run_pipeline(mode='initial', total=1, providers=FakeProviders([page]))
        self.assertEqual(Contract.objects.count(), 2)
        changed = self.page(ids=(4, 1, 2, 3))
        run_pipeline(mode='initial', total=1, providers=FakeProviders([changed]))
        self.assertTrue(Contract.objects.filter(contract_number='demo-4').exists())

    def test_regular_update_starts_from_head_initial_checkpoint_is_independent(self):
        run_pipeline(mode='initial', total=1, providers=FakeProviders([self.page()]))
        providers = FakeProviders([self.page(ids=(2,))])
        run_pipeline(mode='update', total=1, providers=providers)
        self.assertEqual(providers.page_calls, [1])
        self.assertEqual(SourceCheckpoint.objects.get(stream='initial').next_page, 2)

    def test_failed_page_has_no_partial_contracts_observations_or_cursor_advance(self):
        providers = FakeProviders([self.page(ids=(1, 2))])
        original = Contract.objects.update_or_create
        calls = 0
        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise IntegrityError('private-sql-marker')
            return original(*args, **kwargs)
        with patch.object(Contract.objects, 'update_or_create', side_effect=fail_second):
            with self.assertRaises(IngestionFailure) as failure:
                run_pipeline(total=2, providers=providers)
        run = IngestionRun.objects.get(uuid=failure.exception.run_id)
        self.assertEqual(run.next_page, 1)
        self.assertEqual(Contract.objects.count(), 0)
        self.assertFalse(SourceObservation.objects.filter(run=run, status='success').exists())
        self.assertNotIn('private-sql-marker', str(failure.exception))

    def test_enrichment_failure_resume_does_not_fetch_contracts_and_retries_failed_company(self):
        first = Supplier.objects.create(bin='000000000001', name='First')
        second = Supplier.objects.create(bin='000000000002', name='Second')
        providers = FakeProviders(results={('adata', first.bin): {'name': 'Valid'},
                                           ('adata', second.bin): SourceError('offline')})
        with self.assertRaises(IngestionFailure) as failure:
            run_pipeline(mode='enrich', providers=providers)
        fixed = FakeProviders(results={('adata', second.bin): {'name': 'Recovered'}})
        run = run_pipeline(resume=failure.exception.run_id, providers=fixed)
        self.assertEqual(run.stage, 'complete')
        self.assertEqual(fixed.page_calls, [])
        self.assertEqual({value for _, value in fixed.company_calls}, {second.bin})
        second.refresh_from_db()
        self.assertEqual(second.name, 'Recovered')

    def test_cluster_failure_resume_only_cluster_stage(self):
        providers = FakeProviders([self.page()])
        with self.assertRaises(IngestionFailure) as failure:
            run_pipeline(total=1, providers=providers, cluster_builder=lambda: (_ for _ in ()).throw(ValueError('fixture')))
        fixed = FakeProviders()
        run = run_pipeline(resume=failure.exception.run_id, providers=fixed)
        self.assertEqual((fixed.page_calls, fixed.company_calls), ([], []))
        self.assertEqual(run.status, 'succeeded')

    def test_busy_lease_never_fetches_or_creates_run(self):
        lease = RunLease.acquire()
        providers = FakeProviders()
        count = IngestionRun.objects.count()
        try:
            with self.assertRaises(IngestionBusy):
                run_pipeline(providers=providers)
            self.assertEqual(IngestionRun.objects.count(), count)
            self.assertEqual(providers.page_calls, [])
        finally:
            lease.release()

    def test_expired_owner_cannot_publish_or_release_replacement_lease(self):
        lease = RunLease.acquire()
        run = IngestionRun.objects.create(mode='initial')
        lease.attach(run)
        IngestionLease.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        replacement = RunLease.acquire()
        run.refresh_from_db()
        self.assertEqual(run.error_code, 'lease_expired')
        with transaction.atomic(), self.assertRaises(LeaseLost):
            lease.ensure_owned()
        lease.release()
        replacement.heartbeat()
        replacement.release()

    def test_loss_during_network_fetch_fences_all_page_writes(self):
        providers = FakeProviders([self.page()])
        original = providers.contract_page
        def steal(number):
            IngestionLease.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
            RunLease.acquire().release()
            return original(number)
        providers.contract_page = steal
        with self.assertRaisesMessage(IngestionFailure, 'ingestion_lease_lost'):
            run_pipeline(total=1, providers=providers)
        self.assertEqual(Contract.objects.count(), 0)

    def test_commands_and_celery_use_same_service_with_resume(self):
        run = IngestionRun.objects.create(mode='initial', status='succeeded')
        with patch('apps.ingestion.management.commands.ingest_data.run_pipeline', return_value=run) as service:
            call_command('import_contracts', total=2, stdout=StringIO())
            self.assertEqual(service.call_args.kwargs['total'], 2)
            call_command('enrich_suppliers', stdout=StringIO())
            self.assertEqual(service.call_args.kwargs['mode'], 'enrich')
        with override_settings(ENABLE_SCHEDULED_IMPORT=True), patch('apps.core.tasks.run_pipeline', return_value=run) as service:
            update_all_data.run(resume=str(run.uuid))
            service.assert_called_once_with(mode='update', total=500, resume=str(run.uuid))
        with self.assertRaises(CommandError):
            call_command('link_directors')

    def test_status_command_reads_progress_without_live_calls(self):
        run = run_pipeline(providers=FakeProviders())
        output = StringIO()
        with patch('apps.ingestion.providers.SourceProviders.company', side_effect=AssertionError('live')):
            call_command('ingestion_status', stdout=output)
        self.assertIn(str(run.uuid), output.getvalue())


class FactsAndIdentityTests(TestCase):
    def setUp(self):
        self.run = IngestionRun.objects.create(mode='enrich')
        self.company = Supplier.objects.create(bin='000000000001', name='Original')

    def observe(self, supplier=None, source='goszakup_supplier', when=None, status=ResultStatus.SUCCESS, raw=None, **data):
        supplier = supplier or self.company
        result = SourceResult(source, f'company:{supplier.bin}', status, data={'bin': supplier.bin, **data},
                              raw=raw or data, observed_at=when or timezone.now())
        return record_observation(self.run, result, supplier)

    def test_name_only_match_produces_candidate_and_no_confirmed_graph_or_detail_link(self):
        other = Supplier.objects.create(bin='000000000002', name='Other')
        for company in (self.company, other):
            synchronize_director(company, self.observe(company, director_name='Synthetic namesake'))
        roles = list(Directorship.objects.order_by('pk'))
        self.assertNotEqual(roles[0].person_identity_id, roles[1].person_identity_id)
        self.assertEqual(IdentityCandidate.objects.get().status, 'pending')
        self.assertEqual(rebuild_clusters()['groups'], 0)
        response = self.client.get(reverse('companies:detail', args=[self.company.pk]))
        self.assertEqual(response.context['related_by_director'].count(), 0)

    def test_same_confirmed_iin_shares_person_and_different_iin_rejects_candidate(self):
        other = Supplier.objects.create(bin='000000000002', name='Other')
        third = Supplier.objects.create(bin='000000000003', name='Third')
        for company, iin in ((self.company, '000000000010'), (other, '000000000010'), (third, '000000000011')):
            synchronize_director(company, self.observe(company, director_name='Synthetic person',
                director_iin=iin, director_iin_verified=True))
        self.assertEqual(PersonIdentity.objects.count(), 2)
        director_map = build_director_map([self.company, other, third])
        self.assertEqual(director_map[self.company.pk], director_map[other.pk])
        self.assertFalse(director_map[self.company.pk] & director_map[third.pk])
        self.assertTrue(IdentityCandidate.objects.filter(status='rejected').exists())
        response = self.client.get(reverse('companies:detail', args=[self.company.pk]))
        self.assertEqual(list(response.context['related_by_director']), [other])

    def test_director_change_keeps_observed_history_without_invented_legal_end(self):
        earlier = timezone.now() - timedelta(days=2)
        first = self.observe(when=earlier, director_name='First')
        synchronize_director(self.company, first)
        second = self.observe(director_name='Second')
        synchronize_director(self.company, second)
        old = Directorship.objects.get(person_identity__full_name='First')
        self.assertFalse(old.is_current)
        self.assertIsNone(old.end_date)
        self.assertEqual(old.observed_until, second.observed_at)
        synchronize_director(self.company, second)
        self.assertEqual(Directorship.objects.count(), 2)

    def test_reappointment_creates_new_episode(self):
        time = timezone.now() - timedelta(days=3)
        for index, name in enumerate(('First', 'Second', 'First')):
            synchronize_director(self.company, self.observe(when=time + timedelta(days=index), director_name=name))
        self.assertEqual(Directorship.objects.count(), 3)
        self.assertEqual(Directorship.objects.filter(is_current=True).count(), 1)

    def test_missing_director_is_unknown_explicit_absence_retires(self):
        synchronize_director(self.company, self.observe(director_name='First'))
        apply_company_facts(self.company)
        self.observe(director_name=None)
        apply_company_facts(self.company)
        self.assertTrue(Directorship.objects.get().is_current)
        self.observe(director_name='', director_absent=True)
        apply_company_facts(self.company)
        self.assertFalse(Directorship.objects.get().is_current)
        self.company.refresh_from_db()
        self.assertEqual(self.company.director_name, '')

    def test_out_of_order_roles_are_rejected(self):
        synchronize_director(self.company, self.observe(director_name='First'))
        with transaction.atomic(), self.assertRaises(ValueError):
            synchronize_director(self.company, self.observe(when=timezone.now() - timedelta(days=1), director_name='Second'))
        self.assertEqual(Directorship.objects.filter(is_current=True).get().person_identity.full_name, 'First')

    def test_director_does_not_imply_owner_and_unknown_share_remains_null(self):
        synchronize_director(self.company, self.observe(director_name='First'))
        self.assertEqual(Ownership.objects.count(), 0)
        observation = self.observe(owners_complete=True, owners=[{'full_name': 'Explicit owner'}])
        synchronize_owners(self.company, observation)
        self.assertIsNone(Ownership.objects.get().share_percent)
        self.assertFalse(Ownership.objects.get().owner.has_tax_debt)

    def test_complete_owner_list_retires_only_same_source_roles(self):
        earlier = timezone.now() - timedelta(days=1)
        synchronize_owners(self.company, self.observe(when=earlier, owners_complete=True, owners=[{'full_name': 'First', 'share_percent': '25.50'}]))
        synchronize_owners(self.company, self.observe(source='adata', when=earlier, owners_complete=True, owners=[{'full_name': 'Second'}]))
        synchronize_owners(self.company, self.observe(owners_complete=True, owners=[]))
        self.assertFalse(Ownership.objects.get(source='goszakup_supplier').is_current)
        self.assertTrue(Ownership.objects.get(source='adata').is_current)

    def test_invalid_share_and_interval_do_not_create_partial_roles(self):
        for item in ({'full_name': 'Owner', 'share_percent': '101'},
                     {'full_name': 'Owner', 'start_date': '2025-02-01', 'end_date': '2025-01-01'}):
            with self.subTest(item=item), transaction.atomic(), self.assertRaises(ValueError):
                synchronize_owners(self.company, self.observe(owners_complete=True, owners=[item]))
        self.assertEqual(Ownership.objects.count(), 0)

    def test_source_priority_and_fallback_keep_provenance_and_original_values(self):
        self.observe(name='Registry', email='registry@example.test', raw={'name': ' Registry ', 'email': 'registry@example.test'})
        adata = self.observe(source='adata', name='Adata', email='adata@example.test')
        apply_company_facts(self.company)
        self.assertEqual(self.company.name, 'Registry')
        self.assertEqual(self.company.email, 'adata@example.test')
        self.assertEqual(SelectedFact.objects.get(supplier=self.company, field='email').observation_id, adata.pk)
        self.observe(status=ResultStatus.UNAVAILABLE)
        apply_company_facts(self.company)
        self.assertEqual(self.company.name, 'Registry')
        self.assertEqual(SelectedFact.objects.get(supplier=self.company, field='name').observation.raw_values['name'], ' Registry ')

    def test_observation_deduplicates_within_run_and_does_not_keep_unknown_secrets(self):
        when = timezone.now()
        first = self.observe(when=when, name='Demo', raw={'name': 'Demo', 'password': 'private',
            'owners': [{'full_name': 'Owner', 'token': 'private'}]})
        second = self.observe(when=when, name='Demo', raw={'name': 'Demo', 'password': 'other',
            'owners': [{'full_name': 'Owner', 'token': 'other'}]})
        self.assertEqual(first.pk, second.pk)
        self.assertNotIn('password', first.raw_values)
        self.assertNotIn('token', first.raw_values['owners'][0])

    def test_statuses_not_found_failure_unknown_remain_distinct(self):
        for status in (ResultStatus.NOT_FOUND, ResultStatus.UNAVAILABLE, ResultStatus.NOT_CHECKED):
            self.observe(status=status)
        self.assertEqual(set(self.company.source_observations.values_list('status', flat=True)),
                         {'not_found', 'unavailable', 'not_checked'})

    @override_settings(INGESTION_SOURCE_CACHE_SECONDS=60)
    def test_cache_has_ttl_parser_version_and_newer_failure_invalidation(self):
        self.observe(name='Fresh')
        self.assertTrue(cached_company_result('goszakup_supplier', self.company).from_cache)
        self.assertIsNone(cached_company_result('goszakup_supplier', self.company, version='3.0'))
        self.observe(status=ResultStatus.UNAVAILABLE)
        self.assertIsNone(cached_company_result('goszakup_supplier', self.company))
        other = Supplier.objects.create(bin='000000000002', name='Old')
        self.observe(other, when=timezone.now() - timedelta(seconds=61), name='Old')
        self.assertIsNone(cached_company_result('goszakup_supplier', other))

    def test_many_service_contacts_never_form_company_cluster(self):
        for index in range(1, 11):
            Supplier.objects.get_or_create(bin=f'{index:012}', defaults={'name': f'Company {index}', 'email': 'SUPPORT@ADATA.KZ'})
        self.company.email = 'SUPPORT@ADATA.KZ'
        self.company.save()
        self.assertEqual(rebuild_clusters()['groups'], 0)
