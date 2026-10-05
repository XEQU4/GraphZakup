from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase

from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.core.models import SystemSetting
from apps.graph.models import RiskCluster
from apps.owners.models import Director, Directorship
from services.adata_parser import fetch_company_data, parse_company_html
from services.contract_registry_parser import ContractPage, ContractRegistryParser
from services.enricher import enrich_supplier
from services.normalizers import normalize_amount, normalize_bin, normalize_date, normalize_email
from services.parser_errors import SourceError
from services.supplier_registry_parser import SupplierRegistryParser

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
IMPORT_MODULE = "apps.companies.management.commands.import_contracts"
ENRICH_MODULE = "apps.companies.management.commands.enrich_suppliers"


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def response(text, status=200):
    return SimpleNamespace(text=text, status_code=status)


def contract_record(identifier):
    return {
        "contract_number": f"demo-{identifier}", "contract_gos_id": identifier,
        "supplier_bin": "000000000001", "customer_bin": "000000000002",
        "supplier_name": "Демонстрационная компания", "customer_name": "Демонстрационный заказчик",
        "amount": Decimal("100.01"), "sign_date": date(2020, 1, 24), "subject": "Demo",
    }


class SourceParserTests(SimpleTestCase):
    def test_contract_amount_is_exact_and_dates_normalized(self):
        parser = ContractRegistryParser()
        with patch.object(parser, "_get", side_effect=[response(fixture("contracts_page.html")),
                                                      response(fixture("contract_parties.html"))]):
            page = parser.fetch_page(1)
        self.assertEqual(page.records[0]["amount"], Decimal("9007199254740993.01"))
        self.assertEqual(page.records[0]["sign_date"], date(2020, 1, 24))
        self.assertEqual(page.records[0]["supplier_bin"], "000000000001")
        self.assertFalse(page.eof)

    def test_only_confirmed_empty_table_is_eof(self):
        parser = ContractRegistryParser()
        with patch.object(parser, "_get", return_value=response(fixture("contracts_empty.html"))):
            self.assertTrue(parser.fetch_page(5).eof)
        for html in ("<html>Unexpected maintenance page</html>",
                     "<table><tr><th>Номер договора</th></tr></table>",
                     '<table><th>Номер договора</th><tbody><tr><td>broken row</td></tr></tbody></table>'):
            with self.subTest(html=html), patch.object(parser, "_get", return_value=response(html)):
                with self.assertRaises(SourceError):
                    parser.fetch_page(5)

    def test_http_challenge_and_network_error_are_not_empty_pages(self):
        parser = ContractRegistryParser()
        parser.MAX_RATE_LIMIT_RETRIES = 0
        for bad in (response("Service unavailable", 503), response("g-recaptcha", 200), response("", 200)):
            with self.subTest(status=bad.status_code), patch.object(parser.session, "get", return_value=bad):
                with patch("services.contract_registry_parser.time.sleep"), self.assertRaises(SourceError):
                    parser.fetch_page(5)
        from curl_cffi.requests import RequestsError
        with patch.object(parser.session, "get", side_effect=RequestsError("private response")):
            with patch("services.contract_registry_parser.time.sleep"), self.assertRaises(SourceError) as caught:
                parser.fetch_page(5)
        self.assertEqual(str(caught.exception), "source_request_failed")

    def test_invalid_amount_date_and_party_identifier_stop_page(self):
        parser = ContractRegistryParser()
        for valid, damaged in (("9 007 199 254 740 993,01", "bad amount"), ("24.01.2020", "31.02.2020")):
            html = fixture("contracts_page.html").replace(valid, damaged)
            with patch.object(parser, "_get", return_value=response(html)), self.assertRaises(SourceError):
                parser.fetch_page(1)
        bad_parties = fixture("contract_parties.html").replace("000000000001", "broken")
        with patch.object(parser, "_get", return_value=response(bad_parties)), self.assertRaises(SourceError):
            parser.parse_bin_data(101)

    def test_supplier_search_selects_matching_bin_and_checks_card(self):
        parser = SupplierRegistryParser()
        with patch.object(parser, "_get", side_effect=[response(fixture("supplier_search.html")),
                                                      response(fixture("supplier_card.html"))]):
            data = parser.get_supplier_data("000000000001")
        self.assertEqual(data["supplier_id"], 1)
        self.assertEqual(data["registration_date"], date(2020, 1, 24))
        with patch.object(parser, "get_supplier_id", return_value=1):
            with patch.object(parser, "get_supplier_html", return_value=fixture("supplier_card.html")):
                with self.assertRaises(SourceError):
                    parser.get_supplier_data("000000000009")

    def test_supplier_missing_structure_is_not_not_found(self):
        parser = SupplierRegistryParser()
        with patch.object(parser, "_get", return_value=response("<html>Server error</html>")):
            with self.assertRaises(SourceError):
                parser.get_supplier_id("000000000001")

    def test_adata_contacts_come_from_labelled_company_fields(self):
        data = parse_company_html(fixture("adata_company.html"), "000000000001")
        self.assertEqual(data["email"], "demo@example.com")
        self.assertEqual(data["phone"], "77000000001")
        self.assertNotIn("status", data)
        with self.assertRaises(SourceError):
            parse_company_html(fixture("adata_company.html"), "000000000009")
        unlabelled = '<title>Demo, БИН 000000000001.</title><body>help@example.com +7 700 000 00 09</body>'
        self.assertIsNone(parse_company_html(unlabelled, "000000000001")["email"])

    def test_adata_challenge_is_not_a_not_found_response(self):
        with patch("services.adata_parser.requests.get", return_value=response("g-recaptcha", 404)):
            with self.assertRaises(SourceError):
                fetch_company_data("000000000001")

    def test_valid_contact_fallback_is_chosen_after_normalization(self):
        registry = {"bin": "000000000001", "email": "valid@example.com", "phone": "8 (700) 000-00-01",
                    "registration_date": "24.01.2020", "name": "Demo"}
        adata = {"bin": "000000000001", "email": "SUPPORT@ADATA.KZ", "phone": "invalid"}
        with patch("services.enricher.registry_parser.get_supplier_data", return_value=registry):
            with patch("services.enricher.fetch_adata", return_value=adata):
                data = enrich_supplier("000000000001")
        self.assertEqual(data["email"], "valid@example.com")
        self.assertEqual(data["phone"], "77000000001")
        self.assertEqual(data["registration_date"], date(2020, 1, 24))

    def test_unavailable_enrichment_source_is_visible_with_valid_fallback(self):
        with patch("services.enricher.registry_parser.get_supplier_data", side_effect=SourceError("offline")):
            with patch("services.enricher.fetch_adata", return_value={"bin": "000000000001", "name": "Demo"}):
                self.assertTrue(enrich_supplier("000000000001")["_source_errors"])

    def test_normalizers_reject_invalid_money_and_identifiers(self):
        self.assertEqual(normalize_amount("1\xa0234,50"), Decimal("1234.50"))
        for value in ("not a sum", "NaN", "-1", 1.1, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_amount(value)
        self.assertEqual(normalize_bin("000000000001"), "000000000001")
        with self.assertRaises(ValueError):
            normalize_bin("123")
        self.assertEqual(normalize_date("2020-01-24"), date(2020, 1, 24))
        self.assertIsNone(normalize_email("broken-address"))


class ContractImportIntegrityTests(TestCase):
    def run_import(self, pages, **options):
        with patch(f"{IMPORT_MODULE}.ContractRegistryParser") as parser:
            parser.return_value.iter_pages.return_value = iter(pages)
            with patch(f"{IMPORT_MODULE}.call_command") as downstream:
                call_command("import_contracts", stdout=StringIO(), **options)
        return parser.return_value.iter_pages.call_args, downstream.call_args_list

    def test_full_scan_preserves_existing_data_roles_clusters_and_new_cursor(self):
        old = Supplier.objects.create(bin="000000000009", name="Existing")
        contract = Contract.objects.create(supplier=old, contract_number="existing", title="Existing",
                                           amount="1.00", contract_date=date(2019, 1, 1))
        director = Director.objects.create(full_name="Existing director")
        role = Directorship.objects.create(supplier=old, director=director)
        cluster = RiskCluster.objects.create(name="Existing", ai_explanation="Saved")
        cluster.suppliers.add(old)
        SystemSetting.objects.create(key="last_import_page", value="7")
        args, downstream = self.run_import([ContractPage(1, (contract_record(1),))], mode="full", total=1)
        self.assertEqual(args.kwargs["start_page"], 1)
        self.assertTrue(Contract.objects.filter(pk=contract.pk).exists())
        self.assertTrue(Directorship.objects.filter(pk=role.pk).exists())
        cluster.refresh_from_db()
        self.assertEqual(cluster.ai_explanation, "Saved")
        self.assertEqual(SystemSetting.objects.get(key="last_import_page").value, "7")
        self.assertEqual(SystemSetting.objects.get(key="full_import_page").value, "2")
        self.assertEqual([call.args[0] for call in downstream], ["enrich_suppliers", "build_clusters"])

    def test_empty_eof_preserves_cursor_and_does_not_run_pipeline(self):
        SystemSetting.objects.create(key="last_import_page", value="5")
        _, downstream = self.run_import([ContractPage(5, (), eof=True)])
        self.assertEqual(SystemSetting.objects.get(key="last_import_page").value, "5")
        self.assertFalse(SystemSetting.objects.filter(key="last_import").exists())
        self.assertEqual(downstream, [])

    def test_partial_limit_repeats_page_without_losing_remaining_contracts(self):
        first = ContractPage(1, tuple(contract_record(i) for i in range(1, 51)))
        second = ContractPage(2, tuple(contract_record(i) for i in range(51, 101)))
        self.run_import([first, second], total=51)
        self.assertEqual(Contract.objects.count(), 51)
        self.assertEqual(SystemSetting.objects.get(key="last_import_page").value, "2")
        args, _ = self.run_import([second], total=50)
        self.assertEqual(args.kwargs["start_page"], 2)
        self.assertEqual(Contract.objects.count(), 100)
        self.assertEqual(SystemSetting.objects.get(key="last_import_page").value, "3")

    def test_database_failure_rolls_back_page_and_preserves_checkpoint(self):
        SystemSetting.objects.create(key="last_import_page", value="5")
        original = Contract.objects.update_or_create
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise IntegrityError("private source data")
            return original(*args, **kwargs)

        with patch.object(Contract.objects, "update_or_create", side_effect=fail_second):
            with self.assertRaisesMessage(CommandError, "page_save_failed"):
                self.run_import([ContractPage(5, (contract_record(1), contract_record(2)))], total=2)
        self.assertEqual(Contract.objects.count(), 0)
        self.assertEqual(Supplier.objects.count(), 0)
        self.assertEqual(SystemSetting.objects.get(key="last_import_page").value, "5")

    def test_source_failure_keeps_successful_page_and_retries_failed_page(self):
        def pages():
            yield ContractPage(1, (contract_record(1),))
            raise SourceError("source_http_503")

        with patch(f"{IMPORT_MODULE}.ContractRegistryParser") as parser:
            parser.return_value.iter_pages.return_value = pages()
            with patch(f"{IMPORT_MODULE}.call_command") as downstream:
                with self.assertRaisesMessage(CommandError, "source_http_503"):
                    call_command("import_contracts", total=2, stdout=StringIO())
                downstream.assert_not_called()
        self.assertEqual(Contract.objects.count(), 1)
        self.assertEqual(SystemSetting.objects.get(key="last_import_page").value, "2")

    def test_supplier_identity_change_does_not_reassign_existing_contract(self):
        self.run_import([ContractPage(1, (contract_record(1),))], total=1)
        changed = {**contract_record(1), "supplier_bin": "000000000009"}
        with self.assertRaisesMessage(CommandError, "invalid_import_data"):
            self.run_import([ContractPage(1, (changed,))], start_page=1, total=1)
        self.assertEqual(Contract.objects.get(contract_number="demo-1").supplier.bin, "000000000001")
        self.assertFalse(Supplier.objects.filter(bin="000000000009").exists())

    def test_invalid_record_is_not_skipped_as_success(self):
        record = {**contract_record(1), "supplier_bin": "bad"}
        with self.assertRaisesMessage(CommandError, "invalid_import_data"):
            self.run_import([ContractPage(1, (record,))], total=1)
        self.assertFalse(SystemSetting.objects.filter(key="last_import_page").exists())


class SupplierEnrichmentIntegrityTests(TestCase):
    def test_invalid_company_does_not_prevent_next_company_update(self):
        bad = Supplier.objects.create(bin="000000000001", name="Bad")
        good = Supplier.objects.create(bin="000000000002", name="Good")
        results = [{"registration_date": "31.02.2020"}, {"registration_date": "24.01.2020", "name": "Updated"}]
        with patch(f"{ENRICH_MODULE}.enrich_supplier", side_effect=results), patch(f"{ENRICH_MODULE}.sleep"):
            with self.assertRaisesMessage(CommandError, "Enrichment incomplete"):
                call_command("enrich_suppliers", stdout=StringIO(), stderr=StringIO())
        bad.refresh_from_db()
        good.refresh_from_db()
        self.assertIsNone(bad.adata_updated_at)
        self.assertEqual(good.registration_date, date(2020, 1, 24))
        self.assertEqual(good.name, "Updated")
        self.assertIsNotNone(good.adata_updated_at)

    def test_missing_or_failed_observation_does_not_mark_company_fresh(self):
        supplier = Supplier.objects.create(bin="000000000001", name="Demo")
        with patch(f"{ENRICH_MODULE}.enrich_supplier", return_value=None), patch(f"{ENRICH_MODULE}.sleep"):
            call_command("enrich_suppliers", stdout=StringIO())
        supplier.refresh_from_db()
        self.assertIsNone(supplier.adata_updated_at)
        with patch(f"{ENRICH_MODULE}.enrich_supplier", return_value={"name": "Updated", "_source_errors": ["offline"]}):
            with patch(f"{ENRICH_MODULE}.sleep"), self.assertRaises(CommandError):
                call_command("enrich_suppliers", stdout=StringIO())
        supplier.refresh_from_db()
        self.assertEqual(supplier.name, "Updated")
        self.assertIsNone(supplier.adata_updated_at)
