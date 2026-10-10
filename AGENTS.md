# Instructions for working on IZ2

This project is a thesis system for analysing relationships between participants in Kazakhstan's public procurement, with a possible later pilot. Requirements and workflow are in [docs/ROADMAP.md](docs/ROADMAP.md), the target architecture is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and the original findings are in [docs/AUDIT.md](docs/AUDIT.md).

Brand: IZ2; package and GitHub repository: iz2; intended future domain: iz2.kz.
The user supplied the original scope: relationship evidence combined with verified
company/person history and plain-language explanations. Court, bankruptcy and
restricted-participant integrations remain planned; legacy flags do not establish
verified findings. Do not start those sources or Phase 8 automatically.
Keep existing database/volume identifiers, GPG compatibility settings and the
graph-view storage key when rebranding. Compose pins its legacy default namespace
so renaming the local directory does not select empty replacement volumes.
The follow-up local AI check passed four real synthetic cases; the model/demo
servers were stopped afterwards. `scripts/local_ai.ps1` starts/stops an owned
native server, and `scripts/check_local_ai.py --serve` checks real inference on
synthetic data. `--serve-saved` opens cached demo results. Neither probe loads
working credentials/data or requires Redis. Main application settings remain
unchanged and default to templates until the user explicitly enables a model.
The explanation follow-up uses saved `readable-explanation-5.1` documents with a
short summary, evidence meaning, credited points, follow-up checks and aggregated
coverage. Prompt/template versions are 5.1; rules and analysis hashes remain 5.0.
Preserve old immutable texts: GET never rebuilds a document, and updating the
presentation requires an explicit job or a fresh synthetic demo. Technical
metadata is collapsed. `--report-name` isolates probe reports from the user's
last demo. Final visual design remains Phase 7 work.

## Workflow and language

- Read the roadmap and documents for the current phase before starting a task. Complete the assigned phase; do not start the next one automatically.
- Distinguish implemented behaviour from proposed designs. Update a phase's status only after meeting its acceptance criteria and checking the result.
- The user runs Git commands. Do not run Git commands, create commits, branches or pull requests, or push changes without a separate instruction.
- The user does not read Markdown instructions. Put all required user actions, exact commands, environment changes and suggested Git commands directly at the end of each final response in execution order. Do not require opening a document to finish a phase; keep repository records concise for task continuity.
- Preserve the user's changes. `test.py` contains learning exercises, not application tests. Do not repurpose it for this project.
- Use English for project documentation, instructions, code comments, CLI messages, generated explanations, prompts, and proposed commit messages. English remains the default UI language; the user explicitly authorised an EN/RU website switch on 10 October 2026. Save decisions in the repository so the next task can continue without chat history.
- Preserve the verified English interface when adding Russian localisation. Keep official source labels, identifiers and original data in their source language; translating parser selectors would break data collection. Interface language never changes identity rules, review scores, business dates or immutable stored explanation text.

## Data and safe changes

- Before changing a schema or algorithm that can affect saved data, check for a current backup and verified restoration in [docs/RECOVERY.md](docs/RECOVERY.md).
- Do not run `import_contracts --mode=full`, data cleanup, live parsing, the Celery pipeline, or paid generation to verify refactoring. These require an explicit user instruction. Use fixtures and a separate test database.
- Test migrations and imports on an isolated database. Do not delete the source database or use it for trial restoration.
- Do not put passwords, tokens, `.env`, dumps, or original responses containing personal data in documentation, test fixtures, Git or Docker images. Local backups and reports belong in the ignored `artifacts/` directory.
- Parsers fetch and normalise data; ingestion services own persistence and stage orchestration. Do not add separate orchestration to views or management commands.
- Parse money as `Decimal` from a string. Distinguish a missing result, a temporary source failure, and confirmed absence of a finding.
- Phase 3 is complete for its implemented services: two authorised requests verified taxpayer identity and a complete zero-arrears response for one company in an isolated database; see [docs/PHASE3.md](docs/PHASE3.md). The first credential works as `X-Portal-Token`, and the second ISNA credential was accepted as `personalAccountToken` for the selected check. Parser `3.1` fixed the returned reporting timestamp format; offline reprocessing preserved retrieval times and the failed attempt. Keep checks disabled without credentials, preserve company-specific last successes, and do not infer negative checks from unavailable data. Broader company entitlement, quotas and unverified source variants remain operational limits. No automatic KGD pipeline or Phase 4 work is authorised by this status.

## Graphs and explanations

- Do not merge people by name alone. Similarity creates a matching candidate with evidence and confidence.
- Relationships must have a source, evidence and temporal applicability. Company debt belongs to the company and is not automatically assigned to its owner.
- Use the same saved evidence for the graph, rules and explanations. A weak shared contact alone does not establish a violation.
- Preserve stable cluster identifiers and version history. Repeated collection without meaningful changes must not recreate the graph or explanation.
- An LLM presents prepared facts and rule results. Identity, relationships and public review priority are computed by verifiable algorithms. Provide a saved template when the LLM fails. The user authorised considering model scoring if better: keep it as a separate blinded experimental estimate until independent evaluation demonstrates benefit; never silently promote it.
- GET reads saved results. Start generation and recalculation through authorised background tasks with deduplication and result-version checks.

## Interface and verification

- Phase 4 must substantially improve graph presentation and interaction: readable labels, neighbour highlighting, relationship filters, evidence inspection, convenient navigation and saved layouts.
- Phase 4 was completed on 6 October 2026: indexed evidence, immutable snapshots/lineage, personal views and explicit background recalculation. All 191 PostgreSQL tests passed; copy migration preserved original values and working data stayed unchanged. The user accepted the revised coloured graph prototype and explicitly deferred further graph/interface design and animation work to Phase 7. Its palette is provisional. Automated browser/dense/responsive visual checks were unverified at phase completion; the bounded 7 October follow-up is recorded in [docs/PHASE4.md](docs/PHASE4.md). Working data was not migrated or rebuilt during implementation. Read stored snapshots on GET. Do not start Phase 5 automatically.
- The user will provide overall UI/UX references. Do not finalise the site's visual style, palette or Bootstrap replacement before receiving them.
- Phase 5 was completed on 7 October 2026: immutable analysis/text histories, capped review-priority rules, atomic graph/template refresh, explicit deduplicated model jobs and latest-request fencing. All 238 PostgreSQL tests and five real local Qwen3:4b synthetic cases passed; original values in 44 restored-copy tables were preserved and the 45 working tables stayed unchanged. The default is template-only; Ollama is the free local option, with configurable paid APIs gated off. Model output selects finding order/wording variants, not arbitrary prose. Optional blinded estimates never replace public scores; independent prediction/readability benefit and local-ai container startup/GPU use remain unverified. The owned temporary model server was stopped; portable runtime/cache remain under ignored artifacts. Read [docs/PHASE5.md](docs/PHASE5.md) for setup, measured latency and limits. Working data was not migrated or recalculated. Do not start Phase 6 automatically.
- Verify changed behaviour in every phase. Imports, migrations, identity, graph versions and AI require meaningful tests; syntax checks are not a substitute.
- Do not report checks as successful without running them. Distinguish static analysis, offline tests and live-source checks.
- Report changed behaviour, completed checks and remaining limitations. For environment restrictions, first distinguish a sandbox error from a defect in the project.

## Browser verification follow-up

On 7 October 2026, user-configured Playwright MCP checked cached synthetic two-
and twenty-company pages in isolated Chrome at desktop and narrow viewports.
Search, filters, evidence, anonymous layout save/reload/restore and mobile menu
passed; no application JavaScript exception was observed (favicon 404 only). Desktop-saved
zoom needs Fit after narrowing the viewport, dense mobile labels are small,
singular counters are incorrect and the mobile menu toggle is unnamed. Summary
copy remains generic; the saved-analysis link opens JSON. Track these for Phase 7
without treating the current prototype as final design. Drag automation timed
out; authenticated storage, physical touch and larger browser performance are
unverified. Report and screenshots stay in ignored artifacts/browser-check/.
No application code, working data or saved explanations changed in this check.

## Phase 6 completion

Phase 6 was explicitly authorised and completed on 7 October 2026. apps/api owns
versioned /api/v1 JSON projections, typed immutable histories/evidence, own-view
revision fencing, session bootstrap/CSRF login and staff-only explicit jobs/status.
Swagger/schema assets are locally bundled. All 320 PostgreSQL tests passed;
restored original values and all 50 working tables were preserved. Sixteen real
synthetic HTTP reads and browser Swagger GET passed. No new schema/rule change,
source collection, inference or working recalculation was run. GET must keep
reading saved domain state; public projections omit IIN/raw observations/model
estimates. Model POST defaults to template and cannot override server settings.
No HTTP ingestion-start route exists. .env/test.py and existing dependency
versions remain unchanged. The temporary owned API server on 8768 was stopped;
user-owned server on 8766 was untouched. Details in docs/PHASE6.md; private verification in
ignored artifacts/phase6/. Login throttle is process-local and ignores untrusted
forwarding headers; production/shared throttling and public release policy remain
later operational work. Phase 7 requires separate authorisation and user UI/UX
references; do not start it automatically or finalise the design now.

## Working-data and local startup follow-up

On 7 October 2026, the existing configured PostgreSQL was inspected read-only:
777 companies, 500 contracts, four active clusters/11 member companies, eight
snapshots and four saved analyses/explanations; all 68 migrations applied. All
50 table hashes stayed equal across 19 domain API GETs. Use the existing working
API for the frontend; the AI probe on 8766 is synthetic and separate. Legacy
provenance is not freshly verified; no working KGD results or verified shared
person roles exist. Existing template 5.0 texts stay immutable until an explicit
presentation job; do not regenerate them on GET.

Native local startup requires collectstatic after dependency/static updates and
a server restart; default strict manifest storage stays enabled. The actual
manifest and normal-settings Swagger were checked on an owned read-only server,
now stopped. Windows logging uses native process locks and dated file appends
without shared-output rename. The 328-test offline follow-up passed with four
PostgreSQL-only skips; actual Windows startup/concurrent logging and strict static
regressions passed. POSIX/network-share locking remains unverified. Details:
docs/PHASE6.md; private reports: artifacts/data-followup/.

## Phase 7 frontend scope

On 7 October 2026 the user explicitly authorised React with supplied UI references:
serious blue design, restrained cyberpunk details and expressive motion. The user
deferred explanation rewriting and further graph design until after this frontend.
English React supports the existing saved dataset and same-origin session API;
Django serves /app/ and retains /legacy/ compatibility. Node builds are integrated
into Docker. React Bits/Magic UI source licenses and dependency notices are retained.
Use Vite original hashed entry URLs, not storage.url extra hashes, so lazy imports
share one React root/context. GET must remain domain-read-only. Do not silently
rebuild old 5.0 explanations. User visual acceptance is pending; see docs/PHASE7.md.
No Phase 8 or Russian localisation is authorised automatically. The user still runs
Git. Required next-step commands must be given directly in final responses.

Phase 7 technical checks: 338 isolated PostgreSQL tests and 35 React tests passed.
Normal-settings browser checks covered 390/768/1440/1920px, saved working reads,
synthetic CSRF login/logout and independent personal views. All 50 working table
hashes and protected-file hashes matched. OpenAPI, clean npm build, formatting,
Docker config and Node image manifest passed. Linux image execution, physical
touch and high-density graph performance remain unverified. Private reports are
in artifacts/phase7; owned preview servers were stopped.

Phase 7 follow-up (7 October 2026): the user requested Lightswind/Coss UI/UILib as
the main design references. The overview now has licensed aurora lighting,
original dimensional illustration, glass surfaces, spotlight cards, responsive
contract cards and 44px mobile header targets. React/Vite remains in frontend/.
The accidental standalone next-app/ starter was inspected, kept and excluded
from Git/Docker; do not delete it or migrate the application to Next.js without
a task requesting that change. User visual acceptance remains pending; further
graph and stored-explanation redesign is still deferred. See docs/PHASE7.md.

Phase 7 motion/alignment follow-up (7 October 2026): original IZ monogram/local
favicon, deep-blue/black/white identity, semantic TechHeading, manual FocusFrame,
saved integer CountUp and continuous emblems are implemented. Motion follows
manual/device preferences and visibility; do not animate money, identifiers or
review scores. Graph controls are 44px; shared analysis status aligns both cards.
All 48 React tests and six isolated Django frontend tests passed. Chromium
verified motion, keyboard/hover focus, reduced motion and 320–1920px layouts;
all 50 working-table fingerprints and protected file hashes matched. User visual
acceptance remains pending. Preserve local-adaptation
credits and the full React Bits license. No collected source or saved graph,
analysis/text data was changed; no Phase 8 or localisation work is authorised
by this update.

Latest Phase 7 refinement: TechHeading page titles now use transparent hovered
glyphs with dashed SVG outlines/measurement handles; original GroupGlyph and a
fixed 66-star CSS twinkle layer are decorative. Finite button glitch/shine stays
within 0.18px transient blur; search fields gain focus borders/scans/icon glow.
All 48 React tests, six isolated Django frontend tests, build and formatting
passed; bounded browser scenarios and 320–1920px layouts were checked. Final
tooltip-edge and integrity checks passed: all 50 working-table fingerprints and
protected-file hashes matched. User visual acceptance remains pending. Footer, authentication, source/parsing, API-page
and explanation improvements were explicitly deferred; do not start them from
this refinement. No dependency, backend or saved-data change was required.


Latest user-authorised Phase 7 update: About Us is the sixth navigation route; the
full footer restores existing contacts/GitHub/credits and current stack/sources.
React Bits Particles (240 points) replaces the 66-star layer; Border Glow retains
native group-card links and decorates About panels. Ctrl+K was removed; input
carets remain visible, ordinary text has transparent caret styling. Glyph strokes
are thinner and reveal completion is cancellable and independent of final-glyph
hover. All 61 React tests, six Django frontend tests, build and formatting passed;
bounded Chromium checks include 320–1920px, real WebGL, motion/fallback, navigation,
search and saved evidence. Private reports use about-particles prefixes. User
visual acceptance remains pending. Authentication, parsing, API-page, explanation
redesign, localisation and Phase 8 remain deferred. Preserve next-app unchanged.


Latest authorised Phase 7 follow-up supersedes the earlier account/footer
deferrals: independent developer Barakhat Mukhtar Batyruly; related article author
Yestay Arnuruly, Estay-2020@bk.ru. Remove supervisor/department claims from UI.
Sign-up/sign-in dialogs and /app/profile support username changes, read-only email
and current-password-protected password changes without avatars. api.0001 adds
case-insensitive account indexes; restored-copy/reverse checks preserved original
values. Working migration remains pending and must precede registration use.
Graph visual accents/controller and Companies/People/Contracts list surfaces were
updated; evidence, IDs, stored layouts and immutable results remain unchanged.
353 PostgreSQL tests, 77 React tests, build, formatting and bounded Chromium
flows/320–1920px checks passed. Account browser writes used synthetic SQLite only.
Reports and backup are in ignored artifacts/phase7/account-ui/. User visual
acceptance remains pending. No Git commands are authorised yet; the user wants
to review these four items before committing/pushing. Do not automatically start
AI-explanation/group-page work, parser/data-quality work, entity-detail redesign,
localisation or Phase 8. Preserve next-app and the protected learning/environment
files.

Current Phase 7 saved-view follow-up supersedes the previous pending-migration
status: all 69 existing working migrations are applied; no new migration was
added. Article email is in the contact panel; desktop directory arrows are inset.
Authenticated /api/v1/account/views/ returns own paginated metadata, and Profile
Your graph views opens saved snapshots. Save view commits pending camera targets
and clears completed targets to preserve later manual pan/zoom; toolbar feedback
is visible beside controls. Failed private GET/revision conflicts block PUT until
Reload saved account view. Guest state enters an account without a personal view
only after successful GET and explicit save. 357 PostgreSQL tests without skips,
88 React tests, build, formatting and migration drift passed. Fresh-browser
account restore without localStorage retained pins, selection, zoom, filters and
freeze. All 50 source fingerprints matched; the fresh verified backup/report is
under ignored artifacts/phase7/save-view-followup/. User visual acceptance remains
pending. No Git, source collection, inference or next-phase work was run.

Current user-authorised API-page styling supersedes the earlier API-page deferral.
/api/v1/docs/ is a standalone branded navy reference with resource navigation,
native filter/collapsed operations, Nord dark monospace examples, responsive
forms/auth modal and workspace/schema links. Local Manrope/IBM Plex Mono OFL
assets and bundled Swagger assets are retained. Its helper makes no API requests;
native bootstrap/CSRF and operation execution remain intact. No API permission,
authentication, data, schema or rule change was made. Sixteen isolated SQLite API
static/common tests, strict OpenAPI validation, targeted formatting and
collectstatic passed; initial browser resource/filter/modal/native GET 200 checks
passed. Completed Chromium checks covered deep links, empty filtering, native
GET 200/one record, invalid-query validation without a request and page/modal
layouts at 320–1920px against actual clientWidth. Long code scrolls locally;
no JavaScript exception or failed/external/non-GET request was observed. Screenshots
at 320px/1440px were inspected. Report: artifacts/phase7/api-docs/browser-verification.json.
The owned preview on 8774 used read-only working data; user port 8000 was untouched.
Final source fingerprints (all 50 tables), protected files and dependency
versions matched; 357 scanned files contained no configured credentials. Owned
preview/browser stopped with no 8774 listener. User visual acceptance remains pending.
No React, next-app, parser,
explanation, localisation or Phase 8 work is authorised by this update.


Current user-authorised AI follow-up (8 October 2026) supersedes the explanation
deferral. Prompt evidence-presentation-5.3 generates short evidence-cited prose
and checks; readable-explanation-5.2/template-5.2 retain rules/analysis 5.0.
Aliases expand from frozen graph labels; original contacts appear in saved facts.
Bounded schema/reference/number/contradiction guards allow one local Ollama
repair within the same timeout; hosted providers do not retry. Guards are not
semantic proof. Four working clusters now have real Qwen3:4b explanations from
explicit jobs, unchanged requests reuse them, and all older immutable texts,
scores and graphs remain. GET must never regenerate these documents. Default
.env configuration remains template-only; one-time generation used process-local
settings. The aligned review/explanation cards explain points, show model prose
and expose supporting facts; fallback is labelled honestly. 391 PostgreSQL tests
(no skips), 95 React tests, build, format, OpenAPI and collectstatic passed.
Final browser checks covered all four saved results, citation disclosures/reload
and 320–1920px layouts. Four of six final synthetic provider cases were accepted;
director-authority invention and dense-group raw finding IDs were rejected after
repair. Some repetitive wording remains. All original immutable rows and 44
non-AI domain tables were preserved; final tests kept all 50 current hashes equal.
Backup/reports: ignored artifacts/phase7/ai-narrative/. User readability/visual
acceptance remains pending. No Git, source parsing, localisation or Phase 8 work
is authorised by this update. Preserve next-app and learning/environment files.


User review, 8 October 2026: the user accepted the revised AI explanation and
aligned review panels. The agreed remaining sequence is relationship-group
page refinement, parser/data-quality work, and company/person detail pages.
This acceptance does not authorise source collection or start Phase 8.


Current user-authorised directory follow-up (8 October 2026): cluster list/detail
API projections provide frozen member previews, connection-based display titles,
source-backed shared contact/verified role reasons, matching saved review scores
and specifically dated KGD arrears coverage. Persisted names/UUIDs/history/AI
texts remain unchanged. SQL search/filtering precedes pagination; names/BINs use
frozen member nodes. mixed_roles is a directory reason only, not a new graph edge
type. Ignore legacy explanation_stale as it is not maintained by analysis services;
directory status only describes saved graph/analysis correspondence. React cards,
URL filters/chips/reset, historical title scope and filtered return navigation
(including version changes/reload) are implemented. 413 PostgreSQL tests (no skips),
108 React tests, build/format/OpenAPI and38 working GETs passed. Chromium verified
320–1920px, keyboard/reducedmotion and simulated outage recovery. Working data and
protected files remain unchanged; no collection/inference/migration/Git ran.
Reports: ignored artifacts/phase7/cluster-directory/. Directory visual acceptance
is pending. SQLite Unicodecasefold and large-catalogue performance limitations
are recorded in PHASE7.md. Parser/dataquality/entitydetails/localisation/Phase8
require separate tasks; preserve next-app and the user's learning/environment files.


Current user-authorised parser/data-quality follow-up (8 October 2026): readonly
working audit found 777 companies/500 contracts without duplicate BINs/registry
IDs, but all 1,661 observations and 4,311 selected facts are legacy/unconfirmed.
The 384 enrichment timestamps are from June; migration dates are not source
freshness. All 768 identities are unverified; 384 repeated-name groups are within
individual companies' historical/current records, with no cross-company groups.
No working KGD checks or ownerships exist. Do not merge or refresh these by name.
Strict parser identity/field/amount checks, repeat-page/external-ID guards,
atomic chronological role refresh and latest-attempt caches are corrected;
company/contract provenance is 2.1 and KGD is 3.2. The read-only aggregate
`audit_data_quality` command includes saved coverage and safe configuration counts.
All 458 PostgreSQL tests (45 new) passed without skips; fresh backup restoration
and all 50 source/protected fingerprints matched. Owned test databases were
dropped. See PHASE2.md and ignored artifacts/parser-quality/. No schema change,
working cleanup/collection, graph/text regeneration or Git command was run.
Bounded live validation is proposed, not executed: one already configured company,
at most five HTTP attempts across registry search/card, Adata and KGD lookup/debt,
zero automatic retries, isolated evidence database, no working writes. It still
requires explicit user instruction. The private proposal is
artifacts/parser-quality/proposed-live-validation.json. Do not reuse its single
account credential for other companies or start broader collection automatically.


Latest parser/data-quality result, 8 October 2026, supersedes the proposed-only
live-check restriction above: the user authorised use of existing identifiers.
A bounded 12-company sample (all 11 original group members plus one KGD control)
used 72 HTTP attempts. Parser 2.2 handles the verified old.goszakup.gov.kz host,
blank alternative identity cells, safe optional URLs and identity-bound Adata
JSON-LD. Explicit enrichment now freezes bounded company/source selections and
uses per-source freshness; resume preserves its selection. KGD 3.2 separates
HTTP-200 failed lookups from identity-confirmed success; unknown debt stays unknown.
All 495 PostgreSQL tests passed without skips. After verified restore/replay,
29 accepted observations were published for 12 working companies atomically,
with a single final refresh and zero new HTTP/model calls. Three graph/analysis/
template versions were added; all original immutable texts, group UUIDs, accounts,
views, contracts and 765 unrelated companies remain. One phone group changed
from five to four members because both fresh sources agree on a different phone;
its old snapshot remains. Three complete KGD taxpayer/debt pairs are saved,
with explicit zero amounts; wider entitlement/nonzero and entrepreneur variants
remain unverified. One registry search is genuinely ambiguous; failed attempts
remain in isolated evidence rather than accepted working facts. Eleven refreshed
directors remain unverified, with 22 same-company candidates and no name merges.
26 working API reads passed with all 50 table hashes unchanged during reads.
.env, dependency versions, test.py and next-app remain unchanged. Automatic
collection stays disabled. Old Qwen explanations remain historical where evidence
changed; new current explanations are saved templates, without model inference.
Private evidence/replay/publication reports: artifacts/parser-live/. Read the
latest RECOVERY.md entry before another data-changing algorithm. No Git, entity
page redesign, new source integration, localisation or Phase 8 was started.

Latest authorised expansion, 8 October 2026: next 50 identifiers were frozen and
attempted; 49 gained at least one successful source result, five completed both
sources and 45 runs are partial. Adata: 48 success/one not-found/one unavailable;
registry: six success/three ambiguous/41 unavailable (22 circuit-skipped).
Temporary empty-body 302 responses prompted stopping that host; one later probe
returned 200 but did not establish the redirect cause. Transport now stops a host
after three consecutive failed operations and immediately for denial/challenge/
rate limits; independent sources continue. No automatic follow-redirect bypass.
KGD 3.3 accepts explicit source-confirmed IP registration with name and exact
returned type, fences cross-type caches, and blocks IP legal-entity debt as
unverified. One real registration is saved; no live IP debt request was made.
Conflicting exact-identifier registry cards remain unresolved; no name merges.
101 outcomes were replayed on a restored copy then published atomically through
normal ingestion services; five new graph/analysis/template versions, nine active
groups. No inference. Original histories, contracts, accounts and latest personal
layout were preserved; 726 out-of-scope companies unchanged. 505 PostgreSQL tests
and 80 read-only API GETs passed. Current verified backup and private reports are
under artifacts/parser-expansion/; see RECOVERY.md. Next 715 companies have not
been attempted; source gaps remain in this batch. Preserve frozen selection to
avoid retrying completed HTTP calls. .env, dependencies, test.py and next-app
unchanged. No Git or subsequent phase was started.

User-authorised continuous collection (8 October 2026) supersedes the earlier
automatic-collection prohibition: improve existing parsers and keep Celery beat
collecting while development continues. apps/ingestion/background.py owns bounded
independent contracts/profile/KGD stages with durable due times, host cooldowns,
fair source-specific selection, request caps and cycle/pipeline leases. Partial
accepted data refreshes graphs/templates; no automatic LLM calls. Adata parser
2.3 fixes the observed Latin-P leadership label and explicit name parts; founder
markup is not current ownership. Contracts resolve only the chosen party slice;
unsupported identities remain unresolved issues, while network failures preserve
the page checkpoint. Invalid rows count against the requested budget.
scripts/background.ps1 Start/Status/Stop manages one owned native solo worker on
the isolated ingestion queue and one beat. Logs/markers/schedule are ignored in
artifacts/background/. Windows process ownership and stop/restart were checked;
leave the final owned processes running as requested. Do not consume/purge the
user's default Redis queue: an old queued legacy task was encountered during the
initial probe and failed before contract writes. Existing Redis/PostgreSQL belong
to the user. .env remains unchanged; collection flags are process-local.
Before changing collection algorithms, stop this owned collector and verify a
current backup, then restart after tests. Current working hashes legitimately
change under scheduled collection. Recovery details and private reports are in
artifacts/background-verification/. A real cycle completed four registry profiles,
five Adata profiles and two KGD checks; contract stage was partial. The subsequent
party-quarantine fix is offline-tested; successful live contract import under that
fix is not yet claimed. Full Docker opt-in: docker-compose.full.yml plus local-ai
profile; config validates, but full Linux stack/model startup and transfer of the
native database still need verification. No Git, new paid/source integrations,
entity redesign or localisation was performed.

Final background gate: 524 PostgreSQL tests passed without skips. The final 2.3
worker completed another five live Adata checks; duplicate tick made zero HTTP
calls and no versions. One worker/beat remains running, verified with Status.
Current native catalogue is still 777 companies/500 contracts; successful new
contract imports under the quarantine fix remain unverified until a due registry
cycle. Status retains individual source outcomes and UTC next-due times. Full
Compose configuration validates; Windows collector start/stop/restart verified.
Protected environment/dependencies/learning/next-app files stayed unchanged.

Read-only operational verification, 9 October 2026 at 10:21 Asia/Qyzylorda:
the running 2.3 collector completed a real 25-contract import without skips,
adding 36 companies (813 companies/525 contracts total). The same cycle saved
four registry profiles, five Adata profiles and two KGD registrations; one
registry identity remained ambiguous. There are eight successful taxpayer
registrations and three saved zero-arrears checks dated 8 October; no owner KGD
history is implemented. A duplicate tick made zero HTTP requests/new versions.
No duplicate BINs/contract registry IDs or customer-link mismatches were found.
Eight normal-settings API client GETs passed in a PostgreSQL read-only transaction;
port 8000 was unavailable, so live browser verification is not claimed. Prior
524-test gate was inspected, not rerun. Both owned processes remain running.
The catalogue still has substantial legacy coverage; contract polling covers a
bounded registry-head slice, not exhaustive backfill. Report:
artifacts/background-verification/current-audit.json. No ingestion algorithm,
environment, migration or Git command changed in this verification.

Latest user-authorised collection redesign, 9 October 2026, supersedes the old
head-only/template-only background limitations. Ingestion now has persistent head,
history and repair streams, frozen page slices, unchanged-party reuse, durable
ContractRetry/backoff, fair profile refresh, independent KGD debt eligibility and
enrichment backlog backpressure. Migration ingestion.0007 is applied after verified
forward/reverse/reapply on a restored copy; no working records were deleted.
Native Start opts in to local Ollama/Qwen and a separate iz2-ai worker; Stop waits
for active tasks. Automatic model jobs reuse existing dedup/version fences, preserve
templates on failure and never use paid providers. Default .env remains unchanged;
GET remains read-only. The default Redis queue remains unconsumed by native helpers.
544 full PostgreSQL tests passed, then 32 targeted tests after a live-discovered
isolated-timeout cooldown fix. Three live crawl slices passed in an owned restored
copy (six requests). First working cycle saved six additional KGD registrations;
eight automatic real Qwen jobs succeeded before graceful stop/restart. Recovery:
artifacts/collection-v2/recovery-live/database_20261009T061843Z_e3d52472.json.
See latest PHASE2/RECOVERY entries. Full archive traversal, Linux stack runtime,
owner histories, IP debt and broad debt entitlement remain unverified/unimplemented
as applicable. Do not promise every field will become known or delete the source
database to hide gaps. Current owned collector/model processes should stay running;
stop them and verify fresh recovery before further data-changing algorithms.

Final live check for that redesign: all nine current explanations are real saved
Ollama results; the last completed cycle saved ten Adata results and ten KGD
registrations (24 total). Registry retained two ambiguous identities. Catalogue
813/525 is intentionally held while 729 companies await first attempts from both
profile sources. Earlier simultaneous transport failures recovered on bounded
recheck; host-only numerical curl diagnostics now omit exception text/credentials
(five transport tests passed). Graceful Stop/Start was verified twice. Latest
verified recovery before diagnostic logging:
artifacts/collection-v2/recovery-diagnostics/database_20261009T062729Z_6f01e3d2.json.
Final report: artifacts/collection-v2/final-verification.json. Owned ingestion/AI
workers, beat and local Ollama remain running. No Git commands ran.

9 October follow-up: the user wants to save the collection milestone, then continue
with company/person detail pages and complete-stack verification. They request a
full project audit after remaining work, preferably using their label
"GPT6AstraPro"; current model preference is "GPT6Astra", high reasoning. Record
these as preferences, without claiming availability or silently switching models.
See the latest ROADMAP entry. Source coverage is still incomplete; commitment of
the implementation is not a production-readiness or complete-data certification.

User-authorised entity-page follow-up, 9 October: company selected-field provenance
is bound to the exact displayed value/company; legacy migration dates are not
source check dates. Person pages explain separate identities, same-name record
counts and pending matches; no merges. KGD registration/debt stay separate; roles
filter current/inactive observations, contracts switch supplier/customer with
source dates, and mobile rows become cards. Cluster company/person filters use
current saved snapshots in SQL; person links require an exact verified node and
role evidence. No schema, ingestion/rule algorithm or saved document was changed.
551 PostgreSQL tests (no skips), then 18 entity checks, 111 React tests, build,
format, schema and read-only browser checks passed. Stable 320–1920px layouts
fit; touch/large-catalogue performance unmeasured. Report: artifacts/entity-pages/.
Visual review pending. At final status worker/AI-worker/beat were already stopped,
last cycle 07:27 UTC; this task did not stop them. Tell the user the restart command
rather than claiming collection is running. No Git or next-phase work performed.

9 October source-aligned UI follow-up: user requested removal of unused sections.
Hide ownership when its unfiltered read succeeds with zero records; keep real
records and errors visible. Current adapters do not collect confirmed ownership.
Omit empty company fields; retain missing KGD checks. Remove repeated person-history
column/empty history panel and use collapsed source-scope notes instead. Preserve
identity uncertainty, models, histories and future ownership support. 112 React
tests, build/format/collectstatic and read-only 320/1440px browser checks passed.
No backend or collection change. A source-access audit for verified director IDs
and current ownership is a proposed follow-up, not an authorised new integration.

User-authorised parser audit, 9 October 2026: public Goszakup director tables do
expose IIN; parser 2.3 had ignored it. Version 2.4 binds exact unmasked identifiers
to names in the same labelled director section. No name merge, ownership inference
or appointment-date invention. Atomic fact selection follows role chronology and
retains dated verified evidence across matching name-only refreshes; compatible
2.3 contract/legal-form caches remain usable. Current-role People filtering keeps
all historical URLs and namesake comparison; empty group panels are compact.
Legacy company HTML no longer prints director IIN. Public participant identifiers
for entrepreneurs may already equal IIN; do not conflate those with person fields.
Eight bounded HTTP attempts produced four accepted registry cards (two IP/two UL).
Rehearsed then atomically published: four verified directors, one graph/analysis/
template version, original histories and 809 unrelated companies preserved.
563 PostgreSQL and 112 React tests, build/format/OpenAPI, 38 read-only public GETs
and bounded Chromium checks passed. Recovery before/after was independently verified.
Worker/AI-worker/beat were restarted; native collection remains authorised/running.
Status then showed 150 KGD registrations/three debt results, 598 first-attempt
profile gaps and source cooldown/failures. No universal completeness claim.
User has no OWS token; existing public adapters remain in use. See
docs/PARSER_AUDIT_2026_10_09.md and docs/RECOVERY.md; private artifacts under
artifacts/parser-final-audit/. No Git, schema, new source or next phase was started.

9 October People-list clarification: the user sees repeated names in the UI.
Read-only audit: 1,068 identity records, 384 current identities, 383 same-company
repeated-name sets plus one cross-company current name collision; zero duplicate
verified IIN. Preserve history and do not merge by name. Current-role default stays;
company previews distinguish namesakes and Source history explicitly includes
repeats with row state labels. PersonDirectorySerializer adds safe bounded company
context via prefetch; nested person serializers and existing API defaults remain.
21 PostgreSQL entity tests, 112 React tests, build/format/schema/static and bounded
320-1920px browser checks passed. No data/schema/ingestion/AI mutation or Git.
Collector left running; owned preview stopped. Details in docs/PHASE7.md; private
reports in artifacts/people-record-audit/. MVP currently demonstrates contact-based
links (no real shared verified director yet); demo preparation remains proposed.

9 October readiness follow-up: main Companies defaults to source-checked selected
name/BIN profiles; People to verified current identities. Pending/unverified/all
history remain explicit filters; public API omission keeps previous all-records
semantics. GET reads committed facts, never collects or generates. Company
Directorships now defaults to current (the reported company 567: one of three);
person historical views/empty ownership behaviour remain. Queue refresh bypasses
failure retry delay only for successful outdated parser versions; exact subject
and BIN checks protect due/backlog/KGD selection. All existing budgets/cooldowns
remain. 568 PostgreSQL tests, 113 React tests (two-worker rerun), build/format/schema
and bounded browser checks passed. All 51 working hashes matched verified recovery
before collection restart. See docs/DATA_READINESS.md and docs/RECOVERY.md; private
artifacts/readiness/. No schema/source expansion/Git/next phase. User's next order:
visual refinement, then whole-project audit and deployment; require those tasks.
# Latest user-authorised UI refinement, 9 October 2026

Saved graph layouts can be removed from GraphExplorer and Profile. DELETE on the
personal view route uses strict revision/CSRF/account fencing. Empty JSON payload
is a deletion marker with retained revision; normalized saved layouts are always
nonempty. Exclude markers from account listings, return null with their revision,
and never reset revisions or resurrect guest layouts after account removal.
No schema change. Shared IZ monogram/favicon, charcoal surfaces, restrained blue,
finite surface/disclosure motion and API motion preference are implemented.
178 PostgreSQL API/graph and 118 React tests passed, plus build/format/schema/static
checks. Chromium verified responsive routes, guest and synthetic-account removal,
Profile, API native GET/filtering/reduced motion. See latest PHASE7 entry and
ignored artifacts/ui-polish/. Working preview was read-only; owned collectors
remain running. User visual acceptance, whole-project audit and deployment remain
pending. Do not run Git or start the next task automatically.

User review correction: the user rejected the near-grayscale palette and wants
softened contrast with a clearly blue identity. Navy surfaces/blue actions are
restored across the workspace and API; graph canvas/inspector match. Logo dots
and favicon connectors use #5797f0. Preserve this direction rather than globally
desaturating the UI again. Build/format/static and twelve Chromium layout checks
passed; see PHASE7.md. No backend/data change or Git command was needed.

Latest UI consistency follow-up: shared surface tokens replace positional card
colours and per-cell gradients across the workspace. Home uses additive overview
checked_company_count/current_verified_people_count fields matching default
directory query scopes, shared via apps/api/catalogue.py. Raw count fields remain
compatible and are labelled as saved records in coverage, not unique current
people. Do not merge identities to reconcile displayed counts. Swagger now points
to workspace session access instead of generic credential buttons; native CSRF
and OpenAPI security remain. 28 isolated PostgreSQL, two static and 119 React
tests plus build/schema/browser checks passed. No working writes/schema/parser/
Git changes. See latest PHASE7 entry; user visual acceptance remains pending.

Latest authorised design audit: directory arrows now align at the right edge with
a 20px inset and rounded row hover has no square backdrop. Particles has a separate
3-7 second twinkle clock plus animated CSS fallback; manual/device motion and
visibility pause remain. A noninteractive desktop crescent sits behind content in
the upper-right gutter; hide it below 768px. Mobile navigation scrolls internally,
portal surfaces/actions use the blue palette, and compact controls are at least
44px. Swagger resource filtering uses its documented fn.opsFilter hook for trimmed
case-insensitive matching without replacing native bootstrap/CSRF. 120 React and
two strict Swagger static tests, build/format/static and bounded Chromium design
checks passed; see PHASE7.md and ignored artifacts/design-audit/. Working reads
were read-only; account writes synthetic only. Collection stays running. No Git,
parser/schema/dependency change. Full project audit/deployment remain separate.

## Final-audit timezone/localisation follow-up, 10 October 2026

The user explicitly authorised AUD-001 remediation and an EN/RU website switch;
this supersedes earlier localisation deferrals, not the other audit findings.
FINAL_AUDIT.md remains a historical audit with a bounded remediation note.
Django TIME_ZONE is Asia/Qyzylorda, Celery uses the same setting, and UTC-aware
storage remains enabled. Data-quality contract/role dates use localdate(now).
Ten new cross-domain boundary regressions and all 583 PostgreSQL tests passed
without skips; owned test database removed. Native and isolated Linux
normal-settings probes confirmed UTC+05:00 with no database/network work.

Read-only repeatable-read working assessment found no current graph/role/KGD
projection differences across the old/new relevant dates and no creation-day
mismatch candidates in 57 graph snapshots, 44 analyses or 47 jobs. Preserve
saved histories: no migration, source recollection or saved-result rewrite was
performed. Fresh verified recovery (51 tables/18,890 rows/70 migrations) is in
artifacts/final-audit/recovery/summary.json and docs/RECOVERY.md.

Workspace/API language preference is localStorage['iz2-language'], en/ru,
default en. API chrome/help/filter/motion and native Try/Cancel/Reset/Execute/Clear
labels are localised through Swagger React wrappers; native validation, entered
values, CSRF and schema remain. Technical contract descriptions/examples/responses
retain their original language. Two final strict Swagger tests and bounded
Chromium EN/RU/persistence/cross-tab/native GET/validation/320-1920px checks passed.
Workspace EN/RU passed 141 React tests, build, formatting, normal collectstatic
and ten-route Chromium checks at 320/768/1440/1920px. Language changes preserve
drafts, filters, graph layout and revision fences without API requests or writes.
Source values and saved explanation prose remain original; the latter has an
explicit language note. Calendar dates do not shift; timestamps use Qyzylorda.
Synthetic registration/profile/graph save-reload-removal and workspace/API
cross-tab language synchronisation passed. See PHASE7 for verification limits.
Private reports: artifacts/timezone-fix/ and artifacts/localization/.
Worker, AI-worker and beat were already stopped at audit entry and remain stopped;
do not restart collection just to test localisation. No Git, dependency update,
paid generation, source expansion or Phase 8 was started.

User review, 10 October 2026: the current website design and Russian localisation
are accepted. The user subsequently requested English-only developer API docs;
remove its EN/RU controls and preference listeners, keeping React's switch and
stored preference. The next agreed task after the user-operated commit/push is
Docker configuration for a Linux server; no host has been selected. Do not treat
this as public-deployment approval or closure of the remaining audit findings.
For the laptop, use the existing background.ps1 Start/Status/Stop controls; no
Windows startup task is installed. Start also enables the local Ollama/Qwen AI
worker. Stop waits for owned workers but leaves Ollama available; local_ai.ps1
-Stop stops the owned model server separately. A read-only Status check again
found worker/ai-worker/beat stopped; this UI task did not start collection.
English-only API cleanup passed two strict Swagger tests, syntax/formatting,
collectstatic and browser GET/filter/320-1920px checks with a retained Russian
workspace preference. Only the API template/helper/styles and continuity docs
changed. No Git, collection, deployment or model job was run.

