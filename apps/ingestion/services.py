"""The single ingestion process for commands and Celery; no ORM in parsers."""
from datetime import timedelta
from decimal import Decimal
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery, Value
from django.db.models.functions import Concat
from django.utils import timezone

from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.core.models import SystemSetting
from apps.ai.services import refresh_graph_analysis as rebuild_clusters
from .dto import ResultStatus, SourceResult
from .errors import SourceError
from .leases import RunLease, LeaseLost
from .models import IngestionRun, SourceCheckpoint, IngestionIssue, SelectedFact, SourceObservation
from .normalizers import normalize_amount, normalize_bin, normalize_date
from .observations import (
    CONTRACT_FIELDS, apply_company_facts, cached_company_result, fingerprint,
    json_values, normalize_company_result, record_observation,
)
from .providers import SourceProviders
from .kgd import normalize_kgd_result, record_kgd_result
from .parsers.contracts import ContractRegistryParser
from .parsers.kgd import KgdParser, TAXPAYER_SOURCE, DEBT_SOURCE
from django.conf import settings


class IngestionFailure(Exception):
    def __init__(self, run, code):
        self.run_id, self.code = str(run.uuid), code
        super().__init__(f'{code}; run={self.run_id}')


def issue(run, source, subject, stage, code, *, supplier=None, page=None, resolved=False):
    row, _ = IngestionIssue.objects.get_or_create(
        run=run, source=source, subject_key=subject, stage=stage,
        defaults={'error_code': code, 'supplier': supplier, 'page': page},
    )
    row.error_code, row.resolved = code, resolved
    row.attempts += 1
    row.last_seen_at = timezone.now()
    row.save(update_fields=['error_code', 'resolved', 'attempts', 'last_seen_at'])


def save_contract(run, item):
    supplier_bin = normalize_bin(item.get('supplier_bin'))
    customer_bin = normalize_bin(item.get('customer_bin'))
    signed, amount = normalize_date(item.get('sign_date')), normalize_amount(item.get('amount'))
    number = item.get('contract_number')
    identifier = item.get('contract_gos_id')
    if (not signed or not isinstance(number, str) or not number.strip() or len(number.strip()) > 255
            or not isinstance(identifier, int) or isinstance(identifier, bool) or identifier <= 0):
        raise ValueError('invalid_contract_identity_or_date')
    number = number.strip()
    previous = Contract.objects.filter(contract_number=number).select_related('supplier').first()
    if previous and previous.supplier.bin != supplier_bin:
        raise ValueError('contract_supplier_identity_changed')
    if previous and previous.contract_gos_id and previous.contract_gos_id != identifier:
        raise ValueError('contract_external_identity_changed')
    if Contract.objects.filter(contract_gos_id=identifier).exclude(contract_number=number).exists():
        raise ValueError('contract_external_id_conflict')
    supplier, _ = Supplier.objects.get_or_create(
        bin=supplier_bin, defaults={'name': item.get('supplier_name') or supplier_bin, 'is_supplier': True},
    )
    if not supplier.is_supplier:
        supplier.is_supplier = True
        supplier.save(update_fields=['is_supplier'])
    customer, _ = Supplier.objects.get_or_create(
        bin=customer_bin, defaults={'name': item.get('customer_name') or customer_bin,
                                    'is_supplier': False, 'is_customer': True},
    )
    if not customer.is_customer:
        customer.is_customer = True
        customer.save(update_fields=['is_customer'])
    values = {
        'supplier': supplier, 'customer': customer, 'tender_id': item.get('purchase_number') or '',
        'contract_gos_id': identifier, 'title': item.get('subject') or '', 'amount': amount,
        'customer_name': item.get('customer_name') or '', 'customer_bin': customer_bin, 'contract_date': signed,
    }
    # Validate sizes and typed fields without mistaking the idempotent key for a duplicate.
    candidate = Contract(contract_number=number, **values)
    candidate.full_clean(validate_unique=False, validate_constraints=False)
    contract, _ = Contract.objects.update_or_create(contract_number=number, defaults=values)
    data = {key: item.get(key) for key in CONTRACT_FIELDS}
    data['amount'], data['sign_date'] = amount, signed
    result = SourceResult(
        'goszakup_contracts', f'contract:{identifier}', ResultStatus.SUCCESS,
        data=data, raw=item.get('_raw') or data,
        parser_version=SourceProviders.VERSION,
        source_url=f'{ContractRegistryParser.BASE_URL}/ru/egzcontract/cpublic/show/{identifier}',
    )
    record_observation(run, result, supplier, contract)
    for company, label in ((supplier, 'supplier_name'), (customer, 'customer_name')):
        company_result = SourceResult('goszakup_contracts', f'company:{company.bin}', ResultStatus.SUCCESS,
                                      data={'bin': company.bin, 'name': item.get(label) or company.bin},
                                      raw={'bin': company.bin, 'name': (item.get('_raw') or item).get(label)},
                                      parser_version=SourceProviders.VERSION,
                                      source_url=result.source_url, observed_at=result.observed_at)
        obs = record_observation(run, company_result, company, contract)
        SelectedFact.objects.get_or_create(supplier=company, field='name', defaults={'observation': obs})
    return contract


def enrichment_selection(total, force, days, company_bin, sources, version):
    """Freeze an eligible catalogue slice; one source's success cannot freshen another."""
    companies = Supplier.objects.order_by('pk')
    if company_bin is not None:
        companies = companies.filter(bin=normalize_bin(company_bin))
        if not companies.exists():
            raise ValueError('enrichment_company_not_found')
    if not force:
        cutoff = timezone.now() - timedelta(days=days)
        eligible = Q()
        for source in sources:
            latest = SourceObservation.objects.filter(
                supplier_id=OuterRef('pk'), source=source,
                subject_key=Concat(Value('company:'), OuterRef('bin')),
            ).order_by('-observed_at', '-pk')
            status_key, time_key, version_key = (f'_enrich_{source}_{field}' for field in ('status', 'time', 'version'))
            companies = companies.annotate(**{
                status_key: Subquery(latest.values('status')[:1]),
                time_key: Subquery(latest.values('observed_at')[:1]),
                version_key: Subquery(latest.values('parser_version')[:1]),
            })
            eligible |= (Q(**{status_key + '__isnull': True})
                         | ~Q(**{status_key + '__in': ['success', 'not_found']})
                         | Q(**{time_key + '__lt': cutoff})
                         | ~Q(**{version_key: version}))
        companies = companies.filter(eligible)
    return list(companies.values_list('pk', flat=True)[:total])


def _new_run(mode, total, start_page, force, days, company_bin=None, kgd_service=None,
             company_sources=None, provider_version=None):
    mode = {'new': 'initial'}.get(mode, mode)
    if mode not in ('initial', 'update', 'full', 'enrich', 'kgd'):
        raise ValueError('invalid_ingestion_mode')
    if total <= 0 or (start_page is not None and start_page < 1) or days <= 0:
        raise ValueError('invalid_ingestion_options')
    if company_sources is not None and mode != 'enrich':
        raise ValueError('company_sources_require_enrich_mode')
    if mode == 'enrich':
        if total > 1000 or start_page is not None or kgd_service is not None:
            raise ValueError('invalid_enrichment_options')
        sources = SourceProviders.COMPANY_SOURCES if company_sources is None else company_sources
        if (not isinstance(sources, (tuple, list)) or not sources or
                any(source not in SourceProviders.COMPANY_SOURCES for source in sources) or
                len(set(sources)) != len(sources)):
            raise ValueError('invalid_company_sources')
        version = provider_version or SourceProviders.VERSION
        ids = enrichment_selection(total, force, days, company_bin, sources, version)
        return IngestionRun.objects.create(mode=mode, stage='enrichment' if ids else 'complete', options={
            'total': total, 'force': force, 'days': days, 'company_ids': ids,
            'company_sources': list(sources), 'selection_parser_version': version,
        })
    if mode == 'kgd':
        if total > 500 or start_page is not None or kgd_service not in (None, 'taxpayer', 'tax_debt'):
            raise ValueError('invalid_kgd_options')
        companies = Supplier.objects.order_by('pk')
        if company_bin is not None:
            companies = companies.filter(bin=normalize_bin(company_bin))
        ids = list(companies.values_list('pk', flat=True)[:total])
        if company_bin is not None and not ids:
            raise ValueError('kgd_company_not_found')
        return IngestionRun.objects.create(mode=mode, stage='kgd', options={
            'total': total, 'force': force, 'days': days, 'company_ids': ids,
            'kgd_service': kgd_service or 'taxpayer',
        })
    if company_bin is not None or kgd_service is not None:
        raise ValueError('kgd_options_require_kgd_mode')
    run = IngestionRun.objects.create(mode=mode, stage='enrichment' if mode == 'enrich' else 'contracts',
                                     options={'total': total, 'force': force, 'days': days})
    if mode != 'enrich':
        checkpoint, created = SourceCheckpoint.objects.get_or_create(source='goszakup_contracts', stream=mode)
        # Compatibility for phase1 checkpoints created after migration (including offline fixtures).
        if created and mode == 'initial':
            value = SystemSetting.objects.filter(key='last_import_page').values_list('value', flat=True).first()
            if value is not None:
                if not value.isdigit() or int(value) <= 0:
                    raise ValueError('invalid_legacy_checkpoint')
                checkpoint.next_page = int(value)
                checkpoint.save(update_fields=['next_page'])
        if start_page is not None:
            run.next_page = start_page
        elif mode in ('update', 'full'):
            run.next_page = 1
        else:
            run.next_page, run.offset, run.page_fingerprint = checkpoint.next_page, checkpoint.offset, checkpoint.page_fingerprint
        run.save(update_fields=['next_page', 'offset', 'page_fingerprint'])
    return run


def _contracts_stage(run, lease, providers):
    limit = run.options['total']
    saved = run.counters.get('contracts', 0)
    while saved < limit:
        lease.heartbeat()
        number = run.next_page
        try:
            page = providers.contract_page(number)
            if page.number != number or (not page.records and not page.eof):
                raise SourceError('contract_page_invalid')
            if page.eof:
                if page.records:
                    raise SourceError('contract_eof_invalid')
                with transaction.atomic():
                    lease.ensure_owned()
                    record_observation(run, SourceResult('goszakup_contracts', f'page:{number}', ResultStatus.NOT_FOUND,
                                                       parser_version=providers.VERSION))
                    IngestionIssue.objects.filter(run=run, stage='contracts', page=number).update(resolved=True)
                break
            page_hash = fingerprint(page.records)
            previous_page = run.counters.get('last_complete_contract_page', {})
            if (not run.offset and previous_page.get('number') != number
                    and previous_page.get('fingerprint') == page_hash):
                raise SourceError('contract_page_repeated')
            offset = run.offset if run.page_fingerprint == page_hash else 0
            selected = page.records[offset:offset + limit - saved]
            if not selected:
                raise SourceError('contract_page_offset_invalid')
            with transaction.atomic():
                lease.ensure_owned()
                for item in selected:
                    save_contract(run, item)
                consumed = offset + len(selected)
                next_page = number + 1 if consumed == len(page.records) else number
                next_offset = 0 if consumed == len(page.records) else consumed
                SourceCheckpoint.objects.update_or_create(source='goszakup_contracts', stream=run.mode, defaults={
                    'next_page': next_page, 'offset': next_offset, 'page_fingerprint': page_hash if next_offset else '', 'run': run,
                })
                saved += len(selected)
                run.next_page, run.offset = next_page, next_offset
                run.page_fingerprint = page_hash if next_offset else ''
                run.counters = {**run.counters, 'contracts': saved}
                if not next_offset:
                    run.counters['last_complete_contract_page'] = {'number': number, 'fingerprint': page_hash}
                run.save(update_fields=['next_page', 'offset', 'page_fingerprint', 'counters', 'updated_at'])
                # Read-only compatibility consumers; ingestion's checkpoint is authoritative.
                key = {'initial': 'last_import_page', 'full': 'full_import_page', 'update': 'last_update_page'}[run.mode]
                SystemSetting.objects.update_or_create(key=key, defaults={'value': str(next_page)})
                SystemSetting.objects.update_or_create(key='last_import', defaults={'value': timezone.now().isoformat()})
                IngestionIssue.objects.filter(run=run, stage='contracts', page=number).update(resolved=True)
        except LeaseLost:
            raise
        except Exception as error:
            code = error.code if isinstance(error, SourceError) else (
                'invalid_import_data' if isinstance(error, (ValueError, ValidationError)) else 'page_save_failed')
            with transaction.atomic():
                lease.ensure_owned()
                run.refresh_from_db()
                issue(run, 'goszakup_contracts', f'page:{number}', 'contracts', code, page=number)
                record_observation(run, SourceResult('goszakup_contracts', f'page:{number}',
                                                     ResultStatus.INVALID if code == 'invalid_import_data' else ResultStatus.UNAVAILABLE,
                                                     parser_version=providers.VERSION,
                                                     error_code=code))
            raise IngestionFailure(run, code) from None
    with transaction.atomic():
        lease.ensure_owned()
        run.stage = 'enrichment' if saved else 'complete'
        run.save(update_fields=['stage', 'updated_at'])


def _enrichment_stage(run, lease, providers):
    failed_ids = run.issues.filter(stage='enrichment', resolved=False).values_list('supplier_id', flat=True)
    suppliers = Supplier.objects.order_by('pk').filter(Q(pk__gt=run.enrichment_cursor) | Q(pk__in=failed_ids))
    if run.mode == 'enrich':
        suppliers = suppliers.filter(pk__in=run.options['company_ids'])
        sources = run.options['company_sources']
    else:
        sources = providers.COMPANY_SOURCES
    if run.mode != 'enrich' and not run.options['force']:
        cutoff = timezone.now() - timedelta(days=run.options['days'])
        suppliers = suppliers.filter(Q(adata_updated_at__isnull=True) | Q(adata_updated_at__lt=cutoff) | Q(pk__in=failed_ids))
    checked = 0
    for supplier in suppliers.iterator(chunk_size=100):
        lease.heartbeat()
        results = []
        for source in sources:
            cached = None if run.options['force'] else cached_company_result(source, supplier, providers.VERSION)
            try:
                result = cached or providers.company(source, supplier.bin)
                if result.source != source or result.subject_key != f'company:{supplier.bin}':
                    raise ValueError('source_result_identity_invalid')
                result = normalize_company_result(result, supplier)
            except LeaseLost:
                raise
            except Exception as error:
                result = SourceResult(source, f'company:{supplier.bin}', ResultStatus.INVALID if isinstance(
                    error, (ValueError, ValidationError)) else ResultStatus.UNAVAILABLE,
                    parser_version=providers.VERSION, error_code='source_result_invalid')
            results.append(result)
        try:
            with transaction.atomic():
                lease.ensure_owned()
                for result in results:
                    record_observation(run, result, supplier)
                    bad = result.status in (ResultStatus.UNAVAILABLE, ResultStatus.INVALID, ResultStatus.NOT_CHECKED)
                    if bad:
                        issue(run, result.source, result.subject_key, 'enrichment', result.error_code or 'source_not_checked', supplier=supplier)
                    else:
                        run.issues.filter(source=result.source, subject_key=result.subject_key, stage='enrichment').update(resolved=True)
                changed = int(apply_company_facts(supplier))
                run.issues.filter(source='persistence', subject_key=f'company:{supplier.bin}', stage='enrichment').update(resolved=True)
                all_sources = run.mode != 'enrich' or set(sources) == set(SourceProviders.COMPANY_SOURCES)
                if all_sources and any(result.status == ResultStatus.SUCCESS for result in results) and all(
                        result.status in (ResultStatus.SUCCESS, ResultStatus.NOT_FOUND) for result in results):
                    successful = [result.observed_at for result in results if result.status == ResultStatus.SUCCESS]
                    supplier.adata_updated_at = min(successful)
                    supplier.save(update_fields=['adata_updated_at'])
                checked += 1
                run.enrichment_cursor = max(run.enrichment_cursor, supplier.pk)
                run.counters = {**run.counters, 'companies_checked': run.counters.get('companies_checked', 0) + 1,
                                'companies_changed': run.counters.get('companies_changed', 0) + changed}
                run.save(update_fields=['enrichment_cursor', 'counters', 'updated_at'])
        except LeaseLost:
            raise
        except Exception:
            with transaction.atomic():
                lease.ensure_owned()
                run.refresh_from_db()
                issue(run, 'persistence', f'company:{supplier.bin}', 'enrichment', 'company_save_failed', supplier=supplier)
                run.enrichment_cursor = max(run.enrichment_cursor, supplier.pk)
                run.save(update_fields=['enrichment_cursor', 'updated_at'])
    if run.issues.filter(stage='enrichment', resolved=False).exists():
        raise IngestionFailure(run, 'enrichment_incomplete')
    with transaction.atomic():
        lease.ensure_owned()
        run.stage = 'clusters' if (checked or run.counters.get('contracts')) else 'complete'
        run.save(update_fields=['stage', 'counters', 'updated_at'])


def _kgd_stage(run, lease, providers):
    """Bounded company checks; never updates people, clusters or explanations."""
    failed_ids = run.issues.filter(stage='kgd', resolved=False).values_list('supplier_id', flat=True)
    suppliers = Supplier.objects.filter(pk__in=run.options['company_ids']).filter(
        Q(pk__gt=run.enrichment_cursor) | Q(pk__in=failed_ids)).order_by('pk')
    sources = (TAXPAYER_SOURCE, DEBT_SOURCE) if run.options['kgd_service'] == 'tax_debt' else (TAXPAYER_SOURCE,)
    for supplier in suppliers.iterator(chunk_size=100):
        lease.heartbeat()
        results = []
        for source in sources:
            confirmed = bool(results and results[0].status == ResultStatus.SUCCESS)
            try:
                if source == DEBT_SOURCE and not confirmed:
                    result = SourceResult(source, f'company:{supplier.bin}', ResultStatus.NOT_CHECKED,
                                          parser_version=KgdParser.VERSION, error_code='kgd_legal_entity_unconfirmed')
                else:
                    cached = None
                    if not run.options['force'] and providers.kgd_cache_allowed(source, supplier.bin):
                        cached = cached_company_result(source, supplier, KgdParser.VERSION,
                                                       seconds=settings.KGD_SOURCE_CACHE_SECONDS)
                    result = cached or providers.kgd(source, supplier.bin, legal_entity_confirmed=confirmed)
                result = normalize_kgd_result(result, source, supplier)
            except LeaseLost:
                raise
            except Exception as error:
                result = SourceResult(source, f'company:{supplier.bin}', ResultStatus.INVALID if isinstance(
                    error, (ValueError, TypeError, ValidationError)) else ResultStatus.UNAVAILABLE,
                    parser_version=KgdParser.VERSION, source_url=KgdParser.SOURCE_URLS[source],
                    error_code='kgd_result_invalid')
            results.append(result)
        try:
            with transaction.atomic():
                lease.ensure_owned()
                for result in results:
                    record_kgd_result(run, result, supplier)
                    if result.status in (ResultStatus.SUCCESS, ResultStatus.NOT_FOUND):
                        run.issues.filter(source=result.source, subject_key=result.subject_key,
                                          stage='kgd').update(resolved=True)
                    else:
                        issue(run, result.source, result.subject_key, 'kgd',
                              result.error_code or 'kgd_not_checked', supplier=supplier)
                run.issues.filter(source='persistence', subject_key=f'company:{supplier.bin}',
                                  stage='kgd').update(resolved=True)
                run.enrichment_cursor = max(run.enrichment_cursor, supplier.pk)
                run.counters = {**run.counters, 'kgd_company_attempts': run.counters.get('kgd_company_attempts', 0) + 1}
                run.save(update_fields=['enrichment_cursor', 'counters', 'updated_at'])
        except LeaseLost:
            raise
        except Exception:
            with transaction.atomic():
                lease.ensure_owned()
                run.refresh_from_db()
                issue(run, 'persistence', f'company:{supplier.bin}', 'kgd', 'kgd_save_failed', supplier=supplier)
                run.enrichment_cursor = max(run.enrichment_cursor, supplier.pk)
                run.save(update_fields=['enrichment_cursor', 'updated_at'])
    if run.issues.filter(stage='kgd', resolved=False).exists():
        raise IngestionFailure(run, 'kgd_checks_incomplete')
    with transaction.atomic():
        lease.ensure_owned()
        run.stage = 'complete'
        run.save(update_fields=['stage', 'updated_at'])


def run_pipeline(*, mode='update', total=500, start_page=None, force=False, days=7,
                 resume=None, providers=None, cluster_builder=None, company_bin=None, kgd_service=None, company_sources=None):
    if resume is not None:
        run = IngestionRun.objects.get(uuid=uuid.UUID(str(resume)))
        if run.mode == 'legacy':
            raise ValueError('legacy_run_cannot_resume')
        if run.status == 'succeeded':
            return run
        if run.mode == 'enrich' and ('company_ids' not in run.options or 'company_sources' not in run.options):
            raise ValueError('unbounded_enrichment_run_requires_new_run')
    else:
        run = None
    lease = RunLease.acquire()
    client = None
    try:
        with transaction.atomic():
            lease.ensure_owned()
            if run is None:
                run = _new_run(mode, total, start_page, force, days, company_bin, kgd_service,
                    company_sources, getattr(providers, 'VERSION', SourceProviders.VERSION))
            else:
                run.refresh_from_db()
                run.status, run.error_code, run.finished_at = 'running', '', None
                run.attempts += 1
                run.save(update_fields=['status', 'error_code', 'finished_at', 'attempts', 'updated_at'])
            lease.attach(run)
        client = providers or SourceProviders(heartbeat=lease.heartbeat)
        if run.stage == 'kgd':
            _kgd_stage(run, lease, client)
        if run.stage == 'contracts':
            _contracts_stage(run, lease, client)
        if run.stage == 'enrichment':
            _enrichment_stage(run, lease, client)
        if run.stage == 'clusters':
            with transaction.atomic():
                lease.ensure_owned()
                report = (cluster_builder or rebuild_clusters)()
                # Graphs and derived templates must share the final lease fence.
                lease.ensure_owned()
                run.counters = {**run.counters, 'clusters': json_values(report)}
                run.stage = 'complete'
                run.save(update_fields=['stage', 'counters', 'updated_at'])
        with transaction.atomic():
            lease.ensure_owned()
            run.status, run.finished_at, run.error_code = 'succeeded', timezone.now(), ''
            run.save(update_fields=['status', 'finished_at', 'error_code', 'updated_at'])
        return run
    except Exception as error:
        if run is None:
            raise
        code = error.code if isinstance(error, IngestionFailure) else (
            'ingestion_lease_lost' if isinstance(error, LeaseLost) else 'ingestion_stage_failed')
        IngestionRun.objects.filter(pk=run.pk, status='running').update(
            status='partial' if run.counters else 'failed', error_code=code, finished_at=timezone.now(),
        )
        raise IngestionFailure(run, code) from None
    finally:
        try:
            if client is not None and providers is None:
                try:
                    client.close()
                except Exception:
                    pass  # Closing transport must not hide the recorded run outcome.
        finally:
            lease.release()
