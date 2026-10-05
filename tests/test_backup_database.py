"""Offline safeguards for backup metadata and verification database isolation."""

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.backup_database import (
    BackupError, TEST_PREFIX, checksum_rows, compare_metadata, database_config,
    local_host, process_config, run_tool, safe_output_directory, validate_test_database,
)


class BackupSafeguardTests(unittest.TestCase):
    def test_hash_ignores_read_order_and_spilling(self):
        rows = ['{"id":1}', '{"id":2}', '{"id":1}', '{"id":3}']
        with tempfile.TemporaryDirectory() as directory:
            expected = checksum_rows(iter(rows), Path(directory), batch_size=100)
            actual = checksum_rows(iter(reversed(rows)), Path(directory), batch_size=2)
        self.assertEqual(expected, actual)

    def test_hash_retains_duplicate_multiplicity_and_detects_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            one = checksum_rows(iter(['{"id":1}']), directory)
            duplicate = checksum_rows(iter(['{"id":1}', '{"id":1}']), directory)
            changed = checksum_rows(iter(['{"id":2}']), directory)
        self.assertNotEqual(one["sha256"], duplicate["sha256"])
        self.assertNotEqual(one["sha256"], changed["sha256"])
        self.assertEqual(duplicate["count"], 2)

    def test_cleanup_accepts_only_exact_created_name(self):
        generated = TEST_PREFIX + "a" * 32
        validate_test_database(generated, "source", generated, True)
        for name, source, token, created in [
            ("source", "source", generated, True),
            (generated, generated, generated, True),
            (TEST_PREFIX + "b" * 32, "source", generated, True),
            (generated, "source", generated, False),
            ("postgres", "source", "postgres", True),
        ]:
            with self.subTest(name=name, created=created), self.assertRaises(BackupError):
                validate_test_database(name, source, token, created)

    def test_pg_environment_has_priority_and_password_is_not_in_argv(self):
        config = database_config({"DB_NAME": "fallback", "PGDATABASE": "chosen",
                                  "DB_PASSWORD": "fallback-secret", "PGPASSWORD": "secret-value"})
        args, env = process_config(config, TEST_PREFIX + "a" * 32)
        self.assertEqual(config["dbname"], "chosen")
        self.assertEqual(env["PGPASSWORD"], "secret-value")
        self.assertNotIn("secret-value", " ".join(args))
        self.assertNotIn("chosen", args)

    def test_restore_rejects_remote_or_multi_host_targets(self):
        for host in ("localhost", "127.0.0.1", "::1", "", "/var/run/postgresql"):
            self.assertTrue(local_host(host))
        for host in ("db.example.com", "10.0.0.1", "localhost,db.example.com"):
            self.assertFalse(local_host(host))

    def test_output_rejects_paths_outside_artifacts_before_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            accepted = root / "artifacts" / "phase0"
            self.assertEqual(safe_output_directory(accepted, root), accepted.resolve())
            self.assertFalse(accepted.exists())
            for rejected in (root, root / "backup", root / "artifacts" / ".." / "elsewhere"):
                with self.subTest(path=rejected), self.assertRaises(BackupError):
                    safe_output_directory(rejected, root)
                self.assertFalse((root / "elsewhere").exists())

    def test_database_name_cannot_expose_uri_or_dsn_credentials_in_argv(self):
        for name in ("postgresql://user:secret@localhost/source",
                     "postgres://user:secret@localhost/source", "dbname=source password=secret"):
            with self.subTest(name=name), self.assertRaises(BackupError):
                database_config({"PGDATABASE": name})

    def test_unsupported_libpq_routing_is_rejected(self):
        for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"):
            with self.subTest(key=key), self.assertRaises(BackupError):
                database_config({"DB_NAME": "source", key: "nonempty"})

    def test_subprocess_error_never_exposes_stderr_credentials(self):
        result = SimpleNamespace(returncode=1, stderr=b"password=secret host=private role=private")
        with patch("scripts.backup_database.subprocess.run", return_value=result):
            with self.assertRaises(BackupError) as caught:
                run_tool(["pg_dump"], {}, "pg_dump")
        self.assertEqual(str(caught.exception), "pg_dump_exit_1")

    def test_metadata_detects_missing_extra_and_changed_tables(self):
        differences = compare_metadata({"a": {"count": 1}, "b": {"count": 0}},
                                       {"a": {"count": 2}, "c": {"count": 0}})
        self.assertEqual(set(differences), {"a", "b", "c"})


if __name__ == "__main__":
    unittest.main()
