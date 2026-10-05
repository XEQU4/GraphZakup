from types import SimpleNamespace
from unittest.mock import Mock
from django.test import SimpleTestCase
from apps.ingestion.errors import SourceError
from apps.ingestion.transport import HttpTransport


def response(status=200, text='<html>company</html>', headers=None):
    return SimpleNamespace(status_code=status, text=text, headers=headers or {})


class TransportTests(SimpleTestCase):
    def transport(self, responses, **options):
        self.time, self.delays = 0.0, []
        def sleep(seconds):
            self.delays.append(seconds)
            self.time += seconds
        self.session = Mock()
        self.session.get.side_effect = responses
        return HttpTransport(session=self.session, clock=lambda: self.time, sleeper=sleep, **options)

    def test_shared_host_pacing_and_success_cache_avoid_duplicate_requests(self):
        client = self.transport([response(), response()], min_interval=1.5, cache_ttl=10)
        url = 'https://goszakup.gov.kz/card/1'
        first = client.get(url)
        self.assertIs(client.get(url), first)
        client.get('https://goszakup.gov.kz/card/2')
        self.assertEqual(self.session.get.call_count, 2)
        self.assertEqual(self.delays, [1.5])

    def test_retry_after_is_bounded_and_failed_responses_not_cached(self):
        client = self.transport([response(429, headers={'Retry-After': '999999'}), response(), response()], retries=1, cache_ttl=0)
        client.get('https://goszakup.gov.kz/card/1')
        client.get('https://goszakup.gov.kz/card/1')
        self.assertEqual(self.session.get.call_count, 3)
        self.assertIn(60, self.delays)

    def test_failure_codes_exclude_raw_response_and_credentials(self):
        from curl_cffi.requests import RequestsError
        client = self.transport([RequestsError('private-token-marker')] * 3, min_interval=0)
        with self.assertRaisesMessage(SourceError, 'source_request_failed') as error:
            client.get('https://pk.adata.kz/company/000000000001')
        self.assertNotIn('private-token-marker', str(error.exception))
        self.assertEqual(self.session.get.call_count, 3)

    def test_eof_404_and_challenge_are_distinct(self):
        client = self.transport([response(404), response(404, 'g-recaptcha')], retries=0)
        self.assertEqual(client.get('https://pk.adata.kz/company/1', allow_not_found=True).status_code, 404)
        with self.assertRaises(SourceError):
            client.get('https://pk.adata.kz/company/2', allow_not_found=True)

    def test_unknown_hosts_redirects_credentials_and_non_https_are_rejected(self):
        client = self.transport([response(302)])
        for url in ('http://goszakup.gov.kz/', 'https://unknown.invalid/',
                    'https://token@goszakup.gov.kz/', 'https://goszakup.gov.kz:8443/'):
            with self.subTest(url=url), self.assertRaises(SourceError):
                client.get(url)
        self.assertEqual(self.session.get.call_count, 0)
        with self.assertRaises(SourceError):
            client.get('https://goszakup.gov.kz/')
        self.assertFalse(self.session.get.call_args.kwargs['allow_redirects'])

    def test_response_size_and_cache_capacity_are_bounded(self):
        client = self.transport([response(text='x' * (4 * 1024 * 1024 + 1))], retries=0)
        with self.assertRaisesMessage(SourceError, 'source_response_too_large'):
            client.get('https://goszakup.gov.kz/')
        client = self.transport([response()] * 40, min_interval=0)
        for index in range(40):
            client.get(f'https://goszakup.gov.kz/{index}')
        self.assertEqual(len(client._cache), 32)
        client.close()
        self.assertEqual(len(client._cache), 0)
        self.session.close.assert_called_once()

    def test_heartbeat_before_each_retry_prevents_stale_worker_write(self):
        heartbeat = Mock()
        client = self.transport([response(503), response()], heartbeat=heartbeat)
        client.get('https://goszakup.gov.kz/')
        self.assertEqual(heartbeat.call_count, 2)
