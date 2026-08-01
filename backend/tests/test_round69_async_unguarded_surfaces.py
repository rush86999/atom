"""
Round 69 — Theme A: async/unguarded execution surfaces (Red-Green-Refactor).

Closes two gaps:
  * execution surfaces that reach critical MCP tools / workflow execution
    without the R67/R68 ``WORKFLOW_MANAGE`` gate (``core/workflow_security.py``)
  * fail-open async triggers (event-triggered critical workflows, Shopify HMAC,
    scheduler node sinks, unauthenticated generate-from-agent, teams/gmail webhooks)

Every test below asserts the *new* secure behaviour; each had a failing red
phase before the corresponding fix landed.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from advanced_workflow_orchestrator import (
    AdvancedWorkflowOrchestrator,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepType,
)
from core.auth import get_current_user as auth_get_current_user
from core.database import get_db
from core.webhook_handlers import WebhookEvent
from core.workflow_security import (
    has_critical_automation_nodes,
    has_critical_definition,
    has_critical_step,
    require_workflow_trigger_tool,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers (mirror R68)
# ---------------------------------------------------------------------------


def user(role="member"):
    return MagicMock(id="u-69", email="u@example.com", role=role, tenant_id="tenant-69")


def make_client(router_obj, role=None):
    app = FastAPI()
    app.include_router(router_obj)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    if role:
        app.dependency_overrides[auth_get_current_user] = lambda: user(role)
    return TestClient(app, raise_server_exceptions=False)


def _run(coro):
    return asyncio.run(coro)


def _ctx(workflow_id="wf-1"):
    ctx = WorkflowContext(
        workflow_id=f"exec-{workflow_id}",
        input_data={},
        status=WorkflowStatus.COMPLETED,
        started_at=None,
        completed_at=None,
    )
    ctx.error_message = "ok"
    return ctx


def step(step_type, step_id="s1", **params):
    return WorkflowStep(
        step_id=step_id,
        step_type=step_type,
        description="d",
        parameters=params,
        next_steps=[],
    )


def definition(workflow_id, steps):
    return WorkflowDefinition(
        workflow_id=workflow_id,
        name=workflow_id,
        description="",
        steps=steps,
        start_step=steps[0].step_id if steps else "end",
        version="1",
    )


def make_orchestrator(workflows=None, templates=None):
    orch = MagicMock()
    orch.workflows = dict(workflows or {})
    tm = MagicMock()
    tm.get_template = MagicMock(side_effect=lambda wid: (templates or {}).get(wid))
    orch.template_manager = tm
    orch.execute_workflow = AsyncMock()
    return orch


def _hmac_header(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


# ---------------------------------------------------------------------------
# A2 helpers — require_workflow_trigger_tool
# ---------------------------------------------------------------------------


class TestWorkflowTriggerToolHelper:
    def test_member_trigger_tool_403(self):
        with pytest.raises(HTTPException) as ei:
            _run(require_workflow_trigger_tool(user("member"), "trigger_workflow"))
        assert ei.value.status_code == 403

    def test_member_benign_tool_pass(self):
        _run(require_workflow_trigger_tool(user("member"), "present_markdown"))

    def test_team_lead_trigger_tool_pass(self):
        _run(require_workflow_trigger_tool(user("team_lead"), "trigger_workflow"))

    def test_none_tool_not_trigger(self):
        _run(require_workflow_trigger_tool(user("member"), None))


# ---------------------------------------------------------------------------
# A1 — POST /api/mcp/execute critical-tool gate
# ---------------------------------------------------------------------------


class TestMCPExecuteCriticalGate:
    def test_anon_401(self):
        from integrations.mcp_routes import router

        client = make_client(router)
        resp = client.post(
            "/api/mcp/execute",
            json={"server_id": "local-tools", "tool_name": "present_markdown", "arguments": {}},
        )
        assert resp.status_code == 401

    def test_member_critical_403(self):
        from integrations.mcp_routes import router

        client = make_client(router, role="member")
        with patch("integrations.mcp_service.mcp_service.execute_tool", new_callable=AsyncMock) as mt:
            resp = client.post(
                "/api/mcp/execute",
                json={"server_id": "local-tools", "tool_name": "browser_navigate", "arguments": {}},
            )
        assert resp.status_code == 403
        mt.assert_not_called()

    def test_member_benign_200(self):
        from integrations.mcp_routes import router

        client = make_client(router, role="member")
        with patch("integrations.mcp_service.mcp_service.execute_tool", new_callable=AsyncMock) as mt:
            mt.return_value = {"ok": True}
            resp = client.post(
                "/api/mcp/execute",
                json={"server_id": "local-tools", "tool_name": "present_markdown", "arguments": {}},
            )
        assert resp.status_code == 200
        mt.assert_called_once()

    def test_team_lead_critical_200(self):
        from integrations.mcp_routes import router

        client = make_client(router, role="team_lead")
        with patch("integrations.mcp_service.mcp_service.execute_tool", new_callable=AsyncMock) as mt:
            mt.return_value = {"ok": True}
            resp = client.post(
                "/api/mcp/execute",
                json={"server_id": "local-tools", "tool_name": "browser_navigate", "arguments": {}},
            )
        assert resp.status_code == 200
        mt.assert_called_once()


# ---------------------------------------------------------------------------
# A2 — trigger_workflow MCP tool gate (route + service defense-in-depth)
# ---------------------------------------------------------------------------


class TestMCPExecuteTriggerWorkflow:
    def test_member_trigger_workflow_403(self):
        from integrations.mcp_routes import router

        client = make_client(router, role="member")
        with patch("integrations.mcp_service.mcp_service.execute_tool", new_callable=AsyncMock) as mt:
            resp = client.post(
                "/api/mcp/execute",
                json={"server_id": "local-tools", "tool_name": "trigger_workflow", "arguments": {"workflow_id": "wf-1"}},
            )
        assert resp.status_code == 403
        mt.assert_not_called()

    def test_team_lead_trigger_workflow_200(self):
        from integrations.mcp_routes import router

        client = make_client(router, role="team_lead")
        with patch("integrations.mcp_service.mcp_service.execute_tool", new_callable=AsyncMock) as mt:
            mt.return_value = {"ok": True}
            resp = client.post(
                "/api/mcp/execute",
                json={"server_id": "local-tools", "tool_name": "trigger_workflow", "arguments": {"workflow_id": "wf-1"}},
            )
        assert resp.status_code == 200

    def test_intelligence_route_member_trigger_workflow_403(self):
        from api.intelligence_routes import router

        client = make_client(router, role="member")
        with patch("integrations.mcp_service.mcp_service.execute_tool", new_callable=AsyncMock) as mt:
            resp = client.post(
                "/api/intelligence/execute",
                json={"action_type": "tool", "action_payload": {"tool_name": "trigger_workflow", "arguments": {"workflow_id": "wf-1"}}},
            )
        assert resp.status_code == 403
        mt.assert_not_called()

    def test_service_half_critical_refused(self):
        from integrations.mcp_service import mcp_service

        orch = make_orchestrator({"wf-1": definition("wf-1", [step(WorkflowStepType.TERMINAL)])})
        with patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orch):
            result = _run(mcp_service.execute_tool("local-tools", "trigger_workflow", {"workflow_id": "wf-1", "input_data": {}}))
        assert isinstance(result, dict)
        assert "error" in result
        orch.execute_workflow.assert_not_called()

    def test_service_half_benign_executes(self):
        from integrations.mcp_service import mcp_service

        orch = make_orchestrator({"wf-2": definition("wf-2", [step(WorkflowStepType.SLACK_NOTIFICATION)])})
        orch.execute_workflow = AsyncMock(return_value=_ctx("wf-2"))
        with patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orch):
            result = _run(mcp_service.execute_tool("local-tools", "trigger_workflow", {"workflow_id": "wf-2", "input_data": {}}))
        assert result["status"] == WorkflowStatus.COMPLETED.value
        orch.execute_workflow.assert_called_once()

    def test_service_half_unknown_fails_closed(self):
        from integrations.mcp_service import mcp_service

        orch = make_orchestrator(workflows={})
        with patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orch):
            result = _run(mcp_service.execute_tool("local-tools", "trigger_workflow", {"workflow_id": "nope", "input_data": {}}))
        assert isinstance(result, dict)
        assert "error" in result
        orch.execute_workflow.assert_not_called()


# ---------------------------------------------------------------------------
# A3 — trigger_event critical-step guard + first-party opt-in flag
# ---------------------------------------------------------------------------


def _bare_orch(workflows):
    orch = AdvancedWorkflowOrchestrator.__new__(AdvancedWorkflowOrchestrator)
    orch.workflows = workflows
    return orch


class TestTriggerEventCriticalSkip:
    def test_critical_not_flagged_not_fired(self):
        orch = _bare_orch({"wf-crit": definition("wf-crit", [step(WorkflowStepType.TERMINAL)])})
        orch.workflows["wf-crit"].triggers = ["EVENT"]
        orch.execute_workflow = AsyncMock(return_value=_ctx("wf-crit"))
        with patch("asyncio.create_task", new_callable=MagicMock) as ct:
            count = _run(orch.trigger_event("EVENT", {}))
        assert count == 0
        ct.assert_not_called()
        orch.execute_workflow.assert_not_called()

    def test_critical_flagged_fires(self):
        orch = _bare_orch({"wf-crit": definition("wf-crit", [step(WorkflowStepType.TERMINAL)])})
        orch.workflows["wf-crit"].triggers = ["EVENT"]
        orch.workflows["wf-crit"].allow_event_critical = True
        orch.execute_workflow = AsyncMock(return_value=_ctx("wf-crit"))
        with patch("asyncio.create_task", wraps=asyncio.ensure_future) as ct:
            count = _run(orch.trigger_event("EVENT", {}))
        assert count == 1
        assert ct.call_count == 1

    def test_benign_fires(self):
        orch = _bare_orch({"wf-benign": definition("wf-benign", [step(WorkflowStepType.SLACK_NOTIFICATION)])})
        orch.workflows["wf-benign"].triggers = ["EVENT"]
        orch.execute_workflow = AsyncMock(return_value=_ctx("wf-benign"))
        with patch("asyncio.create_task", wraps=asyncio.ensure_future) as ct:
            count = _run(orch.trigger_event("EVENT", {}))
        assert count == 1
        assert ct.call_count == 1

    def test_builtin_email_flows_flagged_and_critical(self):
        orch = AdvancedWorkflowOrchestrator()
        for wid in ("b2b_lead_triage", "autonomous_interview_scheduler"):
            wf = orch.workflows.get(wid)
            assert wf is not None, f"{wid} must remain a built-in workflow"
            assert getattr(wf, "allow_event_critical", False) is True
            assert has_critical_step(wf.steps) is True


# ---------------------------------------------------------------------------
# A4 — Shopify webhooks fail-closed HMAC
# ---------------------------------------------------------------------------


class TestShopifyWebhookFailClosed:
    def test_verify_false_when_secret_unset(self):
        from integrations import shopify_webhooks

        def fake_getenv(name, default=None):
            if name in ("SHOPIFY_WEBHOOK_SECRET", "SHOPIFY_API_SECRET"):
                return None
            return os.environ.get(name, default)

        with patch("integrations.shopify_webhooks.os.getenv", side_effect=fake_getenv):
            assert shopify_webhooks.verify_shopify_webhook(b"{}", "abc") is False

    def test_missing_header_401(self):
        from integrations.shopify_webhooks import router

        client = make_client(router)
        resp = client.post(
            "/api/webhooks/shopify/orders-create", json={"customer": {"email": "a@b.c"}}
        )
        assert resp.status_code == 401

    def test_bad_hmac_401(self):
        from integrations.shopify_webhooks import router

        client = make_client(router)
        resp = client.post(
            "/api/webhooks/shopify/orders-create",
            json={"customer": {"email": "a@b.c"}},
            headers={"X-Shopify-Hmac-Sha256": "bogus"},
        )
        assert resp.status_code == 401

    def test_unset_secret_with_header_401(self):
        from integrations.shopify_webhooks import router

        client = make_client(router)
        with patch("integrations.shopify_webhooks.os.getenv", return_value=None):
            resp = client.post(
                "/api/webhooks/shopify/orders-create",
                json={"customer": {"email": "a@b.c"}},
                headers={"X-Shopify-Hmac-Sha256": "bogus"},
            )
        assert resp.status_code == 401

    def test_valid_hmac_200(self):
        from integrations.shopify_webhooks import router

        secret = "shopify-test-secret"
        body = json.dumps({"customer": {"email": "a@b.c"}}).encode()
        header = _hmac_header(secret, body)
        client = make_client(router)
        with patch.dict(os.environ, {"SHOPIFY_WEBHOOK_SECRET": secret}), patch(
            "integrations.shopify_webhooks.get_workspace_id", new_callable=AsyncMock
        ) as m_gw, patch(
            "integrations.shopify_webhooks.CustomerResolutionEngine"
        ) as m_cre, patch(
            "integrations.shopify_webhooks.AdvancedWorkflowOrchestrator"
        ) as m_orch:
            m_gw.return_value = "tenant-1"
            m_cre.return_value.resolve_customer = MagicMock(return_value=MagicMock(id="c1"))
            resp = client.post(
                "/api/webhooks/shopify/orders-create",
                content=body,
                headers={"X-Shopify-Hmac-Sha256": header, "X-Shopify-Shop-Domain": "shop.myshopify.com"},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# A5 — /generate-from-agent auth + token-derived identity
# ---------------------------------------------------------------------------


class TestGenerateFromAgentAuth:
    def test_anon_401(self):
        from advanced_workflow_api import router

        client = make_client(router)
        resp = client.post(
            "/api/v1/workflows/generate-from-agent", json={"prompt": "Build a workflow"}
        )
        assert resp.status_code == 401

    def test_member_200_token_identity(self):
        from ai.nlp_engine import RouteCategory
        from advanced_workflow_api import router

        client = make_client(router, role="member")
        with patch("core.llm_service.LLMService") as m_llm, patch(
            "ai.nlp_engine.NaturalLanguageEngine"
        ) as m_nlu, patch("core.agents.queen_agent.QueenAgent") as m_queen:
            m_nlu.return_value.classify_route = AsyncMock(
                return_value=MagicMock(category=RouteCategory.AUTOMATION, reasoning="r")
            )
            m_queen.return_value.generate_blueprint = AsyncMock(
                return_value={"architecture_name": "n", "description": "d", "nodes": []}
            )
            m_queen.return_value.realize_blueprint = AsyncMock(return_value="wf-69")
            resp = client.post(
                "/api/v1/workflows/generate-from-agent",
                json={"prompt": "p", "tenant_id": "evil-tenant", "user_id": "evil-user"},
            )
        assert resp.status_code == 200
        # token-derived tenant/user, not the spoofed body fields
        assert m_llm.call_args.kwargs["tenant_id"] == "tenant-69"
        assert m_queen.call_args.kwargs["tenant_id"] == "tenant-69"
        assert m_queen.return_value.realize_blueprint.call_args.kwargs["tenant_id"] == "tenant-69"

    def test_member_without_workflow_run_403(self):
        from advanced_workflow_api import router
        from core.rbac_service import RBACService

        client = make_client(router, role="member")
        with patch.object(RBACService, "check_permission", return_value=False):
            resp = client.post(
                "/api/v1/workflows/generate-from-agent", json={"prompt": "p"}
            )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# A6 — scheduler critical-node sink + authorized threading
# ---------------------------------------------------------------------------


class FakeEngine:
    def __init__(self):
        self.executions = {}

    async def execute_workflow_definition(self, workflow, input_data, execution_id=None):
        self.executions[execution_id] = {"workflow_id": workflow.get("id")}
        return {"status": "completed"}


class TestWorkflowSchedulerCriticalNodes:
    def _node(self, action_type):
        return {"id": "n1", "type": "action", "config": {"actionType": action_type}}

    def test_has_critical_automation_nodes_unit(self):
        assert has_critical_automation_nodes({"nodes": [self._node("send_email")]}) is True
        assert has_critical_automation_nodes({"nodes": [self._node("run_agent_task")]}) is True
        assert has_critical_automation_nodes({"nodes": [self._node("notify")]}) is False
        assert has_critical_automation_nodes({"nodes": []}) is False
        assert has_critical_automation_nodes(None) is False

    def test_has_critical_definition_misses_nodes(self):
        defn = {"id": "wf", "nodes": [self._node("send_email")]}
        assert has_critical_definition(defn) is False
        assert has_critical_automation_nodes(defn) is True

    def test_execute_job_skips_critical_nodes_when_not_authorized(self):
        from ai.workflow_scheduler import WorkflowScheduler

        defn = {"id": "wf-node", "workflow_id": "wf-node", "nodes": [self._node("send_email")]}
        engine = FakeEngine()
        with patch("ai.automation_engine.AutomationEngine", return_value=engine), patch(
            "core.workflow_endpoints.load_workflows", return_value=[defn]
        ):
            _run(WorkflowScheduler._execute_job("wf-node", {}, False))
        assert engine.executions == {}

    def test_execute_job_runs_critical_nodes_when_authorized(self):
        from ai.workflow_scheduler import WorkflowScheduler

        defn = {"id": "wf-node", "workflow_id": "wf-node", "nodes": [self._node("send_email")]}
        engine = FakeEngine()
        with patch("ai.automation_engine.AutomationEngine", return_value=engine), patch(
            "core.workflow_endpoints.load_workflows", return_value=[defn]
        ):
            _run(WorkflowScheduler._execute_job("wf-node", {}, True))
        assert len(engine.executions) == 1

    def test_execute_job_runs_benign_nodes(self):
        from ai.workflow_scheduler import WorkflowScheduler

        defn = {"id": "wf-node", "workflow_id": "wf-node", "nodes": [self._node("notify")]}
        engine = FakeEngine()
        with patch("ai.automation_engine.AutomationEngine", return_value=engine), patch(
            "core.workflow_endpoints.load_workflows", return_value=[defn]
        ):
            _run(WorkflowScheduler._execute_job("wf-node", {}, False))
        assert len(engine.executions) == 1


# ---------------------------------------------------------------------------
# A7 — teams/gmail webhook auth + gmail resume gate
# ---------------------------------------------------------------------------


def _secret_client(router, env_var, secret=None):
    client = make_client(router)
    if secret:
        client.app.dependency_overrides = {}
        client.app.dependency_overrides[get_db] = lambda: MagicMock()
        return TestClient(client.app, raise_server_exceptions=False)
    return client


class TestTeamsGmailWebhookAuth:
    def test_teams_without_secret_401(self):
        from api.webhook_routes import router

        client = make_client(router)

        def fake_getenv(name, default=None):
            if name == "ATOM_TEAMS_WEBHOOK_SECRET":
                return None
            return os.environ.get(name, default)

        with patch("api.webhook_routes.os.getenv", side_effect=fake_getenv), patch(
            "api.webhook_routes.webhook_processor.process_teams_webhook", new_callable=AsyncMock
        ) as m:
            resp = client.post("/api/webhooks/teams", json={})
        assert resp.status_code == 401
        m.assert_not_called()

    def test_teams_correct_bearer_200(self):
        from api.webhook_routes import router

        secret = "teams-secret-69"
        client = make_client(router)
        with patch.dict(os.environ, {"ATOM_TEAMS_WEBHOOK_SECRET": secret}), patch(
            "api.webhook_routes.webhook_processor.process_teams_webhook", new_callable=AsyncMock
        ) as m:
            m.return_value = {"status": "success"}
            resp = client.post(
                "/api/webhooks/teams", json={}, headers={"Authorization": f"Bearer {secret}"}
            )
        assert resp.status_code == 200
        m.assert_called_once()

    def test_teams_wrong_bearer_401(self):
        from api.webhook_routes import router

        client = make_client(router)
        with patch.dict(os.environ, {"ATOM_TEAMS_WEBHOOK_SECRET": "real-secret"}), patch(
            "api.webhook_routes.webhook_processor.process_teams_webhook", new_callable=AsyncMock
        ) as m:
            resp = client.post(
                "/api/webhooks/teams", json={}, headers={"Authorization": "Bearer wrong"}
            )
        assert resp.status_code == 401
        m.assert_not_called()

    def test_gmail_without_secret_401(self):
        from api.webhook_routes import router

        client = make_client(router)

        def fake_getenv(name, default=None):
            if name == "ATOM_GMAIL_WEBHOOK_SECRET":
                return None
            return os.environ.get(name, default)

        with patch("api.webhook_routes.os.getenv", side_effect=fake_getenv), patch(
            "api.webhook_routes.webhook_processor.process_gmail_webhook", new_callable=AsyncMock
        ) as m:
            resp = client.post("/api/webhooks/gmail", json={})
        assert resp.status_code == 401
        m.assert_not_called()

    def test_gmail_correct_bearer_200(self):
        from api.webhook_routes import router

        secret = "gmail-secret-69"
        client = make_client(router)
        with patch.dict(os.environ, {"ATOM_GMAIL_WEBHOOK_SECRET": secret}), patch(
            "api.webhook_routes.webhook_processor.process_gmail_webhook", new_callable=AsyncMock
        ) as m:
            m.return_value = {"status": "success"}
            resp = client.post(
                "/api/webhooks/gmail", json={}, headers={"Authorization": f"Bearer {secret}"}
            )
        assert resp.status_code == 200
        m.assert_called_once()


def _gmail_push_event():
    return WebhookEvent(
        platform="gmail",
        event_type="push_notification",
        event_data={"metadata": {"notification": {"emailAddress": "candidate@x.com"}}},
        raw_payload={},
    )


class TestGmailResumeCriticalGate:
    def _run_resume(self, orch, resume_step="wait_for_reply"):
        from core.webhook_handlers import WebhookProcessor

        proc = WebhookProcessor()
        state = MagicMock()
        state.workflow_execution_id = "exec-1"
        state.candidate_email = "c@x.com"
        state.status = "pending_candidate"
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [state]
        orch.active_contexts = {"exec-1": _ctx("interview_scheduler")}
        orch.resume_workflow = AsyncMock()
        with patch("core.database.get_db_session") as m_db, patch(
            "advanced_workflow_orchestrator.get_orchestrator", return_value=orch
        ), patch("core.models.CandidateBookingState", MagicMock(), create=True):
            m_db.return_value.__enter__.return_value = db
            _run(proc._process_message(_gmail_push_event()))
        return orch.resume_workflow

    def test_resume_refused_critical_not_flagged(self):
        orch = make_orchestrator(
            {"interview_scheduler": definition("interview_scheduler", [step(WorkflowStepType.EMAIL_SEND, step_id="wait_for_reply")])}
        )
        resume = self._run_resume(orch)
        resume.assert_not_called()

    def test_resume_allowed_flagged(self):
        wf = definition("interview_scheduler", [step(WorkflowStepType.EMAIL_SEND, step_id="wait_for_reply")])
        wf.allow_event_critical = True
        orch = make_orchestrator({"interview_scheduler": wf})
        resume = self._run_resume(orch)
        resume.assert_called_once()
