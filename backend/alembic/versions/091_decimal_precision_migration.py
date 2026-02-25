"""decimal_precision_migration

Revision ID: 091_decimal_precision
Revises: b78e9c2f1a3d
Create Date: 2026-02-25

Convert Float columns to Numeric(19, 4) for all monetary values.
This ensures database precision matches Python Decimal arithmetic.

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite

# revision identifiers, used by Alembic.
revision = '091_decimal_precision'
down_revision = 'b78e9c2f1a3d'
branch_labels = None
depends_on = None


def upgrade():
    """Convert Float to Numeric(19, 4) for monetary columns"""

    # Transaction.amount (nullable)
    op.alter_column(
        'accounting_transactions',
        'amount',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=19, scale=4),
        nullable=True,
        existing_nullable=True
    )

    # JournalEntry.amount (non-nullable)
    op.alter_column(
        'accounting_journal_entries',
        'amount',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=19, scale=4),
        nullable=False,
        existing_nullable=False
    )

    # Bill.amount (non-nullable)
    op.alter_column(
        'accounting_bills',
        'amount',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=19, scale=4),
        nullable=False,
        existing_nullable=False
    )

    # Invoice.amount (non-nullable)
    op.alter_column(
        'accounting_invoices',
        'amount',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=19, scale=4),
        nullable=False,
        existing_nullable=False
    )

    # Budget.amount (non-nullable)
    op.alter_column(
        'accounting_budgets',
        'amount',
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=19, scale=4),
        nullable=False,
        existing_nullable=False
    )


def downgrade():
    """Revert to Float (not recommended - loses precision guarantees)"""

    op.alter_column(
        'accounting_budgets',
        'amount',
        existing_type=sa.Numeric(precision=19, scale=4),
        type_=sa.Float(),
        nullable=False,
        existing_nullable=False
    )

    op.alter_column(
        'accounting_invoices',
        'amount',
        existing_type=sa.Numeric(precision=19, scale=4),
        type_=sa.Float(),
        nullable=False,
        existing_nullable=False
    )

    op.alter_column(
        'accounting_bills',
        'amount',
        existing_type=sa.Numeric(precision=19, scale=4),
        type_=sa.Float(),
        nullable=False,
        existing_nullable=False
    )

    op.alter_column(
        'accounting_journal_entries',
        'amount',
        existing_type=sa.Numeric(precision=19, scale=4),
        type_=sa.Float(),
        nullable=False,
        existing_nullable=False
    )

    op.alter_column(
        'accounting_transactions',
        'amount',
        existing_type=sa.Numeric(precision=19, scale=4),
        type_=sa.Float(),
        nullable=True,
        existing_nullable=True
    )
