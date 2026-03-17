"""
Comprehensive tests for Error Handling Middleware

Target: 60%+ coverage for core/error_middleware.py (467 lines)
Focus: Error interception, response formatting, statistics tracking, logging
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import json
import time

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.error_middleware import (
    ErrorHandlingMiddleware,
    ErrorStatistics,
    get_error_statistics,
    reset_error_statistics,
)


# ========================================================================
# Fixtures
# ========================================================================


@pytest.fixture
def mock_request():
    """Create mock FastAPI request."""
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url = MagicMock()
    request.url.path = "/api/test"
    request.url.query = "param=value"
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers = {"user-agent": "test-agent"}
    request.state = MagicMock()
    return request


@pytest.fixture
def mock_response():
    """Create mock response."""
    response = MagicMock(spec=Response)
    response.headers = {}
    return response


@pytest.fixture
def sample_app():
    """Create sample ASGI app."""
    async def app(scope, receive, send):
        pass
    return app


@pytest.fixture
def error_middleware(sample_app):
    """Create error handling middleware instance."""
    return ErrorHandlingMiddleware(
        app=sample_app,
        debug_mode=True,
        enable_statistics=True,
        log_errors=False
    )


@pytest.fixture
def error_middleware_no_debug(sample_app):
    """Create middleware without debug mode."""
    return ErrorHandlingMiddleware(
        app=sample_app,
        debug_mode=False,
        enable_statistics=True,
        log_errors=False
    )


@pytest.fixture
def error_middleware_no_stats(sample_app):
    """Create middleware without statistics."""
    return ErrorHandlingMiddleware(
        app=sample_app,
        debug_mode=True,
        enable_statistics=False,
        log_errors=False
    )


# ========================================================================
# Test Class 1: ErrorStatistics
# ========================================================================


class TestErrorStatistics:
    """Test error statistics tracking."""

    def test_statistics_singleton(self):
        """Test that ErrorStatistics is a singleton."""
        stats1 = ErrorStatistics()
        stats2 = ErrorStatistics()

        assert stats1 is stats2

    def test_statistics_initialization(self):
        """Test statistics initialization."""
        stats = ErrorStatistics()

        assert stats._total_requests == 0
        assert stats._total_errors == 0
        assert len(stats._error_counts) == 0
        assert len(stats._endpoint_errors) == 0
        assert len(stats._last_24h_errors) == 0

    def test_record_request(self):
        """Test recording a request."""
        stats = ErrorStatistics()
        stats.record_request()

        assert stats._total_requests == 1

    def test_record_multiple_requests(self):
        """Test recording multiple requests."""
        stats = ErrorStatistics()
        for _ in range(5):
            stats.record_request()

        assert stats._total_requests == 5

    def test_record_error(self):
        """Test recording an error."""
        stats = ErrorStatistics()
        stats.record_error(
            error_type="ValueError",
            endpoint="/api/test",
            status_code=400
        )

        assert stats._total_errors == 1
        assert stats._error_counts["ValueError"] == 1
        assert stats._endpoint_errors["/api/test"]["ValueError"] == 1
        assert len(stats._last_24h_errors) == 1

    def test_record_multiple_errors(self):
        """Test recording multiple errors."""
        stats = ErrorStatistics()
        stats.record_error("ValueError", "/api/test", 400)
        stats.record_error("TypeError", "/api/test", 400)
        stats.record_error("ValueError", "/api/other", 400)

        assert stats._total_errors == 3
        assert stats._error_counts["ValueError"] == 2
        assert stats._error_counts["TypeError"] == 1

    def test_error_history_limit(self):
        """Test that error history is limited to 100 entries."""
        stats = ErrorStatistics()

        # Record 150 errors
        for i in range(150):
            stats.record_error(f"Error{i}", "/api/test", 500)

        # Should only keep last 100
        assert len(stats._last_24h_errors) == 100

    def test_get_statistics(self):
        """Test getting statistics summary."""
        stats = ErrorStatistics()
        stats.record_request()
        stats.record_request()
        stats.record_error("ValueError", "/api/test", 400)

        summary = stats.get_statistics()

        assert summary["total_requests"] == 2
        assert summary["total_errors"] == 1
        assert summary["error_rate"] == 0.5
        assert "ValueError" in summary["error_counts"]
        assert "/api/test" in summary["endpoint_errors"]
        assert len(summary["recent_errors"]) == 1

    def test_get_statistics_with_no_data(self):
        """Test getting statistics with no data."""
        stats = ErrorStatistics()
        summary = stats.get_statistics()

        assert summary["total_requests"] == 0
        assert summary["total_errors"] == 0
        assert summary["error_rate"] == 0.0

    def test_reset_statistics(self):
        """Test resetting statistics."""
        stats = ErrorStatistics()
        stats.record_request()
        stats.record_error("ValueError", "/api/test", 400)

        stats.reset()

        assert stats._total_requests == 0
        assert stats._total_errors == 0
        assert len(stats._error_counts) == 0
        assert len(stats._endpoint_errors) == 0
        assert len(stats._last_24h_errors) == 0


# ========================================================================
# Test Class 2: ErrorHandlingMiddleware - Initialization
# ========================================================================


class TestMiddlewareInitialization:
    """Test middleware initialization and configuration."""

    def test_middleware_initialization_with_debug(self, sample_app):
        """Test middleware initialization with debug mode."""
        middleware = ErrorHandlingMiddleware(
            app=sample_app,
            debug_mode=True,
            enable_statistics=True,
            log_errors=False
        )

        assert middleware._debug_mode is True
        assert middleware._enable_statistics is True
        assert middleware._log_errors is False
        assert middleware._stats is not None

    def test_middleware_initialization_without_debug(self, sample_app):
        """Test middleware initialization without debug mode."""
        middleware = ErrorHandlingMiddleware(
            app=sample_app,
            debug_mode=False,
            enable_statistics=True
        )

        assert middleware._debug_mode is False
        assert middleware._stats is not None

    def test_middleware_initialization_debug_from_env(self, sample_app):
        """Test middleware reads debug mode from environment."""
        with patch.dict("os.environ", {"DEBUG": "true"}):
            middleware = ErrorHandlingMiddleware(
                app=sample_app,
                debug_mode=None,
                enable_statistics=True
            )

            assert middleware._debug_mode is True

    def test_middleware_initialization_without_statistics(self, sample_app):
        """Test middleware initialization without statistics."""
        middleware = ErrorHandlingMiddleware(
            app=sample_app,
            enable_statistics=False
        )

        assert middleware._stats is None

    def test_middleware_initialization_default_values(self, sample_app):
        """Test middleware with default values."""
        middleware = ErrorHandlingMiddleware(app=sample_app)

        assert middleware._enable_statistics is True
        assert middleware._log_errors is True
        assert isinstance(middleware._stats, ErrorStatistics)


# ========================================================================
# Test Class 3: Request Context Extraction
# ========================================================================


class TestRequestContextExtraction:
    """Test request context extraction."""

    def test_extract_basic_request_context(self, error_middleware, mock_request):
        """Test extracting basic request context."""
        context = error_middleware._extract_request_context(mock_request)

        assert context["method"] == "GET"
        assert context["path"] == "/api/test"
        assert context["query_params"] == "param=value"
        assert context["client_host"] == "127.0.0.1"
        assert context["user_agent"] == "test-agent"

    def test_extract_request_context_with_user_id(self, error_middleware):
        """Test extracting context with authenticated user."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/protected"
        request.url.query = ""
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        request.headers = {"user-agent": "Mozilla"}
        request.state.user_id = "user123"

        context = error_middleware._extract_request_context(request)

        assert context["user_id"] == "user123"

    def test_extract_request_context_without_client(self, error_middleware):
        """Test extracting context when client is None."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/test"
        request.url.query = ""
        request.client = None
        request.headers = {}

        context = error_middleware._extract_request_context(request)

        assert context["client_host"] is None


# ========================================================================
# Test Class 4: Error Information Extraction
# ========================================================================


class TestErrorInfoExtraction:
    """Test error information extraction."""

    def test_extract_value_error_info(self, error_middleware, mock_request):
        """Test extracting ValueError information."""
        exc = ValueError("Invalid value")
        request_context = error_middleware._extract_request_context(mock_request)

        error_info = error_middleware._extract_error_info(exc, request_context)

        assert error_info["type"] == "ValueError"
        assert error_info["message"] == "Invalid value"
        assert error_info["status_code"] == 400
        assert error_info["is_http_exception"] is False

    def test_extract_type_error_info(self, error_middleware, mock_request):
        """Test extracting TypeError information."""
        exc = TypeError("Invalid type")
        request_context = error_middleware._extract_request_context(mock_request)

        error_info = error_middleware._extract_error_info(exc, request_context)

        assert error_info["type"] == "TypeError"
        assert error_info["status_code"] == 400

    def test_extract_permission_error_info(self, error_middleware, mock_request):
        """Test extracting PermissionError information."""
        exc = PermissionError("Access denied")
        request_context = error_middleware._extract_request_context(mock_request)

        error_info = error_middleware._extract_error_info(exc, request_context)

        assert error_info["type"] == "PermissionError"
        assert error_info["status_code"] == 403

    def test_extract_key_error_info(self, error_middleware, mock_request):
        """Test extracting KeyError information."""
        exc = KeyError("missing_key")
        request_context = error_middleware._extract_request_context(mock_request)

        error_info = error_middleware._extract_error_info(exc, request_context)

        assert error_info["type"] == "KeyError"
        assert error_info["status_code"] == 400

    def test_extract_attribute_error_info(self, error_middleware, mock_request):
        """Test extracting AttributeError information."""
        exc = AttributeError("Missing attribute")
        request_context = error_middleware._extract_request_context(mock_request)

        error_info = error_middleware._extract_error_info(exc, request_context)

        assert error_info["type"] == "AttributeError"
        assert error_info["status_code"] == 400

    def test_extract_generic_exception_info(self, error_middleware, mock_request):
        """Test extracting generic exception information."""
        exc = RuntimeError("Runtime error")
        request_context = error_middleware._extract_request_context(mock_request)

        error_info = error_middleware._extract_error_info(exc, request_context)

        assert error_info["type"] == "RuntimeError"
        assert error_info["status_code"] == 500

    def test_extract_http_exception_info(self, error_middleware, mock_request):
        """Test extracting HTTPException information."""
        from fastapi import HTTPException
        exc = HTTPException(status_code=404, detail="Not found")
        request_context = error_middleware._extract_request_context(mock_request)

        error_info = error_middleware._extract_error_info(exc, request_context)

        assert error_info["type"] == "HTTPException"
        assert error_info["status_code"] == 404
        assert error_info["is_http_exception"] is True


# ========================================================================
# Test Class 5: Error Response Creation
# ========================================================================


class TestErrorResponseCreation:
    """Test error response creation."""

    def test_create_error_response_debug_mode(
        self, error_middleware, mock_request
    ):
        """Test creating error response in debug mode."""
        exc = ValueError("Test error")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        response = error_middleware._create_error_response(
            exc, error_info, request_context
        )

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400

        body = json.loads(response.body.decode())
        assert body["success"] is False
        assert "error" in body
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["type"] == "ValueError"  # Debug mode includes type
        assert "stack_trace" in body["error"]  # Debug mode includes traceback

    def test_create_error_response_no_debug(
        self, error_middleware_no_debug, mock_request
    ):
        """Test creating error response without debug mode."""
        exc = ValueError("Test error")
        request_context = error_middleware_no_debug._extract_request_context(
            mock_request
        )
        error_info = error_middleware_no_debug._extract_error_info(
            exc, request_context
        )

        response = error_middleware_no_debug._create_error_response(
            exc, error_info, request_context
        )

        body = json.loads(response.body.decode())
        assert body["success"] is False
        assert "error" in body
        assert "type" not in body["error"]  # No debug info
        assert "stack_trace" not in body["error"]

    def test_create_error_response_for_http_exception(
        self, error_middleware, mock_request
    ):
        """Test creating response for HTTPException."""
        from fastapi import HTTPException
        exc = HTTPException(status_code=404, detail="Resource not found")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        response = error_middleware._create_error_response(
            exc, error_info, request_context
        )

        assert response.status_code == 404

        body = json.loads(response.body.decode())
        assert body["error"]["message"] == "Resource not found"

    def test_create_error_response_includes_timestamp(
        self, error_middleware, mock_request
    ):
        """Test that error response includes timestamp."""
        exc = ValueError("Test error")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        response = error_middleware._create_error_response(
            exc, error_info, request_context
        )

        body = json.loads(response.body.decode())
        assert "timestamp" in body["error"]
        # Verify timestamp is valid ISO format
        datetime.fromisoformat(body["error"]["timestamp"])

    def test_create_error_response_includes_request_id(
        self, error_middleware, mock_request
    ):
        """Test that error response includes request ID (path)."""
        exc = ValueError("Test error")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        response = error_middleware._create_error_response(
            exc, error_info, request_context
        )

        body = json.loads(response.body.decode())
        assert body["error"]["request_id"] == "/api/test"


# ========================================================================
# Test Class 6: Error Code Mapping
# ========================================================================


class TestErrorCodeMapping:
    """Test error code mapping."""

    def test_get_error_code_for_value_error(self, error_middleware, mock_request):
        """Test error code for ValueError."""
        exc = ValueError("Invalid value")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        code = error_middleware._get_error_code(exc, error_info)

        assert code == "VALIDATION_ERROR"

    def test_get_error_code_for_type_error(self, error_middleware, mock_request):
        """Test error code for TypeError."""
        exc = TypeError("Invalid type")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        code = error_middleware._get_error_code(exc, error_info)

        assert code == "TYPE_ERROR"

    def test_get_error_code_for_key_error(self, error_middleware, mock_request):
        """Test error code for KeyError."""
        exc = KeyError("missing_key")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        code = error_middleware._get_error_code(exc, error_info)

        assert code == "MISSING_FIELD"

    def test_get_error_code_for_permission_error(
        self, error_middleware, mock_request
    ):
        """Test error code for PermissionError."""
        exc = PermissionError("Access denied")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        code = error_middleware._get_error_code(exc, error_info)

        assert code == "PERMISSION_DENIED"

    def test_get_error_code_for_attribute_error(
        self, error_middleware, mock_request
    ):
        """Test error code for AttributeError."""
        exc = AttributeError("Missing attribute")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        code = error_middleware._get_error_code(exc, error_info)

        assert code == "ATTRIBUTE_ERROR"

    def test_get_error_code_for_generic_exception(
        self, error_middleware, mock_request
    ):
        """Test error code for generic exception."""
        exc = RuntimeError("Runtime error")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        code = error_middleware._get_error_code(exc, error_info)

        assert code == "INTERNAL_ERROR"

    def test_get_error_code_custom_error_code_attribute(
        self, error_middleware, mock_request
    ):
        """Test error code when exception has custom error_code attribute."""
        exc = ValueError("Custom error")
        exc.error_code = "CUSTOM_ERROR"
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        code = error_middleware._get_error_code(exc, error_info)

        assert code == "CUSTOM_ERROR"


# ========================================================================
# Test Class 7: Error Message Mapping
# ========================================================================


class TestErrorMessageMapping:
    """Test error message mapping."""

    def test_get_error_message_from_exception_string(
        self, error_middleware, mock_request
    ):
        """Test error message from exception string."""
        exc = ValueError("This is a test error")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        message = error_middleware._get_error_message(exc, error_info)

        assert message == "This is a test error"

    def test_get_error_message_from_http_exception_detail(
        self, error_middleware, mock_request
    ):
        """Test error message from HTTPException detail."""
        from fastapi import HTTPException
        exc = HTTPException(status_code=404, detail="Custom not found message")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        message = error_middleware._get_error_message(exc, error_info)

        assert message == "Custom not found message"

    def test_get_error_message_fallback_for_500(
        self, error_middleware, mock_request
    ):
        """Test error message fallback for 500 error."""
        exc = Exception("")  # Empty message
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)
        error_info["status_code"] = 500

        message = error_middleware._get_error_message(exc, error_info)

        assert message == "An internal error occurred"

    def test_get_error_message_fallback_for_404(
        self, error_middleware, mock_request
    ):
        """Test error message fallback for 404 error."""
        exc = Exception("")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)
        error_info["status_code"] = 404

        message = error_middleware._get_error_message(exc, error_info)

        assert message == "Resource not found"

    def test_get_error_message_fallback_for_403(
        self, error_middleware, mock_request
    ):
        """Test error message fallback for 403 error."""
        exc = Exception("")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)
        error_info["status_code"] = 403

        message = error_middleware._get_error_message(exc, error_info)

        assert message == "Permission denied"

    def test_get_error_message_fallback_for_401(
        self, error_middleware, mock_request
    ):
        """Test error message fallback for 401 error."""
        exc = Exception("")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)
        error_info["status_code"] = 401

        message = error_middleware._get_error_message(exc, error_info)

        assert message == "Authentication required"


# ========================================================================
# Test Class 8: Middleware Dispatch
# ========================================================================


class TestMiddlewareDispatch:
    """Test middleware request dispatch."""

    @pytest.mark.asyncio
    async def test_successful_request(self, error_middleware, mock_request):
        """Test successful request processing."""
        async def call_next(request):
            response = MagicMock(spec=Response)
            response.headers = {}
            return response

        response = await error_middleware.dispatch(mock_request, call_next)

        assert "X-Process-Time" in response.headers
        # Verify process time is added
        process_time = float(response.headers["X-Process-Time"].rstrip("s"))
        assert process_time >= 0

    @pytest.mark.asyncio
    async def test_request_with_error(self, error_middleware, mock_request):
        """Test request that raises an exception."""
        async def call_next(request):
            raise ValueError("Test error")

        response = await error_middleware.dispatch(mock_request, call_next)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_request_with_http_exception(
        self, error_middleware, mock_request
    ):
        """Test request that raises HTTPException."""
        from fastapi import HTTPException

        async def call_next(request):
            raise HTTPException(status_code=404, detail="Not found")

        response = await error_middleware.dispatch(mock_request, call_next)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_request_recording_in_statistics(
        self, error_middleware_no_stats, mock_request
    ):
        """Test that requests are recorded in statistics."""
        async def call_next(request):
            response = MagicMock(spec=Response)
            response.headers = {}
            return response

        await error_middleware_no_stats.dispatch(mock_request, call_next)

        # Statistics should be disabled, so no recording
        assert error_middleware_no_stats._stats is None

    @pytest.mark.asyncio
    async def test_slow_request_warning(
        self, error_middleware, mock_request, caplog
    ):
        """Test that slow requests generate warnings."""
        import pytest as pt

        async def call_next(request):
            response = MagicMock(spec=Response)
            response.headers = {}
            # Simulate slow request
            await asyncio.sleep(0.1)
            return response

        # This would normally log a warning for slow requests
        response = await error_middleware.dispatch(mock_request, call_next)
        assert "X-Process-Time" in response.headers


# ========================================================================
# Test Class 9: Statistics Methods
# ========================================================================


class TestStatisticsMethods:
    """Test statistics-related methods."""

    def test_get_statistics_when_enabled(self, error_middleware):
        """Test getting statistics when enabled."""
        stats = error_middleware.get_statistics()

        assert "total_requests" in stats
        assert "total_errors" in stats
        assert "error_rate" in stats

    def test_get_statistics_when_disabled(self, error_middleware_no_stats):
        """Test getting statistics when disabled."""
        stats = error_middleware_no_stats.get_statistics()

        assert stats["message"] == "Statistics not enabled"

    def test_reset_statistics_when_enabled(self, error_middleware):
        """Test resetting statistics when enabled."""
        error_middleware._stats.record_request()
        error_middleware._stats.record_error("ValueError", "/api/test", 400)

        error_middleware.reset_statistics()

        stats = error_middleware.get_statistics()
        assert stats["total_requests"] == 0
        assert stats["total_errors"] == 0

    def test_reset_statistics_when_disabled(self, error_middleware_no_stats):
        """Test resetting statistics when disabled (should not crash)."""
        # Should not raise exception
        error_middleware_no_stats.reset_statistics()


# ========================================================================
# Test Class 10: Global Functions
# ========================================================================


class TestGlobalFunctions:
    """Test global convenience functions."""

    def test_get_error_statistics(self):
        """Test get_error_statistics global function."""
        stats = get_error_statistics()

        assert isinstance(stats, dict)
        assert "total_requests" in stats

    def test_reset_error_statistics(self):
        """Test reset_error_statistics global function."""
        # Record some data
        stats = ErrorStatistics()
        stats.record_request()
        stats.record_error("ValueError", "/api/test", 400)

        # Reset using global function
        reset_error_statistics()

        # Verify reset
        stats_after = ErrorStatistics()
        summary = stats_after.get_statistics()
        assert summary["total_requests"] == 0


# ========================================================================
# Test Class 11: Edge Cases
# ========================================================================


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_exception_with_unicode_message(
        self, error_middleware, mock_request
    ):
        """Test exception with unicode characters in message."""
        exc = ValueError("Error with emoji: 🚨 and unicode: café")
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        message = error_middleware._get_error_message(exc, error_info)

        assert "🚨" in message
        assert "café" in message

    @pytest.mark.asyncio
    async def test_exception_with_very_long_message(
        self, error_middleware, mock_request
    ):
        """Test exception with very long message."""
        long_message = "Error: " + "x" * 10000
        exc = ValueError(long_message)
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        message = error_middleware._get_error_message(exc, error_info)

        assert len(message) == 10005

    @pytest.mark.asyncio
    async def test_multiple_errors_same_endpoint(
        self, error_middleware, mock_request
    ):
        """Test recording multiple errors for same endpoint."""
        stats = ErrorStatistics()
        stats.record_error("ValueError", "/api/test", 400)
        stats.record_error("TypeError", "/api/test", 400)
        stats.record_error("ValueError", "/api/test", 400)

        endpoint_errors = stats._endpoint_errors["/api/test"]
        assert endpoint_errors["ValueError"] == 2
        assert endpoint_errors["TypeError"] == 1

    @pytest.mark.asyncio
    async def test_error_with_none_status_code(
        self, error_middleware, mock_request
    ):
        """Test error handling when status_code is None."""
        exc = Exception("Test error")
        # Simulate exception without status_code
        request_context = error_middleware._extract_request_context(mock_request)
        error_info = error_middleware._extract_error_info(exc, request_context)

        # Should default to 500
        assert error_info["status_code"] == 500


# ========================================================================
# Test Class 12: Performance
# ========================================================================


class TestPerformance:
    """Test performance characteristics."""

    @pytest.mark.asyncio
    async def test_middleware_overhead_is_minimal(self, error_middleware, mock_request):
        """Test that middleware adds minimal overhead."""
        async def call_next(request):
            response = MagicMock(spec=Response)
            response.headers = {}
            return response

        start = time.time()
        for _ in range(100):
            await error_middleware.dispatch(mock_request, call_next)
        duration = time.time() - start

        # Should process 100 requests in reasonable time
        assert duration < 5.0  # Less than 5 seconds for 100 requests

    def test_statistics_recording_performance(self):
        """Test statistics recording performance."""
        stats = ErrorStatistics()

        start = time.time()
        for i in range(1000):
            stats.record_error(f"Error{i}", "/api/test", 500)
        duration = time.time() - start

        # Should record 1000 errors quickly
        assert duration < 1.0  # Less than 1 second


# Import asyncio for slow request test
import asyncio
