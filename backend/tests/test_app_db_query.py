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


class TestProbeCacheAndFormulas:
    """Gap fixes 2026-09-16: (1) Stage-0 probe results carry the FORMULAS
    sidecar (only the LLM-SQL path attached it before — derivation asks
    saw values without the cell formulas); (2) per-(file-version, token)
    probe cache — the cross-file scan re-scanned 200+ parquets per token
    per turn, making catalog answers intermittent under load."""

    def test_probe_result_carries_formulas(self, tmp_path, monkeypatch):
        import json as _json

        import core.sheet_dataset_service as sds

        parquet = tmp_path / "d.xlsx_sheet1.parquet"
        import pandas as pd

        pd.DataFrame({"A": ["x"]}).to_parquet(parquet)
        sidecar = tmp_path / "d.xlsx_sheet1.parquet.formulas.json"
        sidecar.write_text(_json.dumps(
            {"sheet": "Sheet1", "formulas": {"B2": "=A2*1.02"}}))

        entries = [{
            "dataset_name": "d", "entity_name": "Sheet1",
            "file_name": "d.xlsx", "parquet_path": str(parquet),
        }]
        out = sds._probe_sheet_hits(entries, "x", 10)
        assert out and out.get("formulas") == {"B2": "=A2*1.02"}

    def test_probe_cache_hit_and_kill_switch(self, monkeypatch):
        import core.sheet_dataset_service as sds

        calls = {"n": 0}

        def fake_probe(entries, token, max_rows):
            calls["n"] += 1
            return {"rows": [{"A": token}], "row_count": 1}

        monkeypatch.setattr(sds, "_probe_sheet_hits", fake_probe)
        sds._PROBE_CACHE.clear()
        monkeypatch.setattr(sds, "_PROBE_CACHE_TTL_S", 300.0)
        e = [{"content_hash": "h1"}]
        assert sds._probe_cached(e, "tok", 10)["row_count"] == 1
        assert sds._probe_cached(e, "tok", 10)["row_count"] == 1
        assert calls["n"] == 1  # second call cached
        # different content hash → re-probe (re-materialized file)
        sds._probe_cached([{"content_hash": "h2"}], "tok", 10)
        assert calls["n"] == 2
        # kill switch
        monkeypatch.setattr(sds, "_PROBE_CACHE_TTL_S", 0.0)
        sds._probe_cached(e, "tok", 10)
        assert calls["n"] == 3

    def test_row_selection_prefers_message_figure(self, monkeypatch):
        """The winner file can hold rows for several figure tokens; the row
        the MESSAGE names must win over canvas-history bystanders (live:
        '7519' R235 lost to canvas-'8880' R192 at a co-0 tie)."""
        import asyncio

        import core.chat_tool_planner as ctp
        import core.sheet_dataset_service as sds
        import integrations.chat_orchestrator as co

        def probe(entries, token, max_rows):
            rows = {
                "8880": {"Product Name": "graymills", "LIST": 80005},
                "7519": {"Product Name": 'F-52"x16G', "LIST": 7519},
            }.get(token)
            if not rows:
                return None
            return {"rows": [rows], "row_count": 1, "columns": list(rows),
                    "file_name": "W.xlsx"}

        monkeypatch.setattr(sds, "_probe_cached", probe)
        monkeypatch.setattr(
            ctp, "_distinctive_figure_phrases",
            lambda text: ["8880", "7519"] if "Tennsmith" in text
            else (["7519"] if "7519" in text else []))
        monkeypatch.setattr(
            sds, "search_all_datasets_sync",
            lambda q, u, w, l, m, c: {
                "token": q, "files_searched": 1,
                "hits": [{"file_name": "W.xlsx", "external_id": "E",
                          "columns": ["A"], "rows": [{"A": 1, "__sheet_row": 1}],
                          "row_count": 1}]})
        monkeypatch.setattr(
            sds, "find_entries_sync",
            lambda q, u, w, l: [{"source": "outlook", "external_id": "E",
                                 "file_name": "W.xlsx"}])

        out = asyncio.run(co._derivation_dataset_block(
            "show how the 7519 price was derived",
            "u1",
            {"canvas": {"body": "Tennsmith $8,880.00 quote"},
             "history": []},
            llm_service=None))
        assert out and 'F-52"x16G' in out, out[:300] if out else None
