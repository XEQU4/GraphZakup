from datetime import timedelta
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import IngestionLease, IngestionRun


class IngestionBusy(Exception):
    pass


class LeaseLost(Exception):
    pass


class RunLease:
    KEY = 'procurement-ingestion'

    def __init__(self, token):
        self.token = token

    @classmethod
    @transaction.atomic
    def acquire(cls):
        now = timezone.now()
        row, _ = IngestionLease.objects.get_or_create(key=cls.KEY, defaults={'expires_at': now})
        row = IngestionLease.objects.select_for_update().get(pk=row.pk)
        if row.expires_at > now:
            raise IngestionBusy('ingestion_busy')
        if row.run_id:
            IngestionRun.objects.filter(pk=row.run_id, status='running').update(
                status='failed', error_code='lease_expired', finished_at=now,
            )
        row.token = uuid.uuid4()
        row.expires_at = now + timedelta(seconds=max(60, settings.INGESTION_LEASE_SECONDS))
        row.run = None
        row.save(update_fields=['token', 'expires_at', 'run'])
        return cls(row.token)

    def attach(self, run):
        if not IngestionLease.objects.filter(key=self.KEY, token=self.token, expires_at__gt=timezone.now()).update(run=run):
            raise LeaseLost('ingestion_lease_lost')

    def ensure_owned(self):
        # Called inside each write transaction, serializing publication with lease takeover.
        row = IngestionLease.objects.select_for_update().get(key=self.KEY)
        if row.token != self.token or row.expires_at <= timezone.now():
            raise LeaseLost('ingestion_lease_lost')

    def heartbeat(self):
        now = timezone.now()
        if not IngestionLease.objects.filter(key=self.KEY, token=self.token, expires_at__gt=now).update(
                expires_at=now + timedelta(seconds=max(60, settings.INGESTION_LEASE_SECONDS))):
            raise LeaseLost('ingestion_lease_lost')

    def release(self):
        IngestionLease.objects.filter(key=self.KEY, token=self.token).update(expires_at=timezone.now())
