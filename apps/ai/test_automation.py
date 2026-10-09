from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from .automation import schedule_explanations
from .jobs import analyse_cluster_task
from .models import AnalysisJob, AnalysisState
from .services import prepare_analysis
from .tests import AnalysisFixtures


@override_settings(ENABLE_BACKGROUND_AI=True, AI_PROVIDER='ollama', AI_MODEL='qwen3:4b')
class AutomationTests(AnalysisFixtures, TestCase):
    def setUp(self):
        self.cluster, self.companies = self.group()
        self.analysis, _ = prepare_analysis(self.cluster.pk)

    @override_settings(ENABLE_BACKGROUND_AI=False)
    def test_disabled_does_not_enqueue(self):
        self.assertEqual(schedule_explanations()['status'], 'disabled')
        self.assertFalse(AnalysisJob.objects.exists())

    @override_settings(AI_PROVIDER='openai', AI_ALLOW_PAID=True, AI_API_KEY='offline-test')
    def test_automatic_generation_never_uses_paid_provider(self):
        self.assertEqual(schedule_explanations()['status'], 'local_provider_required')
        self.assertFalse(AnalysisJob.objects.exists())

    def test_jobs_use_isolated_queue_and_repeat_cycles_deduplicate(self):
        with patch('apps.ai.jobs.analyse_cluster_task.apply_async') as send:
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(schedule_explanations()['queued'], 1)
            self.assertEqual(send.call_args.kwargs['queue'], 'iz2-ai')
            self.assertEqual(schedule_explanations()['queued'], 0)
        self.assertEqual(AnalysisJob.objects.count(), 1)

    def test_failed_model_waits_before_retry_and_retains_template(self):
        with self.captureOnCommitCallbacks(execute=False):
            schedule_explanations()
        job = AnalysisJob.objects.get()
        job.status, job.finished_at = 'failed', timezone.now()
        job.save()
        self.assertEqual(schedule_explanations()['queued'], 0)
        self.assertEqual(AnalysisState.objects.get().explanation.provider, 'template')
        AnalysisJob.objects.update(finished_at=timezone.now() - timedelta(hours=7))
        with self.captureOnCommitCallbacks(execute=False):
            self.assertEqual(schedule_explanations()['queued'], 1)

    def test_success_is_reused_and_new_evidence_gets_a_new_job(self):
        with self.captureOnCommitCallbacks(execute=False):
            schedule_explanations()
        job = AnalysisJob.objects.get()
        with patch('apps.ai.jobs.generate', return_value=(self.plan(self.analysis), {})):
            result = analyse_cluster_task.run(job.pk)
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(schedule_explanations()['queued'], 0)
        self.arrears(self.companies[0], '4000.00')
        prepare_analysis(self.cluster.pk)
        with self.captureOnCommitCallbacks(execute=False):
            self.assertEqual(schedule_explanations()['queued'], 1)

    def test_pending_lost_broker_message_is_replayed_without_new_job(self):
        with self.captureOnCommitCallbacks(execute=False):
            schedule_explanations()
        AnalysisJob.objects.update(created_at=timezone.now() - timedelta(minutes=11))
        with patch('apps.ai.automation.enqueue') as enqueue:
            self.assertEqual(schedule_explanations()['queued'], 0)
        enqueue.assert_called_once_with(AnalysisJob.objects.get().pk, queue='iz2-ai')
        self.assertEqual(AnalysisJob.objects.count(), 1)
