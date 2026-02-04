"""
Standardized Error Handling for Atom Platform

Provides consistent error responses and exception handling across all API endpoints.
Integrates with core/exceptions.py AtomException hierarchy.
"""

import logging
import traceback
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Import AtomException hierarchy for unified error handling
try:
    from core.exceptions import AtomException, ErrorCode as AtomErrorCode
    ATOM_EXCEPTIONS_AVAILABLE = True
except ImportError:
    ATOM_EXCEPTIONS_AVAILABLE = False
    logger.warning("core.exceptions.AtomException not available, using legacy error handling")


class ErrorCode(str, Enum):
    """Standardized error codes for Atom Platform"""

    # Authentication & Authorization
    AUTHENTICATION_REQUIRED = "AUTH_REQUIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"

    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    MISSING_REQUIRED_FIELD = "MISSING_FIELD"
    INVALID_VALUE = "INVALID_VALUE"

    # Resources
    RESOURCE_NOT_FOUND = "NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "ALREADY_EXISTS"
    RESOURCE_CONFLICT = "CONFLICT"

    # Business Logic
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"

    # External Services
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    EXTERNAL_SERVICE_TIMEOUT = "EXTERNAL_SERVICE_TIMEOUT"

    # System
    INTERNAL_SERVER_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"

    # Agent-Specific
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    AGENT_EXECUTION_FAILED = "AGENT_EXECUTION_FAILED"
    AGENT_GOVERNANCE_BLOCKED = "AGENT_GOVERNANCE_BLOCKED"
    AGENT_MATURITY_INSUFFICIENT = "AGENT_MATURITY_INSUFFICIENT"

    # Canvas-Specific
    CANVAS_NOT_FOUND = "CANVAS_NOT_FOUND"
    INVALID_COMPONENT_TYPE = "INVALID_COMPONENT_TYPE"

    # Invoice-Specific
    INVOICE_NOT_FOUND = "INVOICE_NOT_FOUND"
    INVOICE_VALIDATION_ERROR = "INVOICE_VALIDATION_ERROR"
    INVOICE_PRICING_ERROR = "INVOICE_PRICING_ERROR"
    APPOINTMENT_NOT_FOUND = "APPOINTMENT_NOT_FOUND"
    APPOINTMENT_INVALID_STATUS = "APPOINTMENT_INVALID_STATUS"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    MILESTONE_NOT_FOUND = "MILESTONE_NOT_FOUND"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    PRICE_NOT_DETERMINED = "PRICE_NOT_DETERMINED"

    # OAuth-Specific
    OAUTH_TOKEN_INVALID = "OAUTH_TOKEN_INVALID"
    OAUTH_TOKEN_EXPIRED = "OAUTH_TOKEN_EXPIRED"


class ErrorResponse(BaseModel):
    """Standardized error response model"""

    success: bool = False
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str
    request_id: Optional[str] = None


class ValidationErrorDetail(BaseModel):
    """Validation error detail"""

    field: str
    message: str
    value: Optional[Any] = None


def api_error(
    error_code: ErrorCode,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    status_code: int = 500,
    request_id: Optional[str] = None
) -> HTTPException:
    """
    Create a standardized API error exception.

    Args:
        error_code: Standardized error code from ErrorCode enum
        message: Human-readable error message
        details: Additional error details (optional)
        status_code: HTTP status code (default: 500)
        request_id: Request ID for tracing (optional)

    Returns:
        HTTPException with standardized error format

    Examples:
        raise api_error(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Agent not found",
            {"agent_id": "abc123"},
            status_code=404
        )

        raise api_error(
            ErrorCode.VALIDATION_ERROR,
            "Invalid agent configuration",
            {"errors": ["name is required", "domain must be valid"]},
            status_code=400
        )
    """
    content = {
        "success": False,
        "error_code": error_code.value,
        "message": message,
        "details": details or {},
        "timestamp": datetime.utcnow().isoformat(),
    }

    if request_id:
        content["request_id"] = request_id

    logger.error(
        f"API Error: {error_code.value} - {message}",
        extra={"error_code": error_code.value, "details": details, "request_id": request_id}
    )

    return HTTPException(status_code=status_code, detail=content)


def success_response(
    data: Any,
    message: Optional[str] = None,
    status_code: int = 200
) -> Dict[str, Any]:
    """
    Create a standardized success response.

    Args:
        data: Response data (can be dict, list, str, etc.)
        message: Optional success message
        status_code: HTTP status code (for reference, not used in return)

    Returns:
        Dictionary with standardized success format

    Examples:
        return success_response(
            {"agent_id": "abc123", "name": "Test Agent"},
            "Agent created successfully"
        )

        return success_response(
            ["agent1", "agent2", "agent3"],
            "Retrieved all agents"
        )
    """
    return {
        "success": True,
        "data": data,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }


def paginated_response(
    data: list,
    total: int,
    page: int = 1,
    page_size: int = 50
) -> Dict[str, Any]:
    """
    Create a standardized paginated response.

    Args:
        data: List of items for current page
        total: Total number of items across all pages
        page: Current page number (1-indexed)
        page_size: Number of items per page

    Returns:
        Dictionary with pagination metadata

    Examples:
        agents = db.query(Agent).limit(page_size).offset((page-1)*page_size).all()
        total = db.query(Agent).count()

        return paginated_response(
            [agent.to_dict() for agent in agents],
            total,
            page,
            page_size
        )
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return {
        "success": True,
        "data": data,
        "pagination": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        },
        "timestamp": datetime.utcnow().isoformat()
    }


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler for uncaught exceptions.

    This should be registered in main.py:
    app.add_exception_handler(Exception, global_exception_handler)

    Args:
        request: FastAPI request object
        exc: Uncaught exception

    Returns:
        JSONResponse with standardized error format
    """
    request_id = getattr(request.state, "request_id", None)

    # Handle AtomException if available
    if ATOM_EXCEPTIONS_AVAILABLE and isinstance(exc, AtomException):
        return await atom_exception_handler(request, exc)

    # Log the full traceback
    logger.error(
        f"Uncaught exception: {type(exc).__name__}: {str(exc)}",
        extra={"request_id": request_id, "path": str(request.url)},
        exc_info=True
    )

    # Don't expose internal errors in production
    error_message = "An internal server error occurred"
    error_code = ErrorCode.INTERNAL_SERVER_ERROR

    # In development, expose more details
    import os
    if os.getenv("ENVIRONMENT", "production") == "development":
        error_message = f"{type(exc).__name__}: {str(exc)}"

    error_response = ErrorResponse(
        success=False,
        error_code=error_code.value,
        message=error_message,
        details={"traceback": traceback.format_exc()} if os.getenv("ENVIRONMENT") == "development" else None,
        timestamp=datetime.utcnow().isoformat(),
        request_id=request_id
    )

    return JSONResponse(
        status_code=500,
        content=error_response.dict(exclude_none=True)
    )


async def atom_exception_handler(request: Request, exc: AtomException) -> JSONResponse:
    """
    Exception handler for AtomException hierarchy.

    This should be registered in main.py:
    app.add_exception_handler(AtomException, atom_exception_handler)

    Args:
        request: FastAPI request object
        exc: AtomException instance

    Returns:
        JSONResponse with standardized error format
    """
    if not ATOM_EXCEPTIONS_AVAILABLE:
        # Fallback to global handler if AtomException not available
        return await global_exception_handler(request, exc)

    request_id = getattr(request.state, "request_id", None)

    # Log the error with appropriate severity
    log_func = {
        "critical": logger.critical,
        "high": logger.error,
        "medium": logger.warning,
        "low": logger.info,
        "info": logger.info
    }.get(exc.severity.value, logger.error)

    log_func(
        f"AtomException: {exc.error_code.value} - {exc.message}",
        extra={"request_id": request_id, "path": str(request.url), "details": exc.details},
        exc_info=exc.cause is not None
    )

    # Map AtomException severity to HTTP status codes
    status_code_map = {
        "critical": 500,
        "high": 500,
        "medium": 400,
        "low": 400,
        "info": 200
    }
    status_code = status_code_map.get(exc.severity.value, 500)

    # Build error response
    error_response = ErrorResponse(
        success=False,
        error_code=exc.error_code.value,
        message=exc.message,
        details=exc.details if exc.details else None,
        timestamp=datetime.utcnow().isoformat(),
        request_id=request_id
    )

    return JSONResponse(
        status_code=status_code,
        content=error_response.dict(exclude_none=True)
    )


def handle_validation_error(
    field: str,
    message: str,
    value: Optional[Any] = None,
    status_code: int = 400
) -> HTTPException:
    """
    Create a validation error for a specific field.

    Args:
        field: Field name that failed validation
        message: Validation error message
        value: The invalid value (optional)
        status_code: HTTP status code

    Returns:
        HTTPException with validation error details

    Examples:
        if not agent_name:
            raise handle_validation_error(
                "agent_name",
                "Agent name is required",
                value=agent_name
            )
    """
    return api_error(
        ErrorCode.VALIDATION_ERROR,
        f"Validation failed for field '{field}'",
        details={
            "field": field,
            "message": message,
            "value": value
        },
        status_code=status_code
    )


def handle_not_found(
    resource_type: str,
    resource_id: str,
    details: Optional[Dict[str, Any]] = None
) -> HTTPException:
    """
    Create a "not found" error for a resource.

    Args:
        resource_type: Type of resource (e.g., "Agent", "Workspace", "User")
        resource_id: ID of the resource that wasn't found
        details: Additional details (optional)

    Returns:
        HTTPException with 404 status

    Examples:
        if not agent:
            raise handle_not_found("Agent", agent_id)
    """
    return api_error(
        ErrorCode.RESOURCE_NOT_FOUND,
        f"{resource_type} with ID '{resource_id}' not found",
        details=details or {"resource_type": resource_type, "resource_id": resource_id},
        status_code=404
    )


def handle_permission_denied(
    action: str,
    resource_type: str,
    details: Optional[Dict[str, Any]] = None
) -> HTTPException:
    """
    Create a permission denied error.

    Args:
        action: Action that was denied (e.g., "delete", "modify")
        resource_type: Type of resource (e.g., "Agent", "Workspace")
        details: Additional details (optional)

    Returns:
        HTTPException with 403 status

    Examples:
        if not user.can_delete(agent):
            raise handle_permission_denied("delete", "Agent")
    """
    return api_error(
        ErrorCode.PERMISSION_DENIED,
        f"You don't have permission to {action} this {resource_type}",
        details=details or {"action": action, "resource_type": resource_type},
        status_code=403
    )


# ============================================================================
# Specialized Exception Classes
# ============================================================================

class InvoiceError(Exception):
    """Base exception for invoice-related errors"""

    def __init__(
        self,
        message: str,
        code: ErrorCode,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        self.timestamp = datetime.utcnow()
        # Set http_status from HTTP_STATUS_MAP
        self.http_status = HTTP_STATUS_MAP.get(code, 500)
        super().__init__(self.message)

    def to_http_exception(self) -> HTTPException:
        """Convert to HTTPException"""
        return api_error(
            self.code,
            self.message,
            self.details,
            status_code=self.http_status
        )


class InvoiceNotFoundError(InvoiceError):
    """Raised when an invoice or related entity cannot be found"""

    def __init__(
        self,
        message: str,
        invoice_type: str = "unknown",
        details: Optional[Dict[str, Any]] = None
    ):
        _details = details or {}
        _details["invoice_type"] = invoice_type
        super().__init__(message, ErrorCode.INVOICE_NOT_FOUND, _details)


class InvoiceValidationError(InvoiceError):
    """Raised when invoice validation fails"""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, ErrorCode.INVOICE_VALIDATION_ERROR, details)


class InvoicePricingError(InvoiceError):
    """Raised when invoice pricing cannot be determined"""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, ErrorCode.INVOICE_PRICING_ERROR, details)


# HTTP Status Code Mapping for Invoice Errors
HTTP_STATUS_MAP: Dict[ErrorCode, int] = {
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


# ============================================================================
# Result Pattern for Operations
# ============================================================================

from typing import TypeVar, Generic

T = TypeVar('T')


class Result(Generic[T]):
    """
    Result pattern for operation outcomes.

    Encourages explicit error handling instead of returning None.

    Example:
        def divide(a: int, b: int) -> Result[float]:
            if b == 0:
                return Result.error("Division by zero", ErrorCode.VALIDATION_ERROR)
            return Result.ok(a / b)

        result = divide(10, 2)
        if result.is_ok:
            print(result.value)  # 5.0
        else:
            print(result.error)  # Error details
    """

    def __init__(
        self,
        is_ok: bool,
        value: Optional[T] = None,
        error: Optional[InvoiceError] = None
    ):
        self.is_ok = is_ok
        self.value = value
        self.error = error

    @staticmethod
    def ok(value: T) -> 'Result[T]':
        """Create a successful result"""
        return Result(is_ok=True, value=value)

    @staticmethod
    def error(
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ) -> 'Result[T]':
        """Create a failed result"""
        return Result(
            is_ok=False,
            error=InvoiceError(message=message, code=code, details=details)
        )

    @staticmethod
    def from_exception(e: Exception) -> 'Result[T]':
        """Create a failed result from an exception"""
        if isinstance(e, InvoiceError):
            return Result(is_ok=False, error=e)
        return Result(
            is_ok=False,
            error=InvoiceError(
                message=str(e),
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                details={"original_exception": type(e).__name__}
            )
        )

    def unwrap(self) -> T:
        """Unwrap the value or raise the error"""
        if self.is_ok:
            return self.value
        if self.error:
            raise self.error
        raise InvoiceError("Unknown error", ErrorCode.INTERNAL_SERVER_ERROR)

    def unwrap_or(self, default: T) -> T:
        """Unwrap the value or return default"""
        return self.value if self.is_ok else default

    def map(self, func) -> 'Result':
        """Map the value if result is ok"""
        if self.is_ok:
            try:
                return Result.ok(func(self.value))
            except Exception as e:
                return Result.from_exception(e)
        return self

    def and_then(self, func) -> 'Result':
        """Chain another operation that returns a Result"""
        if self.is_ok:
            return func(self.value)
        return self
