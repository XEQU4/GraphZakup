from django.contrib import admin

from .models import Contract


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "supplier",
        "customer_name",
        "amount",
        "winner",
        "contract_date",
    )

    search_fields = (
        "title",
        "tender_id",
        "customer_name",
        "customer_bin",
        "supplier__name",
        "supplier__bin",
    )

    list_filter = (
        "winner",
        "contract_date",
    )

    ordering = (
        "-contract_date",
    )
