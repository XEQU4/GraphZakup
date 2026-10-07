import sys
import logging
import os

from colorama import init

from logging_setup.cleanup_old_logs import cleanup_old_logs_by_filename
from logging_setup.formats import ColorFormatter, file_fmt, date_fmt, DailyFileHandler
from logging_setup.filters import filter_maker, max_level_filter, handle_exception


def init_logging(log_dir: str = "logs", to_files: bool = True):
    """
    Initialise logging for IZ2.

    Called once through Apps.ready() during Django setup
    or directly from manage.py.

    Outputs:
      - Console (coloured output through colorama):
          DEBUG..WARNING → stdout
          ERROR..CRITICAL → stderr
      - logs/app-YYYY-MM-DD.log (DEBUG..WARNING, 7 UTC calendar days)
      - logs/error-YYYY-MM-DD.log (ERROR+, 14 UTC calendar days)
    """
    init(autoreset=True)
    if to_files:
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

    handlers = [stdout_handler, stderr_handler]
    if to_files:
        for name, level, retention_days in (('app', logging.DEBUG, 7), ('error', logging.ERROR, 14)):
            handler = DailyFileHandler(
                filename=os.path.join(log_dir, name + '.log'),
                retention_days=retention_days, encoding='utf-8',
            )
            handler.setLevel(level)
            handler.setFormatter(file_formatter)
            if name == 'app':
                handler.addFilter(max_level_filter('WARNING'))
            handlers.append(handler)

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=handlers,
    )

    # Capture unhandled exceptions in the dated error log
    sys.excepthook = handle_exception

    logging.getLogger(__name__).info("Logging initialized (log_dir=%s)", log_dir)


def schedule_log_cleanup():
    """
    Clean up old logs.
    Called by a daily Celery beat task or manually.
    """
    cleanup_old_logs_by_filename(days=30)
