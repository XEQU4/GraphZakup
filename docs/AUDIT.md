# GovernmentProcurementGraph audit

Date: **2026-10-05**, Asia/Qyzylorda. Evidence describes the original audit; later fixes have separate status sections. See [ROADMAP.md](ROADMAP.md), [PHASE1.md](PHASE1.md), and [PHASE2.md](PHASE2.md). Goal: prepare a thesis/pilot while preserving accumulated data and explaining every link.

## Scope and limits

Reviewed Django apps/models/migrations/commands, original `services/` parsers, graph/explanations, templates/JS, Celery/Docker/documentation. Application sources were not changed during the audit. Existing `pyproject.toml`, `test.py`, `uv.lock` changes preserved; `test.py` is educational work, not application tests.

Reproductions used isolated in-memory SQLite, without changing source PostgreSQL, live sources, or queues. Phase 0 backup/recovery verification is separate and cannot be inferred from model checks.

| Check | Actual result | Limit |
| --- | --- | --- |
| Python AST | 99 files passed | Not business/source correctness |
| Database-free Django checks | Passed | Not production/XSS/import verification |
| Model/migration comparison | Changes `{}` | Not migration of existing PostgreSQL |
| Initial application tests | **0** | No regression coverage; later utility tests separate |
| Compose service config | Five services passed | No image build/container startup |
| collectstatic without SECRET_KEY | Dry-run passed | Not full build/safe keyless runtime |
| Empty import at page 5 | Cursor became 6 | Source error treated as progress |
| `total=51`, 50-row pages | Remaining page-2 rows lost | No import completeness checksum |
| Float money parsing | Precision loss reproduced | Decimal from float cannot recover original digits |
| Registration `dd.mm.yyyy` | DateField ValidationError | No pre-save date normalisation |
| Five-company graph with prefetched directors | **20 SQL queries** during links | Per-pair values_list ignores prefetch |
| 19 companies sharing one email | **100/100** | Not wrongdoing probability |
| Log cleanup/rotation | Naive/aware TypeError; archives missed | backupCount alone cannot ensure retention |

Python 3.13.5 worked outside sandbox runtime limits; `.venv` was not broken. Verified Django 6.0.6/Celery 5.6.3/beat 2.9.0/WhiteNoise 6.12.0; beat allows Django <6.1, no installed-version conflict found. Compose already grouped five services; reliable startup/state were the problem. Original cluster GET used the **deterministic** explainer, not external LLM.

Priorities: **P0** data loss/executable untrusted HTML; **P1** incorrect results/state/startup; **P2** maintenance/UI/extensibility. Phases: 0 baseline; 1 fixes/infrastructure; 2 ingestion/model; 3 KGD; 4 graph state/UI; 5 rules/AI; 6 DRF; 7 React/UI; 8 thesis/pilot.

## Confirmed defects and implementation limits

### Status after Phase 1

| Findings | Status on 5 October 2026 |
| --- | --- |
| 001, 003-005, 007-008 | Deletions/XSS/checkpoints/dates/money fixed with regressions |
| 002, 017 | UUID/text preserved, atomic rebuild, read-only GET/staleness; full snapshots/versions remain Phases 4-5 |
| 006, 009-012 | Atomic pages/source failures/BIN/fallback fixed; runs/history/common identity contract Phase 2 |
| 014-015 | Automatic name merges disabled, known intervals used; legacy repair/history Phase 2 |
| 018 | Per-pair SQL removed; quadratic comparisons/current-edge recomputation remain until Phase 4 |
| 020-026, 028 | Docker/lock/STORAGES/migration gate/settings/logs/thresholds/filter validation fixed/verified |
| 027 | Counts deduplicated; versioned monetary metric remains future work |
| 030 | README/DEPLOY/tests added; all 83 PostgreSQL tests passed |
| Others | Assigned future phases; live source quality/full AI unverified |

Original paths/line numbers below predate fixes. They are retained for traceability, not assertions that all defects remain in current code.

### Status after Phase 2

| Findings | Outcome |
| --- | --- |
| 006, 009-010, 012-013 | Unified ingestion/typed states/checkpoints/retry-resume/raw-normalised observations/selected fields; failures visible by UUID |
| 014-015 | Names create candidates, legacy roles isolated, changes preserve history; shared identity requires confirmed IIN/company evidence |
| 030 | All 128 PostgreSQL tests passed; restored-copy migration preserved original values; documentation updated |
| 033 | Collection states distinct; legacy tax/court booleans still not verified checks; sources/use remain Phases 3/5 |
| Others | Assigned phases remain; no live sources/snapshots/DRF/React/LLM verification or implementation in Phase 2 |

See [PHASE2.md](PHASE2.md) for priorities, HTML-adapter limits, and migration results.

### AUD 001 Deletion before successful full import

**ID:** AUD-001. **Priority:** P0. **Evidence:** original `apps/companies/management/commands/import_contracts.py:29` deleted all contracts/suppliers before requesting data; supplier deletion cascaded. **Impact:** failure leaves no original data, without staging/atomic switch/recovery. **Fix:** Phase 1 disable destructive behaviour; Phase 2 run/staging/completeness and safe publication.

### AUD 002 Rebuild destroys cluster identity/history

**ID:** AUD-002. **Priority:** P0. **Evidence:** `build_clusters.py:158` deleted every cluster; `apps/graph/models.py:50` assigned new UUIDs. **Impact:** explanations/links/identity lost, failure leaves partial results even after ordinary imports. **Fix:** Phase 1 stop deletion; Phase 4 stable IDs/composition-edge versions/merge-split history/atomic snapshots.

### AUD 003 Stored XSS through source values

**ID:** AUD-003. **Priority:** P0. **Evidence:** `static/js/cluster_graph.js:248` used `.html()` with company names; companies/views.py:69, owners/views.py:63, dashboard/views.py:33 interpolated unescaped fields. **Impact:** names/contract numbers can execute HTML in tooltips/AJAX; JSON/json_script does not protect later insertion. **Fix:** Phase 1 text DOM/escaping; Phases 6-7 structured JSON/React.

### AUD 004 Empty/error pages advance cursor

**ID:** AUD-004. **Priority:** P1. **Evidence:** contract_registry_parser.py:105/:119 returned [] on errors; import_contracts.py:90 used max(1, ...) even with zero records. **Impact:** cursor 5 became 6, turning unavailability into missing data/success. **Fix:** Phase 1 no error advancement; Phase 2 explicit results/confirmed checkpoints.

### AUD 005 Truncation loses the final page remainder

**ID:** AUD-005. **Priority:** P1. **Evidence:** parser.py:200 sliced `contracts[:total]`; import_contracts.py:90 calculated progress from slice length. **Impact:** total=51 retains one page-2 row and resumes page 3, losing 49. **Fix:** full pages or page+offset; checkpoint reflects processed records, not requested limits.

### AUD 006 Record errors do not participate in retry

**ID:** AUD-006. **Priority:** P1. **Evidence:** import_contracts.py:86 caught save errors but :92 advanced; tasks.py:25 retried only escaping exceptions. **Impact:** rows lost; enrichment failure retries from another page; concurrent runs unlocked. **Fix:** Phase 1 retain failures; Phase 2 staged runs/record retry/idempotence/locking/transactional checkpoints.

### AUD 007 Raw registration dates reach DateField

**ID:** AUD-007. **Priority:** P1. **Evidence:** supplier_registry_parser.py:185 returned text; enricher.py:50 forwarded it; enrich_suppliers.py:141/:175 saved outside fetch-error handling. **Impact:** dd.mm.yyyy raises ValidationError and aborts enrichment. **Fix:** explicit date formats/typed results/quarantine/independent company retry.

### AUD 008 Money loses precision and invalid values become zero

**ID:** AUD-008. **Priority:** P1. **Evidence:** parser.py:148 used float/:150 substituted zero; command.py:76 constructed Decimal afterwards. **Impact:** inaccurate/invalid data appears valid. **Fix:** direct Decimal; retain raw value/currency/parse error.

### AUD 009 Identifiers lack a shared contract

**ID:** AUD-009. **Priority:** P1. **Evidence:** import_contracts.py:60 only stripped BIN; supplier parser.py:87 selected first card; contracts/models.py:19 made contract number globally unique. **Impact:** wrong subjects/malformed identifiers/key collisions; registry numbering uniqueness not live-verified. **Fix:** validate 12 digits/leading zeros/response identity; source/external-ID keys and amendment rules.

### AUD 010 Unavailability conflated with missing data

**ID:** AUD-010. **Priority:** P1. **Evidence:** adata_parser.py:22/:98 returned None for HTTP/parse errors; contract parser.py:97 hid BIN failures; enrich_suppliers.py:82 marked empty results fresh. **Impact:** retry delayed seven days, missing BIN skipped, errors resemble absence. **Fix:** typed source states/observations/retries; freshness only after confirmed checks.

### AUD 011 Adata contact/status extraction can be misleading

**ID:** AUD-011. **Priority:** P1. **Evidence:** adata_parser.py:65/:79 chose first phone/email in entire HTML; :95 always returned active. **Impact:** support/navigation contacts falsely link companies; active status unproven. **Fix:** labelled/structured fields, subject verification, fixtures/provenance.

### AUD 012 Normalisation/fallback retain bad or stale values

**ID:** AUD-012. **Priority:** P1. **Evidence:** enricher.py:40 chose Adata before normalising; command.py:121 retained old values with `or`; raw addresses/names compared, blacklist duplicated. **Impact:** invalid preferred contacts block valid fallback; disappearing values remain. **Fix:** shared normalisers, normalise-before-fallback, absent/unknown states/source policies.

### AUD 013 Collection fragmented across parsers and commands

**ID:** AUD-013. **Priority:** P2. **Evidence:** HTTP/HTML in services parsers, persistence in company commands; enrichment help mentioned eGov despite Adata/registry only. **Impact:** moving files alone cannot unify retry/schema/checkpoints; misleading source names. **Fix:** common ingestion/transport/DTO/orchestration; thin commands/Celery.

### AUD 014 People automatically merged by name

**ID:** AUD-014. **Priority:** P1. **Evidence:** link_directors.py:43 get_or_create(full_name); owners/models.py:25 lacked identity uniqueness. **Impact:** namesakes falsely link companies; concurrent duplicates. **Fix:** source identities/candidates/verified exact IIN/evidence/confidence/review.

### AUD 015 Director links ignore role changes

**ID:** AUD-015. **Priority:** P1. **Evidence:** command.py:49 only added roles; dates unused/unfilled; explainer.py:73 claimed simultaneous leadership. **Impact:** former directors remain current without temporal proof. **Fix:** effective intervals/observations/as-of analysis/confirmed closure.

### AUD 016 Connection is not populated

**ID:** AUD-016. **Priority:** P1. **Evidence:** graph/models.py:9 declares Connection; command.py:191 creates only RiskCluster; views/explainer compare fields again; OpenRouter reads empty edges. **Impact:** no shared saved evidence, divergent implementations. **Fix:** Phase 4 materialised evidence/confidence/validity edges and shared snapshots.

### AUD 017 GET persists explanations without freshness checks

**ID:** AUD-017. **Priority:** P1. **Evidence:** graph/views.py:130/:133 generated/saved only when empty; model.py:56 had no version/fingerprint/status. **Impact:** stale nonempty text, duplicate concurrent work; deterministic path incurred no external cost. **Fix:** snapshots/rule-prompt-model versions/jobs/dedup/read-only GET.

### AUD 018 Quadratic work and per-pair SQL

**ID:** AUD-018. **Priority:** P1. **Evidence:** command.py:72/:115 all pairs; graph/views.py:44/:45 ORM values_list per pair; five companies used 20 queries. **Impact:** O(n squared), prefetch ignored; 100 companies roughly 9,900 queries in that section, each view rebuilds. **Fix:** indexes/saved edges/large-graph limits/measured query budgets.

### AUD 019 Inactive OpenRouter raises strings

**ID:** AUD-019. **Priority:** P2. **Evidence:** ai/openrouter.py:76/:88 raise strings; active view imports another explainer. **Impact:** TypeError masks provider errors; prompt has no concrete evidence. **Fix:** Phase 5 typed results/errors/retry/schema/provider/evidence-only/version/cost controls.

### AUD 020 Gunicorn port absent from Compose

**ID:** AUD-020. **Priority:** P1. **Evidence:** Dockerfile:19 bound `$PORT`; Compose/:env omitted it. **Impact:** EXPOSE/mapping do not populate CMD variable. **Fix:** explicit/default 8000, entrypoint, clean-start smoke test.

### AUD 021 Docker ignores lockfile

**ID:** AUD-021. **Priority:** P1. **Evidence:** Dockerfile:13 `uv pip install --system .`; broad lower dependency bounds. **Impact:** rebuilds differ; reproducibility risk, not proven beat conflict. **Fix:** frozen install/supported Django/equal dev-CI-Docker versions.

### AUD 022 Staticfiles setting ineffective

**ID:** AUD-022. **Priority:** P1. **Evidence:** settings.py:88 old STATICFILES_STORAGE; Django 6 runtime used ordinary storage. **Impact:** manifest hashes/compression absent. Keyless dry-run passed, so no build failure claimed. **Fix:** STORAGES/CompressedManifestStaticFilesStorage and real asset serving checks.

### AUD 023 Worker/beat can precede migrations

**ID:** AUD-023. **Priority:** P1. **Evidence:** migrations in web CMD; worker/beat only wait for db/redis. **Impact:** database readiness does not mean tables exist. **Fix:** dedicated migrate gate/app-queue readiness/one beat per deployment.

### AUD 024 Unsafe default settings

**ID:** AUD-024. **Priority:** P1. **Evidence:** settings.py:11 debug defaults on/:12 all hosts/:10 no required key validation; secure-cookie settings absent. **Impact:** accidental debug exposure/unexpected hosts. **Fix:** dev-test-prod separation/fail-fast key/debug false/hosts/proxy-aware HTTPS.

### AUD 025 Log retention fails

**ID:** AUD-025. **Priority:** P2. **Evidence:** cleanup.py:11 aware cutoff/:21 naive date/:23 comparison; formats.py:29 renamed archives without discovery changes. **Impact:** caught TypeError leaves files; retention misses archives. **Fix:** consistent UTC/names/tested cleanup; container stdout/platform rotation.

### AUD 026 Inconsistent risk representation

**ID:** AUD-026. **Priority:** P2. **Evidence:** graph JS thresholds 70/40 versus detail 80/50; company views average risk versus stored Supplier.risk_score elsewhere. **Impact:** inconsistent severity/nonupdated score. **Fix:** Phase 1 thresholds; Phases 4-5 shared score-level-version; Phase 7 components.

### AUD 027 Duplicate company/contract counts

**ID:** AUD-027. **Priority:** P2. **Evidence:** company/view.py:174 sums feature querysets; dashboard.py:64 cluster totals; owner.py:21 Count without distinct. **Impact:** repeated signals/overlapping clusters/search joins inflate counts. **Fix:** deduplicate current counts; define independent versioned metrics/distinct IDs/contracts and overlap tests.

### AUD 028 Risk filter unvalidated

**ID:** AUD-028. **Priority:** P2. **Evidence:** graph/views.py:93 raw GET into numeric filter. **Impact:** risk=abc raises 500; out-of-range semantics undefined. **Fix:** safe parse/error; DRF schema 0-100/tests.

### AUD 029 JSON responses are not a complete API

**ID:** AUD-029. **Priority:** P2. **Evidence:** company views return HTML, limit 50, total equals returned length; similar owners/dashboard. **Impact:** Bootstrap markup coupling/no real totals/schema/permissions/pagination. **Fix:** DRF serializers/filtering/pagination/OpenAPI/permissions; retain admin.

### AUD 030 Original README/tests absent

**ID:** AUD-030. **Priority:** P1. **Evidence:** README 0 bytes, seven app placeholders/0 tests; DEPLOY systemd separate from Compose. **Impact:** unreproducible setup/no regressions. **Fix:** Phase 0 records; Phase 1 meaningful tests/startup; Phase 8 final README/CI/demo/operations. Documentation scaffolding alone is not startup verification.

### AUD 031 Graph snapshots/views not saved

**ID:** AUD-031. **Priority:** P2. **Evidence:** views.py:127 builds data on read; graph JS:287 starts forceSimulation/:335 resets zoom; no snapshot/layout model. **Impact:** unstable layout/no reproducible shared graph-text version. **Fix:** Phase 4 immutable snapshots/separate layout-zoom/evidence updates/graph improvement; Phase 7 reference-based site design.

## Methodological risks

### AUD 032 Uncalibrated heuristic score

**ID:** AUD-032. **Priority:** P1. **Evidence:** sums feature weights plus five per company over two; 19 shared-email companies: 15 + 17 * 5 = 100. **Impact:** service contacts look maximum-risk; component membership proves neither every pair nor wrongdoing. **Decision:** separate evidence strength/risk, feature frequency/time/behaviour, labelled false-positive evaluation.

### AUD 033 Missing checks resemble negative checks

**ID:** AUD-033. **Priority:** P1. **Evidence:** owner booleans default false; pipeline lacks verified ownership/debt/bankruptcy/court sources. **Impact:** not checked/unavailable resembles checked absent. **Decision:** states/dates/source/evidence in Phases 2-3; confirmed observations only in Phase 5.

### AUD 034 Observation and interpretation conflated

**ID:** AUD-034. **Priority:** P1. **Evidence:** explainer.py:142 calls contact groups affiliated; dashboard money_at_risk totals all group contracts. **Impact:** contact similarity mistaken for legal affiliation, amounts for damage, score for probability. **Decision:** evidence-based language/sources/dates/alternatives/limits; label amounts as analysed contract volume.

### AUD 035 LLM requires independent quality control

**ID:** AUD-035. **Priority:** P2. **Evidence:** inactive OpenRouter prompt gives names/types/score without evidence; working explanation is deterministic. **Impact:** future unsupported accusations/source prompt injection; current GET cost/hallucinations not established. **Decision:** evidence JSON/rules determine score; LLM formulates validated structured text with fallback/versioning.

## External information and unverified access

KGD has an [official API catalogue](https://portal.kgd.gov.kz/pages/api-services). [Taxpayer lookup documentation](https://portal.kgd.gov.kz/ru/pages/info-services/find-taxpayer/_/attachment/download/591204a8-1450-4824-afc1-8298245e6f6c%3A7e918a95b376cd46c2af2f60a387d81996b03f47/ipn_ru%20%281%29.pdf) describes GET `taxpayer-data` and administrator-issued `X-Portal-Token`. This establishes documentation, not project access/token/quotas/debt/beneficial-owner coverage. Verify separately in Phase 3.

Current goszakup/Adata markup/completeness/access/selectors were not checked through mass live collection. Local reproductions establish code defects independently. OpenRouter model availability/cost/quality unverified; the original configured free model must become configurable when integrated. Define source access/personal IIN/publication/external transfer conditions for the specific pilot; this audit is not legal advice.

## Decisions for later phases

Fix P0/import integrity before adding sources. Parser relocation requires shared states/errors/checkpoints. Persist evidence/snapshots with matching explanation revision; changed membership creates a version, unchanged fingerprints reuse results. Similarity yields review candidates, not irreversible identity merges; verified BIN identifies companies. Add DRF to Django and React to API; Bootstrap decision awaits references. Thesis needs reproducible demonstration/rules/measured quality; pilots also need access/observability/recovery/limits. Record finding updates with date/check/change reference. **This document alone does not mean a defect is fixed.**
