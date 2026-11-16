# PostgreSQL fresh bootstrap — November 16, 2026

The supported empty-database installer bootstrap passed on a new disposable
PostgreSQL 15.19 database at product source `5aa8c1c8b8cdec59e17675e42c7ac4ec4338615a`.
It created **371 registered tables** and recorded all **seven revision IDs**
intact in a `VARCHAR(255)` version column. The owned test container was
removed and its absence confirmed. This qualifies fresh schema adoption,
not PostgreSQL production readiness.

## Problems repaired

SQLAlchemy 2.1 selects psycopg 3 for an implicit PostgreSQL URL, but this
application declares psycopg2. A central scheme-only normalizer now selects
the declared default and preserves the rest of the URL and explicit driver
choices. SQLAlchemy async-engine URLs and native asyncpg DSNs use separate
converters; the native event bus receives a plain protocol DSN.

The initial real trial refused before schema creation because the implicit
driver was missing. A second explicit-driver trial exposed the synchronous
driver being used by the async engine. After correction, 371 tables were
created, but Alembic rejected a 38-character head in its default 32-character
version column. Those earlier failures are retained, not reported as passes.

The final patch uses Alembic's supported PostgreSQL `version_table_impl` hook
and raises the existing Alembic dependency minimum to 1.14. New version tables
retain their name, schema, primary key and revision strings with wider
storage. Other dialects retain their normal implementation. Existing narrow
version tables are not automatically altered; read-only commands stay
read-only.

References: [SQLAlchemy PostgreSQL drivers](https://docs.sqlalchemy.org/en/21/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg2),
[Alembic version-table hook](https://alembic.sqlalchemy.org/en/latest/api/ddl.html#alembic.ddl.impl.DefaultImpl.version_table_impl).

## Independent verification

A new container used only a cached image, a memory-backed data directory,
384 MiB and one CPU. Identity, owner label, image, loopback port and PostgreSQL
system identifier were checked before an independent zero-table check.
Python children could connect only to that owned port under an OS network
rule; an independent C-driver probe verified refusal on another disposable
listener. No existing database, provider credential or application service
was contacted.

The test ran the installer's guarded EMPTY-path operations: `Base.metadata.create_all`
followed by `alembic stamp heads`. This is the [documented Alembic fresh-database
pattern](https://alembic.sqlalchemy.org/en/latest/cookbook.html#building-an-up-to-date-database-from-scratch).
SQL readback confirmed 371 tables before stamping, column width 255 and exact
seven-head equality afterward. This does not execute the historical migration
chain. [The result receipt](evidence/postgresql_fresh_bootstrap_20261116/result.json)
contains the measured scope.

Independently, **68 checks passed in 21.62 seconds** for driver selection,
scheduler URLs, version-table behavior and account migrations. Native asyncpg
handoff tests use a controlled client; that optional package was unavailable
in the cached environment. Real async transport is unverified. One existing
anchoring test's inherited-marker failure was separately reproduced on the
clean base and was not weakened or counted as a pass.

## Remaining scope

Existing database upgrades, narrow version-table conversion, historical
migration replay, full application boot/login, persistent-volume restart,
backup/restore and multi-worker operation remain separate requirements.
The seven-head graph still makes `upgrade head` ambiguous; this change does
not merge branches, rename revisions or stamp an existing database.
