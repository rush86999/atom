# PostgreSQL document-lineage migration — existing-table proof

**Independent result: 29 tests passed, none skipped**, including one real
PostgreSQL **14.24 (Homebrew)** cluster. Qualified acceptance source:
`51fedc077d5e5db0fa750069dc2f5bc792a02c65`; migration source is merged main
`02c9b16744e4fc9cfe7c81dce2ebf82cac7bf909` (PR #978). The harness and test
file bytes match that qualified source. The harness itself remains identical
to the earlier `e61c6c646` proof; the unit fixture now uses canonical `/tmp`
on both macOS and Linux instead of assuming the Mac-only path. This adds a repeatable operator check,
not a production behavior change or whole Goal3/16 completion.

## What ran

The real revision `20261117_dataset_entry_lineage` ran through
Alembic Operations against a freshly created **legacy-shaped existing**
`dataset_entries` table containing four synthetic sentinel rows, its primary
key, named version uniqueness constraint and legacy indexes. The revision
was not replaced with equivalent hand-written test DDL.

The check proved nullable VARCHAR/no backfill/default, a valid non-unique
lineage index, unchanged sentinel rows and legacy structures, new lineage and
row writes, repeated upgrade idempotence, missing-index repair, downgrade
removing only the new objects, and successful re-upgrade. Duplicate versions
were rejected with SQLSTATE 23505 before and after the migration and restart.
An absent-table database remained a no-op on repeated upgrade/downgrade.

The sentinel digest stayed
`a66e3af0af258ba7e1411ce47339398eaedc6bbb333446513086ae05d27fd377`.
The clean fast stop/start changed the owned server PID, retained the same
data directory, and a new connection read both existing and newly written
lineage values and enforced uniqueness. Root separately checked that the
server PID and postmaster PID file were absent after cleanup, with no TCP
listener. The scratch evidence was preserved.
[Filtered source-bound result](evidence/postgres_document_lineage_20261117/result.json).

## Isolation and retained failures

The harness refuses protected, non-empty, relative and symlinked roots before
creating a cluster. It binds only a private 0700 Unix socket, disables TCP, and
requires its marker, PID file and actual postgres data-directory command to
agree before restart/stop. It never uses an existing database connection or
stops an owner service.

A review found that child-command environment filtering did not isolate
SQLAlchemy connections in the parent. The final CLI re-executes once with
owner PG variables and DATABASE_URL removed, private HOME/TMPDIR, and explicit
private libpq options. The real regression supplies synthetic hostile service,
password/TLS paths and unreadable simulated owner files; resolved connection
parameters remain bound to the private cluster. No owner credentials or files
are used. TLS/GSS are disabled for this local check, not handshake-tested.

An intermediate real run failed because connection parameters were read after
closing the connection. It stopped its owned server and was retained. The
final code reads the parameters while connected. Root's first verification
refused an outdated expected commit before tests or cluster creation; after
checking the actual final source, the independent full run passed. These
setup failures are not hidden or counted as passes.

## Run the check

Use the project's configured Python environment with SQLAlchemy, Alembic and
psycopg2 already installed, plus a local PostgreSQL binary directory:

```sh
python scripts/acceptance/postgres_document_lineage_upgrade.py --pg-bindir /path/to/postgresql/bin
```

The default creates a new private directory under `/private/tmp`; never point
it at app data or an existing cluster. The harness leaves its report and data
for inspection after stopping its server. The default unit suite skips the
real-cluster test; opt in explicitly to include it:

```sh
TESTING=1 ATOM_PG_LINEAGE_ACCEPTANCE_REAL=1 python -m pytest backend/tests/test_postgres_document_lineage_upgrade_acceptance.py -q
```

The real path currently targets the locally installed PostgreSQL binary path;
hosted CI runs the database-free controls with the real case visibly skipped.
This is not a claim that CI runs a live database migration.

## Scope still open

Only PostgreSQL 14.24 with the installed libpq 17 client was tested. The direct
revision check does not run the full Alembic graph, start Atom on that database,
exercise concurrency/multiple workers, test abrupt crash recovery/PITR, or
establish other PostgreSQL versions/platforms. The original 143 claims and 18
goals remain incomplete. Broader document/live-connector and operator gaps
remain as recorded in the current goal map.

Publication code head: `3784a97c74a48e84a44f8843c92a97421cc9763b` on documentation main `1453f2cf4`.
Root checked that rebasing changed only the nine already-reviewed documentation
files: runtime, harness/test and CI bytes remain identical to the executed
source. All 642 CI-preservation controls passed independently on this release.
