from apps.ingestion.management.commands.ingest_data import Command as IngestionCommand


class Command(IngestionCommand):
    help = 'Обогащение компаний через общий ingestion без обхода договоров'

    def handle(self, *args, **options):
        options['mode'] = 'enrich'
        return super().handle(*args, **options)
