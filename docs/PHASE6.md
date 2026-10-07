# Phase 6: versioned DRF API

Completed on 7 October 2026. Django models/admin and legacy pages remain available
until React replaces their scenarios in Phase 7. No domain schema, graph/rule
algorithm or working data changed. Phase 7 requires a separate instruction and
user references; Russian localisation follows the completed English interface.

## Implemented contract

The JSON API lives at /api/v1/. Swagger at /api/v1/docs/ uses locked local sidecar
assets; /api/v1/schema/ serves the validated OpenAPI contract. Dependencies are
DRF 3.17.2, drf-spectacular 0.29.0 and sidecar 2026.10.1; existing dependency
versions were preserved. Responses use typed allowlists, exact Decimal strings
and a stable error envelope: error.code, error.message, error.details.

| Routes under /api/v1/ | Behaviour |
| --- | --- |
| companies/, people/, contracts/ and numeric detail | Saved entity projections; people omit IIN/scope keys and unverified legacy history |
| directorships/, ownerships/ | Company/person filters, identity reliability, dates and nullable legal applicability |
| clusters/ and UUID detail | Saved current versions, activity, review priority; no legacy score masquerading as current analysis |
| clusters/{uuid}/snapshots/, snapshots/{id}/ | Immutable history and merge/split lineage |
| clusters/{uuid}/graph/?version=N | Current or exact saved graph; no rebuild |
| clusters/{uuid}/analysis/?version=N&analysis_version=M | Saved analysis/text, explicit ready/stale/not_calculated state |
| clusters/{uuid}/analyses/ and version detail | Exact saved analysis histories |
| clusters/{uuid}/analyses/{version}/explanations/ and ID detail | Published saved text/template histories; old texts are preserved |
| snapshots/{id}/evidence/ and reference detail | Snapshot-scoped copied references and safe observation metadata |
| clusters/{uuid}/view/ GET/PUT | Authenticated user's own view; optimistic revision and exact snapshot/hash fencing |
| clusters/{uuid}/recalculate/ POST | Staff-only deduplicated job from saved evidence |
| clusters/{uuid}/explanations/ POST | Staff-only deduplicated/fenced analysis request; model use must be explicit |
| jobs/graph/{uuid}/, jobs/analysis/{uuid}/ | Staff-only stored status and exact result versions |
| jobs/ingestion/ and UUID detail | Staff-only saved operational status; no collection-start endpoint |
| explanations/{id}/experimental-estimate/ | Staff-only separate unvalidated model estimate |
| session/, session/login/, session/logout/ | Same-origin session bootstrap, CSRF-protected login/logout |

Lists default to 25 records and accept page_size 1..100. Query fields, ordering,
dates, identifiers and duplicate parameters are validated; unsupported fields
are rejected. Search is bounded to 100 characters. JSON request bodies are
bounded to 128 KiB; deeply nested/invalid JSON and excessive query fields return
client errors. Serializers/select_related/prefetch/subqueries avoid entity-list
N+1 queries. Whole graph payloads and historical evidence extraction still scale
with the selected saved snapshot; no large-graph performance guarantee is made.

Public reads match the local thesis site's existing access model. Authenticated
users may save their own views; only staff may start/read operational jobs and
read experimental estimates. Source options, credentials, raw/normalised
observations, personal IIN and experimental values are excluded from public
projections. Company BIN and original names/source labels remain unchanged.
Safe source links suppress query credentials and personal-ID locations. This is
not a public-startup access/data-release policy.

Session bootstrap returns a CSRF token and sets the csrftoken cookie. Send that
token as X-CSRFToken with cookies on writes. Anonymous login also requires CSRF;
successful login rotates it. Session responses are not cacheable. Login has a
10/minute IP limit and ignores untrusted X-Forwarded-For (NUM_PROXIES=0). The
current local-memory limiter is process-local; shared production throttling and
trusted proxy configuration require later operational work. Accounts are managed
through Django admin; there is no registration endpoint.

Job bodies reject unrecognised fields, credentials, provider URLs and date
changes. Explanation POST defaults to use_model=false; true uses only existing
server provider/paid gates. retry_model=true requires use_model=true. POST starts
work through existing services/on_commit dispatch, not views. Repeats reuse jobs;
failed enqueue returns a safe pollable 503. Graph requests reject inactive/empty
groups and more than 500 selected member seeds; existing dirty-impact processing
may still inspect a wider dataset. GET never dispatches or updates domain state.

Company KGD projections distinguish a failed latest attempt from retained dated
success; mixed/future reporting dates follow existing analysis validation. Missing
checks are not zero debt. Legal role intervals with missing boundaries are
unknown, independently of identity verification and observed current flags.

## Verification and preservation

A fresh backup was independently restored with all 50 public tables and migration
history matching. Report: artifacts/phase6/database_20261007T093012Z_af7436d0.json.
Dump SHA-256: cc084d7e345583036da4cb66cf557ffa6042d904b569ccaef0ec9e44a82f22fd.
Another isolated restore/migration retained original values in all 49 tables
outside migration history. The complete 320-test suite passed on PostgreSQL,
including exact large Decimal output, concurrency, saved history, CSRF, permissions,
view conflicts, dispatch deduplication/failure and public-data projections. Both
owned verification databases were dropped; all 50 working tables stayed unchanged.

OpenAPI generated and validated with --fail-on-warn without warnings. Static
manifest collection included locally bundled Swagger assets. Migration drift
reported no changes. Both Node regression suites and Compose config --quiet
passed. Compose validation is not a new container-startup test.

A copied synthetic SQLite demo served 16 real HTTP reads and preserved every
table after GET. Anonymous private reads and invalid query/version errors were
checked. Playwright loaded Swagger, its schema and all assets from localhost;
Try it out executed a company GET with HTTP 200 and no JavaScript errors. Browser
checks do not establish new graph drag/touch/large-screen performance results.
The owned probe server on 8768 was stopped; the user's 8766 demo was untouched.

Private reports/screenshots/helpers remain in ignored artifacts/phase6/. The
final source/documentation scan found no configured credential values; its
file count and result are recorded privately. .env and test.py hashes
matched; existing dependency versions were retained. No live parsing, ingestion
pipeline, paid/local inference, working migration or recalculation was performed.
New job dispatch tests use mocks; live broker execution remains covered only by
previous phases, not a new Phase 6 end-to-end worker check.

## Running

No new environment variables or migrations are required. Install from uv.lock and
restart Django, or rebuild the existing Compose stack. Swagger is available at
http://127.0.0.1:8000/api/v1/docs/ with the normal local server. User actions and
Git commands are supplied directly in chat; do not require these notes to finish.

Primary references: [DRF authentication/CSRF](https://www.django-rest-framework.org/api-guide/authentication/),
[DRF pagination](https://www.django-rest-framework.org/api-guide/pagination/),
[DRF release compatibility](https://www.django-rest-framework.org/community/release-notes/),
[drf-spectacular schema and local UI assets](https://drf-spectacular.readthedocs.io/en/stable/readme.html).

## Working-data and native startup follow-up, 7 October 2026

The existing PostgreSQL contains 777 companies, 500 contracts and four active
clusters covering 11 companies, with eight snapshots and four saved analyses/
explanations. All 68 migrations are applied. Nineteen bounded domain API GETs
returned 200 under PostgreSQL READ ONLY; all 50 table fingerprints stayed equal.
The normal API uses this dataset; the 8766 AI probe remains a separate synthetic
demo. No import, migration, source request, model job or graph refresh was run.

Legacy migration observations do not independently verify original parser
provenance. Current links are contact-based; no identifier-confirmed common
director/owner or working KGD result is present. Existing template 5.0 texts remain
immutable; a 5.1 presentation refresh requires an explicit job. The inventory is
private at artifacts/data-followup/inventory.json.

Swagger failed with DEBUG=false because local static collection lacked the new
sidecar entries. collectstatic rebuilt the actual manifest; a fresh owned server
using normal settings/read-only working PostgreSQL served Swagger, hashed assets
and real entity lists with 200 and no Swagger JavaScript errors. The largest saved
graph rendered six nodes; its unrelated favicon request returned 404. The owned
8769 server was stopped. Restart existing servers after collecting static assets.

Windows file logging now appends to dated app/error files under native process
locks instead of renaming shared open files. Ten logging tests include real Django
startup and complete concurrent Windows records across simulated midnight; two
Swagger regressions use strict manifest storage and collected assets. The full
offline suite ran 328 tests, passing with four PostgreSQL-only checks skipped.
Migration drift reported no changes. POSIX locking/network filesystems were not
verified in this Windows follow-up. Generated logs are ignored; old active logs,
.env, test.py and the Celery schedule file are preserved.
