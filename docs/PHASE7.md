# Phase 7 React delivery

Implemented on 7 October 2026. Technical verification passed; user visual acceptance
is pending. The user authorised the supplied blue, serious, animated references and
explicitly deferred rewriting explanations and further graph design. English comes
first; Russian localisation and Phase 8 have not started.

## Delivered

- React/TypeScript routes for overview, companies, people, contracts, relationship
  groups and details, saved graph/analysis/text histories and evidence dialogs.
- Existing working data through /api/v1; saved-data-only overview aggregates,
  exact monetary strings, explicit unknown/failed coverage, URL filters/pagination,
  abort/stale-response fencing, loading/empty/error/retry states.
- Dark blue UI, self-hosted fonts, Radix icons/dialogs, licensed lighting and
  Magic UI Border Beam. Motion supports OS reduction and a saved manual preference;
  the shader caps DPR/frames and stops offscreen or in a hidden document.
  Further graph visual design and stored-text rewriting remain deferred.
- Existing D3 interaction and storage key retained. Initial/reset layouts settle
  before fitting; search, filters, highlighting, evidence, version selection,
  anonymous and authenticated view persistence are integrated.
- Same-origin sessions/CSRF, accessible login, independent personal views and
  explicitly confirmed staff actions; mounting pages starts no job or collection.
- Django serves /app/ and deep links; / redirects there. /legacy/, old detail
  routes and admin remain. Bootstrap is excluded from React.
- Locked npm build, source formatting, locally distributed component/dependency
  notices, Node Docker build stage before Python collectstatic. Compose and data
  volume identifiers remain unchanged. No new environment setting or domain
  migration is required.

## Verification

All 338 Django tests passed on a new isolated PostgreSQL database, without skips.
The runner dropped that database and its absence was independently checked.
The offline suite passed the same 338 tests with four PostgreSQL-only skips.
All 35 React tests, TypeScript, clean npm ci/build, formatting and OpenAPI validation
passed. npm audit reported zero known vulnerabilities at installation.

Normal-settings browser checks used enforced read-only working PostgreSQL:
777 companies, 500 contracts, 768 people, four active groups, eight snapshots and
four saved analyses/texts. All 50 table fingerprints matched the pre-frontend
record; .env, test.py and celerybeat-schedule hashes stayed unchanged. A scan of
290 relevant source/build/documentation files found no configured credentials.

Chromium checked 390/768/1440/1920px layouts, deep routes, company/global search,
pagination, contract ordering/exact values, unknown KGD and empty verified people,
historical graphs/save locks, graph bounds, saved filters/layout reload, evidence
modal focus restoration, mobile navigation/login, OS/manual motion and offscreen
beam pause/resume. An isolated synthetic SQLite server verified real CSRF login,
own-view PUT/reload, user separation and logout. A mocked 503 verified retry recovery.
No runtime exception remained after fixes; no automatic job request occurred.
Swagger remained available. Contrast checks were bounded CSS calculations and
keyboard checks, not a complete accessibility conformance assessment.

Browser QA found duplicate React contexts because Django's second storage hash
gave Vite's entry another URL. The SPA now serves original Vite-hashed entry names,
matching lazy imports; a manifest-storage regression covers this. Other fixes
covered session-read cancellation, canceled view revisions, dev graph links,
initial fit, modal styling/focus, operational contrast and animation observation.

Docker Compose configuration and the public Node image manifest passed inspection.
Actual Linux image build/startup was not run: Docker Engine was unavailable.
Physical touch, high-density graph performance and final user visual acceptance
remain unverified. No live parsing, model generation, working migration/recalculation
or Git command ran. Owned preview servers were stopped after checks.

Private reports/screenshots: artifacts/phase7/. Required user startup/Git actions
are given directly in the delivery reply; these records are for task continuity.

## Component sources

- [React Bits Orb source](https://github.com/DavidHDev/react-bits/blob/main/src/ts-default/Backgrounds/Orb/Orb.tsx):
  MIT plus Commons Clause; full notice in frontend/licenses/react-bits.txt.
- [Magic UI Border Beam source](https://github.com/magicuidesign/magicui/blob/main/apps/www/registry/magicui/border-beam.tsx):
  MIT; full notice in frontend/licenses/magic-ui.txt.
- [Radix icons](https://www.radix-ui.com/icons) and
  [dialog primitive](https://www.radix-ui.com/primitives/docs/components/dialog).
- Spline was a visual reference; no remote Spline scene is embedded.
  frontend/public/third-party-notices.txt is copied into every build.

## Standalone Next.js experiment inspection

On 7 October 2026, `next-app/` was inspected without installation or execution.
It is a separate npm-installed Next.js 16.3.6/React 19.3.0 starter with shadcn,
Tailwind and its own package/lock files. Its React Bits registry and unused
`TechText.jsx`/CSS suggest a component experiment; the exact creation command is
unverified. `app/page.tsx` imports `@/components/ui/button`, but that component is
absent. No Next.js build or startup was tested.

IZ2 still builds `frontend/` with Vite and serves its saved Vite manifest through
Django at `/app/`. No root npm workspace or Next.js API/backend integration was
found. Root `.gitignore` and `.dockerignore` now exclude `/next-app/`; its sources
are excluded from the Docker build context, and its untracked files are ignored.
The directory and animation files were retained in place. Existing Git tracking
was not inspected; ignore rules do not untrack previously added files.

Hashes of `.env`, `test.py` and `celerybeat-schedule` matched the saved Phase 7
protected-file baseline. No working database operation or Git command ran.

## Reference-based design follow-up

The user supplied Lightswind, Coss UI and UILib on 7 October 2026 and requested
a richer visual direction. The overview now uses a licensed Lightswind-derived
blue/cyan/indigo aurora, original dimensional evidence illustration, floating
glass labels, distinct statistic surfaces and pointer/keyboard card highlights.
Navigation has a moving active surface; tables, dialogs and source coverage use
the same blue glass treatment. Mobile overview contracts use complete stacked
records, and top-bar targets measure at least 44px. No new runtime dependency
or backend/schema/analysis change was needed.

[Lightswind Aurora](https://github.com/codewithMUHILAN/Lightswind-UI-Library/blob/Master/registry/aurora-background.tsx)
is MIT; its full notice is included in distributed notices. Coss
[cards](https://coss.com/ui/docs/components/card) and
[fields](https://coss.com/ui/docs/components/field), plus UILib's
[gradient hero](https://www.uilib.co/project/hero-section-with-animated-gradients)
and [glass navigation](https://www.uilib.co/project/glassmorphic-navbar-with-physical-button-styling)
informed the visual patterns. Spotlight, coverage and SVG artwork are original;
no Coss or UILib source was vendored. The retained Orb is no longer mounted on
the overview. Existing Radix accessibility and D3 graph interactions remain.

This follow-up passed production TypeScript/Vite build, all 40 React tests,
six isolated Django frontend tests and formatting. Chromium checked
320/390/768/1024/1440/1920px, real totals, company BIN search/detail, mobile
navigation/login layout, evidence focus restoration and manual/OS/offscreen
animation stops. No browser exception, failed request or automatic write was
recorded. Normal application assets were served with read-only working
PostgreSQL; all 50 before/after table fingerprints and protected file hashes
matched. Stored graph/explanation content was not regenerated.
Physical-device and full accessibility audits, Docker startup and user visual
acceptance remain pending. Private screenshots are under artifacts/phase7/.

## Motion and alignment follow-up

On 7 October 2026, the user requested a deep-blue, black and white identity with
more expressive motion. An original IZ monogram and locally served SVG favicon
replace the generic mark. Semantic `TechHeading` keeps real heading text while
adding glyph reveal/inspection; manual `FocusFrame` follows navigation targets.
`CountUp` animates saved non-negative integer quantities, preserving accessible
final values and label width. Money, identifiers and review-priority scores stay
exact. Continuous emblems and decorative motion respect manual/device preferences
and visibility.

Graph search/buttons share 44px heights; relationship chips have consistent
checkbox sizing and result labels wrap safely. Analysis status occupies a shared
row so both panels start together; responsive heading/version controls and
stacked mobile layouts remain. Lazy graph styles cannot override the namespaced
layout fixes. Graph rendering algorithms, relationship palette, source data and saved
analysis/explanation contents were not changed.

True Focus and CountUp are local React Bits adaptations, credited with source
links in frontend/licenses/text-motion-sources.txt and distributed
frontend/public/third-party-notices.txt. The full existing MIT + Commons Clause
notice remains intact. The frontend test run passed all 48 cases, including
eight CountUp tests. CSS parsing/formatting passed for the alignment changes.
User visual acceptance of this latest follow-up remains pending. Browser results
for the latest changes are recorded below; earlier results above describe the
preceding design.

Verification for this follow-up passed the production TypeScript/Vite build,
formatting, all 48 React tests and six isolated Django frontend tests. Chromium
verified heading accessible names, counter progression/stable width/final totals,
all three emblems, glitch hover, pointer/keyboard navigation focus, manual and
OS reduced motion, hidden/offscreen pause, mobile navigation/login and evidence
focus restoration. Overview/group layouts passed at 320/390/768/1440/1920px;
graph search/buttons measured 44px with matching tops and desktop analysis cards
shared the same top. A CSS specificity defect that paused heading reveals and
per-letter accessible names were corrected during browser verification. No
JavaScript exception, failed request or automatic write was recorded. All 50
working-table fingerprints and protected-file hashes matched; 313 project files
contained no configured credential matches. Private reports and screenshots use
the text-motion prefix in artifacts/phase7/. User visual acceptance, physical
devices and a full accessibility audit remain pending.

## Glyph, starfield and control refinement

The latest user-directed refinement keeps semantic page titles in `TechHeading`;
hovered glyphs become transparent with dashed SVG outlines, measurement frames
and handles. Original `GroupGlyph` constellation artwork decorates group counts
and cards without representing new relationship evidence. A fixed background
uses 66 stable decorative stars with CSS twinkle. Manual/device preferences and
hidden-document pauses remain; no data drives these coordinates.

Buttons have finite blue glitch/shine on hover, keyboard focus and press, with
transient blur capped at 0.18px and stable click targets. Search controls have
focus borders, a brief scanning accent and icon glow; the group-search capsule
has a dark background and border. Disabled/busy states retain ordinary static
feedback. No checkbox/select internals or graph interaction logic changed.

All 48 React tests, six isolated Django frontend tests, production build and
formatting passed. Browser checks confirmed glyph hover and initial reveal,
icon movement, button/search feedback, star twinkle, manual/OS/hidden motion,
saved motion preference and layouts from 320 to 1920px. Final tooltip-edge and
working-database integrity results are recorded below. These
bounded results do not establish final visual acceptance, which remains pending.

The user explicitly deferred footer, authentication, source/parsing, API-page
and explanation improvements. Do not start those tasks from this visual update.
No dependency, backend or saved-data change was required.

Final checks passed: tooltip labels stay inside their heading at 320px; disabled
and busy controls stay static, the single search focus frame remains visible,
and saved-evidence dialogs restore focus after closing. Graph search/buttons
retain 44px heights and desktop analysis panels remain aligned. Chromium recorded
no application exception, failed request or automatic write. All 50 working-table
fingerprints and protected-file hashes matched; 318 scanned project files contained
no configured credentials. Private reports/screenshots use design-life prefixes
in artifacts/phase7/. User visual acceptance and physical-device checks remain
pending. next-app remains a preserved, ignored standalone experiment; inspection
confirmed its startup page imports the absent components/ui/button module.


## About, footer and React Bits particle refinement

The user explicitly authorised About Us and the full footer. The sixth navigation
route explains the project, intended audiences, review steps and implemented
versus planned integrations. The footer restores verified repository/contact
references, existing project credits, source services, stack and component credits.
Authentication, parsing, API-page and saved-explanation redesign remain deferred.

React Bits Particles replaces the 66-star layer with 240 small full-viewport
white/blue points, capped drawing/DPR, visibility and motion controls, GPU cleanup
and a static fallback. Border Glow decorates native group-card links and About
panels. Narrow glow gutters prevent horizontal overflow; card hit targets stay
stable. Ctrl+K hint/interception were removed. Ordinary text has no visible caret;
editable fields retain it. The screenshot cursor may also reflect browser caret
browsing, which remains a browser setting. Glyph outlines are 0.65px; inactive
headings stay readable and a bounded, cancellable completion handles a hovered
final glyph that cancels its CSS reveal event.

All 61 React tests, six isolated Django frontend tests, build and formatting
passed. Chromium verified 320–1920px layout, real WebGL drawing, manual/OS/hidden
pauses, context-loss fallback, edge glow, keyboard focus, mobile About navigation,
search and saved graph/evidence reads. No application exception, failed request
or automatic write was recorded in the bounded scenarios. Final private integrity
results are recorded in artifacts/phase7/about-particles-final-verification.json;
working-table fingerprints and protected files are checked there. Physical-device
performance, full accessibility audit and user visual acceptance remain pending.
No dependency, backend, schema, source collection or saved-result change was made.

Final integrity verification passed: all 50 working-table fingerprints and
protected-file hashes matched; 338 scanned project files contained no configured
credential matches. Owned preview resources were stopped after verification.


## Footer, accounts, graph and directory follow-up

The user authorised these four items and postponed all Git commands. Public
credits now name the independent developer and related article author Yestay
Arnuruly (Estay-2020@bk.ru); supervisor/department claims were removed from React
and compatibility footers. About Us preserves the distinction between roles.

CSRF-protected registration signs in an ordinary account. The profile changes
only its username; email is read-only, with no avatar. Password changes check
the current password under a row lock, validate the replacement, retain the
requesting session and rotate CSRF while invalidating other sessions. Functional
unique indexes prevent concurrent case-duplicate usernames/nonempty emails;
existing values and legacy empty emails are preserved. Duplicate preflight stops
rather than modifying accounts. No environment change is required. Email
verification/recovery and production operational hardening remain future work.

The graph adds layered blue surfaces, node icons/contours, keyboard-accessible
wide edge targets, structured inspection and selected-edge accents capped at 12.
Motion changes update the existing controller without remounting: saved layout,
selection, filters, frozen state, evidence/version IDs and original storage key
remain stable. Decorative accents imply no new relationship direction. Companies,
People and Contracts directories use separated rows, labelled mobile cards and
finite hover/focus feedback while retaining native links, filters, pagination,
identity uncertainty and exact amount strings. Entity detail redesign is deferred.

All 353 isolated PostgreSQL tests and 77 React tests passed, as did migration-drift,
formatting and production build checks. Restored-copy migration/reversal preserved
original values; see RECOVERY.md. Chromium verified signup, confirmation/errors,
username change, password change, old/new-password login and focus restoration on
synthetic accounts. Profiles, dialogs, directories, graph and footer fit widths
320/390/768/1024/1440/1920px. At 320px both auth buttons retain full labels and 44px
targets; a 150-character username stays bounded with its full accessible name.
Graph keyboard inspection, filtering, anonymous view save/reload and manual/device/
offscreen/simulated-hidden motion checks passed without coordinate loss or working
writes. Browser reports/screenshots use ignored artifacts/phase7/account-ui/.
Final protected-file/working-table integrity checks are recorded there. Physical
device performance, a full accessibility audit and user visual acceptance remain
pending. Saved AI explanations, group-page redesign, parsers/data quality,
localisation and Phase 8 require the next explicit task.

Final integrity comparison passed: all 50 working tables and protected files
matched, existing Python dependency versions were unchanged, and the 353-file
credential scan found no configured credential values. Working migration remains
pending; frontend assets are built and collected.

Owned preview servers and browser resources were stopped; ports 8770/8772 were
checked for remaining listeners. The user's development server was untouched.

## Saved views and account purpose follow-up

The article author's email moved from credits to the contact panel in both
footers; credits retain his name. Desktop directory arrows now have a comfortable
right inset while preserving 44px targets and full-width mobile links.

Authenticated `GET /api/v1/account/views/` returns paginated metadata for the
requesting account only. The profile's Your graph views links open saved
snapshots. Accounts retain personal layouts across browsers; guest layouts stay
in the current browser. Saving during camera navigation commits its final target;
completed targets are cleared so later manual pan/zoom remains authoritative.
Feedback appears beside the graph toolbar. Failed private reads and revision
conflicts block PUT until Reload saved account view. Guest state can initialise
an account without a personal view only after a successful GET and explicit save.

All 357 isolated PostgreSQL tests passed without skips, along with 88 React tests,
production build, formatting and migration-drift checks. A fresh-browser account
restore passed without localStorage, retaining a pinned selected node, zoom,
filters and frozen state. All 50 source-table fingerprints matched before/after;
the current working database has all 69 migrations applied. No new migration,
working write, source collection or model job was run. Fresh verified recovery records
and private reports are in artifacts/phase7/save-view-followup/. User visual
acceptance remains pending; Git and the next phase were not started.

Final Chromium checks passed on synthetic accounts only: a real save restored
pins, selection, camera, filters and freeze in a new browser with no local view
keys. Stale concurrent saves returned 409 and private-read failure returned 503;
both blocked writes until reload/retry, which preserved geometry and allowed a
successful save. Guest save and sign-in handoff issued no automatic PUT; explicit
account save appeared in the profile. Footer, People, profile cards and graph
feedback had no horizontal overflow at 320/390/768/1024/1440/1920px; desktop arrows
retained 44px targets and a 34px inset. Article email appeared only in contacts.
1440px/320px screenshots were inspected. Report:
`artifacts/phase7/save-view-followup/browser-verification.json`. Account writes
used the isolated synthetic preview; the working database remained read-only.

Final integrity matched all 50 working-table fingerprints and protected files;
354 scanned project files contained no configured credentials. Owned previews
and their browser were stopped; ports 8770/8772 had no remaining listeners.
The user's development server was untouched. Reports: `final-verification.json`
and `cleanup.json` in the same private follow-up directory.

## API reference styling follow-up

The user authorised API-page styling, superseding the earlier deferral.
`/api/v1/docs/` is a standalone IZ2 reference with solid navy surfaces, resource
navigation, native endpoint filtering, initially collapsed operations, Nord dark
syntax/monospace examples, responsive parameter forms and authorisation modal,
and workspace/schema links. Manrope and IBM Plex Mono OFL assets, the SDK and
theme assets are bundled locally. The page helper makes no API requests; native
Swagger bootstrap, session/CSRF interceptors and operation execution are retained.
API permissions, authentication, data, schema and rules did not change. React,
next-app, parsing, explanations, localisation and Phase 8 are outside this task.

Sixteen isolated SQLite API static/common tests passed, as did OpenAPI validation
with warnings treated as failures, targeted formatting and collectstatic.
Initial Chromium resource navigation, filtering, authorisation-modal and native
GET 200 checks passed. Completed browser verification covered filter/empty-filter
states, company-tag deep-link reload and native Try it out: page_size=1 returned
HTTP 200 with 777 total companies and one record; page_size=0 showed validation
without issuing a request. Page/modal layouts fit actual document clientWidth at
320/390/768/1024/1440/1920px; long mobile responses scroll inside code without page
overflow. No JavaScript exception or failed, external or non-GET request was
observed. Final 320px/1440px screenshots were inspected. Report:
`artifacts/phase7/api-docs/browser-verification.json`. The owned normal-settings
preview on 8774 used read-only working data; user port 8000 was untouched.
Final integrity matched all 50 working-table fingerprints, protected files and
existing Python dependency versions. The 357-file scan found no configured
credentials. The owned preview/browser were stopped and port 8774 had no
remaining listener. Reports: `final-verification.json` and `cleanup.json` in the
same private directory. User visual acceptance remains pending.


## Saved AI explanations and aligned review panels, 8 October 2026

The user explicitly authorised AI explanation rewriting and regeneration. The
right card now presents saved model-written paragraphs, cited fact disclosures
and practical checks. The left card explains the deterministic review-priority
index and its credited points. Both cards share one status row and align at the
top on desktop; narrow layouts stack without page overflow. Original contact
values are available in the evidence disclosure. A rejected model response is
visibly labelled as a saved template fallback.

Free local Qwen3:4b generated new prompt-5.3 explanations for all four working
clusters through explicit durable jobs. Their repeated requests reused the same
results. Three jobs took 8.4–9.6 seconds; the email case passed after one repair
in 18.1 seconds. Original texts, analyses, scores and graphs were preserved.
A fresh backup was restored and verified before these writes. All 44 non-AI
domain tables remain unchanged; only AI job/text pointers/history and the
released orchestration lease changed. No migration or source collection ran.

All 391 isolated PostgreSQL tests passed without skips, as did 95 React tests,
production build, formatting, strict OpenAPI validation and collectstatic.
Chromium checked all four published results against saved API documents,
citations, exact contact details and stable reloads. Layouts fit actual client
widths at 320/390/768/1024/1440/1920px; desktop panel top differences were zero.
The 1440px and 320px screenshots were inspected. No JavaScript exception, failed
request, external request or non-GET request was observed in this browser pass.
All 50 current source-table hashes matched across final PostgreSQL tests.

The final six-case synthetic provider check accepted four responses and rejected
two after bounded repair: an invented director tender-authority claim and raw
finding IDs in a twenty-company explanation. These remain honest fallback
cases, not successful prose generation. Some procedural/repetitive wording
remains; validators do not prove semantic correctness or editorial quality.
Private reports are under artifacts/phase7/ai-narrative/. Main .env settings stay
unchanged: these saved results are readable without a running model, while
future model jobs require explicit configured generation. User visual/readability
acceptance remains pending; no Git, parsing, localisation or Phase 8 work ran.

Final post-generation/browser comparison preserved all 50 current table hashes.
Protected .env/test.py/celerybeat files and existing dependency versions matched;
362 scanned project files contained no configured credentials. Owned preview
8778 and local model 11435 were stopped; no listeners remained on those ports.
The user server was not controlled. See final-verification.json and cleanup.json.


User review, 8 October 2026: the user accepted the revised AI explanation and
aligned review panels. The agreed remaining sequence is relationship-group
page refinement, parser/data-quality work, and company/person detail pages.
This acceptance does not authorise source collection or start Phase 8.


## Relationship-group directory follow-up, 8 October 2026

The user authorised clearer group titles, cards, search and filters. New typed
API directory projections read current frozen graph members and matching saved
analysis. Display titles describe evidenced shared contacts/verified roles;
mixed ownership/director roles are distinct. Persisted names, UUIDs, histories,
public scores and model explanations are unchanged. Company previews and name/BIN
search use frozen member records; original group names remain searchable.
Relationship/coverage filters execute before SQL pagination with bounded query
counts. Coverage means usable KGD arrears checks at the saved analysis date,
not overall source completeness or current clearance. Missing/mismatched/malformed
metrics stay unknown. The unmaintained legacy explanation_stale flag is not
authoritative; directory status describes graph/analysis correspondence.

The React directory has responsive evidence cards, static scores, dated coverage,
URL-backed filters, removable chips and distinct empty/error/loading states.
Current detail titles agree with cards; historical versions avoid current-link
claims. Back to results preserves filters through graph/analysis version changes
and reload. Decorative glow stays within tablet page width without clipping text
or keyboard outlines. Controls retain 44px targets and reduced motion support.

413 isolated PostgreSQL tests passed without skips, as did 108 React tests, build,
formatting, strict OpenAPI and collectstatic. Thirty-eight real GET checks covered
all four working groups, search, relationship/coverage/score/state filters, SQL
pagination and unchanged saved model versions. Chromium checked keyboard opening,
filtered return/history/reload, chips/reset/back navigation, empty results and a
simulated HTTP503 with successful retry. Layouts fit actual clientWidth at
320/390/768/1024/1440/1920px; screenshots were inspected. No JavaScript exception
or external/non-GET request occurred; the deliberately simulated503 was expected.
All50 source hashes and protected/locked files remained equal across final tests;
the isolated database was dropped. No source collection, generation, migration,
Git operation, localisation or next phase ran.

SQLite retains its built-in Unicode case-folding limitation; Cyrillic case-insensitive
search passed on PostgreSQL. Very large catalogue/filter performance and physical
touch remain unmeasured. User visual acceptance of this directory is pending.
Private reports: artifacts/phase7/cluster-directory/.

Final post-browser comparison preserved all 50 source tables, protected files and
25 next-app source files. The owned browser/preview stopped; port 8780 has no
remaining listener. User servers were untouched. See source-compare-latest.json
and cleanup.json in the private directory.

## Company and person detail follow-up, 9 October 2026

The user authorised entity detail refinement. Company facts now expose bounded
selected-field provenance only when the saved observation matches the company,
field and displayed value. Legacy import dates are not source check dates.
KGD registration and arrears remain separate, including retained dated results,
failed attempts and missing checks. Contract previews switch supplier/customer
roles and show source retrieval dates; role filters distinguish observed current
and inactive records without inventing legal periods.

Related-group filtering runs in SQL before pagination against current immutable
snapshots. Person filters require the exact verified node and evidenced role;
name matches never establish membership. Person pages explain separate identities,
count other exact case-insensitive name records and pending match candidates,
and distinguish company checks from unavailable personal-history integrations.
Mobile roles/contracts use vertical cards. No migration or saved-data algorithm
change, collection request, model generation or Git command was performed.

551 isolated PostgreSQL tests passed without skips; 18 entity tests subsequently
passed with an explicit timezone-equivalent contract timestamp assertion. All 111
React tests, production build, formatting, strict OpenAPI and collectstatic passed.
GET-only browser checks used a PostgreSQL read-only connection and covered saved
legacy/fresh company facts, roles/contracts filters, group/name-search links,
keyboard section navigation and 320/390/768/1440/1920px. Stable layouts fit their
client width; screenshots were inspected. Physical touch and large-catalogue
performance remain unmeasured. Private report: artifacts/entity-pages/verification.json.
Final status found the pre-existing worker/AI-worker/beat stopped (last cycle
07:27 UTC); this task did not stop them. User restart instructions are in chat.
Visual acceptance remains pending. Complete-stack verification is the next task,
not started here.

### Source-aligned simplification, 9 October 2026

The user requested removal of unused/empty UI. Current adapters collect director
records, not confirmed ownership/shares. Empty ownership sections and their person
navigation link are suppressed; saved ownership records and request errors remain
visible. Company fact lists omit unpopulated values with an explicit coverage note.
The unused person-directory history column and large unimplemented-history panel
are replaced by one collapsed scope explanation. Legacy scores are removed from
company metadata. KGD unknown checks and identity uncertainty remain visible.
No database field, source adapter or saved evidence was removed or changed.
112 React tests passed, including retained ownership and failed-read cases; build,
formatting and collectstatic passed. Read-only Chromium checks covered company,
person and people-list pages at 320/1440px without page overflow or JS errors.
Further ownership/person-identifier coverage needs a separate source-access audit;
this task did not start new integrations or change collection.

## People record clarity, 9 October 2026

The user reported repeats in People, not a request to erase database history.
A read-only repeatable-read audit found 1,068 identities, 384 with current roles,
384 repeated-name sets (383 within one company), one current cross-company name
collision, and no duplicate verified IIN. Legacy original/company-scoped records
and later source-scoped identities explain most repetition. Do not merge by name.

The existing current-role default is retained. Directory projections now add
bounded company context (up to two names and an exact distinct company count),
loaded in four list queries without per-person requests. Source history is clearly
labelled as including repeats, with current/historical row labels and an explicit
return to Current people. Source history, IDs, roles, snapshots and AI texts remain
unchanged; API filters are backward compatible. The collector was not interrupted.

21 isolated PostgreSQL entity tests and 112 React tests passed; build, formatting,
strict OpenAPI, collectstatic and Chromium filter/reload/context checks passed.
320/768/1440/1920px had no horizontal overflow or application error. Screenshots
were inspected and the owned read-only preview/browser stopped. Port 8000 refused
connections during inspection; the user's server was not started or stopped.
Private aggregates/tests/screenshots: artifacts/people-record-audit/.

MVP assessment at audit time: 813 companies, 525 contracts, 235 companies with an
accepted nonlegacy profile, 168 KGD registrations, three debt results and ten active
groups. Shared features are six addresses, three phones and one email; there is
no current real shared-verified-director feature. This supports a relationship
analysis thesis demonstration, not a proven fraud detector or complete catalogue.
A clearly labelled synthetic shared-director scenario and a reproducible saved
real-data walkthrough are proposed demonstration preparation, not executed here.
# Saved-view removal and neutral visual refinement, 9 October 2026

The user requested removal of saved graph views, a quieter black/white/blue
palette, smoother interactions, API-page refinement and a new logo/favicon.
DELETE `/api/v1/clusters/{uuid}/view/` accepts exactly an integer `revision`,
requires the authenticated account and CSRF, and clears only that account's
layout. Empty payload is a deletion marker; normal validation always produces a
nonempty layout. Keeping the revision prevents stale tabs from resurrecting it.
Profile lists exclude markers, GET returns null plus the retained revision,
and a subsequent explicit save restores a visible layout. Archived views can
also be removed. No migration or graph/evidence deletion is needed.

Graph toolbar and Profile provide removal; browser-only views use the existing
localStorage key. Removal preserves the current arrangement; Restore disables
until another view is saved. Removed account views do not fall back to an old
guest layout. Conflict and failed-read fencing remain in place.

Large surfaces now use charcoal and muted steel blue, with lighter primary
actions. Semantic graph relationship colours remain distinct. Shared IZ evidence
monogram and matching favicons cover header/footer/API/Vite. Page surfaces and
API disclosures have finite entrance motion; controls transition smoothly. API
motion uses the existing preference key and device reduced-motion setting.
The overview heading's two lines now remain separate.

Verification: 178 isolated PostgreSQL API/graph tests, all 118 React tests,
production build, formatting, strict OpenAPI validation and collectstatic passed.
Chromium checked seven routes plus graph at 320/768/1440/1920px without document
overflow or observed JavaScript exceptions; inspected desktop screenshots.
Guest save/remove/reload/re-save/restore and real synthetic-account save/remove/
reload/re-save/Profile removal passed. API filtering, native GET (200/one record),
motion persistence and device reduced motion passed. Working-data preview was
GET-only and PostgreSQL read-only; account writes used isolated synthetic SQLite.
Recovery precondition: independently verified 51-table backup recorded under
the Directory readiness entry in RECOVERY.md. Collection remains running.
Private reports/screenshots: ignored artifacts/ui-polish/. No Git, source
algorithm, dependency, environment or learning-file changes. Visual acceptance
and physical touch remain unverified; final audit/deployment are separate tasks.

## Blue palette correction after user review, 9 October 2026

The user rejected the preceding nearly monochrome treatment: reduce harsh
contrast while retaining the blue identity. Restored navy fills throughout the
workspace, directories, footer/dialogs and API; surfaces now use softer blue
steps, and primary actions are blue with off-white text. Graph canvas, inspector,
toolbar and surrounding panels share that palette while relationship colours
remain distinct. Logo connectors/dots and both favicon assets use #5797f0.
The previous grayscale choice is superseded; motion and saved-view behaviour
are unchanged. Production build, formatting and collectstatic passed. Chromium
screenshots of overview, graph, companies and API were inspected; twelve layout
checks at 320/768/1440px found no document overflow or JavaScript exceptions.
This was presentation-only, so backend tests were not rerun. Read-only preview
was stopped; collection/user server were untouched. Private screenshots use
artifacts/ui-polish/blue-*; user visual acceptance remains pending.

## Shared card surfaces and catalogue totals, 9 October 2026

The user requested consistent blue cards/rows and reported that overview counts
did not match the directory. Shared card/inset/row tokens now cover statistics,
groups, coverage, directories, detail panels, Profile, About and account surfaces.
Removed positional colour variants and repeating per-cell gradients; semantic
status/relationship colours and decorative hero artwork remain distinct.

Overview adds checked_company_count and current_verified_people_count using
the same company-profile/person-current-role query helpers as directory filters.
Home links those counts to default directories. Existing API total fields keep
their compatible meaning; raw identity totals include earlier/unverified source
records and are explicitly labelled as records in Evidence coverage. No records
are deleted or merged. No ingestion, persistence or schema algorithm changed.

Swagger's generic credential buttons are hidden; a visible account guide explains
public reads, workspace session reuse, page reload after login and staff-only jobs.
OpenAPI security definitions, CSRF/bootstrap and native request execution remain
unchanged. No separate API login or token entry is needed in this same-origin UI.

Verification: 28 isolated PostgreSQL overview/entity tests, two strict-static
Swagger tests, all 119 React tests, build/format/schema/collectstatic passed.
Read-only working HTTP checks matched 105 default people and 296 checked companies
between overview and their directories; 1,176 raw identities remained separately
reported (counts can change under ongoing collection). Chromium checked identical
computed backgrounds on eight overview cards and solid list cells, six routes at
320/768/1440px without document overflow/errors, and Swagger GET 200/one record.
Screenshots/reports: ignored artifacts/ui-consistency/. Owned read-only preview
stopped; user server and collection untouched. No Git. Visual acceptance pending.

## Design audit and space background, 9 October 2026

The user requested right-aligned directory arrows, a site-wide design review,
brighter twinkling stars and a small moon. People reserves a fixed action column;
People/Companies arrows sit about 20px from the row edge. Rounded cell hover no
longer has a square row backdrop. Mobile card actions retain their full width.

Particles uses an independent twinkle clock with staggered 3-7 second fades;
slow drift, one RAF loop, frame/DPR bounds and visibility pauses remain. The CSS
fallback also twinkles. Manual/device reduced motion freezes decoration. A small
textured blue-white crescent occupies the upper-right desktop gutter behind
content, is noninteractive/hidden from accessibility APIs, and hides below 768px.

The audit also fixed the unscrollable short-screen navigation drawer, aligned its
portal colours and registration actions with the workspace, enlarged compact
pagination/dialog/tab controls to 44px, and increased analysis scroll margins
past the sticky header. Swagger's documented fn.opsFilter hook now trims queries
and matches resource tags case-insensitively; bootstrap, CSRF and native operation
execution are unchanged. API styling remains as previously accepted.

Verification: 120 React tests, two strict Swagger static/manifest tests, production
build, formatting and collectstatic passed. Chromium checked eleven routes at
320/768/1440/1920px, with additional 390px and 500px-height checks. No document
overflow or application JavaScript errors were observed. Inspected desktop/mobile
screenshots, rounded row hover, aligned analysis columns, keyboard focus, scrollable
menu/signup and synthetic authenticated Profile. Real WebGL pixel samples changed
over 1.4 seconds; manual/reduced motion and context-loss fallback passed. Lowercase,
mixed-case/spaced and cleared API filters passed; native GET returned 200/one row.

Working preview was GET-only with PostgreSQL read-only; registration/Profile used
isolated synthetic SQLite. No schema/parser/dependency/data algorithm or Git change.
Worker, AI-worker and beat continued running. Owned previews are stopped after
verification. Private screenshots/report: artifacts/design-audit/. Physical touch,
Firefox/Safari and subjective visual acceptance remain unverified. This is a UI
audit; full project audit and deployment remain separate tasks.

## Kazakhstan dates and authorised EN/RU interface, 10 October 2026

After the final audit, the user explicitly authorised fixing AUD-001 and adding
Russian website localisation through an EN/RU control. This supersedes the
earlier localisation deferral. English remains the default, and project
documentation, CLI messages, code comments and source selectors stay English.
Official source labels, identifiers, company/person names and saved evidence are
preserved. Language selection must not change identity matching, review points,
the business timezone or immutable explanation text; no translation inference or
working recalculation was requested or performed.

Django explicitly uses `Asia/Qyzylorda`; Celery derives its timezone from the
same setting. `USE_TZ` and Celery UTC handling remain enabled. Calendar-day rules
therefore use Kazakhstan dates while timestamps retain aware UTC storage.
The data-quality report now uses the same local civil date for future contracts
and role applicability instead of extracting the UTC date from `now`.

Ten new regressions cover Kazakhstan and UTC midnight, year/leap-day rollover,
language-independent dates, inclusive role starts/exclusive ends, API/graph
agreement, same-day/future/undated KGD reporting, seven/eight-day freshness,
retained successes after failure, elapsed retrieval age, UTC timestamp round
trips, new graph/analysis/job dates and unchanged immutable histories on GET.
All **583 PostgreSQL tests** passed with zero skips (100.530 s including setup);
the owned database was removed. Normal-settings native and Linux probes both
resolved `2026-10-09T19:00:00Z` to `2026-10-10T00:00:00+05:00`. The Linux check
used the existing audited image with only current configuration mounted read-only,
no network, database or data volumes; it was not a new full-stack deployment.

Read-only working assessment covered 813 companies and 1,238 indexed edges.
At a fixed 04:10 UTC comparison clock, Chicago used 9 October and Kazakhstan
10 October. Current edge keys, applicable roles, KGD API statuses and current
group analysis-input hashes did not differ for this saved dataset. None of the
57 graph snapshots, 44 analyses or 47 jobs had a date differing from its
Kazakhstan creation day. Historical date differences can be legitimate, so this
check does not itself authorise refreshing saved results. No working migration,
regeneration, source request or model call was made.

The standalone API page shares `localStorage['iz2-language']` (`en`/`ru`, default
`en`) with the workspace and listens for cross-tab preference changes. Its
navigation, account help, status, resource search and motion controls are bilingual.
Swagger React preset wrappers translate Try/Cancel/Reset/Execute/Clear labels while
preserving native handlers, validation, entered values, CSRF and request
interceptors. Paths, fields, schema descriptions, examples and responses retain
their original contract/data. The page explains this boundary. The resource
filter accepts both English tags and Russian section names; no source text is
translated through a blanket DOM observer.

API checks completed: two strict static/manifest/bootstrap tests, JavaScript/CSS
formatting, Chromium language persistence and cross-tab changes, case/space-safe
Russian filtering and empty state, native GET 200 with one record, parameter
retention during language changes, rejected invalid parameters without an HTTP
request, Cancel and blocked-storage fallback. Layouts at 320/768/1440/1920 px
had no horizontal overflow. Reduced motion disabled animation after the media
change event. No application JavaScript exception was observed; Swagger emitted
one existing underscore deep-link deprecation message. Screenshots were inspected.

Private reports: `artifacts/timezone-fix/` and `artifacts/localization/`.
API account data and preview writes were synthetic; working reads were explicitly
read-only. Collectors remain stopped as found. No Git, dependency update, parser
expansion, saved-text rewrite or Phase 8 work was started.

Workspace localisation is complete for the current React routes, navigation,
footer, account dialogs/profile, directories, entity details, graph controls and
analysis presentation. `LanguageProvider` shares the API preference without
remounting the application. D3 labels update in place; changing language does
not refetch or save domain data, reset layouts or clear form/search drafts.
Account errors are translated when rendered. Source names, original descriptions,
identifiers and immutable saved explanation prose remain unchanged; an English
saved explanation has an explicit Russian language note. Decimal money formatting
changes separators without conversion to floating point. Calendar-only source
dates do not shift; timestamp displays use `Asia/Qyzylorda` in both languages.

All **141 React tests** passed, including locale preference/storage failures,
cross-tab changes, date boundaries, exact amounts, form state, directory filters,
graph state and account revision fencing. TypeScript/Vite build, formatting and
normal-settings collectstatic passed. Final Chromium verification covered ten
workspace routes at 320/768/1440/1920 px with no horizontal page overflow or
application JavaScript exceptions. The mobile header uses a second search row;
registration remains available inside the account dialog. Synthetic registration,
profile draft retention, graph save/reload/removal and EN/RU persistence passed.
Switching the graph language made zero API requests and retained node positions.
Workspace/API cross-tab synchronisation passed against the built assets. Desktop
profile/graph and narrow overview screenshots were inspected. Existing unit-test
act warnings and the Swagger deprecation above are not application exceptions.

Final report: `artifacts/localization/workspace-verification.json`. Browser writes
were confined to the owned synthetic SQLite database. No working records or saved
explanations were rewritten. `.env`, learning exercises, dependency manifests and
the accidental `next-app` starter were preserved. The temporary preview is stopped
after verification; restart the local application to load the new settings/assets.

## Accepted website and English-only API reference, 10 October 2026

The user accepted the current website design and Russian localisation, then chose
English-only developer documentation. The API template/helper/styles no longer
contain locale controls, dictionaries, language preference access or Swagger
translation wrappers. Native English controls, resource filtering, motion,
account guidance and the existing design remain. React EN/RU and its browser
preference are unchanged.

The two strict Swagger manifest/bootstrap tests, JavaScript syntax, scoped
formatting and normal collectstatic passed. Synthetic Chromium verification kept
`iz2-language=ru`: API html/title/buttons stayed English, native Execute returned
HTTP 200 with one record, English case/space-safe filtering worked and returning
to the website retained Russian. API layouts at 320/768/1440/1920 px had no page
overflow. Collected normal/preview JS and CSS hashes matched the source. Preview
was stopped afterwards; no working data, collection or model requests were used.
Screenshot/report: ignored `artifacts/localization/api-english-only-*`.

A read-only collector Status check found ingestion worker, AI worker and beat
stopped. The existing manual Start/Status/Stop workflow remains; no startup task
was installed. The next agreed task, after the user-operated commit/push, is
Docker configuration for a Linux server without a selected hosting provider.
Other final-audit findings and public deployment approval remain separate.

