"""merge divergent alembic heads

Revision ID: 20260807_merge_heads
Revises: 0e360bb1a3d3, 20260628_browser_audit_action_target, 20260721_add_field_guides, 20260805_mini_apps, 20260807b_episode_feedback_capabilities, a7b8c9d0e1f2
Create Date: 2026-08-07 03:00:00.000000

The revision graph had accumulated six heads (parallel feature branches never
merged), which makes ``alembic upgrade head`` fail on PostgreSQL deployments
("Multiple head revisions are present"). This merge revision joins them all
into a single linear head so ``upgrade head`` applies every pending migration.

No schema changes — upgrade/downgrade are intentional no-ops.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "20260807_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "0e360bb1a3d3",
    "20260628_browser_audit_action_target",
    "20260721_add_field_guides",
    "20260805_mini_apps",
    "20260807b_episode_feedback_capabilities",
    "a7b8c9d0e1f2",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.get_bind()  # noqa: B018  (no-op merge; binding is validated)


def downgrade() -> None:
    pass
