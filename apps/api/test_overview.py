from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.owners.models import PersonIdentity
from apps.ingestion.models import SourceObservation, IngestionRun

class SavedOverviewTests(TestCase):
    def test_empty_saved_workspace_has_no_invented_coverage(self):
        response=self.client.get('/api/v1/overview/')
        self.assertEqual(response.status_code,200)
        body=response.json()
        self.assertEqual(body['total_contract_amount'],'0.00')
        self.assertEqual(body['companies_with_kgd_records'],0)
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
