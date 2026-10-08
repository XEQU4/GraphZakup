"""Inspect saved data without collection or repair."""

import json

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.ingestion.quality import build_data_quality_report


class Command(BaseCommand):
    help = 'Read-only aggregate audit of saved provenance, freshness, duplicates and identity evidence'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help='Saved retrieval freshness window (1-3650 days)')

    def handle(self, *args, **options):
        if not 1 <= options['days'] <= 3650:
            raise CommandError('quality_days_must_be_between_1_and_3650')
        nested = connection.in_atomic_block
        with transaction.atomic():
            if connection.vendor == 'postgresql' and not nested:
                with connection.cursor() as cursor:
                    cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            report = build_data_quality_report(days=options['days'])
        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
