# IZ2 roadmap

Plan date: 5 October 2026. The user authorises phases individually and runs Git commands. Changes follow preservation of the baseline.

Based on the [audit](AUDIT.md), [baseline](BASELINE.md), [recovery record](RECOVERY.md), and [architecture](ARCHITECTURE.md). Future model/module names remain proposals until implemented. Completion requires verified criteria, not merely code.

## Current status

| Phase | Outcome | Status |
| --- | --- | --- |
| 0 | Record baseline and proposed thesis scope | Complete |
| 1 | Fix dangerous defects and make startup reproducible | Complete |
| 2 | Consolidate ingestion and correct the fact model | Complete |
| 3 | Integrate available KGD information | Complete: taxpayer and zero-arrears checks verified for one authorised company |
| 4 | Persist graph versions and substantially improve graph interaction | Complete: 191 PostgreSQL tests; revised graph prototype accepted by the user |
| 5 | Introduce verifiable analysis and versioned explanations | Complete: 238 PostgreSQL tests and five local-model synthetic cases passed |
| 6 | Provide a DRF API | Complete: 320 PostgreSQL tests; versioned API and locally served OpenAPI verified |
| 7 | Build a React interface using user references | Implemented; browser checks passed, user visual acceptance pending |
| 8 | Prepare thesis demonstration and operations | Planned |

Phases 0-2 were completed on 5 October 2026. Phase 2 consolidated parsers/the service pipeline, added provenance, resumable runs, and safe person identity. All 128 tests passed on PostgreSQL; a new backup was restored and migrated separately with existing values preserved. The source database and user files remained unchanged. See [BASELINE.md](BASELINE.md), [PHASE1.md](PHASE1.md), and [PHASE2.md](PHASE2.md) for protocols and limits. Audience, schedule, and spending limits remain open.

## Product name and restored scope, 7 October 2026

The user renamed the product IZ2, with package/repository `iz2` and intended domain
`iz2.kz`. The original goal combines company relationships, verified company/person
history and plain-language explanations for further review. Current KGD covers
company registration/aggregate arrears within the documented scope. Court records,
restricted-participant lists, bankruptcy and owner-specific history need separately
authorised source work; existing legacy flags are not accepted evidence. Tender
allocation patterns need bidding inputs. These requirements remain product goals,
not new parsers or behavioural findings implemented by the rename.

Public branding/package metadata changed; dependencies and data identifiers remain
stable. Compose preserves its legacy default volume namespace across a folder
rename. Local AI can be started/tested through reusable scripts without working
data, Redis or paid generation. GitHub rename and the optional local folder rename
are user actions; no Git operation or domain deployment was performed.

## Project language

Use English for documentation, instructions, comments, UI/CLI messages, prompts, and newly prepared explanations. Develop and verify the English website first. Add Russian website localisation later, after the English interface is complete. Preserve official source labels and original data in their source language. Translating files does not regenerate existing stored explanations.

## Dependencies

```text
0 -> 1 -> 2 -> 4 -> 5
         |-> 3
         |-> 6 -> 7
3, 4, 5, 6, 7 -> 8
```

KGD and DRF work can proceed independently after Phase 2 stabilises the model. Include snapshot/explanation contracts in the API before the corresponding React pages. Graph improvements begin in Phase 4; final website design follows user references in Phase 7. Tests, documentation, migrations, and data-preservation checks belong to every phase; Phase 8 assembles verified results.

## Phase 0 Baseline and scope

Goal: control refactoring and preserve a recovery path.

- Record the tree, versions, significant user changes, and audit boundaries without secrets.
- Save audit, architecture, roadmap, and repository rules.
- Back up accessible existing data/schema; restore separately and compare tables/counts.
- Record unavailable data and how to resolve access. Backup instructions alone do not prove recovery.
- Define proposed minimum thesis scope, demonstration scenarios, and open questions.
- Record Phase 4 graph improvements and obtain references before final UI/UX approval.

Deliverables: `docs/`, repository rules, and a verified baseline. Personal archives/backups stay outside Git.

Acceptance: user changes preserved without hidden application refactoring; confirmed defects distinguished from risks/unverified areas; verified recovery or confirmed absence of a database, with inaccessible data unresolved; scope/deferred decisions saved independently of chat history.

## Phase 1 Defect fixes and startup

Dependency: Phase 0, especially preserved data before changing imports.

- Escape source values in graphs/tables; prevent untrusted HTML insertion.
- Stop deletion before successful collection; define full import preserving related records.
- Stop deleting all clusters; retain IDs/texts and mark outdated analysis before full snapshots.
- Correct checkpoints for empty/error/partial pages; retain unconfirmed records for retry.
- Normalise dates; parse Decimal directly from strings, never substituting zero for errors; distinguish missing data from source failure.
- Validate filters, unify thresholds, deduplicate counts, fix log cleanup.
- Use frozen Docker dependencies, current staticfiles settings, a dedicated migration stage, startup ordering, and health checks.
- Align PostgreSQL with verified recovery: baseline local 17.6 versus original Compose 16; verify transfer separately.
- Provide `.env.example` and safe startup instructions without real credentials.

Verification: malicious HTML, invalid dates, exact money, empty/partial pages, and database-failure fixtures; isolated Compose startup without destructive import.

Acceptance: source failure cannot delete data or skip unprocessed pages; invalid values are handled deliberately; after configuring `.env`, one command starts the stack with migrations preceding application services.

Outcome: complete. [PHASE1.md](PHASE1.md) records 83 PostgreSQL tests, restored-copy migration, HTTP/Compose verification, and remaining Phase 2-5 limitations.

## Phase 2 Unified ingestion and fact model

Dependency: Phase 1.

- Consolidate registry/Adata adapters in `apps/ingestion/parsers/` with verified behaviour.
- Add shared transport, normalisers, and request results; services persist data/manage stages.
- Add runs, observations, checkpoints, retries; CLI/Celery call one pipeline.
- Separate initial traversal, updates, and enrichment; add pacing/cache/concurrency protection.
- Preserve raw facts, dates, parser versions; select values after normalisation/quality checks.
- Name matches create identity candidates; repair legacy false merges without losing evidence.
- Preserve role intervals/history; changed roles do not remain current indefinitely.
- Support supplier/customer companies; directorship does not imply ownership/shares.

Verification: repeat/interrupted imports, source conflicts, namesakes, director changes, mass service contacts.

Acceptance: idempotence, visible progress/errors, significant fact provenance, no verified company links from unreliable person matches.

Outcome: complete. [PHASE2.md](PHASE2.md) documents CLI/Celery, observations, field selection, role history, legacy isolation, and migrations. No live collection. Confirmed IIN/ownership scenarios use fixtures; an external confirming source is still needed. Apply prepared migrations to the working database separately.

## Phase 3 KGD integration

Dependency: Phase 2 ingestion/subject model. Read-only access research may start earlier.

- Verify official services, access conditions, tokens, and fields; one API does not expose all tax information.
- Choose the first supported service and add its adapter to the common directory.
- Store result, effective date, source, and subject; company debt belongs to the company.
- Add limits/timeouts/retries, preserving the last reliable observation.
- Prepare anonymised fixtures; separately verify live integration when access is available.

Acceptance: identifier-confirmed subjects; distinct `not_found`, `unavailable`, `not_checked`; reproducible results. Live official-source verification is required for completion. Without access, document the limitation rather than claim fixture-only integration is complete.

Outcome: complete for the implemented taxpayer and aggregate company-arrears services. On 6 October 2026 two authorised requests checked one company in an isolated database: registration confirmed the exact BIN/type `UL`, and arrears returned all five zero amounts with a source reporting date. The second ISNA credential was accepted as `personalAccountToken` alongside the first portal token. Parser `3.1` fixed the observed reporting timestamp format; offline reprocessing preserved original retrieval times and the failed attempt, without another HTTP request. All 167 tests passed on isolated PostgreSQL; restored-copy migration preserved existing values and all 38 working tables remained unchanged. GET, successful resume and cache reuse read saved results. Scope and unverified source variants/other-company entitlement are documented in [PHASE3.md](PHASE3.md). Phase 4 requires separate authorisation.

## Phase 4 Graph state and appearance

Dependency: Phase 2 entities, temporal facts, and observations; add KGD inputs when ready.

Data work:

- Create shared evidence service/`EvidenceEdge` for both UI and analysis.
- Replace all-pairs comparisons with feature indexes; avoid huge cliques from common contacts.
- Preserve UUIDs, immutable snapshots, `graph_hash`, change provenance, merge/split history.
- Recompute affected components within a verified impact boundary; publish atomically.
- Save coordinates/viewing state separately from analytical state.

Interaction work:

- Prototype/select graph libraries by readability, performance, layout persistence.
- Distinguish companies, people, and links; add legend/confidence indicators.
- Highlight selected nodes/neighbours; add search, link filters, zoom/pan, reset/restore.
- Show edge evidence/sources/intervals; distinguish direct links from paths.
- Verify dense graphs, long labels, small-screen selection; meaning cannot rely on colour alone.
- Preserve existing positions, place new nodes carefully, indicate historical versions.

Final style awaits user references. Technical/functional graph work may precede them. References received in Phase 4 inform the graph before React integration in Phase 7.

Verification: unchanged rebuild, added/removed edge, merge/split, non-overlapping roles, coordinate restore, several graph sizes.

Acceptance: stable links, explained group transitions, readable evidence, correct new-company versions without needless view resets, no global recreation for a single component change.

## Phase 5 Analysis and explanations

Dependency: Phase 4 versions/evidence; behavioural rules depend on available procurement inputs.

[PHASE5.md](PHASE5.md) records the implemented free local model option and
environment-based provider switching. On 7 October 2026 the user instructed the
agent to proceed at its discretion and consider model scoring if it improves
on the baseline. Model scores remain separate experimental estimates until
independent evaluation demonstrates benefit. Public scores remain checkable,
uncalibrated review-priority indices.

- Version rules, evidence, temporal conditions, and limitations.
- Separate identity confidence, link strength, behavioural risk; assess false scoring conclusions.
- Add `AnalysisSnapshot`, findings, `analysis_hash`, shared text/UI metrics.
- Save English template explanations by analysis version with uncertainty. Include language in reuse keys for later localisation.
- Select LLM/model/budget only for measurable benefit; supply structured evidence, validate/store output.
- Deduplicate jobs; version prompts; add generation states/fallback; reject stale-result publication.
- Do not claim coordinated bidding without participants, bids, and outcomes.

Verification: unchanged inputs, changed rules/facts, repeats, LLM failure, invented output identifiers, late old-version jobs.

Acceptance: significant claims have evidence; identical inputs reuse text; significant changes create versions; useful without LLM; many weak matches alone do not force maximum risk.

Outcome: complete on 7 October 2026. Versioned rules, immutable analyses/texts,
saved template/model presentations and deduplicated fenced jobs are implemented.
Authorised graph refresh atomically prepares affected templates. All 238 tests
passed on isolated PostgreSQL; restored-copy migration preserved 44 original
tables and working data stayed unchanged. Five synthetic cases passed with free
local Qwen3:4b, including reuse and a separate blinded model estimate. Independent
prediction/readability benefit, paid inference and local-ai container startup
remain unverified; see [PHASE5.md](PHASE5.md). Phase 6 needs separate authorisation.

## Phase 6 DRF API

Dependency: stable Phase 2 model; refine graph/explanation contracts with Phases 4-5.

- Add `/api/v1/` serializers for companies, people, contracts, clusters, snapshots, evidence, explanations.
- Define filters/order/pagination/errors/OpenAPI; return data without HTML.
- Separate reads/job starts; expose job state and exact result version.
- Define roles/permissions; verify same-origin sessions/CSRF initially.
- Keep Django admin; retire old pages when replacement scenarios are ready.

Verification: permissions, invalid filters, query limits, job status, schema consistency.

Acceptance: documented API supports main scenarios; GET never generates or changes domain data; unauthorised users cannot launch collection/resource-consuming jobs.

Outcome: complete on 7 October 2026. [PHASE6.md](PHASE6.md) records versioned
JSON entities, snapshots/evidence/analysis/text histories, own-view concurrency,
same-origin sessions/CSRF, staff-only explicit jobs and OpenAPI. All 320 tests
passed on isolated PostgreSQL; original restored data and all 50 working tables
were preserved. Sixteen synthetic HTTP reads and browser Swagger execution
passed. No new schema migration, live collection or model inference was run.
Phase 7 and final design require separate authorisation and user references.

## Phase 7 React and reference-based design

Dependency: Phase 6 contracts and Phase 4 graph; user supplies references before visual approval.

- Build React/TypeScript; record build/component choices after review.
- Analyse layouts, typography, colours, density, navigation, graph behaviour; agree on key-screen mockups.
- Move dashboard/search/company details/cluster lists/analysis.
- Integrate graph/evidence/version history/saved views.
- Show loading, empty, source-error, KGD-check, explanation-generation states.
- Verify accessibility/responsiveness/contrast; decide on Bootstrap based on design/migration cost.
- Complete and verify English first. Add Russian localisation later as a separate task with language selection and translated UI/explanation handling, retaining original source data.

Acceptance: React supports main scenarios and approved references; refresh restores views; source-confirmed facts and opened analysis versions are clear.

## Phase 8 Thesis readiness and pilot preparation

Dependency: Phase 1-7 functions and documented external-access limits.

- Prepare reproducible data/scenarios from the [architecture](ARCHITECTURE.md#thesis-version-and-further-development).
- Run end-to-end/load/baseline comparisons.
- Complete README purpose/features/limits/architecture/startup/upgrades/tests/demo, consistent with DEPLOY/`.env.example`.
- Verify final-schema recovery, clean installation, upgrade.
- Prepare defence materials with measurements/examples/stated limits.

Before a pilot: action audit, operational roles, sensitive-identifier protection, monitoring, resource/AI budgets, source-use conditions, disputed-data corrections. These are proposed follow-up tasks, not an approved public product.

Acceptance: another person can reproduce startup/demo; measured quality/performance; verified recovery; explicit unavailable sources/unsupported patterns.

## Evaluation

| Area | Measurement |
| --- | --- |
| Identity | Precision/recall on manual labels; namesakes separately |
| Evidence | False edges by feature/source |
| Temporal facts | Simultaneous-role correctness on independent examples |
| Explanations | Supported significant claims and unsupported-claim count |
| Performance | Runtime/SQL/memory on fixed inputs, before/after |
| Reuse | New snapshots/LLM calls for unchanged inputs: no generation expected |
| Recovery | Losses/duplicates after interruption/network failure/retry |
| Usability | Success/time to find companies, inspect links, restore views |

Set thresholds after baseline measurement/sample selection. Algorithm-tailored examples do not replace independent labels.

## Open decisions

KGD broader-company entitlement, quotas and unverified source variants (three taxpayer/complete zero-arrears pairs verified in the bounded follow-up); sample size/bidding data; references/UI/graph library; audience/roles/publication (procurement analyst is unconfirmed); independent model benefit/calibration labels (local Qwen3:4b and configurable API adapters implemented in Phase 5); thesis deadline/API costs; phase calendar after scope confirmation without invented estimates.

The user accepted the revised graph prototype and deferred further design/animation work to Phase 7. Final site styling awaits references. Phase 5 is complete within its implemented scope; measurements and limitations are in [PHASE5.md](PHASE5.md). Phase 6 is complete; Phase 7 requires a separate instruction and references. Do not repeat accepted KGD checks merely to read saved results. Broader KGD validation remains bounded and explicitly authorised.

## Phase 7 delivery scope, 7 October 2026

The user supplied React Bits, Magic UI, Spline and an article of UI resources, and
authorised a serious animated blue interface with restrained cyberpunk details.
React/TypeScript now supports saved-data workflows and is integrated into Django
and Docker builds. Bootstrap remains only on compatibility templates. User visual
acceptance is pending; saved explanation rewriting and further graph design were
explicitly deferred by the user. No localisation or Phase 8 work started.
See [PHASE7.md](PHASE7.md) for actual checks and deployment limits.

The latest user-directed Phase 7 refinement adds About Us, the full project footer,
React Bits Particles and Border Glow. Technical checks are recorded in PHASE7.md;
visual acceptance remains pending. Authentication, parsing, API-page and saved
explanation redesign remain separate follow-up tasks.


Latest follow-up, 8 October 2026: the user accepted the revised saved AI panels
and authorised the relationship-group directory refinement. Connection-based
display titles, dated saved KGD coverage, server-side filters/frozen search and
filtered return navigation are implemented and verified (see PHASE7.md). Earlier
follow-up deferrals above are historical; current directory visual acceptance
is pending. Parser/data-quality work and entity-detail redesign are next proposed
tasks, not started automatically.


The user accepted the directory and explicitly authorised parser/data-quality
work on 8 October 2026. The read-only audit found that existing facts are legacy
and need external refresh; targeted parser, cache, import identity and role-history
corrections are recorded in PHASE2.md. Working data was preserved. Bounded live
validation is a separate explicit operation; no source expansion, entity-page
redesign, localisation or Phase 8 started from this follow-up.


The authorised parser/data-quality follow-up now includes a real 12-company
refresh after isolated validation and restore rehearsal: 29 accepted observations,
three KGD taxpayer/arrears pairs, preserved immutable history and one corrected
weak-contact group membership. All 495 PostgreSQL tests passed. Per-source bounded
refresh and parser 2.2 fixes are implemented; full-catalogue freshness, ambiguous
registry cards, wider KGD variants and source quotas remain open. See PHASE2/3
and RECOVERY for evidence and actual publication. No subsequent phase started.
