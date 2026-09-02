"""verify_panel_runs table (persistence for verification-panel verdicts)

Revision ID: 20260902_verify_panel_runs
Revises: 20260902_exchange_examples
Create Date: 2026-09-02 00:00:00.000000

One row per ``verify_reply()`` call (fire-and-forget write from
``core/verify_panel.py``). Verdicts were previously computed + logged only —
this gives the opt-in ATOM_VERIFY_PANEL shadow→enforce latch its evidence
base and gives dashboards a queryable record.

Guarded create pattern for the hybrid SQLite/PostgreSQL setup.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260902_verify_panel_runs"
down_revision: Union[str, Sequence[str], None] = "20260902_exchange_examples"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _index_exists(index_name: str, table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return index_name in (i["name"] for i in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("verify_panel_runs"):
        op.create_table(
            "verify_panel_runs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=True),
            sa.Column("agent_id", sa.String(), nullable=True),
            sa.Column("ran", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("grounded", sa.Boolean(), nullable=True),
            sa.Column("agreement", sa.Float(), nullable=True),
            sa.Column("level", sa.String(), nullable=True),
            sa.Column("samples", sa.Integer(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )

    if not _index_exists("idx_verify_panel_runs_created", "verify_panel_runs"):
        op.create_index(
            "idx_verify_panel_runs_created", "verify_panel_runs", ["created_at"]
        )
    for col in ("tenant_id", "agent_id"):
        ix_name = f"ix_verify_panel_runs_{col}"
        if not _index_exists(ix_name, "verify_panel_runs"):
            op.create_index(ix_name, "verify_panel_runs", [col])


def downgrade() -> None:
    if _table_exists("verify_panel_runs"):
        op.drop_table("verify_panel_runs")
