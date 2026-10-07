"""Explicit saved-data recalculation; no source collection or text generation."""
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.companies.models import Supplier
from apps.ingestion.leases import RunLease, IngestionBusy
from .evidence import digest, ALGORITHM_VERSION
from .models import GraphRebuildJob
from apps.ai.services import refresh_graph_analysis as rebuild_clusters


@transaction.atomic
def request_rebuild(user, supplier_ids):
    if not isinstance(supplier_ids, list) or len(supplier_ids) > 500 or any(type(pk) is not int or pk < 1 for pk in supplier_ids):
        raise ValueError('Select at most 500 valid company identifiers.')
    ids = sorted(set(supplier_ids))
    if set(Supplier.objects.filter(pk__in=ids).values_list('pk', flat=True)) != set(ids):
        raise ValueError('An unknown company was selected.')
    key = digest({'companies': ids, 'algorithm': ALGORITHM_VERSION})
    # Expired work remains visible in history and can be explicitly requested again.
    GraphRebuildJob.objects.filter(dedup_key=key, status__in=['pending', 'running'],
                                  created_at__lt=timezone.now() - timedelta(hours=1)).update(
        status='failed', error_code='job_expired', finished_at=timezone.now())
    job, created = GraphRebuildJob.objects.get_or_create(dedup_key=key, status__in=['pending', 'running'],
            defaults={'requested_by': user, 'supplier_ids': ids, 'status': 'pending'})
    if created:
        transaction.on_commit(lambda: enqueue(job.pk))
    return job, created


def enqueue(pk):
    try:
        rebuild_graph_task.delay(pk)
    except Exception:
        GraphRebuildJob.objects.filter(pk=pk, status='pending').update(
            status='failed', error_code='broker_unavailable', finished_at=timezone.now())


@shared_task(bind=True, max_retries=5)
def rebuild_graph_task(self, pk):
    job = GraphRebuildJob.objects.get(pk=pk)
    if job.status != 'pending':
        return {'status': job.status}
    try:
        lease = RunLease.acquire()
    except IngestionBusy:
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30)
        GraphRebuildJob.objects.filter(pk=pk, status='pending').update(
            status='failed', error_code='ingestion_busy', finished_at=timezone.now())
        return {'status': 'failed'}
    try:
        if not GraphRebuildJob.objects.filter(pk=pk, status='pending').update(status='running'):
            return {'status': 'already_claimed'}
        with transaction.atomic():
            # The job row and lease fence protect publication after expiry/takeover.
            claimed = GraphRebuildJob.objects.select_for_update().get(pk=pk)
            if claimed.status != 'running':
                return {'status': claimed.status}
            result = rebuild_clusters(supplier_ids=job.supplier_ids or None, publication_guard=lease.ensure_owned)
            claimed.status, claimed.summary, claimed.finished_at = 'succeeded', result, timezone.now()
            claimed.save(update_fields=['status', 'summary', 'finished_at'])
        return result
    except Exception as error:
        code = 'ingestion_lease_lost' if type(error).__name__ == 'LeaseLost' else 'graph_rebuild_failed'
        GraphRebuildJob.objects.filter(pk=pk, status='running').update(status='failed', error_code=code, finished_at=timezone.now())
        raise
    finally:
        lease.release()
