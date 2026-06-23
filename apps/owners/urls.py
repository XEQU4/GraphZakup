from django.urls import path

from .views import (
    DirectorListView,
    DirectorDetailView,
)

app_name = "owners"

urlpatterns = [

    path(
        "",
        DirectorListView.as_view(),
        name="list"
    ),

    path(
        "<int:pk>/",
        DirectorDetailView.as_view(),
        name="detail"
    ),

]
