from django.contrib import admin

from .models import Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "bin",
        "region",
        "city",
        "phone",
        "risk_score",
        "created_at",
    )

    search_fields = (
        "name",
        "bin",
        "phone",
        "email",
    )

    list_filter = (
        "region",
        "city",
        "risk_score",
        "created_at",
    )

    ordering = (
        "name",
    )
