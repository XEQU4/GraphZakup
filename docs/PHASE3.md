# Phase 3: KGD adapters and retained company checks

Recorded on 5 October 2026; acceptance completed on 6 October 2026. **Status: complete for the implemented taxpayer and aggregate company-arrears services, within the verified scope below.** Two explicitly authorised requests were made for one selected company in an isolated PostgreSQL database: taxpayer lookup and arrears. The first credential worked as `X-Portal-Token`; the second ISNA credential was accepted as `personalAccountToken` in the arrears request. The response matched the selected BIN and contained all five aggregate amounts, each zero, with a reporting date of 6 October 2026. Parser version `3.1` corrected the observed timestamp format; the same retained response fields were reprocessed without another HTTP request. The working database was neither migrated nor modified. Other-company entitlement and operational limits remain unverified. Phase 4 has not started.

## Official services and scope

Research covered the [official API catalogue](https://portal.kgd.gov.kz/pages/api-services), the [taxpayer lookup specification](https://portal.kgd.gov.kz/ru/pages/info-services/find-taxpayer/_/attachment/download/591204a8-1450-4824-afc1-8298245e6f6c%3A7e918a95b376cd46c2af2f60a387d81996b03f47/ipn_ru%20%281%29.pdf), and the [tax arrears service](https://portal.kgd.gov.kz/pages/api-services/info-absence-tax-debt). The latter's linked API instruction describes the account-token parameter. These are separate services; taxpayer registration does not establish absence of tax arrears.

The first supported operation is taxpayer lookup. The second is aggregate company arrears, gated on a successful legal-entity lookup. Both use an administrator-issued `X-Portal-Token`. The arrears request additionally requires `personalAccountToken`; the implementation keeps this credential in a private map keyed by the company BIN. Entitlement to one account must not be assumed to cover other companies. Credential provisioning, access rights and quotas still need confirmation with KGD.

The adapters use the documented HTTPS endpoints:

| Source | Endpoint | Request fields |
| --- | --- | --- |
| `kgd_taxpayer` | `/services/isnaportalsync/public/taxpayer-data` | `taxpayerCode`, `taxpayerType`, `print=false` |
| `kgd_tax_debt` | `/services/isnaportalsync/public/tax-debt-info` | `taxpayerCode`, `personalAccountToken` |

Only legal-entity types `UL` and `UL_NR` are accepted. BINs remain exact 12-digit strings, including leading zeroes. Returned identifiers must match the requested BIN; names never establish identity. Individual/entrepreneur results are rejected for this company workflow. The adapter does not collect beneficial owners, bankruptcy, litigation or unrelated KGD checks. One positive `UL` response was verified live; `UL_NR`, empty results and other registration variants remain offline-tested only.

KGD documents HTTP 404 as forbidden service access. The adapter records it, along with 401/403, as `unavailable`, never `not_found` or zero arrears. [Official taxpayer specification](https://portal.kgd.gov.kz/ru/pages/info-services/find-taxpayer/_/attachment/download/591204a8-1450-4824-afc1-8298245e6f6c%3A7e918a95b376cd46c2af2f60a387d81996b03f47/ipn_ru%20%281%29.pdf).

## Implemented behaviour

- `apps/ingestion/parsers/kgd.py` fetches and normalises JSON through the shared HTTP transport. It imports no ORM models and performs no writes.
- `run_pipeline(mode='kgd')` owns collection, validation, observations, issues and resumable progress. CLI and the manual Celery task call this same service. KGD is not attached to automatic contract updates or beat schedules.
- Each run selects a fixed set of at most 500 existing companies. Resume retries unsuccessful companies in that set; it does not silently expand the set when new companies appear. Successful run UUIDs return the saved outcome without new collection.
- The existing database lease serialises pipelines. Publication verifies lease ownership in the write transaction. Company results, their state projections and the company cursor are published atomically.
- KGD collection does not change company profile fields, person identities, ownership/directorships, legacy owner flags, clusters, scores or explanations. Future evidence/rule integration belongs to Phases 4-5.

`SourceObservation` stores source, subject, parser version, retrieval timestamp, typed normalised facts, permitted original field values and a credential-free documentation URL. Unknown fields and nested personal account details are discarded. Monetary fields are exact Decimal values serialised as strings, including JSON numbers decoded directly as Decimal. Missing/invalid amounts are never replaced by zero.

Taxpayer facts include legal-entity type/name and available registration dates/end reason. Arrears facts include the overall amount and separate tax, pension, social and health-insurance amounts. Overall arrears can include structural units; they are liabilities of the company, not automatically of its owners. The source's available `reportAcrualDate` values are stored as a distinct list of reporting dates; retrieval time is not substituted for a missing effective date. Version `3.1` also accepts complete `YYYY-MM-DDTHH:MM:SS` reporting timestamps, validates the full calendar/time value and preserves the source calendar date. Original timestamp strings remain in permitted raw fields. Malformed times and trailing content are rejected rather than truncated. Registration-date parsing and other sources are unchanged.

Migration `ingestion.0006_companykgdstate` adds only a state table and foreign keys/uniqueness. For each `(company, source)`, `CompanyKgdState` references the latest attempt and the last successful observation. Failures do not erase the latter. Older replies cannot replace newer state. A repeated identical observation within one run is deduplicated.

| Result | Meaning in this integration |
| --- | --- |
| `success` | Accepted identity-confirmed response; complete financial fields required for arrears |
| `not_found` | Valid empty taxpayer response list; provisional mapping pending live verification |
| `unavailable` | Access denied, network/server failure, rate limit or challenge |
| `invalid` | Malformed/mismatched/ambiguous response or invalid financial values |
| `not_checked` | Disabled checks, missing/invalid configuration, missing account credential or unconfirmed legal entity |

Only an accepted complete response with an overall amount of zero records zero arrears. The debt adapter does not return `not_found`; an injected debt `not_found` is rejected at the service boundary.

The current company page reads saved results. It shows status, latest attempt, last success, reporting dates and available amounts. Retained data after failure or beyond the configured age is labelled potentially outdated. Unknown checks have no amount. GET performs neither network requests nor domain writes. This is a functional addition to the existing UI; final visual design still awaits user references.

## Configuration and access preparation

Keep `ENABLE_KGD_CHECKS=false` in the working environment until the intended collection scope is authorised. The controlled check enabled it only inside the isolated process. Do not send tokens in chat or put them in commands, tracked files, screenshots, fixtures or reports. Identify `X-Portal-Token` and `personalAccountToken` from the issuing instructions, not from token format or the sender's email address.

The first configured portal token succeeded in taxpayer lookup. The user clarified that only the first email/Word attachment named `X-Portal-Token`; the second email from ISNA contained the token alone. The earlier attribution of that label to the second email was incorrect. The subsequent bounded arrears check accepted the second credential as `personalAccountToken` alongside the first portal token, returning identity-matched aggregate data. No replacement credential is required for this verified scenario. This establishes accepted usage for the selected check, not general entitlement to other companies; an access error alone would not conclusively identify which credential or entitlement failed.

The [official arrears service page](https://portal.kgd.gov.kz/kk/pages/api-services/info-absence-tax-debt), rechecked on 6 October 2026, specifies two credential roles: `X-Portal-Token` in the header and `personalAccountToken` (account token) in the request parameters. Use these confirmed roles in the private configuration. The map restricts collection locally to selected BINs; it is not proof of universal or company-specific entitlement. Keep working checks disabled until the intended collection scope is authorised. Further checks must have a bounded scope and reuse observations only within the configured cache period.

Preparation and execution, 6 October 2026: the user selected a company BIN. A separate local PostgreSQL database was created, migrated and seeded with only that subject and a placeholder name. It initially contained no observations or KGD states. After local credential setup and explicit authorisation, `artifacts/phase3/run_kgd_validation.py --allow-live` performed exactly one taxpayer request, without automatic retries or account-token use. At that point it retained one accepted observation and one KGD state pointing to it as both latest attempt and last success. Its generated name/ownership marker remain in `artifacts/phase3/kgd-check-preparation.json`. That taxpayer runner refuses a second execution against this already-checked database; the later separately authorised arrears check used another bounded runner. The working database was not migrated or populated with these results.

According to the [official taxpayer service page](https://portal.kgd.gov.kz/kk/pages/api-services/find-taxpayer), request access through an authenticated portal appeal. The user must sign in using their own authorised identity, open the API service and submit the access request. Do not infer that portal login alone grants API entitlement. Ask KGD to confirm the current payload version, legal-entity types, permitted use, quotas and account-token provisioning for the selected company. The user reports completing the request on 6 October 2026; the agent did not submit it. No credential values have been added to project documentation.

Once issued, configure private `.env` (local Python) or `.env.docker` (Compose):

Use [.env.example](../.env.example) for the complete supported configuration. Preserve the existing `SECRET_KEY`, database connection/password and any already configured optional API keys. Do not replace the local database credentials with Compose example credentials. Put the first, explicitly identified portal token in `KGD_PORTAL_TOKEN`, and the accepted second ISNA token in the JSON map under the verified company's BIN. The map is a local scope restriction; it does not prove that the credential is company-specific or entitled to other companies. Keep this JSON on one line, use double quotes inside it, and enclose the whole value in single quotes in the dotenv file. For example, replacing both placeholders privately:

```dotenv
ENABLE_KGD_CHECKS=false
KGD_PORTAL_TOKEN=replace-with-first-portal-token
KGD_ACCOUNT_TOKENS_JSON='{"YOUR_COMPANY_BIN":"replace-with-second-isna-token"}'
```

Keep working checks disabled until collection in that environment is authorised. The isolated verification enabled them only for its selected subject and request budget. Saving a credential does not itself execute a request, apply migrations or start Celery. Local Python reads `.env`; the established Compose startup command reads `.env.docker` and supplies its own database/Redis container addresses.

| Variable | Default / purpose |
| --- | --- |
| `ENABLE_KGD_CHECKS` | `false`; opt-in collection and manual Celery task |
| `KGD_PORTAL_TOKEN` | Empty; the issued portal credential |
| `KGD_ACCOUNT_TOKENS_JSON` | `{}`; private JSON object mapping authorised BINs to their account tokens; empty accepted |
| `KGD_TAXPAYER_TYPE` | `UL`; select `UL_NR` explicitly when appropriate |
| `KGD_HTTP_TIMEOUT` | `30`; seconds per request, allowed 1-60 |
| `KGD_SOURCE_CACHE_SECONDS` | `900`; successful observation reuse; zero disables reuse |
| `KGD_RESULT_MAX_AGE_DAYS` | `7`; UI freshness indicator, not a legal validity period |

Shared host pacing uses `INGESTION_REQUEST_INTERVAL` (default 1.5 seconds). HTTP retries are bounded to two additional attempts; backoff/Retry-After is capped at 60 seconds and heartbeats run before retries. Redirects are disabled. JSON must have an appropriate content type; duplicate keys/non-finite numbers/invalid bodies are rejected. Bodies above 4 MiB are rejected after receipt; this is not a streaming download-memory cap. Authenticated responses are excluded from the in-memory HTTP cache.

The persistent observation cache accepts only successful results with the current parser version within the configured TTL. A later failure, including one with an equal timestamp and higher ID, invalidates reuse. Reuse retains the original observation date and marks `from_cache`; it is not a new live check. Disabled/missing credentials cannot turn a retained success into a successful current attempt. `--force` bypasses observation reuse. Restart affected Docker services after changing their environment.

## Apply and use

After checking a current verified backup, apply the additive migration locally:

```powershell
uv run python manage.py migrate
```

For Docker, rebuild/start using the established command; the migration service applies the update before web/worker startup:

```powershell
docker compose --env-file .env.docker up --build -d --wait
```

The commands below deliberately contact KGD when enabled and authorised. The live checks used the same ingestion service through bounded isolated runners, rather than these working-database commands. Replace the placeholder BIN with one existing authorised company; the synthetic fixture BIN is not a live demonstration subject. Previous isolated acceptance does not authorise new or working-database collection.

```powershell
uv run python manage.py ingest_data --mode=kgd --company-bin=YOUR_COMPANY_BIN --total=1 --kgd-service=taxpayer --force
uv run python manage.py ingest_data --mode=kgd --company-bin=YOUR_COMPANY_BIN --total=1 --kgd-service=tax_debt --force
uv run python manage.py ingestion_status
uv run python manage.py ingest_data --resume=RUN_UUID
```

`tax_debt` performs registration verification first, then checks arrears only if registration succeeds. A missing account credential records `not_checked` and leaves a resumable issue. Failed/unperformed checks produce a failed/partial run and a safe error code plus UUID. Resume retains the saved selection/options. `ingestion_status` only reads stored progress.

The optional manual task `apps.core.tasks.check_kgd` accepts `company_bin`, `service` (`taxpayer` or `tax_debt`), `total` (default 1) and `resume`; credentials come from settings. Its retry resumes the same run. No UI endpoint or automatic KGD schedule was added.

## Verification completed

- Fresh PostgreSQL 17.6 backup `artifacts/phase3/database_20261005T180443Z_3f4eaeb2.json` passed independent restoration: all 38 public tables matched, including migration history; temporary database dropped.
- The dump was restored again and upgraded through current migrations in a separate database. Existing values in 37 tables outside migration history matched by original PKs/columns. Migration created zero KGD state rows; it did not invent successful/negative checks. Source comparison before and after matched the backup. Both verification databases were removed.
- On 5 October, all **165 Django tests passed on isolated PostgreSQL**, including 37 new KGD tests and existing concurrency checks. That SQLite suite ran 163 successfully and skipped its two PostgreSQL-only tests. On 6 October, after adding two reporting-timestamp regressions, all **167 tests passed on isolated PostgreSQL**; the SQLite full suite was not repeated.
- Tests cover identity/type gates, exact amounts, complete zero versus unknown, reporting dates, forbidden access, malformed JSON, credential filtering, bounded runs, cache age/version/invalidation, resumability, atomic rollback, stale-worker fencing, data retention, additive migration and read-only escaped company pages.
- Existing JavaScript regressions passed. Migration drift check reported no changes. Compose configuration validated with `.env.example`; it defined the six expected services without starting them. `test.py`, `pyproject.toml` and `uv.lock` retained their baseline hashes.

PostgreSQL testing exposed an unsupported lock over a nullable outer join; publication now locks only `CompanyKgdState`. The complete PostgreSQL suite passed after correction. Safe local report: `artifacts/phase3/postgresql-verification.json`. Fixtures in `tests/fixtures/kgd_*.json` contain invented identifiers, names and amounts; no live response was copied into fixtures or documentation.

On 6 October 2026, a fresh backup passed restoration before live-check preparation. All 38 working tables matched the backup after preparation. Before authorisation, the script's guard returned `explicit_live_authorisation_required`, zero requests. Report: `artifacts/phase3/kgd-preparation-verification.json`.

The subsequent authorised check succeeded at `2026-10-06T10:22:09.862800+00:00` using parser version `3.0`. The documented response envelope contained one `SUCCESS` entry with a matching `code`, `taxpayerType=UL`, `name` and `beginDate`. The existing adapter accepted it without a code/schema change. Only permitted company facts were persisted in the isolated database; the full response and credential values were not saved. Safe status/type-only report: `artifacts/phase3/kgd-live-validation.json`.

Post-check verification made zero HTTP requests and confirmed:

- All 38 working tables still matched the verified backup, and protected user/dependency files retained their hashes.
- Two further company-page GETs returned HTTP 200 and issued only SELECT queries. Reads did not add observations or alter the retrieval time/fingerprint.
- Resuming the successful run returned its saved result with only SELECT queries and no network request.
- The observation cache returned the same validated facts with the original timestamp and `from_cache=true`.
- The arrears projection remained `Not checked` with no amount, rather than zero.
- The token was absent from saved fact fields, run options and the evidence URL.

Report: `artifacts/phase3/kgd-live-preservation-verification.json`. The isolated database remains locally retained for review and must be ownership-checked before cleanup. No additional collection is authorised by retaining it.

## Arrears acceptance, 6 October 2026

After the user saved the second token and instructed continuation, `artifacts/phase3/run_kgd_debt_validation.py --allow-live` issued exactly one arrears request, without retries, to the selected company. To avoid another registration request, this isolated process used a 24-hour observation cache and the identity-confirmed taxpayer result fetched 3,468 seconds earlier that same day. The working cache remained at 900 seconds. Reused registration retained its original retrieval time; this was an explicit test configuration, not a new default or a new source check.

The service returned JSON with the exact requested `iinBin`, all five monetary fields as zero integers, and five tax-organisation records dated `2026-10-06T00:00:00`. Parser `3.0` rejected the unhandled date format as `invalid`; the company page correctly displayed an invalid result without an amount. Status/type-only report: `artifacts/phase3/kgd-debt-live-validation.json`. Only bounded identity, aggregate amounts and reporting-date fields were retained privately for offline reprocessing; the full response, names and nested account details were discarded.

The correction is source-specific reporting-date parsing in `apps/ingestion/parsers/kgd.py`, with parser version increased to `3.1`. Synthetic tests cover complete timestamp normalization, original-field retention, impossible dates/times and trailing content. The current backup checksum/restoration and upgrade were verified again, preserving all 37 original tables outside migration history. All 167 tests passed on a separate PostgreSQL test database; both restore/test databases were removed. Working-data comparisons matched all 38 tables before and after. Report: `artifacts/phase3/postgresql-reporting-date-verification.json`.

`artifacts/phase3/reprocess_kgd_debt_result.py` then resumed the same partial run through the normal ingestion service using retained permitted fields, with HTTP explicitly blocked. It revalidated both subjects under parser `3.1`, preserved each original retrieval time and the `3.0` failed observation, resolved the issue and published a successful zero-arrears observation. Reprocessed observations are marked `from_cache=true`; they do not claim a new retrieval. The five accepted aggregate values remain exact Decimal zero; the reporting-date list is 6 October 2026. The company page and successful resume issued only SELECT queries, cache reuse retained the original timestamp, and all 38 working tables still matched the verified backup. Report: `artifacts/phase3/kgd-debt-reprocessing-verification.json`.

## Acceptance and remaining limits

The roadmap criteria are met for the implemented services: identity-confirmed subjects, distinct absence/access/unperformed states, retained reproducible results, and authorised official-source verification. Live evidence covers one positive legal-entity registration and one complete zero-arrears response for the same company. Offline tests and documented HTTP codes cover the error/state distinctions. This closes Phase 3 implementation and available-service acceptance; it does not claim universal credential entitlement or exhaustive live coverage of every source variant.

Actual empty taxpayer responses, nonzero/negative arrears variants, alternate timestamp formats, duplicate registration episodes and live rate-limit/error envelopes were not exercised. Empty taxpayer mapping remains provisional, and an unavailable/invalid result must never be interpreted as no finding or zero arrears. The total-equals-four-categories rule is conservative and fixture-tested; the zero live example does not establish nonzero reconciliation. Unknown formats, negative amounts and inconsistencies remain rejected rather than silently accepted. Do not manufacture an absent-company example or deliberately trigger rate limits to broaden acceptance.

Quotas, contractual freshness, source completeness and other-company entitlement still require operational clarification before a broader pilot. No mass collection, Celery pipeline, paid generation, working-database migration, Docker stack startup or load benchmark occurred in these checks. Compose configuration validation is separate from Phase 1 runtime startup verification. Debt is not yet part of graph scoring or explanations. Phase 4 requires a separate user instruction.
