"""add messaging feature parity tables

Revision ID: 6463674076ea
Revises: fix_incomplete_phase1
Create Date: 2026-02-04 10:33:14.660792

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6463674076ea'
down_revision: Union[str, Sequence[str], None] = 'fix_incomplete_phase1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create proactive_messages table
    op.create_table(
        'proactive_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('agent_name', sa.String(), nullable=False),
        sa.Column('agent_maturity_level', sa.String(), nullable=False),
        sa.Column('platform', sa.String(), nullable=False),
        sa.Column('recipient_id', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('send_now', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('approved_by', sa.String(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('governance_metadata', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('platform_message_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], name=op.f('fk_proactive_messages_agent_id')),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], name=op.f('fk_proactive_messages_approved_by')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_proactive_messages'))
    )
    op.create_index('ix_proactive_messages_agent_status', 'proactive_messages', ['agent_id', 'status'])
    op.create_index('ix_proactive_messages_platform_status', 'proactive_messages', ['platform', 'status'])
    op.create_index('ix_proactive_messages_scheduled', 'proactive_messages', ['scheduled_for', 'status'])
    op.create_index('ix_proactive_messages_created', 'proactive_messages', ['created_at'])
    op.create_index(op.f('ix_proactive_messages_agent_id'), 'proactive_messages', ['agent_id'])
    op.create_index(op.f('ix_proactive_messages_platform'), 'proactive_messages', ['platform'])
    op.create_index(op.f('ix_proactive_messages_recipient_id'), 'proactive_messages', ['recipient_id'])
    op.create_index(op.f('ix_proactive_messages_status'), 'proactive_messages', ['status'])
    op.create_index(op.f('ix_proactive_messages_approved_by'), 'proactive_messages', ['approved_by'])

    # Create scheduled_messages table
    op.create_table(
        'scheduled_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('agent_name', sa.String(), nullable=False),
        sa.Column('platform', sa.String(), nullable=False),
        sa.Column('recipient_id', sa.String(), nullable=False),
        sa.Column('template', sa.Text(), nullable=False),
        sa.Column('template_variables', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('schedule_type', sa.String(), nullable=False),
        sa.Column('cron_expression', sa.String(), nullable=True),
        sa.Column('natural_language_schedule', sa.String(), nullable=True),
        sa.Column('next_run', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_run', sa.DateTime(timezone=True), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_runs', sa.Integer(), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('timezone', sa.String(), nullable=False, server_default='UTC'),
        sa.Column('governance_metadata', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], name=op.f('fk_scheduled_messages_agent_id')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_scheduled_messages'))
    )
    op.create_index('ix_scheduled_messages_next_run', 'scheduled_messages', ['next_run', 'status'])
    op.create_index('ix_scheduled_messages_agent_status', 'scheduled_messages', ['agent_id', 'status'])
    op.create_index('ix_scheduled_messages_platform', 'scheduled_messages', ['platform', 'status'])
    op.create_index('ix_scheduled_messages_created', 'scheduled_messages', ['created_at'])
    op.create_index(op.f('ix_scheduled_messages_agent_id'), 'scheduled_messages', ['agent_id'])
    op.create_index(op.f('ix_scheduled_messages_recipient_id'), 'scheduled_messages', ['recipient_id'])
    op.create_index(op.f('ix_scheduled_messages_schedule_type'), 'scheduled_messages', ['schedule_type'])
    op.create_index(op.f('ix_scheduled_messages_status'), 'scheduled_messages', ['status'])

    # Create condition_monitors table
    op.create_table(
        'condition_monitors',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=False),
        sa.Column('agent_name', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('condition_type', sa.String(), nullable=False),
        sa.Column('threshold_config', sa.JSON(), nullable=False),
        sa.Column('composite_logic', sa.String(), nullable=True),
        sa.Column('composite_conditions', sa.JSON(), nullable=True),
        sa.Column('check_interval_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('platforms', sa.JSON(), nullable=False),
        sa.Column('alert_template', sa.Text(), nullable=True),
        sa.Column('throttle_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('last_alert_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('governance_metadata', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], name=op.f('fk_condition_monitors_agent_id')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_condition_monitors'))
    )
    op.create_index('ix_condition_monitors_agent_status', 'condition_monitors', ['agent_id', 'status'])
    op.create_index('ix_condition_monitors_type', 'condition_monitors', ['condition_type', 'status'])
    op.create_index('ix_condition_monitors_created', 'condition_monitors', ['created_at'])
    op.create_index(op.f('ix_condition_monitors_agent_id'), 'condition_monitors', ['agent_id'])
    op.create_index(op.f('ix_condition_monitors_condition_type'), 'condition_monitors', ['condition_type'])
    op.create_index(op.f('ix_condition_monitors_status'), 'condition_monitors', ['status'])

    # Create condition_alerts table
    op.create_table(
        'condition_alerts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('monitor_id', sa.String(), nullable=False),
        sa.Column('condition_value', sa.JSON(), nullable=False),
        sa.Column('threshold_value', sa.JSON(), nullable=False),
        sa.Column('alert_message', sa.Text(), nullable=False),
        sa.Column('platforms_sent', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('triggered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['monitor_id'], ['condition_monitors.id'], name=op.f('fk_condition_alerts_monitor_id')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_condition_alerts'))
    )
    op.create_index('ix_condition_alerts_monitor', 'condition_alerts', ['monitor_id', 'triggered_at'])
    op.create_index('ix_condition_alerts_status', 'condition_alerts', ['status'])
    op.create_index('ix_condition_alerts_triggered', 'condition_alerts', ['triggered_at'])
    op.create_index(op.f('ix_condition_alerts_monitor_id'), 'condition_alerts', ['monitor_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('condition_alerts')
    op.drop_table('condition_monitors')
    op.drop_table('scheduled_messages')
    op.drop_table('proactive_messages')
