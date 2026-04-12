"""add notification preferences to users

Revision ID: add_notification_prefs
Revises: e186393951b0
Create Date: 2026-04-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

revision = 'add_notification_prefs'
down_revision = 'e186393951b0'
branch_labels = None
depends_on = None

def upgrade():
    # Use JSON type for SQLite compatibility (stored as TEXT, works like JSON)
    op.add_column('users', sa.Column('notification_preferences', sa.JSON(), nullable=True))

def downgrade():
    op.drop_column('users', 'notification_preferences')
