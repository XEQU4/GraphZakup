from django.contrib import admin

from .models import (
    Connection,
    RiskCluster,
    EvidenceEdge, GraphSnapshot, ClusterLineage, GraphRebuildJob,
)


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = (
        "source_supplier",
        "target_supplier",
        "connection_type",
        "weight",
        "created_at",
    )

    search_fields = (
        "source_supplier__name",
        "source_supplier__bin",
        "target_supplier__name",
        "target_supplier__bin",
    )

    list_filter = (
        "connection_type",
        "created_at",
    )


@admin.register(RiskCluster)
class RiskClusterAdmin(admin.ModelAdmin):
    readonly_fields = ('uuid', 'current_snapshot', 'analysis_fingerprint', 'last_analyzed_at',
                       'explanation_stale', 'is_active', 'risk_score', 'total_contract_amount', 'suppliers')
    list_display = (
        "name",
        "risk_score",
        "total_contract_amount",
        "created_at",
    )

    search_fields = (
        "name",
        "uuid",
    )

    list_filter = (
        "risk_score",
        "created_at",
    )

    def has_delete_permission(self, request, obj=None):
        return False


class PublishedReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GraphSnapshot)
class GraphSnapshotAdmin(PublishedReadOnlyAdmin):
    list_display = ('cluster', 'version', 'state', 'as_of', 'graph_hash', 'created_at')
    list_filter = ('state',)
    list_select_related = ('cluster',)


@admin.register(EvidenceEdge)
class EvidenceEdgeAdmin(PublishedReadOnlyAdmin):
    list_display = ('supplier', 'relationship_type', 'target_key', 'is_active')
    list_filter = ('relationship_type', 'is_active')
    list_select_related = ('supplier',)


@admin.register(ClusterLineage)
class ClusterLineageAdmin(PublishedReadOnlyAdmin):
    list_display = ('source', 'target', 'kind')


@admin.register(GraphRebuildJob)
class GraphRebuildJobAdmin(PublishedReadOnlyAdmin):
    list_display = ('uuid', 'status', 'error_code', 'created_at', 'finished_at')
    list_filter = ('status',)
