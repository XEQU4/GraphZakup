import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from config.beat import HealthyDatabaseScheduler
from config.container_health import beat_is_healthy


class ContainerHeartbeatTests(SimpleTestCase):
    def test_missing_stale_and_future_heartbeats_are_unhealthy(self):
        with TemporaryDirectory() as directory:
            heartbeat = Path(directory) / "heartbeat"
            self.assertFalse(beat_is_healthy(heartbeat, now=1000))
            heartbeat.touch()
            os.utime(heartbeat, (1000, 1000))
            self.assertTrue(beat_is_healthy(heartbeat, now=1000))
            self.assertTrue(beat_is_healthy(heartbeat, now=1090))
            self.assertFalse(beat_is_healthy(heartbeat, now=1091))
            self.assertFalse(beat_is_healthy(heartbeat, now=999))

    def test_scheduler_refreshes_heartbeat_only_after_completed_tick(self):
        scheduler = object.__new__(HealthyDatabaseScheduler)
        with TemporaryDirectory() as directory:
            heartbeat = Path(directory) / "heartbeat"
            with patch("config.beat.BEAT_HEARTBEAT", heartbeat), patch(
                "config.beat.DatabaseScheduler.tick", return_value=5,
            ) as tick:
                self.assertEqual(scheduler.tick(), 5)
                self.assertTrue(beat_is_healthy(heartbeat))
                os.utime(heartbeat, (1000, 1000))
                tick.side_effect = RuntimeError("Synthetic scheduler failure")
                with self.assertRaises(RuntimeError):
                    scheduler.tick()
                self.assertEqual(heartbeat.stat().st_mtime, 1000)


class ContainerHTTPConfigurationTests(SimpleTestCase):
    def load_configuration(self, environment):
        specification = importlib.util.spec_from_file_location(
            "isolated_gunicorn_settings", Path(__file__).resolve().parents[1] / "config/gunicorn.py",
        )
        configuration = importlib.util.module_from_spec(specification)
        with patch.dict(os.environ, environment, clear=True):
            specification.loader.exec_module(configuration)
        return configuration

    def test_runtime_worker_and_shutdown_settings_are_configurable(self):
        configuration = self.load_configuration({
            "PORT": "8080", "WEB_CONCURRENCY": "3", "GUNICORN_TIMEOUT": "90",
            "GUNICORN_GRACEFUL_TIMEOUT": "20", "GUNICORN_MAX_REQUESTS": "500",
            "GUNICORN_MAX_REQUESTS_JITTER": "0",
        })
        self.assertEqual(configuration.bind, "0.0.0.0:8080")
        self.assertEqual(configuration.workers, 3)
        self.assertEqual(configuration.timeout, 90)
        self.assertEqual(configuration.graceful_timeout, 20)
        self.assertEqual(configuration.max_requests, 500)
        self.assertEqual(configuration.max_requests_jitter, 0)
        self.assertNotIn("%(q)", configuration.access_log_format)
        self.assertEqual(configuration.forwarded_allow_ips, "")

    def test_invalid_worker_or_unbounded_timeout_fails_startup(self):
        for setting in ("WEB_CONCURRENCY", "GUNICORN_TIMEOUT", "GUNICORN_GRACEFUL_TIMEOUT"):
            with self.subTest(setting=setting), self.assertRaises(ValueError):
                self.load_configuration({setting: "0"})
