from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from apps.companies.models import Supplier
from apps.graph.models import RiskCluster
from apps.graph.services import build_director_map
from apps.ingestion.models import IngestionRun
from apps.ingestion.services import run_pipeline, IngestionFailure
from apps.ingestion.dto import SourceResult, ResultStatus
from apps.ingestion.observations import record_observation
from apps.core.tasks import update_all_data
from apps.owners.models import Director
from .helpers import FakeProviders, verified_role


class EvidenceRegressionTests(TestCase):
    def test_observation_rejects_credential_query_parameters(self):
        run = IngestionRun.objects.create(mode='enrich')
        result = SourceResult('adata', 'company:000000000001', ResultStatus.UNAVAILABLE,
                              source_url='https://pk.adata.kz/company?token=private')
        with self.assertRaisesMessage(ValueError, 'invalid_observation_url'):
            record_observation(run, result)

    def test_explicit_absence_without_name_retires_and_clears_display_name(self):
        company = Supplier.objects.create(bin='000000000001', name='First')
        run_pipeline(mode='enrich', force=True, providers=FakeProviders(results={
            ('goszakup_supplier', company.bin): {'director_name': 'Synthetic'}}))
        run_pipeline(mode='enrich', force=True, providers=FakeProviders(results={
            ('goszakup_supplier', company.bin): {'director_absent': True}}))
        company.refresh_from_db()
        self.assertEqual(company.director_name, '')
        self.assertFalse(company.directorships.get().is_current)

    def test_incomplete_owner_payload_cannot_retire_roles(self):
        company = Supplier.objects.create(bin='000000000001', name='First')
        run_pipeline(mode='enrich', force=True, providers=FakeProviders(results={
            ('goszakup_supplier', company.bin): {'owners_complete': True, 'owners': [{'full_name': 'Synthetic owner'}]}}))
        with self.assertRaises(IngestionFailure):
            run_pipeline(mode='enrich', force=True, providers=FakeProviders(results={
                ('goszakup_supplier', company.bin): {'owners_complete': True}}))
        self.assertTrue(company.ownerships.get().is_current)

    def test_unrelated_observation_cannot_confirm_director_link(self):
        first = Supplier.objects.create(bin='000000000001', name='First')
        other = Supplier.objects.create(bin='000000000002', name='Second')
        director = Director.objects.create(full_name='Synthetic')
        first_role = verified_role(first, director)
        other_role = verified_role(other, director)
        other_role.source_observation = first_role.source_observation
        other_role.save(update_fields=['source_observation'])
        self.assertFalse(build_director_map([first, other])[other.pk])
        response = self.client.get(reverse('companies:detail', args=[first.pk]))
        self.assertEqual(response.context['related_by_director'].count(), 0)

    def test_iin_without_confirmation_does_not_create_verified_person(self):
        company = Supplier.objects.create(bin='000000000001', name='First')
        providers = FakeProviders(results={('goszakup_supplier', company.bin): {
            'director_name': 'Synthetic', 'director_iin': '000000000010'}})
        run_pipeline(mode='enrich', providers=providers)
        role = company.directorships.get()
        self.assertFalse(role.person_identity.is_verified)
        self.assertFalse(build_director_map([company])[company.pk])

    def test_repeated_enrichment_without_fact_change_keeps_cluster_uuid_text_and_fingerprint(self):
        companies = [Supplier.objects.create(bin=f'{index:012}', name=f'Company {index}') for index in (1, 2)]
        results = {('goszakup_supplier', company.bin): {'name': company.name, 'address': 'Same synthetic office'}
                   for company in companies}
        run_pipeline(mode='enrich', force=True, providers=FakeProviders(results=results))
        cluster = RiskCluster.objects.get(is_active=True)
        cluster.ai_explanation, cluster.explanation_stale = 'Saved explanation', False
        cluster.save(update_fields=['ai_explanation', 'explanation_stale'])
        original = (cluster.uuid, cluster.analysis_fingerprint, cluster.last_analyzed_at)
        run_pipeline(mode='enrich', force=True, providers=FakeProviders(results=results))
        cluster.refresh_from_db()
        self.assertEqual((cluster.uuid, cluster.analysis_fingerprint, cluster.last_analyzed_at), original)
        self.assertEqual(cluster.ai_explanation, 'Saved explanation')
        self.assertFalse(cluster.explanation_stale)

    @override_settings(ENABLE_SCHEDULED_IMPORT=True)
    def test_celery_retry_preserves_run_uuid_without_serializing_source_error(self):
        run = IngestionRun.objects.create(mode='update', status='partial')
        from celery.exceptions import Retry
        def retry(*, exc, throw, kwargs):
            self.assertEqual(kwargs, {'resume': str(run.uuid)})
            self.assertFalse(throw)
            return Retry(exc=exc)
        with (patch('apps.core.tasks.run_pipeline', side_effect=IngestionFailure(run, 'source_http_503')),
              patch.object(update_all_data, 'retry', side_effect=retry)):
            with self.assertRaises(Retry):
                update_all_data.run()

    def test_director_change_before_rebuild_does_not_leave_old_current_link(self):
        company = Supplier.objects.create(bin='000000000001', name='First')
        director = Director.objects.create(full_name='Old director')
        role = verified_role(company, director)
        role.is_current = False
        role.observed_until = timezone.now() - timedelta(days=1)
        role.save(update_fields=['is_current', 'observed_until'])
        self.assertFalse(build_director_map([company])[company.pk])
