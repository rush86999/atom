"""add self_consistency_votes table

Revision ID: 20260629_self_consistency_votes
Revises: 20260628_match_confidence_gating
Create Date: 2026-06-29 00:00:00.000000

Adds the ``self_consistency_votes`` audit table backing the
self-consistency voter (Phase 2 hallucination mitigation, Workstream C).
Each row is one invocation of
``SelfConsistencyVoter.vote_with_consensus``. Parallel to ``browser_audit``
from the match-confidence layer.

Shadow mode by default (``ATOM_SELF_CONSISTENCY=false`` AND
``ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL=false``): rows are only written
when the voter actually runs, which is opt-in via the
``enable_self_consistency`` kwarg on ``LLMService.generate_structured``.
See ``docs/architecture/SELF_CONSISTENCY_VOTER.md``.

Uses the guarded ``_table_exists`` pattern from
``20260624_add_turn_facts.py`` — SQLite hybrid DB compatibility (the dev
DB has schema advanced via ``Base.metadata.create_all`` while alembic
bookkeeping lags; unguarded migrations fail with "table already exists").
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260629_self_consistency_votes"
# Linearizes on top of the Round 41 match-confidence migration.
down_revision: Union[str, Sequence[str], None] = "20260628_match_confidence_gating"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("self_consistency_votes"):
        print("    [skip] self_consistency_votes already exists")
        return

    op.create_table(
        "self_consistency_votes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("workspace_id", sa.String(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("agent_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("response_model_name", sa.String(length=200), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("valid_count", sa.Integer(), nullable=False),
        sa.Column("winner_count", sa.Integer(), nullable=False),
        sa.Column("distinct_hashes", sa.Integer(), nullable=False),
        sa.Column("agreement_ratio", sa.Float(), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("winner_hash", sa.String(length=64), nullable=True),
        sa.Column("temperatures", sa.JSON(), nullable=True),
        sa.Column("gated", sa.Boolean(), nullable=True),
        sa.Column("proposal_id", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agent_registry.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_self_consistency_votes_tenant_id"),
        "self_consistency_votes",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_self_consistency_votes_workspace_id"),
        "self_consistency_votes",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_self_consistency_votes_timestamp"),
        "self_consistency_votes",
        ["timestamp"],
        unique=False,
    )
    op.create_index(
        op.f("ix_self_consistency_votes_agent_id"),
        "self_consistency_votes",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_self_consistency_votes_user_id"),
        "self_consistency_votes",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_self_consistency_votes_session_id"),
        "self_consistency_votes",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_self_consistency_votes_prompt_hash"),
        "self_consistency_votes",
        ["prompt_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_self_consistency_votes_level"),
        "self_consistency_votes",
        ["level"],
        unique=False,
    )
    op.create_index(
        op.f("ix_self_consistency_votes_winner_hash"),
        "self_consistency_votes",
        ["winner_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_self_consistency_votes_gated"),
        "self_consistency_votes",
        ["gated"],
        unique=False,
    )
    op.create_index(
        op.f("ix_self_consistency_votes_proposal_id"),
        "self_consistency_votes",
        ["proposal_id"],
        unique=False,
    )
    op.create_index(
        "ix_scv_agent_created",
        "self_consistency_votes",
        ["agent_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_scv_level_created",
        "self_consistency_votes",
        ["level", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    if not _table_exists("self_consistency_votes"):
        return
    op.drop_index("ix_scv_level_created", table_name="self_consistency_votes")
    op.drop_index("ix_scv_agent_created", table_name="self_consistency_votes")
    op.drop_index(
        op.f("ix_self_consistency_votes_proposal_id"),
        table_name="self_consistency_votes",
    )
    op.drop_index(
        op.f("ix_self_consistency_votes_gated"),
        table_name="self_consistency_votes",
    )
    op.drop_index(
        op.f("ix_self_consistency_votes_winner_hash"),
        table_name="self_consistency_votes",
    )
    op.drop_index(
        op.f("ix_self_consistency_votes_level"),
        table_name="self_consistency_votes",
    )
    op.drop_index(
        op.f("ix_self_consistency_votes_prompt_hash"),
        table_name="self_consistency_votes",
    )
    op.drop_index(
        op.f("ix_self_consistency_votes_session_id"),
        table_name="self_consistency_votes",
    )
    op.drop_index(
        op.f("ix_self_consistency_votes_user_id"),
        table_name="self_consistency_votes",
    )
    op.drop_index(
        op.f("ix_self_consistency_votes_agent_id"),
        table_name="self_consistency_votes",
    )
    op.drop_index(
        op.f("ix_self_consistency_votes_timestamp"),
        table_name="self_consistency_votes",
    )
    op.drop_index(
        op.f("ix_self_consistency_votes_workspace_id"),
        table_name="self_consistency_votes",
    )
    op.drop_index(
        op.f("ix_self_consistency_votes_tenant_id"),
        table_name="self_consistency_votes",
    )
    op.drop_table("self_consistency_votes")
