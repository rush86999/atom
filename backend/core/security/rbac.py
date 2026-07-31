"""
Role-Based Access Control (RBAC) Utilities

Provides role checking dependencies for FastAPI routes.
"""

import logging
from typing import Callable
from fastapi import Depends, HTTPException, status

from core.auth import get_current_user
from core.models import User, UserRole

logger = logging.getLogger(__name__)


def require_role(required_role: UserRole) -> Callable[[User], User]:
    """
    Dependency that requires a specific user role.

    Args:
        required_role: The UserRole required to access the endpoint

    Returns:
        Dependency function that returns the user if authorized, raises 403 otherwise

    Raises:
        HTTPException: 403 Forbidden if user doesn't have required role
    """
    # H1 fix: role hierarchy — higher-privilege roles should pass checks for
    # lower-required roles. Previously exact-match meant OWNER/SUPER_ADMIN
    # were rejected from ADMIN-only endpoints (privilege inversion).
    _ROLE_LEVELS = {
        "member": 1,
        "intern": 2,
        "student": 2,
        "workspace_admin": 3,
        "admin": 4,
        "owner": 5,
        "super_admin": 6,
    }

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_level = _ROLE_LEVELS.get(current_user.role, 0)
        required_level = _ROLE_LEVELS.get(required_role, 99)
        if user_level < required_level:
            logger.warning(
                f"Access denied: user {current_user.id} has role {current_user.role} "
                f"(level {user_level}), required {required_role} (level {required_level})"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )
        return current_user

    return role_checker
