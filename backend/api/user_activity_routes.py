"""
User Activity Routes

API endpoints for user activity tracking and state management.
Frontend sends heartbeats every 30 seconds to track user availability.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User, UserRole, UserActivity, UserActivitySession, UserState
from core.rbac_service import Permission
from core.security.rbac import user_meets_role
from core.security_dependencies import require_permission
from core.user_activity_service import UserActivityService
from core.presence_override_write_service import (
    parse_expiry,
    verified_clear_override,
    verified_get_state,
    verified_set_override,
)
from sqlalchemy.orm import Session

router = BaseAPIRouter(prefix="/api/users", tags=["user-activity"])


def _ensure_own_activity(user_id: str, current_user: User) -> None:
    """Activity heartbeats/overrides are per-user: the path user must be
    the caller. Previously any authenticated user could forge or override
    anyone else's presence."""
    if str(user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage another user's activity state",
        )


def _ensure_session_access(session: UserActivitySession, current_user: User) -> None:
    """Activity sessions expose bearer tokens — owner-only, plus the
    supervisor band (team_lead+) that monitors live sessions."""
    if str(session.user_id) != str(current_user.id) and not user_meets_role(
        current_user, UserRole.TEAM_LEAD
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required role: team_lead or higher",
        )


# ============================================================================
# Request/Response Models
# ============================================================================

class HeartbeatRequest(BaseModel):
    """Heartbeat request from frontend"""
    session_token: str
    session_type: str = "web"  # "web" or "desktop"
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None


class UserStateResponse(BaseModel):
    """User state response.

    ``verification``/``operation_id``/``audit_id`` are additive presence
    receipt metadata; the original fields and meanings are unchanged.
    """
    user_id: str
    state: str  # "online", "away", "offline"
    last_activity_at: str
    manual_override: bool
    manual_override_expires_at: Optional[str]
    success: bool = True
    operation_id: Optional[str] = None
    audit_id: Optional[str] = None
    verification: Optional[dict] = None


class ManualOverrideRequest(BaseModel):
    """Manual state override request"""
    state: str  # "online", "away", "offline"
    expires_at: Optional[str] = None  # ISO datetime string
    operation_id: Optional[str] = None


class SupervisorInfo(BaseModel):
    """Available supervisor info"""
    user_id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    state: str
    last_activity_at: str
    specialty: Optional[str]


class AvailableSupervisorsResponse(BaseModel):
    """Available supervisors response"""
    supervisors: List[SupervisorInfo]
    total_count: int


class SessionInfo(BaseModel):
    """Active session info"""
    id: str
    session_type: str
    session_token: str
    last_heartbeat: str
    user_agent: Optional[str]
    ip_address: Optional[str]
    created_at: str


class ActiveSessionsResponse(BaseModel):
    """Active sessions response"""
    sessions: List[SessionInfo]
    total_count: int


# ============================================================================
# API Endpoints
# ============================================================================

def _presence_result(result: dict):
    """Map a verified presence decision onto the existing response fields."""
    state = str(result.get("status") or "")
    if state in ("verified", "already_applied", "no_change"):
        data = result.get("data") or {
            key: result.get(key) for key in (
                "user_id", "state", "last_activity_at", "manual_override",
                "manual_override_expires_at")
        }
        return UserStateResponse(
            **data,
            success=True,
            operation_id=result.get("operation_id"),
            audit_id=result.get("audit_id"),
            verification=result.get("verification"),
        )
    if state == "refused":
        raise HTTPException(
            status_code=int(result.get("http_status") or 403),
            detail=str(result.get("error") or "Presence change refused"),
        )
    if state == "conflict":
        raise HTTPException(
            status_code=int(result.get("http_status") or 409),
            detail=str(result.get("error") or "Presence changed"),
        )
    body = {
        "success": False,
        "error": result.get("error") or result.get("message"),
        "operation_id": result.get("operation_id"),
        "audit_id": result.get("audit_id"),
        "verification": result.get("verification"),
    }
    data = result.get("data")
    if isinstance(data, dict):
        body.update(data)
    # Never return 2xx for an ambiguous commit: existing web consumers treat
    # response.ok as success and would replace a valid state with this body.
    code = 503 if state in ("committed_unverified", "effect_unknown") else 409
    return JSONResponse(status_code=code, content=body)


@router.post("/{user_id}/activity/heartbeat", response_model=UserStateResponse)
async def send_heartbeat(
    user_id: str,
    heartbeat: HeartbeatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send user activity heartbeat (called by frontend every 30 seconds).

    Updates user's activity state based on recent heartbeat.
    Creates session if it doesn't exist.
    """
    _ensure_own_activity(user_id, current_user)
    service = UserActivityService(db)

    try:
        activity = await service.record_heartbeat(
            user_id=user_id,
            session_token=heartbeat.session_token,
            session_type=heartbeat.session_type,
            user_agent=heartbeat.user_agent,
            ip_address=heartbeat.ip_address
        )

        return UserStateResponse(
            user_id=activity.user_id,
            state=activity.state.value,
            last_activity_at=activity.last_activity_at.isoformat(),
            manual_override=activity.manual_override,
            manual_override_expires_at=activity.manual_override_expires_at.isoformat()
            if activity.manual_override_expires_at else None
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error"
        )


@router.get("/{user_id}/activity/state", response_model=UserStateResponse)
async def get_user_state(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user state with normalized UTC timestamps.

    Existing authenticated read visibility is preserved; expired overrides
    are cleared before the response so a stale manual state is not reported
    active.
    """
    result = await verified_get_state(
        db, actor=current_user, target_user_id=user_id)
    return _presence_result(result)


@router.post("/{user_id}/activity/override", response_model=UserStateResponse)
async def set_manual_override(
    user_id: str,
    override: ManualOverrideRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set a verified manual presence override.

    The actor/target guard, activity CAS, audit receipt and independent
    readback are in the service transaction. Invalid input is a typed 400.
    """
    try:
        state = UserState(override.state)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid state: {override.state}. Must be 'online', "
                "'away', or 'offline'"
            ),
        )
    try:
        expires_at = parse_expiry(override.expires_at)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid datetime format: {override.expires_at}",
        )
    try:
        result = await verified_set_override(
            db,
            actor=current_user,
            target_user_id=user_id,
            state=state,
            expires_at=expires_at,
            operation_id=override.operation_id,
        )
        return _presence_result(result)
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error"
        )


@router.delete("/{user_id}/activity/override", response_model=UserStateResponse)
async def clear_manual_override(
    user_id: str,
    operation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear a manual override with verified readback.

    Existing response fields are preserved; receipt metadata is additive.
    """
    try:
        result = await verified_clear_override(
            db,
            actor=current_user,
            target_user_id=user_id,
            operation_id=operation_id,
        )
        return _presence_result(result)
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error"
        )


@router.get(
    "/available-supervisors",
    response_model=AvailableSupervisorsResponse,
    # user:view per the permission matrix (viewer+): a workspace directory
    # read. This is the endpoint that makes USER_VIEW an enforced
    # permission instead of a granted-but-never-checked one.
    dependencies=[Depends(require_permission(Permission.USER_VIEW))],
)
async def get_available_supervisors(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of users available for supervision (online or away).

    Optionally filter by category/specialty.
    """
    service = UserActivityService(db)

    try:
        supervisors = await service.get_available_supervisors(category)

        # Filter by category if specified
        if category:
            supervisors = [
                s for s in supervisors
                if s.get("specialty") == category
            ]

        return AvailableSupervisorsResponse(
            supervisors=supervisors,
            total_count=len(supervisors)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error"
        )


@router.get("/{user_id}/activity/sessions", response_model=ActiveSessionsResponse)
async def get_active_sessions(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all active sessions for a user."""
    _ensure_own_activity(user_id, current_user)
    service = UserActivityService(db)

    try:
        sessions = await service.get_active_sessions(user_id)

        session_infos = [
            SessionInfo(
                id=s.id,
                session_type=s.session_type,
                session_token=s.session_token,
                last_heartbeat=s.last_heartbeat.isoformat(),
                user_agent=s.user_agent,
                ip_address=s.ip_address,
                created_at=s.created_at.isoformat()
            )
            for s in sessions
        ]

        return ActiveSessionsResponse(
            sessions=session_infos,
            total_count=len(session_infos)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error"
        )


@router.delete("/activity/sessions/{session_token}")
async def terminate_session(
    session_token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Terminate a specific session (e.g., user logout).

    Owner-only (plus the supervisor band): the session token identifies the
    victim, so an arbitrary authenticated user must not be able to kill
    someone else's session.
    """
    session = db.query(UserActivitySession).filter(
        UserActivitySession.session_token == session_token
    ).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_token}"
        )
    _ensure_session_access(session, current_user)

    service = UserActivityService(db)

    try:
        success = await service.terminate_session(session_token)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_token}"
            )

        return {"success": True, "message": "Session terminated"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error"
        )
