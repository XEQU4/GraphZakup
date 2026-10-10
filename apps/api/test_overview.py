from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.owners.models import Director, Directorship, Owner, Ownership, PersonIdentity
from apps.ingestion.models import SourceObservation, IngestionRun, SelectedFact

class SavedOverviewTests(TestCase):
    def test_empty_saved_workspace_has_no_invented_coverage(self):
        response=self.client.get('/api/v1/overview/')
        self.assertEqual(response.status_code,200)
        body=response.json()
        self.assertEqual(body['total_contract_amount'],'0.00')
        self.assertEqual(body['companies_with_kgd_records'],0)
        self.assertEqual(body['checked_company_count'],0)
        self.assertEqual(body['current_verified_people_count'],0)
        self.assertIsNone(body['contract_date_to'])
    def test_aggregates_saved_contracts_roles_and_unverified_people(self):
        supplier=Supplier.objects.create(bin='000000000101',name='Synthetic supplier')
        customer=Supplier.objects.create(bin='000000000102',name='Synthetic customer',is_supplier=False,is_customer=True)
        for number,amount in enumerate(['100.01','25.10']):
            Contract.objects.create(supplier=supplier,customer=customer,contract_number=str(number),title='Synthetic record',amount=Decimal(amount),contract_date=timezone.localdate())
        PersonIdentity.objects.create(full_name='Synthetic unresolved person',scope_key='synthetic-person')
        before=Contract.objects.count()
        response=self.client.get('/api/v1/overview/')
        self.assertEqual(response.status_code,200)
        values=response.json()
        self.assertEqual(values['company_count'],2)
        self.assertEqual(values['contract_count'],2)
        self.assertEqual(values['total_contract_amount'],'125.11')
        self.assertEqual(values['verified_people_count'],0)
        self.assertEqual(values['checked_company_count'],0)
        self.assertEqual(values['current_verified_people_count'],0)
        self.assertEqual(Contract.objects.count(),before)
        self.assertNotIn('Synthetic unresolved person',response.content.decode())
    def test_overview_rejects_unrecognised_and_duplicate_query_parameters(self):
        for query in ['?refresh=true','?page=1','?search=x&search=y']:
            response=self.client.get('/api/v1/overview/'+query)
            self.assertEqual(response.status_code,400)
            self.assertEqual(response.json()['error']['code'],'validation_error')

    def test_legacy_coverage_uses_source_not_a_specific_backfill_version(self):
        supplier=Supplier.objects.create(bin='000000000103',name='Synthetic historical company')
        run=IngestionRun.objects.create(mode='initial')
        SourceObservation.objects.create(run=run,subject_key='synthetic:historical',fingerprint='synthetic',supplier=supplier,source='legacy',status='not_checked',parser_version='legacy-backfill-1',observed_at=timezone.now())
        body=self.client.get('/api/v1/overview/').json()
        self.assertEqual(body['legacy_observation_count'],1)
        self.assertEqual(body['nonlegacy_success_count'],0)

    def test_company_card_matches_checked_directory_and_preserves_all_record_total(self):
        checked = Supplier.objects.create(bin='000000000111', name='Synthetic checked company')
        Supplier.objects.create(bin='000000000112', name='Synthetic pending company')
        run = IngestionRun.objects.create(mode='update')
        observation = SourceObservation.objects.create(
            run=run, supplier=checked, subject_key=f'company:{checked.bin}',
            source='adata', status='success', fingerprint='synthetic-profile',
            parser_version='2.4', observed_at=timezone.now(),
            normalized_values={'bin': checked.bin, 'name': checked.name},
        )
        SelectedFact.objects.create(supplier=checked, field='name', observation=observation)

        def compare(expected):
            overview = self.client.get('/api/v1/overview/').json()
            directory = self.client.get('/api/v1/companies/', {'profile_status': 'checked'}).json()
            self.assertEqual(overview['checked_company_count'], expected)
            self.assertEqual(overview['checked_company_count'], directory['count'])
            self.assertEqual(overview['company_count'], 2)
            self.assertEqual(self.client.get('/api/v1/companies/').json()['count'], 2)

        compare(1)
        SourceObservation.objects.filter(pk=observation.pk).update(subject_key='contract:111')
        compare(0)
        SourceObservation.objects.filter(pk=observation.pk).update(subject_key=f'company:{checked.bin}')
        compare(1)

    def test_people_card_matches_default_directory_without_history_or_role_duplicates(self):
        company = Supplier.objects.create(bin='000000000121', name='Synthetic first company')
        other_company = Supplier.objects.create(bin='000000000122', name='Synthetic second company')

        def identity(key, *, verified=False):
            return PersonIdentity.objects.create(
                scope_key=f'synthetic:{key}', full_name='Synthetic shared name',
                iin=f'{key:012}' if verified else '', is_verified=verified,
            )

        current = identity(1, verified=True)
        director = Director.objects.create(full_name=current.full_name)
        for supplier in (company, other_company):
            Directorship.objects.create(supplier=supplier, director=director, person_identity=current)
        Ownership.objects.create(supplier=company, owner=Owner.objects.create(full_name=current.full_name),
            person_identity=current)
        owner_identity = identity(2, verified=True)
        Ownership.objects.create(supplier=other_company,
            owner=Owner.objects.create(full_name=owner_identity.full_name), person_identity=owner_identity)
        historical = identity(3, verified=True)
        Directorship.objects.create(supplier=company, director=Director.objects.create(full_name=historical.full_name),
            person_identity=historical, is_current=False)
        unverified = identity(4)
        Directorship.objects.create(supplier=company, director=Director.objects.create(full_name=unverified.full_name),
            person_identity=unverified)
        identity(5, verified=True)  # A saved verified identity without any role.
        identity(6)  # Earlier unresolved source record of the same name.

        def compare(expected):
            overview = self.client.get('/api/v1/overview/').json()
            directory = self.client.get('/api/v1/people/', {
                'is_verified': 'true', 'has_current_role': 'true', 'page_size': 1,
            }).json()
            self.assertEqual(overview['current_verified_people_count'], expected)
            self.assertEqual(overview['current_verified_people_count'], directory['count'])
            self.assertEqual(overview['people_count'], 6)
            self.assertEqual(overview['verified_people_count'], 4)
            self.assertEqual(self.client.get('/api/v1/people/').json()['count'], 6)

        compare(2)
        Directorship.objects.filter(person_identity=historical).update(is_current=True)
        compare(3)
