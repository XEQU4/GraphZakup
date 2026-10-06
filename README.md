# GrafZakup

GrafZakup is a thesis project for analysing company relationships in Kazakhstan's public procurement. It collects contract and company information, shows matching attributes, and explains the grounds for further review by an analyst.

The current version is a Django prototype with PostgreSQL, Celery, Redis, HTML templates and D3.js. KGD adapters and retained company checks are implemented: authorised taxpayer and complete zero-arrears responses are verified for one company, with saved-result reuse. Broader entitlement and source variants remain unverified. Migration to DRF and React, saved analysis versions and interface improvements are planned in phases. Observed matches and the current heuristic score do not establish a violation.

English is the primary language for project documentation, code comments, interfaces and generated explanations. Russian website localisation will be added later, after the English version is complete. Source data and the labels used to parse official websites retain their original language.

## Project documentation

| Document | Contents |
| --- | --- |
| [Audit](docs/AUDIT.md) | Confirmed defects, data-quality risks and verification limits |
| [Phased roadmap](docs/ROADMAP.md) | Scope, dependencies and acceptance criteria |
| [Architecture](docs/ARCHITECTURE.md) | Current implementation and proposed designs |
| [Baseline](docs/BASELINE.md) | Phase 0 results and reproducible checks |
| [Backup and recovery](docs/RECOVERY.md) | Database export, restoration checks and local artifacts |
| [Phase 1 results](docs/PHASE1.md) | Fixes, verification and remaining limitations |
| [Phase 2 results](docs/PHASE2.md) | Unified ingestion, provenance, role history and migration checks |
| [Phase 3 implementation](docs/PHASE3.md) | KGD adapters, verified registration/zero-arrears checks, saved results and scope limits |
| [English project baseline](docs/LANGUAGE.md) | Language rules, translated deliverables and offline verification |
| [Deployment and updates](DEPLOY.md) | Docker Compose, environment variables and health checks |
| [Codex instructions](AGENTS.md) | Workflow, data preservation and verification rules |

## Run with Docker

Docker Desktop with Linux containers and Docker Compose v2 is required. Preserve any existing `.env` that connects to your local database. For a separate Docker environment, create `.env.docker` from `.env.example`, set a generated `SECRET_KEY` and your own `DB_PASSWORD`:

```powershell
if (-not (Test-Path .env.docker)) { Copy-Item .env.example .env.docker }
python -c "import secrets; print(secrets.token_urlsafe(50))"
docker compose --env-file .env.docker up --build -d --wait
```

Website: http://127.0.0.1:8000/ . The stack starts PostgreSQL 17, Redis, migrations, Gunicorn, a Celery worker and one beat scheduler. Web and worker wait for migrations; dependencies are installed from `uv.lock`, and static assets use manifest WhiteNoise. Database and Redis data are stored in separate volumes. Automatic collection is disabled (`ENABLE_SCHEDULED_IMPORT=false`); an empty database does not populate itself.

Check readiness:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/ready/
docker compose --env-file .env.docker ps -a
```

Startup, shutdown without data loss, HTTPS and migration of an existing database are covered in [DEPLOY.md](DEPLOY.md) and [RECOVERY.md](docs/RECOVERY.md). Do not attach a PostgreSQL 16 volume directly to PostgreSQL 17.

## Local development and verification

The project requires Python 3.13 or later. Dependencies are defined in `pyproject.toml` and `uv.lock`. Set local credentials in `.env`; a real `SECRET_KEY` is required. Before running Django against an existing database, verify its backup, then apply migrations:

```powershell
uv sync --frozen
uv run python manage.py migrate
uv run python manage.py runserver
```

Offline tests use in-memory SQLite and mocked HTTP. They do not load `.env` or connect to the working database, Redis or websites. JavaScript checks use only Node.js standard modules:

```powershell
.\.venv\Scripts\python.exe -B manage.py test --settings=config.test_settings
node tests/frontend_regressions.cjs
.\.venv\Scripts\python.exe -B manage.py makemigrations --check --dry-run --settings=config.test_settings
```

`test.py` contains the user's learning exercises, not application tests. With Phase 3 parser version `3.1`, all 167 tests passed on isolated PostgreSQL; SQLite skips two PostgreSQL concurrency checks. The update protocols and limitations are in [PHASE2.md](docs/PHASE2.md) and [PHASE3.md](docs/PHASE3.md).

To capture source files and check the current environment from PowerShell:

```powershell
.\.venv\Scripts\python.exe -B scripts/capture_baseline.py --label 2026-10-05
```

Follow [docs/RECOVERY.md](docs/RECOVERY.md) for backup and restoration checks. Files under `artifacts/` are excluded from Git and Docker images. They contain project data and are stored locally.

## Working in phases

Phases 0-2 are complete. Parsers are in `apps/ingestion/parsers/`; CLI and Celery use one service. Run status, errors and value provenance are saved in the database. People with matching names become identity candidates; a shared director in the graph requires a confirmed IIN and evidence for each role.

Read saved progress without live requests after applying migrations:

```powershell
uv run python manage.py ingestion_status
```

Intentional collection uses `ingest_data`: `--mode=initial` continues the initial scan, `--mode=update` reads a window of new/updated contracts from the beginning, and `--mode=enrich` refreshes company profiles. `--resume=UUID` continues a saved run from its failed stage. `full` performs upserts without clearing data. These commands contact live sources; modes, limits and field provenance are documented in [PHASE2.md](docs/PHASE2.md). Local updates require the new migrations; the working database was not changed during phase verification.

Phase 3 adds an opt-in `--mode=kgd` for existing companies: taxpayer registration first, optionally aggregate company arrears. The company page only reads stored checks; failed requests retain the last success and never imply zero arrears. Checks default off (`ENABLE_KGD_CHECKS=false`) and are not added to automatic imports or beat schedules. Registration requires a portal token; arrears additionally require an accepted account token. Two authorised requests verified registration and a complete zero-arrears response for one company in an isolated database. Parser `3.1` fixed the returned reporting timestamp format; offline reprocessing preserved original retrieval times and failure history, without another request. The working database was neither migrated nor modified. Phase 3 is complete within this verified scope; access setup, commands and operational limits are in [PHASE3.md](docs/PHASE3.md).

Start the next implementation after verifying the current phase's acceptance criteria. Phase 4 changes the graph algorithm, storage and presentation. The overall React UI/UX will follow the user's references in Phase 7. Russian localisation follows completion of the English interface.

The user runs Git commands. For a separate Codex chat, specify the phase, scope and verification criteria; use repository documents for architecture decisions and current status.
