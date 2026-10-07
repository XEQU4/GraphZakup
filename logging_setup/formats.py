import logging
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from colorama import Fore, Style


class ColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: Fore.WHITE,
        logging.INFO: Fore.CYAN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelno, "")
        message = super().format(record)
        return f"{color}{message}{Style.RESET_ALL}"


class DailyFileHandler(logging.Handler):
    """Append to a UTC date file without retaining a shared Windows handle.

    Django autoreload and Celery processes may share the directory. Opening and
    closing each append avoids renaming a file that another process holds open.
    An OS file lock serialises append/retention across processes.
    Calendar retention covers this handler's dated files and legacy rotated logs.
    """

    terminator = "\n"

    def __init__(self, filename, retention_days=7, encoding="utf-8"):
        super().__init__()
        if (not isinstance(retention_days, int) or isinstance(retention_days, bool)
                or retention_days < 1):
            raise ValueError("retention_days must be a positive integer")
        self.base_path = Path(filename).resolve()
        self.retention_days = retention_days
        self.lock_path = self.base_path.with_name(f"{self.base_path.stem}-lock.log")
        self.encoding = encoding
        self._retention_date = None
        self._write_failed = False
        stem = re.escape(self.base_path.stem)
        name = re.escape(self.base_path.name)
        self._dated_pattern = re.compile(
            rf"^(?:{stem}-(\d{{4}}-\d{{2}}-\d{{2}})\.log|"
            rf"{name}\.(\d{{4}}-\d{{2}}-\d{{2}}))$"
        )

    def _today(self):
        return datetime.now(timezone.utc).date()

    @contextmanager
    def _append_lock(self):
        # Keep one stable lock inode; deleting/replacing it would split writers.
        with self.lock_path.open("a+b") as stream:
            if stream.seek(0, os.SEEK_END) == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                acquire = lambda: msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                release = lambda: msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                acquire = lambda: fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                release = lambda: fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            deadline = time.monotonic() + 10
            while True:
                try:
                    acquire()
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.01)
            try:
                yield
            finally:
                release()

    def _prune(self, today):
        cutoff = today - timedelta(days=self.retention_days - 1)
        try:
            entries = list(self.base_path.parent.iterdir())
        except OSError:
            return
        for entry in entries:
            match = self._dated_pattern.fullmatch(entry.name)
            if not match or entry.is_symlink():
                continue
            try:
                file_date = datetime.strptime(next(value for value in match.groups() if value), "%Y-%m-%d").date()
                if file_date < cutoff and entry.is_file():
                    entry.unlink()
            except (OSError, ValueError):
                # Another process may have removed it, or an external tool may
                # still hold a legacy file. Retry on the next calendar day.
                continue

    def emit(self, record):
        try:
            today = self._today()
            message = self.format(record) + self.terminator
            with self._append_lock():
                if self._retention_date != today:
                    self._retention_date = today
                    self._prune(today)
                daily_path = self.base_path.with_name(f"{self.base_path.stem}-{today}.log")
                with daily_path.open("a", encoding=self.encoding) as stream:
                    stream.write(message)
            self._write_failed = False
        except Exception:
            # Console handlers still receive the original record. A file failure
            # must not dump its message, traceback or possible credentials again.
            if not self._write_failed:
                self._write_failed = True
                try:
                    sys.stderr.write("Log file write failed; console logging remains available.\n")
                except Exception:
                    pass


file_fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
date_fmt = "%Y-%m-%d %H:%M:%S"
