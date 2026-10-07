"""Offline API task permissions, explicit starts, deduplication and saved status."""
import json
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ai.models import AnalysisJob, AnalysisSnapshot, AnalysisState, Explanation
from apps.companies.models import Supplier
from apps.graph.models import GraphRebuildJob, GraphSnapshot, RiskCluster
from apps.ingestion.models import IngestionRun


class JobFixtures:
    @classmethod
    def create_group(cls):
        companies = [Supplier.objects.create(bin=f'{number:012}', name=f'Synthetic company {number}')
                     for number in (1, 2)]
        cluster = RiskCluster.objects.create(name='Synthetic group')
        cluster.suppliers.set(companies)
        snapshot = GraphSnapshot.objects.create(cluster=cluster, version=1,
            graph_hash='a' * 64, algorithm_version='synthetic', state='active',
            as_of=timezone.localdate(), member_ids=[item.pk for item in companies],
            payload={'nodes': [{'id': f'company:{item.pk}', 'kind': 'company',
                               'company_id': item.pk, 'label': item.name, 'bin': item.bin}
                              for item in companies], 'links': []})
        cluster.current_snapshot = snapshot
        cluster.save(update_fields=['current_snapshot'])
        return cluster, snapshot, companies

    def analysis_record(self):
        return AnalysisSnapshot.objects.create(cluster=self.cluster, graph_snapshot=self.snapshot,
            version=7, analysis_hash='b' * 64, input_hash='c' * 64, rules_version='synthetic',
            as_of=timezone.localdate(), metrics={'review_priority': 2})

    def explanation_record(self, analysis, score=92):
        return Explanation.objects.create(analysis=analysis, reuse_key='d' * 64,
            provider='synthetic', model='synthetic-local', prompt_version='synthetic',
            status='ready', text='Saved synthetic explanation.', experimental_score=score,
            experimental_evidence=['synthetic-finding'])


class JobApiTests(JobFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(username='synthetic-staff', is_staff=True)
        cls.viewer = get_user_model().objects.create_user(username='synthetic-viewer')
        cls.cluster, cls.snapshot, cls.companies = cls.create_group()

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.staff)
        self.graph_url = reverse('api:cluster-recalculate', args=[self.cluster.uuid])
        self.analysis_url = reverse('api:cluster-explanation-start', args=[self.cluster.uuid])
        self.graph_dispatch = self.patch_external('apps.graph.jobs.rebuild_graph_task.delay')
        self.analysis_dispatch = self.patch_external('apps.ai.jobs.analyse_cluster_task.delay')
        self.network = self.patch_external('requests.sessions.Session.request', side_effect=AssertionError('External HTTP forbidden'))

    def patch_external(self, target, **kwargs):
        mocked = patch(target, **kwargs)
        result = mocked.start()
        self.addCleanup(mocked.stop)
        return result

    def test_anonymous_and_non_staff_cannot_launch_or_read_jobs(self):
        graph_job = GraphRebuildJob.objects.create(dedup_key='e' * 64, supplier_ids=[])
        analysis_job = AnalysisJob.objects.create(graph_snapshot=self.snapshot,
            input_hash='f' * 64, dedup_key='1' * 64, as_of=timezone.localdate())
        run = IngestionRun.objects.create(mode='synthetic')
        urls = [reverse('api:graph-job-detail', args=[graph_job.uuid]),
                reverse('api:analysis-job-detail', args=[analysis_job.uuid]),
                reverse('api:ingestion-run-detail', args=[run.uuid]),
                reverse('api:ingestion-run-list')]
        for user in (None, self.viewer):
            self.client.force_authenticate(user=user)
            for url in urls:
                with self.subTest(user=user, url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(response.json()['error']['code'], 'not_authenticated' if user is None else 'permission_denied')
            for url in (self.graph_url, self.analysis_url):
                self.assertEqual(self.client.post(url, {}, format='json').status_code, 403)
        self.assertEqual(GraphRebuildJob.objects.count(), 1)
        self.assertEqual(AnalysisJob.objects.count(), 1)

    def test_authenticated_session_requires_csrf_for_job_starts(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        for url in (self.graph_url, self.analysis_url):
            response = client.post(url, '{}', content_type='application/json')
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['error']['code'], 'permission_denied')
        self.assertEqual(GraphRebuildJob.objects.count(), 0)
        self.assertEqual(AnalysisJob.objects.count(), 0)
        self.graph_dispatch.assert_not_called()
        self.analysis_dispatch.assert_not_called()
        request = RequestFactory().get('/')
        token = get_token(request)
        client.cookies['csrftoken'] = request.META['CSRF_COOKIE']
        with patch('apps.graph.jobs.rebuild_graph_task.delay') as dispatch, self.captureOnCommitCallbacks(execute=True):
            response = client.post(self.graph_url, '{}', content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 202)
        dispatch.assert_called_once()

    def test_graph_start_deduplicates_and_dispatches_after_commit(self):
        with patch('apps.graph.jobs.rebuild_graph_task.delay') as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                first = self.client.post(self.graph_url, {}, format='json')
                second = self.client.post(self.graph_url, {}, format='json')
        self.assertEqual((first.status_code, second.status_code), (202, 202))
        self.assertTrue(first.json()['created'])
        self.assertFalse(second.json()['created'])
        self.assertEqual(first.json()['job'], second.json()['job'])
        self.assertEqual(first.json()['status'], 'pending')
        self.assertEqual(first.json()['results'], [])
        job = GraphRebuildJob.objects.get(uuid=first.json()['job'])
        self.assertEqual(job.supplier_ids, [item.pk for item in self.companies])
        dispatch.assert_called_once_with(job.pk)
        self.assertEqual(first.json()['url'], 'http://testserver' + reverse('api:graph-job-detail', args=[job.uuid]))

    def test_analysis_start_defaults_to_template_and_deduplicates(self):
        with patch('apps.ai.jobs.analyse_cluster_task.delay') as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                first = self.client.post(self.analysis_url, {}, format='json')
                second = self.client.post(self.analysis_url, {}, format='json')
        self.assertEqual((first.status_code, second.status_code), (202, 202))
        self.assertEqual(first.json()['job'], second.json()['job'])
        self.assertEqual((first.json()['created'], second.json()['created']), (True, False))
        job = AnalysisJob.objects.get(uuid=first.json()['job'])
        self.assertEqual(job.options['provider'], 'template')
        self.assertEqual(first.json()['result']['graph_version'], self.snapshot.version)
        self.assertIsNone(first.json()['result']['analysis_version'])
        dispatch.assert_called_once_with(job.pk)
        self.assertEqual(AnalysisSnapshot.objects.count(), 0)
        self.assertEqual(Explanation.objects.count(), 0)

    @override_settings(AI_PROVIDER='ollama', AI_MODEL='qwen3:4b', AI_BASE_URL='', AI_OLLAMA_BASE_URL='http://127.0.0.1:11434')
    def test_explicit_model_start_uses_server_configuration_only(self):
        with patch('apps.ai.jobs.analyse_cluster_task.delay') as dispatch, self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.analysis_url, {'use_model': True}, format='json')
        self.assertEqual(response.status_code, 202)
        job = AnalysisJob.objects.get(uuid=response.json()['job'])
        self.assertEqual((job.options['provider'], job.options['model']), ('ollama', 'qwen3:4b'))
        self.assertNotIn('api_key', job.options)
        self.assertNotIn('base_url', response.json())
        dispatch.assert_called_once_with(job.pk)
        self.network.assert_not_called()
        self.assertEqual(AnalysisSnapshot.objects.count(), 0)

    @override_settings(AI_PROVIDER='openai', AI_MODEL='gpt-4o', AI_BASE_URL='', AI_API_KEY='synthetic-key', AI_ALLOW_PAID=False)
    def test_paid_provider_cannot_be_enabled_by_request(self):
        response = self.client.post(self.analysis_url, {'use_model': True}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], 'paid_provider_disabled')
        self.assertNotIn('synthetic-key', response.content.decode())
        self.assertEqual(AnalysisJob.objects.count(), 0)
        template = self.client.post(self.analysis_url, {}, format='json')
        self.assertEqual(template.status_code, 202)

    def test_job_options_reject_unknown_fields_non_objects_and_non_boolean_values(self):
        for value in ({'use_model': 'true'}, {'use_model': 1}, {'use_model': None},
                      {'retry_model': True}, {'provider': 'openai'}, {'base_url': 'https://example.invalid'},
                      {'api_key': 'synthetic'}, {'as_of': '2026-99-99'}, {'force': True}, [], None):
            with self.subTest(value=value):
                response = self.client.generic('POST', self.analysis_url, json.dumps(value), content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['error']['code'], 'validation_error')
        for value in ({'company_ids': []}, {'as_of': '2026-01-01'}, {'mode': 'full'}, [], None):
            with self.subTest(value=value):
                self.assertEqual(self.client.generic('POST', self.graph_url, json.dumps(value), content_type='application/json').status_code, 400)
        self.assertEqual(GraphRebuildJob.objects.count(), 0)
        self.assertEqual(AnalysisJob.objects.count(), 0)

    def test_non_json_and_invalid_json_are_rejected(self):
        response = self.client.post(self.analysis_url, {'use_model': 'true'})
        self.assertEqual(response.status_code, 415)
        response = self.client.generic('POST', self.analysis_url, '{', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], 'parse_error')

    def test_job_starts_reject_unknown_and_duplicate_query_parameters(self):
        for url in (self.graph_url, self.analysis_url):
            for suffix in ('?version=1', '?x=1&x=2'):
                self.assertEqual(self.client.post(url + suffix, {}, format='json').status_code, 400)
        self.assertEqual(GraphRebuildJob.objects.count(), 0)
        self.assertEqual(AnalysisJob.objects.count(), 0)

    def test_missing_clusters_have_safe_not_found_errors(self):
        for name in ('api:cluster-recalculate', 'api:cluster-explanation-start'):
            response = self.client.post(reverse(name, args=[uuid4()]), {}, format='json')
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()['error']['code'], 'not_found')

    def test_inactive_clusters_cannot_launch_jobs(self):
        self.cluster.is_active = False
        self.cluster.save(update_fields=['is_active'])
        for url in (self.graph_url, self.analysis_url):
            response = self.client.post(url, {}, format='json')
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['error']['code'], 'inactive_cluster')
        self.assertEqual(GraphRebuildJob.objects.count(), 0)
        self.assertEqual(AnalysisJob.objects.count(), 0)

    def test_empty_group_cannot_accidentally_request_a_global_rebuild(self):
        self.cluster.suppliers.clear()
        with patch('apps.api.jobs.request_rebuild') as service:
            response = self.client.post(self.graph_url, {}, format='json')
        self.assertEqual(response.status_code, 400)
        service.assert_not_called()

    def test_oversized_group_cannot_launch_a_rebuild(self):
        extra = Supplier.objects.bulk_create([Supplier(bin=f'{number:012}', name='Synthetic extra')
                                             for number in range(3, 502)])
        self.cluster.suppliers.add(*extra)
        with patch('apps.api.jobs.request_rebuild') as service:
            response = self.client.post(self.graph_url, {}, format='json')
        self.assertEqual(response.status_code, 400)
        service.assert_not_called()

    def test_analysis_requires_an_active_saved_graph(self):
        self.cluster.current_snapshot = None
        self.cluster.save(update_fields=['current_snapshot'])
        response = self.client.post(self.analysis_url, {}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error']['code'], 'active_graph_required')
        self.assertEqual(AnalysisJob.objects.count(), 0)

    def test_graph_status_reads_saved_exact_versions_and_hides_unexpected_summary_fields(self):
        summary = {'analyzed': 2, 'snapshots_created': 1, 'secret': 'synthetic-private',
            'results': [{'cluster_uuid': str(self.cluster.uuid), 'version': 9, 'graph_hash': '9' * 64,
                         'state': 'active', 'analysis_version': 12, 'analysis_hash': '8' * 64,
                         'private': 'synthetic-private'}]}
        job = GraphRebuildJob.objects.create(dedup_key='e' * 64, supplier_ids=[],
                                             status='succeeded', summary=summary)
        with CaptureQueriesContext(connection) as queries, patch('apps.graph.jobs.rebuild_graph_task.delay') as dispatch:
            response = self.client.get(reverse('api:graph-job-detail', args=[job.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['version'], 9)
        self.assertEqual(response.json()['results'][0]['analysis_version'], 12)
        self.assertNotIn('synthetic-private', response.content.decode())
        self.assertNotIn('supplier_ids', response.json())
        self.assertFalse(any(item['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for item in queries))
        dispatch.assert_not_called()

    def test_analysis_status_exposes_fenced_result_versions_without_experimental_score(self):
        analysis = self.analysis_record()
        explanation = self.explanation_record(analysis)
        job = AnalysisJob.objects.create(graph_snapshot=self.snapshot, analysis=analysis, explanation=explanation,
            input_hash='e' * 64, dedup_key='f' * 64, as_of=timezone.localdate(), status='stale',
            error_code='analysis_input_superseded', options={'api_key': 'synthetic-private'})
        with CaptureQueriesContext(connection) as queries, patch('apps.ai.jobs.analyse_cluster_task.delay') as dispatch:
            response = self.client.get(reverse('api:analysis-job-detail', args=[job.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'stale')
        self.assertEqual(response.json()['error_code'], 'analysis_input_superseded')
        self.assertEqual(response.json()['result']['analysis_version'], 7)
        self.assertEqual(response.json()['result']['explanation_id'], explanation.pk)
        self.assertEqual(response.json()['result']['graph_version'], self.snapshot.version)
        self.assertNotIn('experimental', response.content.decode())
        self.assertNotIn('synthetic-private', response.content.decode())
        self.assertFalse(any(item['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for item in queries))
        dispatch.assert_not_called()

    def test_status_reads_reject_unknown_and_duplicate_parameters(self):
        job = GraphRebuildJob.objects.create(dedup_key='e' * 64, supplier_ids=[])
        url = reverse('api:graph-job-detail', args=[job.uuid])
        for suffix in ('?refresh=true', '?version=1', '?x=1&x=2'):
            self.assertEqual(self.client.get(url + suffix).status_code, 400)
        job.refresh_from_db()
        self.assertEqual(job.status, 'pending')

    def test_missing_jobs_and_unsupported_methods_are_rejected(self):
        for name in ('api:graph-job-detail', 'api:analysis-job-detail', 'api:ingestion-run-detail'):
            url = reverse(name, args=[uuid4()])
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, {}, format='json').status_code, 405)
        self.assertEqual(self.client.get(self.graph_url).status_code, 405)
        self.assertEqual(self.client.get(self.analysis_url).status_code, 405)

    def test_ingestion_status_excludes_options_and_nested_subject_data(self):
        run = IngestionRun.objects.create(mode='kgd', status='partial', stage='kgd',
            options={'personalAccountToken': 'synthetic-private', 'company_ids': [self.companies[0].pk]},
            counters={'contracts': 3, 'kgd_company_attempts': 2, 'clusters': {'private': 'synthetic-private'},
                      'unknown': 'synthetic-private'}, error_code='source_unavailable')
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('api:ingestion-run-detail', args=[run.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['counters'], {'contracts': 3, 'kgd_company_attempts': 2})
        self.assertEqual(response.json()['error_code'], 'source_unavailable')
        self.assertNotIn('synthetic-private', response.content.decode())
        self.assertFalse(any(item['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for item in queries))

    def test_ingestion_history_is_paginated_bounded_and_read_only(self):
        # ingestion.0003 records the legacy backfill even in an otherwise empty test DB.
        baseline = list(IngestionRun.objects.values())
        self.assertTrue(all(item['mode'] == 'legacy' and item['status'] == 'succeeded'
                            and item['stage'] == 'complete' for item in baseline))
        created = IngestionRun.objects.bulk_create(
            [IngestionRun(mode='synthetic', status='succeeded') for _ in range(4)])
        before_reads = list(IngestionRun.objects.values())
        url = reverse('api:ingestion-run-list')
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url, {'page_size': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], len(baseline) + len(created))
        self.assertEqual(len(response.json()['results']), 2)
        self.assertTrue({item['job'] for item in response.json()['results']}
                        <= {str(item.uuid) for item in created})
        self.assertIsNotNone(response.json()['next'])
        self.assertFalse(any(item['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE '))
                             for item in queries))
        for query in ({'page_size': 101}, {'page': 0}, {'search': 'synthetic'}, {'mode': 'full'}):
            self.assertEqual(self.client.get(url, query).status_code, 400)
        self.assertEqual(self.client.post(url, {}, format='json').status_code, 405)
        self.assertEqual(list(IngestionRun.objects.values()), before_reads)
        self.network.assert_not_called()

    def test_experimental_estimate_is_an_explicit_separate_staff_read(self):
        analysis = self.analysis_record()
        explanation = self.explanation_record(analysis)
        url = reverse('api:explanation-experimental-estimate', args=[explanation.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['experimental_score'], 92)
        self.assertIn('does not replace public review priority', response.json()['interpretation'])
        self.assertEqual(analysis.metrics['review_priority'], 2)
        for user in (self.viewer, None):
            self.client.force_authenticate(user=user)
            self.assertEqual(self.client.get(url).status_code, 403)


class JobBrokerFailureApiTests(JobFixtures, TransactionTestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(username='synthetic-staff', is_staff=True)
        self.cluster, self.snapshot, self.companies = self.create_group()
        self.client = APIClient()
        self.client.force_authenticate(user=self.staff)
        network = patch('requests.sessions.Session.request', side_effect=AssertionError('External HTTP forbidden'))
        network.start()
        self.addCleanup(network.stop)

    def test_graph_broker_failure_is_pollable_and_reported_as_service_unavailable(self):
        with patch('apps.graph.jobs.rebuild_graph_task.delay', side_effect=RuntimeError('synthetic-private')):
            response = self.client.post(reverse('api:cluster-recalculate', args=[self.cluster.uuid]), {}, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error']['code'], 'broker_unavailable')
        job = GraphRebuildJob.objects.get(uuid=response.json()['error']['details']['job'])
        self.assertEqual((job.status, job.error_code), ('failed', 'broker_unavailable'))
        self.assertNotIn('synthetic-private', response.content.decode())
        poll = self.client.get(reverse('api:graph-job-detail', args=[job.uuid]))
        self.assertEqual(poll.status_code, 200)
        self.assertEqual(poll.json()['status'], 'failed')

    def test_analysis_broker_failure_is_pollable_and_reported_as_service_unavailable(self):
        with patch('apps.ai.jobs.analyse_cluster_task.delay', side_effect=RuntimeError('synthetic-private')):
            response = self.client.post(reverse('api:cluster-explanation-start', args=[self.cluster.uuid]), {}, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error']['code'], 'broker_unavailable')
        job = AnalysisJob.objects.get(uuid=response.json()['error']['details']['job'])
        self.assertEqual((job.status, job.error_code), ('failed', 'broker_unavailable'))
        self.assertNotIn('synthetic-private', response.content.decode())
        poll = self.client.get(reverse('api:analysis-job-detail', args=[job.uuid]))
        self.assertEqual(poll.status_code, 200)
        self.assertEqual(poll.json()['status'], 'failed')
