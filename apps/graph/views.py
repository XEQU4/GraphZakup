from collections import defaultdict
import json
import re

from django.db.models import prefetch_related_objects, Prefetch, Case, When, F, Value, IntegerField
from django.db.models.functions import Cast, Coalesce
from django.http import HttpResponseBadRequest, JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.utils import timezone
from django.views.generic import ListView, DetailView

from apps.core.mixins import ClampedPaginationMixin
from .models import RiskCluster, GraphSnapshot, GraphRebuildJob
from .view_states import saved_view, save_view, ViewConflict
from .jobs import request_rebuild
from apps.owners.models import Directorship, Ownership
from .services import analysis_fingerprint, build_director_map, get_connection_types, get_risk_weights


def build_graph_data(suppliers, cluster=None):
    """
    Legacy pair projection retained for old callers; pages use saved evidence.

    Node risk is the score of the currently viewed cluster.
    Without an explicit cluster, average active-cluster scores for each supplier;
    an explicitly supplied cluster takes precedence.
    """
    nodes = []
    links = []
    supplier_list = list(suppliers)
    prefetch_related_objects(supplier_list, "directorships__director", "directorships__person_identity", "directorships__source_observation")
    director_map = build_director_map(supplier_list)
    if cluster is None:
        prefetch_related_objects(supplier_list, "risk_clusters")

    for supplier in supplier_list:
        if cluster is not None:
            node_risk = cluster.risk_score
        else:
            clusters = [item.risk_score for item in supplier.risk_clusters.all() if item.is_active]
            node_risk = round(sum(clusters) / len(clusters)) if clusters else 0

        nodes.append({
            "id":   supplier.id,
            "name": supplier.name,
            "risk": node_risk,
        })

    pair_links = defaultdict(list)

    for i, s1 in enumerate(supplier_list):
        for s2 in supplier_list[i + 1:]:
            pair_key = tuple(sorted((s1.id, s2.id)))

            for director_id in sorted(director_map[s1.pk] & director_map[s2.pk]):
                pair_links[pair_key].append({"source": s1.id, "target": s2.id,
                                             "type": "director", "director_id": director_id})
            for kind in sorted(get_connection_types(s1, s2, director_map) - {"director"}):
                pair_links[pair_key].append({"source": s1.id, "target": s2.id, "type": kind})

    for pair_key, pair_link_list in pair_links.items():
        total = len(pair_link_list)
        for idx, link in enumerate(pair_link_list):
            link["curve_index"] = idx
            link["curve_total"] = total
            links.append(link)

    return {"nodes": nodes, "links": links}


class ClusterListView(ClampedPaginationMixin, ListView):
    model = RiskCluster
    template_name = "clusters/list.html"
    context_object_name = "clusters"
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        raw = request.GET.get("risk", "").strip()
        try:
            self.minimum_risk = max(0, min(100, int(raw))) if raw else None
        except ValueError:
            return HttpResponseBadRequest("Score threshold must be an integer between 0 and 100.")
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            RiskCluster.objects
            .filter(is_active=True)
            .select_related('current_snapshot', 'analysis_state__analysis').prefetch_related('suppliers')
            .annotate(saved_review_priority=Case(
                When(analysis_state__analysis__graph_snapshot_id=F('current_snapshot_id'),
                     then=Cast('analysis_state__analysis__metrics__review_priority', IntegerField())),
                default=Value(None), output_field=IntegerField()))
            .alias(display_score=Coalesce('saved_review_priority', 'risk_score', output_field=IntegerField()))
            .order_by(F('saved_review_priority').desc(nulls_last=True), '-risk_score')
        )
        min_risk = getattr(self, "minimum_risk", None)
        if min_risk is not None:
            qs = qs.filter(display_score__gte=min_risk)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for cluster in context["clusters"]:
            cluster.connection_types = {edge['type'] for edge in cluster.current_snapshot.payload['links']} if cluster.current_snapshot else set()
            cluster.saved_review_analysis = cluster.analysis_state.analysis if cluster.saved_review_priority is not None else None
        return context


class ClusterDetailView(DetailView):
    model = RiskCluster
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    template_name = "clusters/detail.html"

    def get_queryset(self):
        return super().get_queryset().select_related('current_snapshot').prefetch_related(
            Prefetch('suppliers__directorships', queryset=Directorship.objects.select_related(
                'director', 'person_identity', 'source_observation')),
            Prefetch('suppliers__ownerships', queryset=Ownership.objects.select_related('owner')),
            'suppliers__contracts',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cluster = self.object
        suppliers = list(cluster.suppliers.all())
        snapshot = selected_snapshot(self.request, cluster)
        graph_data = snapshot.payload if snapshot else {'nodes': [], 'links': []}
        context["graph_data"] = graph_data
        context['snapshot'] = snapshot
        context['versions'] = list(cluster.snapshots.only('id', 'version', 'state', 'as_of', 'created_at', 'changes'))
        context['transitions'] = list(snapshot.incoming_transitions.select_related('source__cluster')) if snapshot else []
        context['graph_options'] = {
            'cluster_id': str(cluster.uuid), 'snapshot_id': snapshot.pk if snapshot else None,
            'version': snapshot.version if snapshot else None, 'graph_hash': snapshot.graph_hash if snapshot else None,
            'view': saved_view(self.request.user, cluster, snapshot),
            'authenticated': self.request.user.is_authenticated,
            'historical': snapshot is not None and snapshot.pk != cluster.current_snapshot_id,
        }

        current_fingerprint = analysis_fingerprint(suppliers, get_risk_weights(), timezone.localdate())
        context["explanation_stale"] = cluster.explanation_stale or current_fingerprint != cluster.analysis_fingerprint
        historical = snapshot and snapshot.pk != cluster.current_snapshot_id
        text = snapshot.legacy_explanation if historical else cluster.ai_explanation
        context['explanation_stale'] = context['explanation_stale'] or bool(historical)
        context["ai_explanation_html"] = self._linkify_explanation(text or "Explanation has not been prepared yet.", suppliers)
        from apps.ai.services import saved_analysis
        analysis, explanation, stale = saved_analysis(cluster, snapshot)
        context['analysis'], context['saved_explanation'] = analysis, explanation
        context['analysis_stale'] = stale
        if analysis and explanation:
            context['ai_explanation_html'] = self._linkify_explanation(explanation.text, suppliers)
            # Render the stored document, never reconstruct historical text on GET.
            from apps.ai.presentation import DOCUMENT_VERSION
            document = explanation.presentation.get('document')
            if document and document.get('version') == DOCUMENT_VERSION:
                context['explanation_document'] = document
            context['explanation_stale'] = stale
            context['analysis_versions'] = list(snapshot.analyses.values('version', 'created_at'))
        return context

    @staticmethod
    def _linkify_explanation(text, suppliers):
        from django.utils.html import escape, format_html
        from django.urls import reverse

        tokens, entity_targets = {}, defaultdict(set)
        for supplier in suppliers:
            entity_targets[f"«{supplier.name}»"].add(reverse("companies:detail", args=[supplier.pk]))
        for supplier in suppliers:
            for ds in supplier.directorships.all():
                entity_targets[ds.director.full_name].add(reverse("owners:detail", args=[ds.director.pk]))
        for label, urls in entity_targets.items():
            if label and len(urls) == 1:
                tokens[label] = format_html('<a href="{}" class="text-info">{}</a>', next(iter(urls)), label)
        if not tokens:
            return escape(text)
        pattern = re.compile("|".join(re.escape(label) for label in sorted(tokens, key=lambda item: (-len(item), item))))
        chunks, position = [], 0
        for match in pattern.finditer(text):
            chunks.extend([str(escape(text[position:match.start()])), str(tokens[match.group()])])
            position = match.end()
        chunks.append(str(escape(text[position:])))
        from django.utils.safestring import mark_safe
        return mark_safe("".join(chunks))


def selected_snapshot(request, cluster):
    raw = request.GET.get('version')
    if raw is None:
        return cluster.current_snapshot
    if not raw.isascii() or not raw.isdecimal() or len(raw) > 9 or int(raw) < 1:
        raise Http404('Unknown graph version.')
    return get_object_or_404(GraphSnapshot, cluster=cluster, version=int(raw))


@require_GET
def graph_data(request, uuid):
    cluster = get_object_or_404(RiskCluster.objects.select_related('current_snapshot'), uuid=uuid)
    snapshot = selected_snapshot(request, cluster)
    return JsonResponse({'cluster': str(cluster.uuid), 'version': snapshot.version if snapshot else None,
                         'graph_hash': snapshot.graph_hash if snapshot else None,
                         'state': snapshot.state if snapshot else 'not_calculated',
                         'graph': snapshot.payload if snapshot else {'nodes': [], 'links': []}})


@require_http_methods(['GET', 'POST'])
def graph_view(request, uuid):
    cluster = get_object_or_404(RiskCluster.objects.select_related('current_snapshot'), uuid=uuid)
    if request.method == 'GET':
        return JsonResponse(saved_view(request.user, cluster, selected_snapshot(request, cluster)))
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'authentication_required'}, status=403)
    try:
        data = json.loads(request.body) if len(request.body) <= 2_000_000 else None
        if not isinstance(data, dict) or set(data) != {'snapshot_id', 'graph_hash', 'revision', 'payload'}:
            raise ValidationError('Invalid request fields.')
        if type(data['snapshot_id']) is not int or type(data['revision']) is not int or data['revision'] < 0:
            raise ValidationError('Invalid version identifiers.')
        result = save_view(request.user, cluster.pk, data['snapshot_id'], data['graph_hash'], data['revision'], data['payload'])
        return JsonResponse(result)
    except ViewConflict as error:
        return JsonResponse({'error': 'view_conflict', 'message': str(error)}, status=409)
    except (ValueError, ValidationError):
        return JsonResponse({'error': 'invalid_view'}, status=400)


@require_POST
def graph_rebuild(request, uuid):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'staff_required'}, status=403)
    cluster = get_object_or_404(RiskCluster, uuid=uuid)
    try:
        job, created = request_rebuild(request.user, list(cluster.suppliers.values_list('pk', flat=True)))
    except ValueError as error:
        return JsonResponse({'error': 'invalid_selection', 'message': str(error)}, status=400)
    from django.urls import reverse
    return JsonResponse({'job': str(job.uuid), 'status': job.status, 'created': created,
                         'url': reverse('graph:job_status', args=[job.uuid])}, status=202)


@require_GET
def job_status(request, uuid):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'staff_required'}, status=403)
    job = get_object_or_404(GraphRebuildJob, uuid=uuid)
    return JsonResponse({'job': str(job.uuid), 'status': job.status, 'summary': job.summary, 'error': job.error_code})
