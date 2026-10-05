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
