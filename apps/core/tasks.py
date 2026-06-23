import logging

from celery import shared_task
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
      parse 500 new contracts → enrich_suppliers → link_directors → build_clusters

    Ручной запуск:
        uv run celery -A config call apps.core.tasks.update_all_data
    """
    logger.info("=== Старт обновления данных (500 новых контрактов) ===")
    try:
        call_command("import_contracts", total=500, mode="new")
        logger.info("=== Пайплайн завершён успешно ===")
    except Exception as exc:
        logger.exception("Пайплайн упал: %s", exc)
        raise self.retry(exc=exc)


@shared_task(name="apps.core.tasks.cleanup_logs")
def cleanup_logs():
    """Ежедневная очистка логов старше 30 дней."""
    logger.info("Запуск очистки старых логов...")
    from logging_setup import schedule_log_cleanup
    schedule_log_cleanup()
    logger.info("Очистка логов завершена.")
