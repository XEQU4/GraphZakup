"""KGD persistence and read projections; all collection orchestration stays in services."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .dto import ResultStatus
from .models import CompanyKgdState
from .observations import record_observation
from .parsers.kgd import DEBT_SOURCE, FIELDS_BY_SOURCE, KgdParser, TAXPAYER_SOURCE, validate_facts

STATUS_LABELS = {
    'success': 'Success', 'not_found': 'Not found', 'unavailable': 'Unavailable',
    'invalid': 'Invalid response', 'not_checked': 'Not checked',
}


def normalize_kgd_result(result, source, supplier):
    if result.source != source or result.subject_key != f'company:{supplier.bin}' or result.status not in ResultStatus:
        raise ValueError('kgd_result_identity_invalid')
    if source == DEBT_SOURCE and result.status == ResultStatus.NOT_FOUND:
        raise ValueError('kgd_debt_absence_unconfirmed')
    if result.parser_version != KgdParser.VERSION:
        raise ValueError('kgd_parser_version_invalid')
    data = validate_facts(source, result.data, supplier.bin) if result.status == ResultStatus.SUCCESS else {}
    raw = {key: value for key, value in result.raw.items() if key in FIELDS_BY_SOURCE[source]} if data else {}
    if raw:
        try:
            validate_facts(source, raw, supplier.bin)
        except (ValueError, TypeError):
            raw = {}
    # The evidence URL cannot contain the account token, even for custom providers.
    code = result.error_code if re.fullmatch(r'[a-z0-9_]{0,80}', result.error_code) else 'kgd_source_failed'
    return replace(result, data=data, raw=raw, error_code=code, source_url=KgdParser.SOURCE_URLS[source])


@transaction.atomic
def record_kgd_result(run, result, supplier):
    result = normalize_kgd_result(result, result.source, supplier)
    observation = record_observation(run, result, supplier)
    state, created = CompanyKgdState.objects.get_or_create(supplier=supplier, source=result.source, defaults={
        'latest_observation': observation,
        'last_successful_observation': observation if result.status == ResultStatus.SUCCESS else None,
    })
    if created:
        return observation
    state = CompanyKgdState.objects.select_for_update(of=('self',)).select_related(
        'latest_observation', 'last_successful_observation').get(pk=state.pk)
    key = (observation.observed_at, observation.pk)
    latest = state.latest_observation
    changed = []
    if key > (latest.observed_at, latest.pk):
        state.latest_observation = observation
        changed.append('latest_observation')
    previous = state.last_successful_observation
    if result.status == ResultStatus.SUCCESS and (previous is None or key > (previous.observed_at, previous.pk)):
        state.last_successful_observation = observation
        changed.append('last_successful_observation')
    if changed:
        state.save(update_fields=changed)
    return observation


def company_kgd_statuses(supplier):
    rows = {row.source: row for row in supplier.kgd_states.select_related(
        'latest_observation', 'last_successful_observation')}
    cutoff = timezone.now() - timedelta(days=settings.KGD_RESULT_MAX_AGE_DAYS)
    result = []
    for source, title in ((TAXPAYER_SOURCE, 'Taxpayer registration'), (DEBT_SOURCE, 'Tax arrears')):
        row = rows.get(source)
        latest = row.latest_observation if row else None
        successful = row.last_successful_observation if row else None
        data = successful.normalized_values if successful else {}
        value = {
            'source': source, 'title': title, 'latest': latest, 'successful': successful,
            'status': STATUS_LABELS.get(latest.status, 'Unknown') if latest else 'Not checked',
            'stale': bool(successful and (latest.status != 'success' or successful.observed_at < cutoff)),
            'data': data, 'source_url': KgdParser.SOURCE_URLS[source],
        }
        if source == DEBT_SOURCE and successful:
            value.update(total_arrears=Decimal(data['kgd_total_arrears']),
                         tax_arrears=Decimal(data['kgd_tax_arrears']),
                         reporting_dates=data['kgd_reporting_dates'])
        result.append(value)
    return result
