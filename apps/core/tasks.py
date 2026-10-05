import logging

from celery import shared_task
from django.conf import settings
from apps.ingestion.leases import IngestionBusy
from apps.ingestion.services import IngestionFailure, run_pipeline

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    name="apps.core.tasks.update_all_data",
)
def update_all_data(self, resume=None):
    """
    Check 500 contracts from the registry head and update companies and graph.
    Retries resume the saved run at its current stage.

    Manual invocation:
        uv run celery -A config call apps.core.tasks.update_all_data
    """
    if not settings.ENABLE_SCHEDULED_IMPORT:
        logger.warning("Celery import disabled: ENABLE_SCHEDULED_IMPORT=false")
        return {"status": "disabled"}
    logger.info("=== Starting data update (up to 500 contracts) ===")
    try:
        run = run_pipeline(mode='update', total=500, resume=resume)
        logger.info("=== Pipeline completed successfully ===")
    except IngestionBusy:
        return {'status': 'busy'}
    except Exception as exc:
        if isinstance(exc, IngestionFailure):
            resume = exc.run_id
        failure_type = type(exc).__name__
        logger.error("Pipeline failed (%s)", failure_type)
    else:
        return {'status': run.status, 'run': str(run.uuid)}

    # Retry outside the original except block: neither its values nor its
    # cause chain may enter Celery's exception serialization/logging.
    safe_error = RuntimeError(f"Pipeline failed ({failure_type})")
    try:
        retry = self.retry(exc=safe_error, throw=False, kwargs={'resume': resume})
    except Exception:
        # Covers exhausted retries and failures while publishing the retry.
        raise safe_error from None
    raise retry from None


@shared_task(name="apps.core.tasks.cleanup_logs")
def cleanup_logs():
    """Daily cleanup of logs older than 30 days."""
    logger.info("Starting old log cleanup...")
    from logging_setup import schedule_log_cleanup
    schedule_log_cleanup()
    logger.info("Log cleanup completed.")
