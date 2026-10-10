import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from scripts.prepare_deploy import prepare


class DeploymentEnvironmentTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        template = Path(__file__).resolve().parents[1] / ".env.example"
        (self.root / ".env.example").write_bytes(template.read_bytes())
        (self.root / "artifacts").mkdir()
        patcher = patch("scripts.prepare_deploy.PROJECT_ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_generated_environment_has_unique_secrets_and_disabled_collection(self):
        with patch("scripts.prepare_deploy.PROJECT_ROOT", self.root):
            first = self.root / ".env.first"
            second = self.root / "artifacts" / "second.env"
            prepare(first, "iz2-synthetic-first")
            prepare(second, "iz2-synthetic-second")
            values = {}
            for path in (first, second):
                values[path] = dict(
                    line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines()
                    if line and not line.startswith("#") and "=" in line
                )
                for name in ("SECRET_KEY", "DB_PASSWORD"):
                    self.assertGreaterEqual(len(values[path][name]), 48)
                    self.assertNotIn("replace-with", values[path][name])
                for name in (
                    "ENABLE_SCHEDULED_IMPORT", "ENABLE_SCHEDULED_KGD",
                    "ENABLE_KGD_CHECKS", "ENABLE_BACKGROUND_AI", "AI_ALLOW_PAID",
                ):
                    self.assertEqual(values[path][name], "false")
                for name in ("AI_API_KEY", "OPENROUTER_API_KEY", "GOSZAKUP_TOKEN", "KGD_PORTAL_TOKEN"):
                    self.assertEqual(values[path][name], "")
                self.assertEqual(values[path]["AI_TIMEOUT_SECONDS"], "180")
                self.assertEqual(values[path]["AI_MAX_OUTPUT_TOKENS"], "2048")
                if os.name == "posix":
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(values[first]["COMPOSE_PROJECT_NAME"], "iz2-synthetic-first")
            self.assertNotEqual(values[first]["SECRET_KEY"], values[second]["SECRET_KEY"])
            self.assertNotEqual(values[first]["DB_PASSWORD"], values[second]["DB_PASSWORD"])

    def test_existing_environment_is_never_replaced(self):
        with patch("scripts.prepare_deploy.PROJECT_ROOT", self.root):
            path = self.root / ".env.docker"
            original = b"Synthetic original environment\r\n"
            path.write_bytes(original)
            with self.assertRaises(FileExistsError):
                prepare(path, "iz2-synthetic")
            self.assertEqual(path.read_bytes(), original)

    def test_cpu_and_gpu_settings_select_one_coherent_model_runtime(self):
        for runtime, profile, host in (
            ("cpu", "local-ai", "ollama"), ("gpu", "local-ai-gpu", "ollama-gpu"),
        ):
            with self.subTest(runtime=runtime):
                path = self.root / f".env.{runtime}"
                prepare(path, "iz2-synthetic", ai=runtime)
                values = dict(line.split("=", 1) for line in path.read_text().splitlines()
                              if line and not line.startswith("#") and "=" in line)
                self.assertEqual(values["COMPOSE_PROFILES"], profile)
                self.assertEqual(values["AI_PROVIDER"], "ollama")
                self.assertEqual(values["AI_MODEL"], values["OLLAMA_MODEL"])
                self.assertEqual(values["DOCKER_OLLAMA_BASE_URL"], f"http://{host}:11434")
                self.assertEqual(values["AI_ALLOW_PAID"], "false")
                self.assertEqual(values["ENABLE_SCHEDULED_IMPORT"], "false")

    def test_https_settings_include_single_proxy_trust_and_secure_cookies(self):
        path = self.root / ".env.server"
        prepare(path, "iz2-synthetic", ai="cpu", domain="IZ2.Example.Test", acme_email="ops@example.test")
        values = dict(line.split("=", 1) for line in path.read_text().splitlines()
                      if line and not line.startswith("#") and "=" in line)
        self.assertEqual(values["COMPOSE_PROFILES"], "local-ai,https")
        self.assertEqual(values["SITE_DOMAIN"], "iz2.example.test")
        self.assertEqual(values["CSRF_TRUSTED_ORIGINS"], "https://iz2.example.test")
        self.assertEqual(values["AUTH_TRUSTED_PROXY_CIDRS"], values["PROXY_ADDRESS"] + "/32")
        for flag in ("TRUST_PROXY_SSL_HEADER", "SECURE_SSL_REDIRECT", "SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE"):
            self.assertEqual(values[flag], "true")
        self.assertEqual(values["SECURE_HSTS_SECONDS"], "0")

    def test_invalid_runtime_and_https_configuration_do_not_create_an_environment(self):
        path = self.root / ".env.invalid"
        for values in (
            {"ai": "both"}, {"domain": "iz2.example.test"}, {"acme_email": "ops@example.test"},
            {"domain": "https://iz2.example.test", "acme_email": "ops@example.test"},
            {"domain": "iz2.example.test:443", "acme_email": "ops@example.test"},
            {"domain": "iz2.example.test\nOTHER=value", "acme_email": "ops@example.test"},
            {"domain": "iz2.example.test", "acme_email": "ops@example.test\nOTHER=value"},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                prepare(path, "iz2-synthetic", **values)
            self.assertFalse(path.exists())

    def test_native_environment_is_rejected_before_any_write(self):
        with self.assertRaisesRegex(ValueError, "native .env unchanged"):
            prepare(self.root / ".env", "iz2-synthetic")

    def test_invalid_namespace_does_not_create_file(self):
        with patch("scripts.prepare_deploy.PROJECT_ROOT", self.root):
            path = self.root / ".env.docker"
            for project in ("", "UPPERCASE", "../other-project", "with spaces", "-bad", "x" * 64):
                with self.subTest(project=project), self.assertRaises(ValueError):
                    prepare(path, project)
                self.assertFalse(path.exists())

    def test_public_template_and_nonignored_paths_are_rejected(self):
        template = self.root / ".env.example"
        original = template.read_bytes()
        for path in (
            template, self.root / ".env.EXAMPLE", self.root / "credentials.txt",
            self.root / "deploy" / ".env.docker", self.root.parent / ".env.other",
            self.root / "artifacts" / ".." / "credentials.env",
        ):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "ignored artifacts child"):
                prepare(path, "iz2-synthetic")
        self.assertEqual(template.read_bytes(), original)

    def test_resolved_artifact_escape_is_rejected(self):
        candidate = self.root / "artifacts" / "linked" / "credentials.env"
        actual_resolve = Path.resolve

        def resolve_path(path, *args, **kwargs):
            if path == candidate:
                return self.root.parent / "outside" / "credentials.env"
            return actual_resolve(path, *args, **kwargs)

        # Windows may require administrator privileges for real symlinks.
        with patch.object(Path, "resolve", autospec=True, side_effect=resolve_path):
            with self.assertRaisesRegex(ValueError, "ignored artifacts child"):
                prepare(candidate, "iz2-synthetic")
        self.assertFalse(candidate.exists())

        if os.name == "posix":
            with TemporaryDirectory() as outside:
                link = self.root / "artifacts" / "linked"
                link.symlink_to(outside, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, "ignored artifacts child"):
                    prepare(link / "credentials.env", "iz2-synthetic")
                self.assertFalse((Path(outside) / "credentials.env").exists())
