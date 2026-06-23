import sys
import logging
import os

from colorama import init

from logging_setup.cleanup_old_logs import cleanup_old_logs_by_filename
from logging_setup.formats import ColorFormatter, file_fmt, date_fmt, DatedTimedRotatingFileHandler
from logging_setup.filters import filter_maker, max_level_filter, handle_exception


def init_logging(log_dir: str = "logs"):
    """
    Инициализация логирования для ГрафЗакуп.

    Вызывается один раз из config/settings.py через Apps.ready()
    или напрямую в manage.py.

    Пишет:
      - В консоль (цветной вывод через colorama):
          DEBUG..WARNING → stdout
          ERROR..CRITICAL → stderr
      - В файл logs/app.log   (DEBUG..WARNING, ротация ежедневно, 7 дней)
      - В файл logs/error.log (ERROR+,         ротация ежедневно, 14 дней)
    """
    init(autoreset=True)
    os.makedirs(log_dir, exist_ok=True)

    color_formatter = ColorFormatter(fmt=file_fmt, datefmt=date_fmt)
    file_formatter  = logging.Formatter(fmt=file_fmt, datefmt=date_fmt)

    # --- Console: INFO..WARNING → stdout ---
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.setFormatter(color_formatter)
    stdout_handler.addFilter(filter_maker("WARNING"))

    # --- Console: ERROR+ → stderr ---
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(color_formatter)

    # --- File: app.log (все кроме ERROR) ---
    app_file = DatedTimedRotatingFileHandler(
        filename=os.path.join(log_dir, "app.log"),
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
        utc=True,
    )
    app_file.setLevel(logging.DEBUG)
    app_file.setFormatter(file_formatter)
    app_file.addFilter(max_level_filter("WARNING"))

    # --- File: error.log (ERROR+) ---
    error_file = DatedTimedRotatingFileHandler(
        filename=os.path.join(log_dir, "error.log"),
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
        utc=True,
    )
    error_file.setLevel(logging.ERROR)
    error_file.setFormatter(file_formatter)

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[stdout_handler, stderr_handler, app_file, error_file],
    )

    # Перехват необработанных исключений → error.log
    sys.excepthook = handle_exception

    logging.getLogger(__name__).info("Logging initialized (log_dir=%s)", log_dir)


def schedule_log_cleanup():
    """
    Запускает очистку старых логов.
    Вызывается из Celery beat (ежедневная задача) или вручную.
    """
    cleanup_old_logs_by_filename(days=30)
