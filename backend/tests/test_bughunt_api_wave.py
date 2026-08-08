# -*- coding: utf-8 -*-
"""
Bug-hunt wave — api/mobile_workflows.py, api/operations_api.py, api/tools.py,
api/line_routes.py (TDD RED->GREEN).

Bugs (all reproduced RED before the minimal source fix):
1.  mobile_workflows: GET /api/mobile/workflows/search shadowed by
    /{workflow_id} (registration order) — search endpoint unreachable.
2.  mobile_workflows: execution details read nonexistent `triggered_by`
    column -> 500 on every run.
3.  mobile_workflows: search returned `Workflow.category`/`Workflow.tags`
    (columns don't exist) -> 500 on any search hit.
4.  mobile_workflows: cancel ownership check trusted the spoofable
    `user_id` query param (IDOR — cancel anyone's execution).
5.  mobile_workflows: workflows.json keys on `workflow_id`, code read `id`
    -> 44/48 workflows unresolvable (details/trigger 404).
6.  operations_api: str(e) leak in dashboard + simulate error paths.
7.  operations_api: GET /dashboard has no auth dependency (anonymous).
8.  tools: get_tool not-found re-wrapped as 500 (own HTTPException caught).
9.  tools: short search query re-wrapped as 500 instead of 422.
10. tools: all /api/tools endpoints anonymous.
11. line_routes: profile ownership check used nonexistent
    `current_user.is_superuser` -> 500 instead of 403 on foreign access.
12. line_routes: send-message/send-messages/send-quick-reply/send-template
    have no auth (anonymous outbound messaging).
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
from core.models import Tenant, User, Workflow, WorkflowExecution, WorkflowStepExecution

TABLES = [
    "tenants", "users", "workspaces", "workflows", "workflow_executions",
    "workflow_step_executions", "analytics_workflow_logs", "boards",
    "board_columns", "board_tasks",
]


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Base.metadata.tables[n] for n in TABLES if n in Base.metadata.tables],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def _seed_tenant_user(db, user_id="user-1", role="member", email="u1@x.com"):
    if not db.query(Tenant).filter(Tenant.id == "t1").first():
        db.add(Tenant(id="t1", name="T", subdomain="t-default"))
    db.add(User(
        id=user_id, tenant_id="t1", email=email,
        first_name="A", last_name="B", hashed_password="pw",
        role=role, status="active",
    ))
    db.commit()


def _app_for(router_module, db, holder, auth_required=True):
    app = FastAPI()
    app.include_router(router_module.router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if auth_required:
        def override_user():
            return SimpleNamespace(id=holder["user_id"], role=holder.get("role", "member"))
        from core.auth import get_current_user as auth_current_user
        from core.security_dependencies import get_current_user as security_current_user
        app.dependency_overrides[auth_current_user] = override_user
        app.dependency_overrides[security_current_user] = override_user
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, holder


# =============================================================================
# api/mobile_workflows.py
# =============================================================================

@pytest.fixture()
def mw_client(db_session):
    from api import mobile_workflows
    _seed_tenant_user(db_session)
    yield from _app_for(mobile_workflows, db_session, {"user_id": "user-1"})


def _execution(db, exec_id="exec-1", workflow_id="wf-1", status="running", user_id="user-1"):
    db.add(WorkflowExecution(
        execution_id=exec_id, workflow_id=workflow_id, status=status,
        user_id=user_id, input_data=None,
    ))
    db.commit()


class TestMobileWorkflowsBugs:
    def test_search_not_shadowed_by_workflow_id_route(self, mw_client):
        """B1: /search is unreachable — captured by /{workflow_id}."""
        c, _ = mw_client
        resp = c.get("/api/mobile/workflows/search", params={"query": "email"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_execution_details_do_not_500_on_missing_triggered_by(self, mw_client, db_session):
        """B2: details read nonexistent `triggered_by` -> AttributeError 500."""
        _execution(db_session)
        c, _ = mw_client
        resp = c.get("/api/mobile/workflows/executions/exec-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "exec-1"
        assert body["triggered_by"] == "user-1"

    def test_cancel_foreign_execution_forbidden(self, mw_client, db_session):
        """B4: attacker passes victim's user_id in query -> must NOT cancel."""
        _execution(db_session, exec_id="exec-2", user_id="user-2")
        c, _ = mw_client
        resp = c.post("/api/mobile/workflows/executions/exec-2/cancel", params={"user_id": "user-2"})
        assert resp.status_code == 403
        assert db_session.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == "exec-2"
        ).first().status == "running"

    def test_cancel_own_execution_ok(self, mw_client, db_session):
        _execution(db_session, exec_id="exec-3", user_id="user-1")
        c, _ = mw_client
        with patch("core.workflow_engine.get_workflow_engine") as get_engine:
            engine = MagicMock()
            engine.cancel_execution = AsyncMock(return_value=True)
            get_engine.return_value = engine
            resp = c.post("/api/mobile/workflows/executions/exec-3/cancel", params={"user_id": "user-1"})
        assert resp.status_code == 200
        assert db_session.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == "exec-3"
        ).first().status == "cancelled"

    def test_search_workflows_returns_rows_without_500(self, mw_client, db_session):
        """B3: Workflow has no category/tags columns -> AttributeError 500."""
        db_session.add(Workflow(
            id="wf-1", name="Email Blast", description="send emails",
            tenant_id="t1", status="active", configuration={"category": "marketing"},
        ))
        db_session.commit()
        c, _ = mw_client
        resp = c.get("/api/mobile/workflows/search", params={"query": "email"})
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["id"] == "wf-1"
        assert rows[0]["name"] == "Email Blast"

    def test_workflow_definition_resolves_workflow_id_key(self, mw_client):
        """B5: workflows.json entries key on `workflow_id`, code matched `id`."""
        with open("workflows.json") as f:
            entries = json.load(f)
        wid = next(w["workflow_id"] for w in entries if "workflow_id" in w)
        c, _ = mw_client
        resp = c.get(f"/api/mobile/workflows/{wid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == wid

    def test_workflow_list_uses_workflow_id_key(self, mw_client):
        """B5b: list grouped executions by workflow_id key, not missing id."""
        with open("workflows.json") as f:
            entries = json.load(f)
        wid = next(w["workflow_id"] for w in entries if "workflow_id" in w)
        c, _ = mw_client
        resp = c.get("/api/mobile/workflows")
        assert resp.status_code == 200
        ids = [w["id"] for w in resp.json()]
        assert wid in ids


# =============================================================================
# api/operations_api.py
# =============================================================================

@pytest.fixture()
def ops_client(db_session):
    from api import operations_api
    _seed_tenant_user(db_session)
    yield from _app_for(operations_api, db_session, {"user_id": "user-1"})


@pytest.fixture()
def ops_anon_client(db_session):
    from api import operations_api
    yield from _app_for(operations_api, db_session, {"user_id": "user-1"}, auth_required=False)


class TestOperationsApiBugs:
    def test_dashboard_requires_auth(self, ops_anon_client):
        """B7: dashboard is anonymous today."""
        c, _ = ops_anon_client
        resp = c.get("/api/operations/dashboard")
        assert resp.status_code == 401

    def test_dashboard_error_message_does_not_leak_str_e(self, ops_client):
        """B6: exception detail leaked into the client response."""
        c, _ = ops_client
        with patch("api.operations_api.business_health_service.get_health_metrics",
                   side_effect=RuntimeError("sekrit-internal-detail")):
            resp = c.get("/api/operations/dashboard")
        assert resp.status_code == 500
        assert "sekrit-internal-detail" not in resp.text

    def test_simulate_error_message_does_not_leak_str_e(self, ops_client):
        c, _ = ops_client
        with patch("api.operations_api.business_health_service.simulate_decision",
                   side_effect=RuntimeError("sekrit-sim-detail")):
            resp = c.post(
                "/api/operations/simulate",
                json={"decision_type": "pricing", "parameters": {"price": 10}},
            )
        assert resp.status_code == 500
        assert "sekrit-sim-detail" not in resp.text


# =============================================================================
# api/tools.py
# =============================================================================

@pytest.fixture()
def tools_client(db_session):
    from api import tools as tools_module
    _seed_tenant_user(db_session)
    yield from _app_for(tools_module, db_session, {"user_id": "user-1"})


@pytest.fixture()
def tools_anon_client(db_session):
    from api import tools as tools_module
    yield from _app_for(tools_module, db_session, {"user_id": "user-1"}, auth_required=False)


class TestToolsBugs:
    def test_get_missing_tool_404_not_500(self, tools_client):
        """B8: not_found_error caught by except Exception -> 500."""
        c, _ = tools_client
        resp = c.get("/api/tools/definitely-not-a-tool")
        assert resp.status_code == 404

    def test_short_search_query_422_not_500(self, tools_client):
        """B9: validation_error caught by except Exception -> 500."""
        c, _ = tools_client
        resp = c.get("/api/tools/search", params={"query": "a"})
        assert resp.status_code == 422

    def test_tools_list_requires_auth(self, tools_anon_client):
        """B10: anonymous /api/tools works today."""
        c, _ = tools_anon_client
        assert c.get("/api/tools").status_code == 401

    def test_tool_detail_requires_auth(self, tools_anon_client):
        c, _ = tools_anon_client
        assert c.get("/api/tools/some-tool").status_code == 401


# =============================================================================
# api/line_routes.py
# =============================================================================

@pytest.fixture()
def line_client(db_session):
    from api import line_routes
    _seed_tenant_user(db_session, user_id="user-1", email="u1@x.com")
    _seed_tenant_user(db_session, user_id="user-2", role="member", email="u2@x.com")
    yield from _app_for(line_routes, db_session, {"user_id": "user-1"})


@pytest.fixture()
def line_anon_client(db_session):
    from api import line_routes
    _seed_tenant_user(db_session)
    yield from _app_for(line_routes, db_session, {"user_id": "user-1"}, auth_required=False)


class TestLineRoutesBugs:
    def test_foreign_profile_403_not_500(self, line_client):
        """B11: is_superuser doesn't exist -> AttributeError -> 500."""
        c, _ = line_client
        with patch("api.line_routes.line_adapter.get_user_profile",
                   new=AsyncMock(return_value={"ok": True, "profile": {"id": "LINE1"}})):
            resp = c.get("/api/line/user/user-2/profile")
        assert resp.status_code == 403

    def test_send_message_requires_auth(self, line_anon_client):
        """B12: anonymous outbound messaging."""
        c, _ = line_anon_client
        resp = c.post("/api/line/send-message", json={"to": "U1", "text": "spam"})
        assert resp.status_code == 401

    def test_send_messages_requires_auth(self, line_anon_client):
        c, _ = line_anon_client
        resp = c.post("/api/line/send-messages", json={"to": "U1", "messages": [{"type": "text", "text": "x"}]})
        assert resp.status_code == 401

    def test_send_quick_reply_requires_auth(self, line_anon_client):
        c, _ = line_anon_client
        resp = c.post("/api/line/send-quick-reply", json={"to": "U1", "text": "x", "quick_reply_items": []})
        assert resp.status_code == 401

    def test_send_template_requires_auth(self, line_anon_client):
        c, _ = line_anon_client
        resp = c.post("/api/line/send-template", json={"to": "U1", "alt_text": "x", "template": {}})
        assert resp.status_code == 401


# =============================================================================
# Late additions (found during coverage push — RED reproduced before fixes)
# =============================================================================

class TestLateBugs:
    def test_mobile_details_not_found_is_404_not_500(self, db_session):
        """Broad except swallowed not_found_error -> every 404 became 500."""
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        c, _ = next(iter(()), (None, None)) or (None, None)
        app = FastAPI()
        app.include_router(mobile_workflows.router)

        def override_db():
            yield db_session

        app.dependency_overrides[get_db] = override_db

        def override_user():
            return SimpleNamespace(id="user-1", role="member")

        from core.auth import get_current_user as auth_current_user
        from core.security_dependencies import get_current_user as security_current_user
        app.dependency_overrides[auth_current_user] = override_user
        app.dependency_overrides[security_current_user] = override_user
        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.get("/api/mobile/workflows/executions/nope").status_code == 404
            assert client.get("/api/mobile/workflows/no-such-wf/executions").status_code == 404

    def test_schedule_missing_config_is_400_not_500(self, tmp_path, monkeypatch):
        """schedule_workflow except Exception swallowed its own 400."""
        from core import workflow_endpoints as we
        wf_file = tmp_path / "workflows.json"
        with open(wf_file, "w") as f:
            json.dump([{"id": "wf-1", "name": "N", "description": "d", "version": "1",
                        "nodes": [], "connections": [], "triggers": [], "enabled": True}], f)
        monkeypatch.setattr(we, "WORKFLOWS_FILE", str(wf_file))
        app = FastAPI()
        app.include_router(we.router, prefix="/api/v1/workflows")

        def _fake_user():
            return SimpleNamespace(id="u1", role="team_lead")

        from core.auth import get_current_user as auth_current_user
        app.dependency_overrides[auth_current_user] = _fake_user
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/api/v1/workflows/workflows/wf-1/schedule", json={})
        assert resp.status_code == 400

    def test_tools_static_routes_not_shadowed(self, db_session):
        """/search, /stats, /categories were shadowed by /{name} -> 404s."""
        from api import tools as tools_module
        from tools.registry import get_tool_registry
        _seed_tenant_user(db_session)
        registry = MagicMock()
        registry.get_stats.return_value = {"total": 1, "categories": {}, "complexity": {}, "maturity": {}}
        registry.search.return_value = []
        registry.list_all.return_value = []
        app = FastAPI()
        app.include_router(tools_module.router)

        def override_db():
            yield db_session

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_tool_registry] = lambda: registry

        def override_user():
            return SimpleNamespace(id="user-1", role="member")

        from core.auth import get_current_user as auth_current_user
        from core.security_dependencies import get_current_user as security_current_user
        app.dependency_overrides[auth_current_user] = override_user
        app.dependency_overrides[security_current_user] = override_user
        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.get("/api/tools/search", params={"query": "ab"}).status_code == 200
            assert client.get("/api/tools/stats").status_code == 200
            assert client.get("/api/tools/categories").status_code == 200

    def test_create_trace_stream_id_matches_params(self, db_session):
        """stream id emitted execution_id/session_id swapped vs signature."""
        from core.workflow_debugger import WorkflowDebugger
        d = WorkflowDebugger(db_session)
        sid = d.create_trace_stream("sess-1", "exec-1")
        assert sid.startswith("trace_sess-1_exec-1_")
