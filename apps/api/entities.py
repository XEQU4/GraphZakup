"""Bounded read projections of saved companies, identities, roles and contracts."""

from datetime import timedelta
from django.conf import settings
from django.db.models import OuterRef, Prefetch, Q, Subquery
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_field, extend_schema_view
from rest_framework import serializers

from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.graph.evidence import confirmed_owner
from apps.ingestion.models import CompanyKgdState, SourceObservation, SelectedFact, IdentityCandidate
from apps.ingestion.parsers.kgd import DEBT_SOURCE, KgdParser, TAXPAYER_SOURCE, validate_facts
from apps.owners.models import Directorship, Ownership, PersonIdentity
from apps.owners.querysets import is_confirmed_role

from .common import ApiDetailView, ApiListView, EmptyQuerySerializer, ListQuerySerializer, safe_source_url
from .catalogue import company_profile_scope, person_role_scope


class CompanyQuerySerializer(ListQuerySerializer):
    profile_status = serializers.ChoiceField(choices=['checked', 'pending'], required=False,
        help_text='Checked means the displayed company name/BIN has accepted registry or Adata profile evidence; not complete checks.')
    bin = serializers.RegexField(r'\A[0-9]{12}\Z', required=False, trim_whitespace=False)
    is_supplier = serializers.BooleanField(required=False)
    is_customer = serializers.BooleanField(required=False)
    ordering = serializers.ChoiceField(choices=['name', '-name', 'bin', '-bin', 'id', '-id'], default='name')


class PersonQuerySerializer(ListQuerySerializer):
    is_verified = serializers.BooleanField(required=False)
    has_current_role = serializers.BooleanField(required=False, help_text='Has a role marked current in saved observations; not a confirmed legal period.')
    ordering = serializers.ChoiceField(choices=['full_name', '-full_name', 'id', '-id'], default='full_name')


class ContractQuerySerializer(ListQuerySerializer):
    supplier_id = serializers.IntegerField(min_value=1, required=False)
    customer_id = serializers.IntegerField(min_value=1, required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    winner = serializers.BooleanField(required=False)
    ordering = serializers.ChoiceField(choices=['contract_date', '-contract_date', 'amount', '-amount',
                                               'contract_number', '-contract_number', 'id', '-id'], default='-contract_date')

    def validate(self, values):
        if values.get('date_from') and values.get('date_to') and values['date_from'] > values['date_to']:
            raise serializers.ValidationError({'date_to': 'Must be on or after date_from.'})
        return values


class RoleQuerySerializer(ListQuerySerializer):
    company_id = serializers.IntegerField(min_value=1, required=False)
    person_id = serializers.IntegerField(min_value=1, required=False)
    is_current = serializers.BooleanField(required=False, help_text='Observed current flag; legal dates are reported separately.')
    ordering = serializers.ChoiceField(choices=['id', '-id', 'start_date', '-start_date'], default='id')


class CompanySerializer(serializers.ModelSerializer):
    legacy_risk_score = serializers.IntegerField(source='risk_score', read_only=True)
    legacy_score_interpretation = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = ['id', 'bin', 'name', 'is_supplier', 'is_customer', 'region', 'city',
                  'legacy_risk_score', 'legacy_score_interpretation']
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_legacy_score_interpretation(self, company):
        return 'uncalibrated_legacy_index'


class KgdSavedResultSerializer(serializers.Serializer):
    observation_id = serializers.IntegerField()
    observed_at = serializers.DateTimeField()
    parser_version = serializers.CharField()
    stale = serializers.BooleanField()
    taxpayer_type = serializers.CharField(required=False)
    taxpayer_name = serializers.CharField(required=False)
    registration_begin = serializers.DateField(allow_null=True, required=False)
    registration_end = serializers.DateField(allow_null=True, required=False)
    total_arrears = serializers.DecimalField(max_digits=30, decimal_places=2, coerce_to_string=True, required=False)
    tax_arrears = serializers.DecimalField(max_digits=30, decimal_places=2, coerce_to_string=True, required=False)
    pension_arrears = serializers.DecimalField(max_digits=30, decimal_places=2, coerce_to_string=True, required=False)
    social_arrears = serializers.DecimalField(max_digits=30, decimal_places=2, coerce_to_string=True, required=False)
    health_insurance_arrears = serializers.DecimalField(max_digits=30, decimal_places=2, coerce_to_string=True, required=False)
    reporting_dates = serializers.ListField(child=serializers.DateField(), required=False)


class KgdSummarySerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=[TAXPAYER_SOURCE, DEBT_SOURCE])
    status = serializers.ChoiceField(choices=['success', 'not_found', 'unavailable', 'invalid', 'not_checked'])
    latest_observation_id = serializers.IntegerField(allow_null=True)
    latest_observed_at = serializers.DateTimeField(allow_null=True)
    source_url = serializers.URLField()
    last_successful = KgdSavedResultSerializer(allow_null=True)


def saved_kgd_summaries(company):
    """A failed attempt never becomes zero debt or overwrites a dated success."""
    rows = {row.source: row for row in company._api_kgd_states}
    cutoff = timezone.now() - timedelta(days=settings.KGD_RESULT_MAX_AGE_DAYS)
    today = timezone.localdate()
    summaries = []
    for source in (TAXPAYER_SOURCE, DEBT_SOURCE):
        row = rows.get(source)
        latest = row.latest_observation if row else None
        successful = row.last_successful_observation if row else None
        latest_valid = bool(latest and latest.source == source and latest.supplier_id == company.pk
                            and latest.subject_key == f'company:{company.bin}')
        status = latest.status if latest_valid else ('invalid' if latest else 'not_checked')
        if status not in {'success', 'not_found', 'unavailable', 'invalid', 'not_checked'}:
            status = 'invalid'
        result = None
        if successful and successful.status == 'success' and successful.source == source and (
                successful.supplier_id == company.pk and successful.subject_key == f'company:{company.bin}'):
            try:
                facts = validate_facts(source, successful.normalized_values, company.bin)
                if source == DEBT_SOURCE and any(day > today for day in facts['kgd_reporting_dates']):
                    raise ValueError('future_reporting_date')
            except (ValueError, TypeError, KeyError, AttributeError):
                if successful.pk == (latest.pk if latest else None):
                    status = 'invalid'
            else:
                stale = status != 'success' or successful.observed_at < cutoff
                result = {'observation_id': successful.pk, 'observed_at': successful.observed_at,
                          'parser_version': successful.parser_version, 'stale': stale}
                if source == TAXPAYER_SOURCE:
                    result.update(taxpayer_type=facts['kgd_taxpayer_type'], taxpayer_name=facts['kgd_taxpayer_name'],
                                  registration_begin=facts['kgd_registration_begin'], registration_end=facts['kgd_registration_end'])
                else:
                    dates = facts['kgd_reporting_dates']
                    result.update({name: facts['kgd_' + name] for name in (
                        'total_arrears', 'tax_arrears', 'pension_arrears', 'social_arrears', 'health_insurance_arrears')})
                    result.update(reporting_dates=dates, stale=stale or not dates or
                        (today - min(dates)).days > settings.KGD_RESULT_MAX_AGE_DAYS)
        if status == 'success' and (result is None or not latest or result['observation_id'] != latest.pk):
            # A success status without its identity-validated facts is not a usable success.
            status = 'invalid'
        if source == DEBT_SOURCE and status == 'not_found':
            status = 'invalid'
        if result and status != 'success':
            result['stale'] = True
        summaries.append({'source': source, 'status': status,
                          'latest_observation_id': latest.pk if latest_valid else None,
                          'latest_observed_at': latest.observed_at if latest_valid else None,
                          'source_url': KgdParser.SOURCE_URLS[source], 'last_successful': result})
    return summaries


class FieldEvidenceSerializer(serializers.Serializer):
    field = serializers.CharField()
    source = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=['source_backed', 'legacy', 'unconfirmed'])
    observed_at = serializers.DateTimeField(allow_null=True)
    url = serializers.URLField(allow_null=True)


class CompanyDetailSerializer(CompanySerializer):
    kgd_checks = serializers.SerializerMethodField()
    website = serializers.SerializerMethodField()
    field_evidence = serializers.SerializerMethodField()

    class Meta(CompanySerializer.Meta):
        fields = CompanySerializer.Meta.fields + ['oked', 'company_status', 'registration_date', 'address', 'phone', 'email',
                 'description', 'resident_status', 'company_size', 'kopf', 'economic_sector', 'website',
                 'created_at', 'updated_at', 'adata_updated_at', 'kgd_checks', 'field_evidence']
        read_only_fields = fields

    @extend_schema_field(KgdSummarySerializer(many=True))
    def get_kgd_checks(self, company):
        return KgdSummarySerializer(saved_kgd_summaries(company), many=True).data

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_website(self, company):
        return safe_source_url(company.website)

    @extend_schema_field(FieldEvidenceSerializer(many=True))
    def get_field_evidence(self, company):
        selected = {row.field: row.observation for row in company._api_selected_facts}
        result = []
        for field in ('name', 'registration_date', 'company_status', 'region', 'city', 'address',
                      'oked', 'phone', 'email', 'company_size', 'economic_sector', 'description', 'website'):
            obs = selected.get(field)
            bound = bool(obs and obs.supplier_id == company.pk and obs.subject_key == f'company:{company.bin}')
            legacy = bound and obs.source == 'legacy'
            values = obs.normalized_values if bound and isinstance(obs.normalized_values, dict) else {}
            confirmed = bool(bound and not legacy and obs.status == 'success' and field in values
                             and str(values[field]) == str(getattr(company, field)))
            result.append({'field': field, 'source': obs.source if bound else None,
                'status': 'source_backed' if confirmed else 'legacy' if legacy else 'unconfirmed',
                'observed_at': obs.observed_at if confirmed else None,
                'url': safe_source_url(obs.source_url) if bound and not legacy else None})
        return FieldEvidenceSerializer(result, many=True).data


class PersonSerializer(serializers.ModelSerializer):
    identity_status = serializers.SerializerMethodField()
    history_status = serializers.SerializerMethodField()

    class Meta:
        model = PersonIdentity
        fields = ['id', 'full_name', 'is_verified', 'identity_status', 'history_status']
        read_only_fields = fields

    @extend_schema_field(serializers.ChoiceField(choices=['identifier_verified', 'unverified']))
    def get_identity_status(self, person):
        return 'identifier_verified' if person.is_verified and person.iin else 'unverified'

    @extend_schema_field(serializers.CharField())
    def get_history_status(self, person):
        return 'verified_history_not_integrated'


class PersonDetailSerializer(PersonSerializer):
    same_name_count = serializers.SerializerMethodField()
    pending_match_count = serializers.SerializerMethodField()

    class Meta(PersonSerializer.Meta):
        fields = PersonSerializer.Meta.fields + ['same_name_count', 'pending_match_count']

    @extend_schema_field(serializers.IntegerField())
    def get_same_name_count(self, person):
        if not person.full_name.strip():
            return 0
        return PersonIdentity.objects.filter(full_name__iexact=person.full_name).exclude(pk=person.pk).count()

    @extend_schema_field(serializers.IntegerField())
    def get_pending_match_count(self, person):
        return IdentityCandidate.objects.filter(Q(left__person=person) | Q(right__person=person), status='pending').count()


class PersonCompanyPreviewSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class PersonRoleContextSerializer(serializers.Serializer):
    has_current_role = serializers.BooleanField()
    company_count = serializers.IntegerField()
    companies = PersonCompanyPreviewSerializer(many=True)


class PersonDirectorySerializer(PersonSerializer):
    role_context = serializers.SerializerMethodField()

    class Meta(PersonSerializer.Meta):
        fields = PersonSerializer.Meta.fields + ['role_context']

    @extend_schema_field(PersonRoleContextSerializer)
    def get_role_context(self, person):
        roles = [*person._directory_directorships, *person._directory_ownerships]
        current = [role for role in roles if role.is_current]
        companies = {role.supplier_id: role.supplier.name for role in (current or roles)}
        ordered = sorted(companies.items(), key=lambda pair: (pair[1], pair[0]))
        return {'has_current_role': bool(current), 'company_count': len(companies),
                'companies': [{'id': pk, 'name': name} for pk, name in ordered[:2]]}


class ContractSerializer(serializers.ModelSerializer):
    supplier = CompanySerializer(read_only=True)
    customer = CompanySerializer(read_only=True, allow_null=True)
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, coerce_to_string=True, read_only=True)
    source_url = serializers.URLField(source='goszakup_url', read_only=True, allow_null=True)
    source_observation_id = serializers.IntegerField(source='_api_observation_id', read_only=True, allow_null=True)
    source_observed_at = serializers.DateTimeField(source='_api_observed_at', read_only=True, allow_null=True)

    class Meta:
        model = Contract
        fields = ['id', 'contract_number', 'contract_gos_id', 'tender_id', 'title', 'amount',
                  'contract_date', 'winner', 'supplier', 'customer', 'customer_name', 'customer_bin',
                  'source_url', 'source_observation_id', 'source_observed_at', 'created_at']
        read_only_fields = fields


class EntitySourceReferenceSerializer(serializers.Serializer):
    observation_id = serializers.IntegerField()
    source = serializers.CharField()
    status = serializers.CharField()
    observed_at = serializers.DateTimeField(allow_null=True)
    parser_version = serializers.CharField()
    url = serializers.URLField(allow_null=True)


def observation_reference(observation, company_id):
    if observation is None or observation.supplier_id != company_id:
        return None
    return {'observation_id': observation.pk, 'source': observation.source, 'status': observation.status,
            'observed_at': observation.observed_at if observation.source != 'legacy' else None,
            'parser_version': observation.parser_version,
            'url': safe_source_url(observation.source_url)}


class DirectorshipSerializer(serializers.ModelSerializer):
    company = CompanySerializer(source='supplier', read_only=True)
    person = PersonSerializer(source='person_identity', read_only=True, allow_null=True)
    observed_name = serializers.CharField(source='director.full_name', read_only=True)
    identity_verified = serializers.SerializerMethodField()
    currently_applicable = serializers.SerializerMethodField()
    temporal_status = serializers.SerializerMethodField()
    source_reference = serializers.SerializerMethodField()

    class Meta:
        model = Directorship
        fields = ['id', 'company', 'person', 'observed_name', 'identity_status', 'identity_verified',
                  'is_current', 'currently_applicable', 'temporal_status', 'start_date', 'end_date', 'observed_from', 'observed_until',
                  'source', 'source_reference']
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_identity_verified(self, role):
        observation = role.source_observation
        if observation and not isinstance(observation.normalized_values, dict):
            return False
        return is_confirmed_role(role)

    @extend_schema_field(serializers.BooleanField(allow_null=True,
        help_text='Known current legal interval uses [start_date, end_date); missing legal bounds yield null unless already outside a known bound.'))
    def get_currently_applicable(self, role):
        today = timezone.localdate()
        if not role.is_current or (role.start_date is not None and role.start_date > today) or (
                role.end_date is not None and role.end_date <= today):
            return False
        if role.start_date is None or role.end_date is None:
            return None
        return True

    @extend_schema_field(serializers.ChoiceField(choices=['unknown', 'in_period', 'not_in_period', 'observed_inactive']))
    def get_temporal_status(self, role):
        if not role.is_current:
            return 'observed_inactive'
        applicable = self.get_currently_applicable(role)
        return 'unknown' if applicable is None else 'in_period' if applicable else 'not_in_period'

    @extend_schema_field(EntitySourceReferenceSerializer(allow_null=True))
    def get_source_reference(self, role):
        result = observation_reference(role.source_observation, role.supplier_id)
        return EntitySourceReferenceSerializer(result).data if result else None


class OwnershipSerializer(DirectorshipSerializer):
    observed_name = serializers.CharField(source='owner.full_name', read_only=True)
    share_percent = serializers.DecimalField(max_digits=5, decimal_places=2, coerce_to_string=True, allow_null=True, read_only=True)

    class Meta(DirectorshipSerializer.Meta):
        model = Ownership
        fields = DirectorshipSerializer.Meta.fields + ['share_percent']
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_identity_verified(self, role):
        return confirmed_owner(role)


@extend_schema_view(get=extend_schema(parameters=[CompanyQuerySerializer], tags=['Companies']))
class CompanyListView(ApiListView):
    serializer_class = CompanySerializer
    query_serializer_class = CompanyQuerySerializer

    def get_queryset(self):
        query = getattr(self, 'query', {})
        queryset = Supplier.objects.all()
        if 'profile_status' in query:
            queryset = company_profile_scope(queryset, checked=query['profile_status'] == 'checked')
        for field in ('bin', 'is_supplier', 'is_customer'):
            if field in query:
                queryset = queryset.filter(**{field: query[field]})
        if query.get('search'):
            queryset = queryset.filter(Q(name__icontains=query['search']) | Q(bin__icontains=query['search']))
        return queryset.order_by(query.get('ordering', 'name'), 'pk')


@extend_schema_view(get=extend_schema(tags=['Companies']))
class CompanyDetailView(ApiDetailView):
    serializer_class = CompanyDetailSerializer
    query_serializer_class = EmptyQuerySerializer
    queryset = Supplier.objects.prefetch_related(Prefetch('kgd_states', queryset=CompanyKgdState.objects.select_related(
        'latest_observation', 'last_successful_observation'), to_attr='_api_kgd_states'),
        Prefetch('selected_facts', queryset=SelectedFact.objects.select_related('observation'), to_attr='_api_selected_facts'))


@extend_schema_view(get=extend_schema(parameters=[PersonQuerySerializer], tags=['People']))
class PersonListView(ApiListView):
    serializer_class = PersonDirectorySerializer
    query_serializer_class = PersonQuerySerializer

    def get_queryset(self):
        query = getattr(self, 'query', {})
        queryset = PersonIdentity.objects.all()
        if 'is_verified' in query:
            queryset = queryset.filter(is_verified=query['is_verified'])
        if 'has_current_role' in query:
            queryset = person_role_scope(queryset, current=query['has_current_role'])
        if query.get('search'):
            queryset = queryset.filter(full_name__icontains=query['search'])
        return queryset.order_by(query.get('ordering', 'full_name'), 'pk').prefetch_related(
            Prefetch('directorship_set', queryset=Directorship.objects.select_related('supplier'),
                     to_attr='_directory_directorships'),
            Prefetch('ownership_set', queryset=Ownership.objects.select_related('supplier'),
                     to_attr='_directory_ownerships'))


@extend_schema_view(get=extend_schema(tags=['People']))
class PersonDetailView(ApiDetailView):
    serializer_class = PersonDetailSerializer
    query_serializer_class = EmptyQuerySerializer
    queryset = PersonIdentity.objects.all()


def contract_queryset():
    latest = SourceObservation.objects.filter(contract_id=OuterRef('pk'), supplier_id=OuterRef('supplier_id'),
        status='success', subject_key__startswith='contract:').order_by('-observed_at', '-pk')
    return Contract.objects.select_related('supplier', 'customer').annotate(
        _api_observation_id=Subquery(latest.values('pk')[:1]),
        _api_observed_at=Subquery(latest.exclude(source='legacy').values('observed_at')[:1]))


@extend_schema_view(get=extend_schema(parameters=[ContractQuerySerializer], tags=['Contracts']))
class ContractListView(ApiListView):
    serializer_class = ContractSerializer
    query_serializer_class = ContractQuerySerializer

    def get_queryset(self):
        query = getattr(self, 'query', {})
        queryset = contract_queryset()
        for field in ('supplier_id', 'customer_id', 'winner'):
            if field in query:
                queryset = queryset.filter(**{field: query[field]})
        if query.get('date_from'):
            queryset = queryset.filter(contract_date__gte=query['date_from'])
        if query.get('date_to'):
            queryset = queryset.filter(contract_date__lte=query['date_to'])
        if query.get('search'):
            queryset = queryset.filter(Q(title__icontains=query['search']) | Q(contract_number__icontains=query['search'])
                                       | Q(tender_id__icontains=query['search']))
        return queryset.order_by(query.get('ordering', '-contract_date'), 'pk')


@extend_schema_view(get=extend_schema(tags=['Contracts']))
class ContractDetailView(ApiDetailView):
    serializer_class = ContractSerializer
    query_serializer_class = EmptyQuerySerializer
    queryset = contract_queryset()


class RoleListView(ApiListView):
    query_serializer_class = RoleQuerySerializer
    role_model = None
    role_related_name = None

    def get_queryset(self):
        query = getattr(self, 'query', {})
        queryset = self.role_model.objects.select_related('supplier', self.role_related_name, 'person_identity', 'source_observation')
        for parameter, field in (('company_id', 'supplier_id'), ('person_id', 'person_identity_id'), ('is_current', 'is_current')):
            if parameter in query:
                queryset = queryset.filter(**{field: query[parameter]})
        if query.get('search'):
            queryset = queryset.filter(Q(supplier__name__icontains=query['search']) | Q(supplier__bin__icontains=query['search'])
                                       | Q(**{self.role_related_name + '__full_name__icontains': query['search']}))
        return queryset.order_by(query.get('ordering', 'id'), 'pk')


@extend_schema_view(get=extend_schema(parameters=[RoleQuerySerializer], tags=['People']))
class DirectorshipListView(RoleListView):
    serializer_class = DirectorshipSerializer
    role_model = Directorship
    role_related_name = 'director'


@extend_schema_view(get=extend_schema(parameters=[RoleQuerySerializer], tags=['People']))
class OwnershipListView(RoleListView):
    serializer_class = OwnershipSerializer
    role_model = Ownership
    role_related_name = 'owner'
