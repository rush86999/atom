from fastapi import Depends, HTTPException, status
from core.auth import get_current_user
from core.models import User
from core.rbac_service import RBACService, Permission

def require_permission(permission: Permission):
    """Factory for permission dependency"""
    async def permission_checker(user: User = Depends(get_current_user)):
        if not RBACService.check_permission(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires permission: {permission.value}"
            )
        return user
    return permission_checker
