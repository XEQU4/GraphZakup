from datetime import timedelta
from time import sleep

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.companies.models import Supplier
from services.enricher import enrich_supplier


class Command(BaseCommand):
    help = "Enrich suppliers from Adata + eGov"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update all suppliers"
        )

        parser.add_argument(
            "--days",
            type=int,
            help="Update suppliers older than N days"
        )

    def handle(self, *args, **options):
        force = options["force"]
        days = options["days"]

        if force:
            suppliers = Supplier.objects.all()

        elif days:
            cutoff = timezone.now() - timedelta(days=days)

            suppliers = Supplier.objects.filter(
                Q(adata_updated_at__isnull=True)
                |
                Q(adata_updated_at__lt=cutoff)
            )

        else:
            suppliers = Supplier.objects.filter(
                adata_updated_at__isnull=True
            )

        total = suppliers.count()

        self.stdout.write(
            f"Found {total} suppliers to process"
        )

        updated = 0
        not_found = 0
        skipped = 0

        for index, supplier in enumerate(
                suppliers,
                start=1
        ):
            self.stdout.write(
                f"[{index}/{total}] {supplier.bin}"
            )

            try:
                data = enrich_supplier(
                    supplier.bin
                )

            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(
                        f"Error: {e}"
                    )
                )

                skipped += 1
                continue

            if not data:
                supplier.adata_updated_at = (
                    timezone.now()
                )

                supplier.save(
                    update_fields=[
                        "adata_updated_at"
                    ]
                )

                not_found += 1
                continue

            supplier.name = (
                    data.get("name")
                    or supplier.name
            )

            supplier.director_name = (
                    data.get("director_name")
                    or supplier.director_name
            )

            supplier.address = (
                    data.get("address")
                    or supplier.address
            )

            supplier.region = (
                    data.get("region")
                    or supplier.region
            )

            supplier.city = (
                    data.get("city")
                    or supplier.city
            )

            supplier.phone = (
                    data.get("phone")
                    or supplier.phone
            )

            supplier.email = (
                    data.get("email")
                    or supplier.email
            )

            supplier.oked = (
                    data.get("oked")
                    or supplier.oked
            )

            supplier.company_status = (
                    data.get("company_status")
                    or supplier.company_status
            )

            supplier.registration_date = (
                    data.get("registration_date")
                    or supplier.registration_date
            )

            supplier.resident_status = (
                    data.get("resident_status")
                    or supplier.resident_status
            )

            supplier.company_size = (
                    data.get("company_size")
                    or supplier.company_size
            )

            supplier.kopf = (
                    data.get("kopf")
                    or supplier.kopf
            )

            supplier.economic_sector = (
                    data.get("economic_sector")
                    or supplier.economic_sector
            )

            supplier.website = (
                    data.get("website")
                    or supplier.website
            )

            supplier.adata_updated_at = (
                timezone.now()
            )

            supplier.save(
                update_fields=[
                    "name",
                    "director_name",
                    "address",
                    "region",
                    "city",
                    "phone",
                    "email",
                    "oked",
                    "company_status",
                    "registration_date",

                    "resident_status",
                    "company_size",
                    "kopf",
                    "economic_sector",
                    "website",

                    "adata_updated_at",
                ]
            )

            updated += 1

            sleep(0.3)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Enrichment completed"
            )
        )

        self.stdout.write(
            f"Updated: {updated}"
        )

        self.stdout.write(
            f"Not found: {not_found}"
        )

        self.stdout.write(
            f"Skipped: {skipped}"
        )
