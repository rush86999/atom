from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.auth import get_current_user as get_current_user_core
from core.database import get_db
from core.models import User

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Get authenticated user from request.
    """
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    return await get_current_user_core(request, token=token, db=db)

async def get_tenant_id(request: Request, current_user: User = Depends(get_current_user)) -> str:
    """
    Get tenant_id from authenticated user.
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User does not belong to a tenant"
        )

    return str(current_user.tenant_id)
