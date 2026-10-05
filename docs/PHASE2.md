# Phase 2: unified ingestion and fact provenance

Date: 5 October 2026. Complete. Offline SQLite/PostgreSQL 17.6 checks; working database unchanged. Next phase does not start automatically.

## Implemented behaviour

Three adapters in [apps/ingestion/parsers](../apps/ingestion/parsers) handle registry contracts, participant cards, Adata. Old `services/*_parser.py`/`services/enricher.py` removed. Parsers obtain/normalise data without ORM. [SourceProviders](../apps/ingestion/providers.py) returns `SourceResult`; complete `ContractPage` results become versioned observations.

[HttpTransport](../apps/ingestion/transport.py) shares one session across run adapters; per-host pacing/timeouts/up to two temporary retries/bounded Retry-After. HTTPS/two current hosts only; redirects disabled. Successful-response cache: 32 entries/60 seconds. Post-receipt response limit: 4 MiB, not streaming memory protection. Challenges/malformed HTML/HTTP failures are not empty pages.

[run_pipeline](../apps/ingestion/services.py) manages persistence/enrichment/current-cluster rebuild. CLI/[Celery](../apps/core/tasks.py) call it; commands do not call each other. No LLM/paid generation; existing explanations retained.

| Mechanism | Behaviour |
| --- | --- |
| `IngestionRun` | UUID/mode/stage/parameters/counters/page-company cursors/attempts/status/safe error |
| `SourceCheckpoint` | Stream progress/page/offset/content hash |
| `IngestionIssue` | Page/company-source failure/attempts/resolution |
| `IngestionLease` | Database pipeline lease/heartbeat/token check before publishing |
| `SourceObservation` | Allowed raw fields/normalised values/result/time/URL/parser version |
| `SelectedFact` | Observation supplying the final company field |
| Person/source identity | Confirmed identifier or company/source-scoped person/name variants |
| `IdentityCandidate` | Name match/rule evidence/heuristic confidence/review status |

Each page transaction covers contracts/new participants/observations/checkpoint. Failure cannot leave a half-page. Reimports update existing keys; supplier/external-ID reassignment rejected. Full import clears nothing.

Partial-page offsets apply only with unchanged hash; changed pages replay from the start through upsert. Enrichment preserves stage/company failures; resume does not reimport. Rebuild failure retries only clustering. Completed UUID returns saved results without requests.

Lease excludes simultaneous service CLI/Celery runs. Expired workers cannot publish, and old release cannot remove replacement lease. Direct parser calls outside the service are unprotected. Successful company observations are reusable within TTL; newer failure/parser-version change invalidates cache.

## Fact and identity policy

`success`, `not_found`, `unavailable`, `invalid`, `not_checked` stay distinct. Errors retain last valid fields; missing means unknown. Phone/email prefer valid Adata then registry; other fields prefer registry/Adata/contract participants. Select each source's latest nonempty successful value. Older valid priority-source facts may survive a newer error; inspect dates/results rather than call them fresh.

Explicit `director_absent=true` closes observed role/clears display. Empty name alone closes nothing; adapters never infer absence from empty cards.

Same names across companies create separate people plus `same_name_v1` confidence 0.250: a heuristic, not measured probability. Different verified IINs reject candidates. Automatic sharing requires exact source-confirmed IIN. HTML adapters cannot provide this; positive scenarios are fixtures for a future confirming source.

Director edges require current role, verified person, and successful company-specific observation with matching confirmed IIN. Status or arbitrary observation FK alone is insufficient. Company detail uses the same filter; unverified leadership is labelled but cannot verify cross-company links. `link_directors` never merges by name.

Changes close old observed roles with `is_current=false`/`observed_until`, retaining history without inventing legal end dates. Source legal intervals use `[start_date, end_date)`. Reappointments create new roles; older observations cannot override newer roles. Historical graph snapshots belong to Phase 4, not arbitrary date reconstruction by the current graph.

Ownership requires an explicitly complete list. Missing/incomplete lists close nothing; complete lists close only previous same-source roles. Unknown shares are NULL; directors are not inferred owners; company debt does not transfer to them. No beneficial-owner source added.

`Supplier` remains the compatible company table; supplier/customer flags support both roles. `Contract.customer` uses exact BIN; legacy customer fields retained. Customer-only companies excluded from supplier lists/counts.

Observations exclude HTML/exception messages/passwords/unknown fields. Only allowlisted structured fields, including bounded owners, persist. Credential/unknown-query URLs rejected. Admin observations/runs/issues/candidates/role history are read-only; arbitrary edits cannot verify identity.

## Legacy migration

Added `companies.0006`, `contracts.0006`, `owners.0003`, `ingestion.0001-0004`; two initial migrations break role/evidence dependency cycles.

Existing fields/contracts/roles receive `legacy/not_checked` observations. Old IIN is not automatically verified. Original roles archived; new roles have company-scoped people. Original people/role references/dates/shares preserved. Previous default 100% share is not copied as proven; old risk flags are not copied onto new unverified identities. Legacy name matches create candidates.

Reverse data migration intentionally does not remerge identities. Recover old application/schema from a verified separate backup, not a routine code rollback.

Legacy name-only edges excluded. Migrations preserve cluster UUID/membership/text. GET marks fingerprint staleness; next authorised pipeline safely rebuilds/archives vanished groups retaining IDs/texts.

Verified new PostgreSQL 17.6 backup before schema work:

- `artifacts/phase2/database_20261005T155408Z_21f9e0e2.dump` and JSON;
- `artifacts/phase2/postgresql-verification.json`;
- local `artifacts/phase2/verify_phase2.py`, enforcing exact temporary DB names.

All 29 tables matched before migration. Existing values in 28 tables outside migration history matched afterwards by original PK/columns, allowing additions. Created 1,661 legacy observations, 384 current unverified roles; 500 customer FKs populated. Cluster UUIDs/membership/explanations preserved. Temporary DBs dropped; source matched backup before/after.

## Executed checks

| Check | Result |
| --- | --- |
| PostgreSQL 17.6 | All 128 passed, including two concurrency tests |
| SQLite | 126 passed, two PostgreSQL-only skips |
| Models/migrations | No drift; system checks passed |
| Restored real-data migration | Existing values in 28 tables retained; source unchanged |
| Namesake migration fixture | Original references retained/new identities isolated/no false shared-director edge |
| JavaScript | Escaping/late-response/tooltips passed |
| Compose config | Six services valid; ingestion settings passed through |

Coverage: idempotence/full-partial-changed pages/DB failure/stage resume/independent checkpoints/priority/fallback/raw-normalised values/cache TTL-version/namesakes/verified IIN/foreign evidence/director change-reappointment/unknown-explicit absence/owners/service contacts/start race/expired-lease fencing. Unchanged enrichment preserves UUID/fingerprint/analysis time/text.

## Usage and limitations

Apply prepared migrations after checking a current backup: `uv run python manage.py migrate`. Docker migrate service does this. The source was not migrated during Phase 2.

Read status without external requests:

```powershell
uv run python manage.py ingestion_status
```

Live collection examples, not executed for phase verification:

```powershell
uv run python manage.py ingest_data --mode=initial --total=500
uv run python manage.py ingest_data --mode=update --total=500
uv run python manage.py ingest_data --mode=enrich --days=7
uv run python manage.py ingest_data --resume=<RUN-UUID>
```

`initial` continues traversal; each new update reads a bounded head window; full starts safely at page 1 without clearing. Resume by UUID. `--force` bypasses freshness/cache; start-page affects new runs; resume retains saved parameters.

Compatibility commands call the same service; new aliases initial. Enrichment checks stale companies including customers. `adata_updated_at` retains its legacy overall-success name; observations hold source states. Counters count processed records/attempts, not unique new entities.

Celery uses update and retries by UUID. Scheduled imports default off; concurrent starts return busy. Defaults: interval 1.5 seconds, source cache 900, lease 900 (minimum 60). HTTP/observation caches differ; UUID exposes progress/errors via CLI/admin.

No live markup/completeness verification. Bounded updates cannot find every old-contract change. Legal periods/verified IINs require actual sources. Legacy tax/court booleans are not fresh verified checks; tax observation/analysis belong to Phases 3/5.

Compose checked statically; daemon not running. Phase 1 stack check remains separate. KGD/snapshots/redesigned graph/DRF/React were not implemented in Phase 2.
