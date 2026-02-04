"""Add mobile workflow models

Revision ID: 61484a704b1b
Revises: 82b786c43d49
Create Date: 2026-02-01 16:49:18.659667

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '61484a704b1b'
down_revision: Union[str, Sequence[str], None] = '82b786c43d49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create workflow_execution_logs table
    op.create_table(
        'workflow_execution_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('execution_id', sa.String(), nullable=False),
        sa.Column('level', sa.String(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('step_id', sa.String(), nullable=True),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now'), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.execution_id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_execution_logs_execution', 'workflow_execution_logs', ['execution_id'])
    op.create_index('ix_workflow_execution_logs_timestamp', 'workflow_execution_logs', ['timestamp'])

    # Create workflow_step_executions table
    op.create_table(
        'workflow_step_executions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('execution_id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('step_id', sa.String(), nullable=False),
        sa.Column('step_name', sa.String(), nullable=False),
        sa.Column('step_type', sa.String(), nullable=False),
        sa.Column('sequence_order', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now'), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.execution_id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_step_executions_execution', 'workflow_step_executions', ['execution_id'])
    op.create_index('ix_workflow_step_executions_step', 'workflow_step_executions', ['step_id'])
    op.create_index('ix_workflow_step_executions_workflow_id', 'workflow_step_executions', ['workflow_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_workflow_step_executions_workflow_id', table_name='workflow_step_executions')
    op.drop_index('ix_workflow_step_executions_step', table_name='workflow_step_executions')
    op.drop_index('ix_workflow_step_executions_execution', table_name='workflow_step_executions')
    op.drop_table('workflow_step_executions')

    op.drop_index('ix_workflow_execution_logs_timestamp', table_name='workflow_execution_logs')
    op.drop_index('ix_workflow_execution_logs_execution', table_name='workflow_execution_logs')
    op.drop_table('workflow_execution_logs')
