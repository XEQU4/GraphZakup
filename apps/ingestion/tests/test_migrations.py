from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from apps.ingestion.leases import RunLease, IngestionBusy


class LegacyMigrationTests(TransactionTestCase):
    def test_old_values_are_preserved_and_name_only_people_are_isolated(self):
        old_targets = [('companies', '0005_supplier_company_size_supplier_economic_sector_and_more'),
                       ('contracts', '0005_fix_unique_keys'), ('owners', '0002_alter_director_iin_alter_owner_iin'),
                       ('ingestion', None)]
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        executor.migrate(old_targets)
        old = executor.loader.project_state([target for target in old_targets if target[1]]).apps
        Company = old.get_model('companies', 'Supplier')
        Director = old.get_model('owners', 'Director')
        Role = old.get_model('owners', 'Directorship')
        Contract = old.get_model('contracts', 'Contract')
        try:
            first = Company.objects.create(bin='000000000001', name='First', director_name='Namesake')
            second = Company.objects.create(bin='000000000002', name='Second', director_name='Namesake')
            person = Director.objects.create(full_name='Namesake')
            original_roles = [Role.objects.create(supplier=company, director=person) for company in (first, second)]
            contract = Contract.objects.create(supplier=first, contract_number='legacy', title='Contract', amount='123.45',
                contract_date='2020-01-01', customer_bin='000000000003', customer_name='Customer')
            before_roles = [(role.pk, role.supplier_id, role.director_id, role.start_date, role.end_date) for role in original_roles]
            executor = MigrationExecutor(connection)
            executor.migrate(leaves)
            from apps.companies.models import Supplier
            from apps.contracts.models import Contract as NewContract
            from apps.owners.models import Directorship, PersonIdentity
            from apps.ingestion.models import SourceObservation, SelectedFact, IdentityCandidate
            from apps.graph.services import rebuild_clusters
            self.assertEqual(list(Directorship.objects.filter(pk__in=[role.pk for role in original_roles]).order_by('pk').values_list(
                'pk', 'supplier_id', 'director_id', 'start_date', 'end_date')), before_roles)
            self.assertEqual(Directorship.objects.filter(is_current=False).count(), 2)
            active = list(Directorship.objects.filter(is_current=True).order_by('pk'))
            self.assertEqual(len(active), 2)
            self.assertNotEqual(active[0].person_identity_id, active[1].person_identity_id)
            self.assertEqual(active[0].identity_status, 'unverified')
            self.assertFalse(PersonIdentity.objects.filter(is_verified=True).exists())
            self.assertEqual(IdentityCandidate.objects.get().status, 'pending')
            self.assertEqual(rebuild_clusters()['groups'], 0)
            new_contract = NewContract.objects.get(pk=contract.pk)
            self.assertEqual(str(new_contract.amount), '123.45')
            self.assertEqual(new_contract.customer.bin, '000000000003')
            self.assertFalse(new_contract.customer.is_supplier)
            self.assertEqual(Supplier.objects.get(pk=first.pk).name, first.name)
            self.assertTrue(SourceObservation.objects.filter(contract=new_contract, source='legacy', status='not_checked').exists())
            self.assertTrue(SelectedFact.objects.filter(supplier=new_contract.customer, field='name').exists())
        finally:
            MigrationExecutor(connection).migrate(leaves)


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row-lock concurrency test')
class LeaseConcurrencyTests(TransactionTestCase):
    def test_two_workers_acquiring_initial_lease_have_one_winner(self):
        barrier = Barrier(2)
        def acquire():
            connections.close_all()
            try:
                barrier.wait(timeout=10)
                try:
                    lease = RunLease.acquire()
                except IngestionBusy:
                    return 'busy'
                return str(lease.token)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: acquire(), range(2)))
        self.assertEqual(results.count('busy'), 1)
        self.assertEqual(len(set(results)), 2)
