"""
TDD regression test: the Executions tab only read the orchestrator's in-memory
contexts, so executions started via POST /workflows/{id}/execute (durable
WorkflowEngine → ExecutionStateManager → DB WorkflowExecution table) never
appeared. _merge_persisted_executions must surface them.
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
from core import workflow_ui_endpoints


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(workflow_ui_endpoints.router, prefix="/api/v1/workflow-ui")

    def _fake_get_current_user():
        return SimpleNamespace(id="u1", role="member")

    app.dependency_overrides[core.auth.get_current_user] = _fake_get_current_user
    return app


def test_get_executions_includes_persisted_engine_executions(app):
    """A durable-engine execution (DB WorkflowExecution row) must appear in
    the Executions tab response."""
    row = SimpleNamespace(
        execution_id="exec_durable_1",
        workflow_id="wf_1",
        status="RUNNING",
        input_data='{"foo": "bar"}',
        steps='{"s1": {}}',
        outputs='{"result": "ok"}',
        created_at=datetime.now(timezone.utc),
        completed_at=None,
        error=None,
    )
    fake_db = MagicMock()
    query_chain = fake_db.query.return_value.order_by.return_value.limit.return_value
    query_chain.all.return_value = [row]
    fake_db.close = MagicMock()

    client = TestClient(app)
    with (
        patch("advanced_workflow_orchestrator.get_orchestrator", return_value=SimpleNamespace(active_contexts={})),
        patch.object(workflow_ui_endpoints, "get_db", return_value=iter([fake_db])),
    ):
        resp = client.get("/api/v1/workflow-ui/executions")

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    ids = [e["execution_id"] for e in data["executions"]]
    assert "exec_durable_1" in ids, (
        "durable-engine execution missing from Executions tab"
    )


def test_get_executions_dedupes_orchestrator_and_persisted(app):
    """Same execution_id from both sources must appear only once."""
    from core.workflow_ui_endpoints import WorkflowExecution

    existing = WorkflowExecution(
        execution_id="exec_shared",
        workflow_id="wf_1",
        status="running",
        start_time="2024-01-01T00:00:00",
        end_time=None,
        current_step=1,
        total_steps=2,
        trigger_data={},
        results={},
        errors=[],
    )
    row = SimpleNamespace(
        execution_id="exec_shared",
        workflow_id="wf_1",
        status="COMPLETED",
        input_data="{}",
        steps="{}",
        outputs="{}",
        created_at=datetime.now(timezone.utc),
        completed_at=None,
        error=None,
    )
    fake_db = MagicMock()
    query_chain = fake_db.query.return_value.order_by.return_value.limit.return_value
    query_chain.all.return_value = [row]
    fake_db.close = MagicMock()

    # Orchestrator already returns exec_shared; the DB row for the same id
    # must NOT be duplicated.
    orchestrator = SimpleNamespace(active_contexts={})
    client = TestClient(app)
    with (
        patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orchestrator),
        patch.object(workflow_ui_endpoints, "get_db", return_value=iter([fake_db])),
        patch.object(workflow_ui_endpoints, "_merge_persisted_executions", return_value=[existing]),
    ):
        resp = client.get("/api/v1/workflow-ui/executions")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["executions"]) == 1
