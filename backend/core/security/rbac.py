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
    # W103 fix: hierarchy now keyed on the UserRole enum members — the map
    # previously keyed plain strings and MISSED team_lead/viewer/guest (all
    # resolved to level 0 → TEAM_LEAD wrongly denied from MEMBER+ endpoints)
    # while carrying dead "intern"/"student" entries (maturity levels, not
    # roles). UserRole is a str-enum, so lookups by raw role string (as
    # stored on User.role) resolve via str-hash equality.
    _ROLE_LEVELS = {
        UserRole.GUEST: 1,
        UserRole.VIEWER: 2,
        UserRole.MEMBER: 3,
        UserRole.TEAM_LEAD: 4,
        UserRole.WORKSPACE_ADMIN: 5,
        UserRole.ADMIN: 6,
        UserRole.OWNER: 7,
        UserRole.SUPER_ADMIN: 8,
    }

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_level = _ROLE_LEVELS.get(current_user.role, 0)
        required_level = _ROLE_LEVELS.get(required_role, 99)
        if user_level < required_level:
            required_name = getattr(required_role, "value", required_role)
            logger.warning(
                f"Access denied: user {current_user.id} has role {current_user.role} "
                f"(level {user_level}), required {required_name} (level {required_level})"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_name}"
            )
        return current_user

    return role_checker
