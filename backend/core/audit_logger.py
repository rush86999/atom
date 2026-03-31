"""
Audit Logger - Unified audit logging for integrations

Single-tenant version for upstream (no tenant isolation).
Logs all integration operations with request/response metadata.
"""
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class IntegrationAuditLog:
    """
    Structured audit log entry for integration operations.
    Single-tenant version (no tenant_id field).
    """

    def __init__(
        self,
        connector_id: str,
        method: str,
        params: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        timestamp: Optional[float] = None
    ):
        self.connector_id = connector_id
        self.method = method
        self.params = params
        self.result = result
        self.error = error
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit log to dictionary for logging/serialization."""
        return {
            "connector_id": self.connector_id,
            "method": self.method,
            "params": self._sanitize_params(self.params),
            "result": self.result,
            "error": self.error,
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(timespec='milliseconds') + 'Z',
            "epoch": self.timestamp
        }

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize sensitive parameters (passwords, tokens, etc.).

        Args:
            params: Raw parameters dictionary

        Returns:
            Sanitized parameters with sensitive values redacted
        """
        if not params:
            return {}

        sanitized = {}
        sensitive_keys = {
            "password", "token", "api_key", "secret", "access_token",
            "refresh_token", "private_key", "credentials"
        }

        for key, value in params.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                # Redact sensitive values
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_params(value)
            else:
                sanitized[key] = value

        return sanitized


def log_integration_call(
    connector_id: str,
    method: str,
    params: Dict[str, Any],
    result: Optional[Dict[str, Any]] = None
) -> IntegrationAuditLog:
    """
    Log a successful integration call.

    Args:
        connector_id: Integration identifier (e.g., "slack", "gmail")
        method: Method name (e.g., "send_message", "get_emails")
        params: Request parameters
        result: Optional result data

    Returns:
        IntegrationAuditLog entry
    """
    audit_log = IntegrationAuditLog(
        connector_id=connector_id,
        method=method,
        params=params,
        result=result,
        error=None
    )

    # Log structured output
    logger.info(
        f"Integration call: {connector_id}.{method}",
        extra=audit_log.to_dict()
    )

    return audit_log


def log_integration_error(
    connector_id: str,
    method: str,
    error: Exception,
    params: Optional[Dict[str, Any]] = None
) -> IntegrationAuditLog:
    """
    Log an integration error.

    Args:
        connector_id: Integration identifier (e.g., "slack", "gmail")
        method: Method name (e.g., "send_message", "get_emails")
        error: Exception that occurred
        params: Optional request parameters

    Returns:
        IntegrationAuditLog entry
    """
    audit_log = IntegrationAuditLog(
        connector_id=connector_id,
        method=method,
        params=params or {},
        result=None,
        error=str(error)
    )

    # Log structured error
    logger.error(
        f"Integration error: {connector_id}.{method}: {error}",
        extra=audit_log.to_dict(),
        exc_info=type(error)
    )

    return audit_log


def log_integration_attempt(
    connector_id: str,
    method: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Log the start of an integration attempt (for timing/monitoring).

    Args:
        connector_id: Integration identifier
        method: Method name
        params: Request parameters

    Returns:
        Context dictionary with timing information
    """
    return {
        "connector_id": connector_id,
        "method": method,
        "start_time": time.time(),
        "params": params
    }


def log_integration_complete(
    context: Dict[str, Any],
    result: Optional[Dict[str, Any]] = None,
    error: Optional[Exception] = None
) -> float:
    """
    Log the completion of an integration attempt with timing.

    Args:
        context: Context from log_integration_attempt
        result: Optional result data
        error: Optional error that occurred

    Returns:
        Duration in milliseconds
    """
    duration_ms = (time.time() - context["start_time"]) * 1000

    if error:
        log_integration_error(
            context["connector_id"],
            context["method"],
            error,
            context.get("params")
        )
    else:
        log_integration_call(
            context["connector_id"],
            context["method"],
            context.get("params", {}),
            result
        )

    return duration_ms
