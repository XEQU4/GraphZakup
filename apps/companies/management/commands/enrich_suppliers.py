from apps.ingestion.management.commands.ingest_data import Command as IngestionCommand


class Command(IngestionCommand):
    help = 'Enrich companies through shared ingestion without scanning contracts'

    def handle(self, *args, **options):
        options['mode'] = 'enrich'
        return super().handle(*args, **options)
