"""Coverage wave 105 — integrations/workflow_approval_routes.py (TDD, 0% baseline).

Fully mocked (fake SQLAlchemy session via dependency override, fake
get_current_user, AdvancedWorkflowOrchestrator class patched on the module),
zero network, zero LLM spend.

BUG FOUND + FIXED (TDD RED->GREEN): GET /pending crashed with an unhandled
500 when any PAUSED execution row had (a) malformed (non-JSON) `context` or
`input_data`, or (b) a NULL `created_at` — one corrupt row took down the
entire pending-approvals list. The malformed-context / malformed-input /
null-created_at tests below were RED (500) before the fix; parsing is now
fail-safe (bad JSON -> {}) and created_at is guarded. The rest of the list
still renders.

Covers: /pending (success with waiting steps + input data, empty list,
malformed context JSON, malformed input_data JSON, null created_at,
execution with no waiting steps, anon 401), /{execution_id}/respond
(approve on PAUSED, approve on legacy waiting_approval marker, approve
service failure -> 500, reject sets FAILED + comments + commit, 404 unknown
execution, 400 not-waiting execution, 422 missing decision, 422 missing
step_id, anon 401).
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.database import get_db
from core.models import User

from integrations import workflow_approval_routes as war


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "wap105-user"
    u.email = "wap105@x.com"
    return u


def _execution(**overrides):
    defaults = dict(
        execution_id="exec-1",
        workflow_id="wf-1",
        status="PAUSED",
        context='{"results": {"s1": {"status": "waiting_approval"}}}',
        input_data='{"amount": 100}',
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_db(rows, first=None):
    db = MagicMock()
    query_chain = db.query.return_value.filter.return_value
    query_chain.all.return_value = rows
    query_chain.first.return_value = first if first is not None else (rows[0] if rows else None)
    return db


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(war.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(war.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _orch():
    with patch.object(war, "AdvancedWorkflowOrchestrator") as cls:
        inst = MagicMock()
        inst.resume_workflow = AsyncMock()
        cls.return_value = inst
        yield inst


@pytest.fixture(autouse=True)
def _db_override(client, anon_client):
    db = MagicMock()
    app = client.app
    anon_app = anon_client.app
    app.dependency_overrides[get_db] = lambda: db
    anon_app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.pop(get_db, None)
    anon_app.dependency_overrides.pop(get_db, None)


class TestGetPendingApprovals:
    def test_success(self, client, _db_override):
        _db_override.query.return_value.filter.return_value.all.return_value = [
            _execution(),
        ]
        response = client.get("/api/v1/workflows/approvals/pending")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        row = body[0]
        assert row["execution_id"] == "exec-1"
        assert row["workflow_id"] == "wf-1"
        assert row["status"] == "PAUSED"
        assert row["waiting_steps"] == ["s1"]
        assert row["input_data"] == {"amount": 100}
        assert row["created_at"].startswith("2026-01-01")

    def test_empty_list(self, client, _db_override):
        _db_override.query.return_value.filter.return_value.all.return_value = []
        response = client.get("/api/v1/workflows/approvals/pending")
        assert response.status_code == 200
        assert response.json() == []

    def test_no_waiting_steps(self, client, _db_override):
        _db_override.query.return_value.filter.return_value.all.return_value = [
            _execution(context='{"results": {"s1": {"status": "done"}}}'),
        ]
        response = client.get("/api/v1/workflows/approvals/pending")
        assert response.status_code == 200
        assert response.json()[0]["waiting_steps"] == []

    def test_malformed_context_json(self, client, _db_override):
        _db_override.query.return_value.filter.return_value.all.return_value = [
            _execution(context="{not valid json!!"),
        ]
        response = client.get("/api/v1/workflows/approvals/pending")
        assert response.status_code == 200
        assert response.json()[0]["waiting_steps"] == []

    def test_malformed_input_data_json(self, client, _db_override):
        _db_override.query.return_value.filter.return_value.all.return_value = [
            _execution(input_data="<html>garbage"),
        ]
        response = client.get("/api/v1/workflows/approvals/pending")
        assert response.status_code == 200
        assert response.json()[0]["input_data"] == {}

    def test_null_context_and_input(self, client, _db_override):
        _db_override.query.return_value.filter.return_value.all.return_value = [
            _execution(context=None, input_data=None),
        ]
        response = client.get("/api/v1/workflows/approvals/pending")
        assert response.status_code == 200
        row = response.json()[0]
        assert row["waiting_steps"] == []
        assert row["input_data"] == {}

    def test_null_created_at(self, client, _db_override):
        _db_override.query.return_value.filter.return_value.all.return_value = [
            _execution(created_at=None),
        ]
        response = client.get("/api/v1/workflows/approvals/pending")
        assert response.status_code == 200
        assert response.json()[0]["created_at"] is None

    def test_anonymous_401(self, anon_client, _db_override):
        response = anon_client.get("/api/v1/workflows/approvals/pending")
        assert response.status_code == 401


class TestRespondToApproval:
    def test_approve_success(self, client, _db_override, _orch):
        _db_override.query.return_value.filter.return_value.first.return_value = \
            _execution()
        response = client.post(
            "/api/v1/workflows/approvals/exec-1/respond",
            json={"decision": "approve", "step_id": "s1", "comments": "go"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["message"] == "Workflow exec-1 resumed"
        _orch.resume_workflow.assert_awaited_once_with("exec-1", "s1")

    def test_approve_legacy_waiting_marker(self, client, _db_override, _orch):
        _db_override.query.return_value.filter.return_value.first.return_value = \
            _execution(status="waiting_approval")
        response = client.post(
            "/api/v1/workflows/approvals/exec-1/respond",
            json={"decision": "approve", "step_id": "s1"})
        assert response.status_code == 200
        _orch.resume_workflow.assert_awaited_once_with("exec-1", "s1")

    def test_approve_service_failure_500(self, client, _db_override, _orch):
        _db_override.query.return_value.filter.return_value.first.return_value = \
            _execution()
        _orch.resume_workflow.side_effect = RuntimeError("boom")
        response = client.post(
            "/api/v1/workflows/approvals/exec-1/respond",
            json={"decision": "approve", "step_id": "s1"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal error"

    def test_reject_success(self, client, _db_override):
        execution = _execution()
        _db_override.query.return_value.filter.return_value.first.return_value = \
            execution
        response = client.post(
            "/api/v1/workflows/approvals/exec-1/respond",
            json={"decision": "reject", "step_id": "s1", "comments": "nope"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "cancelled"
        assert "was rejected" in body["message"]
        assert execution.status == "FAILED"
        assert execution.error == "Rejected by user: nope"
        _db_override.commit.assert_called_once()

    def test_reject_no_comments(self, client, _db_override):
        execution = _execution()
        _db_override.query.return_value.filter.return_value.first.return_value = \
            execution
        response = client.post(
            "/api/v1/workflows/approvals/exec-1/respond",
            json={"decision": "reject", "step_id": "s1"})
        assert response.status_code == 200
        assert execution.status == "FAILED"
        assert execution.error == "Rejected by user: None"

    def test_unknown_execution_404(self, client, _db_override):
        _db_override.query.return_value.filter.return_value.first.return_value = None
        response = client.post(
            "/api/v1/workflows/approvals/exec-zz/respond",
            json={"decision": "approve", "step_id": "s1"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Execution not found"

    def test_not_waiting_400(self, client, _db_override):
        _db_override.query.return_value.filter.return_value.first.return_value = \
            _execution(status="RUNNING")
        response = client.post(
            "/api/v1/workflows/approvals/exec-1/respond",
            json={"decision": "approve", "step_id": "s1"})
        assert response.status_code == 400
        assert response.json()["detail"] == "Execution is not waiting for approval"

    def test_missing_decision_422(self, client, _db_override):
        response = client.post(
            "/api/v1/workflows/approvals/exec-1/respond",
            json={"step_id": "s1"})
        assert response.status_code == 422

    def test_missing_step_id_422(self, client, _db_override):
        response = client.post(
            "/api/v1/workflows/approvals/exec-1/respond",
            json={"decision": "approve"})
        assert response.status_code == 422

    def test_bad_decision_422(self, client, _db_override):
        response = client.post(
            "/api/v1/workflows/approvals/exec-1/respond",
            json={"decision": "maybe", "step_id": "s1"})
        assert response.status_code == 422

    def test_anonymous_401(self, anon_client, _db_override):
        response = anon_client.post(
            "/api/v1/workflows/approvals/exec-1/respond",
            json={"decision": "approve", "step_id": "s1"})
        assert response.status_code == 401
