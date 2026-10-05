from django.contrib import admin
from .models import (IngestionRun, IngestionLease, SourceCheckpoint, SourceObservation,
                     IngestionIssue, SelectedFact, PersonSourceIdentity, IdentityCandidate)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IngestionRun)
class RunAdmin(ReadOnlyAdmin):
    list_display = ('uuid', 'mode', 'status', 'stage', 'next_page', 'offset', 'enrichment_cursor', 'error_code', 'started_at')
    list_filter = ('mode', 'status', 'stage')
    search_fields = ('uuid',)


@admin.register(IngestionIssue)
class IssueAdmin(ReadOnlyAdmin):
    list_display = ('run', 'source', 'stage', 'supplier_id', 'page', 'error_code', 'resolved', 'attempts')
    list_filter = ('resolved', 'stage', 'source')


@admin.register(SourceObservation)
class ObservationAdmin(ReadOnlyAdmin):
    list_display = ('id', 'run', 'source', 'supplier_id', 'status', 'parser_version', 'observed_at', 'from_cache')
    list_filter = ('source', 'status', 'from_cache')


@admin.register(IdentityCandidate)
class CandidateAdmin(ReadOnlyAdmin):
    list_display = ('left', 'right', 'reason', 'confidence', 'status', 'created_at')
    list_filter = ('status', 'reason')


for model in (IngestionLease, SourceCheckpoint, SelectedFact, PersonSourceIdentity):
    admin.site.register(model, ReadOnlyAdmin)
