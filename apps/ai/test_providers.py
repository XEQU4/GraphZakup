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
        self.analysis = SimpleNamespace(findings=[{'id': 'known', 'code': 'shared_address',
            'company_ids': [1, 2], 'contribution': 2,
            'statements': ['First verified wording.', 'Second verified wording.'],
            'limitations': ['The latest source attempt was unsuccessful; the last success is retained.']}],
            inputs={'graph': {'nodes': [{'kind': 'company', 'company_id': 1, 'name': 'Synthetic Cedar'},
                                       {'kind': 'company', 'company_id': 2, 'name': 'Synthetic Pine'}]}},
            metrics={'review_priority': 2}, limitations=['Uncalibrated index.'])

    def valid_plan(self, variant=1):
        return {'narrative': {'paragraphs': [{'text': '{{C1}} and {{C2}} share a recorded address. '
                'This match alone does not establish affiliation.', 'finding_ids': ['known']}],
                'checks': [{'text': 'Confirm whether the address is a shared office or a service provider.',
                            'finding_ids': ['known']}]}, 'risk_estimate': None, 'risk_evidence': []}

    def result(self, plan=None, **options):
        return {'done': True, 'done_reason': 'stop', 'message': {'content': json.dumps(plan or self.valid_plan())},
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
        self.assertTrue(any('unsuccessful' in limit for limit in facts['findings'][0]['limitations']))
        self.assertEqual(plan['sections'][0]['variant'], 0)
        self.assertIn('{{C1}}', plan['narrative']['paragraphs'][0]['text'])
        self.assertIn('narrative', request['body']['format']['required'])
        self.assertNotIn('sections', request['body']['format']['properties'])
        self.assertNotIn('variants', facts['findings'][0])
        self.assertIn('recorded address', facts['findings'][0]['fact'])
        self.assertEqual(usage['output_tokens'], 30)
        self.assertNotIn('Authorization', request['headers'])

    def test_invalid_and_truncated_outputs_are_rejected(self):
        for value in ([], self.result(done=False), self.result(done_reason='length'),
                      self.result({'sections': [{'finding_id': 'invented', 'variant': 0}],
                                   'risk_estimate': None, 'risk_evidence': []})):
            self.responses.append((200, 'application/json', value))
            with self.assertRaises(ProviderError):
                generate(self.analysis, configuration())

    def test_live_legacy_plan_without_model_prose_is_rejected(self):
        self.responses.append((200, 'application/json', self.result({
            'sections': [{'finding_id': 'known', 'variant': 0}],
            'risk_estimate': None, 'risk_evidence': []})))
        with self.assertRaisesRegex(ProviderError, 'output_schema_invalid'):
            generate(self.analysis, configuration())

    def test_model_prose_with_invented_number_uses_a_safe_validation_code(self):
        plan = self.valid_plan()
        plan['narrative']['paragraphs'][0]['text'] = 'The 99 companies have a matching recorded address.'
        self.responses.append((200, 'application/json', self.result(plan)))
        self.responses.append((200, 'application/json', self.result(plan)))
        with self.assertRaisesRegex(ProviderError, 'output_narrative_number_unsupported'):
            generate(self.analysis, configuration())
        self.assertEqual(len(self.requests), 2)

    def test_local_repair_rewrites_with_same_facts_and_sums_both_attempts(self):
        invalid = self.valid_plan()
        invalid['narrative']['paragraphs'][0]['text'] = 'These companies coordinated their bids.'
        self.responses.append((200, 'application/json', self.result(invalid)))
        self.responses.append((200, 'application/json', self.result()))
        plan, usage = generate(self.analysis, configuration())
        self.assertEqual((usage['input_tokens'], usage['output_tokens'], usage['attempts']), (200, 60, 2))
        self.assertEqual(len(self.requests), 2)
        first, second = [request['body'] for request in self.requests]
        self.assertEqual(first['format'], second['format'])
        self.assertEqual(first['messages'], second['messages'][:-1])
        self.assertIn('output_claim_unsupported', second['messages'][-1]['content'])
        self.assertNotIn(invalid['narrative']['paragraphs'][0]['text'], second['messages'][-1]['content'])
        self.assertIn('share a recorded address', plan['narrative']['paragraphs'][0]['text'])

    def test_remote_provider_never_retries_invalid_prose(self):
        invalid = self.valid_plan()
        invalid['narrative']['paragraphs'][0]['text'] = 'The companies coordinated their bids.'
        payload = {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(invalid)}}],
                   'usage': {'prompt_tokens': 123, 'completion_tokens': 25}}
        with override_settings(AI_PROVIDER='openai', AI_MODEL='gpt-4o', AI_BASE_URL='',
                               AI_API_KEY='offline-placeholder', AI_ALLOW_PAID=True):
            with patch('requests.Session.post') as post:
                response = post.return_value.__enter__.return_value
                response.status_code, response.headers = 200, {'Content-Type': 'application/json'}
                response.iter_content.return_value = [json.dumps(payload).encode()]
                with self.assertRaisesRegex(ProviderError, 'output_claim_unsupported'):
                    generate(self.analysis, configuration())
                self.assertEqual(post.call_count, 1)

    def test_non_contact_repair_uses_its_recorded_interpretation_without_service_explanation(self):
        self.analysis.findings[0]['evidence'] = []
        self.analysis.inputs['graph']['links'] = []
        self.analysis.inputs['company_checks'] = [{'company_id': 1, 'status': 'fresh',
            'values': {'kgd_total_arrears': '123.45', 'kgd_reporting_dates': ['2026-10-08']}}]
        self.analysis.metrics.update(stored_contract_count=2, stored_contract_amount='1000.00')
        for code, phrase in [('shared_director', 'decision-making authority worth checking'),
                             ('company_arrears', 'This dated result concerns a company.'),
                             ('stored_contract_summary', 'Contract totals describe activity')]:
            with self.subTest(code=code):
                self.requests.clear()
                self.analysis.findings[0]['code'] = code
                invalid = self.valid_plan()
                invalid['narrative']['paragraphs'][0]['text'] = 'These companies coordinated their bids.'
                valid = self.valid_plan()
                valid['narrative']['paragraphs'][0]['text'] = '{{C1}} and {{C2}} have a saved record requiring further checking.'
                valid['narrative']['checks'][0]['text'] = 'Obtain the relevant dated records to verify the finding.'
                self.responses.extend([(200, 'application/json', self.result(invalid)),
                                       (200, 'application/json', self.result(valid))])
                _, usage = generate(self.analysis, configuration())
                correction = self.requests[1]['body']['messages'][-1]['content']
                self.assertIn(phrase, correction)
                self.assertNotIn('ordinary service explanation', correction)
                self.assertEqual(usage['attempts'], 2)

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
        plan = self.valid_plan(variant=0)
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
