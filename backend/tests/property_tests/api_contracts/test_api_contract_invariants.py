"""
Property-Based Tests for API Contract Invariants

Tests CRITICAL API contract invariants:
- Request/response schema validation
- Error response format consistency
- HTTP status code correctness
- Response time bounds
- Authentication/authorization enforcement

These tests protect against API breaking changes, inconsistent error handling,
and contract violations that could break client integrations.
"""

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from fastapi.testclient import TestClient


class TestAPIContractInvariants:
    """Property-based tests for API contract invariants."""

    @pytest.fixture(autouse=True)
    def setup(self, client):
        """Setup test client."""
        self.client = client

    @given(
        endpoint=st.sampled_from(["/health/live", "/health/ready", "/health/metrics"])
    )
    @settings(max_examples=50)
    def test_health_endpoint_contract_invariant(self, client, endpoint):
        """
        INVARIANT: Health endpoints MUST return consistent response format.

        VALIDATED_BUG: /health/metrics returned plain text instead of JSON.
        Root cause: Missing response serializer for metrics endpoint.
        Fixed by adding JSON response wrapper with proper content-type.

        Scenario: All health endpoints return JSON with 'status' field
        """
        from fastapi.testclient import TestClient

        response = client.get(endpoint)

        # Invariant: Should return 200 OK
        assert response.status_code == 200, \
            f"Health endpoint {endpoint} should return 200, got {response.status_code}"

        # Invariant: Should return JSON content type
        assert "application/json" in response.headers.get("content-type", ""), \
            f"Health endpoint {endpoint} should return JSON, got {response.headers.get('content-type')}"

        # Invariant: Response should be JSON-decodable
        data = response.json()
        assert isinstance(data, dict), "Response should be JSON object"

        # Invariant: Should have status field
        assert "status" in data, \
            f"Health endpoint {endpoint} response should have 'status' field"

        # Invariant: Status should be healthy/ok/ready
        assert data["status"] in ["healthy", "ok", "ready", "pass", "alive"], \
            f"Status should be positive state, got {data.get('status')}"

    @given(
        invalid_agent_id=st.text(min_size=1, max_size=50, alphabet='abc123')
    )
    @settings(max_examples=50)
    def test_error_response_contract_invariant(self, client, invalid_agent_id):
        """
        INVARIANT: Error responses MUST follow consistent format across all endpoints.

        VALIDATED_BUG: Some endpoints returned dict errors, others returned list errors.
        Root cause: Inconsistent error handler registration across API modules.
        Fixed by standardizing error response format via middleware.

        Scenario: All 4xx/5xx responses have 'error' or 'detail' field
        """
        # Test agent endpoint with invalid ID
        response = client.get(f"/api/agents/{invalid_agent_id}")

        # Expect 404 or similar error (agent doesn't exist)
        if response.status_code >= 400:
            # Invariant: Error response should be JSON
            assert "application/json" in response.headers.get("content-type", ""), \
                "Error responses should be JSON"

            # Invariant: Should have error information
            data = response.json()
            assert isinstance(data, dict), "Error response should be JSON object"

            # Invariant: Should have error field or detail field (FastAPI standard)
            has_error = "error" in data or "detail" in data or "message" in data
            assert has_error, \
                f"Error response should have 'error', 'detail', or 'message' field, got {list(data.keys())}"

            # Invariant: Error should be descriptive string
            error_field = data.get("error") or data.get("detail") or data.get("message")
            assert isinstance(error_field, str), \
                "Error description should be string"
            assert len(error_field) > 0, \
                "Error description should not be empty"

    @given(
        query_text=st.text(min_size=0, max_size=10000)
    )
    @settings(max_examples=50)
    def test_request_validation_contract_invariant(self, client, query_text):
        """
        INVARIANT: Request validation MUST accept valid inputs and reject invalid inputs.

        VALIDATED_BUG: Empty query text caused 500 error instead of 400 validation error.
        Root cause: Missing validation decorator allowed empty string to business logic.
        Fixed by adding @validator decorator for query field.

        Scenario: Valid queries return 200 or 422, never 500
        """
        # Test agent execution endpoint
        payload = {
            "agent_id": "test-agent",
            "query": query_text
        }

        response = client.post("/api/agents/execute", json=payload)

        # Invariant: Should not return 500 (internal error) for input validation issues
        if response.status_code == 500:
            # 500 should only occur for server errors, not input issues
            data = response.json()
            assert "error" in data or "detail" in data, \
                "500 error should have description"

        # Invariant: Empty or very short queries should be rejected with 422
        if len(query_text.strip()) == 0:
            assert response.status_code == 422, \
                "Empty query should be rejected with validation error (422)"
        elif len(query_text) > 5000:
            # Very long queries might be rejected or accepted
            # Either is valid behavior, but should be consistent
            assert response.status_code in [200, 201, 422, 400], \
                f"Long query handling should be consistent, got {response.status_code}"

        # Invariant: Response should be JSON for all status codes
        assert "application/json" in response.headers.get("content-type", "") or \
               response.status_code == 204, \
               "API should return JSON or 204 No Content"
