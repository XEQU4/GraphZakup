"""Bounded local-only explanation outbox; source collection never waits for inference."""
from datetime import timedelta

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from .jobs import enqueue, request_analysis
from .models import AnalysisJob, AnalysisState
from .providers import configuration, ProviderError, reuse_key


def schedule_explanations():
    if not settings.ENABLE_BACKGROUND_AI:
        return {'status': 'disabled', 'queued': 0}
    try:
        config = configuration()
    except ProviderError:
        return {'status': 'configuration_required', 'queued': 0}
    if config.provider != 'ollama':
        return {'status': 'local_provider_required', 'queued': 0}
    now = timezone.now()
    queued = 0
    # AnalysisJob is the durable outbox: broker loss does not lose the candidate.
    states = AnalysisState.objects.filter(cluster__current_snapshot_id=F('analysis__graph_snapshot_id'),
        analysis__graph_snapshot__state='active').select_related('analysis', 'explanation').order_by('updated_at', 'pk')
    for state in states:
        text = state.explanation
        if text.status == 'ready' and text.reuse_key == reuse_key(state.analysis, config):
            continue
        recent = AnalysisJob.objects.filter(graph_snapshot_id=state.analysis.graph_snapshot_id,
            options__provider='ollama').order_by('-created_at').first()
        if recent and recent.input_hash == state.analysis.input_hash:
            if recent.status in ('pending', 'running') and recent.created_at > now - timedelta(hours=1):
                # Pending messages may have been lost with Redis. A replay is idempotent.
                if recent.status == 'pending' and recent.created_at < now - timedelta(minutes=10):
                    enqueue(recent.pk, queue='iz2-ai')
                continue
            if recent.status in ('failed', 'fallback') and (recent.finished_at or recent.created_at) > now - timedelta(hours=6):
                continue
        job, created = request_analysis(None, state.cluster_id, use_model=True, retry_model=True, queue='iz2-ai')
        queued += int(created)
        if queued >= settings.BACKGROUND_AI_BATCH:
            break
    return {'status': 'enabled', 'queued': queued,
            'pending': AnalysisJob.objects.filter(status__in=['pending', 'running'], options__provider='ollama').count()}
