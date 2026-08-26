"""Round 82 — reasoning-step model provenance (requested + resolved).

SQLite-safe guarded batch migration per repo canonical pattern
(alembic/versions/20260624_add_turn_facts.py): column-existence checks +
batch_alter_table, because dev DBs are hybrid (create_all schema with lagging
alembic bookkeeping) and SQLite has no native ALTER COLUMN.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_reasoning_model_provenance"
down_revision: Union[str, Sequence[str], None] = "20260826_domain_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    binder = op.get_bind()
    insp = sa.inspect(binder)
    try:
        return column in {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False


def _table_exists(table: str) -> bool:
    binder = op.get_bind()
    insp = sa.inspect(binder)
    try:
        return table in insp.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    if not _table_exists("agent_reasoning_steps"):
        return
    with op.batch_alter_table("agent_reasoning_steps") as batch:
        if not _column_exists("agent_reasoning_steps", "requested_model"):
            batch.add_column(
                sa.Column("requested_model", sa.String(length=120), nullable=True)
            )
        if not _column_exists("agent_reasoning_steps", "resolved_model"):
            batch.add_column(
                sa.Column("resolved_model", sa.String(length=160), nullable=True)
            )


def downgrade() -> None:
    if not _table_exists("agent_reasoning_steps"):
        return
    with op.batch_alter_table("agent_reasoning_steps") as batch:
        if _column_exists("agent_reasoning_steps", "resolved_model"):
            batch.drop_column("agent_reasoning_steps", "resolved_model")
        if _column_exists("agent_reasoning_steps", "requested_model"):
            batch.drop_column("agent_reasoning_steps", "requested_model")
