# GrafZakup

GrafZakup is a thesis project for analysing company relationships in Kazakhstan's public procurement. It collects contract and company information, shows matching attributes, and explains the grounds for further review by an analyst.

The current version uses Django, PostgreSQL, Celery, Redis, HTML templates and D3.js. KGD checks are verified for one company's registration and zero-arrears scenario. Indexed evidence, stable groups, graph history and personal layouts are implemented. Phase 5 adds versioned findings, an evidence-bound review-priority index, saved English explanations and optional local model assistance. DRF and React follow in Phases 6-7; further visual design awaits user references. Relationships and scores do not establish a violation.

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
| [Phase 4 implementation](docs/PHASE4.md) | Indexed evidence, immutable graph versions, lineage, interaction and personal views |
| [Phase 5 implementation](docs/PHASE5.md) | Versioned review priority, saved explanations, free local model setup and experimental scoring |
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
node tests/graph_interactions.cjs
.\.venv\Scripts\python.exe -B manage.py makemigrations --check --dry-run --settings=config.test_settings
```

`test.py` contains the user's learning exercises, not application tests. All 238 tests passed on isolated PostgreSQL in Phase 5; SQLite skips three PostgreSQL-only concurrency scenarios. Five real free-local-model synthetic cases also passed. The protocol, recovery checks, measurements and unverified quality/operational limits are in [PHASE5.md](docs/PHASE5.md); earlier phase documents retain their historical results.

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

Phase 4 publishes saved evidence graphs and preserves UUID/version history through changes, merges and splits. Graph pages read saved results; authenticated users save personal views, and staff explicitly request deduplicated background recalculation from saved data. No collection or explanation generation runs on GET. Search, filters, neighbour highlighting, path/evidence inspection, pinning and layout restoration are implemented. See [PHASE4.md](docs/PHASE4.md) for applying migrations, an explicit first rebuild, verification and visual-check limits. The current graph prototype is accepted; further design and animation work follows the user's references in Phase 7. Russian localisation follows completion of the English interface.

The user runs Git commands. For a separate Codex chat, specify the phase, scope and verification criteria; use repository documents for architecture decisions and current status.

## Saved analysis and free local AI

The default `AI_PROVIDER=template` needs no API key or model. After a current verified backup and applying migrations, prepare existing saved graphs explicitly:

```powershell
uv run python manage.py analyse_clusters
```

This command reads stored evidence and saves versioned findings/templates without HTTP requests. Graph refreshes now update affected analyses/templates in the same transaction. Repeated unchanged inputs reuse saved results; GET never generates. Group pages distinguish review priority, link strength, coverage and unavailable behavioural risk. Company/dashboard compatibility scores remain labelled legacy values.

For free local assistance, set `AI_PROVIDER=ollama`, `AI_MODEL=qwen3:4b` and `OLLAMA_MODEL=qwen3:4b` in a private `.env.docker`, with empty `AI_BASE_URL`:

```powershell
docker compose --env-file .env.docker --profile local-ai up --build -d
```

The optional profile adds a persistent local model service and initial model download; the normal profile runs without it. Native Windows setup and host/container URLs are in [PHASE5.md](docs/PHASE5.md). Profile syntax is validated; actual container model startup/GPU use remains unverified. Model generation starts through explicit staff POST or `analyse_clusters --cluster UUID --use-model`, using the running worker.

The model selects finding order and validated wording variants. It cannot invent graph edges, identities or published scores. Failures retain a saved template; repeated completed requests reuse text. Optional `AI_EXPERIMENTAL_SCORING` stores a separate staff-only model estimate for evaluation. No independent labelled benchmark establishes a benefit yet; public review priority remains deterministic and uncalibrated. Future paid OpenAI/OpenRouter providers use environment settings and explicit paid opt-in. No ChatGPT subscription is needed for local inference.
