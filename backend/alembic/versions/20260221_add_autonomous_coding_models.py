"""add_autonomous_coding_models

Revision ID: 20260221_autonomous_coding
Revises: 20260220_smoke_test
Create Date: 2026-02-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260221_autonomous_coding'
down_revision = '20260220_smoke_test'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""

    # Create autonomous_workflows table
    op.create_table(
        'autonomous_workflows',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('feature_request', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('current_phase', sa.String(), nullable=True),
        sa.Column('completed_phases', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('requirements', sa.JSON(), nullable=True),
        sa.Column('user_stories', sa.JSON(), nullable=True),
        sa.Column('acceptance_criteria', sa.JSON(), nullable=True),
        sa.Column('implementation_plan', sa.JSON(), nullable=True),
        sa.Column('estimated_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('files_created', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('files_modified', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('test_results', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for autonomous_workflows
    op.create_index('ix_autonomous_workflows_workspace_id', 'autonomous_workflows', ['workspace_id'])
    op.create_index('ix_autonomous_workflows_status', 'autonomous_workflows', ['status'])

    # Create autonomous_checkpoints table
    op.create_table(
        'autonomous_checkpoints',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('checkpoint_sha', sa.String(), nullable=False),
        sa.Column('phase', sa.String(), nullable=True),
        sa.Column('agent_states', sa.JSON(), nullable=True),
        sa.Column('shared_state', sa.JSON(), nullable=True),
        sa.Column('artifacts', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('is_rollback_point', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['workflow_id'], ['autonomous_workflows.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for autonomous_checkpoints
    op.create_index('ix_autonomous_checkpoints_workflow_id', 'autonomous_checkpoints', ['workflow_id'])

    # Create agent_logs table
    op.create_table(
        'agent_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('phase', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=True),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['workflow_id'], ['autonomous_workflows.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for agent_logs
    op.create_index('ix_agent_logs_workflow_id', 'agent_logs', ['workflow_id'])
    op.create_index('ix_agent_logs_agent_id', 'agent_logs', ['agent_id'])
    op.create_index('ix_agent_logs_status', 'agent_logs', ['status'])
    op.create_index('ix_agent_logs_phase', 'agent_logs', ['phase'])
    op.create_index('ix_agent_logs_duration_seconds', 'agent_logs', ['duration_seconds'])


def downgrade() -> None:
    """Downgrade schema."""

    # Drop agent_logs table and indexes
    op.drop_index('ix_agent_logs_duration_seconds', 'agent_logs')
    op.drop_index('ix_agent_logs_phase', 'agent_logs')
    op.drop_index('ix_agent_logs_status', 'agent_logs')
    op.drop_index('ix_agent_logs_agent_id', 'agent_logs')
    op.drop_index('ix_agent_logs_workflow_id', 'agent_logs')
    op.drop_table('agent_logs')

    # Drop autonomous_checkpoints table and indexes
    op.drop_index('ix_autonomous_checkpoints_workflow_id', 'autonomous_checkpoints')
    op.drop_table('autonomous_checkpoints')

    # Drop autonomous_workflows table and indexes
    op.drop_index('ix_autonomous_workflows_status', 'autonomous_workflows')
    op.drop_index('ix_autonomous_workflows_workspace_id', 'autonomous_workflows')
    op.drop_table('autonomous_workflows')
