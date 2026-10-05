from django.db.models import Q
from django.utils import timezone

from .models import Directorship


def current_role_filter(prefix=''):
    """Roles use [start_date, end_date); an unknown bound remains unknown."""
    today = timezone.localdate()
    return (
        (Q(**{prefix + 'start_date__isnull': True}) | Q(**{prefix + 'start_date__lte': today}))
        & (Q(**{prefix + 'end_date__isnull': True}) | Q(**{prefix + 'end_date__gt': today}))
    )


def current_roles():
    return Directorship.objects.filter(current_role_filter()).select_related('supplier', 'director')
