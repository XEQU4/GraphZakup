"""Durable analysis and explanation history, separate from personal graph views."""
import uuid

from django.conf import settings
from django.db import models
from apps.graph.models import ImmutableRecord


class AnalysisSnapshot(ImmutableRecord):
    cluster = models.ForeignKey('graph.RiskCluster', on_delete=models.PROTECT, related_name='analyses')
    graph_snapshot = models.ForeignKey('graph.GraphSnapshot', on_delete=models.PROTECT, related_name='analyses')
    version = models.PositiveIntegerField()
    analysis_hash = models.CharField(max_length=64)
    input_hash = models.CharField(max_length=64)
    rules_version = models.CharField(max_length=40)
    as_of = models.DateField()
    inputs = models.JSONField(default=dict)
    findings = models.JSONField(default=list)
    metrics = models.JSONField(default=dict)
    limitations = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version']
        constraints = [
            models.UniqueConstraint(fields=['cluster', 'version'], name='ai_analysis_version_unique'),
            models.UniqueConstraint(fields=['graph_snapshot', 'analysis_hash'], name='ai_analysis_content_unique'),
        ]


class Explanation(ImmutableRecord):
    analysis = models.ForeignKey(AnalysisSnapshot, on_delete=models.PROTECT, related_name='explanations')
    reuse_key = models.CharField(max_length=64, unique=True)
    language = models.CharField(max_length=12, default='en')
    provider = models.CharField(max_length=20)
    model = models.CharField(max_length=120, blank=True)
    prompt_version = models.CharField(max_length=40)
    status = models.CharField(max_length=12, choices=[('ready', 'Ready'), ('fallback', 'Template fallback')])
    text = models.TextField()
    presentation = models.JSONField(default=dict)
    usage = models.JSONField(default=dict)
    error_code = models.CharField(max_length=80, blank=True)
    experimental_score = models.PositiveSmallIntegerField(null=True, blank=True)
    experimental_evidence = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)


class AnalysisState(models.Model):
    cluster = models.OneToOneField('graph.RiskCluster', on_delete=models.PROTECT, related_name='analysis_state')
    analysis = models.ForeignKey(AnalysisSnapshot, on_delete=models.PROTECT, related_name='+')
    explanation = models.ForeignKey(Explanation, on_delete=models.PROTECT, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)


class AnalysisJob(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    graph_snapshot = models.ForeignKey('graph.GraphSnapshot', on_delete=models.PROTECT)
    analysis = models.ForeignKey(AnalysisSnapshot, null=True, blank=True, on_delete=models.PROTECT)
    explanation = models.ForeignKey(Explanation, null=True, blank=True, on_delete=models.PROTECT)
    input_hash = models.CharField(max_length=64)
    dedup_key = models.CharField(max_length=64)
    as_of = models.DateField()
    options = models.JSONField(default=dict)
    status = models.CharField(max_length=12, default='pending', choices=[
        ('pending', 'Pending'), ('running', 'Running'), ('succeeded', 'Succeeded'),
        ('fallback', 'Template fallback'), ('stale', 'Superseded'), ('failed', 'Failed')])
    error_code = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['dedup_key'], condition=models.Q(status__in=['pending', 'running']),
                                              name='ai_active_job_unique')]


class AnalysisTarget(models.Model):
    """Latest explicit request fences older workers, including other deployments."""
    cluster = models.OneToOneField('graph.RiskCluster', on_delete=models.PROTECT)
    job = models.ForeignKey(AnalysisJob, on_delete=models.PROTECT)
