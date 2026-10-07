"""Session, error and schema contracts for the future same-origin React client."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.validation import validate_schema
from rest_framework.test import APIClient

from apps.companies.models import Supplier
from .common import safe_source_url


class ApiSessionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('synthetic-reader', password='synthetic-only-password')
        cls.staff = get_user_model().objects.create_user('synthetic-staff', password='synthetic-only-password', is_staff=True)

    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)

    def bootstrap(self):
        response = self.client.get('/api/v1/session/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('csrftoken', self.client.cookies)
        self.assertEqual(response['Cache-Control'], 'no-store')
        return response.json()['csrf_token']

    def test_anonymous_bootstrap_and_unknown_parameters(self):
        token = self.bootstrap()
        self.assertTrue(token)
        body = self.client.get('/api/v1/session/').json()
        self.assertEqual(body['user'], {'id': None, 'username': None, 'role': 'anonymous'})
        self.assertFalse(body['capabilities']['can_start_jobs'])
        response = self.client.get('/api/v1/session/?provider=external')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], 'validation_error')

    def test_login_requires_csrf_even_when_anonymous(self):
        response = self.client.post('/api/v1/session/login/', {
            'username': self.user.username, 'password': 'synthetic-only-password'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('sessionid', self.client.cookies)

    def test_login_rotates_csrf_and_logout_requires_new_token(self):
        old_token = self.bootstrap()
        response = self.client.post('/api/v1/session/login/', {
            'username': self.user.username, 'password': 'synthetic-only-password'},
            format='json', HTTP_X_CSRFTOKEN=old_token)
        self.assertEqual(response.status_code, 200)
        current_token = response.json()['csrf_token']
        self.assertNotEqual(current_token, old_token)
        self.assertEqual(response.json()['user']['role'], 'user')
        self.assertTrue(response.json()['capabilities']['can_save_views'])
        self.assertFalse(response.json()['capabilities']['can_start_jobs'])
        self.assertEqual(self.client.post('/api/v1/session/logout/', {}, format='json',
            HTTP_X_CSRFTOKEN=old_token).status_code, 403)
        self.assertEqual(self.client.post('/api/v1/session/logout/', {}, format='json',
            HTTP_X_CSRFTOKEN=current_token).status_code, 204)
        self.assertEqual(self.client.get('/api/v1/session/').json()['user']['role'], 'anonymous')

    def test_staff_capabilities_and_invalid_credentials_are_generic(self):
        token = self.bootstrap()
        bad = self.client.post('/api/v1/session/login/', {'username': self.user.username,
            'password': 'wrong-synthetic-password'}, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(bad.status_code, 403)
        self.assertEqual(bad.json()['error']['code'], 'invalid_credentials')
        self.assertNotIn('wrong-synthetic-password', bad.content.decode())
        good = self.client.post('/api/v1/session/login/', {'username': self.staff.username,
            'password': 'synthetic-only-password'}, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(good.status_code, 200)
        self.assertTrue(good.json()['capabilities']['can_start_jobs'])

    def test_unknown_login_fields_and_non_json_are_rejected(self):
        token = self.bootstrap()
        response = self.client.post('/api/v1/session/login/', {'username': 'synthetic',
            'password': 'synthetic', 'is_staff': True}, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/v1/session/login/', 'username=synthetic',
            content_type='application/x-www-form-urlencoded', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.json()['error']['code'], 'unsupported_media_type')

    def test_login_attempts_are_throttled(self):
        token = self.bootstrap()
        for attempt in range(10):
            self.assertEqual(self.client.post('/api/v1/session/login/', {'username': 'missing-synthetic',
                'password': 'synthetic'}, format='json', HTTP_X_CSRFTOKEN=token,
                HTTP_X_FORWARDED_FOR=f'198.51.100.{attempt+1}').status_code, 403)
        response = self.client.post('/api/v1/session/login/', {'username': 'missing-synthetic',
            'password': 'synthetic'}, format='json', HTTP_X_CSRFTOKEN=token,
            HTTP_X_FORWARDED_FOR='198.51.100.11')
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)


class ApiBoundaryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Supplier.objects.create(bin='000000000501', name='Synthetic API boundary company')

    def test_unknown_routes_and_methods_are_json(self):
        for url in ['/api/v1/unknown/', '/api/v1/clusters/not-a-uuid/', '/api/v1/companies/no-integer/']:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()['error']['code'], 'not_found')
        response = self.client.delete('/api/v1/companies/')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()['error']['code'], 'method_not_allowed')

    def test_query_bounds_duplicates_and_json_negotiation(self):
        for query in ['page_size=101', 'page_size=0', 'page=0', 'page=1&page=2', 'unknown=yes']:
            response = self.client.get('/api/v1/companies/?'+query)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()['error']['code'], 'validation_error')
        response = self.client.get('/api/v1/companies/', HTTP_ACCEPT='text/html')
        self.assertEqual(response.status_code, 406)
        self.assertEqual(response.json()['error']['code'], 'not_acceptable')

    @override_settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=3)
    def test_excessive_query_fields_are_a_client_error(self):
        response = self.client.get('/api/v1/companies/?page=1&page_size=2&ordering=name&search=synthetic')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], 'validation_error')

    def test_unhandled_failure_never_returns_internal_details(self):
        with patch('apps.api.entities.CompanyListView.get_queryset',
                   side_effect=RuntimeError('synthetic-internal-sensitive-value')):
            response = self.client.get('/api/v1/companies/')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('synthetic-internal-sensitive-value', response.content.decode())
        self.assertEqual(response.json()['error']['code'], 'internal_error')

    def test_request_body_limit_and_malformed_json(self):
        staff = get_user_model().objects.create_user('synthetic-boundary-staff', is_staff=True)
        self.client.force_authenticate(staff)
        response = self.client.post('/api/v1/session/logout/', '{', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], 'parse_error')
        response = self.client.post('/api/v1/session/logout/', '{"padding":"'+'x'*131072+'"}',
            content_type='application/json')
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()['error']['code'], 'payload_too_large')

    def test_excessively_nested_json_is_a_client_error(self):
        staff = get_user_model().objects.create_user('synthetic-nesting-staff', is_staff=True)
        self.client.force_authenticate(staff)
        response = self.client.post('/api/v1/session/logout/', '['*10000+'0'+']'*10000,
            content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], 'parse_error')

    def test_source_urls_keep_personal_identifiers_and_tokens_private(self):
        self.assertEqual(safe_source_url('https://example.org/registry'), 'https://example.org/registry')
        for value in ['https://example.org/?token=synthetic', 'https://user:synthetic@example.org/',
            'http://example.org/', 'https://example.org/person/999999999999',
            'https://example.org/person/'+'%39'*12, 'https://example.org/'+'%2539'*12,
            'https://example.org/%0a', 'https://example.org/unsafe\\path']:
            self.assertIsNone(safe_source_url(value))

    def test_openapi_is_valid_and_covers_api_only(self):
        schema = SchemaGenerator().get_schema(request=None, public=True)
        validate_schema(schema)
        self.assertTrue(schema['paths'])
        self.assertTrue(all(p.startswith('/api/v1/') for p in schema['paths']))
        self.assertIn('/api/v1/clusters/{uuid}/analysis/', schema['paths'])
        self.assertIn('/api/v1/session/login/', schema['paths'])
        self.assertNotIn('/api/v1/clusters/{uuid}/', {p for p, op in schema['paths'].items() if 'post' in op})
        login_op = schema['paths']['/api/v1/session/login/']['post']
        self.assertTrue(any(p['name']=='X-CSRFToken' and p['required'] for p in login_op['parameters']))
        self.assertIn('ErrorEnvelope', schema['components']['schemas'])
