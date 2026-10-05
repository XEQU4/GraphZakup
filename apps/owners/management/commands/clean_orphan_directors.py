from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.owners.models import Director


class Command(BaseCommand):
    """Удаляет только записи без ролей и без защищённой истории идентичности."""

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
        ).filter(companies_count=0, personidentity__isnull=True)

        count = orphans.count()

        if dry_run:
            self.stdout.write(f"Would delete {count} orphaned directors (dry run, nothing deleted)")
            return

        self.stdout.write(f"Deleting {count} orphaned directors (0 companies)...")
        orphans.delete()
        self.stdout.write(self.style.SUCCESS("Done."))
