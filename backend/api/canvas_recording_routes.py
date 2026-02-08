"""
Canvas Recording API Routes

Provides REST API endpoints for managing canvas session recordings.
Recordings are used for governance, audit trails, and user review.

Features:
- Start/stop recordings
- Record events during sessions
- List and retrieve recordings
- Flag recordings for review
- Playback/replay support
"""

import logging
from typing import Optional
from fastapi import Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.canvas_recording_service import CanvasRecordingService, get_canvas_recording_service
from core.database import get_db
from core.models import CanvasRecording, User

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/canvas/recording", tags=["canvas-recording"])


# Request/Response Models
class StartRecordingRequest(BaseModel):
    """Request to start a canvas recording"""
    agent_id: str = Field(..., description="Agent ID that is performing actions")
    canvas_id: Optional[str] = Field(None, description="Optional canvas ID being recorded")
    reason: str = Field(..., description="Why recording is initiated")
    session_id: Optional[str] = Field(None, description="Optional session ID")
    tags: Optional[list] = Field(default_factory=list, description="Tags for categorization")


class StartRecordingResponse(BaseModel):
    """Response when recording is started"""
    recording_id: str
    agent_id: str
    user_id: str
    reason: str
    status: str


class RecordEventRequest(BaseModel):
    """Request to record an event"""
    event_type: str = Field(..., description="Type of event (operation_start, update, complete, etc.)")
    event_data: dict = Field(..., description="Event data")


class StopRecordingRequest(BaseModel):
    """Request to stop a recording"""
    status: str = Field(default="completed", description="Final status")
    summary: Optional[str] = Field(None, description="Optional summary")


class RecordingResponse(BaseModel):
    """Recording details response"""
    recording_id: str
    agent_id: str
    user_id: str
    canvas_id: Optional[str]
    session_id: Optional[str]
    reason: str
    status: str
    tags: list
    started_at: str
    stopped_at: Optional[str]
    duration_seconds: Optional[float]
    event_count: int
    summary: Optional[str]
    events: list
    recording_metadata: dict
    expires_at: Optional[str]
    flagged_for_review: bool


class FlagRecordingRequest(BaseModel):
    """Request to flag a recording for review"""
    flag_reason: str = Field(..., description="Why it's flagged")


# Endpoints
@router.post("/start", response_model=StartRecordingResponse)
async def start_recording(
    request: StartRecordingRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Start recording a canvas session.

    - **agent_id**: Agent ID that will perform actions
    - **canvas_id**: Optional canvas ID being recorded
    - **reason**: Why recording is initiated (autonomous_action, manual, governance, etc.)
    - **session_id**: Optional session ID for grouping
    - **tags**: Optional tags for categorization

    Returns recording_id for use in subsequent event recording.
    """
    try:
        recording_service = get_canvas_recording_service(db)

        recording_id = await recording_service.start_recording(
            user_id=user.id,
            agent_id=request.agent_id,
            canvas_id=request.canvas_id,
            reason=request.reason,
            session_id=request.session_id,
            tags=request.tags
        )

        return StartRecordingResponse(
            recording_id=recording_id,
            agent_id=request.agent_id,
            user_id=user.id,
            reason=request.reason,
            status="recording"
        )

    except Exception as e:
        logger.error(f"Failed to start recording: {e}")
        raise router.internal_error(
            message=f"Failed to start recording: {str(e)}"
        )


@router.post("/{recording_id}/event")
async def record_event(
    recording_id: str,
    request: RecordEventRequest,
    db: Session = Depends(get_db)
):
    """
    Record an event during canvas session.

    - **event_type**: Type of event (operation_start, update, complete, error, etc.)
    - **event_data**: Event data specific to the event type

    Common event types:
    - operation_start: When an operation begins
    - operation_update: Progress updates
    - operation_complete: When operation completes
    - error: When an error occurs
    - view_switch: When view changes
    - user_input: When user provides input
    """
    try:
        recording_service = get_canvas_recording_service(db)

        await recording_service.record_event(
            recording_id=recording_id,
            event_type=request.event_type,
            event_data=request.event_data
        )

        return router.success_response(
            message="Event recorded successfully"
        )

    except Exception as e:
        logger.error(f"Failed to record event: {e}")
        raise router.internal_error(
            message=f"Failed to record event: {str(e)}"
        )


@router.post("/{recording_id}/stop")
async def stop_recording(
    recording_id: str,
    request: StopRecordingRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Stop recording and finalize.

    - **status**: Final status (completed, failed, cancelled)
    - **summary**: Optional summary of the session

    Calculates duration, generates summary, and sets expiration.
    """
    try:
        recording_service = get_canvas_recording_service(db)

        await recording_service.stop_recording(
            recording_id=recording_id,
            status=request.status,
            summary=request.summary
        )

        return router.success_response(
            message="Recording stopped successfully"
        )

    except Exception as e:
        logger.error(f"Failed to stop recording: {e}")
        raise router.internal_error(
            message=f"Failed to stop recording: {str(e)}"
        )


@router.get("/{recording_id}", response_model=RecordingResponse)
async def get_recording(
    recording_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get recording details with full event timeline.

    Returns complete recording with all events for playback/review.
    """
    try:
        recording_service = get_canvas_recording_service(db)

        recording = await recording_service.get_recording(recording_id)

        if not recording:
            raise router.not_found_error(
                resource="Recording",
                resource_id=recording_id
            )

        # Verify user owns this recording
        if recording["user_id"] != user.id:
            raise router.permission_denied_error(
                action="get_recording",
                resource="Recording",
                details={"recording_id": recording_id}
            )

        return RecordingResponse(**recording)

    except Exception as e:
        if isinstance(e, Exception) and "not found" in str(e).lower():
            raise
        logger.error(f"Failed to get recording: {e}")
        raise router.internal_error(
            message=f"Failed to get recording: {str(e)}"
        )


@router.get("", response_model=list[RecordingResponse])
async def list_recordings(
    agent_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    List recordings for current user.

    - **agent_id**: Optional filter by agent ID
    - **limit**: Max results (default 50)
    - **offset**: Pagination offset

    Returns list of recordings with metadata (not full events).
    """
    try:
        recording_service = get_canvas_recording_service(db)

        recordings = await recording_service.list_recordings(
            user_id=user.id,
            agent_id=agent_id,
            limit=limit,
            offset=offset
        )

        return router.success_list_response(
            items=[RecordingResponse(**r).dict() for r in recordings],
            total=len(recordings),
            message=f"Retrieved {len(recordings)} recordings"
        )

    except Exception as e:
        logger.error(f"Failed to list recordings: {e}")
        raise router.internal_error(
            message=f"Failed to list recordings: {str(e)}"
        )


@router.post("/{recording_id}/flag")
async def flag_recording(
    recording_id: str,
    request: FlagRecordingRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Flag a recording for human review.

    - **flag_reason**: Why it's flagged (suspicious_activity, error, compliance, etc.)

    Flagged recordings appear in review queue for governance team.
    """
    try:
        # Verify recording exists and user owns it
        recording = db.query(CanvasRecording).filter(
            CanvasRecording.recording_id == recording_id,
            CanvasRecording.user_id == user.id
        ).first()

        if not recording:
            raise router.not_found_error(
                resource="Recording",
                resource_id=recording_id
            )

        recording_service = get_canvas_recording_service(db)

        await recording_service.flag_for_review(
            recording_id=recording_id,
            flag_reason=request.flag_reason,
            flagged_by=user.id
        )

        return router.success_response(
            message="Recording flagged for review successfully"
        )

    except Exception as e:
        if isinstance(e, Exception) and "not found" in str(e).lower():
            raise
        logger.error(f"Failed to flag recording: {e}")
        raise router.internal_error(
            message=f"Failed to flag recording: {str(e)}"
        )


@router.get("/{recording_id}/replay")
async def get_recording_replay(
    recording_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get recording data for playback/replay.

    Returns events in chronological order for replay in frontend.
    Similar to get_recording but optimized for playback.
    """
    try:
        recording_service = get_canvas_recording_service(db)

        recording = await recording_service.get_recording(recording_id)

        if not recording:
            raise router.not_found_error(
                resource="Recording",
                resource_id=recording_id
            )

        # Verify user owns this recording
        if recording["user_id"] != user.id:
            raise router.permission_denied_error(
                action="get_recording_replay",
                resource="Recording",
                details={"recording_id": recording_id}
            )

        # Return replay-optimized format
        return router.success_response(
            data={
                "recording_id": recording_id,
                "agent_id": recording["agent_id"],
                "started_at": recording["started_at"],
                "duration_seconds": recording["duration_seconds"],
                "events": recording["events"],  # Already in chronological order
                "recording_metadata": recording["recording_metadata"]
            },
            message="Recording replay data retrieved successfully"
        )

    except Exception as e:
        if isinstance(e, Exception) and "not found" in str(e).lower():
            raise
        logger.error(f"Failed to get recording replay: {e}")
        raise router.internal_error(
            message=f"Failed to get recording replay: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return router.success_response(
        data={"status": "healthy", "service": "canvas_recording"},
        message="Canvas recording service is healthy"
    )
