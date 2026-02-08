"""
User Activity Routes

API endpoints for user activity tracking and state management.
Frontend sends heartbeats every 30 seconds to track user availability.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core.database import get_db
from core.models import UserState
from core.user_activity_service import UserActivityService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/users", tags=["user-activity"])


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
    """User state response"""
    user_id: str
    state: str  # "online", "away", "offline"
    last_activity_at: str
    manual_override: bool
    manual_override_expires_at: Optional[str]


class ManualOverrideRequest(BaseModel):
    """Manual state override request"""
    state: str  # "online", "away", "offline"
    expires_at: Optional[str] = None  # ISO datetime string


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

@router.post("/{user_id}/activity/heartbeat", response_model=UserStateResponse)
async def send_heartbeat(
    user_id: str,
    heartbeat: HeartbeatRequest,
    db: Session = Depends(get_db)
):
    """
    Send user activity heartbeat (called by frontend every 30 seconds).

    Updates user's activity state based on recent heartbeat.
    Creates session if it doesn't exist.
    """
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
            detail=f"Failed to record heartbeat: {str(e)}"
        )


@router.get("/{user_id}/activity/state", response_model=UserStateResponse)
async def get_user_state(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Get current user state (online/away/offline)."""
    service = UserActivityService(db)

    try:
        state = await service.get_user_state(user_id)

        # Get activity record for full response
        activity = await service.get_user_state(user_id)
        activity_record = db.query(service.db.query(UserActivity).filter(
            UserActivity.user_id == user_id
        ).first()).first() if hasattr(service, 'db') else None

        if not activity_record:
            # Create minimal response
            return UserStateResponse(
                user_id=user_id,
                state=state.value,
                last_activity_at=datetime.utcnow().isoformat(),
                manual_override=False,
                manual_override_expires_at=None
            )

        return UserStateResponse(
            user_id=activity_record.user_id,
            state=activity_record.state.value,
            last_activity_at=activity_record.last_activity_at.isoformat(),
            manual_override=activity_record.manual_override,
            manual_override_expires_at=activity_record.manual_override_expires_at.isoformat()
            if activity_record.manual_override_expires_at else None
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user state: {str(e)}"
        )


@router.post("/{user_id}/activity/override", response_model=UserStateResponse)
async def set_manual_override(
    user_id: str,
    override: ManualOverrideRequest,
    db: Session = Depends(get_db)
):
    """
    Manually set user state with optional expiry.

    Allows users to override automatic activity tracking.
    """
    service = UserActivityService(db)

    try:
        # Validate state
        try:
            state = UserState(override.state)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid state: {override.state}. Must be 'online', 'away', or 'offline'"
            )

        # Parse expiry if provided
        expires_at = None
        if override.expires_at:
            try:
                expires_at = datetime.fromisoformat(override.expires_at.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid datetime format: {override.expires_at}"
                )

        activity = await service.set_manual_override(
            user_id=user_id,
            state=state,
            expires_at=expires_at
        )

        return UserStateResponse(
            user_id=activity.user_id,
            state=activity.state.value,
            last_activity_at=activity.last_activity_at.isoformat(),
            manual_override=activity.manual_override,
            manual_override_expires_at=activity.manual_override_expires_at.isoformat()
            if activity.manual_override_expires_at else None
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set manual override: {str(e)}"
        )


@router.delete("/{user_id}/activity/override", response_model=UserStateResponse)
async def clear_manual_override(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Clear manual override and return to automatic activity tracking.
    """
    service = UserActivityService(db)

    try:
        activity = await service.clear_manual_override(user_id)

        return UserStateResponse(
            user_id=activity.user_id,
            state=activity.state.value,
            last_activity_at=activity.last_activity_at.isoformat(),
            manual_override=activity.manual_override,
            manual_override_expires_at=activity.manual_override_expires_at.isoformat()
            if activity.manual_override_expires_at else None
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear manual override: {str(e)}"
        )


@router.get("/available-supervisors", response_model=AvailableSupervisorsResponse)
async def get_available_supervisors(
    category: Optional[str] = None,
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
            detail=f"Failed to get available supervisors: {str(e)}"
        )


@router.get("/{user_id}/activity/sessions", response_model=ActiveSessionsResponse)
async def get_active_sessions(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Get all active sessions for a user."""
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
            detail=f"Failed to get active sessions: {str(e)}"
        )


@router.delete("/activity/sessions/{session_token}")
async def terminate_session(
    session_token: str,
    db: Session = Depends(get_db)
):
    """
    Terminate a specific session (e.g., user logout).
    """
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
            detail=f"Failed to terminate session: {str(e)}"
        )
