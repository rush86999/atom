"""merge divergent alembic heads (mini_apps + field_guides + governance)

Revision ID: 20260805_merge_heads
Revises: 20260805_mini_apps, 20260721_add_field_guides, a7b8c9d0e1f2
Create Date: 2026-08-05 00:00:00.000000

The repo had three divergent heads (pre-existing, from separately-merged
features that were never consolidated):

  * ``20260805_mini_apps``       — mini-apps tables (the 20260805 chain head)
  * ``20260721_add_field_guides``— Field Guide persistence (packages_branch /
    gea_branch lineage)
  * ``a7b8c9d0e1f2``             — missing agent_executions columns

This merge is a no-op that consolidates them into a single head so
``alembic upgrade head`` works on a fresh database. Future migrations extend
from this merged head.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260805_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "20260805_mini_apps",
    "20260721_add_field_guides",
    "a7b8c9d0e1f2",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge heads — no schema changes."""
    pass


def downgrade() -> None:
    """Merge heads — no schema changes."""
    pass
