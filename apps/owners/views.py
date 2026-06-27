from django.db.models import Q, Count
from django.http import JsonResponse
from django.urls import reverse
from django.views.generic import ListView, DetailView

from apps.companies.models import Supplier
from apps.core.mixins import ClampedPaginationMixin
from .models import Director


class DirectorListView(ClampedPaginationMixin, ListView):
    model = Director
    template_name = "owners/list.html"
    context_object_name = "directors"
    paginate_by = 25

    @staticmethod
    def _base_queryset():
        return (
            Director.objects
            .annotate(companies_count=Count("directorships"))
            .filter(companies_count__gt=0)
            .prefetch_related("directorships__supplier")
        )

    def get_queryset(self):
        qs = self._base_queryset()
        q = self.request.GET.get('q', '').strip()

        if q:
            qs = qs.filter(
                Q(full_name__icontains=q) |
                Q(directorships__supplier__name__icontains=q)
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
                    Q(directorships__supplier__name__icontains=q)
                ).distinct()

            qs = qs.order_by("-companies_count", "full_name")[:50]

            rows = []
            for d in qs:
                names = list(d.directorships.all())
                companies_html = ''
                shown = names[:3]

                for i, ds in enumerate(shown):
                    companies_html += (
                        f'<a href="{reverse("companies:detail", args=[ds.supplier.pk])}">'
                        f'{ds.supplier.name[:28]}</a>'
                    )

                    if i < len(shown) - 1:
                        companies_html += ', '

                extra = len(names) - 3
                if extra > 0:
                    companies_html += f' <span class="badge bg-secondary ms-1">+{extra}</span>'

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

        context["companies"] = (
            director.directorships
            .select_related("supplier")
            .values_list("supplier", flat=True)
        )

        company_ids = list(context["companies"])
        context["companies"] = Supplier.objects.filter(id__in=company_ids)

        return context
