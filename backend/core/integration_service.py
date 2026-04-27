"""
Base Integration Service
Defines common interface for all integration services
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IntegrationServiceError(Exception):
    """
    Base exception for all integration service errors.

    All integration-specific exceptions should inherit from this class.
    Provides structured error handling with error codes, retry information,
    and context for debugging.

    Attributes:
        message: Human-readable error message
        error_code: Standardized error code from IntegrationErrorCode enum
        retryable: Whether this error is retryable (True/False)
        status_code: HTTP status code (401, 403, 404, 429, 500, etc.)
        tenant_id: Tenant UUID for context
        connector_id: Integration identifier for context
        operation: Operation being executed when error occurred
    """

    def __init__(
        self,
        message: str,
        error_code: str,
        retryable: bool = False,
        status_code: int = 500,
        tenant_id: Optional[str] = None,
        connector_id: Optional[str] = None,
        operation: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.retryable = retryable
        self.status_code = status_code
        self.tenant_id = tenant_id
        self.connector_id = connector_id
        self.operation = operation
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to structured dictionary for API responses."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "retryable": self.retryable,
            "status_code": self.status_code,
            "tenant_id": self.tenant_id[:8] if self.tenant_id else None,  # First 8 chars for PII
            "connector_id": self.connector_id,
            "operation": self.operation
        }


class AuthenticationError(IntegrationServiceError):
    """
    Authentication or authorization failure.

    Raised when API credentials are invalid, expired, or missing.
    NOT retryable (credentials must be fixed first).

    Examples:
    - Invalid API token
    - Expired OAuth token
    - Missing credentials
    """

    def __init__(
        self,
        message: str,
        tenant_id: Optional[str] = None,
        connector_id: Optional[str] = None,
        operation: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="AUTH_FAILED",
            retryable=False,
            status_code=401,
            tenant_id=tenant_id,
            connector_id=connector_id,
            operation=operation
        )


class RateLimitError(IntegrationServiceError):
    """
    Rate limit exceeded.

    Raised when external API rate limit is hit.
    Retryable after waiting for specified duration.

    Examples:
    - Slack 100 requests/minute exceeded
    - Salesforce 15,000 requests/24h exceeded
    """

    def __init__(
        self,
        message: str,
        wait_time: float = 0.0,
        tenant_id: Optional[str] = None,
        connector_id: Optional[str] = None,
        operation: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="RATE_LIMITED",
            retryable=True,
            status_code=429,
            tenant_id=tenant_id,
            connector_id=connector_id,
            operation=operation
        )
        self.wait_time = wait_time  # Seconds to wait before retry


class ValidationError(IntegrationServiceError):
    """
    Input validation failure.

    Raised when request parameters are invalid or missing.
    NOT retryable (parameters must be fixed first).

    Examples:
    - Missing required parameter
    - Invalid email format
    - Parameter type mismatch
    """

    def __init__(
        self,
        message: str,
        tenant_id: Optional[str] = None,
        connector_id: Optional[str] = None,
        operation: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            retryable=False,
            status_code=400,
            tenant_id=tenant_id,
            connector_id=connector_id,
            operation=operation
        )


class NetworkError(IntegrationServiceError):
    """
    Network or connectivity failure.

    Raised when network request fails due to connectivity issues.
    Retryable (transient network issues).

    Examples:
    - DNS resolution failed
    - Connection timeout
    - Connection refused
    """

    def __init__(
        self,
        message: str,
        tenant_id: Optional[str] = None,
        connector_id: Optional[str] = None,
        operation: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="NETWORK_ERROR",
            retryable=True,
            status_code=503,
            tenant_id=tenant_id,
            connector_id=connector_id,
            operation=operation
        )


class IntegrationNotFoundError(IntegrationServiceError):
    """
    Integration or operation not found.

    Raised when requested integration or operation doesn't exist.
    NOT retryable (resource doesn't exist).

    Examples:
    - Unknown connector_id
    - Unsupported operation
    - Integration not configured for tenant
    """

    def __init__(
        self,
        message: str,
        tenant_id: Optional[str] = None,
        connector_id: Optional[str] = None,
        operation: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="INTEGRATION_NOT_FOUND",
            retryable=False,
            status_code=404,
            tenant_id=tenant_id,
            connector_id=connector_id,
            operation=operation
        )


class PermissionError(IntegrationServiceError):
    """
    Permission or authorization failure.

    Raised when authenticated user lacks permission for requested action.
    NOT retryable (permissions must be granted first).

    Examples:
    - Agent maturity insufficient for operation
    - User lacks API scope
    - Resource access denied
    """

    def __init__(
        self,
        message: str,
        tenant_id: Optional[str] = None,
        connector_id: Optional[str] = None,
        operation: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
            retryable=False,
            status_code=403,
            tenant_id=tenant_id,
            connector_id=connector_id,
            operation=operation
        )


class CircuitBreakerOpenError(IntegrationServiceError):
    """
    Circuit breaker is OPEN, preventing execution.

    Raised when circuit breaker has opened due to repeated failures.
    NOT retryable through this path (must wait for recovery timeout).

    Examples:
    - 3 consecutive failures occurred
    - Circuit breaker in OPEN state
    - Recovery timeout not elapsed
    """

    def __init__(
        self,
        message: str,
        tenant_id: Optional[str] = None,
        connector_id: Optional[str] = None,
        operation: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="CIRCUIT_OPEN",
            retryable=False,
            status_code=503,
            tenant_id=tenant_id,
            connector_id=connector_id,
            operation=operation
        )


class IntegrationErrorCode(Enum):
    """Standardized error codes for integration failures"""
    # Authorization & Identity
    AUTH_EXPIRED = "AUTH_EXPIRED"
    AUTH_INVALID = "AUTH_INVALID"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    
    # Reliability & Resource
    RATE_LIMIT = "RATE_LIMIT"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    
    # Downstream Failures
    SERVICE_DOWN = "SERVICE_DOWN"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    
    # Client Errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    OPERATION_NOT_FOUND = "OPERATION_NOT_FOUND"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    
    # Generic
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN = "UNKNOWN"


class IntegrationService(ABC):
    """
    Base class for all integration services.

    All integration services (Slack, Salesforce, etc.) must inherit from this class
    and implement the required methods for capability discovery and execution.
    """

    def __init__(self, tenant_id: str, config: Dict[str, Any]):
        """
        Initialize integration service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration from IntegrationCatalog.config
        """
        self.tenant_id = tenant_id
        self.config = config

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return integration capabilities for this service.

        Returns:
            Dict with:
            - operations: List of available operations (e.g., ["read", "write", "delete"])
            - required_params: List of required parameters (e.g., ["api_key", "instance_url"])
            - optional_params: List of optional parameters
            - rate_limits: Dict of rate limit info (e.g., {"requests_per_minute": 100})
            - supports_webhooks: Boolean indicating webhook support
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Check if integration service is healthy.

        Returns:
            Dict with:
            - healthy: Boolean
            - message: Status message
            - last_check: ISO timestamp
        """
        pass

    def get_operation_details(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific operation.

        Args:
            operation_id: Operation identifier (e.g., "send_message", "create_record")

        Returns:
            Dict with operation details or None if not found
        """
        capabilities = self.get_capabilities()
        for op in capabilities.get("operations", []):
            if op.get("id") == operation_id:
                return op
        return None

    @abstractmethod
    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute an integration operation with tenant context.

        Args:
            operation: Operation name (e.g., "send_message", "create_record")
            parameters: Operation parameters with variable substitution applied
            context: Tenant context dict with tenant_id, agent_id, workspace_id, connector_id

        Returns:
            Dict with:
            - success (bool): Operation success status
            - result (Any): Operation result data (if successful)
            - error (str): Error message (if failed)
            - details (Dict): Additional execution details

        Raises:
            NotImplementedError: If operation not supported

        CRITICAL: All operations must validate tenant_id from context to prevent cross-tenant access.
        """
        pass

    def get_operations(self) -> List[Dict[str, Any]]:
        """
        Return list of available operations for this integration.

        Each operation dict contains:
        - name: str (operation identifier)
        - description: str (what it does)
        - parameters: dict (parameter schemas)
        - complexity: int (1=read, 2=analyze, 3=execute, 4=critical)

        Returns:
            List of operation definitions

        CRITICAL: Complexity level maps to agent maturity requirements.
        CRITICAL: NO LangChain schema types - use plain dict definitions.
        """
        return []
