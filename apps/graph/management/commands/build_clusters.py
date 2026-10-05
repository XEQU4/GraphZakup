from datetime import date

from django.core.management.base import BaseCommand

# Kept as imports for existing callers while implementation lives in a service.
from apps.graph.services import (
    build_director_map, calculate_risk, find_connected_groups, generate_cluster_name,
    get_connection_types, get_risk_weights, is_connected, rebuild_clusters,
)


class Command(BaseCommand):
    help = "Update affiliation clusters atomically while preserving identifiers and explanations"

    def add_arguments(self, parser):
        parser.add_argument("--as-of", type=date.fromisoformat,
                            help="Consider director roles on this ISO date; default is today")

    def handle(self, *args, **options):
        result = rebuild_clusters(as_of=options.get("as_of"))
        self.stdout.write(self.style.SUCCESS(
            "Analyzed {analyzed} suppliers; groups={groups}, created={created}, "
            "updated={updated}, unchanged={unchanged}, retired={retired}".format(**result)
        ))
