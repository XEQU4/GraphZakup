# Backups and recovery verification

Preserve existing PostgreSQL before application changes. A verified backup requires restoration into a separate temporary database and comparison against a consistent source snapshot. Completed baseline checks are in [BASELINE.md](BASELINE.md).

## What is preserved

`scripts/backup_database.py` creates a custom-format single-database dump with `pg_dump`. A read-only REPEATABLE READ connection exports a snapshot used for both counts/hashes and the dump, keeping concurrent writes from invalidating comparisons.

`--verify-restore` creates local `gpg_restore_verify_<random UUID>`. Restore uses `--exit-on-error`, `--no-owner`, `--no-privileges`. Compare `public` tables, columns, row counts, SHA-256 content including duplicates; read order is irrelevant. `django_migrations` is included and separately reported.

No Django/Celery/parsers/AI run. Cleanup drops only the database created by that invocation after checking the exact generated name and excluding the source. Failures retain dump/JSON. Failed cleanup records the remaining name; never remove by approximate name or broad prefix.

The dump includes schema/data/sequences. Comparison covers regular/partitioned public tables and column characteristics, not every default/constraint/index definition or sequence value. Sequences lie outside the row MVCC snapshot. Successful restore verifies execution, not equivalence of every definition. Server users/tablespaces/`.env`/media/external data need separate preservation. Test restore omits original ownership/privileges.

## Connection and tools

Read root `.env` and process variables. `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGHOST`, `PGPORT` take precedence over corresponding `DB_*`; process values override file values.

Passwords pass through child-process environment only, never output/command arguments/reports. Reports contain source-name hash, versions, structure/checksums, not personal rows.

Phase 0 verified Python 3.13.5/PostgreSQL 17.6. Tools: `C:\Program Files\PostgreSQL\17\bin`; adjust or use discovery elsewhere. Restore requires `CREATE DATABASE`, automatically only on local servers. Ambiguous libpq routing/credential URIs instead of simple database names are rejected.

## Repeat a backup

From the root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -B scripts/backup_database.py --pg-bin 'C:\Program Files\PostgreSQL\17\bin' --verify-restore
```

Without verification:

```powershell
.\.venv\Scripts\python.exe -B scripts/backup_database.py --pg-bin 'C:\Program Files\PostgreSQL\17\bin'
```

The second command alone does not prove recoverability. Acceptance requires successful test restoration.

Offline safeguards:

```powershell
.\.venv\Scripts\python.exe -B -m unittest tests.test_backup_database -v
```

Output defaults to ignored `artifacts/phase0/`, excluded from images. `--output-dir` must stay within `artifacts/`. Restrict dump access. Same-disk backups protect against incorrect changes; disk-failure recovery needs a separate secured copy. External upload was outside Phase 0.

## Check the result

Expected `database_*.json`:

- `status: passed`;
- `verification.status: passed`;
- `verification.differences: {}`;
- `verification.django_migrations_verified: true`;
- `verification.cleanup: dropped`;
- dump SHA-256/size.

Absent/failed verification is not a successful restore check. Preserve dump/safe error code; never retry over the source database.

## Recover the project

Check SHA-256, prepare a separate empty database, restore with verified tools, compare tables/migrations, check the app without collection/AI. Switching `.env` and restarting jobs are separately authorised operations.

Retain the previous database until verification. Do not use `--clean`, source deletion, or destructive import for recovery.

Official references: [PostgreSQL 17 pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html), [pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html).

## Verified Phase 1 upgrade

On 5 October 2026, Phase 0 backup was additionally restored into separate Docker PostgreSQL 17.11. All 29 tables matched before migration; after `graph.0003_cluster_analysis_state`, original values in 28 tables outside the migration log matched. Four cluster UUIDs/memberships/texts remained unchanged; temporary DB dropped. Read-only source comparison matched Phase 0. See [PHASE1.md](PHASE1.md).

Verified copy migration does not imply source migration. Check a current backup before `python manage.py migrate` in the intended environment. Docker uses its migration service.

## Verified Phase 2 upgrade

On 5 October 2026, a new PostgreSQL 17.6 dump was created before schema changes and restored successfully. `artifacts/phase2/database_20261005T155408Z_21f9e0e2.json` records passed status, 29-table comparison, cleanup. SHA-256 was rechecked before migration.

Another restored database was upgraded through all migrations. Existing values in 28 tables outside migration history matched by original PKs/columns, allowing added fields/rows. Contracts/original people/roles/cluster UUIDs/membership/texts survived. All 128 tests passed in another isolated PostgreSQL database; both temporary databases dropped. Source matched the dump before/after checks.

See `artifacts/phase2/postgresql-verification.json` and [PHASE2.md](PHASE2.md). Legacy roles are archived with company-scoped identities; reverse data migration intentionally does not restore name merges. Recover old schema from a separately restored verified backup. The working database was not migrated during Phase 2. Before upgrading, confirm no writes occurred after backup; otherwise create a current one.

## Verified Phase 3 upgrade

On 5 October 2026, the current PostgreSQL 17.6 database was backed up before adding the KGD state model. `artifacts/phase3/database_20261005T180443Z_3f4eaeb2.json` records passed restoration, equality of all 38 public tables, verified migration history and cleanup. Dump SHA-256: `6d9277931ce1645fed7c5af42c3ebdc99e3e3778456f42ab8c83fa36a872e8a5`.

The dump checksum was checked before another isolated restore/upgrade. `ingestion.0006_companykgdstate` preserved original values in all 37 tables outside migration history and created zero KGD state rows. All 165 offline tests passed in a second isolated PostgreSQL database. Source comparison before/after matched the backup; both temporary databases were removed. See `artifacts/phase3/postgresql-verification.json` and [PHASE3.md](PHASE3.md).

The working database was not migrated during this implementation. Apply the prepared migration only after confirming this backup is still current, or create/verify a fresh one if there have been writes. No live KGD data is present merely because the table exists.

## KGD live-check preparation, 6 October 2026

A fresh backup `artifacts/phase3/database_20261006T100832Z_6181978d.json` passed independent restoration; the restore database was dropped. Dump SHA-256: `2445270a3f32703fe9ef0d2bf2d6512c09524594ed575fad7e6064fc3acf63bb`. All 38 working tables matched this backup after preparation.

A separate empty PostgreSQL database was migrated and seeded with one selected company BIN and a placeholder name, without importing working records or inventing KGD observations. Its exact generated name and ownership marker are in the ignored `artifacts/phase3/kgd-check-preparation.json`; use both to verify ownership before later cleanup. This database was not deleted and must not be confused with the temporary restore database, which was deleted. Preparation checks passed before live authorisation; see `artifacts/phase3/kgd-preparation-verification.json`.

After explicit user authorisation, exactly one taxpayer request succeeded. At that point the separate database retained one accepted source observation and one KGD state; the taxpayer runner guards against repeating that request in the same database. Repeated company GETs, successful resume and cache validation used the saved result without HTTP requests. Afterward, all 38 working tables still matched the fresh verified backup. The working database was neither migrated nor modified. Post-check report: `artifacts/phase3/kgd-live-preservation-verification.json`; scope and remaining limits are in [PHASE3.md](PHASE3.md). Retaining the isolated evidence database does not authorise further collection.

## KGD arrears and reporting-date correction, 6 October 2026

A separately authorised single arrears request reused that day's verified registration within a test-only 24-hour cache; the working cache stayed at 900 seconds. The service accepted the second ISNA token as the account-token parameter and returned a complete zero-arrears response. Version `3.0` rejected its reporting timestamp format and retained the failed attempt safely. Only allowlisted identity, amounts and reporting-date fields were saved privately for offline reprocessing.

Before accepting parser `3.1`, the current backup above was checksum-verified, independently restored and upgraded again. All 37 original tables outside migration history retained their values, all 167 tests passed on a separate PostgreSQL test database, and all 38 working tables still matched the backup. Both generated restore/test databases were removed. Report: `artifacts/phase3/postgresql-reporting-date-verification.json`.

The same partial KGD run was resumed using saved permitted fields, with HTTP blocked, and completed successfully. Original retrieval times and the failed `3.0` observation were retained; accepted `3.1` observations are marked as reused. The isolated evidence database now retains both company checks and remains ownership-marked for later controlled cleanup. It was not deleted. The working database was neither migrated nor modified. Report: `artifacts/phase3/kgd-debt-reprocessing-verification.json`. No full original response or credential value was placed in documentation, fixtures or images.

## Verified Phase 4 upgrade, 6 October 2026

A fresh PostgreSQL 17.6 dump was independently restored before graph schema and
algorithm changes. All 38 public tables and migration history matched. Report:
`artifacts/phase4/database_20261006T114348Z_9961d171.json`. SHA-256:
`2a46400bfe2e30b0d061f2407d5350fd52cc950fc9f0fda5ae28be9dcc9b8a2d`.
The verification database was dropped.

Another isolated restore was upgraded through `graph.0005`. Original columns and
rows in all 37 tables outside migration history matched the backup by original
primary keys, including cluster UUIDs/texts/membership. The new graph tables were
empty and no legacy evidence or KGD result was invented by migration. All 191
tests passed in another isolated PostgreSQL database. All 38 working tables
matched before/after. Both generated databases were dropped; the retained Phase
3 KGD evidence database was not touched. Report:
`artifacts/phase4/postgresql-verification.json`. See [PHASE4.md](PHASE4.md).

The working database was neither migrated nor rebuilt. Before applying the
prepared migrations and explicitly rebuilding graphs from saved facts, confirm
this backup remains current or create/verify a new one. Graph retirement and
history preservation are application operations, not a trial restore or data
cleanup. Layouts and immutable graph snapshots are added only after explicit use.

## Verified Phase 5 upgrade, 7 October 2026

A fresh PostgreSQL 17.6 dump was independently restored before analysis schema
and scoring changes. All 45 public tables and migration history matched. Report:
`artifacts/phase5/database_20261007T050831Z_677880d2.json`. Dump SHA-256:
`123eb8e84f238f882c5813e08616250eeb53a6f5089383c92b565345faaf5f97`.
The generated restore database was dropped.

The checksum was checked before another isolated restore/migration through
`ai.0002_analysistarget`. Original PKs/columns/row values in all 44 tables outside
migration history matched; five new AI tables were empty. No graph, legacy text,
analysis or source evidence was regenerated by migration. All 238 tests passed
in a second isolated PostgreSQL database, including concurrent deduplication.
All 45 working tables still matched the backup before/after verification. Both
generated databases were dropped. Report:
`artifacts/phase5/postgresql-verification.json`; see [PHASE5.md](PHASE5.md).

The working database was neither migrated nor recalculated. Apply the schema
only after confirming the backup is current; create and verify another backup
after any intervening writes. `analyse_clusters` explicitly prepares saved
graphs without source/model requests; `build_clusters` now atomically prepares
affected analyses/templates too. Local inference verification uses an unrelated
synthetic SQLite database retained under ignored `artifacts/phase5/`.

## IZ2 rename and repeated local AI check, 7 October 2026

After the user applied Phase 5 migrations/analysis, a new backup was created and
independently restored before rebranding. All 50 public tables and migration
history matched. Report: `artifacts/iz2/database_20261007T072136Z_ae5159b9.json`;
dump SHA-256: `f7e8d6070c02c681e7dfce7119d19d2bca20b5ae1aea892b7cf2a6f93e279c10`.
The owned restore database was dropped. A subsequent read-only comparison matched
all 50 working tables; no working migration, graph refresh or model job was run.

Project metadata changed to iz2 while dependencies/resolution remained identical.
The user's `.env` and `test.py` hashes matched the pre-rename copies. Existing
database/volume identifiers and graph-view keys were preserved; Compose default
volume naming was explicitly checked against a legacy environment without a
project-name setting. New installations may use the iz2 namespace.

The reusable local AI probe passed four synthetic cases through real Qwen3:4b,
saved publication, repeat reuse and graph/JSON reads. The branded demo served all
four saved results and styles. The full offline suite passed 238 tests with three
PostgreSQL-only skips; both Node suites, migration drift and frozen offline uv
installation passed. A 211-file credential scan found no credential values.
Reports are in ignored `artifacts/iz2/` and `artifacts/local-ai/`. Model quality
superiority and local-ai container execution remain unverified.

## Explanation presentation follow-up, 7 October 2026

Before changing saved text generation, a fresh PostgreSQL backup was restored
independently and all 50 tables/migration history matched. Report:
`artifacts/explanations/database_20261007T080814Z_f0b328d1.json`; dump SHA-256:
`ef9c34fdaa53a90527187f67f63bf5a3b1ff8d29f263b809d231c8bf3b518374`.
The owned restoration database was dropped.

Another isolated restore preserved all 49 tables outside migration history; no
schema changes were needed. All 248 PostgreSQL tests passed in a separate test
database. Both generated databases were dropped, and all 50 source tables still
matched. Existing explanations were not rewritten; new presentation versions
were checked only on synthetic data. `.env`, learning exercises and dependency
resolution were preserved. Reports: `artifacts/explanations/postgresql-verification.json`
and `repository-verification.json`. The last user demo/report was untouched.

## Verified Phase 6 API, 7 October 2026

A current 50-table backup was independently restored with migration history and
all values matching. Report: artifacts/phase6/database_20261007T093012Z_af7436d0.json.
Dump SHA-256: cc084d7e345583036da4cb66cf557ffa6042d904b569ccaef0ec9e44a82f22fd.
A second isolated restore/migration retained original values in all 49 tables
outside migration history. All 320 tests passed on a separate PostgreSQL test
database; both owned databases were dropped. All 50 working tables matched before
and after. Report: artifacts/phase6/postgresql-verification.json.

The DRF API adds no domain models/migrations and does not modify rules or saved
histories. Existing dependency versions, .env and test.py were preserved; API
packages were added to the lockfile. A copied synthetic SQLite fixture retained
all table contents after real HTTP GET checks. The owned localhost:8768 API probe
was stopped. The user's existing synthetic demo and working data were untouched.


## Phase 7 self-service accounts, 7 October 2026

Before account-index changes, a fresh backup was independently restored and all
50 tables, values and migration history matched. Report:
`artifacts/phase7/account-ui/database_20261007T160644Z_2dc3026c.json`. Dump SHA-256:
`914e5c9600d737117ff3667578711c84fcee257eb8b8fd79988e5fb922117719`.
The owned verification database was dropped.

A second isolated restore verified `api.0001_account_identity_indexes`, retaining
all 49 original tables outside migration history. Duplicate case probes rolled
back; empty legacy emails remained supported. Reverse/reapply preserved values.
All 353 tests passed on a separate PostgreSQL test database without skips; both
owned databases were dropped and their absence checked. Reports:
`artifacts/phase7/account-ui/postgresql-migration-latest.json` and
`postgresql-tests-latest.json`. Browser account writes used only a synthetic SQLite
preview with external HTTP, background dispatch and models disabled. Working
migration/account writes, graph recalculation and source collection were not run.
Apply the migration before using registration; refresh the backup after any
intervening working-data writes. Final integrity checks are recorded separately.

Final source comparison matched all 50 working-table fingerprints. Protected
files and existing Python dependency versions were unchanged; 353 scanned project
files contained no configured credentials. Account-index migration remains pending
on the working database. Report: artifacts/phase7/account-ui/final-verification.json.

## Phase 7 saved-view follow-up, 7 October 2026

A fresh backup was independently restored with all 50 tables, values and
migration history equal. Report:
`artifacts/phase7/save-view-followup/database_20261007T170237Z_05462997.json`.
Dump SHA-256:
`35b69ff355ded29efdbd26610edd71b058c4c052da3bf685a3de1eaf9d839493`.
The generated restore database was dropped. The working database now has all
69 existing migrations applied; no new migration was added in this follow-up.

All 357 tests passed without skips in a separate owned PostgreSQL test database;
the test runner dropped it and its absence was verified. All 50 working-table
fingerprints matched the fresh backup before and after. Report:
`artifacts/phase7/save-view-followup/postgresql-tests-latest.json`. No working
write, migration, source collection or model job was run during verification.


## Explanation regeneration backup, 8 October 2026

Before the user-authorised explanation changes, a fresh PostgreSQL dump was
independently restored and compared across all 50 tables and migration history.
Report: `artifacts/phase7/ai-narrative/database_20261008T054451Z_58f1fe71.json`.
Dump SHA-256: `911063e44b7a0173634683a49bb33032cc2ae9a58cc0a9ab01281ab13201d446`.
The owned restoration database was dropped. Original graph, analysis and text
rows were also fingerprinted individually before explicit generation jobs.


## Parser and data-quality follow-up, 8 October 2026

Before ingestion algorithm changes, a fresh backup was independently restored.
All 50 tables, values and migration history matched; the owned restore database
was dropped. Report: `artifacts/parser-quality/database_20261008T102835Z_8622e803.json`.
Dump SHA-256: `e0b986f9bfcf115f5e4e359b418bc74a116f1c2c02f73e7cfb8386133b20576a`.
The subsequent working-data audit used read-only transactions and retained exact
source/protected-file fingerprints in `artifacts/parser-quality/`. No schema
migration, source cleanup, collection or explanation job was run by this audit.


## Published source refresh, 8 October 2026

The pre-publication backup above was rechecked against all 50 working tables
before the atomic publication of 29 accepted observations for 12 companies.
Original immutable histories and unrelated rows passed preservation checks;
all 26 public API reads were read-only. The old baseline now describes the
pre-publication state and must not be mistaken for the current working state.

A new post-publication backup was independently restored and verified:
`artifacts/parser-live/recovery-after-publication/database_20261008T121036Z_31a18f35.json`.
Dump SHA-256: `b1a09f146af59d3cf2e3f8a4cc4e211c981bbdb02e450ae8fe82c7aac7ec36de`.
All 50 tables/values and 69 migration rows matched. The owned restore database
was dropped and its absence checked; working data and protected files stayed
equal to the committed publication. Both old and new backups are retained.
The isolated live evidence and rehearsal copies remain separately owned review
artifacts; never use them as the application database or remove the source.

## Fifty-company expansion recovery, 8 October 2026

The previous verified backup matched all 50 working tables before code changes.
During collection the user changed a personal graph layout; all other tables
remained equal. A new dump preserved that layout:
`artifacts/parser-expansion/recovery/database_20261008T170904Z_f7760eb7.json`.
Its restoration matched all 50 tables before offline replay; original histories,
unrelated rows and repeat-refresh stability passed (`rehearse.json`). The owned
copy was dropped. The same frozen results were published atomically without HTTP,
Redis or model calls (`publish.json`); 80 API reads left all table hashes equal.

The current post-publication recovery point is
`artifacts/parser-expansion/recovery-after/database_20261008T171203Z_b9d8a747.json`.
Its independent restoration passed across all 50 tables and migration history;
the verification report contains the dump checksum and exact comparisons. The
owned restoration database was dropped. Earlier backups remain historical.

## Background collection, 8 October 2026

The expansion backup matched all 50 tables before orchestration changes. A further
verified snapshot retained initial operational attempts before parser 2.3 changes:
`artifacts/background-verification/recovery/database_20261008T174228Z_743cc038.json`.
Following the first real bounded iteration, another independent restoration passed:
`artifacts/background-verification/recovery-after/database_20261008T180552Z_5e630227.json`.
Both reports contain checksums, exact table/migration comparisons and owned-copy
cleanup. No source database was restored or removed. Automatic collection is now
explicitly authorised and running; future table differences are expected. Stop the
owned collector before modifying ingestion algorithms and verify a fresh recovery
point against the then-current state. Never compare an active collector with an
old static baseline and treat all differences as corruption.

## Collection redesign, 9 October 2026

The owned collector was stopped before changes. Fresh recovery:
`artifacts/collection-v2/recovery/database_20261009T054153Z_ee92c64d.json`.
Independent restoration passed. Migration ingestion.0007 adds only ContractRetry;
forward/reverse/reapply were checked on a separately restored owned database.
All 47 non-permission/migration tables matched exactly; original permission/content
type rows were preserved (Django adds entries for the new model). Reverse restored
the original schema/migration rows; new content-type/permission entries are retained
by Django. The owned copy was dropped; working data stayed unchanged during rehearsal.

The working migration was then applied and authorised collection/local generation
resumed. After the first live cycle, graceful shutdown and another verified restore
produced `artifacts/collection-v2/recovery-live/database_20261009T061843Z_e3d52472.json`.
This recovery point includes the new table and automatic saved model texts; all
51 tables and migration history matched. Collection resumes afterwards, so later
source differences are expected. Never delete source companies/history to reset coverage.

Before adding safe transport diagnostics, a further graceful stop and independent
restore passed: `artifacts/collection-v2/recovery-diagnostics/database_20261009T062729Z_6f01e3d2.json`.
The collector was subsequently restarted. This is the latest recorded recovery
point, not a static baseline for the now-running collector.

## Director source audit, 9 October 2026

Owned collection was gracefully stopped before parser/selection changes.
`artifacts/parser-final-audit/recovery/database_20261009T102120Z_3a298b8a.json`
records a successful independent restore across all 51 tables and migrations.
Four captured registry observations were rehearsed on an owned restored copy;
original immutable rows and 809 unrelated companies remained unchanged. The copy
was dropped. Identical frozen evidence was then published atomically, with no
network/inference and no additional versions on repeat refresh. Thirty-eight
public GETs preserved the resulting domain tables.

Post-publication recovery independently passed:
`artifacts/parser-final-audit/recovery-after/database_20261009T104602Z_b09c838d.json`.
Reports contain checksums and exact comparisons; the source database was never
restored/deleted. Collection then resumed, so this is a recovery point rather than
a static expectation for the running database. See PARSER_AUDIT_2026_10_09.md.

## Directory readiness, 9 October 2026

After stopping owned collection, a fresh dump was independently restored:
artifacts/readiness/recovery/database_20261009T112032Z_d986d012.json.
All 51 working tables matched before and after offline implementation/tests and
read-only readiness checks. No schema or working-domain migration was required.
Collection resumes afterwards; subsequent changes are expected. Details in
DATA_READINESS.md and ignored artifacts/readiness/.

## Final-audit recovery and date-policy follow-up, 10 October 2026

Fresh recovery was independently verified during the final audit:
`artifacts/final-audit/recovery/database_20261010T044152Z_7c0230ad.json`.
The dump and comparison shared one exported `REPEATABLE READ READ ONLY` snapshot.
All 51 public tables matched by columns, row counts and multiset row hashes:
18,890 rows including 70 migration records. The owned restored database was
dropped and its absence verified. Dump SHA-256:
`3e4f202950117e3953cb997ab0d954b3605c4f07671325603f8ee4d6050e68ff`.
Summary: `artifacts/final-audit/recovery/summary.json`. This verifies saved table
contents; it does not certify sequence values, grants, indexes, external media or
a complete target-host Compose recovery.

This recovery point was checked before the authorised timezone correction.
The correction requires no schema migration, source recollection or history
rewrite. Its tests used an owned PostgreSQL database, removed afterwards.
A separate repeatable-read read-only assessment found no creation-day mismatch
candidates in the 57 graph snapshots, 44 analyses or 47 analysis jobs, and no
current role/graph/KGD projection differences between the two relevant civil
dates. This is a bounded assessment, not permission to rewrite old results.
Private reports: `artifacts/timezone-fix/`. Worker, AI-worker and beat were already
stopped at audit entry and remain stopped; earlier running-status entries above
describe their historical checks.
