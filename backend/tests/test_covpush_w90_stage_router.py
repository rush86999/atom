"""Coverage wave 90 — api/stage_router_routes.py (0% → 95%+).

Admin-gated automation surface. Every management endpoint verified:
401 anonymous, 403 non-admin, 500 on service failure; approve/reject
also cover 422 (missing agent_id), 404 (not applied), 409 (reject with
nothing pending). Public /status covers success + degraded error path.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.stage_router_routes as srr
from core.auth import get_current_user
from core.models import UserRole

ADMIN_ROLE = UserRole.ADMIN.value


class FakeUser:
    def __init__(self, role=ADMIN_ROLE):
        self.id = "u-1"
        self.role = role


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(srr.router)
    app.dependency_overrides[srr.get_current_user] = lambda: FakeUser()
    yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def member_client():
    app = FastAPI()
    app.include_router(srr.router)
    app.dependency_overrides[srr.get_current_user] = lambda: FakeUser(
        role=UserRole.MEMBER.value
    )
    yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(srr.router)
    yield TestClient(app)
    app.dependency_overrides = {}


class TestStatus:
    def test_status_public(self, anon_client):
        with patch(
            "core.llm.stage_router.stage_router_status", return_value={"phase": "shadow"}
        ):
            resp = anon_client.get("/api/v1/llm/stage-router/status")
        assert resp.status_code == 200
        assert resp.json()["phase"] == "shadow"

    def test_status_error_returns_degraded(self, anon_client):
        with patch(
            "core.llm.stage_router.stage_router_status",
            side_effect=RuntimeError("boom"),
        ):
            resp = anon_client.get("/api/v1/llm/stage-router/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["phase"] == "error"
        assert body["error"] == "internal"
        assert "boom" not in resp.text


class TestAutomation:
    def test_automation_requires_auth(self, anon_client):
        assert anon_client.get("/api/v1/llm/stage-router/automation").status_code == 401

    def test_automation_requires_admin(self, member_client):
        resp = member_client.get("/api/v1/llm/stage-router/automation")
        assert resp.status_code == 403

    def test_automation_success(self, client):
        with patch(
            "core.llm.stage_router_automation.get_automation_status",
            return_value={"mode": "approve"},
        ):
            resp = client.get("/api/v1/llm/stage-router/automation")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "approve"

    def test_automation_service_failure_500(self, client):
        with patch(
            "core.llm.stage_router_automation.get_automation_status",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.get("/api/v1/llm/stage-router/automation")
        assert resp.status_code == 500
        assert "Automation status unavailable" in resp.text


class TestConfig:
    def test_config_requires_auth(self, anon_client):
        resp = anon_client.post("/api/v1/llm/stage-router/automation/config", json={})
        assert resp.status_code == 401

    def test_config_requires_admin(self, member_client):
        resp = member_client.post("/api/v1/llm/stage-router/automation/config", json={})
        assert resp.status_code == 403

    def test_config_success(self, client):
        with patch(
            "core.llm.stage_router_automation.set_automation_config",
            return_value={"mode": "off", "interval_min": 120},
        ) as m:
            resp = client.post(
                "/api/v1/llm/stage-router/automation/config",
                json={"mode": "off", "interval_min": 120},
            )
        assert resp.status_code == 200
        assert resp.json()["mode"] == "off"
        m.assert_called_once_with(mode="off", interval_min=120)

    def test_config_service_failure_500(self, client):
        with patch(
            "core.llm.stage_router_automation.set_automation_config",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.post(
                "/api/v1/llm/stage-router/automation/config",
                json={"mode": "notify"},
            )
        assert resp.status_code == 500
        assert "Automation config update failed" in resp.text


class TestRunNow:
    def test_run_now_requires_auth(self, anon_client):
        resp = anon_client.post("/api/v1/llm/stage-router/automation/run-now")
        assert resp.status_code == 401

    def test_run_now_requires_admin(self, member_client):
        resp = member_client.post("/api/v1/llm/stage-router/automation/run-now")
        assert resp.status_code == 403

    def test_run_now_success(self, client):
        with patch(
            "core.llm.stage_router_automation.run_auto_certification",
            return_value={"certified": ["a1"]},
        ):
            resp = client.post("/api/v1/llm/stage-router/automation/run-now")
        assert resp.status_code == 200
        assert resp.json()["certified"] == ["a1"]

    def test_run_now_service_failure_500(self, client):
        with patch(
            "core.llm.stage_router_automation.run_auto_certification",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.post("/api/v1/llm/stage-router/automation/run-now")
        assert resp.status_code == 500
        assert "Automation run failed" in resp.text


class TestApprove:
    def test_approve_requires_auth(self, anon_client):
        resp = anon_client.post(
            "/api/v1/llm/stage-router/automation/approve", json={"agent_id": "a1"}
        )
        assert resp.status_code == 401

    def test_approve_requires_admin(self, member_client):
        resp = member_client.post(
            "/api/v1/llm/stage-router/automation/approve", json={"agent_id": "a1"}
        )
        assert resp.status_code == 403

    def test_approve_missing_agent_id_422(self, client):
        resp = client.post("/api/v1/llm/stage-router/automation/approve", json={})
        assert resp.status_code == 422
        assert "agent_id is required" in resp.text

    def test_approve_success(self, client):
        with patch(
            "core.llm.stage_router_automation.apply_pending_decision",
            return_value={"applied": True, "agent_id": "a1"},
        ) as m:
            resp = client.post(
                "/api/v1/llm/stage-router/automation/approve",
                json={"agent_id": "a1"},
            )
        assert resp.status_code == 200
        assert resp.json()["applied"] is True
        m.assert_called_once()
        assert m.call_args.args[1] == "a1"
        assert m.call_args.kwargs["approve"] is True

    def test_approve_nothing_pending_404(self, client):
        db = MagicMock()
        with patch(
            "core.llm.stage_router_automation.apply_pending_decision",
            return_value={"applied": False, "reason": "no pending decision"},
        ):
            resp = client.post(
                "/api/v1/llm/stage-router/automation/approve",
                json={"agent_id": "a1"},
            )
        assert resp.status_code == 404
        assert "no pending decision" in resp.text

    def test_approve_service_failure_500(self, client):
        db = MagicMock()
        with patch(
            "core.llm.stage_router_automation.apply_pending_decision",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.post(
                "/api/v1/llm/stage-router/automation/approve",
                json={"agent_id": "a1"},
            )
        assert resp.status_code == 500
        assert "Approval failed" in resp.text
        assert "boom" not in resp.text


class TestReject:
    def test_reject_requires_auth(self, anon_client):
        resp = anon_client.post(
            "/api/v1/llm/stage-router/automation/reject", json={"agent_id": "a1"}
        )
        assert resp.status_code == 401

    def test_reject_requires_admin(self, member_client):
        resp = member_client.post(
            "/api/v1/llm/stage-router/automation/reject", json={"agent_id": "a1"}
        )
        assert resp.status_code == 403

    def test_reject_missing_agent_id_422(self, client):
        resp = client.post("/api/v1/llm/stage-router/automation/reject", json={})
        assert resp.status_code == 422
        assert "agent_id is required" in resp.text

    def test_reject_success(self, client):
        with patch(
            "core.llm.stage_router_automation.apply_pending_decision",
            return_value={"applied": True},
        ) as m:
            resp = client.post(
                "/api/v1/llm/stage-router/automation/reject",
                json={"agent_id": "a1"},
            )
        assert resp.status_code == 409
        assert "No pending approval to reject" in resp.text
        m.assert_called_once()
        assert m.call_args.args[1] == "a1"
        assert m.call_args.kwargs["approve"] is False

    def test_reject_service_failure_500(self, client):
        db = MagicMock()
        with patch(
            "core.llm.stage_router_automation.apply_pending_decision",
            side_effect=RuntimeError("boom"),
        ):
            resp = client.post(
                "/api/v1/llm/stage-router/automation/reject",
                json={"agent_id": "a1"},
            )
        assert resp.status_code == 500
        assert "Rejection failed" in resp.text

    def test_reject_applied_false_returns_result(self, client):
        db = MagicMock()
        with patch(
            "core.llm.stage_router_automation.apply_pending_decision",
            return_value={"applied": False, "reason": "already rejected"},
        ):
            resp = client.post(
                "/api/v1/llm/stage-router/automation/reject",
                json={"agent_id": "a1"},
            )
        assert resp.status_code == 200
        assert resp.json()["applied"] is False
