"""
TDD regression tests for the workflow schema mismatch.

Three stores/representations coexist:
1. Durable node-based definitions  (core/workflow_endpoints.py → workflows.json)
2. Step-based UI model             (core/workflow_ui_endpoints.py → DB templates)
3. Step-based frontend UI model    (WorkflowAutomation.tsx)

Bugs covered:
- R1: GET /workflows omits `steps`/`steps_count` for node-based definitions,
  so the step-based frontend renders "0 steps" and can't edit them.
- R2: execute/resume/schedule gate on `workflow.get("steps") or []` — empty
  for node-based definitions, so critical MCP actions (terminal/browser/
  messaging) bypass the WORKFLOW_MANAGE gate for members.
- R3: "Use Template → Execute" posts to /workflows/{template_id}/execute,
  which only reads workflows.json — DB templates 404.
"""

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.auth
from core import workflow_endpoints


def _build_node_workflow(critical: bool = False) -> dict:
    """A durable, node-based WorkflowDefinition with a single node."""
    config = (
        {"service": "mcp", "action": "terminal_command", "parameters": {}}
        if critical
        else {"service": "email", "action": "send", "parameters": {"to": "a@b.c"}}
    )
    return {
        "id": "wf_node_1",
        "name": "Node Workflow",
        "description": "graph-based",
        "version": "1.0",
        "nodes": [
            {
                "id": "n1",
                "type": "action",
                "title": "My Action",
                "description": "desc",
                "position": {"x": 0, "y": 0},
                "config": config,
                "connections": [],
            }
        ],
        "connections": [],
        "triggers": [],
        "enabled": True,
    }


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(workflow_endpoints.router, prefix="/api/v1/workflows")

    # Authenticated MEMBER: has WORKFLOW_VIEW + WORKFLOW_RUN, but NOT
    # WORKFLOW_MANAGE (so critical-step workflows must be refused).
    def _fake_get_current_user():
        return SimpleNamespace(id="u1", role="member")

    app.dependency_overrides[core.auth.get_current_user] = _fake_get_current_user
    return app


@pytest.fixture
def fake_engine():
    engine = MagicMock()
    engine.start_workflow = AsyncMock(return_value="exec_test")
    return engine


class TestNodeBasedWorkflowDerivedSteps:
    """R1: GET endpoints expose steps/steps_count for node-based definitions."""

    def test_get_workflows_includes_derived_steps_for_node_based(self, app):
        wf = _build_node_workflow(critical=False)
        client = TestClient(app)
        with patch.object(workflow_endpoints, "load_workflows", return_value=[wf]):
            resp = client.get("/api/v1/workflows/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        entry = data[0]
        assert entry["steps_count"] == 1, (
            "node-based workflow has no steps_count → frontend shows 0 steps"
        )
        assert isinstance(entry["steps"], list) and len(entry["steps"]) == 1
        assert entry["steps"][0]["service"] == "email"
        assert entry["steps"][0]["action"] == "send"

    def test_get_workflow_includes_derived_steps_for_node_based(self, app):
        wf = _build_node_workflow(critical=False)
        client = TestClient(app)
        with patch.object(workflow_endpoints, "load_workflows", return_value=[wf]):
            resp = client.get("/api/v1/workflows/workflows/wf_node_1")
        assert resp.status_code == 200
        entry = resp.json()
        assert entry["steps_count"] == 1
        assert len(entry["steps"]) == 1


class TestNodeBasedCriticalStepGate:
    """R2: node-based critical steps must require WORKFLOW_MANAGE."""

    def test_member_cannot_execute_node_based_critical_workflow(self, app, fake_engine):
        wf = _build_node_workflow(critical=True)
        client = TestClient(app)
        with (
            patch.object(workflow_endpoints, "load_workflows", return_value=[wf]),
            patch("core.workflow_engine.get_workflow_engine", return_value=fake_engine),
        ):
            resp = client.post(
                "/api/v1/workflows/workflows/wf_node_1/execute", json={}
            )
        assert resp.status_code == 403, (
            "node-based critical (terminal) workflow executed for a member — "
            "the gate saw an empty steps list"
        )
        fake_engine.start_workflow.assert_not_awaited()

    def test_member_can_execute_node_based_benign_workflow(self, app, fake_engine):
        wf = _build_node_workflow(critical=False)
        client = TestClient(app)
        with (
            patch.object(workflow_endpoints, "load_workflows", return_value=[wf]),
            patch("core.workflow_engine.get_workflow_engine", return_value=fake_engine),
        ):
            resp = client.post(
                "/api/v1/workflows/workflows/wf_node_1/execute", json={}
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        fake_engine.start_workflow.assert_awaited_once()


class TestTemplateExecutionFallback:
    """R3: executing a DB template via the durable execute route must work."""

    def test_execute_workflow_falls_back_to_template_definition(self, app, fake_engine):
        client = TestClient(app)
        fake_template = SimpleNamespace(
            id="tpl_x",
            name="Template X",
            description="a template",
            steps=[
                {
                    "id": "s1",
                    "type": "action",
                    "service": "slack",
                    "action": "post",
                    "parameters": {},
                    "name": "Post to Slack",
                }
            ],
        )
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = fake_template
        fake_db.close = MagicMock()

        with (
            patch.object(workflow_endpoints, "load_workflows", return_value=[]),
            patch("core.workflow_engine.get_workflow_engine", return_value=fake_engine),
            patch.object(workflow_endpoints, "get_db", return_value=iter([fake_db])),
        ):
            resp = client.post("/api/v1/workflows/workflows/tpl_x/execute", json={})

        assert resp.status_code == 200, (
            "template execution 404'd — /workflows/{id}/execute only reads "
            "workflows.json, not the template store"
        )
        data = resp.json()
        assert data["status"] == "running"
        assert data["workflow_id"] == "tpl_x"
        fake_engine.start_workflow.assert_awaited_once()

    def test_execute_workflow_still_404s_when_template_missing(self, app, fake_engine):
        client = TestClient(app)
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = None
        fake_db.close = MagicMock()

        with (
            patch.object(workflow_endpoints, "load_workflows", return_value=[]),
            patch("core.workflow_engine.get_workflow_engine", return_value=fake_engine),
            patch.object(workflow_endpoints, "get_db", return_value=iter([fake_db])),
        ):
            resp = client.post("/api/v1/workflows/workflows/does_not_exist/execute", json={})
        assert resp.status_code == 404
