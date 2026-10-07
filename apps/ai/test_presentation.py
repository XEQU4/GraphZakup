"""Readability, preserved history, source uncertainty and HTML escaping."""
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.graph.services import rebuild_clusters
from apps.ingestion.tests.helpers import verified_role
from apps.owners.models import Director
from .jobs import analyse_cluster_task
from .models import AnalysisSnapshot, AnalysisState, Explanation
from .presentation import build_document, document_text, wording_variants
from .services import prepare_analysis, template_for
from .tests import AnalysisFixtures


class PresentationTests(AnalysisFixtures, TestCase):
    def test_director_summary_explains_meaning_points_and_missing_data_once(self):
        cluster, companies = self.group()
        director = Director.objects.create(full_name='Synthetic verified person')
        for company in companies:
            verified_role(company, director, start_date=timezone.localdate() - timedelta(days=1),
                          end_date=timezone.localdate() + timedelta(days=1))
        rebuild_clusters()
        analysis, _ = prepare_analysis(cluster.pk)
        document = AnalysisState.objects.get(cluster=cluster).explanation.presentation['document']
        self.assertEqual(document['score']['value'], 27)
        self.assertEqual([item['points'] for item in document['score']['items']], [25, 2])
        self.assertEqual(len(document['findings']), 2)
        self.assertIn('bid independently', document['summary'])
        self.assertIn('bidding decisions', document['findings'][0]['meaning'])
        text = document_text(document)
        self.assertIn(f'Recorded role dates cover {analysis.inputs["graph_as_of"]}', text)
        self.assertEqual(text.count('No KGD arrears check is saved'), 1)
        self.assertNotIn('Affected company records', text)
        self.assertNotIn('Saved analysis v', text)
        self.assertIn('does not establish collusion', text)

    def test_unknown_role_dates_do_not_become_simultaneous_management(self):
        cluster, companies = self.group()
        director = Director.objects.create(full_name='Synthetic verified person')
        for company in companies:
            verified_role(company, director)
        rebuild_clusters()
        analysis, _ = prepare_analysis(cluster.pk)
        text = template_for(analysis).text
        self.assertIn('simultaneous roles still need confirmation', text)
        self.assertNotIn('Recorded role dates cover', text)

    def test_company_arrears_use_frozen_name_amount_and_date_without_internal_ids(self):
        cluster, companies = self.group()
        companies[0].name = 'Synthetic Cedar Supplies'
        companies[0].save(update_fields=['name'])
        rebuild_clusters()
        self.arrears(companies[0], '123456789012345678.91')
        analysis, _ = prepare_analysis(cluster.pk)
        explanation = template_for(analysis)
        self.assertIn('123456789012345678.91 KZT', explanation.text)
        self.assertIn('Synthetic Cedar Supplies', explanation.text)
        self.assertNotIn(f'company {companies[0].pk} reports', explanation.text)
        self.assertNotIn(f'Company {companies[0].pk} has', explanation.text)
        self.assertNotIn('arrears are unknown for company', explanation.text)
        self.assertIn('company, not its owner', explanation.text)
        financial = next(item for item in explanation.presentation['document']['findings'] if item['title'] == 'Reported company arrears')
        self.assertEqual(financial['companies'][0]['bin'], companies[0].bin)
        self.assertIn(str(timezone.localdate()), financial['fact'])

    def test_retained_zero_and_failed_latest_check_remain_visible(self):
        cluster, companies = self.group()
        self.arrears(companies[0])
        self.arrears(companies[0], status='unavailable')
        analysis, _ = prepare_analysis(cluster.pk)
        document = build_document(analysis)
        self.assertIn('Fresh successful KGD arrears checks: 0 of 2 companies.', document['coverage'])
        self.assertIn('No KGD arrears check is saved for 1 company.', document['coverage'])
        self.assertTrue(any('unsuccessful' in item for item in document['coverage']))
        text = document_text(document)
        self.assertIn('Zero applies to this dated company check', text)
        self.assertIn('last success is retained', text)

    def test_old_positive_result_keeps_date_and_cannot_claim_current_debt(self):
        cluster, companies = self.group()
        self.arrears(companies[0], '123.45', age=400)
        analysis, _ = prepare_analysis(cluster.pk)
        document = build_document(analysis)
        self.assertEqual(analysis.metrics['financial_priority'], 0)
        self.assertIn('1 company result is old or undated and does not establish current arrears.', document['coverage'])
        text = document_text(document)
        self.assertIn('123.45 KZT', text)
        self.assertIn('does not establish current arrears', text)
        self.assertIn(str(timezone.localdate() - timedelta(days=400)), text)

    def test_dense_contact_matches_do_not_repeat_unknown_company_checks(self):
        cluster, _ = self.group(20)
        analysis, _ = prepare_analysis(cluster.pk)
        document = build_document(analysis)
        self.assertEqual(document['score']['value'], 2)
        self.assertEqual(len(document['findings']), 1)
        self.assertLess(len(document_text(document)), 2200)
        self.assertIn('weak signals', document['summary'])
        self.assertIn('No KGD arrears check is saved for 20 companies.', document['coverage'])

    def test_selected_wording_is_saved_and_credited_findings_stay_first(self):
        cluster, companies = self.group()
        self.arrears(companies[0], '100.00')
        analysis, _ = prepare_analysis(cluster.pk)
        plan = {'sections': [{'finding_id': item['id'], 'variant': 1} for item in reversed(analysis.findings)]}
        document = build_document(analysis, plan)
        first = document['findings'][0]
        finding = next(item for item in analysis.findings if item['id'] == first['finding_id'])
        self.assertEqual(finding['contribution'], 20)
        self.assertEqual(first['fact'], wording_variants(analysis, finding)[1])

    def test_new_presentation_requires_explicit_job_and_preserves_old_text(self):
        cluster, _ = self.group()
        with patch('apps.ai.services.TEMPLATE_VERSION', 'synthetic-old-template'):
            analysis, _ = prepare_analysis(cluster.pk)
            old = AnalysisState.objects.get(cluster=cluster).explanation
        prepare_analysis(cluster.pk)
        self.assertEqual(AnalysisState.objects.get(cluster=cluster).explanation_id, old.pk)
        job = self.request(cluster, use_model=False)
        with patch('apps.ai.jobs.generate', side_effect=AssertionError('Unexpected inference')):
            analyse_cluster_task.run(job.pk)
        current = AnalysisState.objects.get(cluster=cluster).explanation
        self.assertNotEqual(current.pk, old.pk)
        self.assertEqual(current.prompt_version, 'explanation-template-5.1')
        self.assertEqual(AnalysisSnapshot.objects.count(), 1)
        self.assertEqual(Explanation.objects.get(pk=old.pk).text, old.text)
        self.assertEqual(self.request(cluster, use_model=False).pk, job.pk)

    def test_get_uses_saved_document_and_escapes_source_labels(self):
        cluster, companies = self.group()
        companies[0].name = '<img src=x onerror=alert(1)>'
        companies[0].save(update_fields=['name'])
        rebuild_clusters()
        self.arrears(companies[0], '100.00')
        analysis, _ = prepare_analysis(cluster.pk)
        companies[0].name = 'Changed name after saved explanation'
        companies[0].save(update_fields=['name'])
        with patch('apps.ai.services.build_document', side_effect=AssertionError('GET reconstructed text')):
            page = self.client.get(reverse('graph:cluster_detail', args=[cluster.uuid]))
            data = self.client.get(reverse('ai:data', args=[cluster.uuid])).json()
        self.assertContains(page, 'Review summary')
        self.assertContains(page, 'What to check next')
        self.assertContains(page, '&lt;img src=x onerror=alert(1)&gt;')
        self.assertNotContains(page, '<img src=x onerror=alert(1)>')
        self.assertEqual(data['explanation']['text'], template_for(analysis).text)
        self.assertEqual(data['explanation']['document'], template_for(analysis).presentation['document'])

    def test_legacy_saved_text_is_not_reinterpreted_on_get(self):
        cluster, _ = self.group()
        analysis, _ = prepare_analysis(cluster.pk)
        old = Explanation.objects.create(analysis=analysis, reuse_key='synthetic-legacy', provider='template',
            prompt_version='synthetic-old', text='Preserved historical explanation.')
        AnalysisState.objects.filter(cluster=cluster).update(explanation=old)
        page = self.client.get(reverse('graph:cluster_detail', args=[cluster.uuid]))
        self.assertContains(page, old.text)
        self.assertNotContains(page, 'What to check next')
