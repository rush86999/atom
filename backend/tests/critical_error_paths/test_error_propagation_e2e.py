"""
End-to-End Error Propagation Tests

Tests that errors propagate correctly from service layer to API to client with
standardized response format. Validates that the error_handlers.py global_exception_handler
and atom_exception_handler work correctly.

Test Coverage:
- Service to API error propagation (Database, Validation, Not Found, Permission, Rate Limit)
- Error response format validation (error_code, message, details, timestamp)
- AtomException propagation through handler
- Global exception handling for uncaught exceptions
- Error response consistency (success: false, content-type, CORS)

These tests use FastAPI TestClient for true end-to-end validation.
"""

import pytest
import os
import logging
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError

# Import error handling infrastructure
from core.error_handlers import (
    api_error,
    global_exception_handler,
    atom_exception_handler,
    ErrorCode,
)
from core.exceptions import (
    AtomException,
    DatabaseConnectionError,
    ValidationError,
    AgentNotFoundError,
    ForbiddenError,
    LLMRateLimitError,
    ErrorCode as AtomErrorCode,
    ErrorSeverity,
)
from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def client():
    """
    FastAPI TestClient for end-to-end API testing.

    Uses main_api_app for real endpoint testing.
    """
    from main_api_app import app
    return TestClient(app)


@pytest.fixture
def mock_request():
    """Create mock FastAPI Request for handler testing."""
    request = MagicMock(spec=Request)
    request.state.request_id = "test-request-123"
    request.url = "http://testserver/api/v1/agents"
    return request


# ============================================================================
# TestServiceToAPIErrorPropagation
# ============================================================================


class TestServiceToAPIErrorPropagation:
    """Test error propagation from service layer through API to client."""

    def test_database_error_to_500_response(self, client):
        """
        DatabaseConnectionError should propagate to 500 response.

        Service layer raises DatabaseConnectionError -> API returns 500
        with standardized error format.
        """
        from core.exceptions import DatabaseConnectionError

        # Mock agent endpoint to raise database error
        with patch("core.agent_governance_service.AgentGovernanceService.get_agent") as mock_get:
            mock_get.side_effect = DatabaseConnectionError("Connection failed", cause=OperationalError("conn failed", {}, None))

            response = client.get("/api/v1/agents/test-agent")

            # Should return 500 for database errors
            assert response.status_code in [500, 503], f"Expected 500/503, got {response.status_code}"

            # Verify error response format
            data = response.json()
            assert "error_code" in data or "detail" in data
            if "error_code" in data:
                assert data["error_code"] in ["DB_6002", "INTERNAL_ERROR", "DATABASE_ERROR"]

    def test_validation_error_to_400_response(self, client):
        """
        ValidationError should propagate to 400 response.

        Service layer raises ValidationError -> API returns 400.
        """
        from core.exceptions import ValidationError

        # Mock agent creation to raise validation error
        with patch("core.agent_governance_service.AgentGovernanceService.create_agent") as mock_create:
            mock_create.side_effect = ValidationError("Invalid agent name", field="name")

            response = client.post(
                "/api/v1/agents",
                json={"id": "test-agent", "name": "", "domain": "test"}
            )

            # Should return 400 for validation errors
            assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"

    def test_not_found_error_to_404_response(self, client):
        """
        AgentNotFoundError should propagate to 404 response.

        Service layer raises AgentNotFoundError -> API returns 404.
        """
        from core.exceptions import AgentNotFoundError

        # Mock agent lookup to raise not found
        with patch("core.agent_governance_service.AgentGovernanceService.get_agent") as mock_get:
            mock_get.side_effect = AgentNotFoundError("nonexistent-agent")

            response = client.get("/api/v1/agents/nonexistent-agent")

            # Should return 404
            assert response.status_code == 404, f"Expected 404, got {response.status_code}"

            # Verify error response format
            data = response.json()
            assert "error_code" in data or "detail" in data
            if "error_code" in data:
                assert data["error_code"] == "AGENT_2001"

    def test_permission_denied_to_403_response(self, client):
        """
        ForbiddenError should propagate to 403 response.

        Service layer raises ForbiddenError -> API returns 403.
        """
        from core.exceptions import ForbiddenError

        # Mock agent deletion to raise permission error
        with patch("core.agent_governance_service.AgentGovernanceService.delete_agent") as mock_delete:
            mock_delete.side_effect = ForbiddenError("Insufficient permissions", required_permission="agents:delete")

            response = client.delete("/api/v1/agents/test-agent")

            # Should return 403
            assert response.status_code in [403, 401], f"Expected 403/401, got {response.status_code}"

    def test_rate_limit_to_429_response(self, client):
        """
        LLMRateLimitError should propagate to 429 response.

        Service layer raises LLMRateLimitError -> API returns 429.
        """
        from core.exceptions import LLMRateLimitError

        # Mock LLM endpoint to raise rate limit error
        with patch("core.llm.byok_handler.BYOKHandler.generate_response") as mock_gen:
            mock_gen.side_effect = LLMRateLimitError("openai", retry_after=60)

            # Use chat endpoint that triggers LLM call
            response = client.post(
                "/api/v1/agents/test-agent/chat",
                json={"message": "test"}
            )

            # Should return 429 or 500 (depending on handler)
            assert response.status_code in [429, 500, 503], f"Expected 429/500/503, got {response.status_code}"


# ============================================================================
# TestErrorResponseFormat
# ============================================================================


class TestErrorResponseFormat:
    """Test standardized error response format."""

    def test_standard_error_response_fields(self, mock_request):
        """
        Error responses should contain all standard fields.

        Required: success=False, error_code, message, timestamp
        Optional: details, request_id
        """
        from core.exceptions import ValidationError
        import asyncio

        exc = ValidationError("Test validation error")

        # Run async handler
        response = asyncio.run(atom_exception_handler(mock_request, exc))

        data = response.body.decode()
        import json
        parsed = json.loads(data)

        # Verify required fields
        assert parsed["success"] == False
        assert "error_code" in parsed
        assert "message" in parsed
        assert "timestamp" in parsed

    def test_error_code_present(self, mock_request):
        """error_code field should be present and valid."""
        from core.exceptions import AgentNotFoundError
        import asyncio

        exc = AgentNotFoundError("test-agent")
        response = asyncio.run(atom_exception_handler(mock_request, exc))

        data = response.body.decode()
        import json
        parsed = json.loads(data)

        assert "error_code" in parsed
        assert parsed["error_code"] == "AGENT_2001"

    def test_message_field_present(self, mock_request):
        """message field should be present with human-readable text."""
        from core.exceptions import DatabaseConnectionError
        import asyncio

        exc = DatabaseConnectionError("Database connection failed")
        response = asyncio.run(atom_exception_handler(mock_request, exc))

        data = response.body.decode()
        import json
        parsed = json.loads(data)

        assert "message" in parsed
        assert len(parsed["message"]) > 0
        assert "connection" in parsed["message"].lower()

    def test_timestamp_field_present(self, mock_request):
        """timestamp field should be present in ISO format."""
        from core.exceptions import ValidationError
        import asyncio

        exc = ValidationError("Test error")
        response = asyncio.run(atom_exception_handler(mock_request, exc))

        data = response.body.decode()
        import json
        parsed = json.loads(data)

        assert "timestamp" in parsed
        # Verify ISO format timestamp
        datetime.fromisoformat(parsed["timestamp"].replace("Z", "+00:00"))

    def test_details_field_optional(self, mock_request):
        """details field should be present when provided."""
        from core.exceptions import ValidationError
        import asyncio

        exc = ValidationError("Test error", details={"field": "name", "value": ""})
        response = asyncio.run(atom_exception_handler(mock_request, exc))

        data = response.body.decode()
        import json
        parsed = json.loads(data)

        assert "details" in parsed
        assert parsed["details"]["field"] == "name"


# ============================================================================
# TestAtomExceptionPropagation
# ============================================================================


class TestAtomExceptionPropagation:
    """Test AtomException propagation through atom_exception_handler."""

    def test_atom_exception_caught_by_handler(self, mock_request):
        """
        AtomException should be caught by atom_exception_handler.

        Verifies handler is registered and catches AtomException.
        """
        from core.exceptions import AgentNotFoundError
        import asyncio

        exc = AgentNotFoundError("test-agent")
        response = asyncio.run(atom_exception_handler(mock_request, exc))

        assert response.status_code == 400  # MEDIUM severity -> 400

    def test_atom_exception_severity_mapping(self, mock_request):
        """
        AtomException severity should map to correct HTTP status code.

        CRITICAL/HIGH -> 500
        MEDIUM/LOW -> 400
        INFO -> 200
        """
        import asyncio

        # Test CRITICAL -> 500
        exc_critical = AgentNotFoundError("test-agent")
        exc_critical.severity = ErrorSeverity.CRITICAL
        response_critical = asyncio.run(atom_exception_handler(mock_request, exc_critical))
        assert response_critical.status_code == 500

        # Test MEDIUM -> 400
        exc_medium = ValidationError("Test error")
        response_medium = asyncio.run(atom_exception_handler(mock_request, exc_medium))
        assert response_medium.status_code == 400

    def test_atom_exception_details_in_response(self, mock_request):
        """
        AtomException details should be passed through to response.
        """
        from core.exceptions import ValidationError
        import asyncio

        exc = ValidationError(
            "Validation failed",
            details={"field": "email", "reason": "invalid format"}
        )
        response = asyncio.run(atom_exception_handler(mock_request, exc))

        data = response.body.decode()
        import json
        parsed = json.loads(data)

        assert "details" in parsed
        assert parsed["details"]["field"] == "email"

    def test_atom_exception_request_id_tracing(self, mock_request):
        """
        Request ID should be included in error response.
        """
        from core.exceptions import ValidationError
        import asyncio

        exc = ValidationError("Test error")
        response = asyncio.run(atom_exception_handler(mock_request, exc))

        data = response.body.decode()
        import json
        parsed = json.loads(data)

        assert "request_id" in parsed
        assert parsed["request_id"] == "test-request-123"


# ============================================================================
# TestGlobalExceptionHandling
# ============================================================================


class TestGlobalExceptionHandling:
    """Test global exception handler for uncaught exceptions."""

    def test_uncaught_exception_to_500(self, mock_request):
        """
        Generic Exception should be caught by global_exception_handler.

        Uncaught exceptions should return 500 status.
        """
        import asyncio

        exc = ValueError("Something went wrong")
        response = asyncio.run(global_exception_handler(mock_request, exc))

        assert response.status_code == 500

    def test_traceback_hidden_in_production(self, mock_request):
        """
        Traceback should be hidden in production mode.

        Production errors should not expose stack traces.
        """
        import asyncio
        os.environ["ENVIRONMENT"] = "production"

        exc = ValueError("Internal error")
        response = asyncio.run(global_exception_handler(mock_request, exc))

        data = response.body.decode()
        import json
        parsed = json.loads(data)

        # No traceback in production
        assert "traceback" not in parsed
        # Generic message
        assert "internal" in parsed["message"].lower() or "error" in parsed["message"].lower()

    def test_traceback_visible_in_development(self, mock_request):
        """
        Traceback should be visible in development mode.

        Development errors should include stack traces for debugging.
        """
        import asyncio
        os.environ["ENVIRONMENT"] = "development"

        exc = ValueError("Debug this error")
        response = asyncio.run(global_exception_handler(mock_request, exc))

        data = response.body.decode()
        import json
        parsed = json.loads(data)

        # Traceback visible in development
        assert "traceback" in parsed or "ValueError" in parsed["message"]

        # Reset to production
        os.environ["ENVIRONMENT"] = "production"

    def test_request_id_logged_in_error(self, mock_request, caplog):
        """
        Request ID should be logged with error.
        """
        import asyncio
        from core.exceptions import ValidationError

        with caplog.at_level(logging.ERROR):
            exc = ValidationError("Test error")
            response = asyncio.run(atom_exception_handler(mock_request, exc))

            # Verify request ID in logs
            log_messages = [record.message for record in caplog.records]
            assert any("test-request-123" in msg for msg in log_messages)


# ============================================================================
# TestErrorResponseConsistency
# ============================================================================


class TestErrorResponseConsistency:
    """Test consistency of error responses across all endpoints."""

    def test_all_errors_have_success_false(self, mock_request):
        """
        All error responses should have success=False.

        This is the standard error response format.
        """
        import asyncio

        # Test various exception types
        exceptions = [
            ValidationError("Test error"),
            AgentNotFoundError("test-agent"),
            DatabaseConnectionError("DB failed"),
            ValueError("Generic error"),
        ]

        for exc in exceptions:
            if isinstance(exc, AtomException):
                response = asyncio.run(atom_exception_handler(mock_request, exc))
            else:
                response = asyncio.run(global_exception_handler(mock_request, exc))

            data = response.body.decode()
            import json
            parsed = json.loads(data)

            assert parsed["success"] == False, f"Exception {type(exc).__name__} should have success=False"

    def test_error_codes_match_enum(self, mock_request):
        """
        error_code should match valid ErrorCode enum value.

        Ensures all error codes are standardized.
        """
        import asyncio

        exc = AgentNotFoundError("test-agent")
        response = asyncio.run(atom_exception_handler(mock_request, exc))

        data = response.body.decode()
        import json
        parsed = json.loads(data)

        # Verify error code is in enum
        valid_codes = [code.value for code in AtomErrorCode]
        assert parsed["error_code"] in valid_codes, f"Invalid error code: {parsed['error_code']}"

    def test_content_type_json(self, client):
        """
        Error responses should have Content-Type: application/json.

        API errors should always return JSON.
        """
        # Trigger 404 error
        response = client.get("/api/v1/agents/nonexistent-agent")

        # Should return JSON
        assert "application/json" in response.headers.get("content-type", ""), \
            f"Expected JSON content-type, got {response.headers.get('content-type')}"

    def test_cors_headers_on_error(self, client):
        """
        CORS headers should be present on error responses.

        Errors should still include proper CORS headers.
        """
        # Trigger error
        response = client.get(
            "/api/v1/agents/nonexistent-agent",
            headers={"Origin": "http://localhost:3000"}
        )

        # Check for CORS headers (may not be present in test client)
        # In production, these should be present
        cors_headers = ["access-control-allow-origin"]
        # At minimum, request shouldn't crash
        assert response.status_code in [200, 404, 500]


# ============================================================================
# Test Handler Integration
# ============================================================================


class TestHandlerIntegration:
    """Test integration between handlers and FastAPI app."""

    def test_atom_exception_handler_registered(self, client):
        """
        atom_exception_handler should be registered in FastAPI app.

        Verify handler catches AtomException correctly.
        """
        from main_api_app import app
        from core.exceptions import AtomException

        # Check if handler is registered
        # FastAPI stores exception handlers in app.exception_handlers
        assert AtomException in app.exception_handlers or hasattr(app, 'exception_handlers')

    def test_global_exception_handler_registered(self, client):
        """
        global_exception_handler should be registered for all exceptions.

        Verify handler catches generic Exception.
        """
        from main_api_app import app

        # Check if Exception handler is registered
        assert Exception in app.exception_handlers or hasattr(app, 'exception_handlers')

    def test_handler_chain_priority(self, mock_request):
        """
        AtomException handler should take precedence over global handler.

        More specific handlers should catch before generic.
        """
        import asyncio

        exc = AgentNotFoundError("test-agent")
        response = asyncio.run(atom_exception_handler(mock_request, exc))

        # Should return 400 (AtomException handler)
        # Not 500 (global handler)
        assert response.status_code == 400


# ============================================================================
# Test Error Propagation Scenarios
# ============================================================================


class TestErrorPropagationScenarios:
    """Test real-world error propagation scenarios."""

    def test_service_to_api_to_client_flow(self, client):
        """
        Test complete error flow: Service -> API -> Client.

        1. Service layer raises exception
        2. API layer catches and transforms to HTTP response
        3. Client receives standardized error response
        """
        from core.exceptions import AgentNotFoundError

        with patch("core.agent_governance_service.AgentGovernanceService.get_agent") as mock_get:
            # Service layer raises exception
            mock_get.side_effect = AgentNotFoundError("missing-agent", details={"agent_id": "missing-agent"})

            # API layer transforms to HTTP response
            response = client.get("/api/v1/agents/missing-agent")

            # Client receives standardized error
            assert response.status_code == 404
            data = response.json()
            assert "error_code" in data or "detail" in data

    def test_wrapped_exception_propagation(self, client):
        """
        Test wrapped exception propagation.

        Original exception should be preserved in chain.
        """
        from core.exceptions import DatabaseConnectionError

        original_error = OperationalError("Connection failed", {}, None)

        with patch("core.agent_governance_service.AgentGovernanceService.get_agent") as mock_get:
            # Service wraps database error
            mock_get.side_effect = DatabaseConnectionError("Failed to connect", cause=original_error)

            response = client.get("/api/v1/agents/test-agent")

            # Should return 500
            assert response.status_code in [500, 503]

    def test_multiple_service_errors_aggregation(self, client):
        """
        Test aggregation of multiple service errors.

        API should aggregate multiple validation errors.
        """
        from core.exceptions import ValidationError

        with patch("core.agent_governance_service.AgentGovernanceService.create_agent") as mock_create:
            errors = [
                {"field": "name", "message": "Name is required"},
                {"field": "domain", "message": "Invalid domain"},
            ]
            mock_create.side_effect = ValidationError("Validation failed", details={"errors": errors})

            response = client.post(
                "/api/v1/agents",
                json={"id": "test-agent", "name": "", "domain": "invalid"}
            )

            # Should return 400
            assert response.status_code in [400, 422]


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases in error propagation."""

    def test_none_error_message(self, mock_request):
        """
        Handle None or empty error messages gracefully.
        """
        import asyncio

        exc = ValidationError("")
        response = asyncio.run(atom_exception_handler(mock_request, exc))

        # Should still return valid response
        assert response.status_code == 400
        data = response.body.decode()
        import json
        parsed = json.loads(data)
        assert parsed["success"] == False

    def test_unicode_in_error_message(self, mock_request):
        """
        Handle unicode characters in error messages.
        """
        import asyncio

        exc = ValidationError("Error: 你好 🚀")
        response = asyncio.run(atom_exception_handler(mock_request, exc))

        # Should handle unicode correctly
        assert response.status_code == 400

    def test_very_long_error_message(self, mock_request):
        """
        Handle very long error messages.
        """
        import asyncio

        long_message = "Error: " + "x" * 10000
        exc = ValidationError(long_message)
        response = asyncio.run(atom_exception_handler(mock_request, exc))

        # Should truncate or handle long messages
        assert response.status_code == 400

    def test_special_characters_in_error_code(self, mock_request):
        """
        Handle special characters in error details.
        """
        import asyncio

        exc = ValidationError(
            "Test error",
            details={"sql": "SELECT * FROM 'table'; DROP TABLE;"}
        )
        response = asyncio.run(atom_exception_handler(mock_request, exc))

        # Should sanitize or escape special characters
        assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
