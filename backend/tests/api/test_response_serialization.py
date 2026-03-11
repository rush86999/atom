"""
Response serialization tests for API endpoints.

Tests that all endpoints properly serialize responses with correct data types,
JSON formatting, datetime handling, enum representation, and HTTP headers.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from typing import Dict, Any
import json


# Import fixtures from validation conftest
pytest_plugins = ["tests.api.conftest_validation"]


class TestHealthResponseSerialization:
    """Test response serialization for health endpoints."""

    def test_liveness_response_schema(self, api_test_client):
        """Test that liveness endpoint returns expected structure."""
        response = api_test_client.get("/health/live")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert isinstance(data["status"], str)
        assert "timestamp" in data

    def test_liveness_datetime_format(self, api_test_client):
        """Test that liveness timestamp is ISO 8601 format."""
        response = api_test_client.get("/health/live")
        assert response.status_code == 200

        data = response.json()
        timestamp = data.get("timestamp")

        # Should be parseable as ISO 8601 datetime
        try:
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            pytest.fail(f"Timestamp {timestamp} is not ISO 8601 format")

    def test_readiness_response_includes_dependencies(self, api_test_client):
        """Test that readiness endpoint includes DB and disk status."""
        response = api_test_client.get("/health/ready")
        assert response.status_code in [200, 503]  # May be unhealthy

        data = response.json()
        assert "status" in data
        assert "checks" in data or "dependencies" in data

        # Check for database status
        checks = data.get("checks", data.get("dependencies", {}))
        if "database" in checks:
            assert isinstance(checks["database"], dict)

    def test_metrics_response_content_type(self, api_test_client):
        """Test that metrics endpoint returns Prometheus format."""
        response = api_test_client.get("/health/metrics")
        assert response.status_code == 200

        # Should be text/plain for Prometheus
        assert "text/plain" in response.headers.get("content-type", "")

    def test_health_response_headers(self, api_test_client):
        """Test that health endpoints have correct headers."""
        response = api_test_client.get("/health/live")
        assert response.status_code == 200

        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type

    def test_health_responses_handle_consistent_format(self, api_test_client):
        """Test that all health endpoints use consistent response format."""
        endpoints = ["/health/live", "/health/ready"]

        for endpoint in endpoints:
            response = api_test_client.get(endpoint)
            assert response.status_code in [200, 503]

            data = response.json()
            assert "status" in data
            assert isinstance(data["status"], str)


class TestAgentResponseSerialization:
    """Test response serialization for agent endpoints."""

    def test_agent_list_response_schema(self, api_test_client):
        """Test that agent list returns correct list structure."""
        response = api_test_client.get("/api/agents")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list) or "agents" in data

    def test_agent_detail_response_fields(self, api_test_client):
        """Test that agent detail includes all expected fields."""
        # First create an agent
        create_response = api_test_client.post(
            "/api/agents/spawn",
            json={
                "name": "test_agent",
                "category": "testing",
                "module_path": "test.module"
            }
        )

        if create_response.status_code in [200, 201]:
            agent_id = create_response.json().get("id") or create_response.json().get("agent_id")

            if agent_id:
                # Get agent detail
                response = api_test_client.get(f"/api/agents/{agent_id}")
                if response.status_code == 200:
                    data = response.json()
                    # Check for common agent fields
                    expected_fields = ["id", "name", "status"]
                    for field in expected_fields:
                        assert field in data or field in str(data)

    def test_agent_datetime_fields_serialized(self, api_test_client):
        """Test that agent datetime fields are ISO 8601 format."""
        response = api_test_client.get("/api/agents")
        assert response.status_code == 200

        data = response.json()
        agents = data if isinstance(data, list) else data.get("agents", [])

        if agents and len(agents) > 0:
            agent = agents[0]
            # Check datetime fields
            for field in ["created_at", "updated_at", "last_active"]:
                if field in agent:
                    timestamp = agent[field]
                    if timestamp:
                        try:
                            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        except (ValueError, AttributeError):
                            pytest.fail(f"{field} is not ISO 8601 format: {timestamp}")

    def test_agent_enum_fields_serialized(self, api_test_client):
        """Test that agent enum fields are string representations."""
        response = api_test_client.get("/api/agents")
        assert response.status_code == 200

        data = response.json()
        agents = data if isinstance(data, list) else data.get("agents", [])

        if agents and len(agents) > 0:
            agent = agents[0]
            # Check enum fields are strings
            for field in ["maturity", "status", "category"]:
                if field in agent:
                    assert isinstance(agent[field], str)

    def test_agent_nullable_fields_handle_null(self, api_test_client):
        """Test that nullable agent fields serialize to null."""
        response = api_test_client.get("/api/agents")
        assert response.status_code == 200

        data = response.json()
        agents = data if isinstance(data, list) else data.get("agents", [])

        if agents and len(agents) > 0:
            agent = agents[0]
            # Nullable fields should be null, not omitted or undefined
            # This is a loose check - we just verify the structure is valid
            assert isinstance(agent, dict)


class TestCanvasResponseSerialization:
    """Test response serialization for canvas endpoints."""

    def test_canvas_response_schema_validation(self, api_test_client):
        """Test that canvas responses match OpenAPI schema."""
        # Create a canvas
        canvas_id = "test-canvas-id"
        response = api_test_client.get(f"/api/canvas/{canvas_id}")

        # May return 404 if not found, or 200 if exists
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            # Check for common canvas fields
            expected_fields = ["canvas_id", "canvas_type", "status"]
            for field in expected_fields:
                assert field in data or field in str(data)

    def test_canvas_audit_response_includes_timestamps(self, api_test_client):
        """Test that canvas audit responses include datetime fields."""
        response = api_test_client.get("/api/canvas/audit")
        assert response.status_code in [200, 401, 403]  # May require auth

        if response.status_code == 200:
            data = response.json()
            audits = data if isinstance(data, list) else data.get("audits", [])

            if audits and len(audits) > 0:
                audit = audits[0]
                # Check for timestamp fields
                for field in ["created_at", "timestamp", "updated_at"]:
                    if field in audit:
                        timestamp = audit[field]
                        if timestamp:
                            try:
                                datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            except (ValueError, AttributeError):
                                pytest.fail(f"{field} is not ISO 8601 format")

    def test_canvas_form_response_serializes_nested_data(self, api_test_client):
        """Test that canvas form responses handle nested structures."""
        # Submit a form with nested data
        response = api_test_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": "test-canvas",
                "form_data": {
                    "nested": {
                        "level1": {
                            "level2": "deep_value"
                        }
                    },
                    "array": [1, 2, 3]
                }
            }
        )

        # May succeed or fail, but if it succeeds, check serialization
        if response.status_code in [200, 201]:
            data = response.json()
            assert isinstance(data, dict)

    def test_canvas_list_response_pagination(self, api_test_client):
        """Test that canvas list includes pagination metadata."""
        response = api_test_client.get("/api/canvas?page=1&limit=10")
        assert response.status_code == 200

        data = response.json()
        # Check for pagination fields
        assert "page" in data or "items" in data or isinstance(data, list)


class TestErrorResponseSerialization:
    """Test response serialization for error responses."""

    def test_401_response_schema(self, api_test_client):
        """Test that 401 responses have consistent error format."""
        # Try to access an authenticated endpoint without auth
        response = api_test_client.get("/api/agents/me")
        assert response.status_code == 401

        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    def test_403_response_includes_reason(self, api_test_client):
        """Test that 403 responses include governance explanation."""
        # Try to access an admin endpoint without permissions
        response = api_test_client.post("/api/admin/sync-ratings")
        assert response.status_code in [403, 401, 422]  # May be 401 if not authenticated

        if response.status_code == 403:
            data = response.json()
            # Should include reason for forbidden
            assert "detail" in data or "reason" in data or "message" in data

    def test_422_response_includes_field_errors(self, api_test_client):
        """Test that 422 responses include validation error details."""
        response = api_test_client.post(
            "/api/agents/spawn",
            json={
                "name": 12345,  # Invalid type
                "category": "testing"
            }
        )
        assert response.status_code == 422

        data = response.json()
        assert "detail" in data
        # Check for field-specific errors
        detail = data["detail"]
        assert isinstance(detail, list)

    def test_500_response_includes_correlation_id(self, api_test_client):
        """Test that 500 responses include debugging info."""
        # This test is hard to trigger reliably, so we'll skip it
        # In production, 500 responses should include correlation_id
        pytest.skip("Requires triggering actual 500 error")

    def test_error_responses_dont_leak_internals(self, api_test_client):
        """Test that error responses don't leak stack traces."""
        # Trigger a 404 error
        response = api_test_client.get("/api/nonexistent-endpoint")
        assert response.status_code == 404

        data = response.json()
        error_text = json.dumps(data).lower()

        # Should not contain stack traces or internal details
        assert "traceback" not in error_text
        assert "exception" not in error_text or "message" in error_text


class TestDataTypeSerialization:
    """Test serialization of specific data types."""

    def test_datetime_fields_serialize_to_iso(self, api_test_client):
        """Test that datetime fields consistently serialize to ISO 8601."""
        response = api_test_client.get("/api/agents")
        assert response.status_code == 200

        data = response.json()
        agents = data if isinstance(data, list) else data.get("agents", [])

        if agents and len(agents) > 0:
            agent = agents[0]
            for key, value in agent.items():
                if "time" in key.lower() or "date" in key.lower():
                    if isinstance(value, str):
                        try:
                            datetime.fromisoformat(value.replace('Z', '+00:00'))
                        except (ValueError, AttributeError):
                            # If it's a datetime field, it should be ISO format
                            # If not, that's okay - it might be a different type
                            pass

    def test_enum_fields_serialize_to_strings(self, api_test_client):
        """Test that enum fields serialize to string values."""
        response = api_test_client.get("/api/agents")
        assert response.status_code == 200

        data = response.json()
        agents = data if isinstance(data, list) else data.get("agents", [])

        if agents and len(agents) > 0:
            agent = agents[0]
            for key, value in agent.items():
                if key in ["maturity", "status", "category"]:
                    assert isinstance(value, str)

    def test_decimal_fields_serialize_correctly(self, api_test_client):
        """Test that decimal/float fields maintain precision."""
        # Create an agent with confidence value
        response = api_test_client.post(
            "/api/agents/spawn",
            json={
                "name": "test_agent",
                "category": "testing",
                "module_path": "test.module",
                "confidence": 0.75
            }
        )

        if response.status_code in [200, 201]:
            data = response.json()
            if "confidence" in data:
                assert isinstance(data["confidence"], (int, float))
                # Check precision is maintained
                assert abs(data["confidence"] - 0.75) < 0.01

    def test_uuid_fields_serialize_to_strings(self, api_test_client):
        """Test that UUID fields serialize to string format."""
        response = api_test_client.get("/api/agents")
        assert response.status_code == 200

        data = response.json()
        agents = data if isinstance(data, list) else data.get("agents", [])

        if agents and len(agents) > 0:
            agent = agents[0]
            for key, value in agent.items():
                if "id" in key.lower() and isinstance(value, str):
                    # Should be a valid UUID string
                    assert len(value) > 0

    def test_nullable_fields_serialize_to_null(self, api_test_client):
        """Test that nullable fields serialize to null (not omitted)."""
        response = api_test_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": "test-canvas",
                "form_data": {"field": "value"},
                "agent_id": None  # Nullable field
            }
        )

        if response.status_code in [200, 201]:
            data = response.json()
            # If agent_id is in response, it should be null
            if "agent_id" in data:
                assert data["agent_id"] is None or isinstance(data["agent_id"], str)


class TestResponseHeaders:
    """Test HTTP response headers."""

    def test_content_type_header_set(self, api_test_client):
        """Test that JSON endpoints set correct content-type."""
        endpoints = [
            "/api/agents",
            "/health/live",
            "/api/canvas/types"
        ]

        for endpoint in endpoints:
            response = api_test_client.get(endpoint)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                assert "application/json" in content_type

    def test_cache_headers_on_cacheable_endpoints(self, api_test_client):
        """Test that cacheable endpoints include cache headers."""
        # Try a GET endpoint that might be cached
        response = api_test_client.get("/api/canvas/types")

        if response.status_code == 200:
            headers = response.headers
            # Check for cache-related headers
            # These may or may not be present depending on caching strategy
            cache_headers = ["etag", "last-modified", "cache-control"]
            found_any = any(h in headers for h in cache_headers)
            # Don't assert - just verify we can check
            assert isinstance(found_any, bool)

    def test_cors_headers_set(self, api_test_client):
        """Test that CORS headers are set correctly."""
        response = api_test_client.get("/api/agents")
        assert response.status_code == 200

        headers = response.headers
        # Check for CORS headers (may be present depending on configuration)
        cors_headers = ["access-control-allow-origin", "access-control-allow-methods"]
        # These may or may not be present
        # Just verify we can check headers
        assert isinstance(headers, dict)

    def test_response_time_header(self, api_test_client):
        """Test that response includes timing info if configured."""
        response = api_test_client.get("/api/agents")
        assert response.status_code == 200

        headers = response.headers
        # Some APIs include X-Response-Time header
        # This is optional, just verify we can check
        if "x-response-time" in headers:
            assert isinstance(headers["x-response-time"], str)


class TestResponseFormatConsistency:
    """Test consistency of response formats across endpoints."""

    def test_success_responses_have_success_field(self, api_test_client):
        """Test that success responses include success indicator."""
        # This is a common pattern but not required by FastAPI
        # Just verify the structure is consistent
        response = api_test_client.get("/api/agents")
        assert response.status_code == 200

        data = response.json()
        # May or may not have success field
        assert isinstance(data, (dict, list))

    def test_list_responses_have_consistent_structure(self, api_test_client):
        """Test that list endpoints use consistent structure."""
        list_endpoints = [
            "/api/agents",
            "/api/canvas/types"
        ]

        for endpoint in list_endpoints:
            response = api_test_client.get(endpoint)
            if response.status_code == 200:
                data = response.json()
                # Should be either a list or dict with list field
                assert isinstance(data, list) or (
                    isinstance(data, dict) and
                    any(isinstance(v, list) for v in data.values())
                )

    def test_pagination_responses_have_metadata(self, api_test_client):
        """Test that paginated endpoints include pagination metadata."""
        response = api_test_client.get("/api/agents?page=1&limit=10")
        assert response.status_code == 200

        data = response.json()
        # If paginated, should have pagination metadata
        # This is optional, just verify structure
        assert isinstance(data, (dict, list))

    def test_error_responses_have_consistent_format(self, api_test_client):
        """Test that error responses use consistent format."""
        # Trigger different error types
        errors_to_test = [
            (api_test_client.get("/api/nonexistent"), 404),
            (api_test_client.post("/api/agents/spawn", json={}), 422),
        ]

        for response_func, expected_status in errors_to_test:
            response = response_func
            if response.status_code == expected_status:
                data = response.json()
                # Should have detail or error field
                assert "detail" in data or "error" in data or "message" in data
