"""add fts5 index over agent_reasoning_steps

Revision ID: 20260624_reasoning_fts
Revises: 20260624_turn_facts
Create Date: 2026-06-24 16:00:00.000000

Adds an FTS5 virtual table over agent_reasoning_steps (thought + observation)
for fast lexical session search — the fallback when semantic recall misses
(exact-match queries: error strings, IDs, function names).

Hermes has SQLite FTS5 session search; Atom previously had semantic-only.
This complements (does not replace) LanceDB vector recall.

Postgres note: FTS5 is SQLite-only. On Postgres, the equivalent is a
tsvector GIN index — created by the same migration via dialect check.
The search helper degrades gracefully on both.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260624_reasoning_fts"
down_revision: Union[str, Sequence[str], None] = "20260624_turn_facts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        # FTS5 virtual table over the reasoning steps content.
        # external-content pattern: the FTS index references the base table by rowid
        # to avoid duplicating data. thought + observation are the searchable columns.
        if _table_exists("agent_reasoning_steps_fts"):
            print("    [skip] agent_reasoning_steps_fts already exists")
            return
        if not _table_exists("agent_reasoning_steps"):
            print("    [skip] agent_reasoning_steps base table not found")
            return
        op.execute(
            "CREATE VIRTUAL TABLE agent_reasoning_steps_fts USING fts5("
            "thought, observation, content='agent_reasoning_steps', content_rowid='rowid'"
            ")"
        )
        # Populate the index from existing rows
        op.execute(
            "INSERT INTO agent_reasoning_steps_fts(rowid, thought, observation) "
            "SELECT rowid, COALESCE(thought,''), COALESCE(observation,'') "
            "FROM agent_reasoning_steps"
        )
        # Triggers keep the index in sync on insert/update/delete
        op.execute(
            "CREATE TRIGGER agent_reasoning_steps_ai AFTER INSERT ON agent_reasoning_steps BEGIN "
            "INSERT INTO agent_reasoning_steps_fts(rowid, thought, observation) "
            "VALUES (new.rowid, COALESCE(new.thought,''), COALESCE(new.observation,'')); END"
        )
        op.execute(
            "CREATE TRIGGER agent_reasoning_steps_ad AFTER DELETE ON agent_reasoning_steps BEGIN "
            "INSERT INTO agent_reasoning_steps_fts(agent_reasoning_steps_fts, rowid, thought, observation) "
            "VALUES('delete', old.rowid, COALESCE(old.thought,''), COALESCE(old.observation,'')); END"
        )
        op.execute(
            "CREATE TRIGGER agent_reasoning_steps_au AFTER UPDATE ON agent_reasoning_steps BEGIN "
            "INSERT INTO agent_reasoning_steps_fts(agent_reasoning_steps_fts, rowid, thought, observation) "
            "VALUES('delete', old.rowid, COALESCE(old.thought,''), COALESCE(old.observation,'')); "
            "INSERT INTO agent_reasoning_steps_fts(rowid, thought, observation) "
            "VALUES (new.rowid, COALESCE(new.thought,''), COALESCE(new.observation,'')); END"
        )

    elif bind.dialect.name == "postgresql":
        # Postgres: tsvector + GIN index. Generated column keeps it in sync.
        if not _table_exists("agent_reasoning_steps"):
            return
        # Add a generated tsvector column + GIN index (idempotent)
        op.execute(
            "ALTER TABLE agent_reasoning_steps "
            "ADD COLUMN IF NOT EXISTS search_vector tsvector "
            "GENERATED ALWAYS AS "
            "(to_tsvector('english', coalesce(thought,'') || ' ' || coalesce(observation,''))) STORED"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_agent_reasoning_steps_search "
            "ON agent_reasoning_steps USING gin(search_vector)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS agent_reasoning_steps_au")
        op.execute("DROP TRIGGER IF EXISTS agent_reasoning_steps_ad")
        op.execute("DROP TRIGGER IF EXISTS agent_reasoning_steps_ai")
        op.execute("DROP TABLE IF EXISTS agent_reasoning_steps_fts")
    elif bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_agent_reasoning_steps_search")
        op.execute(
            "ALTER TABLE agent_reasoning_steps DROP COLUMN IF EXISTS search_vector"
        )
