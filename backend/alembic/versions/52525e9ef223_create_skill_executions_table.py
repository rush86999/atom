"""Create skill_executions table

Revision ID: 52525e9ef223
Revises: 228dac07c492
Create Date: 2026-02-01 10:22:45.843814

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '52525e9ef223'
down_revision: Union[str, Sequence[str], None] = '228dac07c492'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create skill_executions table
    op.create_table(
        'skill_executions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('skill_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=True, server_default='pending'),
        sa.Column('input_params', sa.JSON(), nullable=True),
        sa.Column('output_result', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_seconds', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('cpu_count', sa.Integer(), nullable=True),
        sa.Column('memory_mb', sa.Integer(), nullable=True),
        sa.Column('compute_billed', sa.Boolean(), nullable=True, server_default='False'),
        sa.Column('machine_id', sa.String(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], name='fk_skill_executions_agent_id'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_skill_executions_workspace_id'),
        sa.PrimaryKeyConstraint('id', name='pk_skill_executions')
    )

    # Create indexes
    op.create_index('ix_skill_executions_agent_id', 'skill_executions', ['agent_id'], unique=False)
    op.create_index('ix_skill_executions_skill_id', 'skill_executions', ['skill_id'], unique=False)
    op.create_index('ix_skill_executions_workspace_id', 'skill_executions', ['workspace_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    try:
        op.drop_index('ix_skill_executions_workspace_id', table_name='skill_executions')
    except Exception:
        pass

    try:
        op.drop_index('ix_skill_executions_skill_id', table_name='skill_executions')
    except Exception:
        pass

    try:
        op.drop_index('ix_skill_executions_agent_id', table_name='skill_executions')
    except Exception:
        pass

    # Drop table
    op.drop_table('skill_executions')
