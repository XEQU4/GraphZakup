"""Offline contract tests; every identifier, name and credential is synthetic."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from curl_cffi.requests import RequestsError
from django.test import SimpleTestCase, override_settings

from apps.ingestion.dto import ResultStatus
from apps.ingestion.errors import SourceError
from apps.ingestion.parsers.kgd import (
    AMOUNT_FIELDS, DEBT_SOURCE, KgdParser, TAXPAYER_SOURCE, parse_tax_debt, parse_taxpayer,
)
from apps.ingestion.providers import SourceProviders
from apps.ingestion.transport import HttpTransport

BIN = '000000000001'
FIXTURES = Path(__file__).resolve().parents[3] / 'tests' / 'fixtures'


def fixture(name):
    return json.loads((FIXTURES / f'kgd_{name}.json').read_text(encoding='utf-8'))


class KgdParserTests(SimpleTestCase):
    def setUp(self):
        self.transport = Mock()
        self.parser = KgdParser(self.transport, enabled=True, portal_token='synthetic-portal-token',
                                account_tokens={BIN: 'synthetic-account-token'})

    def test_exact_bin_and_legal_entity_are_required(self):
        data, raw = parse_taxpayer(fixture('taxpayer'), BIN)
        self.assertEqual(data['bin'], BIN)
        self.assertEqual(data['kgd_registration_begin'], date(2020, 1, 1))
        self.assertEqual(raw['kgd_registration_begin'], '2020-01-01')
        for value in ('000000000002', 1):
            payload = fixture('taxpayer')
            payload['taxpayerPortalSearchResponses'][0]['code'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_taxpayer(payload, BIN)
        for kind in ('FL', 'IP', None):
            payload = fixture('taxpayer')
            payload['taxpayerPortalSearchResponses'][0]['taxpayerType'] = kind
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                parse_taxpayer(payload, BIN)

    def test_empty_taxpayer_list_is_distinct_from_malformed_and_error_responses(self):
        self.transport.get_json.return_value = {'taxpayerPortalSearchResponses': []}
        self.assertEqual(self.parser.fetch(TAXPAYER_SOURCE, BIN).status, ResultStatus.NOT_FOUND)
        for payload in ({}, [], {'taxpayerPortalSearchResponses': None},
                        {'taxpayerPortalSearchResponses': [{'messageResult': 'ERROR'}]}):
            self.transport.get_json.return_value = payload
            with self.subTest(payload=payload):
                result = self.parser.fetch(TAXPAYER_SOURCE, BIN)
                self.assertEqual(result.status, ResultStatus.INVALID)
                self.assertEqual(result.data, {})

    def test_duplicate_matches_and_invalid_registration_interval_are_rejected(self):
        payload = fixture('taxpayer')
        payload['taxpayerPortalSearchResponses'] *= 2
        with self.assertRaises(ValueError):
            parse_taxpayer(payload, BIN)
        payload = fixture('taxpayer')
        payload['taxpayerPortalSearchResponses'][0]['endDate'] = '2019-01-01'
        with self.assertRaises(ValueError):
            parse_taxpayer(payload, BIN)

    def test_registration_request_and_provenance_exclude_credentials(self):
        self.transport.get_json.return_value = fixture('taxpayer')
        result = self.parser.fetch(TAXPAYER_SOURCE, BIN)
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        call = self.transport.get_json.call_args
        self.assertEqual(call.kwargs['params'], {'taxpayerCode': BIN, 'taxpayerType': 'UL', 'print': 'false'})
        self.assertEqual(call.kwargs['headers']['X-Portal-Token'], 'synthetic-portal-token')
        self.assertEqual(call.kwargs['timeout'], 30)
        self.assertNotIn('token', result.source_url.lower())
        self.assertNotIn('synthetic-portal-token', repr(result))

    def test_arrears_require_legal_confirmation_and_company_specific_account_token(self):
        result = self.parser.fetch(DEBT_SOURCE, BIN)
        self.assertEqual((result.status, result.error_code), (ResultStatus.NOT_CHECKED, 'kgd_legal_entity_unconfirmed'))
        self.transport.get_json.assert_not_called()
        result = self.parser.fetch(DEBT_SOURCE, '000000000002', legal_entity_confirmed=True)
        self.assertEqual(result.error_code, 'kgd_account_token_missing')
        self.transport.get_json.assert_not_called()
        self.transport.get_json.return_value = fixture('tax_debt')
        result = self.parser.fetch(DEBT_SOURCE, BIN, legal_entity_confirmed=True)
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(self.transport.get_json.call_args.kwargs['params']['personalAccountToken'], 'synthetic-account-token')
        self.assertNotIn('synthetic-account-token', repr(result))

    def test_aggregate_arrears_are_exact_and_reporting_dates_remain_source_dates(self):
        payload = fixture('tax_debt')
        payload['taxOrgInfos'] += [{'reportAcrualDate': '2026-09-30'}, {'reportAcrualDate': '2026-10-01'}]
        data, _ = parse_tax_debt(payload, BIN)
        self.assertEqual(data['kgd_total_arrears'], Decimal('123456789012345.67'))
        self.assertEqual(data['kgd_reporting_dates'], [date(2026, 9, 30), date(2026, 10, 1)])
        payload['taxOrgInfos'] = []
        self.assertEqual(parse_tax_debt(payload, BIN)[0]['kgd_reporting_dates'], [])

    def test_only_complete_valid_zero_response_confirms_zero_arrears(self):
        payload = fixture('tax_debt')
        for field in AMOUNT_FIELDS:
            payload[field] = '0.00'
        self.assertEqual(parse_tax_debt(payload, BIN)[0]['kgd_total_arrears'], Decimal('0.00'))
        for invalid in (None, '', '-1', 'NaN', True, 0.1, '0.001'):
            bad = deepcopy(payload)
            bad['totalArrear'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_tax_debt(bad, BIN)
        del payload['totalTaxArrear']
        with self.assertRaises(ValueError):
            parse_tax_debt(payload, BIN)

    def test_complete_reporting_timestamps_preserve_raw_dates_and_normalize_calendar_dates(self):
        payload = fixture('tax_debt')
        timestamps = ['2022-12-05T00:00:00', '2022-12-05T12:34:56', '2022-12-06']
        payload['taxOrgInfos'] = [{'reportAcrualDate': value} for value in timestamps]
        self.transport.get_json.return_value = payload
        result = self.parser.fetch(DEBT_SOURCE, BIN, legal_entity_confirmed=True)
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.data['kgd_reporting_dates'], [date(2022, 12, 5), date(2022, 12, 6)])
        self.assertEqual(result.raw['kgd_reporting_dates'], timestamps)

    def test_malformed_reporting_timestamps_are_rejected_instead_of_truncated(self):
        for value in ('2022-02-30T00:00:00', '2022-12-05T25:00:00',
                      '2022-12-05T00:00:00unexpected', '2022-12-05Tinvalid'):
            payload = fixture('tax_debt')
            payload['taxOrgInfos'] = [{'reportAcrualDate': value}]
            self.transport.get_json.return_value = payload
            with self.subTest(value=value):
                result = self.parser.fetch(DEBT_SOURCE, BIN, legal_entity_confirmed=True)
                self.assertEqual(result.status, ResultStatus.INVALID)
                self.assertEqual(result.data, {})

    def test_debt_subject_shape_and_inconsistent_totals_are_rejected(self):
        for change in ({'iinBin': '000000000002'}, {'totalArrear': '0.00'},
                       {'taxOrgInfos': None}, {'taxOrgInfos': [{'reportAcrualDate': 'invalid'}]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                parse_tax_debt({**fixture('tax_debt'), **change}, BIN)

    def test_private_nested_fields_are_never_extracted(self):
        payload = fixture('tax_debt')
        payload['taxOrgInfos'][0]['taxpayerInfo'] = {'name': 'synthetic-private-name', 'iin': '000000000010'}
        payload['personalAccountToken'] = 'synthetic-private-token'
        data, raw = parse_tax_debt(payload, BIN)
        self.assertNotIn('synthetic-private', repr((data, raw)))

    def test_http_access_denied_never_means_not_found_or_zero(self):
        for code, status in (('source_http_401', ResultStatus.UNAVAILABLE),
                             ('source_http_403', ResultStatus.UNAVAILABLE),
                             ('source_http_404', ResultStatus.UNAVAILABLE),
                             ('source_http_503', ResultStatus.UNAVAILABLE),
                             ('source_http_400', ResultStatus.INVALID),
                             ('source_json_invalid', ResultStatus.INVALID)):
            self.transport.get_json.side_effect = SourceError(code)
            with self.subTest(code=code):
                result = self.parser.fetch(DEBT_SOURCE, BIN, legal_entity_confirmed=True)
                self.assertEqual(result.status, status)
                self.assertEqual(result.data, {})

    def test_disabled_missing_and_invalid_tokens_make_no_requests(self):
        for options, code in (({}, 'kgd_disabled'), ({'enabled': True}, 'kgd_portal_token_missing'),
                              ({'enabled': True, 'portal_token': 'bad\nheader'}, 'kgd_portal_token_invalid')):
            result = KgdParser(self.transport, **options).fetch(TAXPAYER_SOURCE, BIN)
            self.assertEqual((result.status, result.error_code), (ResultStatus.NOT_CHECKED, code))
        self.transport.get_json.assert_not_called()

    @override_settings(ENABLE_KGD_CHECKS=True, KGD_PORTAL_TOKEN='synthetic-token', KGD_ACCOUNT_TOKENS_JSON='invalid-json')
    def test_invalid_secret_configuration_is_a_safe_not_checked_result(self):
        provider = SourceProviders(transport=self.transport)
        self.assertFalse(provider.kgd_ready)
        self.assertEqual(provider.kgd(TAXPAYER_SOURCE, BIN).error_code, 'kgd_configuration_invalid')
        self.transport.get_json.assert_not_called()


class KgdJsonTransportTests(SimpleTestCase):
    def transport(self, responses, **options):
        self.session = Mock()
        self.session.get.side_effect = responses
        return HttpTransport(session=self.session, min_interval=0, sleeper=Mock(), **options)

    @staticmethod
    def response(body='{}', status=200, content_type='application/json', **headers):
        return SimpleNamespace(text=body, status_code=status, headers={'Content-Type': content_type, **headers})

    def test_json_numbers_are_decimal_and_authenticated_responses_are_not_http_cached(self):
        body = '{"totalArrear":123456789012345.67}'
        client = self.transport([self.response(body)] * 2)
        for _ in range(2):
            data = client.get_json(KgdParser.API_URLS[DEBT_SOURCE], params={'personalAccountToken': 'synthetic-token'},
                                   headers={'X-Portal-Token': 'synthetic-token'})
            self.assertEqual(data['totalArrear'], Decimal('123456789012345.67'))
        self.assertEqual(self.session.get.call_count, 2)
        self.assertEqual(len(client._cache), 0)
        self.assertFalse(self.session.get.call_args.kwargs['allow_redirects'])

    def test_wrong_content_type_duplicate_keys_and_nonfinite_numbers_are_invalid(self):
        for response in (self.response('{}', content_type='text/html'), self.response('{"a":1,"a":2}'),
                         self.response('{"a":NaN}'), self.response('not-json')):
            with self.subTest(response=response), self.assertRaises(SourceError):
                self.transport([response]).get_json(KgdParser.API_URLS[TAXPAYER_SOURCE])

    def test_access_denied_redirects_and_oversized_bodies_are_rejected(self):
        for response in (self.response(status=404), self.response(status=302), self.response('x' * (4 * 1024 * 1024 + 1))):
            with self.subTest(status=response.status_code), self.assertRaises(SourceError):
                self.transport([response], retries=0).get_json(KgdParser.API_URLS[TAXPAYER_SOURCE])

    def test_retries_have_heartbeat_and_safe_errors(self):
        heartbeat = Mock()
        client = self.transport([self.response(status=503), self.response()], heartbeat=heartbeat)
        client.get_json(KgdParser.API_URLS[TAXPAYER_SOURCE])
        self.assertEqual(heartbeat.call_count, 2)
        client = self.transport([RequestsError('synthetic-secret-token')] * 3)
        with self.assertRaisesMessage(SourceError, 'source_request_failed') as failure:
            client.get_json(KgdParser.API_URLS[TAXPAYER_SOURCE])
        self.assertNotIn('synthetic-secret-token', str(failure.exception))

    def test_portal_credentials_cannot_be_sent_to_other_allowed_hosts(self):
        client = self.transport([])
        with self.assertRaises(SourceError):
            client.get_json('https://goszakup.gov.kz/', headers={'X-Portal-Token': 'synthetic-token'})
        self.session.get.assert_not_called()
