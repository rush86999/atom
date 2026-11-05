"""Exercise the durable 2FA migration on a pre-migration scratch account DB.

``Base.metadata.create_all`` is not an upgrade path. This test builds the old
users table, stamps the pre-migration Alembic revision, runs the real Alembic
upgrade, and checks defaults plus the plaintext-to-fingerprint backfill.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parents[1]
PRE_REVISION = "d1e2f3g4h5i6"
MIGRATION_REVISION = "a2f0c1d4e5b6"
CODE_A = "AAAA-BBBB-CCCC-DDDD"
CODE_B = "1111-2222-3333-4444"


def _build_pre_migration_database(db_path: Path) -> None:
    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE users (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR,
                email VARCHAR,
                hashed_password VARCHAR,
                first_name VARCHAR NOT NULL,
                last_name VARCHAR NOT NULL,
                role VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                workspace_id VARCHAR,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                two_factor_enabled BOOLEAN DEFAULT 0,
                two_factor_secret VARCHAR,
                two_factor_backup_codes JSON
            )
        """))
        conn.execute(sa.text(
            "CREATE TABLE alembic_version "
            "(version_num VARCHAR(32) NOT NULL)"
        ))
        conn.execute(sa.text(
            "INSERT INTO alembic_version (version_num) VALUES (:revision)"
        ), {"revision": PRE_REVISION})
        conn.execute(sa.text("""
            INSERT INTO users (
                id, tenant_id, email, hashed_password, first_name,
                last_name, role, status, workspace_id, is_active,
                two_factor_enabled, two_factor_secret,
                two_factor_backup_codes
            ) VALUES (
                :id, :tenant_id, :email, :hashed_password, :first_name,
                :last_name, :role, :status, :workspace_id, 1,
                1, :secret, :codes
            )
        """), {
            "id": "u-pre",
            "tenant_id": "t1",
            "email": "pre@example.com",
            "hashed_password": "x",
            "first_name": "Pre",
            "last_name": "Migration",
            "role": "member",
            "status": "active",
            "workspace_id": "ws-1",
            "secret": "JBSWY3DPEHPK3PXP",
            "codes": json.dumps([CODE_A, CODE_B]),
        })
    engine.dispose()


def test_migration_upgrades_pre_migration_scratch_account_db(tmp_path):
    db_path = tmp_path / "pre-migration-2fa.db"
    _build_pre_migration_database(db_path)

    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{db_path}"
    environment["TESTING"] = "0"
    # Run Alembic from outside the backend root so the local
    # ``backend/alembic`` package directory cannot shadow the installed
    # package. The absolute alembic.ini keeps the script location stable; the
    # migration env adds the backend root after Alembic has been imported.
    environment.pop("PYTHONPATH", None)
    runner = (
        "import sys\n"
        "sys.path = [p for p in sys.path if p not in ('', '.') "
        "and not p.rstrip('/').endswith('/backend')]\n"
        "from alembic.config import main\n"
        "main()\n"
    )
    result = subprocess.run(
        [
            sys.executable, "-c", runner,
            "-c", str(BACKEND_DIR / "alembic.ini"),
            "upgrade", MIGRATION_REVISION,
        ],
        cwd=str(tmp_path),
        env=environment,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(f"sqlite:///{db_path}")
    inspector = sa.inspect(engine)
    assert "auth_2fa_backup_codes" in inspector.get_table_names()
    assert "auth_2fa_operations" in inspector.get_table_names()
    user_columns = {
        column["name"] for column in inspector.get_columns("users")
    }
    assert "two_factor_revision" in user_columns
    assert "two_factor_last_totp_step" in user_columns

    with engine.connect() as conn:
        user = conn.execute(sa.text(
            "SELECT two_factor_revision, two_factor_last_totp_step "
            "FROM users WHERE id = 'u-pre'"
        )).mappings().one()
        assert int(user["two_factor_revision"]) == 0
        assert user["two_factor_last_totp_step"] is None

        rows = conn.execute(sa.text(
            "SELECT code_fingerprint, factor_revision "
            "FROM auth_2fa_backup_codes WHERE user_id = 'u-pre'"
        )).mappings().all()
        all_columns = conn.execute(sa.text(
            "SELECT * FROM auth_2fa_backup_codes"
        )).mappings().all()

    assert len(rows) == 2
    assert all(int(row["factor_revision"]) == 0 for row in rows)

    from core.auth import SECRET_KEY

    expected = {
        hmac.new(
            str(SECRET_KEY).encode("utf-8"),
            f"code|u-pre|{code}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        for code in (CODE_A, CODE_B)
    }
    assert {row["code_fingerprint"] for row in rows} == expected

    stored_text = json.dumps(all_columns, default=str)
    assert CODE_A not in stored_text
    assert CODE_B not in stored_text

    engine.dispose()
