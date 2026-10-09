"""Synthetic entrepreneur registration and legal-debt boundary regressions."""
from unittest.mock import Mock

from django.test import SimpleTestCase, TestCase, override_settings

from apps.companies.models import Supplier
from apps.ingestion.dto import ResultStatus
from apps.ingestion.models import SourceObservation
from apps.ingestion.parsers.kgd import DEBT_SOURCE, TAXPAYER_SOURCE, KgdParser
from apps.ingestion.providers import SourceProviders
from apps.ingestion.services import IngestionFailure, run_pipeline
from .test_kgd_parser import BIN, fixture


def registration(kind='IP'):
    payload = fixture('taxpayer')
    payload['taxpayerPortalSearchResponses'][0]['taxpayerType'] = kind
    return payload


class EntrepreneurParserTests(SimpleTestCase):
    def setUp(self):
        self.transport = Mock()
        self.transport.get_json.return_value = registration()
        self.parser = KgdParser(self.transport, enabled=True, portal_token='synthetic-token', taxpayer_type='IP',
                                account_tokens={BIN: 'synthetic-account-token'})

    def test_registration_requires_explicit_type_and_name_and_preserves_source_dates(self):
        result = self.parser.fetch(TAXPAYER_SOURCE, BIN, taxpayer_name=' Synthetic entrepreneur ')
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.data['kgd_taxpayer_type'], 'IP')
        self.assertEqual(result.data['kgd_registration_begin'].isoformat(), '2020-01-01')
        self.assertEqual(self.transport.get_json.call_args.kwargs['params'],
                         {'taxpayerCode': BIN, 'taxpayerType': 'IP', 'name': 'Synthetic entrepreneur', 'print': 'false'})

    def test_missing_name_does_not_send_an_incomplete_request(self):
        for name in ('', None, 'x' * 501):
            result = self.parser.fetch(TAXPAYER_SOURCE, BIN, taxpayer_name=name)
            self.assertEqual(result.error_code, 'kgd_taxpayer_name_required')
        self.transport.get_json.assert_not_called()

    def test_an_entrepreneur_never_qualifies_for_legal_entity_debt(self):
        result = self.parser.fetch(DEBT_SOURCE, BIN, legal_entity_confirmed=True)
        self.assertEqual((result.status, result.error_code),
                         (ResultStatus.NOT_CHECKED, 'kgd_entrepreneur_debt_scope_unverified'))
        self.transport.get_json.assert_not_called()

    def test_returned_type_must_match_request_in_both_directions(self):
        for requested, returned in (('IP', 'UL'), ('UL', 'IP'), ('UL', 'UL_NR')):
            self.parser.taxpayer_type = requested
            self.transport.get_json.return_value = registration(returned)
            result = self.parser.fetch(TAXPAYER_SOURCE, BIN, taxpayer_name='Synthetic')
            self.assertEqual((result.status, result.error_code), (ResultStatus.INVALID, 'kgd_subject_type_mismatch'))
            self.assertEqual(result.data, {})


@override_settings(ENABLE_KGD_CHECKS=True, KGD_PORTAL_TOKEN='synthetic-token', KGD_TAXPAYER_TYPE='IP',
                   KGD_ACCOUNT_TOKENS_JSON='{"000000000001":"synthetic-account-token"}')
class EntrepreneurPipelineTests(TestCase):
    def setUp(self):
        Supplier.objects.create(bin=BIN, name='Synthetic entrepreneur')
        self.transport = Mock()
        self.transport.get_json.return_value = registration()

    def collect(self, **kwargs):
        return run_pipeline(mode='kgd', total=1, company_bin=BIN,
                            providers=SourceProviders(transport=self.transport), **kwargs)

    def test_registration_is_saved_but_debt_remains_unknown_without_http(self):
        with self.assertRaises(IngestionFailure):
            self.collect(kgd_service='tax_debt', force=True)
        self.assertEqual(self.transport.get_json.call_count, 1)
        self.assertEqual(self.transport.get_json.call_args.kwargs['params']['name'], 'Synthetic entrepreneur')
        observations = {p.source: p for p in SourceObservation.objects.all()}
        self.assertEqual(observations[TAXPAYER_SOURCE].normalized_values['kgd_taxpayer_type'], 'IP')
        self.assertEqual(observations[DEBT_SOURCE].status, 'not_checked')
        self.assertEqual(observations[DEBT_SOURCE].normalized_values, {})
        self.assertEqual(observations[DEBT_SOURCE].error_code, 'kgd_entrepreneur_debt_scope_unverified')

    def test_same_type_cache_preserves_time_but_changed_type_fetches_again(self):
        first = self.collect()
        second = self.collect()
        self.assertEqual(self.transport.get_json.call_count, 1)
        old = SourceObservation.objects.get(run=first)
        cached = SourceObservation.objects.get(run=second)
        self.assertTrue(cached.from_cache)
        self.assertEqual(cached.observed_at, old.observed_at)
        self.transport.get_json.return_value = registration('UL')
        with override_settings(KGD_TAXPAYER_TYPE='UL'):
            third = self.collect()
        self.assertEqual(self.transport.get_json.call_count, 2)
        self.assertEqual(SourceObservation.objects.get(run=third).normalized_values['kgd_taxpayer_type'], 'UL')

    def test_legal_registration_cache_cannot_authorize_debt_in_ip_mode(self):
        self.transport.get_json.return_value = registration('UL')
        with override_settings(KGD_TAXPAYER_TYPE='UL'):
            self.collect()
        self.transport.get_json.return_value = registration()
        with self.assertRaises(IngestionFailure):
            self.collect(kgd_service='tax_debt')
        self.assertEqual(self.transport.get_json.call_count, 2)
        self.assertEqual(SourceObservation.objects.filter(source=DEBT_SOURCE).get().status, 'not_checked')
