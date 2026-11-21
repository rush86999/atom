"""Initialize a brand-new managed SQL database exactly once.

This is a standalone synthetic implementation.  It knows nothing about an
application's models, migrations, or seed data; all of that is supplied as
callbacks.

Contract
--------
* The application schema must be empty before the initializer does any setup.
  A schema containing the completion marker (or an ``alembic_version`` table)
  is *managed* and is refused.  Any other relation makes it *unmanaged* and is
  also refused.  Neither kind is altered or adopted.
* Setup uses unqualified DDL, so the target schema is always the connection's
  current schema.  An explicit ``schema`` must therefore match PostgreSQL's
  ``current_schema()`` exactly; explicit schemas are unsupported on SQLite.
* All work runs on one SQLAlchemy connection inside one transaction.
* On PostgreSQL a transaction-scoped advisory lock serializes concurrent
  initializers.  Its key is derived deterministically from ``project_key``.
* The callbacks run in order: create metadata, verify extra schema/seed,
  record the exact migration heads.  The completion marker is written last.
  Any callback exception rolls the whole transaction back, so no completion
  marker can survive a failure.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Final

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine

DEFAULT_PROJECT_KEY: Final[str] = "atom-managed-bootstrap"
COMPLETION_TABLE: Final[str] = "_bootstrap_completed"
MANAGED_TABLES: Final[frozenset[str]] = frozenset(
    {COMPLETION_TABLE, "alembic_version"}
)

_LOCK_NAMESPACE: Final[str] = "fresh-database-bootstrap/v1"
_SQLITE_INTERNAL_PREFIX: Final[str] = "sqlite_"


class BootstrapError(RuntimeError):
    """Base class for initializer refusals."""


class SchemaNotFreshError(BootstrapError):
    """The target schema is not empty and was therefore refused."""


class ManagedSchemaError(SchemaNotFreshError):
    """The target schema already contains a managed bootstrap/migration marker."""


class UnmanagedSchemaError(SchemaNotFreshError):
    """The target schema contains pre-existing, unmanaged relations."""


class SchemaBindingError(BootstrapError):
    """The requested schema cannot be bound to the connection's DDL target."""


def advisory_lock_key(project_key: str) -> int:
    """Return a stable, project-specific signed 64-bit advisory-lock key."""

    if not project_key:
        raise ValueError("project_key must not be empty")

    material = f"{_LOCK_NAMESPACE}:{project_key}".encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def initialize_fresh_database(
    engine: Engine,
    *,
    create_metadata: Callable[[Connection], None],
    verify_extra: Callable[[Connection], None],
    record_expected_heads: Callable[[Connection], None],
    project_key: str = DEFAULT_PROJECT_KEY,
    schema: str | None = None,
) -> None:
    """Initialize an empty application schema in one transaction.

    Each callback receives the same :class:`sqlalchemy.engine.Connection` used
    for every other step.  Callbacks must not commit or roll back; they should
    only execute work on that connection.

    ``schema=None`` means the connection's current schema (``public`` or the
    first valid ``search_path`` entry on PostgreSQL, ``main`` on SQLite).
    """

    lock_key = advisory_lock_key(project_key)

    with engine.connect() as conn:
        with conn.begin():
            # SQLite's DBAPI otherwise delays BEGIN until the first DML
            # statement, which would make early DDL non-transactional.
            _start_physical_sqlite_transaction(conn)

            # Lock first: parallel initializers must not race the occupancy
            # check against another worker's setup.
            _acquire_transaction_lock(conn, lock_key)
            _require_empty_schema(conn, schema)

            create_metadata(conn)
            verify_extra(conn)
            record_expected_heads(conn)

            # The completion mark is deliberately the last write.  An
            # exception above prevents it, and the transaction rolls back.
            _write_completion_mark(conn, project_key, schema)


def _start_physical_sqlite_transaction(conn: Connection) -> None:
    if conn.dialect.name != "sqlite":
        return

    driver = getattr(conn.connection, "driver_connection", None)
    if driver is not None and getattr(driver, "in_transaction", False):
        return
    conn.exec_driver_sql("BEGIN")


def _acquire_transaction_lock(conn: Connection, lock_key: int) -> None:
    if conn.dialect.name == "postgresql":
        # pg_advisory_xact_lock is released automatically on commit/rollback.
        conn.execute(
            sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key}
        )


def _resolve_schema(conn: Connection, schema: str | None) -> str | None:
    if conn.dialect.name == "postgresql":
        current_schema = conn.execute(
            sa.text("SELECT current_schema()")
        ).scalar_one()
        if current_schema is None:
            raise SchemaBindingError(
                "current_schema() is unresolved; refusing to run unqualified DDL"
            )
        if schema is not None and schema != current_schema:
            raise SchemaBindingError(
                f"requested schema {schema!r} does not match current_schema() "
                f"{current_schema!r}; unqualified DDL would target the wrong schema"
            )
        return current_schema

    if conn.dialect.name == "sqlite":
        if schema is not None:
            raise SchemaBindingError(
                f"explicit schema {schema!r} is not supported on SQLite; "
                "unqualified DDL targets the connection's default schema"
            )
        return None

    return schema


def _relation_names(conn: Connection, schema: str | None) -> set[str]:
    inspector = sa.inspect(conn)
    names = set(inspector.get_table_names(schema=schema))

    try:
        names.update(inspector.get_view_names(schema=schema))
    except NotImplementedError:
        pass

    if conn.dialect.name == "postgresql":
        for method_name in ("get_materialized_view_names", "get_sequence_names"):
            getter = getattr(inspector, method_name, None)
            if getter is not None:
                names.update(getter(schema=schema))

    if conn.dialect.name == "sqlite":
        names = {
            name for name in names if not name.startswith(_SQLITE_INTERNAL_PREFIX)
        }

    return names


def _require_empty_schema(conn: Connection, schema: str | None) -> None:
    resolved_schema = _resolve_schema(conn, schema)
    relations = _relation_names(conn, resolved_schema)

    managed = sorted(relations & MANAGED_TABLES)
    if managed:
        raise ManagedSchemaError(
            f"schema {resolved_schema!r} is already managed "
            f"(found: {', '.join(managed)})"
        )

    if conn.dialect.name == "postgresql":
        has_other_objects = conn.scalar(sa.text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = :schema
                UNION ALL
                SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = :schema AND t.typisdefined
            )
        """), {"schema": resolved_schema})
        if has_other_objects:
            raise UnmanagedSchemaError(f"schema {resolved_schema!r} contains PostgreSQL objects")

    if relations:
        preview = ", ".join(sorted(relations)[:5])
        raise UnmanagedSchemaError(
            f"schema {resolved_schema!r} is not empty (found: {preview})"
        )


def _write_completion_mark(
    conn: Connection, project_key: str, schema: str | None
) -> None:
    mark = sa.Table(
        COMPLETION_TABLE,
        sa.MetaData(),
        sa.Column("project_key", sa.String(255), primary_key=True),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=schema,
    )
    mark.create(conn, checkfirst=False)
    conn.execute(mark.insert().values(project_key=project_key))
