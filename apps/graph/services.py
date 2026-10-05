"""Phase 1 cluster integrity; immutable evidence snapshots follow in phase 4."""

from collections import defaultdict
from decimal import Decimal
from fractions import Fraction
import hashlib
import json

from django.db import connection, transaction
from django.utils import timezone

from apps.companies.models import Supplier
from apps.core.utils import get_int_setting
from apps.graph.models import RiskCluster


EXCLUDED_EMAILS = {"info@adata.kz", "support@adata.kz"}
REBUILD_LOCK = 1196443459


def current_directorships(supplier, as_of=None):
    as_of = as_of or timezone.localdate()
    return [role for role in supplier.directorships.all()
            if (role.start_date is None or role.start_date <= as_of)
            and (role.end_date is None or role.end_date > as_of)]


def build_director_map(suppliers, as_of=None):
    as_of = as_of or timezone.localdate()
    return {supplier.pk: {role.director_id for role in current_directorships(supplier, as_of)}
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

    for i, s1 in enumerate(suppliers):
        for j in range(i + 1, len(suppliers)):
            if is_connected(s1, suppliers[j], director_map):
                parent[find(i)] = find(j)
    groups = defaultdict(list)
    for index, supplier in enumerate(suppliers):
        groups[find(index)].append(supplier)
    return sorted((sorted(group, key=lambda s: s.pk) for group in groups.values() if len(group) > 1),
                  key=lambda group: tuple(s.pk for s in group))


def get_risk_weights():
    defaults = {"director": 35, "address": 25, "phone": 20, "email": 15, "group_size": 5}
    return {kind: max(0, min(100, get_int_setting("risk_" + kind + "_weight", default)))
            for kind, default in defaults.items()}


def calculate_risk(suppliers, director_map, weights=None):
    weights = weights if weights is not None else get_risk_weights()
    suppliers, types = list(suppliers), set()
    for index, s1 in enumerate(suppliers):
        for s2 in suppliers[index + 1:]:
            types.update(get_connection_types(s1, s2, director_map))
    return min(100, sum(weights[kind] for kind in types)
               + max(0, len(suppliers) - 2) * weights["group_size"])


def generate_cluster_name(group, index=None):
    anchor = min(group, key=lambda supplier: (-supplier.risk_score, supplier.name, supplier.pk))
    name = anchor.name if len(anchor.name) <= 40 else anchor.name[:37] + "..."
    others = len(group) - 1
    return f"Группа: {name} и ещё {others}" if others else f"Группа: {name}"


def analysis_fingerprint(group, weights, as_of):
    data = []
    for supplier in sorted(group, key=lambda item: item.pk):
        directors = sorted((role.director_id, role.director.full_name, role.director.iin,
                            str(role.start_date), str(role.end_date))
                           for role in current_directorships(supplier, as_of))
        owners = sorted((role.owner_id, role.owner.full_name, role.owner.iin,
                         str(role.share_percent), role.owner.has_tax_debt,
                         role.owner.has_court_cases, role.owner.is_bankrupt, role.owner.blacklisted)
                        for role in supplier.ownerships.all())
        contracts = sorted((contract.pk, contract.contract_number, contract.tender_id,
                            contract.contract_gos_id, contract.title, str(contract.amount),
                            str(contract.contract_date), contract.customer_name,
                            contract.customer_bin, contract.winner)
                           for contract in supplier.contracts.all())
        data.append({"id": supplier.pk, "bin": supplier.bin, "name": supplier.name,
                     "address": supplier.address, "phone": supplier.phone,
                     "email": supplier.email.strip().lower(), "risk_score": supplier.risk_score,
                     "directors": directors, "owners": owners, "contracts": contracts})
    payload = {"version": "phase1-analysis-v1", "weights": weights, "suppliers": data}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def match_clusters(groups, existing, memberships):
    """Exact first; each remaining UUID can continue in only one component."""
    group_sets = [frozenset(s.pk for s in group) for group in groups]
    assigned, used = {}, set()
    by_age = sorted(existing, key=lambda cluster: (not cluster.is_active, cluster.created_at, cluster.pk))
    for index, members in enumerate(group_sets):
        for cluster in by_age:
            if cluster.pk not in used and memberships[cluster.pk] == members:
                assigned[index] = cluster
                used.add(cluster.pk)
                break
    candidates = []
    for index, members in enumerate(group_sets):
        if index in assigned:
            continue
        for cluster in existing:
            if not cluster.is_active or cluster.pk in used:
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


@transaction.atomic
def rebuild_clusters(as_of=None):
    as_of = as_of or timezone.localdate()
    if connection.vendor == "postgresql":
        # A row lock alone cannot serialize creation when the cluster table is empty.
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (REBUILD_LOCK,))
    existing = list(RiskCluster.objects.select_for_update().order_by("pk").prefetch_related("suppliers"))
    memberships = {cluster.pk: frozenset(s.pk for s in cluster.suppliers.all()) for cluster in existing}
    suppliers = list(Supplier.objects.order_by("pk").prefetch_related(
        "directorships__director", "ownerships__owner", "contracts"))
    director_map = build_director_map(suppliers, as_of)
    groups = find_connected_groups(suppliers, director_map)
    weights = get_risk_weights()
    assigned = match_clusters(groups, existing, memberships)
    summary = {"analyzed": len(suppliers), "groups": len(groups), "created": 0,
               "updated": 0, "unchanged": 0, "retired": 0}
    continuing = set()
    for index, group in enumerate(groups):
        fingerprint = analysis_fingerprint(group, weights, as_of)
        total = sum((contract.amount for supplier in group for contract in supplier.contracts.all()), Decimal("0"))
        values = {"name": generate_cluster_name(group), "risk_score": calculate_risk(group, director_map, weights),
                  "total_contract_amount": total, "analysis_fingerprint": fingerprint, "is_active": True}
        cluster = assigned.get(index)
        if cluster is None:
            cluster = RiskCluster.objects.create(**values, last_analyzed_at=timezone.now())
            cluster.suppliers.set(group)
            summary["created"] += 1
        else:
            changed_input = cluster.analysis_fingerprint != fingerprint
            fields = [field for field, value in values.items() if getattr(cluster, field) != value]
            for field in fields:
                setattr(cluster, field, values[field])
            if changed_input and not cluster.explanation_stale:
                cluster.explanation_stale = True
                fields.append("explanation_stale")
            if fields:
                cluster.last_analyzed_at = timezone.now()
                cluster.save(update_fields=[*fields, "last_analyzed_at", "updated_at"])
                summary["updated"] += 1
            else:
                summary["unchanged"] += 1
            if memberships[cluster.pk] != frozenset(s.pk for s in group):
                cluster.suppliers.set(group)
        continuing.add(cluster.pk)
    for cluster in existing:
        if cluster.is_active and cluster.pk not in continuing:
            cluster.is_active = False
            cluster.explanation_stale = True
            cluster.save(update_fields=["is_active", "explanation_stale", "updated_at"])
            summary["retired"] += 1
    return summary
