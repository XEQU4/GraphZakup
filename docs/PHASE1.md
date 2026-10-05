# Phase 1: defect fixes and startup verification

Date: 5 October 2026. Complete against the [audit](AUDIT.md) and [roadmap](ROADMAP.md#phase-1-defect-fixes-and-startup). This historical record preserves Phase 1 results; later changes have separate records.

## Changed behaviour

### Imports and company data

- Full import starts from page 1 and upserts without deleting companies/contracts/roles/clusters or resetting the normal checkpoint. `--start-page` overrides the start; `full_import_page` tracks scans, but each new full run starts fresh.
- Page/checkpoint commit together. Failure rolls back that page, retaining earlier commits. At the Phase 1 partial limit, retain the page for remainder upserts. Confirmed empty tables indicate end-of-data without advancement; HTTP/challenge/malformed responses fail. Empty imports do not enrich/rebuild.
- Decimal comes directly from strings; invalid amounts never become zero. Explicit date formats produce `date`. BIN/card checks prevent silent external-ID/company reassignment.
- Enrichment normalises before fallback, continues after individual failures, and never marks absence/error fresh. Adata verifies BIN and uses labelled company contacts, excluding support/navigation/footer. Automatic name-only director merging is disabled; legacy repair remained Phase 2 work.

### Clusters and explanations

- Atomic rebuilds preserve exact-membership UUIDs; deterministic overlap continues each old ID in only one new component. Disappeared groups are archived with URLs/texts. PostgreSQL transaction advisory locks serialise rebuilds.
- `graph.0003` adds active state/fingerprint/staleness. Old texts are unconfirmed. After the first rebuild, unchanged facts produce no writes/generation; changed facts retain text as stale.
- GET reads without generation/writes. Detail checks member facts against saved fingerprint to avoid false freshness after partial ingestion. Empty fallback: "Explanation has not been prepared yet." Versioned explanations remain Phase 5.
- A prefetched director map removes per-pair SQL. Ended/future roles excluded, intervals `[start, end)`; unknown bounds do not prove simultaneous leadership.

### Interface and logs

- Search escapes names/contract numbers; tooltips use DOM text. Websites permit validated HTTP/HTTPS, including legacy values. Cancellation/response checks reject late search results.
- Consistent thresholds 80/50 and floored average risk. Archived groups excluded from current stats; related-company counts deduplicate signals; director search joins do not multiply counts.
- Rotation uses `app.log.YYYY-MM-DD`; UTC cleanup supports old/new names without removing active files/symlinks. Docker logs stdout without shared rotating files. Celery records safe error types rather than private exception values/chains.

### Startup

- Python 3.13/frozen lock/shared image for migrate/web/worker/beat. PostgreSQL 17 has a new volume; Redis AOF. Migrations precede application services; beat waits for healthy worker. Liveness/readiness checks are read-only.
- Required SECRET_KEY, DEBUG false, explicit hosts, configurable HTTPS. `.env`/archives/logs/credential directories excluded from images. Automatic import off, guarded even for old beat schedules. README/DEPLOY/`.env.example` updated.

## Executed verification

| Check | Result |
| --- | --- |
| SQLite | 83 discovered, 82 passed, 1 PostgreSQL-only skip |
| Docker PostgreSQL | All 83 passed, including two-connection rebuild concurrency |
| JavaScript | Three search escapers, stale-response handling, literal tooltip text passed |
| Django/migrations | Checks passed; no drift |
| Compose build/wait | Migrate exited 0 before apps; db/redis/web/worker healthy, beat running |
| HTTP | Five pages/health 200; malformed risk 400; real PostgreSQL/Redis readiness |
| Static assets | Manifest-hashed URLs 200, gzip, immutable cache |
| Runtime | UID 10001; Python 3.13.16, PostgreSQL 17.11, Django 6.0.6, Celery 5.6.3 |
| Isolation | Auto-import/API key off; no image secrets/file logs; temporary DB removed |
| User files | Three hashes matched Phase 0 |

Phase 0 dump restored into separate Docker PostgreSQL 17: all 29 tables matched before migration. After `graph.0003`, original values in 28 tables outside migration history matched; four cluster UUIDs/memberships/texts preserved with expected defaults. Temporary DB dropped. Read-only REPEATABLE READ comparison confirmed source unchanged across 29 tables. Final reviewed image/stack were built/started with migrations/health checks.

Local records in `artifacts/phase1/`: `migration-verification.json`, `source-database-unchanged.json`, `compose-verification.json`, `http-smoke.json`, `postgresql-tests.txt`, `user-files-preserved.json`. Hash comparison is not individual ACL/sequence/index/default checking; actual PostgreSQL restore/migration ran. No live parsing, real ingestion pipeline, or paid generation. Test stack stopped without deleting volumes.

## Remaining work

- Phase 2: consolidated parsers, runs/observations/history, retryable issues, leases. Mutable page numbers cannot guarantee full incremental sync; live markup unverified.
- Phase 3: KGD subject/result verification; missing observations are not negative debt checks.
- Phase 4: snapshots/shared evidence/lineage/layout/substantial graph improvement. Archives still read current fields/edges; GET freshness covers existing members, not new neighbours before rebuild. Rebuild locking does not isolate concurrent fact writers.
- Phase 5: calibrated scoring, evidence/rule/template versions, controlled LLM. Weak-contact group size can still inflate risk; inactive OpenRouter needs redesign.
- Phases 6-7: DRF/React. Safe HTML fragments are not API contracts; user references determine later design, not Phase 1.
