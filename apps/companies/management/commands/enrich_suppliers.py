from datetime import timedelta
from time import sleep

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.companies.models import Supplier
from services.enricher import enrich_supplier
from services.normalizers import normalize_bin, normalize_date, normalize_email, normalize_phone


class Command(BaseCommand):
    help = "Enrich suppliers from the supplier registry and Adata"
    FIELDS = (
        "name", "director_name", "address", "region", "city", "phone", "email", "oked",
        "company_status", "registration_date", "resident_status", "company_size", "kopf",
        "economic_sector", "website",
    )

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Update all suppliers")
        parser.add_argument("--days", type=int, help="Update suppliers older than N days")

    def handle(self, *args, **options):
        if options["days"] is not None and options["days"] <= 0:
            raise CommandError("days must be positive")
        suppliers = Supplier.objects.order_by("pk")
        if not options["force"]:
            if options["days"]:
                cutoff = timezone.now() - timedelta(days=options["days"])
                suppliers = suppliers.filter(Q(adata_updated_at__isnull=True) | Q(adata_updated_at__lt=cutoff))
            else:
                suppliers = suppliers.filter(adata_updated_at__isnull=True)
        updated = not_found = failed = 0
        for supplier in suppliers.iterator():
            try:
                data = enrich_supplier(supplier.bin)
                if not data:
                    # An absent observation is not a successfully refreshed company.
                    not_found += 1
                    continue
                if normalize_bin(data.get("bin", supplier.bin)) != supplier.bin:
                    raise ValueError("enrichment_identity_mismatch")
                normalized = dict(data)
                normalized["registration_date"] = normalize_date(data.get("registration_date"))
                normalized["email"] = normalize_email(data.get("email"))
                normalized["phone"] = normalize_phone(data.get("phone"))
                with transaction.atomic():
                    changed = []
                    for field in self.FIELDS:
                        value = normalized.get(field)
                        if value is not None and value != "":
                            setattr(supplier, field, value)
                            changed.append(field)
                    if not data.get("_source_errors"):
                        supplier.adata_updated_at = timezone.now()
                        changed.append("adata_updated_at")
                    supplier.full_clean()
                    if changed:
                        changed.append("updated_at")
                        supplier.save(update_fields=changed)
                updated += 1
                if data.get("_source_errors"):
                    failed += 1
            except Exception:
                # Per-company errors do not abort other companies or expose raw values.
                failed += 1
                self.stderr.write(self.style.WARNING(f"Supplier {supplier.pk}: enrichment failed"))
            finally:
                sleep(0.3)
        self.stdout.write(f"Updated: {updated}; not found: {not_found}; failed: {failed}")
        if failed:
            raise CommandError("Enrichment incomplete; failed companies remain eligible for retry")
