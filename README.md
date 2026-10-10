# IZ2

**Evidence-based analysis of relationships in Kazakhstan public procurement.**

IZ2 brings saved company, contract and person records into an interactive graph.
It shows why companies are connected, which sources support the links, what is
missing, and what an analyst should check next. Graphs, analyses and explanations
have immutable histories; opening a page never starts collection or generation.

This is an independently developed thesis prototype, with a possible later pilot.
The product is IZ2, the repository/package is `iz2`, and the intended future domain
is `iz2.kz`. No public host or domain has been selected for deployment.

## What is implemented

- Searchable companies, people, contracts and relationship groups, with source
  references, retrieval dates and separate current/historical role views.
- Interactive D3 graphs, evidence inspection, filters and version history.
  Accounts can save, restore and remove personal graph layouts across devices.
- Registration, sign-in and profile settings: editable username, read-only email,
  and current-password-protected password changes. Email verification and password
  recovery are not yet implemented.
- Resumable registry/Adata/KGD collection through bounded Celery stages, with
  durable checkpoints, source pacing, retry delays and host cooldowns.
- Deterministic review-priority rules, saved explanation templates and optional
  local Qwen3:4b prose, with validation, version checks and template fallback.
- An accepted React interface with an EN/RU switch and motion preferences.
  The standalone API reference remains English. Original source values and saved
  explanation prose retain their original language.

The stack is Django/DRF, React/TypeScript/Vite, PostgreSQL, Redis, Celery, D3 and
optional Ollama. Django serves the workspace at `/app/`, the API at `/api/v1/`,
and its reference at `/api/v1/docs/`. Existing `/legacy/` routes remain available.

## Evidence and limits

Default company listings show source-checked profiles; default people listings
show identifier-verified current records. Pending, unverified and historical
records remain accessible through filters. A collected record is not necessarily
complete, and equal names alone never merge people or establish a shared director.

KGD taxpayer registration and tax arrears are separate checks. Registration does
not prove absence of debt; failed or unavailable checks remain unknown. Debt
access depends on company-specific entitlement, and entrepreneur debt coverage
is not verified. Company debt is not assigned to directors or owners.

Available sources do not provide complete verified ownership history. Court,
bankruptcy and restricted-participant integrations remain planned. Contracts
alone do not establish coordinated bidding without bidders, bids, lots and
outcomes. Review priority is a manual-review index, not a probability of wrongdoing.

The current system supports a supervised evidence demonstration. Public release
still requires the outstanding model-prose, dependency and publication-policy
checks in [the final audit](docs/FINAL_AUDIT.md). Model validation is not proof that
every generated sentence is correct. Automatic model prose remains off in newly
generated Docker environments.

## Start with Docker

Use Linux containers and Docker Compose 2.24.4 or newer. A single
`docker-compose.yml` contains the stack; optional profiles select CPU/GPU Ollama
and HTTPS. `Dockerfile` builds the shared backend/frontend image.

For a **new, empty installation**, run from the repository root:

```sh
python scripts/prepare_deploy.py --project iz2 --output .env.docker --ai cpu
docker compose --env-file .env.docker up --build -d
docker compose --env-file .env.docker ps -a
```

Open <http://127.0.0.1:8000/app/> and <http://127.0.0.1:8000/api/v1/docs/>.
Readiness is available at `/health/ready/`. The first model startup downloads
Qwen weights into a persistent volume. PostgreSQL, Redis, migrations, web,
ingestion/AI workers and beat are managed by Compose.

The generator creates private credentials and refuses to overwrite an existing
file. Preserve the generated file and project name on subsequent starts; changing
the namespace selects different volumes. Existing installations retain the legacy
Compose namespace unless explicitly configured otherwise. Native `.env` stays separate.

Use `--ai template` to omit Ollama, or `--ai gpu` on an NVIDIA host with the
Container Toolkit. Add `--domain YOUR_DOMAIN --acme-email YOUR_EMAIL` when creating
a new server environment to enable HTTPS and matching proxy/cookie settings.
These options write the matching profiles into the private environment file;
the same Compose startup command is used for every variant.

**To transfer the existing native database, restore into an empty Docker target
before the first full `up`.** Do not let initial migrations populate that target
first. Follow the backup/restore sequence in [DEPLOY.md](DEPLOY.md); the tools
verify the target and never erase existing data. A native database is not copied
automatically. Do not attach a PostgreSQL 16 volume directly to PostgreSQL 17.

Collection, automatic model jobs and paid AI stay disabled in generated
environments. Enable collection deliberately with appropriate source credentials;
an empty installation does not populate itself. Operational settings, backups,
updates and shutdown commands are in [DEPLOY.md](DEPLOY.md).

## Native Windows development

Use Python 3.13+, Node 22.12+ and `uv`. Configure private local credentials in
`.env` using `.env.example`; PostgreSQL must be available. Verify a current backup
before applying migrations to an existing database. From the repository root:

```powershell
uv sync --frozen
.\.venv\Scripts\python.exe manage.py migrate
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
.\.venv\Scripts\python.exe manage.py runserver
```

Restart Django after rebuilding and collecting assets. For hot reload, keep Django
on port 8000 and run `npm.cmd run dev` from `frontend/`; open
<http://127.0.0.1:5173/>. Its development proxy forwards `/api` to Django.

## Background collection on the laptop

Start local PostgreSQL and Redis first. To restart or start the owned collector:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/background.ps1 -Action Stop
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/background.ps1 -Action Start
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/background.ps1 -Action Status
```

`Stop` safely handles already stopped owned processes and waits for active tasks.
`Start` launches separate ingestion/AI workers, one beat and local Ollama/Qwen;
it opts these processes into collection and local automatic model jobs without
editing `.env`. Review generated prose while the model audit finding remains open.
Do not run another collector against the same database. The terminal may be closed
after startup; collection cannot continue while the laptop sleeps or is off.

Use `Status` for process ownership and saved progress. Logs, PID records and the
schedule are under ignored `artifacts/background/`. Stop collection using the
same `-Action Stop` command. To also stop the helper-owned model server:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/local_ai.ps1 -Stop
```

Beat checks due work every minute. Default profile batches are ten companies with
a two-minute minimum interval; KGD registration/debt stages use five-minute
intervals. Pacing, budgets, retries and source availability determine throughput.
Accepted evidence changes refresh saved graphs/templates; unchanged evidence
reuses existing results. No Windows login/startup task is installed.

## Verification

Run offline application/infrastructure tests with explicit labels so the personal
learning file `test.py` is excluded:

```powershell
.\.venv\Scripts\python.exe -B manage.py test apps tests --settings=config.test_settings
.\.venv\Scripts\python.exe -B manage.py makemigrations --check --dry-run --settings=config.test_settings
node tests/frontend_regressions.cjs
node tests/graph_interactions.cjs
cd frontend
npm.cmd test -- --maxWorkers=2
npm.cmd run build
npm.cmd run format:check
cd ..
```

Offline settings do not load `.env` or contact working services. SQLite skips some
PostgreSQL-specific cases; use a separate PostgreSQL test database for full
database/concurrency verification. Real source checks and model inference are
separate explicit operations, not part of this offline command sequence.

Linux Docker startup, data transfer/recovery, HTTPS, account/layout persistence
and a synthetic CPU Qwen job were exercised locally; target-server and NVIDIA GPU
execution still require verification. Dated results and limits are recorded in
[DEPLOYMENT_CHECK.md](docs/DEPLOYMENT_CHECK.md). Earlier phase reports preserve
historical results rather than declaring the current release certified.

## Repository map and documentation

| Location | Responsibility |
| --- | --- |
| `apps/` | Django domains, API, ingestion and saved graph/analysis services |
| `config/` | Django, Celery and test configuration |
| [frontend/](frontend/README.md) | React routes, reusable components, styles and localisation |
| `templates/`, `static/` | Django/API/legacy presentation; generated React output is ignored |
| `scripts/`, `tests/` | Operational tools and infrastructure regression tests |
| [DEPLOY.md](DEPLOY.md) | Current single-Compose startup, transfer and operations |
| [Architecture](docs/ARCHITECTURE.md) | Module boundaries and evidence/versioning rules |
| [Recovery](docs/RECOVERY.md) | Backup and verified restoration records |
| [Roadmap](docs/ROADMAP.md), `docs/PHASE*.md` | Scope decisions and dated implementation history |
| [Final audit](docs/FINAL_AUDIT.md), [repository audit](docs/REPOSITORY_AUDIT.md) | Findings, cleanup and remaining verification limits |

Secrets, database dumps, local reports and runtime/model caches belong outside
Git and Docker images; ignored `artifacts/` contains private local material.
Developer: Barakhat Mukhtar Batyruly. Related article author: Yestay Arnuruly
(Estay-2020@bk.ru). Third-party source and license notices are retained in
`frontend/licenses/` and `frontend/public/third-party-notices.txt`.
