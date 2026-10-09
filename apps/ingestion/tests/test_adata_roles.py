import json
from django.test import SimpleTestCase
from apps.ingestion.parsers.adata import parse_company_html


class AdataRoleVariantsTests(SimpleTestCase):
    def page(self, person):
        company = {'@type': 'Organization', 'identifier': '000000000001', 'vatID': '000000000001',
                   'name': 'Synthetic company', 'founder': 'Synthetic historical founder'}
        person = {'@type': 'Person', 'jobTitle': 'Pуководитель', 'name': 'Synthetic Director',
                  'mainEntityOfPage': 'https://pk.adata.kz/counterparty/main/company/000000000001/basic-info', **person}
        return '<title>Synthetic, БИН 000000000001</title>' + ''.join(
            '<script type="application/ld+json">' + json.dumps(item) + '</script>' for item in (company, person))

    def test_observed_latin_letter_role_label_keeps_unverified_director(self):
        result = parse_company_html(self.page({}), '000000000001')
        self.assertEqual(result['director'], 'Synthetic Director')
        self.assertNotIn('director_iin', result)
        self.assertNotIn('owners', result)

    def test_explicit_structured_name_parts_are_used_when_name_is_empty(self):
        result = parse_company_html(self.page({'name': '', 'familyName': 'Synthetic',
            'givenName': 'Alex', 'additionalName': 'Example', 'birthDate': '2000-01-01'}), '000000000001')
        self.assertEqual(result['director'], 'Synthetic Alex Example')
        self.assertNotIn('birthDate', repr(result))

    def test_masked_or_incomplete_parts_do_not_fall_back_to_founder(self):
        for person in ({'name': '', 'familyName': 'Synthetic'}, {'name': '', 'familyName': 'S***', 'givenName': 'Alex'},
                       {'jobTitle': 'Founder', 'name': 'Synthetic Founder'},
                       {'mainEntityOfPage': 'https://pk.adata.kz/counterparty/main/company/000000000009/basic-info'}):
            self.assertIsNone(parse_company_html(self.page(person), '000000000001')['director'])
