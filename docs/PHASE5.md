# Phase 5: analysis and explanations

Status: planned. On 6 October 2026 the user requested starting this phase after
they save Phase 4 with their own Git commands and report readiness. No Phase 5
schema, provider configuration or generation service has been implemented yet.

Read [ROADMAP.md](ROADMAP.md#phase-5-analysis-and-explanations),
[ARCHITECTURE.md](ARCHITECTURE.md) and [RECOVERY.md](RECOVERY.md) before implementation.
Phase 4 verification and working-database application instructions are in
[PHASE4.md](PHASE4.md). Final interface design remains in Phase 7.

## User requirements and proposed provider choice

- Use a model without a paid subscription or restrictive daily cloud quotas.
- Allow a later paid API connection through environment configuration, without
  changing application code.
- Keep the application useful when generation is unavailable. Save English
  explanations and reuse them when the underlying analysis has not changed.

The proposed first local candidate is `qwen3:4b` served by Ollama. Its published
quantised download is approximately 2.5 GB. Local inference avoids a hosted
provider's daily request allowance; memory, context size, electricity and
generation time still constrain use. Read-only hardware inspection found about
16 GB RAM and an NVIDIA GeForce RTX 4060 Laptop GPU. Suitability is a proposal:
neither a model installation nor a quality/latency benchmark has been performed.
Ollama was not found on PATH during preparation.

GPT-4o is a paid API model, with no supported free API tier. It can remain an
optional future provider/model choice, subject to an explicitly configured key
and budget. Existing OpenRouter settings are a legacy integration, not an
implemented provider-switching mechanism. Free hosted models have request caps
and availability limits; they do not meet a guarantee of unrestricted use.

Primary references checked on 6 October 2026:

- [Qwen3:4b model and download](https://ollama.com/library/qwen3:4b)
- [Ollama local execution and context settings](https://docs.ollama.com/faq)
- [Ollama OpenAI-compatible local endpoint](https://docs.ollama.com/api/openai-compatibility)
- [GPT-4o API pricing and supported tiers](https://developers.openai.com/api/docs/models/gpt-4o)
- [OpenRouter request limits](https://openrouter.ai/docs/api_reference/limits)

## Proposed implementation contract

1. Compute versioned findings from saved graph evidence and available business
   facts. Keep identity confidence, relationship strength and behavioural risk
   separate. Missing checks remain unknown; company debt is not owner debt.
2. Persist immutable analysis inputs, findings, rule versions and `analysis_hash`.
   Bind explanations to an exact analysis version and language. Preserve legacy
   text without inventing a verified historical analysis.
3. Produce a deterministic English template first. LLM generation receives only
   prepared findings and allowed evidence; it does not establish identity,
   create relationships or calculate scores.
4. Add a provider boundary for template-only operation, local Ollama, and optional
   OpenAI/OpenRouter APIs. Proposed settings are `AI_PROVIDER`, `AI_MODEL`,
   `AI_BASE_URL` and `AI_API_KEY`, with provider-specific defaults and explicit
   request/context/output limits. These variables are not supported yet.
   Document host versus Compose endpoint settings and service restart requirements.
5. Store provider/model, prompt version, validation outcome and generation state.
   Validate evidence references, identifiers and numerical claims; use the saved
   template when the model fails or produces unsupported claims.
6. Start work only through authorised background jobs. Deduplicate requests, reuse
   identical results, and prevent an old task from publishing for a newer analysis.
   GET only reads saved results. Do not silently switch to a paid provider.

## Verification and model selection

Check migrations on a restored copy and run meaningful tests on an isolated
database after confirming a current verified backup. Cover unchanged input
reuse, changed rules/facts, unavailable KGD information, weak mass contacts,
invented references, provider failures and stale background results. Do not run
live collection or paid generation as a refactoring check.

Compare local generated explanations with templates on fixed synthetic cases:
supported claims, unsupported claims, readability, latency and token usage.
Record actual measurements before deciding that an LLM improves this project.
An optional stronger or paid model should improve wording or coverage of the
same prepared facts; it must not change the underlying findings or graph.
