"""add_governance_and_workflow_parity

Revision ID: 3a1b2c3d4e5f
Revises: 226403220000
Create Date: 2026-03-29 22:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3a1b2c3d4e5f'
down_revision = '226403220000'
branch_labels = None
depends_on = None


def upgrade():
    # --- Users Table ---
    op.add_column('users', sa.Column('tenant_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_users_tenant_id'), 'users', ['tenant_id'], unique=False)

    # --- Agent Registry Table ---
    op.add_column('agent_registry', sa.Column('diversity_profile', sa.JSON(), nullable=True, server_default='{}'))

    # --- Workflow Executions Table ---
    op.add_column('workflow_executions', sa.Column('tenant_id', sa.String(), nullable=True))
    op.add_column('workflow_executions', sa.Column('parent_execution_id', sa.String(), nullable=True))
    op.add_column('workflow_executions', sa.Column('estimated_time_saved', sa.Integer(), nullable=True, server_default='60'))
    op.add_column('workflow_executions', sa.Column('business_value', sa.Integer(), nullable=True, server_default='10'))
    
    op.create_index(op.f('ix_workflow_executions_tenant_id'), 'workflow_executions', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_workflow_executions_parent_execution_id'), 'workflow_executions', ['parent_execution_id'], unique=False)

    # --- Workflow Snapshots Table ---
    op.create_table('workflow_snapshots',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=True),
        sa.Column('execution_id', sa.String(), nullable=False),
        sa.Column('step_id', sa.String(), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('context_snapshot', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.execution_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workflow_snapshots_execution_id'), 'workflow_snapshots', ['execution_id'], unique=False)
    op.create_index(op.f('ix_workflow_snapshots_tenant_id'), 'workflow_snapshots', ['tenant_id'], unique=False)


def downgrade():
    op.drop_table('workflow_snapshots')
    
    op.drop_index(op.f('ix_workflow_executions_parent_execution_id'), table_name='workflow_executions')
    op.drop_index(op.f('ix_workflow_executions_tenant_id'), table_name='workflow_executions')
    op.drop_column('workflow_executions', 'business_value')
    op.drop_column('workflow_executions', 'estimated_time_saved')
    op.drop_column('workflow_executions', 'parent_execution_id')
    op.drop_column('workflow_executions', 'tenant_id')
    
    op.drop_column('agent_registry', 'diversity_profile')
    
    op.drop_index(op.f('ix_users_tenant_id'), table_name='users')
    op.drop_column('users', 'tenant_id')
