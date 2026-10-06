"""Meaningful offline scenarios for evidence, history, impact and personal views."""
from datetime import date, timedelta
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.companies.models import Supplier
from apps.ingestion.tests.helpers import verified_role
from apps.ingestion.models import SelectedFact, SourceObservation, IngestionRun
from apps.ingestion.leases import LeaseLost
from apps.owners.models import Director, Owner, Ownership, PersonIdentity
from .evidence import EvidenceIndex, COMMON_CONTACT_LIMIT
from .models import RiskCluster, GraphSnapshot, EvidenceEdge, ClusterLineage, GraphInputState, GraphViewState, GraphRebuildJob
from .services import rebuild_clusters, load_graph_suppliers
from .jobs import request_rebuild, rebuild_graph_task


class SnapshotTests(TestCase):
    def company(self, number, address='Fixture office'):
        return Supplier.objects.create(bin=f'{number:012}', name=f'Fixture company {number}', address=address)

    def group(self, start=1, address='Fixture office', count=2):
        companies = [self.company(i, address) for i in range(start, start + count)]
        rebuild_clusters()
        cluster = RiskCluster.objects.get(is_active=True, suppliers=companies[0])
        return cluster, companies

    def test_repeat_preserves_all_versions_without_database_writes(self):
        cluster, _ = self.group()
        original = cluster.current_snapshot_id
        with CaptureQueriesContext(connection) as queries:
            result = rebuild_clusters()
        cluster.refresh_from_db()
        self.assertEqual((cluster.current_snapshot_id, GraphSnapshot.objects.count()), (original, 1))
        self.assertEqual(result['affected_companies'], 0)
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('UPDATE ', 'INSERT ', 'DELETE ')) for q in queries))

    def test_new_company_adds_one_version_and_old_evidence_is_immutable(self):
        cluster, companies = self.group()
        before = cluster.current_snapshot
        added = self.company(3)
        result = rebuild_clusters(supplier_ids=[added.pk])
        cluster.refresh_from_db()
        self.assertEqual(cluster.current_snapshot.version, 2)
        self.assertEqual(cluster.current_snapshot.changes['added_members'], [added.pk])
        self.assertEqual(before.member_ids, [c.pk for c in companies])
        before.refresh_from_db()
        self.assertEqual(len(before.payload['links']), 2)
        self.assertEqual(result['snapshots_created'], 1)
        with self.assertRaises(ValidationError):
            before.save()
        with self.assertRaises(ValidationError):
            GraphSnapshot.objects.filter(pk=before.pk).update(state='retired')
        with self.assertRaises(ValidationError):
            before.delete()

    def test_private_business_change_does_not_recreate_graph(self):
        cluster, companies = self.group()
        companies[0].phone = 'private-new-contact'
        companies[0].save(update_fields=['phone'])
        rebuild_clusters(supplier_ids=[companies[0].pk])
        cluster.refresh_from_db()
        self.assertEqual(cluster.current_snapshot.version, 1)
        self.assertTrue(cluster.explanation_stale)

    def test_impact_scope_does_not_write_unrelated_component(self):
        first, companies = self.group()
        second, _ = self.group(start=10, address='Unrelated office')
        original = (second.current_snapshot_id, second.updated_at, second.analysis_fingerprint)
        companies[0].name = 'Changed fixture company'
        companies[0].save(update_fields=['name'])
        result = rebuild_clusters(supplier_ids=[companies[0].pk])
        second.refresh_from_db()
        self.assertEqual(result['affected_companies'], 2)
        self.assertEqual((second.current_snapshot_id, second.updated_at, second.analysis_fingerprint), original)
        self.assertEqual(GraphSnapshot.objects.filter(cluster=second).count(), 1)

    def test_scope_includes_other_detected_dirty_components(self):
        first, companies = self.group()
        second, others = self.group(start=10, address='Another office')
        companies[0].name, others[0].name = 'Changed A', 'Changed B'
        for company in (companies[0], others[0]):
            company.save(update_fields=['name'])
        result = rebuild_clusters(supplier_ids=[companies[0].pk])
        self.assertEqual(result['affected_companies'], 4)
        self.assertEqual(GraphSnapshot.objects.filter(version=2).count(), 2)

    def test_archived_membership_does_not_expand_current_impact(self):
        archived, companies = self.group(count=4)
        for index, company in enumerate(companies):
            company.address = f'Detached {index}'
            company.save(update_fields=['address'])
        rebuild_clusters()
        for index, company in enumerate(companies):
            company.address = 'New first group' if index < 2 else 'New second group'
            company.save(update_fields=['address'])
        rebuild_clusters()
        unrelated = RiskCluster.objects.get(is_active=True, suppliers=companies[3])
        original = unrelated.current_snapshot_id
        companies[0].name = 'Changed current company'
        companies[0].save(update_fields=['name'])
        result = rebuild_clusters(supplier_ids=[companies[0].pk])
        unrelated.refresh_from_db()
        self.assertEqual(result['affected_companies'], 2)
        self.assertEqual(unrelated.current_snapshot_id, original)

    def test_empty_legacy_group_retires_once_without_losing_text(self):
        cluster = RiskCluster.objects.create(name='Empty legacy', ai_explanation='Preserved')
        rebuild_clusters()
        cluster.refresh_from_db()
        self.assertFalse(cluster.is_active)
        self.assertEqual(cluster.current_snapshot.state, 'retired')
        self.assertEqual(cluster.ai_explanation, 'Preserved')
        before = GraphSnapshot.objects.count()
        rebuild_clusters()
        self.assertEqual(GraphSnapshot.objects.count(), before)

    def test_merge_split_retirement_and_reactivation_have_history(self):
        first, companies = self.group()
        second, others = self.group(start=10, address='Another office')
        original_uuids = {first.uuid, second.uuid}
        for company in (companies[0], others[0]):
            company.phone = 'bridge'
            company.save(update_fields=['phone'])
        rebuild_clusters(supplier_ids=[companies[0].pk])
        self.assertEqual(ClusterLineage.objects.filter(kind='merge').count(), 2)
        self.assertEqual(RiskCluster.objects.filter(is_active=True).count(), 1)
        for company in (companies[0], others[0]):
            company.phone = ''
            company.save(update_fields=['phone'])
        rebuild_clusters(supplier_ids=[companies[0].pk])
        self.assertEqual(set(RiskCluster.objects.filter(is_active=True).values_list('uuid', flat=True)), original_uuids)
        self.assertEqual(ClusterLineage.objects.filter(kind='split').count(), 2)
        companies[0].address = 'Detached'
        companies[0].save(update_fields=['address'])
        rebuild_clusters()
        first.refresh_from_db()
        self.assertEqual(first.current_snapshot.state, 'retired')
        companies[0].address = 'Fixture office'
        companies[0].save(update_fields=['address'])
        rebuild_clusters()
        self.assertTrue(ClusterLineage.objects.filter(kind='reactivated').exists())

    def test_legacy_baseline_preserves_text_without_invented_links(self):
        companies = [self.company(1), self.company(2)]
        cluster = RiskCluster.objects.create(name='Legacy fixture', ai_explanation='Original text')
        cluster.suppliers.set(companies)
        rebuild_clusters()
        legacy = GraphSnapshot.objects.get(cluster=cluster, version=1)
        self.assertEqual(legacy.state, 'legacy')
        self.assertEqual(legacy.payload['links'], [])
        self.assertEqual(legacy.legacy_explanation, 'Original text')
        self.assertEqual(legacy.legacy_explanation_fingerprint, '')

    def test_failed_publication_rolls_back_evidence_and_snapshots(self):
        cluster, companies = self.group()
        companies[0].name = 'Fixture changed'
        companies[0].save(update_fields=['name'])
        old_states = list(GraphInputState.objects.values_list('supplier_id', 'digest'))
        with self.assertRaises(LeaseLost):
            rebuild_clusters(publication_guard=lambda: (_ for _ in ()).throw(LeaseLost('fixture')))
        self.assertEqual(GraphSnapshot.objects.count(), 1)
        self.assertEqual(list(GraphInputState.objects.values_list('supplier_id', 'digest')), old_states)

    def test_high_frequency_contact_has_linear_edges_and_no_mass_group(self):
        Supplier.objects.bulk_create([Supplier(bin=f'{i:012}', name=f'Synthetic {i}', address='Mass contact') for i in range(1, 1001)])
        result = rebuild_clusters()
        self.assertEqual(result['groups'], 0)
        self.assertEqual(EvidenceEdge.objects.count(), 1000)
        self.assertTrue(all(edge.payload['common_contact'] for edge in EvidenceEdge.objects.all()))
        Supplier.objects.filter(bin__gt=f'{COMMON_CONTACT_LIMIT:012}').update(address='')
        result = rebuild_clusters(supplier_ids=[Supplier.objects.get(bin='000000000001').pk])
        self.assertEqual(result['groups'], 1)
        self.assertEqual(len(RiskCluster.objects.get().current_snapshot.payload['links']), COMMON_CONTACT_LIMIT)

    def test_evidence_dates_identity_and_retrieval_reuse(self):
        companies = [self.company(1, ''), self.company(2, '')]
        director = Director.objects.create(full_name='Verified fixture director')
        roles = [verified_role(c, director, start_date=date(2020, 1, 1), end_date=date(2030, 1, 1)) for c in companies]
        rebuild_clusters(as_of=date(2026, 10, 6))
        cluster = RiskCluster.objects.get(is_active=True)
        original = cluster.current_snapshot
        self.assertEqual(len(original.payload['nodes']), 3)
        self.assertEqual({n['kind'] for n in original.payload['nodes']}, {'company', 'person'})
        self.assertNotIn('iin', json.dumps(original.payload))
        edge = original.payload['links'][0]
        self.assertEqual(edge['valid_from'], '2020-01-01')
        self.assertTrue(edge['evidence'][0]['observation_id'])
        obs = roles[0].source_observation
        obs.pk = None
        obs.fingerprint = 'new-fixture-observation'
        obs.observed_at = timezone.now() + timedelta(days=1)
        obs.save()
        roles[0].source_observation = obs
        roles[0].save(update_fields=['source_observation'])
        rebuild_clusters(as_of=date(2026, 10, 6))
        cluster.refresh_from_db()
        self.assertEqual(cluster.current_snapshot_id, original.pk)
        self.assertEqual(cluster.current_snapshot.payload, original.payload)

    def test_nonoverlapping_confirmed_roles_do_not_form_group(self):
        companies = [self.company(1, ''), self.company(2, '')]
        director = Director.objects.create(full_name='Fixture director')
        verified_role(companies[0], director, start_date=date(2020, 1, 1), end_date=date(2024, 1, 1))
        verified_role(companies[1], director, start_date=date(2024, 1, 1), end_date=date(2030, 1, 1))
        self.assertEqual(rebuild_clusters(as_of=date(2024, 1, 1))['groups'], 0)

    def test_contact_source_changes_create_evidence_version(self):
        cluster, companies = self.group()
        cluster.explanation_stale = False
        cluster.save(update_fields=['explanation_stale'])
        run = IngestionRun.objects.create(mode='enrich', status='succeeded')
        obs = SourceObservation.objects.create(run=run, supplier=companies[0], source='fixture', subject_key='fixture',
            status='success', fingerprint='fixture-source', source_url='https://example.org/company',
            observed_at=timezone.now(), normalized_values={'address': companies[0].address})
        SelectedFact.objects.create(supplier=companies[0], field='address', observation=obs)
        rebuild_clusters()
        cluster.refresh_from_db()
        self.assertEqual(cluster.current_snapshot.version, 2)
        self.assertTrue(cluster.explanation_stale)
        self.assertTrue(cluster.current_snapshot.changes['changed_edges'])

    def test_confirmed_ownership_connects_people_without_debt_transfer(self):
        companies = [self.company(1, ''), self.company(2, '')]
        owner = Owner.objects.create(full_name='Fixture owner', has_tax_debt=True)
        person = PersonIdentity.objects.create(scope_key='verified-owner-fixture', full_name=owner.full_name,
                                              iin='000000000101', owner=owner, is_verified=True)
        run = IngestionRun.objects.create(mode='enrich', status='succeeded')
        for company in companies:
            observation = SourceObservation.objects.create(run=run, source='fixture', subject_key=f'fixture:{company.pk}',
                supplier=company, status='success', fingerprint=str(company.pk), observed_at=timezone.now(),
                normalized_values={'owners_complete': True, 'owners': [{'iin': person.iin, 'iin_verified': True}]})
            Ownership.objects.create(supplier=company, owner=owner, person_identity=person,
                                     source='fixture', source_observation=observation, identity_status='verified')
        rebuild_clusters()
        cluster = RiskCluster.objects.get(is_active=True)
        self.assertEqual({edge['type'] for edge in cluster.current_snapshot.payload['links']}, {'owner'})
        from apps.ai.explainer import explain_cluster
        self.assertNotIn('debts are recorded', explain_cluster(cluster))
        self.assertNotIn('has_tax_debt', json.dumps(cluster.current_snapshot.payload))


class GraphReadAndViewTests(TestCase):
    company = SnapshotTests.company
    group = SnapshotTests.group

    def setUp(self):
        self.cluster, self.companies = self.group()
        self.user = get_user_model().objects.create_user(username='fixture-user')
        self.staff = get_user_model().objects.create_user(username='fixture-staff', is_staff=True)
        self.view_url = reverse('graph:graph_view', args=[self.cluster.uuid])

    def view_request(self):
        return {'snapshot_id': self.cluster.current_snapshot_id, 'graph_hash': self.cluster.current_snapshot.graph_hash,
                'revision': 0, 'payload': {'positions': {f'company:{self.companies[0].pk}': {'x': 100, 'y': -200, 'pinned': True}},
                                         'zoom': {'x': 15, 'y': 10, 'k': .75}, 'filters': ['address'], 'frozen': True}}

    def post_view(self, data):
        return self.client.post(self.view_url, data=json.dumps(data), content_type='application/json')

    def test_history_data_and_detail_are_read_only_and_snapshot_specific(self):
        version = self.cluster.current_snapshot
        added = self.company(3)
        rebuild_clusters()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('graph:graph_data', args=[self.cluster.uuid]), {'version': version.version})
            page = self.client.get(reverse('graph:cluster_detail', args=[self.cluster.uuid]), {'version': version.version})
            self.client.get(self.view_url)
        self.assertEqual(response.json()['graph'], version.payload)
        self.assertEqual(page.context['graph_data'], version.payload)
        self.assertTrue(page.context['graph_options']['historical'])
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('UPDATE ', 'INSERT ', 'DELETE ')) for q in queries))
        for value in ('0', '-1', 'NaN', '9' * 5000, '999'):
            self.assertEqual(self.client.get(reverse('graph:graph_data', args=[self.cluster.uuid]), {'version': value}).status_code, 404)

    def test_empty_legacy_get_does_not_create_snapshot(self):
        cluster = RiskCluster.objects.create(name='Legacy fixture')
        self.assertEqual(self.client.get(reverse('graph:cluster_detail', args=[cluster.uuid])).status_code, 200)
        self.assertFalse(GraphSnapshot.objects.filter(cluster=cluster).exists())

    def test_personal_view_round_trip_conflicts_and_no_analysis_change(self):
        self.client.force_login(self.user)
        request = self.view_request()
        saved = self.post_view(request)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()['revision'], 1)
        original = (self.cluster.current_snapshot_id, self.cluster.analysis_fingerprint)
        loaded = self.client.get(self.view_url).json()
        self.assertEqual(loaded['payload']['positions'], request['payload']['positions'])
        self.assertEqual(self.post_view(request).status_code, 409)
        request['revision'] = 1
        self.assertEqual(self.post_view(request).json()['revision'], 1)
        self.cluster.refresh_from_db()
        self.assertEqual((self.cluster.current_snapshot_id, self.cluster.analysis_fingerprint), original)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.view_url).json()['revision'], 0)

    def test_old_graph_save_is_rejected_and_positions_survive_new_company(self):
        self.client.force_login(self.user)
        request = self.view_request()
        self.post_view(request)
        self.company(3)
        rebuild_clusters()
        self.assertEqual(self.post_view({**request, 'revision': 1}).status_code, 409)
        loaded = self.client.get(self.view_url).json()
        self.assertEqual(loaded['payload']['positions'], request['payload']['positions'])
        self.assertEqual(GraphViewState.objects.count(), 1)

    def test_invalid_coordinates_and_unknown_nodes_are_rejected(self):
        self.client.force_login(self.user)
        for payload in (
            {'positions': {'unknown': {'x': 0, 'y': 0, 'pinned': True}}},
            {'positions': {f'company:{self.companies[0].pk}': {'x': float('nan'), 'y': 0, 'pinned': False}}},
            {'positions': {f'company:{self.companies[0].pk}': {'x': True, 'y': 0, 'pinned': False}}},
            {'zoom': {'x': 0, 'y': 0, 'k': 0}}, {'filters': ['invented']}, {'selected': 'unknown'},
            {'positions': {} , 'injected': 'value'},
        ):
            self.assertEqual(self.post_view({**self.view_request(), 'payload': payload}).status_code, 400)
        self.assertEqual(GraphViewState.objects.count(), 0)

    def test_writes_require_authentication_and_csrf_and_job_staff(self):
        self.assertEqual(self.post_view(self.view_request()).status_code, 403)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(protected.post(self.view_url, data=json.dumps(self.view_request()), content_type='application/json').status_code, 403)
        self.client.force_login(self.user)
        rebuild_url = reverse('graph:graph_rebuild', args=[self.cluster.uuid])
        self.assertEqual(self.client.post(rebuild_url).status_code, 403)
        self.assertEqual(self.client.get(rebuild_url).status_code, 405)

    def test_rebuild_request_deduplicates_and_only_enqueues_after_commit(self):
        self.client.force_login(self.staff)
        url = reverse('graph:graph_rebuild', args=[self.cluster.uuid])
        with patch('apps.graph.jobs.rebuild_graph_task.delay') as enqueue:
            with self.captureOnCommitCallbacks(execute=True):
                first = self.client.post(url)
                second = self.client.post(url)
                self.assertFalse(enqueue.called)
            self.assertEqual(enqueue.call_count, 1)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(first.json()['job'], second.json()['job'])
        self.assertFalse(second.json()['created'])
        self.assertEqual(GraphRebuildJob.objects.count(), 1)

    def test_background_task_uses_saved_inputs_and_reports_result(self):
        with patch('apps.graph.jobs.enqueue'):
            job, _ = request_rebuild(self.staff, [self.companies[0].pk])
        with patch('requests.sessions.Session.request', side_effect=AssertionError('No source calls')):
            result = rebuild_graph_task.run(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, 'succeeded')
        self.assertEqual(result['snapshots_created'], 0)
        self.assertEqual(result['results'][0]['graph_hash'], self.cluster.current_snapshot.graph_hash)
        self.assertEqual(rebuild_graph_task.run(job.pk), {'status': 'succeeded'})

    def test_broker_failure_remains_visible_and_can_be_retried(self):
        with patch('apps.graph.jobs.rebuild_graph_task.delay', side_effect=RuntimeError('fixture')):
            with self.captureOnCommitCallbacks(execute=True):
                first, _ = request_rebuild(self.staff, [self.companies[0].pk])
        first.refresh_from_db()
        self.assertEqual(first.error_code, 'broker_unavailable')
        with patch('apps.graph.jobs.enqueue'):
            second, created = request_rebuild(self.staff, [self.companies[0].pk])
        self.assertTrue(created)
        self.assertNotEqual(first.pk, second.pk)
