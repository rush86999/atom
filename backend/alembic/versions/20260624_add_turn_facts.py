"""add turn_facts table

Revision ID: 20260624_turn_facts
Revises: 20260518_fix_acu_fk
Create Date: 2026-06-24 10:00:00.000000

Adds the `turn_facts` table backing the per-turn fact-extraction memory
provider (Hermes-style). Vectors live in LanceDB; this SQL row is the
source of truth for Tier-1 prompt injection. See
docs/architecture/CONTEXT_MEMORY.md.

No backfill — extraction starts fresh from the next agent turn.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260624_turn_facts"
down_revision: Union[str, Sequence[str], None] = "20260518_fix_acu_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("turn_facts"):
        print("    [skip] turn_facts already exists")
        return

    op.create_table(
        "turn_facts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("execution_id", sa.String(), nullable=True),
        sa.Column("reasoning_step_id", sa.String(), nullable=True),
        sa.Column("episode_id", sa.String(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("extraction_source", sa.String(length=32), nullable=False),
        sa.Column("fact_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("vector_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["agent_executions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["reasoning_step_id"],
            ["agent_reasoning_steps.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        # NOTE: no table-level UNIQUE constraint — see partial index below.
    )

    # Postgres-only partial unique index: at most one ACTIVE row per
    # (workspace, hash). Superseded rows retain the same hash for audit.
    # SQLite enforces this in the application layer (TurnFactExtractor._persist_one).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE UNIQUE INDEX uq_turn_facts_active_hash "
            "ON turn_facts (workspace_id, content_hash) "
            "WHERE status = 'active'"
        )

    op.create_index(
        op.f("ix_turn_facts_tenant_id"), "turn_facts", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_turn_facts_workspace_id"), "turn_facts", ["workspace_id"], unique=False
    )
    op.create_index(
        op.f("ix_turn_facts_user_id"), "turn_facts", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_turn_facts_episode_id"), "turn_facts", ["episode_id"], unique=False
    )
    op.create_index(
        op.f("ix_turn_facts_session_id"), "turn_facts", ["session_id"], unique=False
    )
    op.create_index(
        op.f("ix_turn_facts_content_hash"),
        "turn_facts",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_turn_facts_created_at"), "turn_facts", ["created_at"], unique=False
    )
    op.create_index(
        "ix_turn_facts_workspace_status_created",
        "turn_facts",
        ["workspace_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    if not _table_exists("turn_facts"):
        return
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS uq_turn_facts_active_hash")
    op.drop_index("ix_turn_facts_workspace_status_created", table_name="turn_facts")
    op.drop_index(op.f("ix_turn_facts_created_at"), table_name="turn_facts")
    op.drop_index(op.f("ix_turn_facts_content_hash"), table_name="turn_facts")
    op.drop_index(op.f("ix_turn_facts_session_id"), table_name="turn_facts")
    op.drop_index(op.f("ix_turn_facts_episode_id"), table_name="turn_facts")
    op.drop_index(op.f("ix_turn_facts_user_id"), table_name="turn_facts")
    op.drop_index(op.f("ix_turn_facts_workspace_id"), table_name="turn_facts")
    op.drop_index(op.f("ix_turn_facts_tenant_id"), table_name="turn_facts")
    op.drop_table("turn_facts")
