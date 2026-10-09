"""Durable bounded collection cycles shared by Celery and the management command."""
import json
from collections import Counter
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F, OuterRef, Q, Subquery
from django.utils import timezone

from apps.ai.services import refresh_graph_analysis
from apps.companies.models import Supplier
from apps.core.models import SystemSetting
from .leases import IngestionBusy, RunLease
from .models import IngestionRun, SourceObservation
from .parsers.kgd import KgdParser, LEGAL_TYPES, TAXPAYER_SOURCE
from .providers import SourceProviders
from .services import IngestionFailure, run_pipeline
from .transport import HttpTransport

PREFIX = 'background-collection:'


class CycleLease(RunLease):
    KEY = 'background-collection-cycle'


def read_state(stage):
    value = SystemSetting.objects.filter(key=PREFIX + stage).values_list('value', flat=True).first()
    return json.loads(value) if value else {}


def save_state(stage, value):
    SystemSetting.objects.update_or_create(key=PREFIX + stage, defaults={'value': json.dumps(value)})


def collection_status():
    from apps.contracts.models import Contract
    return {'latest_cycle': read_state('latest'),
            'sources': {stage: read_state(stage) for stage in ('goszakup_contracts', *SourceProviders.COMPANY_SOURCES, 'kgd')},
            'totals': {'companies': Supplier.objects.count(), 'contracts': Contract.objects.count()}}


def due_companies(source, *, version, now, limit):
    """Oldest attempted first; failures wait before retry and never starve new IDs."""
    latest = SourceObservation.objects.filter(supplier_id=OuterRef('pk'), source=source).order_by('-observed_at', '-pk')
    companies = Supplier.objects.annotate(
        attempt_time=Subquery(latest.values('observed_at')[:1]),
        attempt_status=Subquery(latest.values('status')[:1]),
        attempt_version=Subquery(latest.values('parser_version')[:1]),
    )
    fresh_cutoff = now - timedelta(days=7)
    retry_cutoff = now - timedelta(seconds=settings.BACKGROUND_RETRY_SECONDS)
    eligible = (Q(attempt_time__isnull=True)
                | Q(attempt_time__lt=retry_cutoff) & (
                    ~Q(attempt_status__in=['success', 'not_found'])
                    | Q(attempt_time__lt=fresh_cutoff) | ~Q(attempt_version=version)))
    return companies.filter(eligible).order_by(F('attempt_time').asc(nulls_first=True), 'pk')[:limit]


def registered_subject_type(company):
    """Use explicit saved registration evidence, never a person's name or ID shape."""
    prior = company.source_observations.filter(source=TAXPAYER_SOURCE, status='success').order_by('-observed_at', '-pk').first()
    if prior and prior.normalized_values.get('kgd_taxpayer_type') in LEGAL_TYPES | {'IP'}:
        return prior.normalized_values['kgd_taxpayer_type']
    registry = company.source_observations.filter(source='goszakup_supplier', status='success',
        parser_version__in=['2.2', SourceProviders.VERSION], observed_at__gte=timezone.now() - timedelta(days=7)).order_by('-observed_at', '-pk').first()
    if not registry:
        return None
    form = str(registry.normalized_values.get('kopf') or '').strip().casefold()
    if form == 'индивидуальное (личное) предпринимательство':
        return 'IP'
    if form in {'товарищество с ограниченной ответственностью', 'акционерное общество',
                'государственное учреждение', 'республиканское государственное предприятие',
                'коммунальное государственное предприятие', 'коммунальное государственное учреждение'}:
        return 'UL'
    return None


def run_background_cycle(*, providers=None):
    if not settings.ENABLE_SCHEDULED_IMPORT:
        return {'status': 'disabled'}
    try:
        cycle = CycleLease.acquire()
    except IngestionBusy:
        return {'status': 'busy'}
    own_provider = providers is None
    provider = providers or SourceProviders(transport=HttpTransport(
        min_interval=max(3, settings.INGESTION_REQUEST_INTERVAL), retries=0, cache_ttl=0,
        heartbeat=cycle.heartbeat, max_requests=settings.BACKGROUND_MAX_REQUESTS))
    summary = {'status': 'completed', 'stages': {}}
    touched = set(read_state('pending').get('company_ids', []))

    def execute(**options):
        cycle.heartbeat()
        try:
            run = run_pipeline(providers=provider, **options)
        except IngestionFailure as error:
            run = IngestionRun.objects.get(uuid=error.run_id)
        # Includes partially accepted contracts/company checks, not just successful runs.
        touched.update(run.observations.exclude(supplier_id=None).values_list('supplier_id', flat=True))
        save_state('pending', {'company_ids': sorted(touched)})
        return run

    def available(host):
        transport = provider.transport
        state = read_state('host:' + host)
        until = datetime.fromisoformat(state['next_due']) if state.get('next_due') else None
        if until and until > timezone.now():
            return False
        if host in transport.blocked_hosts:
            save_state('host:' + host, {'next_due': (timezone.now() + timedelta(
                seconds=settings.BACKGROUND_SOURCE_COOLDOWN_SECONDS)).isoformat(), 'status': 'paused'})
            return False
        return (host not in transport.blocked_hosts
                and (transport.max_requests is None or transport.requests_made < transport.max_requests))

    try:
        for stage in ('goszakup_contracts', *SourceProviders.COMPANY_SOURCES, 'kgd'):
            cycle.heartbeat()
            now = timezone.now()
            state = read_state(stage)
            if state.get('next_due') and datetime.fromisoformat(state['next_due']) > now:
                summary['stages'][stage] = {'status': 'waiting'}
                continue
            if stage == 'kgd' and not (settings.ENABLE_SCHEDULED_KGD and settings.ENABLE_KGD_CHECKS and provider.kgd_ready):
                summary['stages'][stage] = {'status': 'disabled'}
                continue
            host = ('portal.kgd.gov.kz' if stage == 'kgd' else 'pk.adata.kz' if stage == 'adata' else 'old.goszakup.gov.kz')
            if not available(host):
                summary['stages'][stage] = {'status': 'source_paused'}
                continue
            interval = max(settings.BACKGROUND_INTERVAL_SECONDS, 3600 if stage == 'goszakup_contracts' else 1800 if stage == 'kgd' else 0)
            next_state = {'started_at': now.isoformat(), 'next_due': (now + timedelta(seconds=interval)).isoformat(),
                          'status': 'running'}
            save_state(stage, next_state)
            runs = []
            try:
                if stage == 'goszakup_contracts':
                    runs.append(execute(mode='update', total=settings.BACKGROUND_CONTRACT_BATCH, contracts_only=True))
                elif stage == 'kgd':
                    candidates = due_companies(TAXPAYER_SOURCE, version=KgdParser.VERSION, now=now, limit=1000)
                    for company in candidates:
                        kind = registered_subject_type(company)
                        if kind is None:
                            continue
                        if len(runs) >= settings.BACKGROUND_KGD_BATCH or not available(host):
                            break
                        client = provider.kgd_client()
                        client.taxpayer_type = kind
                        service = 'tax_debt' if kind in LEGAL_TYPES and client._valid_token(client.account_tokens.get(company.bin)) else 'taxpayer'
                        runs.append(execute(mode='kgd', total=1, company_bin=company.bin, kgd_service=service))
                else:
                    for company in due_companies(stage, version=provider.VERSION, now=now, limit=settings.BACKGROUND_COMPANY_BATCH):
                        if not available(host):
                            break
                        runs.append(execute(mode='enrich', total=1, company_bin=company.bin, company_sources=[stage],
                            cluster_builder=lambda: {'deferred_to_cycle_refresh': True}))
                outcomes = dict(Counter(run.status for run in runs))
                next_state.update(status='completed' if all(run.status == 'succeeded' for run in runs) else 'partial',
                    runs=[str(run.uuid) for run in runs], outcomes=outcomes,
                    errors=dict(Counter(issue.error_code for run in runs for issue in run.issues.filter(resolved=False))))
                source_outage = any(code.startswith('source_http_') or code in {
                    'source_request_failed', 'source_challenge_or_rate_limit', 'source_batch_circuit_open',
                    'source_request_budget_exhausted', 'kgd_access_denied'} for code in next_state['errors'])
                if not available(host) or source_outage:
                    next_state['next_due'] = (timezone.now() + timedelta(seconds=max(interval, settings.BACKGROUND_SOURCE_COOLDOWN_SECONDS))).isoformat()
            except IngestionBusy:
                next_state.update(status='busy')
            except Exception:
                # Never include source text, SQL, identifiers or credentials in Celery results.
                next_state.update(status='failed', errors={'background_stage_failed': 1})
            finally:
                cycle.heartbeat()
                save_state(stage, next_state)
                summary['stages'][stage] = next_state
        # Refresh even after a failed stage accepted some records. Lease fencing
        # protects the same immutable graph/template publication as manual jobs.
        lease = RunLease.acquire()
        try:
            summary['graph'] = refresh_graph_analysis(supplier_ids=sorted(touched) or None,
                publication_guard=lease.ensure_owned)
            save_state('pending', {'company_ids': []})
        finally:
            lease.release()
        summary['requests'] = provider.transport.requests_made
        if any(stage.get('status') in ('partial', 'failed') for stage in summary['stages'].values()):
            summary['status'] = 'partial'
        summary['finished_at'] = timezone.now().isoformat()
        with transaction.atomic():
            cycle.ensure_owned()
            save_state('latest', summary)
        return summary
    finally:
        try:
            if own_provider:
                provider.close()
        finally:
            cycle.release()
