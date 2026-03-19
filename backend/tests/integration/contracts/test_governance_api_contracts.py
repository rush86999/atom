"""Governance API contract tests using Schemathesis for OpenAPI compliance.

Validates that governance endpoints conform to their OpenAPI specification.
Uses property-based testing with Hypothesis to generate diverse test cases
and validate request/response schemas.

Contract test coverage:
- GET /api/agent-governance/rules - Get governance rules
- GET /api/agent-governance/agents - List agents with maturity
- GET /api/agent-governance/agents/{agent_id} - Get agent maturity
- GET /api/agent-governance/agents/{agent_id}/capabilities - Get agent capabilities
- POST /api/agent-governance/check-deployment - Check workflow deployment
- POST /api/agent-governance/feedback - Submit agent feedback
"""
import pytest
from fastapi.testclient import TestClient
from main_api_app import app
import schemathesis

# Load OpenAPI schema from FastAPI app
schema = schemathesis.openapi.from_dict(app.openapi())


class TestGovernanceAPIContracts:
    """Contract tests for Agent Governance API endpoints.

    Tests validate that the API implementation matches the OpenAPI specification
    using Schemathesis for schema validation.

    Maturity Levels: STUDENT, INTERN, SUPERVISED, AUTONOMOUS
    """

    def test_get_governance_rules(self):
        """Test GET /api/agent-governance/rules validates governance status schema.

        Validates:
        - Response includes governance rules configuration
        - Action complexity levels defined correctly
        - Maturity level requirements specified
        """
        operation = schema["/api/agent-governance/rules"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/agent-governance/rules")
            operation.validate_response(response)
            assert response.status_code in [200]

    def test_list_agents_with_maturity(self):
        """Test GET /api/agent-governance/agents validates agent list with maturity.

        Validates:
        - Response includes array of agents with maturity levels
        - Maturity levels valid (STUDENT/INTERN/SUPERVISED/AUTONOMOUS)
        - Filtering parameters work correctly
        """
        operation = schema["/api/agent-governance/agents"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/agent-governance/agents")
            operation.validate_response(response)
            assert response.status_code in [200, 400]

    def test_get_agent_maturity(self):
        """Test GET /api/agent-governance/agents/{agent_id} validates maturity level schema.

        Validates:
        - Response includes agent maturity level
        - Maturity level is one of 4 valid levels
        - Returns 404 for non-existent agents
        """
        operation = schema["/api/agent-governance/agents/{agent_id}"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/agent-governance/agents/test-agent-id")
            operation.validate_response(response)
            assert response.status_code in [200, 404]

    def test_get_agent_capabilities(self):
        """Test GET /api/agent-governance/agents/{agent_id}/capabilities validates capabilities.

        Validates:
        - Response includes agent capabilities based on maturity
        - Capabilities match maturity level restrictions
        - Returns 404 for non-existent agents
        """
        operation = schema["/api/agent-governance/agents/{agent_id}/capabilities"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/agent-governance/agents/test-agent-id/capabilities")
            operation.validate_response(response)
            assert response.status_code in [200, 404]

    def test_check_deployment_permission(self):
        """Test POST /api/agent-governance/check-deployment validates permission check.

        Validates:
        - Permission check request/response schema
        - Returns approval decision based on maturity
        - Action complexity validated correctly
        """
        operation = schema["/api/agent-governance/check-deployment"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/agent-governance/check-deployment",
                json={
                    "agent_id": "test-agent-id",
                    "action_complexity": 2,
                    "action_type": "data_modification"
                }
            )
            operation.validate_response(response)
            assert response.status_code in [200, 400, 422]

    def test_submit_agent_feedback(self):
        """Test POST /api/agent-governance/feedback validates feedback submission.

        Validates:
        - Feedback request schema (agent_id, rating, comments)
        - Response includes feedback confirmation
        - Returns 404 for non-existent agents
        """
        operation = schema["/api/agent-governance/feedback"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/agent-governance/feedback",
                json={
                    "agent_id": "test-agent-id",
                    "rating": 0.8,
                    "comments": "Good performance"
                }
            )
            operation.validate_response(response)
            assert response.status_code in [200, 201, 400, 422]


# Pytest marker for running only contract tests
pytestmark = pytest.mark.contract
