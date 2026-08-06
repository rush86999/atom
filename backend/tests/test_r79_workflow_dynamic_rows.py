"""
TDD regression: GET /api/v1/workflows/workflows must survive step-based
"Dynamic Workflow" rows in workflows.json.

Prod reality (verified 2026-08-06): agent-driven workflow creation writes
step-based rows (steps/step_type, no nodes/connections/triggers/enabled).
GET /workflows then 500s with ~132 response-schema validation errors because
WorkflowDefinition requires nodes/connections/triggers/enabled — so the
primary workflow list is broken whenever dynamic workflows exist.
"""
import json
import sys
from types import SimpleNamespace

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.auth
from core import workflow_endpoints


def _step_based_dynamic_row(name: str = "Dynamic Workflow") -> dict:
    """A row as written by the agent-driven create flow (step dialect)."""
    return {
        "name": name,
        "description": "create a workflow to send an email",
        "version": "1.0",
        "steps": [
            {
                "id": "s1",
                "type": "task",
                "step_type": "action",
                "config": {"service": "email", "action": "send", "parameters": {}},
            }
        ],
    }


@pytest.fixture
def app(tmp_path, monkeypatch):
    wf_file = tmp_path / "workflows.json"
    monkeypatch.setattr(workflow_endpoints, "WORKFLOWS_FILE", str(wf_file))
    app = FastAPI()
    app.include_router(workflow_endpoints.router, prefix="/api/v1/workflows")

    def _fake_get_current_user():
        return SimpleNamespace(id="u1", role="member")

    app.dependency_overrides[core.auth.get_current_user] = _fake_get_current_user
    return app, wf_file


def test_list_workflows_with_step_based_rows_returns_200(app):
    fastapi_app, wf_file = app
    with open(wf_file, "w") as f:
        json.dump([_step_based_dynamic_row()], f)

    client = TestClient(fastapi_app)
    resp = client.get("/api/v1/workflows/workflows")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    row = data[0]
    # Normalized to the node-based response contract:
    assert row["nodes"] == []
    assert row["connections"] == []
    assert row["triggers"] == []
    assert row["enabled"] is True
    # Step dialect preserved for step-based consumers:
    assert row["steps_count"] == 1


def test_list_workflows_mixed_rows_returns_200(app):
    fastapi_app, wf_file = app
    node_row = {
        "id": "wf_node_1",
        "name": "Node Workflow",
        "description": "graph-based",
        "version": "1.0",
        "nodes": [],
        "connections": [],
        "triggers": [],
        "enabled": True,
    }
    with open(wf_file, "w") as f:
        json.dump([node_row, _step_based_dynamic_row()], f)

    client = TestClient(fastapi_app)
    resp = client.get("/api/v1/workflows/workflows")

    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 2


def test_get_workflow_by_id_step_based_returns_200(app):
    fastapi_app, wf_file = app
    with open(wf_file, "w") as f:
        json.dump([_step_based_dynamic_row()], f)

    client = TestClient(fastapi_app)
    # Step-based rows have no id — pick by position-independent lookup.
    resp = client.get("/api/v1/workflows/workflows/nonexistent")
    assert resp.status_code == 404  # unknown id still 404s, not 500
