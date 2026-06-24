"""Add hash chain fields to FinancialAudit

Revision ID: 3f3fbbfa4df5
Revises: 091_decimal_precision
Create Date: 2026-02-25 16:32:32.318538

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f3fbbfa4df5'
down_revision: Union[str, Sequence[str], None] = '091_decimal_precision'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in cols


def upgrade() -> None:
    """Upgrade schema."""
    # Guard: no-op if financial_audit doesn't exist (fresh Personal Edition DB
    # where the table is created lazily by Base.metadata.create_all at app start).
    if not _table_exists('financial_audit'):
        print("    [skip] financial_audit table not found — migration is a no-op")
        return

    # Add hash chain fields to financial_audit table
    # Note: SQLite requires a multi-step approach for adding NOT NULL columns with defaults

    # Step 1: Add columns as nullable (guard each — may already exist)
    if not _column_exists('financial_audit', 'sequence_number'):
        op.add_column('financial_audit', sa.Column('sequence_number', sa.Integer(), nullable=True))
    if not _column_exists('financial_audit', 'entry_hash'):
        op.add_column('financial_audit', sa.Column('entry_hash', sa.String(64), nullable=True))
    if not _column_exists('financial_audit', 'prev_hash'):
        op.add_column('financial_audit', sa.Column('prev_hash', sa.String(64), nullable=True))

    # Step 2: Populate sequence_number for existing records
    op.execute("""
        UPDATE financial_audit
        SET sequence_number = (
            SELECT COUNT(*)
            FROM financial_audit AS fa2
            WHERE fa2.account_id = financial_audit.account_id
              AND fa2.timestamp <= financial_audit.timestamp
        )
    """)

    # Step 3: Populate entry_hash for existing records (placeholder hash)
    op.execute("""
        UPDATE financial_audit
        SET entry_hash = lower(hex(randomblob(32)))
        WHERE entry_hash IS NULL
    """)

    # Step 4: Make columns NOT NULL
    # SQLite doesn't support ALTER COLUMN directly, so we need to recreate the table
    # For simplicity, we'll rely on application-level validation
    # Production databases (PostgreSQL) would use ALTER COLUMN ... SET NOT NULL

    # Step 5: Create indexes (guard — may already exist)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_indexes = {ix["name"] for ix in inspector.get_indexes('financial_audit')}
    if 'ix_financial_audit_sequence' not in existing_indexes:
        op.create_index('ix_financial_audit_sequence', 'financial_audit', ['account_id', 'sequence_number'])
    if 'ix_financial_audit_hash_chain' not in existing_indexes:
        op.create_index('ix_financial_audit_hash_chain', 'financial_audit', ['account_id', 'prev_hash'])


def downgrade() -> None:
    """Downgrade schema."""
    if not _table_exists('financial_audit'):
        return

    # Drop indexes (guard existence)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_indexes = {ix["name"] for ix in inspector.get_indexes('financial_audit')}
    if 'ix_financial_audit_hash_chain' in existing_indexes:
        op.drop_index('ix_financial_audit_hash_chain', table_name='financial_audit')
    if 'ix_financial_audit_sequence' in existing_indexes:
        op.drop_index('ix_financial_audit_sequence', table_name='financial_audit')

    # Drop columns (guard existence)
    if _column_exists('financial_audit', 'prev_hash'):
        op.drop_column('financial_audit', 'prev_hash')
    if _column_exists('financial_audit', 'entry_hash'):
        op.drop_column('financial_audit', 'entry_hash')
    if _column_exists('financial_audit', 'sequence_number'):
        op.drop_column('financial_audit', 'sequence_number')
