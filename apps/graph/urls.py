from django.urls import path

from .views import (
    ClusterListView,
    ClusterDetailView,
    graph_data, graph_view, graph_rebuild, job_status,
)

app_name = "graph"

urlpatterns = [
    path('jobs/<uuid:uuid>/', job_status, name='job_status'),
    path('<uuid:uuid>/data/', graph_data, name='graph_data'),
    path('<uuid:uuid>/view/', graph_view, name='graph_view'),
    path('<uuid:uuid>/rebuild/', graph_rebuild, name='graph_rebuild'),

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
