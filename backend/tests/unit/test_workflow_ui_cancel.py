"""
TDD regression tests: POST /workflows-ui/executions/{id}/cancel only mutated
MOCK_EXECUTIONS and required no auth, so canceling a real execution 404'd and
the endpoint was an unauthenticated state change.
"""

import inspect
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.auth
from core import workflow_ui_endpoints


def _route_auth_deps(func) -> list:
    deps = []
    for p in inspect.signature(func).parameters.values():
        if p.default is inspect.Parameter.empty:
            continue
        if hasattr(p.default, "dependency"):
            deps.append(getattr(p.default.dependency, "__name__", "") or "")
        elif hasattr(p.default, "__name__"):
            deps.append(p.default.__name__)
    return deps


def test_cancel_execution_requires_auth():
    deps = _route_auth_deps(workflow_ui_endpoints.cancel_execution)
    assert any("get_current_user" in d for d in deps), (
        "cancel_execution has no auth — anyone can cancel executions"
    )


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(workflow_ui_endpoints.router, prefix="/api/v1/workflow-ui")

    def _fake_get_current_user():
        return SimpleNamespace(id="u1", role="member")

    app.dependency_overrides[core.auth.get_current_user] = _fake_get_current_user
    return app


def test_cancel_execution_updates_persisted_row(app):
    """A durable-engine execution (DB WorkflowExecution row) must be cancelled
    in the table — the old route only scanned MOCK_EXECUTIONS and 404'd."""
    row = SimpleNamespace(execution_id="exec_c", workflow_id="wf_1", status="RUNNING")
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = row
    fake_db.commit = MagicMock()
    fake_db.close = MagicMock()

    client = TestClient(app)
    with (
        patch.object(workflow_ui_endpoints, "get_db", return_value=iter([fake_db])),
        patch("advanced_workflow_orchestrator.get_orchestrator", return_value=SimpleNamespace(active_contexts={})),
    ):
        resp = client.post("/api/v1/workflow-ui/executions/exec_c/cancel")

    assert resp.status_code == 200
    assert resp.json() == {"success": True}
    assert row.status == "CANCELLED", (
        "cancel did not update the persisted execution row"
    )
    fake_db.commit.assert_called_once()


def test_cancel_execution_404_for_unknown(app):
    """Unknown execution id must still 404."""
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = None
    fake_db.close = MagicMock()

    client = TestClient(app)
    with (
        patch.object(workflow_ui_endpoints, "get_db", return_value=iter([fake_db])),
        patch("advanced_workflow_orchestrator.get_orchestrator", return_value=SimpleNamespace(active_contexts={})),
    ):
        resp = client.post("/api/v1/workflow-ui/executions/does_not_exist/cancel")

    assert resp.status_code == 404
