"""add run_sandboxes + sandbox_violations tables

Revision ID: 20260630_sandbox_tables
Revises: 20260629_self_consistency_votes
Create Date: 2026-06-30 00:00:00.000000

Adds the Execution Sandbox Layer tables (Round 43 / Phase A):

  * ``run_sandboxes`` — one row per ``AgentExecution``. Stores the
    ``SandboxPolicy`` issued at run start (immutable snapshot of the tier
    at issuance time).
  * ``sandbox_violations`` — one row per ``PolicyIssuer.check()`` call
    that produced RESTRICTED or BLOCKED. Parallel to ``browser_audit``
    and ``self_consistency_votes``.

Shadow mode by default (``ATOM_SANDBOX_ENABLED=false``,
``ATOM_SANDBOX_FORCE_ENFORCE=false``): rows are written whenever the
sandbox layer runs (which is opt-in via ``ATOM_SANDBOX_ENABLED=true``);
no calls are actually blocked until ``ATOM_SANDBOX_FORCE_ENFORCE=true``.

Uses the guarded ``_table_exists`` pattern from
``20260624_add_turn_facts.py`` and ``20260629_add_self_consistency_votes.py``
— SQLite hybrid DB compatibility (the dev DB has schema advanced via
``Base.metadata.create_all`` while alembic bookkeeping lags; unguarded
migrations fail with "table already exists").

See ``docs/architecture/SANDBOX_LAYER.md``.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260630_sandbox_tables"
# Chains on Round 42 self-consistency voter migration.
down_revision: Union[str, Sequence[str], None] = "20260629_self_consistency_votes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """Check if table exists (SQLite hybrid-DB compatibility)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # -----------------------------------------------------------------
    # run_sandboxes
    # -----------------------------------------------------------------
    if _table_exists("run_sandboxes"):
        print("    [skip] run_sandboxes already exists")
    else:
        op.create_table(
            "run_sandboxes",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("tenant_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=True),
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("agent_id", sa.String(), nullable=True),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("session_id", sa.String(), nullable=True),
            sa.Column("tier_at_issuance", sa.String(length=32), nullable=False),
            sa.Column(
                "issued_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.Column("fs_roots", sa.JSON(), nullable=True),
            sa.Column("fs_write_roots", sa.JSON(), nullable=True),
            sa.Column("tool_whitelist", sa.JSON(), nullable=True),
            sa.Column("egress_hosts", sa.JSON(), nullable=True),
            sa.Column("max_bytes_written", sa.Integer(), nullable=True),
            sa.Column("max_exec_seconds", sa.Integer(), nullable=True),
            sa.Column("max_tool_calls", sa.Integer(), nullable=True),
            sa.Column("max_cost_usd", sa.Float(), nullable=True),
            sa.Column("tripwire_actions", sa.JSON(), nullable=True),
            sa.Column("policy_version", sa.String(length=32), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["agent_id"], ["agent_registry.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        for col in (
            "tenant_id",
            "workspace_id",
            "run_id",
            "agent_id",
            "user_id",
            "session_id",
            "issued_at",
        ):
            op.create_index(
                op.f(f"ix_run_sandboxes_{col}"),
                "run_sandboxes",
                [col],
                unique=False,
            )
        op.create_index(
            "idx_rs_agent_issued",
            "run_sandboxes",
            ["agent_id", "issued_at"],
            unique=False,
        )

    # -----------------------------------------------------------------
    # sandbox_violations
    # -----------------------------------------------------------------
    if _table_exists("sandbox_violations"):
        print("    [skip] sandbox_violations already exists")
    else:
        op.create_table(
            "sandbox_violations",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("tenant_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=True),
            sa.Column(
                "timestamp",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.Column("agent_id", sa.String(), nullable=True),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("session_id", sa.String(), nullable=True),
            sa.Column("policy_id", sa.String(), nullable=True),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("phase", sa.String(length=4), nullable=False),
            sa.Column("decision", sa.String(length=16), nullable=False),
            sa.Column("tool_name", sa.String(length=200), nullable=False),
            sa.Column("violation_type", sa.String(length=64), nullable=True),
            sa.Column("violation_detail", sa.Text(), nullable=True),
            sa.Column("args_hash", sa.String(length=64), nullable=True),
            sa.Column("enforced", sa.Boolean(), nullable=True),
            sa.Column("killrun_triggered", sa.Boolean(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["agent_id"], ["agent_registry.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        for col in (
            "tenant_id",
            "workspace_id",
            "timestamp",
            "agent_id",
            "user_id",
            "session_id",
            "policy_id",
            "run_id",
            "phase",
            "decision",
            "tool_name",
            "violation_type",
            "args_hash",
            "enforced",
            "killrun_triggered",
        ):
            op.create_index(
                op.f(f"ix_sandbox_violations_{col}"),
                "sandbox_violations",
                [col],
                unique=False,
            )
        op.create_index(
            "idx_sv_phase_decision",
            "sandbox_violations",
            ["phase", "decision"],
            unique=False,
        )
        op.create_index(
            "idx_sv_run_timestamp",
            "sandbox_violations",
            ["run_id", "timestamp"],
            unique=False,
        )
        op.create_index(
            "idx_sv_agent_created",
            "sandbox_violations",
            ["agent_id", "created_at"],
            unique=False,
        )
        op.create_index(
            "idx_sv_violation_type_created",
            "sandbox_violations",
            ["violation_type", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    if _table_exists("sandbox_violations"):
        for idx_name in (
            "idx_sv_violation_type_created",
            "idx_sv_agent_created",
            "idx_sv_run_timestamp",
            "idx_sv_phase_decision",
        ):
            op.drop_index(idx_name, table_name="sandbox_violations")
        for col in (
            "killrun_triggered",
            "enforced",
            "args_hash",
            "violation_type",
            "tool_name",
            "decision",
            "phase",
            "run_id",
            "policy_id",
            "session_id",
            "user_id",
            "agent_id",
            "timestamp",
            "workspace_id",
            "tenant_id",
        ):
            op.drop_index(
                op.f(f"ix_sandbox_violations_{col}"),
                table_name="sandbox_violations",
            )
        op.drop_table("sandbox_violations")

    if _table_exists("run_sandboxes"):
        op.drop_index("idx_rs_agent_issued", table_name="run_sandboxes")
        for col in (
            "issued_at",
            "session_id",
            "user_id",
            "agent_id",
            "run_id",
            "workspace_id",
            "tenant_id",
        ):
            op.drop_index(
                op.f(f"ix_run_sandboxes_{col}"),
                table_name="run_sandboxes",
            )
        op.drop_table("run_sandboxes")
