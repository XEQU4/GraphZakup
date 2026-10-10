# Source and identity audit, 9 October 2026

The user authorised source inspection, parser fixes and continued native collection.
They have KGD credentials but no separate Goszakup OWS token. No new source,
schema migration, data reset, paid service or Git operation was introduced.

## Findings and implementation

Public Goszakup participant cards contain a labelled director table with name and
IIN. Parser 2.3 ignored the IIN; source-access limitations were not the whole reason
identities remained unverified. Parser 2.4 accepts an unmasked, nonzero, 12-digit
IIN only beside a name in that same table. Participant identifiers, RNN, contacts,
masked values and conflicting sections cannot substitute for director evidence.
This verifies source identity, not a legal appointment period.

Director fact selection now follows chronological role evidence. A later matching
name-only observation retains the dated identifier evidence; a newer different
name changes the observed current role. No person is merged by name. Company fact
selection scans observations once, skips unchanged selections and excludes failed,
foreign-company and contract-subject observations. Fields and roles apply atomically.
Compatible 2.3 contract and registry legal-form evidence remains reusable after the
company-parser upgrade, avoiding needless contract party requests.

People defaults to records with an observed current role. The optional API
`has_current_role` filter precedes pagination. All saved identities/history remain
accessible, including namesake comparisons. Empty related groups are a compact
note: even a verified director need not share a group with another company.
The separate director IIN was removed from legacy company HTML; public API fields
still omit IIN/raw observations. An entrepreneur's existing public participant
identifier can equal their IIN; this is distinct from a new person-ID field.

## Source capabilities and remaining gaps

| Source | Evidence checked | Remaining limitation |
| --- | --- | --- |
| Goszakup public cards | Four fresh cards: two entrepreneurs and two legal entities, each with director name/IIN | Universal availability, appointment dates and current ownership unproven; ambiguous exact-ID search results unresolved |
| Adata | Accepted saved company/contact/director profiles | Three audit requests failed: timeout and two HTTP 502; founder markup is not current ownership |
| KGD registration | Existing identity-bound checks; ten more successes after restart | Registration does not prove zero debt or a director's identity |
| KGD debt | Three retained successful company results | One configured company-specific credential; wider company entitlement and IP debt unsupported/unverified |
| Contracts | Frozen head/archive slices, repair queue and recent-party reuse retained | Full archive traversal and complete national coverage unproven |

[Official OWS documentation](https://old.goszakup.gov.kz/ru/developer/ows_v3)
requires a separate token. No demo/documentation credential was used. HTTP 302/502,
timeouts, ambiguous cards and cooldowns remain unknown results rather than negative
findings. New court/bankruptcy/blacklist sources were not started.

## Verification and publication

Owned collection was gracefully stopped before algorithm changes; a fresh backup
was independently restored. Eight bounded public HTTP attempts, zero retries,
produced four accepted registry captures. The audit itself made no KGD request.
Capture-write timestamps, immediately following retrieval, were retained on replay.

563 isolated PostgreSQL tests passed without skips; 112 React tests, build,
formatting, strict OpenAPI validation and collectstatic passed. New cases cover
identifier-section boundaries, masked/conflicting IDs, role chronology, compatible
contract caches, current/history filtering and legacy identifier privacy.
Chromium checked filter/reload and 320/390/768/1440/1920px layouts without horizontal
overflow or application errors. Final desktop/mobile screenshots were inspected.

The four captures were rehearsed on a separately restored owned database, then
published atomically through normal ingestion without HTTP or inference. Four
verified current identities were added; original histories, cluster identifiers
and 809 unrelated companies were preserved. One graph/analysis/template version
was added. Repeated refresh added none. Thirty-eight public GETs preserved domain
state and passed identifier-field checks. An initial overly broad privacy assertion
matched entrepreneur business IDs; diagnostics confirmed `/bin`, not a new IIN field.
The corrected check includes field-level checks and unpublished director identifiers.
A post-publication backup was independently restored. Old AI texts remain immutable.

Worker, AI worker and beat were restarted and confirmed running. The bounded
post-restart status showed 813 companies, 525 contracts, 598 awaiting first profile
attempts, 150 KGD registrations, three debt results and no contract repair backlog.
Discovery remains paused above the enrichment backlog threshold. Registry cooldown
and Adata failures are still visible. Old-version profiles enter the bounded queue
subject to retry delay; this is not an immediate complete-catalogue refresh. Local
AI retains its separate queue and version checks. Working data continues changing.

Private reports/captures/screenshots: `artifacts/parser-final-audit/`. No original
response or identifier entered repository fixtures. Full Docker runtime/data-transfer
verification, localisation and the final whole-project audit were not started.
