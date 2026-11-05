"""Add durable auth 2FA replay and operation receipt state.

Revision ID: a2f0c1d4e5b6
Revises: d1e2f3g4h5i6
Create Date: 2026-11-05

The five direct auth/2FA mutation routes need durable one-time-use state:
the last accepted TOTP time-step, a monotonic factor revision, per-backup-code
consumption rows, and a safe operation receipt. No raw OTP/secret material is
stored; backup codes are represented by a keyed fingerprint.

The upgrade is guarded so it is safe on databases whose schema was already
created from the current models. Existing plaintext backup-code mirrors are
backfilled once into fingerprint rows; the plaintext mirror is left in place
for the existing UI contract.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import sqlalchemy as sa
from alembic import op


revision = "a2f0c1d4e5b6"
down_revision = "d1e2f3g4h5i6"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return column_name in [
        column["name"] for column in inspector.get_columns(table_name)
    ]


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _column_exists(table_name, column.name):
        op.add_column(table_name, column)


def _fingerprint_code(user_id: str, code: str) -> str:
    # Must match core.auth_2fa_write_service._code_fingerprint exactly.
    from core.auth import SECRET_KEY

    message = f"code|{user_id}|{code}"
    return hmac.new(
        str(SECRET_KEY).encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _backfill_backup_codes() -> None:
    if not _table_exists("auth_2fa_backup_codes"):
        return
    if not _column_exists("users", "two_factor_backup_codes"):
        return
    bind = op.get_bind()
    existing = {
        (str(row["user_id"]), str(row["code_fingerprint"]))
        for row in bind.execute(sa.text(
            "SELECT user_id, code_fingerprint "
            "FROM auth_2fa_backup_codes"
        )).mappings()
    }
    rows = bind.execute(sa.text(
        "SELECT id, tenant_id, workspace_id, two_factor_backup_codes, "
        "two_factor_revision FROM users"
    )).mappings()
    for row in rows:
        codes = row["two_factor_backup_codes"]
        if isinstance(codes, str):
            try:
                codes = json.loads(codes)
            except (TypeError, ValueError):
                continue
        if not isinstance(codes, list) or not codes:
            continue
        revision = int(row["two_factor_revision"] or 0)
        for code in codes:
            fingerprint = _fingerprint_code(str(row["id"]), str(code))
            identity = (str(row["id"]), fingerprint)
            if identity in existing:
                continue
            bind.execute(sa.text(
                "INSERT INTO auth_2fa_backup_codes "
                "(id, user_id, tenant_id, workspace_id, code_fingerprint, "
                "factor_revision, consumed_at, operation_id) "
                "VALUES (:id, :user_id, :tenant_id, :workspace_id, "
                ":fingerprint, :factor_revision, NULL, NULL)"
            ), {
                "id": str(uuid.uuid4()),
                "user_id": str(row["id"]),
                "tenant_id": row["tenant_id"],
                "workspace_id": row["workspace_id"],
                "fingerprint": fingerprint,
                "factor_revision": revision,
            })
            existing.add(identity)


def upgrade():
    if not _table_exists("users"):
        print("    [skip] users does not exist")
        return

    _add_column_if_missing(
        "users",
        sa.Column("two_factor_last_totp_step", sa.Integer(), nullable=True),
    )
    _add_column_if_missing(
        "users",
        sa.Column(
            "two_factor_revision", sa.Integer(), nullable=False,
            server_default="0"),
    )

    if not _table_exists("auth_2fa_backup_codes"):
        op.create_table(
            "auth_2fa_backup_codes",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("tenant_id", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.String(), nullable=True),
            sa.Column("code_fingerprint", sa.String(), nullable=False),
            sa.Column("factor_revision", sa.Integer(), nullable=False),
            sa.Column(
                "consumed_at", sa.DateTime(timezone=True), nullable=True),
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

    if not _table_exists("auth_2fa_operations"):
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

    _backfill_backup_codes()


def downgrade():
    if _table_exists("auth_2fa_operations"):
        op.drop_table("auth_2fa_operations")
    if _table_exists("auth_2fa_backup_codes"):
        op.drop_table("auth_2fa_backup_codes")
    if _table_exists("users"):
        with op.batch_alter_table("users") as batch_op:
            if _column_exists("users", "two_factor_revision"):
                batch_op.drop_column("two_factor_revision")
            if _column_exists("users", "two_factor_last_totp_step"):
                batch_op.drop_column("two_factor_last_totp_step")
