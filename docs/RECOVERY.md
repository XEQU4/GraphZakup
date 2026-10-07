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
