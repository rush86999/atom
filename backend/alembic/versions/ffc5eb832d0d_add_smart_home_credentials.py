"""add smart home credentials

Revision ID: ffc5eb832d0d
Revises: aa093d5ca52c
Create Date: 2026-02-20 19:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ffc5eb832d0d'
down_revision = 'aa093d5ca52c'
branch_labels = None
depends_on = None


def upgrade():
    # ### HueBridge table
    op.create_table(
        'hue_bridges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('bridge_ip', sa.String(), nullable=False),
        sa.Column('bridge_id', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('api_key', sa.String(), nullable=False),
        sa.Column('last_connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hue_bridges_user_id'), 'hue_bridges', ['user_id'], unique=False)

    # ### HomeAssistantConnection table
    op.create_table(
        'home_assistant_connections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('last_connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_home_assistant_connections_user_id'), 'home_assistant_connections', ['user_id'], unique=False)


def downgrade():
    # ### Downgrade for HomeAssistantConnection
    op.drop_index(op.f('ix_home_assistant_connections_user_id'), table_name='home_assistant_connections')
    op.drop_table('home_assistant_connections')

    # ### Downgrade for HueBridge
    op.drop_index(op.f('ix_hue_bridges_user_id'), table_name='hue_bridges')
    op.drop_table('hue_bridges')
