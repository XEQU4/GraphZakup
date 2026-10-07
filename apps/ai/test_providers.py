"""Exercise the real bounded HTTP adapter against a local synthetic server."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from .providers import generate, configuration, ProviderError


class ProviderHTTPTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.responses, cls.requests = [], []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                cls.requests.append({'path': self.path, 'headers': dict(self.headers), 'body': body})
                status, content_type, value = cls.responses.pop(0)
                encoded = json.dumps(value).encode()
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        super().tearDownClass()

    def setUp(self):
        self.responses.clear()
        self.requests.clear()
        self.settings_override = override_settings(AI_PROVIDER='ollama', AI_MODEL='qwen3:4b',
            AI_BASE_URL=f'http://127.0.0.1:{self.server.server_address[1]}')
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.analysis = SimpleNamespace(findings=[{'id': 'known',
            'statements': ['First verified wording.', 'Second verified wording.'],
            'limitations': ['The latest source attempt was unsuccessful; the last success is retained.']}],
                                        metrics={'review_priority': 2}, limitations=['Uncalibrated index.'])

    def result(self, plan=None, **options):
        return {'done': True, 'done_reason': 'stop', 'message': {'content': json.dumps(plan or {
            'sections': [{'finding_id': 'known', 'variant': 1}], 'risk_estimate': None, 'risk_evidence': []})},
            'prompt_eval_count': 100, 'eval_count': 30, **options}

    def test_native_ollama_schema_and_token_limits(self):
        self.responses.append((200, 'application/json', self.result()))
        plan, usage = generate(self.analysis, configuration())
        request = self.requests[0]
        self.assertEqual(request['path'], '/api/chat')
        self.assertEqual(request['body']['options']['num_ctx'], 4096)
        self.assertEqual(request['body']['options']['num_predict'], 1024)
        self.assertFalse(request['body']['think'])
        self.assertFalse(request['body']['stream'])
        facts = json.loads(request['body']['messages'][1]['content'])
        self.assertIn('unsuccessful', facts['findings'][0]['limitations'][0])
        self.assertEqual(plan['sections'][0]['variant'], 1)
        self.assertEqual(usage['output_tokens'], 30)
        self.assertNotIn('Authorization', request['headers'])

    def test_invalid_and_truncated_outputs_are_rejected(self):
        for value in ([], self.result(done=False), self.result(done_reason='length'),
                      self.result({'sections': [{'finding_id': 'invented', 'variant': 0}],
                                   'risk_estimate': None, 'risk_evidence': []})):
            self.responses.append((200, 'application/json', value))
            with self.assertRaises(ProviderError):
                generate(self.analysis, configuration())

    def test_http_and_content_type_failures_do_not_expose_response_body(self):
        for status, content_type in ((503, 'application/json'), (200, 'text/html')):
            self.responses.append((status, content_type, {'private': 'synthetic confidential response'}))
            with self.assertRaises(ProviderError) as error:
                generate(self.analysis, configuration())
            self.assertNotIn('confidential', str(error.exception))

    def test_response_size_cap_is_enforced(self):
        self.responses.append((200, 'application/json', {'padding': 'x' * 530000}))
        with self.assertRaisesRegex(ProviderError, 'provider_response_limit'):
            generate(self.analysis, configuration())

    def test_cloud_model_and_remote_ollama_url_are_rejected(self):
        with override_settings(AI_MODEL='example:cloud'):
            with self.assertRaisesRegex(ProviderError, 'local_model_required'):
                configuration()
        with override_settings(AI_BASE_URL='https://cloud.example.invalid'):
            with self.assertRaisesRegex(ProviderError, 'local_endpoint_required'):
                configuration()

    def test_openai_request_contract_without_remote_generation(self):
        plan = {'sections': [{'finding_id': 'known', 'variant': 0}], 'risk_estimate': None, 'risk_evidence': []}
        payload = {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(plan)}}],
                   'usage': {'prompt_tokens': 123, 'completion_tokens': 25}}
        with override_settings(AI_PROVIDER='openai', AI_MODEL='gpt-4o', AI_BASE_URL='',
                               AI_API_KEY='offline-placeholder', AI_ALLOW_PAID=True):
            with patch('requests.Session.post') as post:
                response = post.return_value.__enter__.return_value
                response.status_code, response.headers = 200, {'Content-Type': 'application/json'}
                response.iter_content.return_value = [json.dumps(payload).encode()]
                _, usage = generate(self.analysis, configuration())
                request = post.call_args.kwargs
                self.assertEqual(post.call_args.args[0], 'https://api.openai.com/v1/chat/completions')
                self.assertEqual(request['json']['response_format']['type'], 'json_schema')
                self.assertEqual(request['json']['max_tokens'], 1024)
                self.assertFalse(request['allow_redirects'])
        self.assertEqual(usage['input_tokens'], 123)
