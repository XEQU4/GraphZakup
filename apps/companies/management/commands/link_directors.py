from django.core.management.base import BaseCommand

from apps.companies.models import Supplier
from apps.owners.models import Director, Directorship


class Command(BaseCommand):
    """
    enrich_suppliers (adata.kz) заполняет Supplier.director_name строкой,
    но никогда не создаёт связь Director <-> Supplier через Directorship —
    из-за этого список компаний и страница владельца оставались пустыми.

    Эта команда проходит по всем поставщикам с непустым director_name и
    создаёт/находит Director с таким же ФИО, затем создаёт Directorship.

    ВАЖНО: adata.kz не отдаёт ИИН директора, только ФИО — поэтому
    сопоставление идёт по точному совпадению full_name. Это не идеально
    (два разных человека с одинаковым ФИО склеятся в одного Director),
    но это лучшее, что можно сделать без ИИН в исходных данных.
    """

    help = "Link Supplier.director_name to Director/Directorship records"

    def handle(self, *args, **options):
        suppliers = Supplier.objects.exclude(
            director_name=""
        ).exclude(
            director_name__isnull=True
        )

        total = suppliers.count()
        self.stdout.write(f"Found {total} suppliers with director_name")

        created_directors = 0
        created_links = 0
        already_linked = 0

        for supplier in suppliers:
            full_name = supplier.director_name.strip()
            if not full_name:
                continue

            director, director_created = Director.objects.get_or_create(
                full_name=full_name
            )
            if director_created:
                created_directors += 1

            _, link_created = Directorship.objects.get_or_create(
                supplier=supplier,
                director=director,
            )
            if link_created:
                created_links += 1
            else:
                already_linked += 1

        self.stdout.write(self.style.SUCCESS("\nLinking completed:"))
        self.stdout.write(f"  Directors created: {created_directors}")
        self.stdout.write(f"  Directorship links created: {created_links}")
        self.stdout.write(f"  Already linked: {already_linked}")
