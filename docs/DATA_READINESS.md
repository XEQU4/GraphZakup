# Directory readiness and collection follow-up, 9 October 2026

The user requested source-backed default listings and a final bounded parser review
before a separate visual-design pass, whole-project audit and deployment work.
Those subsequent tasks have not started.

## Visibility rules

- Companies defaults to Source-checked profiles. The optional API profile_status
  filter uses a selected name fact whose accepted registry/Adata observation matches
  the exact supplier, company subject key, BIN and displayed name. Filtering happens
  before pagination. Contract-only and legacy-only records are pending. This is
  basic profile provenance, not complete checks or proof of good standing.
- Pending and all records remain explicit list choices. Direct links, contract
  participants, saved graph history and unfiltered API compatibility are preserved.
  Successful evidence remains readable after a later temporary source failure.
- People defaults to verified identities with an observed current role. Unverified
  identities and source history remain selectable; name comparison includes both.
  Current adapters still do not establish ownership.
- Company directorships defaults to current records. Historical person URLs retain
  their role history, and empty ownership remains hidden. For company 567 this
  changes the default from three source/history rows to the one current role.
- Refresh reads committed data and reevaluates filters; GET never starts collection
  or generation. A newly accepted profile appears on a later list reload, subject
  to the active search/order/page. No stored publication flags can become stale.

## Collection review and fixes

Successful observations from an older parser version are now eligible immediately
for bounded refresh; failures still respect their retry delay. Half-batch fairness,
source due times, host cooldowns, request budgets and independent source stages stay
in force. Profile due/backlog and KGD eligibility queries require the exact company
subject. Registration-type selection also verifies the returned BIN. Unrelated
contract/wrong-subject observations cannot suppress company collection or establish
KGD legal type. No parser schema/version, migration or source integration was added.

Reviewed existing safeguards remain: exact identity/Decimal parsing, bounded
transport, challenge/denial stop, no redirect bypass, chronological source facts,
contract checkpoints/repair, source-specific caches, retained successful KGD results,
batch graph refresh and separate deduplicated local-AI jobs. Tests exercise them;
this does not prove every external response variant or complete national coverage.

## Verification and operations

Owned collectors were stopped; independent restore of all 51 tables passed:
artifacts/readiness/recovery/database_20261009T112032Z_d986d012.json.
568 isolated PostgreSQL tests passed without skips. 113 React tests passed with two
workers; an earlier concurrent run hit an unrelated Profile timing failure, with
no Profile implementation change. Build, formatting, OpenAPI and collectstatic
passed. Read-only working verification kept all 51 tables equal to the backup:
813 companies = 250 checked + 563 pending; 19 verified current people; company 567
has three total director records and one current. These are bounded audit counts.

Chromium verified default current-role selection, explicit three-row history and
reload, pending-profile filter/reload, and Companies/People at 320/768/1440/1920px.
No horizontal overflow or application error was observed; the reported-company
screenshot was inspected. Owned preview/browser stopped. Native worker, AI-worker
and beat were restarted after checks; existing source cooldowns were not reset.
Source collection may change the above counts normally. No saved domain cleanup,
manual AI regeneration, Git operation or user-server restart was performed.

Source 302/502/timeouts, ambiguous registry cards, missing legal role dates,
unconfirmed ownership and company-specific KGD debt entitlement remain explicit
limitations. Basic source checking must not be renamed full verification. The UI
filter is presentation, not an access-control boundary. Private evidence/reports
are under artifacts/readiness/.
