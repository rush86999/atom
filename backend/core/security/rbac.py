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
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != required_role:
            logger.warning(
                f"Access denied: user {current_user.id} has role {current_user.role}, "
                f"required {required_role}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )
        return current_user

    return role_checker
