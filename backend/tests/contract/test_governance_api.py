"""Contract tests for governance API endpoints using Schemathesis schema validation."""
import pytest
from fastapi.testclient import TestClient
from main_api_app import app
from tests.contract.conftest import schema


class TestGovernanceEndpoints:
    """Contract tests for agent governance endpoints."""

    def test_list_governance_agents_contracts(self):
        """Test GET /api/agent-governance/agents conforms to OpenAPI spec."""
        operation = schema["/api/agent-governance/agents"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/agent-governance/agents")
            operation.validate_response(response)
            # Schemathesis validates schema
            assert response.status_code in [200, 401, 403, 404]

    def test_governance_check_deployment_contracts(self):
        """Test POST /api/agent-governance/check-deployment conforms to OpenAPI spec."""
        operation = schema["/api/agent-governance/check-deployment"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/agent-governance/check-deployment",
                json={
                    "agent_id": "test-agent",
                    "workflow_name": "Test Workflow",
                    "actions": ["present_canvas"]
                }
            )
            operation.validate_response(response)
            assert response.status_code in [200, 400, 401, 422]

    def test_governance_enforce_action_contracts(self):
        """Test POST /api/agent-governance/enforce-action conforms to OpenAPI spec."""
        operation = schema["/api/agent-governance/enforce-action"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/agent-governance/enforce-action",
                json={
                    "agent_id": "test-agent",
                    "action_type": "present_canvas",
                    "context": {}
                }
            )
            operation.validate_response(response)
            assert response.status_code in [200, 400, 401, 422]


class TestApprovalEndpoints:
    """Contract tests for approval workflow endpoints."""

    def test_pending_approvals_contracts(self):
        """Test GET /api/agent-governance/pending-approvals conforms to OpenAPI spec."""
        operation = schema["/api/agent-governance/pending-approvals"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/agent-governance/pending-approvals")
            operation.validate_response(response)
            assert response.status_code in [200, 401, 403, 404]

    def test_submit_for_approval_contracts(self):
        """Test POST /api/agent-governance/submit-for-approval conforms to OpenAPI spec."""
        operation = schema["/api/agent-governance/submit-for-approval"]["POST"]
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
            operation.validate_response(response)
            assert response.status_code in [200, 201, 400, 401, 422, 500]

    def test_approve_workflow_contracts(self):
        """Test POST /api/agent-governance/approve/{approval_id} conforms to OpenAPI spec."""
        operation = schema["/api/agent-governance/approve/{approval_id}"]["POST"]
        with TestClient(app) as client:
            response = client.post("/api/agent-governance/approve/test-approval-id")
            operation.validate_response(response)
            assert response.status_code in [200, 401, 404, 422]

    def test_reject_workflow_contracts(self):
        """Test POST /api/agent-governance/reject/{approval_id} conforms to OpenAPI spec."""
        operation = schema["/api/agent-governance/reject/{approval_id}"]["POST"]
        with TestClient(app) as client:
            response = client.post("/api/agent-governance/reject/test-approval-id")
            operation.validate_response(response)
            assert response.status_code in [200, 401, 404, 422]


class TestFeedbackEndpoints:
    """Contract tests for agent feedback endpoints."""

    def test_submit_feedback_contracts(self):
        """Test POST /api/agent-governance/feedback conforms to OpenAPI spec."""
        operation = schema["/api/agent-governance/feedback"]["POST"]
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
            operation.validate_response(response)
            assert response.status_code in [200, 400, 401, 422, 500]


class TestGovernanceRulesEndpoints:
    """Contract tests for governance rules endpoints."""

    def test_governance_rules_contracts(self):
        """Test GET /api/agent-governance/rules conforms to OpenAPI spec."""
        operation = schema["/api/agent-governance/rules"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/agent-governance/rules")
            operation.validate_response(response)
            assert response.status_code in [200, 401, 403, 404]
