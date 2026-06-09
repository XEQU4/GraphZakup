from django.contrib import admin

from .models import (
    Owner,
    Director,
    Ownership,
    Directorship,
    CourtCase,
    TaxDebt,
    Bankruptcy,
)


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "iin",
        "risk_score",
        "has_tax_debt",
        "has_court_cases",
        "is_bankrupt",
        "blacklisted",
    )

    search_fields = (
        "full_name",
        "iin",
    )

    list_filter = (
        "has_tax_debt",
        "has_court_cases",
        "is_bankrupt",
        "blacklisted",
    )


@admin.register(Director)
class DirectorAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "iin",
        "created_at",
    )

    search_fields = (
        "full_name",
        "iin",
    )

    list_filter = (
        "created_at",
    )


@admin.register(Ownership)
class OwnershipAdmin(admin.ModelAdmin):
    list_display = (
        "supplier",
        "owner",
        "share_percent",
        "created_at",
    )

    search_fields = (
        "supplier__name",
        "supplier__bin",
        "owner__full_name",
        "owner__iin",
    )

    list_filter = (
        "created_at",
    )


@admin.register(Directorship)
class DirectorshipAdmin(admin.ModelAdmin):
    list_display = (
        "supplier",
        "director",
        "start_date",
        "end_date",
    )

    search_fields = (
        "supplier__name",
        "supplier__bin",
        "director__full_name",
        "director__iin",
    )

    list_filter = (
        "start_date",
        "end_date",
    )


@admin.register(CourtCase)
class CourtCaseAdmin(admin.ModelAdmin):
    list_display = (
        "case_number",
        "owner",
        "role",
        "status",
        "decision_date",
    )

    search_fields = (
        "case_number",
        "owner__full_name",
        "owner__iin",
    )

    list_filter = (
        "status",
        "role",
        "decision_date",
    )


@admin.register(TaxDebt)
class TaxDebtAdmin(admin.ModelAdmin):
    list_display = (
        "owner",
        "amount",
        "source",
        "updated_at",
    )

    search_fields = (
        "owner__full_name",
        "owner__iin",
        "source",
    )

    list_filter = (
        "source",
        "updated_at",
    )


@admin.register(Bankruptcy)
class BankruptcyAdmin(admin.ModelAdmin):
    list_display = (
        "owner",
        "status",
        "started_at",
        "finished_at",
    )

    search_fields = (
        "owner__full_name",
        "owner__iin",
        "status",
    )

    list_filter = (
        "status",
        "started_at",
        "finished_at",
    )
