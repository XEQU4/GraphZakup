import os
import runpy
import traceback
from pathlib import Path
from unittest.mock import patch

from celery.exceptions import Retry
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings

from apps.core.tasks import update_all_data


class SettingsSafetyTests(SimpleTestCase):
    def load_settings(self, **values):
        env = {"DJANGO_LOAD_DOTENV": "false", "SECRET_KEY": "offline-tests-secret", **values}
        with patch.dict(os.environ, env, clear=True):
            return runpy.run_path(str(Path(settings.BASE_DIR) / "config/settings.py"))

    def test_defaults_disable_debug_and_live_import(self):
        configured = self.load_settings()
        self.assertFalse(configured["DEBUG"])
        self.assertEqual(configured["ALLOWED_HOSTS"], ["localhost", "127.0.0.1"])
        self.assertFalse(configured["ENABLE_SCHEDULED_IMPORT"])
        self.assertNotIn("update-procurement-data", configured["CELERY_BEAT_SCHEDULE"])
        self.assertIsNone(configured["SECURE_PROXY_SSL_HEADER"])
        self.assertTrue(configured["GPG_LOG_TO_FILES"])
        self.assertEqual(configured["STORAGES"]["staticfiles"]["BACKEND"],
                         "whitenoise.storage.CompressedManifestStaticFilesStorage")

    def test_secret_is_required_and_example_placeholder_is_rejected(self):
        for key in ("", "replace-with-a-generated-secret"):
            with self.subTest(key=key), self.assertRaises(ImproperlyConfigured):
                self.load_settings(SECRET_KEY=key)

    def test_production_rejects_wildcard_and_empty_hosts(self):
        for hosts in ("*", "localhost, *", ""):
            with self.subTest(hosts=hosts), self.assertRaises(ImproperlyConfigured):
                self.load_settings(ALLOWED_HOSTS=hosts)

    def test_boolean_typo_fails_instead_of_enabling_unintended_behavior(self):
        with self.assertRaises(ImproperlyConfigured):
            self.load_settings(ENABLE_SCHEDULED_IMPORT="enabled")

    def test_https_redirect_enables_secure_cookies_without_trusting_proxy(self):
        configured = self.load_settings(SECURE_SSL_REDIRECT="true")
        self.assertTrue(configured["SESSION_COOKIE_SECURE"])
        self.assertTrue(configured["CSRF_COOKIE_SECURE"])
        self.assertIsNone(configured["SECURE_PROXY_SSL_HEADER"])

    def test_explicit_opt_in_adds_schedule(self):
        configured = self.load_settings(ENABLE_SCHEDULED_IMPORT="true")
        self.assertEqual(configured["CELERY_BEAT_SCHEDULE"]["update-procurement-data"]["task"],
                         "apps.core.tasks.update_all_data")

    def test_test_settings_ignore_inherited_production_credentials(self):
        env = {"PGHOST": "production.example.invalid", "PGPASSWORD": "inherited-private-password",
               "OPENROUTER_API_KEY": "inherited-private-api-key"}
        with patch.dict(os.environ, env):
            configured = runpy.run_path(str(Path(settings.BASE_DIR) / "config/test_settings.py"),
                                       run_name="config.test_settings")
        self.assertEqual(configured["DATABASES"]["default"]["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(configured["DATABASES"]["default"]["NAME"], ":memory:")
        self.assertEqual(configured["OPENROUTER_API_KEY"], "")
        self.assertTrue(configured["GPG_DISABLE_LOGGING_INIT"])


class HealthTests(TestCase):
    def test_liveness_has_no_dependency_queries(self):
        with self.assertNumQueries(0), patch("apps.core.views.Redis.from_url") as broker:
            response = self.client.get("/health/live/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        broker.assert_not_called()

    def test_readiness_checks_database_and_broker_without_writes(self):
        with patch("apps.core.views.Redis.from_url") as broker:
            broker.return_value.__enter__.return_value.ping.return_value = True
            with self.assertNumQueries(1):
                response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checks"], {"database": True, "broker": True})

    def test_dependency_failures_return_503_without_error_details(self):
        error = "connection failed: secret-private-password"
        with patch("apps.core.views.connection.cursor", side_effect=OperationalError(error)), \
                patch("apps.core.views.Redis.from_url", side_effect=ConnectionError(error)):
            response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["checks"], {"database": False, "broker": False})
        self.assertNotIn(error, response.content.decode())

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_internal_health_is_exempt_from_https_redirect(self):
        self.assertEqual(self.client.get("/health/live/").status_code, 200)

    def test_health_endpoints_reject_mutating_methods(self):
        for url in ("/health/live/", "/health/ready/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url).status_code, 405)


class ImportOptInTests(SimpleTestCase):
    @override_settings(ENABLE_SCHEDULED_IMPORT=False)
    def test_disabled_task_does_not_run_even_if_old_beat_schedule_enqueues_it(self):
        with patch("apps.core.tasks.run_pipeline") as command:
            self.assertEqual(update_all_data.run(), {"status": "disabled"})
        command.assert_not_called()

    @override_settings(ENABLE_SCHEDULED_IMPORT=True)
    def test_explicit_opt_in_runs_pipeline(self):
        with patch("apps.core.tasks.run_pipeline") as command:
            update_all_data.run()
        command.assert_called_once_with(mode='update', total=500, resume=None)

    @override_settings(ENABLE_SCHEDULED_IMPORT=True)
    def test_retry_and_log_do_not_include_source_exception_values(self):
        marker = "private-source-bin-password-sql-marker"

        def prepare_retry(*, exc, throw, kwargs):
            self.assertFalse(throw)
            self.assertNotIn(marker, str(exc))
            self.assertIsNone(exc.__context__)
            return Retry(exc=exc, when=120)

        with patch("apps.core.tasks.run_pipeline", side_effect=ValueError(marker)), \
                patch.object(update_all_data, "retry", side_effect=prepare_retry), \
                self.assertLogs("apps.core.tasks", level="ERROR") as logs:
            with self.assertRaises(Retry) as raised:
                update_all_data.run()
        self.assertNotIn(marker, " ".join(logs.output))
        self.assertIsNone(logs.records[0].exc_info)
        self.assertNotIn(marker, str(raised.exception))
        self.assertTrue(raised.exception.__suppress_context__)

    @override_settings(ENABLE_SCHEDULED_IMPORT=True)
    def test_exhausted_retries_raise_only_sanitized_failure(self):
        marker = "private-source-sql-on-exhaustion"
        update_all_data.push_request(retries=2, called_directly=False, is_eager=False)
        try:
            with patch("apps.core.tasks.run_pipeline", side_effect=ValueError(marker)), \
                    self.assertLogs("apps.core.tasks", level="ERROR") as logs:
                with self.assertRaises(RuntimeError) as raised:
                    update_all_data.run()
        finally:
            update_all_data.pop_request()
        self.assertEqual(str(raised.exception), "Pipeline failed (ValueError)")
        self.assertNotIn(marker, " ".join(logs.output))
        self.assertTrue(raised.exception.__suppress_context__)

    @override_settings(ENABLE_SCHEDULED_IMPORT=True)
    def test_failure_publishing_retry_does_not_expose_broker_credentials(self):
        marker = "private-source-or-broker-password"
        with patch("apps.core.tasks.run_pipeline", side_effect=ValueError(marker)), \
                patch.object(update_all_data, "retry", side_effect=ConnectionError(marker)), \
                self.assertLogs("apps.core.tasks", level="ERROR") as logs:
            try:
                update_all_data.run()
            except RuntimeError as exc:
                formatted = "".join(traceback.format_exception(exc))
            else:
                self.fail("Expected sanitized retry publication failure")
        self.assertNotIn(marker, " ".join(logs.output))
        self.assertNotIn(marker, formatted)
        self.assertIn("Pipeline failed (ValueError)", formatted)
