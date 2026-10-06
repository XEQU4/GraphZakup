"""Personal coordinates are independent of graph and analysis versions."""
import math

from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.auth import get_user_model

from .models import GraphViewState, RiskCluster

RELATIONSHIPS = {'director', 'owner', 'address', 'phone', 'email'}


class ViewConflict(Exception):
    pass


def number(value, limit):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > limit:
        raise ValidationError('Coordinates must be finite numbers within bounds.')
    return value


def validate_view(payload, snapshot):
    if not isinstance(payload, dict) or set(payload) - {'positions', 'zoom', 'filters', 'selected', 'frozen'}:
        raise ValidationError('Invalid view fields.')
    ids = {node['id'] for node in snapshot.payload['nodes']}
    positions = payload.get('positions', {})
    if not isinstance(positions, dict) or len(positions) > len(ids) or set(positions) - ids:
        raise ValidationError('Positions must reference nodes in the selected snapshot.')
    cleaned = {}
    for key, value in positions.items():
        if not isinstance(value, dict) or set(value) != {'x', 'y', 'pinned'} or not isinstance(value['pinned'], bool):
            raise ValidationError('Invalid node position.')
        cleaned[key] = {'x': number(value['x'], 1e6), 'y': number(value['y'], 1e6), 'pinned': value['pinned']}
    zoom = payload.get('zoom', {'x': 0, 'y': 0, 'k': 1})
    if not isinstance(zoom, dict) or set(zoom) != {'x', 'y', 'k'}:
        raise ValidationError('Invalid zoom transform.')
    transform = {'x': number(zoom['x'], 1e7), 'y': number(zoom['y'], 1e7), 'k': number(zoom['k'], 8)}
    if transform['k'] < 0.05:
        raise ValidationError('Zoom must be between 0.05 and 8.')
    filters = payload.get('filters', sorted(RELATIONSHIPS))
    if not isinstance(filters, list) or any(not isinstance(kind, str) or kind not in RELATIONSHIPS for kind in filters):
        raise ValidationError('Unknown relationship filter.')
    selected = payload.get('selected')
    if selected is not None and (not isinstance(selected, str) or selected not in ids):
        raise ValidationError('Selected node is outside this snapshot.')
    frozen = payload.get('frozen', True)
    if not isinstance(frozen, bool):
        raise ValidationError('Frozen must be a boolean.')
    return {'positions': cleaned, 'zoom': transform, 'filters': sorted(set(filters)),
            'selected': selected, 'frozen': frozen}


def saved_view(user, cluster, snapshot):
    if not user.is_authenticated or snapshot is None:
        return {'revision': 0, 'payload': None}
    state = GraphViewState.objects.filter(user=user, cluster=cluster).first()
    if not state:
        return {'revision': 0, 'payload': None}
    payload = dict(state.payload)
    ids = {node['id'] for node in snapshot.payload['nodes']}
    payload['positions'] = {key: value for key, value in payload.get('positions', {}).items() if key in ids}
    if payload.get('selected') not in ids:
        payload['selected'] = None
    return {'revision': state.revision, 'snapshot_version': state.snapshot.version,
            'payload': payload, 'schema_version': state.schema_version}


@transaction.atomic
def save_view(user, cluster_id, snapshot_id, graph_digest, revision, payload):
    # Serialise first saves as well as updates; the unique constraint is a second guard.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    cluster = RiskCluster.objects.select_for_update(of=('self',)).select_related('current_snapshot').get(pk=cluster_id)
    if cluster.current_snapshot_id != snapshot_id or cluster.current_snapshot.graph_hash != graph_digest:
        raise ViewConflict('The current graph changed. Reload before saving.')
    state = GraphViewState.objects.select_for_update().filter(user=user, cluster=cluster).first()
    if revision != (state.revision if state else 0):
        raise ViewConflict('This view was changed in another tab. Reload before saving.')
    cleaned = validate_view(payload, cluster.current_snapshot)
    if state is None:
        state = GraphViewState.objects.create(user=user, cluster=cluster, snapshot=cluster.current_snapshot, payload=cleaned)
    elif state.payload != cleaned or state.snapshot_id != snapshot_id:
        state.payload, state.snapshot, state.revision = cleaned, cluster.current_snapshot, state.revision + 1
        state.save(update_fields=['payload', 'snapshot', 'revision', 'updated_at'])
    return {'revision': state.revision, 'payload': state.payload}
