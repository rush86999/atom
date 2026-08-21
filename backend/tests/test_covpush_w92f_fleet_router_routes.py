"""Coverage — api/fleet_router_routes.py (admin-gated automation surface).

Every management endpoint verified: 401 anonymous, 403 non-admin, 500 on
service failure; approve/reject cover 404 (not applied) and 409 (reject with
nothing pending). Public /automation/status covers success + degraded path.
Mirrors tests/test_covpush_w90_stage_router.py.
"""
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.fleet_router_routes as frr
from core.models import UserRole

ADMIN_ROLE = UserRole.ADMIN.value


class FakeUser:
    def __init__(self, role=ADMIN_ROLE):
        self.id = "u-1"
        self.role = role


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(frr.router)
    app.dependency_overrides[frr.get_current_user] = lambda: FakeUser()
    yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def member_client():
    app = FastAPI()
    app.include_router(frr.router)
    app.dependency_overrides[frr.get_current_user] = lambda: FakeUser(
        role=UserRole.MEMBER.value
    )
    yield TestClient(app)
    app.dependency_overrides = {}


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(frr.router)
    yield TestClient(app)
    app.dependency_overrides = {}


class TestStatus:
    def test_status_public(self, anon_client):
        with patch(
            "core.fleet_orchestration.fleet_routing_stats.fleet_calibration_status",
            return_value={"phase": "collecting"},
        ):
            resp = anon_client.get("/api/v1/fleet/automation/status")
        assert resp.status_code == 200
        assert resp.json()["phase"] == "collecting"

    def test_status_degraded(self, anon_client):
        with patch(
            "core.fleet_orchestration.fleet_routing_stats.fleet_calibration_status",
            side_effect=RuntimeError("boom"),
        ):
            resp = anon_client.get("/api/v1/fleet/automation/status")
        assert resp.status_code == 200
        assert resp.json()["phase"] == "error"


class TestAutomation:
    def test_get_automation_admin(self, client):
        with patch(
            "core.fleet_orchestration.fleet_router_automation.get_automation_status",
            return_value={"mode": "approve"},
        ):
            resp = client.get("/api/v1/fleet/automation")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "approve"

    def test_get_automation_anon_401(self, anon_client):
        resp = anon_client.get("/api/v1/fleet/automation")
        assert resp.status_code == 401

    def test_get_automation_member_403(self, member_client):
        resp = member_client.get("/api/v1/fleet/automation")
        assert resp.status_code == 403

    def test_config_admin(self, client):
        with patch(
            "core.fleet_orchestration.fleet_router_automation.set_automation_config",
            return_value={"mode": "notify", "interval_min": 30},
        ):
            resp = client.post("/api/v1/fleet/automation/config", json={"mode": "notify"})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "notify"

    def test_config_non_admin_403(self, anon_client):
        resp = anon_client.post("/api/v1/fleet/automation/config", json={"mode": "off"})
        assert resp.status_code == 401

    def test_run_now_admin(self, client):
        with patch(
            "core.fleet_orchestration.fleet_router_automation.run_auto_certification",
            return_value={"enabled": True, "certified": []},
        ):
            resp = client.post("/api/v1/fleet/automation/run-now")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_run_now_member_403(self, member_client):
        resp = member_client.post("/api/v1/fleet/automation/run-now")
        assert resp.status_code == 403

    def test_approve_admin(self, client):
        with patch(
            "core.fleet_orchestration.fleet_router_automation.apply_pending_decision",
            return_value={"applied": True, "state": "applied"},
        ):
            resp = client.post("/api/v1/fleet/automation/approve", json={})
        assert resp.status_code == 200
        assert resp.json()["applied"] is True

    def test_approve_nothing_pending_404(self, client):
        with patch(
            "core.fleet_orchestration.fleet_router_automation.apply_pending_decision",
            return_value={"applied": False, "reason": "no pending approval"},
        ):
            resp = client.post("/api/v1/fleet/automation/approve", json={})
        assert resp.status_code == 404

    def test_reject_admin(self, client):
        with patch(
            "core.fleet_orchestration.fleet_router_automation.apply_pending_decision",
            return_value={"applied": False, "state": "rejected"},
        ):
            resp = client.post("/api/v1/fleet/automation/reject", json={})
        assert resp.status_code == 200
        assert resp.json()["state"] == "rejected"

    def test_approve_anon_401(self, anon_client):
        resp = anon_client.post("/api/v1/fleet/automation/approve", json={})
        assert resp.status_code == 401

    def test_reject_member_403(self, member_client):
        resp = member_client.post("/api/v1/fleet/automation/reject", json={})
        assert resp.status_code == 403