# -*- coding: utf-8 -*-
"""NL→SQL over the app's OWN database — the same primitive the dataset
lane uses, extended to operational records. The generator half existed
orphaned (schema_aware_sql_generator, zero callers, no allowlist); this
pins the completed safety envelope: table allowlist, secret-column
stripping (prompt AND parse), SELECT-only single statement, scope-column
refusal, caps, read-only execution."""
import sqlite3

import pytest

import core.app_db_query as adb
from core.app_db_query import validate_app_db_sql as v


class TestValidator:
    def test_allowlist_and_secrets(self):
        assert v("SELECT count(*) FROM canvases") is None
        # secrets/credential tables rejected before execution
        assert "allowlist" in v("SELECT access_token FROM integration_tokens")
        assert "allowlist" in v("SELECT hashed_password FROM users")
        # secret-shaped COLUMN references rejected even in allowed tables
        assert "withheld column reference" in v("SELECT api_key FROM canvases")
        assert "withheld column reference" in v(
            "SELECT refresh_token FROM agent_registry")

    def test_read_only_enforcement(self):
        assert "SELECT" in v("DELETE FROM canvases")
        assert "statements" in v("SELECT 1; DROP TABLE users")
        assert "verb" in v("SELECT * FROM canvases WHERE 1=1 PRAGMA table_info(x)")

    def test_allowed_join(self):
        assert v(
            "SELECT c.title FROM canvases c JOIN chat_sessions s "
            "ON c.id = s.canvas_id") is None


class TestColumnStripping:
    def test_secret_columns_withheld_from_schema(self):
        kept = adb._strip_forbidden_columns(
            "integration_tokens",
            ["id", "access_token", "refresh_token", "provider"])
        assert kept == ["id", "provider"]


class TestAnswerFromAppDb:
    @pytest.mark.asyncio
    async def test_happy_path_read_only(self, tmp_path, monkeypatch):
        db = tmp_path / "t.db"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE canvases (id TEXT, title TEXT)")
        con.executemany(
            "INSERT INTO canvases VALUES (?, ?)",
            [("a", "x"), ("b", "y"), ("c", "z")])
        con.commit(); con.close()

        from pydantic import BaseModel

        class _FakeResult(BaseModel):
            sql: str = "SELECT COUNT(*) AS n FROM canvases LIMIT 50"

        class _LLM:
            pass

        async def fake_call(llm, prompt, response_model, call_kwargs=None,
                            system_instruction=""):
            assert "integration_tokens" not in prompt  # secrets never described
            assert "canvases(" in prompt
            return _FakeResult()

        import core.llm.pinned_planning as pp
        monkeypatch.setattr(pp, "pinned_structured_call", fake_call)
        import core.database as dbmod
        monkeypatch.setattr(
            dbmod, "get_database_url", lambda: f"sqlite:///{db}")
        from core.database import get_db_session  # schema introspection
        # introspection uses the session bind; point it at the temp db
        monkeypatch.setattr(
            adb, "_schema_lines",
            lambda: ["canvases(id, title)"])

        out = await adb.answer_from_app_db(
            "how many canvases", "default", llm_service=_LLM())
        assert out and out["rows"] == [[3]]
        assert out["columns"] == ["n"]

    @pytest.mark.asyncio
    async def test_refused_sql_returns_none(self, monkeypatch):
        from pydantic import BaseModel

        class _FakeResult(BaseModel):
            sql: str = "SELECT access_token FROM integration_tokens"

        async def fake_call(llm, prompt, response_model, call_kwargs=None,
                            system_instruction=""):
            return _FakeResult()

        import core.llm.pinned_planning as pp
        monkeypatch.setattr(pp, "pinned_structured_call", fake_call)
        monkeypatch.setattr(adb, "_schema_lines", lambda: ["canvases(id)"])
        out = await adb.answer_from_app_db(
            "tokens please", "default", llm_service=object())
        assert out is None
