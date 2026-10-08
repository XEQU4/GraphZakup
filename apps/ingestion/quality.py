"""Aggregate diagnostics over saved data; no fetching, repair or identity merging."""

from collections import Counter
from datetime import timedelta
import json
import re
import unicodedata

from django.conf import settings
from django.db.models import Count, F
from django.utils import timezone

from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.graph.evidence import applicable, confirmed_owner
from apps.owners.models import Directorship, Ownership, PersonIdentity
from apps.owners.querysets import is_confirmed_role
from .models import CompanyKgdState, IdentityCandidate, PersonSourceIdentity, SelectedFact, SourceObservation
from .parsers.kgd import DEBT_SOURCE, KgdParser, TAXPAYER_SOURCE


def _repeat_counts(values):
    counts = Counter(value for value in values if value)
    repeated = [count for count in counts.values() if count > 1]
    return {'groups': len(repeated), 'records': sum(repeated)}


def _name_key(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def _source_coverage(source, total, cutoff, now):
    latest, success = {}, set()
    observations = SourceObservation.objects.filter(source=source, supplier__isnull=False).order_by(
        'supplier_id', '-observed_at', '-pk').values('supplier_id', 'subject_key', 'supplier__bin',
                                                  'status', 'observed_at', 'source_url')
    for row in observations.iterator(chunk_size=500):
        if row['subject_key'] != f"company:{row['supplier__bin']}":
            continue
        company = row['supplier_id']
        latest.setdefault(company, row)
        if row['status'] == 'success':
            success.add(company)
    statuses = Counter(row['status'] if row['status'] in {'success', 'not_found', 'not_checked',
                        'invalid', 'unavailable'} else 'unknown' for row in latest.values())
    return {
        'without_saved_attempt': total - len(latest),
        'latest_statuses': dict(sorted(statuses.items())),
        'recent_successful_latest_attempts': sum(row['status'] == 'success' and cutoff <= row['observed_at'] <= now
                                                for row in latest.values()),
        'success_without_source_url': sum(row['status'] == 'success' and not row['source_url']
                                         for row in latest.values()),
        'retained_success_after_unsuccessful_latest_attempt': sum(company in success and row['status'] != 'success'
                                                                 for company, row in latest.items()),
    }


def _role_quality(model, confirmed, as_of):
    rows = model.objects.filter(is_current=True).select_related('person_identity', 'source_observation')
    result = Counter(current_records=0, confirmed_identity_evidence=0, unconfirmed_identity_evidence=0,
                     unknown_legal_start=0, unknown_legal_end=0, missing_observation=0,
                     source_mismatch=0, expired_or_future_interval=0)
    for role in rows.iterator(chunk_size=500):
        result['current_records'] += 1
        result['confirmed_identity_evidence' if confirmed(role) else 'unconfirmed_identity_evidence'] += 1
        result['unknown_legal_start'] += role.start_date is None
        result['unknown_legal_end'] += role.end_date is None
        result['missing_observation'] += role.source_observation_id is None
        result['source_mismatch'] += bool(role.source_observation_id and role.source != role.source_observation.source)
        result['expired_or_future_interval'] += not applicable(role, as_of)
    return dict(result)


def _kgd_configuration():
    # Counts alone: credentials and the company allowlist must never enter a report.
    valid = True
    try:
        tokens = json.loads(settings.KGD_ACCOUNT_TOKENS_JSON or '{}')
        if (not isinstance(tokens, dict) or len(tokens) > 1000
                or any(not re.fullmatch(r'[0-9]{12}', key) for key in tokens)):
            raise ValueError
        eligible = [key for key, value in tokens.items() if KgdParser._valid_token(value)]
        valid = len(eligible) == len(tokens)
    except (ValueError, TypeError):
        valid, eligible = False, []
    return {
        'collection_enabled': bool(settings.ENABLE_KGD_CHECKS),
        'portal_credential_valid': KgdParser._valid_token(settings.KGD_PORTAL_TOKEN),
        'account_configuration_valid': valid,
        'existing_companies_with_account_credential': Supplier.objects.filter(bin__in=eligible).count(),
        'broader_company_entitlement': 'unverified',
    }


def build_data_quality_report(*, days=7, now=None):
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 3650:
        raise ValueError('quality_days_must_be_between_1_and_3650')
    now = now or timezone.now()
    cutoff = now - timedelta(days=days)
    companies = Supplier.objects.all()
    total = companies.count()
    company_rows = list(companies.values_list('bin', 'name'))
    observations = SourceObservation.objects.all()
    selected = Counter(total=0, legacy_or_unconfirmed=0, older_than_window=0,
                       missing_source_url=0, wrong_company=0)
    for fact in SelectedFact.objects.select_related('observation').iterator(chunk_size=500):
        observation = fact.observation
        selected['total'] += 1
        selected['legacy_or_unconfirmed'] += observation.source == 'legacy' or observation.status != 'success'
        selected['older_than_window'] += observation.observed_at < cutoff
        selected['missing_source_url'] += not observation.source_url
        selected['wrong_company'] += observation.supplier_id != fact.supplier_id
    external_ids = Contract.objects.exclude(contract_gos_id=None).values('contract_gos_id').annotate(
        count=Count('pk')).filter(count__gt=1)
    people = PersonIdentity.objects.all()
    name_scopes = PersonSourceIdentity.objects.exclude(normalized_name='').values('normalized_name').annotate(
        companies=Count('supplier_id', distinct=True), identities=Count('person_id', distinct=True))
    states = CompanyKgdState.objects.select_related('latest_observation', 'last_successful_observation')
    kgd = {}
    for source in (TAXPAYER_SOURCE, DEBT_SOURCE):
        rows = [row for row in states if row.source == source]
        kgd[source] = {
            'without_saved_state': total - len(rows),
            'saved_states': len(rows),
            'retained_success_after_failure': sum(bool(row.last_successful_observation_id)
                and row.latest_observation.status != 'success' for row in rows),
        }
    return {
        'schema': 'data-quality-1.0', 'as_of': now.isoformat(), 'freshness_window_days': days,
        'companies': {
            'total': total,
            'duplicate_bins': _repeat_counts(row[0] for row in company_rows),
            'invalid_bin_shape': sum(not bool(re.fullmatch(r'[0-9]{12}', row[0])) for row in company_rows),
            'repeated_normalized_names': _repeat_counts(_name_key(row[1]) for row in company_rows),
            'missing_registration_date': companies.filter(registration_date=None).count(),
            'legacy_enrichment_timestamp_missing': companies.filter(adata_updated_at=None).count(),
            'legacy_enrichment_timestamp_older_than_window': companies.filter(adata_updated_at__lt=cutoff).count(),
        },
        'contracts': {
            'total': Contract.objects.count(),
            'duplicate_external_id_groups': external_ids.count(),
            'missing_external_id': Contract.objects.filter(contract_gos_id=None).count(),
            'missing_customer_link': Contract.objects.filter(customer=None).count(),
            'customer_identifier_mismatch': Contract.objects.filter(customer__isnull=False).exclude(
                customer_bin=F('customer__bin')).count(),
            'future_contract_date': Contract.objects.filter(contract_date__gt=now.date()).count(),
        },
        'observations': {
            'total': observations.count(),
            'legacy': observations.filter(source='legacy').count(),
            'missing_source_url': observations.filter(source_url='').count(),
            'future_retrieval_time': observations.filter(observed_at__gt=now + timedelta(minutes=5)).count(),
        },
        'selected_facts': dict(selected),
        'sources': {source: _source_coverage(source, total, cutoff, now) for source in (
            'goszakup_supplier', 'adata', TAXPAYER_SOURCE, DEBT_SOURCE)},
        'people': {
            'total': people.count(), 'verified': people.filter(is_verified=True).count(),
            'repeated_normalized_names': _repeat_counts(_name_key(name) for name in people.values_list('full_name', flat=True)),
            'name_groups_with_multiple_companies': name_scopes.filter(companies__gt=1).count(),
            'same_company_name_groups_with_multiple_identities': name_scopes.filter(companies=1, identities__gt=1).count(),
            'matching_candidates': {row['status']: row['count'] for row in IdentityCandidate.objects.values('status').annotate(count=Count('pk'))},
        },
        'roles': {'directors': _role_quality(Directorship, is_confirmed_role, now.date()),
                  'owners': _role_quality(Ownership, confirmed_owner, now.date())},
        'kgd': {'states': kgd, 'configuration': _kgd_configuration()},
        'interpretation': [
            'This report reads saved data only; it does not verify current source availability.',
            'Legacy observation dates record migration provenance, not a fresh external check.',
            'Recent retrieval is not proof that the source record is current or complete.',
            'Without a saved attempt means no retained source observation, not proof that historical fetching never occurred.',
            'Repeated names are review candidates and must not be merged automatically.',
            'Missing checks remain unknown; no KGD state does not mean zero arrears.',
            'Configured credentials do not establish permission for other companies.',
        ],
    }
