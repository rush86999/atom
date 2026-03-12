"""
Core security utilities for the Atom platform.

This package provides:
- Rate limiting middleware
- Security headers middleware
- Role-based access control (RBAC)
"""

from .rbac import require_role

__all__ = ["require_role"]
