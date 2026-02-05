"""
Global Error Handling Middleware for Atom Platform

Provides centralized exception handling with:
- Consistent error response format
- Request context logging
- Error statistics tracking
- Debug mode support (stack traces)
- Performance monitoring

Integration:
    from core.error_middleware import ErrorHandlingMiddleware

    app = FastAPI()
    app.add_middleware(ErrorHandlingMiddleware)
"""

from collections import defaultdict
from datetime import datetime
import json
import logging
import os
import time
import traceback
from typing import Any, Callable, Dict, Optional, Tuple
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class ErrorStatistics:
    """
    Track error statistics for monitoring and alerting.

    Thread-safe singleton pattern for tracking error rates.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = True
            cls._instance._reset()
        return cls._instance

    @classmethod
    def _reset(cls):
        """Initialize or reset statistics"""
        cls._instance._error_counts = defaultdict(int)
        cls._instance._endpoint_errors = defaultdict(lambda: defaultdict(int))
        cls._instance._last_24h_errors = []
        cls._instance._total_requests = 0
        cls._instance._total_errors = 0

    def record_error(self, error_type: str, endpoint: str, status_code: int):
        """Record an error occurrence"""
        self._error_counts[error_type] += 1
        self._endpoint_errors[endpoint][error_type] += 1
        self._total_errors += 1

        # Track recent errors (last 100)
        self._last_24h_errors.append({
            "type": error_type,
            "endpoint": endpoint,
            "status_code": status_code,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Keep only last 100 errors
        if len(self._last_24h_errors) > 100:
            self._last_24h_errors.pop(0)

    def record_request(self):
        """Record a request"""
        self._total_requests += 1

    def get_statistics(self) -> Dict[str, Any]:
        """Get current error statistics"""
        return {
            "total_requests": self._total_requests,
            "total_errors": self._total_errors,
            "error_rate": self._total_errors / max(self._total_requests, 1),
            "error_counts": dict(self._error_counts),
            "endpoint_errors": {
                k: dict(v) for k, v in self._endpoint_errors.items()
            },
            "recent_errors": self._last_24h_errors[-10:]  # Last 10 errors
        }

    def reset(self):
        """Reset statistics (useful for testing)"""
        self._reset()


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware for Atom platform.

    Features:
    - Catches all exceptions
    - Formats responses consistently
    - Logs errors with request context
    - Tracks error statistics
    - Returns tracebacks in debug mode only
    - Measures request duration
    """

    def __init__(
        self,
        app: ASGIApp,
        debug_mode: Optional[bool] = None,
        enable_statistics: bool = True,
        log_errors: bool = True
    ):
        """
        Initialize error handling middleware.

        Args:
            app: ASGI application
            debug_mode: Override debug mode (defaults to DEBUG env var)
            enable_statistics: Whether to track error statistics
            log_errors: Whether to log errors
        """
        super().__init__(app)

        # Configuration
        if debug_mode is None:
            self._debug_mode = os.getenv("DEBUG", "False").lower() == "true"
        else:
            self._debug_mode = debug_mode

        self._enable_statistics = enable_statistics
        self._log_errors = log_errors

        # Statistics tracker
        if enable_statistics:
            self._stats = ErrorStatistics()
        else:
            self._stats = None

        # Error tracking
        self._start_time = time.time()

        logger.info(
            f"ErrorHandlingMiddleware initialized (debug={self._debug_mode}, "
            f"statistics={enable_statistics})"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and handle any exceptions.

        Args:
            request: Incoming request
            call_next: Next middleware/route handler

        Returns:
            Response (either normal or error response)
        """
        # Record request start time
        start_time = time.time()

        # Track request count
        if self._stats:
            self._stats.record_request()

        # Extract request context for logging
        request_context = self._extract_request_context(request)

        try:
            # Process request
            response = await call_next(request)

            # Add timing headers
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = f"{process_time:.3f}s"

            # Log slow requests (>1 second)
            if process_time > 1.0:
                logger.warning(
                    f"Slow request detected: {request.method} {request.url.path} "
                    f"took {process_time:.3f}s",
                    extra=request_context
                )

            return response

        except Exception as exc:
            # Handle exception
            process_time = time.time() - start_time

            # Extract error information
            error_info = self._extract_error_info(exc, request_context)

            # Log error
            if self._log_errors:
                self._log_error(exc, request_context, process_time)

            # Track statistics
            if self._stats:
                self._stats.record_error(
                    error_type=error_info["type"],
                    endpoint=request_context["path"],
                    status_code=error_info["status_code"]
                )

            # Create error response
            return self._create_error_response(exc, error_info, request_context)

    def _extract_request_context(self, request: Request) -> Dict[str, Any]:
        """
        Extract relevant context from request for logging.

        Args:
            request: Incoming request

        Returns:
            Dictionary with request context
        """
        context = {
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.url.query),
            "client_host": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }

        # Add user ID if available (from authentication)
        if hasattr(request.state, "user_id"):
            context["user_id"] = request.state.user_id

        return context

    def _extract_error_info(
        self,
        exc: Exception,
        request_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract structured error information.

        Args:
            exc: Exception that occurred
            request_context: Request context

        Returns:
            Dictionary with error information
        """
        # Determine error type and status code
        error_type = type(exc).__name__

        # Map common exceptions to status codes
        status_code_map = {
            "ValueError": status.HTTP_400_BAD_REQUEST,
            "TypeError": status.HTTP_400_BAD_REQUEST,
            "KeyError": status.HTTP_400_BAD_REQUEST,
            "AttributeError": status.HTTP_400_BAD_REQUEST,
            "PermissionError": status.HTTP_403_FORBIDDEN,
            "NotFoundError": status.HTTP_404_NOT_FOUND,
            "HTTPException": getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
        }

        # Get status code
        if hasattr(exc, "status_code"):
            status_code = exc.status_code
        else:
            status_code = status_code_map.get(
                error_type,
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return {
            "type": error_type,
            "message": str(exc),
            "status_code": status_code,
            "is_http_exception": hasattr(exc, "status_code")
        }

    def _log_error(
        self,
        exc: Exception,
        request_context: Dict[str, Any],
        process_time: float
    ):
        """
        Log error with context.

        Args:
            exc: Exception that occurred
            request_context: Request context
            process_time: Request processing time
        """
        # Create log message
        log_message = (
            f"Error in {request_context['method']} {request_context['path']}: "
            f"{type(exc).__name__}: {str(exc)} (took {process_time:.3f}s)"
        )

        # Log with appropriate level
        if hasattr(exc, "status_code") and exc.status_code < 500:
            # Client error (4xx) - log as warning
            logger.warning(log_message, extra=request_context)
        else:
            # Server error (5xx) - log as error with traceback
            logger.error(
                log_message,
                exc_info=True,
                extra=request_context
            )

    def _create_error_response(
        self,
        exc: Exception,
        error_info: Dict[str, Any],
        request_context: Dict[str, Any]
    ) -> JSONResponse:
        """
        Create standardized error response.

        Args:
            exc: Exception that occurred
            error_info: Extracted error information
            request_context: Request context

        Returns:
            JSONResponse with error details
        """
        # Build error response body
        error_body = {
            "success": False,
            "error": {
                "code": self._get_error_code(exc, error_info),
                "message": self._get_error_message(exc, error_info),
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": request_context.get("path", "unknown")
            }
        }

        # Add error details in debug mode
        if self._debug_mode:
            error_body["error"]["type"] = error_info["type"]
            error_body["error"]["stack_trace"] = traceback.format_exc()
            error_body["debug"] = {
                "request": request_context,
                "process_time": f"{time.time() - self._start_time:.3f}s"
            }

        # Add additional context for non-HTTP exceptions
        if not error_info["is_http_exception"]:
            error_body["error"]["details"] = {
                "exception_type": error_info["type"],
                "path": request_context["path"]
            }

        # Determine status code
        status_code = error_info["status_code"]

        return JSONResponse(
            status_code=status_code,
            content=error_body
        )

    def _get_error_code(self, exc: Exception, error_info: Dict[str, Any]) -> str:
        """
        Get standardized error code for exception.

        Args:
            exc: Exception
            error_info: Extracted error information

        Returns:
            Error code string
        """
        # Check if exception has custom error code
        if hasattr(exc, "error_code"):
            return exc.error_code

        # Map exception types to error codes
        error_code_map = {
            "ValueError": "VALIDATION_ERROR",
            "TypeError": "TYPE_ERROR",
            "KeyError": "MISSING_FIELD",
            "AttributeError": "ATTRIBUTE_ERROR",
            "PermissionError": "PERMISSION_DENIED",
            "NotFoundError": "NOT_FOUND",
        }

        return error_code_map.get(
            error_info["type"],
            "INTERNAL_ERROR"
        )

    def _get_error_message(self, exc: Exception, error_info: Dict[str, Any]) -> str:
        """
        Get user-friendly error message.

        Args:
            exc: Exception
            error_info: Extracted error information

        Returns:
            Error message string
        """
        # Use exception's detail if available (FastAPI HTTPException)
        if hasattr(exc, "detail"):
            detail = exc.detail
            if isinstance(detail, dict):
                return detail.get("error", {}).get("message", str(exc))
            return str(detail)

        # Use exception's message
        if str(exc):
            return str(exc)

        # Fallback based on status code
        if error_info["status_code"] == 500:
            return "An internal error occurred"
        elif error_info["status_code"] == 404:
            return "Resource not found"
        elif error_info["status_code"] == 403:
            return "Permission denied"
        elif error_info["status_code"] == 401:
            return "Authentication required"
        else:
            return "An error occurred"

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics.

        Returns:
            Dictionary with error statistics
        """
        if self._stats:
            return self._stats.get_statistics()
        return {"message": "Statistics not enabled"}

    def reset_statistics(self):
        """Reset error statistics"""
        if self._stats:
            self._stats.reset()


# ========================================================================
# Convenience Functions
# ========================================================================

def get_error_statistics() -> Dict[str, Any]:
    """
    Get global error statistics.

    Returns:
        Dictionary with error statistics
    """
    stats = ErrorStatistics()
    return stats.get_statistics()


def reset_error_statistics():
    """Reset global error statistics"""
    stats = ErrorStatistics()
    stats.reset()
