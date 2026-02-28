"""Add chronological integrity constraints

Revision ID: 20260225_chrono_constraints
Revises: 3f3fbbfa4df5
Create Date: 2026-02-25 21:30:00.000000

This migration adds SOX compliance (AUD-02) constraints to the FinancialAudit table.
It depends on the hash chain fields added in revision 3f3fbbfa4df5 (Phase 94-01).

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError


# revision identifiers, used by Alembic.
revision = '20260225_chrono_constraints'
down_revision = '3f3fbbfa4df5'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add chronological integrity constraints to FinancialAudit table.

    SOX compliance (AUD-02) requires:
    - sequence_number must be positive (> 0)
    - action_type must be valid enum (create, update, delete)
    - agent_maturity must be valid enum (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
    - entry_hash must be 64 characters (SHA-256 hex)

    Note: SQLite has limited CHECK constraint support compared to PostgreSQL.
    These constraints work in SQLite and will be fully enforced in PostgreSQL.
    """
    # Check if financial_audit table has the required columns
    # This makes the migration defensive against incomplete schema states
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('financial_audit')]

    # Only add constraints if columns exist (Plan 01 must have run)
    if 'sequence_number' in columns and 'entry_hash' in columns:
        # For SQLite, we use batch_alter_table which recreates the table
        # This is required because SQLite has limited ALTER TABLE support
        try:
            with op.batch_alter_table('financial_audit') as batch_op:
                # Constraint: sequence_number > 0
                batch_op.create_check_constraint(
                    'ck_financial_audit_sequence_positive',
                    'sequence_number > 0'
                )

                # Constraint: action_type in ('create', 'update', 'delete')
                batch_op.create_check_constraint(
                    'ck_financial_audit_valid_action',
                    "action_type IN ('create', 'update', 'delete')"
                )

                # Constraint: agent_maturity in ('STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS')
                batch_op.create_check_constraint(
                    'ck_financial_audit_valid_maturity',
                    "agent_maturity IN ('STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS')"
                )

                # Constraint: entry_hash length = 64 (SHA-256 hex)
                batch_op.create_check_constraint(
                    'ck_financial_audit_hash_length',
                    "length(entry_hash) = 64"
                )
        except OperationalError as e:
            # Log but don't fail - constraints may already exist or table may be locked
            print(f"Warning: Could not add all constraints: {e}")
    else:
        # Log warning that required columns are missing
        print("Warning: sequence_number or entry_hash columns not found. "
              "Run Phase 94-01 migration first to add hash chain fields.")


def downgrade():
    """Remove chronological integrity constraints."""
    try:
        with op.batch_alter_table('financial_audit') as batch_op:
            batch_op.drop_constraint('ck_financial_audit_hash_length', type_='check')
            batch_op.drop_constraint('ck_financial_audit_valid_maturity', type_='check')
            batch_op.drop_constraint('ck_financial_audit_valid_action', type_='check')
            batch_op.drop_constraint('ck_financial_audit_sequence_positive', type_='check')
    except OperationalError:
        # Constraints may not exist or table structure changed
        print("Warning: Could not remove all constraints")
