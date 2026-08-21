"""Fleet routing validation — audit + automation action tables.

2026-08-21: the fleet-routing master switch flipped to ON (shadow) so eligible
TASK intents get governed recruitment computed + audited on every execute().
This migration adds the persistence for that validation pipeline:

- ``fleet_routing_audit`` — one row per fleet-eligible decision (recruitment
  snapshot + outcome-join columns filled when the meta-agent execution
  finalizes). Calibration-eligible once ``success`` is populated.
- ``fleet_router_automation_actions`` — consent-gated automation actions
  (approval queue + audit trail); the latest applied/revoked row drives
  ``resolved_fleet_enforce()`` (env kill-switch always wins).

SQLite-safe per repo convention: guarded creation + additive outcome columns
(hybrid dev DBs get schema via ``create_all``; alembic bookkeeping lags).
Mirrors ``20260811_add_stage_router_audit.py``.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = "20260821_fleet_routing_audit"
down_revision: Union[str, Sequence[str], None] = "20260821_ingested_docs_role"
branch_labels = None
depends_on = None


def _table_exists(conn, name: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"
            ),
            {"n": name},
        ).fetchone()
    )


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def _ensure_column(conn, table: str, column: str, col_type) -> None:
    """Additively apply a column via batch_alter_table (SQLite-safe)."""
    if not _table_exists(conn, table) or _column_exists(conn, table, column):
        return
    with op.batch_alter_table(table) as batch_op:
        batch_op.add_column(sa.Column(column, col_type, nullable=True))


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "fleet_routing_audit"):
        op.create_table(
            "fleet_routing_audit",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("tenant_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=True),
            sa.Column("agent_id", sa.String(), nullable=True),
            sa.Column("execution_id", sa.String(), nullable=True),
            sa.Column("workload_key", sa.String(length=32), nullable=False),
            sa.Column("request_text", sa.String(length=200), nullable=True),
            sa.Column("chain_id", sa.String(), nullable=True),
            sa.Column("specialists_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("roster_json", sa.JSON(), nullable=True),
            sa.Column("recruitment_succeeded", sa.Boolean(), nullable=True),
            sa.Column("enforced", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("decision_source", sa.String(length=24), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("success", sa.Boolean(), nullable=True),
            sa.Column("actual_latency_ms", sa.Float(), nullable=True),
            sa.Column("actual_model", sa.String(), nullable=True),
            sa.Column("actual_provider", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_fleet_audit_ws_created", "fleet_routing_audit", ["workspace_id", "created_at"])
        op.create_index("ix_fleet_audit_workload_created", "fleet_routing_audit", ["workload_key", "created_at"])
        op.create_index("ix_fleet_audit_execution", "fleet_routing_audit", ["execution_id"])
    else:
        # Hybrid dev DB: schema already via create_all — additively apply the
        # outcome-join columns only.
        for col_name, col_type in (
            ("success", sa.Boolean()),
            ("actual_latency_ms", sa.Float()),
            ("actual_model", sa.String()),
            ("actual_provider", sa.String()),
        ):
            _ensure_column(conn, "fleet_routing_audit", col_name, col_type)

    if not _table_exists(conn, "fleet_router_automation_actions"):
        op.create_table(
            "fleet_router_automation_actions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("workload_key", sa.String(length=32), nullable=False, server_default="__global__"),
            sa.Column("verdict", sa.String(length=16), nullable=False),
            sa.Column("mode", sa.String(length=16), nullable=False),
            sa.Column("state", sa.String(length=16), nullable=False, server_default="approval"),
            sa.Column("stats_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_fleet_router_auto_created", "fleet_router_automation_actions", ["workload_key", "created_at"])


def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, "fleet_router_automation_actions"):
        op.drop_table("fleet_router_automation_actions")
    if _table_exists(conn, "fleet_routing_audit"):
        op.drop_table("fleet_routing_audit")
