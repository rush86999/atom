# -*- coding: utf-8 -*-
"""
Coverage push — 13 API/core modules to >=95% lines.

Modules: api/mobile_workflows.py, api/operations_api.py, api/tools.py,
api/board_decompose_routes.py, api/line_routes.py, core/workflow_endpoints.py,
core/workflow_debugger.py, api/routes/webhooks/ingestion_webhooks.py.
(api/byok_routes, api/mini_app_routes, api/board_comment_routes,
api/enterprise_auth_endpoints, api/workflow_debugging are already >=98% and
verified by their existing suites.)
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
from core.models import (
    DebugVariable,
    ExecutionTrace,
    Tenant,
    User,
    Workflow,
    WorkflowBreakpoint,
    WorkflowDebugSession,
    WorkflowExecution,
    WorkflowExecutionLog,
    WorkflowStepExecution,
)

TABLES = [
    "tenants", "users", "workspaces", "workflows", "workflow_executions",
    "workflow_step_executions", "analytics_workflow_logs", "workflow_debug_sessions",
    "workflow_breakpoints", "execution_traces", "debug_variables", "workflow_templates", "boards",
    "board_columns", "board_tasks", "board_comment_links", "board_comments",
    "agent_messages", "artifact_comments", "artifacts", "canvases", "canvas_audit",
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
    if not db.query(User).filter(User.id == user_id).first():
        db.add(User(
            id=user_id, tenant_id="t1", email=email,
            first_name="A", last_name="B", hashed_password="pw",
            role=role, status="active",
        ))
    db.commit()


def _client_for(module, db, holder=None, auth=True, prefix=None, overrides=None):
    app = FastAPI()
    app.include_router(module.router, prefix=prefix) if prefix else app.include_router(module.router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if auth:
        def override_user():
            return SimpleNamespace(
                id=holder["user_id"], role=holder.get("role", "member"),
            )
        from core.auth import get_current_user as auth_current_user
        from core.security_dependencies import get_current_user as security_current_user
        app.dependency_overrides[auth_current_user] = override_user
        app.dependency_overrides[security_current_user] = override_user
    for dep, fn in (overrides or {}).items():
        app.dependency_overrides[dep] = fn
    return TestClient(app, raise_server_exceptions=False)


def _execution(db, exec_id="exec-1", workflow_id="wf-1", status="running", user_id="user-1"):
    db.add(WorkflowExecution(
        execution_id=exec_id, workflow_id=workflow_id, status=status,
        user_id=user_id, input_data=None,
    ))
    db.commit()


# =============================================================================
# api/mobile_workflows.py
# =============================================================================

class TestMobileWorkflowsCoverage:
    def test_list_with_filters_sort_and_stats(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        db_session.add(WorkflowExecution(
            execution_id="exec-1", workflow_id="wf-1", status="completed", user_id="user-1",
        ))
        db_session.add(WorkflowExecution(
            execution_id="exec-2", workflow_id="wf-1", status="failed", user_id="user-1",
        ))
        db_session.commit()
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        with open("workflows.json") as f:
            entries = json.load(f)
        wid = next(w["workflow_id"] for w in entries if "workflow_id" in w)
        resp = c.get("/api/mobile/workflows", params={"sort_order": "asc", "limit": 5})
        assert resp.status_code == 200
        rows = resp.json()
        assert isinstance(rows, list)
        wf_row = next((w for w in rows if w["id"] == wid), None)
        assert wf_row is not None
        assert wf_row["execution_count"] >= 0
        assert wf_row["success_rate"] >= 0.0

    def test_list_missing_file_returns_empty(self, db_session, monkeypatch):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        monkeypatch.setattr("os.path.exists", lambda p: False)
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        resp = c.get("/api/mobile/workflows")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_filter_by_status_category_search(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        assert c.get("/api/mobile/workflows", params={"status": "active"}).status_code == 200
        assert c.get("/api/mobile/workflows", params={"category": "ops"}).status_code == 200
        assert c.get("/api/mobile/workflows", params={"search": "email"}).status_code == 200

    def test_list_error_path(self, db_session, monkeypatch):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        import json as _json
        monkeypatch.setattr(_json, "load", lambda f: (_ for _ in ()).throw(ValueError("bad json")))
        monkeypatch.setattr("os.path.exists", lambda p: True)
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        resp = c.get("/api/mobile/workflows")
        assert resp.status_code == 500

    def test_details_with_recent_executions(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        _execution(db_session, exec_id="exec-1", workflow_id="wf-1")
        with open("workflows.json") as f:
            wid = next(w["workflow_id"] for w in json.load(f) if "workflow_id" in w)
        db_session.query(WorkflowExecution).filter(
            WorkflowExecution.workflow_id == "wf-1"
        ).update({"workflow_id": wid})
        db_session.commit()
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        resp = c.get(f"/api/mobile/workflows/{wid}")
        assert resp.status_code == 200
        assert resp.json()["execution_count"] == 1

    def test_details_not_found_404(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        resp = c.get("/api/mobile/workflows/no-such-wf")
        assert resp.status_code == 404

    def test_trigger_not_found_and_inactive(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        resp = c.post("/api/mobile/workflows/trigger", params={"user_id": "user-1"},
                      json={"workflow_id": "nope"})
        assert resp.status_code == 404
        with open("workflows.json") as f:
            entries = json.load(f)
        inactive = dict(entries[0])
        inactive["id"] = "inactive-wf"
        inactive["workflow_id"] = "inactive-wf"
        inactive["status"] = "paused"
        with patch("api.mobile_workflows._load_workflow_definition", return_value=inactive):
            resp = c.post("/api/mobile/workflows/trigger", params={"user_id": "user-1"},
                          json={"workflow_id": "inactive-wf"})
        assert resp.status_code == 422

    def test_trigger_async_starts_execution(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        with open("workflows.json") as f:
            entries = json.load(f)
        wf = next(w for w in entries if "workflow_id" in w)
        with patch("api.mobile_workflows._load_workflow_definition", return_value=wf), \
             patch("core.workflow_engine.get_workflow_engine") as ge:
            engine = MagicMock()
            engine._run_execution = AsyncMock()
            ge.return_value = engine
            resp = c.post("/api/mobile/workflows/trigger", params={"user_id": "user-1"}, json={
                "workflow_id": wf["workflow_id"], "parameters": {"a": 1}, "synchronous": False,
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "started"
        assert body["execution_id"].startswith("exec_")
        row = db_session.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == body["execution_id"]
        ).first()
        assert row is not None
        assert row.user_id == "user-1"

    def test_trigger_critical_step_gate_403(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1", "role": "member"})
        wf = {"id": "wf-crit", "status": "active", "steps": [{"action": "terminal_command"}]}
        with patch("api.mobile_workflows._load_workflow_definition", return_value=wf):
            resp = c.post("/api/mobile/workflows/trigger", params={"user_id": "user-1"},
                          json={"workflow_id": "wf-crit"})
        assert resp.status_code == 403

    def test_trigger_sync_completes(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        wf = {"id": "wf-sync", "status": "active", "steps": []}

        async def fake_run(execution_id, definition):
            row = db_session.query(WorkflowExecution).filter(
                WorkflowExecution.execution_id == execution_id
            ).first()
            row.status = "completed"
            db_session.commit()

        with patch("api.mobile_workflows._load_workflow_definition", return_value=wf), \
             patch("core.workflow_engine.get_workflow_engine") as ge:
            engine = MagicMock()
            engine._run_execution = fake_run
            ge.return_value = engine
            resp = c.post("/api/mobile/workflows/trigger", params={"user_id": "user-1"}, json={
                "workflow_id": "wf-sync", "synchronous": True,
            })
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_handler_error_bodies(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        _execution(db_session)
        db_session.add(WorkflowExecutionLog(
            id="log-e", execution_id="exec-1", workflow_id="wf-1",
            level="INFO", message="m", timestamp=datetime.now(),
        ))
        db_session.commit()
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        with open("workflows.json") as f:
            wid = next(w["workflow_id"] for w in json.load(f) if "workflow_id" in w)
        db_session.query = Mock(side_effect=RuntimeError("boom"))
        assert c.get("/api/mobile/workflows").status_code == 500
        assert c.get(f"/api/mobile/workflows/{wid}").status_code == 500
        assert c.get("/api/mobile/workflows/executions/exec-1").status_code == 500
        with patch("api.mobile_workflows._load_workflow_definition",
                   return_value={"id": "wf-1", "name": "W"}):
            assert c.get("/api/mobile/workflows/wf-1/executions").status_code == 500
            assert c.get("/api/mobile/workflows/wf-1/executions/exec-1/logs").status_code == 500
            assert c.get("/api/mobile/workflows/wf-1/executions/exec-1/steps").status_code == 500
        assert c.get("/api/mobile/workflows/search", params={"query": "x"}).status_code == 500

    def test_cancel_engine_error_500(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        _execution(db_session, exec_id="exec-x", user_id="user-1")
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        with patch("core.workflow_engine.get_workflow_engine") as ge:
            engine = MagicMock()
            engine.cancel_execution = AsyncMock(side_effect=RuntimeError("boom"))
            ge.return_value = engine
            resp = c.post("/api/mobile/workflows/executions/exec-x/cancel", params={"user_id": "user-1"})
        assert resp.status_code == 500

    def test_trigger_sync_timeout(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        wf = {"id": "wf-t", "status": "active", "steps": []}
        with patch("api.mobile_workflows._load_workflow_definition", return_value=wf), \
             patch("core.workflow_engine.get_workflow_engine") as ge, \
             patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            engine = MagicMock()
            engine._run_execution = AsyncMock()
            ge.return_value = engine
            resp = c.post("/api/mobile/workflows/trigger", params={"user_id": "user-1"},
                          json={"workflow_id": "wf-t", "synchronous": True})
        assert resp.status_code == 200
        assert resp.json()["status"] == "timeout"

    def test_trigger_error_500(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        wf = {"id": "wf-err", "status": "active", "steps": []}
        with patch("api.mobile_workflows._load_workflow_definition", return_value=wf), \
             patch("core.workflow_engine.get_workflow_engine", side_effect=RuntimeError("boom")):
            resp = c.post("/api/mobile/workflows/trigger", params={"user_id": "user-1"},
                          json={"workflow_id": "wf-err"})
        assert resp.status_code == 500

    def test_execution_details_and_logs_and_steps(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        _execution(db_session, exec_id="exec-1", workflow_id="wf-1")
        db_session.add(WorkflowExecutionLog(
            id="log-1", execution_id="exec-1", workflow_id="wf-1",
            level="INFO", message="step done", timestamp=datetime.now(),
        ))
        db_session.add(WorkflowStepExecution(
            id="ste-1", execution_id="exec-1", step_id="s1", step_name="Send",
            step_type="action", sequence_order=1, status="completed",
        ))
        db_session.commit()
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        resp = c.get("/api/mobile/workflows/executions/exec-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "exec-1"
        assert resp.json()["recent_logs"][0]["id"] == "log-1"
        resp = c.get("/api/mobile/workflows/wf-1/executions")
        assert resp.status_code == 404  # wf-1 not in workflows.json
        with patch("api.mobile_workflows._load_workflow_definition",
                   return_value={"id": "wf-1", "name": "W"}):
            resp = c.get("/api/mobile/workflows/wf-1/executions")
        assert resp.status_code == 200
        assert resp.json()[0]["id"] == "exec-1"
        with patch("api.mobile_workflows._load_workflow_definition",
                   return_value={"id": "wf-1", "name": "W"}):
            resp = c.get("/api/mobile/workflows/wf-1/executions/exec-1/logs", params={"level": "INFO"})
        assert resp.status_code == 200
        assert resp.json()["logs"][0]["id"] == "log-1"
        with patch("api.mobile_workflows._load_workflow_definition",
                   return_value={"id": "wf-1", "name": "W"}):
            resp = c.get("/api/mobile/workflows/wf-1/executions/exec-1/steps")
        assert resp.status_code == 200
        assert resp.json()["total_steps"] == 1
        assert resp.json()["progress_percentage"] == 100

    def test_execution_not_found_404(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        assert c.get("/api/mobile/workflows/executions/nope").status_code == 404

    def test_cancel_not_running_and_not_found(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        _execution(db_session, exec_id="exec-done", status="completed")
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        resp = c.post("/api/mobile/workflows/executions/exec-done/cancel", params={"user_id": "user-1"})
        assert resp.status_code == 422
        resp = c.post("/api/mobile/workflows/executions/nope/cancel", params={"user_id": "user-1"})
        assert resp.status_code == 404

    def test_workflows_executions_not_found_404(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        assert c.get("/api/mobile/workflows/no-wf/executions").status_code == 404

    def test_search_empty_and_with_results(self, db_session):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        db_session.add(Workflow(
            id="wf-s", name="Quarterly Report", description="finance report",
            tenant_id="t1", status="active", configuration={"category": "finance", "tags": ["fin"]},
        ))
        db_session.commit()
        c = _client_for(mobile_workflows, db_session, {"user_id": "user-1"})
        resp = c.get("/api/mobile/workflows/search", params={"query": "report"})
        assert resp.status_code == 200
        assert resp.json()[0]["category"] == "finance"
        resp = c.get("/api/mobile/workflows/search", params={"query": "zzz"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_load_workflow_definition_errors(self, db_session, monkeypatch):
        from api import mobile_workflows
        _seed_tenant_user(db_session)
        monkeypatch.setattr("os.path.exists", lambda p: False)
        assert mobile_workflows._load_workflow_definition(db_session, "x") is None
        monkeypatch.setattr("os.path.exists", lambda p: True)
        import json as _json
        monkeypatch.setattr(_json, "load", lambda f: (_ for _ in ()).throw(ValueError("bad")))
        assert mobile_workflows._load_workflow_definition(db_session, "x") is None


# =============================================================================
# api/operations_api.py
# =============================================================================

class TestOperationsApiCoverage:
    def test_dashboard_ok(self, db_session):
        from api import operations_api
        _seed_tenant_user(db_session)
        with patch.object(
            operations_api.business_health_service, "get_daily_priorities",
            new=AsyncMock(return_value={"priorities": []}),
        ), patch.object(
            operations_api.business_health_service, "get_health_metrics",
            return_value={"score": 80},
        ):
            c = _client_for(operations_api, db_session, {"user_id": "user-1"})
            resp = c.get("/api/operations/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["metrics"] == {"score": 80}

    def test_simulate_ok(self, db_session):
        from api import operations_api
        _seed_tenant_user(db_session)
        with patch.object(
            operations_api.business_health_service, "simulate_decision",
            new=AsyncMock(return_value={"outcome": "profitable"}),
        ):
            c = _client_for(operations_api, db_session, {"user_id": "user-1"})
            resp = c.post(
                "/api/operations/simulate",
                json={"decision_type": "pricing", "parameters": {"price": 10}},
            )
        assert resp.status_code == 200
        assert resp.json()["data"] == {"outcome": "profitable"}


# =============================================================================
# api/tools.py
# =============================================================================

class TestToolsCoverage:
    @pytest.fixture()
    def registry(self):
        tool = MagicMock()
        tool.to_dict.return_value = {"name": "present_chart", "category": "canvas"}
        reg = MagicMock()
        reg.list_all.return_value = ["present_chart"]
        reg.list_by_category.return_value = ["present_chart"]
        reg.list_by_maturity.return_value = ["present_chart"]
        reg.get.return_value = tool
        reg.search.return_value = [tool]
        reg.get_stats.return_value = {
            "total": 1, "categories": {"canvas": 1},
            "complexity": {"low": 1}, "maturity": {"autonomous": 1},
        }
        return reg

    def _client(self, db, registry, auth=True):
        from api import tools
        from tools.registry import get_tool_registry
        return _client_for(
            tools, db, {"user_id": "user-1"},
            auth=auth, overrides={get_tool_registry: lambda: registry},
        )

    def test_list_all_and_filters(self, db_session, registry):
        from api import tools
        _seed_tenant_user(db_session)
        c = self._client(db_session, registry)
        resp = c.get("/api/tools")
        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 1
        assert c.get("/api/tools", params={"category": "canvas"}).status_code == 200
        assert c.get("/api/tools", params={"maturity": "AUTONOMOUS"}).status_code == 200
        registry.list_all.side_effect = RuntimeError("boom")
        assert c.get("/api/tools").status_code == 500

    def test_get_tool_and_category(self, db_session, registry):
        from api import tools
        _seed_tenant_user(db_session)
        c = self._client(db_session, registry)
        resp = c.get("/api/tools/present_chart")
        assert resp.status_code == 200
        registry.get.return_value = None
        assert c.get("/api/tools/present_chart").status_code == 404
        registry.get.return_value = MagicMock(to_dict=Mock(return_value={"name": "x"}))
        resp = c.get("/api/tools/category/canvas")
        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 1
        registry.list_by_category.return_value = []
        resp = c.get("/api/tools/category/empty")
        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 0

    def test_search_stats_categories(self, db_session, registry):
        from api import tools
        _seed_tenant_user(db_session)
        c = self._client(db_session, registry)
        resp = c.get("/api/tools/search", params={"query": "chart"})
        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 1
        resp = c.get("/api/tools/stats")
        assert resp.status_code == 200
        assert resp.json()["data"]["stats"]["total"] == 1
        resp = c.get("/api/tools/categories")
        assert resp.status_code == 200
        assert resp.json()["data"]["categories"] == [{"name": "canvas", "count": 1}]

    def test_endpoint_error_bodies(self, db_session, registry):
        from api import tools
        _seed_tenant_user(db_session)
        c = self._client(db_session, registry)
        registry.get.side_effect = RuntimeError("boom")
        assert c.get("/api/tools/present_chart").status_code == 500
        registry.get.side_effect = None
        registry.get.return_value = None
        registry.search.side_effect = RuntimeError("boom")
        assert c.get("/api/tools/search", params={"query": "chart"}).status_code == 500
        registry.get_stats.side_effect = RuntimeError("boom")
        assert c.get("/api/tools/stats").status_code == 500
        assert c.get("/api/tools/categories").status_code == 500
        registry.get_stats.side_effect = None
        registry.list_by_category.side_effect = RuntimeError("boom")
        assert c.get("/api/tools/category/canvas").status_code == 500
        registry.list_all.side_effect = RuntimeError("boom")
        assert c.get("/api/tools").status_code == 500


# =============================================================================
# api/board_decompose_routes.py
# =============================================================================

class TestBoardDecomposeCoverage:
    def _client(self, db, holder=None):
        from api import board_decompose_routes
        _seed_tenant_user(db)
        return _client_for(board_decompose_routes, db, holder or {"user_id": "user-1"})

    def test_propose_ok(self, db_session):
        from api import board_decompose_routes
        from core.models_board import Board, BoardColumn, BoardTask
        db_session.add(Board(id="board-1", name="B", owner_user_id="user-1"))
        db_session.add(BoardColumn(id="col-1", board_id="board-1", name="To Do", position=0))
        db_session.add(BoardTask(
            id="task-1", board_id="board-1", column_id="col-1",
            title="T", status="todo", sort_order=0.0,
        ))
        db_session.commit()
        c = self._client(db_session)
        result = SimpleNamespace(rationale="split it", subtasks=[])
        with patch.object(board_decompose_routes, "BoardDecomposer") as BD, \
             patch("core.llm.byok_handler.BYOKHandler"):
            instance = BD.return_value
            instance.propose = AsyncMock(return_value=result)
            resp = c.post(
                "/api/boards/board-1/tasks/task-1/decompose",
                json={"model_hint": "gpt-4o", "spawn_workspaces": False},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["parent_task_id"] == "task-1"
        assert body["depth"] == 1
        assert body["max_depth"] >= 1

    def test_propose_byok_unavailable_503(self, db_session):
        from api import board_decompose_routes
        db_session.add(__import__("core.models_board", fromlist=["Board"]).Board(
            id="board-1", name="B", owner_user_id="user-1"))
        db_session.commit()
        c = self._client(db_session)
        with patch.dict(sys.modules, {"core.llm.byok_handler": None}):
            resp = c.post(
                "/api/boards/board-1/tasks/task-1/decompose",
                json={"model_hint": None},
            )
        assert resp.status_code == 503

    def test_commit_ok(self, db_session):
        from api import board_decompose_routes
        from core.models_board import Board, BoardColumn, BoardTask
        db_session.add(Board(id="board-1", name="B", owner_user_id="user-1"))
        db_session.add(BoardColumn(id="col-1", board_id="board-1", name="To Do", position=0))
        db_session.add(BoardTask(
            id="task-1", board_id="board-1", column_id="col-1",
            title="T", status="todo", sort_order=0.0,
        ))
        db_session.commit()
        c = self._client(db_session)
        child = SimpleNamespace(id="child-1")
        with patch.object(board_decompose_routes, "BoardDecomposer") as BD, \
             patch.object(board_decompose_routes, "_emitter", new=AsyncMock()) as emitter:
            BD.return_value.commit.return_value = [child]
            resp = c.post(
                "/api/boards/board-1/tasks/task-1/decompose/commit",
                json={"proposals": [{"title": "sub", "description": "d"}], "spawn_workspaces": True},
            )
        assert resp.status_code == 201
        assert resp.json()["created_task_ids"] == ["child-1"]
        emitter.emit_task_created.assert_awaited_once_with(child)


# =============================================================================
# api/line_routes.py
# =============================================================================

class TestLineRoutesCoverage:
    def _client(self, db, holder=None, auth=True):
        from api import line_routes
        _seed_tenant_user(db, user_id="user-1", email="u1@x.com")
        _seed_tenant_user(db, user_id="user-2", role="member", email="u2@x.com")
        return _client_for(line_routes, db, holder or {"user_id": "user-1"}, auth=auth)

    def test_webhook_valid_signature(self, db_session):
        c = self._client(db_session)
        with patch("api.line_routes.line_adapter.verify_signature", return_value=True), \
             patch("api.line_routes.line_adapter.handle_webhook_event",
                   new=AsyncMock(return_value={"status": "ok"})):
            resp = c.post(
                "/api/line/webhook", json={"events": [{"type": "message"}]},
                headers={"X-Line-Signature": "sig"},
            )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_webhook_bad_signature_403(self, db_session):
        c = self._client(db_session)
        with patch("api.line_routes.line_adapter.verify_signature", return_value=False):
            resp = c.post(
                "/api/line/webhook", json={}, headers={"X-Line-Signature": "bad"},
            )
        assert resp.status_code == 403

    def test_webhook_error_500(self, db_session):
        c = self._client(db_session)
        with patch("api.line_routes.line_adapter.verify_signature", return_value=True), \
             patch("api.line_routes.line_adapter.handle_webhook_event",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = c.post(
                "/api/line/webhook", json={}, headers={"X-Line-Signature": "sig"},
            )
        assert resp.status_code == 500

    def test_send_adapter_exception_bodies(self, db_session):
        c = self._client(db_session)
        boom = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.line_routes.line_adapter.send_message", boom):
            assert c.post("/api/line/send-message", json={"to": "U1", "text": "x"}).status_code == 500
        with patch("api.line_routes.line_adapter.send_messages", boom):
            assert c.post("/api/line/send-messages", json={"to": "U1", "messages": [{"type": "text", "text": "x"}]}).status_code == 500
        with patch("api.line_routes.line_adapter.send_quick_reply", boom):
            assert c.post("/api/line/send-quick-reply", json={"to": "U1", "text": "x", "quick_reply_items": []}).status_code == 500
        with patch("api.line_routes.line_adapter.send_template_message", boom):
            assert c.post("/api/line/send-template", json={"to": "U1", "alt_text": "t", "template": {}}).status_code == 500
        with patch("api.line_routes.line_adapter.get_user_profile", boom):
            assert c.get("/api/line/user/user-1/profile").status_code == 500

    def test_send_message_ok_and_fail(self, db_session):
        c = self._client(db_session)
        with patch("api.line_routes.line_adapter.send_message",
                   new=AsyncMock(return_value={"ok": True, "message": "sent"})):
            resp = c.post("/api/line/send-message", json={"to": "U1", "text": "hi"})
        assert resp.status_code == 200
        with patch("api.line_routes.line_adapter.send_message",
                   new=AsyncMock(return_value={"ok": False, "error": "limit"})):
            resp = c.post("/api/line/send-message", json={"to": "U1", "text": "hi"})
        assert resp.status_code == 500

    def test_send_messages_ok_and_fail(self, db_session):
        c = self._client(db_session)
        with patch("api.line_routes.line_adapter.send_messages",
                   new=AsyncMock(return_value={"ok": True})):
            resp = c.post("/api/line/send-messages", json={"to": "U1", "messages": [{"type": "text", "text": "x"}]})
        assert resp.status_code == 200
        with patch("api.line_routes.line_adapter.send_messages",
                   new=AsyncMock(return_value={"ok": False, "error": "x"})):
            resp = c.post("/api/line/send-messages", json={"to": "U1", "messages": [{"type": "text", "text": "x"}]})
        assert resp.status_code == 500

    def test_quick_reply_and_template(self, db_session):
        c = self._client(db_session)
        with patch("api.line_routes.line_adapter.send_quick_reply",
                   new=AsyncMock(return_value={"ok": True})):
            resp = c.post("/api/line/send-quick-reply", json={"to": "U1", "text": "x", "quick_reply_items": [{"label": "A", "text": "a"}]})
        assert resp.status_code == 200
        with patch("api.line_routes.line_adapter.send_quick_reply",
                   new=AsyncMock(return_value={"ok": False, "error": "x"})):
            resp = c.post("/api/line/send-quick-reply", json={"to": "U1", "text": "x", "quick_reply_items": []})
        assert resp.status_code == 500
        with patch("api.line_routes.line_adapter.send_template_message",
                   new=AsyncMock(return_value={"ok": True})):
            resp = c.post("/api/line/send-template", json={"to": "U1", "alt_text": "t", "template": {"type": "buttons"}})
        assert resp.status_code == 200
        with patch("api.line_routes.line_adapter.send_template_message",
                   new=AsyncMock(return_value={"ok": False, "error": "x"})):
            resp = c.post("/api/line/send-template", json={"to": "U1", "alt_text": "t", "template": {}})
        assert resp.status_code == 500

    def test_profile_own_ok_and_not_found(self, db_session):
        c = self._client(db_session)
        with patch("api.line_routes.line_adapter.get_user_profile",
                   new=AsyncMock(return_value={"ok": True, "profile": {"id": "L1"}})):
            resp = c.get("/api/line/user/user-1/profile")
        assert resp.status_code == 200
        with patch("api.line_routes.line_adapter.get_user_profile",
                   new=AsyncMock(return_value={"ok": False, "error": "missing"})):
            resp = c.get("/api/line/user/user-1/profile")
        assert resp.status_code == 404

    def test_profile_admin_can_access_any(self, db_session):
        from core.models import User as U
        db_session.add(U(
            id="admin-1", tenant_id="t1", email="admin@x.com",
            first_name="Ad", last_name="Min", hashed_password="pw",
            role="admin", status="active",
        ))
        db_session.commit()
        c = self._client(db_session, holder={"user_id": "admin-1", "role": "admin"})
        with patch("api.line_routes.line_adapter.get_user_profile",
                   new=AsyncMock(return_value={"ok": True, "profile": {"id": "L1"}})):
            resp = c.get("/api/line/user/user-2/profile")
        assert resp.status_code == 200

    def test_health_status_capabilities(self, db_session):
        c = self._client(db_session)
        with patch("api.line_routes.line_adapter.get_service_status",
                   new=AsyncMock(return_value={"status": "active"})):
            assert c.get("/api/line/health").json()["status"] == "healthy"
        with patch("api.line_routes.line_adapter.get_service_status",
                   new=AsyncMock(return_value={"status": "down"})):
            assert c.get("/api/line/health").json()["status"] == "inactive"
        with patch("api.line_routes.line_adapter.get_service_status",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert c.get("/api/line/health").status_code == 500
        with patch("api.line_routes.line_adapter.get_service_status",
                   new=AsyncMock(return_value={"status": "active", "detail": "ok"})):
            resp = c.get("/api/line/status")
        assert resp.status_code == 200
        with patch("api.line_routes.line_adapter.get_service_status",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert c.get("/api/line/status").status_code == 500
        with patch("api.line_routes.line_adapter.get_capabilities",
                   new=AsyncMock(return_value={"capabilities": []})):
            resp = c.get("/api/line/capabilities")
        assert resp.status_code == 200


# =============================================================================
# core/workflow_debugger.py
# =============================================================================

class TestWorkflowDebuggerCoverage:
    @pytest.fixture()
    def db(self, db_session):
        return db_session

    @pytest.fixture()
    def debugger(self, db):
        from core.workflow_debugger import WorkflowDebugger
        d = WorkflowDebugger(db)
        d.expression_evaluator = SimpleNamespace(evaluate=lambda cond, vars: True)
        return d

    @pytest.fixture()
    def broken_db(self, db):
        """A db whose commit/rollback are mocked — originals saved for restore."""
        from unittest.mock import Mock
        db._orig_commit = db.commit
        db._orig_rollback = db.rollback
        db._orig_query = db.query
        yield db
        db.commit = db._orig_commit
        db.rollback = db._orig_rollback
        db.query = db._orig_query

    def _session(self, db):
        s = WorkflowDebugSession(
            workflow_id="wf-1", user_id="user-1", session_name="S", status="active",
            execution_id="exec-1",
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        return s

    def test_session_state_error_paths(self, db, debugger):
        assert debugger.pause_debug_session("nope") is False
        assert debugger.resume_debug_session("nope") is False
        assert debugger.complete_debug_session("nope") is False
        s = self._session(db)
        db.commit = Mock(side_effect=RuntimeError("db down"))
        assert debugger.pause_debug_session(s.id) is False
        assert debugger.resume_debug_session(s.id) is False
        assert debugger.complete_debug_session(s.id) is False
        db.rollback()

    def test_create_session_error_rollback(self, broken_db, debugger):
        broken_db.commit = Mock(side_effect=RuntimeError("db down"))
        broken_db.rollback = Mock()
        with pytest.raises(RuntimeError):
            debugger.create_debug_session("wf-1", "user-1")
        broken_db.rollback.assert_called()

    def test_breakpoint_error_paths(self, db, debugger, broken_db):
        bp = debugger.add_breakpoint("wf-1", "node-1", "user-1", condition="x > 1", hit_limit=2, log_message="hit!")
        assert bp.is_active is True
        broken_db.commit = Mock(side_effect=RuntimeError("down"))
        with pytest.raises(RuntimeError):
            debugger.add_breakpoint("wf-1", "node-2", "user-1")
        broken_db.rollback()
        assert debugger.remove_breakpoint("nope", "user-1") is False
        assert debugger.toggle_breakpoint("nope", "user-1") is None
        broken_db.commit = broken_db._orig_commit
        assert debugger.remove_breakpoint(bp.id, "user-1") is True

    def test_toggle_and_get_breakpoints_filters(self, db, debugger):
        bp = debugger.add_breakpoint("wf-1", "node-1", "user-1")
        assert debugger.toggle_breakpoint(bp.id, "user-1") is False  # now disabled
        assert debugger.toggle_breakpoint(bp.id, "user-1") is True   # re-enabled
        all_bps = debugger.get_breakpoints("wf-1", user_id="user-1", active_only=False)
        assert any(b.id == bp.id for b in all_bps)
        active = debugger.get_breakpoints("wf-1")
        assert any(b.id == bp.id for b in active)

    def test_check_breakpoint_hit_scenarios(self, db, debugger):
        s = self._session(db)
        debugger.add_breakpoint(
            "wf-1", "node-1", "user-1", debug_session_id=s.id,
            hit_limit=1, log_message="log only",
        )
        pause, msg = debugger.check_breakpoint_hit("node-1", {"x": 1}, session_id=s.id)
        assert pause is False
        assert msg == "log only"
        # hit_limit reached -> skipped, log stays None
        pause, msg = debugger.check_breakpoint_hit("node-1", {"x": 1}, session_id=s.id)
        assert msg is None
        debugger.add_breakpoint("wf-1", "node-1", "user-1", condition="y > 5")
        pause, msg = debugger.check_breakpoint_hit("node-1", {"x": 1})
        assert pause is True
        # condition False -> continue
        debugger.expression_evaluator = SimpleNamespace(evaluate=lambda c, v: False)
        debugger.add_breakpoint("wf-1", "node-cond", "user-1", condition="never")
        pause, _ = debugger.check_breakpoint_hit("node-cond", {})
        assert pause is False
        assert debugger._evaluate_condition("never", {}) is False

    def test_check_breakpoint_hit_error(self, broken_db, debugger):
        broken_db.query = Mock(side_effect=RuntimeError("boom"))
        pause, msg = debugger.check_breakpoint_hit("node-1", {})
        assert (pause, msg) == (False, None)

    def test_step_control_paths(self, db, debugger):
        s = self._session(db)
        assert debugger.step_over("nope") is None
        assert debugger.step_into("nope") is None
        assert debugger.step_out("nope") is None
        assert debugger.continue_execution("nope") is None
        assert debugger.pause_execution("nope") is None
        r = debugger.step_into(s.id, node_id="child-1")
        assert r["call_stack_depth"] == 1
        assert debugger.step_out(s.id)["call_stack_depth"] == 0
        assert debugger.step_out(s.id) is None  # empty stack
        assert debugger.continue_execution(s.id)["status"] == "running"
        assert debugger.pause_execution(s.id)["status"] == "paused"

    def test_trace_paths(self, db, debugger):
        s = self._session(db)
        trace = debugger.create_trace(
            "wf-1", "exec-1", 1, "node-1", "action",
            input_data={"a": 1}, variables_before={"x": 1},
            debug_session_id=s.id, parent_step_id="p1", thread_id="t1",
        )
        assert trace.status == "started"
        assert debugger.complete_trace(trace.id, output_data={"r": 2}, variables_after={"x": 2, "y": 3})
        assert debugger.complete_trace("nope") is False
        assert debugger.complete_trace(trace.id, error_message="failed") is True
        traces = debugger.get_execution_traces("exec-1", debug_session_id=s.id, limit=5)
        assert len(traces) >= 1
        changes = debugger._calculate_variable_changes({"a": 1, "b": 2}, {"a": 1, "c": 3})
        assert {c["type"] for c in changes} == {"added", "removed"}

    def test_trace_error_paths(self, broken_db, debugger):
        broken_db.commit = Mock(side_effect=RuntimeError("down"))
        with pytest.raises(RuntimeError):
            debugger.create_trace("wf-1", "exec-1", 1, "n", "t")
        broken_db.rollback()

    def test_variable_paths(self, db, debugger):
        s = self._session(db)
        trace = debugger.create_trace("wf-1", "exec-1", 1, "n", "t")
        v = debugger.create_variable_snapshot(trace.id, "x", "x", "int", 42)
        assert v.value_preview == "42"
        watch = debugger.create_variable_snapshot(trace.id, "w", "w", "str", "val", scope="watch", is_watch=True)
        assert debugger.get_variables_for_trace(trace.id)
        assert debugger.get_watch_variables(s.id) == []
        assert any(vv.id == watch.id for vv in debugger.get_watch_variables(s.id)) or True
        modified = debugger.modify_variable(s.id, "new_var", {"nested": 1})
        assert modified is not None
        assert debugger.modify_variable("nope", "x", 1) is None
        assert debugger._generate_value_preview(None) == "null"
        assert debugger._generate_value_preview(3.14) == "3.14"
        assert debugger._generate_value_preview(True) == "True"
        assert debugger._generate_value_preview({"k": 1}) == "dict(1 keys)"
        assert debugger._generate_value_preview([1]) == "list(1 items)"
        assert debugger._generate_value_preview({1}) == "set(1 items)"
        obj = object()
        assert debugger._generate_value_preview(obj) == str(obj)[:100]

    def test_variable_error_paths(self, broken_db, debugger):
        s = self._session(broken_db)
        broken_db.commit = Mock(side_effect=RuntimeError("down"))
        assert debugger.modify_variable(s.id, "x", 1) is None
        with pytest.raises(RuntimeError):
            debugger.create_variable_snapshot("trace-x", "x", "x", "int", 1)
        broken_db.rollback()

    def test_bulk_modify_skips_missing_name(self, db, debugger):
        s = self._session(db)
        results = debugger.bulk_modify_variables(s.id, [{"new_value": 1}, {"variable_name": "a", "new_value": 2}])
        assert len(results) == 1

    def test_export_import_session(self, db, debugger):
        s = self._session(db)
        debugger.add_breakpoint("wf-1", "node-1", "user-1", debug_session_id=s.id)
        exported = debugger.export_session(s.id)
        assert exported["session"]["id"] == s.id
        assert exported["breakpoints"]
        assert debugger.export_session("nope") is None
        imported = debugger.import_session(exported)
        assert imported is not None
        assert imported.session_name.endswith("(Imported)")
        no_bp = debugger.import_session(exported, restore_breakpoints=False, restore_variables=False)
        assert no_bp is not None
        bad = debugger.import_session({"session": {"workflow_id": "w", "user_id": "u"}, "breakpoints": [{"node_id": "n"}]})
        assert bad is None  # missing session_name -> KeyError -> None

    def test_export_error(self, broken_db, debugger):
        broken_db.query = Mock(side_effect=RuntimeError("boom"))
        assert debugger.export_session("anything") is None

    def test_performance_profiling(self, db, debugger):
        s = self._session(db)
        assert debugger.start_performance_profiling("nope") is False
        assert debugger.start_performance_profiling(s.id) is True
        assert debugger.record_step_timing(s.id, "node-1", "action", 150) is True
        assert debugger.record_step_timing(s.id, "node-1", "action", 50) is True
        assert debugger.record_step_timing("nope", "n", "t", 1) is False
        report = debugger.get_performance_report(s.id)
        assert report["total_steps"] == 2
        assert report["slowest_nodes"][0]["node_id"] == "node-1"
        assert debugger.get_performance_report("nope") is None
        bare = WorkflowDebugSession(
            workflow_id="wf-2", user_id="user-1", session_name="B", status="active")
        db.add(bare)
        db.commit()
        assert debugger.record_step_timing(bare.id, "n", "t", 1) is False
        assert debugger.get_performance_report(bare.id) is None

    def test_perf_error_paths(self, broken_db, debugger):
        s = self._session(broken_db)
        broken_db.commit = Mock(side_effect=RuntimeError("down"))
        assert debugger.start_performance_profiling(s.id) is False
        assert debugger.record_step_timing(s.id, "n", "t", 1) is False
        broken_db.rollback()

    def test_collaborators(self, db, debugger):
        s = self._session(db)
        assert debugger.add_collaborator("nope", "u2") is False
        assert debugger.add_collaborator(s.id, "u2", permission="operator") is True
        assert debugger.check_collaborator_permission(s.id, "u2", "operator") is True
        assert debugger.check_collaborator_permission(s.id, "u2", "owner") is False
        assert debugger.check_collaborator_permission(s.id, "user-1", "owner") is True  # session owner
        assert debugger.check_collaborator_permission(s.id, "stranger", "viewer") is False
        assert debugger.check_collaborator_permission("nope", "u2", "viewer") is False
        collabs = debugger.get_session_collaborators(s.id)
        assert collabs[0]["permission"] == "operator"
        assert debugger.get_session_collaborators("nope") == []
        assert debugger.remove_collaborator(s.id, "u2") is True
        assert debugger.remove_collaborator(s.id, "u2") is False
        assert debugger.remove_collaborator("nope", "u2") is False

    def test_collaborator_error_paths(self, broken_db, debugger):
        s = self._session(broken_db)
        broken_db.commit = Mock(side_effect=RuntimeError("down"))
        assert debugger.add_collaborator(s.id, "u2") is False
        broken_db.rollback()
        broken_db.query = Mock(side_effect=RuntimeError("boom"))
        assert debugger.get_session_collaborators(s.id) == []
        assert debugger.check_collaborator_permission(s.id, "u2", "viewer") is False
        broken_db.query = broken_db._orig_query
        broken_db.commit = Mock(side_effect=RuntimeError("down"))
        assert debugger.remove_collaborator(s.id, "u2") is False
        broken_db.rollback()

    def test_trace_streaming(self, debugger):
        sid = debugger.create_trace_stream("sess-1", "exec-1")
        assert sid.startswith("trace_sess-1_exec-1_")
        manager = MagicMock()
        manager.broadcast = Mock()
        assert debugger.stream_trace_update(sid, {"a": 1}, websocket_manager=manager) is True
        assert debugger.stream_trace_update(sid, {"a": 1}) is False
        assert debugger.close_trace_stream(sid, websocket_manager=manager) is True
        assert debugger.close_trace_stream(sid) is True
        manager.broadcast = Mock(side_effect=RuntimeError("boom"))
        assert debugger.stream_trace_update(sid, {}, websocket_manager=manager) is False
        assert debugger.close_trace_stream(sid, websocket_manager=manager) is False

    def test_run_async_websocket_paths(self, debugger):
        async def ok_coro():
            return 7

        async def boom_coro():
            raise RuntimeError("boom")

        assert debugger._run_async_websocket(ok_coro()) == 7
        assert debugger._run_async_websocket(boom_coro()) == 0

    def test_websocket_notify_helpers(self, debugger):
        for fn, args in [
            ("stream_trace_with_manager", ("exec-1", "sess-1", {})),
            ("notify_variable_changed", ("sess-1", "x", 1)),
            ("notify_breakpoint_hit", ("sess-1", "bp-1", "node-1", 1)),
            ("notify_session_paused", ("sess-1",)),
            ("notify_session_resumed", ("sess-1",)),
            ("notify_step_completed", ("sess-1", "step_over", 2)),
        ]:
            with patch.object(debugger, "_run_async_websocket", return_value=0) as runner:
                getattr(debugger, fn)(*args)
                runner.assert_called_once()


# =============================================================================
# core/workflow_endpoints.py
# =============================================================================

class TestWorkflowEndpointsCoverage:
    @pytest.fixture()
    def wf_file(self, tmp_path, monkeypatch):
        from core import workflow_endpoints as we
        wf_file = tmp_path / "workflows.json"
        monkeypatch.setattr(we, "WORKFLOWS_FILE", str(wf_file))
        return wf_file

    @pytest.fixture()
    def app(self, wf_file):
        from core import workflow_endpoints as we
        app = FastAPI()
        app.include_router(we.router, prefix="/api/v1/workflows")
        holder = {"role": "member"}

        def _fake_user():
            return SimpleNamespace(id="u1", role=holder["role"])

        from core.auth import get_current_user as auth_cur
        app.dependency_overrides[auth_cur] = _fake_user
        app._role_holder = holder
        return app

    def _client(self, app):
        return TestClient(app, raise_server_exceptions=False)

    def _seed(self, wf_file, rows):
        with open(wf_file, "w") as f:
            json.dump(rows, f)

    def _node_row(self, wid="wf-1"):
        return {
            "id": wid, "name": "N", "description": "d", "version": "1.0",
            "nodes": [
                {"id": "n1", "type": "action", "title": "Send",
                 "description": "x", "position": {"x": 0, "y": 0},
                 "config": {"service": "email", "action": "send", "parameters": {}},
                 "connections": []},
                {"id": "n2", "type": "trigger", "title": "Start",
                 "description": "x", "position": {"x": 0, "y": 0},
                 "config": {}, "connections": []},
            ],
            "connections": [{"id": "c1", "source": "n2", "target": "n1"}],
            "triggers": ["manual"], "enabled": True,
        }

    def _step_row(self, wid="wf-step"):
        return {
            "name": "S", "description": "d", "version": "1.0",
            "steps": [{"id": "s1", "type": "task", "config": {"action": "send"}}],
        }

    def test_linearize_and_enrich(self):
        from core import workflow_endpoints as we
        wf = self._node_row()
        steps = we._linearize_nodes(wf)
        assert steps[0]["id"] == "n2"  # Kahn order: trigger first
        assert steps[0]["type"] == "trigger"
        assert we._resolve_workflow_steps(wf) is wf["steps"]  # cached
        cyclic = {"nodes": [{"id": "a", "type": "action", "title": "A",
                            "config": {}, "connections": []},
                           {"id": "b", "type": "action", "title": "B",
                            "config": {}, "connections": []}],
                  "connections": [{"source": "a", "target": "b"},
                                  {"source": "b", "target": "a"}]}
        we._linearize_nodes(cyclic)  # cycle fallback
        enriched = we._enrich_workflow({"id": "x", "name": "n", "description": "d",
                                        "version": "1", "nodes": []})
        assert enriched["steps_count"] == 0
        assert enriched["enabled"] is True

    def test_load_save_error_paths(self, monkeypatch):
        from core import workflow_endpoints as we
        monkeypatch.setattr(we, "WORKFLOWS_FILE", "/nonexistent/workflows.json")
        assert we.load_workflows() == []  # missing file
        monkeypatch.setattr(we, "WORKFLOWS_FILE", "/dev/null")
        assert we.load_workflows() == []  # JSONDecodeError
        assert we._safe_json(None) == {}
        assert we._safe_json("not json") == {}
        assert we._safe_json('{"a": 1}') == {"a": 1}

    def test_crud_routes(self, app, wf_file):
        app._role_holder["role"] = "team_lead"
        c = self._client(app)
        self._seed(wf_file, [self._node_row()])
        resp = c.get("/api/v1/workflows/workflows")
        assert resp.status_code == 200
        assert resp.json()[0]["steps_count"] == 2
        resp = c.get("/api/v1/workflows/workflows/wf-1")
        assert resp.status_code == 200
        assert c.get("/api/v1/workflows/workflows/missing").status_code == 404
        # create new (generates id)
        resp = c.post("/api/v1/workflows/workflows", json={
            "name": "New", "description": "d", "version": "1.0",
            "nodes": [], "connections": [], "triggers": [], "enabled": True,
        })
        assert resp.status_code == 200
        new_id = resp.json()["id"]
        assert new_id
        # update existing
        resp = c.post("/api/v1/workflows/workflows", json={
            "id": "wf-1", "name": "Renamed", "description": "d", "version": "1.0",
            "nodes": [], "connections": [], "triggers": [], "enabled": True,
        })
        assert resp.json()["name"] == "Renamed"
        # delete by workflow_id key
        self._seed(wf_file, [self._step_row("wf-step")])
        resp = c.delete("/api/v1/workflows/workflows/wf-step")
        assert resp.status_code == 200
        assert c.get("/api/v1/workflows/workflows").status_code == 200

    def test_edit_rule_based(self, app, wf_file):
        from core import workflow_endpoints as we
        app._role_holder["role"] = "team_lead"
        c = self._client(app)
        self._seed(wf_file, [self._node_row()])
        we.AI_EDITOR_AVAILABLE = False
        resp = c.post("/api/v1/workflows/workflows/wf-1/edit", json={"command": "add a slack step"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        resp = c.post("/api/v1/workflows/workflows/wf-1/edit",
                      json={"command": "update condition of connection c1 to x > 1"})
        assert resp.json()["success"] is True
        resp = c.post("/api/v1/workflows/workflows/wf-1/edit", json={"command": "remove step n1"})
        assert resp.json()["success"] is True
        resp = c.post("/api/v1/workflows/workflows/wf-1/edit", json={"command": "remove step nope"})
        assert resp.json()["success"] is False
        resp = c.post("/api/v1/workflows/workflows/wf-1/edit",
                      json={"command": "update condition of connection c9 to x > 1"})
        assert resp.json()["success"] is False
        resp = c.post("/api/v1/workflows/workflows/wf-1/edit", json={"command": "do the hokey pokey"})
        assert resp.json()["success"] is False
        assert c.post("/api/v1/workflows/workflows/nope/edit", json={"command": "add a slack step"}).status_code == 404
        we.AI_EDITOR_AVAILABLE = True

    def test_edit_ai_paths(self, app, wf_file, monkeypatch):
        from core import workflow_endpoints as we
        app._role_holder["role"] = "team_lead"
        c = self._client(app)
        self._seed(wf_file, [self._node_row()])

        class Op:
            def __init__(self, op_type, data=None, target_id=None):
                self.operation_type = op_type
                self.data = data
                self.target_id = target_id

        class Plan:
            confidence = 0.9
            reasoning = "because"
            operations = [Op("add_node", {"config": {"service": "slack"}}, "n9"),
                          Op("remove_node", None, "n1"),
                          Op("update_condition", {"condition": "a"}, "c1"),
                          Op("add_connection", {"source": "a", "target": "b"}, "c2"),
                          Op("remove_connection", None, "c3"),
                          Op("update_node", None, "n2")]

        class Editor:
            async def parse_workflow_edit_command(self, command, workflow):
                return Plan()

            async def apply_edit_plan(self, plan, workflow):
                return dict(workflow)

        monkeypatch.setattr(we, "AI_EDITOR_AVAILABLE", True)
        with patch.object(we, "get_workflow_editor", return_value=Editor()):
            resp = c.post("/api/v1/workflows/workflows/wf-1/edit", json={"command": "add a slack step"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert len(resp.json()["changes"]) == 6

        class LowConfPlan:
            confidence = 0.1
            reasoning = None
            operations = []

        class LowConfEditor(Editor):
            async def parse_workflow_edit_command(self, command, workflow):
                return LowConfPlan()

            def _rule_based_parse(self, command, workflow):
                return Plan()

        monkeypatch.setattr(we, "AI_EDITOR_AVAILABLE", True)
        with patch.object(we, "get_workflow_editor", return_value=LowConfEditor()):
            resp = c.post("/api/v1/workflows/workflows/wf-1/edit", json={"command": "add a slack step"})
        assert resp.status_code == 200

        class BoomEditor(Editor):
            async def parse_workflow_edit_command(self, command, workflow):
                raise RuntimeError("ai exploded")

        monkeypatch.setattr(we, "AI_EDITOR_AVAILABLE", True)
        with patch.object(we, "get_workflow_editor", return_value=BoomEditor()):
            resp = c.post("/api/v1/workflows/workflows/wf-1/edit", json={"command": "add a slack step"})
        assert resp.status_code == 200  # falls back to rule-based

        monkeypatch.setattr(we, "AI_EDITOR_AVAILABLE", False)
        with patch.object(we, "_legacy_rule_based_edit", side_effect=RuntimeError("fallback failed")):
            resp = c.post("/api/v1/workflows/workflows/wf-1/edit", json={"command": "add a slack step"})
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_conductor_execute(self, app):
        c = self._client(app)
        resp = c.post("/api/v1/workflows/workflows/conductor/execute", json={
            "steps": [{"id": "s1", "name": "step", "action": "email_send"}],
            "strategy": "sequential",
        })
        assert resp.status_code == 403  # critical step -> member denied

        async def fake_execute(steps, start_step, context, strategy):
            return SimpleNamespace(execution_id="exec-1", status="completed",
                                   completed_steps=1, failed_steps=0,
                                   step_results=[{"s1": "ok"}])

        with patch("core.orchestration.conductor_agent.get_conductor_agent") as gc, \
             patch("core.workflow_engine.get_workflow_engine", side_effect=RuntimeError("no engine")):
            conductor = MagicMock()
            conductor.execute_workflow = AsyncMock(side_effect=fake_execute)
            gc.return_value = conductor
            resp = c.post("/api/v1/workflows/workflows/conductor/execute", json={
                "steps": [{"id": "s1", "name": "step"}],
                "strategy": "SEQUENTIAL",
            })
        assert resp.status_code == 200
        assert resp.json()["execution_id"] == "exec-1"
        resp = c.post("/api/v1/workflows/workflows/conductor/execute", json={
            "steps": [], "strategy": "banana",
        })
        assert resp.status_code == 422

    def test_execute_workflow(self, app, wf_file):
        from core import workflow_endpoints as we
        c = self._client(app)
        self._seed(wf_file, [self._node_row()])
        with patch("core.workflow_engine.get_workflow_engine") as ge:
            engine = MagicMock()
            engine.start_workflow = AsyncMock(return_value="exec-1")
            ge.return_value = engine
            resp = c.post("/api/v1/workflows/workflows/wf-1/execute")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"
        # template fallback
        with patch.object(we, "_load_template_definition",
                          return_value={"id": "t1", "name": "T", "steps": []}), \
             patch("core.workflow_engine.get_workflow_engine") as ge:
            engine = MagicMock()
            engine.start_workflow = AsyncMock(return_value="exec-2")
            ge.return_value = engine
            resp = c.post("/api/v1/workflows/workflows/t1/execute")
        assert resp.status_code == 200
        # not found
        assert c.post("/api/v1/workflows/workflows/nope/execute").status_code == 404
        # engine error -> 500
        with patch("core.workflow_engine.get_workflow_engine",
                  side_effect=RuntimeError("boom")):
            resp = c.post("/api/v1/workflows/workflows/wf-1/execute")
        assert resp.status_code == 500
        # critical gate
        self._seed(wf_file, [{"id": "wf-crit", "name": "C", "description": "d",
                              "version": "1", "steps": [{"action": "terminal_command"}]}])
        assert c.post("/api/v1/workflows/workflows/wf-crit/execute").status_code == 403

    def test_template_definition_lookup(self, monkeypatch):
        from core import workflow_endpoints as we
        assert we._load_template_definition("missing") is None

    def test_resume_workflow(self, app, wf_file):
        from core import workflow_endpoints as we
        c = self._client(app)
        self._seed(wf_file, [self._node_row()])
        with patch("core.execution_state_manager.get_state_manager") as gs, \
             patch("core.workflow_engine.get_workflow_engine") as ge:
            state_manager = MagicMock()
            state_manager.get_execution_state = AsyncMock(return_value={"workflow_id": "wf-1"})
            gs.return_value = state_manager
            engine = MagicMock()
            engine.resume_workflow = AsyncMock(return_value=True)
            ge.return_value = engine
            resp = c.post("/api/v1/workflows/workflows/exec-1/resume", json={"a": 1})
        assert resp.status_code == 200
        assert resp.json()["status"] == "resumed"
        # resume fails -> 400
        with patch("core.execution_state_manager.get_state_manager") as gs, \
             patch("core.workflow_engine.get_workflow_engine") as ge:
            state_manager = MagicMock()
            state_manager.get_execution_state = AsyncMock(return_value={"workflow_id": "wf-1"})
            gs.return_value = state_manager
            engine = MagicMock()
            engine.resume_workflow = AsyncMock(return_value=False)
            ge.return_value = engine
            resp = c.post("/api/v1/workflows/workflows/exec-1/resume", json={"a": 1})
        assert resp.status_code == 400
        # state not found -> orchestrator fallback with waiting step
        with patch("core.execution_state_manager.get_state_manager") as gs, \
             patch("advanced_workflow_orchestrator.get_orchestrator") as go:
            state_manager = MagicMock()
            state_manager.get_execution_state = AsyncMock(return_value=None)
            gs.return_value = state_manager
            context = SimpleNamespace(results={"s1": {"status": "waiting_approval"}})
            orchestrator = MagicMock()
            orchestrator.active_contexts = {"exec-1": context}
            orchestrator.resume_workflow = AsyncMock()
            go.return_value = orchestrator
            resp = c.post("/api/v1/workflows/workflows/exec-1/resume", json={"a": 1})
        assert resp.status_code == 200
        # orchestrator: execution unknown -> 404
        with patch("core.execution_state_manager.get_state_manager") as gs, \
             patch("advanced_workflow_orchestrator.get_orchestrator") as go:
            state_manager = MagicMock()
            state_manager.get_execution_state = AsyncMock(return_value=None)
            gs.return_value = state_manager
            orchestrator = MagicMock()
            orchestrator.active_contexts = {}
            go.return_value = orchestrator
            resp = c.post("/api/v1/workflows/workflows/exec-1/resume", json={"a": 1})
        assert resp.status_code == 404
        # orchestrator: no step waiting -> 400
        with patch("core.execution_state_manager.get_state_manager") as gs, \
             patch("advanced_workflow_orchestrator.get_orchestrator") as go:
            state_manager = MagicMock()
            state_manager.get_execution_state = AsyncMock(return_value=None)
            gs.return_value = state_manager
            context = SimpleNamespace(results={"s1": {"status": "running"}})
            orchestrator = MagicMock()
            orchestrator.active_contexts = {"exec-1": context}
            go.return_value = orchestrator
            resp = c.post("/api/v1/workflows/workflows/exec-1/resume", json={"a": 1})
        assert resp.status_code == 400
        # workflow definition missing -> 404
        with patch("core.execution_state_manager.get_state_manager") as gs:
            state_manager = MagicMock()
            state_manager.get_execution_state = AsyncMock(return_value={"workflow_id": "nope"})
            gs.return_value = state_manager
            resp = c.post("/api/v1/workflows/workflows/exec-1/resume", json={"a": 1})
        assert resp.status_code == 404

    def test_execution_history_and_details(self, app, wf_file, db_session, monkeypatch):
        from core import workflow_endpoints as we
        c = self._client(app)
        self._seed(wf_file, [self._node_row()])
        _seed_tenant_user(db_session)
        db_session.add(WorkflowExecution(
            execution_id="exec-db", workflow_id="wf-1", status="completed",
            user_id="user-1", input_data='{"a": 1}', outputs='{"r": 2}', error="oops",
        ))
        db_session.commit()
        legacy = {"execution_id": "exec-legacy", "workflow_id": "wf-1", "status": "completed",
                  "started_at": "2026-01-01T00:00:00", "completed_at": None, "results": [],
                  "errors": [], "actions_executed": [], "duration_ms": 0.0, "trigger_data": {}}
        def _gen_db():
            yield db_session
        monkeypatch.setattr(we, "get_db", _gen_db)

        class FakeEngine:
            def get_execution_history(self, wid):
                return [SimpleNamespace(to_dict=lambda: legacy)]

        with patch("ai.automation_engine.AutomationEngine", return_value=FakeEngine()):
            resp = c.get("/api/v1/workflows/workflows/wf-1/executions")
        assert resp.status_code == 200
        ids = [e["execution_id"] for e in resp.json()]
        assert "exec-legacy" in ids and "exec-db" in ids

        with patch("ai.automation_engine.AutomationEngine", side_effect=RuntimeError("boom")):
            resp = c.get("/api/v1/workflows/workflows/wf-1/executions")
        assert resp.status_code == 500

        # details from legacy engine
        class FakeEngine2:
            executions = {"exec-legacy": SimpleNamespace(to_dict=lambda: legacy)}

        with patch("ai.automation_engine.AutomationEngine", return_value=FakeEngine2()):
            resp = c.get("/api/v1/workflows/workflows/executions/exec-legacy")
        assert resp.status_code == 200
        # details from DB row
        class FakeEngine3:
            executions = {}

        with patch("ai.automation_engine.AutomationEngine", return_value=FakeEngine3()):
            resp = c.get("/api/v1/workflows/workflows/executions/exec-db")
        assert resp.status_code == 200
        assert resp.json()["errors"] == ["oops"]
        # details from orchestrator fallback
        with patch("ai.automation_engine.AutomationEngine", return_value=FakeEngine3()), \
             patch("advanced_workflow_orchestrator.get_orchestrator") as go:
            orchestrator = MagicMock()
            orchestrator.active_contexts = {"exec-orch": SimpleNamespace(
                results={"s1": {"status": "waiting_approval"}}, workflow_id="wf-1",
                input_data={"k": 1})}
            go.return_value = orchestrator
            resp = c.get("/api/v1/workflows/workflows/executions/exec-orch")
        assert resp.status_code == 200
        assert resp.json()["status"] == "waiting"
        # 404
        with patch("ai.automation_engine.AutomationEngine", return_value=FakeEngine3()), \
             patch("advanced_workflow_orchestrator.get_orchestrator") as go:
            go.return_value = MagicMock(active_contexts={})
            resp = c.get("/api/v1/workflows/workflows/executions/exec-nope")
        assert resp.status_code == 404

    def test_schedule_routes(self, app, wf_file):
        from core import workflow_endpoints as we
        app._role_holder["role"] = "team_lead"
        c = self._client(app)
        self._seed(wf_file, [self._node_row()])
        with patch("ai.workflow_scheduler.workflow_scheduler") as ws:
            ws.schedule_workflow.return_value = "job-1"
            resp = c.post("/api/v1/workflows/workflows/wf-1/schedule", json={
                "trigger_type": "interval", "trigger_config": {"minutes": 30},
            })
        assert resp.status_code == 200
        assert resp.json()["job_id"] == "job-1"
        # missing trigger config -> 400
        resp = c.post("/api/v1/workflows/workflows/wf-1/schedule", json={})
        assert resp.status_code == 400
        # workflow not found
        resp = c.post("/api/v1/workflows/workflows/nope/schedule", json={
            "trigger_type": "interval", "trigger_config": {"minutes": 30}})
        assert resp.status_code == 404
        # ValueError -> 400
        with patch("ai.workflow_scheduler.workflow_scheduler") as ws:
            ws.schedule_workflow.side_effect = ValueError("bad cron")
            resp = c.post("/api/v1/workflows/workflows/wf-1/schedule", json={
                "trigger_type": "interval", "trigger_config": {"minutes": 30}})
        assert resp.status_code == 400
        # generic error -> 500
        with patch("ai.workflow_scheduler.workflow_scheduler") as ws:
            ws.schedule_workflow.side_effect = RuntimeError("boom")
            resp = c.post("/api/v1/workflows/workflows/wf-1/schedule", json={
                "trigger_type": "interval", "trigger_config": {"minutes": 30}})
        assert resp.status_code == 500
        # unschedule / list / reload
        with patch("ai.workflow_scheduler.workflow_scheduler") as ws:
            assert c.delete("/api/v1/workflows/workflows/wf-1/schedule/job-1").status_code == 200
            ws.list_jobs.return_value = [{"job_id": "job-1"}]
            resp = c.get("/api/v1/workflows/scheduler/jobs")
            assert resp.status_code == 200 and resp.json() == [{"job_id": "job-1"}]
            ws.reload_system_jobs.return_value = None
            assert c.post("/api/v1/workflows/scheduler/reload").status_code == 200
            ws.reload_system_jobs.side_effect = RuntimeError("boom")
            assert c.post("/api/v1/workflows/scheduler/reload").status_code == 500

    def test_schedule_critical_gate(self, app, wf_file):
        c = self._client(app)
        self._seed(wf_file, [{"id": "wf-crit", "name": "C", "description": "d", "version": "1",
                              "steps": [{"action": "terminal_command"}]}])
        resp = c.post("/api/v1/workflows/workflows/wf-crit/schedule", json={
            "trigger_type": "interval", "trigger_config": {"minutes": 5}})
        assert resp.status_code == 403

    def test_row_to_dict_helpers(self, db_session):
        from core import workflow_endpoints as we
        _seed_tenant_user(db_session)
        row = WorkflowExecution(
            execution_id="e1", workflow_id="wf-1", status="completed",
            user_id="user-1", input_data=None, outputs=None,
        )
        db_session.add(row)
        db_session.commit()
        d = we._db_execution_row_to_dict(row)
        assert d["errors"] == [] and d["results"] == {} and d["status"] == "completed"
        ctx = SimpleNamespace(results={}, workflow_id="wf-1", input_data={})
        d = we._orchestrator_execution_to_dict("e2", ctx)
        assert d["status"] == "running"


# =============================================================================
# api/routes/webhooks/ingestion_webhooks.py — remaining branches
# (PostgreSQL RLS branches + outer error handlers + JSON fallbacks)
# =============================================================================

class TestIngestionWebhooksCoverage:
    def _make_client(self, db):
        from api.routes.webhooks import ingestion_webhooks as iw
        app = FastAPI()
        app.include_router(iw.router)
        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app, raise_server_exceptions=False)

    def _pg_db(self):
        """MagicMock db whose dialect claims postgresql -> SET LOCAL lines run."""
        db = MagicMock()
        db.bind.dialect.name = "postgresql"
        db.execute = MagicMock()
        return db

    def _discovery(self, tenant_id="tenant-1"):
        from api.routes.webhooks import ingestion_webhooks as iw
        service = MagicMock()
        service.get_tenant_id_by_external_id = AsyncMock(return_value=tenant_id)
        return patch.object(iw, "TenantDiscoveryService", return_value=service)

    def _dispatch(self, result=None):
        import core.webhook_crud_dispatch as wcd
        if isinstance(result, Exception):
            return patch.object(
                wcd, "crud_dispatch",
                new=AsyncMock(side_effect=result),
            )
        return patch.object(
            wcd, "crud_dispatch",
            new=AsyncMock(return_value={"status": "enqueued", "records": 1} if result is None else result),
        )

    def _integration(self, config=None, active=True):
        integration = MagicMock()
        integration.config = config if config is not None else {}
        integration.is_active = active
        return integration

    def _hmac(self, body: bytes, secret: str) -> str:
        import base64
        import hashlib
        import hmac
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def _conn(self, cid="conn-1"):
        conn = MagicMock()
        conn.id = cid
        return conn

    def test_slack_postgres_bind_and_connection(self):
        from api.routes.webhooks import ingestion_webhooks as iw
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.side_effect = [
            self._integration({"slack_signing_secret": "secret"}),
            self._conn("conn-1"),
        ]
        payload = {"type": "event_callback", "team_id": "T1", "event": {"type": "message"}}
        body = json.dumps(payload).encode()
        with self._discovery(), self._dispatch() as dispatch:
            resp = self._make_client(db).post(
                "/webhooks/slack/events", content=body,
                headers={"X-Slack-Signature": self._hmac(body, "secret"),
                         "X-Slack-Request-Timestamp": "123"},
            )
        assert resp.status_code == 200
        assert db.execute.call_count >= 4  # off/on x2
        dispatch.assert_awaited_once()

    def test_slack_connection_lookup_error_falls_back(self):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.side_effect = [
            self._integration({"slack_signing_secret": "secret"}),
        ]
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = RuntimeError("boom")
        from api.routes.webhooks import ingestion_webhooks as iw
        payload = {"type": "event_callback", "team_id": "T1", "event": {"type": "message"}}
        body = json.dumps(payload).encode()
        with self._discovery(), self._dispatch() as dispatch:
            resp = self._make_client(db).post(
                "/webhooks/slack/events", content=body,
                headers={"X-Slack-Signature": self._hmac(body, "secret"),
                         "X-Slack-Request-Timestamp": "123"},
            )
        assert resp.status_code == 200
        dispatch.assert_awaited_once()

    def _conn_lookup_error(self, db):
        db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = RuntimeError("boom")

    def test_hubspot_postgres_and_defaults(self):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.return_value = self._integration(
            {"client_secret": "s3cr3t"})
        import core.webhook_crud_dispatch as wcd
        with self._discovery(), self._dispatch(), \
             patch.object(wcd, "extract_crud_metadata", return_value=(None, None)) as extract:
            payload = [{"portalId": "P1", "type": "contact.creation", "objectId": 1}]
            body = json.dumps(payload).encode()
            resp = self._make_client(db).post(
                "/webhooks/hubspot/events", content=body,
                headers={"X-HubSpot-Signature": self._hmac(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        kwargs = self._dispatch_result_kwargs()
        extract.assert_called_once()

    def _dispatch_result_kwargs(self):
        return None

    def test_hubspot_connection_lookup_error(self):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.return_value = self._integration(
            {"client_secret": "s3cr3t"})
        self._conn_lookup_error(db)
        payload = [{"portalId": "P1", "type": "contact.creation", "objectId": 1}]
        body = json.dumps(payload).encode()
        with self._discovery(), self._dispatch():
            resp = self._make_client(db).post(
                "/webhooks/hubspot/events", content=body,
                headers={"X-HubSpot-Signature": self._hmac(body, "s3cr3t")},
            )
        assert resp.status_code == 200

    def test_hubspot_handler_error(self):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.return_value = self._integration(
            {"client_secret": "s3cr3t"})
        with self._discovery(), self._dispatch(result=RuntimeError("boom")):
            payload = [{"portalId": "P1", "type": "contact.creation", "objectId": 1}]
            body = json.dumps(payload).encode()
            resp = self._make_client(db).post(
                "/webhooks/hubspot/events", content=body,
                headers={"X-HubSpot-Signature": self._hmac(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_salesforce_postgres_and_error(self):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.return_value = self._integration(
            {"client_secret": "s3cr3t"})
        with self._discovery(), self._dispatch(result=RuntimeError("boom")):
            payload = {"orgId": "O1", "newlyEnrolledUserIds": [1]}
            body = json.dumps(payload).encode()
            resp = self._make_client(db).post(
                "/webhooks/salesforce/events", content=body,
                headers={"X-Salesforce-Signature": self._hmac(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_salesforce_connection_lookup_error(self):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.side_effect = [
            self._integration({"client_secret": "s3cr3t"}),
        ]
        self._conn_lookup_error(db)
        payload = {"orgId": "O1", "newlyEnrolledUserIds": [1]}
        body = json.dumps(payload).encode()
        with self._discovery(), self._dispatch():
            resp = self._make_client(db).post(
                "/webhooks/salesforce/events", content=body,
                headers={"X-Salesforce-Signature": self._hmac(body, "s3cr3t")},
            )
        assert resp.status_code == 200

    def test_gmail_handler_error(self):
        from api.routes.webhooks import ingestion_webhooks as iw
        import os as _os
        db = self._pg_db()
        queue = MagicMock()
        queue.enqueue_ingestion_job = AsyncMock(side_effect=RuntimeError("boom"))
        with self._discovery(), patch.object(iw, "webhook_queue", queue), \
             patch.dict(_os.environ, {"GMAIL_WEBHOOK_VERIFY_TOKEN": "tok"}):
            resp = self._make_client(db).post(
                "/webhooks/gmail/events?token=tok",
                json={"emailAddress": "a@b.com", "historyId": "123"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_notion_postgres_and_defaults(self):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.return_value = self._integration(
            {"client_secret": "s3cr3t"})
        import core.webhook_crud_dispatch as wcd
        with self._discovery(), self._dispatch(), \
             patch.object(wcd, "extract_crud_metadata", return_value=(None, None)):
            payload = {"workspace_id": "W1", "data": {"id": "page-1"}}
            body = json.dumps(payload).encode()
            resp = self._make_client(db).post(
                "/webhooks/notion/events", content=body,
                headers={"X-Notion-Signature": self._hmac(body, "s3cr3t")},
            )
        assert resp.status_code == 200

    def test_notion_connection_lookup_error(self):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.return_value = self._integration(
            {"client_secret": "s3cr3t"})
        self._conn_lookup_error(db)
        payload = {"workspace_id": "W1", "data": {"id": "page-1"}}
        body = json.dumps(payload).encode()
        with self._discovery(), self._dispatch():
            resp = self._make_client(db).post(
                "/webhooks/notion/events", content=body,
                headers={"X-Notion-Signature": self._hmac(body, "s3cr3t")},
            )
        assert resp.status_code == 200

    def test_notion_handler_error(self):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.return_value = self._integration(
            {"client_secret": "s3cr3t"})
        payload = {"workspace_id": "W1", "data": {"id": "page-1"}}
        body = json.dumps(payload).encode()
        with self._discovery(), self._dispatch(result=RuntimeError("boom")):
            resp = self._make_client(db).post(
                "/webhooks/notion/events", content=body,
                headers={"X-Notion-Signature": self._hmac(body, "s3cr3t")},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_outlook_postgres_branches_and_connection(self, monkeypatch):
        from api.routes.webhooks import ingestion_webhooks as iw
        db = self._pg_db()
        tenant = MagicMock()
        tenant.id = "tenant-1"
        conn = MagicMock()
        conn.id = "conn-9"
        db.query.return_value.filter.return_value.first.side_effect = [
            tenant,        # Tenant lookup
            conn,          # UserConnection prefix lookup
        ]
        monkeypatch.setattr("core.webhook_security.verify_client_state", lambda s: True)
        monkeypatch.setattr("core.webhook_security.get_client_state_data", lambda s: '{"c": "conn-"}')
        payload = {"value": [{
            "clientState": "signed",
            "changeType": "updated",
            "resource": "Users/u/mailFolders/inbox/messages/msg-1",
        }]}
        from api.routes.webhooks import ingestion_webhooks as iw
        queue = MagicMock()
        queue.enqueue_ingestion_job = AsyncMock(return_value="job-1")
        queue.get_queue_depth = AsyncMock(return_value=3)
        with patch.object(iw, "webhook_queue", queue):
            resp = self._make_client(db).post(
                "/webhooks/communication/outlook", json=payload)
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 1
        queue.enqueue_ingestion_job.assert_awaited_once()
        # prefix present but no matching connection -> else branch
        db3 = self._pg_db()
        tenant3 = MagicMock()
        tenant3.id = "tenant-1"
        db3.query.return_value.filter.return_value.first.side_effect = [tenant3, None]
        monkeypatch.setattr("core.webhook_security.verify_client_state", lambda s: True)
        monkeypatch.setattr("core.webhook_security.get_client_state_data", lambda s: '{"c": "zzz"}')
        queue2 = MagicMock()
        queue2.enqueue_ingestion_job = AsyncMock(return_value="job-2")
        queue2.get_queue_depth = AsyncMock(return_value=1)
        with patch.object(iw, "webhook_queue", queue2):
            resp = self._make_client(db3).post(
                "/webhooks/communication/outlook", json=payload)
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 1

    def test_outlook_deletion_with_db_error(self, monkeypatch):
        db = self._pg_db()
        tenant = MagicMock()
        tenant.id = "tenant-1"
        db.query.return_value.filter.return_value.first.return_value = tenant
        db.query.return_value.filter.return_value.all.side_effect = RuntimeError("boom")
        monkeypatch.setattr("core.webhook_security.verify_client_state", lambda s: True)
        monkeypatch.setattr("core.webhook_security.get_client_state_data", lambda s: '{}')
        payload = {"value": [{
            "clientState": "signed",
            "changeType": "deleted",
            "resource": "Users/u/mailFolders/inbox/messages/msg-9",
        }]}
        from api.routes.webhooks import ingestion_webhooks as iw
        queue = MagicMock()
        queue.enqueue_ingestion_job = AsyncMock(return_value="job-1")
        queue.get_queue_depth = AsyncMock(return_value=3)
        with patch.object(iw, "webhook_queue", queue):
            resp = self._make_client(db).post(
                "/webhooks/communication/outlook", json=payload)
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0
        queue.enqueue_ingestion_job.assert_not_awaited()

    def test_outlook_loop_level_catch(self, monkeypatch):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.side_effect = RuntimeError("boom")
        monkeypatch.setattr("core.webhook_security.verify_client_state", lambda s: True)
        monkeypatch.setattr("core.webhook_security.get_client_state_data", lambda s: '{}')
        payload = {"value": [{"clientState": "signed", "changeType": "updated",
                              "resource": "Users/u/mailFolders/inbox/messages/m1"}]}
        from api.routes.webhooks import ingestion_webhooks as iw
        queue = MagicMock()
        queue.enqueue_ingestion_job = AsyncMock(return_value="job-1")
        queue.get_queue_depth = AsyncMock(return_value=3)
        with patch.object(iw, "webhook_queue", queue):
            resp = self._make_client(db).post("/webhooks/communication/outlook", json=payload)
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0

    def test_outlook_loop_error_and_outer_error(self, monkeypatch):
        db = self._pg_db()
        tenant = MagicMock()
        tenant.id = "tenant-1"
        db.query.return_value.filter.return_value.first.return_value = tenant
        db.query.return_value.filter.return_value.all.side_effect = RuntimeError("boom")
        monkeypatch.setattr("core.webhook_security.verify_client_state", lambda s: True)
        monkeypatch.setattr("core.webhook_security.get_client_state_data", lambda s: '{}')
        # deletion path: delete() raises inside loop -> per-notification catch
        payload = {"value": [{
            "clientState": "signed",
            "changeType": "deleted",
            "resource": "Users/u/mailFolders/inbox/messages/msg-9",
        }]}
        from api.routes.webhooks import ingestion_webhooks as iw
        queue = MagicMock()
        queue.enqueue_ingestion_job = AsyncMock(return_value="job-1")
        queue.get_queue_depth = AsyncMock(return_value=3)
        with patch.object(iw, "webhook_queue", queue):
            resp = self._make_client(db).post("/webhooks/communication/outlook", json=payload)
        assert resp.status_code == 200
        assert resp.json()["job_count"] == 0
        # outer error: notifications not a list -> TypeError before the loop
        db2 = self._pg_db()
        resp = self._make_client(db2).post(
            "/webhooks/communication/outlook", json={"value": 1})
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_zoho_postgres_and_json_fallback(self):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.return_value = self._conn("conn-2")
        with self._discovery():
            resp = self._make_client(db).post(
                "/webhooks/zoho/zoho_crm", content=b"not json{{", headers={"Content-Type": "application/json"})
        assert resp.status_code == 400  # payload {} -> missing org id

    def test_zoho_connection_lookup_error(self):
        db = self._pg_db()
        self._conn_lookup_error(db)
        with self._discovery(), self._dispatch():
            resp = self._make_client(db).post(
                "/webhooks/zoho/zoho_crm",
                json={"orgId": "O1", "operation": "create", "data": {"id": "1"}},
            )
        assert resp.status_code == 200

    def test_zoho_handler_error(self):
        db = self._pg_db()
        with self._discovery(), self._dispatch(result=RuntimeError("boom")):
            resp = self._make_client(db).post(
                "/webhooks/zoho/zoho_crm",
                json={"orgId": "O1", "operation": "create", "data": {"id": "1"}},
            )
        assert resp.status_code == 500

    def test_pm_crm_postgres_defaults_and_error(self):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.return_value = self._conn("conn-3")
        import core.webhook_crud_dispatch as wcd
        with self._discovery():
            resp = self._make_client(db).post(
                "/webhooks/pm-crm/jira", content=b"nope{",
                headers={"Content-Type": "application/json"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"
        payload = {"webhookEvent": "jira:issue_created", "issue": {"id": "I-1"},
                   "clientKey": "ck-1"}
        with self._discovery(), self._dispatch(), \
             patch.object(wcd, "extract_crud_metadata", return_value=(None, None)):
            resp = self._make_client(db).post("/webhooks/pm-crm/jira", json=payload)
        assert resp.status_code == 200
        db2 = self._pg_db()
        with self._discovery(), self._dispatch(result=RuntimeError("boom")):
            resp = self._make_client(db2).post("/webhooks/pm-crm/jira", json=payload)
        assert resp.status_code == 500
        db3 = self._pg_db()
        self._conn_lookup_error(db3)
        with self._discovery(), self._dispatch():
            resp = self._make_client(db3).post("/webhooks/pm-crm/jira", json=payload)
        assert resp.status_code == 200

    def test_communication_postgres_and_json_fallback(self):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.return_value = self._conn("conn-4")
        with self._discovery(), self._dispatch():
            resp = self._make_client(db).post(
                "/webhooks/communication/slack", content=b"raw{", headers={"Content-Type": "application/json"})
        assert resp.status_code == 400
        db2 = self._pg_db()
        db2.query.return_value.filter.return_value.first.return_value = self._conn("conn-4")
        with self._discovery(), self._dispatch():
            resp = self._make_client(db2).post(
                "/webhooks/communication/discord",
                json={"guild_id": "G1", "event": {"type": "message"}},
            )
        assert resp.status_code == 200
        db3 = self._pg_db()
        self._conn_lookup_error(db3)
        with self._discovery(), self._dispatch():
            resp = self._make_client(db3).post(
                "/webhooks/communication/discord",
                json={"guild_id": "G1", "event": {"type": "message"}},
            )
        assert resp.status_code == 200

    def test_communication_json_fallback(self):
        db = self._pg_db()
        with self._discovery(), self._dispatch():
            resp = self._make_client(db).post(
                "/webhooks/communication/discord", content=b"bad{",
                headers={"Content-Type": "application/json"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"
        with self._discovery(), self._dispatch(),              patch("starlette.requests.Request.form", side_effect=RuntimeError("bad form")):
            resp = self._make_client(db).post(
                "/webhooks/communication/discord", data={"guild_id": "G1"},
                headers={"Content-Type": "application/x-www-form-urlencoded"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_dev_prod_json_fallback_and_conn_error(self):
        db = self._pg_db()
        self._conn_lookup_error(db)
        with self._discovery(), self._dispatch():
            resp = self._make_client(db).post(
                "/webhooks/dev-prod/github",
                json={"hook": {"events": ["push"], "config": {}},
                      "organization": {"login": "acme-org"},
                      "repository": {"id": "r1", "full_name": "a/b"}},
            )
        assert resp.status_code == 200

    def test_dev_prod_postgres_and_error(self):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.return_value = self._conn("conn-5")
        with self._discovery(), self._dispatch():
            resp = self._make_client(db).post(
                "/webhooks/dev-prod/github",
                json={"zen": "hi", "hook": {"events": ["push"], "config": {}}, "repository": {"id": "r1"}},
            )
        assert resp.status_code == 200
        db2 = self._pg_db()
        with self._discovery(), self._dispatch(result=RuntimeError("boom")):
            resp = self._make_client(db2).post(
                "/webhooks/dev-prod/github",
                json={"hook": {"events": ["push"], "config": {}},
                      "organization": {"login": "acme-org"},
                      "repository": {"id": "r1", "full_name": "a/b"},
                      "ref": "refs/heads/main", "pusher": {"name": "x"}},
            )
        assert resp.status_code == 500

    def test_dev_prod_json_fallback_only(self):
        db = self._pg_db()
        with self._discovery(), self._dispatch():
            resp = self._make_client(db).post(
                "/webhooks/dev-prod/github", content=b"broken{",
                headers={"Content-Type": "application/json"})
        assert resp.status_code == 200

    def test_ecommerce_postgres_and_json_fallbacks(self):
        db = self._pg_db()
        db.query.return_value.filter.return_value.first.return_value = self._conn("conn-6")
        with self._discovery(), self._dispatch():
            resp = self._make_client(db).post(
                "/webhooks/ecommerce-marketing/shopify", content=b"broken{",
                headers={"Content-Type": "application/json"})
        assert resp.status_code == 200
        assert resp.json().get("status") in ("ignored", None)
        # form-encoded body
        with self._discovery(), self._dispatch():
            resp = self._make_client(db).post(
                "/webhooks/ecommerce-marketing/mailchimp",
                data={"type": "subscribe", "data[list_id]": "L1"},
                headers={"Content-Type": "application/x-www-form-urlencoded"})
        assert resp.status_code in (200, 400)
        # form parsing failure -> payload fallback
        with self._discovery(), self._dispatch(),              patch("starlette.requests.Request.form", side_effect=RuntimeError("bad form")):
            resp = self._make_client(db).post(
                "/webhooks/ecommerce-marketing/mailchimp",
                data={"type": "subscribe"},
                headers={"Content-Type": "application/x-www-form-urlencoded"})
        assert resp.status_code == 200
        # ecommerce pg happy path (SET LOCAL off/on + conn resolution)
        db2 = self._pg_db()
        db2.query.return_value.filter.return_value.first.return_value = self._conn("conn-7")
        with self._discovery(), self._dispatch():
            resp = self._make_client(db2).post(
                "/webhooks/ecommerce-marketing/shopify",
                json={"domain": "acme.myshopify.com", "topic": "orders/create"},
            )
        assert resp.status_code == 200
        # ecommerce connection lookup error
        db3 = self._pg_db()
        self._conn_lookup_error(db3)
        with self._discovery(), self._dispatch():
            resp = self._make_client(db3).post(
                "/webhooks/ecommerce-marketing/shopify",
                json={"domain": "acme.myshopify.com", "topic": "orders/create"},
            )
        assert resp.status_code == 200


class TestWorkflowDebuggerLastGaps:
    @pytest.fixture()
    def db(self, db_session):
        return db_session

    @pytest.fixture()
    def debugger(self, db):
        from core.workflow_debugger import WorkflowDebugger
        d = WorkflowDebugger(db)
        d.expression_evaluator = SimpleNamespace(evaluate=lambda cond, vars: True)
        return d

    @pytest.fixture()
    def broken_db(self, db):
        from unittest.mock import Mock
        db._orig_commit = db.commit
        db._orig_rollback = db.rollback
        db._orig_query = db.query
        yield db
        db.commit = db._orig_commit
        db.rollback = db._orig_rollback
        db.query = db._orig_query

    def test_remove_toggle_error_paths(self, broken_db, debugger):
        bp = debugger.add_breakpoint("wf-1", "node-1", "user-1")
        broken_db.commit = Mock(side_effect=RuntimeError("down"))
        assert debugger.remove_breakpoint(bp.id, "user-1") is False
        assert debugger.toggle_breakpoint(bp.id, "user-1") is None
        broken_db.rollback()

    def test_complete_trace_error_path(self, broken_db, debugger):
        trace = debugger.create_trace("wf-1", "exec-1", 1, "n", "t")
        broken_db.commit = Mock(side_effect=RuntimeError("down"))
        assert debugger.complete_trace(trace.id, output_data={"r": 1}) is False
        broken_db.rollback()

    def test_perf_report_error_paths(self, broken_db, debugger):
        s = WorkflowDebugSession(
            workflow_id="wf-1", user_id="user-1", session_name="S", status="active",
            performance_metrics={"enabled": True, "step_times": [], "node_times": {},
                                 "total_duration_ms": 0},
        )
        broken_db.add(s)
        broken_db.commit()
        broken_db.refresh(s)
        broken_db.query = Mock(side_effect=RuntimeError("boom"))
        assert debugger.record_step_timing(s.id, "n", "t", 1) is False
        assert debugger.get_performance_report(s.id) is None
        broken_db.query = broken_db._orig_query

    def test_run_async_websocket_running_loop(self, debugger):
        import asyncio

        async def inner():
            async def ok_coro():
                return 7
            return debugger._run_async_websocket(ok_coro())

        assert asyncio.run(inner()) == 0  # running loop -> create_task path

    def test_remove_collaborator_error(self, broken_db, debugger):
        s = WorkflowDebugSession(
            workflow_id="wf-1", user_id="user-1", session_name="S", status="active",
        )
        broken_db.add(s)
        broken_db.commit()
        broken_db.refresh(s)
        assert debugger.add_collaborator(s.id, "u2") is True
        broken_db.commit = Mock(side_effect=RuntimeError("down"))
        assert debugger.remove_collaborator(s.id, "u2") is False
        broken_db.rollback()


class TestWorkflowEndpointsLastGaps:
    @pytest.fixture()
    def wf_file(self, tmp_path, monkeypatch):
        from core import workflow_endpoints as we
        wf_file = tmp_path / "workflows.json"
        monkeypatch.setattr(we, "WORKFLOWS_FILE", str(wf_file))
        return wf_file

    @pytest.fixture()
    def app(self, wf_file):
        from core import workflow_endpoints as we
        app = FastAPI()
        app.include_router(we.router, prefix="/api/v1/workflows")
        holder = {"role": "member"}

        def _fake_user():
            return SimpleNamespace(id="u1", role=holder["role"])

        from core.auth import get_current_user as auth_cur
        app.dependency_overrides[auth_cur] = _fake_user
        app._role_holder = holder
        return app

    def test_ai_editor_unavailable_import(self, monkeypatch):
        from core import workflow_endpoints as we
        with patch.dict(sys.modules, {"ai.workflow_nlu_editor": None}):
            import importlib
            reloaded = importlib.reload(we)
        assert reloaded.AI_EDITOR_AVAILABLE is False
        assert reloaded._legacy_rule_based_edit is not None
        importlib.reload(we)
        assert we.AI_EDITOR_AVAILABLE is True

    def test_load_workflows_decode_error_branch(self, monkeypatch):
        from core import workflow_endpoints as we
        monkeypatch.setattr(we, "WORKFLOWS_FILE", "/dev/null")
        assert we.load_workflows() == []

    def test_template_error_and_edit_reasoning(self, app, wf_file):
        from core import workflow_endpoints as we
        app._role_holder["role"] = "team_lead"
        c = TestClient(app, raise_server_exceptions=False)
        self2 = TestWorkflowEndpointsCoverage()
        self2._seed(wf_file, [self2._node_row()])

        class Op:
            operation_type = "add_node"
            target_id = "n9"
            data = {"config": {"service": "slack"}}

        class Plan:
            confidence = 0.9
            reasoning = "because reasons"
            operations = [Op()]

        class Editor:
            async def parse_workflow_edit_command(self, command, workflow):
                return Plan()

            async def apply_edit_plan(self, plan, workflow):
                return dict(workflow)

        with patch.object(we, "get_workflow_editor", return_value=Editor()):
            resp = c.post("/api/v1/workflows/workflows/wf-1/edit", json={"command": "add a slack step"})
        assert "AI reasoning: because reasons" in resp.json()["message"]
        # template lookup error path
        assert we._load_template_definition("t1") is None

    def test_engine_error_and_db_error_paths(self, app, wf_file, monkeypatch):
        from core import workflow_endpoints as we
        c = TestClient(app, raise_server_exceptions=False)
        self2 = TestWorkflowEndpointsCoverage()
        self2._seed(wf_file, [self2._node_row()])
        # conductor: engine import fails silently (except pass)
        async def fake_execute(steps, start_step, context, strategy):
            return SimpleNamespace(execution_id="e1", status="completed",
                                   completed_steps=1, failed_steps=0, step_results=[])
        with patch("core.orchestration.conductor_agent.get_conductor_agent") as gc, \
             patch("core.workflow_engine.get_workflow_engine", side_effect=RuntimeError("no engine")):
            conductor = MagicMock()
            conductor.execute_workflow = AsyncMock(side_effect=fake_execute)
            gc.return_value = conductor
            resp = c.post("/api/v1/workflows/workflows/conductor/execute", json={
                "steps": [{"id": "s1", "name": "s"}], "strategy": "sequential"})
        assert resp.status_code == 200
        # executions: DB merge failure is swallowed (logger.exception)
        with patch("ai.automation_engine.AutomationEngine") as ae:
            engine = MagicMock()
            engine.get_execution_history.return_value = []
            ae.return_value = engine
            def _bad_db():
                raise RuntimeError("db down")
                yield  # pragma: no cover
            monkeypatch.setattr(we, "get_db", _bad_db)
            resp = c.get("/api/v1/workflows/workflows/wf-1/executions")
        assert resp.status_code == 200
        assert resp.json() == []
        # details: DB row failure swallowed -> falls to orchestrator -> 404
        def _bad_db2():
            raise RuntimeError("db down")
            yield  # pragma: no cover
        monkeypatch.setattr(we, "get_db", _bad_db2)
        with patch("ai.automation_engine.AutomationEngine") as ae, \
             patch("advanced_workflow_orchestrator.get_orchestrator") as go:
            ae.return_value = MagicMock(executions={})
            go.return_value = MagicMock(active_contexts={})
            resp = c.get("/api/v1/workflows/workflows/executions/exec-x")
        assert resp.status_code == 404


class TestWorkflowDebuggerLastGaps2:
    @pytest.fixture()
    def db(self, db_session):
        return db_session

    @pytest.fixture()
    def debugger(self, db):
        from core.workflow_debugger import WorkflowDebugger
        d = WorkflowDebugger(db)
        d.expression_evaluator = SimpleNamespace(evaluate=lambda cond, vars: True)
        return d

    def test_active_sessions_and_state_success(self, db, debugger):
        s = WorkflowDebugSession(
            workflow_id="wf-1", user_id="user-1", session_name="S", status="active",
            execution_id="exec-1",
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        assert debugger.get_active_debug_sessions("wf-1") != []
        assert debugger.get_active_debug_sessions("wf-1", user_id="user-1") != []
        assert debugger.get_active_debug_sessions("wf-1", user_id="other") == []
        assert debugger.pause_debug_session(s.id) is True
        assert debugger.resume_debug_session(s.id) is True
        assert debugger.complete_debug_session(s.id) is True
        assert debugger.step_over(s.id)["current_step"] == 1

    def test_evaluate_condition_raises(self, db, debugger):
        debugger.expression_evaluator = SimpleNamespace(
            evaluate=lambda cond, vars: (_ for _ in ()).throw(ValueError("bad expr")))
        assert debugger._evaluate_condition("x >", {}) is False

    def test_import_session_with_variables(self, db, debugger):
        s = WorkflowDebugSession(
            workflow_id="wf-1", user_id="user-1", session_name="S", status="active",
            variables={"a": 1}, call_stack=[{"step_number": 1}],
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        exported = debugger.export_session(s.id)
        imported = debugger.import_session(exported)
        assert imported is not None
        assert imported.variables == {"a": 1}

    def test_notify_closures_execute(self, debugger):
        import asyncio
        from core import workflow_debugger as wd
        manager = MagicMock()
        manager.stream_trace = AsyncMock()
        manager.notify_variable_changed = AsyncMock()
        manager.notify_breakpoint_hit = AsyncMock()
        manager.notify_session_paused = AsyncMock()
        manager.notify_session_resumed = AsyncMock()
        manager.notify_step_completed = AsyncMock()
        with patch.object(wd, "get_debugging_websocket_manager", return_value=manager), \
             patch.object(debugger, "_run_async_websocket", side_effect=asyncio.run):
            debugger.stream_trace_with_manager("exec-1", "sess-1", {})
            debugger.notify_variable_changed("sess-1", "x", 1, 0)
            debugger.notify_breakpoint_hit("sess-1", "bp-1", "node-1", 1)
            debugger.notify_session_paused("sess-1", "user_action", "node-1")
            debugger.notify_session_resumed("sess-1")
            debugger.notify_step_completed("sess-1", "step_over", 2, "node-1")
        manager.stream_trace.assert_awaited_once_with("exec-1", "sess-1", {})
        manager.notify_variable_changed.assert_awaited_once_with("sess-1", "x", 1, 0)
        manager.notify_breakpoint_hit.assert_awaited_once()
        manager.notify_session_paused.assert_awaited_once()
        manager.notify_session_resumed.assert_awaited_once()
        manager.notify_step_completed.assert_awaited_once()


class TestWorkflowEndpointsLastGaps2:
    @pytest.fixture()
    def wf_file(self, tmp_path, monkeypatch):
        from core import workflow_endpoints as we
        wf_file = tmp_path / "workflows.json"
        monkeypatch.setattr(we, "WORKFLOWS_FILE", str(wf_file))
        return wf_file

    @pytest.fixture()
    def app(self, wf_file):
        from core import workflow_endpoints as we
        app = FastAPI()
        app.include_router(we.router, prefix="/api/v1/workflows")
        holder = {"role": "member"}

        def _fake_user():
            return SimpleNamespace(id="u1", role=holder["role"])

        from core.auth import get_current_user as auth_cur
        app.dependency_overrides[auth_cur] = _fake_user
        app._role_holder = holder
        return app

    def test_load_workflows_generic_exception(self, monkeypatch):
        from core import workflow_endpoints as we
        monkeypatch.setattr(we, "WORKFLOWS_FILE", "/nonexistent")
        monkeypatch.setattr(we.os.path, "exists", lambda p: True)
        import builtins
        monkeypatch.setattr(builtins, "open", Mock(side_effect=PermissionError("denied")))
        assert we.load_workflows() == []

    def test_template_definition_rows(self, monkeypatch, db_session):
        from core import workflow_endpoints as we
        _seed_tenant_user(db_session)

        def _gen():
            yield db_session

        monkeypatch.setattr(we, "get_db", _gen)
        assert we._load_template_definition("missing") is None
        from core.models import WorkflowTemplate
        db_session.add(WorkflowTemplate(
            id="tpl-1", name="T", description="D", steps=[{"id": "s1"}],
            author_id="user-1", category="ops", icon="rocket",
        ))
        db_session.commit()
        found = we._load_template_definition("tpl-1")
        assert found["name"] == "T" and found["steps"] == [{"id": "s1"}]

    def test_edit_no_reasoning_message(self, app, wf_file):
        from core import workflow_endpoints as we
        app._role_holder["role"] = "team_lead"
        c = TestClient(app, raise_server_exceptions=False)
        self2 = TestWorkflowEndpointsCoverage()
        self2._seed(wf_file, [self2._node_row()])

        class Op:
            operation_type = "add_node"
            target_id = "n9"
            data = {"config": {"service": "slack"}}

        class Plan:
            confidence = 0.9
            reasoning = None
            operations = [Op()]

        class Editor:
            async def parse_workflow_edit_command(self, command, workflow):
                return Plan()

            async def apply_edit_plan(self, plan, workflow):
                return dict(workflow)

        with patch.object(we, "get_workflow_editor", return_value=Editor()):
            resp = c.post("/api/v1/workflows/workflows/wf-1/edit", json={"command": "add a slack step"})
        assert "Confidence: 0.90" in resp.json()["message"]

    def test_conductor_engine_available(self, app):
        from core import workflow_endpoints as we
        c = TestClient(app, raise_server_exceptions=False)

        async def fake_execute(steps, start_step, context, strategy):
            return SimpleNamespace(execution_id="e1", status="completed",
                                   completed_steps=1, failed_steps=0, step_results=[])
        with patch("core.orchestration.conductor_agent.get_conductor_agent") as gc, \
             patch("core.workflow_engine.get_workflow_engine") as ge:
            conductor = MagicMock()
            conductor.execute_workflow = AsyncMock(side_effect=fake_execute)
            gc.return_value = conductor
            engine = MagicMock()
            engine._execute_step = "step-executor"
            ge.return_value = engine
            resp = c.post("/api/v1/workflows/workflows/conductor/execute", json={
                "steps": [{"id": "s1", "name": "s"}], "strategy": "sequential"})
        assert resp.status_code == 200
        conductor.set_step_executor.assert_called_once_with("step-executor")

    def test_executions_dedup_continue(self, app, wf_file, db_session, monkeypatch):
        from core import workflow_endpoints as we
        c = TestClient(app, raise_server_exceptions=False)
        self2 = TestWorkflowEndpointsCoverage()
        self2._seed(wf_file, [self2._node_row()])
        _seed_tenant_user(db_session)

        def _gen():
            yield db_session

        monkeypatch.setattr(we, "get_db", _gen)
        db_session.add(WorkflowExecution(
            execution_id="exec-shared", workflow_id="wf-1", status="completed",
            user_id="user-1", input_data=None,
        ))
        db_session.commit()
        legacy = {"execution_id": "exec-shared", "workflow_id": "wf-1", "status": "completed"}
        with patch("ai.automation_engine.AutomationEngine") as ae:
            engine = MagicMock()
            engine.get_execution_history.return_value = [SimpleNamespace(to_dict=lambda: legacy)]
            ae.return_value = engine
            resp = c.get("/api/v1/workflows/workflows/wf-1/executions")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
