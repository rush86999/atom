"""local model audio transcription capability + per-second audio rate

Adds the settings prerequisite for signed-in local transcription:
- ``supports_transcription``: explicit per-model opt-in, NOT NULL, default
  false. Existing rows are backfilled to disabled.
- ``audio_input_cost_per_second_usd``: nullable USD-per-second audio input
  price. NULL means unset; 0 is an explicit free rate.

Additive only: no existing columns or tables are touched, and fresh schemas
get the same columns through ``core.models.LocalModelCapabilities``.

Revision ID: 20261118_local_model_audio_capability
Revises: 20261102_goal_run_material_revision
Create Date: 2026-11-18 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261118_local_model_audio_capability"
down_revision: Union[str, Sequence[str], None] = "20261102_goal_run_material_revision"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "local_model_capabilities"


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def _require_table(table_name: str) -> None:
    """Fail loudly instead of stamping a revision whose schema never existed."""
    if not _table_exists(table_name):
        raise RuntimeError(
            f"Migration {revision} expected '{table_name}' to exist from its "
            "parent revision 20261102_goal_run_material_revision. Refusing to "
            "continue with an inconsistent migration chain or database; repair "
            "the schema state first."
        )


def upgrade() -> None:
    _require_table(_TABLE)

    with op.batch_alter_table(_TABLE) as batch:
        if not _column_exists(_TABLE, "supports_transcription"):
            batch.add_column(sa.Column(
                "supports_transcription",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ))
        else:
            print("    [skip] supports_transcription already exists")

        if not _column_exists(_TABLE, "audio_input_cost_per_second_usd"):
            batch.add_column(sa.Column(
                "audio_input_cost_per_second_usd",
                sa.Float(),
                nullable=True,
            ))
        else:
            print("    [skip] audio_input_cost_per_second_usd already exists")


def downgrade() -> None:
    _require_table(_TABLE)

    with op.batch_alter_table(_TABLE) as batch:
        if _column_exists(_TABLE, "audio_input_cost_per_second_usd"):
            batch.drop_column("audio_input_cost_per_second_usd")
        if _column_exists(_TABLE, "supports_transcription"):
            batch.drop_column("supports_transcription")
