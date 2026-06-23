import sys
import logging


def filter_maker(level: str):
    levelno = getattr(logging, level.upper(), logging.WARNING)

    def filter_func(record: logging.LogRecord) -> bool:
        return record.levelno <= levelno

    return filter_func


def max_level_filter(max_level_name: str):
    max_level = getattr(logging, max_level_name.upper(), logging.WARNING)

    class MaxLevelFilter(logging.Filter):
        def filter(self, record):
            return record.levelno <= max_level

    return MaxLevelFilter()


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
