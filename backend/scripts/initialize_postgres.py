"""Explicit fresh PostgreSQL initializer for Atom.

Creates model metadata on an empty, UTF-8 PostgreSQL schema, applies the two
historical PostgreSQL FTS operations, validates the generated tsvector
columns/GIN indexes, and stamps every head from the release graph.  All work
runs on the caller-owned connection opened by
``core.postgres_fresh_bootstrap.initialize_fresh_database``.

This path is initialization-only.  It refuses non-PostgreSQL and non-UTF8
servers, and the bootstrap helper refuses occupied or managed schemas.  Full
general migration parity (upgrading existing databases and replaying every
historical revision through Alembic) remains an explicit open item; this path
is create_all plus the two PostgreSQL FTS parity steps only.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALEMBIC_DIR = Path(__file__).resolve().parents[1] / "alembic"

# Base table -> generated tsvector GIN index.
FTS_INDEXES: dict[str, str] = {
    "agent_reasoning_steps": "ix_agent_reasoning_steps_search",
    "ingested_documents": "ix_ingested_documents_search",
    "knowledge_documents": "ix_knowledge_documents_search",
}

# PostgreSQL branches of 20260624_reasoning_fts and 20260808_documents_fts.
FTS_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE agent_reasoning_steps "
    "ADD COLUMN IF NOT EXISTS search_vector tsvector "
    "GENERATED ALWAYS AS "
    "(to_tsvector('english', coalesce(thought,'') || ' ' || coalesce(observation,''))) STORED",
    "CREATE INDEX IF NOT EXISTS ix_agent_reasoning_steps_search "
    "ON agent_reasoning_steps USING gin(search_vector)",
    "ALTER TABLE ingested_documents "
    "ADD COLUMN IF NOT EXISTS search_vector tsvector "
    "GENERATED ALWAYS AS "
    "(to_tsvector('english', coalesce(file_name,'') || ' ' || coalesce(content_preview,''))) STORED",
    "CREATE INDEX IF NOT EXISTS ix_ingested_documents_search "
    "ON ingested_documents USING gin(search_vector)",
    "ALTER TABLE knowledge_documents "
    "ADD COLUMN IF NOT EXISTS search_vector tsvector "
    "GENERATED ALWAYS AS "
    "(to_tsvector('english', coalesce(title,'') || ' ' || coalesce(content,''))) STORED",
    "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_search "
    "ON knowledge_documents USING gin(search_vector)",
)

_FTS_CATALOG_SQL = """
SELECT c.relname,
       a.attgenerated,
       format_type(a.atttypid, a.atttypmod),
       i.relname,
       am.amname,
       ix.indisvalid,
       ix.indisready,
       ix.indnkeyatts,
       ix.indkey[0] = a.attnum,
       ix.indpred IS NULL
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
JOIN pg_attribute AS a
  ON a.attrelid = c.oid
 AND a.attname = 'search_vector'
 AND NOT a.attisdropped
LEFT JOIN pg_index AS ix
  ON ix.indrelid = c.oid
 AND ix.indkey[0] = a.attnum
LEFT JOIN pg_class AS i ON i.oid = ix.indexrelid
LEFT JOIN pg_am AS am ON am.oid = i.relam
WHERE n.nspname = current_schema()
  AND c.relname IN (
      'agent_reasoning_steps',
      'ingested_documents',
      'knowledge_documents'
  )
"""


class InitializationRefused(RuntimeError):
    """A preflight, release-graph, or schema validation check refused setup."""


@dataclass(frozen=True)
class Adapters:
    """External Atom pieces, injectable so tests need no database."""

    engine: Any
    metadata: Any
    scripts: Any
    initialize: Callable[..., None]
    stamp_heads: Callable[[Any, Any, Sequence[str]], None]


def load_adapters() -> Adapters:
    """Load Atom's engine/metadata/registrations and the release graph."""

    # Import for normal model registration and the PostgreSQL version-table
    # width hook.  The hook is registered by import before any stamping.
    import core.models_registration  # noqa: F401
    import core.alembic_version_table  # noqa: F401
    from alembic.script import ScriptDirectory
    from core.database import Base, engine
    from core.postgres_fresh_bootstrap import initialize_fresh_database

    return Adapters(
        engine=engine,
        metadata=Base.metadata,
        scripts=ScriptDirectory(str(ALEMBIC_DIR)),
        initialize=initialize_fresh_database,
        stamp_heads=record_heads,
    )


def preflight(engine: Any) -> None:
    """Refuse unsupported dialects before any connection or DDL."""

    if engine.dialect.name != "postgresql":
        raise InitializationRefused(
            "fresh initialization requires PostgreSQL, "
            f"not {engine.dialect.name!r}"
        )


def validate_encoding(conn: Any) -> None:
    """Require UTF8 on the caller-owned provisioning connection."""

    encoding = conn.exec_driver_sql("SHOW server_encoding").scalar_one()
    if encoding != "UTF8":
        raise InitializationRefused(
            f"database server_encoding is {encoding!r}; expected 'UTF8'"
        )


def resolve_heads(scripts: Any) -> list[str]:
    """Return every exact head in the release graph, or refuse an empty graph."""

    heads = sorted(scripts.get_heads())
    if not heads:
        raise InitializationRefused("release graph has no migration heads")
    known = {revision.revision for revision in scripts.walk_revisions()}
    missing = [head for head in heads if head not in known]
    if missing:
        raise InitializationRefused(
            "release graph heads are not revisable: " + ", ".join(missing)
        )
    return heads


def validate_metadata(metadata: Any) -> None:
    """Require the FTS base tables to be present in normal model metadata."""

    names = {name.rsplit(".", 1)[-1] for name in metadata.tables}
    missing = sorted(set(FTS_INDEXES) - names)
    if missing:
        raise InitializationRefused(
            "model metadata is missing FTS tables: " + ", ".join(missing)
        )


def apply_fts(conn: Any) -> None:
    """Apply the historical PostgreSQL FTS operations on the caller's connection."""

    for statement in FTS_STATEMENTS:
        conn.exec_driver_sql(statement)


def validate_fts(conn: Any) -> None:
    """Validate all three generated tsvector columns and their GIN indexes."""

    found: dict[str, list[tuple[Any, ...]]] = {}
    for row in conn.exec_driver_sql(_FTS_CATALOG_SQL).all():
        table, generated, coltype, index, method, *details = row
        if table in FTS_INDEXES and index:
            found.setdefault(table, []).append(
                (generated, coltype, index, method, *details)
            )

    problems: list[str] = []
    for table, expected_index in FTS_INDEXES.items():
        matches = [
            row for row in found.get(table, ()) if row[2] == expected_index
        ]
        if not matches:
            problems.append(f"{table}.{expected_index} is missing")
            continue
        (
            generated,
            coltype,
            _,
            method,
            valid,
            ready,
            key_count,
            key_matches,
            no_predicate,
        ) = matches[0]
        if generated != "s":
            problems.append(f"{table}.search_vector is not a stored generated column")
        if coltype != "tsvector":
            problems.append(f"{table}.search_vector is {coltype}, not tsvector")
        if method != "gin":
            problems.append(f"{expected_index} uses {method}, not gin")
        if valid is not True:
            problems.append(f"{expected_index} is not valid")
        if ready is not True:
            problems.append(f"{expected_index} is not ready")
        if key_count != 1 or key_matches is not True:
            problems.append(
                f"{expected_index} does not have exactly one search_vector key"
            )
        if no_predicate is not True:
            problems.append(f"{expected_index} has a predicate")

    if problems:
        raise InitializationRefused("; ".join(problems))


def record_heads(conn: Any, scripts: Any, heads: Sequence[str]) -> None:
    """Stamp all heads on the caller's connection; never commit independently."""

    from alembic.migration import MigrationContext

    context = MigrationContext.configure(conn)
    context.stamp(scripts, "heads")
    actual = sorted(context.get_current_heads())
    if actual != sorted(heads):
        raise InitializationRefused(
            f"recorded heads {actual!r} do not match release heads {sorted(heads)!r}"
        )


def run(
    adapters: Adapters,
    *,
    schema: str | None = None,
    out: Callable[[str], None] = print,
) -> int:
    """Perform one explicit fresh initialization through the bootstrap helper."""

    preflight(adapters.engine)
    heads = resolve_heads(adapters.scripts)
    validate_metadata(adapters.metadata)

    def create_metadata(conn: Any) -> None:
        validate_encoding(conn)
        adapters.metadata.create_all(conn)

    def verify_extra(conn: Any) -> None:
        apply_fts(conn)
        validate_fts(conn)

    def record_expected_heads(conn: Any) -> None:
        adapters.stamp_heads(conn, adapters.scripts, heads)

    adapters.initialize(
        adapters.engine,
        create_metadata=create_metadata,
        verify_extra=verify_extra,
        record_expected_heads=record_expected_heads,
        schema=schema,
    )
    out(f"initialized fresh PostgreSQL schema with heads: {', '.join(heads)}")
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    adapters: Adapters | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Initialize an empty, UTF-8 PostgreSQL schema exactly once."
    )
    parser.add_argument(
        "--schema",
        help="explicit schema; must match PostgreSQL current_schema()",
    )
    args = parser.parse_args(argv)

    try:
        return run(adapters or load_adapters(), schema=args.schema)
    except RuntimeError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
