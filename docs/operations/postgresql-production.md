# PostgreSQL deployment status and operations

Last reviewed: November 16, 2026.

**Production readiness is not verified.** The code contains PostgreSQL support;
the current independent result qualifies only a fresh empty-database schema
bootstrap. See [the source-bound fresh-bootstrap record](../engineering/POSTGRES_FRESH_BOOTSTRAP_2026_11_16.md).

## Fresh installation

`installer/install-native.sh` distinguishes EMPTY, MANAGED and UNMANAGED
databases. Its EMPTY branch creates the current ORM schema and records the
current Alembic heads. That pattern is supported by
[Alembic's cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html#building-an-up-to-date-database-from-scratch).
It must not be used to adopt an existing database silently.

A disposable PostgreSQL 15.19 run created 371 registered tables and recorded
all seven revision IDs with the repaired driver/version-table configuration.
This was a development-mode schema test with synthetic identities, not a
production TLS, full-app or disaster-recovery qualification.

The PostgreSQL DBAPI declared in the full backend requirements is psycopg2.
Implicit PostgreSQL URLs are pinned to it; explicit driver choices remain
explicit. The optional asyncpg package and actual async services require
separate qualification. The Personal dependency set is intended for SQLite.

## Existing installations

The historical migration graph currently has seven heads. `alembic heads`
can inspect them without connecting to a database. The old instruction
`alembic upgrade head` is ambiguous and is not a valid general deployment
procedure. Choosing `heads` does not prove the underlying historical chain
succeeds; known legacy DDL and dependency issues remain.

The installer treats an already-managed database separately and stops on
upgrade failure. It does not guarantee an untouched schema after a partial
upgrade. Qualify the exact supported starting revision and target on a
separate copy before deployment. Do not substitute `create_all` or an
ad-hoc stamp for an existing-database upgrade.

New PostgreSQL version tables use `VARCHAR(255)` for current 35/38-character
revision IDs. Existing `VARCHAR(32)` tables are deliberately not altered
automatically. Plan a reviewed explicit schema change for those installations;
read-only `alembic current` must remain read-only.

## Configuration and evidence limits

`backend/core/database.py` requires an explicit database URL in production and
contains PostgreSQL TLS configuration, connection health checks and pooling.
These code paths are configuration mechanisms, not evidence that a particular
production deployment is secure or complete. No live database credentials
belong in logs, committed files or evidence packets.

Before claiming production support, independently verify supported clean and
existing installs, normal application login and work, async services,
persistence across restart, multi-worker behavior and backup/restore/rollback.
The SQLite development snapshot helpers are not PostgreSQL backup proof.
The older [PostgreSQL 14 schema baseline](../engineering/evidence/postgresql_schema_20261107/README.md)
remains ORM-creation evidence only.
