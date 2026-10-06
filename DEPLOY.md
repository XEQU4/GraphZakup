# Run GrafZakup with Docker Compose

The stack combines PostgreSQL 17, Redis, one-time migrations, Django/Gunicorn, a Celery worker and one beat scheduler. Automatic data collection is disabled by default. Real API tokens are not required to start an empty database and check the interface.

## Preparation

Docker with Linux containers and Docker Compose v2 is required. For existing data, first verify backup and recovery as described in [docs/RECOVERY.md](docs/RECOVERY.md).

From the repository root in PowerShell:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Copy the generated value into SECRET_KEY and set your own DB_PASSWORD. If `.env` already exists, preserve it and update the necessary keys manually. Do not replace existing credentials with the example file.

The website listens on `127.0.0.1:8000` by default; DEBUG is disabled. Compose passes only the listed variables. PostgreSQL always uses the internal route `db:5432`; PGHOST from the local `.env` does not override it.

## One command for the stack

```powershell
docker compose up --build -d
```

PostgreSQL and Redis pass health checks. The migrate service applies migrations and exits; web and worker wait for it to succeed. Beat also waits for a healthy worker. Do not scale beat: each environment needs one scheduler.

```powershell
docker compose ps -a
docker compose logs --tail=100 migrate web worker beat
Invoke-RestMethod http://127.0.0.1:8000/health/live/
Invoke-RestMethod http://127.0.0.1:8000/health/ready/
```

`/health/live/` checks the HTTP process without accessing dependencies. `/health/ready/` performs SELECT 1 and Redis PING; an unavailable dependency returns HTTP 503 without credentials or a traceback in the response. These endpoints only read state. The worker health check uses a targeted Celery inspect ping.

Website: http://127.0.0.1:8000/ . Create an administrator separately:

```powershell
docker compose exec web python manage.py createsuperuser
```

An empty database contains no companies or graphs. Compose does not fill it through live parsing.

## Configuration and persistence

| Variable | Purpose |
| --- | --- |
| SECRET_KEY | Required runtime secret; the example placeholder is rejected |
| DB_NAME, DB_USER, DB_PASSWORD | Container database and matching Django credentials |
| WEB_PORT, WEB_BIND_ADDRESS | Host port and address; Gunicorn uses port 8000 inside the container |
| ALLOWED_HOSTS | Explicit hostnames without a protocol; wildcard is rejected when DEBUG=false |
| CSRF_TRUSTED_ORIGINS | Additional origins, including their protocol |
| ENABLE_SCHEDULED_IMPORT | false disables update_all_data; true explicitly enables the live pipeline |
| INGESTION_REQUEST_INTERVAL | Minimum interval between requests to one host; default 1.5 seconds |
| INGESTION_SOURCE_CACHE_SECONDS | Successful company-observation TTL; default 900 seconds, 0 disables it |
| INGESTION_LEASE_SECONDS | Pipeline lease with heartbeat and fencing; default 900 seconds, minimum 60 |
| GPG_LOG_TO_FILES | true for local Python; Compose forces false and writes stdout/stderr |
| OPENROUTER_API_KEY, OPENROUTER_MODEL, GOSZAKUP_TOKEN | External integrations; keys may be empty for infrastructure checks |

The database uses the new postgres17_data volume; Redis uses redis_data and AOF. The old PostgreSQL 16 postgres_data volume is not attached to 17. Transfer data through a verified dump/restore into a separate database. This configuration does not change or delete the old volume.

Shutdown preserves volumes:

```powershell
docker compose down
```

A later `docker compose up -d` reuses the saved database. Do not add `--volumes` when stopping an environment whose data you need.

Docker installs dependencies from uv.lock with `uv sync --frozen --no-dev`, preserving the user's pyproject/lock. Static assets are built with a dummy build-only key; it does not replace runtime SECRET_KEY. The image runs as a non-root user. Only migrate builds the shared backend image; web/worker/beat reuse the same local image with pull_policy=never. Use the command with `--build` above for the first start.

Containers log only to stdout/stderr, available through `docker compose logs`. Gunicorn workers do not share file rotation. Local Python enables file logging by default through GPG_LOG_TO_FILES=true.

## Check a separate environment

Create smoke.env in the ignored artifacts/ directory with temporary credentials, an available WEB_PORT and a unique project name. Do not copy working passwords or API keys. Compose does not load the local `.env` as a container env_file. Process environment variables take precedence over `--env-file`; isolated checks must also use temporary values there.

```powershell
docker compose --env-file artifacts/phase1/smoke.env -p gpg_phase1_smoke up --build -d
docker compose --env-file artifacts/phase1/smoke.env -p gpg_phase1_smoke ps -a
```

Set your own SECRET_KEY/DB_PASSWORD, ENABLE_SCHEDULED_IMPORT=false, empty API keys and a separate WEB_PORT in smoke.env. The project prefix separates containers and volumes from the normal deployment.

Offline application tests use in-memory SQLite, do not load `.env`, connect to working PostgreSQL/Redis, or open log files:

```powershell
.\.venv\Scripts\python.exe -B manage.py test --settings=config.test_settings
```

## Public HTTPS deployment

Use a TLS reverse proxy and put the domain in ALLOWED_HOSTS. Enable SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE. TRUST_PROXY_SSL_HEADER=true is allowed only when the proxy replaces incoming X-Forwarded-Proto. Enable HSTS through SECURE_HSTS_SECONDS after checking HTTPS; subdomains/preload require those domains to be ready.

Health endpoints are exempt from SSL redirect for internal HTTP health checks; Compose adds localhost/127.0.0.1 to allowed hosts. Add a separate frontend origin to CSRF_TRUSTED_ORIGINS when necessary.

Enable automatic collection deliberately after checking sources, data and tokens: ENABLE_SCHEDULED_IMPORT=true. The task guard also blocks previously saved beat schedules while the flag is false; schedule records are not deleted. Schedules are available in Django admin.

After Phase 2, the task reads a window of 500 contracts from the beginning of the registry in `update` mode, then refreshes eligible companies and clusters. A retry continues the same `IngestionRun`; a database lease blocks concurrent pipelines. Read status without source requests using `docker compose exec web python manage.py ingestion_status`. Details and local commands are in [docs/PHASE2.md](docs/PHASE2.md). Rebuild the updated image; migrate creates observations and isolates old name-only roles while preserving original records.

KGD settings from `.env.docker` are passed to application services. Checks default off (`ENABLE_KGD_CHECKS=false`) and have no automatic schedule. The manual task `apps.core.tasks.check_kgd` shares the ingestion lease and saved-run retry mechanism. Apply migrations through the migration service and restart services after changing credentials. Do not place portal/account tokens in CLI/Celery arguments or Compose configuration output. One registration/zero-arrears scenario is accepted; broader coverage remains unverified. See [docs/PHASE3.md](docs/PHASE3.md).

Phase 4 adds schema-only graph migration `graph.0005`. It does not invent historical evidence or calculate graphs during migration. After a current verified backup and migration, explicitly run `docker compose exec web python manage.py build_clusters` to publish graphs from saved facts; no source request or paid generation occurs. Existing UUIDs/texts are preserved. Staff-requested graph jobs use the existing worker, share the ingestion lease and have no automatic beat schedule. Restart/rebuild services so the worker discovers `apps.graph.tasks`. Layouts belong to signed-in users; stale snapshot/revision saves return 409. See [docs/PHASE4.md](docs/PHASE4.md).

Official references: [uv in Docker](https://docs.astral.sh/uv/guides/integration/docker/), [Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/), [Django deployment checklist](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/).
