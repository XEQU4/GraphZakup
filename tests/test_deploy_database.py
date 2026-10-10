"""Offline recovery guards, corruption detection and no-overwrite behaviour."""

import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from scripts.backup_database import BackupError, file_checksum
from scripts.database_manifest import canonical_index_definition
from scripts.deploy_database import (
    Compose, backup, load_verified_dump, parse_compose_ps, require_empty,
    require_same, restore, validate_manifest, validate_project,
)


def manifest(populated=False):
    return {
        "manifest_version": 1, "postgres_major": 17,
        "hash_scheme": "sha256-sorted-row-json-sha256-v1",
        "tables": {"public.example": {"count": 2, "sha256": "abc"}} if populated else {},
        "structure": {
            "schemas": [["public"]], "relations": [["public", "example", "r"]] if populated else [],
            "routines": [], "extensions": [["plpgsql", "1.0"]],
            "defaults": [], "indexes": [], "constraints": [], "sequences": {},
        },
    }


class DeploymentRecoveryTests(unittest.TestCase):
    def test_pg_restore_equivalent_literal_array_cast_has_one_fingerprint(self):
        original = "WHERE ((status)::text = ANY ((ARRAY['pending'::character varying, 'running'::character varying])::text[]))"
        restored = "WHERE ((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('running'::character varying)::text]))"
        self.assertEqual(canonical_index_definition(original), canonical_index_definition(restored))
        self.assertNotEqual(canonical_index_definition(original),
                            canonical_index_definition(restored.replace("running", "finished")))
        bounded = "ARRAY[('abcdef'::character varying(3))::text]"
        self.assertEqual(canonical_index_definition(bounded), bounded)
        value = "ANY ((ARRAY['value::character varying'::character varying])::text[])"
        self.assertEqual(canonical_index_definition(value), "ANY (ARRAY['value::character varying'::text])")
        value = "ANY ((ARRAY['(ARRAY[''x''::character varying])::text[]'::character varying])::text[])"
        self.assertEqual(canonical_index_definition(value),
                         "ANY (ARRAY['(ARRAY[''x''::character varying])::text[]'::text])")

    def test_manifest_rejects_missing_structure_and_old_reports(self):
        for value in ({}, {"tables": {}}, {**manifest(), "manifest_version": 2}):
            with self.subTest(value=value), self.assertRaises(BackupError):
                validate_manifest(value)
        value = manifest()
        del value["structure"]["sequences"]
        with self.assertRaises(BackupError):
            validate_manifest(value)

    def test_empty_database_means_no_schema_objects_not_only_no_rows(self):
        require_empty(manifest())
        for key, value in (
            ("relations", [["public", "existing_view", "v"]]),
            ("sequences", {"public.id_seq": {"state": [1, False]}}),
            ("routines", [["public", "test_function", ""]]),
            ("schemas", [["public"], ["saved_data"]]),
            ("extensions", [["plpgsql", "1.0"], ["pgcrypto", "1.3"]]),
        ):
            candidate = manifest()
            candidate["structure"][key] = value
            with self.subTest(key=key), self.assertRaises(BackupError):
                require_empty(candidate)
        with self.assertRaises(BackupError):
            require_empty(manifest(populated=True))

    def test_damaged_rows_or_indexes_or_sequence_state_fail_verification(self):
        expected = manifest(True)
        expected["structure"]["sequences"] = {"public.example_id_seq": {"state": [3, True]}}
        expected["structure"]["indexes"] = [["public", "example_id", "CREATE UNIQUE INDEX"]]
        expected["structure"]["constraints"] = [["example", "PRIMARY KEY (id)"]]
        for section in ("tables", "sequences", "indexes", "constraints"):
            changed = copy.deepcopy(expected)
            if section == "tables":
                changed["tables"]["public.example"]["sha256"] = "different"
            else:
                changed["structure"][section] = {} if section == "sequences" else []
            with self.subTest(section=section), self.assertRaises(BackupError):
                require_same(expected, changed)

    def test_pg_major_changes_require_separate_migration_rehearsal(self):
        expected, actual = manifest(), manifest()
        actual["postgres_major"] = 18
        with self.assertRaises(BackupError):
            require_same(expected, actual)

    def test_compose_json_and_json_lines_are_supported(self):
        item = {"Service": "db"}
        self.assertEqual(parse_compose_ps(json.dumps([item])), [item])
        self.assertEqual(parse_compose_ps(json.dumps(item)), [item])
        self.assertEqual(parse_compose_ps(json.dumps(item) + "\n" + json.dumps(item)), [item, item])

    def test_recovery_refuses_running_application_but_does_not_stop_it(self):
        compose = Compose(Path("private.env"), "iz2_rehearsal", [Path("docker-compose.yml")])
        for role in ("web", "worker", "ai-worker", "beat", "migrate"):
            with patch.object(compose, "run", return_value=json.dumps([
                {"Service": "db", "State": "running"}, {"Service": role, "State": "running"},
            ]).encode()) as run:
                with self.subTest(role=role), self.assertRaises(BackupError):
                    compose.quiet()
                run.assert_called_once_with(["ps", "--all", "--format", "json"])
        with patch.object(compose, "run", return_value=b'[{"Service":"db","State":"running"},{"Service":"redis","State":"running"}]'):
            compose.quiet()

    def test_paused_or_restarting_workloads_are_not_quiet(self):
        compose = Compose(Path("private.env"), "iz2_rehearsal", [Path("docker-compose.yml")])
        for state in ("paused", "restarting", "created", "unknown"):
            with patch.object(compose, "run", return_value=json.dumps([
                {"Service": "db", "State": "running"}, {"Service": "worker", "State": state},
            ]).encode()):
                with self.subTest(state=state), self.assertRaises(BackupError):
                    compose.quiet()
        with patch.object(compose, "run", return_value=json.dumps([
            {"Service": "db", "State": "running"}, {"Service": "worker", "State": "exited"},
        ]).encode()):
            compose.quiet()

    def test_project_name_is_explicit_and_cannot_inject_options(self):
        self.assertEqual(validate_project("iz2_recovery_123"), "iz2_recovery_123")
        for value in ("", "--project=other", "x;whoami", "../iz2", "IZ2"):
            with self.subTest(value=value), self.assertRaises(BackupError):
                validate_project(value)

    def test_compose_profiles_and_optional_external_override_are_preserved(self):
        compose = Compose(Path("private.env"), "iz2_rehearsal",
                          [Path("docker-compose.yml"), Path("artifacts/custom-compose.yml")],
                          ["local-ai", "extra"])
        with patch("scripts.deploy_database.subprocess.run", return_value=SimpleNamespace(
            returncode=0, stdout=b"[]", stderr=b"",
        )) as run:
            compose.run(["ps", "--all", "--format", "json"])
        command = run.call_args.args[0]
        self.assertEqual(command.count("--file"), 2)
        self.assertIn(str(Path("artifacts/custom-compose.yml").resolve()), command)
        self.assertEqual(command[-8:], ["--profile", "local-ai", "--profile", "extra",
                                       "ps", "--all", "--format", "json"])

    def test_metadata_probe_reuses_migrate_image_without_migrations_or_dependencies(self):
        compose = Compose(Path("private.env"), "iz2_rehearsal", [Path("docker-compose.yml")],
                          ["local-ai"])
        with patch.object(compose, "run", return_value=json.dumps(manifest()).encode()) as run:
            self.assertEqual(compose.manifest(), manifest())
        run.assert_called_once_with([
            "run", "--rm", "--no-deps", "-T", "--entrypoint", "python",
            "migrate", "scripts/database_manifest.py",
        ])

    def test_dump_checksum_and_custom_format_are_required_before_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            dump, report = Path(directory) / "data.dump", Path(directory) / "data.json"
            dump.write_bytes(b"PGDMPexample")
            payload = {"status": "complete", "dump_sha256": file_checksum(dump), "manifest": manifest(True)}
            report.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(load_verified_dump(dump, report), payload["manifest"])
            dump.write_bytes(b"PGDMPdamaged")
            with self.assertRaises(BackupError):
                load_verified_dump(dump, report)
            dump.write_bytes(b"SELECT dangerous_plain_sql;")
            payload["dump_sha256"] = file_checksum(dump)
            report.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(BackupError):
                load_verified_dump(dump, report)

    def test_restore_never_runs_for_existing_database(self):
        compose = MagicMock()
        compose.manifest.return_value = manifest(True)
        with patch("scripts.deploy_database.load_verified_dump", return_value=manifest(True)):
            with self.assertRaises(BackupError):
                restore(compose, Path("data.dump"), Path("data.json"), Path("artifacts/recovery"))
        compose.restore.assert_not_called()

    def test_backup_changed_during_dump_gets_no_success_manifest(self):
        compose = MagicMock()
        before, after = manifest(True), manifest(True)
        after["tables"]["public.example"]["count"] += 1
        compose.manifest.side_effect = [before, after]
        compose.dump.side_effect = lambda path: path.write_bytes(b"PGDMPexample")
        with tempfile.TemporaryDirectory() as directory:
            with patch("scripts.deploy_database.safe_output_directory", return_value=Path(directory)):
                with self.assertRaises(BackupError):
                    backup(compose, Path(directory))
            self.assertEqual(list(Path(directory).glob("*.json")), [])

    def test_restore_command_is_atomic_without_clean_create_or_password_in_argv(self):
        compose = Compose(Path("private.env"), "iz2_rehearsal", [Path("docker-compose.yml")])
        with tempfile.TemporaryDirectory() as directory:
            dump = Path(directory) / "data.dump"
            dump.write_bytes(b"PGDMPexample")
            with patch.object(compose, "run") as run:
                compose.restore(dump)
            args = run.call_args.args[0]
            command = args[-1]
            self.assertIn("--single-transaction", command)
            self.assertIn("--exit-on-error", command)
            self.assertNotIn("--clean", command)
            self.assertNotIn("--create", command)

    def test_errors_never_echo_docker_stderr(self):
        compose = Compose(Path("private.env"), "iz2_rehearsal", [Path("docker-compose.yml")])
        with patch("scripts.deploy_database.subprocess.run", return_value=SimpleNamespace(
            returncode=1, stderr=b"password=secret", stdout=b"",
        )):
            with self.assertRaises(BackupError) as caught:
                compose.run(["ps"])
        self.assertNotIn("secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
