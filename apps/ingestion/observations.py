from datetime import date, datetime, timedelta
from decimal import Decimal
import hashlib
import json
import re
from urllib.parse import urlsplit, parse_qs

from django.conf import settings
from django.utils import timezone

from apps.companies.models import Supplier
from .dto import ResultStatus, SourceResult
from .identities import synchronize_director, synchronize_owners
from .models import SourceObservation, SelectedFact
from .normalizers import normalize_bin, normalize_date, normalize_email, normalize_phone
from .parsers.kgd import FIELDS_BY_SOURCE, KgdParser

COMPANY_FIELDS = (
    'name', 'director_name', 'address', 'region', 'city', 'phone', 'email', 'oked', 'company_status',
    'registration_date', 'resident_status', 'company_size', 'kopf', 'economic_sector', 'website',
)
PERSON_FIELDS = ('director_iin', 'director_iin_verified', 'director_start_date', 'director_end_date',
                 'director_absent', 'owners', 'owners_complete')
CONTRACT_FIELDS = ('contract_number', 'contract_gos_id', 'supplier_bin', 'customer_bin', 'supplier_name',
                   'customer_name', 'amount', 'sign_date', 'subject', 'purchase_number')
ALLOWED_FIELDS = set(COMPANY_FIELDS + PERSON_FIELDS + CONTRACT_FIELDS + ('bin', 'supplier_id'))


def json_values(value):
    if isinstance(value, (Decimal, date, datetime)):
        return str(value) if not isinstance(value, datetime) else value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_values(item) for item in value]
    return value


def fingerprint(value):
    return hashlib.sha256(json.dumps(json_values(value), sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def normalize_company_result(result, supplier):
    if result.status != ResultStatus.SUCCESS:
        return result
    values, raw = dict(result.data), dict(result.raw)
    if normalize_bin(values.get('bin')) != supplier.bin:
        raise ValueError('company_identity_mismatch')
    if 'director' in values:
        values['director_name'] = values.pop('director')
    if 'director' in raw:
        raw['director_name'] = raw.pop('director')
    if values.get('director_absent') is True:
        if values.get('director_name') not in (None, ''):
            raise ValueError('director_presence_conflict')
        values['director_name'] = ''
    if values.get('owners_complete') is True and not isinstance(values.get('owners'), list):
        raise ValueError('complete_owner_list_missing')
    values['email'] = normalize_email(values.get('email'))
    values['phone'] = normalize_phone(values.get('phone'))
    values['registration_date'] = normalize_date(values.get('registration_date'))
    for field in COMPANY_FIELDS:
        value = values.get(field)
        if value not in (None, ''):
            values[field] = Supplier._meta.get_field(field).clean(value, supplier)
    return SourceResult(result.source, result.subject_key, result.status, values, raw, result.parser_version,
                        result.source_url, result.observed_at, result.error_code, result.from_cache)


def record_observation(run, result, supplier=None, contract=None):
    if result.status not in ResultStatus or not re.fullmatch(r'[a-z0-9_]{1,40}', result.source):
        raise ValueError('invalid_observation_metadata')
    if not result.subject_key or len(result.subject_key) > 255 or not result.parser_version or len(result.parser_version) > 40:
        raise ValueError('invalid_observation_metadata')
    allowed = FIELDS_BY_SOURCE.get(result.source, ALLOWED_FIELDS)
    values = {key: value for key, value in result.data.items() if key in allowed}
    raw = {key: value for key, value in result.raw.items() if key in allowed}
    owner_fields = {'full_name', 'iin', 'iin_verified', 'share_percent', 'start_date', 'end_date'}
    for container in (values, raw):
        if 'owners' in container:
            if not isinstance(container['owners'], list):
                raise ValueError('invalid_owner_list')
            container['owners'] = [{key: value for key, value in item.items() if key in owner_fields}
                                   for item in container['owners']]
    source_url = result.source_url
    if source_url:
        parsed = urlsplit(source_url)
        kgd = result.source in FIELDS_BY_SOURCE
        allowed_hosts = ('portal.kgd.gov.kz',) if kgd else ('goszakup.gov.kz', 'old.goszakup.gov.kz', 'pk.adata.kz')
        if (parsed.scheme != 'https' or parsed.hostname not in allowed_hosts
                or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.fragment
                or (kgd and source_url != KgdParser.SOURCE_URLS[result.source])
                or len(source_url) > 1000 or set(parse_qs(parsed.query, keep_blank_values=True)) -
                {'page', 'filter[name]', 'search', 'filter[attribute]'}):
            raise ValueError('invalid_observation_url')
    if timezone.is_naive(result.observed_at) or result.observed_at > timezone.now() + timedelta(minutes=5):
        raise ValueError('invalid_observation_time')
    code = result.error_code if re.fullmatch(r'[a-z0-9_]{0,80}', result.error_code) else 'source_failed'
    digest = fingerprint([result.status, values, raw, result.parser_version, source_url, result.observed_at])
    observation, _ = SourceObservation.objects.get_or_create(
        run=run, source=result.source, subject_key=result.subject_key, fingerprint=digest,
        defaults={'status': result.status, 'normalized_values': json_values(values), 'raw_values': json_values(raw),
                  'parser_version': result.parser_version, 'source_url': source_url,
                  'observed_at': result.observed_at, 'supplier': supplier, 'contract': contract,
                  'error_code': code, 'from_cache': result.from_cache},
    )
    return observation


def cached_company_result(source, supplier, version='2.0', *, seconds=None):
    seconds = settings.INGESTION_SOURCE_CACHE_SECONDS if seconds is None else seconds
    if seconds <= 0:
        return None
    observation = SourceObservation.objects.filter(
        source=source, subject_key=f'company:{supplier.bin}',
    ).order_by('-observed_at', '-pk').first()
    # Only the latest attempt can be reused. An older matching parser version
    # must not hide a later success produced by a different parser or identity.
    if (not observation or observation.supplier_id != supplier.pk
            or observation.status != ResultStatus.SUCCESS
            or observation.parser_version != version
            or observation.observed_at < timezone.now() - timedelta(seconds=seconds)):
        return None
    data = dict(observation.normalized_values)
    return SourceResult(source, observation.subject_key, ResultStatus.SUCCESS, data=data,
                        raw=observation.raw_values, parser_version=version, source_url=observation.source_url,
                        observed_at=observation.observed_at, from_cache=True)


def apply_company_facts(supplier):
    # Source-specific latest successful facts; failures never erase the last valid observation.
    observations = list(supplier.source_observations.filter(status='success').only(
        'pk', 'source', 'normalized_values', 'observed_at').order_by('-observed_at', '-pk'))
    changed = []
    for field in COMPANY_FIELDS:
        priority = ('adata', 'goszakup_supplier') if field in ('phone', 'email') else ('goszakup_supplier', 'adata', 'goszakup_contracts')
        selected = None
        for source in priority:
            selected = next((item for item in observations if item.source == source
                             and (item.normalized_values.get(field) not in (None, '') or
                                  (field == 'director_name' and item.normalized_values.get('director_absent') is True))), None)
            if selected:
                break
        if not selected:
            continue
        value = selected.normalized_values.get(field, '')
        if field == 'director_name' and selected.normalized_values.get('director_absent') is True:
            value = ''
        if field == 'registration_date':
            value = normalize_date(value)
        if getattr(supplier, field) != value:
            setattr(supplier, field, value)
            changed.append(field)
        SelectedFact.objects.update_or_create(supplier=supplier, field=field, defaults={'observation': selected})
        if field == 'director_name':
            synchronize_director(supplier, selected)
    for source in ('goszakup_supplier', 'adata'):
        owner_observation = next((item for item in observations if item.source == source
                                  and item.normalized_values.get('owners_complete') is True), None)
        if owner_observation:
            synchronize_owners(supplier, owner_observation)
    if changed:
        supplier.save(update_fields=[*changed, 'updated_at'])
    return bool(changed)
