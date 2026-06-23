from django.urls import path

from .views import (
    SupplierListView,
    SupplierDetailView,
)

app_name = "companies"

urlpatterns = [

    path(
        "",
        SupplierListView.as_view(),
        name="list"
    ),

    path(
        "<int:pk>/",
        SupplierDetailView.as_view(),
        name="detail"
    ),

]
