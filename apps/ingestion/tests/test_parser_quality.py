"""Synthetic parser regressions: ambiguity is not a fact or a negative check."""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.ingestion.errors import SourceError
from apps.ingestion.normalizers import normalize_amount, normalize_phone, normalize_website
from apps.ingestion.parsers.adata import parse_company_html
from apps.ingestion.parsers.companies import SupplierRegistryParser
from apps.ingestion.parsers.contracts import ContractRegistryParser

FIXTURES = Path(__file__).resolve().parents[3] / 'tests' / 'fixtures'


def html_response(html):
    return SimpleNamespace(text=html, status_code=200)


class ParserQualityTests(SimpleTestCase):
    def test_money_keeps_exact_decimal_zero_and_valid_grouping(self):
        for text, expected in (
                ('0', '0'), ('0,00', '0.00'), ('1234.50', '1234.50'),
                ('1\xa0234,50', '1234.50'), ('1\u202f234\u202f567.89', '1234567.89'),
                ('9 007 199 254 740 993,01', '9007199254740993.01')):
            with self.subTest(text=text):
                self.assertEqual(normalize_amount(text), Decimal(expected))

    def test_money_does_not_concatenate_malformed_groups_or_missing_values(self):
        for text in ('1 2', '12 34.00', '1234 567', '1, 23', '', ' ', None, True, 0.0):
            with self.subTest(text=text), self.assertRaises(ValueError):
                normalize_amount(text)

    def test_phone_never_discards_letters_or_foreign_digits_to_create_a_contact(self):
        for text in ('ұ7 700 000 00 01', 'ё7 700 000 00 01', '7/7000000001',
                     '7+7000000001', '+7 ７００ ０００ ００ ０１', '77000000001 ext'):
            with self.subTest(text=text):
                self.assertIsNone(normalize_phone(text))
        self.assertEqual(normalize_phone('+7 (700) 000-00-01'), '77000000001')
        self.assertEqual(normalize_phone('8 700 000 00 01'), '77000000001')

    def test_missing_customer_section_cannot_borrow_the_supplier_table(self):
        html = ('<h3>Заказчик</h3><h3>Поставщик</h3>'
                '<table><tr><td>БИН</td><td>000000000001</td></tr></table>')
        parser = ContractRegistryParser(transport=Mock())
        with patch.object(parser, '_get', return_value=html_response(html)):
            with self.assertRaisesMessage(SourceError, 'contract_party_identifier_missing'):
                parser.parse_bin_data(1)

    def test_conflicting_party_identifier_rows_are_rejected(self):
        html = ('<h3>Заказчик</h3><table><tr><td>БИН</td><td>000000000002</td></tr>'
                '<tr><td>БИН</td><td>000000000003</td></tr></table>'
                '<h3>Поставщик</h3><table><tr><td>БИН</td><td>000000000001</td></tr></table>')
        parser = ContractRegistryParser(transport=Mock())
        with patch.object(parser, '_get', return_value=html_response(html)):
            with self.assertRaisesMessage(SourceError, 'contract_party_identifier_invalid'):
                parser.parse_bin_data(1)

    def test_page_and_external_identifiers_are_positive_integers_before_http(self):
        transport = Mock()
        parser = ContractRegistryParser(transport=transport)
        for value in (True, False, 1.5, '1', 0, -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parser.fetch_page(value)
            with self.subTest(value=value), self.assertRaises(SourceError):
                parser.parse_bin_data(value)
        transport.get.assert_not_called()

    def test_duplicate_contract_page_is_rejected_before_any_party_fetch(self):
        html = (FIXTURES / 'contracts_page.html').read_text(encoding='utf-8')
        row = html[html.index('<tr><td>101'):html.index('</tbody>')]
        html = html.replace('</tbody>', row + '</tbody>')
        parser = ContractRegistryParser(transport=Mock())
        with patch.object(parser, '_get', return_value=html_response(html)) as get, patch.object(
                parser, 'parse_bin_data') as parties:
            with self.assertRaisesMessage(SourceError, 'contract_page_duplicate_identity'):
                parser.fetch_page(1)
        self.assertEqual(get.call_count, 1)
        parties.assert_not_called()

    def test_conflicting_contract_numbers_are_not_silently_overwritten(self):
        html = (FIXTURES / 'contracts_page.html').read_text(encoding='utf-8')
        row = html[html.index('<tr><td>101'):html.index('</tbody>')].replace('<td>101</td>', '<td>102</td>')
        parser = ContractRegistryParser(transport=Mock())
        with patch.object(parser, '_get', return_value=html_response(html.replace('</tbody>', row + '</tbody>'))):
            with self.assertRaisesMessage(SourceError, 'contract_page_duplicate_identity'):
                parser.fetch_page(1)

    def test_registry_absence_cannot_come_from_unrelated_or_unrecognised_markup(self):
        parser = SupplierRegistryParser(transport=Mock())
        for html in (
                '<h1>Maintenance</h1><footer><table><tbody></tbody></table></footer>',
                '<div>Нет данных</div>',
                '<table><tbody></tbody></table>',
                '<table><th>БИН</th><tbody><tr><td>Unexpected error</td></tr></tbody></table>'):
            with self.subTest(html=html), patch.object(parser, '_get', return_value=html_response(html)):
                with self.assertRaisesMessage(SourceError, 'supplier_search_structure_invalid'):
                    parser.get_supplier_id('000000000001')

    def test_recognised_registry_result_can_establish_absence(self):
        parser = SupplierRegistryParser(transport=Mock())
        for body in ('', '<tr><td colspan="4">Записи не найдены</td></tr>'):
            html = '<table><thead><th>БИН / ИИН</th></thead><tbody>' + body + '</tbody></table>'
            with patch.object(parser, '_get', return_value=html_response(html)):
                self.assertIsNone(parser.get_supplier_id('000000000001'))

    def test_adata_title_tail_does_not_invent_a_director(self):
        html = '<title>Demo, БИН 000000000001. Check this company now</title>'
        data = parse_company_html(html, '000000000001')
        self.assertIsNone(data['director'])
        self.assertIsNone(data['_raw']['director'])
        self.assertNotIn('director_absent', data)

    def test_adata_explicit_role_is_preserved_without_identity_confirmation(self):
        html = ('<title>Demo, БИН 000000000001. Marketing text</title>'
                '<main><dl><dt>Руководитель</dt><dd>Synthetic Director</dd></dl></main>'
                '<footer><dl><dt>Директор</dt><dd>Site contact</dd></dl></footer>')
        data = parse_company_html(html, '000000000001')
        self.assertEqual(data['director'], 'Synthetic Director')
        self.assertEqual(data['_raw']['director'], 'Synthetic Director')
        self.assertNotIn('director_iin', data)
        self.assertNotIn('director_identifier_verified', data)

    def test_adata_company_name_preserves_internal_commas(self):
        html = '<title>Demo Services, East branch, БИН 000000000001. Marketing text</title>'
        self.assertEqual(parse_company_html(html, '000000000001')['name'], 'Demo Services, East branch')


    def test_zero_supplier_record_id_is_invalid_not_not_found(self):
        parser = SupplierRegistryParser(transport=Mock())
        html = ('<table><tr><td>000000000001</td>'
                '<td><a href="/ru/registry/show_supplier/0">Synthetic company</a></td></tr></table>')
        with patch.object(parser, '_get', return_value=html_response(html)):
            with self.assertRaisesMessage(SourceError, 'supplier_link_invalid'):
                parser.get_supplier_data('000000000001')

    def test_contract_external_identifier_does_not_accept_python_number_syntax(self):
        original = (FIXTURES / 'contracts_page.html').read_text(encoding='utf-8')
        parser = ContractRegistryParser(transport=Mock())
        for value in ('1_01', '+101', '１０１'):
            html = original.replace('<td>101</td>', f'<td>{value}</td>')
            with self.subTest(value=value), patch.object(parser, '_get', return_value=html_response(html)):
                with self.assertRaisesMessage(SourceError, 'contract_row_invalid'):
                    parser.fetch_page(1)


    def test_registry_contact_person_cannot_replace_the_labelled_director(self):
        identity = (FIXTURES / 'supplier_card.html').read_text(encoding='utf-8')
        sections = ('<h4>Руководитель</h4><table><tr><th>ФИО</th><td>Synthetic Director</td></tr></table>'
                    '<h4>Контактное лицо</h4><table><tr><th>ФИО</th><td>Synthetic Contact</td></tr></table>')
        parser = SupplierRegistryParser(transport=Mock())
        data = parser.parse_supplier_page(identity.replace('</body>', sections + '</body>'))
        self.assertEqual(data['director'], 'Synthetic Director')
        self.assertEqual(data['_raw']['director'], 'Synthetic Director')
        self.assertNotIn('director_iin', data)

    def test_unscoped_registry_fio_is_unknown_not_a_director_or_absence(self):
        identity = (FIXTURES / 'supplier_card.html').read_text(encoding='utf-8')
        parser = SupplierRegistryParser(transport=Mock())
        html = identity.replace('</body>', '<table><tr><th>ФИО</th><td>Synthetic Contact</td></tr></table></body>')
        data = parser.parse_supplier_page(html)
        self.assertIsNone(data['director'])
        self.assertNotIn('director_absent', data)
        self.assertEqual(data['email'], 'demo@example.com')

    def test_director_heading_does_not_extend_to_the_next_unlabelled_table(self):
        identity = (FIXTURES / 'supplier_card.html').read_text(encoding='utf-8')
        sections = ('<h4>Руководитель</h4><table><tr><th>ФИО</th><td>Synthetic Director</td></tr></table>'
                    '<table><tr><th>ФИО</th><td>Synthetic Contact</td></tr></table>')
        parser = SupplierRegistryParser(transport=Mock())
        data = parser.parse_supplier_page(identity.replace('</body>', sections + '</body>'))
        self.assertEqual(data['director'], 'Synthetic Director')

    def test_explicit_registry_leadership_field_does_not_need_a_section_heading(self):
        identity = (FIXTURES / 'supplier_card.html').read_text(encoding='utf-8')
        row = '<tr><th>ФИО руководителя</th><td>Synthetic Director</td></tr>'
        parser = SupplierRegistryParser(transport=Mock())
        data = parser.parse_supplier_page(identity.replace('</table>', row + '</table>'))
        self.assertEqual(data['director'], 'Synthetic Director')

    def test_conflicting_registry_card_identifiers_are_rejected(self):
        identity = (FIXTURES / 'supplier_card.html').read_text(encoding='utf-8')
        parser = SupplierRegistryParser(transport=Mock())
        for key in ('БИН участника', 'ИИН участника'):
            row = f'<tr><th>{key}</th><td>000000000002</td></tr>'
            with self.subTest(key=key), self.assertRaisesMessage(SourceError, 'supplier_card_identity_invalid'):
                parser.parse_supplier_page(identity.replace('</table>', row + '</table>'))

    def test_repeated_same_registry_card_identifier_remains_usable(self):
        identity = (FIXTURES / 'supplier_card.html').read_text(encoding='utf-8')
        row = '<tr><th>БИН участника</th><td>000000000001</td></tr>'
        parser = SupplierRegistryParser(transport=Mock())
        self.assertEqual(parser.parse_supplier_page(identity.replace('</table>', row + '</table>'))['bin'],
                         '000000000001')

    def test_registry_search_rejects_different_records_for_one_requested_bin(self):
        parser = SupplierRegistryParser(transport=Mock())
        def row(identifier):
            return ('<tr><td>000000000001</td><td>'
                    f'<a href="/ru/registry/show_supplier/{identifier}">Synthetic company</a></td></tr>')
        with patch.object(parser, '_get', return_value=html_response('<table>' + row(1) + row(2) + '</table>')):
            with self.assertRaisesMessage(SourceError, 'supplier_search_identity_invalid'):
                parser.get_supplier_id('000000000001')
        with patch.object(parser, '_get', return_value=html_response('<table>' + row(1) + row(1) + '</table>')):
            self.assertEqual(parser.get_supplier_id('000000000001'), 1)


    def adata_structured(self, organization=None, people=(), extras=()):
        organization = organization or {
            '@type': 'Organization', 'identifier': '000000000001', 'vatID': '000000000001',
            'name': 'Synthetic Structured Company', 'address': 'Synthetic recorded office',
            'email': 'company@example.com', 'telephone': '8 (700) 000-00-01',
            'founder': 'Synthetic founder is not a director',
        }
        objects = [organization, *people, *extras]
        return ('<title>Synthetic title, БИН 000000000001. Untrusted tail</title><main>' +
                ''.join('<script type="application/ld+json">' + json.dumps(obj) + '</script>' for obj in objects) +
                '</main>')

    def adata_person(self, **changes):
        return {'@type': 'Person', 'jobTitle': 'Руководитель', 'name': 'Synthetic Director',
                'mainEntityOfPage': 'https://pk.adata.kz/counterparty/main/company/000000000001/basic-info',
                **changes}

    def test_public_adata_profile_has_exact_identity_and_normalized_contacts(self):
        html = self.adata_structured(people=[self.adata_person()])
        data = parse_company_html(html, '000000000001')
        self.assertEqual(data['name'], 'Synthetic Structured Company')
        self.assertEqual(data['address'], 'Synthetic recorded office')
        self.assertEqual(data['phone'], '77000000001')
        self.assertEqual(data['_raw']['phone'], '8 (700) 000-00-01')
        self.assertEqual(data['email'], 'company@example.com')
        self.assertEqual(data['director'], 'Synthetic Director')
        self.assertNotIn('owners', data)
        self.assertNotIn('founder', data['_raw'])
        self.assertNotIn('director_iin', data)

    def test_other_company_structured_profile_does_not_leak_fields(self):
        other = {'@type': 'Organization', 'identifier': '000000000009', 'vatID': '000000000009',
                 'name': 'Other synthetic company', 'email': 'other@example.com', 'telephone': '77000000009'}
        data = parse_company_html(self.adata_structured(organization=other), '000000000001')
        self.assertEqual(data['name'], 'Synthetic title')
        self.assertIsNone(data['phone'])
        self.assertIsNone(data['email'])
        self.assertIsNone(data['director'])

    def test_bound_adata_profile_ignores_related_company_roles_and_publisher_contacts(self):
        others = [
            {'@type': 'Organization', 'identifier': '000000000009', 'telephone': '77000000009'},
            {'@type': 'WebSite', 'telephone': '77000000008'},
        ]
        person = self.adata_person(mainEntityOfPage=
            'https://pk.adata.kz/counterparty/main/company/000000000009/basic-info')
        html = self.adata_structured(people=[person], extras=others)
        html += '<table><tr><th>Директор</th><td>Unrelated table name</td></tr></table>'
        data = parse_company_html(html, '000000000001')
        self.assertIsNone(data['director'])
        self.assertEqual(data['phone'], '77000000001')

    def test_adata_founder_and_unsupported_job_titles_are_not_directors(self):
        for role in ('Учредитель', 'Бывший директор', 'Accountant', ''):
            data = parse_company_html(self.adata_structured(
                people=[self.adata_person(jobTitle=role)]), '000000000001')
            self.assertIsNone(data['director'])

    def test_adata_conflicting_bound_profiles_roles_and_identifiers_are_rejected(self):
        for html, code in [
            (self.adata_structured(extras=[{'@type': 'Organization', 'identifier': '000000000001',
                                         'name': 'Conflicting synthetic name'}]), 'adata_structured_profile_invalid'),
            (self.adata_structured(people=[self.adata_person(), self.adata_person(name='Other director')]),
             'adata_structured_director_invalid'),
            (self.adata_structured(organization={'@type': 'Organization', 'identifier': '000000000001',
                                                'vatID': '000000000009'}),
             'adata_structured_identity_invalid'),
        ]:
            with self.subTest(code=code), self.assertRaisesMessage(SourceError, code):
                parse_company_html(html, '000000000001')

    def test_adata_person_url_requires_exact_public_company_binding(self):
        for url in (
            'https://evil.example/counterparty/main/company/000000000001/basic-info',
            'https://pk.adata.kz/counterparty/main/company/000000000001/basic-info?other=1',
            'https://pk.adata.kz/counterparty/main/company/000000000001/basic-info#other',
            'http://pk.adata.kz/counterparty/main/company/000000000001/basic-info',
        ):
            data = parse_company_html(self.adata_structured(
                people=[self.adata_person(mainEntityOfPage=url)]), '000000000001')
            self.assertIsNone(data['director'])

    def test_registry_company_and_contract_requests_use_confirmed_canonical_host(self):
        company = SupplierRegistryParser(transport=Mock())
        with patch.object(company, '_get', return_value=html_response(
                (FIXTURES / 'supplier_search.html').read_text(encoding='utf-8'))) as get:
            company.get_supplier_id('000000000001')
        self.assertTrue(get.call_args.args[0].startswith('https://old.goszakup.gov.kz/ru/registry/supplierreg?'))
        contract = ContractRegistryParser(transport=Mock())
        with patch.object(contract, '_get', return_value=html_response(
                (FIXTURES / 'contracts_empty.html').read_text(encoding='utf-8'))) as get:
            contract.fetch_page(1)
        self.assertEqual(get.call_args.args[0], 'https://old.goszakup.gov.kz/ru/registry/contract?page=1')


    def test_adata_duplicate_json_keys_cannot_replace_identity_or_contact_fields(self):
        for duplicate in (
                '"identifier":"000000000009","identifier":"000000000001"',
                '"identifier":"000000000001","email":"first@example.com","email":"second@example.com"',
        ):
            html = ('<title>Synthetic company, БИН 000000000001.</title>'
                    '<script type="application/ld+json">{"@type":"Organization",' + duplicate + '}</script>')
            with self.subTest(duplicate=duplicate), self.assertRaisesMessage(
                    SourceError, 'adata_structured_duplicate_key_invalid'):
                parse_company_html(html, '000000000001')

    def test_registry_blank_alternative_identifier_does_not_hide_exact_iin(self):
        identity = (FIXTURES / 'supplier_card.html').read_text(encoding='utf-8')
        parser = SupplierRegistryParser(transport=Mock())
        iin_row = '<tr><th>ИИН участника</th><td>000000000001</td></tr>'
        blank_row = '<tr><th>БИН участника</th><td> </td></tr>'
        for rows in (iin_row + blank_row, blank_row + iin_row):
            html = identity.replace('<tr><th>БИН участника</th><td>000000000001</td></tr>', rows)
            with self.subTest(rows=rows):
                self.assertEqual(parser.parse_supplier_page(html)['bin'], '000000000001')
        for value in ('', '-', 'unknown'):
            html = identity.replace('000000000001', value)
            with self.subTest(value=value), self.assertRaisesMessage(SourceError, 'supplier_fields_invalid'):
                parser.parse_supplier_page(html)

    def test_registry_nonblank_invalid_alternative_identifier_still_rejects_card(self):
        identity = (FIXTURES / 'supplier_card.html').read_text(encoding='utf-8')
        parser = SupplierRegistryParser(transport=Mock())
        for value in ('-', '000000000002', 'not an identifier'):
            row = f'<tr><th>ИИН участника</th><td>{value}</td></tr>'
            with self.subTest(value=value), self.assertRaises(SourceError):
                parser.parse_supplier_page(identity.replace('</table>', row + '</table>'))

    def test_optional_website_normalization_keeps_supported_urls_only(self):
        for raw, expected in (
                ('example.com', 'https://example.com'),
                (' www.example.com/profile ', 'https://www.example.com/profile'),
                ('http://example.com/profile', 'http://example.com/profile')):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_website(raw), expected)
        for raw in (None, '', '-', 'not a website', 'javascript:alert(1)', 'ftp://example.com',
                    'https://user:secret@example.com', 'https://example.com/' + 'a' * 200):
            with self.subTest(raw=raw):
                self.assertIsNone(normalize_website(raw))

    def test_registry_optional_website_survives_ingestion_validation_with_raw_preserved(self):
        from apps.companies.models import Supplier
        from apps.ingestion.dto import ResultStatus, SourceResult
        from apps.ingestion.observations import normalize_company_result
        identity = (FIXTURES / 'supplier_card.html').read_text(encoding='utf-8')
        parser = SupplierRegistryParser(transport=Mock())
        for value, expected in (('example.com', 'https://example.com'), ('invalid website', None)):
            row = f'<tr><th>Вебсайт</th><td>{value}</td></tr>'
            data = parser.parse_supplier_page(identity.replace('</table>', row + '</table>'))
            raw = data.pop('_raw')
            result = SourceResult('goszakup_supplier', 'company:000000000001', ResultStatus.SUCCESS,
                                  data=data, raw=raw)
            normalized = normalize_company_result(result, Supplier(bin='000000000001', name='Synthetic'))
            self.assertEqual(normalized.data['website'], expected)
            self.assertEqual(normalized.raw['website'], value)

    def test_adata_title_without_identifier_uses_exact_bound_public_profile(self):
        from apps.companies.models import Supplier
        from apps.ingestion.dto import ResultStatus, SourceResult
        from apps.ingestion.observations import normalize_company_result
        organization = {'@type': 'Organization', 'identifier': '000000000001', 'vatID': '000000000001',
                        'name': 'Synthetic Sole Trader', 'telephone': '8 (700) 000-00-01',
                        'url': 'https://pk.adata.kz/counterparty/main/company/000000000001/basic-info'}
        html = self.adata_structured(organization=organization, people=[self.adata_person(jobTitle='Founder')])
        html = html.replace('Synthetic title, БИН 000000000001. Untrusted tail', 'Synthetic business profile')
        data = parse_company_html(html, '000000000001')
        raw = data.pop('_raw')
        result = SourceResult('adata', 'company:000000000001', ResultStatus.SUCCESS, data=data, raw=raw)
        normalized = normalize_company_result(result, Supplier(bin='000000000001', name='Synthetic'))
        self.assertEqual(normalized.data['bin'], '000000000001')
        self.assertEqual(normalized.data['name'], 'Synthetic Sole Trader')
        self.assertEqual(normalized.data['phone'], '77000000001')
        self.assertIsNone(normalized.data['director_name'])
        self.assertNotIn('director_iin', normalized.data)

    def test_adata_title_without_identity_requires_both_identifiers_and_exact_page(self):
        organization = {'@type': 'Organization', 'identifier': '000000000001', 'vatID': '000000000001',
                        'name': 'Synthetic profile',
                        'url': 'https://pk.adata.kz/counterparty/main/company/000000000001/basic-info'}
        for changes in (
                {'identifier': None}, {'vatID': None}, {'identifier': '000000000002'},
                {'url': None}, {'url': 'https://pk.adata.kz/counterparty/main/company/000000000002/basic-info'},
                {'url': 'https://other.example/counterparty/main/company/000000000001/basic-info'},
                {'identifier': '000000000002', 'vatID': '000000000002'}):
            html = self.adata_structured(organization={**organization, **changes})
            html = html.replace('Synthetic title, БИН 000000000001. Untrusted tail', 'Generic profile')
            with self.subTest(changes=changes), self.assertRaises(SourceError):
                parse_company_html(html, '000000000001')

    def test_adata_conflicting_title_or_profile_page_cannot_be_overridden_by_structured_identity(self):
        organization = {'@type': 'Organization', 'identifier': '000000000001', 'vatID': '000000000001',
                        'name': 'Synthetic profile',
                        'url': 'https://pk.adata.kz/counterparty/main/company/000000000001/basic-info'}
        html = self.adata_structured(organization=organization)
        for title in ('Other, БИН 000000000002', 'Mixed, БИН 000000000001. ИИН 000000000002'):
            with self.subTest(title=title), self.assertRaisesMessage(SourceError, 'adata_identity_unconfirmed'):
                parse_company_html(html.replace('Synthetic title, БИН 000000000001. Untrusted tail', title),
                                   '000000000001')
        organization['url'] = 'https://pk.adata.kz/counterparty/main/company/000000000002/basic-info'
        with self.assertRaisesMessage(SourceError, 'adata_structured_identity_invalid'):
            parse_company_html(self.adata_structured(organization=organization), '000000000001')
