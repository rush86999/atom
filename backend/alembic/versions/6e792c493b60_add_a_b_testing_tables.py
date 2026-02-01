"""Add A/B testing tables

Revision ID: 6e792c493b60
Revises: 52525e9ef223
Create Date: 2026-02-01 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e792c493b60'
down_revision: Union[str, Sequence[str], None] = '52525e9ef223'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create ab_tests table
    op.create_table(
        'ab_tests',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='draft'),
        sa.Column('test_type', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('traffic_percentage', sa.Float(), nullable=True, server_default='0.5'),
        sa.Column('variant_a_name', sa.String(), nullable=True, server_default='Control'),
        sa.Column('variant_b_name', sa.String(), nullable=True, server_default='Treatment'),
        sa.Column('variant_a_config', sa.JSON(), nullable=True),
        sa.Column('variant_b_config', sa.JSON(), nullable=True),
        sa.Column('primary_metric', sa.String(), nullable=False),
        sa.Column('secondary_metrics', sa.JSON(), nullable=True),
        sa.Column('min_sample_size', sa.Integer(), nullable=True, server_default='100'),
        sa.Column('confidence_level', sa.Float(), nullable=True, server_default='0.95'),
        sa.Column('statistical_significance_threshold', sa.Float(), nullable=True, server_default='0.05'),
        sa.Column('variant_a_metrics', sa.JSON(), nullable=True),
        sa.Column('variant_b_metrics', sa.JSON(), nullable=True),
        sa.Column('statistical_significance', sa.Float(), nullable=True),
        sa.Column('winner', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], name='fk_ab_tests_agent_id'),
        sa.PrimaryKeyConstraint('id', name='pk_ab_tests')
    )

    # Create indexes for ab_tests
    op.create_index('ix_ab_tests_agent_id', 'ab_tests', ['agent_id'], unique=False)
    op.create_index('ix_ab_tests_status', 'ab_tests', ['status'], unique=False)
    op.create_index('ix_ab_tests_created_at', 'ab_tests', ['created_at'], unique=False)

    # Create ab_test_participants table
    op.create_table(
        'ab_test_participants',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('test_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('assigned_variant', sa.String(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('metric_value', sa.Float(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['test_id'], ['ab_tests.id'], name='fk_ab_test_participants_test_id'),
        sa.PrimaryKeyConstraint('id', name='pk_ab_test_participants')
    )

    # Create indexes for ab_test_participants
    op.create_index('ix_ab_test_participants_test_id', 'ab_test_participants', ['test_id'], unique=False)
    op.create_index('ix_ab_test_participants_user_id', 'ab_test_participants', ['user_id'], unique=False)
    op.create_index('ix_ab_test_participants_session_id', 'ab_test_participants', ['session_id'], unique=False)
    op.create_index('ix_ab_test_participants_test_variant', 'ab_test_participants', ['test_id', 'assigned_variant'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop ab_test_participants indexes and table
    try:
        op.drop_index('ix_ab_test_participants_test_variant', table_name='ab_test_participants')
    except Exception:
        pass

    try:
        op.drop_index('ix_ab_test_participants_session_id', table_name='ab_test_participants')
    except Exception:
        pass

    try:
        op.drop_index('ix_ab_test_participants_user_id', table_name='ab_test_participants')
    except Exception:
        pass

    try:
        op.drop_index('ix_ab_test_participants_test_id', table_name='ab_test_participants')
    except Exception:
        pass

    op.drop_table('ab_test_participants')

    # Drop ab_tests indexes and table
    try:
        op.drop_index('ix_ab_tests_created_at', table_name='ab_tests')
    except Exception:
        pass

    try:
        op.drop_index('ix_ab_tests_status', table_name='ab_tests')
    except Exception:
        pass

    try:
        op.drop_index('ix_ab_tests_agent_id', table_name='ab_tests')
    except Exception:
        pass

    op.drop_table('ab_tests')
