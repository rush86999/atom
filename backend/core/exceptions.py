"""
Custom Exception Hierarchy for Atom Platform

Provides a consistent, structured exception system for better error handling,
logging, and API responses across all services.
"""

from typing import Optional, Any, Dict, List
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels for logging and monitoring"""
    CRITICAL = "critical"  # System-wide failure, immediate attention required
    HIGH = "high"  # Major feature failure, impacts multiple users
    MEDIUM = "medium"  # Feature partially broken, impacts some users
    LOW = "low"  # Minor issue, workaround available
    INFO = "info"  # Informational, not an error per se


class ErrorCode(Enum):
    """Standardized error codes for API responses"""
    # Authentication & Authorization (1000-1099)
    AUTH_INVALID_CREDENTIALS = "AUTH_1001"
    AUTH_TOKEN_EXPIRED = "AUTH_1002"
    AUTH_TOKEN_INVALID = "AUTH_1003"
    AUTH_UNAUTHORIZED = "AUTH_1004"
    AUTH_FORBIDDEN = "AUTH_1005"
    AUTH_MFA_REQUIRED = "AUTH_1006"
    AUTH_SSO_ERROR = "AUTH_1007"

    # User Management (1100-1199)
    USER_NOT_FOUND = "USER_1101"
    USER_ALREADY_EXISTS = "USER_1102"
    USER_INVALID_STATUS = "USER_1103"
    USER_INSUFFICIENT_PERMISSIONS = "USER_1104"

    # Workspace & Teams (1200-1299)
    WORKSPACE_NOT_FOUND = "WS_1201"
    WORKSPACE_ACCESS_DENIED = "WS_1202"
    TEAM_NOT_FOUND = "TEAM_1201"
    TEAM_MEMBER_NOT_FOUND = "TEAM_1202"

    # Agents & AI (2000-2099)
    AGENT_NOT_FOUND = "AGENT_2001"
    AGENT_EXECUTION_FAILED = "AGENT_2002"
    AGENT_TIMEOUT = "AGENT_2003"
    AGENT_GOVERNANCE_FAILED = "AGENT_2004"
    AGENT_INSUFFICIENT_MATURITY = "AGENT_2005"

    # LLM & Streaming (2100-2199)
    LLM_PROVIDER_ERROR = "LLM_2101"
    LLM_RATE_LIMITED = "LLM_2102"
    LLM_INVALID_RESPONSE = "LLM_2103"
    LLM_CONTEXT_TOO_LONG = "LLM_2104"

    # Canvas & Presentations (3000-3099)
    CANVAS_NOT_FOUND = "CANVAS_3001"
    CANVAS_INVALID_COMPONENT = "CANVAS_3002"
    CANVAS_RENDER_FAILED = "CANVAS_3003"
    CANVAS_AUDIT_FAILED = "CANVAS_3004"

    # Browser Automation (4000-4099)
    BROWSER_SESSION_FAILED = "BROWSER_4001"
    BROWSER_NAVIGATION_FAILED = "BROWSER_4002"
    BROWSER_ELEMENT_NOT_FOUND = "BROWSER_4003"
    BROWSER_TIMEOUT = "BROWSER_4004"

    # Device Capabilities (5000-5099)
    DEVICE_NOT_CONNECTED = "DEVICE_5001"
    DEVICE_OPERATION_FAILED = "DEVICE_5002"
    DEVICE_PERMISSION_DENIED = "DEVICE_5003"
    DEVICE_TIMEOUT = "DEVICE_5004"

    # Database (6000-6099)
    DATABASE_ERROR = "DB_6001"
    DATABASE_CONNECTION_FAILED = "DB_6002"
    DATABASE_CONSTRAINT_VIOLATION = "DB_6003"
    DATABASE_QUERY_FAILED = "DB_6004"

    # Validation (7000-7099)
    VALIDATION_ERROR = "VAL_7001"
    VALIDATION_MISSING_FIELD = "VAL_7002"
    VALIDATION_INVALID_TYPE = "VAL_7003"
    VALIDATION_INVALID_FORMAT = "VAL_7004"

    # External Services (8000-8099)
    EXTERNAL_SERVICE_UNAVAILABLE = "EXT_8001"
    EXTERNAL_SERVICE_TIMEOUT = "EXT_8002"
    EXTERNAL_SERVICE_ERROR = "EXT_8003"

    # Configuration (9000-9099)
    CONFIG_MISSING = "CFG_9001"
    CONFIG_INVALID = "CFG_9002"

    # General (0000-0099)
    INTERNAL_SERVER_ERROR = "GEN_0001"
    NOT_IMPLEMENTED = "GEN_0002"
    FEATURE_DISABLED = "GEN_0003"


class AtomException(Exception):
    """
    Base exception class for all Atom platform exceptions.

    Attributes:
        message: Human-readable error message
        error_code: Standardized error code from ErrorCode enum
        severity: Error severity level
        details: Additional error details (optional)
        cause: Original exception that caused this error (optional)
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_SERVER_ERROR,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        self.message = message
        self.error_code = error_code
        self.severity = severity
        self.details = details or {}
        self.cause = cause

        # Build full error message with context
        full_message = f"[{error_code.value}] {message}"
        if cause:
            full_message += f" (caused by: {type(cause).__name__}: {str(cause)})"

        super().__init__(full_message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "severity": self.severity.value,
            "details": self.details
        }


# Authentication & Authorization Exceptions

class AuthenticationError(AtomException):
    """Base class for authentication errors"""

    def __init__(
        self,
        message: str = "Authentication failed",
        error_code: ErrorCode = ErrorCode.AUTH_INVALID_CREDENTIALS,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, error_code, ErrorSeverity.HIGH, details, cause)


class TokenExpiredError(AuthenticationError):
    """JWT or access token has expired"""

    def __init__(self, message: str = "Token has expired", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.AUTH_TOKEN_EXPIRED, details)


class TokenInvalidError(AuthenticationError):
    """JWT or access token is invalid"""

    def __init__(self, message: str = "Invalid token", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.AUTH_TOKEN_INVALID, details)


class UnauthorizedError(AtomException):
    """User is not authenticated"""

    def __init__(self, message: str = "Unauthorized access", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.AUTH_UNAUTHORIZED, ErrorSeverity.HIGH, details)


class ForbiddenError(AtomException):
    """User is authenticated but lacks required permissions"""

    def __init__(
        self,
        message: str = "Access forbidden",
        required_permission: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if required_permission:
            details["required_permission"] = required_permission
        super().__init__(message, ErrorCode.AUTH_FORBIDDEN, ErrorSeverity.MEDIUM, details)


class MFARRequiredError(AuthenticationError):
    """Multi-factor authentication is required"""

    def __init__(self, message: str = "MFA required", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.AUTH_MFA_REQUIRED, details)


class SAMLSError(AuthenticationError):
    """SAML SSO authentication failed"""

    def __init__(self, message: str = "SAML SSO failed", details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(message, ErrorCode.AUTH_SSO_ERROR, details, cause)


# User Management Exceptions

class UserNotFoundError(AtomException):
    """User not found in database"""

    def __init__(self, user_id: Optional[str] = None, email: Optional[str] = None):
        details = {}
        if user_id:
            details["user_id"] = user_id
        if email:
            details["email"] = email

        message = "User not found"
        if user_id:
            message += f" (ID: {user_id})"
        elif email:
            message += f" (Email: {email})"

        super().__init__(message, ErrorCode.USER_NOT_FOUND, ErrorSeverity.MEDIUM, details)


class UserAlreadyExistsError(AtomException):
    """User already exists"""

    def __init__(self, email: str):
        super().__init__(
            f"User already exists with email: {email}",
            ErrorCode.USER_ALREADY_EXISTS,
            ErrorSeverity.MEDIUM,
            {"email": email}
        )


# Workspace & Team Exceptions

class WorkspaceNotFoundError(AtomException):
    """Workspace not found"""

    def __init__(self, workspace_id: str):
        super().__init__(
            f"Workspace not found: {workspace_id}",
            ErrorCode.WORKSPACE_NOT_FOUND,
            ErrorSeverity.MEDIUM,
            {"workspace_id": workspace_id}
        )


class WorkspaceAccessDeniedError(AtomException):
    """User does not have access to workspace"""

    def __init__(self, workspace_id: str, user_id: str, required_role: Optional[str] = None):
        details = {
            "workspace_id": workspace_id,
            "user_id": user_id
        }
        if required_role:
            details["required_role"] = required_role

        super().__init__(
            f"Access denied to workspace: {workspace_id}",
            ErrorCode.WORKSPACE_ACCESS_DENIED,
            ErrorSeverity.MEDIUM,
            details
        )


# Agent & AI Exceptions

class AgentNotFoundError(AtomException):
    """Agent not found"""

    def __init__(self, agent_id: str):
        super().__init__(
            f"Agent not found: {agent_id}",
            ErrorCode.AGENT_NOT_FOUND,
            ErrorSeverity.MEDIUM,
            {"agent_id": agent_id}
        )


class AgentExecutionError(AtomException):
    """Agent execution failed"""

    def __init__(
        self,
        agent_id: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        error_details = {"agent_id": agent_id, "reason": reason}
        if details:
            error_details.update(details)

        super().__init__(
            f"Agent execution failed: {agent_id} - {reason}",
            ErrorCode.AGENT_EXECUTION_FAILED,
            ErrorSeverity.HIGH,
            error_details,
            cause
        )


class AgentTimeoutError(AtomException):
    """Agent execution timed out"""

    def __init__(self, agent_id: str, timeout_seconds: int):
        super().__init__(
            f"Agent timed out after {timeout_seconds}s: {agent_id}",
            ErrorCode.AGENT_TIMEOUT,
            ErrorSeverity.MEDIUM,
            {"agent_id": agent_id, "timeout_seconds": timeout_seconds}
        )


class AgentGovernanceError(AtomException):
    """Agent failed governance check"""

    def __init__(
        self,
        agent_id: str,
        reason: str,
        maturity_level: Optional[str] = None,
        required_action: Optional[str] = None
    ):
        details = {"agent_id": agent_id, "reason": reason}
        if maturity_level:
            details["maturity_level"] = maturity_level
        if required_action:
            details["required_action"] = required_action

        super().__init__(
            f"Agent governance check failed: {agent_id} - {reason}",
            ErrorCode.AGENT_GOVERNANCE_FAILED,
            ErrorSeverity.HIGH,
            details
        )


# LLM & Streaming Exceptions

class LLMProviderError(AtomException):
    """LLM provider API error"""

    def __init__(
        self,
        provider: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        error_details = {"provider": provider}
        if details:
            error_details.update(details)

        super().__init__(
            f"LLM provider error ({provider}): {message}",
            ErrorCode.LLM_PROVIDER_ERROR,
            ErrorSeverity.HIGH,
            error_details,
            cause
        )


class LLMRateLimitError(AtomException):
    """LLM provider rate limit exceeded"""

    def __init__(self, provider: str, retry_after: Optional[int] = None):
        details = {"provider": provider}
        if retry_after:
            details["retry_after_seconds"] = retry_after

        super().__init__(
            f"LLM rate limit exceeded for {provider}",
            ErrorCode.LLM_RATE_LIMITED,
            ErrorSeverity.MEDIUM,
            details
        )


class LLMContextTooLongError(AtomException):
    """LLM context exceeds maximum length"""

    def __init__(
        self,
        provider: str,
        current_tokens: int,
        max_tokens: int
    ):
        super().__init__(
            f"LLM context too long: {current_tokens} tokens (max: {max_tokens})",
            ErrorCode.LLM_CONTEXT_TOO_LONG,
            ErrorSeverity.MEDIUM,
            {"provider": provider, "current_tokens": current_tokens, "max_tokens": max_tokens}
        )


# Canvas & Presentation Exceptions

class CanvasNotFoundError(AtomException):
    """Canvas not found"""

    def __init__(self, canvas_id: str):
        super().__init__(
            f"Canvas not found: {canvas_id}",
            ErrorCode.CANVAS_NOT_FOUND,
            ErrorSeverity.MEDIUM,
            {"canvas_id": canvas_id}
        )


class CanvasValidationError(AtomException):
    """Canvas component validation failed"""

    def __init__(
        self,
        canvas_id: str,
        component_type: str,
        reason: str
    ):
        super().__init__(
            f"Canvas validation failed: {component_type} - {reason}",
            ErrorCode.CANVAS_INVALID_COMPONENT,
            ErrorSeverity.MEDIUM,
            {"canvas_id": canvas_id, "component_type": component_type, "reason": reason}
        )


# Browser Automation Exceptions

class BrowserSessionError(AtomException):
    """Browser session creation or management failed"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(
            f"Browser session error: {message}",
            ErrorCode.BROWSER_SESSION_FAILED,
            ErrorSeverity.HIGH,
            details,
            cause
        )


class BrowserNavigationError(AtomException):
    """Browser navigation failed"""

    def __init__(self, url: str, reason: str):
        super().__init__(
            f"Browser navigation failed to {url}: {reason}",
            ErrorCode.BROWSER_NAVIGATION_FAILED,
            ErrorSeverity.MEDIUM,
            {"url": url, "reason": reason}
        )


class BrowserElementNotFoundError(AtomException):
    """Element not found in browser page"""

    def __init__(self, selector: str, url: Optional[str] = None):
        details = {"selector": selector}
        if url:
            details["url"] = url

        super().__init__(
            f"Element not found: {selector}",
            ErrorCode.BROWSER_ELEMENT_NOT_FOUND,
            ErrorSeverity.MEDIUM,
            details
        )


# Device Capabilities Exceptions

class DeviceNotFoundError(AtomException):
    """Device not connected or not found"""

    def __init__(self, device_id: str):
        super().__init__(
            f"Device not found: {device_id}",
            ErrorCode.DEVICE_NOT_CONNECTED,
            ErrorSeverity.MEDIUM,
            {"device_id": device_id}
        )


class DeviceOperationError(AtomException):
    """Device operation failed"""

    def __init__(
        self,
        device_id: str,
        operation: str,
        reason: str,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            f"Device operation failed: {operation} on {device_id} - {reason}",
            ErrorCode.DEVICE_OPERATION_FAILED,
            ErrorSeverity.MEDIUM,
            {"device_id": device_id, "operation": operation, "reason": reason},
            cause
        )


class DevicePermissionDeniedError(AtomException):
    """Device permission denied"""

    def __init__(
        self,
        device_id: str,
        operation: str,
        permission: str
    ):
        super().__init__(
            f"Device permission denied: {permission} required for {operation}",
            ErrorCode.DEVICE_PERMISSION_DENIED,
            ErrorSeverity.MEDIUM,
            {"device_id": device_id, "operation": operation, "permission": permission}
        )


# Database Exceptions

class DatabaseError(AtomException):
    """Database operation error"""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            f"Database error: {message}",
            ErrorCode.DATABASE_ERROR,
            ErrorSeverity.CRITICAL,
            details,
            cause
        )


class DatabaseConnectionError(DatabaseError):
    """Database connection failed"""

    def __init__(self, message: str = "Failed to connect to database", cause: Optional[Exception] = None):
        super().__init__(message, {"connection_failed": True}, cause)
        self.error_code = ErrorCode.DATABASE_CONNECTION_FAILED


class DatabaseConstraintViolationError(DatabaseError):
    """Database constraint violation"""

    def __init__(self, table: str, constraint: str, details: Optional[Dict[str, Any]] = None):
        error_details = {"table": table, "constraint": constraint}
        if details:
            error_details.update(details)

        super().__init__(
            f"Constraint violation on {table}: {constraint}",
            error_details,
            None
        )
        self.error_code = ErrorCode.DATABASE_CONSTRAINT_VIOLATION


# Validation Exceptions

class ValidationError(AtomException):
    """Data validation error"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if field:
            error_details["field"] = field

        super().__init__(
            message,
            ErrorCode.VALIDATION_ERROR,
            ErrorSeverity.LOW,
            error_details
        )


class MissingFieldError(ValidationError):
    """Required field is missing"""

    def __init__(self, field: str, context: Optional[str] = None):
        message = f"Missing required field: {field}"
        if context:
            message += f" (in {context})"

        super().__init__(message, field)
        self.error_code = ErrorCode.VALIDATION_MISSING_FIELD


class InvalidTypeError(ValidationError):
    """Field has invalid type"""

    def __init__(self, field: str, expected_type: str, actual_type: str):
        message = f"Invalid type for {field}: expected {expected_type}, got {actual_type}"
        super().__init__(message, field, {"expected_type": expected_type, "actual_type": actual_type})
        self.error_code = ErrorCode.VALIDATION_INVALID_TYPE


# External Service Exceptions

class ExternalServiceError(AtomException):
    """External service error"""

    def __init__(
        self,
        service: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        error_details = {"service": service}
        if details:
            error_details.update(details)

        super().__init__(
            f"External service error ({service}): {message}",
            ErrorCode.EXTERNAL_SERVICE_ERROR,
            ErrorSeverity.HIGH,
            error_details,
            cause
        )


class ExternalServiceUnavailableError(ExternalServiceError):
    """External service is unavailable"""

    def __init__(self, service: str, cause: Optional[Exception] = None):
        super().__init__(service, "Service unavailable", None, cause)
        self.error_code = ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE


# Configuration Exceptions

class ConfigurationError(AtomException):
    """Configuration error"""

    def __init__(self, message: str, config_key: Optional[str] = None):
        details = {"config_key": config_key} if config_key else {}
        super().__init__(
            f"Configuration error: {message}",
            ErrorCode.CONFIG_INVALID,
            ErrorSeverity.HIGH,
            details
        )


class MissingConfigurationError(ConfigurationError):
    """Required configuration is missing"""

    def __init__(self, config_key: str):
        super().__init__(f"Missing required configuration: {config_key}", config_key)
        self.error_code = ErrorCode.CONFIG_MISSING


# General Exceptions

class InternalServerError(AtomException):
    """Internal server error"""

    def __init__(self, message: str = "An internal error occurred", cause: Optional[Exception] = None):
        super().__init__(
            message,
            ErrorCode.INTERNAL_SERVER_ERROR,
            ErrorSeverity.CRITICAL,
            {},
            cause
        )


class NotImplementedError(AtomException):
    """Feature not implemented"""

    def __init__(self, feature: str):
        super().__init__(
            f"Feature not implemented: {feature}",
            ErrorCode.NOT_IMPLEMENTED,
            ErrorSeverity.INFO,
            {"feature": feature}
        )


class FeatureDisabledError(AtomException):
    """Feature is disabled"""

    def __init__(self, feature: str):
        super().__init__(
            f"Feature is disabled: {feature}",
            ErrorCode.FEATURE_DISABLED,
            ErrorSeverity.INFO,
            {"feature": feature}
        )


# Helper functions for exception handling

def handle_exception(
    exc: Exception,
    default_message: str = "An error occurred",
    default_severity: ErrorSeverity = ErrorSeverity.MEDIUM
) -> AtomException:
    """
    Convert any exception to an AtomException if it isn't already.

    Args:
        exc: The exception to handle
        default_message: Default message if exception is not an AtomException
        default_severity: Default severity if exception is not an AtomException

    Returns:
        AtomException instance
    """
    if isinstance(exc, AtomException):
        return exc

    # Map common exception types to Atom exceptions
    exception_mapping = {
        ValueError: ValidationError,
        KeyError: MissingFieldError,
        TypeError: InvalidTypeError,
        PermissionError: ForbiddenError,
    }

    for exc_type, atom_exc_type in exception_mapping.items():
        if isinstance(exc, exc_type):
            return atom_exception(
                message=str(exc) or default_message,
                cause=exc
            )

    # Fallback to generic internal server error
    return InternalServerError(default_message, cause=exc)


def create_error_response(exc: AtomException) -> Dict[str, Any]:
    """
    Create a standardized error response for API endpoints.

    Args:
        exc: AtomException instance

    Returns:
        Dictionary suitable for JSON response
    """
    response = exc.to_dict()

    # Add HTTP status code suggestion
    status_code_map = {
        ErrorSeverity.CRITICAL: 500,
        ErrorSeverity.HIGH: 500,
        ErrorSeverity.MEDIUM: 400,
        ErrorSeverity.LOW: 400,
        ErrorSeverity.INFO: 200  # For FEATURE_DISABLED, etc.
    }

    response["suggested_status_code"] = status_code_map.get(exc.severity, 500)

    return response
