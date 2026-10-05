import logging

from celery import shared_task
from django.conf import settings
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    name="apps.core.tasks.update_all_data",
)
def update_all_data(self):
    """
    Запускает полный пайплайн каждые 12 часов:
      parse 500 new contracts → enrich_suppliers → build_clusters

    Ручной запуск:
        uv run celery -A config call apps.core.tasks.update_all_data
    """
    if not settings.ENABLE_SCHEDULED_IMPORT:
        logger.warning("Импорт Celery отключён: ENABLE_SCHEDULED_IMPORT=false")
        return {"status": "disabled"}
    logger.info("=== Старт обновления данных (500 новых контрактов) ===")
    try:
        call_command("import_contracts", total=500, mode="new")
        logger.info("=== Пайплайн завершён успешно ===")
    except Exception as exc:
        failure_type = type(exc).__name__
        logger.error("Пайплайн завершился ошибкой (%s)", failure_type)
    else:
        return None

    # Retry outside the original except block: neither its values nor its
    # cause chain may enter Celery's exception serialization/logging.
    safe_error = RuntimeError(f"Pipeline failed ({failure_type})")
    try:
        retry = self.retry(exc=safe_error, throw=False)
    except Exception:
        # Covers exhausted retries and failures while publishing the retry.
        raise safe_error from None
    raise retry from None


@shared_task(name="apps.core.tasks.cleanup_logs")
def cleanup_logs():
    """Ежедневная очистка логов старше 30 дней."""
    logger.info("Запуск очистки старых логов...")
    from logging_setup import schedule_log_cleanup
    schedule_log_cleanup()
    logger.info("Очистка логов завершена.")
