"""Read-only, snapshot-bound relationship-directory projections and SQL filters."""
from collections import defaultdict

from django.db.models import BooleanField, F, Func, IntegerField
from rest_framework import serializers

REASONS = {
    'owner': 'Shared owner',
    'director': 'Shared director',
    'mixed_roles': 'Shared person across roles',
    'phone': 'Shared phone',
    'email': 'Shared email',
    'address': 'Shared address',
}
COVERAGE = ('not_assessed', 'no_checks', 'partial', 'checked')


class DirectoryReasonSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=list(REASONS))
    label = serializers.CharField()
    company_count = serializers.IntegerField()


class DirectoryCompanySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    bin = serializers.CharField(allow_blank=True)


class DirectoryCoverageSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=COVERAGE)
    checked = serializers.IntegerField(allow_null=True)
    total = serializers.IntegerField()
    as_of = serializers.DateField(allow_null=True)


class ClusterDirectorySerializer(serializers.Serializer):
    title = serializers.CharField()
    companies = DirectoryCompanySerializer(many=True)
    additional_companies = serializers.IntegerField()
    reasons = DirectoryReasonSerializer(many=True)
    primary_reason = DirectoryReasonSerializer(allow_null=True)
    analysis_status = serializers.ChoiceField(choices=['not_calculated', 'stale', 'ready'])
    analysis_as_of = serializers.DateField(allow_null=True)
    review_priority = serializers.IntegerField(allow_null=True)
    coverage = DirectoryCoverageSerializer()


def snapshot_companies(snapshot):
    if snapshot is None:
        return []
    members = set(snapshot.member_ids)
    companies = {}
    for node in snapshot.payload.get('nodes', []):
        if node.get('kind') == 'company' and node.get('company_id') in members:
            pk = node['company_id']
            companies.setdefault(pk, {'id': pk, 'name': node.get('name') or 'Unnamed company',
                                      'bin': node.get('bin', '')})
    return sorted(companies.values(), key=lambda item: (item['name'].casefold(), item['id']))


def shared_reasons(snapshot):
    """Mirror the SQL predicate: distinct member companies, evidence and a valid target."""
    if snapshot is None:
        return []
    members = set(snapshot.member_ids)
    nodes = {node['id']: node for node in snapshot.payload.get('nodes', [])}
    groups = defaultdict(set)
    role_groups = defaultdict(lambda: defaultdict(set))
    for edge in snapshot.payload.get('links', []):
        kind, company = edge.get('type'), edge.get('company_id')
        source, target = nodes.get(edge.get('source'), {}), nodes.get(edge.get('target'), {})
        if (kind not in REASONS or kind == 'mixed_roles' or company not in members or not edge.get('evidence')
                or source.get('kind') != 'company' or source.get('company_id') != company):
            continue
        if kind in {'director', 'owner'}:
            valid_target = target.get('kind') == 'person' and target.get('identity_verified') is True
        else:
            valid_target = target.get('kind') == 'contact' and target.get('contact_type') == kind
        if valid_target:
            groups[kind, edge['target']].add(company)
            if kind in {'director', 'owner'}:
                role_groups[edge['target']][kind].add(company)
    by_kind = defaultdict(set)
    for (kind, _), companies in groups.items():
        if len(companies) >= 2:
            by_kind[kind].update(companies)
    for roles in role_groups.values():
        companies = set().union(*roles.values())
        if len(roles) >= 2 and len(companies) >= 2:
            by_kind['mixed_roles'].update(companies)
    return [{'type': kind, 'label': label, 'company_count': len(by_kind[kind])}
            for kind, label in REASONS.items() if by_kind[kind]]


def directory_projection(cluster):
    snapshot = cluster.current_snapshot
    companies = snapshot_companies(snapshot)
    total = len(set(snapshot.member_ids)) if snapshot else 0
    reasons = shared_reasons(snapshot)
    primary = reasons[0] if reasons else None
    title = f"{primary['label']} · {total} {'company' if total == 1 else 'companies'}" if primary else (
        f"Relationship group · {total} {'company' if total == 1 else 'companies'}" if snapshot
        else 'Group awaiting a saved graph')
    state = getattr(cluster, 'analysis_state', None)
    analysis = state.analysis if state else None
    matches = bool(analysis and snapshot and analysis.graph_snapshot_id == snapshot.pk
                   and analysis.cluster_id == cluster.pk)
    status = 'not_calculated' if not analysis else 'ready' if matches else 'stale'
    metrics = analysis.metrics if matches else {}
    date = analysis.as_of if matches else None
    checked = metrics.get('fresh_arrears_checks')
    # Legacy/incomplete metrics are unassessed, never silently zero or fully covered.
    valid_coverage = (type(checked) is int and 0 <= checked <= total and total > 0
                      and type(metrics.get('company_count')) is int and metrics['company_count'] == total)
    coverage_status = ('checked' if checked == total else 'partial' if checked else 'no_checks'
                       ) if valid_coverage else 'not_assessed'
    return {'title': title, 'companies': companies[:3],
            'additional_companies': max(0, total - len(companies[:3])),
            'reasons': reasons, 'primary_reason': primary, 'analysis_status': status,
            'analysis_as_of': date, 'review_priority': cluster.saved_review_priority,
            'coverage': {'status': coverage_status, 'checked': checked if valid_coverage else None,
                         'total': total, 'as_of': date if valid_coverage else None}}


class SnapshotJSONPredicate(Func):
    """JSON array predicates executed before SQL pagination, for PostgreSQL and SQLite."""
    output_field = BooleanField()

    def __init__(self, *, relationship=None, search=None):
        if relationship is not None and relationship not in REASONS:
            raise ValueError('Unsupported relationship.')
        self.relationship = relationship
        self.search = search
        super().__init__(F('current_snapshot__payload'), F('current_snapshot__member_ids'))

    def as_sql(self, compiler, connection, **extra_context):
        payload, payload_params = compiler.compile(self.source_expressions[0])
        members, member_params = compiler.compile(self.source_expressions[1])
        if payload_params or member_params:
            raise ValueError('Snapshot predicates require column references.')
        pg = connection.vendor == 'postgresql'
        if connection.vendor not in {'postgresql', 'sqlite'}:
            raise NotImplementedError('Snapshot directory predicates require PostgreSQL or SQLite.')

        def array(column, field=None):
            if pg:
                value = f"{column}->'{field}'" if field else column
                return f"jsonb_array_elements(COALESCE({value}, '[]'::jsonb))"
            return f"json_each({column}, '$.{field}')" if field else f"json_each({column})"

        def text(alias, field):
            return f"{alias}.value->>'{field}'" if pg else f"CAST(json_extract({alias}.value, '$.{field}') AS TEXT)"

        def value(alias):
            return f"{alias}.value #>> '{{}}'" if pg else f"CAST({alias}.value AS TEXT)"

        company = text('s', 'company_id')
        source_join = (f"{array(payload, 'nodes')} s JOIN {array(members)} m "
                       f"ON {value('m')} = {company}")
        if self.search is not None:
            # Only company labels/BINs in frozen member nodes are searched; contacts and
            # personal names/identifiers cannot accidentally become a public search index.
            pattern = '%' + connection.ops.prep_for_like_query(self.search) + '%'
            escape = "" if pg else " ESCAPE '\\'"
            sql = (f"EXISTS (SELECT 1 FROM {source_join} WHERE {text('s', 'kind')} = 'company' AND "
                   f"(LOWER({text('s', 'name')}) LIKE LOWER(%s){escape} OR "
                   f"LOWER({text('s', 'bin')}) LIKE LOWER(%s){escape}))")
            return sql, [pattern, pattern]
        kind = self.relationship
        edge_company = text('e', 'company_id')
        evidence = (f"jsonb_array_length(COALESCE(e.value->'evidence', '[]'::jsonb))" if pg
                    else "json_array_length(e.value, '$.evidence')")
        if kind in {'director', 'owner', 'mixed_roles'}:
            identity = ("t.value->'identity_verified' = 'true'::jsonb" if pg
                        else "json_type(t.value, '$.identity_verified') = 'true'")
            target = f"{text('t', 'kind')} = 'person' AND {identity}"
        else:
            target = f"{text('t', 'kind')} = 'contact' AND {text('t', 'contact_type')} = '{kind}'"
        edge_type = text('e', 'type')
        type_filter = f"{edge_type} IN ('director', 'owner')" if kind == 'mixed_roles' else f"{edge_type} = '{kind}'"
        mixed_count = f" AND COUNT(DISTINCT {edge_type}) >= 2" if kind == 'mixed_roles' else ''
        sql = (f"EXISTS (SELECT 1 FROM {source_join} "
               f"JOIN {array(payload, 'links')} e ON {text('e', 'source')} = {text('s', 'id')} "
               f"AND {edge_company} = {company} "
               f"JOIN {array(payload, 'nodes')} t ON {text('t', 'id')} = {text('e', 'target')} "
               f"WHERE {text('s', 'kind')} = 'company' AND {type_filter} "
               f"AND {evidence} > 0 AND {target} GROUP BY {text('e', 'target')} "
               f"HAVING COUNT(DISTINCT {edge_company}) >= 2{mixed_count})")
        return sql, []


class SnapshotMemberCount(Func):
    output_field = IntegerField()

    def as_sql(self, compiler, connection, **extra_context):
        column, params = compiler.compile(self.source_expressions[0])
        if connection.vendor == 'postgresql':
            return f"(SELECT COUNT(DISTINCT value) FROM jsonb_array_elements(COALESCE({column}, '[]'::jsonb)))", params
        if connection.vendor == 'sqlite':
            return f"(SELECT COUNT(DISTINCT value) FROM json_each({column}))", params
        raise NotImplementedError('Snapshot directory counts require PostgreSQL or SQLite.')


class SavedMetricInteger(Func):
    """Absent, string, boolean and malformed metrics remain unknown."""
    output_field = IntegerField()

    def __init__(self, field, key):
        if key not in {'review_priority', 'fresh_arrears_checks', 'company_count'}:
            raise ValueError('Unsupported saved metric.')
        self.key = key
        super().__init__(field)

    def as_sql(self, compiler, connection, **extra_context):
        column, params = compiler.compile(self.source_expressions[0])
        key = self.key
        pattern = '^(?:[0-9]{1,2}|100)$' if key == 'review_priority' else '^[0-9]{1,9}$'
        maximum = 100 if key == 'review_priority' else 999999999
        if connection.vendor == 'postgresql':
            sql = (f"CASE WHEN jsonb_typeof({column}->'{key}') = 'number' "
                   f"AND ({column}->>'{key}') ~ '{pattern}' "
                   f"THEN ({column}->>'{key}')::integer ELSE NULL END")
        elif connection.vendor == 'sqlite':
            sql = (f"CASE WHEN json_type({column}, '$.{key}') = 'integer' "
                   f"AND json_extract({column}, '$.{key}') BETWEEN 0 AND {maximum} "
                   f"THEN json_extract({column}, '$.{key}') ELSE NULL END")
        else:
            raise NotImplementedError('Saved metric projections require PostgreSQL or SQLite.')
        return sql, params
