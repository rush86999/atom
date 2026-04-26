"""
Test Suite for Error Handlers

Tests for core.error_handlers module (628 lines)
- Error response creation and formatting
- Global exception handling
- Validation error handling
- Specialized exception classes (InvoiceError)
- Result pattern for operation outcomes

Target Tests: 20-25
Target Coverage: 25-30%
"""

from datetime import datetime
from unittest.mock import Mock, patch
import pytest

from core.error_handlers import (
    ErrorCode,
    ErrorResponse,
    ValidationErrorDetail,
    api_error,
    success_response,
    paginated_response,
    handle_validation_error,
    handle_not_found,
    handle_permission_denied,
    InvoiceError,
    InvoiceNotFoundError,
    InvoiceValidationError,
    InvoicePricingError,
    Result,
    HTTP_STATUS_MAP
)


class TestErrorCodeEnum:
    """Test ErrorCode enum values."""

    def test_error_code_authentication_codes(self):
        """ErrorCode has authentication-related error codes."""
        assert ErrorCode.AUTHENTICATION_REQUIRED == "AUTH_REQUIRED"
        assert ErrorCode.INVALID_CREDENTIALS == "INVALID_CREDENTIALS"
        assert ErrorCode.TOKEN_EXPIRED == "TOKEN_EXPIRED"
        assert ErrorCode.PERMISSION_DENIED == "PERMISSION_DENIED"

    def test_error_code_validation_codes(self):
        """ErrorCode has validation-related error codes."""
        assert ErrorCode.VALIDATION_ERROR == "VALIDATION_ERROR"
        assert ErrorCode.MISSING_REQUIRED_FIELD == "MISSING_FIELD"
        assert ErrorCode.INVALID_VALUE == "INVALID_VALUE"

    def test_error_code_resource_codes(self):
        """ErrorCode has resource-related error codes."""
        assert ErrorCode.RESOURCE_NOT_FOUND == "NOT_FOUND"
        assert ErrorCode.RESOURCE_ALREADY_EXISTS == "ALREADY_EXISTS"
        assert ErrorCode.RESOURCE_CONFLICT == "CONFLICT"

    def test_error_code_agent_specific_codes(self):
        """ErrorCode has agent-specific error codes."""
        assert ErrorCode.AGENT_NOT_FOUND == "AGENT_NOT_FOUND"
        assert ErrorCode.AGENT_EXECUTION_FAILED == "AGENT_EXECUTION_FAILED"
        assert ErrorCode.AGENT_GOVERNANCE_BLOCKED == "AGENT_GOVERNANCE_BLOCKED"


class TestErrorResponseModel:
    """Test ErrorResponse Pydantic model."""

    def test_error_response_creation(self):
        """ErrorResponse can be created with required fields."""
        response = ErrorResponse(
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Resource not found",
            timestamp=datetime.utcnow().isoformat()
        )

        assert response.success is False
        assert response.error_code == "NOT_FOUND"
        assert response.message == "Resource not found"

    def test_error_response_with_details(self):
        """ErrorResponse can include additional details."""
        response = ErrorResponse(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Validation failed",
            details={"field": "name", "error": "required"},
            timestamp=datetime.utcnow().isoformat(),
            request_id="req-123"
        )

        assert response.details is not None
        assert response.details["field"] == "name"
        assert response.request_id == "req-123"


class TestApiError:
    """Test api_error function."""

    def test_api_error_creates_http_exception(self):
        """api_error creates HTTPException with standardized format."""
        error = api_error(
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Agent not found",
            details={"agent_id": "abc123"},
            status_code=404
        )

        assert error.status_code == 404
        assert "success" in error.detail
        assert error.detail["success"] is False
        assert error.detail["error_code"] == "NOT_FOUND"

    def test_api_error_with_request_id(self):
        """api_error includes request_id when provided."""
        error = api_error(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Invalid input",
            request_id="req-456"
        )

        assert error.detail["request_id"] == "req-456"

    def test_api_error_default_status_code(self):
        """api_error defaults to 500 status code."""
        error = api_error(
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
            message="Internal error"
        )

        assert error.status_code == 500


class TestSuccessResponse:
    """Test success_response function."""

    def test_success_response_with_data(self):
        """success_response creates standardized success response."""
        response = success_response(
            data={"agent_id": "abc123", "name": "Test Agent"},
            message="Agent created successfully"
        )

        assert response["success"] is True
        assert response["data"]["agent_id"] == "abc123"
        assert response["message"] == "Agent created successfully"
        assert "timestamp" in response

    def test_success_response_with_list_data(self):
        """success_response handles list data correctly."""
        response = success_response(
            data=["agent1", "agent2", "agent3"],
            message="Retrieved all agents"
        )

        assert response["success"] is True
        assert len(response["data"]) == 3

    def test_success_response_without_message(self):
        """success_response works without optional message."""
        response = success_response(data={"key": "value"})

        assert response["success"] is True
        assert response["data"]["key"] == "value"
        assert response.get("message") is None


class TestPaginatedResponse:
    """Test paginated_response function."""

    def test_paginated_response_calculates_total_pages(self):
        """paginated_response calculates total_pages correctly."""
        response = paginated_response(
            data=["item1", "item2"],
            total=10,
            page=1,
            page_size=2
        )

        assert response["pagination"]["total"] == 10
        assert response["pagination"]["page"] == 1
        assert response["pagination"]["page_size"] == 2
        assert response["pagination"]["total_pages"] == 5

    def test_paginated_response_has_next_and_prev(self):
        """paginated_response calculates has_next and has_prev flags."""
        response = paginated_response(
            data=["item1"],
            total=10,
            page=2,
            page_size=3
        )

        assert response["pagination"]["has_next"] is True
        assert response["pagination"]["has_prev"] is True

    def test_paginated_response_first_page(self):
        """paginated_response correctly identifies first page."""
        response = paginated_response(
            data=["item1"],
            total=10,
            page=1,
            page_size=3
        )

        assert response["pagination"]["has_prev"] is False
        assert response["pagination"]["has_next"] is True


class TestValidationErrorHandler:
    """Test handle_validation_error function."""

    def test_handle_validation_error_creates_http_exception(self):
        """handle_validation_error creates HTTPException with validation details."""
        error = handle_validation_error(
            field="agent_name",
            message="Agent name is required",
            value=None
        )

        assert error.status_code == 400
        assert error.detail["error_code"] == "VALIDATION_ERROR"

    def test_handle_validation_error_includes_field_details(self):
        """handle_validation_error includes field information in details."""
        error = handle_validation_error(
            field="email",
            message="Invalid email format",
            value="invalid-email"
        )

        details = error.detail["details"]
        assert details["field"] == "email"
        assert details["message"] == "Invalid email format"
        assert details["value"] == "invalid-email"


class TestNotFoundHandler:
    """Test handle_not_found function."""

    def test_handle_not_found_creates_404_error(self):
        """handle_not_found creates 404 HTTPException."""
        error = handle_not_found(
            resource_type="Agent",
            resource_id="agent-123"
        )

        assert error.status_code == 404
        assert error.detail["error_code"] == "NOT_FOUND"

    def test_handle_not_found_includes_resource_details(self):
        """handle_not_found includes resource type and ID in details."""
        error = handle_not_found(
            resource_type="Workspace",
            resource_id="workspace-456",
            details={"workspace_name": "Test Workspace"}
        )

        details = error.detail["details"]
        assert details["resource_type"] == "Workspace"
        assert details["resource_id"] == "workspace-456"


class TestPermissionDeniedHandler:
    """Test handle_permission_denied function."""

    def test_handle_permission_denied_creates_403_error(self):
        """handle_permission_denied creates 403 HTTPException."""
        error = handle_permission_denied(
            action="delete",
            resource_type="Agent"
        )

        assert error.status_code == 403
        assert error.detail["error_code"] == "PERMISSION_DENIED"

    def test_handle_permission_denied_includes_action_details(self):
        """handle_permission_denied includes action in details."""
        error = handle_permission_denied(
            action="modify",
            resource_type="Workspace"
        )

        details = error.detail["details"]
        assert details["action"] == "modify"
        assert details["resource_type"] == "Workspace"


class TestSpecializedExceptions:
    """Test specialized exception classes."""

    def test_invoice_error_base_class(self):
        """InvoiceError can be instantiated with error details."""
        error = InvoiceError(
            message="Invoice processing failed",
            code=ErrorCode.INVOICE_VALIDATION_ERROR,
            details={"invoice_id": "inv-123"}
        )

        assert error.message == "Invoice processing failed"
        assert error.code == ErrorCode.INVOICE_VALIDATION_ERROR
        assert error.details["invoice_id"] == "inv-123"
        assert error.http_status == 500  # From HTTP_STATUS_MAP

    def test_invoice_not_found_error(self):
        """InvoiceNotFoundError can be instantiated."""
        error = InvoiceNotFoundError(
            message="Invoice not found",
            invoice_type="appointment"
        )

        assert error.code == ErrorCode.INVOICE_NOT_FOUND
        assert error.details["invoice_type"] == "appointment"
        assert error.http_status == 404

    def test_invoice_validation_error(self):
        """InvoiceValidationError can be instantiated."""
        error = InvoiceValidationError(
            message="Invalid invoice data",
            details={"field": "amount", "error": "must be positive"}
        )

        assert error.code == ErrorCode.INVOICE_VALIDATION_ERROR
        assert error.http_status == 500

    def test_invoice_pricing_error(self):
        """InvoicePricingError can be instantiated."""
        error = InvoicePricingError(
            message="Cannot determine pricing",
            details={"service_type": "unknown"}
        )

        assert error.code == ErrorCode.INVOICE_PRICING_ERROR
        assert error.http_status == 500

    def test_invoice_error_to_http_exception(self):
        """InvoiceError can convert to HTTPException."""
        invoice_error = InvoiceNotFoundError(
            message="Invoice not found",
            invoice_type="order"
        )

        http_error = invoice_error.to_http_exception()

        assert http_error.status_code == 404
        assert http_error.detail["error_code"] == "INVOICE_NOT_FOUND"

    def test_http_status_map_contains_all_invoice_errors(self):
        """HTTP_STATUS_MAP has entries for all invoice error codes."""
        expected_mappings = {
            ErrorCode.INVOICE_NOT_FOUND: 404,
            ErrorCode.INVOICE_VALIDATION_ERROR: 500,
            ErrorCode.INVOICE_PRICING_ERROR: 500,
            ErrorCode.APPOINTMENT_NOT_FOUND: 404,
            ErrorCode.APPOINTMENT_INVALID_STATUS: 500,
            ErrorCode.ORDER_NOT_FOUND: 404,
            ErrorCode.TASK_NOT_FOUND: 404,
            ErrorCode.MILESTONE_NOT_FOUND: 404,
            ErrorCode.PROJECT_NOT_FOUND: 404,
            ErrorCode.ENTITY_NOT_FOUND: 404,
            ErrorCode.PRICE_NOT_DETERMINED: 500,
            ErrorCode.OAUTH_TOKEN_INVALID: 401,
            ErrorCode.OAUTH_TOKEN_EXPIRED: 401,
        }

        for code, expected_status in expected_mappings.items():
            assert HTTP_STATUS_MAP[code] == expected_status


class TestResultPattern:
    """Test Result pattern for operation outcomes."""

    def test_result_ok_creates_success_result(self):
        """Result.ok creates a successful result."""
        result = Result.ok(value=42)

        assert result.is_ok is True
        assert result.value == 42
        assert result.error is None

    def test_result_error_creates_failure_result(self):
        """Result.error creates a failed result."""
        result = Result.error(
            message="Operation failed",
            code=ErrorCode.INTERNAL_SERVER_ERROR
        )

        assert result.is_ok is False
        assert result.error is not None
        assert result.error.message == "Operation failed"

    def test_result_from_exception(self):
        """Result.from_exception creates result from exception."""
        exc = Exception("Something went wrong")
        result = Result.from_exception(exc)

        assert result.is_ok is False
        assert "Something went wrong" in result.error.message

    def test_result_from_invoice_exception(self):
        """Result.from_exception preserves InvoiceError."""
        invoice_error = InvoiceNotFoundError(
            message="Invoice not found",
            invoice_type="order"
        )
        result = Result.from_exception(invoice_error)

        assert result.is_ok is False
        assert result.error == invoice_error

    def test_result_unwrap_returns_value_on_success(self):
        """Result.unwrap returns value when result is ok."""
        result = Result.ok(value=100)

        value = result.unwrap()

        assert value == 100

    def test_result_unwrap_raises_error_on_failure(self):
        """Result.unwrap raises error when result is failure."""
        result = Result.error(
            message="Failed",
            code=ErrorCode.INTERNAL_SERVER_ERROR
        )

        with pytest.raises(InvoiceError):
            result.unwrap()

    def test_result_unwrap_or_returns_default_on_failure(self):
        """Result.unwrap_or returns default value when result is failure."""
        result = Result.error(
            message="Failed",
            code=ErrorCode.INTERNAL_SERVER_ERROR
        )

        value = result.unwrap_or(default=0)

        assert value == 0

    def test_result_map_transforms_value_on_success(self):
        """Result.map transforms value when result is ok."""
        result = Result.ok(value=10)

        mapped = result.map(lambda x: x * 2)

        assert mapped.is_ok is True
        assert mapped.value == 20

    def test_result_map_preserves_error_on_failure(self):
        """Result.map preserves error when result is failure."""
        result = Result.error(
            message="Failed",
            code=ErrorCode.INTERNAL_SERVER_ERROR
        )

        mapped = result.map(lambda x: x * 2)

        assert mapped.is_ok is False

    def test_result_and_then_chains_operations(self):
        """Result.and_then chains operations that return Results."""
        def divide_by_two(x: int) -> Result[float]:
            if x == 0:
                return Result.error("Division by zero", ErrorCode.VALIDATION_ERROR)
            return Result.ok(x / 2)

        result1 = Result.ok(value=10)
        result2 = result1.and_then(divide_by_two)

        assert result2.is_ok is True
        assert result2.value == 5.0

    def test_result_and_then_stops_on_first_failure(self):
        """Result.and_then stops chain on first failure."""
        def divide_by_zero(x: int) -> Result[float]:
            return Result.error("Division by zero", ErrorCode.VALIDATION_ERROR)

        result1 = Result.ok(value=10)
        result2 = result1.and_then(divide_by_zero)

        assert result2.is_ok is False
        assert result2.error.message == "Division by zero"
