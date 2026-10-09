"""Run or inspect the same bounded collection service used by Celery beat."""
import json
from django.core.management.base import BaseCommand
from apps.ingestion.background import collection_status, run_background_cycle


class Command(BaseCommand):
    help = 'Run one enabled background cycle, or inspect the last completed cycle'

    def add_arguments(self, parser):
        parser.add_argument('--status', action='store_true')

    def handle(self, *args, **options):
        result = collection_status() if options['status'] else run_background_cycle()
        self.stdout.write(json.dumps(result, indent=2, default=str))
