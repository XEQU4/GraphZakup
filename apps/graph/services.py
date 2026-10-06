"""Indexed relationships and atomic, incremental graph publication."""

from collections import defaultdict
from decimal import Decimal
from fractions import Fraction
import hashlib
import json

from django.db import connection, transaction
from django.utils import timezone

from apps.companies.models import Supplier
from apps.core.models import SystemSetting
from apps.graph.models import (RiskCluster, EvidenceEdge, GraphInputState,
                               GraphSnapshot, ClusterLineage)
from apps.graph.evidence import (EvidenceIndex, ALGORITHM_VERSION, COMMON_CONTACT_LIMIT,
                                contact_value, digest, graph_hash, semantic_edge)
from apps.owners.querysets import is_confirmed_role


EXCLUDED_EMAILS = {"info@adata.kz", "support@adata.kz"}
REBUILD_LOCK = 1196443459


def current_directorships(supplier, as_of=None):
    as_of = as_of or timezone.localdate()
    return [role for role in supplier.directorships.all()
            if role.is_current and is_confirmed_role(role)
            and (role.start_date is None or role.start_date <= as_of)
            and (role.end_date is None or role.end_date > as_of)]


def build_director_map(suppliers, as_of=None):
    as_of = as_of or timezone.localdate()
    return {supplier.pk: {role.person_identity_id for role in current_directorships(supplier, as_of)}
            for supplier in suppliers}


def get_connection_types(s1, s2, director_map):
    types = set()
    if director_map[s1.pk] & director_map[s2.pk]:
        types.add("director")
    for field in ("address", "phone", "email"):
        value = getattr(s1, field)
        target = getattr(s2, field)
        if field == "email":
            value, target = value.strip().lower(), target.strip().lower()
        if value and value == target:
            if field != "email" or value not in EXCLUDED_EMAILS:
                types.add(field)
    return types


def is_connected(s1, s2, director_map):
    return bool(get_connection_types(s1, s2, director_map))


def find_connected_groups(suppliers, director_map):
    suppliers = list(suppliers)
    parent = list(range(len(suppliers)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    features = defaultdict(list)
    for i, supplier in enumerate(suppliers):
        for person in director_map[supplier.pk]:
            features[('director', person)].append(i)
        for field in ('address', 'phone', 'email'):
            value = contact_value(field, getattr(supplier, field))
            if value and not (field == 'email' and value in EXCLUDED_EMAILS):
                features[(field, value)].append(i)
    for (kind, _), indexes in features.items():
        if kind != 'director' and len(indexes) > COMMON_CONTACT_LIMIT:
            continue
        for index in indexes[1:]:
            parent[find(index)] = find(indexes[0])
    groups = defaultdict(list)
    for index, supplier in enumerate(suppliers):
        groups[find(index)].append(supplier)
    return sorted((sorted(group, key=lambda s: s.pk) for group in groups.values() if len(group) > 1),
                  key=lambda group: tuple(s.pk for s in group))


def get_risk_weights():
    defaults = {"director": 35, "address": 25, "phone": 20, "email": 15, "group_size": 5}
    saved = dict(SystemSetting.objects.filter(key__in=[f'risk_{kind}_weight' for kind in defaults]).values_list('key', 'value'))
    weights = {}
    for kind, default in defaults.items():
        try:
            value = int(saved.get(f'risk_{kind}_weight', default))
        except (TypeError, ValueError):
            value = default
        weights[kind] = max(0, min(100, value))
    return weights


def calculate_risk(suppliers, director_map, weights=None):
    weights = weights if weights is not None else get_risk_weights()
    suppliers, types, counts = list(suppliers), set(), defaultdict(int)
    for supplier in suppliers:
        for person in director_map[supplier.pk]:
            counts[('director', person)] += 1
        for field in ('address', 'phone', 'email'):
            value = contact_value(field, getattr(supplier, field))
            if value and not (field == 'email' and value in EXCLUDED_EMAILS):
                counts[(field, value)] += 1
    types = {kind for (kind, _), count in counts.items() if count > 1
             and (kind == 'director' or count <= COMMON_CONTACT_LIMIT)}
    return min(100, sum(weights[kind] for kind in types)
               + max(0, len(suppliers) - 2) * weights["group_size"])


def generate_cluster_name(group, index=None):
    anchor = min(group, key=lambda supplier: (-supplier.risk_score, supplier.name, supplier.pk))
    name = anchor.name if len(anchor.name) <= 40 else anchor.name[:37] + "..."
    others = len(group) - 1
    return f"Group: {name} and {others} more" if others else f"Group: {name}"


def analysis_fingerprint(group, weights, as_of):
    data = []
    for supplier in sorted(group, key=lambda item: item.pk):
        directors = sorted((role.director_id, role.director.full_name, role.director.iin,
                            str(role.start_date), str(role.end_date), role.person_identity_id)
                           for role in current_directorships(supplier, as_of))
        owners = sorted((role.owner_id, role.owner.full_name, role.owner.iin,
                         str(role.share_percent), role.owner.has_tax_debt,
                         role.owner.has_court_cases, role.owner.is_bankrupt, role.owner.blacklisted)
                        for role in supplier.ownerships.all() if role.is_current
                        and (role.start_date is None or role.start_date <= as_of)
                        and (role.end_date is None or role.end_date > as_of))
        contracts = sorted((contract.pk, contract.contract_number, contract.tender_id,
                            contract.contract_gos_id, contract.title, str(contract.amount),
                            str(contract.contract_date), contract.customer_name,
                            contract.customer_bin, contract.winner)
                           for contract in supplier.contracts.all())
        data.append({"id": supplier.pk, "bin": supplier.bin, "name": supplier.name,
                     "address": supplier.address, "phone": supplier.phone,
                     "email": supplier.email.strip().lower(), "risk_score": supplier.risk_score,
                     "directors": directors, "owners": owners, "contracts": contracts})
    payload = {"version": "phase2-analysis-v1", "weights": weights, "suppliers": data}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def match_clusters(groups, existing, memberships):
    """Exact first; each remaining UUID can continue in only one component."""
    group_sets = [frozenset(s.pk for s in group) for group in groups]
    assigned, used = {}, set()
    by_age = sorted(existing, key=lambda cluster: (not cluster.is_active, cluster.created_at, cluster.pk))
    exact, by_member = defaultdict(list), defaultdict(set)
    by_id = {cluster.pk: cluster for cluster in existing}
    for cluster in by_age:
        exact[memberships[cluster.pk]].append(cluster)
        if cluster.is_active:
            for member in memberships[cluster.pk]:
                by_member[member].add(cluster.pk)
    for index, members in enumerate(group_sets):
        for cluster in exact[members]:
            if cluster.pk not in used:
                assigned[index] = cluster
                used.add(cluster.pk)
                break
    candidates = []
    for index, members in enumerate(group_sets):
        if index in assigned:
            continue
        possible = set().union(*(by_member[member] for member in members))
        for pk in possible:
            cluster = by_id[pk]
            if cluster.pk in used:
                continue
            common = len(members & memberships[cluster.pk])
            if common:
                union_size = len(members | memberships[cluster.pk])
                candidates.append((-common, -Fraction(common, union_size), cluster.created_at,
                                   cluster.pk, tuple(sorted(members)), index, cluster))
    for *_, index, cluster in sorted(candidates):
        if index not in assigned and cluster.pk not in used:
            assigned[index] = cluster
            used.add(cluster.pk)
    return assigned


def load_graph_suppliers():
    return list(Supplier.objects.order_by('pk').prefetch_related(
        'directorships__director', 'directorships__person_identity', 'directorships__source_observation',
        'ownerships__owner', 'ownerships__person_identity', 'ownerships__source_observation',
        'contracts', 'selected_facts__observation'))


def impact_boundary(index, states, memberships, seeds):
    """Close over both previous and current features and previous membership."""
    neighbours = defaultdict(set)
    features = defaultdict(set)
    for pk, keys in index.company_features.items():
        for key in keys:
            features[key].add(pk)
    for state in states.values():
        for key in state.feature_keys:
            features[key].add(state.supplier_id)
    company_keys = defaultdict(set)
    for key, members in features.items():
        for member in members:
            company_keys[member].add(key)
    for members in memberships.values():
        for member in members:
            neighbours[member].add(members)
    pending, affected, seen_keys, seen_groups = list(seeds), set(), set(), set()
    while pending:
        member = pending.pop()
        if member in affected:
            continue
        affected.add(member)
        for key in company_keys[member] - seen_keys:
            seen_keys.add(key)
            pending.extend(features[key] - affected)
        for group in neighbours[member] - seen_groups:
            seen_groups.add(group)
            pending.extend(group - affected)
    return affected


def persist_evidence(index, states, input_digests, affected):
    old = {edge.key: edge for edge in EvidenceEdge.objects.filter(supplier_id__in=affected)}
    added, updated = [], []
    for key, payload in index.edges.items():
        if payload['company_id'] not in affected:
            continue
        semantic_hash = digest(semantic_edge(payload))
        previous = old.pop(key, None)
        if previous is None:
            added.append(EvidenceEdge(key=key, supplier_id=payload['company_id'], source_key=payload['source'],
                         target_key=payload['target'], relationship_type=payload['type'],
                         semantic_hash=semantic_hash, payload=payload))
        elif previous.semantic_hash == semantic_hash and previous.is_active:
            # Repeated retrieval is not new evidence; keep the published reference.
            index.edges[key] = previous.payload
        else:
            previous.semantic_hash, previous.payload, previous.is_active = semantic_hash, payload, True
            updated.append(previous)
    for edge in old.values():
        if edge.is_active:
            edge.is_active = False
            updated.append(edge)
    if added:
        EvidenceEdge.objects.bulk_create(added)
    if updated:
        EvidenceEdge.objects.bulk_update(updated, ['semantic_hash', 'payload', 'is_active'])
    new_states, changed_states = [], []
    for pk in sorted(affected & index.suppliers.keys()):
        value = input_digests[pk]
        if pk not in states:
            new_states.append(GraphInputState(supplier_id=pk, digest=value,
                              feature_keys=sorted(index.company_features[pk]), algorithm_version=ALGORITHM_VERSION))
        elif states[pk].digest != value or states[pk].algorithm_version != ALGORITHM_VERSION:
            state = states[pk]
            state.digest, state.feature_keys, state.algorithm_version = value, sorted(index.company_features[pk]), ALGORITHM_VERSION
            changed_states.append(state)
    if new_states:
        GraphInputState.objects.bulk_create(new_states)
    if changed_states:
        GraphInputState.objects.bulk_update(changed_states, ['digest', 'feature_keys', 'algorithm_version'])


def publish_snapshot(cluster, payload, members, as_of, state='active'):
    previous = cluster.current_snapshot
    value = graph_hash(payload, state)
    if previous and previous.graph_hash == value:
        return previous, False
    previous_members = set(previous.member_ids) if previous else set()
    previous_edges = {edge['id']: semantic_edge(edge) for edge in previous.payload['links']} if previous else {}
    previous_nodes = {node['id']: node for node in previous.payload['nodes']} if previous else {}
    nodes = {node['id']: node for node in payload['nodes']}
    edges = {edge['id']: semantic_edge(edge) for edge in payload['links']}
    snapshot = GraphSnapshot.objects.create(
        cluster=cluster, version=previous.version + 1 if previous else 1,
        graph_hash=value, algorithm_version=ALGORITHM_VERSION, state=state, as_of=as_of,
        member_ids=sorted(members), payload=payload, previous=previous,
        changes={'added_members': sorted(set(members) - previous_members),
                 'removed_members': sorted(previous_members - set(members)),
                 'added_edges': sorted(edges.keys() - previous_edges.keys()),
                 'removed_edges': sorted(previous_edges.keys() - edges.keys()),
                 'changed_nodes': sorted(key for key in nodes.keys() & previous_nodes.keys() if nodes[key] != previous_nodes[key]),
                 'changed_edges': sorted(key for key in edges.keys() & previous_edges.keys()
                                         if edges[key] != previous_edges[key])},
        legacy_explanation=cluster.ai_explanation,
        legacy_explanation_fingerprint='')
    cluster.current_snapshot = snapshot
    cluster.save(update_fields=['current_snapshot'])
    return snapshot, True


@transaction.atomic
def rebuild_clusters(as_of=None, supplier_ids=None, publication_guard=None):
    as_of = as_of or timezone.localdate()
    if connection.vendor == "postgresql":
        # A row lock alone cannot serialize creation when the cluster table is empty.
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (REBUILD_LOCK,))
    existing = list(RiskCluster.objects.select_for_update(of=('self',)).order_by("pk").select_related('current_snapshot').prefetch_related("suppliers"))
    memberships = {cluster.pk: frozenset(s.pk for s in cluster.suppliers.all()) for cluster in existing}
    suppliers = load_graph_suppliers()
    index = EvidenceIndex(suppliers, as_of)
    director_map = build_director_map(suppliers, as_of)
    weights = get_risk_weights()
    states = {state.supplier_id: state for state in GraphInputState.objects.all()}
    company_edges = defaultdict(list)
    for edge in index.edges.values():
        company_edges[edge['company_id']].append(semantic_edge(edge))
    input_digests = {s.pk: digest({'algorithm': ALGORITHM_VERSION, 'company': index.nodes[f'company:{s.pk}'],
                        'edges': sorted(company_edges[s.pk], key=lambda edge: edge['id']),
                        'business': analysis_fingerprint([s], weights, as_of)}) for s in suppliers}
    dirty = {pk for pk, value in input_digests.items()
             if pk not in states or states[pk].digest != value or states[pk].algorithm_version != ALGORITHM_VERSION}
    dirty.update(pk for c in existing if c.current_snapshot_id is None for pk in memberships[c.pk])
    seeds = dirty | set(supplier_ids or [])
    active_memberships = {c.pk: memberships[c.pk] for c in existing if c.is_active}
    affected = impact_boundary(index, states, active_memberships, seeds)
    all_groups = index.components()
    groups = [group for group in all_groups if any(s.pk in affected for s in group)]
    relevant = [c for c in existing if memberships[c.pk] & affected or (c.is_active and not memberships[c.pk])]
    assigned = match_clusters(groups, relevant, memberships)
    summary = {"analyzed": len(suppliers), "groups": len(all_groups), "created": 0,
               "updated": 0, "unchanged": len(all_groups) - len(groups), "retired": 0,
               'affected_companies': len(affected), 'snapshots_created': 0, 'results': []}
    persist_evidence(index, states, input_digests, affected)
    # Preserve pre-snapshot records honestly: old membership/text, without invented edges.
    for cluster in relevant:
        if cluster.current_snapshot_id is None:
            payload = {'nodes': [index.nodes[f'company:{pk}'] for pk in sorted(memberships[cluster.pk])], 'links': []}
            publish_snapshot(cluster, payload, memberships[cluster.pk], as_of, 'legacy')
            summary['snapshots_created'] += 1
    predecessors = {c.pk: c.current_snapshot for c in relevant if c.is_active}
    continuing = set()
    published = []
    for group_index, group in enumerate(groups):
        fingerprint = analysis_fingerprint(group, weights, as_of)
        total = sum((contract.amount for supplier in group for contract in supplier.contracts.all()), Decimal("0"))
        members = frozenset(s.pk for s in group)
        payload = index.graph(members)
        shared = defaultdict(set)
        for edge in payload['links']:
            if not edge['common_contact']:
                shared[(edge['target'], edge['type'])].add(edge['company_id'])
        kinds = {kind for (_, kind), ids in shared.items() if len(ids) > 1}
        score = min(100, sum(weights.get(kind, 35 if kind == 'owner' else 0) for kind in kinds)
                    + max(0, len(group) - 2) * weights['group_size'])
        values = {"name": generate_cluster_name(group), "risk_score": score,
                  "total_contract_amount": total, "analysis_fingerprint": fingerprint, "is_active": True}
        cluster = assigned.get(group_index)
        if cluster is None:
            cluster = RiskCluster.objects.create(**values, last_analyzed_at=timezone.now())
            cluster.suppliers.set(group)
            summary["created"] += 1
        else:
            if not cluster.is_active and cluster.current_snapshot:
                predecessors[cluster.pk] = cluster.current_snapshot
            changed_input = cluster.analysis_fingerprint != fingerprint
            changed_graph = not cluster.current_snapshot or cluster.current_snapshot.graph_hash != graph_hash(payload)
            fields = [field for field, value in values.items() if getattr(cluster, field) != value]
            for field in fields:
                setattr(cluster, field, values[field])
            if (changed_input or changed_graph) and not cluster.explanation_stale:
                cluster.explanation_stale = True
                fields.append("explanation_stale")
            if fields or changed_graph:
                cluster.last_analyzed_at = timezone.now()
                cluster.save(update_fields=[*fields, "last_analyzed_at", "updated_at"])
                summary["updated"] += 1
            else:
                summary["unchanged"] += 1
            if memberships[cluster.pk] != frozenset(s.pk for s in group):
                cluster.suppliers.set(group)
        continuing.add(cluster.pk)
        snapshot, created = publish_snapshot(cluster, payload, members, as_of)
        summary['results'].append({'cluster_uuid': str(cluster.uuid), 'version': snapshot.version,
                                   'graph_hash': snapshot.graph_hash, 'state': snapshot.state})
        if created:
            summary['snapshots_created'] += 1
            published.append(snapshot)
    for cluster in relevant:
        if cluster.is_active and cluster.pk not in continuing:
            cluster.is_active = False
            cluster.explanation_stale = True
            cluster.save(update_fields=["is_active", "explanation_stale", "updated_at"])
            summary["retired"] += 1
            payload = {'nodes': [node for node in cluster.current_snapshot.payload['nodes'] if node['kind'] == 'company'], 'links': []}
            snapshot, created = publish_snapshot(cluster, payload, memberships[cluster.pk], as_of, 'retired')
            summary['results'].append({'cluster_uuid': str(cluster.uuid), 'version': snapshot.version,
                                       'graph_hash': snapshot.graph_hash, 'state': snapshot.state})
            if created:
                summary['snapshots_created'] += 1
                published.append(snapshot)
    targets_by_member = defaultdict(list)
    predecessors_by_member = defaultdict(set)
    for previous in predecessors.values():
        if previous.state != 'retired':
            for member in previous.member_ids:
                predecessors_by_member[member].add(previous.pk)
    for snapshot in published:
        if snapshot.state == 'active':
            for member in snapshot.member_ids:
                targets_by_member[member].append(snapshot)
    relations = []
    for previous in predecessors.values():
        targets = {target.pk: target for member in previous.member_ids for target in targets_by_member[member]}
        if not targets:
            targets = {s.pk: s for s in published if s.cluster_id == previous.cluster_id}
        for target in targets.values():
            incoming = set().union(*(predecessors_by_member[member] for member in target.member_ids)) if target.state == 'active' else {previous.pk}
            kind = ('retired' if target.state == 'retired' else 'merge_split' if len(targets) > 1 and len(incoming) > 1 else
                    'split' if len(targets) > 1 else
                    'merge' if len(incoming) > 1 else 'reactivated' if previous.state == 'retired' else 'updated')
            relations.append(ClusterLineage(source=previous, target=target, kind=kind,
                             shared_member_ids=sorted(set(previous.member_ids) & set(target.member_ids))))
    if relations:
        ClusterLineage.objects.bulk_create(relations)
    if publication_guard:
        publication_guard()
    return summary
