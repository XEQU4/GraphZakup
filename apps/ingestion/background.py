"""Durable bounded collection cycles shared by Celery and the management command."""
import json
from datetime import timedelta

from django.conf import settings
from django.db.models import F, OuterRef, Q, Subquery, Value
from django.db.models.functions import Concat
from django.utils import timezone

from apps.companies.models import Supplier
from apps.core.models import SystemSetting
from .leases import RunLease
from .models import SourceObservation, ContractRetry
from .parsers.kgd import LEGAL_TYPES, TAXPAYER_SOURCE
from .providers import SourceProviders

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
    from .collection import enrichment_backlog
    from .models import CompanyKgdState
    provider = SourceProviders()
    try:
        kgd_ready = provider.kgd_ready
        kgd_counts = {'registration_success': CompanyKgdState.objects.filter(source='kgd_taxpayer',
            last_successful_observation__isnull=False).count(),
            'debt_success': CompanyKgdState.objects.filter(source='kgd_tax_debt', last_successful_observation__isnull=False).count(),
            'portal_configured': kgd_ready,
            'companies_with_debt_credential': Supplier.objects.filter(bin__in=[key for key, value in
                provider.kgd_client().account_tokens.items() if provider.kgd_client()._valid_token(value)]).count() if kgd_ready else 0}
    finally:
        provider.close()
    return {'latest_cycle': read_state('latest'),
            'sources': {stage: read_state(stage) for stage in ('goszakup_contracts', 'contract_history', 'contract_repair', *SourceProviders.COMPANY_SOURCES, 'kgd', 'kgd_debt', 'ai')},
            'contract_repair': {'unresolved': ContractRetry.objects.filter(resolved_at=None).count()},
            'enrichment_backlog': enrichment_backlog(), 'kgd_coverage': kgd_counts,
            'totals': {'companies': Supplier.objects.count(), 'contracts': Contract.objects.count()}}


def due_companies(source, *, version, now, limit=None):
    """Oldest attempted first; failures wait before retry and never starve new IDs."""
    latest = SourceObservation.objects.filter(supplier_id=OuterRef('pk'), source=source,
        subject_key=Concat(Value('company:'), OuterRef('bin'))).order_by('-observed_at', '-pk')
    companies = Supplier.objects.annotate(
        attempt_time=Subquery(latest.values('observed_at')[:1]),
        attempt_status=Subquery(latest.values('status')[:1]),
        attempt_version=Subquery(latest.values('parser_version')[:1]),
    )
    fresh_cutoff = now - timedelta(days=settings.BACKGROUND_REFRESH_DAYS)
    retry_cutoff = now - timedelta(seconds=settings.BACKGROUND_RETRY_SECONDS)
    eligible = (Q(attempt_time__isnull=True)
                | Q(attempt_status='success') & ~Q(attempt_version=version)
                | Q(attempt_time__lt=retry_cutoff) & (
                    ~Q(attempt_status__in=['success', 'not_found'])
                    | Q(attempt_time__lt=fresh_cutoff) | ~Q(attempt_version=version)))
    # Reserve half the batch for previously attempted records. A growing stream
    # of new companies must not indefinitely starve expired results and retries.
    eligible_companies = companies.filter(eligible)
    if limit is None:
        return eligible_companies.order_by(F('attempt_time').asc(nulls_first=True), 'pk')
    old_ids = list(eligible_companies.filter(attempt_time__isnull=False)
        .order_by('attempt_time', 'pk').values_list('pk', flat=True)[:limit // 2])
    other_ids = list(eligible_companies.exclude(pk__in=old_ids)
        .order_by(F('attempt_time').asc(nulls_first=True), 'pk').values_list('pk', flat=True)[:limit - len(old_ids)])
    return companies.filter(pk__in=old_ids + other_ids).order_by(F('attempt_time').asc(nulls_first=True), 'pk')


def registered_subject_type(company):
    """Use explicit saved registration evidence, never a person's name or ID shape."""
    if hasattr(company, 'saved_kgd'):
        prior_data = company.saved_kgd or {}
        registry_data = company.saved_registry or {}
    else:
        prior = company.source_observations.filter(source=TAXPAYER_SOURCE, status='success',
            subject_key=f'company:{company.bin}').order_by('-observed_at', '-pk').first()
        prior_data = prior.normalized_values if prior else {}
        registry = company.source_observations.filter(source='goszakup_supplier', status='success',
            subject_key=f'company:{company.bin}',
            parser_version__in=['2.2', '2.3', SourceProviders.VERSION], observed_at__gte=timezone.now() - timedelta(days=7)).order_by('-observed_at', '-pk').first()
        registry_data = registry.normalized_values if registry else {}
    if prior_data.get('bin') != company.bin:
        prior_data = {}
    if registry_data.get('bin') != company.bin:
        registry_data = {}
    if prior_data.get('kgd_taxpayer_type') in LEGAL_TYPES | {'IP'}:
        return prior_data['kgd_taxpayer_type']
    if not registry_data:
        return None
    form = str(registry_data.get('kopf') or '').strip().casefold()
    if form == 'индивидуальное (личное) предпринимательство':
        return 'IP'
    if form in {'товарищество с ограниченной ответственностью', 'акционерное общество',
                'государственное учреждение', 'республиканское государственное предприятие',
                'коммунальное государственное предприятие', 'коммунальное государственное учреждение'}:
        return 'UL'
    return None


def run_background_cycle(*, providers=None):
    from .collection import run_cycle
    return run_cycle(providers=providers)
