"""Maintain PostgreSQL backups through Docker Compose using host Python only.

Use an explicit --env-file and --project. Stop web, worker, ai-worker and beat
before backup/restore. Restore accepts only an empty database and never drops,
cleans or replaces data. An isolated successful restore is required to certify
a backup. All backup files must stay inside the ignored artifacts/ directory.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.backup_database import BackupError, file_checksum, safe_output_directory  # noqa: E402

MANIFEST_VERSION = 1
QUIET_SERVICES = {"web", "worker", "ai-worker", "beat", "migrate"}


def validate_project(value):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", value):
        raise BackupError("invalid_explicit_project_name")
    return value


def parse_compose_ps(output):
    try:
        value = json.loads(output)
        return value if isinstance(value, list) else [value]
    except json.JSONDecodeError:
        return [json.loads(line) for line in output.splitlines() if line.strip()]


def validate_manifest(value):
    if (value.get("manifest_version") != MANIFEST_VERSION
            or not isinstance(value.get("tables"), dict)
            or not isinstance(value.get("structure"), dict)
            or not isinstance(value.get("postgres_major"), int)
            or value.get("hash_scheme") != "sha256-sorted-row-json-sha256-v1"):
        raise BackupError("invalid_recovery_manifest")
    for key in ("relations", "defaults", "constraints", "indexes", "schemas", "routines", "extensions"):
        if not isinstance(value["structure"].get(key), list):
            raise BackupError("incomplete_recovery_manifest")
    if not isinstance(value["structure"].get("sequences"), dict):
        raise BackupError("incomplete_recovery_manifest")
    return value


def require_empty(value):
    validate_manifest(value)
    structure = value["structure"]
    if (value["tables"] or structure["relations"] or structure["sequences"]
            or structure["routines"] or structure["schemas"] != [["public"]]
            or structure["extensions"] != [["plpgsql", "1.0"]]):
        raise BackupError("restore_requires_empty_database")


def require_same(expected, actual):
    validate_manifest(expected)
    validate_manifest(actual)
    # Role ownership/ACLs are intentionally mapped to the new deployment user.
    for key in ("manifest_version", "hash_scheme", "postgres_major", "tables", "structure"):
        if expected[key] != actual[key]:
            raise BackupError("restored_" + key + "_mismatch")


def load_verified_dump(dump, report):
    value = json.loads(report.read_text(encoding="utf-8"))
    validate_manifest(value.get("manifest", {}))
    if value.get("status") != "complete" or value.get("dump_sha256") != file_checksum(dump):
        raise BackupError("dump_checksum_or_report_mismatch")
    if dump.stat().st_size < 5:
        raise BackupError("invalid_custom_dump")
    with dump.open("rb") as stream:
        if stream.read(5) != b"PGDMP":
            raise BackupError("invalid_custom_dump")
    return value["manifest"]


class Compose:
    def __init__(self, env_file, project, files, profiles=()):
        self.prefix = ["docker", "compose", "--env-file", str(env_file.resolve()),
                       "--project-name", validate_project(project)]
        for path in files:
            self.prefix.extend(["--file", str(path.resolve())])
        for profile in profiles:
            self.prefix.extend(["--profile", profile])
        # Credentials stay in the private env file. Compose honours explicit
        # process overrides; operators must use the same environment as startup.
        self.env = dict(os.environ)

    def run(self, arguments, *, stdin=None, stdout=subprocess.PIPE):
        result = subprocess.run(self.prefix + arguments, cwd=ROOT, env=self.env,
                                stdin=stdin or subprocess.DEVNULL, stdout=stdout,
                                stderr=subprocess.PIPE, check=False)
        if result.returncode:
            # Compose/libpq failures can contain secrets. Never echo stderr.
            raise BackupError("compose_operation_failed_exit_" + str(result.returncode))
        return result.stdout

    def quiet(self):
        output = self.run(["ps", "--all", "--format", "json"])
        containers = parse_compose_ps(output.decode("utf-8")) if output.strip() else []
        if not any(item.get("Service") == "db" and item.get("State") == "running"
                   for item in containers):
            raise BackupError("database_container_must_be_running")
        if any(item.get("Service") in QUIET_SERVICES and item.get("State") not in {"exited", "dead"}
               for item in containers):
            raise BackupError("stop_web_worker_ai_worker_beat_before_recovery")

    def manifest(self):
        # Reuse the backend image/env without the web service's public proxy
        # network or fixed address. --no-deps and the entrypoint override mean
        # this one-off process cannot run migrations or start other services.
        payload = self.run(["run", "--rm", "--no-deps", "-T", "--entrypoint", "python",
                            "migrate", "scripts/database_manifest.py"])
        return validate_manifest(json.loads(payload))

    def dump(self, output):
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            self.run(["exec", "-T", "db", "sh", "-ec",
                      'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump --format=custom '
                      '--no-owner --no-privileges --no-password --lock-wait-timeout=30s '
                      '--username "$POSTGRES_USER" --dbname "$POSTGRES_DB"'], stdout=stream)

    def restore(self, dump):
        with dump.open("rb") as stream:
            self.run(["exec", "-T", "db", "sh", "-ec",
                      'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_restore --single-transaction '
                      '--exit-on-error --no-owner --no-privileges --no-password '
                      '--username "$POSTGRES_USER" --dbname "$POSTGRES_DB"'], stdin=stream)


def write_private(path, payload):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def backup(compose, directory):
    directory = safe_output_directory(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    compose.quiet()
    before = compose.manifest()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    dump = directory / ("database_" + stamp + ".dump")
    report = dump.with_suffix(".json")
    compose.dump(dump)
    if os.name != "nt":
        dump.chmod(0o600)
    require_same(before, compose.manifest())
    write_private(report, {"status": "complete", "dump_sha256": file_checksum(dump),
                           "manifest": before, "restore_verification": "not_yet_performed"})
    return {"status": "passed", "dump": str(dump), "manifest": str(report),
            "restore_verification": "not_yet_performed"}


def restore(compose, dump, report, output_directory):
    expected = load_verified_dump(dump, report)
    compose.quiet()
    empty = compose.manifest()
    require_empty(empty)
    if expected["postgres_major"] != empty["postgres_major"]:
        raise BackupError("postgres_major_must_match_for_verified_transfer")
    compose.restore(dump)
    actual = compose.manifest()
    require_same(expected, actual)
    output_directory = safe_output_directory(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    verification = output_directory / ("restore_" + uuid.uuid4().hex + ".json")
    result = {"status": "passed", "dump_sha256": file_checksum(dump),
              "tables": len(actual["tables"]),
              "rows": sum(item["count"] for item in actual["tables"].values()),
              "sequences": len(actual["structure"]["sequences"]),
              "indexes": len(actual["structure"]["indexes"]),
              "constraints": len(actual["structure"]["constraints"]),
              "data_schema_and_sequence_state_equal": True,
              "ownership_and_privileges": "mapped_to_target_database_user"}
    write_private(verification, result)
    return {**result, "report": str(verification)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("-f", "--file", type=Path, action="append")
    parser.add_argument("--profile", action="append", help="Enabled Compose profile; repeat when needed")
    sub = parser.add_subparsers(dest="action", required=True)
    save = sub.add_parser("backup")
    save.add_argument("--output-dir", type=Path, default=ROOT / "artifacts" / "backups")
    load = sub.add_parser("restore")
    load.add_argument("--dump", type=Path, required=True)
    load.add_argument("--manifest", type=Path, required=True)
    load.add_argument("--output-dir", type=Path, default=ROOT / "artifacts" / "recovery")
    options = parser.parse_args(argv)
    try:
        if not options.env_file.is_file():
            raise BackupError("private_environment_file_missing")
        # Validate every writable destination before touching the target DB.
        safe_output_directory(options.output_dir)
        compose = Compose(options.env_file, options.project,
                          options.file or [ROOT / "docker-compose.yml"], options.profile or [])
        result = backup(compose, options.output_dir) if options.action == "backup" else restore(
            compose, options.dump, options.manifest, options.output_dir)
        print(json.dumps(result))
        return 0
    except Exception as error:
        print(json.dumps({"status": "failed", "code": str(error)
                          if isinstance(error, BackupError) else type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
