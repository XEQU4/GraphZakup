from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Объединение по ФИО отключено; роли формирует ingestion из наблюдений'

    def handle(self, *args, **options):
        raise CommandError('Объединение по ФИО отключено. Используйте ingest_data --mode=enrich; '
                           'старые роли изолируются миграцией, исходные записи сохраняются в истории.')
