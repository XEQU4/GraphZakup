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
- Use English for project documentation, instructions, code comments, UI and CLI messages, generated explanations, prompts, and proposed commit messages. Save decisions in the repository so the next task can continue without chat history.
- Develop and verify the English version first. Add Russian website localisation later, after the English interface is complete. Preserve official source labels, identifiers and original data in their source language; translating parser selectors would break data collection.

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
