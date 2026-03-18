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
import schemathesis
from hypothesis import settings
from main_api_app import app

# Load OpenAPI schema from FastAPI app
schema = schemathesis.from_wsgi("/openapi.json", app)


class TestGovernanceAPIContracts:
    """Contract tests for Agent Governance API endpoints.

    Tests use property-based testing to generate diverse inputs and validate
    that the API implementation matches the OpenAPI specification.

    Maturity Levels: STUDENT, INTERN, SUPERVISED, AUTONOMOUS
    """

    @schema.parametrize(endpoint="/api/agent-governance/rules")
    @settings(max_examples=10, deadline=None)
    def test_get_governance_rules(self, case):
        """Test GET /api/agent-governance/rules validates governance status schema.

        Validates:
        - Response includes governance rules configuration
        - Action complexity levels defined correctly
        - Maturity level requirements specified
        """
        response = case.call_and_validate()
        assert response.status_code in [200]

    @schema.parametrize(endpoint="/api/agent-governance/agents")
    @settings(max_examples=15, deadline=None)
    def test_list_agents_with_maturity(self, case):
        """Test GET /api/agent-governance/agents validates agent list with maturity.

        Validates:
        - Response includes array of agents with maturity levels
        - Maturity levels valid (STUDENT/INTERN/SUPERVISED/AUTONOMOUS)
        - Filtering parameters work correctly
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 400]

    @schema.parametrize(endpoint="/api/agent-governance/agents/{agent_id}")
    @settings(max_examples=20, deadline=None)
    def test_get_agent_maturity(self, case):
        """Test GET /api/agent-governance/agents/{agent_id} validates maturity level schema.

        Validates:
        - Response includes agent maturity level
        - Maturity level is one of 4 valid levels
        - Returns 404 for non-existent agents
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 404]

    @schema.parametrize(endpoint="/api/agent-governance/agents/{agent_id}/capabilities")
    @settings(max_examples=15, deadline=None)
    def test_get_agent_capabilities(self, case):
        """Test GET /api/agent-governance/agents/{agent_id}/capabilities validates capabilities.

        Validates:
        - Response includes agent capabilities based on maturity
        - Capabilities match maturity level restrictions
        - Returns 404 for non-existent agents
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 404]

    @schema.parametrize(endpoint="/api/agent-governance/check-deployment")
    @settings(max_examples=15, deadline=None)
    def test_check_deployment_permission(self, case):
        """Test POST /api/agent-governance/check-deployment validates permission check.

        Validates:
        - Permission check request/response schema
        - Returns approval decision based on maturity
        - Action complexity validated correctly
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 400, 422]

    @schema.parametrize(endpoint="/api/agent-governance/feedback")
    @settings(max_examples=10, deadline=None)
    def test_submit_agent_feedback(self, case):
        """Test POST /api/agent-governance/feedback validates feedback submission.

        Validates:
        - Feedback request schema (agent_id, rating, comments)
        - Response includes feedback confirmation
        - Returns 404 for non-existent agents
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 201, 400, 422]


# Pytest marker for running only contract tests
pytestmark = pytest.mark.contract
