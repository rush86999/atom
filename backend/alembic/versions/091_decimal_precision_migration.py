"""decimal_precision_migration

Revision ID: 091_decimal_precision
Revises: b78e9c2f1a3d
Create Date: 2026-02-25

Convert Float columns to Numeric(19, 4) for all monetary values.
This ensures database precision matches Python Decimal arithmetic.

SQLite note: SQLite does not support ALTER COLUMN type natively — the
original op.alter_column() calls raised OperationalError on Personal Edition
(SQLite default). Rewritten to use batch_alter_table (table-recreate under
the hood), with existence guards so the migration is a no-op if a table is
missing.

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '091_decimal_precision'
down_revision = 'b78e9c2f1a3d'
branch_labels = None
depends_on = None


# (table, column, nullable) — monetary columns converted to Numeric(19, 4)
_COLUMNS = [
    ("accounting_transactions", "amount", True),
    ("accounting_journal_entries", "amount", False),
    ("accounting_bills", "amount", False),
    ("accounting_invoices", "amount", False),
    ("accounting_budgets", "amount", False),
]


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table (across SQLite + Postgres)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if table_name not in inspector.get_table_names():
        return False
    cols = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in cols


def upgrade():
    """Convert Float to Numeric(19, 4) for monetary columns.

    Uses batch_alter_table for SQLite compatibility (ALTER COLUMN type
    is unsupported there). Guarded so missing tables/columns are skipped.
    """
    for table_name, column_name, nullable in _COLUMNS:
        if not _column_exists(table_name, column_name):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                column_name,
                existing_type=sa.Float(),
                type_=sa.Numeric(precision=19, scale=4),
                nullable=nullable,
                existing_nullable=nullable,
            )


def downgrade():
    """Revert to Float (not recommended - loses precision guarantees)."""
    for table_name, column_name, nullable in reversed(_COLUMNS):
        if not _column_exists(table_name, column_name):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                column_name,
                existing_type=sa.Numeric(precision=19, scale=4),
                type_=sa.Float(),
                nullable=nullable,
                existing_nullable=nullable,
            )
