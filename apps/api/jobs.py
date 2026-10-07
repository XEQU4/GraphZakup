"""Staff-only requests and persisted task status; reads never dispatch work."""
from django.shortcuts import get_object_or_404
from django.urls import reverse
from drf_spectacular.utils import extend_schema, extend_schema_field
from rest_framework import serializers, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from apps.ai.jobs import request_analysis
from apps.ai.models import AnalysisJob, Explanation
from apps.ai.providers import ProviderError
from apps.graph.jobs import request_rebuild
from apps.graph.models import GraphRebuildJob, RiskCluster
from apps.ingestion.models import IngestionRun
from .common import (ApiView, ApiListView, EmptyQuerySerializer, PaginationQuerySerializer,
                     StrictSerializer)
from .schema import ErrorEnvelopeSerializer


class JobRequestSerializer(StrictSerializer):
    """No arbitrary dates, provider configuration or source collection options."""


class JsonBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if type(data) is not bool:
            self.fail('invalid', input=data)
        return data


class EmptyJobRequestSerializer(JobRequestSerializer):
    pass


class ExplanationRequestSerializer(JobRequestSerializer):
    use_model = JsonBooleanField(default=False, help_text='Explicitly use the server-configured provider.')
    retry_model = JsonBooleanField(default=False, help_text='Retry a saved fallback using the configured provider.')

    def validate(self, attrs):
        if attrs['retry_model'] and not attrs['use_model']:
            raise serializers.ValidationError({'retry_model': ['Requires use_model=true.']})
        return attrs


class GraphResultSerializer(serializers.Serializer):
    cluster_uuid = serializers.UUIDField()
    version = serializers.IntegerField()
    graph_hash = serializers.CharField()
    state = serializers.CharField()
    analysis_version = serializers.IntegerField(required=False)
    analysis_hash = serializers.CharField(required=False)


class GraphSummarySerializer(serializers.Serializer):
    analyzed = serializers.IntegerField(required=False)
    groups = serializers.IntegerField(required=False)
    created = serializers.IntegerField(required=False)
    updated = serializers.IntegerField(required=False)
    unchanged = serializers.IntegerField(required=False)
    retired = serializers.IntegerField(required=False)
    affected_companies = serializers.IntegerField(required=False)
    snapshots_created = serializers.IntegerField(required=False)
    analysis_versions_created = serializers.IntegerField(required=False)


class GraphJobSerializer(serializers.Serializer):
    job = serializers.UUIDField(source='uuid')
    kind = serializers.SerializerMethodField()
    status = serializers.CharField()
    error_code = serializers.CharField()
    created_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField(allow_null=True)
    summary = serializers.SerializerMethodField()
    results = serializers.SerializerMethodField()

    def get_kind(self, obj) -> str:
        return 'graph'

    @extend_schema_field(GraphSummarySerializer)
    def get_summary(self, obj):
        return GraphSummarySerializer(obj.summary).data

    @extend_schema_field(GraphResultSerializer(many=True))
    def get_results(self, obj):
        return GraphResultSerializer(obj.summary.get('results', []), many=True).data


class AnalysisResultSerializer(serializers.Serializer):
    cluster_uuid = serializers.UUIDField()
    graph_snapshot_id = serializers.IntegerField()
    graph_version = serializers.IntegerField()
    graph_hash = serializers.CharField()
    analysis_id = serializers.IntegerField(allow_null=True)
    analysis_version = serializers.IntegerField(allow_null=True)
    analysis_hash = serializers.CharField(allow_null=True)
    explanation_id = serializers.IntegerField(allow_null=True)


class AnalysisJobSerializer(serializers.Serializer):
    job = serializers.UUIDField(source='uuid')
    kind = serializers.SerializerMethodField()
    status = serializers.CharField()
    error_code = serializers.CharField()
    created_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField(allow_null=True)
    result = serializers.SerializerMethodField()

    def get_kind(self, obj) -> str:
        return 'analysis'

    @extend_schema_field(AnalysisResultSerializer)
    def get_result(self, obj):
        graph = obj.graph_snapshot
        return {'cluster_uuid': str(graph.cluster.uuid), 'graph_snapshot_id': graph.pk,
                'graph_version': graph.version, 'graph_hash': graph.graph_hash,
                'analysis_id': obj.analysis_id,
                'analysis_version': obj.analysis.version if obj.analysis_id else None,
                'analysis_hash': obj.analysis.analysis_hash if obj.analysis_id else None,
                'explanation_id': obj.explanation_id}


class GraphJobStartSerializer(GraphJobSerializer):
    created = serializers.BooleanField()
    url = serializers.URLField()


class AnalysisJobStartSerializer(AnalysisJobSerializer):
    created = serializers.BooleanField()
    url = serializers.URLField()


def job_error(code, message, *, response_status=400, details=None):
    return Response({'error': {'code': code, 'message': message, 'details': details}},
                    status=response_status)


def start_response(request, job, created, serializer, route):
    # on_commit dispatch can mark a task failed after the service transaction exits.
    job.refresh_from_db()
    url = request.build_absolute_uri(reverse(route, args=[job.uuid]))
    if job.status == 'failed' and job.error_code == 'broker_unavailable':
        return job_error('broker_unavailable', 'The task broker is unavailable.',
                         response_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                         details={'job': str(job.uuid), 'url': url})
    return Response({**serializer(job).data, 'created': created, 'url': url},
                    status=status.HTTP_202_ACCEPTED)


class StaffJobView(ApiView):
    permission_classes = [IsAdminUser]
    query_serializer_class = EmptyQuerySerializer


class GraphRecalculateView(StaffJobView):
    @extend_schema(request=EmptyJobRequestSerializer, responses={202: GraphJobStartSerializer, 409: ErrorEnvelopeSerializer, 503: ErrorEnvelopeSerializer},
                   tags=['Jobs'], description='Recalculate from saved evidence. Does not collect external data.')
    def post(self, request, uuid):
        payload = EmptyJobRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        cluster = get_object_or_404(RiskCluster, uuid=uuid)
        if not cluster.is_active:
            return job_error('inactive_cluster', 'Only active groups can be recalculated.', response_status=409)
        ids = list(cluster.suppliers.order_by('pk').values_list('pk', flat=True)[:501])
        if not ids or len(ids) > 500:
            return job_error('invalid_selection', 'Select a group containing 1 to 500 companies.')
        try:
            job, created = request_rebuild(request.user, ids)
        except ValueError:
            return job_error('invalid_selection', 'The selected companies cannot be recalculated.')
        return start_response(request, job, created, GraphJobSerializer, 'api:graph-job-detail')


class ExplanationStartView(StaffJobView):
    @extend_schema(request=ExplanationRequestSerializer, responses={202: AnalysisJobStartSerializer, 409: ErrorEnvelopeSerializer, 503: ErrorEnvelopeSerializer},
                   tags=['Jobs'], description='Prepare saved analysis through the existing deduplicated background service. '
                   'Model inference requires use_model=true and enabled server configuration.')
    def post(self, request, uuid):
        payload = ExplanationRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        cluster = get_object_or_404(RiskCluster, uuid=uuid)
        if not cluster.is_active:
            return job_error('inactive_cluster', 'Only active groups can be analysed.', response_status=409)
        try:
            job, created = request_analysis(request.user, cluster.pk, **payload.validated_data)
        except ValueError as error:
            if str(error) == 'active_graph_required':
                return job_error('active_graph_required', 'An active saved graph is required.', response_status=409)
            return job_error('invalid_options', 'The analysis options are invalid.')
        except ProviderError as error:
            return job_error(str(error), 'The configured analysis provider is unavailable.')
        job = AnalysisJob.objects.select_related('graph_snapshot__cluster', 'analysis').get(pk=job.pk)
        return start_response(request, job, created, AnalysisJobSerializer, 'api:analysis-job-detail')


class GraphJobDetailView(StaffJobView):
    @extend_schema(responses=GraphJobSerializer, tags=['Jobs'])
    def get(self, request, uuid):
        job = get_object_or_404(GraphRebuildJob, uuid=uuid)
        return Response(GraphJobSerializer(job).data)


class AnalysisJobDetailView(StaffJobView):
    @extend_schema(responses=AnalysisJobSerializer, tags=['Jobs'])
    def get(self, request, uuid):
        job = get_object_or_404(AnalysisJob.objects.select_related('graph_snapshot__cluster', 'analysis'), uuid=uuid)
        return Response(AnalysisJobSerializer(job).data)


class IngestionRunSerializer(serializers.Serializer):
    job = serializers.UUIDField(source='uuid')
    mode = serializers.CharField()
    status = serializers.CharField()
    stage = serializers.CharField()
    next_page = serializers.IntegerField()
    offset = serializers.IntegerField()
    attempts = serializers.IntegerField()
    error_code = serializers.CharField()
    started_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField(allow_null=True)
    updated_at = serializers.DateTimeField()
    counters = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DictField(child=serializers.IntegerField()))
    def get_counters(self, obj):
        # Operational status does not expose options, raw responses or subject identifiers.
        allowed = {'contracts', 'companies_checked', 'companies_changed', 'kgd_company_attempts'}
        return {key: value for key, value in obj.counters.items()
                if key in allowed and type(value) is int and value >= 0}


class IngestionRunListView(ApiListView):
    permission_classes = [IsAdminUser]
    query_serializer_class = PaginationQuerySerializer
    serializer_class = IngestionRunSerializer
    queryset = IngestionRun.objects.order_by('-started_at', '-pk')

    @extend_schema(parameters=[PaginationQuerySerializer], tags=['Jobs'],
                   description='Paginated saved operational status; no source collection is started.')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class IngestionRunDetailView(StaffJobView):
    @extend_schema(responses=IngestionRunSerializer, tags=['Jobs'],
                   description='Read saved operational status. No HTTP collection start is provided.')
    def get(self, request, uuid):
        run = get_object_or_404(IngestionRun, uuid=uuid)
        return Response(IngestionRunSerializer(run).data)


class ExperimentalEstimateSerializer(serializers.Serializer):
    explanation_id = serializers.IntegerField()
    analysis_id = serializers.IntegerField()
    analysis_version = serializers.IntegerField()
    graph_version = serializers.IntegerField()
    experimental_score = serializers.IntegerField(allow_null=True)
    experimental_evidence = serializers.ListField(child=serializers.CharField())
    interpretation = serializers.CharField()


class ExperimentalEstimateView(StaffJobView):
    @extend_schema(responses=ExperimentalEstimateSerializer, tags=['Jobs'],
                   description='Staff-only saved experimental estimate. Never replaces public review priority.')
    def get(self, request, pk):
        explanation = get_object_or_404(Explanation.objects.select_related('analysis__graph_snapshot'), pk=pk)
        return Response({'explanation_id': explanation.pk, 'analysis_id': explanation.analysis_id,
                         'analysis_version': explanation.analysis.version,
                         'graph_version': explanation.analysis.graph_snapshot.version,
                         'experimental_score': explanation.experimental_score,
                         'experimental_evidence': explanation.experimental_evidence,
                         'interpretation': 'Unvalidated experimental estimate; does not replace public review priority.'})
