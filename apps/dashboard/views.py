from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.paginator import Paginator
from django.db.models import Sum, Q, Prefetch
from django.http import JsonResponse
from django.urls import reverse
from django.utils.html import format_html
from django.views.generic import TemplateView

from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.graph.models import RiskCluster
from apps.owners.querysets import current_roles


class DashboardView(TemplateView):
    template_name = "dashboard/index.html"

    def get(self, request, *args, **kwargs):
        if request.GET.get('format') == 'json':
            q = request.GET.get('q', '').strip()
            contracts_list = Contract.objects.select_related("supplier").order_by("-contract_date")

            if q:
                contracts_list = contracts_list.filter(
                    Q(contract_number__icontains=q) |
                    Q(title__icontains=q) |
                    Q(supplier__name__icontains=q) |
                    Q(customer_name__icontains=q)
                )

            rows = []

            for c in contracts_list[:50]:
                if c.contract_gos_id:
                    number_html = format_html(
                        '<a href="{}" target="_blank" rel="noopener noreferrer" '
                        'class="text-info text-decoration-none fw-bold">{} '
                        '<i class="bi bi-box-arrow-up-right" style="font-size:0.75em;"></i></a>',
                        c.goszakup_url, c.contract_number,
                    )
                else:
                    number_html = format_html('<span class="text-muted">{}</span>', c.contract_number)

                rows.append({
                    'number_html': number_html,
                    'title': c.title[:40] + ('…' if len(c.title) > 40 else ''),
                    'supplier_name': c.supplier.name[:35],
                    'supplier_url': reverse('companies:detail', args=[c.supplier.pk]),
                    'customer': c.customer_name[:30] + ('…' if len(c.customer_name) > 30 else ''),
                    'amount': intcomma(c.amount),
                    'date': str(c.contract_date),
                })

            return JsonResponse({'results': rows, 'total': len(rows)})

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["supplier_count"] = Supplier.objects.filter(is_supplier=True).count()
        context["contract_count"] = Contract.objects.count()
        active_clusters = RiskCluster.objects.filter(is_active=True)
        context["cluster_count"] = active_clusters.count()

        context["money_at_risk"] = (
                active_clusters.aggregate(
                    total=Sum("total_contract_amount")
                )["total"]
                or 0
        )

        context["top_clusters"] = (
            active_clusters
            .order_by("-risk_score")[:5]
        )

        suppliers_in_clusters = (
            Supplier.objects
            .filter(risk_clusters__is_active=True)
            .distinct()
            .prefetch_related(Prefetch('directorships', queryset=current_roles()), Prefetch(
                'risk_clusters', queryset=active_clusters.order_by('-risk_score'), to_attr='active_clusters',
            ))
            .order_by('-risk_score')[:5]
        )

        for s in suppliers_in_clusters:
            s.primary_cluster = next(iter(s.active_clusters), None)

        context["short_suppliers"] = suppliers_in_clusters

        contracts_list = (
            Contract.objects
            .select_related("supplier")
            .order_by("-contract_date")
        )

        q = self.request.GET.get('q', '').strip()
        if q:
            contracts_list = contracts_list.filter(
                Q(contract_number__icontains=q) |
                Q(title__icontains=q) |
                Q(supplier__name__icontains=q) |
                Q(customer_name__icontains=q)
            )

        page_number = self.request.GET.get('page', 1)
        paginator = Paginator(contracts_list, 15)
        page_obj = paginator.get_page(page_number)

        context["latest_contracts"] = page_obj
        context["page_obj"] = page_obj
        context["is_paginated"] = page_obj.has_other_pages()
        context["q"] = q

        return context
