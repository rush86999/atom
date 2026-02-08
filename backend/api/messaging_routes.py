"""
Messaging API Routes

Provides REST endpoints for proactive messaging, scheduled messages,
and condition monitoring features.
"""

from datetime import datetime, timezone
import logging
from typing import List, Optional
from fastapi import BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db_session
from core.models import ProactiveMessage, ProactiveMessageStatus
from core.proactive_messaging_service import ProactiveMessagingService

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/v1/messaging", tags=["messaging"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateProactiveMessageRequest(BaseModel):
    """Request to create a proactive message"""
    agent_id: str = Field(..., description="ID of the agent sending the message")
    platform: str = Field(..., description="Target platform (slack, discord, whatsapp, etc.)")
    recipient_id: str = Field(..., description="Target recipient ID")
    content: str = Field(..., description="Message content")
    scheduled_for: Optional[datetime] = Field(None, description="Optional scheduled send time")
    send_now: bool = Field(False, description="Send immediately if approved")
    governance_metadata: Optional[dict] = Field(None, description="Optional governance metadata")


class ProactiveMessageResponse(BaseModel):
    """Response for proactive message operations"""
    id: str
    agent_id: str
    agent_name: str
    agent_maturity_level: str
    platform: str
    recipient_id: str
    content: str
    scheduled_for: Optional[datetime]
    send_now: bool
    status: str
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    rejection_reason: Optional[str]
    sent_at: Optional[datetime]
    error_message: Optional[str]
    platform_message_id: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ApproveMessageRequest(BaseModel):
    """Request to approve a pending message"""
    approver_user_id: str = Field(..., description="ID of the user approving")


class RejectMessageRequest(BaseModel):
    """Request to reject a pending message"""
    rejecter_user_id: str = Field(..., description="ID of the user rejecting")
    rejection_reason: str = Field(..., description="Reason for rejection")


# ============================================================================
# Proactive Messaging Endpoints
# ============================================================================

@router.post("/proactive/send", response_model=ProactiveMessageResponse)
async def send_proactive_message(
    request: CreateProactiveMessageRequest,
    db: Session = Depends(get_db_session),
):
    """
    Send a proactive message from an agent.

    The message behavior depends on the agent's maturity level:
    - STUDENT: Blocked (returns 403)
    - INTERN: Requires human approval (status=PENDING)
    - SUPERVISED: Auto-approved and sent with monitoring
    - AUTONOMOUS: Auto-approved and sent immediately

    Use scheduled_for to delay sending, or send_now=True for immediate delivery.
    """
    service = ProactiveMessagingService(db)

    message = service.create_proactive_message(
        agent_id=request.agent_id,
        platform=request.platform,
        recipient_id=request.recipient_id,
        content=request.content,
        scheduled_for=request.scheduled_for,
        send_now=request.send_now,
        governance_metadata=request.governance_metadata,
    )

    return message


@router.post("/proactive/schedule", response_model=ProactiveMessageResponse)
async def schedule_proactive_message(
    request: CreateProactiveMessageRequest,
    db: Session = Depends(get_db_session),
):
    """
    Schedule a proactive message for later delivery.

    Same as /proactive/send but always requires a scheduled_for time.
    The message will be sent when the scheduled time arrives.
    """
    if not request.scheduled_for:
        raise router.validation_error(
            field="scheduled_for",
            message="scheduled_for is required for scheduled messages"
        )

    service = ProactiveMessagingService(db)

    message = service.create_proactive_message(
        agent_id=request.agent_id,
        platform=request.platform,
        recipient_id=request.recipient_id,
        content=request.content,
        scheduled_for=request.scheduled_for,
        send_now=False,  # Always False for scheduled
        governance_metadata=request.governance_metadata,
    )

    return message


@router.get("/proactive/queue", response_model=List[ProactiveMessageResponse])
async def get_pending_messages(
    agent_id: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db_session),
):
    """
    Get all pending messages awaiting approval or sending.

    Can filter by agent_id and/or platform.
    """
    service = ProactiveMessagingService(db)

    messages = service.get_pending_messages(
        agent_id=agent_id,
        platform=platform,
        limit=limit,
    )

    return messages


@router.post("/proactive/approve/{message_id}", response_model=ProactiveMessageResponse)
async def approve_proactive_message(
    message_id: str,
    request: ApproveMessageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
):
    """
    Approve a pending proactive message (for INTERN agents).

    Once approved, the message will be sent immediately (if not scheduled).
    """
    service = ProactiveMessagingService(db)

    message = service.approve_message(
        message_id=message_id,
        approver_user_id=request.approver_user_id,
    )

    return message


@router.post("/proactive/reject/{message_id}", response_model=ProactiveMessageResponse)
async def reject_proactive_message(
    message_id: str,
    request: RejectMessageRequest,
    db: Session = Depends(get_db_session),
):
    """
    Reject a pending proactive message.

    The message will be marked as CANCELLED and will not be sent.
    """
    service = ProactiveMessagingService(db)

    message = service.reject_message(
        message_id=message_id,
        rejecter_user_id=request.rejecter_user_id,
        rejection_reason=request.rejection_reason,
    )

    return message


@router.delete("/proactive/cancel/{message_id}", response_model=ProactiveMessageResponse)
async def cancel_proactive_message(
    message_id: str,
    db: Session = Depends(get_db_session),
):
    """
    Cancel a scheduled or pending message.

    Cannot cancel messages that are already SENT or CANCELLED.
    """
    service = ProactiveMessagingService(db)

    message = service.cancel_message(message_id=message_id)

    return message


@router.get("/proactive/history", response_model=List[ProactiveMessageResponse])
async def get_message_history(
    agent_id: Optional[str] = None,
    recipient_id: Optional[str] = None,
    platform: Optional[str] = None,
    message_status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db_session),
):
    """
    Get message history with optional filters.

    Can filter by:
    - agent_id: Only messages from this agent
    - recipient_id: Only messages to this recipient
    - platform: Only messages to this platform
    - status: Only messages with this status
    """
    service = ProactiveMessagingService(db)

    messages = service.get_message_history(
        agent_id=agent_id,
        recipient_id=recipient_id,
        platform=platform,
        status=message_status,
        limit=limit,
    )

    return messages


@router.get("/proactive/{message_id}", response_model=ProactiveMessageResponse)
async def get_proactive_message(
    message_id: str,
    db: Session = Depends(get_db_session),
):
    """Get a specific proactive message by ID."""
    service = ProactiveMessagingService(db)

    message = service.get_message(message_id=message_id)

    if not message:
        raise router.not_found_error("Proactive message", message_id)

    return message


@router.post("/proactive/_send_scheduled")
async def send_scheduled_messages(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
):
    """
    Internal endpoint to send scheduled messages.

    This should be called by a background scheduler (e.g., cron or APScheduler).
    Typically runs every minute to send messages whose scheduled_for time has arrived.

    Returns counts of sent and failed messages.
    """
    service = ProactiveMessagingService(db)

    result = await service.send_scheduled_messages()

    return result
