from django.urls import path

from .views import (
    ClusterListView,
    ClusterDetailView,
)

app_name = "graph"

urlpatterns = [

    path(
        "",
        ClusterListView.as_view(),
        name="cluster_list"
    ),

    path(
        "<uuid:uuid>/",
        ClusterDetailView.as_view(),
        name="cluster_detail"
    ),
]