# IZ2 project context for a research article

Analysis date: **5 October 2026**, Asia/Qyzylorda.

This document is for an assistant preparing an article without repository access. It describes implementation/data at the analysis checkpoint, then proposes a research topic and protocol. **The article experiment has not been performed; no experimental results are claimed.**

**Historical scope:** this assessment was prepared after Phases 0-1, before Phase 2. Its paths, database state, test counts, and implementation claims describe that checkpoint. The English translation preserves this record rather than presenting it as a new audit. For subsequent implementation, see [docs/PHASE2.md](docs/PHASE2.md) and the current [roadmap](docs/ROADMAP.md).

Basis: source/configuration reads, Phase 0-1 documents/local reports, repeated offline tests, and aggregate SELECT queries in source PostgreSQL REPEATABLE READ/read-only transactions. No company/person rows, contacts, credentials, or secrets are included. Preparing the original assessment changed neither application code nor source database.

## 1. Project description

### Problem and purpose

The user's thesis topic: "Development of an intelligent system for identifying potentially coordinated behaviour among public procurement participants using dynamic graph analysis, OSINT, and machine learning."

IZ2 is an unfinished thesis prototype for analysing relationships between Kazakhstan public procurement suppliers. It combines contracts/company records and shows shared contacts or director records. It helps analysts select and verify linked companies, then investigate whether those links relate to procurement behaviour.

The assumed audience is an analyst, auditor, or researcher. The legacy LLM prompt mentions financial intelligence, but this is not a confirmed user requirement. Organisation, roles, and pilot format remain unapproved.

The existing prototype workflow:

1. Import registry contracts and create suppliers by 12-digit identifier.
2. Enrich supplier cards from the supplier registry/Adata.
3. Compare shared directors, addresses, phones, and email; save groups/heuristic scores.
4. Open groups/company/director details; view graph/contracts/saved explanations.
5. Inspect matching evidence. The prototype establishes neither collusion, legal affiliation, damage, nor wrongdoing probability.

The thesis title sets a development direction. Dynamic procurement behaviour analysis and a trained model are not implemented capabilities at this checkpoint.

### Actual stack and structure

| Layer | Implementation |
| --- | --- |
| Backend | Python/Django ORM, class-based views, admin, commands |
| Storage | PostgreSQL; no separate graph database |
| Background jobs | Celery/Redis/django-celery-beat; automatic import off by default |
| Acquisition | HTML parsers, BeautifulSoup/curl_cffi/requests, date/contact/money normalisation |
| UI | Django templates/Bootstrap 5.3.7/custom CSS-JS/D3 v7 |
| Startup | Compose PostgreSQL 17/Redis 7/migrate/Gunicorn/worker/beat, frozen uv.lock, WhiteNoise |
| Checks | Django/unittest, in-memory SQLite, Node JS regressions; prior separate Docker PostgreSQL |

Installed versions at analysis: Python **3.13.5**, Django **6.0.6**, Celery **5.6.3**, beat **2.9.0**, WhiteNoise **6.12.0**, psycopg2-binary **2.9.12**, BeautifulSoup **4.15.0**, curl_cffi **0.15.0**, requests **2.34.2**, Pydantic **2.13.4**, Node **24.21.0**. Pydantic does not imply ML. Earlier Docker records specify Python 3.13.16/PostgreSQL 17.11, separately from local versions.

Historical control flow:

```text
Celery update_all_data, if enabled
  -> import_contracts command
    -> ContractRegistryParser -> transactional Supplier/Contract upserts
    -> enrich_suppliers -> enrich_supplier -> registry/Adata parsers
    -> build_clusters -> rebuild_clusters -> RiskCluster

GET -> current PostgreSQL data + saved clusters/text
    -> graph JSON from views -> browser D3
```

At this checkpoint parsers were in `services/`, with commands orchestrating import/enrichment. No unified ingestion service, observation journal, or stage state existed. Page edges were calculated on read, not from persisted evidence snapshots.

The target architecture proposes modular Django/DRF, React/TypeScript, observations/evidence, and graph/analysis/explanation versions in Phases 2-7. DRF/React/EvidenceEdge/ClusterSnapshot/AnalysisSnapshot/GraphViewState were absent.

### Version and checkpoint limits

Recorded HEAD: `fbe848903e27bb9de3f27ee5903aecfe30f76587`, obtained in the original assessment by reading `.git/HEAD`/ref without Git commands. HEAD excludes local changes; future reproducibility requires the actual source/parameter manifest.

The roadmap then marked Phases 0-1 complete and 2-8 planned. No statuses changed during that assessment. The source database lacked `graph.0003_cluster_analysis_state`; it had been tested on a restored copy only. Passing updated-code offline tests did not prove the updated UI could use the unmigrated source database.

## 2. Implementation status at the analysis checkpoint

"Offline verified" means isolated test data executed. "Implemented, limited verification" means code exists without complete/live verification. "Partial" means a subset only; "planned" means roadmap work absent from the application. Behaviour tests do not establish scientific effectiveness.

| Component | Status and code | Limits |
| --- | --- | --- |
| Contract collection | Offline verified; source rows exist. `services/contract_registry_parser.py`: ContractRegistryParser/ContractPage/fetch_page/parse_bin_data/iter_pages | Live markup/completeness unverified; contracts rather than all bids |
| Persistence/resume | Offline verified. import_contracts/Command.handle/update_or_create/SystemSetting | Atomic page/checkpoint; mutable pagination not full incremental sync; concurrent imports unlocked |
| Enrichment | Fixtures/mock HTTP. SupplierRegistryParser/parse_company_html/fetch_company_data/enrich_supplier | No per-field provenance/history; live HTML unknown; string updates do not confirm role history |
| OSINT | Partial registry/Adata public cards | No universal search/beneficiaries/news/courts/full evidence pipeline |
| Normalisation | Offline normalize_bin/date/amount/phone/email | 12-digit format, not full checksum/subject-type validation; limited address normalisation |
| People/roles | Partial; date filters verified. Owner/Director/Ownership/Directorship/current_role_filter/current_directorships | Source data has no IIN/role dates; automatic name linking off, old identities need review |
| Safe person identity | Planned; legacy link_directors still get_or_create(full_name), no longer called by pipeline | Explicit old command can still merge namesakes; no IdentityCandidate/verified matching |
| Link graph | Offline build_director_map/get_connection_types/find_connected_groups/build_graph_data | Pairwise current-field comparisons, four types, no source proof/separate confidence |
| Grouping | Offline find_connected_groups/rebuild_clusters/RiskCluster | Connected components of size >1, not collusion detection/trained clustering |
| Group stability/text freshness | Offline plus earlier PostgreSQL concurrency; match_clusters/analysis_fingerprint/graph.0003/tests | UUID/archive preserved; no full versions/lineage; source migration pending |
| Temporal analysis | Partial build_clusters --as-of/role intervals | Date-filtered roles, no evolving graph/auction windows/behavioural temporal features; contacts lack history |
| Suspicious groups | Partial matching groups/rating | No joint-bidding/price/winner-rotation analysis or verified violation labels |
| Risk | Heuristic execution verified, quality unmeasured; weights/calculate_risk/SystemSetting | Manual type/size weights; no calibration/probability/error evaluation |
| ML | Absent | No training pipeline/fit-predict/model artifact/features/dataset/metrics |
| Deterministic explanations | Function exists; some properties verified, ai/explainer.py | Current matches; no versioned background preparation; affiliation language too strong |
| Explanation display | Offline ClusterDetailView | GET reads/checks saved fingerprint without generation/writes; empty fallback |
| LLM | Inactive OpenRouter client, not live-verified | Empty Connection, string raises, no evidence/version/dedup controls |
| Visualisation | Implemented, selected safety checks | Zoom/pan/drag/labels/neighbour hover/company navigation exist; no type filters/evidence panel/saved layout/usability measurement |
| KGD/tax/court | Models only | Empty debt/bankruptcy/court tables; false/missing rows are not negative checks |
| Docker/background work | Full stack previously verified in Phase 1 | Not rerun here; no real collection/pipeline |

### Checks performed for the original assessment

| Check | Result | Limit |
| --- | --- | --- |
| Source/document reads | Models/parsers/orchestration/formula/graph/text/UI/roadmap reviewed | Not function execution/source verification |
| `.\.venv\Scripts\python.exe -B manage.py test --settings=config.test_settings --verbosity=1` | 83 discovered; **82 passed, 1 skipped**; system checks passed | SQLite, PostgreSQL concurrency skipped; HTTP mocked |
| `node tests/frontend_regressions.cjs` | Three search escapers/late-response guards/literal tooltip passed | No browser visual/usability study |
| Read-only PostgreSQL | Counts/dates/fill rates/contact frequencies/weights obtained | No per-row external verification; source unchanged |
| Prior Phase 1 reports | 83 PostgreSQL passes; migration/source/Compose passed | Historical runs, not reruns here |

Initial sandbox Python runtime access failed; approved runtime access let the same interpreter execute tests. This was an environment limitation, not a project defect. BASELINE/AUDIT contain historical states; current-at-analysis behaviour used code/status/PHASE1. The earlier GET-generation claim no longer matched code.

## 3. Research data

### Sources and fields

| Source/layer | Data | Limitation |
| --- | --- | --- |
| goszakup `/ru/registry/contract` | Contract/external/tender numbers, signing date, amount, supplier/customer/subject | No complete bidder/bid list |
| `/ru/egzcontract/cpublic/customer_n_supplier/<id>` | Party identifiers | 12-digit BIN/IIN accepted, no separate company/person type |
| `/ru/registry/supplierreg`, `/ru/registry/show_supplier/<id>` | Name/ID/director/address/region-city/KATO/contacts/residency/certificate date/size/legal form/economic sector/website | KATO/card ID returned but not saved; certificate date stored as registration_date, semantics unverified |
| Adata `/counterparty/main/company/<bin>/basic-info` | Name/director from BIN-checked title; labelled address/phone/email | No verified director IIN/owners/role history |
| Supplier | Current fields/create-update/enrichment timestamps | One value per field; adata_updated_at is overall successful enrichment, not Adata-specific history |
| Contract | Supplier/numbers/external ID/tender/subject/amount/date/customer BIN/winner/created_at | Import does not fill winner |
| Director/Directorship | Name/optional IIN/company/optional interval | No identity source/confidence; source dates empty |
| Owner/Ownership/debt/bankruptcy/court | Declared schema | Empty tables, not available observations |

Supplier.oked/company_status existed in model/enrichment field lists but were not returned by enrich_supplier. Both were empty throughout the source set.

### Verified size and fill rates

Read directly from the source during the original assessment; main counts matched Phase 0.

| Metric | Value |
| --- | --- |
| Suppliers/contracts/distinct contract suppliers | **384/500/384** |
| Contract date min/max | **18 June 2026 / 19 June 2026** |
| Nonempty tender ID | **318/500** |
| Nonempty customer BIN | **500/500** |
| winner=True | **0/500**: unfilled flag, not absence of winners |
| Supplier name/director string/address | **384/384/384** |
| Phone/email | **328/361** |
| adata_updated_at | **384**, not proof of field truth |
| OKED/company status | **0/0** |
| Directors/directorships | **384/384** |
| Director IIN | **0** |
| Known role start/end | **0/0** |
| Clusters/memberships | **4/11** |
| Nonempty saved explanations | **4**; field name does not establish text origin |
| Connection | **0** |
| Owners/ownership/debt/bankruptcy/court | **0/0/0/0/0** |

Four clusters were old saved state, not rebuilt during assessment; no current fingerprint/version/suspicion status can be assumed.

Repeated fields under existing exact address/phone and trimmed/lowercase email comparison, excluding two Adata service emails:

| Feature | Repeated values | Companies | Maximum frequency | Same-type pairs |
| --- | --- | --- | --- | --- |
| Address | 1 | 2 | 2 | 1 |
| Phone | 2 | 7 | 5 | 11 |
| Email | 1 | 2 | 2 | 1 |
| Shared director record | 0 | 0 | - | 0 |

Pair counts cannot be summed as distinct pairs/groups; one pair may match several types. These are field observations, not shared organisation/coordination proof. Nonempty fields are not necessarily valid/current.

### Real, synthetic, and unavailable data

Source PostgreSQL is intended to contain imported records; row presence/aggregates were verified, but original responses/per-field provenance/collection protocol were absent. Truth or freedom from demo/error values was not established for every row. Ask the author about acquisition and verify a sample before publication; never call it a fully verified national dataset.

HTML fixtures/test objects are synthetic companies/IDs/amounts for regressions. Fixture date 24.01.2020 does not extend the source period. Fixtures do not evaluate real procurement effectiveness. No research dataset/expert labels/confirmed violation corpus was found.

Coverage is contract parties, not all bidders/rejected bids/submission dates/prices/lots/admission/outcomes. Tender IDs cannot reconstruct missing information. Contract amount is not each bidder's offer; contract supplier does not justify the unfilled winner flag.

Contract dates/technical timestamps and optional role intervals offer limited temporal fields: two adjacent contract dates, unknown role dates, no contact/edge-version history. Creation/update times are system actions, not relationship periods. Archives read current company fields, not historical snapshots.

No reliable coordination labels exist. Contact/director matches, scores, and groups cannot be positive collusion labels; their absence cannot create negative labels. Empty debt/court tables mean missing observations.

## 4. Methods actually used

### Nodes, edges, groups

Displayed nodes are Supplier records identified by internal ID, with unique BIN strings. Directors/owners/customers/contracts are not separate graph nodes.

- **director:** intersect director-record IDs whose roles pass the date filter;
- **address:** equal nonempty addresses;
- **phone:** equal nonempty phones;
- **email:** equal nonempty trimmed/lowercase emails, excluding Adata service values.

Address/phone comparison adds no normalisation; ingestion normalises phones, legacy values may differ. Director IDs inherit earlier identity quality and do not eliminate name-merge risk.

Connection declares owner/customer/weight/description/date but is not populated/used by grouping. Shared owner/customer does not create a working edge; default weight 1 is not displayed-edge weighting.

find_connected_groups compares all pairs and uses union-find for components larger than one. A-B-C joins even without A-C. Membership neither implies every pair's evidence nor common behavioural risk.

Pair complexity is O(n squared). Prefetch removes per-pair SQL, not comparisons. UI can show multiple typed edges per pair and one per shared director. Scientific runtime/scalability measurements are absent.

### Heuristic formula

T(C) is the set of matching types found anywhere in group C, n its size:

```text
R(C) = min(100, sum(w[t] for t in T(C)) + max(0, n - 2) * w[group_size])
```

Each type contributes once per group regardless of pair count. No per-edge reliability/common-contact frequency/bidding behaviour; contract amounts do not enter.

| Parameter | Default | Effective source value |
| --- | --- | --- |
| Shared director | 35 | 20 |
| Shared address | 25 | 15 |
| Shared phone | 20 | 10 |
| Shared email | 15 | 10 |
| Company beyond two | 5 | 5 (no override) |

SystemSetting overrides are integers bounded 0-100. Reproducibility requires actual weights; current values do not prove how historical scores were calculated.

Arithmetic illustration: defaults give 19 shared-email companies 15 + 17 * 5 = 100; source weights give 20 companies 10 + 18 * 5 = 100. These are analytical examples, not discovered groups or new experimental results.

UI levels high >=80, medium >=50, otherwise low, without calibration. Nodes get group score, not personal company assessment. Supplier.risk_score is separate and is not retrained/updated by rebuild_clusters. Decimal contract totals are analysed volume, not damage, despite dashboard's money_at_risk name.

### Updates, time, explanations

Rebuild preserves exact membership UUIDs. match_clusters uses overlap, intersection/union ratio, deterministic ties; one old UUID continues once, vanished groups archive. This is identifier continuity, not organisational identity/full lineage.

Fingerprint hashes canonical members/current contacts/selected roles/owners/contracts/weights/format version. Changed facts mark text stale, without preserving old graph or all neighbouring-company state. Outside-membership changes appear after rebuild.

--as-of includes starts <= date, ends > date: `[start_date, end_date)`. Unknown bounds permit comparisons without proving validity. Dates cannot reconstruct old contacts/contracts. Date itself is absent from fingerprint; selected roles change instead of storing a temporal snapshot.

Regular updates/current graph recalculation/technical timestamps/period-filtered contracts are not relationship evolution analysis. No window comparisons/temporal edge appearance-disappearance/motifs/bidder rotation. Describe partial date filtering and plans, not a completed dynamic detector.

Deterministic explainer groups exact matches and adds owner flags/heuristic level; affiliation language needs moderation. Rebuild/GET do not automatically call it; GET shows stored text/staleness. No ML features/training/splits/data-trained weights/inference. OpenRouter text generation is not training a coordination detector; configured qwen/qwen3-8b:free was not live-checked for availability/cost/quality.

## 5. Article topic selection

All topics are narrower than the thesis. Extra-work estimates describe tasks, not unverified deadlines.

| Topic | Question | Inputs/methods | Additional work |
| --- | --- | --- | --- |
| **1. Impact of shared contacts on robust graph grouping of Kazakhstan suppliers** | How do single/common contacts alter groups, and what remains under stricter edges? | Frozen contacts, independently confirmed relations where available, synthetic known groups; components/ablation/multiple-evidence rules/errors | Offline runner/variants/data sheet/labels/scenarios/measurements; existing graph core, no new ML needed |
| **2. Stable supplier-group identifiers during repeated graph updates** | Do UUID continuity/fingerprints retain unchanged results and detect changes? | Controlled repeat/add/remove/merge/split/contract changes; recreate-all baseline/invariants/writes/stale texts | Independent protocol/continuation criteria/benchmark; lineage absent |
| **3. Temporal applicability of director links** | Does proven role overlap reduce false links versus aggregating all roles? | Confirmed identities/intervals/history, synthetic changes; all-role graph versus date/overlap slices | Historical data/identity repair/temporal prototype; actual intervals absent |

**Topic 1 recommended:** it uses working components and a reproducible scoring weakness: common contacts merge companies and inflate size-based scores. It needs neither unavailable bids, trained ML, KGD, nor LLM. Contacts exist; controlled scenarios expose failures.

Topic 2 is technically prepared but closer to software reliability. Topic 3 fits dynamics but needs stronger identity/time data. Topic 1 still lacks independent relation labels, provenance, and a separate experiment pipeline. The small 384-company set/few matches supports preliminary sensitivity, not national coordination-detection effectiveness. Predominantly synthetic evaluation must be explicit and approved by the supervisor.

## 6. Recommended article foundation

**Title:** "The Impact of Shared Contact Information on the Robustness of Graph-Based Grouping of Public Procurement Suppliers in Kazakhstan".

**Question:** how do single/common contact matches change grouping, and can stricter rules reduce false mergers with acceptable loss of confirmed relations?

**Goal:** reproducibly evaluate grouping sensitivity and limits relevant to analysts.

1. Formalise existing edges/components/score and record parameters/data limits.
2. Prepare the working-data sheet and independent synthetic scenarios, separating matches from relations.
3. Compare baseline, contact-type ablations, and a conservative multiple-evidence rule.
4. Measure false merges/missed true relations on labels and structural changes on source data.
5. Recommend weak-link display and non-accusatory interpretation.

**Object:** supplier/concluded-contract information in an analytical system. **Subject:** effects of contact rules on group structure/interpretation reliability.

**Expected contribution:** reproducible rule comparisons, common-contact/transitive scenarios, merger-versus-loss trade-offs, uncertainty-display requirements. Novelty/superiority are unproven until full literature review/experiment.

**Keywords:** public procurement; graph analysis; supplier relationships; OSINT; shared contacts; grouping robustness; explainability.

An abstract must ultimately state actual inputs/rules/results. Until then use a proposal abstract without numerical results or trained-model claims.

## 7. Article outline

| Section | Content/material |
| --- | --- |
| Introduction | Preliminary relation analysis versus bidding behaviour; question/scope; no unsupported national statistics |
| Related work | Procurement graphs/screening/identity/common contacts; verified starting sources then full comparative review; no premature literature-gap claims |
| Data | Sources/period/fields/missingness/provenance/working-synthetic distinction/label meanings; read-only aggregates/data sheet |
| Method | Nodes/typed exact matches/components/formula/alternatives/unknown relations; code-linked pseudocode |
| Experiment | Frozen inputs/weights/ablations/manual review/scenarios/metrics/reproducibility; tests verify execution, not effectiveness |
| Results | Coverage then groups/errors/cases/score sensitivity; actual denominators/unknown, "not measured" until run |
| Discussion | Bridges/strict-rule cost/small set/identity/evidence dependence/transferability; robustness differs from truth/collusion |
| Conclusion | Answer within measured scope; required future data; dynamics/ML/KGD as future work |

### Initial verified references

These links were checked during the original assessment. This is a starting list, not a systematic review. Research metadata/abstracts were read; study full texts before detailed method descriptions.

1. Johannes Wachs, Mihály Fazekas, János Kertész. **Corruption Risk in Contracting Markets: A Network Science Perspective**. 2019 preprint, [arXiv:1909.08664](https://arxiv.org/abs/1909.08664). Bipartite customer/recipient networks differ from this supplier-contact graph; their findings are not IZ2 results.
2. David Imhof, Hannes Wallimann. **Detecting bid-rigging coalitions in different countries and auction formats**. 2021 preprint, [arXiv:2105.00337](https://arxiv.org/abs/2105.00337). Coalition screening/ML uses bid prices; without bids, methods/metrics cannot be transferred to current contacts/contracts.
3. OECD. **OECD Guidelines for Fighting Bid Rigging in Public Procurement (2025 Update)**. [Official document](https://www.oecd.org/content/dam/oecd/en/publications/reports/2025/09/oecd-guidelines-for-fighting-bid-rigging-in-public-procurement-2025-update_127880ea/cbe05a56-en.pdf), DOI `10.1787/cbe05a56-en`, section 3.6. Distinguishes indicators from collusion proof; methodological context, not labels/legal conclusions for this sample.

Search primary literature on entity resolution/common-contact false links/group sensitivity. Novelty of this rule combination is not established.

### Tables and figures needed

Tables: sources/fields/period/missingness/labels with real/synthetic separation; edge normalisation/criteria/weights/limits; frozen comparison rules; typed/distinct edges/groups/size/grouped share; false merges/splits and eligible precision-recall with unknown/coverage; anonymised cases/evidence/alternatives/decisions.

Figures: actual source-normalisation-matches-components-analyst flow; controlled service-contact versus multi-evidence cases under different rules; A-B-C without direct A-C; analytical single-contact score-versus-size curves for both weights, separately from measurements; useful anonymised reviewed graph with legend/unknowns.

D3 screenshots illustrate UI, not detection quality. Do not publish source names/contacts without an explicit permitted-data decision.

## 8. Experiment plan

**Status:** proposed protocol; runner/alternative rules/research labels/measurements absent. This document does not start a development phase.

### Target and data

Measure grouping sensitivity and controlled false-merger mechanisms, not collusion detection.

- **A: synthetic known relationship structure.** Author-defined shared control/leadership or independence, not violation labels. Service contacts may differ from this structure.
- **B: frozen 384 suppliers/500 contracts.** Describe graph/review candidates; true coordination unknown. At most 13 contact candidate pairs from frequencies, possibly overlapping types. A data sheet must establish provenance/completeness.

Label direct relations and true partitions separately. Membership cannot automatically supply direct-edge truth. If only partitions are labelled, use partition metrics, not direct-relation precision/recall.

Prepare these eight future scenarios:

| Scenario | Independent truth | Check |
| --- | --- | --- |
| Verified shared director | Stable synthetic person/known overlapping roles | Preserve link without contacts |
| Two contact types | Related pair sharing phone/email | Multiple observations do not guarantee independent evidence |
| Single true-contact basis | Related pair, one shared contact | Strict-rule false negative |
| Mass service phone | Independent companies/intermediary phone | Large false component/score inflation |
| Business-centre address | Independent companies/common address | Address false links |
| Contact bridge | Two true groups, one weak cross-link | Whole-group false merger |
| Noise/incomplete contacts | Known group/missing phones/formats/email case | Separate extraction/normalisation losses from grouping errors |
| Namesakes | Different people, same names/different IDs | No name-only identity; unsafe legacy variant separately |

Vary common-contact size with predefined values such as 2/5/10/19/20. These are future parameters. Deterministic runs need no randomness; generated variants require seed/full configuration. Separate debugging/final scenarios so evaluation does not merely repeat regressions.

### Compared methods

| Variant | Rule | Status |
| --- | --- | --- |
| M0 current | Any of four features connects a pair; components | Implemented |
| M1 ablations | Same method excluding address/phone/email individually | Proposed, shows feature contributions |
| M2 conservative | Verified shared director or >=2 contact types; other matches remain weak candidates outside grouping | Proposed comparator, not implemented/proven superior |

An unverified source director ID is not confirmed evidence for M2. A labels status independently; B keeps unknowns. Two contact types can share one intermediary, so M2 can still fail.

Compare structure first and score separately. Freeze default/source weights for M0/M1; never choose weights by final-test success. M2 scores are not probabilities without calibration. Static/dynamic comparison is unnecessary here because history is missing.

### Execution protocol

1. Freeze permitted inputs/data sheet: sources/retrieval/fields/period/missingness/normaliser/limits/data-code hashes/Python/dependencies/weights. Anonymisation must preserve equalities/frequencies and graph output.
2. Use separate inputs/SQLite or isolated PostgreSQL. Do not migrate/rebuild source for research. Extract by SELECT only; no import/live enrichment/Celery/LLM.
3. Build an offline runner using pure comparison/group functions, implementing M1/M2 separately. Check row-order invariance, no empty-contact edges, repeatability, no implied direct links from transitivity.
4. Freeze labels/rules/parameters/metrics before final evaluation; debug separately.
5. Run variants on identical inputs; save memberships/typed-distinct pairs/evidence/sizes/scores. Include singleton blocks in partition metrics even when omitted by UI.
6. Review all source contact matches/bridges; optionally predefined random unmatched pairs for missing links, without claiming population recall. Use documents, not scores.
7. Report A/B/scenarios/types separately, retaining unknowns and both benefits/failures of strict rules.

Review answers should separate actual contact equality, documented relationship, common servicing without established relationship, and insufficient evidence. Equality is not relation proof; missing confirmation is not independence. Prefer two reviewers blinded to rankings, recording disagreements; disclose single-author review.

### Metrics and interpretation

| Metric | Applicability | Meaning |
| --- | --- | --- |
| Typed/distinct edges/components/largest/grouped share | A/B | Structure, not improvement by itself |
| Retained co-membership pairs/Jaccard after ablation | A/B | Sensitivity, not truth; handle empty sets explicitly |
| Independent pairs grouped / all independent pairs | A; B only with confirmed negatives | False transitive mergers |
| True-group pairs separated / all true-group pairs | A; B with sufficient labels | Strict-rule cost |
| Direct relation precision/recall/F1 | Independently labelled A/B relations | TP/FP/FN distinct from component membership |
| Confirmed/false/unresolved candidates/review coverage | B | Denominators/unknown required; no overall accuracy with incomplete labels |
| Single-feature size/score/threshold crossings | A; B descriptively | Heuristic/weight sensitivity, not collusion probability |
| Runtime/SQL if included | Same environment/separate load series | Secondary engineering measure, not effectiveness |

Precision TP/(TP+FP), recall TP/(TP+FN); zero denominator: "undefined" plus counts. Direct edges and co-membership need separate confusion matrices. Dependent within-group pairs are not independent confidence-interval samples. Emphasise absolute counts/cases on small data.

Synthetic scenarios test mechanisms under their assumptions; unlabelled source data supports structure/sensitivity/verifiability only. Neither establishes cartel prevalence/wrongdoing probability/damage/complete detection/nonexistent ML quality. Stable groups can still share a service intermediary.

No training in the minimum experiment. Future bids/independent labels require a new time-based train-validation-test protocol with only then-available facts and separation of recurring companies/groups, plus unseen-company evaluation. Random contract-row splits leak company/fact information. Freeze rules/weights before final evaluation.

## 9. Work still needed

These are future tasks, not completed work or phase-status changes.

### Required

1. Agree on research goal/data format with supervisor: robustness/synthetic acceptability, actual-sample requirements, length/venue.
2. Prepare frozen inputs/data sheet; relate 384/500 to acquisition and contact provenance. Use models/historical services/BASELINE. Sensitive research data stays in ignored artifacts, not public fixtures.
3. Define labels/unknown; separate matches, relations, membership, coordination. Do not generate truth using name-only link_directors. Independent synthetic structure minimum; real conclusions need documents.
4. Build offline experiments around get_connection_types/find_connected_groups/calculate_risk, without mutating rebuild_clusters. Implement alternatives/scenarios/reports; app tests/test settings aid execution but research targets must be broader.
5. Freeze both weight sets/input-code hashes/memberships/errors; passing tests are not experimental results.
6. Complete full-text review/targeted literature search; write results after running. No "first"/"proven superiority" claims yet.

Source graph.0003 migration was unnecessary for read-only assessment. Future updated-model/UI experiments need an isolated migrated DB; source upgrade is separate after a current verified backup.

### Recommended improvements

1. Broader periods/categories with predefined sampling; live collection requires separate instruction, 500 contracts do not represent the market.
2. Independent source confirmations/review of common contacts/legacy extraction errors.
3. Proposed contact-frequency variant, separately evaluated against M2 and future Phase 4-5 evidence/rules.
4. Pairwise versus indexed building across sizes, separately from relation quality.
5. Anonymised illustrations/edge evidence inspection; final style awaits references.

### Further thesis development

- Phase 2 ingestion/runs/observations/safe identity/role history (future at this checkpoint).
- Phase 3 verified KGD/distinct check states.
- Phase 4 immutable snapshots/lineage/evidence/layout/graph improvement.
- Phase 5 calibrated bidding analysis/versioned findings/explanations/controlled LLM if useful, data-dependent.
- Phases 6-7 DRF/React/TypeScript/reference-based UI.
- ML/dynamic bidding features/effectiveness only after bids/history/labels, not automatically after refactoring.
- Phase 8 demonstrations/load/roles/pilot, then approved follow-up work.

## 10. Brief handoff

**Historical project:** unfinished Kazakhstan supplier-link thesis prototype, Django/PostgreSQL/Celery/Redis/templates/Bootstrap/D3. HTML collection/contact matches/components/manual scoring/saved text; Phases 0-1 complete at assessment, no trained ML/full dynamics. Later Phase 2 changes are separately documented.

**Recommended topic:** shared-contact impact on grouping robustness, comparing current components/type ablations/proposed strict edges. A research plan, not completed results.

**Data:** read-only 5 October 2026: 384 suppliers, 500 contracts dated 18-19 June 2026, 384 directors/roles without IIN/dates, four old clusters/11 memberships. Phones 328/emails 361/addresses 384; repeated address 1/phones 2/email 1; no shared director records. No owner/debt/bankruptcy/court/Connection records. Provenance unverified per row; fixtures synthetic. No complete bids/history/coordination labels.

**Checks:** original assessment 82/83 passed on SQLite with PostgreSQL skip, JS passed; earlier Phase 1 83/83 PostgreSQL and Compose/restore passed. Source graph.0003 was pending and source unchanged. Regressions are not research results.

**Limits:** contacts do not prove control, groups do not prove collusion, scores are not probabilities, totals not damage. Never train on cluster membership as truth. Date-role filters/database updates are not dynamic behaviour analysis. Source weights 20/15/10/10/5 versus defaults 35/25/20/15/5 must be recorded.

**Next research steps:** approve topic/synthetic scope; review literature; prepare data sheet/frozen inputs/labels; build offline runner; run; report absolute counts/unknown/limits. The entire roadmap need not be completed for an article.

### Questions for author/supervisor

1. Venue/language/length/template/deadline/article type: proposal now or finished experiment?
2. Is grouping quality without ML/full dynamics acceptable, including mostly synthetic evaluation?
3. How/when/with which filters were 500 contracts/cards acquired? Manual/demo records/confirming responses?
4. What source data may be published/shared, and how anonymised?
5. Independent expert/confirmed relations/director history/official coordination cases available?
6. Complete bidder/bid/price/lot-history/longer-period sources available? Not established by repository.
7. Are ML/dynamics mandatory in the article or future thesis work? Required literature comparator?

### Repository navigation for the historical checkpoint

| Material | Purpose |
| --- | --- |
| ROADMAP/ARCHITECTURE | Status/target, not proof of future implementation |
| BASELINE/RECOVERY | Initial counts/backups/verification boundaries |
| PHASE1/AUDIT | Verified fixes/remaining methodology; historical wording |
| Company/contract/owner models | Actual schema |
| Historical services/company commands | Acquisition/normalisation/orchestration; moved in Phase 2 |
| Graph services/models/views | Links/groups/score/UUID/fingerprint/data |
| ai/explainer and openrouter | Separate deterministic/inactive LLM paths |
| App/tests/fixtures | Synthetic regressions, not scientific benchmark |
| Graph JS/cluster detail | UI |

Implementation statements refer to the original analysis checkpoint. Update context before using later functions/data in an article.
