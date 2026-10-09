from django.conf import settings
import json

from .dto import ResultStatus, SourceResult
from .errors import SourceError
from .normalizers import normalize_bin
from .parsers.adata import fetch_company_data
from .parsers.companies import SupplierRegistryParser
from .parsers.contracts import ContractRegistryParser
from .parsers.kgd import KgdParser, TAXPAYER_SOURCE, DEBT_SOURCE, LEGAL_TYPES, REGISTRATION_TYPES
from .transport import HttpTransport


class SourceProviders:
    """One connection pool and pacing policy per run, shared by all adapters."""
    COMPANY_SOURCES = ('goszakup_supplier', 'adata')
    VERSION = '2.3'

    def __init__(self, heartbeat=None, transport=None):
        self.transport = transport or HttpTransport(
            min_interval=settings.INGESTION_REQUEST_INTERVAL, heartbeat=heartbeat,
        )
        self.contracts = ContractRegistryParser(self.transport)
        self.companies = SupplierRegistryParser(self.transport)
        self._kgd = None

    def contract_page(self, number):
        return self.contracts.fetch_page(number, include_parties=False)

    def complete_contract(self, record):
        return self.contracts.complete_record(record)

    def company(self, source, bin_number):
        bin_number = normalize_bin(bin_number)
        if source not in self.COMPANY_SOURCES:
            raise ValueError('unknown_source')
        url = (f'{self.companies.BASE_URL}/ru/registry/supplierreg?filter[name]={bin_number}'
               if source == 'goszakup_supplier'
               else f'https://pk.adata.kz/counterparty/main/company/{bin_number}/basic-info')
        try:
            data = (self.companies.get_supplier_data(bin_number) if source == 'goszakup_supplier'
                    else fetch_company_data(bin_number, self.transport))
            if data is None:
                return SourceResult(source, f'company:{bin_number}', ResultStatus.NOT_FOUND, parser_version=self.VERSION, source_url=url)
            if normalize_bin(data.get('bin')) != bin_number:
                raise SourceError('enrichment_identity_mismatch')
            data = dict(data)
            raw = data.pop('_raw', dict(data))
            if source == 'goszakup_supplier' and data.get('supplier_id'):
                url = f'{self.companies.BASE_URL}/ru/registry/show_supplier/{data["supplier_id"]}'
            return SourceResult(source, f'company:{bin_number}', ResultStatus.SUCCESS,
                                data=data, raw=raw, parser_version=self.VERSION, source_url=url)
        except (SourceError, ValueError) as error:
            code = error.code if isinstance(error, SourceError) else 'source_fields_invalid'
            invalid = any(word in code for word in ('invalid', 'mismatch', 'missing', 'unconfirmed'))
            return SourceResult(source, f'company:{bin_number}', ResultStatus.INVALID if invalid else ResultStatus.UNAVAILABLE,
                                error_code=code, parser_version=self.VERSION, source_url=url)

    def close(self):
        self.transport.close()

    def kgd_client(self):
        if self._kgd is None:
            tokens = json.loads(settings.KGD_ACCOUNT_TOKENS_JSON or '{}')
            if not isinstance(tokens, dict) or len(tokens) > 1000:
                raise ValueError('kgd_account_configuration_invalid')
            for key in tokens:
                normalize_bin(key)
            self._kgd = KgdParser(self.transport, enabled=settings.ENABLE_KGD_CHECKS,
                                  portal_token=settings.KGD_PORTAL_TOKEN, account_tokens=tokens,
                                  taxpayer_type=settings.KGD_TAXPAYER_TYPE, timeout=settings.KGD_HTTP_TIMEOUT)
        return self._kgd

    @property
    def kgd_ready(self):
        try:
            return self.kgd_client().ready
        except (ValueError, TypeError):
            return False

    @property
    def kgd_taxpayer_type(self):
        return self.kgd_client().taxpayer_type

    def kgd(self, source, bin_number, *, legal_entity_confirmed=False, taxpayer_name=''):
        bin_number = normalize_bin(bin_number)
        if source not in KgdParser.SOURCE_URLS:
            raise ValueError('kgd_source_invalid')
        try:
            client = self.kgd_client()
        except (ValueError, TypeError):
            return SourceResult(source, f'company:{bin_number}', ResultStatus.NOT_CHECKED,
                                parser_version=KgdParser.VERSION, source_url=KgdParser.SOURCE_URLS[source],
                                error_code='kgd_configuration_invalid')
        return client.fetch(source, bin_number, legal_entity_confirmed=legal_entity_confirmed,
                            taxpayer_name=taxpayer_name)

    def kgd_cache_allowed(self, source, bin_number):
        """Cache cannot bypass the credentials required by the selected service."""
        try:
            client = self.kgd_client()
        except (ValueError, TypeError):
            return False
        if not client.ready:
            return False
        if source == TAXPAYER_SOURCE:
            return client.taxpayer_type in REGISTRATION_TYPES
        return (source == DEBT_SOURCE and client.taxpayer_type in LEGAL_TYPES
                and client._valid_token(client.account_tokens.get(bin_number)))
