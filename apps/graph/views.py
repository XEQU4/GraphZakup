from collections import defaultdict
import re

from django.db.models import prefetch_related_objects
from django.http import HttpResponseBadRequest
from django.utils import timezone
from django.views.generic import ListView, DetailView

from apps.core.mixins import ClampedPaginationMixin
from .models import RiskCluster
from .services import analysis_fingerprint, build_director_map, get_connection_types, get_risk_weights


def build_graph_data(suppliers, cluster=None):
    """
    Build graph data for D3.js.

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
            return HttpResponseBadRequest("Risk threshold must be an integer between 0 and 100.")
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            RiskCluster.objects
            .filter(is_active=True)
            .prefetch_related("suppliers__directorships__director", "suppliers__directorships__person_identity", "suppliers__directorships__source_observation")
            .order_by("-risk_score")
        )
        min_risk = getattr(self, "minimum_risk", None)
        if min_risk is not None:
            qs = qs.filter(risk_score__gte=min_risk)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for cluster in context["clusters"]:
            suppliers = list(cluster.suppliers.all())
            director_map = build_director_map(suppliers)
            types_found = set()
            for i, s1 in enumerate(suppliers):
                for s2 in suppliers[i + 1:]:
                    types_found |= get_connection_types(s1, s2, director_map)
            cluster.connection_types = types_found
        return context


class ClusterDetailView(DetailView):
    model = RiskCluster
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    template_name = "clusters/detail.html"

    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            "suppliers__directorships__director", "suppliers__directorships__person_identity",
            "suppliers__directorships__source_observation",
            "suppliers__ownerships__owner", "suppliers__contracts",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cluster = self.object
        suppliers = list(cluster.suppliers.all())
        graph_data = build_graph_data(suppliers, cluster=cluster)
        context["graph_data"] = graph_data

        current_fingerprint = analysis_fingerprint(suppliers, get_risk_weights(), timezone.localdate())
        context["explanation_stale"] = cluster.explanation_stale or current_fingerprint != cluster.analysis_fingerprint
        context["ai_explanation_html"] = self._linkify_explanation(
            cluster.ai_explanation or "Explanation has not been prepared yet.", suppliers
        )
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
