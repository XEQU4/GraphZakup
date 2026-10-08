"""Official KGD JSON adapters. No ORM, browser scraping, or inferred owner debt."""

from datetime import datetime
from decimal import Decimal

from ..dto import ResultStatus, SourceResult
from ..errors import SourceError
from ..normalizers import normalize_amount, normalize_bin, normalize_date

TAXPAYER_SOURCE = 'kgd_taxpayer'
DEBT_SOURCE = 'kgd_tax_debt'
LEGAL_TYPES = {'UL', 'UL_NR'}
TAXPAYER_FIELDS = frozenset({
    'bin', 'kgd_taxpayer_type', 'kgd_taxpayer_name', 'kgd_registration_begin',
    'kgd_registration_end', 'kgd_end_reason',
})
AMOUNT_FIELDS = {
    'totalArrear': 'kgd_total_arrears',
    'totalTaxArrear': 'kgd_tax_arrears',
    'pensionContributionArrear': 'kgd_pension_arrears',
    'socialContributionArrear': 'kgd_social_arrears',
    'socialHealthInsuranceArrear': 'kgd_health_insurance_arrears',
}
DEBT_FIELDS = frozenset({'bin', 'kgd_reporting_dates', *AMOUNT_FIELDS.values()})
FIELDS_BY_SOURCE = {TAXPAYER_SOURCE: TAXPAYER_FIELDS, DEBT_SOURCE: DEBT_FIELDS}


def _text(value, limit):
    if value is None:
        return ''
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError('kgd_field_invalid')
    return value.strip()


def _reporting_date(value):
    """KGD also encodes a reporting calendar date as a complete local timestamp."""
    if isinstance(value, str) and 'T' in value:
        # Validate the full value; slicing off time would hide malformed responses.
        return datetime.strptime(value.strip(), '%Y-%m-%dT%H:%M:%S').date()
    return normalize_date(value)


def validate_facts(source, values, bin_number):
    """Revalidate facts at the service boundary, including injected providers/cache."""
    if not isinstance(values, dict) or normalize_bin(values.get('bin')) != bin_number:
        raise ValueError('kgd_identity_mismatch')
    data = {'bin': bin_number}
    if source == TAXPAYER_SOURCE:
        kind = values.get('kgd_taxpayer_type')
        if kind not in LEGAL_TYPES:
            raise ValueError('kgd_subject_not_legal_entity')
        data.update(kgd_taxpayer_type=kind,
                    kgd_taxpayer_name=_text(values.get('kgd_taxpayer_name'), 500),
                    kgd_registration_begin=normalize_date(values.get('kgd_registration_begin')),
                    kgd_registration_end=normalize_date(values.get('kgd_registration_end')),
                    kgd_end_reason=_text(values.get('kgd_end_reason'), 500))
        if (data['kgd_registration_begin'] and data['kgd_registration_end']
                and data['kgd_registration_end'] < data['kgd_registration_begin']):
            raise ValueError('kgd_registration_interval_invalid')
    elif source == DEBT_SOURCE:
        for field in AMOUNT_FIELDS.values():
            data[field] = normalize_amount(values.get(field))
        if data['kgd_total_arrears'] != sum((data[field] for field in AMOUNT_FIELDS.values()
                                           if field != 'kgd_total_arrears'), Decimal('0')):
            raise ValueError('kgd_arrears_totals_inconsistent')
        dates = values.get('kgd_reporting_dates', [])
        if not isinstance(dates, list) or len(dates) > 2000:
            raise ValueError('kgd_reporting_dates_invalid')
        normalized_dates = [_reporting_date(value) for value in dates]
        if any(value is None for value in normalized_dates):
            raise ValueError('kgd_reporting_dates_invalid')
        data['kgd_reporting_dates'] = sorted(set(normalized_dates))
    else:
        raise ValueError('kgd_source_invalid')
    return data


def parse_taxpayer(payload, bin_number):
    if isinstance(payload, dict) and 'errorResponse' in payload:
        # The official service can answer HTTP 200 with a failed lookup plus
        # unrelated payment/detail envelopes. Those details do not verify a
        # legal-entity registration and must never be extracted as a success.
        failure = payload['errorResponse']
        if not isinstance(failure, dict):
            raise SourceError('kgd_taxpayer_response_invalid')
        try:
            matches = normalize_bin(failure.get('code')) == bin_number
        except ValueError:
            matches = False
        if not matches:
            raise SourceError('kgd_identity_mismatch')
        if failure.get('taxpayerType') not in LEGAL_TYPES:
            raise SourceError('kgd_subject_not_legal_entity')
        message = failure.get('errorMessage')
        if (failure.get('messageResult') != 'FAILED' or not isinstance(message, str)
                or not message.strip() or len(message) > 4096):
            raise SourceError('kgd_taxpayer_response_invalid')
        raise SourceError('kgd_taxpayer_result_unconfirmed')
    if not isinstance(payload, dict) or not isinstance(payload.get('taxpayerPortalSearchResponses'), list):
        raise ValueError('kgd_taxpayer_response_invalid')
    entries = payload['taxpayerPortalSearchResponses']
    if len(entries) > 100:
        raise ValueError('kgd_taxpayer_response_invalid')
    if not entries:
        return None, {}
    matching = []
    for item in entries:
        if not isinstance(item, dict) or item.get('messageResult') != 'SUCCESS' or item.get('errorMessage'):
            raise ValueError('kgd_taxpayer_result_unconfirmed')
        if normalize_bin(item.get('code')) == bin_number:
            matching.append(item)
    if len(matching) != 1:
        raise ValueError('kgd_identity_mismatch_or_ambiguous')
    row = matching[0]
    reason = row.get('endReason')
    if reason is not None and not isinstance(reason, dict):
        raise ValueError('kgd_taxpayer_response_invalid')
    raw = {
        'bin': row.get('code'), 'kgd_taxpayer_type': row.get('taxpayerType'),
        'kgd_taxpayer_name': row.get('name'), 'kgd_registration_begin': row.get('beginDate'),
        'kgd_registration_end': row.get('endDate'),
        'kgd_end_reason': (reason.get('en') or reason.get('code')) if reason else row.get('endReasonCode'),
    }
    return validate_facts(TAXPAYER_SOURCE, raw, bin_number), raw


def parse_tax_debt(payload, bin_number):
    if not isinstance(payload, dict) or normalize_bin(payload.get('iinBin')) != bin_number:
        raise ValueError('kgd_identity_mismatch')
    organs = payload.get('taxOrgInfos')
    if not isinstance(organs, list) or len(organs) > 2000:
        raise ValueError('kgd_tax_debt_response_invalid')
    dates = []
    for organ in organs:
        if not isinstance(organ, dict):
            raise ValueError('kgd_tax_debt_response_invalid')
        value = organ.get('reportAcrualDate')
        if value is not None and value != '':
            dates.append(value)
    raw = {'bin': payload.get('iinBin'), 'kgd_reporting_dates': dates}
    raw.update({field: payload.get(key) for key, field in AMOUNT_FIELDS.items()})
    return validate_facts(DEBT_SOURCE, raw, bin_number), raw


class KgdParser:
    VERSION = '3.2'
    API_URLS = {
        TAXPAYER_SOURCE: 'https://portal.kgd.gov.kz/services/isnaportalsync/public/taxpayer-data',
        DEBT_SOURCE: 'https://portal.kgd.gov.kz/services/isnaportalsync/public/tax-debt-info',
    }
    SOURCE_URLS = {
        TAXPAYER_SOURCE: 'https://portal.kgd.gov.kz/en/pages/api-services/find-taxpayer',
        DEBT_SOURCE: 'https://portal.kgd.gov.kz/en/pages/api-services/info-absence-tax-debt',
    }

    def __init__(self, transport, *, enabled=False, portal_token='', account_tokens=None,
                 taxpayer_type='UL', timeout=30):
        self.transport = transport
        self.enabled = enabled
        self.portal_token = portal_token
        self.account_tokens = account_tokens or {}
        self.taxpayer_type = taxpayer_type
        self.timeout = timeout

    @staticmethod
    def _valid_token(value):
        return isinstance(value, str) and 0 < len(value) <= 4096 and all(33 <= ord(char) <= 126 for char in value)

    @property
    def ready(self):
        return self.enabled and self._valid_token(self.portal_token)

    def fetch(self, source, bin_number, *, legal_entity_confirmed=False):
        bin_number = normalize_bin(bin_number)
        if source not in self.SOURCE_URLS:
            raise ValueError('kgd_source_invalid')

        def result(status, *, data=None, raw=None, code=''):
            return SourceResult(source, f'company:{bin_number}', status, data=data or {}, raw=raw or {},
                                parser_version=self.VERSION, source_url=self.SOURCE_URLS[source], error_code=code)

        if not self.enabled:
            return result(ResultStatus.NOT_CHECKED, code='kgd_disabled')
        if not self.portal_token:
            return result(ResultStatus.NOT_CHECKED, code='kgd_portal_token_missing')
        if not self._valid_token(self.portal_token):
            return result(ResultStatus.NOT_CHECKED, code='kgd_portal_token_invalid')
        params = {'taxpayerCode': bin_number}
        if source == TAXPAYER_SOURCE:
            if self.taxpayer_type not in LEGAL_TYPES:
                return result(ResultStatus.NOT_CHECKED, code='kgd_taxpayer_type_invalid')
            params.update(taxpayerType=self.taxpayer_type, print='false')
        else:
            if not legal_entity_confirmed:
                return result(ResultStatus.NOT_CHECKED, code='kgd_legal_entity_unconfirmed')
            account_token = self.account_tokens.get(bin_number)
            if not account_token:
                return result(ResultStatus.NOT_CHECKED, code='kgd_account_token_missing')
            if not self._valid_token(account_token):
                return result(ResultStatus.NOT_CHECKED, code='kgd_account_token_invalid')
            params['personalAccountToken'] = account_token
        try:
            payload = self.transport.get_json(self.API_URLS[source], params=params, timeout=self.timeout,
                                              headers={'X-Portal-Token': self.portal_token, 'Accept': 'application/json'})
            data, raw = (parse_taxpayer(payload, bin_number) if source == TAXPAYER_SOURCE
                         else parse_tax_debt(payload, bin_number))
            return result(ResultStatus.SUCCESS if data is not None else ResultStatus.NOT_FOUND, data=data, raw=raw)
        except SourceError as error:
            if error.code in ('source_http_401', 'source_http_403', 'source_http_404'):
                return result(ResultStatus.UNAVAILABLE, code='kgd_access_denied')
            invalid = error.code in ('source_http_400', 'source_json_invalid', 'source_json_content_type_invalid',
                                      'source_response_too_large', 'kgd_taxpayer_response_invalid',
                                      'kgd_identity_mismatch', 'kgd_subject_not_legal_entity')
            return result(ResultStatus.INVALID if invalid else ResultStatus.UNAVAILABLE, code=error.code)
        except (ValueError, TypeError, KeyError):
            return result(ResultStatus.INVALID, code='kgd_response_invalid')
