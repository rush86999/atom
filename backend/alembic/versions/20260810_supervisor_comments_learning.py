"""add supervisor_comments edit/resolve columns

Revision ID: 20260810_supervisor_comments_learning
Revises: 20260810_supervisor_performance_learning
Create Date: 2026-08-10

Restores ``is_edited`` / ``intervention_reference`` / ``resolved_at`` onto
``supervisor_comments`` (the two-way-learning migration 20260208 created them;
the Hive-port rewrite dropped them while ``feedback_service.update_comment``
still sets ``is_edited``/``resolved_at`` — every edit crashed with
AttributeError). See tests/test_covpush_w24_twoway_stack.py.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260810_supervisor_comments_learning"
down_revision: Union[str, Sequence[str], None] = "20260810_supervisor_performance_learning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ADDED = [
    sa.Column("is_edited", sa.Boolean(), server_default="0"),
    sa.Column("intervention_reference", sa.JSON(), nullable=True),
    sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "supervisor_comments" not in inspector.get_table_names():
        print("    [skip] supervisor_comments table missing")
        return
    existing = {c["name"] for c in inspector.get_columns("supervisor_comments")}
    missing = [c for c in ADDED if c.name not in existing]
    if not missing:
        print("    [skip] supervisor_comments already has edit/resolve columns")
        return
    with op.batch_alter_table("supervisor_comments") as batch_op:
        for col in missing:
            batch_op.add_column(col)
    print(f"    [ok] added {len(missing)} columns to supervisor_comments")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {c["name"] for c in inspector.get_columns("supervisor_comments")}
    with op.batch_alter_table("supervisor_comments") as batch_op:
        for col in ADDED:
            if col.name in existing:
                batch_op.drop_column(col.name)
