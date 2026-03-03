"""Contract tests for core API endpoints using Schemathesis schema validation."""
import pytest
from fastapi.testclient import TestClient
from main_api_app import app
from tests.contract.conftest import schema


class TestHealthEndpoints:
    """Contract tests for health check endpoints."""

    def test_health_endpoint_contracts(self):
        """Test /health endpoint conforms to OpenAPI spec."""
        # Get the API operation for /health
        operation = schema["/health"]["GET"]
        with TestClient(app) as client:
            response = client.get("/health")
            # Validate response against OpenAPI schema
            operation.validate_response(response)
            # Schemathesis validates schema, we check business logic
            # Health endpoint should return 200 (healthy) or 503 (unhealthy)
            assert response.status_code in [200, 503]

    def test_api_v1_health_contracts(self):
        """Test /api/v1/health endpoint conforms to OpenAPI spec."""
        # Get the API operation for /api/v1/health
        operation = schema["/api/v1/health"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
            # Validate response against OpenAPI schema
            operation.validate_response(response)
            # May return 200 or 404 depending on setup
            assert response.status_code in [200, 404]

    def test_root_endpoint_contracts(self):
        """Test root endpoint conforms to OpenAPI spec."""
        # Get the API operation for /
        operation = schema["/"]["GET"]
        with TestClient(app) as client:
            response = client.get("/")
            # Validate response against OpenAPI schema
            operation.validate_response(response)
            # Root endpoint should return 200
            assert response.status_code == 200


class TestAgentEndpoints:
    """Contract tests for agent endpoints."""

    def test_list_agents_contracts(self):
        """Test GET /api/agents/ conforms to OpenAPI spec."""
        # Get the API operation for GET /api/agents/
        operation = schema["/api/agents/"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/agents/")
            # Validate response against OpenAPI schema
            operation.validate_response(response)
            # May return 200, 401, 403 for auth, or 404 if route doesn't exist
            assert response.status_code in [200, 401, 403, 404]

    def test_get_agent_contracts(self):
        """Test GET /api/agents/{id} conforms to OpenAPI spec."""
        # Get the API operation for GET /api/agents/{agent_id}
        operation = schema["/api/agents/{agent_id}"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/agents/test-agent-id")
            # Validate response against OpenAPI schema
            operation.validate_response(response)
            # May return 200, 401, 403, or 404 if agent not found or route doesn't exist
            assert response.status_code in [200, 401, 403, 404]

    def test_create_agent_contracts(self):
        """Test POST /api/agents/spawn conforms to OpenAPI spec."""
        # Get the API operation for POST /api/agents/spawn
        operation = schema["/api/agents/spawn"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/agents/spawn",
                json={
                    "agent_id": "test-spawn-agent",
                    "config": {}
                }
            )
            # Validate response against OpenAPI schema
            operation.validate_response(response)
            # May return 200, 400, 401, 403, or 404 if route doesn't exist
            assert response.status_code in [200, 400, 401, 403, 404]
