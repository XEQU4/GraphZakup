# Phase 5: analysis and explanations

Status: complete on 7 October 2026 for the implemented services: 238 PostgreSQL
tests and five real local-model synthetic cases passed. Phase 5 was authorised
that day after the user
requested a free model, configurable future paid APIs, and consideration of model
scoring if it improves the baseline. Phase 6 has not started.

## Implemented behaviour

The published score is a versioned **review-priority index**, not a probability
of wrongdoing. Identity, relationship strength, company financial indicators,
behavioural risk and data coverage have separate meanings. The default rules are
`review-rules-5.0`; they consume saved graph evidence, retained KGD observations
and stored contract records. Missing bidding data leaves behavioural risk
`not_assessable`, rather than zero. Contract volume is not damage.

| Pattern | Candidate review points | Limits |
| --- | ---: | --- |
| Identifier-confirmed shared owner | 35 with known intervals; otherwise 20 | Unknown legal boundaries require confirmation |
| Identifier-confirmed shared director | 25 with known intervals; otherwise 15 | Names alone cannot create this finding |
| Confirmed person across different roles | 20 with known intervals; otherwise 10 | Used where no same-role shared pattern exists for that person |
| Shared address | 2 | Weak recorded match |
| Shared phone/email | 5 | Weak recorded match |
| Contact used by more than 20 companies | 0 | Does not establish affiliation |
| Recent dated positive company arrears | 20 | Attached only to the checked company; a latest failed attempt remains visible |
| Stored contracts, shared buyers, zero/missing/stale arrears | 0 | Descriptive facts or coverage limits |

Each category credits its strongest finding once. All contact findings together
contribute at most 5 points; relationship contributions are capped at 50 and
financial contributions at 20. There is no company-count bonus. Current rules
therefore reach at most 70 on a 0-100 display scale. Weights and the separate
relationship-strength index are conservative heuristics without calibration.
Every credited point has a saved finding and evidence references.

Arrears inputs revalidate the exact company BIN, all five Decimal amounts and
reporting dates. The oldest reporting date determines freshness against
`KGD_RESULT_MAX_AGE_DAYS`. A failed latest attempt retains the dated last success,
but excludes the company from successful current-check coverage. A recent
retained positive result can still support review; a retained zero is a dated
past fact, not proof of current absence. Old, undated, invalid and missing checks
cannot produce a current zero or financial points.

Group pages and list filters use the saved review priority for the current graph.
Pre-analysis groups, company summaries and dashboard compatibility metrics retain
explicitly labelled legacy indices. Existing legacy fields/texts are preserved;
this phase does not rewrite their historical meaning.

## Persistence and change handling

Schema-only migrations `ai.0001_initial` and `ai.0002_analysistarget` add:

- `AnalysisSnapshot`: immutable copied inputs, findings, metrics, limitations,
  rule version, analysis date, input hash and analysis hash, bound to one exact
  `GraphSnapshot` and cluster version.
- `Explanation`: immutable English template or validated model presentation,
  provider/model, prompt version, usage, safe error code and optional experimental
  score. Language is already part of reuse keys for later localisation.
- `AnalysisState`: the currently published analysis and explanation for a group.
- `AnalysisJob`: durable request, status and exact result references.
- `AnalysisTarget`: the latest explicit request, fencing older workers even when
  they target the same analysis with different providers or settings.

Migrations create no analysis rows, synthetic evidence or graph rebuilds.
`refresh_graph_analysis` is the shared production path used by graph jobs,
`build_clusters` and the ingestion cluster stage. An authorised graph refresh
atomically prepares affected analyses and template texts as well as graph
versions. Adding a linked company updates the graph, analysis and template;
unchanged repeats retain versions and any valid saved model presentation. Pure
graph computation remains available for graph fixtures and compatibility.

Semantic hashes ignore retrieval-only observation IDs/times. Meaningful graph,
KGD, contract or rule changes create analysis versions; freshness-category changes
also count. Text reuse includes the exact analysis binding, hash, language,
template/prompt version and provider configuration. Personal layouts do not affect
analytical hashes. No hidden LLM call occurs after collection or graph refresh.

GET reads saved results, reports changed saved KGD/contract inputs as stale, and
never calculates or generates. Changes to role/contact inputs require explicit
graph refresh. Historical views select text from completed published jobs, falling
back to the saved template; superseded output stays in history but is not shown
as the published explanation.

Staff POST with CSRF starts deduplicated background work through Celery. CLI uses
the same services. Analysis preparation shares the ingestion lease; the lease is
released before model inference. Publication rechecks graph/input/analysis,
configuration, prompt and latest-request versions. Broker failures are visible.
Provider failure publishes a saved template fallback; retry requires an explicit
request. An unchanged completed request makes no further HTTP call.

Temporary endpoints are `/analysis/<cluster-uuid>/`, its `start/` POST and
`/analysis/jobs/<job-uuid>/`. They use Django sessions; the DRF boundary belongs to
Phase 6. `analysis_version` selects history within the chosen graph `version`.

## Model role and scoring decision

The default provider is `template`: the application needs no model to explain its
results. The free local candidate is Ollama `qwen3:4b`, approximately 2.5 GB of
quantised weights. Local inference has no hosted daily token allowance, but is
limited by available memory, context, runtime and electricity. The inspected
computer has about 16 GB RAM and an RTX 4060 Laptop GPU.

The model receives computed findings and selects their order and predefined
English wording variants. It cannot add arbitrary prose, numbers, identities or
edges. A closed JSON schema and server-side validation require each allowed
finding exactly once. Company names, BINs, IINs and contact values are omitted
from the prompt; company labels are inserted by the renderer after validation.
Large analyses keep all saved findings, while model assistance is bounded to the
configured subset. This is presentation assistance, not unrestricted narrative
generation. Its readability advantage over templates remains unverified.

`AI_EXPERIMENTAL_SCORING=true` additionally allows a separate model estimate with
allowed finding IDs. It is stored for staff evaluation, never used as the public
score, graph weight, identity decision or rule contribution. The experimental
prompt includes factual limitations and excludes numerical rule points, avoiding
direct copying of the baseline. No independent labelled benchmark exists, so
model superiority is unknown. Keeping the
public score checkable is the current decision under the user's discretion.

`evaluate_scores` compares independent analyst review-priority labels with rule
and model indices using MAE, RMSE and overestimation frequency. It never promotes
a model. Promotion needs a defined prediction target, company/component-disjoint
held-out cases, time-aware evaluation, acceptable false positives and stable
results. Synthetic cases test mechanics, not real-world prediction quality.

## Configuration and operation

Existing `.env` was preserved. Add the desired settings manually from
[.env.example](../.env.example), then restart web and worker. Defaults are:

```dotenv
AI_PROVIDER=template
AI_MODEL=
AI_MODEL_REVISION=
AI_BASE_URL=
AI_OLLAMA_BASE_URL=http://127.0.0.1:11434
AI_API_KEY=
AI_ALLOW_PAID=false
AI_EXPERIMENTAL_SCORING=false
AI_TIMEOUT_SECONDS=90
AI_MAX_OUTPUT_TOKENS=1024
AI_MAX_INPUT_CHARS=8000
AI_MAX_FINDINGS=12
AI_CONTEXT_TOKENS=4096
```

For free local generation use `AI_PROVIDER=ollama`, `AI_MODEL=qwen3:4b` and the
native Ollama base URL. Local endpoints/models are restricted; cloud model tags
are rejected. Requests disable proxy inheritance, redirects and thinking, set
explicit context/output/time limits, validate bounded JSON responses, and keep
only allowlisted usage values and safe failure codes.

For Compose, set `AI_PROVIDER=ollama`, `AI_MODEL=qwen3:4b`, `OLLAMA_MODEL=qwen3:4b`
and leave `AI_BASE_URL` empty. The `local-ai` profile adds Ollama 0.40.0, persistent
`ollama_models`, a health check and a one-shot model pull; the worker waits for
initialisation. Ollama has no exposed host port and cloud use is disabled.

```powershell
docker compose --env-file .env.docker --profile local-ai up --build -d
```

The default profile starts without Ollama. Host Ollama from application containers
uses `AI_BASE_URL=http://host.docker.internal:11434`; Linux Docker GPU access needs
separate verified setup. Profile configuration is checked; actual profile startup
and container GPU inference have not been verified in this phase.

For a future paid API, configure `AI_PROVIDER=openai`, `AI_MODEL=gpt-4o`,
`AI_BASE_URL=https://api.openai.com/v1`, a private `AI_API_KEY` and
`AI_ALLOW_PAID=true`. GPT-4o API use is paid; a ChatGPT subscription does not make
it a free API. `openrouter` is also supported; free models have cloud limits and
must support this strict output contract. No paid request or remote model
inference was performed. There is no automatic provider failover.

Model aliases can change upstream. Pin a model/version and update
`AI_MODEL_REVISION` when changing weights so reuse is invalidated. This manual
label is saved with requests/usage; the app does not automatically resolve a tag
to an immutable weight digest.

After a current verified backup, apply the schema and prepare existing graphs:

```powershell
uv run python manage.py migrate
uv run python manage.py analyse_clusters
```

These commands perform no source collection or model request. If graphs have not
been published yet, explicitly run `build_clusters` first; it now also saves
affected analyses/templates. With a configured model and running worker:

```powershell
uv run python manage.py analyse_clusters --cluster YOUR_CLUSTER_UUID --use-model
# Explicitly retry a previously failed model request:
uv run python manage.py analyse_clusters --cluster YOUR_CLUSTER_UUID --use-model --retry-model
```

Staff graph pages expose equivalent template/model POST actions and a retry
checkbox. Jobs report pending/running/succeeded/fallback/stale/failed states.
Windows Celery development uses `--pool=solo`; Compose runs the supported Linux
worker. Keep automatic collection disabled unless separately authorised.

The native verification runtime is retained under ignored `artifacts/phase5/`.
Its cache is separate from the global Ollama cache and the Docker volume. After
verification stops its temporary server, it can be started locally on the normal
port with the retained cache:

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = (Join-Path (Get-Location).Path 'artifacts/phase5/ollama-models')
$env:OLLAMA_NO_CLOUD = '1'
Start-Process -FilePath (Resolve-Path 'artifacts/phase5/ollama/ollama.exe').Path -ArgumentList 'serve' -WindowStyle Hidden
```

Use an available port and align `AI_BASE_URL` when an existing server already
occupies 11434. A separately installed Ollama can use its normal `ollama serve`
and `ollama pull qwen3:4b` workflow. Starting this server does not change Django
settings or start Redis/Celery; select the provider and run the application worker
separately, or use the full Compose profile above.

Evaluation file format (independently labelled cases are still required):

```json
[
  {"case_id": "case-001", "label_priority": 10, "rule_score": 12, "model_score": 15},
  {"case_id": "case-002", "label_priority": 40, "rule_score": 35, "model_score": 45}
]
```

Run `uv run python manage.py evaluate_scores path/to/private_labels.json`.
The numbers above illustrate the format and are not benchmark findings.

## Verification

The migration protocol used a freshly checksum-verified, independently restored
PostgreSQL 17.6 backup. All 45 tables matched; migration preserved original values
in all 44 tables outside migration history and left the five new AI tables empty.
The working database was neither migrated nor recalculated. The original
`test.py`, `pyproject.toml` and `uv.lock` hashes match the preserved baseline;
`.env` was not edited. A credential-value scan of 206 source/documentation files
found no matches, including values from the private per-company account map.

Regression coverage includes weak/mass contacts, repeated categories, known and
unknown role intervals, mixed roles, exact contract money, invalid/stale/retained
KGD results, meaningful/retrieval-only version changes, graph/template rollback,
immutable history, read-only GET, published historical texts, staff/CSRF, broker
failure, request deduplication, expired/stale/configuration-changed workers,
latest-request fencing, blinded experimental scoring and bounded HTTP adapters.
OpenAI transport is tested against a synthetic HTTP response without remote
generation. All 238 tests passed on isolated PostgreSQL, including three
PostgreSQL-only concurrency scenarios. Generated restore/test databases were
dropped after verifying ownership. No source parsing, ingestion pipeline or paid
model request was run.

Both Node.js suites passed: frontend escaping/obsolete responses and graph
interaction/layout/filter/path/literal-text checks including 8/50/500-node data.
Migration drift check reported no changes. Default and `local-ai` Compose
configurations passed `config --quiet`; this is configuration validation, not
container startup or a visual/browser performance benchmark.

### Actual free local model probe

Official portable Ollama 0.40.0 and `qwen3:4b` Q4_K_M weights were downloaded and
checksum-verified into ignored artifacts. The registered model digest was:
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
An owned temporary server on `127.0.0.1:11435` used cloud-disabled local inference;
its runtime state showed CUDA on the RTX 4060 with approximately 3.18 GB allocated
in VRAM and 4096 context tokens. This does not verify GPU use in Docker.

Five final synthetic cases passed through the real application job/provider,
closed output validation, saved publication, GET and completed-result reuse.
Model assistance used the bounded finding subset, not every dense-graph finding.

| Case | Companies | Seconds | Input / output tokens | Published priority |
| --- | ---: | ---: | ---: | ---: |
| Weak contacts | 2 | 6.417 | 559 / 132 | 2 |
| Confirmed roles, unknown legal boundaries | 2 | 6.416 | 679 / 161 | 17 |
| Long labels | 8 | 8.900 | 962 / 343 | 2 |
| Dense contact group | 20 | 10.917 | 1167 / 436 | 2 |
| Blinded experimental estimate | 2 | 6.281 | 490 / 196 | 2 |

The last case stored model estimate 2 separately; equality with the rule value
on one synthetic case is not an accuracy result. Each repeat reused its completed
job with model HTTP calls forbidden. No provider fallback occurred in these five
cases. The initial installation probe's first request took 75.212 seconds;
subsequent probes were faster. These are single-machine measurements, not
percentile latency targets or a universal timeout guarantee. Unsupported-claim
validation passed within the closed wording contract; independent readability,
real-world prediction and superiority over templates/rules remain unverified.

The owned verification server was stopped after the probe. Runtime/cache and
synthetic databases remain in ignored `artifacts/phase5/`, outside Git/images.
Reports: `postgresql-verification.json`, `model-probe.json`,
`model-probe-before-blinding.json`, `repository-check.json`, and the fresh backup
report named in [RECOVERY.md](RECOVERY.md). Working data stayed unchanged.

Primary references checked on 6-7 October 2026:

Follow-up, 7 October 2026: user-applied AI migrations were confirmed read-only.
Reusable Windows startup and synthetic probe scripts were added. Four further
real local cases passed (weak contacts 2/100, known shared-director intervals
27/100, twenty-company contact group 2/100, separate experimental estimate).
Requests took approximately 7-12 seconds; repeat requests reused completed jobs.
Public brand/package changed to IZ2/iz2 after verification, preserving all 50
working tables and dependency versions. `--serve-saved` reopens the synthetic
demo without inference. Current user actions are supplied directly in chat.

- [Qwen3:4b weights and licence](https://ollama.com/library/qwen3:4b)
- [Ollama local execution and context](https://docs.ollama.com/faq)
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Ollama Windows portable runtime](https://docs.ollama.com/windows)
- [GPT-4o API pricing and tiers](https://developers.openai.com/api/docs/models/gpt-4o)
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenRouter request limits](https://openrouter.ai/docs/api_reference/limits)
