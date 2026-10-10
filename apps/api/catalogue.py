"""Shared directory scopes for list filters and their overview counts."""

from django.db.models import Exists, F, OuterRef, Q, Value
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Concat
from django.db.models.lookups import Exact

from apps.ingestion.models import SelectedFact
from apps.owners.models import Directorship, Ownership


def company_profile_scope(queryset, *, checked=True):
    """Require selected profile evidence for the exact displayed company identity."""
    supported = SelectedFact.objects.filter(
        supplier_id=OuterRef('pk'), field='name',
        observation__supplier_id=OuterRef('pk'), observation__status='success',
        observation__source__in=['goszakup_supplier', 'adata'],
        observation__subject_key=Concat(Value('company:'), OuterRef('bin')),
    ).filter(
        Exact(KeyTextTransform('bin', F('observation__normalized_values')), OuterRef('bin')),
        Exact(KeyTextTransform('name', F('observation__normalized_values')), OuterRef('name')),
    )
    return queryset.alias(_profile_checked=Exists(supported)).filter(_profile_checked=checked)


def person_role_scope(queryset, *, current=True):
    """Count each saved identity once, even with several current roles."""
    queryset = queryset.alias(
        _current_director=Exists(Directorship.objects.filter(person_identity_id=OuterRef('pk'), is_current=True)),
        _current_owner=Exists(Ownership.objects.filter(person_identity_id=OuterRef('pk'), is_current=True)),
    )
    has_current_role = Q(_current_director=True) | Q(_current_owner=True)
    return queryset.filter(has_current_role if current else ~has_current_role)
