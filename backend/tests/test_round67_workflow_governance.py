"""
Round 67 — Workflow-executed MCP actions bypass governance (agent-action auth)
(Red-Green-Refactor).

The meta-agent path runs every tool call through AgentGovernanceService
(maturity + complexity + HITL) — but the workflow engine's _execute_mcp_action
calls mcp_service.execute_tool with NO context: the governance gate
(`if agent_id:`) is skipped entirely. Any user with WORKFLOW_RUN (members
have it) can execute a workflow with an mcp step (run_local_terminal /
terminal_command / write_code_file / browser_navigate...) and inject tool
arguments via ${input.*} templating — local-machine command execution with
zero governance (the same action via an agent requires AUTONOMOUS maturity).

Fix:
  A. execute_workflow / execute_with_conductor / resume_workflow /
     schedule_workflow gate workflows with critical mcp tools to
     WORKFLOW_MANAGE (TEAM_LEAD+, the same role required to CREATE a
     workflow) — members get 403 before any execution/scheduling starts.
  B. _execute_mcp_action stops leaking str(e) in the failure dict.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db
from core.models import UserRole

SECRET = "secret-workflow-xyz"

TERMINAL_WORKFLOW = {
    "id": "wf-1",
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

TEMPLATED_TOOL_WORKFLOW = {
    "id": "wf-3",
    "name": "Dynamic tool",
    "steps": [
        {
            "id": "s1",
            "service": "mcp",
            "action": "local_tools",
            "parameters": {"server_id": "local-tools", "tool_name": "${input.tool}", "arguments": {}},
            "sequence_order": 0,
        }
    ],
}

BENIGN_MCP_WORKFLOW = {
    "id": "wf-4",
    "name": "Canvas note",
    "steps": [
        {
            "id": "s1",
            "service": "mcp",
            "action": "present_markdown",
            "parameters": {"server_id": "local-tools", "arguments": {"content": "hi"}},
            "sequence_order": 0,
        }
    ],
}

BENIGN_WORKFLOW = {
    "id": "wf-2",
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


def make_client(role="member"):
    from core.workflow_endpoints import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[auth_get_current_user] = lambda: MagicMock(
        id="u-67", email="u@example.com", role=role
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=False)


class TestWorkflowMCPGovernance:
    def test_member_cannot_execute_workflow_with_terminal_step(self):
        with patch(
            "core.workflow_endpoints.load_workflows",
            return_value=[TERMINAL_WORKFLOW],
        ), patch(
            "core.workflow_engine.get_workflow_engine"
        ) as engine:
            resp = make_client(role="member").post(
                "/workflows/wf-1/execute", json={"input_data": {"command": "rm -rf ~"}}
            )

        assert resp.status_code == 403, (
            f"member executed a workflow with a critical mcp tool — "
            f"governance bypass (got {resp.status_code})"
        )
        engine.return_value.start_workflow.assert_not_called()

    def test_team_lead_can_execute_same_workflow(self):
        with patch(
            "core.workflow_endpoints.load_workflows",
            return_value=[TERMINAL_WORKFLOW],
        ), patch(
            "core.workflow_engine.get_workflow_engine"
        ) as engine:
            engine.return_value.start_workflow = AsyncMock(return_value="ex-1")
            resp = make_client(role=UserRole.TEAM_LEAD.value).post(
                "/workflows/wf-1/execute", json={"input_data": {"command": "ls"}}
            )

        assert resp.status_code == 200, resp.text
        engine.return_value.start_workflow.assert_called_once()

    def test_member_cannot_execute_workflow_with_templated_tool_name(self):
        """Tool names can be injected via ${input.*} templating — cannot be
        proven benign statically, so supervisor-only."""
        with patch(
            "core.workflow_endpoints.load_workflows",
            return_value=[TEMPLATED_TOOL_WORKFLOW],
        ), patch(
            "core.workflow_engine.get_workflow_engine"
        ) as engine:
            resp = make_client(role="member").post(
                "/workflows/wf-3/execute", json={"input_data": {"tool": "run_local_terminal"}}
            )

        assert resp.status_code == 403, (
            f"member executed a workflow with a templated mcp tool name — "
            f"tool injection (got {resp.status_code})"
        )
        engine.return_value.start_workflow.assert_not_called()

    def test_member_can_execute_benign_mcp_workflow(self):
        """Regression guard: the gate is tool-specific, not service-wide."""
        with patch(
            "core.workflow_endpoints.load_workflows",
            return_value=[BENIGN_MCP_WORKFLOW],
        ), patch(
            "core.workflow_engine.get_workflow_engine"
        ) as engine:
            engine.return_value.start_workflow = AsyncMock(return_value="ex-4")
            resp = make_client(role="member").post(
                "/workflows/wf-4/execute", json={}
            )

        assert resp.status_code == 200, resp.text
        engine.return_value.start_workflow.assert_called_once()

    def test_member_can_execute_benign_workflow(self):
        """Regression guard: members may still run workflows without critical
        mcp tools."""
        with patch(
            "core.workflow_endpoints.load_workflows",
            return_value=[BENIGN_WORKFLOW],
        ), patch(
            "core.workflow_engine.get_workflow_engine"
        ) as engine:
            engine.return_value.start_workflow = AsyncMock(return_value="ex-2")
            resp = make_client(role="member").post(
                "/workflows/wf-2/execute", json={}
            )

        assert resp.status_code == 200, resp.text
        engine.return_value.start_workflow.assert_called_once()

    def test_member_cannot_run_critical_steps_via_conductor(self):
        """The conductor route executes raw caller-supplied steps through the
        live engine — a direct bypass without even a workflow file."""
        critical_step = {
            "step_id": "s1",
            "step_type": "integration",
            "parameters": {"server_id": "local-tools", "tool_name": "terminal_command"},
        }
        with patch(
            "core.orchestration.conductor_agent.get_conductor_agent"
        ) as conductor:
            conductor.return_value.execute_workflow = AsyncMock()
            resp = make_client(role="member").post(
                "/workflows/conductor/execute", json={"steps": [critical_step]}
            )

        assert resp.status_code == 403, (
            f"member executed critical mcp steps via the conductor route "
            f"(got {resp.status_code})"
        )
        conductor.return_value.execute_workflow.assert_not_called()

    def test_team_lead_can_run_critical_steps_via_conductor(self):
        critical_step = {
            "step_id": "s1",
            "step_type": "integration",
            "parameters": {"server_id": "local-tools", "tool_name": "terminal_command"},
        }
        with patch(
            "core.orchestration.conductor_agent.get_conductor_agent"
        ) as conductor:
            conductor.return_value.execute_workflow = AsyncMock(return_value=MagicMock(
                execution_id="ex-9",
                status="completed",
                completed_steps=1,
                failed_steps=0,
                step_results=[],
            ))
            resp = make_client(role=UserRole.TEAM_LEAD.value).post(
                "/workflows/conductor/execute", json={"steps": [critical_step]}
            )

        assert resp.status_code == 200, resp.text
        conductor.return_value.execute_workflow.assert_called_once()

    def test_member_cannot_schedule_critical_workflow(self):
        """Scheduling defers execution with no per-run auth — the gate must
        fire at schedule time."""
        with patch(
            "core.workflow_endpoints.load_workflows",
            return_value=[TERMINAL_WORKFLOW],
        ), patch(
            "ai.workflow_scheduler.workflow_scheduler"
        ) as scheduler:
            resp = make_client(role="member").post(
                "/workflows/wf-1/schedule",
                json={
                    "trigger_type": "interval",
                    "trigger_config": {"minutes": 5},
                    "input_data": {"command": "rm -rf ~"},
                },
            )

        assert resp.status_code == 403, (
            f"member scheduled a workflow with a critical mcp tool "
            f"(got {resp.status_code})"
        )
        scheduler.schedule_workflow.assert_not_called()

    def test_member_cannot_resume_critical_workflow(self):
        state = {"workflow_id": "wf-1"}
        with patch(
            "core.workflow_endpoints.load_workflows",
            return_value=[TERMINAL_WORKFLOW],
        ), patch(
            "core.execution_state_manager.get_state_manager"
        ) as sm, patch(
            "core.workflow_engine.get_workflow_engine"
        ) as engine:
            sm.return_value.get_execution_state = AsyncMock(return_value=state)
            resp = make_client(role="member").post(
                "/workflows/ex-1/resume", json={"input_data": {"command": "rm -rf ~"}}
            )

        assert resp.status_code == 403, (
            f"member resumed a workflow with a critical mcp tool "
            f"(got {resp.status_code})"
        )
        engine.return_value.resume_workflow.assert_not_called()

    def test_mcp_action_passes_attribution_and_does_not_leak(self):
        """Engine-level: _execute_mcp_action must not leak exception strings
        (str(e) sweep class, R41/R52/R63 pattern)."""
        import asyncio

        from core.workflow_engine import get_workflow_engine

        engine = get_workflow_engine()

        with patch(
            "integrations.mcp_service.mcp_service.execute_tool",
            new=AsyncMock(side_effect=RuntimeError(SECRET)),
        ):
            result = asyncio.run(
                engine._execute_mcp_action(
                    "mcp",
                    {
                        "server_id": "local-tools",
                        "tool_name": "run_local_terminal",
                        "arguments": {"command": "ls"},
                    },
                )
            )

        assert SECRET not in str(result), (
            f"_execute_mcp_action leaks internal detail: {result!r}"
        )
        assert result["status"] == "error"
