"""
TDD regression test: POST /workflows/{workflow_id}/schedule only accepted
file-based workflows (workflows.json). DB templates (WorkflowTemplate) — which
can be executed via POST /workflows/{id}/execute — 404'd on schedule. Templates
must be schedulable.
"""

import sys
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
        return SimpleNamespace(id="u1", role="team_lead")

    app.dependency_overrides[core.auth.get_current_user] = _fake_get_current_user
    return app


def test_schedule_accepts_db_template(app):
    """A DB template definition must be schedulable (not 404)."""
    template = SimpleNamespace(
        id="tpl_1",
        name="Template",
        description="desc",
        steps=[{"id": "s1", "service": "http", "action": "get", "parameters": {}}],
    )
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = template
    fake_db.close = MagicMock()

    scheduler = MagicMock()
    scheduler.schedule_workflow.return_value = "job_1"

    client = TestClient(app)
    with (
        patch("core.workflow_endpoints.load_workflows", return_value=[]),
        patch.object(workflow_endpoints, "get_db", return_value=iter([fake_db])),
        patch("ai.workflow_scheduler.workflow_scheduler", scheduler),
        patch.object(workflow_endpoints.RBACService, "check_permission", return_value=True),
    ):
        resp = client.post(
            "/api/v1/workflows/workflows/tpl_1/schedule",
            json={"trigger_type": "interval", "trigger_config": {"minutes": 30}},
        )

    assert resp.status_code == 200, "template scheduling 404'd"
    assert resp.json()["job_id"] == "job_1"
