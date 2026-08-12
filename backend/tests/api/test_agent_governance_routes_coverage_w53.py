"""Coverage wave 53 — api/agent_governance_routes.py (TDD).

Existing suite (tests/unit/api/test_agent_governance_routes.py) covers
rules/list/single/deploy-check/capabilities/helpers/feedback. This wave fills:
- submit_workflow_for_approval (success, 404, 500)
- list_pending_approvals (with/without approver_id, 500)
- approve_workflow (user-missing 404, role-denied 403, success, failure 400, 500)
- reject_workflow (success, failure 400, 500)
- enforce_action (unknown-agent BLOCKED, APPROVED, PENDING_APPROVAL
  supervised-complexity, BLOCKED insufficient, 500)
- generate_workflow_from_description (autonomous deploy, supervised approval,
  404, 500)
- helper boundary values (get_maturity_level_from_score thresholds,
  can_deploy_directly supervised 0.8 boundary)
"""
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.models  # noqa: F401
from api.agent_governance_routes import (
    can_deploy_directly,
    get_maturity_level_from_score,
    router,
)
from core.database import Base
from core.models import User, UserRole


@pytest.fixture(scope="module")
def engine():
    import os
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    os.unlink(path)


@pytest.fixture
def db(engine):
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _make_user(db, role="member"):
    uid = f"gu-{uuid.uuid4().hex[:8]}"
    u = User(
        id=uid, email=f"{uid}@x.com",
        hashed_password="h", first_name="G", last_name="U",
        role=role, status="active", tenant_id="t-1")
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def client(db, user):
    app = FastAPI()
    app.include_router(router)

    from core.auth import get_current_user
    from core.database import get_db

    def _get_db():
        try:
            yield db
        finally:
            pass

    def _get_current_user():
        return user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def user(db):
    return _make_user(db)


@pytest.fixture
def lead_user(db):
    return _make_user(db, role=UserRole.TEAM_LEAD.value)


@pytest.fixture
def ws_request():
    return {
        "agent_id": "sales-agent",
        "workflow_name": "Lead followup",
        "workflow_definition": {"steps": []},
        "trigger_type": "manual",
        "actions": ["send_email"],
        "requested_by": "u-1",
    }


class TestHelperBoundaries:
    def test_maturity_thresholds(self):
        assert get_maturity_level_from_score(0.95) == "autonomous"
        assert get_maturity_level_from_score(0.9) == "autonomous"
        assert get_maturity_level_from_score(0.85) == "supervised"
        assert get_maturity_level_from_score(0.7) == "supervised"
        assert get_maturity_level_from_score(0.6) == "intern"
        assert get_maturity_level_from_score(0.5) == "intern"
        assert get_maturity_level_from_score(0.4) == "student"

    def test_can_deploy_directly(self):
        assert can_deploy_directly("autonomous", 0.91) is True
        assert can_deploy_directly("supervised", 0.85) is True
        assert can_deploy_directly("supervised", 0.8) is True
        assert can_deploy_directly("supervised", 0.79) is False
        assert can_deploy_directly("intern", 0.6) is False
        assert can_deploy_directly("student", 0.4) is False


class TestSubmitForApproval:
    def test_submit_success(self, client, ws_request):
        response = client.post("/api/agent-governance/submit-for-approval",
                               json=ws_request)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "pending"
        assert data["approval_id"].startswith("apr_")
        assert data["agent_name"] == "Sales Agent"
        assert data["maturity_level"] == "supervised"

    def test_submit_unknown_agent_404(self, client, ws_request):
        ws_request["agent_id"] = "ghost"
        response = client.post("/api/agent-governance/submit-for-approval",
                               json=ws_request)
        assert response.status_code == 404

    def test_submit_exception_500(self, client, ws_request):
        with patch("api.agent_governance_routes.datetime") as mock_dt:
            mock_dt.now.side_effect = RuntimeError("clock broken")
            response = client.post("/api/agent-governance/submit-for-approval",
                                   json=ws_request)
        assert response.status_code == 500


class TestPendingApprovals:
    def test_list_all(self, client):
        svc = MagicMock()
        svc.get_pending_interventions.return_value = [{"id": "a1"}]
        with patch("api.agent_governance_routes.intervention_service", svc):
            response = client.get("/api/agent-governance/pending-approvals")
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_list_by_approver(self, client):
        svc = MagicMock()
        svc.get_pending_interventions.return_value = []
        with patch("api.agent_governance_routes.intervention_service", svc):
            response = client.get(
                "/api/agent-governance/pending-approvals?approver_id=lead-1")
        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_list_exception_500(self, client):
        svc = MagicMock()
        svc.get_pending_interventions.side_effect = RuntimeError("boom")
        with patch("api.agent_governance_routes.intervention_service", svc):
            response = client.get("/api/agent-governance/pending-approvals")
        assert response.status_code == 500


class TestApproveWorkflow:
    def test_approve_user_missing_404(self, client, db):
        ghost = MagicMock(id="no-such-user")
        app = client
        from core.auth import get_current_user
        from core.database import get_db
        app.app.dependency_overrides[get_current_user] = lambda: ghost
        app.app.dependency_overrides[get_db] = lambda: (yield db)
        response = client.post("/api/agent-governance/approve/apr_1")
        assert response.status_code == 404

    def test_approve_role_denied_403(self, client, db, user):
        response = client.post("/api/agent-governance/approve/apr_1")
        assert response.status_code == 403

    def _as_lead(self, client, lead_user):
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: lead_user

    def test_approve_success(self, client, db, lead_user):
        self._as_lead(client, lead_user)
        svc = MagicMock()
        svc.approve_intervention = AsyncMock(
            return_value={"success": True, "message": "ok"})
        with patch("api.agent_governance_routes.intervention_service", svc):
            response = client.post("/api/agent-governance/approve/apr_1")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "approved"
        assert response.json()["data"]["approved_by"] == lead_user.id
        svc.approve_intervention.assert_awaited_once_with("apr_1", lead_user.id)

    def test_approve_failure_400(self, client, db, lead_user):
        self._as_lead(client, lead_user)
        svc = MagicMock()
        svc.approve_intervention = AsyncMock(
            return_value={"success": False,
                          "message": "already handled"})
        with patch("api.agent_governance_routes.intervention_service", svc):
            response = client.post("/api/agent-governance/approve/apr_1")
        assert response.status_code == 400

    def test_approve_exception_500(self, client, db, lead_user):
        self._as_lead(client, lead_user)
        svc = MagicMock()
        svc.approve_intervention = AsyncMock(
            side_effect=RuntimeError("boom"))
        with patch("api.agent_governance_routes.intervention_service", svc):
            response = client.post("/api/agent-governance/approve/apr_1")
        assert response.status_code == 500


class TestRejectWorkflow:
    def test_reject_success(self, client, user):
        svc = MagicMock()
        svc.reject_intervention = AsyncMock(
            return_value={"success": True, "message": "ok"})
        with patch("api.agent_governance_routes.intervention_service", svc):
            response = client.post(
                "/api/agent-governance/reject/apr_1?reason=not+needed")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "rejected"
        assert data["reason"] == "not needed"
        svc.reject_intervention.assert_awaited_once_with(
            "apr_1", user.id, "not needed")

    def test_reject_missing_reason_422(self, client):
        assert client.post("/api/agent-governance/reject/apr_1").status_code == 422

    def test_reject_failure_400(self, client, user):
        svc = MagicMock()
        svc.reject_intervention = AsyncMock(
            return_value={"success": False, "message": "nope"})
        with patch("api.agent_governance_routes.intervention_service", svc):
            response = client.post(
                "/api/agent-governance/reject/apr_1?reason=x")
        assert response.status_code == 400

    def test_reject_exception_500(self, client, user):
        svc = MagicMock()
        svc.reject_intervention = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.agent_governance_routes.intervention_service", svc):
            response = client.post(
                "/api/agent-governance/reject/apr_1?reason=x")
        assert response.status_code == 500


class TestEnforceAction:
    def test_enforce_unknown_agent_blocked(self, client):
        response = client.post("/api/agent-governance/enforce-action", json={
            "agent_id": "ghost", "action_type": "delete"})
        assert response.status_code == 200
        assert response.json()["status"] == "BLOCKED"

    def test_enforce_approved_autonomous(self, client):
        response = client.post("/api/agent-governance/enforce-action", json={
            "agent_id": "finance-agent", "action_type": "delete"})
        assert response.status_code == 200
        assert response.json()["status"] == "APPROVED"
        assert response.json()["proceed"] is True

    def test_enforce_supervised_complex_requires_approval(self, client):
        response = client.post("/api/agent-governance/enforce-action", json={
            "agent_id": "sales-agent", "action_type": "create"})
        assert response.status_code == 200
        assert response.json()["status"] == "PENDING_APPROVAL"
        assert response.json()["action_required"] == "WAIT_FOR_APPROVAL"

    def test_enforce_blocked_student_delete(self, client):
        response = client.post("/api/agent-governance/enforce-action", json={
            "agent_id": "engineering-agent", "action_type": "delete"})
        assert response.status_code == 200
        assert response.json()["status"] == "BLOCKED"
        assert response.json()["action_required"] == "HUMAN_APPROVAL"

    def test_enforce_case_insensitive_action(self, client):
        response = client.post("/api/agent-governance/enforce-action", json={
            "agent_id": "finance-agent", "action_type": "DELETE"})
        assert response.json()["status"] == "APPROVED"

    def test_enforce_exception_500(self, client):
        bad = MagicMock()
        bad.__contains__.return_value = True
        bad.__getitem__.side_effect = RuntimeError("boom")
        with patch("api.agent_governance_routes.MOCK_AGENTS", bad):
            response = client.post("/api/agent-governance/enforce-action", json={
                "agent_id": "finance-agent", "action_type": "delete"})
        assert response.status_code == 500


class TestGenerateWorkflow:
    def test_generate_autonomous_deploys(self, client):
        response = client.post(
            "/api/agent-governance/generate-workflow",
            params={"description": "Send daily report",
                    "agent_id": "finance-agent"})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["can_deploy_directly"] is True
        assert data["workflow"]["steps"][1]["action"] == "analyze"

    def test_generate_supervised_requires_approval(self, client):
        response = client.post(
            "/api/agent-governance/generate-workflow",
            params={"description": "Draft campaign",
                    "agent_id": "marketing-agent"})
        assert response.status_code == 200
        assert response.json()["data"]["requires_approval"] is True

    def test_generate_unknown_agent_404(self, client):
        response = client.post(
            "/api/agent-governance/generate-workflow",
            params={"description": "x", "agent_id": "ghost"})
        assert response.status_code == 404

    def test_generate_missing_params_422(self, client):
        assert client.post("/api/agent-governance/generate-workflow").status_code == 422

    def test_generate_exception_500(self, client):
        with patch("api.agent_governance_routes.datetime") as mock_dt:
            mock_dt.now.side_effect = RuntimeError("clock broken")
            response = client.post(
                "/api/agent-governance/generate-workflow",
                params={"description": "x", "agent_id": "finance-agent"})
        assert response.status_code == 500


class TestRemainingErrorPaths:
    def test_list_agents_category_filter(self, client):
        response = client.get("/api/agent-governance/agents?category=sales")
        assert response.status_code == 200
        assert all(a["category"] == "sales" for a in response.json())

    def test_list_agents_category_no_match(self, client):
        response = client.get("/api/agent-governance/agents?category=ghost")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_agents_exception_500(self, client):
        bad = MagicMock()
        bad.items.side_effect = RuntimeError("boom")
        with patch("api.agent_governance_routes.MOCK_AGENTS", bad):
            response = client.get("/api/agent-governance/agents")
        assert response.status_code == 500

    def test_get_agent_maturity_exception_500(self, client):
        bad = MagicMock()
        bad.__contains__.return_value = True
        bad.__getitem__.side_effect = RuntimeError("boom")
        with patch("api.agent_governance_routes.MOCK_AGENTS", bad):
            response = client.get("/api/agent-governance/agents/sales-agent")
        assert response.status_code == 500

    def test_check_deployment_unknown_agent_404(self, client):
        response = client.post("/api/agent-governance/check-deployment", json={
            "agent_id": "ghost",
            "workflow_name": "w",
            "workflow_definition": {},
            "trigger_type": "manual",
            "actions": [],
            "requested_by": "u-1"})
        assert response.status_code == 404

    def test_check_deployment_exception_500(self, client):
        bad = MagicMock()
        bad.__contains__.return_value = True
        bad.__getitem__.side_effect = RuntimeError("boom")
        with patch("api.agent_governance_routes.MOCK_AGENTS", bad):
            response = client.post("/api/agent-governance/check-deployment", json={
                "agent_id": "sales-agent",
                "workflow_name": "w",
                "workflow_definition": {},
                "trigger_type": "manual",
                "actions": [],
                "requested_by": "u-1"})
        assert response.status_code == 500

    def test_feedback_unknown_agent_404(self, client):
        response = client.post("/api/agent-governance/feedback", json={
            "agent_id": "ghost", "original_output": "a", "user_correction": "b"})
        assert response.status_code == 404

    def test_feedback_exception_500(self, client):
        bad = MagicMock()
        bad.__contains__.side_effect = RuntimeError("boom")
        with patch("api.agent_governance_routes.MOCK_AGENTS", bad):
            response = client.post("/api/agent-governance/feedback", json={
                "agent_id": "sales-agent",
                "original_output": "a", "user_correction": "b"})
        assert response.status_code == 500

    def test_capabilities_unknown_agent_404(self, client):
        response = client.get(
            "/api/agent-governance/agents/ghost/capabilities")
        assert response.status_code == 404

    def test_capabilities_exception_500(self, client):
        bad = MagicMock()
        bad.__contains__.return_value = True
        bad.__getitem__.side_effect = RuntimeError("boom")
        with patch("api.agent_governance_routes.MOCK_AGENTS", bad):
            response = client.get(
                "/api/agent-governance/agents/sales-agent/capabilities")
        assert response.status_code == 500

    def test_check_deployment_intern_requires_team_lead(self, client):
        response = client.post("/api/agent-governance/check-deployment", json={
            "agent_id": "support-agent",
            "workflow_name": "w",
            "workflow_definition": {},
            "trigger_type": "manual",
            "actions": [],
            "requested_by": "u-1"})
        assert response.status_code == 200
        data = response.json()
        assert data["requires_approval"] is True
        assert data["approver_role_required"] == "team_lead"

    def test_check_deployment_student_requires_admin(self, client):
        response = client.post("/api/agent-governance/check-deployment", json={
            "agent_id": "hr-agent",
            "workflow_name": "w",
            "workflow_definition": {},
            "trigger_type": "manual",
            "actions": [],
            "requested_by": "u-1"})
        assert response.status_code == 200
        assert response.json()["approver_role_required"] == "admin"

    def test_submit_for_approval_unknown_agent_404(self, client, ws_request):
        ws_request["agent_id"] = "ghost"
        response = client.post("/api/agent-governance/submit-for-approval",
                               json=ws_request)
        assert response.status_code == 404
