"""Independent, fair collection stages with durable progress and bounded budgets."""
from collections import Counter
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, Subquery
from django.utils import timezone

from apps.ai.services import refresh_graph_analysis
from .background import CycleLease, due_companies, read_state, registered_subject_type, save_state
from .crawl import collect_contract_slice, crawl_state
from .leases import IngestionBusy, RunLease
from .models import IngestionRun, SourceObservation
from apps.companies.models import Supplier
from .parsers.kgd import KgdParser, LEGAL_TYPES, TAXPAYER_SOURCE, DEBT_SOURCE
from .providers import SourceProviders
from .services import IngestionFailure, run_pipeline
from .transport import HttpTransport

STAGES = ('goszakup_supplier', 'adata', 'kgd', 'kgd_debt', 'goszakup_contracts', 'contract_history', 'contract_repair')


def enrichment_backlog():
    companies = Supplier.objects.all()
    for source in SourceProviders.COMPANY_SOURCES:
        companies = companies.annotate(**{source: Exists(SourceObservation.objects.filter(
            supplier_id=OuterRef('pk'), source=source))})
    return companies.exclude(goszakup_supplier=True, adata=True).count()


def eligible_kgd(provider, source, now):
    """Filter eligibility before applying the batch cap; debt has its own clock."""
    client = provider.kgd_client()
    ready, refresh = [], []
    candidates = due_companies(source, version=KgdParser.VERSION, now=now)
    successful = SourceObservation.objects.filter(supplier_id=OuterRef('pk'), status='success').order_by('-observed_at', '-pk')
    candidates = candidates.annotate(
        saved_kgd=Subquery(successful.filter(source=TAXPAYER_SOURCE).values('normalized_values')[:1]),
        saved_registry=Subquery(successful.filter(source='goszakup_supplier',
            parser_version__in=['2.2', SourceProviders.VERSION], observed_at__gte=now - timedelta(days=7))
            .values('normalized_values')[:1]))
    for company in candidates:
        kind = registered_subject_type(company)
        if kind is None or (source == DEBT_SOURCE and (kind not in LEGAL_TYPES
                or not client._valid_token(client.account_tokens.get(company.bin)))):
            continue
        (ready if company.attempt_time is None else refresh).append((company, kind))
    limit = settings.BACKGROUND_KGD_BATCH
    chosen = refresh[:limit // 2]
    return (chosen + ready + refresh[len(chosen):])[:limit]


def run_cycle(*, providers=None):
    if not settings.ENABLE_SCHEDULED_IMPORT:
        return {'status': 'disabled'}
    try:
        cycle = CycleLease.acquire()
    except IngestionBusy:
        return {'status': 'busy'}
    provider = providers or SourceProviders(transport=HttpTransport(
        min_interval=max(3, settings.INGESTION_REQUEST_INTERVAL), retries=0, cache_ttl=0,
        heartbeat=cycle.heartbeat, max_requests=settings.BACKGROUND_MAX_REQUESTS))
    summary = {'status': 'completed', 'stages': {}}
    touched = set(read_state('pending').get('company_ids', []))
    total_budget = settings.BACKGROUND_MAX_REQUESTS

    def remember(run):
        touched.update(run.observations.exclude(supplier_id=None).values_list('supplier_id', flat=True))
        save_state('pending', {'company_ids': sorted(touched)})
        return run

    def execute(**options):
        cycle.heartbeat()
        if options.get('company_bin'):
            touched.update(Supplier.objects.filter(bin=options['company_bin']).values_list('pk', flat=True))
            save_state('pending', {'company_ids': sorted(touched)})
        try:
            run = run_pipeline(providers=provider, **options)
        except IngestionFailure as error:
            run = IngestionRun.objects.get(uuid=error.run_id)
        return remember(run)

    def available(host):
        state = read_state('host:' + host)
        if state.get('next_due') and datetime.fromisoformat(state['next_due']) > timezone.now():
            return False
        if host in provider.transport.blocked_hosts:
            save_state('host:' + host, {'next_due': (timezone.now() + timedelta(
                seconds=settings.BACKGROUND_SOURCE_COOLDOWN_SECONDS)).isoformat(), 'status': 'paused'})
            return False
        return provider.transport.requests_made < provider.transport.max_requests

    try:
        # Rotate stage order as a second fairness guard when the global cap is hit.
        rotation = read_state('rotation').get('offset', 0) % len(STAGES)
        stages = STAGES[rotation:] + STAGES[:rotation]
        save_state('rotation', {'offset': (rotation + 1) % len(STAGES)})
        for stage in stages:
            cycle.heartbeat()
            now, state = timezone.now(), read_state(stage)
            if state.get('next_due') and datetime.fromisoformat(state['next_due']) > now:
                summary['stages'][stage] = {'status': 'waiting'}
                continue
            kgd = stage in ('kgd', 'kgd_debt')
            if stage in ('goszakup_contracts', 'contract_history'):
                backlog = enrichment_backlog()
                if backlog >= settings.BACKGROUND_ENRICHMENT_HIGH_WATER:
                    summary['stages'][stage] = {'status': 'enrichment_backlog', 'companies': backlog}
                    save_state(stage, {**state, 'status': 'enrichment_backlog', 'companies': backlog})
                    continue
            if kgd and not (settings.ENABLE_SCHEDULED_KGD and settings.ENABLE_KGD_CHECKS and provider.kgd_ready):
                summary['stages'][stage] = {'status': 'disabled'}
                continue
            host = 'portal.kgd.gov.kz' if kgd else 'pk.adata.kz' if stage == 'adata' else 'old.goszakup.gov.kz'
            # One stage cannot spend the entire cycle's HTTP budget.
            provider.transport.max_requests = min(total_budget, provider.transport.requests_made +
                (30 if stage == 'goszakup_supplier' else 20 if kgd or stage == 'adata' else 28))
            if not available(host):
                summary['stages'][stage] = {'status': 'source_paused'}
                continue
            interval = settings.BACKGROUND_KGD_SECONDS if kgd else settings.BACKGROUND_PROFILE_SECONDS
            if stage == 'contract_history':
                interval = settings.BACKGROUND_INTERVAL_SECONDS
            if stage == 'contract_repair':
                interval = settings.BACKGROUND_RETRY_SECONDS
            next_state = {'started_at': now.isoformat(), 'status': 'running'}
            save_state(stage, next_state)
            runs = []
            try:
                if stage in ('goszakup_contracts', 'contract_history', 'contract_repair'):
                    stream = {'goszakup_contracts': 'head', 'contract_history': 'history', 'contract_repair': 'repair'}[stage]
                    runs.append(remember(collect_contract_slice(stream, provider,
                        limit=min(settings.BACKGROUND_CONTRACT_BATCH, 3 if stream == 'repair' else 25))))
                    next_state['cursor'] = {k: v for k, v in crawl_state(stream).items()
                        if k in ('page', 'offset', 'passes', 'pass_finished')}
                    if stream == 'history' and next_state['cursor'].get('pass_finished'):
                        interval = settings.BACKGROUND_REFRESH_DAYS * 86400
                elif kgd:
                    source = DEBT_SOURCE if stage == 'kgd_debt' else TAXPAYER_SOURCE
                    for company, kind in eligible_kgd(provider, source, now):
                        if not available(host):
                            break
                        provider.kgd_client().taxpayer_type = kind
                        runs.append(execute(mode='kgd', total=1, company_bin=company.bin,
                            kgd_service='tax_debt' if stage == 'kgd_debt' else 'taxpayer'))
                else:
                    for company in due_companies(stage, version=provider.VERSION, now=now,
                                                  limit=settings.BACKGROUND_COMPANY_BATCH):
                        if not available(host):
                            break
                        runs.append(execute(mode='enrich', total=1, company_bin=company.bin, company_sources=[stage],
                            days=settings.BACKGROUND_REFRESH_DAYS,
                            cluster_builder=lambda: {'deferred_to_cycle_refresh': True}))
                next_state.update(status='completed' if all(run.status == 'succeeded' for run in runs) else 'partial',
                    runs=[str(run.uuid) for run in runs], outcomes=dict(Counter(run.status for run in runs)),
                    errors=dict(Counter(i.error_code for run in runs for i in run.issues.filter(resolved=False))),
                    records=sum(run.counters.get('checked', 0) for run in runs))
                denied = any(code in ('source_http_401', 'source_http_403', 'source_challenge_or_rate_limit',
                                      'kgd_access_denied') for code in next_state['errors'])
                # An isolated timeout belongs to that record's retry queue. Only
                # a host circuit/access denial pauses otherwise healthy subjects.
                if denied or host in provider.transport.blocked_hosts:
                    interval = max(interval, settings.BACKGROUND_SOURCE_COOLDOWN_SECONDS)
            except IngestionBusy:
                next_state.update(status='busy')
            except Exception:
                next_state.update(status='failed', errors={'background_stage_failed': 1})
            finally:
                available(host)
                cycle.heartbeat()
                next_state.update(finished_at=timezone.now().isoformat(),
                                  next_due=(timezone.now() + timedelta(seconds=interval)).isoformat())
                save_state(stage, next_state)
                summary['stages'][stage] = next_state
        lease = RunLease.acquire()
        try:
            touched.update(read_state('pending').get('company_ids', []))
            if touched:
                summary['graph'] = refresh_graph_analysis(supplier_ids=sorted(touched), publication_guard=lease.ensure_owned)
            else:
                summary['graph'] = {'status': 'unchanged', 'snapshots_created': 0, 'analysis_versions_created': 0}
            save_state('pending', {'company_ids': []})
        finally:
            lease.release()
        from apps.ai.automation import schedule_explanations
        summary['ai'] = schedule_explanations()
        save_state('ai', summary['ai'])
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
            if providers is None:
                provider.close()
        finally:
            cycle.release()
