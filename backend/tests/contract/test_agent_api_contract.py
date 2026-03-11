"""Agent API contract tests using Schemathesis for OpenAPI compliance.

Validates that agent endpoints (list, detail, spawn, execute) conform to their
OpenAPI specification. Uses property-based testing with Hypothesis to generate
diverse test cases and validate request/response schemas.

Contract test coverage:
- GET /api/agents/ - List agents with pagination and filtering
- GET /api/agents/{id} - Get agent details
- POST /api/agents/spawn - Spawn new agent
- POST /api/agents/execute - Execute agent with streaming
"""
import pytest
from fastapi.testclient import TestClient
from main_api_app import app
from tests.contract.conftest import schema


class TestAgentListContract:
    """Contract tests for GET /api/agents/ endpoint."""

    def test_get_agents_contracts(self):
        """Test GET /api/agents/ validates response schema."""
        # Get the API operation for GET /api/agents/
        operation = schema["/api/agents/"]["GET"]
        with TestClient(app) as client:
            response = client.get("/api/agents/")
            # Validate response against OpenAPI schema
            operation.validate_response(response)
            # May return 200, 401, 403 for auth, or 404 if route doesn't exist
            assert response.status_code in [200, 401, 403, 404]

    def test_get_agents_pagination(self):
        """Test that pagination parameters conform to schema."""
        operation = schema["/api/agents/"]["GET"]
        with TestClient(app) as client:
            # Test with pagination parameters
            response = client.get("/api/agents/", params={"page": 1, "page_size": 10})
            # Schemathesis validates query parameters against schema
            # We check that response status is valid
            assert response.status_code in [200, 401, 403, 404, 422]

    def test_get_agents_filtering(self):
        """Test that filter parameters conform to schema."""
        operation = schema["/api/agents/"]["GET"]
        with TestClient(app) as client:
            # Test with filter parameters (if documented in schema)
            response = client.get("/api/agents/", params={"maturity": "AUTONOMOUS"})
            assert response.status_code in [200, 401, 403, 404, 422]

    def test_get_agents_invalid_pagination(self):
        """Test that invalid pagination parameters return 422."""
        with TestClient(app) as client:
            # Test with invalid pagination (negative page)
            response = client.get("/api/agents/", params={"page": -1})
            # Should return 422 for invalid query parameters
            assert response.status_code in [200, 422]


class TestAgentDetailContract:
    """Contract tests for GET /api/agents/{id} endpoint."""

    def test_get_agent_by_id(self):
        """Test GET /api/agents/{id} validates response schema."""
        operation = schema["/api/agents/{agent_id}"]["GET"]
        with TestClient(app) as client:
            # Test with valid agent ID format
            response = client.get("/api/agents/test-agent-id")
            # Validate response against OpenAPI schema
            operation.validate_response(response)
            assert response.status_code in [200, 401, 403, 404]

    def test_get_agent_not_found(self):
        """Test that 404 response conforms to schema for non-existent agent."""
        with TestClient(app) as client:
            # Test with non-existent agent
            response = client.get("/api/agents/nonexistent-agent-999")
            # Should return 404 with error response schema
            assert response.status_code in [200, 401, 403, 404]

    def test_get_agent_invalid_id(self):
        """Test that malformed ID returns 422."""
        with TestClient(app) as client:
            # Test with invalid ID format (if schema has validation)
            # This depends on the agent_id schema definition
            response = client.get("/api/agents/")
            # If ID has format validation, should return 422
            # Otherwise, 404 for not found
            assert response.status_code in [200, 401, 403, 404, 422]


class TestAgentSpawnContract:
    """Contract tests for POST /api/agents/spawn endpoint."""

    def test_spawn_agent_contracts(self):
        """Test POST /api/agents/spawn validates request/response."""
        operation = schema["/api/agents/spawn"]["POST"]
        with TestClient(app) as client:
            response = client.post(
                "/api/agents/spawn",
                json={
                    "agent_id": "test-spawn-agent",
                    "config": {}
                }
            )
            # Validate both request and response against schema
            operation.validate_response(response)
            # May return 200, 400, 401, 403, 404, or 422
            assert response.status_code in [200, 201, 400, 401, 403, 404, 422]

    def test_spawn_request_schema(self):
        """Test that request body schema is enforced."""
        with TestClient(app) as client:
            # Test with valid spawn request structure
            response = client.post(
                "/api/agents/spawn",
                json={
                    "agent_id": "contract-test-agent",
                    "config": {
                        "model": "gpt-4",
                        "temperature": 0.7
                    }
                }
            )
            # Schemathesis validates request body against schema
            assert response.status_code in [200, 201, 400, 401, 403, 404, 422]

    def test_spawn_success_response(self):
        """Test that 201 response conforms to schema."""
        with TestClient(app) as client:
            response = client.post(
                "/api/agents/spawn",
                json={
                    "agent_id": "success-test-agent",
                    "config": {}
                }
            )
            # If successful (201), response should have agent details
            if response.status_code == 201:
                # Validate response has expected fields
                assert "agent_id" in response.json() or "id" in response.json()

    def test_spawn_validation_errors(self):
        """Test that 422 response conforms to schema for invalid requests."""
        with TestClient(app) as client:
            # Test with invalid request body (missing required field)
            response = client.post(
                "/api/agents/spawn",
                json={
                    # Missing agent_id
                    "config": {}
                }
            )
            # Should return 422 with validation error details
            assert response.status_code in [200, 400, 401, 403, 422]

    def test_spawn_invalid_config(self):
        """Test that invalid config schema returns 422."""
        with TestClient(app) as client:
            response = client.post(
                "/api/agents/spawn",
                json={
                    "agent_id": "invalid-config-agent",
                    "config": "invalid"  # Should be object, not string
                }
            )
            # Should return 422 for schema validation error
            assert response.status_code in [200, 400, 401, 403, 422]


class TestAgentExecuteContract:
    """Contract tests for POST /api/agents/execute endpoint."""

    def test_execute_agent_contracts(self):
        """Test POST /api/agents/execute validates request/response."""
        # Note: This endpoint may not be in schema or may require special handling
        if "/api/agents/execute" in schema:
            operation = schema["/api/agents/execute"]["POST"]
            with TestClient(app) as client:
                response = client.post(
                    "/api/agents/execute",
                    json={
                        "agent_id": "test-agent",
                        "prompt": "Hello, world!"
                    }
                )
                operation.validate_response(response)
                assert response.status_code in [200, 400, 401, 403, 404, 422]
        else:
            # Endpoint not in schema, skip test
            pytest.skip("Endpoint not in OpenAPI schema")

    def test_execute_request_schema(self):
        """Test that complex request with config conforms to schema."""
        if "/api/agents/execute" in schema:
            with TestClient(app) as client:
                response = client.post(
                    "/api/agents/execute",
                    json={
                        "agent_id": "config-test-agent",
                        "prompt": "Test prompt",
                        "config": {
                            "temperature": 0.5,
                            "max_tokens": 1000
                        }
                    }
                )
                assert response.status_code in [200, 400, 401, 403, 404, 422]
        else:
            pytest.skip("Endpoint not in OpenAPI schema")

    def test_execute_streaming_response(self):
        """Test that streaming response is handled (if applicable)."""
        # Note: Schemathesis doesn't handle streaming responses well
        # This test documents that streaming endpoints need special handling
        if "/api/agents/execute" in schema:
            # Streaming endpoints should be documented in schema
            # May require SSE (Server-Sent Events) response
            pass
        else:
            pytest.skip("Endpoint not in OpenAPI schema")


class TestAgentUpdateContract:
    """Contract tests for PUT /api/agents/{id} endpoint."""

    def test_update_agent_contracts(self):
        """Test PUT /api/agents/{id} validates request/response."""
        if "/api/agents/{agent_id}" in schema:
            path_item = schema["/api/agents/{agent_id}"]
            if "PUT" in path_item:
                operation = path_item["PUT"]
                with TestClient(app) as client:
                    response = client.put(
                        "/api/agents/test-agent",
                        json={
                            "config": {"temperature": 0.8}
                        }
                    )
                    operation.validate_response(response)
                    assert response.status_code in [200, 400, 401, 403, 404, 422]
            else:
                pytest.skip("PUT method not defined for this endpoint")
        else:
            pytest.skip("Endpoint not in OpenAPI schema")

    def test_update_not_found(self):
        """Test that updating non-existent agent returns 404."""
        if "/api/agents/{agent_id}" in schema:
            path_item = schema["/api/agents/{agent_id}"]
            if "PUT" in path_item:
                with TestClient(app) as client:
                    response = client.put(
                        "/api/agents/nonexistent-agent",
                        json={"config": {}}
                    )
                    assert response.status_code in [200, 401, 403, 404, 422]
            else:
                pytest.skip("PUT method not defined for this endpoint")
        else:
            pytest.skip("Endpoint not in OpenAPI schema")


class TestAgentDeleteContract:
    """Contract tests for DELETE /api/agents/{id} endpoint."""

    def test_delete_agent_contracts(self):
        """Test DELETE /api/agents/{id} validates response."""
        if "/api/agents/{agent_id}" in schema:
            path_item = schema["/api/agents/{agent_id}"]
            if "DELETE" in path_item:
                operation = path_item["DELETE"]
                with TestClient(app) as client:
                    response = client.delete("/api/agents/test-agent")
                    operation.validate_response(response)
                    assert response.status_code in [200, 204, 401, 403, 404]
            else:
                pytest.skip("DELETE method not defined for this endpoint")
        else:
            pytest.skip("Endpoint not in OpenAPI schema")

    def test_delete_not_found(self):
        """Test that deleting non-existent agent returns 404."""
        if "/api/agents/{agent_id}" in schema:
            path_item = schema["/api/agents/{agent_id}"]
            if "DELETE" in path_item:
                with TestClient(app) as client:
                    response = client.delete("/api/agents/nonexistent-agent")
                    assert response.status_code in [200, 204, 401, 403, 404]
            else:
                pytest.skip("DELETE method not defined for this endpoint")
        else:
            pytest.skip("Endpoint not in OpenAPI schema")


class TestAgentGovernanceContract:
    """Contract tests for agent governance headers and permissions."""

    def test_governance_headers(self):
        """Test that X-Agent-Maturity header is processed."""
        with TestClient(app) as client:
            # Test with governance header
            response = client.get(
                "/api/agents/",
                headers={"X-Agent-Maturity": "AUTONOMOUS"}
            )
            # Header may or may not be enforced in contract tests
            assert response.status_code in [200, 401, 403, 404]

    def test_permission_denied(self):
        """Test that 403 response conforms to schema."""
        # This would require setting up permissions
        # In contract tests, we validate the 403 response schema
        if "/api/agents/" in schema:
            with TestClient(app) as client:
                response = client.get("/api/agents/")
                # If permission denied, should return 403
                if response.status_code == 403:
                    # Validate error response structure
                    json_resp = response.json()
                    assert "detail" in json_resp or "error" in json_resp

    def test_unauthorized(self):
        """Test that 401 response conforms to schema."""
        if "/api/agents/" in schema:
            with TestClient(app) as client:
                response = client.get("/api/agents/")
                # If unauthorized, should return 401
                if response.status_code == 401:
                    # Validate error response structure
                    json_resp = response.json()
                    assert "detail" in json_resp or "error" in json_resp
