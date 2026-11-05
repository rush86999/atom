"""Add durable auth 2FA replay and operation receipt state.

Revision ID: a2f0c1d4e5b6
Revises: d1e2f3g4h5i6
Create Date: 2026-11-05

The five direct auth/2FA mutation routes need durable one-time-use state:
the last accepted TOTP time-step, a monotonic factor revision, per-backup-code
consumption rows, and a safe operation receipt. No raw OTP/secret material is
stored; backup codes are represented by a keyed fingerprint.
"""
from alembic import op
import sqlalchemy as sa


revision = "a2f0c1d4e5b6"
down_revision = "d1e2f3g4h5i6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("two_factor_last_totp_step", sa.Integer(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "two_factor_revision", sa.Integer(), nullable=False,
            server_default="0"),
    )

    op.create_table(
        "auth_2fa_backup_codes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("workspace_id", sa.String(), nullable=True),
        sa.Column("code_fingerprint", sa.String(), nullable=False),
        sa.Column("factor_revision", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operation_id", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "user_id", "code_fingerprint",
            name="uq_auth_2fa_backup_code"),
    )
    op.create_index(
        "ix_auth_2fa_backup_codes_user_id",
        "auth_2fa_backup_codes", ["user_id"])
    op.create_index(
        "ix_auth_2fa_backup_codes_tenant_id",
        "auth_2fa_backup_codes", ["tenant_id"])
    op.create_index(
        "ix_auth_2fa_backup_codes_code_fingerprint",
        "auth_2fa_backup_codes", ["code_fingerprint"])
    op.create_index(
        "ix_auth_2fa_backup_codes_factor_revision",
        "auth_2fa_backup_codes", ["factor_revision"])
    op.create_index(
        "ix_auth_2fa_backup_codes_operation_id",
        "auth_2fa_backup_codes", ["operation_id"])

    op.create_table(
        "auth_2fa_operations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("workspace_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("factor_revision", sa.Integer(), nullable=False),
        sa.Column("material_fingerprint", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("audit_id", sa.String(), nullable=True),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_auth_2fa_operations_user_id",
        "auth_2fa_operations", ["user_id"])
    op.create_index(
        "ix_auth_2fa_operations_tenant_id",
        "auth_2fa_operations", ["tenant_id"])
    op.create_index(
        "ix_auth_2fa_operations_action",
        "auth_2fa_operations", ["action"])
    op.create_index(
        "ix_auth_2fa_operations_target_id",
        "auth_2fa_operations", ["target_id"])
    op.create_index(
        "ix_auth_2fa_operations_status",
        "auth_2fa_operations", ["status"])


def downgrade():
    op.drop_table("auth_2fa_operations")
    op.drop_table("auth_2fa_backup_codes")
    op.drop_column("users", "two_factor_revision")
    op.drop_column("users", "two_factor_last_totp_step")
