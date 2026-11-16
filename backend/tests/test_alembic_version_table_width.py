"""Alembic version-column width for fresh PostgreSQL bootstrap.

Static/DDL tests use the real Alembic runtime context and PostgreSQL dialect
compiler (no database). SQLite subprocess tests use real Alembic env.py as a
control: SQLite does not enforce VARCHAR length, so they prove the existing
SQLite path and long-ID stamping still work, not PostgreSQL enforcement.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
# The repository's backend/alembic scripts package must not shadow installed
# Alembic. Remove it before importing Alembic, then restore backend for core.
sys.path = [p for p in sys.path if Path(p).name != "backend"]
from alembic.runtime.migration import MigrationContext  # noqa: E402
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.schema import CreateTable  # noqa: E402
sys.path.insert(0, str(BACKEND))
from core.alembic_version_table import (  # noqa: E402
    VERSION_NUM_WIDTH,
    WideVersionTablePostgresqlImpl,
)

ALEMBIC = Path(sys.executable).with_name("alembic")
LONG_HEAD = "20260821_turn_facts_source_attribution"  # 38 chars


def _postgres_table(schema=None, pk=True):
    ctx = MigrationContext.configure(dialect_name="postgresql",
                                     opts={"as_sql": True})
    assert isinstance(ctx.impl, WideVersionTablePostgresqlImpl)
    return ctx.impl.version_table_impl(
        version_table="alembic_version",
        version_table_schema=schema,
        version_table_pk=pk,
    )


def test_postgres_version_hook_is_wide_and_preserves_shape():
    table = _postgres_table(schema="audit")
    assert table.name == "alembic_version"
    assert table.schema == "audit"
    assert table.c.version_num.type.length == VERSION_NUM_WIDTH == 255
    assert table.c.version_num.nullable is False
    assert table.primary_key.name == "alembic_version_pkc"
    assert [c.name for c in table.primary_key.columns] == ["version_num"]

    ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
    assert "VARCHAR(255)" in ddl
    assert "PRIMARY KEY (version_num)" in ddl


def test_postgres_hook_does_not_mutate_an_existing_32_table_metadata():
    existing = sa.Table(
        "alembic_version", sa.MetaData(),
        sa.Column("version_num", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("version_num", name="alembic_version_pkc"),
    )
    _postgres_table()
    assert existing.c.version_num.type.length == 32


def test_sqlite_default_impl_stays_at_32_after_helper_import():
    ctx = MigrationContext.configure(dialect_name="sqlite",
                                     opts={"as_sql": True})
    assert not isinstance(ctx.impl, WideVersionTablePostgresqlImpl)
    table = ctx.impl.version_table_impl(
        version_table="alembic_version",
        version_table_schema=None,
        version_table_pk=True,
    )
    assert table.c.version_num.type.length == 32


def _alembic_env(db: Path, home: Path):
    env = {
        "PATH": f"{Path(sys.executable).parent}:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "TESTING": "1",
        "PYTEST_VERSION": "alembic-version-width-test",
        "DATABASE_URL": f"sqlite:///{db}",
        "ENVIRONMENT": "development",
    }
    return env


def _run_alembic(db: Path, home: Path, *args):
    return subprocess.run(
        [str(ALEMBIC), "-c", "alembic.ini", *args],
        cwd=str(BACKEND), env=_alembic_env(db, home),
        capture_output=True, text=True, timeout=120,
    )


def test_sqlite_stamp_heads_accepts_long_ids_control(tmp_path):
    db = tmp_path / "long-heads.db"
    home = tmp_path / "home"; home.mkdir()

    result = _run_alembic(db, home, "stamp", "heads")

    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(db) as raw:
        rows = [r[0] for r in raw.execute(
            "select version_num from alembic_version order by version_num")]
        col_type = raw.execute(
            "pragma table_info(alembic_version)").fetchall()[0][2]
    assert LONG_HEAD in rows and len(LONG_HEAD) == 38
    # SQLite's declared width is unchanged and unenforced; this is a control,
    # not proof of PostgreSQL enforcement.
    assert "32" in str(col_type)


def test_sqlite_current_is_read_only_on_existing_32_table(tmp_path):
    db = tmp_path / "existing.db"
    home = tmp_path / "home"; home.mkdir()
    with sqlite3.connect(db) as raw:
        raw.execute("create table alembic_version "
                    "(version_num varchar(32) not null)")
        raw.execute("insert into alembic_version values (?)",
                    ("20261113_user_session_token_jti",))
        raw.commit()

    result = _run_alembic(db, home, "current")

    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(db) as raw:
        row = raw.execute(
            "select version_num from alembic_version").fetchone()[0]
        col_type = raw.execute(
            "pragma table_info(alembic_version)").fetchall()[0][2]
    assert row == "20261113_user_session_token_jti"
    assert "32" in str(col_type)
