"""Entity reads preserve identifiers, exact money, uncertain checks and bounded SQL."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.ingestion.models import CompanyKgdState, IngestionRun, SourceObservation
from apps.ingestion.tests.helpers import verified_role
from apps.owners.models import Director, Directorship, Owner, Ownership, PersonIdentity


class EntityApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Supplier.objects.create(bin='000000000102', name='Synthetic Riverstone Services',
            risk_score=91, website='https://example.test/company')
        cls.customer = Supplier.objects.create(bin='000000000103', name='Synthetic Customer',
            is_supplier=False, is_customer=True)
        cls.contract = Contract.objects.create(supplier=cls.company, customer=cls.customer,
            contract_number='synthetic-exact-money', contract_gos_id=123, tender_id='same-tender',
            title='Synthetic procurement', amount=Decimal('123456.91'),
            contract_date=timezone.localdate(), customer_name=cls.customer.name, customer_bin=cls.customer.bin)
        cls.ingestion_run = IngestionRun.objects.create(mode='update', status='succeeded')

    def observation(self, company, *, source='kgd_tax_debt', status='success', facts=None, age=0, **extra):
        return SourceObservation.objects.create(run=self.ingestion_run, supplier=company, source=source,
            subject_key=f'company:{company.bin}', status=status,
            normalized_values=facts or {}, raw_values={'secret': 'synthetic-private-sentinel'},
            fingerprint=f'{SourceObservation.objects.count() + 1:064}', parser_version='3.1',
            observed_at=timezone.now() - timedelta(days=age), **extra)

    def debt_facts(self, company=None, *, amount='0.00', reporting_date=None):
        company = company or self.company
        return {'bin': company.bin, 'kgd_total_arrears': amount, 'kgd_tax_arrears': amount,
            'kgd_pension_arrears': '0.00', 'kgd_social_arrears': '0.00', 'kgd_health_insurance_arrears': '0.00',
            'kgd_reporting_dates': [str(reporting_date or timezone.localdate())]}

    def test_companies_include_customers_without_html_or_unlabelled_risk(self):
        self.company.name = '<img src=x onerror=alert(1)>'
        self.company.save(update_fields=['name'])
        response = self.client.get('/api/v1/companies/')
        self.assertEqual(response.status_code, 200)
        rows = response.json()['results']
        self.assertEqual(response.json()['count'], 2)
        row = next(row for row in rows if row['id'] == self.company.pk)
        self.assertEqual(row['name'], self.company.name)
        self.assertEqual(row['legacy_risk_score'], 91)
        self.assertEqual(row['legacy_score_interpretation'], 'uncalibrated_legacy_index')
        self.assertNotIn('risk_score', row)
        self.assertFalse(any(key.endswith('_html') for key in row))
        only_customers = self.client.get('/api/v1/companies/', {'is_customer': 'true'}).json()
        self.assertEqual([row['id'] for row in only_customers['results']], [self.customer.pk])
        exact = self.client.get('/api/v1/companies/', {'bin': self.company.bin}).json()
        self.assertEqual([row['id'] for row in exact['results']], [self.company.pk])

    def test_company_detail_without_checks_does_not_imply_zero_debt(self):
        response = self.client.get(f'/api/v1/companies/{self.company.pk}/')
        self.assertEqual(response.status_code, 200)
        for row in response.json()['kgd_checks']:
            self.assertEqual(row['status'], 'not_checked')
            self.assertIsNone(row['last_successful'])
            self.assertIsNone(row['latest_observed_at'])

    def test_latest_failure_retains_dated_zero_without_claiming_current_success(self):
        successful = self.observation(self.company, facts=self.debt_facts())
        failed = self.observation(self.company, status='unavailable')
        CompanyKgdState.objects.create(supplier=self.company, source='kgd_tax_debt',
            latest_observation=failed, last_successful_observation=successful)
        with self.assertNumQueries(2):
            response = self.client.get(f'/api/v1/companies/{self.company.pk}/')
        check = response.json()['kgd_checks'][1]
        self.assertEqual(check['status'], 'unavailable')
        self.assertEqual(check['latest_observation_id'], failed.pk)
        self.assertEqual(check['last_successful']['observation_id'], successful.pk)
        self.assertEqual(check['last_successful']['total_arrears'], '0.00')
        self.assertTrue(check['last_successful']['stale'])
        self.assertNotIn('synthetic-private-sentinel', response.content.decode())
        self.assertNotIn('raw_values', response.json())

    def test_stale_reporting_date_and_exact_positive_amount_remain_dated(self):
        old_date = timezone.localdate() - timedelta(days=400)
        successful = self.observation(self.company,
            facts=self.debt_facts(amount='123456789012345678.91', reporting_date=old_date))
        CompanyKgdState.objects.create(supplier=self.company, source='kgd_tax_debt',
            latest_observation=successful, last_successful_observation=successful)
        check = self.client.get(f'/api/v1/companies/{self.company.pk}/').json()['kgd_checks'][1]
        self.assertEqual(check['status'], 'success')
        self.assertEqual(check['last_successful']['total_arrears'], '123456789012345678.91')
        self.assertEqual(check['last_successful']['reporting_dates'], [str(old_date)])
        self.assertTrue(check['last_successful']['stale'])
        successful.normalized_values['kgd_reporting_dates'].append(str(timezone.localdate()))
        successful.save(update_fields=['normalized_values'])
        check = self.client.get(f'/api/v1/companies/{self.company.pk}/').json()['kgd_checks'][1]
        self.assertTrue(check['last_successful']['stale'])
        successful.normalized_values['kgd_reporting_dates'] = [str(timezone.localdate() + timedelta(days=1))]
        successful.save(update_fields=['normalized_values'])
        check = self.client.get(f'/api/v1/companies/{self.company.pk}/').json()['kgd_checks'][1]
        self.assertEqual(check['status'], 'invalid')
        self.assertIsNone(check['last_successful'])

    def test_cross_company_or_malformed_kgd_data_is_not_published_as_success(self):
        wrong = self.observation(self.customer, facts=self.debt_facts(self.customer))
        state = CompanyKgdState.objects.create(supplier=self.company, source='kgd_tax_debt',
            latest_observation=wrong, last_successful_observation=wrong)
        check = self.client.get(f'/api/v1/companies/{self.company.pk}/').json()['kgd_checks'][1]
        self.assertEqual(check['status'], 'invalid')
        self.assertIsNone(check['last_successful'])
        self.assertIsNone(check['latest_observation_id'])
        malformed = self.observation(self.company, facts={'bin': self.company.bin, 'kgd_total_arrears': '0'})
        state.latest_observation = state.last_successful_observation = malformed
        state.save()
        check = self.client.get(f'/api/v1/companies/{self.company.pk}/').json()['kgd_checks'][1]
        self.assertEqual(check['status'], 'invalid')
        self.assertIsNone(check['last_successful'])

    def test_taxpayer_not_found_is_distinct_from_unavailable_and_not_checked(self):
        missing = self.observation(self.company, source='kgd_taxpayer', status='not_found')
        CompanyKgdState.objects.create(supplier=self.company, source='kgd_taxpayer', latest_observation=missing)
        checks = self.client.get(f'/api/v1/companies/{self.company.pk}/').json()['kgd_checks']
        self.assertEqual(checks[0]['status'], 'not_found')
        self.assertEqual(checks[1]['status'], 'not_checked')
        self.assertIsNone(checks[0]['last_successful'])

    def test_namesakes_remain_separate_and_private_legacy_person_flags_are_omitted(self):
        owner = Owner.objects.create(full_name='Synthetic Alex Morgan', iin='000000000001',
            has_tax_debt=True, has_court_cases=True, is_bankrupt=True, blacklisted=True, risk_score=100)
        first = PersonIdentity.objects.create(scope_key='synthetic:one', full_name=owner.full_name,
            owner=owner, iin=owner.iin, is_verified=True)
        second = PersonIdentity.objects.create(scope_key='synthetic:two', full_name=owner.full_name)
        rows = self.client.get('/api/v1/people/', {'search': owner.full_name}).json()['results']
        self.assertEqual({row['id'] for row in rows}, {first.pk, second.pk})
        for row in rows:
            self.assertFalse({'iin', 'scope_key', 'risk_score', 'has_tax_debt', 'has_court_cases',
                              'is_bankrupt', 'blacklisted'} & row.keys())
            self.assertEqual(row['history_status'], 'verified_history_not_integrated')
        detail = self.client.get(f'/api/v1/people/{first.pk}/').json()
        self.assertEqual(detail['identity_status'], 'identifier_verified')
        self.assertEqual(self.client.get('/api/v1/people/', {'is_verified': 'false'}).json()['count'], 1)

    def test_roles_expose_evidence_and_unknown_legal_bounds_without_false_identity(self):
        director = Director.objects.create(full_name='Synthetic verified director')
        verified = verified_role(self.company, director)
        verified.source_observation.source_url = 'https://example.test/record?token=synthetic-private-sentinel'
        verified.source_observation.save(update_fields=['source_url'])
        other = Director.objects.create(full_name=director.full_name)
        unverified = Directorship.objects.create(supplier=self.customer, director=other)
        response = self.client.get('/api/v1/directorships/')
        self.assertEqual(response.status_code, 200)
        rows = {row['id']: row for row in response.json()['results']}
        self.assertTrue(rows[verified.pk]['identity_verified'])
        self.assertIsNone(rows[verified.pk]['start_date'])
        self.assertIsNone(rows[verified.pk]['end_date'])
        self.assertIsNone(rows[verified.pk]['currently_applicable'])
        self.assertEqual(rows[verified.pk]['temporal_status'], 'unknown')
        self.assertIsNone(rows[verified.pk]['source_reference']['url'])
        self.assertFalse(rows[unverified.pk]['identity_verified'])
        self.assertIsNone(rows[unverified.pk]['person'])
        self.assertNotIn('synthetic-private-sentinel', response.content.decode())
        filtered = self.client.get('/api/v1/directorships/', {'person_id': verified.person_identity_id}).json()
        self.assertEqual([row['id'] for row in filtered['results']], [verified.pk])
        verified.start_date = timezone.localdate() - timedelta(days=1)
        verified.end_date = timezone.localdate() + timedelta(days=1)
        verified.save(update_fields=['start_date', 'end_date'])
        row = self.client.get('/api/v1/directorships/', {'person_id': verified.person_identity_id}).json()['results'][0]
        self.assertTrue(row['currently_applicable'])
        self.assertTrue(row['identity_verified'])
        self.assertEqual(row['temporal_status'], 'in_period')
        verified.start_date = timezone.localdate() + timedelta(days=1)
        verified.end_date = timezone.localdate() + timedelta(days=2)
        verified.save(update_fields=['start_date', 'end_date'])
        row = self.client.get('/api/v1/directorships/', {'person_id': verified.person_identity_id}).json()['results'][0]
        self.assertFalse(row['currently_applicable'])
        self.assertTrue(row['identity_verified'])
        self.assertEqual(row['temporal_status'], 'not_in_period')
        verified.is_current = False
        verified.save(update_fields=['is_current'])
        row = self.client.get('/api/v1/directorships/', {'person_id': verified.person_identity_id}).json()['results'][0]
        self.assertFalse(row['currently_applicable'])
        self.assertEqual(row['temporal_status'], 'observed_inactive')

    def test_role_end_is_exclusive_and_ownership_share_remains_exact_or_unknown(self):
        owner = Owner.objects.create(full_name='Synthetic owner')
        ownership = Ownership.objects.create(supplier=self.company, owner=owner, share_percent=Decimal('33.33'),
            end_date=timezone.localdate())
        other = Owner.objects.create(full_name='Synthetic unknown share')
        Ownership.objects.create(supplier=self.company, owner=other)
        rows = self.client.get('/api/v1/ownerships/', {'company_id': self.company.pk}).json()['results']
        row = next(row for row in rows if row['id'] == ownership.pk)
        self.assertEqual(row['share_percent'], '33.33')
        self.assertTrue(row['is_current'])
        self.assertFalse(row['currently_applicable'])
        self.assertFalse(row['identity_verified'])
        self.assertIsNone(next(row for row in rows if row['id'] != ownership.pk)['share_percent'])

    def test_ownership_verification_requires_matching_identity_source_and_company(self):
        owner = Owner.objects.create(full_name='Synthetic identified owner', iin='000000000901')
        person = PersonIdentity.objects.create(scope_key='synthetic:owner', full_name=owner.full_name,
            owner=owner, iin=owner.iin, is_verified=True)
        observation = self.observation(self.company, source='synthetic_registry', facts={
            'owners': [{'iin': person.iin, 'iin_verified': True}]})
        ownership = Ownership.objects.create(supplier=self.company, owner=owner, person_identity=person,
            identity_status='verified', source=observation.source, source_observation=observation)
        with self.assertNumQueries(2):
            response = self.client.get('/api/v1/ownerships/', {'person_id': person.pk})
        self.assertTrue(response.json()['results'][0]['identity_verified'])
        self.assertNotIn(person.iin, response.content.decode())
        observation.supplier = self.customer
        observation.save(update_fields=['supplier'])
        row = self.client.get('/api/v1/ownerships/', {'person_id': person.pk}).json()['results'][0]
        self.assertEqual(row['id'], ownership.pk)
        self.assertFalse(row['identity_verified'])
        self.assertIsNone(row['source_reference'])
        observation.supplier = self.company
        observation.normalized_values = []
        observation.save(update_fields=['supplier', 'normalized_values'])
        response = self.client.get('/api/v1/ownerships/', {'person_id': person.pk})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['results'][0]['identity_verified'])

    def test_contract_exact_decimal_dates_roles_and_source_reference(self):
        observation = self.observation(self.company, source='goszakup_contracts', contract=self.contract)
        observation.subject_key = 'contract:123'
        observation.save(update_fields=['subject_key'])
        # A later company-name observation is not the contract fact reference.
        self.observation(self.customer, source='goszakup_contracts', contract=self.contract)
        response = self.client.get(f'/api/v1/contracts/{self.contract.pk}/')
        self.assertEqual(response.status_code, 200)
        row = response.json()
        self.assertEqual(row['amount'], '123456.91')
        self.assertEqual(row['supplier']['id'], self.company.pk)
        self.assertEqual(row['customer']['id'], self.customer.pk)
        self.assertEqual(row['source_url'], 'https://goszakup.gov.kz/ru/egzcontract/cpublic/show/123')
        self.assertEqual(row['source_observation_id'], observation.pk)
        self.assertEqual(self.client.get('/api/v1/contracts/', {'customer_id': self.customer.pk}).json()['count'], 1)
        self.assertEqual(self.client.get('/api/v1/contracts/', {'supplier_id': self.customer.pk}).json()['count'], 0)

    def test_postgresql_contract_preserves_full_decimal_precision(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Full DecimalField precision requires the production PostgreSQL backend.')
        Contract.objects.filter(pk=self.contract.pk).update(amount=Decimal('123456789012345678.91'))
        response = self.client.get(f'/api/v1/contracts/{self.contract.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['amount'], '123456789012345678.91')

    def test_invalid_filters_unknown_keys_dates_and_ordering_fail_explicitly(self):
        cases = [('/api/v1/companies/', {'bin': '102'}), ('/api/v1/companies/', {'bin': '٠٠٠٠٠٠٠٠٠١٠٢'}),
            ('/api/v1/companies/', {'bin': self.company.bin + '\n'}), ('/api/v1/companies/', {'ordering': 'risk_score'}),
            ('/api/v1/companies/', {'is_supplier': 'maybe'}), ('/api/v1/companies/', {'page_size': 101}),
            ('/api/v1/companies/', {'page': 0}), ('/api/v1/people/', {'iin': '000000000001'}),
            ('/api/v1/directorships/', {'person_id': -1}), ('/api/v1/ownerships/', {'ordering': 'owner__iin'}),
            ('/api/v1/contracts/', {'date_from': 'not-a-date'}),
            ('/api/v1/contracts/', {'date_from': '2026-10-07', 'date_to': '2026-10-06'}),
            (f'/api/v1/companies/{self.company.pk}/', {'search': 'ignored'})]
        for path, params in cases:
            with self.subTest(path=path, params=params):
                response = self.client.get(path, params)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['error']['code'], 'validation_error')

    def test_entity_lists_have_constant_query_counts_and_bounded_stable_pages(self):
        companies = [Supplier(bin=f'{number:012}', name='Synthetic tied name') for number in range(200, 230)]
        Supplier.objects.bulk_create(companies)
        Contract.objects.bulk_create([Contract(supplier=self.company, customer=self.customer,
            contract_number=f'synthetic-bounded-{number}', title='Synthetic', amount=Decimal('1.01'),
            contract_date=timezone.localdate()) for number in range(30)])
        with self.assertNumQueries(2):
            first = self.client.get('/api/v1/companies/', {'page_size': 5, 'ordering': 'name'})
        with self.assertNumQueries(2):
            second = self.client.get('/api/v1/companies/', {'page': 2, 'page_size': 5, 'ordering': 'name'})
        self.assertEqual(len(first.json()['results']), 5)
        self.assertTrue(first.json()['next'])
        self.assertFalse({row['id'] for row in first.json()['results']} & {row['id'] for row in second.json()['results']})
        with self.assertNumQueries(2):
            response = self.client.get('/api/v1/contracts/', {'page_size': 100})
        self.assertEqual(len(response.json()['results']), 31)
        self.assertEqual(self.client.get('/api/v1/companies/', {'page': 999}).status_code, 404)

    def test_get_reads_do_not_write_parse_or_generate_and_domain_writes_are_disallowed(self):
        before = (Supplier.objects.count(), Contract.objects.count(), IngestionRun.objects.count(), SourceObservation.objects.count())
        with patch('apps.ingestion.services.run_pipeline', side_effect=AssertionError('GET started ingestion')), \
             patch('apps.ai.providers.generate', side_effect=AssertionError('GET started inference')), \
             patch('apps.graph.services.rebuild_clusters', side_effect=AssertionError('GET rebuilt graphs')):
            for path in ['/api/v1/companies/', f'/api/v1/companies/{self.company.pk}/', '/api/v1/people/',
                         '/api/v1/contracts/', f'/api/v1/contracts/{self.contract.pk}/',
                         '/api/v1/directorships/', '/api/v1/ownerships/']:
                self.assertEqual(self.client.get(path).status_code, 200)
        after = (Supplier.objects.count(), Contract.objects.count(), IngestionRun.objects.count(), SourceObservation.objects.count())
        self.assertEqual(before, after)
        for method in ('post', 'put', 'patch', 'delete'):
            self.assertEqual(getattr(self.client, method)(f'/api/v1/companies/{self.company.pk}/',
                data='{}', content_type='application/json').status_code, 405)
