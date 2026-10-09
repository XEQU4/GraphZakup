from unittest.mock import Mock, patch
from django.test import TestCase
from apps.contracts.models import Contract
from apps.ingestion.errors import SourceError
from apps.ingestion.models import IngestionRun, SourceObservation
from apps.ingestion.parsers.contracts import ContractPage
from apps.ingestion.services import IngestionFailure, run_pipeline
from .helpers import FakeProviders, contract_record


class ContractSliceTests(TestCase):
    def provider(self, count=3):
        provider = FakeProviders([ContractPage(1, tuple(contract_record(i) for i in range(1, count+1)))])
        provider.complete_contract = Mock(side_effect=lambda row: row)
        return provider

    def test_only_selected_slice_fetches_parties_and_input_fingerprint_stays_stable(self):
        provider = self.provider()
        first = run_pipeline(mode='initial', total=1, contracts_only=True, providers=provider)
        self.assertEqual(provider.complete_contract.call_count, 1)
        self.assertEqual(first.offset, 1)
        provider.complete_contract.reset_mock()
        second = run_pipeline(mode='initial', total=1, contracts_only=True, providers=provider)
        self.assertEqual(second.offset, 2)
        self.assertEqual(provider.complete_contract.call_args.args[0]['contract_gos_id'], 2)

    def test_invalid_party_is_quarantined_without_losing_other_contracts(self):
        provider = self.provider()
        provider.complete_contract.side_effect = [contract_record(1), SourceError('contract_party_identifier_invalid'), contract_record(3)]
        with self.assertRaises(IngestionFailure) as failure:
            run_pipeline(total=3, contracts_only=True, providers=provider)
        run = IngestionRun.objects.get(uuid=failure.exception.run_id)
        self.assertEqual(run.status, 'partial')
        self.assertEqual(run.error_code, 'contract_parties_incomplete')
        self.assertEqual(run.counters['contract_rows_checked'], 3)
        self.assertEqual(run.counters['contracts_skipped'], 1)
        self.assertEqual(Contract.objects.count(), 2)
        self.assertTrue(run.issues.filter(subject_key='contract:2', resolved=False).exists())
        self.assertEqual(SourceObservation.objects.get(run=run, subject_key='contract:2').status, 'invalid')

    def test_network_error_does_not_skip_a_record_or_advance_checkpoint(self):
        provider = self.provider()
        provider.complete_contract.side_effect = [contract_record(1), SourceError('source_http_503')]
        with self.assertRaises(IngestionFailure) as failure:
            run_pipeline(total=3, contracts_only=True, providers=provider)
        run = IngestionRun.objects.get(uuid=failure.exception.run_id)
        self.assertEqual(Contract.objects.count(), 0)
        self.assertEqual((run.next_page, run.offset), (1, 0))

    def test_all_unsupported_parties_stop_at_requested_budget(self):
        provider = self.provider()
        provider.complete_contract.side_effect = SourceError('contract_party_identifier_missing')
        with self.assertRaises(IngestionFailure):
            run_pipeline(total=2, contracts_only=True, providers=provider)
        self.assertEqual(provider.complete_contract.call_count, 2)
        self.assertEqual(provider.page_calls, [1])
        self.assertEqual(Contract.objects.count(), 0)
