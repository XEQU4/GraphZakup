from django.views.generic import (
    ListView,
    DetailView,
)

from apps.core.mixins import ClampedPaginationMixin
from .models import Director
from django.db.models import Count


class DirectorListView(ClampedPaginationMixin, ListView):
    model = Director
    template_name = "owners/list.html"
    context_object_name = "directors"
    paginate_by = 25

    def get_queryset(self):
        return (
            Director.objects
            .annotate(
                companies_count=Count(
                    "directorships"
                )
            )
            # "Осиротевшие" директора (0 компаний) обычно остаются в базе
            # после переимпорта данных в режиме --mode full, когда Supplier
            # и Contract стираются, а Director/Directorship — нет. Такие
            # записи бесполезны для просмотра, поэтому скрываем их по
            # умолчанию.
            .filter(companies_count__gt=0)
            .prefetch_related("directorships__supplier")
            .order_by(
                "-companies_count",
                "full_name",
            )
        )


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
        # Заменяем на реальные объекты Supplier для удобства шаблона
        from apps.companies.models import Supplier
        company_ids = list(context["companies"])
        context["companies"] = Supplier.objects.filter(id__in=company_ids)

        return context
