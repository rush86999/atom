"""Fresh-install SQLite pragmas: every file-backed connection gets WAL.

Sep 6, 2026: the live DB ran in the default journal mode while the
ingestion re-walk wrote continuously — every writer took an exclusive lock
and every reader endpoint blocked behind it ("app is just really slow in
loading anything"; the event-loop thread was sampled parked on a lock
acquire). core/database.py now applies journal_mode=WAL + busy_timeout +
synchronous=NORMAL on every connect. This test pins that a BRAND-NEW db
file (a fresh installation) comes up with those pragmas — nobody should
have to run a manual PRAGMA on a new deployment.
"""
import os
os.environ.setdefault("TESTING", "1")

import importlib

import pytest
from sqlalchemy import text


@pytest.fixture()
def fresh_database(tmp_path, monkeypatch):
    db_path = tmp_path / "fresh_atom.db"  # brand-new file: nothing pre-existing
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    import core.database as database
    importlib.reload(database)
    yield database
    importlib.reload(database)  # restore the default (TESTING scratch) engine


def test_fresh_db_opens_in_wal_mode(fresh_database):
    with fresh_database.engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"


def test_fresh_db_sets_busy_timeout_and_sync(fresh_database):
    with fresh_database.engine.connect() as conn:
        # connect_args already grant 20s; the hook must never LOWER it.
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() >= 5000
        assert conn.execute(text("PRAGMA synchronous")).scalar() == 1  # NORMAL


def test_pragmas_apply_to_every_new_connection(fresh_database):
    """Per-connection settings must be re-applied per checkout, not once."""
    for _ in range(3):
        with fresh_database.engine.connect() as conn:
            assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"


def test_in_memory_sqlite_is_untouched(fresh_database, monkeypatch):
    """:memory: URLs skip the pragmas (StaticPool single-conn fixtures and
    e2e harnesses rely on plain behavior; WAL has no meaning for memory DBs
    — journal_mode reports "memory", not "wal")."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    importlib.reload(fresh_database)
    with fresh_database.engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "memory"
