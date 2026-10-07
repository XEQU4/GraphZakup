"""Private layout navigation is paginated, versioned and read-only."""
from datetime import date, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.graph.models import GraphSnapshot, GraphViewState, RiskCluster


class AccountGraphViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('synthetic-view-reader')
        cls.other = get_user_model().objects.create_user('synthetic-view-other')
        cls.path = '/api/v1/account/views/'
        cls.groups = []
        for index in range(8):
            cluster = RiskCluster.objects.create(name=f'Synthetic saved group {index}', is_active=index != 0)
            first = GraphSnapshot.objects.create(cluster=cluster, version=1, graph_hash=f'{index:064x}',
                algorithm_version='synthetic-test', state='active', as_of=date(2026, 10, 7),
                payload={'nodes': [], 'links': []})
            current = GraphSnapshot.objects.create(cluster=cluster, version=2, graph_hash=f'{index+100:064x}',
                algorithm_version='synthetic-test', state='active', as_of=date(2026, 10, 7),
                payload={'nodes': [], 'links': []}, previous=first)
            cluster.current_snapshot = current
            cluster.save(update_fields=['current_snapshot'])
            for user in (cls.user, cls.other):
                state = GraphViewState.objects.create(user=user, cluster=cluster, snapshot=first,
                    payload={'positions': {'synthetic-private-coordinate': {'x': 70, 'y': 80, 'pinned': True}}})
                # Stable fixture ordering without changing immutable snapshots.
                GraphViewState.objects.filter(pk=state.pk).update(updated_at=timezone.now()-timedelta(minutes=index))
            cls.groups.append(cluster)

    def setUp(self):
        self.client = APIClient()

    def test_authentication_and_user_scope_exclude_other_layouts_and_private_payload(self):
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.client.force_login(self.user)
        response = self.client.get(self.path+'?page_size=6')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        body = response.json()
        self.assertEqual(body['count'], 8)
        self.assertEqual(len(body['results']), 6)
        self.assertIn('page=2', body['next'])
        self.assertIsNone(body['previous'])
        first = body['results'][0]
        self.assertEqual(set(first), {'cluster_uuid', 'cluster_name', 'cluster_is_active',
            'saved_snapshot_version', 'current_snapshot_version', 'revision', 'updated_at'})
        self.assertEqual(first['cluster_uuid'], str(self.groups[0].uuid))
        self.assertFalse(first['cluster_is_active'])
        self.assertEqual((first['saved_snapshot_version'], first['current_snapshot_version']), (1, 2))
        self.assertNotIn('synthetic-private-coordinate', response.content.decode())
        self.assertNotIn('synthetic-view-other', response.content.decode())
        self.client.force_login(get_user_model().objects.create_user('synthetic-empty-reader'))
        self.assertEqual(self.client.get(self.path).json()['results'], [])

    def test_pagination_filters_and_invalid_pages_are_bounded(self):
        self.client.force_login(self.user)
        body = self.client.get(self.path+'?page=2&page_size=6').json()
        self.assertEqual(body['count'], 8)
        self.assertEqual(len(body['results']), 2)
        self.assertIsNone(body['next'])
        self.assertEqual(parse_qs(urlsplit(body['previous']).query).get('page', ['1']), ['1'])
        for query in ['user_id=1', 'search=all', 'ordering=name', 'page_size=101', 'page_size=0',
                      'page=0', 'page=1&page=2']:
            with self.subTest(query=query):
                self.assertEqual(self.client.get(self.path+'?'+query).status_code, 400)
        self.assertEqual(self.client.get(self.path+'?page=3&page_size=6').status_code, 404)

    def test_get_preserves_layout_snapshots_and_does_not_orchestrate(self):
        self.client.force_login(self.user)
        before = list(GraphViewState.objects.order_by('pk').values())
        snapshots = list(GraphSnapshot.objects.order_by('pk').values())
        with patch('apps.graph.services.rebuild_clusters', side_effect=AssertionError('GET rebuilt graph')), patch(
                'apps.ai.services.prepare_analysis', side_effect=AssertionError('GET prepared analysis')):
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(self.path+'?page_size=6')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(GraphViewState.objects.order_by('pk').values()), before)
        self.assertEqual(list(GraphSnapshot.objects.order_by('pk').values()), snapshots)
        # Session/user, count and one joined page; no per-card snapshot queries.
        self.assertLessEqual(len(queries), 4)

    def test_missing_current_snapshot_and_write_methods_are_explicit(self):
        cluster = self.groups[0]
        cluster.current_snapshot = None
        cluster.save(update_fields=['current_snapshot'])
        self.client.force_login(self.user)
        first = self.client.get(self.path).json()['results'][0]
        self.assertIsNone(first['current_snapshot_version'])
        self.assertEqual(first['saved_snapshot_version'], 1)
        self.assertEqual(self.client.post(self.path, {}, format='json').status_code, 405)
        self.assertEqual(self.client.put(self.path, {}, format='json').status_code, 405)
