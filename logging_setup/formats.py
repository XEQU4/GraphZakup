import logging

from logging.handlers import TimedRotatingFileHandler
from colorama import Fore, Style


class ColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: Fore.WHITE,
        logging.INFO: Fore.CYAN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT
    }

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelno, "")
        message = super().format(record)
        return f"{color}{message}{Style.RESET_ALL}"


class DatedTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.suffix = "%Y-%m-%d"

file_fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
date_fmt = "%Y-%m-%d %H:%M:%S"
