from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.ingestion.errors import SourceError
from apps.ingestion.transport import HttpTransport
from curl_cffi import requests


class SourceCircuitTests(SimpleTestCase):
    def test_transport_diagnostic_never_logs_authenticated_exception_text(self):
        session = Mock()
        session.get.side_effect = requests.RequestsError('private-token-in-authenticated-url', code=28)
        client = HttpTransport(session=session, retries=0)
        with self.assertLogs('apps.ingestion.transport', level='WARNING') as output:
            with self.assertRaisesMessage(SourceError, 'source_request_failed'):
                client.get_json('https://portal.kgd.gov.kz/', params={'token': 'private-token'})
        self.assertIn('curl_code=28', output.output[0])
        self.assertNotIn('private-token', output.output[0])

    def transport(self, statuses, retries=0):
        session = Mock()
        session.get.side_effect = [SimpleNamespace(status_code=status, text='Synthetic response', headers={})
                                   for status in statuses]
        return HttpTransport(session=session, min_interval=0, retries=retries, cache_ttl=0, sleeper=Mock())

    def test_repeated_redirects_stop_host_but_allow_other_source(self):
        client = self.transport([302, 302, 302, 200])
        for _ in range(3):
            with self.assertRaisesMessage(SourceError, 'source_http_302'):
                client.get('https://old.goszakup.gov.kz/ru/registry/supplierreg')
        with self.assertRaisesMessage(SourceError, 'source_batch_circuit_open'):
            client.get('https://old.goszakup.gov.kz/ru/registry/supplierreg')
        self.assertEqual(client.session.get.call_count, 3)
        self.assertEqual(client.get('https://pk.adata.kz/').status_code, 200)

    def test_access_denied_and_rate_limits_stop_without_retries(self):
        for status in (403, 429):
            client = self.transport([status, 200], retries=2)
            with self.assertRaises(SourceError):
                client.get('https://old.goszakup.gov.kz/')
            with self.assertRaisesMessage(SourceError, 'source_batch_circuit_open'):
                client.get('https://old.goszakup.gov.kz/')
            self.assertEqual(client.session.get.call_count, 1)

    def test_success_resets_consecutive_failure_count(self):
        client = self.transport([502, 502, 200, 502, 200])
        for status in (502, 502, 200, 502, 200):
            if status == 200:
                self.assertEqual(client.get('https://pk.adata.kz/').status_code, 200)
            else:
                with self.assertRaisesMessage(SourceError, 'source_http_502'):
                    client.get('https://pk.adata.kz/')
        self.assertEqual(client.session.get.call_count, 5)

    def test_shared_budget_counts_http_attempts_and_blocks_another_host(self):
        client = self.transport([200, 200, 200])
        client.max_requests = 2
        client.get('https://old.goszakup.gov.kz/')
        client.get('https://pk.adata.kz/')
        with self.assertRaisesMessage(SourceError, 'source_request_budget_exhausted'):
            client.get('https://portal.kgd.gov.kz/')
        self.assertEqual(client.requests_made, 2)
        self.assertEqual(client.session.get.call_count, 2)
