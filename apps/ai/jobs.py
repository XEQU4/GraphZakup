"""Explicit analysis/generation jobs with deduplication and publication fencing."""
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.graph.evidence import digest
from apps.graph.models import RiskCluster
from apps.ingestion.leases import RunLease, IngestionBusy
from .models import AnalysisJob, AnalysisState, AnalysisTarget, Explanation
from .providers import configuration, reuse_key, generate, ProviderError, PROMPT_VERSION
from .services import (collect_inputs, input_hash, prepare_analysis, explanation_content,
                       template_for, publish_explanation)


def generation_options(config):
    return {**config.public(), 'prompt_version': PROMPT_VERSION}


def set_target(cluster, job):
    target, created = AnalysisTarget.objects.get_or_create(cluster=cluster, defaults={'job': job})
    if not created and target.job_id != job.pk:
        target.job = job
        target.save(update_fields=['job'])


@transaction.atomic
def request_analysis(user, cluster_id, *, use_model=True, retry_model=False):
    if user is not None and (not user.is_authenticated or not user.is_staff):
        raise ValueError('staff_required')
    if type(use_model) is not bool or type(retry_model) is not bool:
        raise ValueError('invalid_options')
    cluster = RiskCluster.objects.select_for_update(of=('self',)).select_related('current_snapshot').get(pk=cluster_id)
    graph = cluster.current_snapshot
    if not graph or graph.state != 'active':
        raise ValueError('active_graph_required')
    config = configuration() if use_model else configuration('template')
    as_of = timezone.localdate()
    signature = input_hash(collect_inputs(graph, as_of))
    key = digest({'graph': graph.pk, 'input': signature, 'config': config.public(), 'prompt': PROMPT_VERSION})
    AnalysisJob.objects.filter(dedup_key=key, status__in=['pending', 'running'],
        created_at__lt=timezone.now() - timedelta(hours=1)).update(
            status='failed', error_code='job_expired', finished_at=timezone.now())
    job = AnalysisJob.objects.filter(dedup_key=key, status__in=['pending', 'running']).first()
    if job:
        set_target(cluster, job)
        return job, False
    completed = AnalysisJob.objects.filter(dedup_key=key, status__in=['succeeded', 'fallback']).order_by('-pk').first()
    already_current = completed and AnalysisState.objects.filter(cluster=cluster,
        analysis_id=completed.analysis_id, explanation_id=completed.explanation_id).exists()
    if already_current and (completed.status == 'succeeded' or not retry_model):
        set_target(cluster, completed)
        return completed, False
    job = AnalysisJob.objects.create(requested_by=user, graph_snapshot=graph,
        input_hash=signature, dedup_key=key, as_of=as_of, options=generation_options(config))
    set_target(cluster, job)
    transaction.on_commit(lambda: enqueue(job.pk))
    return job, True


def enqueue(pk):
    try:
        analyse_cluster_task.delay(pk)
    except Exception:
        AnalysisJob.objects.filter(pk=pk, status='pending').update(
            status='failed', error_code='broker_unavailable', finished_at=timezone.now())


@shared_task(bind=True, max_retries=5)
def analyse_cluster_task(self, pk):
    job = AnalysisJob.objects.select_related('graph_snapshot').get(pk=pk)
    if job.status != 'pending':
        return {'status': job.status}
    try:
        lease = RunLease.acquire()
    except IngestionBusy:
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30)
        AnalysisJob.objects.filter(pk=pk, status='pending').update(
            status='failed', error_code='ingestion_busy', finished_at=timezone.now())
        return {'status': 'failed'}
    try:
        if not AnalysisJob.objects.filter(pk=pk, status='pending').update(status='running'):
            return {'status': 'already_claimed'}
        with transaction.atomic():
            # Match request/expiry lock order: cluster before its job row.
            RiskCluster.objects.select_for_update().get(pk=job.graph_snapshot.cluster_id)
            claimed = AnalysisJob.objects.select_for_update().get(pk=pk)
            if claimed.status != 'running':
                return {'status': claimed.status}
            if not AnalysisTarget.objects.filter(cluster_id=job.graph_snapshot.cluster_id, job_id=pk).exists():
                raise ValueError('analysis_input_superseded')
            analysis, _ = prepare_analysis(job.graph_snapshot.cluster_id, as_of=job.as_of,
                expected_graph_id=job.graph_snapshot_id, expected_input_hash=job.input_hash)
            lease.ensure_owned()
            claimed.analysis = analysis
            claimed.save(update_fields=['analysis'])
    except ValueError as error:
        code = 'analysis_input_superseded' if str(error) in {'analysis_input_superseded', 'active_graph_required'} else 'analysis_failed'
        AnalysisJob.objects.filter(pk=pk, status='running').update(
            status='stale' if code == 'analysis_input_superseded' else 'failed', error_code=code, finished_at=timezone.now())
        return {'status': 'stale' if code == 'analysis_input_superseded' else 'failed'}
    except Exception:
        AnalysisJob.objects.filter(pk=pk, status='running').update(
            status='failed', error_code='analysis_failed', finished_at=timezone.now())
        raise
    finally:
        lease.release()

    try:
        if job.options['provider'] == 'template':
            explanation = template_for(analysis)
        else:
            config = configuration()
            if generation_options(config) != job.options:
                raise ProviderError('provider_configuration_changed')
            key = reuse_key(analysis, config)
            explanation = Explanation.objects.filter(reuse_key=key, status='ready').first()
            if not explanation:
                plan, usage = generate(analysis, config)
                explanation = Explanation.objects.get_or_create(reuse_key=key, defaults={
                    'analysis': analysis, 'provider': config.provider, 'model': config.model,
                    'prompt_version': PROMPT_VERSION, 'status': 'ready',
                    **explanation_content(analysis, plan), 'usage': usage,
                    'experimental_score': plan['risk_estimate'], 'experimental_evidence': plan['risk_evidence']})[0]
    except ProviderError as error:
        explanation = Explanation.objects.create(analysis=analysis,
            reuse_key=digest({'fallback_job': str(job.uuid)}), provider=job.options['provider'],
            model=job.options['model'], prompt_version=PROMPT_VERSION, status='fallback',
            **explanation_content(analysis), error_code=str(error))
    except Exception:
        AnalysisJob.objects.filter(pk=pk, status='running').update(
            status='failed', error_code='generation_failed', finished_at=timezone.now())
        raise
    with transaction.atomic():
        RiskCluster.objects.select_for_update().get(pk=job.graph_snapshot.cluster_id)
        claimed = AnalysisJob.objects.select_for_update().get(pk=pk)
        if claimed.status != 'running':
            return {'status': claimed.status}
        try:
            configuration_current = job.options['provider'] == 'template' or generation_options(configuration()) == job.options
        except ProviderError:
            configuration_current = False
        published = configuration_current and publish_explanation(analysis, explanation, expected_job_id=pk)
        claimed.explanation = explanation
        claimed.status = ('fallback' if explanation.status == 'fallback' else 'succeeded') if published else 'stale'
        claimed.error_code = explanation.error_code if published else 'analysis_input_superseded'
        claimed.finished_at = timezone.now()
        claimed.save(update_fields=['explanation', 'status', 'error_code', 'finished_at'])
    return {'status': claimed.status, 'analysis_version': analysis.version,
            'analysis_hash': analysis.analysis_hash, 'graph_version': analysis.graph_snapshot.version,
            'explanation_id': explanation.pk}
