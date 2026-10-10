"""Quota, proxy and admin regressions without a production Redis/database."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

import redis
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from .checks import authentication_deployment_checks
from .throttling import (AuthenticationThrottle, client_address,
    consume_auth_quota, ThrottleUnavailable, TrustedProxyMiddleware)


class AuthQuotaTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def request(self, ip='198.51.100.7', **headers):
        return self.factory.post('/api/v1/session/login/', REMOTE_ADDR=ip, **headers)

    def test_rotating_untrusted_forwarded_headers_does_not_reset_ip_quota(self):
        for attempt in range(10):
            request = self.request(HTTP_X_FORWARDED_FOR=f'203.0.113.{attempt}',
                HTTP_X_IZ2_CLIENT_IP=f'203.0.113.{attempt}')
            self.assertEqual(consume_auth_quota(request, 'api_login', f'account-{attempt}'), 0)
        self.assertGreater(consume_auth_quota(self.request(), 'api_login', 'another-account'), 0)

    def test_login_account_quota_survives_ip_rotation_and_username_case_changes(self):
        for attempt in range(10):
            self.assertEqual(consume_auth_quota(self.request(f'198.51.100.{attempt}'),
                'api_login', 'Synthetic-User'), 0)
        self.assertGreater(consume_auth_quota(self.request('203.0.113.10'),
            'api_login', ' SYNTHETIC-user '), 0)

    @override_settings(AUTH_TRUSTED_PROXY_CIDRS=['172.30.0.2/32'])
    def test_proxy_clients_have_distinct_registration_quota_and_invalid_header_falls_back(self):
        for attempt in range(5):
            self.assertEqual(consume_auth_quota(self.request('172.30.0.2',
                HTTP_X_IZ2_CLIENT_IP='203.0.113.1'), 'api_register'), 0)
        self.assertGreater(consume_auth_quota(self.request('172.30.0.2',
            HTTP_X_IZ2_CLIENT_IP='203.0.113.1'), 'api_register'), 0)
        self.assertEqual(consume_auth_quota(self.request('172.30.0.2',
            HTTP_X_IZ2_CLIENT_IP='203.0.113.2'), 'api_register'), 0)
        for value in ['203.0.113.1, 203.0.113.2', 'host.invalid', '203.0.113.1:443', 'fe80::1%eth0', '']:
            self.assertEqual(client_address(self.request('172.30.0.2', HTTP_X_IZ2_CLIENT_IP=value)),
                '172.30.0.2')

    def test_ipv4_mapped_ipv6_cannot_create_another_ip_bucket(self):
        self.assertEqual(client_address(self.request('::ffff:198.51.100.7')), '198.51.100.7')

    def test_rolling_window_expires_without_denied_requests_extending_it(self):
        with patch('apps.api.throttling.time.time', return_value=1000):
            for _ in range(10):
                self.assertEqual(consume_auth_quota(self.request(), 'api_login', 'synthetic'), 0)
        with patch('apps.api.throttling.time.time', return_value=1059):
            self.assertEqual(consume_auth_quota(self.request(), 'api_login', 'synthetic'), 1)
        with patch('apps.api.throttling.time.time', return_value=1060):
            self.assertEqual(consume_auth_quota(self.request(), 'api_login', 'synthetic'), 0)

    def test_local_concurrent_requests_do_not_exceed_limit(self):
        def attempt(_):
            return consume_auth_quota(self.request(), 'api_login', 'synthetic')
        with ThreadPoolExecutor(max_workers=8) as pool:
            waits = list(pool.map(attempt, range(30)))
        self.assertEqual(waits.count(0), 10)

    @override_settings(AUTH_THROTTLE_REDIS_URL='redis://isolated.invalid/1')
    def test_shared_failure_never_falls_back_to_local_quota(self):
        with patch('apps.api.throttling._redis_client', side_effect=redis.ConnectionError('private-url')):
            with self.assertRaises(ThrottleUnavailable):
                consume_auth_quota(self.request(), 'api_login', 'synthetic')
        with patch('apps.api.throttling.cache.get') as local:
            with patch('apps.api.throttling._redis_client', side_effect=redis.TimeoutError):
                with self.assertRaises(ThrottleUnavailable):
                    consume_auth_quota(self.request(), 'api_register')
            local.assert_not_called()

    @override_settings(AUTH_THROTTLE_REDIS_URL='redis://isolated.invalid/1')
    def test_shared_operation_consumes_all_dimensions_once_and_hides_identifiers(self):
        with patch('apps.api.throttling._redis_client') as factory:
            factory.return_value.eval.return_value = 1550
            wait = consume_auth_quota(self.request(), 'api_login', 'sensitive-username')
        self.assertEqual(wait, 1.55)
        args = factory.return_value.eval.call_args.args
        self.assertEqual(args[1], 2)
        self.assertNotIn('sensitive-username', str(args))
        self.assertNotIn('198.51.100.7', str(args))
        self.assertEqual(args[-3:-1], (60000, 10))

    def test_non_object_login_input_cannot_raise_internal_error(self):
        request = self.request()
        request.data = ['synthetic']
        self.assertTrue(AuthenticationThrottle().allow_request(request,
            SimpleNamespace(throttle_scope='api_login')))


@override_settings(SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    AUTH_TRUSTED_PROXY_CIDRS=['172.30.0.2/32'])
class ProxySecurityTests(SimpleTestCase):
    def test_untrusted_peer_cannot_claim_https(self):
        request = RequestFactory().get('/', REMOTE_ADDR='198.51.100.7',
            HTTP_X_FORWARDED_PROTO='https', HTTP_X_IZ2_CLIENT_IP='203.0.113.9')
        TrustedProxyMiddleware(lambda current: current)(request)
        self.assertFalse(request.is_secure())
        self.assertEqual(client_address(request), '198.51.100.7')

    def test_allowlisted_single_proxy_can_supply_https_and_client(self):
        request = RequestFactory().get('/', REMOTE_ADDR='172.30.0.2',
            HTTP_X_FORWARDED_PROTO='https', HTTP_X_IZ2_CLIENT_IP='203.0.113.9')
        TrustedProxyMiddleware(lambda current: current)(request)
        self.assertTrue(request.is_secure())
        self.assertEqual(client_address(request), '203.0.113.9')


class AuthDeploymentCheckTests(SimpleTestCase):
    @override_settings(AUTH_THROTTLE_REDIS_URL='', AUTH_TRUSTED_PROXY_CIDRS=[],
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'))
    def test_public_check_warns_about_local_quota_and_ignored_tls_forwarding(self):
        self.assertEqual({item.id for item in authentication_deployment_checks(None)},
            {'iz2.W001', 'iz2.W002'})

    @override_settings(AUTH_THROTTLE_REDIS_URL='redis://isolated.invalid/1',
        AUTH_TRUSTED_PROXY_CIDRS=['172.30.0.2/32'],
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'))
    def test_explicit_deployment_policy_passes_static_checks_without_network_calls(self):
        self.assertEqual(authentication_deployment_checks(None), [])


class AuthHttpThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.token = self.client.get('/api/v1/session/').json()['csrf_token']

    def login(self):
        return self.client.post('/api/v1/session/login/', {'username': 'missing-synthetic',
            'password': 'invalid'}, format='json', HTTP_X_CSRFTOKEN=self.token)

    def test_admin_and_api_login_share_attempt_budget(self):
        for _ in range(5):
            self.assertEqual(self.login().status_code, 403)
        for _ in range(5):
            response = self.client.post('/admin/login/', {'username': 'missing-synthetic',
                'password': 'invalid', 'csrfmiddlewaretoken': self.token})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.login().status_code, 429)
        denied = self.client.post('/admin/login/', {'username': 'missing-synthetic',
            'password': 'invalid', 'csrfmiddlewaretoken': self.token})
        self.assertEqual(denied.status_code, 429)
        self.assertIn('Retry-After', denied)

    @override_settings(AUTH_THROTTLE_REDIS_URL='redis://isolated.invalid/1')
    def test_api_and_admin_fail_closed_without_leaking_backend_details(self):
        with patch('apps.api.throttling._redis_client', side_effect=redis.ConnectionError('private-url')):
            response = self.login()
            admin = self.client.post('/admin/login/', {'username': 'missing-synthetic',
                'password': 'invalid', 'csrfmiddlewaretoken': self.token})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response['Retry-After'], '5')
        self.assertEqual(response.json()['error']['code'], 'authentication_unavailable')
        self.assertEqual(admin.status_code, 503)
        self.assertNotIn('private-url', response.content.decode() + admin.content.decode())

    def test_admin_throttle_preserves_csrf_protection_and_get_access(self):
        response = self.client.post('/admin/login/', {'username': 'missing-synthetic', 'password': 'invalid'})
        self.assertEqual(response.status_code, 403)
        for _ in range(10):
            self.assertEqual(self.login().status_code, 403)
        self.assertEqual(self.client.get('/admin/login/').status_code, 200)

    def test_clickjacking_header_protects_html_and_api_responses(self):
        for url in ['/admin/login/', '/api/v1/docs/', '/api/v1/session/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url)['X-Frame-Options'], 'DENY')
