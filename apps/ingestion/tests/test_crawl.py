from datetime import timedelta
from unittest.mock import Mock

from django.test import TestCase
from django.utils import timezone

from apps.contracts.models import Contract
from apps.ingestion.crawl import collect_contract_slice, crawl_state
from apps.ingestion.errors import SourceError
from apps.ingestion.models import ContractRetry, IngestionIssue, SourceObservation
from apps.ingestion.parsers.contracts import ContractPage
from .helpers import FakeProviders, contract_record


class CrawlTests(TestCase):
    def provider(self, pages):
        provider = FakeProviders([ContractPage(n, tuple(contract_record(i) for i in ids)) for n, ids in pages.items()])
        provider.VERSION = '2.3'
        provider.complete_contract = Mock(side_effect=lambda row: row)
        return provider

    def test_restart_consumes_frozen_page_even_if_registry_head_changes(self):
        provider = self.provider({1: [3, 2, 1]})
        collect_contract_slice('history', provider, limit=1)
        replacement = self.provider({1: [6, 5, 4]})
        collect_contract_slice('history', replacement, limit=2)
        self.assertEqual(replacement.page_calls, [])
        self.assertEqual(set(Contract.objects.values_list('contract_gos_id', flat=True)), {1, 2, 3})
        self.assertEqual(crawl_state('history')['page'], 2)

    def test_head_catches_more_than_one_batch_until_previous_boundary(self):
        provider = self.provider({1: [2, 1]})
        collect_contract_slice('head', provider, limit=2)
        provider = self.provider({1: [6, 5], 2: [4, 3], 3: [2, 1]})
        for _ in range(3):
            collect_contract_slice('head', provider, limit=2)
        self.assertEqual(Contract.objects.count(), 6)
        self.assertEqual(provider.page_calls, [1, 2, 3])
        self.assertEqual(crawl_state('head')['passes'], 2)

    def test_history_reaches_eof_and_starts_a_new_reconciliation_pass(self):
        provider = self.provider({1: [3], 2: [2], 3: [1]})
        for _ in range(4):
            collect_contract_slice('history', provider, limit=1)
        self.assertEqual(crawl_state('history')['passes'], 1)
        self.assertEqual(crawl_state('history')['page'], 1)
        collect_contract_slice('history', provider, limit=2)
        self.assertEqual(provider.page_calls[-2:], [1, 2])
        self.assertEqual(crawl_state('history')['page'], 3)

    def test_network_failure_keeps_failed_row_and_commits_preceding_success(self):
        provider = self.provider({1: [1, 2, 3]})
        provider.complete_contract.side_effect = [contract_record(1), SourceError('source_http_503')]
        run = collect_contract_slice('history', provider, limit=3)
        self.assertEqual(run.status, 'partial')
        self.assertEqual(crawl_state('history')['offset'], 1)
        self.assertEqual(Contract.objects.count(), 1)
        provider.complete_contract.side_effect = lambda row: row
        collect_contract_slice('history', provider, limit=2)
        self.assertEqual(Contract.objects.count(), 3)

    def test_invalid_party_survives_page_progress_and_is_repaired_by_id(self):
        provider = self.provider({1: [1, 2, 3]})
        provider.complete_contract.side_effect = [contract_record(1), SourceError('contract_party_identifier_missing'), contract_record(3)]
        run = collect_contract_slice('history', provider, limit=3)
        self.assertEqual(run.status, 'partial')
        self.assertEqual(ContractRetry.objects.get().external_id, 2)
        self.assertEqual(crawl_state('history')['page'], 2)
        ContractRetry.objects.update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        provider.complete_contract.side_effect = lambda row: row
        collect_contract_slice('repair', provider, limit=3)
        self.assertEqual(Contract.objects.count(), 3)
        self.assertIsNotNone(ContractRetry.objects.get().resolved_at)
        self.assertFalse(IngestionIssue.objects.filter(subject_key='contract:2', resolved=False).exists())

    def test_unchanged_recent_rows_do_not_fetch_parties_or_duplicate_evidence(self):
        provider = self.provider({1: [1, 2]})
        collect_contract_slice('head', provider, limit=2)
        observations = SourceObservation.objects.count()
        provider.complete_contract.reset_mock()
        run = collect_contract_slice('head', provider, limit=2)
        self.assertEqual(run.counters['unchanged'], 2)
        self.assertEqual(provider.complete_contract.call_count, 0)
        self.assertEqual(SourceObservation.objects.count(), observations)

    def test_changed_amount_and_expired_party_evidence_are_refetched(self):
        provider = self.provider({1: [1]})
        collect_contract_slice('head', provider, limit=1)
        record = contract_record(1)
        record['amount'] = '250.00'
        provider.pages[1] = ContractPage(1, (record,))
        collect_contract_slice('head', provider, limit=1)
        self.assertEqual(str(Contract.objects.get().amount), '250.00')
        SourceObservation.objects.update(observed_at=timezone.now() - timedelta(days=8))
        provider.complete_contract.reset_mock()
        collect_contract_slice('head', provider, limit=1)
        self.assertEqual(provider.complete_contract.call_count, 1)

    def test_repeated_or_malformed_page_does_not_advance(self):
        provider = self.provider({1: [1], 2: [1]})
        run = collect_contract_slice('history', provider, limit=2)
        self.assertEqual(run.error_code, 'contract_page_repeated')
        self.assertEqual(crawl_state('history')['page'], 2)

    def test_database_identity_conflict_is_quarantined_without_overwriting(self):
        provider = self.provider({1: [1]})
        collect_contract_slice('head', provider, limit=1)
        record = contract_record(2)
        record['contract_number'] = 'demo-1'
        provider.pages[1] = ContractPage(1, (record, contract_record(3)))
        collect_contract_slice('history', provider, limit=2)
        self.assertEqual(set(Contract.objects.values_list('contract_gos_id', flat=True)), {1, 3})
        self.assertEqual(ContractRetry.objects.get().error_code, 'invalid_import_data')

    def test_failed_repair_has_backoff_and_is_not_immediately_repeated(self):
        provider = self.provider({1: [1]})
        provider.complete_contract.side_effect = SourceError('contract_party_identifier_invalid')
        collect_contract_slice('head', provider, limit=1)
        provider.complete_contract.reset_mock()
        collect_contract_slice('head', provider, limit=1)
        collect_contract_slice('repair', provider, limit=1)
        self.assertEqual(provider.complete_contract.call_count, 0)
        self.assertEqual(ContractRetry.objects.get().attempts, 1)
