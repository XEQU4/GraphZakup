from django.core.paginator import Paginator
from django.db.models import Sum
from django.views.generic import TemplateView

from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.graph.models import RiskCluster


class DashboardView(TemplateView):
    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Общая статистика
        context["supplier_count"] = Supplier.objects.count()
        context["contract_count"] = Contract.objects.count()
        context["cluster_count"] = RiskCluster.objects.count()

        context["money_at_risk"] = (
                RiskCluster.objects.aggregate(
                    total=Sum("total_contract_amount")
                )["total"]
                or 0
        )

        # 1. ТОП-5 опасных групп
        context["top_clusters"] = (
            RiskCluster.objects
            .order_by("-risk_score")[:5]
        )

        # 2. Компании в кластерах — с привязкой к кластеру для отображения номера/названия
        suppliers_in_clusters = (
            Supplier.objects
            .filter(risk_clusters__isnull=False)
            .distinct()
            .prefetch_related('directorships__director', 'risk_clusters')
            .order_by('-risk_score')[:5]
        )
        # Аннотируем каждую компанию её первым (наиболее опасным) кластером
        for s in suppliers_in_clusters:
            s.primary_cluster = s.risk_clusters.order_by('-risk_score').first()
        context["short_suppliers"] = suppliers_in_clusters

        # 3. Реестр контрактов с пагинацией
        contracts_list = (
            Contract.objects
            .select_related("supplier")
            .order_by("-contract_date")
        )

        page_number = self.request.GET.get('page', 1)
        paginator = Paginator(contracts_list, 15)
        page_obj = paginator.get_page(page_number)

        context["latest_contracts"] = page_obj
        context["page_obj"] = page_obj
        context["is_paginated"] = page_obj.has_other_pages()

        return context
