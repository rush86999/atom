from typing import Optional
from fastapi import Depends, HTTPException, Query, WebSocket, status
from sqlalchemy.orm import Session

from core.auth import decode_token, get_current_user
from core.models import User
from core.rbac_service import Permission, RBACService


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


async def get_current_user_websocket(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(lambda: None)  # Will be passed from caller
) -> Optional[User]:
    """
    Get current user from WebSocket connection using JWT token.

    Args:
        websocket: WebSocket connection
        token: JWT token from query params
        db: Database session (optional, passed by caller)

    Returns:
        User object if token is valid, None otherwise
    """
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")

        if not user_id:
            return None

        if db:
            from core.models import User
            user = db.query(User).filter(User.id == user_id).first()
            return user

        return None

    except Exception:
        return None
