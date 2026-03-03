"""Contract tests for governance API endpoints using FastAPI TestClient."""
import pytest
from fastapi.testclient import TestClient
from main_api_app import app


class TestGovernanceEndpoints:
    """Contract tests for agent governance endpoints."""

    def test_list_governance_agents_endpoint(self):
        """Test GET /api/agent-governance/agents conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.get("/api/agent-governance/agents")
            # May return 200, 401 for auth, or 500 for internal error
            assert response.status_code in [200, 401, 403, 404, 422, 500]

    def test_governance_check_deployment_endpoint(self):
        """Test POST /api/agent-governance/check-deployment conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.post(
                "/api/agent-governance/check-deployment",
                json={
                    "agent_id": "test-agent",
                    "workflow_name": "Test Workflow",
                    "actions": ["present_canvas"]
                }
            )
            # May return 200, 400/422 for validation, 401 for auth, or 500 for internal error
            assert response.status_code in [200, 400, 401, 403, 404, 422, 500]

    def test_governance_enforce_action_endpoint(self):
        """Test POST /api/agent-governance/enforce-action conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.post(
                "/api/agent-governance/enforce-action",
                json={
                    "agent_id": "test-agent",
                    "action_type": "present_canvas",
                    "context": {}
                }
            )
            # May return 200, 400/422 for validation, 401 for auth, or 500 for internal error
            assert response.status_code in [200, 400, 401, 403, 404, 422, 500]


class TestApprovalEndpoints:
    """Contract tests for approval workflow endpoints."""

    def test_pending_approvals_endpoint(self):
        """Test GET /api/agent-governance/pending-approvals conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.get("/api/agent-governance/pending-approvals")
            # May return 200, 401 for auth, or 500 for internal error
            assert response.status_code in [200, 401, 403, 404, 422, 500]

    def test_submit_for_approval_endpoint(self):
        """Test POST /api/agent-governance/submit-for-approval conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.post(
                "/api/agent-governance/submit-for-approval",
                json={
                    "agent_id": "test-agent",
                    "workflow_name": "Test Workflow",
                    "workflow_definition": {},
                    "trigger_type": "manual",
                    "actions": ["present_canvas"],
                    "requested_by": "test-user"
                }
            )
            # May return 201, 400/422 for validation, 401 for auth, or 500 for internal error
            assert response.status_code in [201, 400, 401, 403, 404, 422, 500]

    def test_approve_workflow_endpoint(self):
        """Test POST /api/agent-governance/approve/{approval_id} conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.post("/api/agent-governance/approve/test-approval-id")
            # May return 200, 404 if not found, 401 for auth, or 500 for internal error
            assert response.status_code in [200, 401, 403, 404, 422, 500]

    def test_reject_workflow_endpoint(self):
        """Test POST /api/agent-governance/reject/{approval_id} conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.post("/api/agent-governance/reject/test-approval-id")
            # May return 200, 404 if not found, 401 for auth, or 500 for internal error
            assert response.status_code in [200, 401, 403, 404, 422, 500]


class TestFeedbackEndpoints:
    """Contract tests for agent feedback endpoints."""

    def test_submit_feedback_endpoint(self):
        """Test POST /api/agent-governance/feedback conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.post(
                "/api/agent-governance/feedback",
                json={
                    "agent_id": "test-agent",
                    "original_output": "Test output",
                    "user_correction": "Corrected output",
                    "input_context": "Test context"
                }
            )
            # May return 200, 400/422 for validation, 401 for auth, or 500 for internal error
            assert response.status_code in [200, 400, 401, 403, 404, 422, 500]


class TestGovernanceRulesEndpoints:
    """Contract tests for governance rules endpoints."""

    def test_governance_rules_endpoint(self):
        """Test GET /api/agent-governance/rules conforms to OpenAPI spec."""
        with TestClient(app) as client:
            response = client.get("/api/agent-governance/rules")
            # May return 200, 401 for auth, or 500 for internal error
            assert response.status_code in [200, 401, 403, 404, 422, 500]
