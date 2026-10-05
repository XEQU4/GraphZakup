"""Capture source files and offline Django checks without accessing the database."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
from datetime import datetime, timezone
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORIES = ("apps", "config", "logging_setup", "static", "templates", "docs", "scripts", "tests")
SOURCE_FILES = ("AGENTS.md", "README.md", "DEPLOY.md", "Dockerfile", "docker-compose.yml", "pyproject.toml", "uv.lock", "manage.py", "test.py", ".env.example", ".gitignore", ".dockerignore")
EXCLUDED_DIRECTORIES = {"__pycache__", "node_modules", ".venv", ".git"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".pyd", ".dump", ".backup", ".log", ".pem", ".key"}


def source_paths() -> list[Path]:
    files = {ROOT / name for name in SOURCE_FILES if (ROOT / name).is_file()}
    for directory in SOURCE_DIRECTORIES:
        base = ROOT / directory
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
                continue
            if path.name.startswith(".env") or path.suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            files.add(path)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def sha256(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def checks(paths: list[Path]) -> dict:
    errors = []
    python_paths = [path for path in paths if path.suffix == ".py"]
    for path in python_paths:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeError) as exc:
            errors.append({"file": path.relative_to(ROOT).as_posix(), "line": getattr(exc, "lineno", None), "type": type(exc).__name__})
    result = {"syntax": {"files": len(python_paths), "errors": errors}, "database_access": False}
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    # AppConfig.ready() normally creates log files. Keep baseline checks read-only.
    with patch("logging_setup.init_logging"):
        import django
        django.setup()
    from django.apps import apps
    from django.conf import settings
    from django.core.checks import run_checks
    from django.db.migrations.autodetector import MigrationAutodetector
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
    from django.db.migrations.state import ProjectState
    from django.test.runner import DiscoverRunner

    system_checks = run_checks(databases=[])
    result["django_checks"] = [{"id": item.id, "level": item.level, "message": item.msg} for item in system_checks]
    loader = MigrationLoader(None, ignore_no_migrations=True)
    changes = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(apps), NonInteractiveMigrationQuestioner()).changes(graph=loader.graph)
    result["model_migration_drift"] = {app: [migration.name for migration in migrations] for app, migrations in changes.items()}
    result["discovered_tests"] = DiscoverRunner(verbosity=0).build_suite([]).countTestCases()
    result["staticfiles_backend"] = settings.STORAGES["staticfiles"]["BACKEND"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="artifacts/phase0")
    parser.add_argument("--label", default=datetime.now(timezone.utc).date().isoformat(), help="Project date label; execution timestamp remains UTC.")
    args = parser.parse_args()
    if not all(char.isalnum() or char in "-_" for char in args.label):
        parser.error("label may contain letters, digits, hyphens and underscores")
    destination = (ROOT / args.output_dir).resolve()
    if not destination.is_relative_to(ROOT / "artifacts"):
        parser.error("output-dir must be inside the ignored artifacts directory")
    destination.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc)
    stem = "source-" + args.label + "-" + timestamp.strftime("%H%M%S%f")
    archive = destination / (stem + ".zip")
    report_path = destination / (stem + ".json")
    paths = source_paths()
    manifest = {path.relative_to(ROOT).as_posix(): {"sha256": sha256(path), "bytes": path.stat().st_size} for path in paths}
    versions = {}
    for package in ("Django", "celery", "django-celery-beat", "whitenoise", "psycopg2-binary", "redis", "requests", "pydantic"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    report = {"project_date_label": args.label, "captured_at_utc": timestamp.isoformat(), "python": platform.python_version(), "packages": versions, "files": manifest, "source_archive": archive.name, "limitations": ["No Git commands executed.", "No database migration status or production data checked.", "No live parser, Celery, LLM, Docker startup or load test performed.", "Archive excludes .env, Git metadata, environments and runtime data."]}
    try:
        os.chdir(ROOT)
        sys.path.insert(0, str(ROOT))
        report["checks"] = checks(paths)
        report["status"] = "passed" if not report["checks"]["syntax"]["errors"] and not report["checks"]["model_migration_drift"] and not any(item["level"] >= 40 for item in report["checks"]["django_checks"]) else "failed"
    except Exception as exc:
        # Exception text can include connection parameters. Keep a safe failure type.
        report["status"] = "failed"
        report["check_error_type"] = type(exc).__name__
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in paths:
            bundle.write(path, arcname=path.relative_to(ROOT).as_posix())
    changed = [name for name, entry in manifest.items() if sha256(ROOT / name) != entry["sha256"]]
    report["files_changed_during_capture"] = changed
    if changed:
        report["status"] = "failed"
    report["archive_sha256"] = sha256(archive)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "archive": str(archive.relative_to(ROOT)), "report": str(report_path.relative_to(ROOT)), "files": len(paths), "checks": report.get("checks", {}), "check_error_type": report.get("check_error_type")}, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
