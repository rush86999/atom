"""Coverage-push wave 39 — api/agent_governance_routes.py.

Raises coverage of the agent governance router from ~53% to >=90% by
exercising every handler's success, validation, not-found, permission,
service-failure and internal-error paths. Standard repo harness: FastAPI
TestClient + dependency overrides (get_current_user, get_db) + service
mocks (intervention_service patched at the routes-module level). No
network, no real DB, no real LLM.

No production bug fixes were required for this wave: the
``except HTTPException: raise`` re-raise guards (previously swallowed in
the wave-30 fix round) are verified intact by the 404/403 paths asserted
below.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.agent_governance_routes import (
    can_deploy_directly,
    get_maturity_level_from_score,
    router,
)
from core.auth import get_current_user
from core.database import get_db
from core.models import UserRole


# ---------------------------------------------------------------------------
# Shared harness
# ---------------------------------------------------------------------------

USER = SimpleNamespace(id="u-1")


def _make_app(db_session=None):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: USER
    if db_session is not None:
        app.dependency_overrides[get_db] = lambda: db_session
    return app


@pytest.fixture
def client():
    """Plain client — only the auth dependency is overridden."""
    return TestClient(_make_app())


def _approval_client(user_obj):
    """Client with a mocked DB session; user_obj is what the approve
    handler's ``db.query(User).filter(...).first()`` chain returns."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = user_obj
    return TestClient(_make_app(db_session=session))


@pytest.fixture
def intervention():
    """Mock intervention_service at the routes-module level."""
    svc = MagicMock()
    svc.get_pending_interventions.return_value = [
        {"id": "act-1", "agent_id": "sales-agent", "status": "pending"}
    ]
    svc.approve_intervention = AsyncMock(return_value={"success": True})
    svc.reject_intervention = AsyncMock(return_value={"success": True})
    with patch("api.agent_governance_routes.intervention_service", svc):
        yield svc


class _ExplodingAgents(dict):
    """MOCK_AGENTS stand-in whose iteration raises (internal-error path)."""

    def items(self):
        raise RuntimeError("boom")


class _ExplodingContains(dict):
    """MOCK_AGENTS stand-in whose membership test raises (internal-error
    path for handlers that only do a containment check)."""

    def __contains__(self, key):
        raise RuntimeError("boom")


# ===========================================================================
# Helper functions
# ===========================================================================

class TestMaturityHelper:
    @pytest.mark.parametrize("score,expected", [
        (0.95, "autonomous"), (0.90, "autonomous"), (0.899, "supervised"),
        (0.70, "supervised"), (0.699, "intern"), (0.50, "intern"),
        (0.499, "student"), (0.0, "student"),
    ])
    def test_get_maturity_level_from_score(self, score, expected):
        assert get_maturity_level_from_score(score) == expected

    def test_can_deploy_autonomous_always(self):
        assert can_deploy_directly("autonomous", 0.1) is True

    def test_can_deploy_supervised_high_confidence(self):
        assert can_deploy_directly("supervised", 0.9) is True
        assert can_deploy_directly("supervised", 0.8) is True

    def test_cannot_deploy_supervised_low_confidence(self):
        assert can_deploy_directly("supervised", 0.79) is False

    def test_cannot_deploy_lower_levels(self):
        assert can_deploy_directly("intern", 0.99) is False
        assert can_deploy_directly("student", 0.99) is False


# ===========================================================================
# GET /api/agent-governance/agents  (category filter + internal error)
# ===========================================================================

class TestListAgents:
    def test_filter_by_category(self, client):
        response = client.get("/api/agent-governance/agents", params={"category": "sales"})
        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 1
        assert agents[0]["agent_id"] == "sales-agent"
        assert agents[0]["maturity_level"] == "supervised"

    def test_internal_error(self, client):
        with patch("api.agent_governance_routes.MOCK_AGENTS", _ExplodingAgents()):
            response = client.get("/api/agent-governance/agents")
        assert response.status_code == 500
        assert response.json()["detail"]["error"]["code"] == "INTERNAL_ERROR"


# ===========================================================================
# GET /api/agent-governance/agents/{agent_id}
# ===========================================================================

class TestGetAgentMaturity:
    def test_not_found_is_404(self, client):
        response = client.get("/api/agent-governance/agents/ghost-agent")
        assert response.status_code == 404

    def test_internal_error(self, client):
        with patch(
            "api.agent_governance_routes.get_maturity_level_from_score",
            side_effect=RuntimeError("boom"),
        ):
            response = client.get("/api/agent-governance/agents/finance-agent")
        assert response.status_code == 500


# ===========================================================================
# POST /api/agent-governance/check-deployment
# ===========================================================================

class TestCheckDeployment:
    def _payload(self, agent_id="engineering-agent"):
        return {
            "agent_id": agent_id,
            "workflow_name": "w",
            "workflow_definition": {"steps": ["fetch_data"]},
            "trigger_type": "manual",
            "actions": ["fetch_data"],
            "requested_by": "u-1",
        }

    def test_student_requires_admin_approval(self, client):
        response = client.post("/api/agent-governance/check-deployment", json=self._payload())
        assert response.status_code == 200
        result = response.json()
        assert result["can_deploy"] is False
        assert result["requires_approval"] is True
        assert result["status"] == "pending"
        assert result["approver_role_required"] == "admin"

    def test_intern_requires_team_lead_approval(self, client):
        response = client.post(
            "/api/agent-governance/check-deployment",
            json=self._payload(agent_id="productivity-agent"),
        )
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "pending"
        assert result["approver_role_required"] == "team_lead"

    def test_unknown_agent_404(self, client):
        response = client.post(
            "/api/agent-governance/check-deployment",
            json=self._payload(agent_id="ghost-agent"),
        )
        assert response.status_code == 404

    def test_internal_error(self, client):
        with patch(
            "api.agent_governance_routes.get_maturity_level_from_score",
            side_effect=RuntimeError("boom"),
        ):
            response = client.post("/api/agent-governance/check-deployment", json=self._payload())
        assert response.status_code == 500


# ===========================================================================
# POST /api/agent-governance/submit-for-approval
# ===========================================================================

class TestSubmitForApproval:
    def _payload(self, agent_id="finance-agent"):
        return {
            "agent_id": agent_id,
            "workflow_name": "invoice-daily",
            "workflow_definition": {"steps": ["fetch", "send_email"]},
            "trigger_type": "schedule",
            "actions": ["send_email"],
            "requested_by": "u-1",
        }

    def test_success(self, client):
        response = client.post("/api/agent-governance/submit-for-approval", json=self._payload())
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["approval_id"].startswith("apr_")
        assert data["status"] == "pending"
        assert data["agent_id"] == "finance-agent"
        assert data["maturity_level"] == "autonomous"
        assert "estimated_review_time" in data

    def test_unknown_agent_404(self, client):
        response = client.post(
            "/api/agent-governance/submit-for-approval",
            json=self._payload(agent_id="ghost-agent"),
        )
        assert response.status_code == 404

    def test_internal_error(self, client):
        with patch(
            "api.agent_governance_routes.get_maturity_level_from_score",
            side_effect=RuntimeError("boom"),
        ):
            response = client.post("/api/agent-governance/submit-for-approval", json=self._payload())
        assert response.status_code == 500


# ===========================================================================
# POST /api/agent-governance/feedback
# ===========================================================================

class TestSubmitFeedback:
    def _payload(self, agent_id="finance-agent"):
        return {
            "agent_id": agent_id,
            "original_output": "out",
            "user_correction": "fixed",
        }

    def test_unknown_agent_404(self, client):
        response = client.post(
            "/api/agent-governance/feedback",
            json=self._payload(agent_id="ghost-agent"),
        )
        assert response.status_code == 404

    def test_internal_error(self, client):
        with patch("api.agent_governance_routes.MOCK_AGENTS", _ExplodingContains()):
            response = client.post("/api/agent-governance/feedback", json=self._payload())
        assert response.status_code == 500


# ===========================================================================
# GET /api/agent-governance/pending-approvals
# ===========================================================================

class TestPendingApprovals:
    def test_no_filter(self, client, intervention):
        response = client.get("/api/agent-governance/pending-approvals")
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 1
        assert body["pending_approvals"][0]["id"] == "act-1"
        intervention.get_pending_interventions.assert_called_once_with(None)

    def test_filter_by_approver(self, client, intervention):
        response = client.get(
            "/api/agent-governance/pending-approvals",
            params={"approver_id": "u-1"},
        )
        assert response.status_code == 200
        assert response.json()["count"] == 1
        intervention.get_pending_interventions.assert_called_once_with("u-1")

    def test_internal_error(self, client, intervention):
        intervention.get_pending_interventions.side_effect = RuntimeError("boom")
        response = client.get("/api/agent-governance/pending-approvals")
        assert response.status_code == 500


# ===========================================================================
# POST /api/agent-governance/approve/{approval_id}
# ===========================================================================

class TestApproveWorkflow:
    def test_success(self, intervention):
        client = _approval_client(SimpleNamespace(role=UserRole.TEAM_LEAD.value))
        response = client.post("/api/agent-governance/approve/act-1")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "approved"
        assert body["data"]["approved_by"] == "u-1"
        intervention.approve_intervention.assert_awaited_once_with("act-1", "u-1")

    def test_super_admin_role_allowed(self, intervention):
        client = _approval_client(SimpleNamespace(role=UserRole.SUPER_ADMIN.value))
        response = client.post("/api/agent-governance/approve/act-1")
        assert response.status_code == 200

    def test_user_not_found(self, intervention):
        client = _approval_client(None)
        response = client.post("/api/agent-governance/approve/act-1")
        assert response.status_code == 404

    def test_member_role_forbidden(self, intervention):
        client = _approval_client(SimpleNamespace(role=UserRole.MEMBER.value))
        response = client.post("/api/agent-governance/approve/act-1")
        assert response.status_code == 403

    def test_service_failure(self, intervention):
        client = _approval_client(SimpleNamespace(role=UserRole.TEAM_LEAD.value))
        intervention.approve_intervention.return_value = {"success": False, "message": "nope"}
        response = client.post("/api/agent-governance/approve/act-1")
        assert response.status_code == 400
        assert response.json()["detail"]["error"]["code"] == "APPROVAL_FAILED"

    def test_internal_error(self, intervention):
        client = _approval_client(SimpleNamespace(role=UserRole.TEAM_LEAD.value))
        intervention.approve_intervention.side_effect = RuntimeError("boom")
        response = client.post("/api/agent-governance/approve/act-1")
        assert response.status_code == 500


# ===========================================================================
# POST /api/agent-governance/reject/{approval_id}
# ===========================================================================

class TestRejectWorkflow:
    def test_success(self, intervention):
        client = _approval_client(SimpleNamespace(role=UserRole.TEAM_LEAD.value))
        response = client.post("/api/agent-governance/reject/act-1", params={"reason": "too risky"})
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["status"] == "rejected"
        assert body["data"]["rejected_by"] == "u-1"
        assert body["data"]["reason"] == "too risky"
        intervention.reject_intervention.assert_awaited_once_with("act-1", "u-1", "too risky")

    def test_missing_reason_422(self, intervention):
        client = _approval_client(SimpleNamespace(role=UserRole.TEAM_LEAD.value))
        response = client.post("/api/agent-governance/reject/act-1")
        assert response.status_code == 422

    def test_service_failure(self, intervention):
        client = _approval_client(SimpleNamespace(role=UserRole.TEAM_LEAD.value))
        intervention.reject_intervention.return_value = {"success": False, "message": "nope"}
        response = client.post("/api/agent-governance/reject/act-1", params={"reason": "n/a"})
        assert response.status_code == 400
        assert response.json()["detail"]["error"]["code"] == "REJECTION_FAILED"

    def test_internal_error(self, intervention):
        client = _approval_client(SimpleNamespace(role=UserRole.TEAM_LEAD.value))
        intervention.reject_intervention.side_effect = RuntimeError("boom")
        response = client.post("/api/agent-governance/reject/act-1", params={"reason": "n/a"})
        assert response.status_code == 500


# ===========================================================================
# GET /api/agent-governance/agents/{agent_id}/capabilities
# ===========================================================================

class TestAgentCapabilities:
    def test_unknown_agent_404(self, client):
        response = client.get("/api/agent-governance/agents/ghost-agent/capabilities")
        assert response.status_code == 404

    def test_internal_error(self, client):
        with patch(
            "api.agent_governance_routes.get_maturity_level_from_score",
            side_effect=RuntimeError("boom"),
        ):
            response = client.get("/api/agent-governance/agents/finance-agent/capabilities")
        assert response.status_code == 500


# ===========================================================================
# POST /api/agent-governance/enforce-action
# ===========================================================================

class TestEnforceAction:
    def _payload(self, agent_id, action_type):
        return {"agent_id": agent_id, "action_type": action_type}

    def test_unknown_agent_blocked(self, client):
        response = client.post(
            "/api/agent-governance/enforce-action",
            json=self._payload("ghost-agent", "delete"),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["proceed"] is False
        assert body["status"] == "BLOCKED"
        assert body["action_required"] == "HUMAN_APPROVAL"

    def test_student_blocked_on_critical_action(self, client):
        response = client.post(
            "/api/agent-governance/enforce-action",
            json=self._payload("engineering-agent", "delete"),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "BLOCKED"
        assert body["required_status"] == "autonomous"
        assert body["action_complexity"] == 4

    def test_supervised_high_complexity_needs_approval(self, client):
        response = client.post(
            "/api/agent-governance/enforce-action",
            json=self._payload("data-agent", "create"),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["proceed"] is True
        assert body["status"] == "PENDING_APPROVAL"
        assert body["action_required"] == "WAIT_FOR_APPROVAL"

    def test_low_complexity_approved(self, client):
        response = client.post(
            "/api/agent-governance/enforce-action",
            json=self._payload("sales-agent", "search"),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "APPROVED"
        assert body["proceed"] is True
        assert body["action_required"] is None

    def test_substring_action_match_uses_specific_complexity(self, client):
        response = client.post(
            "/api/agent-governance/enforce-action",
            json=self._payload("sales-agent", "send_email_digest"),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "PENDING_APPROVAL"

    def test_unknown_action_defaults_medium_complexity(self, client):
        response = client.post(
            "/api/agent-governance/enforce-action",
            json=self._payload("engineering-agent", "custom_proprietary_op"),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "BLOCKED"
        assert body["action_complexity"] == 2
        assert body["required_status"] == "intern"

    def test_internal_error(self, client):
        with patch(
            "api.agent_governance_routes.get_maturity_level_from_score",
            side_effect=RuntimeError("boom"),
        ):
            response = client.post(
                "/api/agent-governance/enforce-action",
                json=self._payload("sales-agent", "search"),
            )
        assert response.status_code == 500


# ===========================================================================
# POST /api/agent-governance/generate-workflow
# ===========================================================================

class TestGenerateWorkflow:
    def test_success_direct_deploy(self, client):
        response = client.post(
            "/api/agent-governance/generate-workflow",
            params={"description": "generate a weekly sales digest", "agent_id": "sales-agent"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["workflow"]["name"].startswith("Auto:")
        assert data["agent"]["id"] == "sales-agent"
        assert data["can_deploy_directly"] is True
        assert data["requires_approval"] is False

    def test_success_requires_approval(self, client):
        response = client.post(
            "/api/agent-governance/generate-workflow",
            params={"description": "deploy infra", "agent_id": "engineering-agent"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["can_deploy_directly"] is False
        assert data["requires_approval"] is True

    def test_unknown_agent_404(self, client):
        response = client.post(
            "/api/agent-governance/generate-workflow",
            params={"description": "x", "agent_id": "ghost-agent"},
        )
        assert response.status_code == 404

    def test_missing_params_422(self, client):
        response = client.post("/api/agent-governance/generate-workflow")
        assert response.status_code == 422

    def test_internal_error(self, client):
        with patch(
            "api.agent_governance_routes.get_maturity_level_from_score",
            side_effect=RuntimeError("boom"),
        ):
            response = client.post(
                "/api/agent-governance/generate-workflow",
                params={"description": "x", "agent_id": "sales-agent"},
            )
        assert response.status_code == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
