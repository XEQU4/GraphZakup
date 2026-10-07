from django.urls import path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.exceptions import NotFound

from .auth import SessionView, LoginView, LogoutView
from .common import ApiView
from .entities import (CompanyListView, CompanyDetailView, PersonListView, PersonDetailView,
    ContractListView, ContractDetailView, DirectorshipListView, OwnershipListView)
from .saved import (ClusterListView, ClusterDetailView, SnapshotListView, SnapshotDetailView,
    GraphReadView, AnalysisReadView, AnalysisHistoryView, AnalysisDetailView,
    ExplanationHistoryView, ExplanationDetailView, SnapshotEvidenceView,
    SnapshotEvidenceDetailView, PersonalGraphView)
from .jobs import (GraphRecalculateView, ExplanationStartView, GraphJobDetailView,
    AnalysisJobDetailView, IngestionRunListView, IngestionRunDetailView, ExperimentalEstimateView)

app_name = 'api'


class UnknownApiView(ApiView):
    schema = None
    def get(self, request, **kwargs):
        raise NotFound('Unknown API endpoint.')

    post = put = patch = delete = get


urlpatterns = [
    path('session/', SessionView.as_view(), name='session'),
    path('session/login/', LoginView.as_view(), name='session-login'),
    path('session/logout/', LogoutView.as_view(), name='session-logout'),
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='api:schema'), name='docs'),
    path('companies/', CompanyListView.as_view(), name='company-list'),
    path('companies/<int:pk>/', CompanyDetailView.as_view(), name='company-detail'),
    path('people/', PersonListView.as_view(), name='person-list'),
    path('people/<int:pk>/', PersonDetailView.as_view(), name='person-detail'),
    path('contracts/', ContractListView.as_view(), name='contract-list'),
    path('contracts/<int:pk>/', ContractDetailView.as_view(), name='contract-detail'),
    path('directorships/', DirectorshipListView.as_view(), name='directorship-list'),
    path('ownerships/', OwnershipListView.as_view(), name='ownership-list'),
    path('clusters/', ClusterListView.as_view(), name='cluster-list'),
    path('clusters/<uuid:uuid>/', ClusterDetailView.as_view(), name='cluster-detail'),
    path('clusters/<uuid:uuid>/snapshots/', SnapshotListView.as_view(), name='snapshot-list'),
    path('snapshots/<int:pk>/', SnapshotDetailView.as_view(), name='snapshot-detail'),
    path('snapshots/<int:pk>/evidence/', SnapshotEvidenceView.as_view(), name='snapshot-evidence-list'),
    path('snapshots/<int:pk>/evidence/<str:identifier>/', SnapshotEvidenceDetailView.as_view(), name='snapshot-evidence-detail'),
    path('clusters/<uuid:uuid>/graph/', GraphReadView.as_view(), name='cluster-graph'),
    path('clusters/<uuid:uuid>/analysis/', AnalysisReadView.as_view(), name='cluster-analysis'),
    path('clusters/<uuid:uuid>/analyses/', AnalysisHistoryView.as_view(), name='analysis-list'),
    path('clusters/<uuid:uuid>/analyses/<int:version>/', AnalysisDetailView.as_view(), name='analysis-detail'),
    path('clusters/<uuid:uuid>/analyses/<int:version>/explanations/', ExplanationHistoryView.as_view(), name='explanation-list'),
    path('clusters/<uuid:uuid>/analyses/<int:version>/explanations/<int:pk>/', ExplanationDetailView.as_view(), name='explanation-detail'),
    path('clusters/<uuid:uuid>/view/', PersonalGraphView.as_view(), name='cluster-view'),
    path('clusters/<uuid:uuid>/recalculate/', GraphRecalculateView.as_view(), name='cluster-recalculate'),
    path('clusters/<uuid:uuid>/explanations/', ExplanationStartView.as_view(), name='cluster-explanation-start'),
    path('jobs/graph/<uuid:uuid>/', GraphJobDetailView.as_view(), name='graph-job-detail'),
    path('jobs/analysis/<uuid:uuid>/', AnalysisJobDetailView.as_view(), name='analysis-job-detail'),
    path('jobs/ingestion/', IngestionRunListView.as_view(), name='ingestion-run-list'),
    path('jobs/ingestion/<uuid:uuid>/', IngestionRunDetailView.as_view(), name='ingestion-run-detail'),
    path('explanations/<int:pk>/experimental-estimate/', ExperimentalEstimateView.as_view(), name='explanation-experimental-estimate'),
    re_path(r'^(?P<unmatched>.*)$', UnknownApiView.as_view()),
]
