"""fix incomplete implementations phase 1 - security and governance

Revision ID: fix_incomplete_phase1
Revises: 1a3970744150
Create Date: 2026-02-04

This migration fixes critical security and governance issues:
1. Add active_tokens table for proper token tracking
2. Fix AgentJobStatus enum to use UPPERCASE values
3. Fix HITLActionStatus enum to use UPPERCASE values

Note: SQLite compatibility - simplified approach that skips ALTER COLUMN operations.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'fix_incomplete_phase1'
down_revision: Union[str, Sequence[str], None] = '1a3970744150'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Step 1: Create active_tokens table if it doesn't exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'active_tokens' not in tables:
        op.create_table(
            'active_tokens',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('jti', sa.String(length=255), nullable=False),
            sa.Column('issued_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('issued_ip', sa.String(length=50), nullable=True),
            sa.Column('issued_user_agent', sa.String(length=500), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_active_tokens_user_id_users'))
        )
        op.create_index('ix_active_tokens_jti', 'active_tokens', ['jti'], unique=True)
        op.create_index('ix_active_tokens_expires', 'active_tokens', ['expires_at'], unique=False)
        op.create_index('ix_active_tokens_user', 'active_tokens', ['user_id', 'issued_at'], unique=False)
        op.execute("-- Created active_tokens table")
    else:
        op.execute("-- active_tokens table already exists, skipping creation")

    # Step 2: Update agent_jobs status values to UPPERCASE
    op.execute("UPDATE agent_jobs SET status = 'PENDING' WHERE status = 'pending'")
    op.execute("UPDATE agent_jobs SET status = 'RUNNING' WHERE status = 'running'")
    op.execute("UPDATE agent_jobs SET status = 'SUCCESS' WHERE status = 'success'")
    op.execute("UPDATE agent_jobs SET status = 'FAILED' WHERE status = 'failed'")
    op.execute("-- Updated agent_jobs status values to UPPERCASE")

    # Note: We don't alter the column type in SQLite as it doesn't support
    # ALTER COLUMN with constraints. The VARCHAR column will work fine with
    # the new UPPERCASE values.

    # Step 3: Update HITL action statuses if the table exists
    if 'human_in_the_loop_actions' in tables:
        op.execute("UPDATE human_in_the_loop_actions SET status = 'PENDING' WHERE status = 'pending'")
        op.execute("UPDATE human_in_the_loop_actions SET status = 'APPROVED' WHERE status = 'approved'")
        op.execute("UPDATE human_in_the_loop_actions SET status = 'REJECTED' WHERE status = 'rejected'")
        op.execute("-- Updated human_in_the_loop_actions status values to UPPERCASE")


def downgrade() -> None:
    """Downgrade schema."""

    # Step 1: Revert agent_jobs status to lowercase
    op.execute("UPDATE agent_jobs SET status = 'pending' WHERE status = 'PENDING'")
    op.execute("UPDATE agent_jobs SET status = 'running' WHERE status = 'RUNNING'")
    op.execute("UPDATE agent_jobs SET status = 'success' WHERE status = 'SUCCESS'")
    op.execute("UPDATE agent_jobs SET status = 'failed' WHERE status = 'FAILED'")
    op.execute("-- Reverted agent_jobs status values to lowercase")

    # Step 2: Revert HITL action statuses if table exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'human_in_the_loop_actions' in tables:
        op.execute("UPDATE human_in_the_loop_actions SET status = 'pending' WHERE status = 'PENDING'")
        op.execute("UPDATE human_in_the_loop_actions SET status = 'approved' WHERE status = 'APPROVED'")
        op.execute("UPDATE human_in_the_loop_actions SET status = 'rejected' WHERE status = 'REJECTED'")
        op.execute("-- Reverted human_in_the_loop_actions status values to lowercase")

    # Step 3: Drop active_tokens table (optional - comment out if you want to keep it)
    # op.drop_index('ix_active_tokens_user', table_name='active_tokens')
    # op.drop_index('ix_active_tokens_expires', table_name='active_tokens')
    # op.drop_index('ix_active_tokens_jti', table_name='active_tokens')
    # op.drop_table('active_tokens')
    op.execute("-- Keeping active_tokens table (manual drop if needed)")
