"""Account authorization, credentials and uniqueness contracts on isolated databases."""
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Barrier
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from rest_framework.test import APIClient

from .accounts import PasswordSerializer

PASSWORD = 'NovelSaffron!94Kelp'
NEW_PASSWORD = 'Tangerine!63Harbour'


class AccountApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('reader-fixture', email='reader@example.test', password=PASSWORD)
        cls.other = get_user_model().objects.create_user('other-fixture', email='other@example.test', password=PASSWORD)

    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)

    def bootstrap(self, client=None):
        client = client or self.client
        return client.get('/api/v1/session/').json()['csrf_token']

    def sign_in(self, client=None):
        client = client or self.client
        token = self.bootstrap(client)
        response = client.post('/api/v1/session/login/', {'username': self.user.username, 'password': PASSWORD},
            format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        return response.json()['csrf_token']

    def registration(self, **changes):
        return {'username': 'new-reader', 'email': 'NEW@example.test', 'password': PASSWORD,
            'password_confirm': PASSWORD, **changes}

    def test_register_requires_csrf_and_valid_same_origin(self):
        response = self.client.post('/api/v1/session/register/', self.registration(), format='json')
        self.assertEqual(response.status_code, 403)
        token = self.bootstrap()
        response = self.client.post('/api/v1/session/register/', self.registration(), format='json',
            HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN='https://untrusted.example.test')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(get_user_model().objects.filter(username='new-reader').exists())

    def test_register_hashes_password_and_rotates_session_csrf_without_privileges(self):
        token = self.bootstrap()
        response = self.client.post('/api/v1/session/register/', self.registration(), format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response['Cache-Control'], 'no-store')
        body = response.json()
        self.assertNotEqual(token, body['csrf_token'])
        self.assertEqual(body['user']['email'], 'new@example.test')
        self.assertEqual(body['user']['role'], 'user')
        self.assertFalse(body['capabilities']['can_start_jobs'])
        user = get_user_model().objects.get(username='new-reader')
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotIn(PASSWORD, response.content.decode())
        profile = self.client.get('/api/v1/account/profile/')
        self.assertEqual(profile.json()['username'], 'new-reader')
        self.assertEqual(profile.json()['email'], 'new@example.test')

    def test_registration_duplicate_identifiers_are_case_insensitive(self):
        token = self.bootstrap()
        for changes, field in [({'username': 'READER-fixture'}, 'username'),
                               ({'email': 'READER@EXAMPLE.TEST'}, 'email')]:
            response = self.client.post('/api/v1/session/register/', self.registration(**changes),
                format='json', HTTP_X_CSRFTOKEN=token)
            self.assertEqual(response.status_code, 400)
            self.assertIn(field, response.json()['error']['details'])

    def test_registration_validation_rejects_mismatch_weak_password_invalid_names_and_extra_fields(self):
        token = self.bootstrap()
        changes = [{'password_confirm': 'Different!72Flower'},
            {'password': '12345678', 'password_confirm': '12345678'},
            {'password': 'short', 'password_confirm': 'short'}, {'email': 'not-an-email'},
            {'username': '<script>'}, {'is_staff': True}, {'password': 'x'*129, 'password_confirm': 'x'*129}]
        for data in changes:
            cache.clear()
            with self.subTest(fields=sorted(data)):
                response = self.client.post('/api/v1/session/register/', self.registration(**data),
                    format='json', HTTP_X_CSRFTOKEN=token)
                self.assertEqual(response.status_code, 400)
        self.assertEqual(get_user_model().objects.count(), 2)

    def test_registration_attempts_are_throttled(self):
        token = self.bootstrap()
        for _ in range(5):
            response = self.client.post('/api/v1/session/register/', self.registration(email='bad'),
                format='json', HTTP_X_CSRFTOKEN=token)
            self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/v1/session/register/', self.registration(),
            format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)

    def test_authenticated_registration_cannot_replace_current_account(self):
        token = self.sign_in()
        response = self.client.post('/api/v1/session/register/', self.registration(), format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get('/api/v1/session/').json()['user']['username'], self.user.username)
        self.assertEqual(get_user_model().objects.count(), 2)

    def test_profile_is_private_and_get_does_not_change_account_rows(self):
        self.assertEqual(self.client.get('/api/v1/account/profile/').status_code, 403)
        self.sign_in()
        before = list(get_user_model().objects.order_by('pk').values())
        response = self.client.get('/api/v1/account/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(set(response.json()), {'username', 'email', 'role', 'date_joined'})
        self.assertEqual(response.json()['email'], self.user.email)
        self.assertEqual(list(get_user_model().objects.order_by('pk').values()), before)

    def test_username_changes_only_current_user_and_preserves_email_role_and_id(self):
        token = self.sign_in()
        response = self.client.patch('/api/v1/account/profile/', {'username': 'Reader.Renamed'},
            format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db(); self.other.refresh_from_db()
        self.assertEqual(self.user.username, 'Reader.Renamed')
        self.assertEqual(self.user.email, 'reader@example.test')
        self.assertFalse(self.user.is_staff)
        self.assertEqual(self.other.username, 'other-fixture')
        self.assertEqual(self.client.get('/api/v1/session/').json()['user']['username'], 'Reader.Renamed')

    def test_username_edit_requires_csrf_and_rejects_email_permissions_and_other_user_ids(self):
        token = self.sign_in()
        self.assertEqual(self.client.patch('/api/v1/account/profile/', {'username': 'changed'}, format='json').status_code, 403)
        for extra in ({'email': 'another@example.test'}, {'id': self.other.pk}, {'is_staff': True}, {'role': 'staff'}):
            response = self.client.patch('/api/v1/account/profile/', {'username': 'changed', **extra},
                format='json', HTTP_X_CSRFTOKEN=token)
            self.assertEqual(response.status_code, 400)
        conflict = self.client.patch('/api/v1/account/profile/', {'username': 'OTHER-fixture'},
            format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(conflict.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'reader-fixture')

    def test_password_change_checks_current_password_confirmation_and_validators(self):
        token = self.sign_in()
        baseline = self.user.password
        for changes in ({'current_password': 'Wrong!56Flower'}, {'new_password_confirm': 'Wrong!56Flower'},
                        {'new_password': '12345678', 'new_password_confirm': '12345678'}, {'email': 'bad@example.test'}):
            data = {'current_password': PASSWORD, 'new_password': NEW_PASSWORD,
                'new_password_confirm': NEW_PASSWORD, **changes}
            response = self.client.post('/api/v1/account/password/', data, format='json', HTTP_X_CSRFTOKEN=token)
            self.assertEqual(response.status_code, 400)
            self.user.refresh_from_db()
            self.assertEqual(self.user.password, baseline)
            self.assertNotIn(PASSWORD, response.content.decode())

    def test_password_change_keeps_current_session_invalidates_others_and_rotates_csrf(self):
        other_client = APIClient(enforce_csrf_checks=True)
        self.sign_in(other_client)
        token = self.sign_in()
        data = {'current_password': PASSWORD, 'new_password': NEW_PASSWORD, 'new_password_confirm': NEW_PASSWORD}
        self.assertEqual(self.client.post('/api/v1/account/password/', data, format='json').status_code, 403)
        response = self.client.post('/api/v1/account/password/', data, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(token, response.json()['csrf_token'])
        self.assertEqual(self.client.get('/api/v1/session/').json()['user']['role'], 'user')
        self.assertEqual(other_client.get('/api/v1/session/').json()['user']['role'], 'anonymous')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertFalse(self.user.check_password(PASSWORD))
        self.assertNotIn(NEW_PASSWORD, response.content.decode())
        self.assertEqual(self.client.post('/api/v1/session/logout/', {}, format='json', HTTP_X_CSRFTOKEN=token).status_code, 403)
        self.assertEqual(self.client.post('/api/v1/session/logout/', {}, format='json',
            HTTP_X_CSRFTOKEN=response.json()['csrf_token']).status_code, 204)

    def test_database_constraints_prevent_bypassing_api_duplicate_checks(self):
        User = get_user_model()
        for name, email in [('READER-fixture', 'unique@example.test'), ('unique-fixture', 'READER@example.test')]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                User.objects.create_user(name, email=email)
        User.objects.create_user('blank-email-one')
        User.objects.create_user('blank-email-two')


class AccountConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_case_variant_registrations_publish_only_one_account(self):
        cache.clear()
        barrier = Barrier(2)
        User = get_user_model()
        Manager = type(User.objects)
        original = Manager.create_user
        def fenced(manager, *args, **kwargs):
            barrier.wait(timeout=10)
            return original(manager, *args, **kwargs)
        def attempt(index):
            close_old_connections()
            try:
                client = APIClient(enforce_csrf_checks=True)
                token = client.get('/api/v1/session/').json()['csrf_token']
                return client.post('/api/v1/session/register/', {'username': ['ConcurrentName', 'concurrentname'][index],
                    'email': f'concurrent-{index}@example.test', 'password': PASSWORD, 'password_confirm': PASSWORD},
                    format='json', HTTP_X_CSRFTOKEN=token).status_code
            finally:
                close_old_connections()
        with patch.object(Manager, 'create_user', fenced), ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(attempt, [0, 1]))
        self.assertEqual(sorted(statuses), [201, 400])
        self.assertEqual(User.objects.count(), 1)

    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_password_changes_recheck_current_password_under_lock(self):
        cache.clear()
        user = get_user_model().objects.create_user('concurrent-password', email='concurrent@example.test', password=PASSWORD)
        barrier = Barrier(2)
        original = PasswordSerializer.validate
        def fenced(serializer, attrs):
            data = original(serializer, attrs)
            barrier.wait(timeout=10)
            return data
        passwords = [NEW_PASSWORD, 'Basil!83Lighthouse']
        def attempt(index):
            close_old_connections()
            try:
                client = APIClient(enforce_csrf_checks=True)
                client.force_login(user)
                token = client.get('/api/v1/session/').json()['csrf_token']
                response = client.post('/api/v1/account/password/', {'current_password': PASSWORD,
                    'new_password': passwords[index], 'new_password_confirm': passwords[index]},
                    format='json', HTTP_X_CSRFTOKEN=token)
                return index, response.status_code
            finally:
                close_old_connections()
        with patch.object(PasswordSerializer, 'validate', fenced), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, [0, 1]))
        self.assertEqual(sorted(status for _, status in results), [200, 400])
        user.refresh_from_db()
        success = next(index for index, status in results if status == 200)
        self.assertTrue(user.check_password(passwords[success]))


class AccountIndexMigrationTests(TransactionTestCase):
    def test_duplicate_preflight_preserves_rows_and_reverse_restores_previous_schema(self):
        migration = import_module('apps.api.migrations.0001_account_identity_indexes')
        User = get_user_model()
        with connection.schema_editor() as editor:
            migration.remove_indexes(apps, editor)
        try:
            first = User.objects.create_user('LegacyCase', email='legacy-one@example.test')
            second = User.objects.create_user('legacycase', email='legacy-two@example.test')
            before = list(User.objects.order_by('pk').values())
            with self.assertRaisesRegex(RuntimeError, 'username'), connection.schema_editor() as editor:
                migration.add_indexes(apps, editor)
            self.assertEqual(list(User.objects.order_by('pk').values()), before)
            second.delete()
            with connection.schema_editor() as editor:
                migration.add_indexes(apps, editor)
            first.refresh_from_db()
            self.assertEqual(first.username, 'LegacyCase')
        finally:
            with connection.cursor() as cursor:
                constraints = connection.introspection.get_constraints(cursor, User._meta.db_table)
            if 'api_auth_username_ci' not in constraints:
                User.objects.filter(username='legacycase').delete()
                with connection.schema_editor() as editor:
                    migration.add_indexes(apps, editor)
