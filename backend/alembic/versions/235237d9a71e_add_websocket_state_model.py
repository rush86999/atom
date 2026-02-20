"""add websocket state model

Revision ID: 235237d9a71e
Revises: b55b0f499509
Create Date: 2026-02-19 19:02:45.917428

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '235237d9a71e'
down_revision: Union[str, Sequence[str], None] = 'b55b0f499509'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'websocket_state',
        sa.Column('id', sa.Integer(), primary_key=True, default=1),
        sa.Column('connected', sa.Boolean(), nullable=False, default=False, server_default='0'),
        sa.Column('last_connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('disconnect_reason', sa.Text(), nullable=True),
        sa.Column('reconnect_attempts', sa.Integer(), nullable=False, default=0, server_default='0'),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, default=0, server_default='0'),
        sa.Column('fallback_to_polling', sa.Boolean(), nullable=False, default=False, server_default='0'),
        sa.Column('fallback_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_ws_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Index('ix_websocket_state_connected', 'connected')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('websocket_state')
