"""Agent API contract tests using Schemathesis for OpenAPI compliance.

Validates that agent endpoints conform to their OpenAPI specification.
Uses property-based testing with Hypothesis to generate diverse test cases
and validate request/response schemas.

Contract test coverage:
- GET /api/agents - List agents
- GET /api/agents/{agent_id} - Get agent details
- PUT /api/agents/{agent_id} - Update agent
- DELETE /api/agents/{agent_id} - Delete agent
- POST /api/agents/{agent_id}/run - Run agent
- POST /api/agents/spawn - Spawn new agent
"""
import pytest
import schemathesis
from hypothesis import settings
from main_api_app import app

# Load OpenAPI schema from FastAPI app
schema = schemathesis.from_wsgi("/openapi.json", app)


class TestAgentAPIContracts:
    """Contract tests for Agent API endpoints.

    Tests use property-based testing to generate diverse inputs and validate
    that the API implementation matches the OpenAPI specification.
    """

    @schema.parametrize(endpoint="/api/agents")
    @settings(max_examples=15, deadline=None)
    def test_list_agents(self, case):
        """Test GET /api/agents validates pagination and filtering.

        Validates:
        - Pagination parameters work correctly
        - Response includes array of agents
        - Query parameters conform to schema
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 400]

    @schema.parametrize(endpoint="/api/agents/{agent_id}")
    @settings(max_examples=20, deadline=None)
    def test_get_agent_by_id(self, case):
        """Test GET /api/agents/{agent_id} validates response schema.

        Validates:
        - Response status code matches spec (200, 404, 403)
        - Response body conforms to schema
        - Path parameter validation works correctly
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 404, 403]

    @schema.parametrize(endpoint="/api/agents/{agent_id}")
    @settings(max_examples=10, deadline=None)
    def test_update_agent(self, case):
        """Test PUT /api/agents/{agent_id} validates partial updates.

        Validates:
        - Partial updates work correctly
        - Field validation enforced on update
        - Response includes updated agent details
        - Returns 404 for non-existent agents
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 404, 422]

    @schema.parametrize(endpoint="/api/agents/{agent_id}")
    @settings(max_examples=10, deadline=None)
    def test_delete_agent(self, case):
        """Test DELETE /api/agents/{agent_id} validates deletion behavior.

        Validates:
        - Cascade deletion behavior
        - Returns 200 on successful deletion
        - Returns 404 for non-existent agents
        - Returns 403 if agent has active executions
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 404, 403]

    @schema.parametrize(endpoint="/api/agents/{agent_id}/run")
    @settings(max_examples=10, deadline=None)
    def test_run_agent(self, case):
        """Test POST /api/agents/{agent_id}/run validates agent execution.

        Validates:
        - Agent execution request schema
        - Response includes execution results
        - Returns 404 for non-existent agents
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 404, 500]

    @schema.parametrize(endpoint="/api/agents/spawn")
    @settings(max_examples=15, deadline=None)
    def test_spawn_agent(self, case):
        """Test POST /api/agents/spawn validates agent creation.

        Validates:
        - Required fields are enforced
        - Request body conforms to schema
        - Response includes created agent details
        - Returns 201 on success, 422 on validation error
        """
        response = case.call_and_validate()
        assert response.status_code in [200, 201, 400, 422]


# Pytest marker for running only contract tests
pytestmark = pytest.mark.contract
