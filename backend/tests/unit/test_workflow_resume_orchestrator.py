"""
TDD regression tests: POST /workflows/{execution_id}/resume only resumed
durable-engine (ExecutionStateManager) executions and 404'd for executions
owned by the advanced orchestrator (workflow UI path). It must fall back to
the orchestrator when a step is waiting for approval.
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


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(workflow_endpoints.router, prefix="/api/v1/workflows")

    def _fake_get_current_user():
        return SimpleNamespace(id="u1", role="member")

    app.dependency_overrides[core.auth.get_current_user] = _fake_get_current_user
    return app


def test_resume_falls_back_to_orchestrator_waiting_step(app):
    """An orchestrator-owned execution with a step waiting for approval must
    resume via the orchestrator instead of 404ing."""
    state_manager = MagicMock()
    state_manager.get_execution_state = AsyncMock(return_value=None)

    context = SimpleNamespace(results={"step2": {"status": "waiting_approval"}})
    orchestrator = SimpleNamespace(active_contexts={"exec_o": context})
    orchestrator.resume_workflow = AsyncMock()

    client = TestClient(app)
    with (
        patch("core.execution_state_manager.get_state_manager", return_value=state_manager),
        patch("core.workflow_engine.get_workflow_engine", return_value=MagicMock()),
        patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orchestrator),
    ):
        resp = client.post("/api/v1/workflows/workflows/exec_o/resume", json={})

    assert resp.status_code == 200, (
        "orchestrator-owned execution could not be resumed (404 before fix)"
    )
    assert resp.json() == {"status": "resumed", "execution_id": "exec_o"}
    orchestrator.resume_workflow.assert_awaited_once_with("exec_o", "step2")


def test_resume_400_when_orchestrator_step_not_approvable(app):
    """An orchestrator execution with no waiting-approval step gets a clear
    400, not a misleading 404."""
    state_manager = MagicMock()
    state_manager.get_execution_state = AsyncMock(return_value=None)

    context = SimpleNamespace(results={"step1": {"status": "completed"}})
    orchestrator = SimpleNamespace(active_contexts={"exec_o": context})

    client = TestClient(app)
    with (
        patch("core.execution_state_manager.get_state_manager", return_value=state_manager),
        patch("core.workflow_engine.get_workflow_engine", return_value=MagicMock()),
        patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orchestrator),
    ):
        resp = client.post("/api/v1/workflows/workflows/exec_o/resume", json={})

    assert resp.status_code == 400


def test_resume_404_when_no_state_and_no_orchestrator(app):
    """Unknown execution id still 404s."""
    state_manager = MagicMock()
    state_manager.get_execution_state = AsyncMock(return_value=None)
    orchestrator = SimpleNamespace(active_contexts={})

    client = TestClient(app)
    with (
        patch("core.execution_state_manager.get_state_manager", return_value=state_manager),
        patch("core.workflow_engine.get_workflow_engine", return_value=MagicMock()),
        patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orchestrator),
    ):
        resp = client.post("/api/v1/workflows/workflows/ghost/resume", json={})

    assert resp.status_code == 404
