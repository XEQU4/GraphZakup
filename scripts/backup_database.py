"""Consistent PostgreSQL backup with optional isolated local restore verification.

Run from the repository root: python scripts/backup_database.py --verify-restore
Credentials are loaded from .env/environment and never printed or put in argv.
"""

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import heapq
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TEST_PREFIX = "gpg_restore_verify_"
HASH_SCHEME = "sha256-sorted-row-json-sha256-v1"


class BackupError(Exception):
    """An error code safe to include in a public-facing report."""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def database_config(values):
    for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"):
        if values.get(key):
            raise BackupError("unsupported_libpq_routing_environment")
    pairs = {"dbname": ("PGDATABASE", "DB_NAME"),
             "user": ("PGUSER", "DB_USER"), "password": ("PGPASSWORD", "DB_PASSWORD"),
             "host": ("PGHOST", "DB_HOST"), "port": ("PGPORT", "DB_PORT")}
    config = {key: values.get(pg, values.get(db)) for key, (pg, db) in pairs.items()}
    config = {key: value for key, value in config.items() if value is not None}
    config.setdefault("port", "5432")
    if not config.get("dbname"):
        raise BackupError("database_name_missing")
    name = config["dbname"]
    if "=" in name or name.lower().startswith(("postgresql://", "postgres://")):
        raise BackupError("database_name_must_not_be_uri_or_connection_string")
    return config


def safe_output_directory(path, root=ROOT):
    root = Path(root).resolve()
    artifacts = (root / "artifacts").resolve()
    target = Path(path).resolve()
    if not artifacts.is_relative_to(root) or not target.is_relative_to(artifacts):
        raise BackupError("output_directory_must_stay_inside_repository_artifacts")
    return target


def local_host(host):
    if not host or host.lower() == "localhost" or host.startswith("/"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_test_database(name, source_name, generated_name, created):
    if (not created or name != generated_name or name == source_name
            or not re.fullmatch(TEST_PREFIX + r"[0-9a-f]{32}", name)):
        raise BackupError("unsafe_test_database_target")


def process_config(config, database=None):
    # Remove inherited libpq routing/options so subprocesses use precisely this server.
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    env["PGCONNECT_TIMEOUT"] = "10"
    if "password" in config:
        env["PGPASSWORD"] = config["password"]
    args = ["--no-password", "--dbname", database or config["dbname"]]
    for key, flag in (("host", "--host"), ("port", "--port"), ("user", "--username")):
        if config.get(key):
            args.extend([flag, str(config[key])])
    return args, env


def run_tool(command, env, operation):
    result = subprocess.run(command, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            check=False)
    if result.returncode:
        # stderr may contain server/role/credentials; retain only the exit status.
        raise BackupError(f"{operation}_exit_{result.returncode}")


def tool_major(executable):
    result = subprocess.run([str(executable), "--version"], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            check=False)
    match = re.search(rb"PostgreSQL\)\s+(\d+)", result.stdout)
    return int(match.group(1)) if result.returncode == 0 and match else None


def find_tools(server_major, explicit=None):
    candidates = []
    if explicit:
        candidates.append(Path(explicit).resolve())
    else:
        base = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "PostgreSQL"
        if base.is_dir():
            directories = [p for p in base.iterdir() if p.is_dir() and p.name.isdigit()]
            directories.sort(key=lambda p: (int(p.name) != server_major, -int(p.name)))
            candidates.extend(p / "bin" for p in directories)
        located = shutil.which("pg_dump")
        if located:
            candidates.append(Path(located).resolve().parent)
    suffix = ".exe" if os.name == "nt" else ""
    for directory in candidates:
        dump, restore = (directory / (name + suffix) for name in ("pg_dump", "pg_restore"))
        if dump.is_file() and restore.is_file():
            major = tool_major(dump)
            if major and major >= server_major and tool_major(restore) == major:
                return dump, restore, major
    raise BackupError("compatible_pg_dump_and_pg_restore_not_found")


def checksum_rows(rows, temp_parent, batch_size=100000):
    """Bounded-memory multiset hash: duplicate rows retain their multiplicity."""
    total, batch, parts = 0, [], []
    digest = hashlib.sha256(HASH_SCHEME.encode("ascii") + b"\0")
    with tempfile.TemporaryDirectory(prefix="row-hashes-", dir=temp_parent) as directory:
        directory = Path(directory).resolve()
        if directory.parent != Path(temp_parent).resolve():
            raise BackupError("unsafe_hash_temporary_directory")
        for row in rows:
            batch.append(hashlib.sha256(row.encode("utf-8")).digest())
            total += 1
            if len(batch) >= batch_size:
                part = directory / str(len(parts))
                part.write_bytes(b"".join(sorted(batch)))
                parts.append(part)
                batch.clear()
        if not parts:
            for value in sorted(batch):
                digest.update(value)
        else:
            if batch:
                part = directory / str(len(parts))
                part.write_bytes(b"".join(sorted(batch)))
                parts.append(part)
            with ExitStack() as stack:
                streams = [stack.enter_context(p.open("rb")) for p in parts]
                values = [iter(lambda stream=stream: stream.read(32), b"") for stream in streams]
                for value in heapq.merge(*values):
                    digest.update(value)
    return {"count": total, "sha256": digest.hexdigest()}


def configure_snapshot(connection):
    connection.set_session(isolation_level="REPEATABLE READ", readonly=True, autocommit=False)
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL TIME ZONE 'UTC'")
        cursor.execute("SET LOCAL DateStyle = 'ISO, YMD'")
        cursor.execute("SET LOCAL extra_float_digits = 3")
        cursor.execute("SET LOCAL bytea_output = 'hex'")


def table_metadata(connection, output_dir, sql):
    with connection.cursor() as cursor:
        cursor.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n "
                       "ON n.oid=c.relnamespace WHERE n.nspname='public' "
                       "AND c.relkind IN ('r','p') ORDER BY c.relname")
        tables = [row[0] for row in cursor.fetchall()]
    metadata = {}
    for table in tables:
        with connection.cursor() as cursor:
            cursor.execute("SELECT a.attname, format_type(a.atttypid,a.atttypmod), "
                           "a.attnotnull, a.attidentity, a.attgenerated FROM pg_attribute a "
                           "JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n "
                           "ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname=%s "
                           "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum", (table,))
            columns = [{"name": name, "type": kind, "not_null": nullable,
                        "identity": identity, "generated": generated}
                       for name, kind, nullable, identity, generated in cursor.fetchall()]
        with connection.cursor(name="backup_" + uuid.uuid4().hex) as cursor:
            cursor.itersize = 5000
            cursor.execute(sql.SQL("SELECT row_to_json(t)::text FROM ONLY {} AS t")
                           .format(sql.Identifier("public", table)))
            info = checksum_rows((row[0] for row in cursor), output_dir)
        metadata["public." + table] = {**info, "columns": columns}
    return metadata


def compare_metadata(expected, actual):
    return {name: {"source": expected.get(name), "restored": actual.get(name)}
            for name in sorted(expected.keys() | actual.keys())
            if expected.get(name) != actual.get(name)}


def verify_restore(config, restore_tool, dump_path, expected, output_dir, sql, connect, result,
                   expected_structure=None):
    if not local_host(config.get("host", "")):
        raise BackupError("restore_verification_requires_local_server")
    name = TEST_PREFIX + uuid.uuid4().hex
    result.update({"status": "pending", "test_database": name, "created": False,
                   "cleanup": "not_needed"})
    maintenance = connect(**{**config, "dbname": "postgres", "connect_timeout": 10})
    maintenance.autocommit = True
    try:
        with maintenance.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0")
                           .format(sql.Identifier(name)))
        result["created"] = True
        validate_test_database(name, config["dbname"], name, result["created"])
        args, env = process_config(config, name)
        run_tool([str(restore_tool), "--exit-on-error", "--no-owner", "--no-privileges",
                  *args, str(dump_path)], env, "pg_restore")
        restored = connect(**{**config, "dbname": name, "connect_timeout": 10})
        try:
            configure_snapshot(restored)
            actual = table_metadata(restored, output_dir, sql)
            if expected_structure is not None:
                from scripts.database_manifest import structure_metadata
                actual_structure = structure_metadata(restored, sql)
        finally:
            restored.rollback()
            restored.close()
        differences = compare_metadata(expected, actual)
        result.update({"status": "failed" if differences else "passed",
                       "differences": differences, "tables_verified": len(actual),
                       "django_migrations_verified": "public.django_migrations" in expected
                       and expected["public.django_migrations"] == actual.get("public.django_migrations")})
        if differences:
            raise BackupError("restored_table_metadata_mismatch")
        if expected_structure is not None:
            result["structure_and_sequences_verified"] = expected_structure == actual_structure
            if not result["structure_and_sequences_verified"]:
                result["status"] = "failed"
                result["structure_differences"] = compare_metadata(expected_structure, actual_structure)
                raise BackupError("restored_structure_metadata_mismatch")
    finally:
        try:
            if result["created"]:
                validate_test_database(name, config["dbname"], name, result["created"])
                with maintenance.cursor() as cursor:
                    cursor.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
                    cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,))
                    if cursor.fetchone() is not None:
                        raise BackupError("temporary_database_still_exists")
                result["cleanup"] = "dropped"
                result["absence_verified"] = True
        except Exception as error:
            result["cleanup"] = "failed"
            result["cleanup_error_type"] = type(error).__name__
        finally:
            maintenance.close()
        if result["cleanup"] == "failed":
            raise BackupError("temporary_database_cleanup_failed")


def file_checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts" / "phase0")
    parser.add_argument("--pg-bin", type=Path, help="Directory containing pg_dump and pg_restore")
    parser.add_argument("--verify-restore", action="store_true")
    parser.add_argument("--deployment-manifest", action="store_true",
                        help="Also verify schema/sequence state and write a Compose transfer manifest; stop writers first")
    options = parser.parse_args(argv)
    try:
        output_dir = safe_output_directory(options.output_dir)
    except BackupError as error:
        print(json.dumps({"status": "failed", "error": {"code": str(error)}}))
        return 1
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    dump_path = output_dir / ("database_" + stamp + ".dump")
    report_path = output_dir / ("database_" + stamp + ".json")
    report = {"started_at": utc_now(), "status": "pending", "hash_scheme": HASH_SCHEME,
              "verification_scope": "public tables, columns, row counts and row hashes; includes django_migrations",
              "dump_path": str(dump_path), "verification": {"status": "not_requested"}}
    connection = None
    try:
        from dotenv import dotenv_values
        import psycopg2
        from psycopg2 import sql
        config = database_config({**dotenv_values(ROOT / ".env"), **os.environ})
        report["source_database_name_sha256"] = hashlib.sha256(config["dbname"].encode()).hexdigest()
        connection = psycopg2.connect(**config, connect_timeout=10)
        configure_snapshot(connection)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_export_snapshot(), current_setting('server_version_num')::int")
            snapshot, version = cursor.fetchone()
        server_major = version // 10000
        dump_tool, restore_tool, tool_version = find_tools(server_major, options.pg_bin)
        report.update({"server_version_num": version, "tool_major": tool_version,
                       "tables": table_metadata(connection, output_dir, sql)})
        deployment_manifest = None
        if options.deployment_manifest:
            from scripts.database_manifest import capture, structure_metadata
            from scripts.deploy_database import require_same, write_private
            deployment_manifest = {
                "manifest_version": 1, "hash_scheme": HASH_SCHEME,
                "postgres_major": server_major, "tables": report["tables"],
                "structure": structure_metadata(connection, sql),
            }
            report["verification_scope"] += "; defaults, indexes, constraints and sequence definitions/state"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        args, env = process_config(config)
        run_tool([str(dump_tool), "--format=custom", "--file", str(dump_path),
                  "--snapshot", snapshot, "--lock-wait-timeout=30s", *args], env, "pg_dump")
        connection.rollback()
        connection.close()
        connection = None
        report["dump"] = {"sha256": file_checksum(dump_path), "bytes": dump_path.stat().st_size}
        if deployment_manifest is not None:
            require_same(deployment_manifest, capture(config))
        if options.verify_restore:
            verify_restore(config, restore_tool, dump_path, report["tables"], output_dir,
                           sql, psycopg2.connect, report["verification"],
                           expected_structure=deployment_manifest["structure"]
                           if deployment_manifest is not None else None)
        if deployment_manifest is not None:
            transfer_path = dump_path.with_suffix(".deployment.json")
            write_private(transfer_path, {
                "status": "complete", "dump_sha256": report["dump"]["sha256"],
                "manifest": deployment_manifest,
                "restore_verification": report["verification"]["status"],
            })
            report["deployment_manifest_path"] = str(transfer_path)
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = {"code": str(error) if isinstance(error, BackupError) else type(error).__name__}
        if options.verify_restore and report["verification"]["status"] in {"pending", "not_requested"}:
            report["verification"]["status"] = "failed"
    finally:
        if connection is not None:
            try:
                connection.rollback()
                connection.close()
            except Exception:
                pass
        report["finished_at"] = utc_now()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "report_path": str(report_path),
                      "dump_path": str(dump_path), "verification": report["verification"]["status"],
                      "deployment_manifest_path": report.get("deployment_manifest_path"),
                      "error": report.get("error")}, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
