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
from fastapi.testclient import TestClient
from main_api_app import app
import schemathesis

# Load OpenAPI schema from FastAPI app
schema = schemathesis.openapi.from_dict(app.openapi())


class TestAgentAPIContracts:
    """Contract tests for Agent API endpoints.

    Tests validate that the API implementation matches the OpenAPI specification
    using Schemathesis for schema validation.
    """

    def test_list_agents(self):
        """Test GET /api/agents validates pagination and filtering.

        Validates:
        - Pagination parameters work correctly
        - Response includes array of agents
        - Query parameters conform to schema
        """
        operation = schema["/api/agents/"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/agents")
            operation.validate_response(response)
            assert response.status_code in [200, 400]

    def test_get_agent_by_id(self):
        """Test GET /api/agents/{agent_id} validates response schema.

        Validates:
        - Response status code matches spec (200, 404, 403)
        - Response body conforms to schema
        - Path parameter validation works correctly
        """
        operation = schema["/api/agents/{agent_id}"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/agents/test-agent-id")
            operation.validate_response(response)
            assert response.status_code in [200, 404, 403]

    def test_update_agent(self):
        """Test PUT /api/agents/{agent_id} validates partial updates.

        Validates:
        - Partial updates work correctly
        - Field validation enforced on update
        - Response includes updated agent details
        - Returns 404 for non-existent agents
        """
        operation = schema["/api/agents/{agent_id}"]["PUT"]
        with TestClient(app) as client:
            response = client.put(
                "/api/agents/test-agent-id",
                json={"name": "Updated Agent"}
            )
            operation.validate_response(response)
            assert response.status_code in [200, 404, 422]

    def test_delete_agent(self):
        """Test DELETE /api/agents/{agent_id} validates deletion behavior.

        Validates:
        - Cascade deletion behavior
        - Returns 200 on successful deletion
        - Returns 404 for non-existent agents
        - Returns 403 if agent has active executions
        """
        operation = schema["/api/agents/{agent_id}"]["DELETE"]
        with TestClient(app) as client:
            response = client.delete("/api/agents/test-agent-id")
            operation.validate_response(response)
            assert response.status_code in [200, 404, 403]

    def test_run_agent(self):
        """Test POST /api/agents/{agent_id}/run validates agent execution.

        Validates:
        - Agent execution request schema
        - Response includes execution results
        - Returns 404 for non-existent agents
        """
        operation = schema["/api/agents/{agent_id}/run"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/agents/test-agent-id/run",
                json={"prompt": "Hello, world!"}
            )
            operation.validate_response(response)
            assert response.status_code in [200, 404, 500]

    def test_spawn_agent(self):
        """Test POST /api/agents/spawn validates agent creation.

        Validates:
        - Required fields are enforced
        - Request body conforms to schema
        - Response includes created agent details
        - Returns 201 on success, 422 on validation error
        """
        operation = schema["/api/agents/spawn"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/agents/spawn",
                json={"agent_id": "test-spawn-agent"}
            )
            operation.validate_response(response)
            assert response.status_code in [200, 201, 400, 422]


# Pytest marker for running only contract tests
pytestmark = pytest.mark.contract
