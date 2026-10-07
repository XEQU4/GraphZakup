"""Explicit saved-data analysis; model calls require --use-model and a worker."""
from django.core.management.base import BaseCommand, CommandError
from apps.graph.models import RiskCluster
from apps.ingestion.leases import RunLease, IngestionBusy
from apps.ai.services import prepare_analysis
from apps.ai.jobs import request_analysis
from apps.ai.providers import ProviderError


class Command(BaseCommand):
    help = 'Prepare versioned analysis/templates from saved graphs, or enqueue explicit model jobs.'

    def add_arguments(self, parser):
        parser.add_argument('--cluster', action='append', help='Select a stable group UUID; repeat to select several.')
        parser.add_argument('--use-model', action='store_true', help='Enqueue configured generation through Celery.')
        parser.add_argument('--retry-model', action='store_true', help='Explicitly retry a saved model fallback.')

    def handle(self, *args, **options):
        groups = RiskCluster.objects.filter(is_active=True, current_snapshot__state='active').order_by('pk')
        if options['cluster']:
            try:
                from uuid import UUID
                selected = {UUID(value) for value in options['cluster']}
            except ValueError:
                raise CommandError('Invalid group UUID.') from None
            groups = groups.filter(uuid__in=selected)
            if groups.count() != len(selected):
                raise CommandError('A selected group has no active saved graph.')
        if options['use_model']:
            for group in groups:
                try:
                    job, created = request_analysis(None, group.pk, retry_model=options['retry_model'])
                except (ValueError, ProviderError) as error:
                    raise CommandError(str(error)) from None
                self.stdout.write(f'Job {job.uuid}: {job.status}; created={created}')
            return
        try:
            lease = RunLease.acquire()
        except IngestionBusy:
            raise CommandError('Ingestion or graph publication is busy; try again later.') from None
        try:
            from django.db import transaction
            with transaction.atomic():
                count = created = 0
                for group in groups:
                    _, added = prepare_analysis(group.pk)
                    count += 1
                    created += int(added)
                lease.ensure_owned()
            self.stdout.write(f'Analysed {count} groups; new analysis versions: {created}. No model requests.')
        finally:
            lease.release()
