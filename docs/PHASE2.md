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


## Parser and saved-data audit, 8 October 2026

The user authorised this follow-up after the cluster-directory review. The
working PostgreSQL database was inspected read-only after a freshly verified
backup (see RECOVERY.md). It contains 777 companies and 500 contracts, with no
duplicate company BINs or non-null contract registry IDs. All 1,661 observations
and 4,311 selected facts are legacy/unconfirmed, without external source URLs.
The 384 existing enrichment timestamps are from 20 June; migration timestamps
must not be presented as fresh checks. All 768 person identities are unverified.
The 384 repeated-name groups occur within individual companies' historical and
current records; there are no cross-company name groups. No ownerships or working
KGD results are saved. The audit did not merge, delete or rewrite these records.

Implemented corrections:

- Strict amount grouping, phone characters and external identifiers prevent
  malformed values from silently becoming valid data.
- Contract party tables are bounded by their own sections; duplicate page IDs,
  repeated complete pages and external IDs rebound to another contract number
  are rejected. Resume retains the page guard and confirmed cursor.
- Registry absence requires a recognised results table. Ambiguous company IDs
  are rejected. Director names require an explicit leadership label/section;
  Adata title advertising and registry contact-person names are not leadership.
- Role refresh keeps source references aligned and is atomic. Foreign/failed
  evidence cannot replace roles; invalid merged legal intervals are rejected.
  Older same-source updates fail, while older other-source replay retains newer
  roles. Unchanged facts retain the graph version. Existing identity reuse skips
  namesake candidate rescans (4 queries versus 29 in the 13-namesake fixture).
- The observation cache only reuses the latest matching company attempt with
  the required parser version. Company/contract parser provenance is now 2.1;
  KGD is 3.2 because its shared amount validator also changed. Old observations,
  graphs and explanations remain immutable.

The read-only `audit_data_quality` command reports aggregate saved coverage,
provenance, repeated-name scope and credential configuration without identifiers,
personal values or tokens. Missing saved attempts do not prove that historical
fetching never occurred. Configuration presence does not verify access rights.

Live markup, fresh company records and broader KGD entitlement remain unverified.
No live collection, pipeline, schema migration or inference was run. Verification
reports and the database backup are private under `artifacts/parser-quality/`.

Verification: all 458 tests passed on an isolated PostgreSQL database with no
failures, errors or skips, including 45 new regressions. The first full run exposed
a SELECT-only test assertion that did not recognise PostgreSQL cursor reads; it
was corrected and both targeted and full PostgreSQL runs passed. Migration drift
check found no changes. The actual audit command also passed against read-only
working PostgreSQL. All 50 working-table fingerprints and protected files matched
before and after; all owned test databases were dropped. Existing immutable
results were preserved. Reports: `artifacts/parser-quality/postgresql-tests-latest.json`
and `command-verification-final.json`. Live source availability was not tested.


## Authorised live validation, 8 October 2026

The user authorised using existing company identifiers. The bounded sample covers
all 11 members of the four active groups plus one configured KGD control. Across
diagnostic and final checks, 72 HTTP attempts were made without automatic retries;
no new contract import, scheduled collection or model inference was run.

Company/contract parser 2.2 uses the official old.goszakup.gov.kz registry host
after verifying the original host redirect. Redirects remain disabled and KGD
credentials remain restricted to the KGD host. Blank alternative BIN/IIN cells
are ignored only when another exact valid identifier exists. Optional website
normalisation preserves raw text and does not fetch or verify that website.
Adata supports public JSON-LD with explicit identity binding, duplicate-key and
conflict rejection, and separately evidenced leadership roles. An absent title
identifier requires both exact structured identifiers and the canonical profile URL.

Explicit enrichment freezes a bounded company/source selection, honours --total,
--company-bin and repeated --company-source, and checks each source status, age
and parser version. Resume retains that selection. Updating one source alone
does not advance the legacy overall enrichment timestamp.

Final accepted evidence: 11 registry profiles, 11 Adata profiles, one Adata 404,
and three KGD taxpayer/arrears pairs (29 observations for 12 companies). One
registry search returned two distinct supplier cards for the exact identifier;
it remains ambiguous and was not resolved by choosing a card arbitrarily. Failed
attempts and original captures remain in the isolated evidence database and
ignored artifacts/parser-live/. Reprocessing preserves capture times, including
one explicitly recorded bounded capture-time approximation.

All 495 PostgreSQL tests passed with no failures, errors or skips. The test
database was removed and all 50 working tables/protected files matched before
publication. Public contract-list markup was checked; live contract-party cards
and a new contract import were not exercised. See the publication record below
for actual working-data changes.

### Working-data publication

After a second restored-copy rehearsal, the same frozen 29 observations were
applied to the 12 working companies in one transaction, without HTTP or inference.
One final graph/analysis refresh created three snapshots and matching saved
analyses/templates. All original snapshots, analyses, model texts and four group
UUIDs remain. One five-member phone group now has four members: both fresh
sources agree on the removed company's new phone, different from the old shared
legacy value. The previous five-member snapshot remains readable.

All 765 unrelated companies, 500 contracts, accounts and personal views were
preserved. Eleven current source-scoped director records remain unverified;
22 same-company matching candidates do not merge identities. No legal role
periods or ownerships were invented. Copy replay created no additional graph,
analysis or text versions on repetition. Twenty-six public API GETs passed on
both the final copy and committed working data without changing any of 50 tables.
Publication report: artifacts/parser-live/reviewed-promotion-ff2def157f7c42978f72a4529e46503c.json.

This is a verified 12-company refresh, not freshness certification for the whole
777-company catalogue. Failed/ambiguous live attempts remain in the isolated
audit evidence; only accepted observations were published. New templates are
labelled as templates; older model prose was not copied onto changed evidence.

Post-publication aggregate audit: 109 of 4,313 selected facts now have successful
source evidence; 4,204 remain legacy/unconfirmed. There are 1,690 observations,
779 unverified person identities and 384 current unconfirmed director roles.
No duplicate BIN/external contract ID, foreign selected fact, source-role mismatch
or future retrieval was found. The private audit used scrubbed settings, so its
configuration subsection is not a statement about actual credentials. A new
backup passed independent restoration after publication; see RECOVERY.md.

## Fifty-company expansion, 8 October 2026

A frozen next-50 selection excluded the earlier twelve companies. Public sources
returned 48 Adata successes, one confirmed not-found and one temporary failure;
the registry returned six successes, three ambiguous matches and 41 unavailable
results (22 skipped after stopping that host). Repeated HTTP 302 responses had
empty bodies; one later bounded diagnostic returned 200. Their destination/cause
was not established. No redirects were followed. The interrupted capture resumed
from saved source results without repeating completed requests.

49 companies gained at least one successful source observation; five runs
completed both sources and 45 remain partial. This is not complete verification
of all fifty companies. The remaining 715 companies were not attempted in this
batch. Production transport now stops a host after three consecutive failed
operations, immediately on access denial/challenge/rate limiting, while leaving
other hosts available. A new run is needed after addressing/waiting out the cause.

After restoring the current backup, offline replay and preservation checks passed.
One transaction published 100 company-source outcomes plus one verified KGD IP
registration, retaining real retrieval times and failed-attempt distinctions.
Normal ingestion services selected facts; one final refresh created five new
graphs/analyses/templates, bringing active groups to nine. Original immutable
histories, all contracts, accounts and the user's latest layout were preserved;
726 companies outside the 50-plus-existing-IP selection were unchanged. Repeating
the final refresh on the copy created no versions. No model inference occurred.

505 PostgreSQL tests passed without skips. All 80 working API reads passed with
50 table fingerprints unchanged. Reports/captures: ignored
`artifacts/parser-expansion/`; the restored rehearsal database was dropped.
Automatic collection remains disabled. Continue from the saved selection rather
than blindly retrying every partial run or treating migration dates as freshness.

## User-authorised continuous collection, 8 October 2026

The user requested improvements to the real parsers and unattended collection.
`ingestion.background` now owns bounded independent stages called by Celery and
`collect_background`; parser adapters remain ORM-free. Separate cycle/pipeline
leases, persisted due times/host pauses, oldest-attempt-first selection, six-hour
failed-record delays and a 120-attempt transport budget prevent monopolised or
unbounded cycles. Contracts-only runs no longer walk the entire company catalogue.
Accepted partial data is followed by one fenced graph/template refresh; pending
company seeds survive an interrupted refresh. No automatic model generation.

Parser 2.3 recognises Adata's observed Latin-P leadership label and explicit name
parts. Offline parsing of 48 captured pages recovered 28 labelled directors;
no current owners were inferred from founder strings, which matched the director
where both were present. Contract party pages are fetched only for the selected
slice. Invalid/missing participant identifiers leave unresolved contract issues
while valid records in that slice can commit atomically; network failures still
stop without advancing that page. Skipped records count against the slice budget
and remain partial, not silently successful. Later head scans can retry them;
this is not exhaustive historical or tender-participant collection.

The native Windows helper starts/stops one owned solo worker on `ingestion` and
one persistent beat, with private logs and PID/start-time checks. Stop/restart was
verified, including Windows PowerShell JSON-array handling. An initial probe
encountered a pre-existing legacy task in Redis; it failed before contract writes.
The final helper excludes that default queue and leaves its messages untouched.
One real bounded iteration completed 4 registry profiles, 5 Adata profiles and
2 KGD registration checks, with a partial contract stage and one ambiguous company.
The later party-quarantine improvement passed isolated tests; its successful live
contract-import path remains to be confirmed on a scheduled attempt. Subsequent
due-time checks made zero HTTP calls and created no graph versions.

Compose now routes ingestion to the worker and offers `docker-compose.full.yml`
for explicit collection plus Ollama/Qwen. Configuration validates; full image/model
execution is not claimed. The local .env is unchanged. Working data now changes
through the authorised background service; pause it before a data-changing code
change or backup comparison. Reports/backups: `artifacts/background-verification/`.

Final gate: 524 isolated PostgreSQL tests passed without skips; complete Compose
configuration validated. The final 2.3 worker then completed five additional
Adata checks with five HTTP requests; a duplicate queued cycle made zero requests
and created zero versions. Exactly one actual worker and beat remain running.
The helper's Status retains prior source outcomes even when the last tick waited.
No new working contracts are claimed yet (catalogue remains 777/500); the registry
stages retain their saved cooldowns. The user's environment, dependency locks,
learning files and next-app fingerprints remained equal.

## Operational verification, 9 October 2026

At 10:21 Asia/Qyzylorda, the scheduled parser 2.3 run imported 25 real contracts
without skips and added 36 companies: 813 companies and 525 contracts total.
Four of five registry profiles, five Adata profiles and two KGD registrations
succeeded. One registry identity remains ambiguous. Duplicate BINs, duplicate
contract registry IDs, missing customer links and customer identifier mismatches
were all zero. A duplicate tick made no requests or new graph/analysis versions.
KGD coverage is eight taxpayer registrations and three zero-arrears results
dated 8 October; owner-history coverage is absent. Registry/Adata latest success
coverage is only 25/73 companies; broad legacy-data gaps remain.

Eight API projections passed through the normal-settings Django client inside a
read-only PostgreSQL transaction. No live HTTP/browser success is claimed because
port 8000 was unavailable. The prior 524-test report was reviewed, not rerun.
Both owned background processes remain running. This confirms the previously
unverified live contract path, not exhaustive backfill or full production readiness.
Private read-only audit: artifacts/background-verification/current-audit.json.
