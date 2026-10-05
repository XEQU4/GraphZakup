from apps.ingestion.management.commands.ingest_data import Command as IngestionCommand


class Command(IngestionCommand):
    help = 'Compatible ingestion entry point (new = initial; full deletes nothing)'
