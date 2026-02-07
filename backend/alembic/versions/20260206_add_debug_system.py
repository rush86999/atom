"""Add AI Debug System tables

Add comprehensive debug system with event collection, insight generation,
state snapshots, metrics tracking, and interactive debug sessions.

Revision ID: 20260206_add_debug_system
Revises: 20260205_menubar_integration
Create Date: 2026-02-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260206_add_debug_system'
down_revision = '95ee90a806a6'  # Current head as of 2026-02-06
branch_labels = None
depends_on = None


def upgrade():
    """Create all debug system tables."""

    # ========================================================================
    # Debug Events Table
    # ========================================================================
    op.create_table(
        'debug_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('component_type', sa.String(length=50), nullable=False),
        sa.Column('component_id', sa.String(), nullable=True),
        sa.Column('correlation_id', sa.String(), nullable=False),
        sa.Column('parent_event_id', sa.String(), nullable=True),
        sa.Column('level', sa.String(length=20), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('event_metadata', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for debug_events
    op.create_index('ix_debug_event_timestamp', 'debug_events', ['timestamp'])
    op.create_index('ix_debug_event_component', 'debug_events', ['component_type', 'component_id', 'timestamp'])
    op.create_index('ix_debug_event_correlation', 'debug_events', ['correlation_id', 'timestamp'])
    op.create_index('ix_debug_event_type_level', 'debug_events', ['event_type', 'level', 'timestamp'])
    op.create_index('ix_debug_event_parent', 'debug_events', ['parent_event_id'])
    op.create_index('ix_debug_event_event_type', 'debug_events', ['event_type'])
    op.create_index('ix_debug_event_component_type', 'debug_events', ['component_type'])
    op.create_index('ix_debug_event_component_id', 'debug_events', ['component_id'])
    op.create_index('ix_debug_event_level', 'debug_events', ['level'])

    # ========================================================================
    # Debug Insights Table
    # ========================================================================
    op.create_table(
        'debug_insights',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('insight_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('summary', sa.String(length=500), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('suggestions', sa.JSON(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('scope', sa.String(length=50), nullable=False),
        sa.Column('affected_components', sa.JSON(), nullable=True),
        sa.Column('source_event_id', sa.String(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['source_event_id'], ['debug_events.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for debug_insights
    op.create_index('ix_debug_insight_generated', 'debug_insights', ['generated_at'])
    op.create_index('ix_debug_insight_type_severity', 'debug_insights', ['insight_type', 'severity', 'generated_at'])
    op.create_index('ix_debug_insight_scope', 'debug_insights', ['scope', 'generated_at'])
    op.create_index('ix_debug_insight_resolved', 'debug_insights', ['resolved', 'generated_at'])
    op.create_index('ix_debug_insight_expires', 'debug_insights', ['expires_at'])
    op.create_index('ix_debug_insight_insight_type', 'debug_insights', ['insight_type'])
    op.create_index('ix_debug_insight_severity', 'debug_insights', ['severity'])

    # ========================================================================
    # Debug State Snapshots Table
    # ========================================================================
    op.create_table(
        'debug_state_snapshots',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('component_type', sa.String(length=50), nullable=False),
        sa.Column('component_id', sa.String(), nullable=False),
        sa.Column('operation_id', sa.String(), nullable=False),
        sa.Column('checkpoint_name', sa.String(length=100), nullable=True),
        sa.Column('state_data', sa.JSON(), nullable=False),
        sa.Column('diff_from_previous', sa.JSON(), nullable=True),
        sa.Column('snapshot_type', sa.String(length=20), nullable=False),
        sa.Column('captured_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for debug_state_snapshots
    op.create_index('ix_debug_state_component', 'debug_state_snapshots', ['component_type', 'component_id', 'captured_at'])
    op.create_index('ix_debug_state_operation', 'debug_state_snapshots', ['operation_id', 'captured_at'])
    op.create_index('ix_debug_state_checkpoint', 'debug_state_snapshots', ['component_id', 'checkpoint_name', 'captured_at'])
    op.create_index('ix_debug_state_component_type', 'debug_state_snapshots', ['component_type'])
    op.create_index('ix_debug_state_component_id', 'debug_state_snapshots', ['component_id'])
    op.create_index('ix_debug_state_operation_id', 'debug_state_snapshots', ['operation_id'])

    # ========================================================================
    # Debug Metrics Table
    # ========================================================================
    op.create_table(
        'debug_metrics',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('component_type', sa.String(length=50), nullable=False),
        sa.Column('component_id', sa.String(), nullable=True),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=True),
        sa.Column('dimensions', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for debug_metrics
    op.create_index('ix_debug_metric_name_timestamp', 'debug_metrics', ['metric_name', 'timestamp'])
    op.create_index('ix_debug_metric_component', 'debug_metrics', ['component_type', 'component_id', 'timestamp'])
    op.create_index('ix_debug_metric_dimensions', 'debug_metrics', ['metric_name', 'timestamp'])
    op.create_index('ix_debug_metric_metric_name', 'debug_metrics', ['metric_name'])
    op.create_index('ix_debug_metric_component_type', 'debug_metrics', ['component_type'])
    op.create_index('ix_debug_metric_component_id', 'debug_metrics', ['component_id'])

    # ========================================================================
    # Debug Sessions Table
    # ========================================================================
    op.create_table(
        'debug_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.Column('scope', sa.JSON(), nullable=True),
        sa.Column('event_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('insight_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('query_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for debug_sessions
    op.create_index('ix_debug_session_created', 'debug_sessions', ['created_at'])
    op.create_index('ix_debug_session_active', 'debug_sessions', ['active', 'created_at'])
    op.create_index('ix_debug_session_resolved', 'debug_sessions', ['resolved', 'created_at'])


def downgrade():
    """Drop all debug system tables."""

    # Drop tables in reverse order of creation (due to foreign keys)
    op.drop_table('debug_sessions')
    op.drop_table('debug_metrics')
    op.drop_table('debug_state_snapshots')
    op.drop_table('debug_insights')
    op.drop_table('debug_events')
