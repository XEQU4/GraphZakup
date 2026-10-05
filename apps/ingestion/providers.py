from django.conf import settings

from .dto import ResultStatus, SourceResult
from .errors import SourceError
from .normalizers import normalize_bin
from .parsers.adata import fetch_company_data
from .parsers.companies import SupplierRegistryParser
from .parsers.contracts import ContractRegistryParser
from .transport import HttpTransport


class SourceProviders:
    """One connection pool and pacing policy per run, shared by all adapters."""
    COMPANY_SOURCES = ('goszakup_supplier', 'adata')
    VERSION = '2.0'

    def __init__(self, heartbeat=None, transport=None):
        self.transport = transport or HttpTransport(
            min_interval=settings.INGESTION_REQUEST_INTERVAL, heartbeat=heartbeat,
        )
        self.contracts = ContractRegistryParser(self.transport)
        self.companies = SupplierRegistryParser(self.transport)

    def contract_page(self, number):
        return self.contracts.fetch_page(number)

    def company(self, source, bin_number):
        bin_number = normalize_bin(bin_number)
        if source not in self.COMPANY_SOURCES:
            raise ValueError('unknown_source')
        url = (f'https://goszakup.gov.kz/ru/registry/supplierreg?filter[name]={bin_number}'
               if source == 'goszakup_supplier'
               else f'https://pk.adata.kz/counterparty/main/company/{bin_number}/basic-info')
        try:
            data = (self.companies.get_supplier_data(bin_number) if source == 'goszakup_supplier'
                    else fetch_company_data(bin_number, self.transport))
            if data is None:
                return SourceResult(source, f'company:{bin_number}', ResultStatus.NOT_FOUND, source_url=url)
            if normalize_bin(data.get('bin')) != bin_number:
                raise SourceError('enrichment_identity_mismatch')
            data = dict(data)
            raw = data.pop('_raw', dict(data))
            if source == 'goszakup_supplier' and data.get('supplier_id'):
                url = f'https://goszakup.gov.kz/ru/registry/show_supplier/{data["supplier_id"]}'
            return SourceResult(source, f'company:{bin_number}', ResultStatus.SUCCESS,
                                data=data, raw=raw, parser_version=self.VERSION, source_url=url)
        except (SourceError, ValueError) as error:
            code = error.code if isinstance(error, SourceError) else 'source_fields_invalid'
            invalid = any(word in code for word in ('invalid', 'mismatch', 'missing', 'unconfirmed'))
            return SourceResult(source, f'company:{bin_number}', ResultStatus.INVALID if invalid else ResultStatus.UNAVAILABLE,
                                error_code=code, parser_version=self.VERSION, source_url=url)

    def close(self):
        self.transport.close()
