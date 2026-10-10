"""Only an exact, explicitly scoped registry identifier can verify a director."""
from pathlib import Path
from unittest.mock import Mock
from django.test import SimpleTestCase
from apps.ingestion.errors import SourceError
from apps.ingestion.parsers.companies import SupplierRegistryParser


class RegistryDirectorIdentifierTests(SimpleTestCase):
    def parse(self, sections):
        base = (Path(__file__).resolve().parents[3] / 'tests/fixtures/supplier_card.html').read_text(encoding='utf-8')
        return SupplierRegistryParser(transport=Mock()).parse_supplier_page(base.replace('</body>', sections + '</body>'))

    def table(self, identifier='000000000010', *, name='Synthetic Director', heading='Руководитель'):
        return (f'<h4>{heading}</h4><table><tr><th>ИИН</th><td>{identifier}</td></tr>'
                '<tr><th>РНН</th><td>000000000020</td></tr>'
                f'<tr><th>ФИО</th><td>{name}</td></tr></table>')

    def test_exact_identifier_and_name_come_from_the_same_director_section(self):
        data = self.parse(self.table())
        self.assertEqual(data['director_iin'], '000000000010')
        self.assertTrue(data['director_iin_verified'])
        self.assertEqual(data['_raw']['director_iin'], data['director_iin'])
        self.assertEqual(data['director'], 'Synthetic Director')

    def test_missing_masked_invalid_and_zero_identifiers_do_not_manufacture_verification(self):
        for identifier in ('', '********0010', '000000000000', 'unknown', '123', '１２３４５６７８９０１２'):
            with self.subTest(identifier=identifier):
                data = self.parse(self.table(identifier))
                self.assertNotIn('director_iin', data)
                self.assertEqual(data['director'], 'Synthetic Director')

    def test_contact_iin_or_participant_iin_cannot_verify_a_director(self):
        data = self.parse(self.table('') + self.table(heading='Контактное лицо'))
        self.assertNotIn('director_iin', data)

    def test_a_director_identifier_without_its_own_name_is_not_borrowed(self):
        data = self.parse(self.table(name='') + self.table('', name='Synthetic Director'))
        self.assertNotIn('director_iin', data)

    def test_conflicting_director_identifiers_are_rejected(self):
        with self.assertRaisesMessage(SourceError, 'supplier_director_identity_invalid'):
            self.parse(self.table() + self.table('000000000011'))

    def test_unlabelled_following_table_cannot_supply_director_identifier(self):
        data = self.parse(self.table('') + '<table><tr><th>ИИН</th><td>000000000010</td></tr></table>')
        self.assertNotIn('director_iin', data)
