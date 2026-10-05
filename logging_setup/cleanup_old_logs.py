import logging
import re

from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_old_logs_by_filename(logs_dir="logs", days=30):
    if not isinstance(days, int) or isinstance(days, bool) or days < 0:
        raise ValueError('days must be a non-negative integer')
    logs_path = Path(logs_dir)
    cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days)
    deleted_files = 0
    if not logs_path.exists():
        return 0
    pattern = re.compile(r'^(?:app|error)(?:\.log\.|-)(\d{4}-\d{2}-\d{2})(?:\.log)?$')
    for file in logs_path.iterdir():
        try:
            match = pattern.fullmatch(file.name)
            if not match or file.is_symlink() or not file.is_file():
                continue
            file_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()

            if file_date < cutoff_date:
                file.unlink()
                deleted_files += 1
                logger.info(f"🗑️ The log was deleted: {file.name}")

        except Exception as e:
            logger.warning(f"⚠️ File problem {file.name}: {e}")

    if deleted_files == 0:
        logger.info("ℹ️ There are no old logs to delete.")
    else:
        logger.info(f"✅ Deleted {deleted_files} logs older than {days} days.")
    return deleted_files
