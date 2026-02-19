"""add_gea_agent_evolution_traces

Group-Evolving Agents (GEA) — Experience Archive table.
Stores evolutionary traces for cross-agent experience sharing.
Paper: UC Santa Barbara, Feb 2026.

Revision ID: a3f2d1e0b9c8
Revises: 9ddf19c49160
Create Date: 2026-02-19 06:54:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a3f2d1e0b9c8'
down_revision: Union[str, Sequence[str], None] = '9ddf19c49160'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create agent_evolution_traces table (GEA Experience Archive)."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("agent_evolution_traces"):
        op.create_table(
            "agent_evolution_traces",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "agent_id",
                sa.String(),
                sa.ForeignKey("agent_registry.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            # Lineage
            sa.Column("generation", sa.Integer(), server_default="1", nullable=False),
            sa.Column("parent_agent_ids", sa.JSON(), server_default="[]"),
            sa.Column("ancestor_count", sa.Integer(), server_default="0"),
            # Selection scores (Performance-Novelty Algorithm)
            sa.Column("performance_score", sa.Float(), server_default="0.0"),
            sa.Column("novelty_score", sa.Float(), server_default="0.0"),
            sa.Column("combined_selection_score", sa.Float(), server_default="0.0"),
            # Experience Archive fields
            sa.Column("tool_use_log", sa.JSON(), server_default="[]"),
            sa.Column("task_log", sa.Text(), nullable=True),
            sa.Column("predicted_task_patch", sa.Text(), nullable=True),
            sa.Column("model_patch", sa.Text(), nullable=True),
            sa.Column("evolving_requirements", sa.Text(), nullable=True),
            # Benchmark outcome
            sa.Column("benchmark_passed", sa.Boolean(), nullable=True),
            sa.Column("benchmark_name", sa.String(), nullable=True),
            sa.Column("benchmark_score", sa.Float(), nullable=True),
            # Quality gate
            sa.Column("is_high_quality", sa.Boolean(), server_default="true", nullable=False),
            sa.Column("quality_filter_reason", sa.String(), nullable=True),
            # Timestamps
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                index=True,
            ),
        )
        print("Created table: agent_evolution_traces")
    else:
        print("Table already exists: agent_evolution_traces")

    # Composite indexes for pool queries
    try:
        op.create_index(
            "idx_aet_tenant_agent",
            "agent_evolution_traces",
            ["tenant_id", "agent_id"],
        )
        op.create_index(
            "idx_aet_tenant_generation",
            "agent_evolution_traces",
            ["tenant_id", "generation"],
        )
        op.create_index(
            "idx_aet_quality_score",
            "agent_evolution_traces",
            ["tenant_id", "is_high_quality", "performance_score"],
        )
    except Exception:
        pass  # Indexes may already exist


def downgrade() -> None:
    """Drop agent_evolution_traces table."""
    try:
        op.drop_index("idx_aet_quality_score", table_name="agent_evolution_traces")
        op.drop_index("idx_aet_tenant_generation", table_name="agent_evolution_traces")
        op.drop_index("idx_aet_tenant_agent", table_name="agent_evolution_traces")
    except Exception:
        pass
    op.drop_table("agent_evolution_traces")
