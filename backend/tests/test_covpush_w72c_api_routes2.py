"""W72C — coverage push batch for 7 API route modules.

Targets (statement coverage >= 95% each):
1. api/background_agent_routes.py      — 87% baseline (ImportError branches,
   register/start bodies behind the governance wrapper)
2. api/intelligence_routes.py          — 46% baseline (insights/entities/refresh/
   execute matrix, dev-seed path, error paths)
3. api/mcp_server_routes.py            — 60% baseline (bad JSON, batch, 202,
   SSE stream, disabled-503)
4. api/notifications_routes.py         — 100% baseline (no gap-fill needed)
5. api/notification_settings_routes.py — 43% baseline (full endpoint matrix +
   ownership 404s + test-notification branches)
6. api/nav_stub_routes.py              — never tested (full endpoint matrix +
   degradation branches)
7. api/ai_workflows_routes.py          — 91% baseline (fallback intent keyword
   branches, number/email entity extraction, providers error branch)

Style: FastAPI TestClient + app.dependency_overrides; patches use real
module names (no `backend.` prefix). Zero network / zero LLM spend.
"""

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.database import get_db


# ============================================================================
# Helpers
# ============================================================================

def make_client(router, overrides=None):
    """Build an isolated TestClient for a router with dependency overrides.

    ``overrides`` must be keyed by the dependency callable objects the router
    module imported (e.g. the router's own ``get_current_user``) — never by
    keyword names.
    """
    app = FastAPI()
    app.include_router(router)
    for dep, value in (overrides or {}).items():
        app.dependency_overrides[dep] = value
    return TestClient(app, raise_server_exceptions=False)


def fake_user(user_id="u-72c", tenant_id="t-1", role="team_lead"):
    u = MagicMock()
    u.id = user_id
    u.tenant_id = tenant_id
    u.role = role
    return u


def user_override(user_id="u-72c", tenant_id="t-1", role="team_lead"):
    def _override():
        return fake_user(user_id, tenant_id, role)
    return _override


def _chain(rows_return=None, first_return=None, count_return=0):
    """MagicMock whose every chained call returns itself, except
    .all() / .count() / .first() which return the supplied values."""
    chain = MagicMock()
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.limit.return_value = chain
    chain.offset.return_value = chain
    chain.all.return_value = rows_return or []
    chain.first.return_value = first_return
    chain.count.return_value = count_return
    return chain


# ============================================================================
# 1. api/background_agent_routes.py
# ============================================================================

class TestBackgroundAgentRoutes:
    """Gap-fill coverage for background_agent_routes (87% -> >=95%)."""

    @pytest.fixture
    def client(self):
        from api.background_agent_routes import router

        return make_client(
            router,
            {
                get_current_user: user_override(),
                get_db: lambda: MagicMock(),
            },
        )

    @pytest.fixture
    def runner(self):
        mock = MagicMock()
        mock.get_status = MagicMock(return_value={
            "agents": {
                "agent-1": {"running": True, "interval": 3600},
                "agent-2": {"running": False, "interval": 7200},
            },
            "timestamp": "2026-03-11T12:00:00Z",
        })
        mock.register_agent = MagicMock()
        mock.start_agent = AsyncMock(return_value=None)
        mock.stop_agent = AsyncMock(return_value=None)
        mock.get_logs = MagicMock(return_value=[
            {"timestamp": "t", "level": "INFO", "message": "started"},
        ])
        return mock

    def test_requires_auth(self):
        from api.background_agent_routes import router

        client = make_client(router, {get_db: lambda: MagicMock()})
        assert client.get("/api/background-agents/tasks").status_code == 401
        assert client.get("/api/background-agents/status").status_code == 401
        assert client.post("/api/background-agents/a/register").status_code == 401
        assert client.post("/api/background-agents/a/start").status_code == 401
        assert client.post("/api/background-agents/a/stop").status_code == 401
        assert client.get("/api/background-agents/a/logs").status_code == 401
        assert client.get("/api/background-agents/logs").status_code == 401

    def test_list_tasks_import_error_branch(self, client):
        with patch.dict(sys.modules, {"core.background_agent_runner": None}):
            resp = client.get("/api/background-agents/tasks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["tasks"] == []
        assert body["data"]["total"] == 0
        assert body["data"]["active"] == 0

    def test_all_status_import_error_branch(self, client):
        with patch.dict(sys.modules, {"core.background_agent_runner": None}):
            resp = client.get("/api/background-agents/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["agents"] == {}
        assert "Background runner not available" in body["message"]

    def test_list_tasks_success(self, client, runner):
        with patch("core.background_agent_runner.background_runner", runner):
            resp = client.get("/api/background-agents/tasks")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 2
        assert data["active"] == 1
        assert data["timestamp"] == "2026-03-11T12:00:00Z"

    def test_register_success_custom_interval(self, client, runner):
        with patch("core.background_agent_runner.background_runner", runner):
            resp = client.post(
                "/api/background-agents/agent-9/register",
                json={"interval_seconds": 7200},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["agent_id"] == "agent-9"
        assert body["data"]["interval"] == 7200
        assert "registered" in body["message"].lower()
        runner.register_agent.assert_called_once_with("agent-9", 7200)

    def test_register_success_default_interval(self, client, runner):
        with patch("core.background_agent_runner.background_runner", runner):
            resp = client.post("/api/background-agents/agent-9/register", json={})
        assert resp.status_code == 200
        runner.register_agent.assert_called_once_with("agent-9", 3600)

    def test_register_invalid_payload_422(self, client):
        resp = client.post(
            "/api/background-agents/agent-9/register",
            json={"interval_seconds": "not-an-int"},
        )
        assert resp.status_code == 422

    def test_start_success(self, client, runner):
        with patch("core.background_agent_runner.background_runner", runner):
            resp = client.post("/api/background-agents/agent-9/start")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["agent_id"] == "agent-9"
        assert "started" in body["message"].lower()
        runner.start_agent.assert_called_once_with("agent-9")

    def test_start_value_error_404(self, client, runner):
        runner.start_agent = AsyncMock(side_effect=ValueError("not registered"))
        with patch("core.background_agent_runner.background_runner", runner):
            resp = client.post("/api/background-agents/ghost/start")
        assert resp.status_code == 404

    def test_stop_success(self, client, runner):
        with patch("core.background_agent_runner.background_runner", runner):
            resp = client.post("/api/background-agents/agent-9/stop")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["agent_id"] == "agent-9"
        assert "stopped" in body["message"].lower()
        runner.stop_agent.assert_called_once_with("agent-9")

    def test_single_agent_status(self, client, runner):
        runner.get_status.return_value = {"running": False, "interval": 3600}
        with patch("core.background_agent_runner.background_runner", runner):
            resp = client.get("/api/background-agents/agent-9/status")
        assert resp.status_code == 200
        assert resp.json()["interval"] == 3600
        runner.get_status.assert_called_once_with("agent-9")

    def test_agent_logs_custom_limit(self, client, runner):
        with patch("core.background_agent_runner.background_runner", runner):
            resp = client.get("/api/background-agents/agent-9/logs?limit=25")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        runner.get_logs.assert_called_once_with("agent-9", 25)

    def test_all_logs_default_and_custom(self, client, runner):
        with patch("core.background_agent_runner.background_runner", runner):
            resp = client.get("/api/background-agents/logs")
        assert resp.status_code == 200
        runner.get_logs.assert_called_once_with(limit=100)
        with patch("core.background_agent_runner.background_runner", runner):
            resp = client.get("/api/background-agents/logs?limit=5")
        assert resp.status_code == 200
        runner.get_logs.assert_called_with(limit=5)


# ============================================================================
# 2. api/intelligence_routes.py
# ============================================================================

def _engine_mock():
    eng = MagicMock()
    eng.entity_registry = {}
    eng.detect_anomalies = AsyncMock(return_value=[])
    eng._get_platform_data = AsyncMock(return_value={"entities": []})
    eng.ingest_platform_data = AsyncMock(return_value=None)
    return eng


def _entity(eid="e-1", etype="contact", platforms=None, status="active",
            amount=None, value=None):
    e = MagicMock()
    e.entity_id = eid
    e.canonical_name = f"name-{eid}"
    e.entity_type = MagicMock()
    e.entity_type.value = etype
    e.source_platforms = [MagicMock(value=p) for p in (platforms or ["slack"])]
    e.attributes = {}
    if status is not None:
        e.attributes["status"] = status
    if amount is not None:
        e.attributes["amount"] = amount
    if value is not None:
        e.attributes["value"] = value
    e.updated_at = MagicMock()
    e.updated_at.isoformat.return_value = "2026-01-01T00:00:00"
    return e


class TestIntelligenceRoutes:
    """Gap-fill coverage for intelligence_routes (46% -> >=95%)."""

    @pytest.fixture
    def client(self):
        from api.intelligence_routes import router

        return make_client(router, {get_current_user: user_override()})

    # --- /insights ---------------------------------------------------------

    def test_requires_auth(self):
        from api.intelligence_routes import router

        client = make_client(router)
        assert client.get("/api/intelligence/insights").status_code == 401
        assert client.get("/api/intelligence/entities").status_code == 401
        assert client.post("/api/intelligence/refresh").status_code == 401
        assert client.post("/api/intelligence/execute", json={}).status_code == 401

    def test_insights_with_entities(self, client):
        eng = _engine_mock()
        eng.entity_registry = {"e1": _entity()}
        eng.detect_anomalies.return_value = []
        with patch("api.intelligence_routes.engine", eng):
            resp = client.get("/api/intelligence/insights")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["count"] == 0
        assert data["insights"] == []

    def test_insights_dev_seeds_platforms(self, client):
        eng = _engine_mock()
        eng.entity_registry = []
        with patch("api.intelligence_routes.engine", eng), \
                patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            resp = client.get("/api/intelligence/insights")
        assert resp.status_code == 200
        assert eng._get_platform_data.await_count == 3
        assert eng.ingest_platform_data.await_count == 3
        eng.detect_anomalies.assert_awaited_once()

    def test_insights_empty_production_skips_seed(self, client):
        eng = _engine_mock()
        eng.entity_registry = []
        with patch("api.intelligence_routes.engine", eng), \
                patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            resp = client.get("/api/intelligence/insights")
        assert resp.status_code == 200
        eng._get_platform_data.assert_not_awaited()
        eng.detect_anomalies.assert_awaited_once()

    def test_insights_sorts_critical_first(self, client):
        eng = _engine_mock()
        eng.entity_registry = {"e1": _entity()}

        class _Anomaly:
            def __init__(self, severity):
                self.severity = severity

        eng.detect_anomalies.return_value = [
            _Anomaly("unknown"), _Anomaly("info"),
            _Anomaly("critical"), _Anomaly("warning"),
        ]
        with patch("api.intelligence_routes.engine", eng):
            resp = client.get("/api/intelligence/insights")
        assert resp.status_code == 200
        severities = [a["severity"] for a in resp.json()["data"]["insights"]]
        assert severities == ["critical", "warning", "info", "unknown"]

    def test_insights_error_is_500(self, client):
        eng = _engine_mock()
        eng.detect_anomalies = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.intelligence_routes.engine", eng):
            resp = client.get("/api/intelligence/insights")
        assert resp.status_code == 500
        assert "boom" not in resp.text

    # --- /entities ---------------------------------------------------------

    def test_entities_no_filter(self, client):
        eng = _engine_mock()
        eng.entity_registry = {
            "e1": _entity(eid="e1", etype="contact", platforms=["slack"],
                          status="active", amount=100),
            "e2": _entity(eid="e2", etype="company", platforms=["salesforce"],
                          status=None, amount=None, value=50),
        }
        with patch("api.intelligence_routes.engine", eng):
            resp = client.get("/api/intelligence/entities")
        assert resp.status_code == 200
        entities = resp.json()["data"]["entities"]
        assert len(entities) == 2
        first = entities[0]
        assert first["id"] == "e1"
        assert first["type"] == "contact"
        assert first["platforms"] == ["slack"]
        assert first["status"] == "active"
        assert first["value"] == 100
        assert first["modified_at"] == "2026-01-01T00:00:00"
        assert entities[1]["value"] == 50

    def test_entities_type_and_platform_filter(self, client):
        eng = _engine_mock()
        eng.entity_registry = {
            "e1": _entity(eid="e1", etype="contact", platforms=["slack"]),
            "e2": _entity(eid="e2", etype="company", platforms=["salesforce"]),
        }
        with patch("api.intelligence_routes.engine", eng):
            resp = client.get("/api/intelligence/entities?type=contact")
        assert [e["id"] for e in resp.json()["data"]["entities"]] == ["e1"]
        with patch("api.intelligence_routes.engine", eng):
            resp = client.get("/api/intelligence/entities?platform=salesforce")
        assert [e["id"] for e in resp.json()["data"]["entities"]] == ["e2"]
        with patch("api.intelligence_routes.engine", eng):
            resp = client.get(
                "/api/intelligence/entities?type=contact&platform=slack"
            )
        assert [e["id"] for e in resp.json()["data"]["entities"]] == ["e1"]
        with patch("api.intelligence_routes.engine", eng):
            resp = client.get("/api/intelligence/entities?type=ghost")
        assert resp.json()["data"]["entities"] == []

    def test_entities_error_is_500(self, client):
        eng = _engine_mock()
        eng.entity_registry = {"e1": _entity()}
        eng.entity_registry["e1"].updated_at = None
        with patch("api.intelligence_routes.engine", eng):
            resp = client.get("/api/intelligence/entities")
        assert resp.status_code == 500
        assert "Internal error" in resp.text

    # --- /refresh ----------------------------------------------------------

    def test_refresh_syncs_platforms(self, client):
        eng = _engine_mock()
        eng.entity_registry = {"e1": _entity(), "e2": _entity()}

        async def data_for(platform, ctx):
            if platform.value == "slack":
                return {"entities": []}
            return {}

        eng._get_platform_data = AsyncMock(side_effect=data_for)
        with patch("api.intelligence_routes.engine", eng):
            resp = client.post("/api/intelligence/refresh")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["platforms_synced"] == 1
        assert data["total_entities"] == 2
        assert eng.ingest_platform_data.await_count == 1

    def test_refresh_platform_error_is_contained(self, client):
        eng = _engine_mock()

        async def fail_for(platform, ctx):
            if platform.value == "asana":
                raise RuntimeError("platform down")
            return {"entities": []}

        eng._get_platform_data = AsyncMock(side_effect=fail_for)
        with patch("api.intelligence_routes.engine", eng):
            resp = client.post("/api/intelligence/refresh")
        assert resp.status_code == 200
        assert resp.json()["data"]["platforms_synced"] >= 1

    def test_refresh_overall_error_is_500(self, client):
        eng = _engine_mock()

        class ExplodingDict(dict):
            def __len__(self):
                raise RuntimeError("boom")

        eng.entity_registry = ExplodingDict()
        with patch("api.intelligence_routes.engine", eng):
            resp = client.post("/api/intelligence/refresh")
        assert resp.status_code == 500
        assert "boom" not in resp.text

    # --- /execute ----------------------------------------------------------

    def test_execute_workflow_success_team_lead(self, client):
        from advanced_workflow_orchestrator import (
            WorkflowDefinition,
            WorkflowStep,
            WorkflowStepType,
        )

        orch = MagicMock()
        orch.execute_workflow = AsyncMock(return_value={"status": "completed"})
        orch.workflows = {
            "wf-1": WorkflowDefinition(
                workflow_id="wf-1",
                name="wf-1",
                description="",
                steps=[WorkflowStep(
                    step_id="s1",
                    step_type=WorkflowStepType.EMAIL_SEND,
                    description="d",
                    parameters={},
                    next_steps=[],
                )],
                start_step="s1",
                version="1",
            )
        }
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orch):
            resp = client.post(
                "/api/intelligence/execute",
                json={
                    "action_type": "workflow",
                    "action_payload": {"workflow_id": "wf-1", "inputs": {"a": 1}},
                },
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["result"] == {"status": "completed"}
        orch.execute_workflow.assert_called_once_with("wf-1", {"a": 1})

    def test_execute_workflow_member_critical_403(self, client):
        from advanced_workflow_orchestrator import (
            WorkflowDefinition,
            WorkflowStep,
            WorkflowStepType,
        )

        orch = MagicMock()
        orch.workflows = {
            "wf-1": WorkflowDefinition(
                workflow_id="wf-1",
                name="wf-1",
                description="",
                steps=[WorkflowStep(
                    step_id="s1",
                    step_type=WorkflowStepType.EMAIL_SEND,
                    description="d",
                    parameters={},
                    next_steps=[],
                )],
                start_step="s1",
                version="1",
            )
        }
        orch.execute_workflow = AsyncMock()
        from api.intelligence_routes import router

        member_client = make_client(
            router, {get_current_user: user_override(role="member")}
        )
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orch):
            resp = member_client.post(
                "/api/intelligence/execute",
                json={
                    "action_type": "workflow",
                    "action_payload": {"workflow_id": "wf-1", "inputs": {}},
                },
            )
        assert resp.status_code == 403
        orch.execute_workflow.assert_not_called()

    def test_execute_workflow_unknown_definition_403(self, client):
        orch = MagicMock()
        orch.workflows = {}
        orch.execute_workflow = AsyncMock()
        with patch("advanced_workflow_orchestrator.get_orchestrator",
                   return_value=orch):
            resp = client.post(
                "/api/intelligence/execute",
                json={
                    "action_type": "workflow",
                    "action_payload": {"workflow_id": "ghost", "inputs": {}},
                },
            )
        assert resp.status_code == 403

    def test_execute_tool_benign_success(self, client):
        with patch("integrations.mcp_service.mcp_service.execute_tool",
                   new_callable=AsyncMock) as mt:
            mt.return_value = {"status": "ok"}
            resp = client.post(
                "/api/intelligence/execute",
                json={
                    "action_type": "tool",
                    "action_payload": {
                        "tool_name": "present_markdown",
                        "arguments": {"markdown": "# hi"},
                    },
                },
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["result"] == {"status": "ok"}
        mt.assert_awaited_once()
        args = mt.call_args
        assert args[0][0] == "local-tools"
        assert args[0][1] == "present_markdown"
        assert args[0][3]["user_id"] == "u-72c"

    def test_execute_tool_critical_member_403(self, client):
        from api.intelligence_routes import router

        member_client = make_client(
            router, {get_current_user: user_override(role="member")}
        )
        with patch("integrations.mcp_service.mcp_service.execute_tool",
                   new_callable=AsyncMock) as mt:
            resp = member_client.post(
                "/api/intelligence/execute",
                json={
                    "action_type": "tool",
                    "action_payload": {
                        "tool_name": "terminal_command",
                        "arguments": {},
                    },
                },
            )
        assert resp.status_code == 403
        mt.assert_not_called()

    def test_execute_tool_trigger_workflow_member_403(self, client):
        from api.intelligence_routes import router

        member_client = make_client(
            router, {get_current_user: user_override(role="member")}
        )
        with patch("integrations.mcp_service.mcp_service.execute_tool",
                   new_callable=AsyncMock) as mt:
            resp = member_client.post(
                "/api/intelligence/execute",
                json={
                    "action_type": "tool",
                    "action_payload": {"tool_name": "trigger_workflow", "arguments": {}},
                },
            )
        assert resp.status_code == 403
        mt.assert_not_called()

    def test_execute_unsupported_action_422(self, client):
        resp = client.post(
            "/api/intelligence/execute",
            json={"action_type": "nope", "action_payload": {}},
        )
        assert resp.status_code == 422

    def test_execute_missing_action_422(self, client):
        resp = client.post("/api/intelligence/execute", json={})
        assert resp.status_code == 422

    def test_execute_generic_error_is_500(self, client):
        with patch("integrations.mcp_service.mcp_service.execute_tool",
                   new_callable=AsyncMock) as mt:
            mt.side_effect = RuntimeError("boom")
            resp = client.post(
                "/api/intelligence/execute",
                json={
                    "action_type": "tool",
                    "action_payload": {"tool_name": "present_markdown", "arguments": {}},
                },
            )
        assert resp.status_code == 500
        assert "boom" not in resp.text

    def test_execute_http_exception_passthrough(self, client):
        with patch("integrations.mcp_service.mcp_service.execute_tool",
                   new_callable=AsyncMock) as mt:
            mt.side_effect = HTTPException(status_code=409, detail="conflict")
            resp = client.post(
                "/api/intelligence/execute",
                json={
                    "action_type": "tool",
                    "action_payload": {"tool_name": "present_markdown", "arguments": {}},
                },
            )
        assert resp.status_code == 409


# ============================================================================
# 3. api/mcp_server_routes.py
# ============================================================================

class TestMcpServerRoutes:
    """Gap-fill coverage for mcp_server_routes (60% -> >=95%)."""

    @pytest.fixture
    def client(self):
        from api.mcp_server_routes import router, get_current_user as mcp_auth

        return make_client(router, {mcp_auth: user_override()})

    def test_requires_auth(self):
        from api.mcp_server_routes import router

        client = make_client(router)
        assert client.post("/mcp/", json={"jsonrpc": "2.0"}).status_code == 401
        assert client.get("/mcp/sse").status_code == 401

    def test_post_single_response(self, client):
        with patch("api.mcp_server_routes.handle_jsonrpc",
                   new_callable=AsyncMock) as h:
            h.return_value = {"jsonrpc": "2.0", "id": 1, "result": {}}
            resp = client.post("/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert resp.status_code == 200
        assert resp.json()["result"] == {}
        h.assert_awaited_once()

    def test_post_notification_202(self, client):
        with patch("api.mcp_server_routes.handle_jsonrpc",
                   new_callable=AsyncMock) as h:
            h.return_value = None
            resp = client.post(
                "/mcp/",
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            )
        assert resp.status_code == 202
        assert resp.json() == {}

    def test_post_invalid_json_400(self, client):
        resp = client.post(
            "/mcp/",
            content="{not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_post_batch_mixed(self, client):
        with patch("api.mcp_server_routes.handle_jsonrpc",
                   new_callable=AsyncMock) as h:
            async def side(req):
                if req.get("method") == "notifications/initialized":
                    return None
                return {"jsonrpc": "2.0", "id": req["id"], "result": {}}

            h.side_effect = side
            resp = client.post(
                "/mcp/",
                json=[
                    {"jsonrpc": "2.0", "id": 1, "method": "ping"},
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                ],
            )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["id"] == 1

    def test_post_batch_all_notifications_empty_object(self, client):
        with patch("api.mcp_server_routes.handle_jsonrpc",
                   new_callable=AsyncMock) as h:
            h.return_value = None
            resp = client.post(
                "/mcp/",
                json=[
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                ],
            )
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_post_disabled_503(self):
        from api.mcp_server_routes import router, get_current_user as mcp_auth

        client = make_client(router, {mcp_auth: user_override()})
        with patch("api.mcp_server_routes.MCP_SERVER_ENABLED", False):
            resp = client.post("/mcp/", json={"jsonrpc": "2.0", "id": 1})
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_sse_stream(self, client):
        from api.mcp_server_routes import mcp_sse

        async def _sleep(_seconds):
            raise RuntimeError("stream closed")

        with patch("asyncio.sleep", side_effect=_sleep):
            resp = await mcp_sse(fake_user())
        assert resp.media_type == "text/event-stream"
        assert resp.headers["Cache-Control"] == "no-cache"
        assert resp.headers["Connection"] == "keep-alive"
        chunks = []
        with pytest.raises(RuntimeError):
            async for chunk in resp.body_iterator:
                chunks.append(chunk)
        joined = b"".join(chunks).decode()
        assert "event: endpoint" in joined
        assert "event: ping" in joined

    def test_sse_disabled_503(self):
        from api.mcp_server_routes import router, get_current_user as mcp_auth

        client = make_client(router, {mcp_auth: user_override()})
        with patch("api.mcp_server_routes.MCP_SERVER_ENABLED", False):
            resp = client.get("/mcp/sse")
        assert resp.status_code == 503


# ============================================================================
# 5. api/notification_settings_routes.py
# ============================================================================

class TestNotificationSettingsRoutes:
    """Gap-fill coverage for notification_settings_routes (43% -> >=95%)."""

    @pytest.fixture
    def client(self):
        from api.notification_settings_routes import router

        return make_client(router, {get_current_user: user_override()})

    def _workflow(self, created_by="u-72c"):
        wf = MagicMock()
        wf.id = "wf-1"
        wf.created_by = created_by
        return wf

    def test_requires_auth(self):
        from api.notification_settings_routes import router

        client = make_client(router)
        assert client.get("/api/notifications/wf-1").status_code == 401
        assert client.put("/api/notifications/wf-1", json={}).status_code == 401
        assert client.post("/api/notifications/wf-1/test").status_code == 401

    def test_get_settings_success(self, client):
        session = MagicMock()
        session_cls = MagicMock()
        session_cls.return_value = session
        session.query.return_value = _chain(first_return=self._workflow())
        settings = MagicMock()
        settings.to_dict.return_value = {"enabled": True, "slack_channel": "#ops"}
        with patch("core.database.SessionLocal", session_cls), \
                patch("core.models.Workflow", MagicMock()), \
                patch("core.workflow_notifier.get_notification_settings",
                      return_value=settings):
            resp = client.get("/api/notifications/wf-1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["slack_channel"] == "#ops"
        session.close.assert_called_once()

    def test_get_settings_ownerless_workflow(self, client):
        session = MagicMock()
        session_cls = MagicMock()
        session_cls.return_value = session
        session.query.return_value = _chain(first_return=self._workflow(None))
        settings = MagicMock()
        settings.to_dict.return_value = {"enabled": True}
        with patch("core.database.SessionLocal", session_cls), \
                patch("core.models.Workflow", MagicMock()), \
                patch("core.workflow_notifier.get_notification_settings",
                      return_value=settings):
            resp = client.get("/api/notifications/wf-1")
        assert resp.status_code == 200

    def test_get_settings_404_missing(self, client):
        session = MagicMock()
        session_cls = MagicMock()
        session_cls.return_value = session
        session.query.return_value = _chain(first_return=None)
        with patch("core.database.SessionLocal", session_cls), \
                patch("core.models.Workflow", MagicMock()):
            resp = client.get("/api/notifications/ghost")
        assert resp.status_code == 404
        session.close.assert_called_once()

    def test_get_settings_404_other_user(self, client):
        session = MagicMock()
        session_cls = MagicMock()
        session_cls.return_value = session
        session.query.return_value = _chain(first_return=self._workflow("other"))
        with patch("core.database.SessionLocal", session_cls), \
                patch("core.models.Workflow", MagicMock()):
            resp = client.get("/api/notifications/wf-1")
        assert resp.status_code == 404

    def test_update_settings_success(self, client):
        session = MagicMock()
        session_cls = MagicMock()
        session_cls.return_value = session
        session.query.return_value = _chain(first_return=self._workflow())
        saved = {}

        def _set(wf_id, settings):
            saved["wf"] = wf_id
            saved["settings"] = settings

        with patch("core.database.SessionLocal", session_cls), \
                patch("core.models.Workflow", MagicMock()), \
                patch("core.workflow_notifier.set_notification_settings",
                      side_effect=_set):
            resp = client.put(
                "/api/notifications/wf-1",
                json={
                    "enabled": True,
                    "notify_on_success": False,
                    "notify_on_failure": True,
                    "slack_enabled": True,
                    "slack_channel": "#deploy",
                    "slack_mention_users": ["@alice"],
                    "email_enabled": True,
                    "email_recipients": ["a@b.co"],
                    "custom_success_message": "done",
                    "custom_failure_message": "failed",
                },
            )
        assert resp.status_code == 200
        body = resp.json()["data"]["settings"]
        assert body["slack_channel"] == "#deploy"
        assert saved["wf"] == "wf-1"
        s = saved["settings"]
        assert s.notify_on_success is False
        assert s.slack_mention_users == ["@alice"]
        assert s.email_recipients == ["a@b.co"]
        assert s.custom_success_message == "done"
        assert s.custom_failure_message == "failed"

    def test_update_settings_404(self, client):
        session = MagicMock()
        session_cls = MagicMock()
        session_cls.return_value = session
        session.query.return_value = _chain(first_return=None)
        with patch("core.database.SessionLocal", session_cls), \
                patch("core.models.Workflow", MagicMock()):
            resp = client.put("/api/notifications/wf-1", json={})
        assert resp.status_code == 404

    def test_update_settings_422(self, client):
        resp = client.put(
            "/api/notifications/wf-1", json={"enabled": "not-a-bool"}
        )
        assert resp.status_code == 422

    def test_test_notification_disabled_skipped(self, client):
        settings = MagicMock()
        settings.enabled = False
        notifier = MagicMock()
        with patch("core.workflow_notifier.get_notification_settings",
                   return_value=settings), \
                patch("core.workflow_notifier.notifier", notifier):
            resp = client.post("/api/notifications/wf-1/test")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "skipped"
        notifier.notify_completion.assert_not_called()

    def test_test_notification_success(self, client):
        settings = MagicMock()
        settings.enabled = True
        notifier = MagicMock()
        notifier.notify_completion = AsyncMock(return_value=None)
        with patch("core.workflow_notifier.get_notification_settings",
                   return_value=settings), \
                patch("core.workflow_notifier.notifier", notifier):
            resp = client.post("/api/notifications/wf-1/test")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "success"
        notifier.notify_completion.assert_awaited_once()
        _, kwargs = notifier.notify_completion.call_args
        assert kwargs["workflow_id"] == "wf-1"
        assert kwargs["execution_id"] == "test-wf-1"
        assert kwargs["workflow_name"] == "Test Workflow"

    def test_test_notification_error_500(self, client):
        settings = MagicMock()
        settings.enabled = True
        notifier = MagicMock()
        notifier.notify_completion = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("core.workflow_notifier.get_notification_settings",
                   return_value=settings), \
                patch("core.workflow_notifier.notifier", notifier):
            resp = client.post("/api/notifications/wf-1/test")
        assert resp.status_code == 500
        assert "boom" not in resp.text


# ============================================================================
# 6. api/nav_stub_routes.py
# ============================================================================

class TestNavStubRoutes:
    """Full coverage for nav_stub_routes (never tested)."""

    @pytest.fixture
    def client(self):
        from api.nav_stub_routes import router

        return make_client(
            router,
            {get_current_user: user_override(), get_db: lambda: MagicMock()},
        )

    def test_requires_auth(self):
        from api.nav_stub_routes import router

        client = make_client(router, {get_db: lambda: MagicMock()})
        assert client.get("/api/v1/tasks").status_code == 401
        assert client.get("/api/v1/projects").status_code == 401
        assert client.get(
            "/api/atom/communication/live/support/tickets"
        ).status_code == 401
        assert client.get(
            "/api/atom/communication/memory/analytics"
        ).status_code == 401
        assert client.get("/api/atom/communication/memory/apps").status_code == 401
        assert client.get("/api/integrations/slack/health").status_code == 401

    def _task(self, tid="t-1", title="Task 1", description="desc", status="todo",
              priority="high", due=None, project="p-1"):
        from core.models import UserTask

        t = UserTask(
            id=tid,
            tenant_id="t-1",
            user_id="u-72c",
            project_id=project,
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_date=due,
        )
        t.created_at = datetime(2026, 1, 1, 12, 0, 0)
        t.updated_at = datetime(2026, 1, 1, 12, 5, 0)
        return t

    def test_list_tasks_success(self, client):
        db = MagicMock()
        db.query.return_value = _chain(rows_return=[self._task()])
        client.app.dependency_overrides[get_db] = lambda: db
        resp = client.get("/api/v1/tasks?limit=10&offset=5")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) == 1
        t = tasks[0]
        assert t["id"] == "t-1"
        assert t["title"] == "Task 1"
        assert t["description"] == "desc"
        assert t["status"] == "todo"
        assert t["priority"] == "high"
        assert t["dueDate"] is not None
        assert t["createdAt"] == "2026-01-01T12:00:00"
        assert t["projectId"] == "p-1"

    def test_list_tasks_empty(self, client):
        db = MagicMock()
        db.query.return_value = _chain(rows_return=[])
        client.app.dependency_overrides[get_db] = lambda: db
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        assert resp.json()["tasks"] == []

    def test_list_tasks_exception_returns_empty(self, client):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        client.app.dependency_overrides[get_db] = lambda: db
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        assert resp.json()["tasks"] == []

    def test_list_projects(self, client):
        resp = client.get("/api/v1/projects")
        assert resp.status_code == 200
        assert resp.json() == {"projects": []}

    def _ticket(self, tid="tk-1", subject="Need help", status="open",
                priority="medium"):
        from core.models import SupportTicket

        tk = SupportTicket(
            id=tid,
            tenant_id="t-1",
            workspace_id="w-1",
            user_id="u-72c",
            subject=subject,
            description="details",
            status=status,
            priority=priority,
        )
        tk.created_at = datetime(2026, 1, 1, 12, 0, 0)
        return tk

    def test_list_support_tickets_success(self, client):
        db = MagicMock()
        db.query.return_value = _chain(rows_return=[self._ticket()])
        client.app.dependency_overrides[get_db] = lambda: db
        resp = client.get("/api/atom/communication/live/support/tickets")
        assert resp.status_code == 200
        tickets = resp.json()["tickets"]
        assert len(tickets) == 1
        assert tickets[0]["id"] == "tk-1"
        assert tickets[0]["subject"] == "Need help"
        assert tickets[0]["status"] == "open"
        assert tickets[0]["priority"] == "medium"
        assert tickets[0]["created_at"] == "2026-01-01T12:00:00"

    def test_list_support_tickets_exception_returns_empty(self, client):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        client.app.dependency_overrides[get_db] = lambda: db
        resp = client.get("/api/atom/communication/live/support/tickets")
        assert resp.status_code == 200
        assert resp.json()["tickets"] == []

    def test_communication_analytics(self, client):
        resp = client.get("/api/atom/communication/memory/analytics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["analytics"]["status_distribution"] == {
            "unread": 0, "read": 0, "responded": 0,
        }
        assert body["analytics"]["performance"]["response_rate"] == 0.0

    def test_communication_apps(self, client):
        resp = client.get("/api/atom/communication/memory/apps")
        assert resp.status_code == 200
        assert resp.json() == {"apps": []}

    def test_integration_health(self, client):
        resp = client.get("/api/integrations/slack/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "slack"
        assert body["status"] == "not_configured"
        assert "not configured" in body["message"]


# ============================================================================
# 7. api/ai_workflows_routes.py
# ============================================================================

class TestAIWorkflowsRoutes:
    """Gap-fill coverage for ai_workflows_routes (91% -> >=95%)."""

    @pytest.fixture
    def client(self):
        from api.ai_workflows_routes import router

        return make_client(router, {get_current_user: user_override()})

    def _fallback_service(self, text=None):
        svc = MagicMock()
        svc.process_with_nlu = AsyncMock(
            side_effect=Exception("service unavailable")
        )
        svc.analyze_text = AsyncMock(return_value="completed text")
        return svc

    def test_requires_auth(self):
        from api.ai_workflows_routes import router

        client = make_client(router)
        assert client.post("/api/ai-workflows/nlu/parse", json={
            "text": "hi"}).status_code == 401
        assert client.get("/api/ai-workflows/providers").status_code == 401
        assert client.post("/api/ai-workflows/complete", json={
            "prompt": "hi"}).status_code == 401

    def test_parse_nlu_missing_text_422(self, client):
        assert client.post("/api/ai-workflows/nlu/parse", json={}).status_code == 422
        assert client.post("/api/ai-workflows/complete", json={}).status_code == 422

    def test_fallback_intent_communication(self, client):
        svc = self._fallback_service()
        with patch("enhanced_ai_workflow_endpoints.ai_service", svc):
            resp = client.post(
                "/api/ai-workflows/nlu/parse",
                json={"text": "send an email to boss@corp.com"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["intent"] == "communication"
        assert body["provider_used"] == "fallback"
        assert body["confidence"] == 0.7
        assert {"type": "email", "value": "boss@corp.com"} in body["entities"]

    def test_fallback_intent_creation(self, client):
        svc = self._fallback_service()
        with patch("enhanced_ai_workflow_endpoints.ai_service", svc):
            resp = client.post(
                "/api/ai-workflows/nlu/parse",
                json={"text": "create a new report"},
            )
        assert resp.status_code == 200
        assert resp.json()["intent"] == "creation"

    def test_fallback_intent_workflow_creation(self, client):
        svc = self._fallback_service()
        with patch("enhanced_ai_workflow_endpoints.ai_service", svc):
            resp = client.post(
                "/api/ai-workflows/nlu/parse",
                json={"text": "automate the workflow"},
            )
        assert resp.status_code == 200
        assert resp.json()["intent"] == "workflow_creation"

    def test_fallback_intent_general_with_number_entity(self, client):
        svc = self._fallback_service()
        with patch("enhanced_ai_workflow_endpoints.ai_service", svc):
            resp = client.post(
                "/api/ai-workflows/nlu/parse",
                json={"text": "remind me in 7 days"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["intent"] == "general"
        assert {"type": "number", "value": "7"} in body["entities"]

    def test_fallback_extracts_multiple_entities(self, client):
        svc = self._fallback_service()
        with patch("enhanced_ai_workflow_endpoints.ai_service", svc):
            resp = client.post(
                "/api/ai-workflows/nlu/parse",
                json={"text": "find order 42 and email a@b.co"},
            )
        assert resp.status_code == 200
        entities = resp.json()["entities"]
        assert {"type": "number", "value": "42"} in entities
        assert {"type": "email", "value": "a@b.co"} in entities

    def test_fallback_tasks_truncated(self, client):
        svc = self._fallback_service()
        long_text = "x" * 300
        with patch("enhanced_ai_workflow_endpoints.ai_service", svc):
            resp = client.post(
                "/api/ai-workflows/nlu/parse", json={"text": long_text}
            )
        assert resp.status_code == 200
        assert resp.json()["tasks"] == [f"Process: {long_text[:100]}"]

    def test_nlu_success_path(self, client):
        svc = MagicMock()
        svc.process_with_nlu = AsyncMock(return_value={
            "intent": "scheduling",
            "entities": [{"type": "email", "value": "a@b.co"}],
            "tasks": ["t1"],
            "confidence": 0.9,
            "ai_provider_used": "deepseek",
        })
        with patch("enhanced_ai_workflow_endpoints.ai_service", svc):
            resp = client.post(
                "/api/ai-workflows/nlu/parse",
                json={"text": "schedule a meeting with a@b.co"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["intent"] == "scheduling"
        assert body["provider_used"] == "deepseek"
        assert body["confidence"] == 0.9
        assert body["tasks"] == ["t1"]
        assert body["entities"] == [{"type": "email", "value": "a@b.co"}]
        assert body["request_id"].startswith("nlu_")

    def test_nlu_success_non_list_entities(self, client):
        svc = MagicMock()
        svc.process_with_nlu = AsyncMock(return_value={
            "intent": "general",
            "entities": "not-a-list",
            "tasks": [],
        })
        with patch("enhanced_ai_workflow_endpoints.ai_service", svc):
            resp = client.post(
                "/api/ai-workflows/nlu/parse",
                json={"text": "hello"},
            )
        assert resp.status_code == 200
        assert resp.json()["entities"] == []

    def test_providers_error_branch(self, client):
        with patch.dict(sys.modules, {"enhanced_ai_workflow_endpoints": None}):
            resp = client.get("/api/ai-workflows/providers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["default"] == "openai"
        assert all(not p["enabled"] for p in body["providers"])

    def test_complete_success(self, client):
        svc = MagicMock()
        svc.analyze_text = AsyncMock(return_value="Hello world")
        with patch("enhanced_ai_workflow_endpoints.ai_service", svc):
            resp = client.post(
                "/api/ai-workflows/complete",
                json={"prompt": "say hello", "provider": "deepseek"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["completion"] == "Hello world"
        assert body["provider_used"] == "deepseek"
        assert body["tokens_used"] == 4

    def test_complete_fallback_error_response(self, client):
        svc = MagicMock()
        svc.analyze_text = AsyncMock(side_effect=Exception("down"))
        with patch("enhanced_ai_workflow_endpoints.ai_service", svc):
            resp = client.post(
                "/api/ai-workflows/complete",
                json={"prompt": "say hello"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider_used"] == "error"
        assert body["tokens_used"] == 0
        assert "unavailable" in body["completion"].lower()
