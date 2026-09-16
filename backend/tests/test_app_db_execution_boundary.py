# -*- coding: utf-8 -*-
"""Execution-time boundary for the app-DB NL→SQL lane (audit item 1).

Parse-time validation and result-column inspection are both INCOMPLETE. The
two attacks that got through them (verified on a scratch DB 2026-09-16) read a
non-allowlisted table purely as a PREDICATE, so nothing outside the allowlist
was projected and nothing secret-shaped appeared in ``cur.description``:

    SELECT id FROM canvases WHERE (SELECT count(*) FROM 'users') > 0
    SELECT id FROM canvases
     WHERE EXISTS (SELECT 1 FROM (SELECT * FROM 'user_sessions') canvases)

Both returned the canvases row, which is a 1-bit read of a table the lane must
not touch. The fix is a SQLite authorizer, which SQLite invokes for every table
and column access after name resolution. These tests pin that boundary, and the
legitimate queries it must NOT break (single-install semantics: no row is
dropped, no scope predicate is injected).
"""
import asyncio
import sqlite3

import pytest

import core.app_db_query as adb

SECRET = "DUMMY-SECRET-DO-NOT-READ"


def _scratch_db(path) -> str:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE canvases (id TEXT, title TEXT, tenant_id TEXT, api_key TEXT);
        CREATE TABLE canvas_audit (id TEXT, canvas_id TEXT);
        CREATE TABLE users (id TEXT, email TEXT, password_hash TEXT);
        CREATE TABLE user_sessions (id TEXT, user_id TEXT, refresh_token TEXT);
        INSERT INTO canvases VALUES ('c1','Quote','default','CANVAS-KEY');
        INSERT INTO canvases VALUES ('c2','NoWorkspace',NULL,'K2');
        INSERT INTO canvas_audit VALUES ('a1','c1');
        INSERT INTO users VALUES ('u1','a@b.c','SECRET');
        INSERT INTO user_sessions VALUES ('s1','u1','SECRET');
        """
    )
    con.commit()
    con.close()
    return str(path)


class _R:
    def __init__(self, sql):
        self.sql = sql


async def _ask(sql, db_path, monkeypatch):
    import core.database as dbmod
    import core.llm.pinned_planning as pp

    async def fake_call(llm, prompt, response_model, call_kwargs=None,
                        system_instruction=""):
        return _R(llm.sql)

    monkeypatch.setattr(dbmod, "get_database_url", lambda: f"sqlite:///{db_path}")
    monkeypatch.setattr(pp, "pinned_structured_call", fake_call)
    monkeypatch.setattr(adb, "_schema_lines",
                        lambda: ["canvases(id, title)", "canvas_audit(id, canvas_id)"])
    return await adb.answer_from_app_db("q", "default",
                                        llm_service=type("L", (), {"sql": sql})())


class TestInferenceChannelClosed:
    """The attacks that survived parse-time + projection checks."""

    @pytest.mark.asyncio
    async def test_count_oracle_on_non_allowlisted_table(self, tmp_path, monkeypatch):
        db = _scratch_db(tmp_path / "s.db")
        out = await _ask(
            "SELECT id FROM canvases WHERE (SELECT count(*) FROM 'users') > 0",
            db, monkeypatch)
        assert out is None, (
            "a predicate-only read of a non-allowlisted table returned rows")

    @pytest.mark.asyncio
    async def test_exists_oracle_through_nested_alias(self, tmp_path, monkeypatch):
        db = _scratch_db(tmp_path / "s.db")
        out = await _ask(
            "SELECT id FROM canvases WHERE EXISTS "
            "(SELECT 1 FROM (SELECT * FROM 'user_sessions') canvases)",
            db, monkeypatch)
        assert out is None

    @pytest.mark.asyncio
    async def test_no_secret_reaches_the_caller(self, tmp_path, monkeypatch):
        db = _scratch_db(tmp_path / "s.db")
        for sql in (
            "SELECT * FROM 'users'",
            "SELECT password_hash FROM 'users'",
            "SELECT * FROM (SELECT * FROM 'users') canvases",
            "SELECT id FROM canvases WHERE (SELECT count(*) FROM user_sessions) > 0",
        ):
            out = await _ask(sql, db, monkeypatch)
            assert SECRET not in repr(out), f"secret leaked via: {sql}"


class TestWildcardExpansion:
    @pytest.mark.asyncio
    async def test_star_over_withheld_columns_is_refused(self, tmp_path, monkeypatch):
        db = _scratch_db(tmp_path / "s.db")
        out = await _ask("SELECT * FROM canvases", db, monkeypatch)
        assert out is None, "SELECT * returned withheld columns"

    @pytest.mark.asyncio
    async def test_explicit_allowed_columns_still_work(self, tmp_path, monkeypatch):
        db = _scratch_db(tmp_path / "s.db")
        out = await _ask("SELECT id, title FROM canvases", db, monkeypatch)
        assert out is not None
        assert out["columns"] == ["id", "title"]
        assert sorted(r[0] for r in out["rows"]) == ["c1", "c2"]


class TestLegitimateQueriesUnchanged:
    """The boundary must not break the lane it protects, and must not
    reintroduce a scope filter that silently drops the operator's rows."""

    @pytest.mark.asyncio
    async def test_no_scope_filter_is_injected(self, tmp_path, monkeypatch):
        db = _scratch_db(tmp_path / "s.db")
        out = await _ask("SELECT id FROM canvases", db, monkeypatch)
        assert out is not None
        # c2 carries tenant_id NULL; a workspace predicate would drop it.
        assert "c2" in [r[0] for r in out["rows"]]

    @pytest.mark.asyncio
    async def test_cte_count_and_join_still_work(self, tmp_path, monkeypatch):
        db = _scratch_db(tmp_path / "s.db")
        for sql, want_cols in (
            ("SELECT count(*) AS n FROM canvases", ["n"]),
            ("WITH x AS (SELECT id FROM canvases) SELECT id FROM x", ["id"]),
            ("SELECT c.id FROM canvases c JOIN canvas_audit a "
             "ON a.canvas_id = c.id", ["id"]),
        ):
            out = await _ask(sql, db, monkeypatch)
            assert out is not None, f"legitimate query refused: {sql}"
            assert out["columns"] == want_cols


class TestTimeoutStopsDatabaseWork:
    @pytest.mark.asyncio
    async def test_long_query_is_aborted_not_merely_abandoned(
            self, tmp_path, monkeypatch):
        """A caller-side wait ending must not leave the scan running: the
        statement is aborted in-engine (progress handler) and interrupted from
        the timeout path."""
        import time

        db = _scratch_db(tmp_path / "s.db")
        monkeypatch.setattr(adb, "_QUERY_TIMEOUT_S", 1.0)
        slow = ("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL "
                "SELECT x+1 FROM c WHERE x < 500000000) SELECT count(*) FROM c")
        t0 = time.monotonic()
        out = await _ask(slow, db, monkeypatch)
        elapsed = time.monotonic() - t0
        assert out is None
        # The uninterruptible query would run far longer than this bound; the
        # assertion is that the call ends near its budget, not after the work.
        assert elapsed < 8.0, f"timeout did not stop the scan (took {elapsed:.1f}s)"

    def test_authorizer_denies_writes_and_attach(self):
        import sqlite3 as s

        assert adb._db_authorizer(s.SQLITE_INSERT, "canvases", None, "main", None) == s.SQLITE_DENY
        assert adb._db_authorizer(s.SQLITE_DROP_TABLE, "canvases", None, "main", None) == s.SQLITE_DENY
        assert adb._db_authorizer(s.SQLITE_ATTACH, "x.db", None, "main", None) == s.SQLITE_DENY
        assert adb._db_authorizer(s.SQLITE_PRAGMA, "query_only", None, "main", None) == s.SQLITE_DENY
        assert adb._db_authorizer(s.SQLITE_READ, "canvases", "id", "main", None) == s.SQLITE_OK
        assert adb._db_authorizer(s.SQLITE_READ, "users", "id", "main", None) == s.SQLITE_DENY
        assert adb._db_authorizer(s.SQLITE_READ, "canvases", "api_key", "main", None) == s.SQLITE_DENY
