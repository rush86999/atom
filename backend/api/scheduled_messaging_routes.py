"""
Scheduled Messaging API Routes

Provides REST endpoints for creating and managing scheduled
and recurring messages with natural language support.
"""

from datetime import datetime
import logging
from typing import List, Optional
from fastapi import BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db_session
from core.models import ScheduledMessage
from core.scheduled_messaging_service import ScheduledMessagingService

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/v1/messaging/schedule", tags=["scheduled-messaging"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateScheduledMessageRequest(BaseModel):
    """Request to create a scheduled message"""
    agent_id: str = Field(..., description="ID of the agent")
    platform: str = Field(..., description="Target platform")
    recipient_id: str = Field(..., description="Target recipient ID")
    template: str = Field(..., description="Message template (can include {{variables}})")
    schedule_type: str = Field(..., description="'one_time' or 'recurring'")
    scheduled_for: Optional[datetime] = Field(None, description="Specific time (for one_time)")
    cron_expression: Optional[str] = Field(None, description="Cron expression (for recurring)")
    natural_language_schedule: Optional[str] = Field(
        None,
        description="Natural language (e.g., 'every day at 9am')"
    )
    template_variables: Optional[dict] = Field(
        None,
        description="Variable definitions for template substitution"
    )
    max_runs: Optional[int] = Field(None, description="Max executions (None = infinite)")
    end_date: Optional[datetime] = Field(None, description="Stop after this date")
    timezone: str = Field("UTC", description="Timezone for schedule")
    governance_metadata: Optional[dict] = Field(None, description="Governance metadata")


class ScheduledMessageResponse(BaseModel):
    """Response for scheduled message operations"""
    id: str
    agent_id: str
    agent_name: str
    platform: str
    recipient_id: str
    template: str
    template_variables: dict
    schedule_type: str
    cron_expression: Optional[str]
    natural_language_schedule: Optional[str]
    next_run: datetime
    last_run: Optional[datetime]
    run_count: int
    max_runs: Optional[int]
    end_date: Optional[datetime]
    status: str
    timezone: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class UpdateScheduledMessageRequest(BaseModel):
    """Request to update a scheduled message"""
    template: Optional[str] = None
    cron_expression: Optional[str] = None
    natural_language_schedule: Optional[str] = None
    max_runs: Optional[int] = None
    end_date: Optional[datetime] = None


class ParseNaturalLanguageRequest(BaseModel):
    """Request to parse natural language to cron"""
    schedule: str = Field(..., description="Natural language schedule")


class ParseNaturalLanguageResponse(BaseModel):
    """Response with cron expression"""
    schedule: str
    cron_expression: str
    description: str


# ============================================================================
# Scheduled Messaging Endpoints
# ============================================================================

@router.post("/create", response_model=ScheduledMessageResponse)
async def create_scheduled_message(
    request: CreateScheduledMessageRequest,
    db: Session = Depends(get_db_session),
):
    """
    Create a new scheduled or recurring message.

    For one_time messages: Provide `scheduled_for`
    For recurring messages: Provide `cron_expression` or `natural_language_schedule`

    Examples:
    - One-time: "scheduled_for": "2026-02-05T09:00:00Z"
    - Recurring (cron): "cron_expression": "0 9 * * *"
    - Recurring (NL): "natural_language_schedule": "every day at 9am"
    """
    service = ScheduledMessagingService(db)

    message = service.create_scheduled_message(
        agent_id=request.agent_id,
        platform=request.platform,
        recipient_id=request.recipient_id,
        template=request.template,
        schedule_type=request.schedule_type,
        scheduled_for=request.scheduled_for,
        cron_expression=request.cron_expression,
        natural_language_schedule=request.natural_language_schedule,
        template_variables=request.template_variables,
        max_runs=request.max_runs,
        end_date=request.end_date,
        timezone_str=request.timezone,
        governance_metadata=request.governance_metadata,
    )

    return message


@router.get("/list", response_model=List[ScheduledMessageResponse])
async def list_scheduled_messages(
    agent_id: Optional[str] = None,
    message_status: Optional[str] = None,
    schedule_type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db_session),
):
    """
    List scheduled messages with optional filters.

    Can filter by:
    - agent_id: Only messages from this agent
    - status: Only messages with this status
    - schedule_type: Only 'one_time' or 'recurring'
    """
    service = ScheduledMessagingService(db)

    messages = service.get_scheduled_messages(
        agent_id=agent_id,
        status=message_status,
        schedule_type=schedule_type,
        limit=limit,
    )

    return messages


@router.get("/{message_id}", response_model=ScheduledMessageResponse)
async def get_scheduled_message(
    message_id: str,
    db: Session = Depends(get_db_session),
):
    """Get a specific scheduled message by ID."""
    service = ScheduledMessagingService(db)

    message = service.get_scheduled_message(message_id=message_id)

    if not message:
        raise router.not_found_error("Scheduled message", message_id)

    return message


@router.put("/{message_id}", response_model=ScheduledMessageResponse)
async def update_scheduled_message(
    message_id: str,
    request: UpdateScheduledMessageRequest,
    db: Session = Depends(get_db_session),
):
    """
    Update a scheduled message.

    Can update:
    - template: Message template
    - cron_expression: New cron schedule
    - natural_language_schedule: New natural language schedule
    - max_runs: Maximum execution count
    - end_date: End date for recurring messages
    """
    service = ScheduledMessagingService(db)

    message = service.update_scheduled_message(
        message_id=message_id,
        template=request.template,
        cron_expression=request.cron_expression,
        natural_language_schedule=request.natural_language_schedule,
        max_runs=request.max_runs,
        end_date=request.end_date,
    )

    return message


@router.post("/{message_id}/pause", response_model=ScheduledMessageResponse)
async def pause_scheduled_message(
    message_id: str,
    db: Session = Depends(get_db_session),
):
    """
    Pause a scheduled message.

    Paused messages will not execute until resumed.
    """
    service = ScheduledMessagingService(db)

    message = service.pause_scheduled_message(message_id=message_id)

    return message


@router.post("/{message_id}/resume", response_model=ScheduledMessageResponse)
async def resume_scheduled_message(
    message_id: str,
    db: Session = Depends(get_db_session),
):
    """
    Resume a paused scheduled message.

    Resumes execution based on the schedule.
    """
    service = ScheduledMessagingService(db)

    message = service.resume_scheduled_message(message_id=message_id)

    return message


@router.delete("/{message_id}", response_model=ScheduledMessageResponse)
async def cancel_scheduled_message(
    message_id: str,
    db: Session = Depends(get_db_session),
):
    """
    Cancel a scheduled message.

    Cancelled messages will not execute again.
    """
    service = ScheduledMessagingService(db)

    message = service.cancel_scheduled_message(message_id=message_id)

    return message


@router.get("/history/executions")
async def get_execution_history(
    agent_id: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db_session),
):
    """
    Get execution history for scheduled messages.

    Shows past executions with metadata.
    """
    service = ScheduledMessagingService(db)

    history = service.get_execution_history(
        agent_id=agent_id,
        limit=limit,
    )

    return history


@router.post("/parse-nl", response_model=ParseNaturalLanguageResponse)
async def parse_natural_language_schedule(
    request: ParseNaturalLanguageRequest,
):
    """
    Parse natural language schedule to cron expression.

    Examples:
    - "every day at 9am" → "0 9 * * *"
    - "every monday at 2:30pm" → "30 14 * * 1"
    - "hourly" → "0 * * * *"
    - "daily" → "0 9 * * *"
    - "weekly" → "0 9 * * 1"
    - "monthly" → "0 9 1 * *"

    Returns the cron expression and description.
    """
    from core.cron_parser import natural_language_to_cron

    try:
        cron_expression = natural_language_to_cron(request.schedule)

        # Generate description
        description = f"Cron expression: {cron_expression}"

        return ParseNaturalLanguageResponse(
            schedule=request.schedule,
            cron_expression=cron_expression,
            description=description,
        )
    except ValueError as e:
        raise router.validation_error(
            field="schedule",
            message=str(e)
        )


@router.post("/_execute-due")
async def execute_due_messages(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
):
    """
    Internal endpoint to execute scheduled messages that are due.

    This should be called by a background scheduler (e.g., cron or APScheduler).
    Typically runs every minute to execute messages whose next_run time has arrived.

    Returns counts of sent, failed, and completed messages.
    """
    service = ScheduledMessagingService(db)

    result = await service.execute_due_messages()

    return result
