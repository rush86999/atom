# -*- coding: utf-8 -*-
"""Coverage wave 101 — integrations/zoho_projects_service (ZohoProjectsService).

Standalone, fully mocked (httpx.AsyncClient methods + httpx.Response objects
+ patched SessionLocal), zero network, zero LLM spend. Follows wave-97 zoho
books conventions.

Covers: __init__ (config + env fallbacks), get_capabilities, health_check
(token present/absent), execute_operation (get_portals / param-token path /
unsupported / inner-exception -> generic envelope), get_portals / get_projects
/ get_tasks (success + error -> []), get_all_active_tasks (loop, limit break,
project_name injection, empty, exception -> []), create_task (success / error
-> 500 generic), sync_to_postgres_cache (with + without portal_id, existing
row update, phantom `tenant_id` column RED, inner rollback generic, outer
error generic), full_sync.

Bugs fixed (TDD RED -> GREEN):
- sync_to_postgres_cache used `tenant_id=...` in filter_by + IntegrationMetric(
  tenant_id=...) but the model declares no `tenant_id` column (phantom column)
  -> TypeError/AttributeError on every sync. Now `workspace_id=...`.
- execute_operation leaked str(exc); now generic envelope.
- sync_to_postgres_cache inner/outer error paths leaked str(e); now generic.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from integrations.zoho_projects_service import ZohoProjectsService


def _svc(config=None):
    return ZohoProjectsService(tenant_id="t1", config=config or {})


def _resp(status=200, payload=None):
    return httpx.Response(status, json=payload if payload is not None else {},
                          request=httpx.Request("GET", "http://x"))


@pytest.fixture()
def db_session_factory():
    engine = create_engine("sqlite://")
    from core.models import Base
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


class TestInit:
    def test_config_passthrough(self, monkeypatch):
        monkeypatch.delenv("ZOHO_CLIENT_ID", raising=False)
        monkeypatch.delenv("ZOHO_CLIENT_SECRET", raising=False)
        svc = _svc({"client_id": "cid", "client_secret": "cs"})
        assert svc.client_id == "cid"
        assert svc.client_secret == "cs"
        assert svc.base_url == "https://projectsapi.zoho.com/restapi/v1"
        assert svc.tenant_id == "t1"

    def test_env_fallbacks(self, monkeypatch):
        monkeypatch.setenv("ZOHO_CLIENT_ID", "env-cid")
        monkeypatch.setenv("ZOHO_CLIENT_SECRET", "env-cs")
        svc = ZohoProjectsService()
        assert svc.client_id == "env-cid"
        assert svc.client_secret == "env-cs"


class TestCapabilities:
    def test_operations(self):
        caps = _svc().get_capabilities()
        assert caps["operations"] == ['get_portals', 'get_projects', 'get_tasks', 'create_task']
        assert caps["required_params"] == ["access_token"]
        assert caps["supports_webhooks"] is False
        assert caps["rate_limits"] == {"requests_per_minute": 100}


class TestHealthCheck:
    def test_healthy_with_token(self):
        out = _svc({"access_token": "tok"}).health_check()
        assert out["healthy"] is True
        assert out["message"] == "connected"
        assert "last_check" in out
        assert out["base_url"] == "https://projectsapi.zoho.com/restapi/v1"

    def test_unhealthy_without_token(self):
        out = _svc().health_check()
        assert out["healthy"] is False
        assert "no access token" in out["message"]


class TestExecuteOperation:
    async def test_get_portals_op(self):
        svc = _svc()
        svc.get_portals = AsyncMock(return_value=[{"portal_id": "p1"}])
        out = await svc.execute_operation("get_portals", {"access_token": "tok"})
        assert out["success"] is True
        assert out["result"] == [{"portal_id": "p1"}]
        svc.get_portals.assert_awaited_once_with("tok")

    async def test_get_portals_op_falls_back_to_self_token(self):
        svc = _svc({"access_token": "self-tok"})
        svc.get_portals = AsyncMock(return_value=[])
        out = await svc.execute_operation("get_portals", {})
        assert out["success"] is True
        svc.get_portals.assert_awaited_once_with("self-tok")

    async def test_unsupported_operation(self):
        out = await _svc().execute_operation("nope", {})
        assert out["success"] is False
        assert "Unsupported operation" in out["error"]
        assert 'get_portals' in out["supported"]

    async def test_inner_exception_generic_envelope(self):
        """RED: exception path leaked str(exc); must be generic."""
        svc = _svc()
        svc.get_portals = AsyncMock(side_effect=RuntimeError("secret-detail"))
        out = await svc.execute_operation("get_portals", {"access_token": "tok"})
        assert out["success"] is False
        assert "secret-detail" not in out["error"]
        assert out["error"] == "Zoho Projects operation failed"


class TestGetPortals:
    async def test_success(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(200, {"portals": [{"id": "p1"}]}))
        out = await svc.get_portals("tok")
        assert out == [{"id": "p1"}]
        assert svc.client.get.call_args.kwargs["headers"] == {"Authorization": "Zoho-oauthtoken tok"}

    async def test_error_returns_empty(self):
        svc = _svc()
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_portals("tok") == []

    async def test_http_500_returns_empty(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(500, {}))
        assert await svc.get_portals("tok") == []


class TestGetProjects:
    async def test_success(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(200, {"projects": [{"id_string": "pr1"}]}))
        out = await svc.get_projects("tok", "portal1")
        assert out == [{"id_string": "pr1"}]
        url = svc.client.get.call_args.args[0]
        assert url.endswith("/portal/portal1/projects/")

    async def test_error_returns_empty(self):
        svc = _svc()
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_projects("tok", "portal1") == []


class TestGetTasks:
    async def test_success(self):
        svc = _svc()
        svc.client.get = AsyncMock(return_value=_resp(200, {"tasks": [{"id": "tk1"}]}))
        out = await svc.get_tasks("tok", "portal1", "pr1")
        assert out == [{"id": "tk1"}]
        url = svc.client.get.call_args.args[0]
        assert url.endswith("/portal/portal1/projects/pr1/tasks/")

    async def test_error_returns_empty(self):
        svc = _svc()
        svc.client.get = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_tasks("tok", "portal1", "pr1") == []


class TestGetAllActiveTasks:
    async def test_gathers_across_projects_with_project_name(self):
        svc = _svc()
        svc.get_projects = AsyncMock(return_value=[
            {"id_string": "pr1", "name": "Alpha"},
            {"id_string": "pr2", "name": "Beta"},
        ])
        svc.get_tasks = AsyncMock(side_effect=[
            [{"id": "t1"}, {"id": "t2"}],
            [{"id": "t3"}],
        ])
        out = await svc.get_all_active_tasks("tok", "portal1", limit=50)
        assert [t["id"] for t in out] == ["t1", "t2", "t3"]
        assert out[0]["project_name"] == "Alpha"
        assert out[2]["project_name"] == "Beta"
        assert svc.get_tasks.await_args_list[1].args == ("tok", "portal1", "pr2")

    async def test_limit_breaks_early(self):
        svc = _svc()
        svc.get_projects = AsyncMock(return_value=[
            {"id_string": "pr1", "name": "Alpha"},
            {"id_string": "pr2", "name": "Beta"},
        ])
        svc.get_tasks = AsyncMock(return_value=[{"id": "t1"}, {"id": "t2"}, {"id": "t3"}])
        out = await svc.get_all_active_tasks("tok", "portal1", limit=2)
        assert len(out) == 2
        assert svc.get_tasks.await_count == 1

    async def test_empty_projects(self):
        svc = _svc()
        svc.get_projects = AsyncMock(return_value=[])
        assert await svc.get_all_active_tasks("tok", "portal1") == []

    async def test_exception_returns_empty(self):
        svc = _svc()
        svc.get_projects = AsyncMock(side_effect=httpx.ConnectError("net"))
        assert await svc.get_all_active_tasks("tok", "portal1") == []


class TestCreateTask:
    async def test_success(self):
        svc = _svc()
        svc.client.post = AsyncMock(return_value=_resp(201, {"tasks": [{"id": "tk9"}]}))
        out = await svc.create_task("tok", "portal1", "pr1", {"name": "Do thing"})
        assert out == {"id": "tk9"}
        assert svc.client.post.call_args.kwargs["json"] == {"name": "Do thing"}

    async def test_error_500_generic(self):
        svc = _svc()
        svc.client.post = AsyncMock(side_effect=httpx.ConnectError("net"))
        with pytest.raises(HTTPException) as ei:
            await svc.create_task("tok", "portal1", "pr1", {})
        assert ei.value.status_code == 500
        assert ei.value.detail == "Zoho Task creation failed"
        assert "net" not in ei.value.detail


class TestSyncToPostgresCache:
    async def test_success_with_portal_id(self, db_session_factory):
        """RED: used phantom `tenant_id` column on IntegrationMetric; sync
        must persist rows under workspace_id."""
        svc = _svc()
        svc.get_projects = AsyncMock(return_value=[
            {"id_string": "pr1"}, {"id_string": "pr2"},
        ])
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("w1", "tok", "portal1")
        assert out["success"] is True
        assert out["metrics_synced"] == 1
        svc.get_projects.assert_awaited_once_with("tok", "portal1")
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 1
        assert rows[0].metric_key == "zoho_projects_project_count"
        assert rows[0].value == 2.0
        assert rows[0].unit == "count"
        assert rows[0].workspace_id == "w1"
        assert rows[0].integration_type == "zoho_projects"
        db.close()

    async def test_success_without_portal_id(self, db_session_factory):
        svc = _svc()
        svc.get_projects = AsyncMock()
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("w1", "tok")
        assert out["success"] is True
        assert out["metrics_synced"] == 1
        svc.get_projects.assert_not_awaited()
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert rows[0].value == 0.0
        db.close()

    async def test_existing_row_updated(self, db_session_factory):
        svc = _svc()
        svc.get_projects = AsyncMock(return_value=[{"id_string": "pr1"}])
        with patch("core.database.SessionLocal", db_session_factory):
            await svc.sync_to_postgres_cache("w1", "tok", "portal1")
            await svc.sync_to_postgres_cache("w1", "tok", "portal1")
        db = db_session_factory()
        from core.models import IntegrationMetric
        rows = db.query(IntegrationMetric).all()
        assert len(rows) == 1
        assert rows[0].last_synced_at is not None
        db.close()

    async def test_portal_fetch_exception_continues_with_zero(self, db_session_factory):
        """The inner portal fetch is best-effort: an exception must not fail
        the sync; project count stays 0."""
        svc = _svc()
        svc.get_projects = AsyncMock(side_effect=RuntimeError("portal-secret"))
        with patch("core.database.SessionLocal", db_session_factory):
            out = await svc.sync_to_postgres_cache("w1", "tok", "portal1")
        assert out["success"] is True
        assert out["metrics_synced"] == 1
        db = db_session_factory()
        from core.models import IntegrationMetric
        assert db.query(IntegrationMetric).first().value == 0.0
        db.close()

    async def test_inner_error_rollback_generic(self):
        """RED: inner error path leaked str(e); must be generic."""
        svc = _svc()

        class Boom:
            def __init__(self, *a, **k):
                pass

            def query(self, *a, **k):
                raise RuntimeError("db-explode-detail")

            def add(self, *a, **k):
                pass

            def commit(self):
                pass

            def rollback(self):
                pass

            def close(self):
                pass

        with patch("core.database.SessionLocal", Boom):
            out = await svc.sync_to_postgres_cache("w1", "tok")
        assert out["success"] is False
        assert "db-explode-detail" not in out["error"]
        assert out["error"] == "Zoho Projects metrics sync failed"

    async def test_outer_error_generic(self):
        """RED: outer error path leaked str(e); must be generic."""
        svc = _svc()

        class Explode:
            def query(self, *a, **k):
                raise RuntimeError("session-secret")

        with patch("core.database.SessionLocal", lambda: Explode()):
            out = await svc.sync_to_postgres_cache("w1", "tok")
        assert out["success"] is False
        assert "session-secret" not in out["error"]
        assert out["error"] == "Zoho Projects PostgreSQL cache sync failed"


class TestFullSync:
    async def test_success(self):
        svc = _svc()
        svc.sync_to_postgres_cache = AsyncMock(return_value={"success": True, "metrics_synced": 1})
        out = await svc.full_sync("w1", "tok", "portal1")
        assert out["success"] is True
        assert out["workspace_id"] == "w1"
        assert out["postgres_cache"]["success"] is True
        assert "timestamp" in out
