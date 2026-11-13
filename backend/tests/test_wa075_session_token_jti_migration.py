"""Exercise the WA-075 session-inventory migration on a scratch legacy DB.

``Base.metadata.create_all`` is not an upgrade path. This test builds the
pre-WA-075 ``user_sessions`` table, stamps the previous Alembic revision, runs
the real migration, and checks the column, the unique index, and that a legacy
raw-token row is preserved (it is upgraded lazily by ``session_registry``).

Scratch-only: the database lives under ``tmp_path`` and ``DATABASE_URL`` is
pointed at it for the subprocess; no live development database is opened.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parents[1]
PRE_REVISION = "20261107_task_operation_result"
MIGRATION_REVISION = "20261113_user_session_token_jti"


def _build_pre_migration_database(db_path: Path) -> None:
    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE user_sessions (
                id VARCHAR NOT NULL PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                session_token VARCHAR NOT NULL UNIQUE,
                user_agent VARCHAR,
                ip_address VARCHAR,
                device_type VARCHAR,
                browser VARCHAR,
                os VARCHAR,
                is_active BOOLEAN,
                created_at DATETIME,
                last_active_at DATETIME,
                expires_at DATETIME NOT NULL
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
            INSERT INTO user_sessions (
                id, user_id, session_token, is_active, expires_at
            ) VALUES (
                'legacy', 'user-a', 'raw-legacy-bearer', 1,
                '2027-01-01 00:00:00'
            )
        """))
    engine.dispose()


def _run_alembic(tmp_path: Path, db_path: Path, *arguments: str) -> None:
    alembic_bin = shutil.which("alembic")
    if not alembic_bin:
        pytest.skip("alembic console script is not available on PATH")
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{db_path}"
    environment["TESTING"] = "0"
    environment.pop("PYTHONPATH", None)
    # Run outside backend/ so the local ``backend/alembic`` package directory
    # cannot shadow the installed Alembic package.
    result = subprocess.run(
        [
            alembic_bin,
            "-c", str(BACKEND_DIR / "alembic.ini"),
            *arguments,
        ],
        cwd=str(tmp_path),
        env=environment,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stderr


def test_migration_adds_revocable_identity_to_legacy_sessions(tmp_path):
    db_path = tmp_path / "pre-migration-sessions.db"
    _build_pre_migration_database(db_path)

    _run_alembic(tmp_path, db_path, "upgrade", MIGRATION_REVISION)

    engine = sa.create_engine(f"sqlite:///{db_path}")
    inspector = sa.inspect(engine)
    columns = {
        column["name"] for column in inspector.get_columns("user_sessions")
    }
    assert "token_jti" in columns
    # The inventory writer sets tenant_id on every login; it was missing from
    # the original table-creating revision, so this migration must add it too.
    assert "tenant_id" in columns

    indexes = {index["name"]: index for index in inspector.get_indexes("user_sessions")}
    token_index = indexes["ix_user_sessions_token_jti"]
    assert bool(token_index["unique"]) is True
    assert token_index["column_names"] == ["token_jti"]

    with engine.begin() as conn:
        legacy = conn.execute(sa.text(
            "SELECT session_token, token_jti FROM user_sessions "
            "WHERE id = 'legacy'"
        )).mappings().one()
        assert legacy["session_token"] == "raw-legacy-bearer"
        assert legacy["token_jti"] is None
        conn.execute(sa.text(
            "INSERT INTO user_sessions "
            "(id, user_id, session_token, token_jti, expires_at) "
            "VALUES ('new', 'user-a', 'sha256:abc', 'jti-1', "
            "'2027-01-01 00:00:00')"
        ))

    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO user_sessions "
                "(id, user_id, session_token, token_jti, expires_at) "
                "VALUES ('duplicate', 'user-a', 'sha256:def', 'jti-1', "
                "'2027-01-01 00:00:00')"
            ))
    engine.dispose()

    _run_alembic(tmp_path, db_path, "downgrade", PRE_REVISION)
    engine = sa.create_engine(f"sqlite:///{db_path}")
    columns = {
        column["name"]
        for column in sa.inspect(engine).get_columns("user_sessions")
    }
    assert "token_jti" not in columns
    # tenant_id predates this revision; downgrade must not destroy its data.
    assert "tenant_id" in columns
    with engine.connect() as conn:
        assert conn.execute(sa.text(
            "SELECT COUNT(*) FROM user_sessions WHERE id = 'legacy'"
        )).scalar_one() == 1
    engine.dispose()


def test_sqlite_repair_adds_the_unique_index_that_add_column_cannot(tmp_path):
    from core.sqlite_schema_repair import ensure_sqlite_unique_index

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'repaired-sessions.db'}")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE user_sessions (
                id VARCHAR PRIMARY KEY,
                session_token VARCHAR NOT NULL UNIQUE,
                token_jti VARCHAR
            )
        """))

    ensure_sqlite_unique_index(
        engine, "user_sessions", "ix_user_sessions_token_jti", "token_jti")

    indexes = {index["name"]: index for index in sa.inspect(engine).get_indexes("user_sessions")}
    assert bool(indexes["ix_user_sessions_token_jti"]["unique"]) is True
    engine.dispose()
