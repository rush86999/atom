"""Add immutability trigger to financial_audit table

Revision ID: add_audit_immutable_trigger
Revises: 20260225_chrono_constraints
Create Date: 2026-02-25

This migration adds PostgreSQL triggers to prevent UPDATE and DELETE
operations on financial_audit table, enforcing SOX immutability requirements.

For SQLite (development environment), application-level enforcement is used.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_audit_immutable_trigger'
down_revision = '20260225_chrono_constraints'
branch_labels = None
depends_on = None


def upgrade():
    """Create trigger function and triggers for immutability."""

    # Note: SQLite doesn't support triggers with exceptions in the same way.
    # For development/testing with SQLite, immutability is enforced at
    # the application level (audit_immutable_guard.py).
    # Production uses PostgreSQL with triggers.

    # Check if we're using PostgreSQL (not SQLite)
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'postgresql':
        # PostgreSQL function to prevent modifications
        op.execute("""
            CREATE OR REPLACE FUNCTION prevent_audit_modification()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'Cannot modify or delete financial audit entries (SOX immutability requirement). Audit ID: %, Action: %', OLD.id, TG_OP;
                RETURN NULL;
            END;
            $$ LANGUAGE plpgsql;
        """)

        # Create trigger for UPDATE
        op.execute("""
            CREATE TRIGGER financial_audit_immutable_update
            BEFORE UPDATE ON financial_audit
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_modification();
        """)

        # Create trigger for DELETE
        op.execute("""
            CREATE TRIGGER financial_audit_immutable_delete
            BEFORE DELETE ON financial_audit
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_modification();
        """)

    else:
        # For SQLite or other databases, application-level guard will handle it
        # See: backend/core/audit_immutable_guard.py
        pass


def downgrade():
    """Drop triggers and function."""

    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == 'postgresql':
        op.execute("DROP TRIGGER IF EXISTS financial_audit_immutable_update ON financial_audit;")
        op.execute("DROP TRIGGER IF EXISTS financial_audit_immutable_delete ON financial_audit;")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_modification();")
    else:
        # Nothing to downgrade for SQLite
        pass
