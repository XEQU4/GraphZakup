# Phase 4: graph state and interaction

Status: complete for the authorised Phase 4 scope; the user accepted the revised
graph prototype on 6 October 2026 and deferred further design/motion work to Phase 7.
Authorised on 6 October 2026. Phase 5 is not started. Final website design and
Bootstrap replacement await the user's references.

## Implemented behaviour

`apps/graph/evidence.py` builds one indexed evidence representation. A company
connects to a verified person or a normalised contact, instead of generating
company-pair cliques. Person identity requires the existing identifier/source
checks; names alone never create person links. Confirmed ownership is supported
when its observation verifies the owner's identifier. Unknown legal boundaries
remain unknown; roles ending on the evaluation date are excluded.

Contacts used by more than 20 companies are retained as weak evidence but do not
form groups. This threshold is an explicit conservative heuristic, not a
calibrated risk rule. Private contacts do not appear as relational graph edges.
Legacy company fields carry an 'External provenance unconfirmed' label when no
matching selected observation exists. Source links exclude query strings,
fragments, credentials and executable schemes. Public graph JSON does not
include IIN, raw responses or KGD credentials.

`EvidenceEdge` stores the current projection. `GraphSnapshot` stores membership,
nodes, copied evidence, algorithm version, evaluation date, hash and changes.
Snapshots and `ClusterLineage` have application-level immutable managers and
insert-only model saves; database administrators can still alter data through
raw SQL. New schema migration creates no invented graphs or observations.
An explicit first rebuild preserves old membership/text as a `legacy` baseline
with no invented edges, then publishes verified current evidence.

Rebuilds retain stable UUIDs: exact membership first, then greatest overlap,
Jaccard overlap and oldest record as deterministic tie breakers. One UUID
continues into one component. Merges retire other groups; splits can reactivate
an exact archived composition or create new UUIDs. Lineage preserves predecessor
versions and distinguishes merges, splits, retirement, reactivation and mixed
transitions. Old UUIDs remain readable.

`GraphInputState` detects semantic changes. Impact closes over old/current
features and active group membership; archived memberships do not widen current
recalculation. Detected dirty inputs outside the requested selection are included
rather than silently publishing an inconsistent boundary. Index construction
still reads all companies/roles/business inputs; publication is limited to
verified affected components. This is not a fully incremental ingestion index.
A PostgreSQL advisory transaction lock serialises graph builds. Evidence,
membership, snapshots and lineage publish in one transaction.

Unchanged inputs cause no INSERT/UPDATE/DELETE. Retrieval times and observation
IDs alone do not change a graph hash; the original published observation remains
referenced. Changed private business facts mark the legacy explanation stale
without creating an unchanged graph version. Graph/source changes also mark
saved text stale. Saved text is preserved, with no asserted explanation-to-graph
binding; `legacy_explanation_fingerprint` stays empty. Phase 5 supplies analysis
versions and validated generation. The deterministic compatibility explainer now
reads saved graph evidence and omits unsupported legacy owner-debt assertions.
The current matching score remains a legacy heuristic, explicitly labelled as
such; it is not an assessment of wrongdoing.

## Interface

The revised D3 prototype uses coloured company cards with BIN, distinct person
and contact shapes, a subtle background grid, relationship colour/shape legends,
wrapped labels and full names in inspection. Role links are solid and weak
contacts dashed. It adds smooth focus/fit transitions, selection highlighting
and restrained motion, respecting reduced-motion preferences. Colours are
specific to this graph prototype; the overall website remains awaiting references.
It provides search, neighbour highlighting, relationship filters,
zoom/pan/fit/reset, pinning/freeze, evidence/source/interval inspection and
shortest paths under the current filters. Counters show companies, people,
contacts and relationships. The inspector lists connected companies, source
quality, confidence and intervals. Paths are labelled separately from
direct relationships. Node and edge selection support Enter/Space; nodes support
P for pinning; the graph region supports arrows and +/- for pan/zoom. Inspector
and search results are text nodes, including untrusted names.

History selection reads immutable versions. `GraphViewState` saves coordinates,
pins, zoom, filters and selection per signed-in user; anonymous views use local
browser storage. Old coordinates are retained and new nodes start near saved
neighbours with a spatial placement grid. Personal state never affects graph
hashes. Saving an old snapshot or an obsolete view revision returns HTTP 409.
Coordinates and references are validated; writes require session authentication
and CSRF. Historical views must open the current version before server-side save.

Group/detail/data/view GETs read results and never rebuild or generate text.
A staff-only POST requests a deduplicated `GraphRebuildJob`; Celery is enqueued
only after commit. Broker failure remains visible. The task uses saved data,
shares the ingestion lease and fences atomic publication. Expired jobs can be
explicitly requested again. There is no new beat schedule, collection request,
KGD request or paid generation. The existing ingestion cluster stage and
`build_clusters` call the same core service. The command also acquires the lease.
The old `build_graph_data` company-pair helper remains for compatibility callers
and tests; production group pages no longer use it.

## Preservation

Before schema/algorithm changes, a fresh backup was independently restored and
all 38 public tables, including migration history, matched. Report:
`artifacts/phase4/database_20261006T114348Z_9961d171.json`.
Dump SHA-256: `2a46400bfe2e30b0d061f2407d5350fd52cc950fc9f0fda5ae28be9dcc9b8a2d`.
The verification database was dropped. Working data is never used for trials.

The isolated PostgreSQL protocol restores the dump again, upgrades the copy,
compares all original columns/rows by their original primary keys, runs tests in
another generated database, checks working tables before/after and drops both
created databases. The working database is neither migrated nor rebuilt here.
The retained Phase 3 KGD evidence database is not touched.

## Verification

- Initial full offline suite: 189 tests passed on SQLite (two PostgreSQL scenarios
  skipped) and all 189 passed on PostgreSQL after correcting nullable-join row
  locking and a test that assumed sequence IDs started at one.
- The final full suite passed all **191 tests on PostgreSQL**, including the
  archived-membership impact and empty-legacy retirement regressions. All 38
  working tables matched the backup before and afterward; all 37 original tables
  outside migration history retained their original values after copy migration.
  New graph tables were empty after migration. Both generated restore/test
  databases were removed. Report: `artifacts/phase4/postgresql-verification.json`.
- Graph scenarios cover repeat/no writes, additions, private fact changes,
  unrelated and independently dirty components, immutable history, legacy
  preservation, merge/split/reactivation, rollback after lease loss, 1,000 mass
  contacts, threshold crossing, confirmed ownership, temporal non-overlap,
  provenance changes and unchanged retrieval reuse.
- View/job scenarios cover read-only history, unknown versions, saved positions,
  isolated users, stale graph/revision conflicts, invalid/nonfinite coordinates,
  CSRF/auth/staff permission, deduplication, post-commit enqueue, saved-data tasks
  with HTTP blocked and broker failures.
- `node tests/frontend_regressions.cjs` passed search/stale-response/security and
  graph literal-tooltip checks. `node tests/graph_interactions.cjs` passed path
  filters, missing paths, coordinate reuse/new nodes, invalid coordinates, long
  labels, safe links and 8/50/500-node synthetic helper scenarios. These are not
  browser rendering or responsive visual checks.
- An in-memory synthetic benchmark with 10 companies per contact produced equal
  memberships. At 2,000 companies, old all-pairs grouping made 1,999,000 comparisons
  and took 2.192459 seconds; indexed grouping took 0.005881 seconds. This is one
  local algorithm measurement, not an ingestion/database/UI benchmark. Report:
  `artifacts/phase4/grouping-benchmark.json`.

- Static manifest collection succeeded in an ignored test directory; the graph's
  CSS and JavaScript were present. Migration drift checks reported no changes.
  Protected SHA-256 hashes of `test.py`, `pyproject.toml` and `uv.lock` matched
  their phase-start values.
- A private scan checked 187 project deliverables against configured credentials
  and found zero credential values; output contained counts only.

Browser automation inventory exposed no browser; opening `iab` and `chrome`
returned 'Browser is not available'. A localhost-only server used an ignored,
separate synthetic SQLite fixture containing 8-, 50- and 120-company graphs.
The user reviewed the 8-company example, rejected the initial monochrome
prototype, then approved the revised colours/forms/motion and asked to leave
further polishing until Phase 7. This is manual appearance acceptance, not an
automated browser, dense-graph or responsive visual test. Those independent
visual checks remain unverified; helper/HTTP tests are stated separately above.
Fixture URLs and database path are in `artifacts/phase4/ui-fixture.json`.
The temporary demonstration server was stopped after the review; the private
synthetic fixture was retained. It can be reopened locally with
`python manage.py runserver 127.0.0.1:8765 --noreload --settings=artifacts.phase4.ui_settings`
while that ignored fixture remains available. This is not a deployment command.
D3/Bootstrap are still supplied by existing external CDNs; the graph displays a
read-only fallback when D3 fails to load. Final design awaits user references.

## Applying the prepared change

After checking a current verified backup, the user applies migrations and
rebuilds from saved data deliberately. For a local environment:

```powershell
.\.venv\Scripts\python.exe -B scripts/backup_database.py --pg-bin 'C:\Program Files\PostgreSQL\17\bin' --verify-restore
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py build_clusters
.\.venv\Scripts\python.exe manage.py runserver
```

`build_clusters --company-id <id>` can be repeated for a selected impact seed;
other detected dirty inputs are still included. It performs no source fetching.
For Compose, rebuild/start the image and let its migration service finish. The
worker registers graph tasks through `apps.graph.tasks`; staff can then request
recalculation from the group page. No automatic graph job was added.

Until this explicit rebuild, migrated legacy groups show 'not calculated' and
retain their original UUIDs/texts. `test.py`, the dependency files and `.env`
are not part of the phase edits. Git commands remain the user's responsibility.
The user accepted the current graph prototype; start Phase 5 only after a separate
instruction. Continue final graph/interface design and animation work in Phase 7.
