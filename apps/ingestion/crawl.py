"""Restartable head catch-up and repeated archive reconciliation with a repair queue.

The HTML registry has mutable numbered pages, not a snapshot/export API. Frozen
page slices survive restarts; repeated archive passes reconcile page movement.
Never describe one pass as a transactional snapshot of the external registry.
"""
import json
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.models import SystemSetting
from .errors import SourceError
from .leases import RunLease, LeaseLost
from .models import ContractRetry, IngestionRun, IngestionIssue, SourceObservation
from .normalizers import normalize_amount, normalize_date
from .observations import fingerprint, json_values
from .services import save_contract, issue

PREFIX = 'collection-crawl:'


def crawl_state(stream):
    value = SystemSetting.objects.filter(key=PREFIX + stream).values_list('value', flat=True).first()
    return json.loads(value) if value else {}


def write_cursor(stream, state):
    SystemSetting.objects.update_or_create(key=PREFIX + stream, defaults={'value': json.dumps(json_values(state))})


def recently_unchanged(record):
    """Reuse recent party evidence only while all available registry fields agree."""
    previous = SourceObservation.objects.filter(source='goszakup_contracts',
        subject_key=f'contract:{record["contract_gos_id"]}', status='success',
        observed_at__gte=timezone.now() - timedelta(days=settings.BACKGROUND_REFRESH_DAYS),
        parser_version__in=['2.3', '2.4']).order_by('-observed_at', '-pk').first()
    if not previous:
        return False
    fields = ('contract_number', 'contract_gos_id', 'supplier_name', 'customer_name', 'subject', 'purchase_number')
    old = previous.normalized_values
    return (all((record.get(key) or '') == (old.get(key) or '') for key in fields)
            and normalize_amount(record['amount']) == normalize_amount(old.get('amount'))
            and normalize_date(record['sign_date']) == normalize_date(old.get('sign_date')))


def retry_row(record, code):
    row, _ = ContractRetry.objects.get_or_create(external_id=record['contract_gos_id'],
        defaults={'record': json_values(record), 'error_code': code})
    row.record, row.error_code = json_values(record), code
    row.attempts += 1
    row.resolved_at = None
    row.next_attempt_at = timezone.now() + timedelta(seconds=min(
        settings.BACKGROUND_RETRY_SECONDS * 2 ** min(row.attempts - 1, 5), 86400))
    row.save()


def accept_record(run, lease, provider, record):
    identifier = record['contract_gos_id']
    pending = ContractRetry.objects.filter(external_id=identifier, resolved_at=None).first()
    if pending and pending.next_attempt_at > timezone.now():
        return 'deferred'
    if not pending and recently_unchanged(record):
        return 'unchanged'
    try:
        complete = provider.complete_contract(record) if hasattr(provider, 'complete_contract') else record
    except SourceError as error:
        if error.code not in ('contract_party_identifier_invalid', 'contract_party_identifier_missing'):
            raise
        with transaction.atomic():
            lease.ensure_owned()
            retry_row(record, error.code)
            issue(run, 'goszakup_contracts', f'contract:{identifier}', 'contracts', error.code)
        return 'rejected'
    try:
        with transaction.atomic():
            lease.ensure_owned()
            contract = save_contract(run, complete)
            from .background import read_state, save_state
            dirty = set(read_state('pending').get('company_ids', []))
            dirty.update((contract.supplier_id, contract.customer_id))
            save_state('pending', {'company_ids': sorted(dirty - {None})})
            ContractRetry.objects.filter(external_id=identifier).update(resolved_at=timezone.now())
            IngestionIssue.objects.filter(source='goszakup_contracts', subject_key=f'contract:{identifier}',
                resolved=False).update(resolved=True)
    except (ValueError, ValidationError):
        with transaction.atomic():
            lease.ensure_owned()
            retry_row(record, 'invalid_import_data')
            issue(run, 'goszakup_contracts', f'contract:{identifier}', 'contracts', 'invalid_import_data')
        return 'rejected'
    return 'saved'


def collect_contract_slice(stream, provider, *, limit):
    if stream not in ('head', 'history', 'repair'):
        raise ValueError('invalid_crawl_stream')
    lease = RunLease.acquire()
    run = None
    try:
        run = IngestionRun.objects.create(mode=stream, options={'total': limit, 'contracts_only': True})
        lease.attach(run)
        counts = {'checked': 0, 'saved': 0, 'unchanged': 0, 'rejected': 0, 'deferred': 0}
        state = crawl_state(stream)
        state.pop('pass_finished', None)
        if stream == 'repair':
            records = list(ContractRetry.objects.filter(resolved_at=None, next_attempt_at__lte=timezone.now())
                .order_by('next_attempt_at', 'pk').values_list('record', flat=True)[:limit])
            for record in records:
                lease.heartbeat()
                outcome = accept_record(run, lease, provider, record)
                counts[outcome] += 1
                counts['checked'] += 1
        else:
            state.setdefault('page', 1)
            state.setdefault('passes', 0)
            state.setdefault('boundary', [])
            while counts['checked'] < limit:
                lease.heartbeat()
                if not state.get('records'):
                    page = provider.contract_page(state['page'])
                    if page.number != state['page'] or (not page.records and not page.eof) or (page.eof and page.records):
                        raise SourceError('contract_page_invalid')
                    if page.eof:
                        finish_pass(state)
                        with transaction.atomic():
                            lease.ensure_owned()
                            write_cursor(stream, state)
                        break
                    digest = fingerprint(page.records)
                    if state.get('previous_page_hash') == digest:
                        raise SourceError('contract_page_repeated')
                    identifiers = [row['contract_gos_id'] for row in page.records]
                    if state['page'] == 1:
                        state['next_boundary'] = identifiers
                        state['remaining_boundary'] = list(state['boundary'])
                    state.update(records=json_values(page.records), offset=0, page_hash=digest)
                    with transaction.atomic():
                        lease.ensure_owned()
                        write_cursor(stream, state)
                record = state['records'][state['offset']]
                outcome = accept_record(run, lease, provider, record)
                counts[outcome] += 1
                counts['checked'] += 1
                state['offset'] += 1
                remaining = state.get('remaining_boundary', [])
                if record['contract_gos_id'] in remaining:
                    remaining.remove(record['contract_gos_id'])
                if state['offset'] == len(state['records']):
                    state.update(records=[], offset=0, page=state['page'] + 1,
                                 previous_page_hash=state.pop('page_hash'))
                    # First head pass establishes its boundary; history handles the archive.
                    if stream == 'head' and (not state['boundary'] or not remaining):
                        finish_pass(state)
                with transaction.atomic():
                    lease.ensure_owned()
                    write_cursor(stream, state)
                    run.counters = counts.copy()
                    run.next_page = state['page']
                    run.save(update_fields=['counters', 'next_page', 'updated_at'])
                if state.get('pass_finished'):
                    break
        run.status = 'partial' if counts['rejected'] or counts['deferred'] else 'succeeded'
        run.stage = 'complete'
        run.counters = counts
        run.finished_at = timezone.now()
        with transaction.atomic():
            lease.ensure_owned()
            run.save()
        return run
    except LeaseLost:
        raise
    except Exception as error:
        if run is None:
            raise
        code = error.code if isinstance(error, SourceError) else 'crawl_stage_failed'
        with transaction.atomic():
            lease.ensure_owned()
            issue(run, 'goszakup_contracts', f'page:{state.get("page", 1)}', 'contracts', code)
            run.status = 'partial' if counts['checked'] else 'failed'
            run.error_code, run.finished_at, run.counters = code, timezone.now(), counts
            run.save()
        return run
    finally:
        lease.release()


def finish_pass(state):
    state.update(page=1, records=[], offset=0, passes=state['passes'] + 1,
                 boundary=state.pop('next_boundary', []), remaining_boundary=[],
                 previous_page_hash=None, pass_finished=timezone.now().isoformat())
