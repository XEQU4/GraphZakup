import logging
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.core.models import SystemSetting
from services.contract_registry_parser import ContractRegistryParser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import contracts from goszakup.gov.kz registry"

    def add_arguments(self, parser):
        parser.add_argument("--total",      type=int, default=500,  help="Сколько контрактов скачать")
        parser.add_argument("--mode",       choices=["new", "full"], default="new")
        parser.add_argument("--start-page", type=int, default=1,    help="С какой страницы начинать")

    def handle(self, *args, **options):
        total      = options["total"]
        mode       = options["mode"]
        start_page = options["start_page"]

        if mode == "full":
            logger.warning("FULL MODE: удаляем все контракты и поставщиков...")
            Contract.objects.all().delete()
            Supplier.objects.all().delete()

        if mode == "new" and start_page == 1:
            try:
                last_page_obj = SystemSetting.objects.get(key="last_import_page")
                start_page = int(last_page_obj.value)
                logger.info("Продолжаем с last_import_page=%d", start_page)
            except (SystemSetting.DoesNotExist, ValueError):
                start_page = 1

        logger.info("Импорт контрактов: total=%d, mode=%s, start_page=%d", total, mode, start_page)

        client    = ContractRegistryParser()
        contracts = client.search_contracts_paginated(total=total, start_page=start_page)
        logger.info("Получено %d контрактов от парсера", len(contracts))

        created_suppliers = created_contracts = updated_contracts = skipped = 0

        for item in contracts:
            supplier_bin = item.get("supplier_bin")
            if not supplier_bin:
                logger.debug("Пропуск %s: нет BIN поставщика", item.get("contract_number"))
                skipped += 1
                continue
            if not item.get("sign_date"):
                skipped += 1
                continue

            supplier_bin = str(supplier_bin).strip()
            supplier, supplier_created = Supplier.objects.get_or_create(
                bin=supplier_bin,
                defaults={"name": item.get("supplier_name", "").strip()},
            )
            if supplier_created:
                created_suppliers += 1

            try:
                _, contract_created = Contract.objects.update_or_create(
                    contract_number=item.get("contract_number"),
                    defaults={
                        "supplier":        supplier,
                        "tender_id":       item.get("purchase_number") or "",
                        "contract_gos_id": item.get("contract_gos_id"),
                        "title":           item.get("subject") or "",
                        "amount":          Decimal(str(item.get("amount") or 0)),
                        "customer_name":   item.get("customer_name") or "",
                        "customer_bin":    item.get("customer_bin") or "",
                        "contract_date":   item.get("sign_date"),
                    },
                )
                if contract_created:
                    created_contracts += 1
                else:
                    updated_contracts += 1
            except Exception:
                logger.exception("DB Error при сохранении контракта %s", item.get("contract_number"))
                skipped += 1

        pages_fetched = max(1, (len(contracts) + 49) // 50)
        next_page     = start_page + pages_fetched
        SystemSetting.objects.update_or_create(key="last_import_page", defaults={"value": str(next_page)})
        SystemSetting.objects.update_or_create(key="last_import",      defaults={"value": timezone.now().isoformat()})

        logger.info(
            "Импорт завершён: поставщиков +%d, контрактов +%d, обновлено %d, пропущено %d, next_page=%d",
            created_suppliers, created_contracts, updated_contracts, skipped, next_page,
        )

        logger.info("Запуск enrich_suppliers...")
        call_command("enrich_suppliers", days=7)

        logger.info("Запуск link_directors...")
        call_command("link_directors")

        logger.info("Запуск build_clusters...")
        call_command("build_clusters")

        logger.info("Пайплайн завершён.")
