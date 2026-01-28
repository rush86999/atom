from fastapi import Depends, HTTPException, status
from core.auth import get_current_user
from core.models import User, UserRole

async def get_super_admin(current_user: User = Depends(get_current_user)):
    """
    Dependency to ensure the current user is a super admin.
    Used for sensitive platform-level health and administrative routes.
    """
    if current_user.role != UserRole.SUPER_ADMIN.value and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin access required for this operation"
        )
    return current_user
