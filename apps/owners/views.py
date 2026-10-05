from django.db.models import Q, Count, Prefetch
from django.http import JsonResponse
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.views.generic import ListView, DetailView

from apps.companies.models import Supplier
from apps.core.mixins import ClampedPaginationMixin
from .models import Director
from .querysets import current_role_filter, current_roles


class DirectorListView(ClampedPaginationMixin, ListView):
    model = Director
    template_name = "owners/list.html"
    context_object_name = "directors"
    paginate_by = 25

    @staticmethod
    def _base_queryset():
        return (
            Director.objects
            .annotate(companies_count=Count(
                'directorships__supplier', filter=current_role_filter('directorships__'), distinct=True,
            ))
            .filter(companies_count__gt=0)
            .prefetch_related(Prefetch('directorships', queryset=current_roles()))
        )

    def get_queryset(self):
        qs = self._base_queryset()
        q = self.request.GET.get('q', '').strip()

        if q:
            qs = qs.filter(
                Q(full_name__icontains=q) |
                (Q(directorships__supplier__name__icontains=q) & current_role_filter('directorships__'))
            ).distinct()

        return qs.order_by("-companies_count", "full_name")

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
                    Q(full_name__icontains=q) |
                    (Q(directorships__supplier__name__icontains=q) & current_role_filter('directorships__'))
                ).distinct()

            qs = qs.order_by("-companies_count", "full_name")[:50]

            rows = []
            for d in qs:
                names = list(d.directorships.all())
                shown = names[:3]
                companies_html = format_html_join(
                    ', ', '<a href="{}">{}</a>',
                    ((reverse('companies:detail', args=[ds.supplier.pk]), ds.supplier.name[:28]) for ds in shown),
                )

                extra = len(names) - 3
                if extra > 0:
                    companies_html = format_html(
                        '{} <span class="badge bg-secondary ms-1">+{}</span>', companies_html, extra,
                    )

                rows.append({
                    'full_name': d.full_name,
                    'url': reverse('owners:detail', args=[d.pk]),
                    'companies_count': d.companies_count,
                    'companies_html': companies_html,
                })

            return JsonResponse({'results': rows, 'total': len(rows)})

        return super().get(request, *args, **kwargs)


class DirectorDetailView(DetailView):
    model = Director
    template_name = "owners/detail.html"
    context_object_name = "director"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        director = self.object

        company_ids = current_roles().filter(director=director).values_list('supplier_id', flat=True)
        context['companies'] = Supplier.objects.filter(id__in=company_ids)

        return context
