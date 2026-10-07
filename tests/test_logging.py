import logging
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from logging_setup.cleanup_old_logs import cleanup_old_logs_by_filename
from logging_setup.formats import DailyFileHandler
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
    def test_real_django_startup_splits_file_levels_and_preserves_console_colours(self):
        worker = r'''
import logging
import sys
sys.path.insert(0, sys.argv[1])
from django.conf import settings
settings.configure(
    INSTALLED_APPS=['apps.core.apps.CoreConfig'], LOGGING_CONFIG=None,
    GPG_DISABLE_LOGGING_INIT=False, GPG_LOG_TO_FILES=True,
    SECRET_KEY='isolated-logging-startup',
    DATABASES={'default': {'ENGINE': 'django.db.backends.dummy'}},
)
import django
django.setup()
logging.getLogger('integration').info('synthetic-app-record')
logging.getLogger('integration').warning('synthetic-warning-record')
logging.getLogger('integration').error('synthetic-error-record')
logging.shutdown()
'''
        with tempfile.TemporaryDirectory() as directory:
            today = datetime.now(timezone.utc).date()
            root = Path(directory) / 'logs'
            root.mkdir()
            app_expired = root / f'app-{today - timedelta(days=7)}.log'
            error_retained = root / f'error-{today - timedelta(days=13)}.log'
            error_expired = root / f'error-{today - timedelta(days=14)}.log'
            for file in (app_expired, error_retained, error_expired):
                file.write_text('synthetic history', encoding='utf-8')
            completed = subprocess.run(
                [sys.executable, '-c', worker, str(Path(__file__).resolve().parents[1])],
                cwd=directory, capture_output=True, text=True,
                timeout=20,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('synthetic-app-record', completed.stdout)
            self.assertIn('synthetic-warning-record', completed.stdout)
            self.assertNotIn('synthetic-error-record', completed.stdout)
            self.assertIn('synthetic-error-record', completed.stderr)
            self.assertNotIn('synthetic-app-record', completed.stderr)
            # ColorFormatter itself remains coloured; colorama may strip ANSI
            # in the child process because its stdout/stderr are redirected.
            from logging_setup.formats import ColorFormatter
            self.assertIn('\x1b[', ColorFormatter().format(logging.makeLogRecord({'msg': 'coloured', 'levelno': logging.INFO})))
            app_log = (root / f'app-{today}.log').read_text(encoding='utf-8')
            error_log = (root / f'error-{today}.log').read_text(encoding='utf-8')
            self.assertIn('synthetic-app-record', app_log)
            self.assertIn('synthetic-warning-record', app_log)
            self.assertNotIn('synthetic-error-record', app_log)
            self.assertIn('synthetic-error-record', error_log)
            self.assertNotIn('synthetic-app-record', error_log)
            self.assertNotIn('\x1b[', app_log + error_log)
            self.assertFalse(app_expired.exists())
            self.assertFalse(error_expired.exists())
            self.assertTrue(error_retained.exists())

    def test_daily_retention_covers_legacy_files_in_dotted_directory(self):
        with tempfile.TemporaryDirectory(suffix='.logs.test') as directory:
            root = Path(directory)
            today = date(2026, 10, 7)
            preserved = ('app-2026-10-06.log', 'error-2026-01-01.log', 'app.log', 'notes-2020-01-01.log')
            expired = ('app-2026-10-05.log', 'app.log.2020-01-01')
            for name in preserved + expired:
                (root / name).write_text('synthetic log', encoding='utf-8')
            handler = DailyFileHandler(root / 'app.log', retention_days=2)
            try:
                with patch.object(handler, '_today', return_value=today):
                    handler.handle(logging.makeLogRecord({'msg': 'retained', 'levelno': logging.INFO}))
                self.assertTrue(all((root / name).exists() for name in preserved))
                self.assertTrue(all(not (root / name).exists() for name in expired))
                self.assertEqual((root / 'app-2026-10-07.log').read_text(encoding='utf-8'), 'retained\n')
                self.assertTrue(all(file.parent == root for file in root.iterdir()))
            finally:
                handler.close()

    def test_midnight_switch_has_no_rename_or_open_handle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            handler = DailyFileHandler(root / 'app.log')
            try:
                with patch.object(handler, '_today', return_value=date(2026, 10, 6)):
                    handler.handle(logging.makeLogRecord({'msg': 'before midnight', 'levelno': logging.INFO}))
                # A live handler must not lock its output, even on Windows.
                previous = root / 'app-2026-10-06.log'
                moved = root / 'closed-handle.log'
                previous.rename(moved)
                moved.rename(previous)
                with patch.object(handler, '_today', return_value=date(2026, 10, 7)):
                    handler.handle(logging.makeLogRecord({'msg': 'after midnight', 'levelno': logging.INFO}))
                self.assertEqual(previous.read_text(encoding='utf-8'), 'before midnight\n')
                self.assertEqual((root / 'app-2026-10-07.log').read_text(encoding='utf-8'), 'after midnight\n')
            finally:
                handler.close()

    def test_locked_legacy_file_does_not_drop_current_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app.log.2020-01-01').write_text('old', encoding='utf-8')
            handler = DailyFileHandler(root / 'app.log')
            try:
                with patch.object(handler, '_today', return_value=date(2026, 10, 7)), \
                        patch('logging_setup.formats.Path.unlink', side_effect=PermissionError('locked')), \
                        patch('logging_setup.formats.sys.stderr') as stderr:
                    handler.handle(logging.makeLogRecord({'msg': 'current record', 'levelno': logging.INFO}))
                self.assertEqual((root / 'app-2026-10-07.log').read_text(encoding='utf-8'), 'current record\n')
                self.assertTrue((root / 'app.log.2020-01-01').exists())
                stderr.write.assert_not_called()
            finally:
                handler.close()

    def test_file_failure_notice_does_not_repeat_private_record_or_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            handler = DailyFileHandler(Path(directory) / 'app.log')
            try:
                record = logging.makeLogRecord({'msg': 'private test message', 'levelno': logging.ERROR})
                with patch('logging_setup.formats.Path.open', side_effect=OSError('private failure detail')), \
                        patch('logging_setup.formats.sys.stderr') as stderr:
                    handler.handle(record)
                    handler.handle(record)
                stderr.write.assert_called_once_with('Log file write failed; console logging remains available.\n')
            finally:
                handler.close()

    def test_two_processes_append_all_records_across_utc_midnight(self):
        worker = r'''
import logging
import sys
import time
from datetime import date
from pathlib import Path
from logging_setup.formats import DailyFileHandler
handler = DailyFileHandler(Path(sys.argv[1]) / 'error.log', retention_days=2)
print('ready', flush=True)
if sys.stdin.readline().strip() != 'start':
    raise SystemExit('missing test start')
for day in ('2026-10-06', '2026-10-07'):
    handler._today = lambda day=day: date.fromisoformat(day)
    for number in range(100):
        message = f'{sys.argv[2]}:{day}:{number}:' + 'x' * 2000
        handler.handle(logging.makeLogRecord({'msg': message, 'levelno': logging.ERROR}))
        time.sleep(0.001)
handler.close()
print('done', flush=True)
'''
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(__file__).resolve().parents[1]
            processes = [subprocess.Popen(
                [sys.executable, '-c', worker, directory, str(worker_id)],
                cwd=project_root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            ) for worker_id in range(2)]
            try:
                for process in processes:
                    self.assertEqual(process.stdout.readline().strip(), 'ready')
                for process in processes:
                    process.stdin.write('start\n')
                    process.stdin.flush()
                for process in processes:
                    output, errors = process.communicate(timeout=20)
                    self.assertEqual(process.returncode, 0, errors)
                    self.assertEqual(errors, '')
                    self.assertEqual(output.strip(), 'done')
                for day in ('2026-10-06', '2026-10-07'):
                    lines = (Path(directory) / f'error-{day}.log').read_text(encoding='utf-8').splitlines()
                    expected = {
                        f'{worker_id}:{day}:{number}:' + 'x' * 2000
                        for worker_id in range(2) for number in range(100)
                    }
                    self.assertEqual(len(lines), 200)
                    self.assertEqual(set(lines), expected)
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.terminate()  # Only a subprocess owned by this isolated test.
                    process.wait(timeout=5)
                    for stream in (process.stdin, process.stdout, process.stderr):
                        stream.close()

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

    def test_invalid_daily_retention_is_rejected(self):
        for days in (-1, 0, True, 1.5, '7'):
            with self.subTest(days=days), self.assertRaises(ValueError):
                DailyFileHandler('app.log', retention_days=days)
