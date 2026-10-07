from datetime import date

from django.core.management.base import BaseCommand

# Kept as imports for existing callers while implementation lives in a service.
from apps.graph.services import (
    build_director_map, calculate_risk, find_connected_groups, generate_cluster_name,
    get_connection_types, get_risk_weights, is_connected,
)
from apps.ai.services import refresh_graph_analysis as rebuild_clusters


class Command(BaseCommand):
    help = "Update affiliation clusters atomically while preserving identifiers and explanations"

    def add_arguments(self, parser):
        parser.add_argument("--as-of", type=date.fromisoformat,
                            help="Consider director roles on this ISO date; default is today")
        parser.add_argument('--company-id', type=int, action='append',
                            help='Limit publication to affected components; repeat for multiple companies')

    def handle(self, *args, **options):
        from apps.ingestion.leases import RunLease, IngestionBusy
        from django.core.management.base import CommandError
        try:
            lease = RunLease.acquire()
        except IngestionBusy as error:
            raise CommandError('Collection or graph recalculation is already running.') from error
        try:
            result = rebuild_clusters(as_of=options.get("as_of"), supplier_ids=options.get('company_id'),
                                      publication_guard=lease.ensure_owned)
        finally:
            lease.release()
        self.stdout.write(self.style.SUCCESS(
            "Analyzed {analyzed} suppliers; groups={groups}, created={created}, "
            "updated={updated}, unchanged={unchanged}, retired={retired}".format(**result)
        ))
