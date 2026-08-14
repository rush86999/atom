# -*- coding: utf-8 -*-
"""Coverage wave 94 — integrations/monday_service.py (TDD, fully mocked).

Baseline: 0% — no test file ever imported this module. This wave drives the
whole service: OAuth URL generation (with/without state), code exchange +
refresh (success and RequestException re-raise), GraphQL request pipeline
(success + failure), boards/board/items CRUD (with and without optional
params), workspaces, users, board creation, health status (healthy/
unhealthy/error), item search, Postgres metric cache sync (create + update
paths, mandatory workspace_id, rollback, outer failure), full sync,
capabilities, health check, and every execute_operation branch including the
unknown-op and exception paths.

Bugs fixed (TDD RED->GREEN):
- monday_service.py:442/449: sync_to_postgres_cache leaked raw str(e) in the
  API-visible error field -> generic message, detail kept server-side in logs.
- monday_service.py:583: execute_operation leaked raw str(e) -> generic
  message + server-side logging.
"""
import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from integrations.monday_service import MondayService


def _svc(**config):
    return MondayService(tenant_id="t1", config=config)


def _fake_response(status=200, data=None, text=""):
    resp = Mock()
    resp.status_code = status
    resp.json.return_value = data if data is not None else {}
    resp.text = text
    return resp


def _resp(data, status=200):
    resp = _fake_response(status=status, data=data)
    resp.raise_for_status = Mock()
    return resp


# ============================================================================
# Init / OAuth
# ============================================================================

class TestInit:
    def test_init_defaults(self):
        svc = MondayService()
        assert svc.base_url == "https://api.monday.com/v2"
        assert svc.redirect_uri == "http://localhost:3000/api/integrations/monday/callback"
        assert svc.client_id is None
        assert svc.tenant_id == "default"

    def test_init_env_fallbacks(self, monkeypatch):
        monkeypatch.setenv("MONDAY_CLIENT_ID", "env-id")
        monkeypatch.setenv("MONDAY_CLIENT_SECRET", "env-secret")
        svc = MondayService(config={})
        assert svc.client_id == "env-id"
        assert svc.client_secret == "env-secret"

    def test_init_config_wins(self, monkeypatch):
        monkeypatch.setenv("MONDAY_CLIENT_ID", "env-id")
        svc = _svc(client_id="cfg-id", client_secret="cfg-secret",
                   redirect_uri="https://cb.example/return")
        assert svc.client_id == "cfg-id"
        assert svc.redirect_uri == "https://cb.example/return"


class TestOAuth:
    def test_get_authorization_url_with_state(self):
        svc = _svc(client_id="cid", redirect_uri="https://cb")
        url = svc.get_authorization_url(state="st123")
        assert url.startswith("https://auth.monday.com/oauth2/authorize?")
        assert "client_id=cid" in url
        assert "response_type=code" in url
        assert "state=st123" in url
        assert "scope=boards:read boards:write" in url

    def test_get_authorization_url_default_state(self):
        svc = _svc(client_id="cid")
        url = svc.get_authorization_url()
        assert "state=no_workspace" in url

    def test_exchange_code_for_token_success(self):
        svc = _svc(client_id="cid", client_secret="sec")
        payload = {"access_token": "at", "refresh_token": "rt",
                   "expires_in": 3600, "token_type": "bearer", "scope": "boards:read"}
        with patch("integrations.monday_service.requests.post",
                   return_value=_resp(payload)) as m_post:
            result = svc.exchange_code_for_token("code1")
        assert result == payload
        posted = m_post.call_args
        assert posted[0][0] == "https://auth.monday.com/oauth2/token"
        assert posted[1]["data"]["grant_type"] == "authorization_code"
        assert posted[1]["data"]["code"] == "code1"

    def test_exchange_code_for_token_raises(self):
        svc = _svc(client_id="cid", client_secret="sec")
        with patch("integrations.monday_service.requests.post",
                   side_effect=requests.RequestException("boom")):
            with pytest.raises(requests.RequestException):
                svc.exchange_code_for_token("code1")

    def test_refresh_access_token_success(self):
        svc = _svc(client_id="cid", client_secret="sec")
        payload = {"access_token": "at2"}
        with patch("integrations.monday_service.requests.post",
                   return_value=_resp(payload)) as m_post:
            result = svc.refresh_access_token("rt1")
        assert result == payload
        assert m_post.call_args[1]["data"]["grant_type"] == "refresh_token"

    def test_refresh_access_token_raises(self):
        svc = _svc(client_id="cid", client_secret="sec")
        with patch("integrations.monday_service.requests.post",
                   side_effect=requests.RequestException("boom")):
            with pytest.raises(requests.RequestException):
                svc.refresh_access_token("rt1")


# ============================================================================
# GraphQL pipeline
# ============================================================================

class TestGraphQLPipeline:
    def test_make_request_success(self):
        svc = _svc()
        data = {"data": {"boards": []}}
        with patch("integrations.monday_service.requests.post",
                   return_value=_resp(data)) as m_post:
            result = svc._make_request("tok", "query { boards { id } }", {"a": 1})
        assert result == data
        args, kwargs = m_post.call_args
        assert kwargs["json"] == {"query": "query { boards { id } }", "variables": {"a": 1}}
        assert kwargs["headers"]["Authorization"] == "Bearer tok"
        assert kwargs["headers"]["API-Version"] == "2023-10"

    def test_make_request_no_variables(self):
        svc = _svc()
        with patch("integrations.monday_service.requests.post",
                   return_value=_resp({"data": {}})) as m_post:
            svc._make_request("tok", "query")
        assert m_post.call_args[1]["json"]["variables"] == {}

    def test_make_request_raises(self):
        svc = _svc()
        with patch("integrations.monday_service.requests.post",
                   side_effect=requests.RequestException("net down")):
            with pytest.raises(requests.RequestException):
                svc._make_request("tok", "query")


# ============================================================================
# Boards / items / workspaces / users
# ============================================================================

class TestBoardsAndItems:
    def test_get_boards(self):
        svc = _svc()
        boards = [{"id": "1", "name": "B"}]
        with patch.object(svc, "_make_request", return_value={"data": {"boards": boards}}) as m:
            assert svc.get_boards("tok") == boards
        assert m.call_args[0][2] == {}

    def test_get_boards_with_workspace(self):
        svc = _svc()
        with patch.object(svc, "_make_request", return_value={"data": {"boards": []}}) as m:
            svc.get_boards("tok", workspace_id="ws9")
        assert m.call_args[0][2] == {"workspaceId": "ws9"}

    def test_get_board_found(self):
        svc = _svc()
        board = {"id": "b1", "name": "Board"}
        with patch.object(svc, "_make_request",
                          return_value={"data": {"boards": [board]}}) as m:
            assert svc.get_board("tok", "b1") == board
        assert m.call_args[0][2] == {"boardId": "b1"}

    def test_get_board_missing(self):
        svc = _svc()
        with patch.object(svc, "_make_request", return_value={"data": {"boards": []}}):
            assert svc.get_board("tok", "nope") == {}

    def test_get_items(self):
        svc = _svc()
        items = [{"id": "i1"}]
        with patch.object(svc, "_make_request",
                          return_value={"data": {"boards": [{"items": items}]}}) as m:
            assert svc.get_items("tok", "b1") == items
        assert m.call_args[0][2] == {"boardId": "b1", "limit": 50}

    def test_get_items_no_boards(self):
        svc = _svc()
        with patch.object(svc, "_make_request", return_value={"data": {"boards": []}}):
            assert svc.get_items("tok", "b1", limit=10) == []

    def test_create_item_with_columns(self):
        svc = _svc()
        item = {"id": "i1"}
        with patch.object(svc, "_make_request",
                          return_value={"data": {"create_item": item}}) as m:
            result = svc.create_item("tok", "b1", "Task", {"status": "In Progress"})
        assert result == item
        assert m.call_args[0][2]["columnValues"] == json.dumps({"status": "In Progress"})

    def test_create_item_no_columns(self):
        svc = _svc()
        with patch.object(svc, "_make_request",
                          return_value={"data": {"create_item": {}}}) as m:
            svc.create_item("tok", "b1", "Task")
        assert m.call_args[0][2]["columnValues"] is None

    def test_update_item_with_columns(self):
        svc = _svc()
        with patch.object(svc, "_make_request",
                          return_value={"data": {"change_multiple_column_values": {"id": "i1"}}}) as m:
            result = svc.update_item("tok", "i1", {"status": "Done"})
        assert result == {"id": "i1"}
        assert m.call_args[0][2]["columnValues"] == json.dumps({"status": "Done"})

    def test_update_item_no_columns(self):
        svc = _svc()
        with patch.object(svc, "_make_request",
                          return_value={"data": {"change_multiple_column_values": {}}}) as m:
            svc.update_item("tok", "i1")
        assert m.call_args[0][2]["columnValues"] == "{}"

    def test_get_workspaces(self):
        svc = _svc()
        workspaces = [{"id": "w1", "name": "W"}]
        with patch.object(svc, "_make_request",
                          return_value={"data": {"workspaces": workspaces}}):
            assert svc.get_workspaces("tok") == workspaces

    def test_get_users(self):
        svc = _svc()
        users = [{"id": "u1"}]
        with patch.object(svc, "_make_request", return_value={"data": {"users": users}}) as m:
            assert svc.get_users("tok") == users
        assert m.call_args[0][2] == {}

    def test_get_users_with_workspace(self):
        svc = _svc()
        with patch.object(svc, "_make_request", return_value={"data": {"users": []}}) as m:
            svc.get_users("tok", workspace_id="ws9")
        assert m.call_args[0][2] == {"workspaceId": "ws9"}

    def test_create_board_full(self):
        svc = _svc()
        board = {"id": "b1"}
        with patch.object(svc, "_make_request",
                          return_value={"data": {"create_board": board}}) as m:
            result = svc.create_board("tok", "New", board_kind="private",
                                      workspace_id="ws1", template_id="tpl")
        assert result == board
        variables = m.call_args[0][2]
        assert variables == {"name": "New", "boardKind": "PRIVATE",
                             "workspaceId": "ws1", "templateId": "tpl"}

    def test_create_board_defaults(self):
        svc = _svc()
        with patch.object(svc, "_make_request",
                          return_value={"data": {"create_board": {}}}) as m:
            svc.create_board("tok", "New")
        assert m.call_args[0][2]["boardKind"] == "PUBLIC"
        assert m.call_args[0][2]["workspaceId"] is None

    def test_search_items(self):
        svc = _svc()
        items = [{"id": "i1"}]
        with patch.object(svc, "_make_request",
                          return_value={"data": {"items": items}}) as m:
            assert svc.search_items("tok", "bug", board_ids=["b1", "b2"]) == items
        assert m.call_args[0][2] == {"query": "bug", "boardIds": ["b1", "b2"]}

    def test_search_items_no_board_ids(self):
        svc = _svc()
        with patch.object(svc, "_make_request", return_value={"data": {"items": []}}) as m:
            svc.search_items("tok", "bug")
        assert m.call_args[0][2]["boardIds"] == []


# ============================================================================
# Health
# ============================================================================

class TestHealth:
    def test_get_health_status_healthy(self):
        svc = _svc()
        with patch.object(svc, "_make_request", return_value={"data": {"boards": []}}):
            result = svc.get_health_status("tok")
        assert result["status"] == "healthy"
        assert result["details"] == {"data": {"boards": []}}

    def test_get_health_status_unhealthy(self):
        svc = _svc()
        with patch.object(svc, "_make_request", return_value={"errors": [{"message": "x"}]}):
            result = svc.get_health_status("tok")
        assert result["status"] == "unhealthy"

    def test_get_health_status_error(self):
        svc = _svc()
        with patch.object(svc, "_make_request", side_effect=requests.RequestException("api down")):
            result = svc.get_health_status("tok")
        assert result["status"] == "error"
        assert "api down" in result["error"]

    def test_health_check(self):
        svc = _svc()
        result = svc.health_check()
        assert result["healthy"] is True
        assert "healthy" in result["message"]

    def test_health_check_exception_path(self):
        svc = _svc()
        with patch("integrations.monday_service.datetime") as m_dt:
            real_timezone = timezone
            m_dt.timezone = real_timezone
            results = []
            def _now(*args, **kwargs):
                if not results:
                    results.append(1)
                    raise RuntimeError("clock broke")
                return datetime(2026, 1, 1, tzinfo=real_timezone.utc)
            m_dt.now.side_effect = _now
            result = svc.health_check()
        assert result["healthy"] is False
        assert "unhealthy" in result["message"]


# ============================================================================
# Postgres cache sync
# ============================================================================

class TestSyncToPostgresCache:
    @pytest.fixture()
    def db_session(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
        yield session
        session.close()

    def _patch_db(self, session):
        return patch("core.database.SessionLocal", return_value=session)

    def test_sync_success_create(self, db_session):
        svc = _svc()
        boards = [{"id": "1", "items_count": 5}, {"id": "2", "items_count": 3}]
        with patch.object(svc, "get_boards", return_value=boards), \
             patch.object(svc, "get_users", return_value=[{"id": "u1"}]), \
             self._patch_db(db_session):
            result = asyncio.run(svc.sync_to_postgres_cache("tok", "ws-1"))
        assert result == {"success": True, "metrics_synced": 3}
        from core.models import IntegrationMetric
        rows = db_session.query(IntegrationMetric).all()
        assert len(rows) == 3
        assert all(r.workspace_id == "ws-1" for r in rows)
        assert all(r.integration_type == "monday" for r in rows)
        by_key = {r.metric_key: r.value for r in rows}
        assert by_key == {"monday_board_count": 2.0, "monday_item_count": 8.0,
                          "monday_user_count": 1.0}

    def test_sync_success_update_existing(self, db_session):
        from core.models import IntegrationMetric
        db_session.add(IntegrationMetric(
            workspace_id="ws-1", integration_type="monday",
            metric_key="monday_board_count", value=1.0, unit="count"))
        db_session.commit()
        svc = _svc()
        with patch.object(svc, "get_boards", return_value=[{"id": "1", "items_count": 0}]), \
             patch.object(svc, "get_users", return_value=[]), \
             self._patch_db(db_session):
            result = asyncio.run(svc.sync_to_postgres_cache("tok", "ws-1"))
        assert result["success"] is True
        row = db_session.query(IntegrationMetric).filter_by(
            metric_key="monday_board_count").first()
        assert row.value == 1.0
        assert row.last_synced_at is not None

    def test_sync_missing_workspace_id(self, db_session):
        svc = _svc()
        with patch.object(svc, "get_boards", return_value=[]), \
             patch.object(svc, "get_users", return_value=[]), \
             self._patch_db(db_session):
            result = asyncio.run(svc.sync_to_postgres_cache("tok", None))
        assert result == {"success": False, "error": "workspace_id mandatory"}
        from core.models import IntegrationMetric
        assert db_session.query(IntegrationMetric).count() == 0

    def test_sync_db_error_rollback(self, db_session):
        svc = _svc()
        with patch.object(svc, "get_boards", return_value=[{"id": "1", "items_count": 0}]), \
             patch.object(svc, "get_users", return_value=[]), \
             self._patch_db(db_session), \
             patch("core.models.IntegrationMetric",
                   side_effect=RuntimeError("db exploded")):
            result = asyncio.run(svc.sync_to_postgres_cache("tok", "ws-1"))
        assert result["success"] is False
        assert "db exploded" not in result["error"]

    def test_sync_outer_error(self, db_session):
        svc = _svc()
        with patch.object(svc, "get_boards", side_effect=RuntimeError("fetch failed")), \
             self._patch_db(db_session):
            result = asyncio.run(svc.sync_to_postgres_cache("tok", "ws-1"))
        assert result["success"] is False
        assert "fetch failed" not in result["error"]

    def test_full_sync(self, db_session):
        svc = _svc()
        with patch.object(svc, "get_boards", return_value=[]), \
             patch.object(svc, "get_users", return_value=[]), \
             self._patch_db(db_session):
            result = asyncio.run(svc.full_sync("tok", "ws-1"))
        assert result["success"] is True
        assert result["workspace_id"] == "ws-1"
        assert result["postgres_cache"]["success"] is True


# ============================================================================
# Capabilities / execute_operation
# ============================================================================

class TestCapabilities:
    def test_get_capabilities(self):
        caps = _svc().get_capabilities()
        assert caps["required_params"] == ["access_token"]
        assert len(caps["operations"]) == 9
        assert caps["supports_webhooks"] is True

    def test_execute_get_boards(self):
        svc = _svc()
        with patch.object(svc, "get_boards", return_value=[{"id": "1"}]) as m:
            result = asyncio.run(svc.execute_operation(
                "get_boards", {"access_token": "tok", "workspace_id": "ws"}))
        assert result == {"success": True, "result": [{"id": "1"}]}
        assert m.call_args[1]["workspace_id"] == "ws"

    def test_execute_get_board(self):
        svc = _svc()
        with patch.object(svc, "get_board", return_value={"id": "b1"}):
            result = asyncio.run(svc.execute_operation(
                "get_board", {"access_token": "tok", "board_id": "b1"}))
        assert result["success"] is True

    def test_execute_get_items(self):
        svc = _svc()
        with patch.object(svc, "get_items", return_value=[]):
            result = asyncio.run(svc.execute_operation(
                "get_items", {"access_token": "tok", "board_id": "b1"}))
        assert result["success"] is True

    def test_execute_create_item(self):
        svc = _svc()
        with patch.object(svc, "create_item", return_value={"id": "i1"}):
            result = asyncio.run(svc.execute_operation(
                "create_item", {"access_token": "tok", "board_id": "b1", "item_name": "T"}))
        assert result["success"] is True

    def test_execute_update_item(self):
        svc = _svc()
        with patch.object(svc, "update_item", return_value={"id": "i1"}):
            result = asyncio.run(svc.execute_operation(
                "update_item", {"access_token": "tok", "item_id": "i1"}))
        assert result["success"] is True

    def test_execute_get_workspaces(self):
        svc = _svc()
        with patch.object(svc, "get_workspaces", return_value=[]):
            result = asyncio.run(svc.execute_operation(
                "get_workspaces", {"access_token": "tok"}))
        assert result["success"] is True

    def test_execute_get_users(self):
        svc = _svc()
        with patch.object(svc, "get_users", return_value=[]):
            result = asyncio.run(svc.execute_operation(
                "get_users", {"access_token": "tok"}))
        assert result["success"] is True

    def test_execute_create_board(self):
        svc = _svc()
        with patch.object(svc, "create_board", return_value={"id": "b2"}):
            result = asyncio.run(svc.execute_operation(
                "create_board", {"access_token": "tok", "name": "N"}))
        assert result["success"] is True

    def test_execute_search_items(self):
        svc = _svc()
        with patch.object(svc, "search_items", return_value=[]):
            result = asyncio.run(svc.execute_operation(
                "search_items", {"access_token": "tok", "query_term": "q"}))
        assert result["success"] is True

    def test_execute_unknown_operation(self):
        svc = _svc()
        result = asyncio.run(svc.execute_operation(
            "nuke_everything", {"access_token": "tok"}))
        assert result["success"] is False
        assert "Unknown operation" in result["error"]

    def test_execute_exception_no_str_leak(self):
        svc = _svc()
        with patch.object(svc, "get_boards", side_effect=RuntimeError("token-secret-99")):
            result = asyncio.run(svc.execute_operation(
                "get_boards", {"access_token": "tok"}))
        assert result["success"] is False
        assert "token-secret-99" not in result["error"]
        assert result["error"]  # generic message present
