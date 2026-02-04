"""
User Management API Routes
Provides endpoints for user profile and session management
"""
from datetime import datetime
from typing import List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import User, UserSession

router = APIRouter(prefix="/api/users", tags=["User Management"])


async def get_current_session_token(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Tuple[User, Optional[str]]:
    """
    Extract the current session token from Authorization header or cookies.

    Returns a tuple of (user, session_token) where session_token may be None
    if the user is authenticated via JWT without a corresponding session record.
    """
    # Try Authorization header first
    auth_header = request.headers.get("Authorization")
    session_token = None

    if auth_header and auth_header.startswith("Bearer "):
        session_token = auth_header.replace("Bearer ", "")

    # Fall back to NextAuth cookies
    if not session_token:
        session_token = request.cookies.get("next-auth.session-token")
        if not session_token:
            session_token = request.cookies.get("__Secure-next-auth.session-token")

    return current_user, session_token


# Request/Response Models
class UserResponse(BaseModel):
    """Detailed user information response"""
    id: str
    email: str
    name: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    role: str
    status: str
    email_verified: Optional[bool]
    tenant_id: Optional[str]
    created_at: Optional[datetime]
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class UserSessionResponse(BaseModel):
    """User session information"""
    id: str
    device_type: Optional[str]
    browser: Optional[str]
    os: Optional[str]
    ip_address: Optional[str]
    last_active_at: Optional[datetime]
    created_at: Optional[datetime]
    is_active: bool
    is_current: bool

    class Config:
        from_attributes = True


class RevokeSessionResponse(BaseModel):
    """Response after revoking session"""
    message: str


# Endpoints
@router.get("/me", response_model=UserResponse)
async def get_current_user_detail(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed current user information

    Returns comprehensive user profile including email verification status,
    tenant association, and account metadata.
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        role=current_user.role,
        status=current_user.status,
        email_verified=getattr(current_user, 'email_verified', None),
        tenant_id=getattr(current_user, 'tenant_id', None),
        created_at=current_user.created_at,
        last_login=current_user.last_login
    )


@router.get("/sessions", response_model=List[UserSessionResponse])
async def list_user_sessions(
    auth_data: Tuple[User, Optional[str]] = Depends(get_current_session_token),
    db: Session = Depends(get_db)
):
    """
    List all active sessions for the current user

    Returns all active, non-expired sessions ordered by most recent activity.
    Useful for session management and security monitoring.
    """
    current_user, current_token = auth_data

    # Find current session if token is available
    current_session_id = None
    if current_token:
        current_session = db.query(UserSession).filter(
            UserSession.session_token == current_token,
            UserSession.user_id == current_user.id
        ).first()
        if current_session:
            current_session_id = current_session.id

    sessions = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active == True,
        UserSession.expires_at > datetime.utcnow()
    ).order_by(UserSession.last_active_at.desc()).all()

    return [
        UserSessionResponse(
            id=s.id,
            device_type=s.device_type,
            browser=s.browser,
            os=s.os,
            ip_address=s.ip_address,
            last_active_at=s.last_active_at,
            created_at=s.created_at,
            is_active=s.is_active,
            is_current=(s.id == current_session_id) if current_session_id else False
        )
        for s in sessions
    ]


@router.delete("/sessions/{session_id}", response_model=RevokeSessionResponse)
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke a specific session

    Allows users to sign out from a specific device/session.
    Requires ownership of the session.
    """
    session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    session.is_active = False
    db.commit()

    return RevokeSessionResponse(message="Session revoked successfully")


@router.delete("/sessions", response_model=RevokeSessionResponse)
async def revoke_all_sessions(
    auth_data: Tuple[User, Optional[str]] = Depends(get_current_session_token),
    db: Session = Depends(get_db)
):
    """
    Revoke all sessions except current

    Signs out the user from all devices except the current one.
    Useful for security incidents or "sign out everywhere" functionality.
    """
    current_user, current_token = auth_data

    # Find current session if token is available
    current_session_id = None
    if current_token:
        current_session = db.query(UserSession).filter(
            UserSession.session_token == current_token,
            UserSession.user_id == current_user.id
        ).first()
        if current_session:
            current_session_id = current_session.id

    # Revoke all active sessions except current
    query = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active == True
    )

    # Exclude current session from revocation
    if current_session_id:
        query = query.filter(UserSession.id != current_session_id)

    query.update({"is_active": False})
    db.commit()

    return RevokeSessionResponse(message="All sessions revoked successfully")
