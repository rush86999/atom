"""GoalRun material_revision for reviewed-approval CAS.

A held decision is reviewed against a concrete plan/cursor/parameters/state
snapshot. Approval claims must be conditional on that exact material revision;
otherwise a plan changed after validation can execute under the old approval.
The revision is monotonic and is advanced by every writer of binding-material
fields. Diagnostic decision-log entries and display timestamps do not advance
it.
"""
from alembic import op
import sqlalchemy as sa


revision = "20261102_goal_run_material_revision"
down_revision = "20260912_agent_verified_record"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("goal_runs") as batch:
        batch.add_column(sa.Column(
            "material_revision", sa.Integer(), nullable=False,
            server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("goal_runs") as batch:
        batch.drop_column("material_revision")
