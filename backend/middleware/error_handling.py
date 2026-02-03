"""
Comprehensive Error Handling Middleware
Provides detailed error responses and logging for production use
"""

import json
import logging
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Configure error logging
error_logger = logging.getLogger("atom.errors")
performance_logger = logging.getLogger("atom.performance")

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Comprehensive error handling middleware"""

    def __init__(self, app, debug: bool = False):
        super().__init__(app)
        self.debug = debug
        self.setup_logging()

    def setup_logging(self):
        """Setup error logging configuration"""
        # Create file handler for errors
        error_handler = logging.FileHandler("logs/errors.log")
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        error_handler.setFormatter(error_formatter)
        error_logger.addHandler(error_handler)

        # Create performance handler
        perf_handler = logging.FileHandler("logs/performance.log")
        perf_handler.setLevel(logging.INFO)
        perf_handler.setFormatter(error_formatter)
        performance_logger.addHandler(perf_handler)

    async def dispatch(self, request: Request, call_next):
        """Process request and handle any errors"""
        # Generate request ID for tracking
        request_id = str(uuid.uuid4())
        start_time = datetime.now()

        # Add request ID to request state
        request.state.request_id = request_id

        try:
            # Process the request
            response = await call_next(request)

            # Log performance metrics
            duration = (datetime.now() - start_time).total_seconds()
            self.log_performance(request, response, duration, request_id)

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except HTTPException as e:
            # Handle HTTP exceptions (client errors)
            return await self.handle_http_exception(e, request, request_id, start_time)

        except Exception as e:
            # Handle unexpected errors (server errors)
            return await self.handle_server_error(e, request, request_id, start_time)

    async def handle_http_exception(
        self,
        exception: HTTPException,
        request: Request,
        request_id: str,
        start_time: datetime
    ) -> JSONResponse:
        """Handle HTTP exceptions (4xx errors)"""

        error_response = {
            "error": {
                "type": "http_error",
                "code": exception.status_code,
                "message": exception.detail,
                "request_id": request_id,
                "timestamp": datetime.now().isoformat(),
                "path": str(request.url.path),
                "method": request.method
            }
        }

        # Add debug information in development
        if self.debug:
            error_response["debug"] = {
                "headers": dict(request.headers),
                "query_params": dict(request.query_params)
            }

        # Log the error
        error_logger.warning(
            f"HTTP {exception.status_code} - {request.method} {request.url.path} - "
            f"{exception.detail} - Request ID: {request_id}"
        )

        return JSONResponse(
            status_code=exception.status_code,
            content=error_response
        )

    async def handle_server_error(
        self,
        exception: Exception,
        request: Request,
        request_id: str,
        start_time: datetime
    ) -> JSONResponse:
        """Handle server errors (5xx errors)"""

        # Get full traceback
        error_traceback = traceback.format_exc()

        # Log the full error
        error_logger.error(
            f"Server Error - {request.method} {request.url.path} - "
            f"{str(exception)} - Request ID: {request_id}\n"
            f"Traceback:\n{error_traceback}"
        )

        # Create user-friendly error response
        error_response = {
            "error": {
                "type": "server_error",
                "code": 500,
                "message": "Internal server error occurred",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat(),
                "path": str(request.url.path),
                "method": request.method
            }
        }

        # Add debug information in development
        if self.debug:
            error_response["debug"] = {
                "exception": str(exception),
                "traceback": error_traceback.split('\n'),
                "headers": dict(request.headers)
            }

        return JSONResponse(
            status_code=500,
            content=error_response
        )

    def log_performance(
        self,
        request: Request,
        response: Response,
        duration: float,
        request_id: str
    ):
        """Log performance metrics"""
        # Log slow requests (> 2 seconds)
        if duration > 2.0:
            performance_logger.warning(
                f"Slow Request - {request.method} {request.url.path} - "
                f"{duration:.3f}s - Status: {response.status_code} - "
                f"Request ID: {request_id}"
            )
        else:
            performance_logger.info(
                f"Request - {request.method} {request.url.path} - "
                f"{duration:.3f}s - Status: {response.status_code} - "
                f"Request ID: {request_id}"
            )


class ValidationErrorMiddleware(BaseHTTPMiddleware):
    """Middleware for handling Pydantic validation errors"""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            # Check if it's a validation error
            if "validation" in str(e).lower() or "pydantic" in str(e).lower():
                return self.handle_validation_error(e, request)
            else:
                # Let other middleware handle it
                raise

    def handle_validation_error(self, exception: Exception, request: Request) -> JSONResponse:
        """Handle validation errors with detailed feedback"""

        # Try to extract validation details
        validation_errors = []

        try:
            # Parse validation error from exception message
            error_str = str(exception)

            # Common patterns for validation errors
            if "field required" in error_str.lower():
                validation_errors.append({
                    "field": "unknown",
                    "message": "Required field is missing",
                    "type": "missing"
                })

            # Add more validation error parsing as needed
            # This is a simplified version for the MVP

        except:
            pass

        error_response = {
            "error": {
                "type": "validation_error",
                "code": 422,
                "message": "Invalid request data",
                "timestamp": datetime.now().isoformat(),
                "path": str(request.url.path),
                "method": request.method,
                "validation_errors": validation_errors
            }
        }

        return JSONResponse(
            status_code=422,
            content=error_response
        )


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """Simple circuit breaker for critical endpoints"""

    def __init__(self, app, failure_threshold: int = 5, timeout: int = 60):
        super().__init__(app)
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = {}
        self.last_failure_time = {}

    async def dispatch(self, request: Request, call_next):
        endpoint = f"{request.method}_{request.url.path}"

        # Check if circuit is open
        if self.is_circuit_open(endpoint):
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "type": "service_unavailable",
                        "message": "Service temporarily unavailable. Please try again later.",
                        "retry_after": self.timeout
                    }
                }
            )

        try:
            response = await call_next(request)

            # Reset failure count on success
            if endpoint in self.failure_count:
                del self.failure_count[endpoint]
            if endpoint in self.last_failure_time:
                del self.last_failure_time[endpoint]

            return response

        except Exception as e:
            # Increment failure count
            self.failure_count[endpoint] = self.failure_count.get(endpoint, 0) + 1
            self.last_failure_time[endpoint] = datetime.now()

            # Log circuit breaker activation
            if self.failure_count[endpoint] >= self.failure_threshold:
                error_logger.critical(
                    f"Circuit breaker opened for endpoint: {endpoint} - "
                    f"Failure count: {self.failure_count[endpoint]}"
                )

            raise


def setup_error_middleware(app, debug: bool = False):
    """Setup all error handling middleware"""
    # Add error handling middleware (last to first)
    app.add_middleware(ValidationErrorMiddleware)
    app.add_middleware(CircuitBreakerMiddleware)
    app.add_middleware(ErrorHandlingMiddleware, debug=debug)

    # Create logs directory if it doesn't exist
    import os
    os.makedirs("logs", exist_ok=True)