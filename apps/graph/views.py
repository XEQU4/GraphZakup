from collections import defaultdict

from django.views.generic import ListView, DetailView

from apps.core.mixins import ClampedPaginationMixin
from .models import RiskCluster

EXCLUDED_EMAILS = {"info@adata.kz", "support@adata.kz"}


def build_graph_data(suppliers, cluster=None):
    """
    Строит данные графа для D3.js.

    risk в узле = риск кластера, открытого в данный момент.
    Если поставщик входит в несколько кластеров — берём среднее по ним,
    но текущий кластер (cluster) всегда передаётся явно и берётся как основа.
    """
    nodes = []
    links = []
    seen_links = set()

    supplier_list = list(suppliers)

    for supplier in supplier_list:
        if cluster is not None:
            node_risk = cluster.risk_score
        else:
            clusters = list(supplier.risk_clusters.values_list("risk_score", flat=True))
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

            d1 = set(s1.directorships.values_list('director_id', flat=True))
            d2 = set(s2.directorships.values_list('director_id', flat=True))
            for d_id in d1 & d2:
                key = (s1.id, s2.id, "director", d_id)
                if key not in seen_links:
                    seen_links.add(key)
                    pair_links[pair_key].append({"source": s1.id, "target": s2.id, "type": "director"})

            if s1.address and s2.address and s1.address == s2.address:
                key = (s1.id, s2.id, "address")
                if key not in seen_links:
                    seen_links.add(key)
                    pair_links[pair_key].append({"source": s1.id, "target": s2.id, "type": "address"})

            if s1.phone and s2.phone and s1.phone == s2.phone:
                key = (s1.id, s2.id, "phone")
                if key not in seen_links:
                    seen_links.add(key)
                    pair_links[pair_key].append({"source": s1.id, "target": s2.id, "type": "phone"})

            if s1.email and s2.email and s1.email == s2.email:
                if s1.email not in EXCLUDED_EMAILS:
                    key = (s1.id, s2.id, "email")
                    if key not in seen_links:
                        seen_links.add(key)
                        pair_links[pair_key].append({"source": s1.id, "target": s2.id, "type": "email"})

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

    def get_queryset(self):
        qs = (
            RiskCluster.objects
            .prefetch_related("suppliers__directorships__director")
            .order_by("-risk_score")
        )
        min_risk = self.request.GET.get("risk")
        if min_risk:
            qs = qs.filter(risk_score__gte=min_risk)
        return qs

    def get_context_data(self, **kwargs):
        from apps.graph.management.commands.build_clusters import (
            get_connection_types,
            build_director_map,
        )
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cluster = self.object
        suppliers = list(
            cluster.suppliers.prefetch_related('directorships__director').all()
        )
        graph_data = build_graph_data(suppliers, cluster=cluster)
        context["graph_data"] = graph_data

        if not cluster.ai_explanation:
            from apps.ai.explainer import explain_cluster
            cluster.ai_explanation = explain_cluster(cluster)
            cluster.save()

        context["ai_explanation_html"] = self._linkify_explanation(
            cluster.ai_explanation, suppliers
        )
        return context

    @staticmethod
    def _linkify_explanation(text, suppliers):
        from django.utils.html import escape, format_html
        from django.urls import reverse

        escaped = escape(text)
        for supplier in suppliers:
            quoted = f"«{escape(supplier.name)}»"
            if quoted in escaped:
                url = reverse("companies:detail", args=[supplier.pk])
                link = format_html('<a href="{}" class="text-info">«{}»</a>', url, supplier.name)
                escaped = escaped.replace(quoted, link)

        seen_directors = {}
        for supplier in suppliers:
            for ds in supplier.directorships.all():
                seen_directors[ds.director.full_name] = ds.director.pk

        for full_name in sorted(seen_directors, key=len, reverse=True):
            escaped_name = escape(full_name)
            if escaped_name in escaped:
                url = reverse("owners:detail", args=[seen_directors[full_name]])
                link = format_html('<a href="{}" class="text-info">{}</a>', url, full_name)
                escaped = escaped.replace(escaped_name, str(link))

        from django.utils.safestring import mark_safe
        return mark_safe(escaped)
