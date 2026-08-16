# -*- coding: utf-8 -*-
"""Coverage wave 100 — verified gap batch D.

Targets (verified under 80% by existing suites):
1.  core/token_refresher.py                (39%)
2.  core/llm/registry/lmsys_client.py      (24%)
3.  core/data/dataset_manager.py           (63%)
4.  api/mobile_workflows.py                (29%)
5.  core/action_registry.py                (78%)

No network, no real LLM — httpx clients and DB sessions are mocked everywhere.
Plain pytest + unittest.mock (asyncio_mode=auto).
"""
import asyncio
import json as json_mod
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import (
    AsyncMock, MagicMock, Mock, mock_open, patch,
)

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# =========================================================================== #
# core/token_refresher.py
# =========================================================================== #
class TestTokenRefresher:
    def _refresher(self):
        from core.token_refresher import TokenRefresher
        return TokenRefresher()

    def test_register_and_defaults(self):
        tr = self._refresher()
        tr.register_service("svc", AsyncMock(), expires_at=None, refresh_token="r")
        assert "svc" in tr.refresh_handlers
        assert tr.token_metadata["svc"]["last_refreshed"] is None

    def test_should_refresh_unknown_and_no_expiry(self):
        tr = self._refresher()
        assert tr.should_refresh("nope") is False
        tr.register_service("svc", AsyncMock())
        assert tr.should_refresh("svc") is False

    def test_should_refresh_naive_datetime_coerced(self):
        # tz-naive expires_at must not blow up the comparison
        tr = self._refresher()
        tr.register_service(
            "svc", AsyncMock(),
            expires_at=datetime.now() - timedelta(minutes=5),  # naive, past
        )
        assert tr.should_refresh("svc") is True

    def test_should_refresh_future_aware_false(self):
        tr = self._refresher()
        tr.register_service(
            "svc", AsyncMock(),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        assert tr.should_refresh("svc") is False
        assert tr.should_refresh("svc", buffer_minutes=180) is True

    async def test_refresh_token_no_handler(self):
        tr = self._refresher()
        assert await tr.refresh_token("missing") is False

    async def test_refresh_token_success_updates_metadata(self):
        tr = self._refresher()
        handler = AsyncMock(return_value={
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "refresh_token": "new-r",
        })
        tr.register_service("svc", handler, expires_at=None, refresh_token="r")
        assert await tr.refresh_token("svc") is True
        assert tr.token_metadata["svc"]["refresh_token"] == "new-r"
        assert tr.token_metadata["svc"]["last_refreshed"] is not None

    async def test_refresh_token_handler_returns_none(self):
        tr = self._refresher()
        tr.register_service("svc", AsyncMock(return_value=None))
        assert await tr.refresh_token("svc") is False

    async def test_refresh_token_handler_raises(self):
        tr = self._refresher()
        tr.register_service("svc", AsyncMock(side_effect=RuntimeError("boom")))
        assert await tr.refresh_token("svc") is False

    async def test_check_and_refresh_all(self):
        tr = self._refresher()
        ok = AsyncMock(return_value=True)
        bad = AsyncMock(side_effect=RuntimeError("x"))
        tr.register_service("a", ok, expires_at=datetime.now(timezone.utc))
        tr.register_service("b", bad, expires_at=datetime.now(timezone.utc))
        tr.register_service("c", AsyncMock(), expires_at=datetime.now(timezone.utc) + timedelta(days=1))
        await tr.check_and_refresh_all()
        ok.assert_awaited_once()
        bad.assert_awaited_once()

    def test_get_status(self):
        tr = self._refresher()
        exp = datetime.now(timezone.utc) + timedelta(hours=2)
        tr.register_service("svc", AsyncMock(), expires_at=exp)
        tr.token_metadata["svc"]["last_refreshed"] = datetime(2026, 1, 1)
        status = tr.get_status()
        assert status["svc"]["expires_at"] == exp.isoformat()
        assert status["svc"]["needs_refresh"] is False
        assert status["svc"]["last_refreshed"] == "2026-01-01T00:00:00"

    def test_get_status_no_expiry(self):
        tr = self._refresher()
        tr.register_service("svc", AsyncMock())
        s = tr.get_status()["svc"]
        assert s["expires_at"] is None and s["last_refreshed"] is None

    # ---- provider handlers ----
    async def test_refresh_google_token(self):
        from core.token_refresher import refresh_google_token
        handler = MagicMock()
        handler.refresh_access_token = AsyncMock(return_value={
            "expires_in": 3600, "access_token": "at", "refresh_token": "nr",
        })
        with patch("core.oauth_handler.OAuthHandler", return_value=handler), \
             patch("core.oauth_handler.GOOGLE_OAUTH_CONFIG", {}):
            out = await refresh_google_token({"refresh_token": "r"})
        assert out["access_token"] == "at" and out["refresh_token"] == "nr"
        assert out["expires_at"] > datetime.now() - timedelta(seconds=5)

    async def test_refresh_google_token_no_token(self):
        from core.token_refresher import refresh_google_token
        assert await refresh_google_token({}) is None

    async def test_refresh_google_token_error(self):
        from core.token_refresher import refresh_google_token
        handler = MagicMock()
        handler.refresh_access_token = AsyncMock(side_effect=RuntimeError("x"))
        with patch("core.oauth_handler.OAuthHandler", return_value=handler), \
             patch("core.oauth_handler.GOOGLE_OAUTH_CONFIG", {}):
            assert await refresh_google_token({"refresh_token": "r"}) is None

    async def test_refresh_microsoft_token(self):
        from core.token_refresher import refresh_microsoft_token
        handler = MagicMock()
        handler.refresh_access_token = AsyncMock(return_value={"access_token": "at"})
        with patch("core.oauth_handler.OAuthHandler", return_value=handler), \
             patch("core.oauth_handler.MICROSOFT_OAUTH_CONFIG", {}):
            out = await refresh_microsoft_token({"refresh_token": "r"})
        assert out["refresh_token"] == "r"  # keeps old when not rotated
        assert out["expires_at"] > datetime.now()

    async def test_refresh_microsoft_token_missing_and_error(self):
        from core.token_refresher import refresh_microsoft_token
        assert await refresh_microsoft_token({}) is None
        handler = MagicMock()
        handler.refresh_access_token = AsyncMock(side_effect=ValueError("x"))
        with patch("core.oauth_handler.OAuthHandler", return_value=handler), \
             patch("core.oauth_handler.MICROSOFT_OAUTH_CONFIG", {}):
            assert await refresh_microsoft_token({"refresh_token": "r"}) is None

    async def test_refresh_salesforce_token(self):
        from core.token_refresher import refresh_salesforce_token
        handler = MagicMock()
        handler.refresh_access_token = AsyncMock(return_value={})
        with patch("core.oauth_handler.OAuthHandler", return_value=handler), \
             patch("core.oauth_handler.SALESFORCE_OAUTH_CONFIG", {}):
            out = await refresh_salesforce_token({"refresh_token": "r"})
        # default 7200s window
        assert out["expires_at"] > datetime.now() + timedelta(hours=1)

    async def test_refresh_salesforce_token_missing(self):
        from core.token_refresher import refresh_salesforce_token
        assert await refresh_salesforce_token({}) is None

    async def test_refresh_whatsapp_token_success(self, monkeypatch):
        from core.token_refresher import refresh_whatsapp_token
        monkeypatch.setenv("WHATSAPP_APP_ID", "cid")
        monkeypatch.setenv("WHATSAPP_APP_SECRET", "sec")
        resp = MagicMock()
        resp.json.return_value = {"access_token": "long-lived", "expires_in": 1000}
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(return_value=resp)
        with patch("core.token_refresher.httpx.AsyncClient", return_value=client):
            out = await refresh_whatsapp_token({"refresh_token": "short"})
        assert out["access_token"] == "long-lived"
        assert out["expires_at"] > datetime.now()

    async def test_refresh_whatsapp_token_missing_creds(self, monkeypatch):
        from core.token_refresher import refresh_whatsapp_token
        monkeypatch.delenv("WHATSAPP_APP_ID", raising=False)
        monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)
        assert await refresh_whatsapp_token({"refresh_token": "t"}) is None

    async def test_refresh_whatsapp_token_http_error(self, monkeypatch):
        from core.token_refresher import refresh_whatsapp_token
        monkeypatch.setenv("WHATSAPP_APP_ID", "cid")
        monkeypatch.setenv("WHATSAPP_APP_SECRET", "sec")
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(side_effect=RuntimeError("net down"))
        with patch("core.token_refresher.httpx.AsyncClient", return_value=client):
            assert await refresh_whatsapp_token({"refresh_token": "t"}) is None


# =========================================================================== #
# core/llm/registry/lmsys_client.py
# =========================================================================== #
def _cache_mock(get_value=None):
    cache = MagicMock()
    cache.get_async = AsyncMock(return_value=get_value)
    cache.set_async = AsyncMock(return_value=True)
    return cache


def _http_response(payload, status=200):
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = RuntimeError(f"HTTP {status}")
    return resp


def _client_with(response=None, error=None):
    c = MagicMock()
    c.get = AsyncMock(return_value=response) if response is not None else \
        AsyncMock(side_effect=error)
    return c


class TestLMSYSClient:
    def _make(self, cache=None):
        from core.llm.registry.lmsys_client import LMSYSClient
        return LMSYSClient(cache_service=cache or _cache_mock())

    async def test_fetch_leaderboard_api_and_cache_set(self):
        c = self._make(_cache_mock(None))
        payload = {"leaderboard": [
            {"name": "gpt-4o", "score": 1287.5},
            {"model": "claude-3", "elo": 1250},
            {"id": "gemini", "rating": 1200},
            {"name": "bad", "score": "not-a-number"},
            "not-a-dict",
            {"name": "empty"},
        ]}
        with patch.object(c, "_get_client", AsyncMock(return_value=_client_with(_http_response(payload)))):
            scores = await c.fetch_leaderboard()
        assert scores["gpt-4o"] == 1287.5
        assert scores["claude-3"] == 1250.0
        assert scores["gemini"] == 1200.0
        assert "bad" not in scores and "empty" not in scores
        c.cache.set_async.assert_awaited_once()

    async def test_fetch_leaderboard_cache_hit(self):
        cached = json_mod.dumps({"gpt-4o": 1.0})
        c = self._make(_cache_mock(cached))
        assert await c.fetch_leaderboard() == {"gpt-4o": 1.0}

    async def test_fetch_leaderboard_corrupt_cache_falls_through(self):
        c = self._make(_cache_mock("{not json"))
        payload = {"models": [{"name": "m", "score": 1}]}
        with patch.object(c, "_get_client", AsyncMock(return_value=_client_with(_http_response(payload)))):
            assert await c.fetch_leaderboard() == {"m": 1.0}

    async def test_fetch_leaderboard_failure_uses_cached_fallback(self):
        c = self._make(_cache_mock(json_mod.dumps({"cached": 2.0})))
        with patch.object(c, "_get_client", AsyncMock(return_value=_client_with(error=RuntimeError("boom")))):
            assert await c.fetch_leaderboard() == {"cached": 2.0}

    async def test_fetch_leaderboard_failure_no_cache_raises(self):
        c = self._make(_cache_mock(None))
        with patch.object(c, "_get_client", AsyncMock(return_value=_client_with(error=RuntimeError("boom")))):
            with pytest.raises(RuntimeError):
                await c.fetch_leaderboard()

    async def test_fetch_leaderboard_failure_no_cache_use(self):
        c = self._make(_cache_mock(None))
        with patch.object(c, "_get_client", AsyncMock(return_value=_client_with(error=RuntimeError("x")))):
            with patch.object(c.cache, "get_async", AsyncMock(return_value="{}")):
                with pytest.raises(RuntimeError):
                    await c.fetch_leaderboard(use_cache=False)

    async def test_close(self):
        from core.llm.registry.lmsys_client import LMSYSClient
        c = LMSYSClient(cache_service=_cache_mock())
        c._client = MagicMock()
        c._client.aclose = AsyncMock()
        inner = c._client
        await c.close()
        inner.aclose.assert_awaited_once()
        assert c._client is None
        await c.close()  # no client — no-op

    def test_parse_leaderboard_formats(self):
        c = self._make()
        assert c._parse_leaderboard_response({"data": [{"name": "x", "score": 3}]}) == {"x": 3.0}
        assert c._parse_leaderboard_response({}) == {}

    def test_normalize_model_name(self):
        c = self._make()
        assert c.normalize_model_name("chat-GPT-4-Turbo") == "gpt-4"
        assert c.normalize_model_name("Claude-3-PRO") == "claude-3"

    def test_map_model_name_variants(self):
        c = self._make()
        models = ["GPT-4-Turbo", "claude-3-5-sonnet", "llama-3-70b"]
        assert c.map_model_name("gpt-4-turbo", models) == "GPT-4-Turbo"  # direct
        assert c.map_model_name("chat_gpt_4_turbo", models) == "GPT-4-Turbo"  # normalized
        assert c.map_model_name("claude-3", models) == "claude-3-5-sonnet"  # prefix
        assert c.map_model_name("zzz-unknown-model", models) is None  # none

    async def test_map_scores_to_registry(self):
        c = self._make()
        mapped = await c.map_scores_to_registry(
            {"gpt-4-turbo": 1.0, "unknown-model-x": 2.0}, ["GPT-4-Turbo"]
        )
        assert mapped == {"GPT-4-Turbo": 1.0}

    def test_elo_to_quality_score(self):
        c = self._make()
        assert c.elo_to_quality_score(800) == 0.0
        assert c.elo_to_quality_score(1300) == 100.0
        assert c.elo_to_quality_score(700) == 0.0   # clamped
        assert c.elo_to_quality_score(1400) == 100.0  # clamped
        assert 0 < c.elo_to_quality_score(1050) < 100

    async def test_fetch_lmsys_scores_convenience(self):
        with patch("core.llm.registry.lmsys_client.LMSYSClient") as cls:
            inst = cls.return_value
            inst.fetch_leaderboard = AsyncMock(return_value={"m": 1.0})
            inst.close = AsyncMock()
            from core.llm.registry.lmsys_client import fetch_lmsys_scores
            assert await fetch_lmsys_scores() == {"m": 1.0}
            inst.close.assert_awaited_once()


# =========================================================================== #
# core/data/dataset_manager.py
# =========================================================================== #
class TestDatasetManager:
    def _mgr(self):
        from core.data.dataset_manager import DatasetManager
        return DatasetManager()

    def test_load_inline_json_list_and_dict(self):
        m = self._mgr()
        h = m.load('[{"a": 1}, {"a": 2}]', "ds", session_id="s1")
        assert h.row_count == 2 and h.columns == ["a"]
        assert m.get_handle("ds", "s1").name == "ds"
        h2 = m.load('{"a": 5}', "ds2", session_id="s1")
        assert h2.row_count == 1

    def test_load_inline_json_too_large(self, monkeypatch):
        monkeypatch.setattr("core.data.dataset_manager._MAX_INLINE_JSON_BYTES", 10)
        with pytest.raises(ValueError, match="too large"):
            self._mgr().load('{"a": ' + "1" * 20 + "}", "big")

    def test_load_empty_raises(self):
        with pytest.raises(ValueError, match="loaded empty"):
            self._mgr().load("[]", "empty")

    def test_load_unsupported_format(self, tmp_path):
        p = tmp_path / "t.bin"
        p.write_text("stuff")
        with pytest.raises(ValueError, match="Unsupported format"):
            self._mgr().load(str(p), "d", format="xml")

    def test_load_csv_from_temp_file(self, tmp_path):
        p = tmp_path / "t.csv"
        p.write_text("a,b\n1,2\n3,4\n")
        m = self._mgr()
        h = m.load(str(p), "csvds")
        assert h.row_count == 2
        assert m.get_dataframe("csvds") is not None

    def test_load_json_format_override(self, tmp_path):
        p = tmp_path / "t.dat"
        p.write_text('[{"x": 1}]')
        h = self._mgr().load(str(p), "j", format="json")
        assert h.row_count == 1

    def test_load_rejects_urls_and_system_paths(self):
        with pytest.raises(ValueError, match="URL sources"):
            self._mgr().load("https://evil/x.csv", "d")
        with pytest.raises(ValueError, match="outside allowed"):
            self._mgr().load("/etc/passwd", "d")

    def test_load_rejects_outside_data_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path / "data"))
        # Point the temp allowlist somewhere irrelevant so tmp_path is *not*
        # auto-allowed and only ATOM_DATA_DIR counts.
        monkeypatch.setattr("tempfile.gettempdir", lambda: "/nonexistent-atom-tmp")
        outside = tmp_path / "not-data.csv"
        outside.write_text("a\n1\n")
        with pytest.raises(ValueError, match="outside allowed"):
            self._mgr().load(str(outside), "d", format="csv")

    def test_get_missing_returns_none(self):
        m = self._mgr()
        assert m.get_dataframe("nope") is None
        assert m.get_handle("nope") is None

    def test_list_datasets_session_scoped(self):
        m = self._mgr()
        m.load('[{"a": 1}]', "one", session_id="sA")
        m.load('[{"b": 1}]', "two", session_id="sB")
        names_a = [d["name"] for d in m.list_datasets(session_id="sA")]
        assert names_a == ["one"]
        d = m.list_datasets(session_id="sA")[0]
        assert set(d) == {"name", "source", "row_count", "columns", "dtypes", "backend"}

    def test_query_not_loaded(self):
        assert self._mgr().query("nope", "select 1") == {
            "success": False, "error": "Dataset 'nope' not loaded"
        }

    def test_query_blocks_restricted_functions(self):
        m = self._mgr()
        m.load('[{"a": 1}]', "d")
        for sql in (
            "SELECT * FROM read_csv('/etc/passwd')",
            "SELECT * FROM df -- read_parquet('x')",
            "/* read_blob */ SELECT 1",
        ):
            out = m.query("d", sql)
            assert out["success"] is False and "sandbox policy" in out["error"]

    def test_query_blocks_httpfs_url(self):
        m = self._mgr()
        m.load('[{"a": 1}]', "d")
        out = m.query("d", "SELECT * FROM 'https://evil.example/x'")
        assert out["success"] is False and "URL reference" in out["error"]

    def test_query_allows_function_name_in_string_literal(self):
        # duckdb absent in this env → non-SQL pandas path, but the guard must
        # still not block a benign literal mentioning a restricted fn name.
        m = self._mgr()
        m.load('[{"a": "read_csv"}, {"a": 2}]', "d")
        out = m.query("d", "df[df['a'] == 'read_csv']")
        assert out["success"] is True and out["row_count"] == 1

    def test_query_pandas_expression_paths(self):
        m = self._mgr()
        m.load('[{"a": 1}, {"a": 2}]', "d")
        out = m.query("d", "df[df['a'] > 1]")
        assert out["success"] is True and out["data"] == [{"a": 2}]
        out = m.query("d", "df.shape[0]")
        assert out == {"success": True, "data": "2", "row_count": 1}

    def test_query_blocked_code(self):
        m = self._mgr()
        m.load('[{"a": 1}]', "d")
        out = m.query("d", "__import__('os').system('ls')")
        assert out["success"] is False

    def test_query_failure_returns_error(self):
        m = self._mgr()
        m.load('[{"a": 1}]', "d")
        out = m.query("d", "df['no_such_col']")
        assert out == {"success": False, "error": "Query failed"}

    def test_head_and_describe(self):
        m = self._mgr()
        m.load('[{"a": 1}, {"a": 2}, {"a": 3}]', "d")
        head = m.head("d", n=2)
        assert head["row_count"] == 2
        desc = m.describe("d")
        assert desc["success"] is True and "a" in desc["statistics"]
        assert m.head("nope")["success"] is False
        assert m.describe("nope")["success"] is False

    def test_clear_session_and_all(self):
        m = self._mgr()
        m.load('[{"a": 1}]', "x", session_id="s1")
        m.load('[{"a": 1}]', "y", session_id="s2")
        assert m.clear_session("s1") == 1
        assert m.get_handle("x", "s1") is None
        assert m.clear_session("s1") == 0
        assert m.clear_all() == 1

    def test_get_dataset_manager_singleton(self):
        from core.data import dataset_manager as dm
        a = dm.get_dataset_manager()
        b = dm.get_dataset_manager()
        assert a is b


# =========================================================================== #
# api/mobile_workflows.py
# =========================================================================== #
def _wf_row(**kw):
    base = dict(
        id="wf-1", workflow_id="wf-1", name="Wf", description="d",
        configuration={"category": "cat", "tags": ["t"]}, status="active",
        createdAt="2026-01-02", created_at="2026-01-02",
    )
    base.update(kw)
    return NS(**base)


def _exec_row(**kw):
    # Doubles as a log row too (the mock query chains are shared).
    base = dict(
        execution_id="exec_1", workflow_id="wf-1", status="completed",
        created_at=datetime(2026, 1, 2, 3, 4, 5), completed_at=None,
        updated_at=None, user_id="u1", error=None,
        id=1, level="INFO", message="m1", timestamp=datetime(2026, 1, 2, 3, 4, 5),
        step_id="step-1",
    )
    base.update(kw)
    return NS(**base)


def _make_client(db, user=None):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.mobile_workflows import router, get_current_user  # noqa: F401
    from core.auth import get_current_user as auth_get_user
    from core.database import get_db
    import api.mobile_workflows as mw

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth_get_user] = lambda: (user or NS(id="u1"))
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app), mw


def _configure_db(db, executions=(), first_execution=None, workflows=(), logs=(), steps=()):
    q = db.query.return_value
    q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = list(executions)
    q.filter.return_value.order_by.return_value.limit.return_value.first.return_value = first_execution
    q.filter.return_value.order_by.return_value.all.return_value = list(steps)
    q.filter.return_value.limit.return_value.all.return_value = list(workflows)
    q.filter.return_value.all.return_value = list(executions)
    q.filter.return_value.first.return_value = first_execution
    q.order_by.return_value.limit.return_value.all.return_value = list(logs)
    q.limit.return_value.all.return_value = list(logs)
    q.all.return_value = list(workflows)
    q.first.return_value = first_execution


class TestMobileWorkflowsRoutes:
    def test_list_workflows(self):
        db = MagicMock()
        _configure_db(db, executions=[_exec_row()])
        payload = [
            {"id": "wf-1", "workflow_id": "wf-1", "name": "Alpha", "description": "abc",
             "category": "cat", "status": "active", "created_at": "", "createdAt": "2026-02",
             "tags": []},
            {"id": "wf-2", "workflow_id": "wf-2", "name": "Beta", "description": "xyz",
             "category": "cat", "status": "paused", "created_at": "", "createdAt": "2026-01",
             "tags": []},
        ]
        client, _ = _make_client(db)
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=json_mod.dumps(payload))), \
             patch("json.load", return_value=payload):
            r = client.get("/api/mobile/workflows")
        assert r.status_code == 200
        body = r.json()
        assert [w["id"] for w in body] == ["wf-1", "wf-2"]  # sorted desc by createdAt
        assert body[0]["execution_count"] == 1 and body[0]["success_rate"] == 100.0

    def test_list_workflows_no_file(self):
        db = MagicMock()
        client, _ = _make_client(db)
        with patch("os.path.exists", return_value=False):
            r = client.get("/api/mobile/workflows")
        assert r.status_code == 200 and r.json() == []

    def test_list_workflows_filters_search_sort(self):
        db = MagicMock()
        _configure_db(db)
        payload = [
            {"id": "a", "name": "Alpha", "description": "x", "category": "c1", "status": "active", "createdAt": "1"},
            {"id": "b", "name": "Beta", "description": "alpha", "category": "c2", "status": "paused", "createdAt": "2"},
        ]
        client, _ = _make_client(db)
        with patch("os.path.exists", return_value=True), \
             patch("json.load", return_value=payload):
            r = client.get("/api/mobile/workflows", params={"search": "alpha", "category": "c2", "sort_order": "asc"})
        assert r.status_code == 200
        assert [w["id"] for w in r.json()] == ["b"]

    def test_list_workflows_error_500(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        client, _ = _make_client(db)
        payload = [{"id": "a", "name": "n", "description": "", "category": "", "status": "s", "createdAt": ""}]
        with patch("os.path.exists", return_value=True), \
             patch("json.load", return_value=payload):
            r = client.get("/api/mobile/workflows")
        assert r.status_code == 500

    def test_search_workflows(self):
        db = MagicMock()
        _configure_db(db, workflows=[_wf_row()])
        client, _ = _make_client(db)
        r = client.get("/api/mobile/workflows/search", params={"query": "Wf"})
        assert r.status_code == 200
        assert r.json()[0]["category"] == "cat"

    def test_search_workflows_error(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("x")
        client, _ = _make_client(db)
        r = client.get("/api/mobile/workflows/search", params={"query": "q"})
        assert r.status_code == 500

    def test_workflow_details(self):
        db = MagicMock()
        _configure_db(db, executions=[_exec_row()])
        wf = {"id": "wf-1", "name": "N", "description": "D", "status": "active", "tags": []}
        client, _ = _make_client(db)
        with patch("api.mobile_workflows._load_workflow_definition", return_value=wf):
            r = client.get("/api/mobile/workflows/wf-1")
        assert r.status_code == 200
        body = r.json()
        assert body["execution_count"] == 1
        assert body["recent_executions"][0]["id"] == "exec_1"

    def test_workflow_details_not_found(self):
        db = MagicMock()
        client, _ = _make_client(db)
        with patch("api.mobile_workflows._load_workflow_definition", return_value=None):
            r = client.get("/api/mobile/workflows/nope")
        assert r.status_code == 404

    def test_workflow_details_internal_error(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("x")
        client, _ = _make_client(db)
        with patch("api.mobile_workflows._load_workflow_definition", return_value={"id": "wf-1"}):
            r = client.get("/api/mobile/workflows/wf-1")
        assert r.status_code == 500

    def test_trigger_async(self):
        db = MagicMock()
        _configure_db(db)
        wf = {"id": "wf-1", "name": "N", "status": "active", "steps": []}
        engine = Mock()
        engine._run_execution = AsyncMock()
        client, mw = _make_client(db)
        with patch("api.mobile_workflows._load_workflow_definition", return_value=wf), \
             patch.object(mw, "require_workflow_executor", new=AsyncMock()) as gate, \
             patch("core.workflow_engine.get_workflow_engine", return_value=engine):
            r = client.post(
                "/api/mobile/workflows/trigger",
                params={"user_id": "ignored"},
                json={"workflow_id": "wf-1", "parameters": {"a": 1}},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "started"
        gate.assert_awaited_once()
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_trigger_not_found(self):
        db = MagicMock()
        client, _ = _make_client(db)
        with patch("api.mobile_workflows._load_workflow_definition", return_value=None):
            r = client.post(
                "/api/mobile/workflows/trigger",
                params={"user_id": "u"},
                json={"workflow_id": "nope"},
            )
        assert r.status_code == 404

    def test_trigger_inactive_workflow_rejected(self):
        db = MagicMock()
        client, _ = _make_client(db)
        with patch("api.mobile_workflows._load_workflow_definition", return_value={"id": "wf-1", "status": "paused"}):
            r = client.post(
                "/api/mobile/workflows/trigger",
                params={"user_id": "u"},
                json={"workflow_id": "wf-1"},
            )
        assert r.status_code == 422

    def test_trigger_executor_gate_403(self):
        from core.base_routes import BaseAPIRouter  # ensure helpers loaded
        db = MagicMock()
        wf = {"id": "wf-1", "status": "active", "steps": []}
        client, mw = _make_client(db)

        async def deny(*a, **k):
            raise mw.router.permission_denied_error("trigger", "Workflow")

        with patch("api.mobile_workflows._load_workflow_definition", return_value=wf), \
             patch.object(mw, "require_workflow_executor", new=deny):
            r = client.post(
                "/api/mobile/workflows/trigger",
                params={"user_id": "u"},
                json={"workflow_id": "wf-1"},
            )
        assert r.status_code == 403
        db.rollback.assert_called()

    def test_trigger_synchronous(self):
        db = MagicMock()
        _configure_db(db)
        wf = {"id": "wf-1", "status": "active", "steps": []}
        engine = Mock()
        engine._run_execution = AsyncMock(return_value=None)

        def refresh(obj):
            obj.status = "completed"

        db.refresh = refresh
        client, mw = _make_client(db)
        with patch("api.mobile_workflows._load_workflow_definition", return_value=wf), \
             patch.object(mw, "require_workflow_executor", new=AsyncMock()), \
             patch("core.workflow_engine.get_workflow_engine", return_value=engine):
            r = client.post(
                "/api/mobile/workflows/trigger",
                params={"user_id": "u"},
                json={"workflow_id": "wf-1", "synchronous": True},
            )
        assert r.status_code == 200
        assert r.json()["status"] == "completed"
        engine._run_execution.assert_awaited_once()

    def test_trigger_internal_error(self):
        db = MagicMock()
        db.add.side_effect = RuntimeError("insert fails")
        client, mw = _make_client(db)
        with patch("api.mobile_workflows._load_workflow_definition", return_value={"id": "wf-1", "status": "active"}), \
             patch.object(mw, "require_workflow_executor", new=AsyncMock()):
            r = client.post(
                "/api/mobile/workflows/trigger",
                params={"user_id": "u"},
                json={"workflow_id": "wf-1"},
            )
        assert r.status_code == 500
        db.rollback.assert_called()

    def test_execution_details(self):
        db = MagicMock()
        _configure_db(
            db, first_execution=_exec_row(), executions=[_exec_row()],
            logs=[_exec_row()],
        )
        client, _ = _make_client(db)
        with patch("api.mobile_workflows._load_workflow_definition", return_value={"name": "N"}):
            r = client.get("/api/mobile/workflows/executions/exec_1")
        assert r.status_code == 200
        body = r.json()
        assert body["workflow_name"] == "N"
        assert body["recent_logs"][0]["level"] == "INFO"

    def test_execution_details_not_found(self):
        db = MagicMock()
        _configure_db(db, first_execution=None)
        client, _ = _make_client(db)
        r = client.get("/api/mobile/workflows/executions/nope")
        assert r.status_code == 404

    def test_workflow_executions_list(self):
        db = MagicMock()
        _configure_db(db, executions=[_exec_row()])
        client, _ = _make_client(db)
        with patch("api.mobile_workflows._load_workflow_definition", return_value={"id": "wf-1"}):
            r = client.get("/api/mobile/workflows/wf-1/executions")
        assert r.status_code == 200 and r.json()[0]["id"] == "exec_1"

    def test_workflow_executions_not_found(self):
        db = MagicMock()
        client, _ = _make_client(db)
        with patch("api.mobile_workflows._load_workflow_definition", return_value=None):
            r = client.get("/api/mobile/workflows/nope/executions")
        assert r.status_code == 404

    def test_execution_logs(self):
        db = MagicMock()
        _configure_db(db, executions=[_exec_row(id=1), _exec_row(id=2)])
        client, _ = _make_client(db)
        r = client.get("/api/mobile/workflows/wf-1/executions/exec_1/logs")
        assert r.status_code == 200
        assert len(r.json()["logs"]) == 2
        r = client.get(
            "/api/mobile/workflows/wf-1/executions/exec_1/logs",
            params={"level": "ERROR"},
        )
        assert r.status_code == 200

    def test_execution_logs_error(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("x")
        client, _ = _make_client(db)
        r = client.get("/api/mobile/workflows/wf-1/executions/exec_1/logs")
        assert r.status_code == 500

    def test_execution_steps(self):
        db = MagicMock()
        step = NS(
            step_id="s1", step_name="Do", step_type="action", sequence_order=1,
            status="completed", started_at=datetime(2026, 1, 1), completed_at=None,
            duration_ms=5, error_message=None,
        )
        _configure_db(db, steps=[step])
        client, _ = _make_client(db)
        r = client.get("/api/mobile/workflows/wf-1/executions/exec_1/steps")
        assert r.status_code == 200
        body = r.json()
        assert body["progress_percentage"] == 100 and body["total_steps"] == 1

    def test_execution_steps_error(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("x")
        client, _ = _make_client(db)
        r = client.get("/api/mobile/workflows/wf-1/executions/exec_1/steps")
        assert r.status_code == 500

    def test_cancel_execution(self):
        db = MagicMock()
        _configure_db(db, first_execution=_exec_row(status="running"))
        engine = Mock()
        engine.cancel_execution = AsyncMock()
        client, _ = _make_client(db)
        with patch("core.workflow_engine.get_workflow_engine", return_value=engine):
            r = client.post("/api/mobile/workflows/executions/exec_1/cancel", params={"user_id": "u1"})
        assert r.status_code == 200
        engine.cancel_execution.assert_awaited_once_with("exec_1")

    def test_cancel_not_running(self):
        db = MagicMock()
        _configure_db(db, first_execution=_exec_row(status="completed"))
        client, _ = _make_client(db)
        r = client.post("/api/mobile/workflows/executions/exec_1/cancel", params={"user_id": "u1"})
        assert r.status_code == 422

    def test_cancel_other_users_execution(self):
        db = MagicMock()
        _configure_db(db, first_execution=_exec_row(status="running", user_id="someone-else"))
        client, _ = _make_client(db)
        r = client.post("/api/mobile/workflows/executions/exec_1/cancel", params={"user_id": "u1"})
        assert r.status_code == 403

    def test_cancel_not_found(self):
        db = MagicMock()
        _configure_db(db, first_execution=None)
        client, _ = _make_client(db)
        r = client.post("/api/mobile/workflows/executions/nope/cancel", params={"user_id": "u1"})
        assert r.status_code == 404

    def test_cancel_internal_error(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("x")
        client, _ = _make_client(db)
        r = client.post("/api/mobile/workflows/executions/exec_1/cancel", params={"user_id": "u1"})
        assert r.status_code == 500


# =========================================================================== #
# core/action_registry.py
# =========================================================================== #
class TestActionRegistryCore:
    def test_list_action_names_alias(self):
        from core.action_registry import action_registry
        assert action_registry.list_action_names() == action_registry.list_actions()

    async def test_execute_action_not_found(self):
        from core.action_registry import ActionNotFoundError, action_registry
        with pytest.raises(ActionNotFoundError):
            await action_registry.execute_action("definitely.not.registered", {}, {})

    def test_context_user_id_variants(self):
        from core.action_registry import _context_user_id
        assert _context_user_id({}) is None
        assert _context_user_id(None) is None
        assert _context_user_id({"user_id": 7}) == "7"
        assert _context_user_id({"userId": "u"}) == "u"
        assert _context_user_id({"actor_id": "a"}) == "a"
        assert _context_user_id({"user": NS(id="from-user")}) == "from-user"
        assert _context_user_id({"user": NS()}) is None

    async def test_documents_search_hybrid_path(self):
        from core.action_registry import action_registry
        svc = MagicMock()
        svc.search = AsyncMock(return_value={"success": True, "results": ["r"]})
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True), \
             patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch", return_value=svc):
            out = await action_registry.execute_action(
                "documents.search", {"query": "q", "limit": 5, "since": "2026-01-01"}, {}
            )
        assert out["success"] is True
        svc.search.assert_awaited_once()

    async def test_documents_search_error(self):
        from core.action_registry import action_registry
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=True), \
             patch("core.hybrid_search.documents_hybrid.DocumentsHybridSearch", side_effect=RuntimeError("x")):
            out = await action_registry.execute_action("documents.search", {"query": "q"}, {})
        assert out["success"] is False

    async def test_documents_search_empty_query(self):
        from core.action_registry import action_registry
        out = await action_registry.execute_action("documents.search", {"query": "   "}, {})
        assert out["success"] is False

    async def test_documents_search_legacy_flag_off(self):
        from core.action_registry import action_registry
        db = MagicMock()
        db.query.return_value.filter.return_value.limit.return_value.all.return_value = []
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=db)
        ctx.__exit__ = MagicMock(return_value=False)
        with patch("core.knowledge_vfs_config.knowledge_vfs_enabled", return_value=False), \
             patch("core.database.get_db_session", return_value=ctx):
            out = await action_registry.execute_action("documents.search", {"query": "q"}, {})
        assert out == {"success": True, "query": "q", "results": []}

    async def test_canvas_read(self):
        from core.action_registry import action_registry
        with patch("tools.canvas_crud_tool.read_canvas", new=AsyncMock(return_value={"success": True})) as rc:
            out = await action_registry.execute_action(
                "canvas.read", {"canvas_id": "c1"}, {"user_id": "u1"}
            )
        assert out["success"] is True
        rc.assert_awaited_once_with("u1", "c1")

    async def test_canvas_read_missing_args(self):
        from core.action_registry import action_registry
        out = await action_registry.execute_action("canvas.read", {}, {})
        assert "canvas_id is required" in out["error"]
        out = await action_registry.execute_action("canvas.read", {"canvas_id": "c"}, {})
        assert "Authenticated user" in out["error"]

    async def test_canvas_update(self):
        from core.action_registry import action_registry
        with patch("tools.canvas_crud_tool.update_canvas_content", new=AsyncMock(return_value={"success": True})) as uc:
            out = await action_registry.execute_action(
                "canvas.update",
                {"canvas_id": "c", "content": {"k": 1}, "title": "T"},
                {"user_id": "u1"},
            )
        assert out["success"] is True
        uc.assert_awaited_once()
        assert uc.await_args.kwargs["title"] == "T"

    async def test_canvas_update_missing_args(self):
        from core.action_registry import action_registry
        out = await action_registry.execute_action("canvas.update", {}, {"user_id": "u"})
        assert "required" in out["error"]
        out = await action_registry.execute_action(
            "canvas.update", {"canvas_id": "c", "content": {}}, {}
        )
        assert "Authenticated user" in out["error"]

    async def test_tasks_create(self):
        from core.action_registry import action_registry
        db = MagicMock()
        svc_inst = MagicMock()
        svc_inst.create_task.return_value = NS(
            id="t1", board_id="b", column_id="col", title="T",
            description="d", status="backlog",
        )
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=db)
        ctx.__exit__ = MagicMock(return_value=False)
        with patch("core.board_service.BoardService", return_value=svc_inst) as BS, \
             patch("core.board_service.TaskCreate", MagicMock()), \
             patch("core.database.get_db_session", return_value=ctx):
            out = await action_registry.execute_action(
                "tasks.create",
                {"title": "T", "board_id": "b", "description": "d"},
                {"user_id": "u1"},
            )
        assert out["success"] is True and out["task"]["id"] == "t1"
        BS.assert_called_once_with(db)

    async def test_tasks_create_validation_and_error(self):
        from core.action_registry import action_registry
        out = await action_registry.execute_action("tasks.create", {"title": " "}, {})
        assert "required" in out["error"]
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            out = await action_registry.execute_action(
                "tasks.create", {"title": "T", "board_id": "b"}, {}
            )
        assert out == {"success": False, "error": "Task creation failed"}

    async def test_agents_list(self):
        from core.action_registry import action_registry
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.all.return_value = [
            NS(id="a1", name="A", description="d", status="active",
               category="ops", capabilities=["x"])
        ]
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=db)
        ctx.__exit__ = MagicMock(return_value=False)
        with patch("core.database.get_db_session", return_value=ctx):
            out = await action_registry.execute_action("agents.list", {}, {})
            assert out["agents"][0]["id"] == "a1"
            out = await action_registry.execute_action("agents.list", {"category": "ops"}, {})
            assert out["success"] is True

    async def test_agents_list_error(self):
        from core.action_registry import action_registry
        with patch("core.database.get_db_session", side_effect=RuntimeError("x")):
            out = await action_registry.execute_action("agents.list", {}, {})
        assert out == {"success": False, "error": "Agent listing failed", "agents": []}


class TestActionRegistryMiniAppWrappers:
    """Thin wrappers delegate to tools.mini_app_tool — verify dispatch."""

    @pytest.mark.parametrize("action,tool", [
        ("mini_app_scaffold", "mini_app_scaffold"),
        ("mini_app_write_logic", "mini_app_write_logic"),
        ("mini_app_dev_run", "mini_app_dev_run"),
        ("mini_app_publish", "mini_app_publish"),
        ("mini_app_install", "mini_app_install"),
        ("mini_app_run", "mini_app_run"),
        ("mini_app_list", "mini_app_list"),
        ("mini_app_get_state", "mini_app_get_state"),
        ("mini_app_db_query", "mini_app_db_query"),
        ("mini_app_db_write", "mini_app_db_write"),
        ("mini_app_set_tests", "mini_app_set_tests"),
        ("mini_app_run_tests", "mini_app_run_tests"),
        ("mini_app_logic_history", "mini_app_logic_history"),
        ("mini_app_revert_logic", "mini_app_revert_logic"),
        ("mini_app_status", "mini_app_status"),
    ])
    async def test_wrapper_delegates(self, action, tool):
        from core.action_registry import action_registry
        mock_fn = AsyncMock(return_value={"success": True, "tool": tool})
        with patch(f"tools.mini_app_tool.{tool}", new=mock_fn):
            out = await action_registry.execute_action(action, {"app_id": "a1"}, {"user_id": "u"})
        assert out == {"success": True, "tool": tool}
        mock_fn.assert_awaited_once()
