# IZ2

**Evidence-based analysis of Kazakhstan public procurement relationships.**

IZ2 helps analysts find companies connected through recorded owners, directors,
addresses and contacts, inspect the evidence in an interactive graph, and decide
what needs further verification. Each group has saved graph/analysis versions and
an English explanation tied to the same facts.

The product name is **IZ2**, the package/repository name is **iz2**, and the intended
future domain is **iz2.kz**. Domain registration and public hosting are not part of
the current implementation. The project is developed as a thesis prototype with
a possible later pilot.

## Product scope

| Capability | Current status |
| --- | --- |
| Contract/company collection | Unified registry, Adata and KGD adapters; resumable ingestion and provenance |
| Company relationships | Saved contact and identifier-confirmed role evidence; names alone do not merge people |
| Graph dashboards | Interactive D3 graph, evidence inspection, history and personal layouts |
| Company tax information | Identity-gated KGD registration and aggregate arrears, live-verified for one authorised company |
| Review priority | Versioned, capped rules with separate link strength, financial indicators and unknown coverage |
| Explanations | Saved English templates; optional free local Qwen3:4b selects supported wording/order, with fallback and reuse |
| Court records, bankruptcy and restricted-participant lists | Planned source-verified indicators; legacy person flags are not verified findings |
| Owner-specific history | Planned exact-person evidence; company debt is not automatically owner debt |
| Coordinated tender behaviour | Not assessable yet without bidders, bids, lots and outcomes |
| DRF / React | Versioned DRF API and React/TypeScript workspace implemented; visual acceptance pending |

The original product goal is to combine relationship evidence with relevant,
verified company/person history and explain review priorities in plain language.
Those additional sources require separately authorised integration and verified
access. A shared address, an ordinary court case or a legacy flag alone cannot
establish dishonest tender allocation. Current scores are uncalibrated review
indices, not probabilities of wrongdoing.

The current stack is Django/DRF, React/TypeScript, PostgreSQL, Celery, Redis and D3.js. Django serves React at /app/; the home page redirects there. Legacy templates remain at /legacy/ and their existing detail routes.

English is the primary language for project documentation, code comments, interfaces and generated explanations. Russian website localisation will be added later, after the English version is complete. Source data and the labels used to parse official websites retain their original language.


## Versioned API

The backend exposes saved companies, people, contracts, role evidence, clusters,
graph/analysis/text history, personal views and explicit staff jobs at /api/v1/.
Open http://127.0.0.1:8000/api/v1/docs/ for interactive Swagger documentation;
the schema and UI assets are served locally. See [Phase 6](docs/PHASE6.md) for the
implemented contracts and measured verification boundaries.

Lists support documented filters/order and page_size 1..100. Public reads omit
personal IIN, raw observations and experimental model estimates. KGD failures and
unknown legal dates remain explicit. All monetary amounts are JSON strings.

GET /api/v1/session/ returns the current role and a CSRF token. Use Django session
cookies and X-CSRFToken for login and writes; only staff can launch jobs. An
explanation job defaults to template preparation; use_model=true is explicit and
uses server configuration/paid gates. GET never regenerates domain results.

No new .env settings or domain migrations are needed for the API. Run
`uv run python manage.py collectstatic --noinput` after installing or updating
dependencies, then restart the server; legacy pages and admin remain available. API introduction does not start collection
or enable a model. Russian localisation follows the completed English frontend.

## React workspace

The English interface includes an overview, searchable company/person directories,
company/person details, contracts, relationship groups, saved graphs, evidence and
analysis histories, an About Us guide and a project footer with contacts, sources
and credits. Sign-up/sign-in dialogs and a personal profile support username
updates and password changes; email is read-only and no avatar is used. The
project is independently developed by Barakhat Mukhtar Batyruly; Yestay Arnuruly
(Estay-2020@bk.ru) is preparing a related article.
It reads the existing API and saved working records. Lighting
and motion combine Lightswind-derived aurora, local React Bits text/focus/count
adaptations, Particles/Border Glow and Magic UI Border Beam; Radix provides icons
and accessible dialogs. Motion can be paused and follows device preferences.
Fonts, assets and dependency notices are served locally. Bootstrap
is excluded from React; compatibility templates retain it.

Use Node 24 LTS (minimum 22.12) and run these commands from the repository root:

```powershell
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
uv run python manage.py runserver
```

Open http://127.0.0.1:8000/app/ . No environment change, new domain migration, Redis,
collection or model is required to browse saved data. Restart Django after rebuilding
and collecting assets. For development with hot reload, keep Django on port 8000 and
run `npm.cmd run dev` in frontend, then open http://127.0.0.1:5173/ . The development
proxy stays same-origin from the browser and forwards CSRF origin to Django.

Docker builds React automatically from package-lock.json before collectstatic.
English design follows the supplied blue, restrained cyberpunk references; rewriting
saved explanations and the relationship-group page remain separate follow-up work.
Russian localisation remains deferred. See [Phase 7](docs/PHASE7.md) for verification.

The overview combines Lightswind-derived aurora lighting with original dimensional
artwork, glass cards and accessible saved-record controls. Mobile contract cards
show complete records. Motion can be paused and follows device preferences.
The standalone ignored next-app/ experiment is not part of the application.

The current design uses an original IZ monogram/local favicon and a deep-blue,
black and white palette. Semantic animated headings, navigation focus frames,
saved-count reveals and continuous emblems follow the motion preferences.
Graph controls share 44px heights; analysis status spans both aligned panels.
Graph selection contours, bounded edge accents and structured evidence panels
preserve saved positions, filters and versions. Directory tables use separated
rows and labelled mobile cards, with inset desktop navigation arrows. The article
author's email appears in the footer contact panel beside the developer's email.
Chromium checks passed from 320 to 1920px;
user visual acceptance remains pending.

Accounts keep personal graph layouts on the server: positions, pinned nodes,
zoom, selection, relationship filters and frozen state. The profile's **Your graph
views** section opens each saved snapshot, and views restore in another browser.
Guests can browse saved records and keep layouts in their current browser.
`GET /api/v1/account/views/` provides authenticated, paginated view metadata.
Save view shows feedback beside its toolbar and commits the final camera target
when a navigation animation is still running. A failed account-view read or a
revision conflict requires **Reload saved account view** before another write.
An account without a saved view can adopt the guest layout after a successful
account-view read; saving it remains an explicit action.

Account writes use session cookies and CSRF. Registration creates ordinary users;
profile changes cannot edit email or permissions. Changing a password checks the
current password, retains the requesting session and invalidates other sessions.
`api.0001_account_identity_indexes` adds case-insensitive username/email uniqueness
without rewriting existing accounts. Empty legacy emails remain supported. The
migration and reversal were verified on a restored copy; the working database now
has all 69 existing migrations applied, with no pending or newly added migration
in this follow-up.
Email verification and email-based password recovery are not implemented.
Latest checks: 357 isolated PostgreSQL tests without skips and 88 React tests,
production build, formatting and migration drift passed. A fresh browser restored
an account view without localStorage, including its pinned selected node, zoom,
filters and frozen state. All 50 working-table fingerprints remained unchanged.

## Try the free local AI

On this development computer, the portable Ollama runtime and Qwen weights are
already cached under ignored `artifacts/phase5/`. Windows startup reuses them:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/local_ai.ps1
uv run python scripts/check_local_ai.py --serve
```

The second command creates an isolated SQLite database with synthetic companies,
runs real local inference, checks saved publication and unchanged-request reuse,
then serves the demo at http://127.0.0.1:8766/clusters/ . It does not load `.env`,
connect to working PostgreSQL, collect source data or require Redis. The model
estimation case is stored separately from the public rules. Output is limited to
prepared claims; independent scoring/readability superiority is unverified.

New saved explanations show a brief summary, key connections and their meaning,
the review-point breakdown, suggested checks and missing-data coverage. Technical
metadata is expandable. Existing texts stay in history: reopening a cached older
demo does not regenerate its explanation; a fresh probe uses the updated format.

`--serve-saved` opens the last synthetic demo without new generation. Press Ctrl+C
in the demo terminal to stop it; `scripts/local_ai.ps1 -Stop` stops only a server
owned by that helper and retains its cache. A clean clone needs a local Ollama
installation first; the helper downloads missing Qwen weights. Runtime/weights
are not distributed in Git or application images.

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
| [Phase 6 API](docs/PHASE6.md) | Versioned JSON routes, sessions/CSRF, permissions, histories, jobs and OpenAPI verification |
| [Phase 7 frontend](docs/PHASE7.md) | React integration, visual references, verification and remaining limits |
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

The project requires Python 3.13 or later and Node 22.12 or later (Node 24 LTS recommended). Dependencies are defined in `pyproject.toml` and `uv.lock`. Set local credentials in `.env`; a real `SECRET_KEY` is required. Before running Django against an existing database, verify its backup, then apply migrations:

```powershell
uv sync --frozen
uv run python manage.py migrate
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
uv run python manage.py collectstatic --noinput
uv run python manage.py runserver
```

Native file logs use `logs/app-YYYY-MM-DD.log` and `logs/error-YYYY-MM-DD.log`, with process locks and 7/14 UTC calendar days of retention. Existing `app.log` and `error.log` are preserved. Restart Django and any running Celery processes after updating logging.

Offline tests use in-memory SQLite and mocked HTTP. They do not load `.env` or connect to the working database, Redis or websites. JavaScript checks use only Node.js standard modules:

```powershell
.\.venv\Scripts\python.exe -B manage.py test --settings=config.test_settings
node tests/frontend_regressions.cjs
node tests/graph_interactions.cjs
.\.venv\Scripts\python.exe -B manage.py makemigrations --check --dry-run --settings=config.test_settings
```

`test.py` contains the user's learning exercises, not application tests. The 320-test phase-completion suite passed on isolated PostgreSQL in Phase 6. The working-data/static/logging follow-up ran 328 offline tests, passing with four PostgreSQL-only skips for concurrency and full-precision money. Phase 7 passed 338 isolated PostgreSQL tests without skips and 35 React tests; responsive browser and synthetic session/view checks passed. Five real free-local-model synthetic cases also passed. API/recovery verification is in [PHASE6.md](docs/PHASE6.md); AI measurements and quality/operational limits are in [PHASE5.md](docs/PHASE5.md). Earlier phase documents retain their historical results.

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
