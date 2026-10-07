"""Swagger must work with collected local assets under strict production storage."""
import json
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.test import Client, SimpleTestCase, override_settings
from whitenoise.storage import CompressedManifestStaticFilesStorage


class SwaggerAssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script" and attributes.get("src"):
            self.urls.append(attributes["src"])
        elif tag == "link" and attributes.get("rel") in {"stylesheet", "icon"}:
            self.urls.append(attributes["href"])


class SwaggerManifestTests(SimpleTestCase):
    def setUp(self):
        static_root = tempfile.TemporaryDirectory(prefix="iz2-swagger-static-")
        self.addCleanup(static_root.cleanup)
        self.static_root = Path(static_root.name)
        settings = override_settings(
            DEBUG=False,
            STATIC_ROOT=self.static_root,
            WHITENOISE_AUTOREFRESH=False,
            WHITENOISE_USE_FINDERS=False,
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                "staticfiles": {
                    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
                },
            },
        )
        settings.enable()
        self.addCleanup(settings.disable)

    def test_missing_sidecar_manifest_is_not_silently_served_from_finders(self):
        self.assertIsInstance(staticfiles_storage, CompressedManifestStaticFilesStorage)
        self.assertTrue(staticfiles_storage.manifest_strict)
        with self.assertRaisesRegex(ValueError, "Missing staticfiles manifest entry.*drf_spectacular_sidecar"):
            staticfiles_storage.url("drf_spectacular_sidecar/swagger-ui-dist/swagger-ui.css")
        response = Client().get("/api/v1/docs/")
        self.assertEqual(response.status_code, 500)

    def test_collected_swagger_schema_and_hashed_local_assets_are_served(self):
        call_command("collectstatic", interactive=False, verbosity=0)
        manifest = json.loads((self.static_root / "staticfiles.json").read_text(encoding="utf-8"))
        client = Client()
        response = client.get("/api/v1/docs/")
        self.assertEqual(response.status_code, 200)
        assets = SwaggerAssetParser()
        assets.feed(response.content.decode())
        expected_names = {
            "swagger-ui.css",
            "swagger-ui-bundle.js",
            "swagger-ui-standalone-preset.js",
            "favicon-32x32.png",
        }
        expected_urls = {
            "/static/" + manifest["paths"]["drf_spectacular_sidecar/swagger-ui-dist/" + name]
            for name in expected_names
        }
        self.assertEqual(set(assets.urls), expected_urls)
        for url in assets.urls:
            parsed = urlsplit(url)
            self.assertEqual((parsed.scheme, parsed.netloc), ("", ""))
            self.assertRegex(parsed.path, r"\.[a-f0-9]{12}\.")
            with self.subTest(asset=url):
                asset = client.get(url)
                self.assertEqual(asset.status_code, 200)
                self.assertIn("immutable", asset["Cache-Control"])
                self.assertTrue(b"".join(asset.streaming_content))
                asset.close()
        schema = client.get("/api/v1/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json")
        self.assertEqual(schema.status_code, 200)
        self.assertIn("/api/v1/companies/", json.loads(schema.content)["paths"])
