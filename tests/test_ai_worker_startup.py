"""Model startup guards never consume a task, download weights or infer text."""

import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
import requests

from apps.ai.providers import configuration, ProviderError
from config.ai_worker import MODEL_METADATA_LIMIT, WORKER_ARGUMENTS, main, require_local_model


class AIWorkerStartupTests(SimpleTestCase):
    def check_response(self, status, content):
        probe = SimpleNamespace(provider="ollama", base_url="http://ollama:11434", model="qwen3:4b")
        with patch("config.ai_worker.requests.Session") as session_type:
            session = session_type.return_value.__enter__.return_value
            response = session.post.return_value.__enter__.return_value
            response.status_code = status
            response.iter_content.return_value = [content]
            require_local_model(probe)
            return session

    def test_template_and_hosted_workers_never_probe_an_ollama_endpoint(self):
        with patch("config.ai_worker.requests.Session") as session:
            for provider in ("template", "openai", "openrouter"):
                require_local_model(SimpleNamespace(provider=provider))
            session.assert_not_called()

    def test_available_model_uses_metadata_only_and_no_redirect_or_proxy(self):
        session = self.check_response(200, json.dumps({"details": {"family": "qwen3"}}).encode())
        session.post.assert_called_once_with(
            "http://ollama:11434/api/show", json={"model": "qwen3:4b"},
            timeout=(3, 5), allow_redirects=False, stream=True,
        )
        self.assertFalse(session.trust_env)

    def test_missing_model_server_error_and_redirect_refuse_startup(self):
        for status in (404, 500, 302):
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, "model_metadata_unavailable"):
                self.check_response(status, b'{"error":"synthetic missing model"}')

    def test_invalid_or_oversized_model_metadata_refuses_startup(self):
        for body in (b"not-json", b"[]", b"{}", b'{"details":null}', b"x" * (MODEL_METADATA_LIMIT + 1)):
            with self.subTest(size=len(body)), self.assertRaises(ValueError):
                self.check_response(200, body)

    def test_metadata_timeout_is_not_retried(self):
        probe = SimpleNamespace(provider="ollama", base_url="http://ollama:11434", model="qwen3:4b")
        with patch("config.ai_worker.requests.Session") as session_type:
            session = session_type.return_value.__enter__.return_value
            session.post.side_effect = requests.Timeout("synthetic timeout")
            with self.assertRaises(requests.Timeout):
                require_local_model(probe)
            self.assertEqual(session.post.call_count, 1)

    def test_failed_model_never_starts_celery_or_logs_transport_details(self):
        with patch("django.setup"), patch("apps.ai.providers.configuration"), patch(
            "config.ai_worker.require_local_model", side_effect=requests.ConnectionError("private transport detail"),
        ), patch("config.ai_worker.os.execvp") as execute, patch("sys.stderr", new_callable=StringIO) as output:
            self.assertEqual(main(), 1)
            execute.assert_not_called()
            self.assertIn("AI worker not started", output.getvalue())
            self.assertNotIn("private transport detail", output.getvalue())

    def test_ready_configuration_starts_only_the_ai_queue(self):
        with patch("django.setup"), patch("apps.ai.providers.configuration") as configure, patch(
            "config.ai_worker.require_local_model",
        ) as check, patch("config.ai_worker.os.execvp") as execute:
            main()
            check.assert_called_once_with(configure.return_value)
            execute.assert_called_once_with("celery", WORKER_ARGUMENTS)
            self.assertIn("--queues=iz2-ai", WORKER_ARGUMENTS)

    @override_settings(AI_PROVIDER="ollama", AI_MODEL="selected:4b", AI_BASE_URL="",
                       AI_OLLAMA_BASE_URL="http://ollama-gpu:11434")
    def test_gpu_runtime_uses_same_validated_model_configuration_as_jobs(self):
        provider = configuration()
        self.assertEqual(provider.base_url, "http://ollama-gpu:11434")
        self.assertEqual(provider.model, "selected:4b")
        with override_settings(AI_BASE_URL="https://untrusted.example.test"):
            with self.assertRaisesRegex(ProviderError, "local_endpoint_required"):
                configuration()

    @override_settings(AI_PROVIDER="ollama", AI_MODEL="", AI_BASE_URL="",
                       AI_OLLAMA_BASE_URL="http://ollama:11434")
    def test_blank_model_uses_provider_default_and_cloud_model_stays_blocked(self):
        self.assertEqual(configuration().model, "qwen3:4b")
        with override_settings(AI_MODEL="synthetic-cloud"):
            with self.assertRaisesRegex(ProviderError, "local_model_required"):
                configuration()
