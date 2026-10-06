from django.core.management.base import BaseCommand, CommandError
from apps.ingestion.leases import IngestionBusy
from apps.ingestion.models import IngestionRun
from apps.ingestion.services import IngestionFailure, run_pipeline


class Command(BaseCommand):
    help = 'Initial collection, updates or enrichment with saved progress'

    def add_arguments(self, parser):
        parser.add_argument('--mode', choices=['initial', 'new', 'update', 'full', 'enrich', 'kgd'], default='initial')
        parser.add_argument('--total', type=int, default=500)
        parser.add_argument('--start-page', type=int)
        parser.add_argument('--force', action='store_true')
        parser.add_argument('--days', type=int, default=7)
        parser.add_argument('--resume', help='Run UUID; retains the saved mode and parameters')
        parser.add_argument('--company-bin', help='KGD: check one existing company by its 12-digit BIN')
        parser.add_argument('--kgd-service', choices=['taxpayer', 'tax_debt'], help='KGD: registration or registration plus arrears')

    def handle(self, *args, **options):
        try:
            run = run_pipeline(**{key: options[key] for key in (
                'mode', 'total', 'start_page', 'force', 'days', 'resume', 'company_bin', 'kgd_service')})
        except (IngestionFailure, IngestionBusy) as error:
            raise CommandError(str(error)) from None
        except (ValueError, TypeError):
            raise CommandError('invalid_ingestion_options') from None
        except IngestionRun.DoesNotExist:
            raise CommandError('ingestion_run_not_found') from None
        self.stdout.write(f'run={run.uuid}; status={run.status}; stage={run.stage}; '
                          f'page={run.next_page}; offset={run.offset}; counters={run.counters}')
