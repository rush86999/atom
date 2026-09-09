"""
Role-Based Access Control (RBAC) Utilities

Provides role checking dependencies for FastAPI routes.
"""

import logging
from typing import Callable, Union
from fastapi import Depends, HTTPException, status

from core.auth import get_current_user
from core.models import User, UserRole

logger = logging.getLogger(__name__)

# H1 fix: role hierarchy — higher-privilege roles should pass checks for
# lower-required roles. Previously exact-match meant OWNER/SUPER_ADMIN
# were rejected from ADMIN-only endpoints (privilege inversion).
# W103 fix: hierarchy now keyed on the UserRole enum members — the map
# previously keyed plain strings and MISSED team_lead/viewer/guest (all
# resolved to level 0 → TEAM_LEAD wrongly denied from MEMBER+ endpoints)
# while carrying dead "intern"/"student" entries (maturity levels, not
# roles). UserRole is a str-enum, so lookups by raw role string (as
# stored on User.role) resolve via str-hash equality.
# 2026-09-08: promoted to module-level data so ad-hoc allowlists across
# route modules can compare levels instead of hand-maintained role lists
# that kept forgetting roles (admin/owner excluded from TEAM_LEAD+ gates,
# admin/owner excluded from WORKSPACE_ADMIN+ gates — same inversion H1
# fixed, replicated in ~10 files).
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


def role_level(role: Union[UserRole, str, None]) -> int:
    """Level for a role (enum or raw string as stored on User.role / config
    maps); case-insensitive for raw strings; 0 if unknown."""
    if role is None:
        return 0
    level = _ROLE_LEVELS.get(role)
    if level is not None:
        return level
    if isinstance(role, str):
        try:
            return _ROLE_LEVELS.get(UserRole(role.strip().lower()), 0)
        except ValueError:
            return 0
    return 0


def user_meets_role(user: User, minimum: UserRole) -> bool:
    """True if the user's role is at or above `minimum` in the hierarchy."""
    return role_level(getattr(user, "role", None)) >= _ROLE_LEVELS.get(minimum, 99)


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

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_level = role_level(current_user.role)
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
