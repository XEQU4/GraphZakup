from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.ingestion.background import CycleLease, collection_status, due_companies, read_state, registered_subject_type, run_background_cycle
from apps.ingestion.dto import ResultStatus, SourceResult
from apps.ingestion.errors import SourceError
from apps.ingestion.models import IngestionRun
from apps.ingestion.observations import record_observation
from apps.ingestion.parsers.contracts import ContractPage
from apps.ingestion.services import run_pipeline
from .helpers import FakeProviders, contract_record


class BackgroundProvider(FakeProviders):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.transport = SimpleNamespace(blocked_hosts=set(), max_requests=100, requests_made=0)


@override_settings(ENABLE_SCHEDULED_IMPORT=True, ENABLE_SCHEDULED_KGD=False, BACKGROUND_COMPANY_BATCH=1)
class BackgroundTests(TestCase):
    def setUp(self):
        self.first = Supplier.objects.create(bin='000000000001', name='First')
        self.second = Supplier.objects.create(bin='000000000002', name='Second')

    def observe(self, company, *, source='adata', status='success', hours=0, version='2.0', data=None):
        run = IngestionRun.objects.create(mode='enrich', status='succeeded')
        return record_observation(run, SourceResult(source, f'company:{company.bin}', ResultStatus(status),
            parser_version=version, observed_at=timezone.now() - timedelta(hours=hours),
            data=data or {'bin': company.bin, 'name': company.name}), company)

    @override_settings(ENABLE_SCHEDULED_IMPORT=False)
    def test_disabled_cycle_does_not_write_or_fetch(self):
        with self.assertNumQueries(0):
            self.assertEqual(run_background_cycle(), {'status': 'disabled'})

    def test_contract_only_does_not_walk_the_whole_company_catalogue(self):
        provider = BackgroundProvider(pages=[ContractPage(1, (contract_record(4),))])
        run = run_pipeline(mode='update', total=1, contracts_only=True, providers=provider)
        self.assertEqual(run.status, 'succeeded')
        self.assertEqual(Contract.objects.count(), 1)
        self.assertEqual(provider.company_calls, [])

    def test_broken_contract_source_does_not_prevent_adata_and_final_refresh(self):
        provider = BackgroundProvider(results={('adata', self.first.bin): {'name': 'Updated'}})
        provider.pages[1] = SourceError('source_http_502')
        with patch('apps.ingestion.background.refresh_graph_analysis', return_value={'changed': True}) as refresh:
            result = run_background_cycle(providers=provider)
        self.assertEqual(result['stages']['goszakup_contracts']['status'], 'partial')
        self.assertEqual(result['stages']['adata']['status'], 'completed')
        self.first.refresh_from_db()
        self.assertEqual(self.first.name, 'Updated')
        self.assertEqual(refresh.call_count, 1)
        self.assertEqual(len(provider.company_calls), 2)
        self.assertTrue(read_state('latest')['finished_at'])

    def test_due_selection_skips_recent_failures_and_prioritizes_unattempted(self):
        self.observe(self.first, status='unavailable', hours=1)
        self.assertEqual(list(due_companies('adata', version='2.0', now=timezone.now(), limit=1)), [self.second])
        self.assertEqual(list(due_companies('goszakup_supplier', version='2.0', now=timezone.now(), limit=1)), [self.first])

    def test_older_failures_do_not_starve_unattempted_companies(self):
        self.observe(self.first, status='invalid', hours=10)
        self.assertEqual(list(due_companies('adata', version='2.0', now=timezone.now(), limit=2)), [self.second, self.first])

    def test_fresh_success_does_not_need_repeat_collection(self):
        self.observe(self.first)
        self.observe(self.second, hours=200)
        self.assertEqual(list(due_companies('adata', version='2.0', now=timezone.now(), limit=2)), [self.second])

    def test_cycle_deduplication_and_persisted_stage_due_times(self):
        lease = CycleLease.acquire()
        try:
            self.assertEqual(run_background_cycle(providers=BackgroundProvider()), {'status': 'busy'})
        finally:
            lease.release()
        provider = BackgroundProvider()
        with patch('apps.ingestion.background.refresh_graph_analysis', return_value={}):
            run_background_cycle(providers=provider)
            provider.page_calls.clear()
            provider.company_calls.clear()
            second = run_background_cycle(providers=provider)
        self.assertEqual(provider.page_calls, [])
        self.assertEqual(provider.company_calls, [])
        self.assertEqual(second['stages']['adata']['status'], 'waiting')

    def test_closed_registry_circuit_still_allows_adata(self):
        provider = BackgroundProvider()
        provider.transport.blocked_hosts.add('old.goszakup.gov.kz')
        with patch('apps.ingestion.background.refresh_graph_analysis', return_value={}):
            result = run_background_cycle(providers=provider)
        self.assertEqual(provider.page_calls, [])
        self.assertEqual(provider.company_calls, [('adata', self.first.bin)])
        self.assertEqual(result['stages']['goszakup_supplier']['status'], 'source_paused')

    def test_type_detection_never_uses_name_or_identifier_shape(self):
        self.first.name = 'IP Synthetic'
        self.first.save()
        self.assertIsNone(registered_subject_type(self.first))
        self.observe(self.first, source='goszakup_supplier', version='2.2',
                     data={'bin': self.first.bin, 'kopf': 'Индивидуальное (личное) предпринимательство'})
        self.assertEqual(registered_subject_type(self.first), 'IP')

    def test_unknown_registration_form_is_not_guessed(self):
        self.observe(self.first, source='goszakup_supplier', version='2.2',
                     data={'bin': self.first.bin, 'kopf': 'Unknown legal form'})
        self.assertIsNone(registered_subject_type(self.first))

    def test_status_retains_previous_source_outcome_and_does_not_collect(self):
        provider = BackgroundProvider()
        with patch('apps.ingestion.background.refresh_graph_analysis', return_value={}):
            run_background_cycle(providers=provider)
            run_background_cycle(providers=provider)
        with patch('apps.ingestion.background.run_pipeline', side_effect=AssertionError('unexpected collection')):
            state = collection_status()
        self.assertEqual(state['latest_cycle']['stages']['adata']['status'], 'waiting')
        self.assertEqual(state['sources']['adata']['status'], 'completed')
        self.assertEqual(state['totals']['companies'], 2)
