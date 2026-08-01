"""
Round 68 — Sweep workflow trigger paths for the R67 governance bypass
(Red-Green-Refactor).

R67 gated critical MCP tools (terminal/browser/email/write) to WORKFLOW_MANAGE
(TEAM_LEAD+) on only the 4 routes in core/workflow_endpoints.py. Other trigger
paths still executed the same critical local-machine actions with no gate:

  Tier 1 — unauthenticated real execution:
    * advanced_workflow_api /api/v1/workflows/execute + demo endpoints
    * core/workflow_ui_endpoints /execute + /workflows/{id}/execute
  Tier 2 — authenticated but no critical-tool gate:
    * api/intelligence_routes /execute (also trusted a spoofable body user_id)
    * core/atom_agent_endpoints run/schedule/execute-generated
    * api/workflow_template_routes /{id}/execute
    * api/mobile_workflows /trigger (latent, not mounted)
  Tier 3 — anonymous workflow triggers:
    * core/analytics_endpoints /burnout-risk, /deadline-risk
    * core/automation_settings_endpoints GET/POST

This round applies the shared gate (core/workflow_security.py) at every
reachable trigger and adds auth to the anonymous surfaces.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from advanced_workflow_orchestrator import (
    WorkflowContext,
    WorkflowDefinition,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepType,
)
from core.auth import get_current_user as auth_get_current_user
from core.burnout_detection_engine import WellnessScore
from core.database import get_db
from core.workflow_security import (
    has_critical_step,
    has_critical_definition,
    resolve_orchestrator_steps,
    require_workflow_executor,
    require_workflow_executor_orchestrator,
    require_critical_tool,
)
from core.workflow_template_system import TemplateStep

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

CRITICAL_DICT_STEP = {
    "id": "s1",
    "service": "mcp",
    "action": "run_local_terminal",
    "parameters": {"server_id": "local-tools", "arguments": {"command": "x"}},
}

BENIGN_DICT_STEP = {
    "id": "s1",
    "service": "email",
    "action": "send",
    "parameters": {"to": "x@y.z"},
}

TERMINAL_WORKFLOW = {
    "id": "wf-1",
    "workflow_id": "wf-1",
    "name": "Local shell",
    "steps": [
        {
            "id": "s1",
            "service": "mcp",
            "action": "run_local_terminal",
            "parameters": {"server_id": "local-tools", "arguments": {"command": "${input.command}"}},
            "sequence_order": 0,
        }
    ],
}

BENIGN_WORKFLOW = {
    "id": "wf-2",
    "workflow_id": "wf-2",
    "name": "Notify",
    "steps": [
        {
            "id": "s1",
            "service": "email",
            "action": "send",
            "parameters": {"to": "x@y.z"},
            "sequence_order": 0,
        }
    ],
}


def user(role="member"):
    return MagicMock(id="u-68", email="u@example.com", role=role)


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
        started_at=datetime(2026, 1, 1, 12, 0, 0),
        completed_at=datetime(2026, 1, 1, 12, 0, 5),
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


# ---------------------------------------------------------------------------
# core.workflow_security unit tests
# ---------------------------------------------------------------------------


class TestWorkflowSecurityUnit:
    def test_r67_dict_regression_critical_mcp(self):
        assert has_critical_step([CRITICAL_DICT_STEP]) is True

    def test_r67_dict_regression_benign_email_service(self):
        assert has_critical_step([BENIGN_DICT_STEP]) is False

    def test_workflowstep_terminal_and_email_send_critical(self):
        assert has_critical_step([step(WorkflowStepType.TERMINAL)]) is True
        assert has_critical_step([step(WorkflowStepType.EMAIL_SEND)]) is True

    def test_workflowstep_slack_benign(self):
        assert has_critical_step([step(WorkflowStepType.SLACK_NOTIFICATION)]) is False

    def test_templatestep_terminal_critical(self):
        ts = TemplateStep(id="s1", name="Terminal", step_type="terminal", parameters={})
        assert has_critical_step([ts]) is True

    def test_templatestep_nlu_analysis_benign(self):
        ts = TemplateStep(id="s1", name="NLU", step_type="nlu_analysis", parameters={})
        assert has_critical_step([ts]) is False

    def test_templated_tool_name_critical(self):
        steps = [{"service": "mcp", "action": "safe", "parameters": {"tool_name": "${input.tool}"}}]
        assert has_critical_step(steps) is True

    def test_missing_tool_name_critical(self):
        steps = [{"service": "mcp", "action": None, "parameters": {}}]
        assert has_critical_step(steps) is True

    def test_universal_integration_email_critical(self):
        steps = [{"step_type": "universal_integration", "parameters": {"service": "email", "action": "send"}}]
        assert has_critical_step(steps) is True

    def test_universal_integration_slack_benign(self):
        steps = [{"step_type": "universal_integration", "parameters": {"service": "slack", "action": "post"}}]
        assert has_critical_step(steps) is False

    def test_has_critical_definition_list_dict_object(self):
        assert has_critical_definition([CRITICAL_DICT_STEP]) is True
        assert has_critical_definition({"steps": [CRITICAL_DICT_STEP]}) is True
        assert has_critical_definition(definition("wf-1", [step(WorkflowStepType.TERMINAL)])) is True
        assert has_critical_definition({"steps": [BENIGN_DICT_STEP]}) is False

    def test_require_workflow_executor_member_403(self):
        with pytest.raises(HTTPException) as ei:
            _run(require_workflow_executor(user("member"), [CRITICAL_DICT_STEP]))
        assert ei.value.status_code == 403

    def test_require_workflow_executor_team_lead_pass(self):
        _run(require_workflow_executor(user("team_lead"), [CRITICAL_DICT_STEP]))

    def test_resolve_orchestrator_steps_workflow_then_template(self):
        orch = make_orchestrator(
            workflows={"wf-1": definition("wf-1", [step(WorkflowStepType.TERMINAL)])},
            templates={"tpl-1": MagicMock(steps=[BENIGN_DICT_STEP])},
        )
        assert len(resolve_orchestrator_steps(orch, "wf-1")) == 1
        assert len(resolve_orchestrator_steps(orch, "tpl-1")) == 1
        assert resolve_orchestrator_steps(orch, "unknown") is None

    def test_require_orchestrator_unknown_definition_fails_closed(self):
        orch = make_orchestrator(workflows={})
        with pytest.raises(HTTPException) as ei:
            _run(require_workflow_executor_orchestrator(user("team_lead"), orch, "unknown"))
        assert ei.value.status_code == 403

    def test_require_critical_tool_member(self):
        with pytest.raises(HTTPException):
            _run(require_critical_tool(user("member"), "terminal_command"))
        with pytest.raises(HTTPException):
            _run(require_critical_tool(user("member"), "${input.tool}"))
        # benign tool passes for members
        _run(require_critical_tool(user("member"), "present_markdown"))

    def test_require_critical_tool_team_lead_exempt(self):
        _run(require_critical_tool(user("team_lead"), "terminal_command"))


# ---------------------------------------------------------------------------
# Tier 1 — advanced_workflow_api
# ---------------------------------------------------------------------------


class TestAdvancedWorkflowApi:
    def test_execute_anon_401(self):
        from advanced_workflow_api import router

        client = make_client(router)
        resp = client.post("/api/v1/workflows/execute", json={"workflow_id": "wf-1", "input_data": {}})
        assert resp.status_code == 401

    def test_execute_member_critical_403(self):
        from advanced_workflow_api import router

        orch = make_orchestrator({"wf-1": definition("wf-1", [step(WorkflowStepType.TERMINAL)])})
        orch.execute_workflow = AsyncMock(return_value=_ctx("wf-1"))
        client = make_client(router, role="member")
        with patch("advanced_workflow_api.get_orchestrator", return_value=orch):
            resp = client.post("/api/v1/workflows/execute", json={"workflow_id": "wf-1", "input_data": {}})
        assert resp.status_code == 403
        orch.execute_workflow.assert_not_called()

    def test_execute_team_lead_critical_200(self):
        from advanced_workflow_api import router

        orch = make_orchestrator({"wf-1": definition("wf-1", [step(WorkflowStepType.TERMINAL)])})
        orch.execute_workflow = AsyncMock(return_value=_ctx("wf-1"))
        client = make_client(router, role="team_lead")
        with patch("advanced_workflow_api.get_orchestrator", return_value=orch):
            resp = client.post("/api/v1/workflows/execute", json={"workflow_id": "wf-1", "input_data": {}})
        assert resp.status_code == 200
        orch.execute_workflow.assert_called_once()

    def test_execute_member_benign_200(self):
        from advanced_workflow_api import router

        orch = make_orchestrator({"wf-2": definition("wf-2", [step(WorkflowStepType.SLACK_NOTIFICATION)])})
        orch.execute_workflow = AsyncMock(return_value=_ctx("wf-2"))
        client = make_client(router, role="member")
        with patch("advanced_workflow_api.get_orchestrator", return_value=orch):
            resp = client.post("/api/v1/workflows/execute", json={"workflow_id": "wf-2", "input_data": {}})
        assert resp.status_code == 200

    def test_execute_member_unknown_id_403(self):
        from advanced_workflow_api import router

        orch = make_orchestrator(workflows={})
        client = make_client(router, role="member")
        with patch("advanced_workflow_api.get_orchestrator", return_value=orch):
            resp = client.post("/api/v1/workflows/execute", json={"workflow_id": "nope", "input_data": {}})
        assert resp.status_code == 403

    @pytest.mark.parametrize(
        "path,wid",
        [
            ("/api/v1/workflows/demo-customer-support", "customer_support_automation"),
            ("/api/v1/workflows/demo-project-management", "project_management_automation"),
            ("/api/v1/workflows/demo-sales-lead", "sales_lead_processing"),
        ],
    )
    def test_demo_anon_401(self, path, wid):
        from advanced_workflow_api import router

        client = make_client(router)
        resp = client.post(path)
        assert resp.status_code == 401

    @pytest.mark.parametrize(
        "path,wid",
        [
            ("/api/v1/workflows/demo-customer-support", "customer_support_automation"),
            ("/api/v1/workflows/demo-project-management", "project_management_automation"),
            ("/api/v1/workflows/demo-sales-lead", "sales_lead_processing"),
        ],
    )
    def test_demo_member_403_team_lead_200(self, path, wid):
        from advanced_workflow_api import router

        orch = make_orchestrator(
            {wid: definition(wid, [step(WorkflowStepType.EMAIL_SEND)])}
        )
        orch.execute_workflow = AsyncMock(return_value=_ctx(wid))
        with patch("advanced_workflow_api.get_orchestrator", return_value=orch):
            member_resp = make_client(router, role="member").post(path)
            tl_resp = make_client(router, role="team_lead").post(path)
        assert member_resp.status_code == 403
        assert tl_resp.status_code == 200


# ---------------------------------------------------------------------------
# Tier 1 — core.workflow_ui_endpoints
# ---------------------------------------------------------------------------


class TestWorkflowUiEndpoints:
    def test_execute_anon_401(self):
        from core.workflow_ui_endpoints import router

        client = make_client(router)
        resp = client.post("/execute", json={"workflow_id": "x", "input": {}})
        assert resp.status_code == 401

    def test_execute_bridge_to_email_member_403(self):
        from core.workflow_ui_endpoints import WorkflowStep as UIWorkflowStep
        from core.workflow_ui_endpoints import WorkflowTemplateResponse
        from core.workflow_ui_endpoints import router

        template = WorkflowTemplateResponse(
            id="tpl_bridge_email",
            name="Email bridge",
            description="",
            category="",
            icon="",
            steps=[
                UIWorkflowStep(id="s1", type="email", service="email", action="send", parameters={}, name="Send")
            ],
            input_schema={},
        )
        orch = make_orchestrator(workflows={})
        orch.execute_workflow = AsyncMock(return_value=_ctx())
        client = make_client(router, role="member")
        with patch("core.workflow_ui_endpoints.MOCK_TEMPLATES", [template]), patch(
            "advanced_workflow_orchestrator.get_orchestrator", return_value=orch
        ):
            resp = client.post("/execute", json={"workflow_id": "tpl_bridge_email", "input": {}})
        assert resp.status_code == 403, "gate must see the effective (bridged) EMAIL_SEND step"

    def test_execute_bridge_to_slack_member_200(self):
        from core.workflow_ui_endpoints import WorkflowStep as UIWorkflowStep
        from core.workflow_ui_endpoints import WorkflowTemplateResponse
        from core.workflow_ui_endpoints import router

        template = WorkflowTemplateResponse(
            id="tpl_bridge_slack",
            name="Slack bridge",
            description="",
            category="",
            icon="",
            steps=[
                UIWorkflowStep(id="s1", type="slack", service="slack", action="post", parameters={}, name="Notify")
            ],
            input_schema={},
        )
        orch = make_orchestrator(workflows={})
        orch.execute_workflow = AsyncMock(return_value=_ctx())
        client = make_client(router, role="member")
        with patch("core.workflow_ui_endpoints.MOCK_TEMPLATES", [template]), patch(
            "advanced_workflow_orchestrator.get_orchestrator", return_value=orch
        ):
            resp = client.post("/execute", json={"workflow_id": "tpl_bridge_slack", "input": {}})
        assert resp.status_code == 200

    def test_execute_bridge_to_email_team_lead_200(self):
        from core.workflow_ui_endpoints import WorkflowStep as UIWorkflowStep
        from core.workflow_ui_endpoints import WorkflowTemplateResponse
        from core.workflow_ui_endpoints import router

        template = WorkflowTemplateResponse(
            id="tpl_bridge_email",
            name="Email bridge",
            description="",
            category="",
            icon="",
            steps=[
                UIWorkflowStep(id="s1", type="email", service="email", action="send", parameters={}, name="Send")
            ],
            input_schema={},
        )
        orch = make_orchestrator(workflows={})
        orch.execute_workflow = AsyncMock(return_value=_ctx())
        client = make_client(router, role="team_lead")
        with patch("core.workflow_ui_endpoints.MOCK_TEMPLATES", [template]), patch(
            "advanced_workflow_orchestrator.get_orchestrator", return_value=orch
        ):
            resp = client.post("/execute", json={"workflow_id": "tpl_bridge_email", "input": {}})
        assert resp.status_code == 200

    def test_workflow_by_id_member_terminal_403(self):
        from core.workflow_ui_endpoints import router

        orch = make_orchestrator(
            {"wf_term": definition("wf_term", [step(WorkflowStepType.TERMINAL)])}
        )
        orch.execute_workflow = AsyncMock(return_value=_ctx("wf_term"))
        client = make_client(router, role="member")
        with patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orch):
            resp = client.post("/workflows/wf_term/execute", json={"input": {}})
        assert resp.status_code == 403

    def test_workflow_by_id_team_lead_200(self):
        from core.workflow_ui_endpoints import router

        orch = make_orchestrator(
            {"wf_term": definition("wf_term", [step(WorkflowStepType.TERMINAL)])}
        )
        orch.execute_workflow = AsyncMock(return_value=_ctx("wf_term"))
        client = make_client(router, role="team_lead")
        with patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orch):
            resp = client.post("/workflows/wf_term/execute", json={"input": {}})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tier 2 — api.intelligence_routes
# ---------------------------------------------------------------------------


class TestIntelligenceExecute:
    def test_tool_member_critical_403(self):
        from api.intelligence_routes import router

        client = make_client(router, role="member")
        with patch("integrations.mcp_service.mcp_service.execute_tool", new_callable=AsyncMock) as mt:
            resp = client.post(
                "/api/intelligence/execute",
                json={"action_type": "tool", "action_payload": {"tool_name": "terminal_command", "arguments": {}}},
            )
        assert resp.status_code == 403
        mt.assert_not_called()

    def test_tool_team_lead_200(self):
        from api.intelligence_routes import router

        client = make_client(router, role="team_lead")
        with patch("integrations.mcp_service.mcp_service.execute_tool", new_callable=AsyncMock) as mt:
            mt.return_value = {"status": "ok"}
            resp = client.post(
                "/api/intelligence/execute",
                json={"action_type": "tool", "action_payload": {"tool_name": "terminal_command", "arguments": {}}},
            )
        assert resp.status_code == 200
        mt.assert_called_once()

    def test_tool_member_benign_200(self):
        from api.intelligence_routes import router

        client = make_client(router, role="member")
        with patch("integrations.mcp_service.mcp_service.execute_tool", new_callable=AsyncMock) as mt:
            mt.return_value = {"status": "ok"}
            resp = client.post(
                "/api/intelligence/execute",
                json={"action_type": "tool", "action_payload": {"tool_name": "present_markdown", "arguments": {}}},
            )
        assert resp.status_code == 200

    def test_tool_body_user_id_ignored(self):
        from api.intelligence_routes import router

        client = make_client(router, role="member")
        with patch("integrations.mcp_service.mcp_service.execute_tool", new_callable=AsyncMock) as mt:
            mt.return_value = {"status": "ok"}
            resp = client.post(
                "/api/intelligence/execute",
                json={
                    "action_type": "tool",
                    "user_id": "evil",
                    "action_payload": {"tool_name": "present_markdown", "arguments": {}},
                },
            )
        assert resp.status_code == 200
        # context uses current_user.id, not the spoofed body user_id
        context_arg = mt.call_args[0][3]
        assert context_arg["user_id"] == "u-68"

    def test_workflow_member_critical_403(self):
        from api.intelligence_routes import router

        orch = make_orchestrator(
            {"wf-1": definition("wf-1", [step(WorkflowStepType.EMAIL_SEND)])}
        )
        orch.execute_workflow = AsyncMock(return_value=_ctx())
        client = make_client(router, role="member")
        with patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/intelligence/execute",
                json={"action_type": "workflow", "action_payload": {"workflow_id": "wf-1", "inputs": {}}},
            )
        assert resp.status_code == 403
        orch.execute_workflow.assert_not_called()

    def test_workflow_team_lead_200(self):
        from api.intelligence_routes import router

        orch = make_orchestrator(
            {"wf-1": definition("wf-1", [step(WorkflowStepType.EMAIL_SEND)])}
        )
        orch.execute_workflow = AsyncMock(return_value=_ctx())
        client = make_client(router, role="team_lead")
        with patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/intelligence/execute",
                json={"action_type": "workflow", "action_payload": {"workflow_id": "wf-1", "inputs": {}}},
            )
        assert resp.status_code == 200
        orch.execute_workflow.assert_called_once()


# ---------------------------------------------------------------------------
# Tier 2 — core.atom_agent_endpoints
# ---------------------------------------------------------------------------


class FakeEngine:
    async def execute_workflow_definition(self, workflow, input_data, execution_id=None):
        return {"status": "completed"}


class TestAtomAgentEndpoints:
    def test_execute_generated_member_terminal_403_not_500(self):
        from core.atom_agent_endpoints import router

        client = make_client(router, role="member")
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[TERMINAL_WORKFLOW]):
            resp = client.post(
                "/api/atom-agent/execute-generated",
                json={"workflow_id": "wf-1", "input_data": {}},
            )
        assert resp.status_code == 403

    def test_execute_generated_team_lead_200(self):
        from core.atom_agent_endpoints import router

        client = make_client(router, role="team_lead")
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[TERMINAL_WORKFLOW]), patch(
            "core.atom_agent_endpoints.AutomationEngine", FakeEngine
        ):
            resp = client.post(
                "/api/atom-agent/execute-generated",
                json={"workflow_id": "wf-1", "input_data": {}},
            )
        assert resp.status_code == 200

    def test_execute_generated_member_benign_200(self):
        from core.atom_agent_endpoints import router

        client = make_client(router, role="member")
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[BENIGN_WORKFLOW]):
            resp = client.post(
                "/api/atom-agent/execute-generated",
                json={"workflow_id": "wf-2", "input_data": {}},
            )
        assert resp.status_code == 200

    async def test_handle_run_workflow_member_refusal(self):
        from core.atom_agent_endpoints import ChatRequest
        from core.atom_agent_endpoints import handle_run_workflow

        req = MagicMock(spec=ChatRequest)
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[TERMINAL_WORKFLOW]):
            result = await handle_run_workflow(req, {"workflow_ref": "Local shell"}, user("member"))
        assert result["success"] is False
        assert "WORKFLOW_MANAGE" in result["response"]["message"]

    async def test_handle_run_workflow_team_lead_success(self):
        from core.atom_agent_endpoints import ChatRequest
        from core.atom_agent_endpoints import handle_run_workflow

        req = MagicMock(spec=ChatRequest)
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[TERMINAL_WORKFLOW]), patch(
            "core.atom_agent_endpoints.AutomationEngine", FakeEngine
        ):
            result = await handle_run_workflow(req, {"workflow_ref": "Local shell"}, user("team_lead"))
        assert result["success"] is True

    async def test_handle_schedule_workflow_member_refusal_no_scheduler(self):
        from core.atom_agent_endpoints import ChatRequest
        from core.atom_agent_endpoints import handle_schedule_workflow

        req = MagicMock(spec=ChatRequest)
        scheduler = MagicMock()
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[TERMINAL_WORKFLOW]), patch(
            "core.atom_agent_endpoints.workflow_scheduler", scheduler
        ), patch(
            "core.time_expression_parser.parse_time_expression",
            AsyncMock(return_value={"schedule_type": "cron", "cron_expression": "* * * * *", "human_readable": "daily at 9am"}),
        ):
            result = await handle_schedule_workflow(
                req, {"workflow_ref": "Local shell", "time_expression": "daily at 9am"}, user("member")
            )
        assert result["success"] is False
        scheduler.schedule_workflow_cron.assert_not_called()

    async def test_handle_schedule_workflow_team_lead_success(self):
        from core.atom_agent_endpoints import ChatRequest
        from core.atom_agent_endpoints import handle_schedule_workflow

        req = MagicMock(spec=ChatRequest)
        scheduler = MagicMock()
        with patch("core.atom_agent_endpoints.load_workflows", return_value=[TERMINAL_WORKFLOW]), patch(
            "core.atom_agent_endpoints.workflow_scheduler", scheduler
        ), patch(
            "core.time_expression_parser.parse_time_expression",
            AsyncMock(return_value={"schedule_type": "cron", "cron_expression": "* * * * *", "human_readable": "daily at 9am"}),
        ):
            result = await handle_schedule_workflow(
                req, {"workflow_ref": "Local shell", "time_expression": "daily at 9am"}, user("team_lead")
            )
        assert result["success"] is True
        scheduler.schedule_workflow_cron.assert_called_once()


# ---------------------------------------------------------------------------
# Tier 2 — api.workflow_template_routes
# ---------------------------------------------------------------------------


class TestWorkflowTemplateRoutes:
    def _patch_manager(self, workflow_definition):
        manager = MagicMock()
        manager.create_workflow_from_template = MagicMock(
            return_value={
                "workflow_id": "workflow_abc",
                "workflow_definition": workflow_definition,
            }
        )
        return manager

    def test_execute_member_email_template_403(self):
        from api.workflow_template_routes import router

        email_def = {"steps": [{"step_id": "s1", "step_type": "email_send", "parameters": {}}]}
        orch = make_orchestrator(workflows={})
        orch.execute_workflow = AsyncMock(return_value=_ctx())
        client = make_client(router, role="member")
        with patch("api.workflow_template_routes.get_template_manager", return_value=self._patch_manager(email_def)), patch(
            "advanced_workflow_orchestrator.get_orchestrator", return_value=orch
        ):
            resp = client.post("/api/workflow-templates/tpl_email/execute", json={})
        assert resp.status_code == 403
        orch.execute_workflow.assert_not_called()

    def test_execute_team_lead_email_template_200(self):
        from api.workflow_template_routes import router

        email_def = {"steps": [{"step_id": "s1", "step_type": "email_send", "parameters": {}}]}
        orch = make_orchestrator(workflows={})
        orch.execute_workflow = AsyncMock(return_value=_ctx())
        client = make_client(router, role="team_lead")
        with patch("api.workflow_template_routes.get_template_manager", return_value=self._patch_manager(email_def)), patch(
            "advanced_workflow_orchestrator.get_orchestrator", return_value=orch
        ):
            resp = client.post("/api/workflow-templates/tpl_email/execute", json={})
        assert resp.status_code == 200
        orch.execute_workflow.assert_called_once()

    def test_execute_member_benign_200(self):
        from api.workflow_template_routes import router

        benign_def = {"steps": [{"step_id": "s1", "step_type": "slack_notification", "parameters": {}}]}
        orch = make_orchestrator(workflows={})
        orch.execute_workflow = AsyncMock(return_value=_ctx())
        client = make_client(router, role="member")
        with patch("api.workflow_template_routes.get_template_manager", return_value=self._patch_manager(benign_def)), patch(
            "advanced_workflow_orchestrator.get_orchestrator", return_value=orch
        ):
            resp = client.post("/api/workflow-templates/tpl_benign/execute", json={})
        assert resp.status_code == 200

    def test_execute_mock_without_workflow_definition_stays_green(self):
        from api.workflow_template_routes import router

        manager = MagicMock()
        manager.create_workflow_from_template = MagicMock(return_value={"workflow_id": "workflow_abc"})
        orch = make_orchestrator(workflows={})
        orch.execute_workflow = AsyncMock(return_value=_ctx())
        client = make_client(router, role="member")
        with patch("api.workflow_template_routes.get_template_manager", return_value=manager), patch(
            "advanced_workflow_orchestrator.get_orchestrator", return_value=orch
        ):
            resp = client.post("/api/workflow-templates/tpl_no_def/execute", json={})
        assert resp.status_code == 200
        orch.execute_workflow.assert_called_once()


# ---------------------------------------------------------------------------
# Tier 2 — api.mobile_workflows (latent, not mounted — mount directly)
# ---------------------------------------------------------------------------


class TestMobileWorkflows:
    def _wf_dict(self, steps):
        return {"id": "mob-1", "name": "Mob", "status": "active", "steps": steps}

    def test_trigger_member_terminal_403(self):
        from api.mobile_workflows import router

        orch = make_orchestrator(workflows={})
        db = MagicMock()
        engine = MagicMock()
        client = make_client(router, role="member")
        client.app.dependency_overrides[get_db] = lambda: db
        with patch(
            "api.mobile_workflows._load_workflow_definition",
            return_value=self._wf_dict(TERMINAL_WORKFLOW["steps"]),
        ), patch("core.workflow_engine.get_workflow_engine", return_value=engine):
            resp = client.post(
                "/api/mobile/workflows/trigger?user_id=evil",
                json={"workflow_id": "mob-1", "synchronous": False},
            )
        assert resp.status_code == 403
        db.add.assert_not_called()
        engine._run_execution.assert_not_called()

    def test_trigger_team_lead_200_uses_current_user(self):
        from api.mobile_workflows import router

        db = MagicMock()
        engine = MagicMock()
        client = make_client(router, role="team_lead")
        client.app.dependency_overrides[get_db] = lambda: db
        with patch(
            "api.mobile_workflows._load_workflow_definition",
            return_value=self._wf_dict(TERMINAL_WORKFLOW["steps"]),
        ), patch("core.workflow_engine.get_workflow_engine", return_value=engine):
            resp = client.post(
                "/api/mobile/workflows/trigger?user_id=evil",
                json={"workflow_id": "mob-1", "synchronous": False},
            )
        assert resp.status_code == 200
        # spoofed Query user_id must be ignored in favor of current_user.id
        added = db.add.call_args[0][0]
        assert added.user_id == "u-68"

    def test_trigger_member_benign_200(self):
        from api.mobile_workflows import router

        db = MagicMock()
        engine = MagicMock()
        client = make_client(router, role="member")
        client.app.dependency_overrides[get_db] = lambda: db
        with patch(
            "api.mobile_workflows._load_workflow_definition",
            return_value=self._wf_dict(BENIGN_WORKFLOW["steps"]),
        ), patch("core.workflow_engine.get_workflow_engine", return_value=engine):
            resp = client.post(
                "/api/mobile/workflows/trigger?user_id=evil",
                json={"workflow_id": "mob-1", "synchronous": False},
            )
        assert resp.status_code == 200
        engine._run_execution.assert_called_once()


# ---------------------------------------------------------------------------
# Tier 3 — analytics + automation settings
# ---------------------------------------------------------------------------


class TestAnalyticsWorkflowTriggers:
    def _wellness(self):
        return WellnessScore(
            risk_level="Low",
            score=20,
            factors={},
            recommendations=[],
            timestamp=datetime(2026, 1, 1, 12, 0, 0),
        )

    def test_burnout_risk_anon_401(self):
        from core.analytics_endpoints import router

        client = make_client(router)
        assert client.get("/api/v1/analytics/burnout-risk").status_code == 401

    def test_burnout_risk_authenticated_200(self):
        from core.analytics_endpoints import router

        client = make_client(router, role="member")
        with patch(
            "core.analytics_endpoints.burnout_engine.calculate_burnout_risk",
            AsyncMock(return_value=self._wellness()),
        ):
            resp = client.get("/api/v1/analytics/burnout-risk")
        assert resp.status_code == 200

    def test_deadline_risk_anon_401(self):
        from core.analytics_endpoints import router

        client = make_client(router)
        assert client.get("/api/v1/analytics/deadline-risk").status_code == 401

    def test_deadline_risk_authenticated_200(self):
        from core.analytics_endpoints import router

        client = make_client(router, role="member")
        with patch(
            "core.analytics_endpoints.burnout_engine.calculate_deadline_risk",
            AsyncMock(return_value=self._wellness()),
        ):
            resp = client.get("/api/v1/analytics/deadline-risk")
        assert resp.status_code == 200


class TestAutomationSettings:
    def test_get_anon_401(self):
        from core.automation_settings_endpoints import router

        client = make_client(router)
        assert client.get("/api/v1/settings/automations/").status_code == 401

    def test_post_anon_401(self):
        from core.automation_settings_endpoints import router

        client = make_client(router)
        assert client.post("/api/v1/settings/automations/", json={}).status_code == 401

    def test_get_authenticated_200(self):
        from core.automation_settings_endpoints import router

        client = make_client(router, role="member")
        with patch(
            "core.automation_settings_endpoints.get_automation_settings",
            return_value=MagicMock(get_settings=MagicMock(return_value={})),
        ):
            resp = client.get("/api/v1/settings/automations/")
        assert resp.status_code == 200

    def test_post_authenticated_200(self):
        from core.automation_settings_endpoints import router

        client = make_client(router, role="member")
        with patch(
            "core.automation_settings_endpoints.get_automation_settings",
            return_value=MagicMock(update_settings=MagicMock(return_value={})),
        ):
            resp = client.post("/api/v1/settings/automations/", json={"auto_approve": True})
        assert resp.status_code == 200
