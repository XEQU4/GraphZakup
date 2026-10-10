# IZ2 on a Linux server

The image includes Django/Gunicorn and the compiled React workspace. Compose
runs PostgreSQL 17, Redis, migrations, web, ingestion worker, AI worker and one
beat scheduler. One Compose file has optional profiles for Ollama/Qwen, NVIDIA
access and Caddy HTTPS. Dockerfile builds the shared application image.
No Node installation is needed on the server.

This is deployment preparation, not public-release approval. Remaining gates
are in docs/FINAL_AUDIT.md. In particular, review model prose while AUD-002 is
open. EN/RU changes the workspace; source records, saved explanations and the
standalone English API reference keep their language.

## New installation

Requirements: Linux Docker Engine, Compose 2.24.4+ and Python 3 for host helpers.
Run commands from the repository root. Windows can use Docker Desktop in Linux
mode and .venv\Scripts\python.exe instead of python3.

For an empty installation, use the complete block below. To transfer existing
native data, run only environment preparation and configuration validation,
then continue with the transfer section before the first `up`.

```sh
python3 scripts/prepare_deploy.py --project iz2 --output .env.docker --ai cpu
docker compose --env-file .env.docker config --quiet
docker compose --env-file .env.docker up --build -d --wait
docker compose --env-file .env.docker ps -a
```

The helper generates secrets locally, uses mode 0600 on Linux, refuses overwrites
and preserves native .env. With --ai cpu it enables local Ollama/Qwen and saves
COMPOSE_PROFILES=local-ai. Use --ai template to omit the model, or --ai gpu for
an NVIDIA host with the NVIDIA Container Toolkit. Select one AI mode only.
Collection, automatic model jobs and paid generation remain off.
Generated Docker environments use a 180-second AI timeout and 2048 output tokens
for local CPU inference; native defaults remain 90 seconds and 1024 tokens.
Do not print expanded Compose configuration with working secrets; use --quiet.

Keep COMPOSE_PROJECT_NAME unchanged for an existing installation. The default
namespace remains governmentprocurementgraph; iz2 is for a new installation.
Preserve postgres17_data, redis_data, ollama_models and database identifiers.
Old PostgreSQL 16 data needs dump/restore, never a direct volume attachment to 17.
Compose always uses db:5432 regardless of the native database host.

Local HTTP binds only 127.0.0.1:8000. PostgreSQL, Redis and Ollama have no public
ports. An empty database is not populated automatically. Create an administrator:

```sh
docker compose --env-file .env.docker exec web python manage.py createsuperuser
```

## Transfer the native database before starting the application

Stop collection and other application writers for a consistent transfer. Native
Windows commands (also stop a running Django development server with Ctrl+C):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/background.ps1 -Action Stop
.\.venv\Scripts\python.exe scripts/backup_database.py --verify-restore --deployment-manifest
```

The output identifies the dump and companion .deployment.json without printing
secrets or rows. Transfer both securely into the target artifacts/transfer/.
Keep another encrypted backup off the server; never commit backups or tokens.

Build the image and start only the target database/Redis. Do not migrate before
restoring into the empty target:

```sh
docker compose --env-file .env.docker build migrate
docker compose --env-file .env.docker up -d --wait db redis
python3 scripts/deploy_database.py --env-file .env.docker --project iz2 restore --dump artifacts/transfer/DATABASE.dump --manifest artifacts/transfer/DATABASE.deployment.json --output-dir artifacts/recovery
docker compose --env-file .env.docker up -d --wait
```

Replace DATABASE with the generated basename and iz2 with the target namespace.
Restore refuses a populated target or active application containers. It validates
the checksum, restores transactionally, then compares rows, sequences, indexes
and constraints. It never drops a database or cleans an existing schema.
Ownership/ACLs map to the target user; external media/custom PostgreSQL roles need
separate handling. A changed SECRET_KEY invalidates old sessions, requiring login.
The verified transfer requires the same PostgreSQL major version. Cross-major
upgrades need a separate rehearsal. If comparison fails after restoration, the
helper preserves the target for inspection; it never erases it for another try.

For later Docker backups:

```sh
docker compose --env-file .env.docker stop beat worker ai-worker web
python3 scripts/deploy_database.py --env-file .env.docker --project iz2 backup --output-dir artifacts/backups
docker compose --env-file .env.docker up -d --wait
```

Use an independent empty project for restore rehearsals. A checksum alone is not
restore proof. Docker backups output a `.dump` and companion `.json`; use that
JSON path for `restore --manifest`. Native `--deployment-manifest` instead outputs
the `.deployment.json` shown above. Never use down --volumes on data you need.

The same .env.docker selects optional services for startup and recovery. No extra
Compose files or profile flags are needed:

```sh
python3 scripts/deploy_database.py --env-file .env.docker --project iz2 backup --output-dir artifacts/backups
```

Its metadata container uses `--no-deps`; inspection does not start migrations,
application processes, collection or model jobs.

## Collection and Qwen

The generated CPU/GPU environment configures Ollama and worker queues. To collect on
this host, set these private environment values:

```dotenv
ENABLE_SCHEDULED_IMPORT=true
ENABLE_SCHEDULED_KGD=true
ENABLE_KGD_CHECKS=true
ENABLE_BACKGROUND_AI=false
```

Copy authorised credentials privately. KGD registration and company-scoped debt
tokens have different roles; missing entitlement never means zero debt. Native
and Docker database copies do not synchronise automatically.

```sh
docker compose --env-file .env.docker up --build -d --wait --wait-timeout 600
docker compose --env-file .env.docker exec web python manage.py ingestion_status
```

First model setup downloads weights into ollama_models and may exceed this wait
on slow networks. Inspect ollama-init logs and repeat startup once it finishes.
Ingestion does not depend on model readiness; the AI worker waits for it.

Collection uses independent bounded contract/profile/KGD stages, due times,
retries, host cooldowns and database leases. Meaningful evidence changes update
saved graph/analysis/template versions. GET never collects or regenerates.
Automatic model jobs additionally require ENABLE_BACKGROUND_AI=true; leave it
false until prose publication is ready. Explicit staff model jobs remain
available. Generated environments disable paid providers.

On an NVIDIA host, generate with --ai gpu instead of --ai cpu. The helper selects
local-ai-gpu and its matching internal model address. Do not enable both AI
profiles together. To change an existing deployment, preserve secrets and project
name; set COMPOSE_PROFILES, AI_PROVIDER, AI_MODEL and DOCKER_OLLAMA_BASE_URL
consistently, then stop the previous model service before starting its replacement.
CPU uses local-ai/http://ollama:11434; GPU uses
local-ai-gpu/http://ollama-gpu:11434; both use AI_PROVIDER=ollama,
AI_MODEL=qwen3:4b. Preserve any https profile in the comma-separated list.
Measure actual memory and latency:
a six-GiB model cap is a limit, not a hardware recommendation. Keep model revision
metadata aligned with deployed weights.

## Domain and HTTPS

For a new deployment with a chosen domain, generate its environment with HTTPS
settings from the outset (replace example.org/contact with your real values):

```sh
python3 scripts/prepare_deploy.py --project iz2 --output .env.docker --ai cpu --domain example.org --acme-email admin@example.org
docker compose --env-file .env.docker up --build -d --wait
docker compose --env-file .env.docker exec web python manage.py check --deploy
```

Run environment preparation only once; it refuses to overwrite an existing file.
For an existing .env.docker preserve all secrets and its namespace. Add https to
COMPOSE_PROFILES; set SITE_DOMAIN, ACME_EMAIL, ALLOWED_HOSTS and
CSRF_TRUSTED_ORIGINS=https://your-domain. Set TRUST_PROXY_SSL_HEADER,
SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE to true, and
AUTH_TRUSTED_PROXY_CIDRS=172.30.254.2/32 for the default proxy address. The proxy
refuses incomplete/insecure matching settings. Configure DNS and open TCP 80/443;
UDP 443 is optional HTTP/3.

Caddy persists certificates. The direct web diagnostic port stays bound to
127.0.0.1; only Caddy publishes public ports. Secure cookies and HTTPS redirects
are enabled. Only its fixed peer address may supply overwritten
client-IP/scheme headers. Default dedicated subnet is 172.30.254.0/28, proxy
172.30.254.2 with web peer 172.30.254.3; change PROXY_SUBNET, PROXY_ADDRESS and
WEB_PROXY_ADDRESS together if they conflict, also updating AUTH_TRUSTED_PROXY_CIDRS.
This single-host configuration has one
web container with multiple Gunicorn processes; replica scaling needs a new
address plan.
This assumes one public edge; adding a CDN needs a new trust-policy review.
Enable HSTS only after verifying real HTTPS; preload/subdomains need separate
readiness. Domain issuance/firewalls still require checks on the chosen server.

API/admin account quotas are atomic across processes in private Redis DB 1.
Redis outages return 503 for protected account operations instead of resetting
limits. Keep Redis noeviction. Native local quotas produce a deployment warning.
Framing is denied. Redis Cluster is not supported by this multi-key limiter.

## Operations and upgrades

Use the same private environment file for later starts/stops/upgrades.

```sh
docker compose --env-file .env.docker ps -a
docker compose --env-file .env.docker logs --tail=100 web worker ai-worker beat
curl -f http://127.0.0.1:8000/health/live/
curl -f http://127.0.0.1:8000/health/ready/
docker compose --env-file .env.docker stats --no-stream
docker compose --env-file .env.docker stop
docker compose --env-file .env.docker up -d --wait
```

Use the HTTPS domain for health requests with the https profile. Readiness
checks PostgreSQL/Redis; worker probes use targeted ping; beat probes a heartbeat
written after scheduler progress. Health does not prove complete source coverage.
Docker marks unhealthy services but does not restart them solely because a probe
fails. Monitor that state. unless-stopped restarts crashed services and starts
them after Docker/host restart, unless explicitly stopped. Enable Docker Engine
startup on the host.

Logs rotate at 10 MiB x 3 per service. Memory/CPU/PID limits are configurable.
Redis has a 192-MiB data budget inside a 512-MiB cap; monitor queue/memory growth.
Workers have warm-shutdown windows; do not force short timeouts during collection.
Backends are non-root, read-only, without capabilities and have a writable /tmp.
Gunicorn recycles workers and omits query strings/headers from access logs.
Backup disk retention is an operator decision.

Before upgrading, verify a backup, stop writers, build, run startup/migrations,
then inspect health and representative saved pages. Do not use live parsing or
paid generation as a test. Migrations do not regenerate immutable explanations.

References: [Compose services](https://docs.docker.com/reference/compose-file/services/),
[Caddy proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy),
[Django checklist](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/).

