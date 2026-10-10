"""Offline API history, privacy, GET purity and personal-view concurrency checks."""
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.middleware.csrf import get_token
from django.test import TestCase, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ai.models import AnalysisSnapshot, AnalysisState, Explanation, AnalysisJob
from apps.ai.services import prepare_analysis
from apps.ai.tests import AnalysisFixtures
from apps.companies.models import Supplier
from apps.graph.models import RiskCluster, GraphSnapshot, GraphViewState
from apps.graph.services import rebuild_clusters
from apps.ingestion.models import SourceObservation
from apps.ingestion.tests.helpers import verified_role
from apps.owners.models import Director
from .saved import SourceReferenceSerializer


class SavedApiTests(AnalysisFixtures, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.cluster, self.companies = self.group()
        self.base = f'/api/v1/clusters/{self.cluster.uuid}/'

    def get_json(self, path, status=200):
        response = self.client.get(path)
        self.assertEqual(response.status_code, status, response.content.decode())
        self.assertEqual(response['Content-Type'], 'application/json')
        return response.json()

    def test_missing_saved_results_are_explicit_and_get_never_prepares_them(self):
        AnalysisSnapshot.objects.all().count()
        bare = RiskCluster.objects.create(name='Synthetic uncalculated group')
        with patch('apps.ai.services.prepare_analysis', side_effect=AssertionError('GET prepared analysis')), patch(
                'apps.graph.services.rebuild_clusters', side_effect=AssertionError('GET rebuilt graph')):
            data = self.get_json(f'/api/v1/clusters/{bare.uuid}/graph/')
            analysis = self.get_json(self.base + 'analysis/')
        self.assertEqual(data['state'], 'not_calculated')
        self.assertEqual(data['graph'], {'nodes': [], 'links': []})
        self.assertIsNone(data['version'])
        self.assertEqual(analysis['status'], 'not_calculated')
        self.assertIsNone(analysis['analysis'])
        self.assertIsNone(analysis['explanation'])
        self.assertEqual(AnalysisSnapshot.objects.count(), 0)
        self.assertEqual(Explanation.objects.count(), 0)

    def test_get_reuses_saved_graph_analysis_document_without_domain_writes(self):
        analysis, _ = prepare_analysis(self.cluster.pk)
        explanation = AnalysisState.objects.get(cluster=self.cluster).explanation
        with patch('apps.ai.services.prepare_analysis', side_effect=AssertionError('GET prepared analysis')), patch(
                'apps.ai.services.template_for', side_effect=AssertionError('GET generated text')), patch(
                'apps.ai.providers.generate', side_effect=AssertionError('GET used model'), create=True), CaptureQueriesContext(connection) as queries:
            first = self.get_json(self.base + 'analysis/')
            second = self.get_json(self.base + 'analysis/')
            self.get_json(self.base + 'graph/')
            self.get_json(f'/api/v1/snapshots/{self.cluster.current_snapshot_id}/evidence/')
        self.assertEqual(first, second)
        self.assertEqual(first['analysis']['id'], analysis.pk)
        self.assertEqual(first['explanation']['text'], explanation.text)
        self.assertEqual(first['explanation']['document'], explanation.presentation['document'])
        self.assertFalse(any(item['sql'].lstrip().upper().startswith(('UPDATE ', 'INSERT ', 'DELETE ')) for item in queries))
        self.assertEqual((AnalysisSnapshot.objects.count(), Explanation.objects.count(), AnalysisJob.objects.count()), (1, 1, 0))

    def test_current_and_historical_graphs_are_exact_scoped_versions(self):
        old = self.cluster.current_snapshot
        old_payload = deepcopy(old.payload)
        old_analysis, _ = prepare_analysis(self.cluster.pk)
        Supplier.objects.create(bin='000000000099', name='Synthetic addition', address='Synthetic shared office')
        rebuild_clusters()
        self.cluster.refresh_from_db()
        current_analysis, _ = prepare_analysis(self.cluster.pk)
        latest = self.get_json(self.base + 'graph/')
        historical = self.get_json(self.base + 'graph/?version=1')
        self.assertEqual((latest['version'], historical['version']), (2, 1))
        self.assertTrue(historical['historical'])
        self.assertEqual(historical['graph']['nodes'][0]['name'], old_payload['nodes'][0]['name'])
        self.assertEqual(len(historical['graph']['nodes']), len(old_payload['nodes']))
        data = self.get_json(self.base + 'analysis/?version=1')
        self.assertEqual(data['analysis']['id'], old_analysis.pk)
        self.assertTrue(data['historical'])
        self.assertEqual(self.get_json(self.base + 'analysis/')['analysis']['id'], current_analysis.pk)
        self.get_json(self.base + f'analysis/?version=1&analysis_version={current_analysis.version}', 404)
        self.get_json(self.base + 'graph/?version=99', 404)
        self.get_json(self.base + 'analysis/?analysis_version=99', 404)
        history = self.get_json(self.base + 'snapshots/?page_size=1')
        self.assertEqual((history['count'], history['results'][0]['version']), (2, 2))
        self.assertIsNotNone(history['next'])
        self.assertEqual(self.get_json(self.base + 'snapshots/?page=2&page_size=1')['results'][0]['version'], 1)

    def test_snapshot_detail_preserves_lineage_and_frozen_membership(self):
        old = self.cluster.current_snapshot
        added = Supplier.objects.create(bin='000000000099', name='Synthetic lineage addition', address='Synthetic shared office')
        rebuild_clusters()
        self.cluster.refresh_from_db()
        current = self.cluster.current_snapshot
        detail = self.get_json(f'/api/v1/snapshots/{old.pk}/')
        self.assertEqual(detail['member_ids'], old.member_ids)
        self.assertNotIn(added.pk, detail['member_ids'])
        self.assertEqual(detail['cluster'], str(self.cluster.uuid))
        self.assertEqual(detail['outgoing_transitions'][0]['target_snapshot_id'], current.pk)
        self.assertEqual(detail['outgoing_transitions'][0]['target_cluster'], str(self.cluster.uuid))
        current_detail = self.get_json(f'/api/v1/snapshots/{current.pk}/')
        self.assertEqual(current_detail['previous_id'], old.pk)
        self.assertEqual(current_detail['incoming_transitions'][0]['source_snapshot_id'], old.pk)
        self.assertEqual(current_detail['incoming_transitions'][0]['shared_member_ids'], old.member_ids)
        self.get_json('/api/v1/snapshots/99999999/', 404)

    def test_retired_group_keeps_uuid_saved_history_and_readable_analysis(self):
        analysis, _ = prepare_analysis(self.cluster.pk)
        old_id = self.cluster.current_snapshot_id
        for number, company in enumerate(self.companies):
            company.address = f'Synthetic separate office {number}'
            company.save(update_fields=['address'])
        rebuild_clusters()
        self.cluster.refresh_from_db()
        self.assertFalse(self.cluster.is_active)
        data = self.get_json(self.base + 'graph/')
        self.assertEqual(data['state'], 'retired')
        self.assertEqual(self.get_json(self.base)['uuid'], str(self.cluster.uuid))
        self.assertEqual(self.get_json(self.base + 'graph/?version=1')['snapshot_id'], old_id)
        self.assertEqual(self.get_json(self.base + 'analysis/?version=1')['analysis']['id'], analysis.pk)
        self.assertEqual(self.get_json('/api/v1/clusters/')['count'], 0)
        self.assertEqual(self.get_json('/api/v1/clusters/?active=false')['count'], 1)

    def test_cluster_score_filters_use_saved_review_priority_and_deduplicate_members(self):
        self.cluster.risk_score = 99
        self.cluster.save(update_fields=['risk_score'])
        self.assertIsNone(self.get_json(self.base)['review_priority'])
        self.assertEqual(self.get_json('/api/v1/clusters/?minimum_review_priority=50')['count'], 0)
        prepare_analysis(self.cluster.pk)
        self.assertEqual(self.get_json(self.base)['review_priority'], 2)
        found = self.get_json('/api/v1/clusters/?search=Synthetic&minimum_review_priority=2')
        self.assertEqual(found['count'], 1)
        self.assertEqual(found['results'][0]['company_count'], 2)
        self.assertEqual(self.get_json('/api/v1/clusters/?minimum_review_priority=3')['count'], 0)
        self.get_json('/api/v1/clusters/?ordering=metric__secret', 400)

    def test_invalid_and_repeated_queries_are_rejected_before_reading(self):
        for suffix in ('?version=0', '?version=-1', '?version=1.0', '?version=1e1', '?version=true',
                       '?version=1&version=2', '?unused=true', '?version=1000000000'):
            data = self.get_json(self.base + 'graph/' + suffix, 400)
            self.assertEqual(data['error']['code'], 'validation_error')
        for suffix in ('?page_size=101', '?page=0', '?search=unexpected'):
            self.get_json(self.base + 'snapshots/' + suffix, 400)
        self.get_json('/api/v1/clusters/?minimum_review_priority=101', 400)
        self.get_json('/api/v1/clusters/?active=maybe', 400)
        self.get_json(self.base + 'graph/?version=123', 404)

    def test_analysis_staleness_does_not_replace_text_or_saved_metrics(self):
        analysis, _ = prepare_analysis(self.cluster.pk)
        text = AnalysisState.objects.get(cluster=self.cluster).explanation.text
        self.arrears(self.companies[0], '125.91')
        data = self.get_json(self.base + 'analysis/')
        self.assertEqual(data['status'], 'stale')
        self.assertEqual(data['analysis']['metrics'], analysis.metrics)
        self.assertEqual(data['explanation']['text'], text)
        self.assertEqual(AnalysisSnapshot.objects.count(), 1)

    def test_legacy_text_is_not_reconstructed_and_explanations_are_cluster_scoped(self):
        analysis, _ = prepare_analysis(self.cluster.pk)
        legacy = Explanation.objects.create(analysis=analysis, reuse_key='a' * 64, language='en',
            provider='template', prompt_version='legacy', status='ready', text='Original immutable legacy text.',
            presentation={})
        detail = self.get_json(self.base + f'analyses/{analysis.version}/explanations/{legacy.pk}/')
        self.assertEqual(detail['text'], legacy.text)
        self.assertIsNone(detail['document'])
        historical = self.get_json(self.base + 'analyses/')
        self.assertEqual(historical['results'][0]['id'], analysis.pk)
        self.assertEqual(self.get_json(self.base + f'analyses/{analysis.version}/')['analysis_hash'], analysis.analysis_hash)
        other = RiskCluster.objects.create(name='Other synthetic cluster')
        self.get_json(f'/api/v1/clusters/{other.uuid}/analyses/{analysis.version}/', 404)
        self.get_json(f'/api/v1/clusters/{other.uuid}/analyses/{analysis.version}/explanations/{legacy.pk}/', 404)
        self.assertEqual(self.get_json(self.base + f'analyses/{analysis.version}/explanations/')['count'], 2)
        legacy.refresh_from_db()
        self.assertEqual(legacy.presentation, {})

    def test_unpublished_experimental_output_is_not_public_explanation_history(self):
        analysis, _ = prepare_analysis(self.cluster.pk)
        unpublished = Explanation.objects.create(analysis=analysis, reuse_key='b' * 64, language='en',
            provider='ollama', model='synthetic', prompt_version='test', status='ready', text='Superseded output.',
            experimental_score=99, experimental_evidence=['private'], usage={'private': True})
        data = self.get_json(self.base + f'analyses/{analysis.version}/explanations/')
        self.assertEqual(data['count'], 1)
        self.get_json(self.base + f'analyses/{analysis.version}/explanations/{unpublished.pk}/', 404)
        public = self.get_json(self.base + 'analysis/')['explanation']
        self.assertNotIn('experimental_score', public)
        self.assertNotIn('experimental_evidence', public)
        self.assertNotIn('usage', public)

    def test_current_published_text_is_navigable_without_exposing_experimental_fields(self):
        analysis, _ = prepare_analysis(self.cluster.pk)
        published = Explanation.objects.create(analysis=analysis, reuse_key='d' * 64, language='en',
            provider='ollama', model='synthetic', prompt_version='test', status='ready',
            text='Synthetic saved published text.', experimental_score=99,
            experimental_evidence=['private'], presentation={})
        state = AnalysisState.objects.get(cluster=self.cluster)
        state.explanation = published
        state.save(update_fields=['explanation'])
        current = self.get_json(self.base + 'analysis/')['explanation']
        detail = self.get_json(self.base + f'analyses/{analysis.version}/explanations/{published.pk}/')
        self.assertEqual(current['id'], detail['id'])
        self.assertEqual(detail['text'], published.text)
        self.assertNotIn('experimental_score', detail)
        self.assertNotIn('experimental_evidence', detail)

    def test_saved_metric_categories_omit_private_metadata_without_rescoring(self):
        original, _ = prepare_analysis(self.cluster.pk)
        state = AnalysisState.objects.get(cluster=self.cluster)
        original_text = state.explanation.text
        metrics = deepcopy(original.metrics)
        metrics['score_categories'].update(experimental_score=99, **{'iin:990101123456': 10})
        retained = AnalysisSnapshot.objects.create(cluster=self.cluster,
            graph_snapshot=original.graph_snapshot, version=original.version + 1,
            analysis_hash='e' * 64, input_hash=original.input_hash, rules_version=original.rules_version,
            as_of=original.as_of, inputs=original.inputs, findings=original.findings,
            metrics=metrics, limitations=original.limitations)
        text = Explanation.objects.create(analysis=retained, reuse_key='f' * 64,
            provider='template', prompt_version=state.explanation.prompt_version,
            status='ready', text=original_text, presentation=state.explanation.presentation)
        state.analysis, state.explanation = retained, text
        state.save(update_fields=['analysis', 'explanation'])
        result = self.get_json(self.base + 'analysis/')
        self.assertEqual(result['analysis']['metrics']['score_categories'], original.metrics['score_categories'])
        self.assertEqual(result['analysis']['metrics']['review_priority'], original.metrics['review_priority'])
        self.assertEqual(result['explanation']['text'], original_text)
        self.assertNotIn('experimental_score', str(result))
        self.assertNotIn('990101123456', str(result))
        retained.refresh_from_db()
        self.assertEqual(retained.metrics['score_categories']['experimental_score'], 99)

    def test_source_urls_cannot_leak_percent_encoded_person_identifiers_or_credentials(self):
        person_id = '990101123456'
        encoded = ''.join(f'%{ord(character):02X}' for character in person_id)
        nested = encoded.replace('%', '%25')
        cases = ['https://source.invalid/person/' + encoded, 'https://source.invalid/person/' + nested,
                 'https://source.invalid/person/' + nested.replace('%', '%25'),
                 'https://source.invalid/check?personalAccountToken=synthetic-secret',
                 'https://synthetic-secret@source.invalid/check', 'javascript:alert(1)',
                 'https://source.invalid/path\\private']
        for url in cases:
            with self.subTest(url=url):
                self.assertEqual(SourceReferenceSerializer({'source': 'synthetic', 'url': url}).data['url'], '')
        self.assertEqual(SourceReferenceSerializer({'source': 'synthetic',
            'url': 'https://source.invalid/public-check'}).data['url'], 'https://source.invalid/public-check')

    def test_nested_allowlists_hide_identity_credentials_and_raw_observations(self):
        director = Director.objects.create(full_name='Synthetic API verified director')
        role = verified_role(self.companies[0], director,
            start_date=timezone.localdate() - timedelta(days=1), end_date=timezone.localdate() + timedelta(days=1))
        observation = role.source_observation
        observation.raw_values = {'personalAccountToken': 'synthetic-secret', 'iin': '990101123456'}
        observation.source_url = 'https://source.invalid/person/990101123456?token=synthetic-secret'
        observation.save(update_fields=['raw_values', 'source_url'])
        rebuild_clusters()
        self.cluster.refresh_from_db()
        original = self.cluster.current_snapshot
        payload = deepcopy(original.payload)
        payload['scope_key'] = 'private'
        for node in payload['nodes']:
            node['iin'] = '990101123456'
            node['scope_key'] = 'iin:990101123456'
            if node['kind'] != 'company':
                node['bin'] = '990101123456'
        for edge in payload['links']:
            edge['raw_values'] = {'secret': 'synthetic-secret'}
            for ref in edge['evidence']:
                ref['subject_key'] = 'person:990101123456'
                ref['url'] = 'https://source.invalid/person/990101123456'
                ref['raw_values'] = observation.raw_values
        poisoned = GraphSnapshot.objects.create(cluster=self.cluster, version=original.version + 1,
            graph_hash='c' * 64, algorithm_version=original.algorithm_version, state='active',
            as_of=original.as_of, member_ids=original.member_ids, payload=payload, previous=original,
            changes={'raw_values': observation.raw_values})
        self.cluster.current_snapshot = poisoned
        self.cluster.save(update_fields=['current_snapshot'])
        analysis, _ = prepare_analysis(self.cluster.pk)
        for path in (self.base + 'graph/', self.base + 'analysis/', self.base + 'snapshots/',
                     f'/api/v1/snapshots/{poisoned.pk}/evidence/'):
            encoded = str(self.get_json(path))
            self.assertNotIn('synthetic-secret', encoded)
            self.assertNotIn('990101123456', encoded)
            self.assertNotIn('raw_values', encoded)
            self.assertNotIn('scope_key', encoded)
        self.assertNotIn('inputs', self.get_json(self.base + f'analyses/{analysis.version}/'))

    def test_finding_references_navigate_only_evidence_in_the_same_snapshot(self):
        director = Director.objects.create(full_name='Synthetic evidence person')
        role = verified_role(self.companies[0], director)
        rebuild_clusters()
        self.cluster.refresh_from_db()
        self.arrears(self.companies[0], '123.45')
        analysis, _ = prepare_analysis(self.cluster.pk)
        snapshot_id = self.cluster.current_snapshot_id
        items = self.get_json(f'/api/v1/snapshots/{snapshot_id}/evidence/')['results']
        refs = {item['id'] for item in items}
        for finding in analysis.findings:
            for reference in finding['evidence']:
                identifier = f"{reference['kind']}:{reference['id']}"
                self.assertIn(identifier, refs)
                detail = self.get_json(f'/api/v1/snapshots/{snapshot_id}/evidence/{identifier}/')
                self.assertEqual(detail['graph_snapshot_id'], snapshot_id)
        observation_ref = self.get_json(f'/api/v1/snapshots/{snapshot_id}/evidence/observation:{role.source_observation_id}/')
        self.assertEqual(observation_ref['status'], 'success')
        self.assertNotIn('normalized_values', observation_ref)
        self.assertNotIn('subject_key', observation_ref)
        self.get_json(f'/api/v1/snapshots/{snapshot_id}/evidence/observation:99999999/', 404)
        original = self.cluster.snapshots.order_by('version').first()
        self.get_json(f'/api/v1/snapshots/{original.pk}/evidence/observation:{role.source_observation_id}/', 404)


class PersonalGraphApiTests(AnalysisFixtures, TestCase):
    def test_remove_is_private_revision_fenced_and_can_be_saved_again(self):
        self.assertEqual(self.client.delete(self.path, {'revision': 0}, format='json').status_code, 403)
        self.client.force_login(self.user)
        self.put(self.body)
        self.client.force_login(self.other)
        self.assertEqual(self.client.delete(self.path, {'revision': 1}, format='json').status_code, 409)
        self.assertEqual(GraphViewState.objects.get(user=self.user).revision, 1)
        self.client.force_login(self.user)
        response = self.client.delete(self.path, {'revision': 1}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'revision': 2, 'payload': None})
        self.assertEqual(self.client.get(self.path).json(), response.json())
        self.assertEqual(self.client.get('/api/v1/account/views/').json()['count'], 0)
        # Old tabs must not resurrect the layout, even after removal and re-save.
        self.put(self.body, 409)
        self.body['revision'] = 1
        self.put(self.body, 409)
        self.assertEqual(self.client.delete(self.path, {'revision': 1}, format='json').status_code, 409)
        self.assertEqual(self.client.delete(self.path, {'revision': 2}, format='json').json(), response.json())
        self.body['revision'] = 2
        self.assertEqual(self.put(self.body)['revision'], 3)
        self.assertEqual(self.client.get('/api/v1/account/views/').json()['count'], 1)
        self.assertEqual(self.client.delete(self.path, {'revision': 2}, format='json').status_code, 409)

    def test_remove_requires_csrf_and_exact_revision_body(self):
        self.client.force_login(self.user)
        self.put(self.body)
        for body in ({}, {'revision': True}, {'revision': '1'}, {'revision': -1}, {'revision': 1, 'user': self.other.pk}):
            self.assertEqual(self.client.delete(self.path, body, format='json').status_code, 400)
        self.assertEqual(self.client.delete(self.path+'?version=1', {'revision': 1}, format='json').status_code, 400)
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.assertEqual(self.client.delete(self.path, {'revision': 1}, format='json').status_code, 403)
        token = get_token(RequestFactory().get('/'))
        self.client.cookies['csrftoken'] = token
        self.assertEqual(self.client.delete(self.path, {'revision': 1}, format='json', HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_remove_archived_view_preserves_graph_and_other_account(self):
        self.client.force_login(self.other)
        self.put(self.body)
        self.client.force_login(self.user)
        self.put(self.body)
        self.cluster.is_active = False
        self.cluster.save(update_fields=['is_active'])
        snapshots = list(GraphSnapshot.objects.values())
        self.assertEqual(self.client.delete(self.path, {'revision': 1}, format='json').status_code, 200)
        self.assertEqual(list(GraphSnapshot.objects.values()), snapshots)
        self.assertEqual(GraphViewState.objects.get(user=self.other).payload, self.body['payload'])

    def setUp(self):
        self.client = APIClient()
        self.cluster, _ = self.group()
        self.user = get_user_model().objects.create_user(username='synthetic-layout-user', password='synthetic')
        self.other = get_user_model().objects.create_user(username='synthetic-layout-other', password='synthetic')
        self.path = f'/api/v1/clusters/{self.cluster.uuid}/view/'
        self.node = self.cluster.current_snapshot.payload['nodes'][0]['id']
        self.body = {'snapshot_id': self.cluster.current_snapshot_id, 'graph_hash': self.cluster.current_snapshot.graph_hash,
            'revision': 0, 'payload': {'positions': {self.node: {'x': 100, 'y': 120, 'pinned': True}},
                'zoom': {'x': 10, 'y': 20, 'k': 1.25}, 'filters': ['address'], 'selected': self.node, 'frozen': True}}

    def put(self, body, status=200, **extra):
        response = self.client.put(self.path, body, format='json', **extra)
        self.assertEqual(response.status_code, status, response.content.decode())
        return response.json()

    def test_personal_view_requires_authenticated_session_and_is_user_scoped(self):
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.put(self.body, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.path).json(), {'revision': 0, 'payload': None})
        saved = self.put(self.body)
        self.assertEqual(saved['revision'], 1)
        self.assertEqual(saved['payload'], self.body['payload'])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.path).json(), {'revision': 0, 'payload': None})
        self.put(self.body)
        self.assertEqual(GraphViewState.objects.count(), 2)

    def test_optimistic_revision_rejects_old_tab_and_same_payload_is_idempotent(self):
        self.client.force_login(self.user)
        self.put(self.body)
        conflict = self.put(self.body, 409)
        self.assertEqual(conflict['error']['code'], 'view_conflict')
        self.body['revision'] = 1
        self.assertEqual(self.put(self.body)['revision'], 1)
        changed = deepcopy(self.body)
        changed['payload']['positions'][self.node]['x'] = 999
        self.assertEqual(self.put(changed)['revision'], 2)
        self.put(self.body, 409)
        self.assertEqual(self.client.get(self.path).json()['payload']['positions'][self.node]['x'], 999)

    def test_replaced_graph_rejects_save_against_old_snapshot_without_writing(self):
        self.client.force_login(self.user)
        Supplier.objects.create(bin='000000000099', name='Synthetic additional company', address='Synthetic shared office')
        rebuild_clusters()
        self.put(self.body, 409)
        self.assertEqual(GraphViewState.objects.count(), 0)
        self.assertEqual(self.client.get(self.path + '?version=1').status_code, 200)
        response = self.client.put(self.path + '?version=1', self.body, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(GraphViewState.objects.count(), 0)

    def test_nested_original_json_validation_rejects_unknown_nodes_types_and_fields(self):
        self.client.force_login(self.user)
        cases = []
        for position in ({'x': True, 'y': 0, 'pinned': True}, {'x': 0, 'y': 0, 'pinned': 'true'},
                         {'x': 0, 'y': 0, 'pinned': True, 'secret': 'unexpected'},
                         {'x': 1000001, 'y': 0, 'pinned': True}):
            body = deepcopy(self.body)
            body['payload']['positions'][self.node] = position
            cases.append(body)
        for key, value in [('positions', {'person:not-in-snapshot': {'x': 1, 'y': 2, 'pinned': True}}),
                           ('selected', 'person:not-in-snapshot'), ('zoom', {'x': 0, 'y': 0, 'k': 0.01}),
                           ('filters', ['unsupported']), ('frozen', 'true'), ('private', 'unexpected')]:
            body = deepcopy(self.body)
            body['payload'][key] = value
            cases.append(body)
        for key, value in [('revision', True), ('snapshot_id', str(self.body['snapshot_id'])),
                           ('revision', -1), ('graph_hash', 'invalid'), ('private', 'unexpected')]:
            body = deepcopy(self.body)
            body[key] = value
            cases.append(body)
        for body in cases:
            self.put(body, 400)
        self.assertEqual(GraphViewState.objects.count(), 0)

    def test_session_csrf_required_and_valid_token_allows_own_view_without_analysis_job(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.put(self.body, 403)
        token = get_token(RequestFactory().get('/'))
        self.client.cookies['csrftoken'] = token
        self.put(self.body, HTTP_X_CSRFTOKEN=token)
        self.assertEqual((GraphViewState.objects.count(), AnalysisSnapshot.objects.count(), AnalysisJob.objects.count()), (1, 0, 0))
        self.assertEqual(GraphSnapshot.objects.count(), 1)
