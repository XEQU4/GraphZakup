from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Name-only merging is disabled; ingestion creates roles from observations'

    def handle(self, *args, **options):
        raise CommandError('Name-only merging is disabled. Use ingest_data --mode=enrich; '
                           'migrations isolate legacy roles and preserve original records in history.')
