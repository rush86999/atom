"""PostgreSQL Alembic version-table width for fresh bootstrap installs.

Alembic's default ``alembic_version.version_num`` is ``VARCHAR(32)``.
Current head identifiers exceed that (e.g.
``20260821_turn_facts_source_attribution`` is 38 characters), so the
installer's supported fresh path (``create_all`` + ``alembic stamp heads``)
fails on PostgreSQL with ``StringDataRightTruncation``.  The version-table
creation is transactional, so the table is normally rolled back.

This uses Alembic's supported ``DefaultImpl.version_table_impl`` hook (added
in Alembic 1.14) for the PostgreSQL dialect only.  It preserves the table
name, optional schema, column name, nullable=False and the default primary
key name, and delegates all other dialects to Alembic's normal implementation.

Fresh PostgreSQL databases get ``VARCHAR(255)``.  Existing databases whose
``alembic_version`` table is still ``VARCHAR(32)`` are intentionally not
altered by this module: read-only commands like ``alembic current`` remain
read-only, and stamping a long head against an existing narrow table still
fails loudly.  Widening an existing managed table is a separate, explicit
operator action (``ALTER TABLE alembic_version ALTER COLUMN version_num
TYPE VARCHAR(255)`` after review/backup), not an automatic migration here.
"""
from __future__ import annotations

from typing import Any, Optional

from alembic.ddl.postgresql import PostgresqlImpl
from sqlalchemy import String, Table

VERSION_NUM_WIDTH = 255


class WideVersionTablePostgresqlImpl(PostgresqlImpl):
    """PostgreSQL impl using a version column wide enough for current heads."""

    __dialect__ = "postgresql"

    def version_table_impl(
        self,
        *,
        version_table: str,
        version_table_schema: Optional[str],
        version_table_pk: bool,
        **kw: Any,
    ) -> Table:
        table = super().version_table_impl(
            version_table=version_table,
            version_table_schema=version_table_schema,
            version_table_pk=version_table_pk,
            **kw,
        )
        table.c.version_num.type = String(VERSION_NUM_WIDTH)
        return table
