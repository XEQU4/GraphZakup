from django.db.models import Q, F
from django.db.models.fields.json import KeyTextTransform
from django.db.models.lookups import Exact
from django.utils import timezone

from .models import Directorship


def current_role_filter(prefix=''):
    """Roles use [start_date, end_date); an unknown bound remains unknown."""
    today = timezone.localdate()
    return (
        Q(**{prefix + 'is_current': True})
        & (Q(**{prefix + 'start_date__isnull': True}) | Q(**{prefix + 'start_date__lte': today}))
        & (Q(**{prefix + 'end_date__isnull': True}) | Q(**{prefix + 'end_date__gt': today}))
    )


def current_roles():
    return Directorship.objects.filter(current_role_filter()).select_related('supplier', 'director')


def confirmed_role_filter(prefix=''):
    return Q(**{
        prefix + 'identity_status': 'verified',
        prefix + 'person_identity__is_verified': True,
        prefix + 'director_id': F(prefix + 'person_identity__director_id'),
        prefix + 'source': F(prefix + 'source_observation__source'),
        prefix + 'source_observation__status': 'success',
        prefix + 'source_observation__supplier_id': F(prefix + 'supplier_id'),
        prefix + 'source_observation__normalized_values__director_iin_verified': True,
    }) & Q(Exact(KeyTextTransform('director_iin', F(prefix + 'source_observation__normalized_values')),
                 F(prefix + 'person_identity__iin')))


def is_confirmed_role(role):
    if not (role.identity_status == 'verified' and role.person_identity_id and role.source_observation_id):
        return False
    person, observation = role.person_identity, role.source_observation
    data = observation.normalized_values
    return (person.is_verified and bool(person.iin) and person.director_id == role.director_id
            and observation.supplier_id == role.supplier_id and observation.status == 'success'
            and observation.source == role.source and data.get('director_iin_verified') is True
            and data.get('director_iin') == person.iin)
