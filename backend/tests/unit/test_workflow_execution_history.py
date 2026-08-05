"""
TDD regression tests: GET /workflows/{workflow_id}/executions and
GET /workflows/executions/{execution_id} only read the legacy
AutomationEngine (executions.json), so durable-engine executions
(ExecutionStateManager -> DB WorkflowExecution table) and orchestrator
contexts never appear — the frontend detail/history views 404 or show empty.
"""

import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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


def _row(execution_id="exec_d", workflow_id="wf_1", status="RUNNING"):
    return SimpleNamespace(
        execution_id=execution_id,
        workflow_id=workflow_id,
        status=status,
        input_data='{"foo": "bar"}',
        steps='{"s1": {}}',
        outputs='{"result": "ok"}',
        created_at=datetime.now(timezone.utc),
        completed_at=None,
        error=None,
    )


def _patch_db(fake_db):
    """Patch the module's get_db to yield fake_db."""
    return patch.object(workflow_endpoints, "get_db", return_value=iter([fake_db]))


def _patch_engine(executions=None, history=None):
    return patch(
        "ai.automation_engine.AutomationEngine",
        return_value=SimpleNamespace(
            executions=executions or {},
            get_execution_history=lambda wf: history or [],
        ),
    )


def test_execution_details_returns_durable_row(app):
    """A durable-engine execution (DB WorkflowExecution row) must return 200
    details instead of 404ing (only the legacy AutomationEngine was read)."""
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = _row()
    fake_db.close = MagicMock()

    client = TestClient(app)
    with (_patch_db(fake_db), _patch_engine()):
        resp = client.get("/api/v1/workflows/workflows/executions/exec_d")

    assert resp.status_code == 200, "durable execution details 404'd"
    data = resp.json()
    assert data["execution_id"] == "exec_d"
    assert data["workflow_id"] == "wf_1"
    assert data["status"] == "running"


def test_execution_details_404_unknown(app):
    """Unknown execution id still 404s."""
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = None
    fake_db.close = MagicMock()

    client = TestClient(app)
    with (
        _patch_db(fake_db),
        _patch_engine(),
        patch("advanced_workflow_orchestrator.get_orchestrator", return_value=SimpleNamespace(active_contexts={})),
    ):
        resp = client.get("/api/v1/workflows/workflows/executions/ghost")

    assert resp.status_code == 404


def test_workflow_executions_includes_durable_rows(app):
    """Workflow history must include durable-engine DB rows, not just the
    legacy AutomationEngine executions."""
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.all.return_value = [_row()]
    fake_db.close = MagicMock()

    client = TestClient(app)
    with (_patch_db(fake_db), _patch_engine()):
        resp = client.get("/api/v1/workflows/workflows/wf_1/executions")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    ids = [e["execution_id"] for e in data]
    assert "exec_d" in ids, "durable execution missing from workflow history"
