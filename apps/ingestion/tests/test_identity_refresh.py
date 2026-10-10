"""Synthetic regressions for role refresh, provenance and bounded identity reuse."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.companies.models import Supplier
from apps.graph.evidence import confirmed_owner
from apps.graph.models import GraphSnapshot
from apps.graph.services import rebuild_clusters
from apps.ingestion.dto import ResultStatus, SourceResult
from apps.ingestion.identities import resolve_person, synchronize_director, synchronize_owners
from apps.ingestion.models import IdentityCandidate, IngestionRun, PersonSourceIdentity
from apps.ingestion.observations import apply_company_facts, record_observation
from apps.owners.models import Directorship, Ownership, PersonIdentity
from apps.owners.querysets import is_confirmed_role


class IdentityRefreshTests(TestCase):
    def setUp(self):
        self.ingestion_run = IngestionRun.objects.create(mode='enrich')
        self.company = Supplier.objects.create(bin='000000000001', name='Synthetic company')
        self.earlier = timezone.now() - timedelta(days=3)

    def observation(self, *, company=None, source='goszakup_supplier', when=None, status=ResultStatus.SUCCESS, **facts):
        company = company or self.company
        return record_observation(self.ingestion_run, SourceResult(source, f'company:{company.bin}', status,
            data={'bin': company.bin, **facts}, observed_at=when or self.earlier), company)

    def director_facts(self, **extra):
        return {'director_name': 'Synthetic person', 'director_iin': '000000000010',
                'director_iin_verified': True, **extra}

    def owner_facts(self, **extra):
        return {'owners_complete': True, 'owners': [{'full_name': 'Synthetic owner', 'iin': '000000000011',
                'iin_verified': True, **extra}]}

    def test_same_verified_director_source_and_date_refresh_keeps_backing_source_consistent(self):
        first = self.observation(**self.director_facts())
        synchronize_director(self.company, first)
        second = self.observation(source='adata', when=self.earlier + timedelta(days=1),
            **self.director_facts(director_start_date='2020-01-01', director_end_date='2030-01-01'))
        synchronize_director(self.company, second)
        role = Directorship.objects.get(is_current=True)
        self.assertEqual(role.source, role.source_observation.source)
        self.assertTrue(is_confirmed_role(role))
        self.assertEqual(role.start_date.isoformat(), '2020-01-01')
        self.assertEqual(PersonIdentity.objects.count(), 1)

    def test_same_verified_owner_source_refresh_keeps_backing_source_consistent(self):
        synchronize_owners(self.company, self.observation(**self.owner_facts(share_percent='10.00')))
        second = self.observation(source='adata', when=self.earlier + timedelta(days=1),
            **self.owner_facts(share_percent='20.00'))
        synchronize_owners(self.company, second)
        role = Ownership.objects.get(is_current=True)
        self.assertEqual(role.source, role.source_observation.source)
        self.assertTrue(confirmed_owner(role))
        self.assertEqual(role.share_percent, Decimal('20.00'))
        self.assertEqual(PersonIdentity.objects.count(), 1)

    def test_owner_newer_refresh_cannot_be_overwritten_by_intermediate_older_observation(self):
        synchronize_owners(self.company, self.observation(**self.owner_facts(share_percent='10.00')))
        latest = self.observation(when=self.earlier + timedelta(days=2), **self.owner_facts(share_percent='20.00'))
        synchronize_owners(self.company, latest)
        older = self.observation(when=self.earlier + timedelta(days=1), **self.owner_facts(share_percent='30.00'))
        with self.assertRaisesMessage(ValueError, 'out_of_order_role_observation'):
            synchronize_owners(self.company, older)
        role = Ownership.objects.get(is_current=True)
        self.assertEqual(role.share_percent, Decimal('20.00'))
        self.assertEqual(role.source_observation_id, latest.pk)

    def test_director_newer_date_refresh_cannot_be_overwritten_by_older_observation(self):
        synchronize_director(self.company, self.observation(**self.director_facts()))
        latest = self.observation(when=self.earlier + timedelta(days=2),
            **self.director_facts(director_start_date='2021-01-01', director_end_date='2030-01-01'))
        synchronize_director(self.company, latest)
        older = self.observation(when=self.earlier + timedelta(days=1),
            **self.director_facts(director_start_date='2020-01-01', director_end_date='2030-01-01'))
        with self.assertRaisesMessage(ValueError, 'out_of_order_role_observation'):
            synchronize_director(self.company, older)
        self.assertEqual(Directorship.objects.get(is_current=True).start_date.isoformat(), '2021-01-01')

    def test_unchanged_director_refresh_keeps_order_fence_without_recreating_graph(self):
        other = Supplier.objects.create(bin='000000000002', name='Synthetic other company')
        facts = self.director_facts(director_start_date='2020-01-01', director_end_date='2030-01-01')
        for company in (self.company, other):
            synchronize_director(company, self.observation(company=company, **facts))
        rebuild_clusters()
        original = list(GraphSnapshot.objects.values_list('pk', 'graph_hash'))
        latest = self.observation(when=self.earlier + timedelta(days=2), **facts)
        synchronize_director(self.company, latest)
        role = Directorship.objects.get(supplier=self.company, is_current=True)
        self.assertEqual(role.source_observation_id, latest.pk)
        older = self.observation(when=self.earlier + timedelta(days=1),
            **self.director_facts(director_start_date='2021-01-01', director_end_date='2030-01-01'))
        with self.assertRaisesMessage(ValueError, 'out_of_order_role_observation'):
            synchronize_director(self.company, older)
        rebuild_clusters()
        self.assertEqual(list(GraphSnapshot.objects.values_list('pk', 'graph_hash')), original)

    def test_foreign_or_failed_observation_cannot_change_company_roles(self):
        other = Supplier.objects.create(bin='000000000002', name='Synthetic other company')
        foreign = self.observation(company=other, **self.director_facts())
        with self.assertRaises(ValueError):
            synchronize_director(self.company, foreign)
        self.assertEqual(Directorship.objects.count(), 0)
        unavailable = self.observation(status=ResultStatus.UNAVAILABLE, **self.owner_facts())
        synchronize_owners(self.company, unavailable)
        self.assertEqual(Ownership.objects.count(), 0)

    def test_invalid_replacement_is_atomic_and_keeps_previous_current_director(self):
        synchronize_director(self.company, self.observation(director_name='Synthetic first director'))
        invalid = self.observation(when=self.earlier + timedelta(days=1), director_name='Synthetic replacement',
            director_start_date='2030-01-01', director_end_date='2020-01-01')
        with self.assertRaisesMessage(ValueError, 'invalid_role_interval'):
            synchronize_director(self.company, invalid)
        self.assertEqual(Directorship.objects.get(is_current=True).person_identity.full_name, 'Synthetic first director')
        self.assertEqual(PersonIdentity.objects.count(), 1)

    def test_partial_date_updates_cannot_invert_retained_director_or_owner_interval(self):
        first = self.observation(**self.director_facts(director_start_date='2025-01-01', director_end_date='2030-01-01'))
        synchronize_director(self.company, first)
        wrong_end = self.observation(when=self.earlier + timedelta(days=1), **self.director_facts(director_end_date='2020-01-01'))
        with self.assertRaisesMessage(ValueError, 'invalid_role_interval'):
            synchronize_director(self.company, wrong_end)
        director = Directorship.objects.get(is_current=True)
        self.assertEqual(director.start_date.isoformat(), '2025-01-01')
        self.assertEqual(director.end_date.isoformat(), '2030-01-01')
        self.assertEqual(director.source_observation_id, first.pk)
        owner_first = self.observation(**self.owner_facts(start_date='2025-01-01', end_date='2030-01-01'))
        synchronize_owners(self.company, owner_first)
        owner_wrong_end = self.observation(when=self.earlier + timedelta(days=1), **self.owner_facts(end_date='2020-01-01'))
        with self.assertRaisesMessage(ValueError, 'invalid_role_interval'):
            synchronize_owners(self.company, owner_wrong_end)
        owner = Ownership.objects.get(is_current=True)
        self.assertEqual(owner.start_date.isoformat(), '2025-01-01')
        self.assertEqual(owner.end_date.isoformat(), '2030-01-01')
        self.assertEqual(owner.source_observation_id, owner_first.pk)

    def test_stale_cross_source_owner_keeps_later_episode_without_failing_replay(self):
        latest = self.observation(when=self.earlier + timedelta(days=2), **self.owner_facts(share_percent='20.00'))
        synchronize_owners(self.company, latest)
        older = self.observation(source='adata', when=self.earlier + timedelta(days=1), **self.owner_facts(share_percent='10.00'))
        synchronize_owners(self.company, older)
        owner = Ownership.objects.get(is_current=True)
        self.assertEqual(owner.share_percent, Decimal('20.00'))
        self.assertEqual(owner.source_observation_id, latest.pk)
        self.assertEqual(PersonSourceIdentity.objects.filter(role='owner').count(), 2)

    def test_mixed_source_owner_and_director_replay_preserves_newer_role_evidence(self):
        registry = self.observation(**{**self.owner_facts(share_percent='10.00'),
            **self.director_facts(director_start_date='2020-01-01', director_end_date='2030-01-01')})
        apply_company_facts(self.company)
        latest = self.observation(source='adata', when=self.earlier + timedelta(days=1),
            **{**self.owner_facts(share_percent='20.00'),
               **self.director_facts(director_start_date='2021-01-01', director_end_date='2030-01-01')})
        synchronize_director(self.company, latest)
        synchronize_owners(self.company, latest)
        for _ in range(2):
            apply_company_facts(self.company)
            director = Directorship.objects.get(is_current=True)
            owner = Ownership.objects.get(is_current=True)
            self.assertEqual(director.source_observation_id, latest.pk)
            self.assertEqual(owner.source_observation_id, latest.pk)
            self.assertEqual(owner.share_percent, Decimal('20.00'))
            self.assertEqual(director.start_date.isoformat(), '2021-01-01')
            self.assertTrue(is_confirmed_role(director))
            self.assertTrue(confirmed_owner(owner))
        self.assertNotEqual(registry.pk, latest.pk)

    def test_existing_source_identity_reuse_does_not_scan_all_namesake_candidates(self):
        first = self.observation(director_name='Synthetic namesake')
        person = resolve_person(self.company, first, 'director', 'Synthetic namesake')
        for number in range(2, 14):
            other = Supplier.objects.create(bin=f'{number:012}', name=f'Synthetic company {number}')
            observation = self.observation(company=other, director_name='Synthetic namesake')
            resolve_person(other, observation, 'director', 'Synthetic namesake')
        count = IdentityCandidate.objects.count()
        with self.assertNumQueries(4):
            repeated = resolve_person(self.company, first, 'director', 'Synthetic namesake')
        self.assertEqual(repeated.pk, person.pk)
        self.assertEqual(IdentityCandidate.objects.count(), count)
        self.assertEqual(PersonSourceIdentity.objects.count(), 13)

    def test_newer_name_only_source_does_not_downgrade_matching_verified_director(self):
        verified = self.observation(**self.director_facts())
        apply_company_facts(self.company)
        self.observation(source='adata', when=self.earlier + timedelta(days=1), director_name='Synthetic person')
        apply_company_facts(self.company)
        role = Directorship.objects.get(is_current=True)
        self.assertEqual(role.source_observation_id, verified.pk)
        self.assertTrue(is_confirmed_role(role))
        self.assertEqual(Directorship.objects.count(), 1)

    def test_newer_changed_director_updates_both_company_field_and_current_role(self):
        self.observation(**self.director_facts())
        apply_company_facts(self.company)
        latest = self.observation(source='adata', when=self.earlier + timedelta(days=1), director_name='Synthetic successor')
        apply_company_facts(self.company)
        self.company.refresh_from_db()
        self.assertEqual(self.company.director_name, 'Synthetic successor')
        self.assertEqual(Directorship.objects.get(is_current=True).source_observation_id, latest.pk)
        self.assertFalse(is_confirmed_role(Directorship.objects.get(is_current=True)))

    def test_contract_payload_cannot_be_selected_as_a_company_profile(self):
        from apps.ingestion.models import SourceObservation
        bad = self.observation(source='goszakup_supplier', name='Synthetic unrelated value')
        SourceObservation.objects.filter(pk=bad.pk).update(subject_key='contract:99')
        apply_company_facts(self.company)
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, 'Synthetic company')
