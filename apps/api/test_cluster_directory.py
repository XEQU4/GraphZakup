"""Directory semantics are frozen, paginated in SQL and read-only."""
from copy import deepcopy
from datetime import date
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.ai.models import AnalysisSnapshot, AnalysisState, Explanation
from apps.companies.models import Supplier
from apps.graph.models import GraphSnapshot, RiskCluster


class ClusterDirectoryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sequence = 0

    def group(self, *, kind='address', count=2, checked=None, members=None,
              evidence=True, verified=True, analysis=True):
        self.sequence += 1
        number = self.sequence
        ids = members or list(range(number * 10, number * 10 + count))
        cluster = RiskCluster.objects.create(name=f'Saved group {number}', risk_score=99)
        role = kind in {'director', 'owner'}
        nodes = [{'id': f'company:{pk}', 'kind': 'company', 'company_id': pk,
                  'name': f'Frozen enterprise {pk}', 'bin': f'{pk:012}'} for pk in sorted(set(ids))]
        nodes.append({'id': 'shared', 'kind': 'person' if role else 'contact',
                      'name': 'Synthetic saved contact', 'contact_type': kind,
                      'identity_verified': verified})
        links = [{'id': f'edge:{pk}', 'source': f'company:{pk}', 'target': 'shared',
                  'company_id': pk, 'type': kind, 'value': '', 'confidence': 'weak',
                  'valid_from': None, 'valid_until': None, 'temporal_status': 'unknown',
                  'common_contact': False, 'limitations': [],
                  'evidence': [{'source': 'synthetic'}] if evidence else []} for pk in ids]
        snapshot = GraphSnapshot.objects.create(cluster=cluster, version=1,
            graph_hash=f'{number:064}', algorithm_version='synthetic', state='active',
            as_of=date(2026, 10, 8), member_ids=ids, payload={'nodes': nodes, 'links': links})
        cluster.current_snapshot = snapshot
        cluster.save(update_fields=['current_snapshot'])
        if analysis:
            metrics = {'review_priority': 2 if kind == 'address' else 5,
                       'company_count': len(set(ids)), 'fresh_arrears_checks': checked or 0}
            self.analysis(cluster, snapshot, metrics)
        return cluster

    def analysis(self, cluster, snapshot, metrics, *, version=1):
        analysis = AnalysisSnapshot.objects.create(cluster=cluster, graph_snapshot=snapshot,
            version=version, analysis_hash=f'{cluster.pk * 100 + version:064}',
            input_hash='0' * 64, rules_version='review-rules-5.0', as_of=date(2026, 10, 8),
            metrics=metrics)
        explanation = Explanation.objects.create(analysis=analysis,
            reuse_key=f'{cluster.pk * 100 + version:064}', provider='template',
            prompt_version='synthetic', status='ready', text='Synthetic saved explanation.')
        AnalysisState.objects.update_or_create(cluster=cluster,
            defaults={'analysis': analysis, 'explanation': explanation})
        return analysis

    def get(self, path='/api/v1/clusters/', **query):
        response = self.client.get(path, query)
        self.assertEqual(response.status_code, 200, response.content.decode())
        return response.json()

    def detail(self, cluster):
        return self.get(f'/api/v1/clusters/{cluster.uuid}/')

    def test_title_companies_reasons_and_scores_use_saved_evidence(self):
        cluster = self.group(kind='phone', count=5)
        data = self.detail(cluster)
        directory = data['directory']
        self.assertEqual(data['name'], 'Saved group 1')
        self.assertEqual(directory['title'], 'Shared phone · 5 companies')
        self.assertEqual(directory['reasons'], [
            {'type': 'phone', 'label': 'Shared phone', 'company_count': 5}])
        self.assertEqual(directory['primary_reason'], directory['reasons'][0])
        self.assertEqual(len(directory['companies']), 3)
        self.assertEqual(directory['additional_companies'], 2)
        self.assertEqual(directory['review_priority'], 5)
        self.assertEqual(directory['analysis_status'], 'ready')
        self.assertEqual(directory['analysis_as_of'], '2026-10-08')
        self.assertEqual(directory['coverage'],
            {'status': 'no_checks', 'checked': 0, 'total': 5, 'as_of': '2026-10-08'})

    def test_frozen_search_does_not_follow_mutable_supplier_names_or_bins(self):
        company = Supplier.objects.create(bin='160000000001', name='Mutable replacement name')
        cluster = self.group(members=[company.pk, company.pk + 1])
        self.assertEqual(self.get(search=f'Frozen enterprise {company.pk}')['count'], 1)
        self.assertEqual(self.get(search=f'{company.pk:012}')['count'], 1)
        self.assertEqual(self.get(search=company.name)['count'], 0)
        self.assertEqual(self.get(search=company.bin)['count'], 0)
        self.assertEqual(self.get(search=cluster.name)['count'], 1)
        self.assertEqual(self.get(search='Shared address · 2 companies')['count'], 1)
        self.assertEqual(self.get(search='shared address')['count'], 1)
        self.assertEqual(self.get(search='Synthetic saved contact')['count'], 0)

    def test_search_treats_percent_underscore_and_sql_text_as_literals(self):
        self.group()
        for search in ('%', '_', "' OR 1=1 --", 'shared phone'):
            self.assertEqual(self.get(search=search)['count'], 0)

    def test_shared_filter_requires_distinct_members_and_actual_evidence(self):
        valid = self.group(kind='phone')
        duplicate = self.group(kind='phone', members=[100, 100])
        missing_evidence = self.group(kind='phone', evidence=False)
        not_shared = self.group(kind='phone', count=1)
        data = self.get(relationship='phone')
        self.assertEqual([item['uuid'] for item in data['results']], [str(valid.uuid)])
        for cluster in (duplicate, missing_evidence, not_shared):
            self.assertEqual(self.detail(cluster)['directory']['reasons'], [])
        self.assertEqual(self.detail(duplicate)['company_count'], 1)

    def test_role_filter_does_not_promote_unverified_identity(self):
        verified = self.group(kind='director', verified=True)
        unverified = self.group(kind='director', verified=False)
        self.assertEqual([item['uuid'] for item in self.get(relationship='director')['results']],
                         [str(verified.uuid)])
        self.assertEqual(self.detail(unverified)['directory']['reasons'], [])

    def test_all_relationship_filters_and_missing_group_are_explicit(self):
        for kind in ('director', 'owner', 'address', 'phone', 'email'):
            group = self.group(kind=kind)
            data = self.get(relationship=kind)
            self.assertEqual(data['count'], 1)
            self.assertEqual(data['results'][0]['uuid'], str(group.uuid))
        bare = RiskCluster.objects.create(name='Uncalculated', risk_score=99)
        data = self.detail(bare)['directory']
        self.assertEqual(data['title'], 'Group awaiting a saved graph')
        self.assertEqual(data['analysis_status'], 'not_calculated')
        self.assertIsNone(data['review_priority'])
        self.assertEqual(data['coverage']['status'], 'not_assessed')

    def test_coverage_filters_use_saved_checks_and_paginate_before_serialization(self):
        expected = {
            'not_assessed': self.group(analysis=False),
            'no_checks': self.group(checked=0),
            'partial': self.group(checked=1),
            'checked': self.group(checked=2),
        }
        for status, cluster in expected.items():
            data = self.get(coverage=status, page_size=1)
            self.assertEqual(data['count'], 1)
            self.assertEqual(data['results'][0]['uuid'], str(cluster.uuid))
            self.assertEqual(data['results'][0]['directory']['coverage']['status'], status)
        more = [self.group(kind='phone', checked=0) for _ in range(3)]
        first = self.get(relationship='phone', coverage='no_checks', page_size=1, ordering='created_at')
        second = self.get(relationship='phone', coverage='no_checks', page_size=1,
                          ordering='created_at', page=2)
        self.assertEqual(first['count'], 3)
        self.assertEqual(first['results'][0]['uuid'], str(more[0].uuid))
        self.assertEqual(second['results'][0]['uuid'], str(more[1].uuid))
        self.assertIsNotNone(first['next'])
        self.assertIsNotNone(second['previous'])

    def test_analysis_for_an_old_graph_is_not_current_score_or_coverage(self):
        cluster = self.group(checked=2)
        old = cluster.current_snapshot
        new = GraphSnapshot.objects.create(cluster=cluster, version=2, graph_hash='f' * 64,
            algorithm_version='synthetic', state='active', as_of=old.as_of,
            member_ids=old.member_ids, payload=deepcopy(old.payload), previous=old)
        cluster.current_snapshot = new
        cluster.save(update_fields=['current_snapshot'])
        data = self.detail(cluster)['directory']
        self.assertEqual(data['analysis_status'], 'stale')
        self.assertIsNone(data['review_priority'])
        self.assertIsNone(data['analysis_as_of'])
        self.assertEqual(data['coverage']['status'], 'not_assessed')
        self.assertIsNone(data['coverage']['checked'])
        self.assertEqual(self.get(coverage='checked')['count'], 0)
        self.assertEqual(self.get(minimum_review_priority=1)['count'], 0)
        self.assertEqual(self.get(coverage='not_assessed')['count'], 1)

    def test_bad_coverage_metrics_are_unassessed_not_zero_or_complete(self):
        metrics_list = [
            {'company_count': 2},
            {'company_count': 2, 'fresh_arrears_checks': None},
            {'company_count': 2, 'fresh_arrears_checks': '2'},
            {'company_count': 2, 'fresh_arrears_checks': True},
            {'company_count': 2, 'fresh_arrears_checks': 3},
            {'company_count': 2, 'fresh_arrears_checks': -1},
            {'company_count': 3, 'fresh_arrears_checks': 2},
        ]
        for metrics in metrics_list:
            cluster = self.group(analysis=False)
            self.analysis(cluster, cluster.current_snapshot, {'review_priority': 2, **metrics})
            self.assertEqual(self.detail(cluster)['directory']['coverage']['status'], 'not_assessed')
        self.assertEqual(self.get(coverage='not_assessed')['count'], len(metrics_list))
        self.assertEqual(self.get(coverage='checked')['count'], 0)
        self.assertEqual(self.get(coverage='no_checks')['count'], 0)

    def test_search_filters_and_large_page_have_a_constant_query_count(self):
        self.group()
        with CaptureQueriesContext(connection) as small:
            self.get(search='Frozen', relationship='address', coverage='no_checks')
        for _ in range(11):
            self.group()
        with CaptureQueriesContext(connection) as large:
            data = self.get(search='Frozen', relationship='address', coverage='no_checks')
        self.assertEqual(data['count'], 12)
        self.assertEqual(len(large), len(small))
        self.assertLessEqual(len(large), 3)

    def test_get_preserves_saved_rows_and_never_starts_generation(self):
        cluster = self.group()
        before = list(Explanation.objects.values())
        with patch('apps.ai.services.prepare_analysis', side_effect=AssertionError('GET wrote analysis')), patch(
                'apps.graph.services.rebuild_clusters', side_effect=AssertionError('GET rebuilt')), CaptureQueriesContext(connection) as queries:
            self.get(relationship='address', coverage='no_checks', search='Shared address')
            self.detail(cluster)
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
                             for query in queries))
        self.assertEqual(list(Explanation.objects.values()), before)

    def test_filters_are_strict(self):
        for query in ({'relationship': 'supplier'}, {'coverage': 'high'},
                      {'relationship': 'address,phone'}, {'minimum_review_priority': -1}):
            self.assertEqual(self.client.get('/api/v1/clusters/', query).status_code, 400)


    def test_mismatched_analysis_owner_does_not_expose_score_or_coverage(self):
        first = self.group(checked=2)
        second = self.group(checked=2)
        foreign = AnalysisState.objects.get(cluster=second)
        AnalysisState.objects.filter(cluster=first).update(analysis=foreign.analysis, explanation=foreign.explanation)
        directory = self.detail(first)['directory']
        self.assertEqual(directory['analysis_status'], 'stale')
        self.assertIsNone(directory['review_priority'])
        self.assertEqual(directory['coverage']['status'], 'not_assessed')
        self.assertEqual(self.get(coverage='checked')['count'], 1)

    def test_nonmember_and_wrong_source_edges_cannot_manufacture_a_reason(self):
        cluster = self.group()
        old = cluster.current_snapshot
        payload = deepcopy(old.payload)
        payload['links'][1]['company_id'] = 999999
        replacement = GraphSnapshot.objects.create(cluster=cluster, version=2, graph_hash='a' * 64,
            algorithm_version='synthetic', state='active', as_of=old.as_of,
            member_ids=old.member_ids, payload=payload, previous=old)
        cluster.current_snapshot = replacement
        cluster.save(update_fields=['current_snapshot'])
        self.assertEqual(self.get(relationship='address')['count'], 0)
        self.assertEqual(self.detail(cluster)['directory']['reasons'], [])

    def test_readable_title_search_matches_the_same_primary_reason_as_cards(self):
        cluster = self.group(kind='address')
        old = cluster.current_snapshot
        payload = deepcopy(old.payload)
        payload['nodes'].append({'id': 'phone', 'kind': 'contact', 'name': 'Synthetic phone',
                                 'contact_type': 'phone'})
        payload['links'].extend([{**edge, 'id': f"phone:{edge['id']}", 'target': 'phone', 'type': 'phone'}
                                 for edge in old.payload['links']])
        replacement = GraphSnapshot.objects.create(cluster=cluster, version=2, graph_hash='b' * 64,
            algorithm_version='synthetic', state='active', as_of=old.as_of,
            member_ids=old.member_ids, payload=payload, previous=old)
        cluster.current_snapshot = replacement
        cluster.save(update_fields=['current_snapshot'])
        directory = self.detail(cluster)['directory']
        self.assertEqual(directory['title'], 'Shared phone · 2 companies')
        self.assertEqual([reason['type'] for reason in directory['reasons']], ['phone', 'address'])
        self.assertEqual(self.get(search=directory['title'])['count'], 1)
        self.assertEqual(self.get(relationship='address')['count'], 1)


    def replace_graph(self, cluster, payload):
        old = cluster.current_snapshot
        replacement = GraphSnapshot.objects.create(cluster=cluster, version=old.version + 1,
            graph_hash=f'{cluster.pk + 1000:064}', algorithm_version='synthetic', state='active',
            as_of=old.as_of, member_ids=old.member_ids, payload=payload, previous=old)
        cluster.current_snapshot = replacement
        cluster.save(update_fields=['current_snapshot'])

    def test_verified_mixed_roles_have_their_own_reason_and_filter(self):
        cluster = self.group(kind='director')
        payload = deepcopy(cluster.current_snapshot.payload)
        payload['links'][1]['type'] = 'owner'
        self.replace_graph(cluster, payload)
        directory = self.detail(cluster)['directory']
        self.assertEqual(directory['title'], 'Shared person across roles · 2 companies')
        self.assertEqual(directory['reasons'],
            [{'type': 'mixed_roles', 'label': 'Shared person across roles', 'company_count': 2}])
        self.assertEqual(self.get(relationship='mixed_roles')['count'], 1)
        self.assertEqual(self.get(relationship='director')['count'], 0)
        self.assertEqual(self.get(relationship='owner')['count'], 0)
        self.assertEqual(self.get(search=directory['title'])['count'], 1)

    def test_multiple_roles_in_one_company_are_not_a_shared_person(self):
        cluster = self.group(kind='director', count=1)
        payload = deepcopy(cluster.current_snapshot.payload)
        payload['links'].append({**payload['links'][0], 'type': 'owner', 'id': 'extra-role'})
        self.replace_graph(cluster, payload)
        self.assertEqual(self.get(relationship='mixed_roles')['count'], 0)
        self.assertEqual(self.detail(cluster)['directory']['reasons'], [])

    def test_chain_reason_counts_distinct_companies_across_shared_targets(self):
        cluster = self.group(kind='phone', count=3)
        payload = deepcopy(cluster.current_snapshot.payload)
        payload['nodes'].append({'id': 'other-phone', 'kind': 'contact',
                                 'name': 'Synthetic second phone', 'contact_type': 'phone'})
        payload['links'][2]['target'] = 'other-phone'
        payload['links'].append({**payload['links'][1], 'id': 'second-link', 'target': 'other-phone'})
        self.replace_graph(cluster, payload)
        directory = self.detail(cluster)['directory']
        self.assertEqual(directory['reasons'],
            [{'type': 'phone', 'label': 'Shared phone', 'company_count': 3}])
        self.assertEqual(self.get(relationship='phone')['count'], 1)

    def test_legacy_stale_flag_does_not_replace_authoritative_saved_state(self):
        cluster = self.group(checked=2)
        self.assertTrue(cluster.explanation_stale)
        directory = self.detail(cluster)['directory']
        self.assertEqual(directory['analysis_status'], 'ready')
        self.assertEqual(directory['review_priority'], 2)
        self.assertEqual(directory['coverage']['status'], 'checked')


    def test_frozen_cyrillic_names_are_searchable(self):
        cluster = self.group()
        payload = deepcopy(cluster.current_snapshot.payload)
        payload['nodes'][0]['name'] = 'СИНТЕТИЧЕСКАЯ КОМПАНИЯ'
        self.replace_graph(cluster, payload)
        self.assertEqual(self.get(search='СИНТЕТИЧЕСКАЯ')['count'], 1)
        if connection.vendor == 'postgresql':
            self.assertEqual(self.get(search='синтетическая')['count'], 1)


    def test_uncalculated_group_is_searchable_by_its_displayed_title(self):
        group = RiskCluster.objects.create(name='Saved uncalculated group')
        title = self.detail(group)['directory']['title']
        self.assertEqual(self.get(search=title)['count'], 1)

    def test_invalid_saved_scores_are_unknown_not_clamped_or_legacy_risk(self):
        for score in (999, -1, True, '99', None):
            cluster = self.group(analysis=False)
            self.analysis(cluster, cluster.current_snapshot,
                {'review_priority': score, 'company_count': 2, 'fresh_arrears_checks': 0})
            data = self.detail(cluster)
            self.assertIsNone(data['review_priority'])
            self.assertIsNone(data['directory']['review_priority'])
        self.assertEqual(self.get(minimum_review_priority=0)['count'], 0)
