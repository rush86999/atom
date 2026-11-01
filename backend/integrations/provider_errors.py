"""Typed provider failures shared by the Zoho/Microsoft adapters.

The business workflows must never turn an unavailable provider into an empty
success.  A list endpoint that returns ``[]`` because the token expired, the
organization was not authorized, the data center was wrong, or the provider
returned a malformed body is a *failure*, not a fact about the customer.

This module keeps the classification small and stable so the agent surface,
the contract matrix and the accounting loop can make the same decision:

``auth_expired`` / ``auth_revoked``
    The grant cannot be refreshed.  A reconnect is required; retrying the
    same request will not help.
``auth_unavailable``
    No grant was resolved for the requested user/workspace/org.
``unauthorized``
    The grant is valid but does not cover the organization/object.
``not_found``
    The provider says the object does not exist (deletion is a real fact).
``rate_limited`` / ``transient``
    Retryable without changing the request.
``invalid_request`` / ``provider_error`` / ``parse_error``
    Not retryable as-is; the caller must change the request or the provider
    must be fixed.  ``parse_error`` specifically means a 2xx body that we
    could not interpret as the documented shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


RETRYABLE_KINDS = frozenset({"rate_limited", "transient"})
RECONNECT_KINDS = frozenset({"auth_expired", "auth_revoked", "auth_unavailable"})


@dataclass
class ProviderRequestError(Exception):
    """A provider request that did not produce a trustworthy result."""

    provider: str
    operation: str
    kind: str
    message: str
    status_code: Optional[int] = None
    retryable: Optional[bool] = None
    requires_reconnect: Optional[bool] = None
    correlation_id: Optional[str] = None
    provider_error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.retryable is None:
            self.retryable = self.kind in RETRYABLE_KINDS
        if self.requires_reconnect is None:
            self.requires_reconnect = self.kind in RECONNECT_KINDS
        # Exception args stay human-readable; the structured members carry
        # the machine decision.
        Exception.__init__(self, self.message)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "status": "error",
            "success": False,
            "provider": self.provider,
            "operation": self.operation,
            "error_kind": self.kind,
            "error": self.message,
            "retryable": bool(self.retryable),
            "requires_reconnect": bool(self.requires_reconnect),
        }
        if self.status_code is not None:
            payload["status_code"] = self.status_code
        if self.provider_error:
            payload["provider_error"] = self.provider_error
        if self.correlation_id:
            payload["correlation_id"] = self.correlation_id
        if self.details:
            payload["details"] = dict(self.details)
        return payload


def classify_http_status(
    provider: str,
    operation: str,
    status_code: int,
    *,
    provider_error: Optional[str] = None,
    message: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> ProviderRequestError:
    """Map an HTTP status / Zoho error code onto the stable error kinds."""

    error_code = str(provider_error or "").strip().lower()
    if status_code in (401,) or error_code in (
        "invalid_token", "invalid_oauth", "unauthenticated",
    ):
        kind = "auth_expired"
    elif status_code == 403 or error_code in (
        "unauthorized", "access_denied", "insufficient_scope",
        "no_permission", "not_authorized",
    ):
        # Zoho uses 400 + INVALID_OAUTHSCOPE for missing org scope; the
        # caller passes that as provider_error.  It is an authorization
        # failure, not a malformed request.
        kind = "unauthorized" if error_code not in ("invalid_oauth",) else "auth_revoked"
    elif status_code == 404 or error_code in ("not_found", "invaliddata"):
        kind = "not_found" if status_code == 404 else "invalid_request"
    elif status_code == 429 or error_code in ("too_many_requests", "rate_limit"):
        kind = "rate_limited"
    elif status_code >= 500:
        kind = "transient"
    elif error_code in ("invalid_client", "invalid_code", "invalid_grant"):
        kind = "auth_revoked"
    else:
        kind = "invalid_request" if 400 <= status_code < 500 else "provider_error"

    if error_code in ("invalid_oauthscope", "oauth_scope_error", "scope_mismatch"):
        kind = "unauthorized"

    return ProviderRequestError(
        provider=provider,
        operation=operation,
        kind=kind,
        message=message or f"{provider} {operation} failed (HTTP {status_code})",
        status_code=status_code,
        provider_error=provider_error or None,
        correlation_id=correlation_id,
    )


def parse_error(
    provider: str,
    operation: str,
    message: str = "provider returned an unreadable success body",
    *,
    status_code: Optional[int] = None,
) -> ProviderRequestError:
    return ProviderRequestError(
        provider=provider,
        operation=operation,
        kind="parse_error",
        message=message,
        status_code=status_code,
        retryable=False,
    )


def unavailable(
    provider: str,
    operation: str,
    message: str,
    *,
    kind: str = "auth_unavailable",
    details: Optional[Dict[str, Any]] = None,
) -> ProviderRequestError:
    return ProviderRequestError(
        provider=provider,
        operation=operation,
        kind=kind,
        message=message,
        retryable=kind in RETRYABLE_KINDS,
        requires_reconnect=kind in RECONNECT_KINDS,
        details=details or {},
    )
