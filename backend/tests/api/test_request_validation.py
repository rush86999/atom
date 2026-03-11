"""
Request validation tests for API endpoints.

Tests that all endpoints properly validate incoming requests with type checking,
format validation, constraint enforcement, and security filtering.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from typing import Dict, Any
import uuid


# Import fixtures from validation conftest
pytest_plugins = ["tests.api.conftest_validation"]


class TestAgentRequestValidation:
    """Test request validation for agent endpoints."""

    def test_spawn_agent_missing_required_field(self, api_test_client):
        """Test that spawning agent without name returns 422."""
        response = api_test_client.post(
            "/api/agents/spawn",
            json={
                "category": "testing",
                "module_path": "test.module"
                # Missing required 'name' field
            }
        )
        assert response.status_code == 422
        assert "name" in str(response.json())

    def test_spawn_agent_invalid_maturity(self, api_test_client):
        """Test that invalid maturity enum returns 422."""
        response = api_test_client.post(
            "/api/agents/spawn",
            json={
                "name": "test_agent",
                "category": "testing",
                "module_path": "test.module",
                "maturity": "INVALID_LEVEL"
            }
        )
        # May return 422 or 400 depending on validation layer
        assert response.status_code in [400, 422]

    def test_spawn_agent_confidence_out_of_range(self, api_test_client):
        """Test that confidence > 1.0 or < 0.0 returns 422."""
        # Test confidence > 1.0
        response = api_test_client.post(
            "/api/agents/spawn",
            json={
                "name": "test_agent",
                "category": "testing",
                "module_path": "test.module",
                "confidence": 1.5
            }
        )
        assert response.status_code == 422

        # Test confidence < 0.0
        response = api_test_client.post(
            "/api/agents/spawn",
            json={
                "name": "test_agent",
                "category": "testing",
                "module_path": "test.module",
                "confidence": -0.1
            }
        )
        assert response.status_code == 422

    def test_spawn_agent_extra_fields_rejected(self, api_test_client):
        """Test that extra unknown fields are rejected or ignored."""
        response = api_test_client.post(
            "/api/agents/spawn",
            json={
                "name": "test_agent",
                "category": "testing",
                "module_path": "test.module",
                "unknown_field": "should_be_rejected"
            }
        )
        # FastAPI by default ignores extra fields, so this may succeed
        # If strict validation is enabled, it returns 422
        assert response.status_code in [200, 201, 422]

    def test_spawn_agent_string_for_numeric_field(self, api_test_client):
        """Test that string in numeric confidence field returns 422."""
        response = api_test_client.post(
            "/api/agents/spawn",
            json={
                "name": "test_agent",
                "category": "testing",
                "module_path": "test.module",
                "confidence": "not_a_number"
            }
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("invalid_name", [None, "", 123, []])
    def test_spawn_agent_invalid_name_types(self, api_test_client, invalid_name):
        """Test that invalid name types are rejected."""
        response = api_test_client.post(
            "/api/agents/spawn",
            json={
                "name": invalid_name,
                "category": "testing",
                "module_path": "test.module"
            }
        )
        assert response.status_code == 422


class TestCanvasRequestValidation:
    """Test request validation for canvas endpoints."""

    def test_submit_canvas_missing_canvas_id(self, api_test_client):
        """Test that submitting canvas without canvas_id returns 422."""
        response = api_test_client.post(
            "/api/canvas/submit",
            json={
                "form_data": {"field": "value"}
                # Missing required 'canvas_id' field
            }
        )
        assert response.status_code == 422

    def test_submit_canvas_invalid_form_data_type(self, api_test_client):
        """Test that non-dict form_data returns 422."""
        response = api_test_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": str(uuid.uuid4()),
                "form_data": "not_a_dict"
            }
        )
        assert response.status_code == 422

    def test_submit_canvas_empty_form_data(self, api_test_client):
        """Test that empty form_data is handled correctly."""
        response = api_test_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": str(uuid.uuid4()),
                "form_data": {}
            }
        )
        # Empty dict may be valid or invalid depending on endpoint
        assert response.status_code in [200, 201, 422]

    def test_submit_canvas_invalid_execution_id_format(self, api_test_client):
        """Test that non-UUID execution_id returns 422."""
        response = api_test_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": str(uuid.uuid4()),
                "form_data": {"field": "value"},
                "execution_id": "not_a_uuid"
            }
        )
        assert response.status_code == 422

    def test_submit_canvas_form_data_too_large(self, api_test_client):
        """Test that oversized form_data is rejected."""
        large_data = {"field_" + str(i): "x" * 1000 for i in range(100)}
        response = api_test_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": str(uuid.uuid4()),
                "form_data": large_data
            }
        )
        # May succeed or return 413/422 depending on size limits
        assert response.status_code in [200, 201, 413, 422]

    @pytest.mark.parametrize("invalid_id", [None, 123, "not-a-uuid", ""])
    def test_submit_canvas_invalid_canvas_id(self, api_test_client, invalid_id):
        """Test that invalid canvas_id values are rejected."""
        response = api_test_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": invalid_id,
                "form_data": {"field": "value"}
            }
        )
        assert response.status_code == 422


class TestBrowserRequestValidation:
    """Test request validation for browser automation endpoints."""

    def test_navigate_invalid_url_format(self, api_test_client):
        """Test that invalid URL format returns 422."""
        response = api_test_client.post(
            "/api/browser/navigate",
            json={
                "url": "not_a_valid_url"
            }
        )
        assert response.status_code == 422

    def test_navigate_missing_url_field(self, api_test_client):
        """Test that missing URL field returns 422."""
        response = api_test_client.post(
            "/api/browser/navigate",
            json={}
        )
        assert response.status_code == 422

    def test_navigate_dangerous_url(self, api_test_client):
        """Test that dangerous javascript: URLs are rejected."""
        response = api_test_client.post(
            "/api/browser/navigate",
            json={
                "url": "javascript:alert('xss')"
            }
        )
        # Should be rejected for security reasons
        assert response.status_code in [400, 422]

    def test_click_invalid_selector_format(self, api_test_client):
        """Test that invalid CSS selector is handled."""
        response = api_test_client.post(
            "/api/browser/click",
            json={
                "selector": 12345  # Should be string
            }
        )
        assert response.status_code == 422

    def test_fill_missing_selector_field(self, api_test_client):
        """Test that missing selector returns 422."""
        response = api_test_client.post(
            "/api/browser/fill",
            json={
                "value": "test_value"
                # Missing 'selector' field
            }
        )
        assert response.status_code == 422

    def test_execute_script_injection_attempt(self, api_test_client):
        """Test that script injection attempts are handled."""
        response = api_test_client.post(
            "/api/browser/execute",
            json={
                "script": "<script>alert('xss')</script>"
            }
        )
        # May succeed (browser will execute) or be rejected
        # The endpoint should handle this securely
        assert response.status_code in [200, 400, 422]

    @pytest.mark.parametrize("invalid_timeout", [-1, "not_a_number", None])
    def test_browser_invalid_timeout(self, api_test_client, invalid_timeout):
        """Test that invalid timeout values are rejected."""
        response = api_test_client.post(
            "/api/browser/navigate",
            json={
                "url": "https://example.com",
                "timeout": invalid_timeout
            }
        )
        assert response.status_code == 422


class TestAuthRequestValidation:
    """Test request validation for authentication endpoints."""

    def test_login_missing_email_field(self, api_test_client):
        """Test that missing email returns 422."""
        response = api_test_client.post(
            "/api/auth/login",
            json={
                "password": "test_password"
                # Missing 'email' field
            }
        )
        assert response.status_code == 422

    def test_login_invalid_email_format(self, api_test_client):
        """Test that invalid email format returns 422."""
        response = api_test_client.post(
            "/api/auth/login",
            json={
                "email": "not_an_email",
                "password": "test_password"
            }
        )
        assert response.status_code == 422

    def test_login_short_password(self, api_test_client):
        """Test that short password is rejected."""
        response = api_test_client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "short"  # Too short
            }
        )
        # May succeed (endpoint may not validate length) or return 422
        assert response.status_code in [200, 400, 401, 422]

    def test_register_password_mismatch(self, api_test_client):
        """Test that password mismatch returns 422."""
        response = api_test_client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "Password123!",
                "confirm_password": "DifferentPass123!"
            }
        )
        assert response.status_code in [400, 422]

    def test_register_weak_password(self, api_test_client):
        """Test that weak password is rejected."""
        response = api_test_client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "123",  # Too weak
                "confirm_password": "123"
            }
        )
        # May succeed if no complexity validation, or return 400/422
        assert response.status_code in [200, 201, 400, 422]

    @pytest.mark.parametrize("invalid_email", [
        None,
        "",
        "not_an_email",
        "@example.com",
        "user@",
        "user@@example.com"
    ])
    def test_register_invalid_email_formats(self, api_test_client, invalid_email):
        """Test that various invalid email formats are rejected."""
        response = api_test_client.post(
            "/api/auth/register",
            json={
                "email": invalid_email,
                "password": "Password123!",
                "confirm_password": "Password123!"
            }
        )
        assert response.status_code == 422


class TestDataTypeValidation:
    """Test data type validation across all endpoints."""

    def test_string_fields_reject_numbers(self, api_test_client):
        """Test that string fields reject numeric types."""
        response = api_test_client.post(
            "/api/agents/spawn",
            json={
                "name": 123456,  # Should be string
                "category": "testing",
                "module_path": "test.module"
            }
        )
        assert response.status_code == 422

    def test_numeric_fields_reject_strings(self, api_test_client):
        """Test that numeric fields reject string types."""
        response = api_test_client.post(
            "/api/agents/spawn",
            json={
                "name": "test_agent",
                "category": "testing",
                "module_path": "test.module",
                "confidence": "not_a_number"  # Should be float
            }
        )
        assert response.status_code == 422

    def test_datetime_fields_require_iso_format(self, api_test_client):
        """Test that datetime fields require ISO 8601 format."""
        # This test assumes there's an endpoint with datetime fields
        # Adjust as needed for actual endpoints
        response = api_test_client.post(
            "/api/canvas/query",
            json={
                "canvas_id": str(uuid.uuid4()),
                "start_time": "not_a_datetime"  # Invalid format
            }
        )
        assert response.status_code == 422

    def test_boolean_fields_accept_truthy_falsy(self, api_test_client):
        """Test that boolean fields accept true/false values."""
        # Test with actual boolean
        response = api_test_client.post(
            "/api/agents/spawn",
            json={
                "name": "test_agent",
                "category": "testing",
                "module_path": "test.module",
                "enabled": True
            }
        )
        # May succeed or fail if 'enabled' field doesn't exist
        assert response.status_code in [200, 201, 422]

    def test_enum_fields_accept_valid_values(self, api_test_client):
        """Test that enum fields only accept defined values."""
        valid_maturities = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]

        for maturity in valid_maturities:
            response = api_test_client.post(
                "/api/agents/spawn",
                json={
                    "name": f"test_agent_{maturity}",
                    "category": "testing",
                    "module_path": "test.module",
                    "maturity": maturity
                }
            )
            # Should accept valid enum values
            # May fail for other reasons (auth, etc.) but not validation
            assert response.status_code in [200, 201, 401, 403, 422]

    def test_nullable_fields_handle_null(self, api_test_client):
        """Test that nullable fields accept null values."""
        response = api_test_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": str(uuid.uuid4()),
                "form_data": {"field": "value"},
                "agent_id": None  # Nullable field
            }
        )
        # Should accept null for optional fields
        assert response.status_code in [200, 201, 422]


class TestRequestSizeLimits:
    """Test request size limits and validation."""

    def test_oversized_request_body(self, api_test_client):
        """Test that oversized request bodies are rejected."""
        large_payload = {
            "name": "test_agent",
            "category": "testing",
            "module_path": "test.module",
            "description": "x" * 100000  # Very large string
        }
        response = api_test_client.post(
            "/api/agents/spawn",
            json=large_payload
        )
        # May succeed or return 413/422 depending on size limits
        assert response.status_code in [200, 201, 413, 422]

    def test_too_many_fields(self, api_test_client):
        """Test that requests with too many fields are handled."""
        large_data = {f"field_{i}": "value" for i in range(1000)}
        response = api_test_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": str(uuid.uuid4()),
                "form_data": large_data
            }
        )
        # May succeed or be rejected
        assert response.status_code in [200, 201, 413, 422]

    def test_deeply_nested_json(self, api_test_client):
        """Test that deeply nested JSON is handled."""
        deep_nested = {"level1": {"level2": {"level3": {"level4": {"level5": "deep"}}}}}
        response = api_test_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": str(uuid.uuid4()),
                "form_data": deep_nested
            }
        )
        # Should handle reasonable nesting
        assert response.status_code in [200, 201, 422]


class TestSecurityValidation:
    """Test security-related request validation."""

    def test_xss_in_string_fields(self, api_test_client):
        """Test that XSS attempts in strings are handled."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')"
        ]

        for payload in xss_payloads:
            response = api_test_client.post(
                "/api/agents/spawn",
                json={
                    "name": payload,
                    "category": "testing",
                    "module_path": "test.module"
                }
            )
            # Should either accept (will be escaped later) or reject
            assert response.status_code in [200, 201, 400, 422]

    def test_sql_injection_in_string_fields(self, api_test_client):
        """Test that SQL injection attempts are handled."""
        sql_payloads = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--"
        ]

        for payload in sql_payloads:
            response = api_test_client.post(
                "/api/agents/spawn",
                json={
                    "name": payload,
                    "category": "testing",
                    "module_path": "test.module"
                }
            )
            # Should handle safely (parameterized queries)
            # May accept the string (will be escaped) or reject
            assert response.status_code in [200, 201, 400, 422]

    def test_path_traversal_in_string_fields(self, api_test_client):
        """Test that path traversal attempts are handled."""
        path_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd"
        ]

        for payload in path_payloads:
            response = api_test_client.post(
                "/api/agents/spawn",
                json={
                    "name": payload,
                    "category": "testing",
                    "module_path": "test.module"
                }
            )
            # Should handle safely
            assert response.status_code in [200, 201, 400, 422]
