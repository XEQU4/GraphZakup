from apps.ingestion.management.commands.ingest_data import Command as IngestionCommand


class Command(IngestionCommand):
    help = 'Совместимый вход в ingestion (new = initial; full ничего не удаляет)'
