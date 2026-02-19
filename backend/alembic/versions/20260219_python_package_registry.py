"""create package registry

Revision ID: 20260219_python_package
Revises: 20260218_add_canvas
Create Date: 2026-02-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260219_python_package'
down_revision: str | None = '20260218_add_canvas'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create package_registry table and add package_id foreign key to skill_executions."""

    # Create package_registry table
    op.create_table(
        'package_registry',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('package_type', sa.String(), server_default='python', nullable=False),
        sa.Column('min_maturity', sa.String(), server_default='INTERN', nullable=False),
        sa.Column('status', sa.String(), server_default='untrusted', nullable=False),
        sa.Column('ban_reason', sa.Text(), nullable=True),
        sa.Column('approved_by', sa.String(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], name='fk_package_approved_by')
    )

    # Create indexes for fast permission lookups
    op.create_index('ix_package_registry_name', 'package_registry', ['name'])
    op.create_index('ix_package_registry_version', 'package_registry', ['version'])
    op.create_index('ix_package_registry_package_type', 'package_registry', ['package_type'])
    op.create_index('ix_package_registry_status', 'package_registry', ['status'])

    # Add package_id column to skill_executions using batch mode for SQLite
    # Note: Foreign key constraint not added due to SQLite limitation
    # The relationship is maintained at the ORM level in models.py
    with op.batch_alter_table('skill_executions') as batch_op:
        batch_op.add_column(sa.Column('package_id', sa.String(), nullable=True))
        batch_op.create_index('ix_skill_executions_package_id', 'skill_executions', ['package_id'])
    op.create_table(
        'package_registry',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('package_type', sa.String(), server_default='python', nullable=False),
        sa.Column('min_maturity', sa.String(), server_default='INTERN', nullable=False),
        sa.Column('status', sa.String(), server_default='untrusted', nullable=False),
        sa.Column('ban_reason', sa.Text(), nullable=True),
        sa.Column('approved_by', sa.String(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], name='fk_package_approved_by')
    )

    # Create indexes for fast permission lookups
    op.create_index('ix_package_registry_name', 'package_registry', ['name'])
    op.create_index('ix_package_registry_version', 'package_registry', ['version'])
    op.create_index('ix_package_registry_package_type', 'package_registry', ['package_type'])
    op.create_index('ix_package_registry_status', 'package_registry', ['status'])

    # Add package_id foreign key to skill_executions
    op.add_column(
        'skill_executions',
        sa.Column('package_id', sa.String(), nullable=True)
    )
    op.create_foreign_key(
        'fk_skill_executions_package',
        'skill_executions', 'package_registry',
        ['package_id'], ['id']
    )
    op.create_index('ix_skill_executions_package_id', 'skill_executions', ['package_id'])


def downgrade() -> None:
    """Remove package_registry table and package_id column from skill_executions."""

    # Drop package_id column from skill_executions using batch mode
    with op.batch_alter_table('skill_executions') as batch_op:
        batch_op.drop_index('ix_skill_executions_package_id')
        batch_op.drop_column('package_id')

    # Drop package_registry table
    op.drop_index('ix_package_registry_status', table_name='package_registry')
    op.drop_index('ix_package_registry_package_type', table_name='package_registry')
    op.drop_index('ix_package_registry_version', table_name='package_registry')
    op.drop_index('ix_package_registry_name', table_name='package_registry')
    op.drop_table('package_registry')
