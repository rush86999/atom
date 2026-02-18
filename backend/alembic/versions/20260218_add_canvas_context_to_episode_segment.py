"""add canvas_context to episode_segment

Revision ID: 20260218_add_canvas
Revises: b53c19d68ac1
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260218_add_canvas'
down_revision: Union[str, Sequence[str], None] = 'b53c19d68ac1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Add canvas_context column as JSONB (JSON type maps to JSONB in PostgreSQL)
    op.add_column(
        'episode_segments',
        sa.Column(
            'canvas_context',
            sa.JSON(),
            nullable=True,
            comment='Canvas presentation context for semantic understanding'
        )
    )

    # Create GIN index on canvas_context for efficient JSON queries
    # This enables: WHERE canvas_context->>'canvas_type' = 'orchestration'
    # Note: Skip GIN index for SQLite (not supported)
    try:
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_episode_segments_canvas_context
            ON episode_segments USING GIN (canvas_context)
        """)
    except Exception:
        # SQLite doesn't support GIN indexes, skip gracefully
        pass

    # Create index on canvas_type for common queries
    try:
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_episode_segments_canvas_type
            ON episode_segments ((canvas_context->>'canvas_type'))
            WHERE canvas_context IS NOT NULL
        """)
    except Exception:
        # SQLite doesn't support JSON indexing, skip gracefully
        pass


def downgrade() -> None:
    """Downgrade schema."""

    # Drop indexes first (PostgreSQL)
    try:
        op.execute("DROP INDEX IF EXISTS idx_episode_segments_canvas_type")
        op.execute("DROP INDEX IF EXISTS idx_episode_segments_canvas_context")
    except Exception:
        # Ignore errors for SQLite
        pass

    # Remove column
    op.drop_column('episode_segments', 'canvas_context')
