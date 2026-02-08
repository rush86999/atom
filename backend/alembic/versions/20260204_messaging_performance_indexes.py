"""Add messaging performance indexes

Revision ID: 20260204_messaging_perf
Revises: 6463674076ea
Create Date: 2026-02-04

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260204_messaging_perf'
down_revision = '6463674076ea'
branch_labels = None
depends_on = None


def upgrade():
    """Add performance indexes for messaging tables."""

    # Proactive Messages indexes
    # Agent queries with status filter (most common pattern)
    op.create_index(
        'idx_proactive_messages_agent_status',
        'proactive_messages',
        ['agent_id', 'status'],
        unique=False
    )

    # Scheduled sends lookup
    op.create_index(
        'idx_proactive_messages_scheduled',
        'proactive_messages',
        ['scheduled_for'],
        unique=False
    )

    # Governance checks (maturity level)
    op.create_index(
        'idx_proactive_messages_maturity',
        'proactive_messages',
        ['agent_maturity_level'],
        unique=False
    )

    # Scheduled Messages indexes
    # Time-based queries for execution (most critical)
    op.create_index(
        'idx_scheduled_messages_next_run',
        'scheduled_messages',
        ['next_run', 'active'],
        unique=False
    )

    # Agent queries
    op.create_index(
        'idx_scheduled_messages_agent',
        'scheduled_messages',
        ['agent_id', 'active'],
        unique=False
    )

    # Schedule type queries
    op.create_index(
        'idx_scheduled_messages_type',
        'scheduled_messages',
        ['schedule_type', 'active'],
        unique=False
    )

    # Condition Monitors indexes
    # Active monitor lookup (most common)
    op.create_index(
        'idx_condition_monitors_active',
        'condition_monitors',
        ['status', 'condition_type'],
        unique=False
    )

    # Agent monitor lookup
    op.create_index(
        'idx_condition_monitors_agent',
        'condition_monitors',
        ['agent_id', 'status'],
        unique=False
    )

    # Check interval queries (for scheduler)
    op.create_index(
        'idx_condition_monitors_check',
        'condition_monitors',
        ['check_interval_seconds', 'status'],
        unique=False
    )

    # Condition Alerts indexes
    # Alert history queries
    op.create_index(
        'idx_condition_alerts_monitor',
        'condition_alerts',
        ['monitor_id', 'triggered_at'],
        unique=False
    )

    # Status queries
    op.create_index(
        'idx_condition_alerts_status',
        'condition_alerts',
        ['status', 'triggered_at'],
        unique=False
    )

    # Monitor + status combo (common dashboard query)
    op.create_index(
        'idx_condition_alerts_monitor_status',
        'condition_alerts',
        ['monitor_id', 'status'],
        unique=False
    )


def downgrade():
    """Remove messaging performance indexes."""

    # Proactive Messages
    op.drop_index('idx_proactive_messages_maturity', table_name='proactive_messages')
    op.drop_index('idx_proactive_messages_scheduled', table_name='proactive_messages')
    op.drop_index('idx_proactive_messages_agent_status', table_name='proactive_messages')

    # Scheduled Messages
    op.drop_index('idx_scheduled_messages_type', table_name='scheduled_messages')
    op.drop_index('idx_scheduled_messages_agent', table_name='scheduled_messages')
    op.drop_index('idx_scheduled_messages_next_run', table_name='scheduled_messages')

    # Condition Monitors
    op.drop_index('idx_condition_monitors_check', table_name='condition_monitors')
    op.drop_index('idx_condition_monitors_agent', table_name='condition_monitors')
    op.drop_index('idx_condition_monitors_active', table_name='condition_monitors')

    # Condition Alerts
    op.drop_index('idx_condition_alerts_monitor_status', table_name='condition_alerts')
    op.drop_index('idx_condition_alerts_status', table_name='condition_alerts')
    op.drop_index('idx_condition_alerts_monitor', table_name='condition_alerts')
