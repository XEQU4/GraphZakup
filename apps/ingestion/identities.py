from decimal import Decimal
import hashlib

from django.db import transaction

from apps.owners.models import Director, Directorship, Owner, Ownership, PersonIdentity
from .models import IdentityCandidate, PersonSourceIdentity
from .normalizers import normalize_bin, normalize_date


def normalized_name(value):
    return ' '.join(value.casefold().split())


def role_observation_data(supplier, observation):
    """A failed or foreign response cannot change a company's role history."""
    if observation.status != 'success':
        return None
    data = observation.normalized_values
    if (observation.supplier_id != supplier.pk or observation.subject_key != f'company:{supplier.bin}'
            or not isinstance(data, dict) or normalize_bin(data.get('bin')) != supplier.bin):
        raise ValueError('role_observation_identity_invalid')
    return data


def latest_role_observed_at(role):
    times = [role.observed_from] if role.observed_from else []
    previous = role.source_observation
    if previous:
        times.append(previous.observed_at)
    return max(times) if times else None


def stale_other_source(role, observation):
    latest = latest_role_observed_at(role)
    return role.source != observation.source and latest is not None and observation.observed_at < latest


def ensure_role_order(current, observation):
    for role in current:
        latest = latest_role_observed_at(role)
        if latest is not None and observation.observed_at < latest:
            raise ValueError('out_of_order_role_observation')


def validate_role_interval(dates):
    if dates['start_date'] and dates['end_date'] and dates['end_date'] < dates['start_date']:
        raise ValueError('invalid_role_interval')


@transaction.atomic
def resolve_person(supplier, observation, role, name, iin='', verified=False):
    if role not in ('director', 'owner') or not isinstance(name, str):
        raise ValueError('person_name_invalid')
    name = ' '.join(name.split())
    if not name or len(name) > 255:
        raise ValueError('person_name_invalid')
    name_key = normalized_name(name)
    if verified:
        iin = normalize_bin(iin)
        scope = 'iin:' + iin
    else:
        iin = ''
        scope = f'{observation.source}:{supplier.bin}:{role}:' + hashlib.sha256(name_key.encode()).hexdigest()
    person, _ = PersonIdentity.objects.get_or_create(
        scope_key=scope, defaults={'full_name': name, 'iin': iin, 'is_verified': verified},
    )
    field, Model = ('director', Director) if role == 'director' else ('owner', Owner)
    if not getattr(person, field + '_id'):
        representation = Model.objects.create(full_name=name, iin=iin)
        setattr(person, field, representation)
        person.save(update_fields=[field])
    # One source identity per company/name observation, even for a verified shared person.
    source_key = f'{supplier.bin}:{role}:' + hashlib.sha256((scope + ':' + name_key).encode()).hexdigest()
    identity, created = PersonSourceIdentity.objects.get_or_create(
        source=observation.source, source_key=source_key,
        defaults={'supplier': supplier, 'person': person, 'role': role, 'observed_name': name,
                  'normalized_name': name_key, 'observation': observation},
    )
    # The other identity creates the pair when it first appears. A replay does not
    # need to rescan every existing namesake or recreate unchanged candidates.
    if not created:
        return person
    for other in PersonSourceIdentity.objects.filter(normalized_name=name_key).exclude(person=person).select_related('person').iterator():
        if other.person.is_verified and person.is_verified:
            # Different confirmed IINs are already negative identity evidence.
            status = 'rejected'
        else:
            status = 'pending'
        left, right = sorted((identity.pk, other.pk))
        IdentityCandidate.objects.get_or_create(left_id=left, right_id=right, defaults={
            'confidence': Decimal('0.250'), 'status': status,
            'evidence': {'rule': 'same_name_v1', 'sources': sorted({identity.source, other.source}),
                         'requires_identifier_verification': True},
        })
    return person


@transaction.atomic
def synchronize_director(supplier, observation):
    data = role_observation_data(supplier, observation)
    if data is None:
        return
    name = data.get('director_name')
    # Missing/unknown fields cannot close the last known role.
    if name in (None, '') and data.get('director_absent') is not True:
        return
    person = None
    if name:
        person = resolve_person(supplier, observation, 'director', name,
                                data.get('director_iin', ''), data.get('director_iin_verified') is True)
    current = list(Directorship.objects.select_for_update(of=('self',)).select_related('source_observation').filter(
        supplier=supplier, is_current=True))
    # Applying saved source priorities replays observations from both sources.
    # An older other-source record is still evidence, but cannot replace a newer
    # episode or make all future enrichment fail on the same saved replay.
    if any(stale_other_source(role, observation) for role in current):
        return
    ensure_role_order(current, observation)
    role = next((item for item in current if person and item.person_identity_id == person.pk), None)
    for item in current:
        if role and item.pk == role.pk:
            continue
        if item.observed_from and observation.observed_at < item.observed_from:
            raise ValueError('out_of_order_role_observation')
        item.is_current = False
        item.observed_until = observation.observed_at
        # Observation end is not a proven legal end date.
        item.save(update_fields=['is_current', 'observed_until'])
    if person is None:
        return
    dates = {key: normalize_date(data.get('director_' + key)) for key in ('start_date', 'end_date')}
    validate_role_interval(dates)
    if role is None:
        Directorship.objects.create(
            supplier=supplier, director=person.director, person_identity=person, source=observation.source,
            source_observation=observation, identity_status='verified' if person.is_verified else 'source_scoped',
            observed_from=observation.observed_at, **dates,
        )
    else:
        validate_role_interval({key: value if value is not None else getattr(role, key) for key, value in dates.items()})
        changed = role.source != observation.source or role.source_observation_id != observation.pk
        for key, value in dates.items():
            if value is not None and getattr(role, key) != value:
                setattr(role, key, value)
                changed = True
        if changed:
            role.source_observation = observation
            role.source = observation.source
            role.save(update_fields=['start_date', 'end_date', 'source', 'source_observation'])


@transaction.atomic
def synchronize_owners(supplier, observation):
    data = role_observation_data(supplier, observation)
    if data is None:
        return
    if data.get('owners_complete') is not True:
        return
    if not isinstance(data.get('owners'), list):
        raise ValueError('complete_owner_list_missing')
    current = list(Ownership.objects.select_for_update(of=('self',)).select_related('source_observation').filter(
        supplier=supplier, source=observation.source, is_current=True))
    ensure_role_order(current, observation)
    observed = set()
    for item in data.get('owners', []):
        person = resolve_person(supplier, observation, 'owner', item['full_name'],
                                item.get('iin', ''), item.get('iin_verified') is True)
        share = Decimal(str(item['share_percent'])) if item.get('share_percent') is not None else None
        if share is not None and (not share.is_finite() or not 0 <= share <= 100):
            raise ValueError('invalid_share_percent')
        if share is not None:
            share = Ownership._meta.get_field('share_percent').clean(share, None)
        dates = {key: normalize_date(item.get(key)) for key in ('start_date', 'end_date')}
        validate_role_interval(dates)
        role = Ownership.objects.select_for_update(of=('self',)).select_related('source_observation').filter(
            supplier=supplier, person_identity=person, is_current=True).first()
        if role is None:
            Ownership.objects.create(
                supplier=supplier, owner=person.owner, person_identity=person, source=observation.source,
                source_observation=observation, share_percent=share, observed_from=observation.observed_at,
                identity_status='verified' if person.is_verified else 'source_scoped', **dates,
            )
        else:
            if stale_other_source(role, observation):
                observed.add(person.pk)
                continue
            ensure_role_order([role], observation)
            validate_role_interval({key: value if value is not None else getattr(role, key) for key, value in dates.items()})
            role.share_percent, role.source_observation = share, observation
            role.source = observation.source
            for key, value in dates.items():
                if value is not None:
                    setattr(role, key, value)
            role.save(update_fields=['share_percent', 'source', 'source_observation', 'start_date', 'end_date'])
        observed.add(person.pk)
    # Only a complete, successful owner list from the same source can retire roles.
    Ownership.objects.filter(supplier=supplier, source=observation.source, is_current=True).exclude(
        person_identity_id__in=observed,
    ).update(is_current=False, observed_until=observation.observed_at)
