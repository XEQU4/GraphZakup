class ClampedPaginationMixin:
    """
    Clamp out-of-range page requests instead of Django's default Http404.

    Requests beyond the last page show the last page. Zero, negative,
    and nonnumeric values show the first page.

    Use with any ListView that specifies paginate_by:

        class SomeListView(ClampedPaginationMixin, ListView):
            paginate_by = 25
            ...
    """

    def paginate_queryset(self, queryset, page_size):
        paginator = self.get_paginator(
            queryset,
            page_size,
            orphans=self.get_paginate_orphans(),
            allow_empty_first_page=self.get_allow_empty(),
        )

        page_kwarg = self.page_kwarg
        page_number = (
            self.kwargs.get(page_kwarg)
            or self.request.GET.get(page_kwarg)
            or 1
        )

        try:
            page_number = int(page_number)
        except (TypeError, ValueError):
            page_number = 1

        if page_number < 1:
            page_number = 1
        elif page_number > paginator.num_pages:
            page_number = paginator.num_pages

        page = paginator.page(page_number)
        return paginator, page, page.object_list, page.has_other_pages()
