from django.core.management.base import BaseCommand
from apps.ingestion.models import IngestionRun


class Command(BaseCommand):
    help = 'Прогресс и безопасные коды ошибок последних запусков (без запросов к источникам)'

    def handle(self, *args, **options):
        for run in IngestionRun.objects.order_by('-started_at')[:20]:
            self.stdout.write(f'{run.uuid} {run.mode} {run.status} stage={run.stage} '
                              f'page={run.next_page} offset={run.offset} cursor={run.enrichment_cursor} '
                              f'error={run.error_code} counters={run.counters}')
            for issue in run.issues.filter(resolved=False).order_by('pk')[:20]:
                self.stdout.write(f'  issue={issue.pk} source={issue.source} stage={issue.stage} '
                                  f'page={issue.page} company={issue.supplier_id} code={issue.error_code}')
