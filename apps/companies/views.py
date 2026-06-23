from django.db.models import Sum
from django.views.generic import DetailView, ListView
from django.db.models import Avg, Count, FloatField
from django.db.models.functions import Coalesce

from apps.core.mixins import ClampedPaginationMixin
from apps.owners.models import Directorship
from .models import Supplier

EXCLUDED_EMAILS = {"info@adata.kz", "support@adata.kz"}


class SupplierListView(ClampedPaginationMixin, ListView):
    model = Supplier
    template_name = "companies/list.html"
    context_object_name = "companies"
    paginate_by = 25

    def get_queryset(self):
        queryset = Supplier.objects.annotate(
            # Считаем общее количество контрактов
            contracts_count=Count('contracts', distinct=True),

            # Явно указываем output_field=FloatField(), чтобы подружить типы данных СУБД
            computed_risk=Coalesce(
                Avg('risk_clusters__risk_score'),
                'risk_score',
                output_field=FloatField()
            )
        ).prefetch_related('directorships__director')

        return queryset.order_by('-computed_risk')


class SupplierDetailView(DetailView):
    model = Supplier
    template_name = "companies/detail.html"
    context_object_name = "company"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.object

        # Контракты
        contracts = company.contracts.all().order_by("-contract_date")
        total_amount = contracts.aggregate(total=Sum("amount"))["total"] or 0

        # Директора через Directorship
        directorships = (
            Directorship.objects
            .filter(supplier=company)
            .select_related("director")
        )

        # Связанные компании через общего директора
        director_ids = list(
            directorships.values_list("director_id", flat=True)
        )
        related_by_director = Supplier.objects.none()
        if director_ids:
            related_by_director = (
                Supplier.objects
                .filter(directorships__director_id__in=director_ids)
                .exclude(pk=company.pk)
                .distinct()
            )

        # Связанные по адресу
        related_by_address = Supplier.objects.none()
        if company.address:
            related_by_address = (
                Supplier.objects
                .filter(address=company.address)
                .exclude(pk=company.pk)
            )

        # Связанные по телефону
        related_by_phone = Supplier.objects.none()
        if company.phone:
            related_by_phone = (
                Supplier.objects
                .filter(phone=company.phone)
                .exclude(pk=company.pk)
            )

        # Связанные по email
        related_by_email = Supplier.objects.none()
        if company.email and company.email.lower() not in EXCLUDED_EMAILS:
            related_by_email = (
                Supplier.objects
                .filter(email=company.email)
                .exclude(pk=company.pk)
            )

        # Аффилированные группы (RiskCluster)
        clusters = company.risk_clusters.all().order_by("-risk_score")

        # ── Расчет среднего значения риск-скора по всем кластерам ──
        if clusters.exists():
            total_risk = sum(cluster.risk_score for cluster in clusters)
            avg_risk_score = int(total_risk / clusters.count())
        else:
            # Если в кластерах не состоит, берем индивидуальный риск компании
            avg_risk_score = company.risk_score or 0

        # Динамический цвет на основе рассчитанного avg_risk_score
        # Пороги подстроены под логику отображения кластеров в шаблоне (80 и 50)
        if avg_risk_score >= 80:
            risk_color = "danger"
        elif avg_risk_score >= 50:
            risk_color = "warning text-dark"  # text-dark нужен для читаемости текста на желтом фоне
        elif avg_risk_score > 0:
            risk_color = "success"
        else:
            risk_color = "secondary"

        total_related = (
                related_by_director.count()
                + related_by_address.count()
                + related_by_phone.count()
                + related_by_email.count()
        )

        context.update({
            "contracts": contracts,
            "total_amount": total_amount,
            "directorships": directorships,
            "related_by_director": related_by_director,
            "related_by_address": related_by_address,
            "related_by_phone": related_by_phone,
            "related_by_email": related_by_email,
            "clusters": clusters,
            "avg_risk_score": avg_risk_score,  # Передаем средний риск в шаблон
            "risk_color": risk_color,  # Передаем вычисленный цвет плашки
            "total_related": total_related,
        })

        return context
