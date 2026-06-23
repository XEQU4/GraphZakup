import logging

from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_old_logs_by_filename(logs_dir="logs", days=30):
    logs_path = Path(logs_dir)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    deleted_files = 0

    for file in logs_path.glob("*.log"):
        try:
            parts = file.name.split("-")
            if len(parts) < 2:
                continue

            date_str = "-".join(parts[1:])[:-4]
            file_date = datetime.strptime(date_str, "%Y-%m-%d")

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
