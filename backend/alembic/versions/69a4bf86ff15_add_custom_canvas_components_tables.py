"""Add custom canvas components tables

Revision ID: 69a4bf86ff15
Revises: bcfaa9f4c376
Create Date: 2026-02-01 11:35:43.890631

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '69a4bf86ff15'
down_revision: Union[str, Sequence[str], None] = 'bcfaa9f4c376'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create custom_components table
    op.create_table(
        'custom_components',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(), nullable=True, server_default='custom'),
        sa.Column('html_content', sa.Text(), nullable=True),
        sa.Column('css_content', sa.Text(), nullable=True),
        sa.Column('js_content', sa.Text(), nullable=True),
        sa.Column('props_schema', sa.JSON(), nullable=True),
        sa.Column('default_props', sa.JSON(), nullable=True),
        sa.Column('dependencies', sa.JSON(), nullable=True),
        sa.Column('requires_governance', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('min_maturity_level', sa.String(), nullable=True, server_default='AUTONOMOUS'),
        sa.Column('is_public', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('usage_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_version', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('parent_component_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['parent_component_id'], ['custom_components.id'], name='fk_custom_components_parent'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_custom_components_user_id'),
        sa.PrimaryKeyConstraint('id', name='pk_custom_components'),
        sa.UniqueConstraint('slug', name='uq_custom_components_slug')
    )

    # Create indexes for custom_components
    op.create_index('ix_custom_components_user_id', 'custom_components', ['user_id'], unique=False)
    op.create_index('ix_custom_components_slug', 'custom_components', ['slug'], unique=False)
    op.create_index('ix_custom_components_created_at', 'custom_components', ['created_at'], unique=False)
    op.create_index('ix_custom_components_workspace_user', 'custom_components', ['workspace_id', 'user_id'], unique=False)
    op.create_index('ix_custom_components_category', 'custom_components', ['category'], unique=False)
    op.create_index('ix_custom_components_is_active', 'custom_components', ['is_active'], unique=False)
    op.create_index('ix_custom_components_is_public', 'custom_components', ['is_public'], unique=False)

    # Create component_versions table
    op.create_table(
        'component_versions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('component_id', sa.String(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('html_content', sa.Text(), nullable=True),
        sa.Column('css_content', sa.Text(), nullable=True),
        sa.Column('js_content', sa.Text(), nullable=True),
        sa.Column('props_schema', sa.JSON(), nullable=True),
        sa.Column('default_props', sa.JSON(), nullable=True),
        sa.Column('dependencies', sa.JSON(), nullable=True),
        sa.Column('change_description', sa.Text(), nullable=True),
        sa.Column('changed_by', sa.String(), nullable=True),
        sa.Column('change_type', sa.String(), nullable=True, server_default='update'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], name='fk_component_versions_changed_by'),
        sa.ForeignKeyConstraint(['component_id'], ['custom_components.id'], name='fk_component_versions_component_id'),
        sa.PrimaryKeyConstraint('id', name='pk_component_versions'),
        sa.UniqueConstraint('component_id', 'version_number', name='uq_component_versions_component_version')
    )

    # Create indexes for component_versions
    op.create_index('ix_component_versions_component_id', 'component_versions', ['component_id'], unique=False)
    op.create_index('ix_component_versions_component_version', 'component_versions', ['component_id', 'version_number'], unique=False)
    op.create_index('ix_component_versions_created_at', 'component_versions', ['created_at'], unique=False)

    # Create component_usage table
    op.create_table(
        'component_usage',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('component_id', sa.String(), nullable=False),
        sa.Column('canvas_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('props_passed', sa.JSON(), nullable=True),
        sa.Column('rendering_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('governance_check_passed', sa.Boolean(), nullable=True),
        sa.Column('agent_maturity_level', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_registry.id'], name='fk_component_usage_agent_id'),
        sa.ForeignKeyConstraint(['component_id'], ['custom_components.id'], name='fk_component_usage_component_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_component_usage_user_id'),
        sa.PrimaryKeyConstraint('id', name='pk_component_usage')
    )

    # Create indexes for component_usage
    op.create_index('ix_component_usage_component_id', 'component_usage', ['component_id'], unique=False)
    op.create_index('ix_component_usage_canvas_id', 'component_usage', ['canvas_id'], unique=False)
    op.create_index('ix_component_usage_session_id', 'component_usage', ['session_id'], unique=False)
    op.create_index('ix_component_usage_user_id', 'component_usage', ['user_id'], unique=False)
    op.create_index('ix_component_usage_agent_id', 'component_usage', ['agent_id'], unique=False)
    op.create_index('ix_component_usage_created_at', 'component_usage', ['created_at'], unique=False)
    op.create_index('ix_component_usage_component_canvas', 'component_usage', ['component_id', 'canvas_id'], unique=False)
    op.create_index('ix_component_usage_session', 'component_usage', ['session_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop component_usage table and indexes
    try:
        op.drop_index('ix_component_usage_session', table_name='component_usage')
    except Exception:
        pass
    try:
        op.drop_index('ix_component_usage_component_canvas', table_name='component_usage')
    except Exception:
        pass
    try:
        op.drop_index('ix_component_usage_created_at', table_name='component_usage')
    except Exception:
        pass
    try:
        op.drop_index('ix_component_usage_agent_id', table_name='component_usage')
    except Exception:
        pass
    try:
        op.drop_index('ix_component_usage_user_id', table_name='component_usage')
    except Exception:
        pass
    try:
        op.drop_index('ix_component_usage_session_id', table_name='component_usage')
    except Exception:
        pass
    try:
        op.drop_index('ix_component_usage_canvas_id', table_name='component_usage')
    except Exception:
        pass
    try:
        op.drop_index('ix_component_usage_component_id', table_name='component_usage')
    except Exception:
        pass

    op.drop_table('component_usage')

    # Drop component_versions table and indexes
    try:
        op.drop_index('ix_component_versions_created_at', table_name='component_versions')
    except Exception:
        pass
    try:
        op.drop_index('ix_component_versions_component_version', table_name='component_versions')
    except Exception:
        pass
    try:
        op.drop_index('ix_component_versions_component_id', table_name='component_versions')
    except Exception:
        pass

    op.drop_table('component_versions')

    # Drop custom_components table and indexes
    try:
        op.drop_index('ix_custom_components_is_public', table_name='custom_components')
    except Exception:
        pass
    try:
        op.drop_index('ix_custom_components_is_active', table_name='custom_components')
    except Exception:
        pass
    try:
        op.drop_index('ix_custom_components_category', table_name='custom_components')
    except Exception:
        pass
    try:
        op.drop_index('ix_custom_components_workspace_user', table_name='custom_components')
    except Exception:
        pass
    try:
        op.drop_index('ix_custom_components_created_at', table_name='custom_components')
    except Exception:
        pass
    try:
        op.drop_index('ix_custom_components_slug', table_name='custom_components')
    except Exception:
        pass
    try:
        op.drop_index('ix_custom_components_user_id', table_name='custom_components')
    except Exception:
        pass

    op.drop_table('custom_components')
