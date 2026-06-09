from django.contrib import admin

from .models import (
    Connection,
    RiskCluster,
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

    filter_horizontal = (
        "suppliers",
    )
