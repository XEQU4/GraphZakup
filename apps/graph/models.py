import uuid
from django.conf import settings
from django.core.exceptions import ValidationError

from django.db import models
from django.db.models import Sum

from apps.companies.models import Supplier


class Connection(models.Model):
    OWNER = "owner"
    DIRECTOR = "director"
    ADDRESS = "address"
    PHONE = "phone"
    EMAIL = "email"
    CUSTOMER = "customer"

    CONNECTION_TYPES = [
        (OWNER, "Common Owner"),
        (DIRECTOR, "Common Director"),
        (ADDRESS, "Common Address"),
        (PHONE, "Common Phone"),
        (EMAIL, "Common Email"),
        (CUSTOMER, "Shared customer"),
    ]

    source_supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="outgoing_connections")
    target_supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="incoming_connections")
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPES)
    weight = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "connection_type"
                ]
            )
        ]

    def __str__(self):
        return (
            f"{self.source_supplier} -> "
            f"{self.target_supplier}"
        )


class RiskCluster(models.Model):
    current_snapshot = models.ForeignKey('GraphSnapshot', null=True, blank=True,
                                         on_delete=models.PROTECT, related_name='+')
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255)
    risk_score = models.PositiveSmallIntegerField(default=0)
    total_contract_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    explanation = models.TextField(blank=True)
    suppliers = models.ManyToManyField(Supplier, related_name="risk_clusters")
    ai_explanation = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    analysis_fingerprint = models.CharField(max_length=64, blank=True)
    explanation_stale = models.BooleanField(default=True)
    last_analyzed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-risk_score"]

    def __str__(self):
        return f"{self.name} ({self.risk_score})"

    def update_total_amount(self):
        total = (
                self.suppliers
                .aggregate(
                    total=Sum("contracts__amount")
                )["total"]
                or 0
        )

        self.total_contract_amount = total
        self.save(
            update_fields=["total_contract_amount"]
        )


class ImmutableQuerySet(models.QuerySet):
    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False, update_conflicts=False,
                    update_fields=None, unique_fields=None):
        if update_conflicts:
            raise ValidationError('Published history cannot be overwritten.')
        return super().bulk_create(objs, batch_size=batch_size, ignore_conflicts=ignore_conflicts,
                                   update_conflicts=False, update_fields=update_fields, unique_fields=unique_fields)

    def update(self, **kwargs):
        raise ValidationError('Published graph history is immutable.')

    def delete(self):
        raise ValidationError('Published graph history cannot be deleted.')


class ImmutableRecord(models.Model):
    objects = ImmutableQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Published graph history is immutable.')
        if kwargs.get('force_update') or kwargs.get('update_fields'):
            raise ValidationError('Published graph history is immutable.')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Published graph history cannot be deleted.')


class EvidenceEdge(models.Model):
    """Current projection; each published snapshot embeds its own immutable copy."""
    key = models.CharField(max_length=64, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='evidence_edges')
    source_key = models.CharField(max_length=100)
    target_key = models.CharField(max_length=100, db_index=True)
    relationship_type = models.CharField(max_length=20, db_index=True)
    semantic_hash = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)


class GraphInputState(models.Model):
    supplier = models.OneToOneField(Supplier, on_delete=models.PROTECT, related_name='graph_input_state')
    digest = models.CharField(max_length=64)
    feature_keys = models.JSONField(default=list)
    algorithm_version = models.CharField(max_length=30)


class GraphSnapshot(ImmutableRecord):
    cluster = models.ForeignKey(RiskCluster, on_delete=models.PROTECT, related_name='snapshots')
    version = models.PositiveIntegerField()
    graph_hash = models.CharField(max_length=64)
    algorithm_version = models.CharField(max_length=30)
    state = models.CharField(max_length=12, choices=[('active', 'Active'), ('retired', 'Retired'), ('legacy', 'Legacy')])
    as_of = models.DateField()
    member_ids = models.JSONField(default=list)
    payload = models.JSONField(default=dict)
    changes = models.JSONField(default=dict)
    previous = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='next_versions')
    legacy_explanation = models.TextField(blank=True)
    legacy_explanation_fingerprint = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version']
        constraints = [models.UniqueConstraint(fields=['cluster', 'version'], name='graph_snapshot_version_unique')]


class ClusterLineage(ImmutableRecord):
    source = models.ForeignKey(GraphSnapshot, on_delete=models.PROTECT, related_name='outgoing_transitions')
    target = models.ForeignKey(GraphSnapshot, on_delete=models.PROTECT, related_name='incoming_transitions')
    kind = models.CharField(max_length=20)
    shared_member_ids = models.JSONField(default=list)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source', 'target'], name='graph_lineage_pair_unique')]


class GraphViewState(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cluster = models.ForeignKey(RiskCluster, on_delete=models.PROTECT)
    snapshot = models.ForeignKey(GraphSnapshot, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField(default=1)
    schema_version = models.PositiveIntegerField(default=1)
    payload = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'cluster'], name='graph_personal_view_unique')]


class GraphRebuildJob(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    dedup_key = models.CharField(max_length=64)
    supplier_ids = models.JSONField(default=list)
    status = models.CharField(max_length=12, default='pending', choices=[
        ('pending', 'Pending'), ('running', 'Running'), ('succeeded', 'Succeeded'), ('failed', 'Failed')])
    summary = models.JSONField(default=dict)
    error_code = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['dedup_key'], condition=models.Q(status__in=['pending', 'running']),
                                              name='graph_active_job_unique')]
