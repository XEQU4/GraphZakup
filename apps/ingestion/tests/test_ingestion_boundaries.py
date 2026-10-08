"""Synthetic service regressions for repeated pages and parser-version evidence."""
from unittest.mock import patch

from django.test import TestCase

from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.ingestion.errors import SourceError
from apps.ingestion.models import IngestionRun, SourceCheckpoint, SourceObservation
from apps.ingestion.parsers.contracts import ContractPage, ContractRegistryParser
from apps.ingestion.providers import SourceProviders
from apps.ingestion.services import IngestionFailure, run_pipeline, save_contract
from .helpers import FakeProviders, contract_record


class IngestionBoundaryTests(TestCase):
    def page(self, number, identifiers):
        return ContractPage(number, tuple(contract_record(identifier) for identifier in identifiers))

    def test_repeated_complete_page_stops_and_resume_preserves_guard_and_cursor(self):
        first = self.page(1, [1])
        repeated = self.page(2, [1])
        with self.assertRaisesMessage(IngestionFailure, 'contract_page_repeated') as failure:
            run_pipeline(total=2, providers=FakeProviders([first, repeated]), cluster_builder=lambda: {'synthetic': True})
        run = IngestionRun.objects.get(uuid=failure.exception.run_id)
        self.assertEqual((run.stage, run.next_page, run.offset), ('contracts', 2, 0))
        self.assertEqual(run.counters['contracts'], 1)
        self.assertEqual(run.counters['last_complete_contract_page']['number'], 1)
        self.assertEqual(SourceCheckpoint.objects.get(stream='update').next_page, 2)
        self.assertEqual(Contract.objects.count(), 1)
        with self.assertRaisesMessage(IngestionFailure, 'contract_page_repeated'):
            run_pipeline(resume=run.uuid, providers=FakeProviders([repeated]), cluster_builder=lambda: {'synthetic': True})
        run.refresh_from_db()
        self.assertEqual(run.counters['contracts'], 1)
        self.assertEqual(run.next_page, 2)
        fixed = FakeProviders([self.page(2, [2])])
        finished = run_pipeline(resume=run.uuid, providers=fixed, cluster_builder=lambda: {'synthetic': True})
        self.assertEqual(finished.status, 'succeeded')
        self.assertEqual(fixed.page_calls, [2])
        self.assertEqual(finished.counters['contracts'], 2)
        self.assertFalse(finished.issues.filter(resolved=False).exists())
        self.assertEqual(Contract.objects.count(), 2)

    def test_exact_partial_page_replay_keeps_pending_record_and_parser_version(self):
        page = self.page(1, [1, 2])
        first = run_pipeline(mode='initial', total=1, providers=FakeProviders([page]), cluster_builder=lambda: {'synthetic': True})
        original = Contract.objects.get()
        self.assertEqual((first.next_page, first.offset), (1, 1))
        second = run_pipeline(mode='initial', total=1, providers=FakeProviders([page]), cluster_builder=lambda: {'synthetic': True})
        self.assertEqual((second.next_page, second.offset), (2, 0))
        self.assertEqual(Contract.objects.get(contract_number=original.contract_number).pk, original.pk)
        self.assertEqual(Contract.objects.count(), 2)
        self.assertEqual(set(SourceObservation.objects.filter(source='goszakup_contracts', status='success')
            .values_list('parser_version', flat=True)), {SourceProviders.VERSION})

    def test_service_error_observation_uses_the_active_provider_parser_version(self):
        company = Supplier.objects.create(bin='000000000001', name='Synthetic company')
        providers = FakeProviders(results={('goszakup_supplier', company.bin): SourceError('source_http_503')})
        providers.VERSION = 'synthetic-2.1'
        with self.assertRaises(IngestionFailure) as failure:
            run_pipeline(mode='enrich', providers=providers, cluster_builder=lambda: {'synthetic': True})
        run = IngestionRun.objects.get(uuid=failure.exception.run_id)
        observation = SourceObservation.objects.get(run=run, source='goszakup_supplier')
        self.assertEqual(observation.status, 'unavailable')
        self.assertEqual(observation.parser_version, providers.VERSION)
        self.assertEqual(observation.error_code, 'source_result_invalid')

    def test_existing_external_contract_id_cannot_be_imported_under_a_second_number(self):
        run = IngestionRun.objects.create(mode='initial')
        original = save_contract(run, contract_record(123))
        counts = (Supplier.objects.count(), Contract.objects.count(), SourceObservation.objects.count())
        changed = contract_record(123, supplier='000000000099', customer='000000000100')
        changed['contract_number'] = 'synthetic-renumbered-contract'
        with self.assertRaisesMessage(ValueError, 'contract_external_id_conflict'):
            save_contract(run, changed)
        self.assertEqual((Supplier.objects.count(), Contract.objects.count(), SourceObservation.objects.count()), counts)
        self.assertEqual(Contract.objects.get().pk, original.pk)
        self.assertFalse(Supplier.objects.filter(bin__in=['000000000099', '000000000100']).exists())

    def test_contract_and_party_provenance_use_the_active_registry_host(self):
        run = IngestionRun.objects.create(mode='initial')
        with patch.object(ContractRegistryParser, 'BASE_URL', 'https://old.goszakup.gov.kz'):
            save_contract(run, contract_record(123))
        self.assertEqual(set(run.observations.values_list('source_url', flat=True)),
                         {'https://old.goszakup.gov.kz/ru/egzcontract/cpublic/show/123'})
