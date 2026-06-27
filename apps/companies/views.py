from django.db.models import Sum, Q, Avg, Count, FloatField
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.urls import reverse
from django.views.generic import DetailView, ListView

from apps.core.mixins import ClampedPaginationMixin
from apps.owners.models import Directorship
from .models import Supplier

EXCLUDED_EMAILS = {"info@adata.kz", "support@adata.kz"}


class SupplierListView(ClampedPaginationMixin, ListView):
    model = Supplier
    template_name = "companies/list.html"
    context_object_name = "companies"
    paginate_by = 25

    @staticmethod
    def _base_queryset():
        return Supplier.objects.annotate(
            contracts_count=Count('contracts', distinct=True),
            computed_risk=Coalesce(
                Avg('risk_clusters__risk_score'),
                'risk_score',
                output_field=FloatField()
            )
        ).prefetch_related('directorships__director')

    def get_queryset(self):
        qs = self._base_queryset()
        q = self.request.GET.get('q', '').strip()

        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(bin__icontains=q) |
                Q(directorships__director__full_name__icontains=q)
            ).distinct()

        return qs.order_by('-computed_risk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        return context

    def get(self, request, *args, **kwargs):
        if request.GET.get('format') == 'json':
            q = request.GET.get('q', '').strip()
            qs = self._base_queryset()

            if q:
                qs = qs.filter(
                    Q(name__icontains=q) |
                    Q(bin__icontains=q) |
                    Q(directorships__director__full_name__icontains=q)
                ).distinct()

            qs = qs.order_by('-computed_risk')[:50]

            rows = []

            for c in qs:
                first_dir = c.directorships.all().first()

                if first_dir:
                    director_html = (
                        f'<a href="{reverse("owners:detail", args=[first_dir.director.pk])}" '
                        f'class="text-white text-decoration-none border-bottom border-secondary">'
                        f'{first_dir.director.full_name}</a>'
                    )
                else:
                    director_html = '<span class="text-muted small">Не указан</span>'

                risk = c.computed_risk or 0

                if risk >= 80:
                    badge = f'<span class="badge bg-danger w-100 py-2">{int(risk)}/100</span>'
                elif risk >= 50:
                    badge = f'<span class="badge bg-warning text-dark w-100 py-2">{int(risk)}/100</span>'
                elif risk > 0:
                    badge = f'<span class="badge bg-success w-100 py-2">{int(risk)}/100</span>'
                else:
                    badge = '<span class="badge bg-secondary w-100 py-2">0/100</span>'

                rows.append({
                    'name': c.name,
                    'url': reverse('companies:detail', args=[c.pk]),
                    'bin': c.bin,
                    'director_html': director_html,
                    'contracts_count': c.contracts_count,
                    'badge_html': badge,
                })

            return JsonResponse({'results': rows, 'total': len(rows)})

        return super().get(request, *args, **kwargs)


class SupplierDetailView(DetailView):
    model = Supplier
    template_name = "companies/detail.html"
    context_object_name = "company"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.object

        contracts = company.contracts.all().order_by("-contract_date")
        total_amount = contracts.aggregate(total=Sum("amount"))["total"] or 0

        directorships = (
            Directorship.objects
            .filter(supplier=company)
            .select_related("director")
        )

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

        related_by_address = Supplier.objects.none()
        if company.address:
            related_by_address = (
                Supplier.objects
                .filter(address=company.address)
                .exclude(pk=company.pk)
            )

        related_by_phone = Supplier.objects.none()
        if company.phone:
            related_by_phone = (
                Supplier.objects
                .filter(phone=company.phone)
                .exclude(pk=company.pk)
            )

        related_by_email = Supplier.objects.none()
        if company.email and company.email.lower() not in EXCLUDED_EMAILS:
            related_by_email = (
                Supplier.objects
                .filter(email=company.email)
                .exclude(pk=company.pk)
            )

        clusters = company.risk_clusters.all().order_by("-risk_score")

        if clusters.exists():
            total_risk = sum(cluster.risk_score for cluster in clusters)
            avg_risk_score = int(total_risk / clusters.count())
        else:
            avg_risk_score = company.risk_score or 0

        if avg_risk_score >= 80:
            risk_color = "danger"
        elif avg_risk_score >= 50:
            risk_color = "warning text-dark"
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
            "avg_risk_score": avg_risk_score,
            "risk_color": risk_color,
            "total_related": total_related,
        })

        return context
