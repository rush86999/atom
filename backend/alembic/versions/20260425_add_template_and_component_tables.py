"""add template and component version tables

Revision ID: 20260425_add_template_component_tables
Revises: add_notification_prefs
Create Date: 2026-04-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite, postgresql

# revision identifiers, used by Alembic.
revision = '20260425_add_template_component_tables'
down_revision = 'add_notification_prefs'
branch_labels = None
depends_on = None


def upgrade():
    # Create template_versions table
    op.create_table(
        'template_versions',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('template_id', sa.String(255), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('steps', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.Index('ix_template_versions_template_id', 'template_id')
    )
    
    # Create custom_components table
    op.create_table(
        'custom_components',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('component_type', sa.String(50), nullable=False),
        sa.Column('html_content', sa.Text(), nullable=True),
        sa.Column('css_content', sa.Text(), nullable=True),
        sa.Column('js_content', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_sanitized', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.Index('ix_custom_components_name', 'name')
    )
    
    # Create component_versions table
    op.create_table(
        'component_versions',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('component_id', sa.String(255), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('html_content', sa.Text(), nullable=True),
        sa.Column('css_content', sa.Text(), nullable=True),
        sa.Column('js_content', sa.Text(), nullable=True),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['component_id'], ['custom_components.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.Index('ix_component_versions_component_id', 'component_id')
    )
    
    # Create component_usage table
    op.create_table(
        'component_usage',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('component_id', sa.String(255), nullable=False),
        sa.Column('canvas_id', sa.String(255), nullable=False),
        sa.Column('execution_context', sa.JSON(), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['component_id'], ['custom_components.id'], ondelete='CASCADE'),
        sa.Index('ix_component_usage_component_id', 'component_id'),
        sa.Index('ix_component_usage_canvas_id', 'canvas_id')
    )


def downgrade():
    op.drop_table('component_usage')
    op.drop_table('component_versions')
    op.drop_table('custom_components')
    op.drop_table('template_versions')
