# Project baseline before Phase 1

Recorded on 5 October 2026. Phase 0 preserves the application before fixes and records continuation documents. The user runs Git commands; the agent did not commit/push.

Related: [audit](AUDIT.md), [architecture](ARCHITECTURE.md), [roadmap](ROADMAP.md), [recovery](RECOVERY.md).

## Completion status

Phase 0 complete: documents/utilities prepared, restoration and source integrity verified, application/user changes preserved. Product questions remain open; Phase 1 had not begun at this historical checkpoint.

## Preserved user changes

These files already had changes at phase start:

| File | SHA-256 |
| --- | --- |
| `test.py` | `d8e280a3856400f65181224360921c65d16bf22abdb4f02d2e6e58c9253ce061` |
| `pyproject.toml` | `6cf2099096eefcdb2c4c51045df502d5cba1c8f22610f1c57d36c2390c13f035` |
| `uv.lock` | `ee1ece784fb109509c1deb09be5abb6c45fc4c1ae666de558542409eec1fb6bb` |

Phase 0 did not modify these files, apps, migrations, parsers, templates, or working-database configuration. The archive includes their current/uncommitted contents.

## Environment and initial checks

Verified Python 3.13.5, Django 6.0.6, Celery 5.6.3, django-celery-beat 2.9.0, WhiteNoise 6.12.0. Initial sandbox runtime access failure did not mean `.venv` was broken; the interpreter worked with installed-runtime access.

| Check | Result and limits |
| --- | --- |
| Python AST | 99 files; no syntax errors |
| Django system checks | No errors; no database connection |
| Model/migration state | No drift; applied source state not separately checked |
| Application tests | 0; app test files were placeholders |
| Compose configuration | db/redis/web/worker/beat; no build/start |
| Staticfiles | Ordinary `StaticFilesStorage`; old setting ineffective |
| collectstatic without SECRET_KEY | Dry-run passed; no Docker failure established |
| Deployment checks | X-Frame-Options/HTTPS/HSTS/secure-cookie warnings on safe sample configuration; Phase 1 work |

See [AUDIT.md](AUDIT.md) for reproductions. These checks establish neither production readiness nor live HTML correctness.

## Database backup

Preflight confirmed PostgreSQL 17.6, 29 public tables, PostgreSQL 17 tools, and permission for a separate verification DB. No source rows/credentials are published. Original Compose used 16; restoration was verified on 17.6, not 16. Align versions in Phase 1.

Ran `scripts/backup_database.py --pg-bin 'C:/Program Files/PostgreSQL/17/bin' --verify-restore`: passed, no differences, migration log verified, temporary DB dropped. Additional read-only check confirmed temporary DB absence. Source migration plan had no pending migrations at this checkpoint.

| Item | Value |
| --- | --- |
| Dump | `artifacts/phase0/database_20261005T083129Z_919471cd.dump` |
| Report | `artifacts/phase0/database_20261005T083129Z_919471cd.json` |
| Size | 181,714 bytes |
| SHA-256 | `9b73e99cb323a319409861e40fbc77438a8e8f2707ea0e93803b9d166a1f1e0a` |
| Public snapshot | 29 tables, 1,849 rows |
| Restore comparison | Rows/hashes/column characteristics matched |
| Utility safeguards | 10/10 passed |

| Application data | Rows |
| --- | --- |
| Companies | 384 |
| Contracts | 500 |
| Directors/directorships | 384/384 |
| Clusters/memberships | 4/11 |
| Connection | 0 |
| Owners/ownerships | 0/0 |
| Tax debts/bankruptcies/court cases | 0 |

Empty tables mean missing observations, not confirmed absence of conditions. Source unchanged. Full index/default/constraint definitions, sequences, ownership, ACL were not individually compared; see [RECOVERY.md](RECOVERY.md).

## Source archive

`scripts/capture_baseline.py` saves application/current user changes/Phase 0 documents in ZIP, with per-file SHA-256, environment versions, and offline Django checks in JSON. No database connection/Git commands. Excludes `.env`, `.git`, virtual environments, logs, dumps, artifacts: an application snapshot, not a whole-computer archive.

```powershell
.\.venv\Scripts\python.exe -B scripts/capture_baseline.py --label 2026-10-05
```

Created 135 files; CRC and all file hashes matched. Final copy: `artifacts/phase0/source-2026-10-05-*.zip`, matching JSON. Choose latest by `captured_at_utc`, checking status/archive hash/manifest rather than filename alone.

| Final Phase 0 check | Result |
| --- | --- |
| Syntax | 103 Python files, no errors |
| Database-free Django checks | No errors |
| Migration drift | None |
| Tests | 10 backup tests discovered/passed; application tests still needed |
| User files | Three hashes unchanged |
| Documentation links | Local targets exist |
| Exclusions | Artifacts excluded from Git/Docker; `.env`/runtime directories excluded from archive |

Manifest reflects capture time. Later documentation changes require recapture to preserve that state. Phase 0 did not fix staticfiles/application defects.

## Scope and open questions

[ARCHITECTURE.md](ARCHITECTURE.md) proposes thesis scope/scenarios. Analyst audience, deadline, budgets are unconfirmed; these affect priorities but not preservation. Explicit user requirement: substantial graph appearance/interaction improvement in Phase 4; overall UI/UX follows later references, with no final style yet approved.

## Next work and Git

After acceptance, Phase 1 follows [ROADMAP.md](ROADMAP.md). DRF/React/new graph algorithms are outside Phase 0. User reviews/records changes. Phase 0 paths include `AGENTS.md`, `README.md`, `.gitignore`, `.dockerignore`, `docs/`, `scripts/`, `tests/`. Existing changes in `test.py`, `pyproject.toml`, `uv.lock` must not accidentally enter a separate Phase 0 commit.
