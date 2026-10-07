"""Legacy template/JSON compatibility endpoints; versioned clients use apps.api."""
import json

from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.graph.models import RiskCluster
from apps.graph.views import selected_snapshot
from .jobs import request_analysis
from .models import AnalysisJob, AnalysisSnapshot
from .providers import ProviderError
from .services import saved_analysis, historical_explanation


@require_POST
def start_analysis(request, uuid):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'staff_required'}, status=403)
    cluster = get_object_or_404(RiskCluster, uuid=uuid)
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body) if len(request.body) <= 2048 else None
            if not isinstance(data, dict) or set(data) - {'use_model', 'retry_model'}:
                raise ValueError('invalid_options')
        else:
            data = {'use_model': request.POST.get('use_model') == 'true',
                    'retry_model': request.POST.get('retry_model') == 'true'}
        job, created = request_analysis(request.user, cluster.pk, **data)
    except (ValueError, ProviderError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    url = reverse('ai:job_status', args=[job.uuid])
    if request.content_type != 'application/json':
        return redirect(url)
    return JsonResponse({'job': str(job.uuid), 'status': job.status, 'created': created, 'url': url}, status=202)


@require_GET
def job_status(request, uuid):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'staff_required'}, status=403)
    job = get_object_or_404(AnalysisJob.objects.select_related('analysis', 'explanation'), uuid=uuid)
    return JsonResponse({'job': str(job.uuid), 'status': job.status, 'error': job.error_code,
        'graph_snapshot_id': job.graph_snapshot_id, 'analysis_id': job.analysis_id,
        'analysis_version': job.analysis.version if job.analysis_id else None,
        'analysis_hash': job.analysis.analysis_hash if job.analysis_id else None,
        'explanation_id': job.explanation_id,
        'experimental_model_score': job.explanation.experimental_score if job.explanation_id else None})


@require_GET
def analysis_data(request, uuid):
    cluster = get_object_or_404(RiskCluster.objects.select_related('current_snapshot'), uuid=uuid)
    graph = selected_snapshot(request, cluster)
    analysis, explanation, stale = saved_analysis(cluster, graph)
    current_selected_analysis = analysis
    historical = bool(graph and graph.pk != cluster.current_snapshot_id)
    raw = request.GET.get('analysis_version')
    if raw is not None:
        if not raw.isascii() or not raw.isdecimal() or len(raw) > 9 or int(raw) < 1:
            raise Http404('Unknown analysis version.')
        analysis = get_object_or_404(AnalysisSnapshot.objects.select_related('graph_snapshot'),
                                    cluster=cluster, graph_snapshot=graph, version=int(raw))
        explanation = historical_explanation(analysis)
        historical = historical or not current_selected_analysis or analysis.pk != current_selected_analysis.pk
        stale = stale if not historical else False
    return JsonResponse({'cluster': str(cluster.uuid), 'graph_version': graph.version if graph else None,
        'status': 'not_calculated' if not analysis else 'stale' if stale else 'ready',
        'historical': historical,
        'analysis_version': analysis.version if analysis else None,
        'analysis_hash': analysis.analysis_hash if analysis else None,
        'analysis_as_of': str(analysis.as_of) if analysis else None,
        'created_at': analysis.created_at.isoformat() if analysis else None,
        'rules_version': analysis.rules_version if analysis else None,
        'metrics': analysis.metrics if analysis else {}, 'findings': analysis.findings if analysis else [],
        'limitations': analysis.limitations if analysis else [],
        'explanation': {'id': explanation.pk, 'text': explanation.text, 'language': explanation.language,
                        'document': explanation.presentation.get('document'),
                        'provider': explanation.provider, 'model': explanation.model,
                        'status': explanation.status} if explanation else None})
