from decimal import Decimal
from random import choice
from random import randint
from random import sample

from django.core.management.base import BaseCommand
from faker import Faker

from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.graph.models import (
    RiskCluster
)
from apps.graph.risk_engine import (
    calculate_cluster_risk
)
from apps.owners.models import (
    Owner,
    Director,
    Ownership,
    Directorship,
    TaxDebt,
    CourtCase
)

fake = Faker("ru_RU")


class Command(BaseCommand):
    help = "Generate demo AFM data"

    def handle(self, *args, **kwargs):

        self.stdout.write(
            self.style.SUCCESS(
                "Generating demo data..."
            )
        )

        Supplier.objects.all().delete()
        Owner.objects.all().delete()
        Director.objects.all().delete()

        owners = []
        directors = []

        for i in range(20):
            owner = Owner.objects.create(
                iin=f"9901{i:07}",
                full_name=fake.name(),
                has_tax_debt=(i % 4 == 0),
                has_court_cases=(i % 5 == 0),
                is_bankrupt=(i % 8 == 0),
            )

            owners.append(owner)

        for i in range(12):
            director = Director.objects.create(
                iin=f"8802{i:07}",
                full_name=fake.name()
            )

            directors.append(director)

        regions = [
            "Алматы",
            "Астана",
            "Шымкент",
            "Караганда",
            "Актобе"
        ]

        suspicious_addresses = [
            "г. Алматы, ул. Абая 100",
            "г. Астана, ул. Кабанбай Батыра 15",
            "г. Шымкент, ул. Тауке Хана 22",
        ]

        suppliers = []

        for i in range(50):
            supplier = Supplier.objects.create(
                bin=f"999{i:09}",
                name=f"ТОО Компания {i + 1}",
                address=fake.address(),
                phone=f"+7707{randint(1000000, 9999999)}",
                email=f"company{i}@mail.kz",
                region=choice(regions),
                city=choice(regions),
                risk_score=0,
            )

            suppliers.append(supplier)

            Ownership.objects.create(
                supplier=supplier,
                owner=choice(owners),
                share_percent=100
            )

            Directorship.objects.create(
                supplier=supplier,
                director=choice(directors)
            )

        cluster_suppliers = []

        for group_index in range(6):

            shared_director = choice(directors)
            shared_owner = choice(owners)
            shared_address = suspicious_addresses[
                group_index % len(
                    suspicious_addresses
                )
                ]

            group = sample(
                suppliers,
                4
            )

            for supplier in group:
                supplier.address = shared_address
                supplier.save()

                Ownership.objects.update_or_create(
                    supplier=supplier,
                    owner=shared_owner,
                    defaults={
                        "share_percent": 100
                    }
                )

                Directorship.objects.update_or_create(
                    supplier=supplier,
                    director=shared_director
                )

            cluster_suppliers.append(group)

        for supplier in suppliers:

            for contract_index in range(4):
                Contract.objects.create(
                    supplier=supplier,
                    tender_id=f"TENDER-{supplier.id}-{contract_index}",
                    title=f"Госзакупка №{contract_index}",
                    amount=Decimal(
                        randint(
                            1_000_000,
                            150_000_000
                        )
                    ),
                    winner=True,
                    contract_date=fake.date_this_decade(),
                    customer_name=f"ГУ Заказчик {randint(1, 20)}",
                    customer_bin=f"123{randint(100000000, 999999999)}",
                )

        for owner in Owner.objects.filter(
                has_tax_debt=True
        ):
            TaxDebt.objects.create(
                owner=owner,
                amount=Decimal(
                    randint(
                        500000,
                        5000000
                    )
                ),
                source="salyk.kz"
            )

        for owner in Owner.objects.filter(
                has_court_cases=True
        ):
            CourtCase.objects.create(
                owner=owner,
                case_number=f"CASE-{owner.id}",
                role="Ответчик",
                status="Завершено"
            )

        for index, group in enumerate(
                cluster_suppliers,
                start=1
        ):
            cluster = RiskCluster.objects.create(
                name=f"Подозрительная группа {index}"
            )

            cluster.suppliers.set(group)

            cluster.risk_score = (
                calculate_cluster_risk(
                    cluster
                )
            )

            cluster.save()

        self.stdout.write(
            self.style.SUCCESS(
                "Demo data generated."
            )
        )
