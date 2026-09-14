"""Agent marketplace × goal runs (docs/architecture/AGENT_MARKETPLACE_GOAL_RUNS.md):

agent_templates.verified_record — the platform-computed goal-run track
record (runs achieved/failed, steps executed, human interventions, maturity
at publish) that a sellable listing carries. Counts come from GoalRun rows
via AgentMarketplaceService.package_agent_for_sale; buyers' installs seed
evidence-honest confidence from it. Nullable JSON — plain ADD COLUMN,
sqlite-safe, and core.sqlite_schema_repair.ensure_sqlite_columns self-heals
drifted dev files.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260912_agent_verified_record"
down_revision = "20260909_goal_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_templates",
        sa.Column("verified_record", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_templates", "verified_record")
