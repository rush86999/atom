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
