from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.owners.models import Director


class Command(BaseCommand):
    """
    Команда import_contracts --mode full стирает Supplier и Contract,
    но не трогает Director/Directorship. Если до этого уже были связи
    Directorship на удалённые Supplier (через on_delete=CASCADE они тоже
    удаляются), у Director может остаться 0 directorships — "осиротевшая"
    запись без единой компании.

    Эта команда находит и удаляет таких "осиротевших" директоров.
    Безопасна для повторного запуска.
    """

    help = "Remove Director records with zero linked companies"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only show what would be deleted, without deleting",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        orphans = Director.objects.annotate(
            companies_count=Count("directorships")
        ).filter(companies_count=0)

        count = orphans.count()

        if dry_run:
            self.stdout.write(f"Would delete {count} orphaned directors (dry run, nothing deleted)")
            return

        self.stdout.write(f"Deleting {count} orphaned directors (0 companies)...")
        orphans.delete()
        self.stdout.write(self.style.SUCCESS("Done."))
