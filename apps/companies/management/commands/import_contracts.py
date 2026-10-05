import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.core.models import SystemSetting
from services.contract_registry_parser import ContractRegistryParser
from services.normalizers import normalize_amount, normalize_bin, normalize_date
from services.parser_errors import SourceError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Upsert contracts without deleting existing data; full starts a new scan"

    def add_arguments(self, parser):
        parser.add_argument("--total", type=int, default=500, help="Максимум договоров за запуск")
        parser.add_argument("--mode", choices=["new", "full"], default="new")
        parser.add_argument("--start-page", type=int, default=None, help="Начальная страница вместо checkpoint")

    def handle(self, *args, **options):
        total, mode = options["total"], options["mode"]
        if total <= 0 or (options["start_page"] is not None and options["start_page"] < 1):
            raise CommandError("total and start-page must be positive")
        checkpoint_key = "last_import_page" if mode == "new" else "full_import_page"
        start_page = options["start_page"]
        if start_page is None:
            start_page = 1
            if mode == "new":
                saved = SystemSetting.objects.filter(key=checkpoint_key).values_list("value", flat=True).first()
                if saved is not None:
                    try:
                        start_page = int(saved)
                        if start_page < 1:
                            raise ValueError
                    except ValueError as error:
                        raise CommandError("Invalid import checkpoint; use --start-page explicitly") from error

        processed = 0
        try:
            for page in ContractRegistryParser().iter_pages(start_page=start_page):
                if page.eof:
                    break
                selected = page.records[:total - processed]
                # A partial page repeats next time with upserts, preserving the remainder.
                with transaction.atomic():
                    for item in selected:
                        supplier_bin = normalize_bin(item.get("supplier_bin"))
                        customer_bin = normalize_bin(item.get("customer_bin"))
                        signed = normalize_date(item.get("sign_date"))
                        number = item.get("contract_number")
                        if not signed or not isinstance(number, str) or not number.strip():
                            raise ValueError("invalid_contract_identity_or_date")
                        number = number.strip()
                        supplier, _ = Supplier.objects.get_or_create(
                            bin=supplier_bin, defaults={"name": item.get("supplier_name", "").strip()},
                        )
                        previous = Contract.objects.filter(contract_number=number).select_related("supplier").first()
                        if previous and previous.supplier.bin != supplier_bin:
                            raise ValueError("contract_supplier_identity_changed")
                        if (previous and previous.contract_gos_id and item.get("contract_gos_id")
                                and previous.contract_gos_id != item["contract_gos_id"]):
                            raise ValueError("contract_external_identity_changed")
                        Contract.objects.update_or_create(
                            contract_number=number,
                            defaults={
                                "supplier": supplier, "tender_id": item.get("purchase_number") or "",
                                "contract_gos_id": item.get("contract_gos_id"),
                                "title": item.get("subject") or "",
                                "amount": normalize_amount(item.get("amount")),
                                "customer_name": item.get("customer_name") or "", "customer_bin": customer_bin,
                                "contract_date": signed,
                            },
                        )
                    next_page = page.number + 1 if len(selected) == len(page.records) else page.number
                    SystemSetting.objects.update_or_create(key=checkpoint_key, defaults={"value": str(next_page)})
                    SystemSetting.objects.update_or_create(key="last_import", defaults={"value": timezone.now().isoformat()})
                processed += len(selected)
                logger.info("Imported page %d: %d records; checkpoint=%d", page.number, len(selected), next_page)
                if processed >= total:
                    break
        except (SourceError, ValueError) as error:
            code = error.code if isinstance(error, SourceError) else "invalid_import_data"
            raise CommandError(f"Import stopped: {code}; uncommitted page will be retried") from error
        except Exception as error:
            raise CommandError("Import stopped: page_save_failed; uncommitted page will be retried") from error

        self.stdout.write(f"Imported {processed} contracts")
        if not processed:
            return
        call_command("enrich_suppliers", days=7)
        # Name-only reconciliation can merge unrelated people. It remains explicit
        # until evidence-based identity resolution is introduced in phase 2.
        call_command("build_clusters")
