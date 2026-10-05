import logging
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

from logging_setup.cleanup_old_logs import cleanup_old_logs_by_filename
from logging_setup.formats import DatedTimedRotatingFileHandler
from logging_setup import init_logging


class LogRetentionTests(unittest.TestCase):
    def test_container_logging_does_not_open_shared_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'not-created'
            with patch('logging_setup.logging.basicConfig') as configure, \
                    patch('logging_setup.sys.excepthook'), patch('logging_setup.init'):
                init_logging(str(path), to_files=False)
            self.assertFalse(path.exists())
            handlers = configure.call_args.kwargs['handlers']
            self.assertEqual(len(handlers), 2)
            self.assertFalse(any(isinstance(handler, logging.FileHandler) for handler in handlers))
    def test_rotation_keeps_dotted_directory_and_enforces_backup_count(self):
        with tempfile.TemporaryDirectory(suffix='.logs.test') as directory:
            root = Path(directory)
            for day in range(1, 6):
                (root / f'app.log.2020-01-{day:02d}').write_text('old', encoding='utf-8')
            handler = DatedTimedRotatingFileHandler(
                root / 'app.log', when='midnight', backupCount=2, utc=True, encoding='utf-8',
            )
            try:
                handler.emit(logging.makeLogRecord({'msg': 'before rotation', 'levelno': logging.INFO}))
                handler.doRollover()
                self.assertEqual(len(list(root.glob('app.log.*'))), 2)
                self.assertTrue((root / 'app.log').exists())
                self.assertTrue(all(file.parent == root for file in root.iterdir()))
            finally:
                handler.close()

    def test_cleanup_handles_both_formats_and_preserves_active_and_boundary_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            today = datetime.now(timezone.utc).date()
            old = today - timedelta(days=31)
            boundary = today - timedelta(days=30)
            old_names = (f'app-{old}.log', f'error.log.{old}')
            preserved = ('app.log', 'error.log', 'notes-2000-01-01.log', 'app-2026-99-99.log', f'app.log.{boundary}')
            for name in old_names + preserved:
                (root / name).write_text('synthetic log', encoding='utf-8')
            self.assertEqual(cleanup_old_logs_by_filename(root, days=30), 2)
            self.assertTrue(all(not (root / name).exists() for name in old_names))
            self.assertTrue(all((root / name).exists() for name in preserved))

    def test_invalid_retention_cannot_delete_files(self):
        for days in (-1, True, 1.5, '30'):
            with self.subTest(days=days), self.assertRaises(ValueError):
                cleanup_old_logs_by_filename(days=days)
