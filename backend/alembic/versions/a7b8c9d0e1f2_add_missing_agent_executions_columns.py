"""add missing agent_executions columns

Revision ID: a7b8c9d0e1f2
Revises: d4e5f6g7h8i9
Create Date: 2026-07-30

Adds columns that the AgentExecution model defines but no migration created:
tenant_id, chain_id, metadata_json, human_intervention_count. Without these,
fresh-DB deployments (alembic upgrade head without create_all) crash on every
agent-execution insert.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a7b8c9d0e1f2'
down_revision = 'd4e5f6g7h8i9'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = [c['name'] for c in inspector.get_columns('agent_executions')]

    if 'tenant_id' not in existing:
        op.add_column('agent_executions', sa.Column('tenant_id', sa.String(), nullable=True))
        op.create_index('ix_agent_executions_tenant_id', 'agent_executions', ['tenant_id'])

    if 'chain_id' not in existing:
        op.add_column('agent_executions', sa.Column('chain_id', sa.String(), nullable=True))
        op.create_index('ix_agent_executions_chain_id', 'agent_executions', ['chain_id'])

    if 'metadata_json' not in existing:
        op.add_column('agent_executions', sa.Column('metadata_json', sa.Text(), nullable=True))

    if 'human_intervention_count' not in existing:
        op.add_column('agent_executions',
                      sa.Column('human_intervention_count', sa.Integer(), server_default='0'))


def downgrade():
    op.drop_column('agent_executions', 'human_intervention_count')
    op.drop_column('agent_executions', 'metadata_json')
    op.drop_index('ix_agent_executions_chain_id', table_name='agent_executions')
    op.drop_column('agent_executions', 'chain_id')
    op.drop_index('ix_agent_executions_tenant_id', table_name='agent_executions')
    op.drop_column('agent_executions', 'tenant_id')
