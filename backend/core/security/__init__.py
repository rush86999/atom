from __future__ import annotations
"""
Core security utilities for the Atom platform.

This package provides:
- Rate limiting middleware (Global, Tenant-specific, and External API)
- Security headers and CSRF protection
- Role-based access control (RBAC)
- Input validation and sanitization
"""

import logging

# Security Logger
logger = logging.getLogger(__name__)

# --- MIDDLEWARE & UTILITY EXPORTS ---
from .middleware import (
    CSRFProtectionMiddleware,
    ExternalAPIRateLimitMiddleware,
    InputValidationMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    generate_api_key,
    log_tenant_enumeration_attempt,
    sanitize_input,
    validate_email,
)

# --- RBAC EXPORTS ---
from .rbac import require_role

__all__ = [
    # Middleware
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
    "InputValidationMiddleware",
    "CSRFProtectionMiddleware",
    "ExternalAPIRateLimitMiddleware",
    "log_tenant_enumeration_attempt",
    "sanitize_input",
    "validate_email",
    "generate_api_key",
    # RBAC
    "require_role",
]
