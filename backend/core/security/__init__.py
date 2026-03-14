"""
Core security utilities for the Atom platform.

This package provides:
- Rate limiting middleware
- Security headers middleware
- Role-based access control (RBAC)
"""

from .rbac import require_role
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware stub (placeholder for implementation)."""

    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Security headers middleware stub (placeholder for implementation)."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


__all__ = ["require_role", "RateLimitMiddleware", "SecurityHeadersMiddleware"]
