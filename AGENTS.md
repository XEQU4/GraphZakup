# Instructions for working on IZ2

This project is a thesis system for analysing relationships between participants in Kazakhstan's public procurement, with a possible later pilot. Requirements and workflow are in [docs/ROADMAP.md](docs/ROADMAP.md), the target architecture is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and the original findings are in [docs/AUDIT.md](docs/AUDIT.md).

Brand: IZ2; package and GitHub repository: iz2; intended future domain: iz2.kz.
The user supplied the original scope: relationship evidence combined with verified
company/person history and plain-language explanations. Court, bankruptcy and
restricted-participant integrations remain planned; legacy flags do not establish
verified findings. Do not start those sources or Phase 7 automatically.
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
