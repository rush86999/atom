"""
API Exception Middleware Error Tests

Tests verify that the backend exception middleware handles and logs API errors
with proper status codes, ensuring graceful error responses for all error types.

Pattern from Phase 157-RESEARCH.md: Error boundary testing for backend API middleware
"""

import pytest
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from sqlalchemy.exc import IntegrityError, OperationalError

from core.error_handlers import (
    global_exception_handler,
    atom_exception_handler,
    api_error,
    handle_validation_error,
    handle_not_found,
    handle_permission_denied,
    ErrorCode,
    ErrorResponse,
)
from core.exceptions import AtomException, ErrorSeverity


# ============================================================================
# Middleware Error Handling Tests
# ============================================================================


class TestMiddlewareErrorHandling:
    """Test suite for API middleware error handling"""

    async def test_middleware_catches_unhandled_exceptions(self):
        """Test that middleware catches and logs unexpected exceptions."""
        # Create mock request
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "test-request-123"
        request.url = "https://api.example.com/agents"

        # Create unexpected exception
        exc = Exception("Unexpected database connection failure")

        # Mock logger to capture error logs
        with patch('core.error_handlers.logger.error') as mock_logger:
            response = await global_exception_handler(request, exc)

            # Verify error was logged with full context
            assert mock_logger.called
            log_call_args = mock_logger.call_args
            assert "Uncaught exception" in str(log_call_args)

            # Verify response structure
            assert isinstance(response, JSONResponse)
            assert response.status_code == 500

    async def test_middleware_returns_500_on_internal_error(self):
        """Test that middleware returns 500 status code for unhandled exceptions."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = None
        request.url = "https://api.example.com/agents"

        exc = RuntimeError("Internal service unavailable")

        response = await global_exception_handler(request, exc)

        assert response.status_code == 500
        body = response.body.decode()
        assert "success" in body
        assert "error_code" in body

    async def test_middleware_preserves_error_context(self):
        """Test that error details are logged and preserved in response."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "ctx-123"
        request.url = "https://api.example.com/agents/test-agent"

        exc = ValueError("Invalid agent configuration: missing required field")

        with patch('core.error_handlers.logger.error') as mock_logger:
            response = await global_exception_handler(request, exc)

            # Verify error context was logged
            assert mock_logger.called
            call_kwargs = mock_logger.call_args.kwargs
            assert "extra" in call_kwargs
            assert call_kwargs["extra"]["request_id"] == "ctx-123"
            assert "path" in call_kwargs["extra"]

    async def test_middleware_handles_validation_errors(self):
        """Test that validation errors return 400 status code."""
        # Create validation error via helper
        validation_exc = handle_validation_error(
            field="agent_name",
            message="Agent name is required",
            value=None
        )

        # HTTPException is raised directly, not caught by global_exception_handler
        # This test verifies the error structure is correct
        assert isinstance(validation_exc, HTTPException)
        assert validation_exc.status_code == 400
        assert validation_exc.detail["error_code"] == "VALIDATION_ERROR"
        assert "agent_name" in validation_exc.detail["details"]["field"]

    async def test_middleware_handles_not_found(self):
        """Test that not found errors return 404 status code."""
        # Create not found error via helper
        not_found_exc = handle_not_found(
            resource_type="Agent",
            resource_id="nonexistent"
        )

        # HTTPException is raised directly, not caught by global_exception_handler
        # This test verifies the error structure is correct
        assert isinstance(not_found_exc, HTTPException)
        assert not_found_exc.status_code == 404
        assert not_found_exc.detail["error_code"] == "NOT_FOUND"
        assert "nonexistent" in not_found_exc.detail["message"]

    async def test_middleware_handles_authentication_errors(self):
        """Test that authentication errors return 401/403 status codes."""
        # Test permission denied (403)
        permission_exc = handle_permission_denied(
            action="delete",
            resource_type="Agent"
        )

        # HTTPException is raised directly, not caught by global_exception_handler
        # This test verifies the error structure is correct
        assert isinstance(permission_exc, HTTPException)
        assert permission_exc.status_code == 403
        assert permission_exc.detail["error_code"] == "PERMISSION_DENIED"


# ============================================================================
# AtomException Handler Tests
# ============================================================================


class TestAtomExceptionHandling:
    """Test suite for AtomException-specific error handling"""

    async def test_atom_exception_with_high_severity(self):
        """Test that high-severity AtomException returns 500 status."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "atom-123"
        request.url = "https://api.example.com/agents"

        exc = AtomException(
            error_code=ErrorCode.AGENT_EXECUTION_FAILED,
            message="Agent execution crashed",
            severity=ErrorSeverity.HIGH,
            details={"agent_id": "test-agent", "crash_reason": "Null pointer"}
        )

        with patch('core.error_handlers.logger.error') as mock_logger:
            response = await atom_exception_handler(request, exc)

            assert response.status_code == 500
            assert mock_logger.called

    async def test_atom_exception_with_medium_severity(self):
        """Test that medium-severity AtomException returns 400 status."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "atom-456"
        request.url = "https://api.example.com/agents"

        exc = AtomException(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Invalid agent maturity level",
            severity=ErrorSeverity.MEDIUM,
            details={"field": "maturity_level", "value": "INVALID"}
        )

        with patch('core.error_handlers.logger.warning') as mock_logger:
            response = await atom_exception_handler(request, exc)

            assert response.status_code == 400
            assert mock_logger.called

    async def test_atom_exception_preserves_details(self):
        """Test that AtomException details are included in response."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "atom-789"
        request.url = "https://api.example.com/agents"

        exc_details = {
            "agent_id": "test-agent",
            "execution_time": "5.2s",
            "error_type": "TimeoutError"
        }

        exc = AtomException(
            error_code=ErrorCode.AGENT_EXECUTION_FAILED,
            message="Agent execution timeout",
            severity=ErrorSeverity.HIGH,
            details=exc_details
        )

        response = await atom_exception_handler(request, exc)

        body = response.body.decode()
        assert "test-agent" in body
        assert "TimeoutError" in body


# ============================================================================
# Error Helper Function Tests
# ============================================================================


class TestErrorHelperFunctions:
    """Test suite for error helper functions"""

    def test_api_error_creates_http_exception(self):
        """Test that api_error creates properly formatted HTTPException."""
        exc = api_error(
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Canvas not found",
            details={"canvas_id": "canvas-123"},
            status_code=404,
            request_id="req-123"
        )

        assert isinstance(exc, HTTPException)
        assert exc.status_code == 404
        assert exc.detail["success"] is False
        assert exc.detail["error_code"] == "NOT_FOUND"
        assert exc.detail["message"] == "Canvas not found"
        assert exc.detail["details"]["canvas_id"] == "canvas-123"
        assert exc.detail["request_id"] == "req-123"

    def test_handle_validation_error_creates_proper_exception(self):
        """Test that handle_validation_error creates validation error."""
        exc = handle_validation_error(
            field="maturity_level",
            message="Must be one of: STUDENT, INTERN, SUPERVISED, AUTONOMOUS",
            value="INVALID_LEVEL",
            status_code=400
        )

        assert isinstance(exc, HTTPException)
        assert exc.status_code == 400
        assert exc.detail["error_code"] == "VALIDATION_ERROR"
        assert "maturity_level" in exc.detail["details"]["field"]

    def test_handle_not_found_creates_proper_exception(self):
        """Test that handle_not_found creates not found error."""
        exc = handle_not_found(
            resource_type="Agent",
            resource_id="agent-999",
            details={"searched_in": "production_db"}
        )

        assert isinstance(exc, HTTPException)
        assert exc.status_code == 404
        assert exc.detail["error_code"] == "NOT_FOUND"
        assert "agent-999" in exc.detail["message"]

    def test_handle_permission_denied_creates_proper_exception(self):
        """Test that handle_permission_denied creates permission error."""
        exc = handle_permission_denied(
            action="execute",
            resource_type="Agent",
            details={"required_maturity": "AUTONOMOUS", "actual_maturity": "STUDENT"}
        )

        assert isinstance(exc, HTTPException)
        assert exc.status_code == 403
        assert exc.detail["error_code"] == "PERMISSION_DENIED"


# ============================================================================
# Error Response Model Tests
# ============================================================================


class TestErrorResponseModel:
    """Test suite for ErrorResponse model validation"""

    def test_error_response_serialization(self):
        """Test that ErrorResponse serializes correctly."""
        response = ErrorResponse(
            success=False,
            error_code="AGENT_NOT_FOUND",
            message="Agent not found",
            details={"agent_id": "missing-agent"},
            timestamp="2026-03-09T12:00:00Z",
            request_id="req-123"
        )

        serialized = response.dict(exclude_none=True)

        assert serialized["success"] is False
        assert serialized["error_code"] == "AGENT_NOT_FOUND"
        assert serialized["message"] == "Agent not found"
        assert serialized["details"]["agent_id"] == "missing-agent"
        assert serialized["request_id"] == "req-123"

    def test_error_response_without_optional_fields(self):
        """Test that ErrorResponse works without optional fields."""
        response = ErrorResponse(
            success=False,
            error_code="INTERNAL_ERROR",
            message="Internal server error",
            timestamp=datetime.utcnow().isoformat()
        )

        serialized = response.dict(exclude_none=True)

        assert serialized["success"] is False
        assert "details" not in serialized
        assert "request_id" not in serialized


# ============================================================================
# Integration Tests with Mock API
# ============================================================================


class TestMiddlewareIntegration:
    """Integration tests for middleware with mock API endpoints"""

    async def test_end_to_end_error_handling_flow(self):
        """Test complete error handling flow from exception to response."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "e2e-123"
        request.url = "https://api.example.com/agents/invalid-agent"

        # Simulate generic error (not HTTPException)
        exc = Exception("Unexpected error during agent lookup")

        with patch('core.error_handlers.logger.error'):
            response = await global_exception_handler(request, exc)

            # Verify complete response
            assert response.status_code == 500
            body = response.body.decode()

            # Verify all required fields present
            assert "success" in body
            assert "error_code" in body
            assert "message" in body
            assert "timestamp" in body
            assert "e2e-123" in body

    async def test_concurrent_error_handling(self):
        """Test that middleware handles concurrent errors correctly."""
        import asyncio

        request1 = MagicMock(spec=Request)
        request1.state = MagicMock()
        request1.state.request_id = "conc-1"
        request1.url = "https://api.example.com/agents"

        request2 = MagicMock(spec=Request)
        request2.state = MagicMock()
        request2.state.request_id = "conc-2"
        request2.url = "https://api.example.com/canvases"

        exc1 = Exception("Error 1")
        exc2 = Exception("Error 2")

        # Handle errors concurrently
        with patch('core.error_handlers.logger.error'):
            results = await asyncio.gather(
                global_exception_handler(request1, exc1),
                global_exception_handler(request2, exc2)
            )

            # Both should return 500
            assert results[0].status_code == 500
            assert results[1].status_code == 500

            # Each should have unique request_id in body
            body1 = results[0].body.decode()
            body2 = results[1].body.decode()
            assert "conc-1" in body1
            assert "conc-2" in body2


# ============================================================================
# Database Error Handling Tests
# ============================================================================


class TestDatabaseErrorHandling:
    """Test suite for database-related error handling"""

    async def test_database_connection_error(self):
        """Test handling of database connection errors."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "db-123"
        request.url = "https://api.example.com/agents"

        # Simulate database connection error
        exc = OperationalError(
            "could not connect to server: Connection refused",
            {},
            None
        )

        with patch('core.error_handlers.logger.error'):
            response = await global_exception_handler(request, exc)

            assert response.status_code == 500
            body = response.body.decode()
            assert "success" in body

    async def test_database_integrity_error(self):
        """Test handling of database integrity errors."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "int-123"
        request.url = "https://api.example.com/agents"

        # Simulate foreign key violation
        exc = IntegrityError(
            "foreign key constraint violation",
            {},
            Exception("DETAIL: Key (agent_id)=(invalid) is not present in table \"agents\"")
        )

        with patch('core.error_handlers.logger.error'):
            response = await global_exception_handler(request, exc)

            assert response.status_code == 500
            body = response.body.decode()
            assert "INTERNAL_ERROR" in body


# ============================================================================
# Development vs Production Error Messages
# ============================================================================


class TestEnvironmentSpecificErrors:
    """Test suite for environment-specific error responses"""

    async def test_development_exposes_detailed_errors(self):
        """Test that development environment exposes detailed error information."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "dev-123"
        request.url = "https://api.example.com/agents"

        exc = ValueError("Detailed error message for debugging")

        with patch('core.error_handlers.logger.error'):
            with patch.dict('os.environ', {'ENVIRONMENT': 'development'}):
                response = await global_exception_handler(request, exc)

                body = response.body.decode()
                # Development mode should include detailed error
                assert "ValueError" in body or "Detailed error message" in body

    async def test_production_hides_internal_errors(self):
        """Test that production environment hides internal error details."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.request_id = "prod-123"
        request.url = "https://api.example.com/agents"

        exc = ValueError("Internal implementation detail")

        with patch('core.error_handlers.logger.error'):
            with patch.dict('os.environ', {'ENVIRONMENT': 'production'}):
                response = await global_exception_handler(request, exc)

                body = response.body.decode()
                # Production mode should show generic message
                assert "internal server error" in body.lower()
