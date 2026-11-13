"""
User Management API Routes
Provides endpoints for user profile and session management

WA-075: "Active Sessions" is an inventory view over ``UserSession``; the
enforcement mechanism for a revoked session is the existing durable
``RevokedToken`` ledger read by ``core.auth.credential_session_matches``.
Revocation here therefore writes that ledger — flipping a display flag alone
never terminated a session.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy.orm import Session

from core import session_registry
from core.auth import get_current_user, oauth2_scheme, resolve_request_access_token
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User, UserSession

router = BaseAPIRouter(prefix="/api/users", tags=["User Management"])


@dataclass(frozen=True)
class CurrentSessionAuth:
    """Authenticated caller plus the exact credential that authorized it.

    ``__iter__`` keeps the historical ``(user, token)`` unpacking contract for
    any caller that still uses ``get_current_session_token`` as a dependency.
    """

    user: User
    token: Optional[str]
    payload: Optional[Dict[str, Any]] = None

    @property
    def jti(self) -> Optional[str]:
        value = (self.payload or {}).get("jti")
        return value if isinstance(value, str) and value else None

    def __iter__(self):
        yield self.user
        yield self.token


async def get_current_session_token(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> CurrentSessionAuth:
    """
    Extract the credential that authorized this request.

    The user is already authenticated by ``get_current_user`` (including the
    durable revocation check). This helper only resolves the exact bearer or
    NextAuth cookie so ``is_current`` and per-session revocation can identify
    the session without trusting a client-supplied token in the body.
    """
    presented = resolve_request_access_token(request, token)
    payload = session_registry.decode_session_claims(presented) if presented else None
    return CurrentSessionAuth(user=current_user, token=presented, payload=payload)


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

    model_config = ConfigDict(from_attributes=True)


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
    # WA-075: False when the inventory row has no token identity this server
    # can prove. Such a row cannot be revoked, so the UI must not imply it was.
    revocable: bool = True

    model_config = ConfigDict(from_attributes=True)


class RevokeSessionResponse(BaseModel):
    """Response after revoking session"""
    message: str
    revoked: Optional[int] = None
    skipped: Optional[int] = None
    already_applied: Optional[bool] = None
    verification: Optional[Dict[str, Any]] = None
    # WA-075 honesty: inventory-based revocation cannot reach tokens that were
    # never recorded (mobile/SSO/enterprise issuance, pre-deployment tokens).
    untracked_tokens_possible: Optional[bool] = None
    residual_window_seconds: Optional[int] = None
    current_session_tracked: Optional[bool] = None


class SessionHeartbeatResponse(BaseModel):
    """Result of recording activity for the presented session."""
    tracked: bool
    registered: bool
    is_current: bool
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
    auth: CurrentSessionAuth = Depends(get_current_session_token),
    db: Session = Depends(get_db)
):
    """
    List all active sessions for the current user

    Returns active, non-expired inventory rows ordered by most recent activity.
    Owner-scoped: rows are only ever read for the authenticated user. Token
    material (raw or fingerprint) is never returned.
    """
    sessions = db.query(UserSession).filter(
        UserSession.user_id == auth.user.id,
        UserSession.is_active == True,  # noqa: E712 - SQL boolean predicate
        UserSession.expires_at > datetime.now(timezone.utc)
    ).order_by(UserSession.last_active_at.desc()).limit(50).all()

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
            is_current=session_registry.is_current_row(s, jti=auth.jti, token=auth.token),
            revocable=session_registry.is_revocable(s),
        )
        for s in sessions
    ]


@router.post("/sessions", response_model=SessionHeartbeatResponse)
async def record_current_session(
    request: Request,
    auth: CurrentSessionAuth = Depends(get_current_session_token),
    db: Session = Depends(get_db)
):
    """
    Heartbeat for the presented session.

    The credential comes from the Authorization header/cookie only — a token in
    the request body is ignored, so a client can never record (or later revoke)
    a session it does not hold. Missing inventory is registered from the
    server-verified credential, and the response says whether it was tracked.
    """
    if not auth.token:
        return SessionHeartbeatResponse(
            tracked=False, registered=False, is_current=False,
            message="No session credential was presented; nothing was recorded.",
        )

    row, registered = session_registry.touch_session(
        db, auth.user, auth.token, request=request, payload=auth.payload,
    )
    if row is None:
        return SessionHeartbeatResponse(
            tracked=False, registered=False, is_current=False,
            message=(
                "This session is not in the device inventory, so it cannot be "
                "revoked from this page. It will stop working when it expires."
            ),
        )
    return SessionHeartbeatResponse(
        tracked=True,
        registered=registered,
        is_current=True,
        message=(
            "This device was newly recorded in the session inventory."
            if registered else "Session activity recorded."
        ),
    )


@router.delete("/sessions/{session_id}", response_model=RevokeSessionResponse)
async def revoke_session(
    session_id: str,
    request: Request,
    auth: CurrentSessionAuth = Depends(get_current_session_token),
    db: Session = Depends(get_db)
):
    """
    Revoke a specific session

    Owner-scoped lookup (another user's id is a 404). The row's token identity
    is resolved and revoked through the durable ``RevokedToken`` ledger in the
    same commit that deactivates the inventory row. The effect is confirmed by
    a fresh database read before success is reported.
    """
    session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == auth.user.id
    ).first()

    if not session:
        raise router.not_found_error("Session", session_id)

    outcome = session_registry.revoke_rows(
        db, auth.user, [session],
        reason="session_revoked",
        request=request,
        action="session_revoked",
    )

    if outcome["verification"]["status"] != "verified":
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={
            "message": "Session revocation could not be confirmed. Do not assume the device is signed out.",
            "revoked": 0,
            "skipped": outcome["skipped"],
            "verification": outcome["verification"],
            "replay": "do_not_repeat",
        })

    if outcome["skipped"]:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
            "message": (
                "This entry could not be tied to a revocable token, so it was removed "
                "from the device list but the credential may keep working until it expires."
            ),
            "revoked": outcome["revoked"],
            "skipped": outcome["skipped"],
            "skip_reasons": outcome["skip_reasons"],
            "verification": outcome["verification"],
            "residual_window_seconds": session_registry.ACCESS_TOKEN_SECONDS,
        })

    return RevokeSessionResponse(
        message="Session revoked successfully",
        revoked=outcome["revoked"],
        skipped=0,
        already_applied=outcome["already_revoked"] > 0,
        verification=outcome["verification"],
        untracked_tokens_possible=False,
    )


@router.delete("/sessions", response_model=RevokeSessionResponse)
async def revoke_all_sessions(
    request: Request,
    auth: CurrentSessionAuth = Depends(get_current_session_token),
    db: Session = Depends(get_db)
):
    """
    Revoke all recorded sessions except the current one

    Only inventory rows can be revoked. Tokens that were never recorded (other
    issuance paths, pre-deployment credentials) keep working until they expire;
    the response states that residual window instead of implying a global
    sign-out. The current browser session is terminated by the client's
    NextAuth sign-out event calling ``/api/auth/logout``.
    """
    sessions = db.query(UserSession).filter(
        UserSession.user_id == auth.user.id,
        UserSession.is_active == True,  # noqa: E712 - SQL boolean predicate
    ).all()

    current_rows = [
        s for s in sessions
        if session_registry.is_current_row(s, jti=auth.jti, token=auth.token)
    ]
    current_ids = {s.id for s in current_rows}
    targets = [s for s in sessions if s.id not in current_ids]

    outcome = session_registry.revoke_rows(
        db, auth.user, targets,
        reason="sessions_revoked_all",
        request=request,
        action="sessions_revoked",
    )

    current_session_tracked: Optional[bool] = bool(current_rows) if auth.token else None

    if outcome["verification"]["status"] != "verified":
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={
            "message": "Sign-out from other devices could not be confirmed. Do not assume they are signed out.",
            "revoked": 0,
            "skipped": outcome["skipped"],
            "verification": outcome["verification"],
            "replay": "do_not_repeat",
        })

    unverifiable = [item for item in outcome["skip_reasons"] if item["reason"] != "expired"]
    if unverifiable:
        message = (
            f"{outcome['revoked']} recorded session(s) revoked. {len(unverifiable)} "
            "device entry(ies) had no revocable token and were removed from the list only."
        )
    else:
        message = "All sessions revoked successfully"

    return RevokeSessionResponse(
        message=message,
        revoked=outcome["revoked"],
        skipped=len(unverifiable),
        already_applied=outcome["revoked"] == 0,
        verification=outcome["verification"],
        # Truthful even on a clean run: only issuance paths that call the
        # registry are in the inventory, so unrecorded tokens may still be
        # live for up to the access-token lifetime.
        untracked_tokens_possible=True,
        residual_window_seconds=session_registry.ACCESS_TOKEN_SECONDS,
        current_session_tracked=current_session_tracked,
    )
