from datetime import date
from decimal import Decimal
from apps.ingestion.dto import SourceResult, ResultStatus
from apps.ingestion.parsers.contracts import ContractPage


def contract_record(identifier, supplier='000000000001', customer='000000000002'):
    return {'contract_number': f'demo-{identifier}', 'contract_gos_id': identifier,
            'supplier_bin': supplier, 'customer_bin': customer,
            'supplier_name': 'Synthetic supplier', 'customer_name': 'Synthetic customer',
            'amount': Decimal('100.01'), 'sign_date': date(2020, 1, 24), 'subject': 'Demo'}


class FakeProviders:
    VERSION = '2.0'
    COMPANY_SOURCES = ('goszakup_supplier', 'adata')

    def __init__(self, pages=(), results=None):
        self.pages = {page.number: page for page in pages}
        self.results = results or {}
        self.page_calls, self.company_calls = [], []

    def contract_page(self, number):
        self.page_calls.append(number)
        page = self.pages.get(number, ContractPage(number, (), eof=True))
        if isinstance(page, Exception):
            raise page
        return page

    def company(self, source, bin_value):
        self.company_calls.append((source, bin_value))
        result = self.results.get((source, bin_value))
        if isinstance(result, Exception):
            raise result
        if isinstance(result, SourceResult):
            return result
        return SourceResult(source, f'company:{bin_value}', ResultStatus.SUCCESS if result else ResultStatus.NOT_FOUND,
                            data={'bin': bin_value, **result} if result else {}, raw=result or {})


def verified_role(supplier, director, **dates):
    from django.utils import timezone
    from apps.ingestion.models import IngestionRun, SourceObservation
    from apps.owners.models import Directorship, PersonIdentity
    run = IngestionRun.objects.create(mode='enrich', status='succeeded')
    person, _ = PersonIdentity.objects.get_or_create(scope_key=f'fixture:{director.pk}',
        defaults={'full_name': director.full_name, 'director': director, 'iin': f'{director.pk:012}', 'is_verified': True})
    obs = SourceObservation.objects.create(run=run, source='fixture', subject_key=f'company:{supplier.bin}',
        supplier=supplier, status='success', fingerprint=f'{supplier.pk:064}', observed_at=timezone.now(),
        normalized_values={'director_name': director.full_name, 'director_iin': person.iin, 'director_iin_verified': True})
    return Directorship.objects.create(supplier=supplier, director=director, person_identity=person,
        source='fixture', source_observation=obs, identity_status='verified', **dates)
