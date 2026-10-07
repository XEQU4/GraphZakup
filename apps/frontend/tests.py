"""SPA integration checks without working data or a frontend development server."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import SimpleTestCase, override_settings


class FrontendServingTests(SimpleTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.manifest = self.base / 'static/frontend/vite-manifest.json'
        self.manifest.parent.mkdir(parents=True)
        (self.base / 'collected').mkdir()
        self.override = override_settings(BASE_DIR=self.base, STATIC_ROOT=self.base / 'collected')
        self.override.enable()
        self.addCleanup(self.override.disable)

    def write_manifest(self, value):
        self.manifest.write_text(json.dumps(value), encoding='utf-8')

    def test_home_redirects_to_react_and_legacy_dashboard_is_retained(self):
        self.assertRedirects(self.client.get('/'), '/app/', fetch_redirect_response=False)
        from django.urls import reverse
        self.assertTrue(reverse('dashboard:index').startswith('/legacy/'))

    def test_missing_build_has_actionable_service_unavailable_response(self):
        response = self.client.get('/app/companies/42')
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, 'collectstatic', status_code=503)

    def test_compiled_entry_is_served_on_deep_routes_without_bootstrap(self):
        self.write_manifest({'index.html': {'file': 'assets/main-abcd.js', 'css': ['assets/main-abcd.css']}})
        response = self.client.get('/app/companies/42')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/static/frontend/assets/main-abcd.js')
        self.assertContains(response, '/static/frontend/assets/main-abcd.css')
        self.assertContains(response, 'id="root"')
        self.assertNotContains(response, 'bootstrap')
        self.assertEqual(response['Cache-Control'], 'no-cache')

    def test_corrupt_or_traversing_manifest_fails_closed(self):
        for entry in [None, {'file': '../private.js'}, {'file': '/assets/evil.js'}, {'file': 'assets/../../evil.js'}, {'file': 17}]:
            with self.subTest(entry=entry):
                self.write_manifest({'index.html': entry})
                self.assertEqual(self.client.get('/app/').status_code, 503)
        self.manifest.write_text('{invalid', encoding='utf-8')
        self.assertEqual(self.client.get('/app/').status_code, 503)

    def test_collected_manifest_takes_precedence_over_source_build(self):
        self.write_manifest({'index.html': {'file': 'assets/source.js'}})
        collected = self.base / 'collected/frontend/vite-manifest.json'
        collected.parent.mkdir(parents=True)
        collected.write_text(json.dumps({'index.html': {'file': 'assets/collected.js'}}), encoding='utf-8')
        response = self.client.get('/app/')
        self.assertContains(response, 'assets/collected.js')
        self.assertNotContains(response, 'assets/source.js')

    def test_entry_urls_keep_vite_hashes_under_manifest_storage(self):
        self.write_manifest({'index.html': {'file': 'assets/index-ABC123.js', 'css': ['assets/index-ABC123.css']}})
        mappings = {'frontend/assets/index-ABC123.js':'frontend/assets/index-ABC123.abcdef123456.js', 'frontend/assets/index-ABC123.css':'frontend/assets/index-ABC123.abcdef123456.css', 'frontend/favicon.svg':'frontend/favicon.abcdef123456.svg'}
        (self.base / 'collected/staticfiles.json').write_text(json.dumps({'version':'1.1','paths':mappings,'hash':'test'}),encoding='utf-8')
        with override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.InMemoryStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'}}):
            response=self.client.get('/app/')
            self.assertContains(response, 'src="/static/frontend/assets/index-ABC123.js"')
            self.assertContains(response, 'href="/static/frontend/assets/index-ABC123.css"')
            self.assertNotContains(response, 'index-ABC123.abcdef123456')
