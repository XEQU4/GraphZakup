"""Versioned, evidence-bound API reads and optimistic personal graph views."""
import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Case, CharField, F, IntegerField, Q, Value, When
from django.db.models.functions import Cast, Concat
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_field

from apps.ai.models import AnalysisSnapshot, AnalysisState, Explanation
from apps.ai.services import saved_analysis, historical_explanation
from apps.graph.models import GraphSnapshot, RiskCluster
from apps.graph.view_states import saved_view, save_view, ViewConflict
from apps.ingestion.models import SourceObservation
from .common import (ApiListView, ApiView, EmptyQuerySerializer, ListQuerySerializer,
                     PaginationQuerySerializer, safe_source_url as _safe_source_url)
from .schema import ErrorEnvelopeSerializer
from .cluster_directory import (COVERAGE, REASONS, ClusterDirectorySerializer,
    SnapshotJSONPredicate, SnapshotMemberCount, SavedMetricInteger, directory_projection)


# URLs from saved source data are references, never trusted navigation targets.
def safe_source_url(value):
    return _safe_source_url(value) or ''


class PositiveVersionField(serializers.IntegerField):
    def __init__(self, **kwargs):
        super().__init__(min_value=1, max_value=999999999, **kwargs)

    def to_internal_value(self, data):
        if isinstance(data, bool) or not re.fullmatch(r'[0-9]{1,9}', str(data)):
            self.fail('invalid')
        return super().to_internal_value(data)


class VersionQuerySerializer(EmptyQuerySerializer):
    version = PositiveVersionField(required=False, help_text='Saved graph version; defaults to the current pointer.')


class AnalysisQuerySerializer(VersionQuerySerializer):
    analysis_version = PositiveVersionField(required=False, help_text='Exact analysis version within the selected graph.')


class HistoryQuerySerializer(PaginationQuerySerializer):
    pass


class ClusterQuerySerializer(ListQuerySerializer):
    active = serializers.BooleanField(required=False, default=True)
    relationship = serializers.ChoiceField(choices=list(REASONS), required=False,
        help_text='Shared, evidenced relationship between distinct members of the saved graph.')
    coverage = serializers.ChoiceField(choices=COVERAGE, required=False,
        help_text='Successful KGD arrears check coverage at the saved analysis date, not overall data completeness.')
    minimum_review_priority = serializers.IntegerField(min_value=0, max_value=100, required=False)
    ordering = serializers.ChoiceField(required=False, default='-review_priority', choices=[
        'name', '-name', 'review_priority', '-review_priority', 'created_at', '-created_at'])


class SourceReferenceSerializer(serializers.Serializer):
    source = serializers.CharField()
    observation_id = serializers.IntegerField(required=False)
    record_id = serializers.IntegerField(required=False)
    url = serializers.SerializerMethodField()
    quality = serializers.CharField(required=False, allow_blank=True)
    observed_at = serializers.DateTimeField(required=False, allow_null=True)

    @extend_schema_field(serializers.URLField(allow_blank=True))
    def get_url(self, obj):
        return safe_source_url(obj.get('url'))


class GraphNodeSerializer(serializers.Serializer):
    id = serializers.CharField()
    kind = serializers.ChoiceField(choices=['company', 'person', 'contact'])
    name = serializers.CharField(allow_blank=True)
    bin = serializers.CharField(required=False, allow_blank=True)
    company_id = serializers.IntegerField(required=False)
    contact_type = serializers.CharField(required=False)
    identity_verified = serializers.BooleanField(required=False)

    def to_representation(self, instance):
        # Company BINs are public company keys. A stray person/contact BIN field
        # in an old payload must not become a public personal identifier.
        result = super().to_representation(instance)
        extras = {'company': {'bin', 'company_id'}, 'person': {'identity_verified'}, 'contact': {'contact_type'}}
        allowed = {'id', 'kind', 'name'} | extras.get(result['kind'], set())
        return {key: value for key, value in result.items() if key in allowed}


class GraphEdgeSerializer(serializers.Serializer):
    id = serializers.CharField()
    source = serializers.CharField()
    target = serializers.CharField()
    type = serializers.CharField()
    value = serializers.CharField(allow_blank=True)
    company_id = serializers.IntegerField()
    confidence = serializers.CharField()
    valid_from = serializers.DateField(allow_null=True)
    valid_until = serializers.DateField(allow_null=True)
    temporal_status = serializers.CharField()
    common_contact = serializers.BooleanField(required=False)
    evidence = SourceReferenceSerializer(many=True)
    limitations = serializers.ListField(child=serializers.CharField())


class GraphPayloadSerializer(serializers.Serializer):
    nodes = GraphNodeSerializer(many=True)
    links = GraphEdgeSerializer(many=True)


class SnapshotChangesSerializer(serializers.Serializer):
    added_members = serializers.ListField(child=serializers.IntegerField(), required=False)
    removed_members = serializers.ListField(child=serializers.IntegerField(), required=False)
    added_nodes = serializers.ListField(child=serializers.CharField(), required=False)
    removed_nodes = serializers.ListField(child=serializers.CharField(), required=False)
    added_edges = serializers.ListField(child=serializers.CharField(), required=False)
    removed_edges = serializers.ListField(child=serializers.CharField(), required=False)
    changed_edges = serializers.ListField(child=serializers.CharField(), required=False)
    changed_nodes = serializers.ListField(child=serializers.CharField(), required=False)


class SnapshotSerializer(serializers.ModelSerializer):
    changes = SnapshotChangesSerializer()
    previous_id = serializers.IntegerField(allow_null=True)
    member_ids = serializers.ListField(child=serializers.IntegerField())

    class Meta:
        model = GraphSnapshot
        fields = ['id', 'version', 'graph_hash', 'algorithm_version', 'state', 'as_of',
                  'member_ids', 'changes', 'previous_id', 'created_at']
        extra_kwargs = {'member_ids': {'read_only': True}}


class ClusterSerializer(serializers.ModelSerializer):
    review_priority = serializers.IntegerField(source='saved_review_priority', allow_null=True)
    company_count = serializers.SerializerMethodField()
    current_snapshot = SnapshotSerializer(allow_null=True)
    directory = serializers.SerializerMethodField()

    class Meta:
        model = RiskCluster
        fields = ['uuid', 'name', 'is_active', 'review_priority', 'company_count',
                  'current_snapshot', 'directory', 'created_at', 'updated_at']

    @extend_schema_field(serializers.IntegerField())
    def get_company_count(self, obj):
        return len(set(obj.current_snapshot.member_ids)) if obj.current_snapshot else 0

    @extend_schema_field(ClusterDirectorySerializer)
    def get_directory(self, obj):
        return ClusterDirectorySerializer(directory_projection(obj)).data


def cluster_queryset():
    matching = Q(analysis_state__analysis__graph_snapshot_id=F('current_snapshot_id'),
                 analysis_state__analysis__cluster_id=F('pk'))
    metrics = 'analysis_state__analysis__metrics'
    return RiskCluster.objects.select_related('current_snapshot', 'analysis_state__analysis').defer(
        'analysis_state__analysis__inputs', 'analysis_state__analysis__findings',
        'analysis_state__analysis__limitations', 'current_snapshot__legacy_explanation').annotate(
        saved_review_priority=Case(When(matching, then=SavedMetricInteger(metrics, 'review_priority')),
            default=Value(None), output_field=IntegerField()),
        saved_member_count=SnapshotMemberCount('current_snapshot__member_ids'),
        saved_checked=Case(When(matching, then=SavedMetricInteger(metrics, 'fresh_arrears_checks')),
            default=Value(None), output_field=IntegerField()),
        saved_analysis_count=Case(When(matching, then=SavedMetricInteger(metrics, 'company_count')),
            default=Value(None), output_field=IntegerField()),
    ).annotate(saved_coverage=Case(
        When(saved_member_count__gt=0, saved_analysis_count=F('saved_member_count'),
             saved_checked=F('saved_member_count'), then=Value('checked')),
        When(saved_member_count__gt=0, saved_analysis_count=F('saved_member_count'),
             saved_checked__gt=0, saved_checked__lt=F('saved_member_count'), then=Value('partial')),
        When(saved_member_count__gt=0, saved_analysis_count=F('saved_member_count'),
             saved_checked=0, then=Value('no_checks')),
        default=Value('not_assessed'), output_field=CharField()))


def cluster_for(uuid):
    return get_object_or_404(cluster_queryset(), uuid=uuid)


def selected_graph(cluster, query):
    if 'version' in query:
        return get_object_or_404(GraphSnapshot, cluster=cluster, version=query['version'])
    return cluster.current_snapshot


class ClusterListView(ApiListView):
    query_serializer_class = ClusterQuerySerializer
    serializer_class = ClusterSerializer

    @extend_schema(parameters=[ClusterQuerySerializer], responses=ClusterSerializer(many=True))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return RiskCluster.objects.none()
        query = self.query
        qs = cluster_queryset().filter(is_active=query['active'])
        if query.get('search'):
            qs = qs.annotate(directory_search=SnapshotJSONPredicate(search=query['search']))
            title_label = Case(*[When(SnapshotJSONPredicate(relationship=kind), then=Value(label))
                                for kind, label in REASONS.items()],
                              default=Value('Relationship group'), output_field=CharField())
            qs = qs.annotate(directory_title=Case(
                When(current_snapshot_id__isnull=True, then=Value('Group awaiting a saved graph')),
                default=Concat(title_label, Value(' · '),
                Cast('saved_member_count', CharField()), Value(' '),
                Case(When(saved_member_count=1, then=Value('company')), default=Value('companies'),
                     output_field=CharField())), output_field=CharField()))
            qs = qs.filter(Q(name__icontains=query['search']) | Q(directory_search=True) |
                           Q(directory_title__icontains=query['search']))
        if query.get('relationship'):
            qs = qs.filter(SnapshotJSONPredicate(relationship=query['relationship']))
        if query.get('coverage'):
            qs = qs.filter(saved_coverage=query['coverage'])
        if 'minimum_review_priority' in query:
            qs = qs.filter(saved_review_priority__gte=query['minimum_review_priority'])
        ordering = query['ordering']
        if ordering.removeprefix('-') == 'review_priority':
            score_order = F('saved_review_priority').desc(nulls_last=True) if ordering.startswith('-') else F(
                'saved_review_priority').asc(nulls_last=True)
            return qs.order_by(score_order, 'pk')
        return qs.order_by(ordering, 'pk')


class ClusterDetailView(ApiView):
    query_serializer_class = EmptyQuerySerializer

    @extend_schema(responses=ClusterSerializer)
    def get(self, request, uuid):
        return Response(ClusterSerializer(cluster_for(uuid)).data)


class SnapshotListView(ApiListView):
    query_serializer_class = HistoryQuerySerializer
    serializer_class = SnapshotSerializer

    @extend_schema(parameters=[HistoryQuerySerializer], responses=SnapshotSerializer(many=True))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return GraphSnapshot.objects.none()
        return GraphSnapshot.objects.filter(cluster=cluster_for(self.kwargs['uuid'])).order_by('-version')


class LineageSerializer(serializers.Serializer):
    source_snapshot_id = serializers.IntegerField(source='source_id')
    source_cluster = serializers.UUIDField(source='source.cluster.uuid')
    source_version = serializers.IntegerField(source='source.version')
    target_snapshot_id = serializers.IntegerField(source='target_id')
    target_cluster = serializers.UUIDField(source='target.cluster.uuid')
    target_version = serializers.IntegerField(source='target.version')
    kind = serializers.CharField()
    shared_member_ids = serializers.ListField(child=serializers.IntegerField())


class SnapshotDetailSerializer(SnapshotSerializer):
    cluster = serializers.UUIDField(source='cluster.uuid')
    graph = GraphPayloadSerializer(source='payload')
    incoming_transitions = LineageSerializer(many=True)
    outgoing_transitions = LineageSerializer(many=True)

    class Meta(SnapshotSerializer.Meta):
        fields = SnapshotSerializer.Meta.fields + ['cluster', 'graph', 'incoming_transitions', 'outgoing_transitions']


class SnapshotDetailView(ApiView):
    query_serializer_class = EmptyQuerySerializer

    @extend_schema(responses=SnapshotDetailSerializer)
    def get(self, request, pk):
        from django.db.models import Prefetch
        from apps.graph.models import ClusterLineage
        transitions = ClusterLineage.objects.select_related('source__cluster', 'target__cluster').order_by('pk')
        snapshot = get_object_or_404(GraphSnapshot.objects.select_related('cluster').prefetch_related(
            Prefetch('incoming_transitions', queryset=transitions),
            Prefetch('outgoing_transitions', queryset=transitions)), pk=pk)
        return Response(SnapshotDetailSerializer(snapshot).data)


class GraphReadSerializer(serializers.Serializer):
    cluster = serializers.UUIDField()
    version = serializers.IntegerField(allow_null=True)
    snapshot_id = serializers.IntegerField(allow_null=True)
    graph_hash = serializers.CharField(allow_null=True)
    state = serializers.CharField()
    historical = serializers.BooleanField()
    graph = GraphPayloadSerializer()


class GraphReadView(ApiView):
    query_serializer_class = VersionQuerySerializer

    @extend_schema(parameters=[VersionQuerySerializer], responses=GraphReadSerializer)
    def get(self, request, uuid):
        cluster = cluster_for(uuid)
        graph = selected_graph(cluster, self.query)
        return Response(GraphReadSerializer({'cluster': cluster.uuid, 'version': graph.version if graph else None,
            'snapshot_id': graph.pk if graph else None, 'graph_hash': graph.graph_hash if graph else None,
            'state': graph.state if graph else 'not_calculated',
            'historical': bool(graph and graph.pk != cluster.current_snapshot_id),
            'graph': graph.payload if graph else {'nodes': [], 'links': []}}).data)


class FindingEvidenceSerializer(serializers.Serializer):
    kind = serializers.CharField()
    id = serializers.CharField()
    source = serializers.CharField(required=False)
    url = serializers.SerializerMethodField()
    observed_at = serializers.DateTimeField(required=False, allow_null=True)
    quality = serializers.CharField(required=False)

    @extend_schema_field(serializers.URLField(allow_blank=True))
    def get_url(self, obj):
        return safe_source_url(obj.get('url'))


class FindingSerializer(serializers.Serializer):
    id = serializers.CharField()
    code = serializers.CharField()
    rule_version = serializers.CharField()
    company_ids = serializers.ListField(child=serializers.IntegerField())
    evidence = FindingEvidenceSerializer(many=True)
    statements = serializers.ListField(child=serializers.CharField())
    candidate_contribution = serializers.IntegerField()
    contribution = serializers.IntegerField()
    dimension = serializers.CharField()
    limitations = serializers.ListField(child=serializers.CharField())


class ScoreBreakdownSerializer(serializers.Serializer):
    finding_id = serializers.CharField()
    points = serializers.IntegerField()


class ScoreCategoriesSerializer(serializers.Serializer):
    director = serializers.IntegerField(required=False)
    owner = serializers.IntegerField(required=False)
    contacts = serializers.IntegerField(required=False)
    cross_role = serializers.IntegerField(required=False)


class MetricsSerializer(serializers.Serializer):
    review_priority = serializers.IntegerField()
    relationship_priority = serializers.IntegerField()
    financial_priority = serializers.IntegerField()
    link_strength = serializers.IntegerField()
    behavioural_risk = serializers.IntegerField(allow_null=True)
    behavioural_status = serializers.CharField()
    company_count = serializers.IntegerField()
    fresh_arrears_checks = serializers.IntegerField()
    unknown_current_arrears = serializers.IntegerField()
    retained_recent_arrears_results = serializers.IntegerField()
    companies_with_fresh_arrears = serializers.ListField(child=serializers.IntegerField())
    score_interpretation = serializers.CharField()
    stored_contract_count = serializers.IntegerField()
    stored_contract_amount = serializers.CharField()
    shared_customer_count = serializers.IntegerField()
    score_categories = ScoreCategoriesSerializer()
    score_breakdown = ScoreBreakdownSerializer(many=True)


class DocumentCompanySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    bin = serializers.CharField()


class DocumentFindingSerializer(serializers.Serializer):
    finding_id = serializers.CharField()
    title = serializers.CharField()
    fact = serializers.CharField()
    meaning = serializers.CharField(allow_blank=True)
    companies = DocumentCompanySerializer(many=True)
    additional_companies = serializers.IntegerField()
    notes = serializers.ListField(child=serializers.CharField())
    details = serializers.ListField(child=serializers.CharField(), required=False)


class DocumentScoreItemSerializer(serializers.Serializer):
    finding_id = serializers.CharField()
    label = serializers.CharField()
    points = serializers.IntegerField()


class DocumentScoreSerializer(serializers.Serializer):
    value = serializers.IntegerField()
    items = DocumentScoreItemSerializer(many=True)
    meaning = serializers.CharField()


class NarrativeItemSerializer(serializers.Serializer):
    text = serializers.CharField()
    finding_ids = serializers.ListField(child=serializers.CharField())


class NarrativeSerializer(serializers.Serializer):
    paragraphs = NarrativeItemSerializer(many=True)
    checks = NarrativeItemSerializer(many=True)


class DocumentSerializer(serializers.Serializer):
    version = serializers.CharField()
    summary = serializers.CharField()
    findings = DocumentFindingSerializer(many=True)
    additional_findings = serializers.IntegerField()
    checks = serializers.ListField(child=serializers.CharField())
    coverage = serializers.ListField(child=serializers.CharField())
    score = DocumentScoreSerializer()
    conclusion = serializers.CharField()
    narrative = NarrativeSerializer(required=False)


class ExplanationSerializer(serializers.ModelSerializer):
    document = serializers.SerializerMethodField()

    class Meta:
        model = Explanation
        fields = ['id', 'analysis_id', 'text', 'language', 'provider', 'model', 'prompt_version',
                  'status', 'created_at', 'document']

    @extend_schema_field(DocumentSerializer(allow_null=True))
    def get_document(self, obj):
        document = obj.presentation.get('document') if isinstance(obj.presentation, dict) else None
        # Old immutable texts do not acquire a document on a read request.
        return DocumentSerializer(document).data if document else None


class AnalysisSerializer(serializers.ModelSerializer):
    graph_version = serializers.IntegerField(source='graph_snapshot.version')
    metrics = MetricsSerializer()
    findings = FindingSerializer(many=True)

    class Meta:
        model = AnalysisSnapshot
        fields = ['id', 'version', 'graph_snapshot_id', 'graph_version', 'analysis_hash', 'rules_version',
                  'as_of', 'created_at', 'metrics', 'findings', 'limitations']


class AnalysisReadSerializer(serializers.Serializer):
    cluster = serializers.UUIDField()
    graph_version = serializers.IntegerField(allow_null=True)
    status = serializers.ChoiceField(choices=['not_calculated', 'ready', 'stale'])
    historical = serializers.BooleanField()
    analysis = AnalysisSerializer(allow_null=True)
    explanation = ExplanationSerializer(allow_null=True)


class AnalysisReadView(ApiView):
    query_serializer_class = AnalysisQuerySerializer

    @extend_schema(parameters=[AnalysisQuerySerializer], responses=AnalysisReadSerializer)
    def get(self, request, uuid):
        cluster = cluster_for(uuid)
        graph = selected_graph(cluster, self.query)
        analysis, explanation, stale = saved_analysis(cluster, graph)
        historical = bool(graph and graph.pk != cluster.current_snapshot_id)
        if 'analysis_version' in self.query:
            previous = analysis
            analysis = get_object_or_404(AnalysisSnapshot.objects.select_related('graph_snapshot'),
                cluster=cluster, graph_snapshot=graph, version=self.query['analysis_version'])
            explanation = historical_explanation(analysis)
            historical = historical or previous is None or previous.pk != analysis.pk
            if historical:
                stale = False
        return Response(AnalysisReadSerializer({'cluster': cluster.uuid,
            'graph_version': graph.version if graph else None,
            'status': 'not_calculated' if analysis is None else 'stale' if stale else 'ready',
            'historical': historical, 'analysis': analysis, 'explanation': explanation}).data)


class AnalysisHistoryView(ApiListView):
    query_serializer_class = HistoryQuerySerializer
    serializer_class = AnalysisSerializer

    @extend_schema(parameters=[HistoryQuerySerializer], responses=AnalysisSerializer(many=True))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return AnalysisSnapshot.objects.none()
        return AnalysisSnapshot.objects.filter(cluster=cluster_for(self.kwargs['uuid'])).select_related(
            'graph_snapshot').order_by('-version')


class AnalysisDetailView(ApiView):
    query_serializer_class = EmptyQuerySerializer

    @extend_schema(responses=AnalysisSerializer)
    def get(self, request, uuid, version):
        analysis = get_object_or_404(AnalysisSnapshot.objects.select_related('graph_snapshot'),
                                   cluster__uuid=uuid, version=version)
        return Response(AnalysisSerializer(analysis).data)


def published_explanations(uuid, version):
    analysis = get_object_or_404(AnalysisSnapshot, cluster__uuid=uuid, version=version)
    return Explanation.objects.filter(analysis=analysis).filter(
        Q(provider='template') | Q(analysisjob__status__in=['succeeded', 'fallback']) |
        Q(pk__in=AnalysisState.objects.filter(analysis=analysis).values('explanation_id'))).distinct().order_by(
            '-created_at', '-pk')


class ExplanationHistoryView(ApiListView):
    query_serializer_class = HistoryQuerySerializer
    serializer_class = ExplanationSerializer

    @extend_schema(parameters=[HistoryQuerySerializer], responses=ExplanationSerializer(many=True))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Explanation.objects.none()
        return published_explanations(self.kwargs['uuid'], self.kwargs['version'])


class ExplanationDetailView(ApiView):
    query_serializer_class = EmptyQuerySerializer

    @extend_schema(responses=ExplanationSerializer)
    def get(self, request, uuid, version, pk):
        explanation = get_object_or_404(published_explanations(uuid, version), pk=pk)
        return Response(ExplanationSerializer(explanation).data)


class SnapshotEvidenceSerializer(serializers.Serializer):
    id = serializers.CharField(help_text='Snapshot-scoped graph_edge:<hash>, observation:<pk> or contract_record:<pk>.')
    kind = serializers.CharField()
    graph_snapshot_id = serializers.IntegerField()
    graph_edge = GraphEdgeSerializer(required=False)
    source = serializers.CharField(required=False)
    observation_id = serializers.IntegerField(required=False)
    contract_id = serializers.IntegerField(required=False)
    url = serializers.URLField(required=False, allow_blank=True)
    quality = serializers.CharField(required=False)
    observed_at = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.CharField(required=False)
    parser_version = serializers.CharField(required=False, allow_blank=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)


def snapshot_evidence(snapshot):
    records, observation_ids = {}, set()
    for edge in snapshot.payload.get('links', []):
        key = 'graph_edge:' + str(edge['id'])
        records[key] = {'id': key, 'kind': 'graph_edge', 'graph_snapshot_id': snapshot.pk, 'graph_edge': edge}
        for ref in edge.get('evidence', []):
            if ref.get('observation_id') is not None:
                pk = ref['observation_id']
                key = 'observation:' + str(pk)
                records.setdefault(key, {'id': key, 'kind': 'observation', 'graph_snapshot_id': snapshot.pk,
                    **{field: ref[field] for field in ('source', 'observation_id', 'quality', 'observed_at') if field in ref},
                    'url': safe_source_url(ref.get('url'))})
                observation_ids.add(pk)
    for analysis in snapshot.analyses.only('findings').order_by('version'):
        for finding in analysis.findings:
            for ref in finding.get('evidence', []):
                if ref.get('kind') not in {'observation', 'contract_record'}:
                    continue
                pk, kind = ref['id'], ref['kind']
                key = kind + ':' + str(pk)
                records.setdefault(key, {'id': key, 'kind': kind, 'graph_snapshot_id': snapshot.pk,
                    **{field: ref[field] for field in ('source', 'quality', 'observed_at') if field in ref},
                    'url': safe_source_url(ref.get('url')), 'observation_id' if kind == 'observation' else 'contract_id': pk})
                if kind == 'observation':
                    observation_ids.add(pk)
    # Only metadata for IDs already copied into this snapshot is navigable.
    for observation in SourceObservation.objects.filter(pk__in=observation_ids).only(
            'pk', 'supplier_id', 'status', 'parser_version', 'observed_at', 'source'):
        item = records['observation:' + str(observation.pk)]
        item.update(status=observation.status, parser_version=observation.parser_version,
                    company_id=observation.supplier_id)
        item.setdefault('source', observation.source)
        item.setdefault('observed_at', observation.observed_at)
    return [records[key] for key in sorted(records)]


class SnapshotEvidenceView(ApiListView):
    query_serializer_class = HistoryQuerySerializer
    serializer_class = SnapshotEvidenceSerializer

    @extend_schema(parameters=[HistoryQuerySerializer], responses=SnapshotEvidenceSerializer(many=True))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return []
        return snapshot_evidence(get_object_or_404(GraphSnapshot, pk=self.kwargs['pk']))


class SnapshotEvidenceDetailView(ApiView):
    query_serializer_class = EmptyQuerySerializer

    @extend_schema(responses=SnapshotEvidenceSerializer)
    def get(self, request, pk, identifier):
        snapshot = get_object_or_404(GraphSnapshot, pk=pk)
        record = next((item for item in snapshot_evidence(snapshot) if item['id'] == identifier), None)
        if record is None:
            from django.http import Http404
            raise Http404('Evidence is not part of this saved snapshot.')
        return Response(SnapshotEvidenceSerializer(record).data)


class PositionSerializer(serializers.Serializer):
    x = serializers.FloatField()
    y = serializers.FloatField()
    pinned = serializers.BooleanField()


class ZoomSerializer(serializers.Serializer):
    x = serializers.FloatField()
    y = serializers.FloatField()
    k = serializers.FloatField()


class ViewPayloadSerializer(serializers.Serializer):
    positions = serializers.DictField(child=PositionSerializer(), required=False)
    zoom = ZoomSerializer(required=False)
    filters = serializers.ListField(child=serializers.ChoiceField(
        choices=['director', 'owner', 'address', 'phone', 'email']), required=False)
    selected = serializers.CharField(allow_null=True, required=False)
    frozen = serializers.BooleanField(required=False)


class ViewWriteSerializer(serializers.Serializer):
    snapshot_id = PositiveVersionField()
    graph_hash = serializers.RegexField(r'^[a-f0-9]{64}$')
    revision = serializers.IntegerField(min_value=0)
    payload = ViewPayloadSerializer()

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) != set(self.fields):
            raise ValidationError({'non_field_errors': [
                'Exactly snapshot_id, graph_hash, revision and payload are required.']})
        # The existing service validates exact nested fields/types and finite bounds;
        # validate the original JSON, never a coercion that silently drops fields.
        parsed = super().to_internal_value(data)
        if type(data['snapshot_id']) is not int or type(data['revision']) is not int:
            raise ValidationError({'non_field_errors': ['Version identifiers must be JSON integers.']})
        parsed['payload'] = data['payload']
        return parsed


class ViewReadSerializer(serializers.Serializer):
    revision = serializers.IntegerField()
    payload = ViewPayloadSerializer(allow_null=True)
    snapshot_version = serializers.IntegerField(required=False)
    schema_version = serializers.IntegerField(required=False)


class ViewConflictError(APIException):
    status_code = 409
    default_code = 'view_conflict'
    default_detail = 'The graph or personal view changed. Reload before saving.'


class PersonalGraphView(ApiView):
    permission_classes = [IsAuthenticated]
    query_serializer_class = VersionQuerySerializer
    query_serializer_classes = {'GET': VersionQuerySerializer, 'PUT': EmptyQuerySerializer}

    @extend_schema(parameters=[VersionQuerySerializer], responses=ViewReadSerializer)
    def get(self, request, uuid):
        cluster = cluster_for(uuid)
        return Response(ViewReadSerializer(saved_view(request.user, cluster, selected_graph(cluster, self.query))).data)

    @extend_schema(request=ViewWriteSerializer, responses={200: ViewReadSerializer, 409: ErrorEnvelopeSerializer})
    def put(self, request, uuid):
        if self.query:
            raise ValidationError('Select the exact graph in the request body, without query parameters.')
        cluster = cluster_for(uuid)
        serializer = ViewWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = save_view(request.user, cluster.pk, **{
                'snapshot_id': serializer.validated_data['snapshot_id'],
                'graph_digest': serializer.validated_data['graph_hash'],
                'revision': serializer.validated_data['revision'], 'payload': serializer.validated_data['payload']})
        except ViewConflict as error:
            raise ViewConflictError(str(error)) from error
        except DjangoValidationError as error:
            raise ValidationError({'payload': error.messages}) from error
        return Response(ViewReadSerializer(result).data)
