"""add episode schema columns

Revision ID: 20260310_add_episode_schema_columns
Revises: 1c42debcfabc
Create Date: 2026-03-10

This migration adds missing schema columns for episode service features:
1. Add consolidated_into to agent_episodes (for episode consolidation)
2. Add canvas_context to episode_segments (already exists in DB, skip if present)
3. Add episode_id to canvas_audit with FK to agent_episodes (already exists in DB, skip if present)
4. Add supervision fields to agent_episodes (supervisor_rating, intervention_types, supervision_feedback)

Note: Some columns may already exist from previous migrations.
We use try/except blocks to handle idempotent operations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite


# revision identifiers, used by Alembic.
revision: str = '20260310_add_episode_schema_columns'
down_revision: Union[str, Sequence[str], None] = '1c42debcfabc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add missing episode service columns."""

    # Step 1: Add consolidated_into to agent_episodes
    # This allows episodes to be consolidated into parent episodes
    with op.batch_alter_table('agent_episodes', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'consolidated_into',
                sa.String(255),
                nullable=True,
                comment='Parent episode ID if this episode was consolidated'
            )
        )

    # Step 2: Add canvas_context to episode_segments (if not exists)
    # This column was added in migration 20260218_add_canvas, but we check to be safe
    try:
        # Check if column exists by attempting to add it
        with op.batch_alter_table('episode_segments', schema=None, copy_from=op.get_bind()) as batch_op:
            # This will fail if column already exists, which we catch
            batch_op.add_column(
                sa.Column(
                    'canvas_context',
                    sa.JSON(),
                    nullable=True,
                    comment='Canvas presentation context (canvas_type, presentation_summary, critical_data_points, visual_elements)'
                )
            )
    except Exception:
        # Column already exists, skip
        pass

    # Step 3: Add episode_id to canvas_audit (if not exists)
    # This column was added in migration canvas_feedback_ep_integration, but we check to be safe
    try:
        with op.batch_alter_table('canvas_audit', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    'episode_id',
                    sa.String(255),
                    nullable=True,
                    comment='Link to agent episode for episodic memory context'
                )
            )
    except Exception:
        # Column already exists, skip
        pass

    # Step 4: Add supervision fields to agent_episodes
    with op.batch_alter_table('agent_episodes', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'supervisor_rating',
                sa.Integer(),
                nullable=True,
                comment='Supervisor rating 1-5 for this episode'
            )
        )
        batch_op.add_column(
            sa.Column(
                'intervention_types',
                sa.JSON(),
                nullable=True,
                comment='List of intervention types (human_correction, guidance, termination)'
            )
        )
        batch_op.add_column(
            sa.Column(
                'supervision_feedback',
                sa.Text(),
                nullable=True,
                comment='Detailed feedback from supervisor'
            )
        )

    # Step 5: Create indexes for foreign keys
    # Index for agent_episodes.consolidated_into
    try:
        op.create_index(
            'ix_agent_episodes_consolidated_into',
            'agent_episodes',
            ['consolidated_into'],
            unique=False
        )
    except Exception:
        # Index might already exist
        pass

    # Index for canvas_audit.episode_id (if not exists)
    try:
        op.create_index(
            'ix_canvas_audit_episode_id_agent_episodes',
            'canvas_audit',
            ['episode_id'],
            unique=False
        )
    except Exception:
        # Index might already exist
        pass


def downgrade() -> None:
    """Downgrade schema - remove added columns and indexes."""

    # Drop indexes
    try:
        op.drop_index('ix_canvas_audit_episode_id_agent_episodes', table_name='canvas_audit')
    except Exception:
        pass

    try:
        op.drop_index('ix_agent_episodes_consolidated_into', table_name='agent_episodes')
    except Exception:
        pass

    # Remove supervision fields from agent_episodes
    with op.batch_alter_table('agent_episodes', schema=None) as batch_op:
        batch_op.drop_column('supervision_feedback')
        batch_op.drop_column('intervention_types')
        batch_op.drop_column('supervisor_rating')

    # Remove episode_id from canvas_audit (if it exists)
    try:
        with op.batch_alter_table('canvas_audit', schema=None) as batch_op:
            batch_op.drop_column('episode_id')
    except Exception:
        pass

    # Remove canvas_context from episode_segments (if it exists)
    try:
        with op.batch_alter_table('episode_segments', schema=None) as batch_op:
            batch_op.drop_column('canvas_context')
    except Exception:
        pass

    # Remove consolidated_into from agent_episodes
    with op.batch_alter_table('agent_episodes', schema=None) as batch_op:
        batch_op.drop_column('consolidated_into')
