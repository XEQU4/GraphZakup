import uuid

from django.db import models
from django.utils import timezone


class IngestionRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = 'running', 'Running'
        SUCCEEDED = 'succeeded', 'Completed'
        FAILED = 'failed', 'Failed'
        PARTIAL = 'partial', 'Partially completed'

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    mode = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=Status, default=Status.RUNNING, db_index=True)
    stage = models.CharField(max_length=20, default='contracts')
    options = models.JSONField(default=dict)
    next_page = models.PositiveIntegerField(default=1)
    offset = models.PositiveIntegerField(default=0)
    page_fingerprint = models.CharField(max_length=64, blank=True)
    enrichment_cursor = models.PositiveBigIntegerField(default=0)
    counters = models.JSONField(default=dict)
    error_code = models.CharField(max_length=80, blank=True)
    attempts = models.PositiveIntegerField(default=1)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-started_at']


class IngestionLease(models.Model):
    key = models.CharField(max_length=80, unique=True)
    token = models.UUIDField(default=uuid.uuid4)
    expires_at = models.DateTimeField(default=timezone.now)
    run = models.ForeignKey(IngestionRun, null=True, blank=True, on_delete=models.SET_NULL)


class SourceCheckpoint(models.Model):
    source = models.CharField(max_length=40)
    stream = models.CharField(max_length=20)
    next_page = models.PositiveIntegerField(default=1)
    offset = models.PositiveIntegerField(default=0)
    page_fingerprint = models.CharField(max_length=64, blank=True)
    run = models.ForeignKey(IngestionRun, null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source', 'stream'], name='ingestion_checkpoint_stream_unique')]


class SourceObservation(models.Model):
    """Structured source facts; HTML, credentials and exception messages are never stored."""
    run = models.ForeignKey(IngestionRun, on_delete=models.PROTECT, related_name='observations')
    source = models.CharField(max_length=40)
    subject_key = models.CharField(max_length=255)
    supplier = models.ForeignKey('companies.Supplier', null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='source_observations')
    contract = models.ForeignKey('contracts.Contract', null=True, blank=True, on_delete=models.PROTECT,
                                 related_name='source_observations')
    status = models.CharField(max_length=20)
    raw_values = models.JSONField(default=dict)
    normalized_values = models.JSONField(default=dict)
    parser_version = models.CharField(max_length=40)
    source_url = models.URLField(max_length=1000, blank=True)
    observed_at = models.DateTimeField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    error_code = models.CharField(max_length=80, blank=True)
    fingerprint = models.CharField(max_length=64)
    from_cache = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=['source', 'subject_key', '-observed_at'], name='ingestion_observation_lookup')]
        constraints = [models.UniqueConstraint(fields=['run', 'source', 'subject_key', 'fingerprint'],
                                              name='ingestion_observation_run_unique')]


class SelectedFact(models.Model):
    supplier = models.ForeignKey('companies.Supplier', on_delete=models.PROTECT, related_name='selected_facts')
    field = models.CharField(max_length=40)
    observation = models.ForeignKey(SourceObservation, on_delete=models.PROTECT, related_name='selected_fields')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['supplier', 'field'], name='ingestion_selected_field_unique')]


class CompanyKgdState(models.Model):
    """Current attempt and retained last success; evidence lives in observations."""
    supplier = models.ForeignKey('companies.Supplier', on_delete=models.PROTECT, related_name='kgd_states')
    source = models.CharField(max_length=40, choices=[
        ('kgd_taxpayer', 'Taxpayer registration'), ('kgd_tax_debt', 'Tax arrears'),
    ])
    latest_observation = models.ForeignKey(SourceObservation, on_delete=models.PROTECT,
                                          related_name='latest_kgd_states')
    last_successful_observation = models.ForeignKey(SourceObservation, null=True, blank=True,
                                                   on_delete=models.PROTECT, related_name='successful_kgd_states')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['supplier', 'source'], name='ingestion_kgd_company_source_unique')]


class IngestionIssue(models.Model):
    run = models.ForeignKey(IngestionRun, on_delete=models.PROTECT, related_name='issues')
    source = models.CharField(max_length=40)
    subject_key = models.CharField(max_length=255)
    stage = models.CharField(max_length=20)
    error_code = models.CharField(max_length=80)
    supplier = models.ForeignKey('companies.Supplier', null=True, blank=True, on_delete=models.PROTECT)
    page = models.PositiveIntegerField(null=True, blank=True)
    resolved = models.BooleanField(default=False, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['run', 'source', 'subject_key', 'stage'],
                                              name='ingestion_issue_subject_unique')]


class ContractRetry(models.Model):
    """A rejected registry row remains actionable independently of page movement."""
    external_id = models.PositiveBigIntegerField(unique=True)
    record = models.JSONField(default=dict)
    error_code = models.CharField(max_length=80)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class PersonSourceIdentity(models.Model):
    person = models.ForeignKey('owners.PersonIdentity', on_delete=models.PROTECT, related_name='source_identities')
    supplier = models.ForeignKey('companies.Supplier', on_delete=models.PROTECT)
    source = models.CharField(max_length=40)
    source_key = models.CharField(max_length=255)
    role = models.CharField(max_length=20)
    observed_name = models.CharField(max_length=255)
    normalized_name = models.CharField(max_length=255, db_index=True)
    observation = models.ForeignKey(SourceObservation, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source', 'source_key'], name='ingestion_person_source_unique')]


class IdentityCandidate(models.Model):
    left = models.ForeignKey(PersonSourceIdentity, on_delete=models.PROTECT, related_name='left_candidates')
    right = models.ForeignKey(PersonSourceIdentity, on_delete=models.PROTECT, related_name='right_candidates')
    reason = models.CharField(max_length=40, default='same_name')
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default='0.250')
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Needs review'), ('rejected', 'Different people'), ('confirmed', 'Confirmed'),
    ])
    evidence = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['left', 'right'], name='ingestion_identity_pair_unique'),
                       models.CheckConstraint(condition=models.Q(left__lt=models.F('right')), name='ingestion_candidate_ordered')]
