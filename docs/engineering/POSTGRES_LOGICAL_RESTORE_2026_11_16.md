# PostgreSQL logical restore — November 16, 2026

A new owned PostgreSQL 15.19 case at product source
`c1ab1af1da0600f6bc91199b7569d5756ce64492` passed a logical dump/restore and
normal public-API use of the restored data. All **372 public tables** matched
by exact row count and canonical row-content SHA-256 fingerprint, including
all seven original migration heads and the 255-character version column.
The count includes 371 application tables plus the Alembic version table.

After normal signup/login and creation of a harmless owned canvas, both
source API processes stopped. The verifier checked Docker owner/image/ID and
PostgreSQL database/user/cluster identity, created a new database from
`template0`, proved it empty, then made one custom-format `pg_dump` and one
`pg_restore --exit-on-error --single-transaction --no-owner --no-acl`.
It used no clean/drop/overwrite operation. Source snapshots before and after
the dump matched; restored table lists, counts, contents and heads matched.
The measured archive was 1,285,858 bytes; its SHA-256 is recorded in the
filtered result. The synthetic archive was inside the disposable container,
not retained as a backup of user data.

Fresh canonical API processes then used the restored database: normal login,
readback of the same canvas ID/title, unauthenticated refusal (401), another
API-process restart, normal login again and the same readback all passed.
No user or canvas was re-created on the restored database. Synthetic login
credentials passed through anonymous pipes and process memory, never command
arguments, logs or credential files. Normal login legitimately adds session
rows after the restore-content comparison.

The run used the cached Python 3.12.13 environment, controlled test mode,
synthetic data and a new memory-backed container limited to 384 MiB/one CPU
with no host volume. OS/listener/native-driver controls allowed only the
owned PostgreSQL and HTTP ports. All four API children stopped and the exact
owned container was removed; independent absence checks confirmed cleanup.
No provider inference, auth override, dependency installation, existing
operator database, app port or unrelated Docker resource was used.

This is single-database logical recovery evidence. It does not establish
cluster-role/extension recovery, PITR, database-container restart,
persistent-volume durability, multiworker operation, soak, ordinary browser
journeys, model quality or production disaster-recovery readiness. The
original 143 claims/18 goals and historical score remain unchanged.

References: [PostgreSQL 15 pg_dump](https://www.postgresql.org/docs/15/app-pgdump.html),
[PostgreSQL 15 pg_restore](https://www.postgresql.org/docs/15/app-pgrestore.html).

[Filtered result](evidence/postgresql_logical_restore_20261116/result.json).
