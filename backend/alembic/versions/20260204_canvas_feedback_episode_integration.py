"""canvas_feedback_episode_integration

Revision ID: canvas_feedback_ep_integration
Revises: fix_incomplete_phase1
Create Date: 2026-02-04

This migration adds canvas and feedback integration to episodic memory:
1. Add canvas_ids, canvas_action_count, feedback_ids, aggregate_feedback_score to episodes
2. Add episode_id backlink to canvas_audit
3. Add episode_id backlink to agent_feedback
4. Create composite index for canvas queries

Note: SQLite compatibility - all new columns are nullable or have defaults.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

revision: str = 'canvas_feedback_ep_integration'
down_revision: Union[str, Sequence[str], None] = 'fix_incomplete_phase1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Step 1: Add Episode fields for canvas and feedback linkage
    # Using batch_alter_table for SQLite compatibility
    with op.batch_alter_table('episodes', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('canvas_ids', sa.JSON(), nullable=True)
        )
        batch_op.add_column(
            sa.Column('canvas_action_count', sa.Integer(), nullable=True, server_default='0')
        )
        batch_op.add_column(
            sa.Column('feedback_ids', sa.JSON(), nullable=True)
        )
        batch_op.add_column(
            sa.Column('aggregate_feedback_score', sa.Float(), nullable=True)
        )

    # Step 2: Add CanvasAudit backlink (episode_id)
    with op.batch_alter_table('canvas_audit', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('episode_id', sa.String(), nullable=True)
        )

    # Step 3: Add AgentFeedback backlink (episode_id)
    with op.batch_alter_table('agent_feedback', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('episode_id', sa.String(), nullable=True)
        )

    # Step 4: Create indexes for efficient querying
    # Note: SQLite doesn't support composite indexes with ALTER TABLE,
    # so we create them separately

    # Index for canvas_audit.episode_id
    try:
        op.create_index(
            'ix_canvas_audit_episode_id',
            'canvas_audit',
            ['episode_id'],
            unique=False
        )
    except Exception as e:
        # Index might already exist or table structure differs
        print(f"Warning: Could not create ix_canvas_audit_episode_id: {e}")

    # Index for agent_feedback.episode_id
    try:
        op.create_index(
            'ix_agent_feedback_episode_id',
            'agent_feedback',
            ['episode_id'],
            unique=False
        )
    except Exception as e:
        print(f"Warning: Could not create ix_agent_feedback_episode_id: {e}")

    # Composite index for episodes (agent_id, canvas_action_count)
    # This requires creating a new table in SQLite
    try:
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        tables = inspector.get_table_names()

        # Check if index already exists
        existing_indexes = inspector.get_indexes('episodes')
        index_names = [idx['name'] for idx in existing_indexes]

        if 'ix_episodes_agent_canvas' not in index_names:
            # For SQLite, we need to create the index directly
            conn.execute(sa.text(
                "CREATE INDEX ix_episodes_agent_canvas ON episodes (agent_id, canvas_action_count)"
            ))
    except Exception as e:
        print(f"Warning: Could not create composite index ix_episodes_agent_canvas: {e}")


def downgrade() -> None:
    """Downgrade schema - remove added columns and indexes."""

    # Drop indexes
    try:
        op.drop_index('ix_episodes_agent_canvas', table_name='episodes')
    except Exception:
        pass  # Index might not exist

    try:
        op.drop_index('ix_agent_feedback_episode_id', table_name='agent_feedback')
    except Exception:
        pass  # Index might not exist

    try:
        op.drop_index('ix_canvas_audit_episode_id', table_name='canvas_audit')
    except Exception:
        pass  # Index might not exist

    # Remove AgentFeedback episode_id column
    with op.batch_alter_table('agent_feedback', schema=None) as batch_op:
        batch_op.drop_column('episode_id')

    # Remove CanvasAudit episode_id column
    with op.batch_alter_table('canvas_audit', schema=None) as batch_op:
        batch_op.drop_column('episode_id')

    # Remove Episode fields
    with op.batch_alter_table('episodes', schema=None) as batch_op:
        batch_op.drop_column('aggregate_feedback_score')
        batch_op.drop_column('feedback_ids')
        batch_op.drop_column('canvas_action_count')
        batch_op.drop_column('canvas_ids')
