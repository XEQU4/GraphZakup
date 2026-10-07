"""Aggregate saved workspace facts; never starts collection or analysis."""
from decimal import Decimal
from django.db.models import Max, Min, Sum
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from apps.companies.models import Supplier
from apps.contracts.models import Contract
from apps.ingestion.models import SourceObservation, CompanyKgdState
from apps.owners.models import PersonIdentity
from apps.graph.models import RiskCluster, GraphSnapshot
from .common import ApiView, EmptyQuerySerializer

class OverviewSerializer(serializers.Serializer):
    company_count = serializers.IntegerField()
    supplier_count = serializers.IntegerField()
    customer_count = serializers.IntegerField()
    contract_count = serializers.IntegerField()
    people_count = serializers.IntegerField()
    verified_people_count = serializers.IntegerField()
    active_group_count = serializers.IntegerField()
    snapshot_count = serializers.IntegerField()
    total_contract_amount = serializers.DecimalField(max_digits=40, decimal_places=2, coerce_to_string=True)
    contract_date_from = serializers.DateField(allow_null=True)
    contract_date_to = serializers.DateField(allow_null=True)
    latest_saved_observation_at = serializers.DateTimeField(allow_null=True)
    legacy_observation_count = serializers.IntegerField()
    nonlegacy_success_count = serializers.IntegerField()
    companies_with_kgd_records = serializers.IntegerField()

class OverviewView(ApiView):
    query_serializer_class = EmptyQuerySerializer
    @extend_schema(responses=OverviewSerializer)
    def get(self, request):
        contracts = Contract.objects.aggregate(amount=Sum('amount'), first=Min('contract_date'), last=Max('contract_date'))
        observations = SourceObservation.objects
        values = {
            'company_count':Supplier.objects.count(),
            'supplier_count':Supplier.objects.filter(is_supplier=True).count(),
            'customer_count':Supplier.objects.filter(is_customer=True).count(),
            'contract_count':Contract.objects.count(),
            'people_count':PersonIdentity.objects.count(),
            'verified_people_count':PersonIdentity.objects.filter(is_verified=True).exclude(iin='').count(),
            'active_group_count':RiskCluster.objects.filter(is_active=True).count(),
            'snapshot_count':GraphSnapshot.objects.count(),
            'total_contract_amount':contracts['amount'] if contracts['amount'] is not None else Decimal('0.00'),
            'contract_date_from':contracts['first'], 'contract_date_to':contracts['last'],
            'latest_saved_observation_at':observations.aggregate(value=Max('observed_at'))['value'],
            'legacy_observation_count':observations.filter(source='legacy').count(),
            'nonlegacy_success_count':observations.filter(status='success').exclude(source='legacy').count(),
            'companies_with_kgd_records':CompanyKgdState.objects.filter(source__in=['kgd_taxpayer','kgd_tax_debt']).values('supplier_id').distinct().count(),
        }
        return Response(OverviewSerializer(values).data)
