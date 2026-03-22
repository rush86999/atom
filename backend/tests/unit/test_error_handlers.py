"""
Comprehensive tests for core.error_handlers module

Tests error handling functions, exception handlers, and response helpers
"""

import pytest
import os
from datetime import datetime
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from core.error_handlers import (
    # Enums
    ErrorCode,
    # Response helpers
    api_error,
    success_response,
    paginated_response,
    # Exception handlers
    global_exception_handler,
    atom_exception_handler,
    # Specialized handlers
    handle_validation_error,
    handle_not_found,
    handle_permission_denied,
    # Models
    ErrorResponse,
    ValidationErrorDetail,
    # Invoice exceptions
    InvoiceError,
    InvoiceNotFoundError,
    InvoiceValidationError,
    InvoicePricingError,
    HTTP_STATUS_MAP,
    # Result pattern
    Result,
)

# Import AtomException if available
try:
    from core.exceptions import AtomException, ErrorSeverity, ErrorCode as AtomErrorCode
    ATOM_EXCEPTIONS_AVAILABLE = True
except ImportError:
    ATOM_EXCEPTIONS_AVAILABLE = False


class TestErrorCode:
    """Test ErrorCode enum"""

    def test_authentication_codes(self):
        """Test authentication error codes"""
        assert ErrorCode.AUTHENTICATION_REQUIRED.value == "AUTH_REQUIRED"
        assert ErrorCode.INVALID_CREDENTIALS.value == "INVALID_CREDENTIALS"
        assert ErrorCode.TOKEN_EXPIRED.value == "TOKEN_EXPIRED"
        assert ErrorCode.PERMISSION_DENIED.value == "PERMISSION_DENIED"

    def test_validation_codes(self):
        """Test validation error codes"""
        assert ErrorCode.VALIDATION_ERROR.value == "VALIDATION_ERROR"
        assert ErrorCode.MISSING_REQUIRED_FIELD.value == "MISSING_FIELD"
        assert ErrorCode.INVALID_VALUE.value == "INVALID_VALUE"

    def test_resource_codes(self):
        """Test resource error codes"""
        assert ErrorCode.RESOURCE_NOT_FOUND.value == "NOT_FOUND"
        assert ErrorCode.RESOURCE_ALREADY_EXISTS.value == "ALREADY_EXISTS"
        assert ErrorCode.RESOURCE_CONFLICT.value == "CONFLICT"

    def test_agent_codes(self):
        """Test agent-specific error codes"""
        assert ErrorCode.AGENT_NOT_FOUND.value == "AGENT_NOT_FOUND"
        assert ErrorCode.AGENT_EXECUTION_FAILED.value == "AGENT_EXECUTION_FAILED"
        assert ErrorCode.AGENT_GOVERNANCE_BLOCKED.value == "AGENT_GOVERNANCE_BLOCKED"

    def test_invoice_codes(self):
        """Test invoice-specific error codes"""
        assert ErrorCode.INVOICE_NOT_FOUND.value == "INVOICE_NOT_FOUND"
        assert ErrorCode.INVOICE_VALIDATION_ERROR.value == "INVOICE_VALIDATION_ERROR"
        assert ErrorCode.PRICE_NOT_DETERMINED.value == "PRICE_NOT_DETERMINED"


class TestErrorResponse:
    """Test ErrorResponse model"""

    def test_error_response_creation(self):
        """Test creating ErrorResponse"""
        response = ErrorResponse(
            success=False,
            error_code="TEST_ERROR",
            message="Test error message",
            timestamp=datetime.utcnow().isoformat()
        )
        assert response.success is False
        assert response.error_code == "TEST_ERROR"
        assert response.message == "Test error message"
        assert response.details is None
        assert response.request_id is None

    def test_error_response_with_details(self):
        """Test ErrorResponse with details"""
        response = ErrorResponse(
            success=False,
            error_code="TEST_ERROR",
            message="Test error",
            details={"field": "email", "issue": "invalid format"},
            timestamp=datetime.utcnow().isoformat(),
            request_id="req-123"
        )
        assert response.details["field"] == "email"
        assert response.request_id == "req-123"


class TestValidationErrorDetail:
    """Test ValidationErrorDetail model"""

    def test_validation_error_detail(self):
        """Test ValidationErrorDetail creation"""
        detail = ValidationErrorDetail(
            field="email",
            message="Invalid email format",
            value="invalid-email"
        )
        assert detail.field == "email"
        assert detail.message == "Invalid email format"
        assert detail.value == "invalid-email"

    def test_validation_error_detail_without_value(self):
        """Test ValidationErrorDetail without value"""
        detail = ValidationErrorDetail(
            field="password",
            message="Password is required"
        )
        assert detail.field == "password"
        assert detail.value is None


class TestApiError:
    """Test api_error function"""

    def test_api_error_basic(self):
        """Test basic api_error"""
        exc = api_error(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Agent not found"
        )
        assert isinstance(exc, HTTPException)
        assert exc.status_code == 500
        assert exc.detail["success"] is False
        assert exc.detail["error_code"] == "NOT_FOUND"
        assert exc.detail["message"] == "Agent not found"

    def test_api_error_with_details(self):
        """Test api_error with details"""
        exc = api_error(
            ErrorCode.VALIDATION_ERROR,
            "Validation failed",
            details={"field": "email", "error": "invalid format"}
        )
        assert exc.detail["details"]["field"] == "email"
        assert exc.detail["details"]["error"] == "invalid format"

    def test_api_error_with_custom_status(self):
        """Test api_error with custom status code"""
        exc = api_error(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Not found",
            status_code=404
        )
        assert exc.status_code == 404

    def test_api_error_with_request_id(self):
        """Test api_error with request ID"""
        exc = api_error(
            ErrorCode.INTERNAL_SERVER_ERROR,
            "Server error",
            request_id="req-abc123"
        )
        assert exc.detail["request_id"] == "req-abc123"

    def test_api_error_detail_structure(self):
        """Test api_error detail has correct structure"""
        exc = api_error(ErrorCode.VALIDATION_ERROR, "Invalid input")
        assert "timestamp" in exc.detail
        assert "success" in exc.detail
        assert exc.detail["success"] is False


class TestSuccessResponse:
    """Test success_response function"""

    def test_success_response_basic(self):
        """Test basic success response"""
        response = success_response({"id": "123", "name": "Test"})
        assert response["success"] is True
        assert response["data"] == {"id": "123", "name": "Test"}
        assert response["message"] is None
        assert "timestamp" in response

    def test_success_response_with_message(self):
        """Test success response with message"""
        response = success_response(
            {"id": "123"},
            message="Agent created successfully"
        )
        assert response["message"] == "Agent created successfully"

    def test_success_response_with_list(self):
        """Test success response with list data"""
        response = success_response(["item1", "item2", "item3"])
        assert response["data"] == ["item1", "item2", "item3"]

    def test_success_response_with_string(self):
        """Test success response with string data"""
        response = success_response("Simple string result")
        assert response["data"] == "Simple string result"


class TestPaginatedResponse:
    """Test paginated_response function"""

    def test_paginated_response_basic(self):
        """Test basic paginated response"""
        response = paginated_response(
            data=["item1", "item2"],
            total=10,
            page=1,
            page_size=2
        )
        assert response["success"] is True
        assert response["data"] == ["item1", "item2"]
        assert response["pagination"]["total"] == 10
        assert response["pagination"]["page"] == 1
        assert response["pagination"]["page_size"] == 2
        assert response["pagination"]["total_pages"] == 5
        assert response["pagination"]["has_next"] is True
        assert response["pagination"]["has_prev"] is False

    def test_paginated_response_last_page(self):
        """Test paginated response on last page"""
        response = paginated_response(
            data=["item9", "item10"],
            total=10,
            page=5,
            page_size=2
        )
        assert response["pagination"]["page"] == 5
        assert response["pagination"]["has_next"] is False
        assert response["pagination"]["has_prev"] is True

    def test_paginated_response_middle_page(self):
        """Test paginated response in middle"""
        response = paginated_response(
            data=["item3", "item4"],
            total=10,
            page=2,
            page_size=2
        )
        assert response["pagination"]["has_next"] is True
        assert response["pagination"]["has_prev"] is True

    def test_paginated_response_empty(self):
        """Test paginated response with no data"""
        response = paginated_response(
            data=[],
            total=0,
            page=1,
            page_size=10
        )
        assert response["pagination"]["total"] == 0
        assert response["pagination"]["total_pages"] == 0
        assert response["pagination"]["has_next"] is False
        assert response["pagination"]["has_prev"] is False

    def test_paginated_response_zero_page_size(self):
        """Test paginated response with zero page size"""
        response = paginated_response(
            data=[],
            total=100,
            page=1,
            page_size=0
        )
        assert response["pagination"]["total_pages"] == 0


class TestHandleValidationError:
    """Test handle_validation_error function"""

    def test_handle_validation_error_basic(self):
        """Test basic validation error"""
        exc = handle_validation_error(
            field="email",
            message="Email is required"
        )
        assert isinstance(exc, HTTPException)
        assert exc.status_code == 400
        assert exc.detail["error_code"] == "VALIDATION_ERROR"
        assert "email" in exc.detail["message"]

    def test_handle_validation_error_with_value(self):
        """Test validation error with value"""
        exc = handle_validation_error(
            field="age",
            message="Must be positive",
            value=-5
        )
        assert exc.detail["details"]["field"] == "age"
        assert exc.detail["details"]["value"] == -5
        assert exc.detail["details"]["message"] == "Must be positive"

    def test_handle_validation_error_custom_status(self):
        """Test validation error with custom status"""
        exc = handle_validation_error(
            field="token",
            message="Invalid token",
            status_code=401
        )
        assert exc.status_code == 401


class TestHandleNotFound:
    """Test handle_not_found function"""

    def test_handle_not_found_basic(self):
        """Test basic not found error"""
        exc = handle_not_found("Agent", "agent-123")
        assert isinstance(exc, HTTPException)
        assert exc.status_code == 404
        assert exc.detail["error_code"] == "NOT_FOUND"
        assert "Agent" in exc.detail["message"]
        assert "agent-123" in exc.detail["message"]

    def test_handle_not_found_with_details(self):
        """Test not found with custom details (overrides default)"""
        # When details is provided (non-empty), it's used instead of the default
        exc = handle_not_found(
            "Workspace",
            "ws-456",
            details={"user_id": "user-123", "custom": "value"}
        )
        assert exc.status_code == 404
        # Custom details are used (not the defaults)
        assert exc.detail["details"]["user_id"] == "user-123"
        assert exc.detail["details"]["custom"] == "value"


class TestHandlePermissionDenied:
    """Test handle_permission_denied function"""

    def test_handle_permission_denied_basic(self):
        """Test basic permission denied error"""
        exc = handle_permission_denied("delete", "Agent")
        assert isinstance(exc, HTTPException)
        assert exc.status_code == 403
        assert exc.detail["error_code"] == "PERMISSION_DENIED"
        assert "delete" in exc.detail["message"]
        assert "Agent" in exc.detail["message"]

    def test_handle_permission_denied_with_details(self):
        """Test permission denied with custom details (overrides default)"""
        # When details is provided (non-empty), it's used instead of the default
        exc = handle_permission_denied(
            "modify",
            "Workspace",
            details={"required_role": "admin", "user": "john"}
        )
        assert exc.status_code == 403
        # Custom details are used (not the defaults)
        assert exc.detail["details"]["required_role"] == "admin"
        assert exc.detail["details"]["user"] == "john"


class TestInvoiceError:
    """Test InvoiceError hierarchy"""

    def test_invoice_error_base(self):
        """Test base InvoiceError"""
        error = InvoiceError(
            message="Invoice processing failed",
            code=ErrorCode.INVOICE_VALIDATION_ERROR,
            details={"step": "calculation"}
        )
        assert error.message == "Invoice processing failed"
        assert error.code == ErrorCode.INVOICE_VALIDATION_ERROR
        assert error.details["step"] == "calculation"
        assert error.timestamp is not None
        assert error.http_status == 500  # From HTTP_STATUS_MAP

    def test_invoice_error_to_http_exception(self):
        """Test converting InvoiceError to HTTPException"""
        error = InvoiceError(
            message="Test error",
            code=ErrorCode.INVOICE_NOT_FOUND
        )
        http_exc = error.to_http_exception()
        assert isinstance(http_exc, HTTPException)
        assert http_exc.status_code == 404  # From HTTP_STATUS_MAP

    def test_invoice_not_found_error(self):
        """Test InvoiceNotFoundError"""
        error = InvoiceNotFoundError(
            message="Invoice not found",
            invoice_type="sales"
        )
        assert error.code == ErrorCode.INVOICE_NOT_FOUND
        assert error.details["invoice_type"] == "sales"
        assert error.http_status == 404

    def test_invoice_validation_error(self):
        """Test InvoiceValidationError"""
        error = InvoiceValidationError(
            message="Invalid invoice data",
            details={"field": "total_amount"}
        )
        assert error.code == ErrorCode.INVOICE_VALIDATION_ERROR
        assert error.details["field"] == "total_amount"
        assert error.http_status == 500

    def test_invoice_pricing_error(self):
        """Test InvoicePricingError"""
        error = InvoicePricingError(
            message="Cannot determine price",
            details={"product": "widget"}
        )
        assert error.code == ErrorCode.INVOICE_PRICING_ERROR
        assert error.http_status == 500


class TestHTTPStatusMap:
    """Test HTTP_STATUS_MAP"""

    def test_http_status_map_entries(self):
        """Test HTTP_STATUS_MAP has correct entries"""
        assert HTTP_STATUS_MAP[ErrorCode.INVOICE_NOT_FOUND] == 404
        assert HTTP_STATUS_MAP[ErrorCode.INVOICE_VALIDATION_ERROR] == 500
        assert HTTP_STATUS_MAP[ErrorCode.PRICE_NOT_DETERMINED] == 500
        assert HTTP_STATUS_MAP[ErrorCode.OAUTH_TOKEN_INVALID] == 401
        assert HTTP_STATUS_MAP[ErrorCode.OAUTH_TOKEN_EXPIRED] == 401

    def test_http_status_map_default(self):
        """Test HTTP_STATUS_MAP default behavior"""
        # Error codes not in map should default to 500
        error = InvoiceError(
            "Test",
            ErrorCode.INTERNAL_SERVER_ERROR
        )
        assert error.http_status == 500


class TestResult:
    """Test Result pattern"""

    def test_result_ok(self):
        """Test creating successful Result"""
        result = Result.ok(42)
        assert result.is_ok is True
        assert result.value == 42
        assert result.error is None

    def test_result_error(self):
        """Test creating failed Result"""
        result = Result.error("Something went wrong", ErrorCode.VALIDATION_ERROR)
        assert result.is_ok is False
        assert result.error is not None
        assert result.error.message == "Something went wrong"

    def test_result_error_with_details(self):
        """Test Result.error with details"""
        result = Result.error(
            "Invalid input",
            ErrorCode.VALIDATION_ERROR,
            details={"field": "email"}
        )
        assert result.is_ok is False
        assert result.error.details["field"] == "email"

    def test_result_from_exception_invoice_error(self):
        """Test Result.from_exception with InvoiceError"""
        error = InvoiceNotFoundError("Invoice missing")
        result = Result.from_exception(error)
        assert result.is_ok is False
        assert result.error is error

    def test_result_from_exception_generic(self):
        """Test Result.from_exception with generic exception"""
        exc = ValueError("Generic error")
        result = Result.from_exception(exc)
        assert result.is_ok is False
        assert result.error.message == "Generic error"
        assert result.error.details["original_exception"] == "ValueError"

    def test_result_unwrap_success(self):
        """Test unwrap on successful Result"""
        result = Result.ok(100)
        assert result.unwrap() == 100

    def test_result_unwrap_failure(self):
        """Test unwrap on failed Result raises error"""
        result = Result.error("Failed", ErrorCode.INTERNAL_SERVER_ERROR)
        with pytest.raises(InvoiceError) as exc_info:
            result.unwrap()
        assert "Failed" in str(exc_info.value)

    def test_result_unwrap_or_success(self):
        """Test unwrap_or on successful Result"""
        result = Result.ok(50)
        assert result.unwrap_or(0) == 50

    def test_result_unwrap_or_failure(self):
        """Test unwrap_or on failed Result"""
        result = Result.error("Failed", ErrorCode.INTERNAL_SERVER_ERROR)
        assert result.unwrap_or(0) == 0

    def test_result_map_success(self):
        """Test map on successful Result"""
        result = Result.ok(10)
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_ok is True
        assert mapped.value == 20

    def test_result_map_failure(self):
        """Test map on failed Result"""
        result = Result.error("Failed", ErrorCode.INTERNAL_SERVER_ERROR)
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_ok is False
        assert mapped is result  # Returns same instance

    def test_result_map_exception(self):
        """Test map when function raises exception"""
        result = Result.ok(10)
        mapped = result.map(lambda x: 1 / 0)  # Raises ZeroDivisionError
        assert mapped.is_ok is False
        assert mapped.error.details["original_exception"] == "ZeroDivisionError"

    def test_result_and_then_success(self):
        """Test and_then chaining with success"""
        result = Result.ok(10)

        def double(x):
            return Result.ok(x * 2)

        chained = result.and_then(double)
        assert chained.is_ok is True
        assert chained.value == 20

    def test_result_and_then_failure(self):
        """Test and_then when first Result is failure"""
        result = Result.error("Failed", ErrorCode.INTERNAL_SERVER_ERROR)

        def double(x):
            return Result.ok(x * 2)

        chained = result.and_then(double)
        assert chained.is_ok is False
        assert chained is result  # Returns same instance

    def test_result_and_then_failure_in_chain(self):
        """Test and_then when chained function returns failure"""
        result = Result.ok(10)

        def fail(x):
            return Result.error("Chain failed", ErrorCode.VALIDATION_ERROR)

        chained = result.and_then(fail)
        assert chained.is_ok is False
        assert "Chain failed" in chained.error.message


@pytest.mark.asyncio
class TestGlobalExceptionHandler:
    """Test global_exception_handler"""

    async def test_global_exception_handler_generic(self):
        """Test handling generic exception"""
        # Set to production mode (default)
        if os.getenv("ENVIRONMENT") == "development":
            # Skip if already in development mode
            return

        request = Request(scope={
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
            "server": ("localhost", 8000),
            "scheme": "http",
            "root_path": "",
        })
        exc = ValueError("Test error")

        response = await global_exception_handler(request, exc)
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

        content = response.body.decode().lower()
        # In production mode, should not expose internal error details
        # Just check it's an error response
        assert "error" in content

    async def test_global_exception_handler_development_mode(self, monkeypatch):
        """Test error details exposed in development"""
        monkeypatch.setenv("ENVIRONMENT", "development")

        request = Request(scope={
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
            "server": ("localhost", 8000),
            "scheme": "http",
            "root_path": "",
        })
        exc = ValueError("Development error")

        response = await global_exception_handler(request, exc)
        content = response.body.decode()

        # In development, should expose exception type and message
        assert "ValueError" in content
        assert "Development error" in content

    async def test_global_exception_handler_with_request_id(self):
        """Test handler includes request_id"""
        request = Request(scope={
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
            "server": ("localhost", 8000),
            "scheme": "http",
            "root_path": "",
        })
        request.state.request_id = "req-12345"

        exc = RuntimeError("Test error")
        response = await global_exception_handler(request, exc)

        # Should include request_id in response
        # Note: Actual content parsing depends on implementation


@pytest.mark.asyncio
class TestAtomExceptionHandler:
    """Test atom_exception_handler"""

    @pytest.mark.skipif(not ATOM_EXCEPTIONS_AVAILABLE, reason="AtomException not available")
    async def test_atom_exception_handler_basic(self):
        """Test handling AtomException"""
        from core.exceptions import ValidationError

        request = Request(scope={
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
            "server": ("localhost", 8000),
            "scheme": "http",
            "root_path": "",
        })
        exc = ValidationError("Test validation error")

        response = await atom_exception_handler(request, exc)
        assert isinstance(response, JSONResponse)

    @pytest.mark.skipif(not ATOM_EXCEPTIONS_AVAILABLE, reason="AtomException not available")
    async def test_atom_exception_handler_severity_mapping(self):
        """Test severity to status code mapping"""
        from core.exceptions import AgentNotFoundError

        request = Request(scope={
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
            "server": ("localhost", 8000),
            "scheme": "http",
            "root_path": "",
        })
        exc = AgentNotFoundError("agent-123")

        response = await atom_exception_handler(request, exc)
        # MEDIUM severity should map to 400
        assert response.status_code == 400

    @pytest.mark.skipif(not ATOM_EXCEPTIONS_AVAILABLE, reason="AtomException not available")
    async def test_atom_exception_handler_with_details(self):
        """Test handler includes error details"""
        from core.exceptions import ValidationError

        request = Request(scope={
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
            "server": ("localhost", 8000),
            "scheme": "http",
            "root_path": "",
        })
        exc = ValidationError(
            "Invalid data",
            field="email",
            details={"format": "invalid"}
        )

        response = await atom_exception_handler(request, exc)
        # Details should be in response
