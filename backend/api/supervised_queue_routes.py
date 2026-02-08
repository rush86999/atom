"""
Supervised Queue Routes

API endpoints for managing supervised execution queue.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from core.database import get_db
from core.models import QueueStatus
from core.supervised_queue_service import SupervisedQueueService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/supervised-queue", tags=["supervised-queue"])


# ============================================================================
# Request/Response Models
# ============================================================================

class QueueEntryResponse(BaseModel):
    """Queue entry response"""
    id: str
    agent_id: str
    agent_name: Optional[str]
    user_id: str
    trigger_type: str
    status: str
    supervisor_type: str
    priority: int
    attempt_count: int
    max_attempts: int
    expires_at: str
    execution_id: Optional[str]
    error_message: Optional[str]
    created_at: str
    updated_at: str


class QueueListResponse(BaseModel):
    """Queue list response"""
    entries: List[QueueEntryResponse]
    total_count: int


class QueueStatsResponse(BaseModel):
    """Queue statistics response"""
    pending: int
    executing: int
    completed: int
    failed: int
    cancelled: int
    total: int


class SuccessResponse(BaseModel):
    """Generic success response"""
    success: bool
    message: str


class QueueProcessResponse(BaseModel):
    """Queue processing response"""
    processed_count: int
    entries: List[QueueEntryResponse]


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/users/{user_id}", response_model=QueueListResponse)
async def get_user_queue(
    user_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """
    Get all queue entries for a user.

    Optionally filter by status (pending, executing, completed, failed, cancelled).
    """
    service = SupervisedQueueService(db)

    try:
        # Parse status if provided
        status_filter = None
        if status:
            try:
                status_filter = QueueStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status}"
                )

        entries = await service.get_user_queue(user_id, status_filter)

        entry_responses = []
        for entry in entries:
            # Get agent name
            agent = db.query(service.db.query(
                __import__('core.models', fromlist=['AgentRegistry']).AgentRegistry
            ).filter(
                __import__('core.models', fromlist=['AgentRegistry']).AgentRegistry.id == entry.agent_id
            ).first()).first() if hasattr(service, 'db') else None

            entry_responses.append(QueueEntryResponse(
                id=entry.id,
                agent_id=entry.agent_id,
                agent_name=agent.name if agent else None,
                user_id=entry.user_id,
                trigger_type=entry.trigger_type,
                status=entry.status.value,
                supervisor_type=entry.supervisor_type,
                priority=entry.priority,
                attempt_count=entry.attempt_count,
                max_attempts=entry.max_attempts,
                expires_at=entry.expires_at.isoformat(),
                execution_id=entry.execution_id,
                error_message=entry.error_message,
                created_at=entry.created_at.isoformat(),
                updated_at=entry.updated_at.isoformat()
            ))

        return QueueListResponse(
            entries=entry_responses,
            total_count=len(entry_responses)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user queue: {str(e)}"
        )


@router.delete("/{queue_id}", response_model=SuccessResponse)
async def cancel_queue_entry(
    queue_id: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Cancel a queued execution.

    User must own the queue entry to cancel it.
    Only pending entries can be cancelled.
    """
    service = SupervisedQueueService(db)

    try:
        success = await service.cancel_queue_entry(queue_id, user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Queue entry not found or cannot be cancelled: {queue_id}"
            )

        return SuccessResponse(
            success=True,
            message=f"Queue entry {queue_id} cancelled"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel queue entry: {str(e)}"
        )


@router.post("/process", response_model=QueueProcessResponse)
async def process_queue_manually(
    limit: int = Query(10, ge=1, le=100, description="Max entries to process"),
    db: Session = Depends(get_db)
):
    """
    Manually trigger queue processing (for testing).

    Processes pending queue entries for available users.
    """
    service = SupervisedQueueService(db)

    try:
        processed = await service.process_pending_queues(limit=limit)

        entry_responses = []
        for entry in processed:
            entry_responses.append(QueueEntryResponse(
                id=entry.id,
                agent_id=entry.agent_id,
                agent_name=None,
                user_id=entry.user_id,
                trigger_type=entry.trigger_type,
                status=entry.status.value,
                supervisor_type=entry.supervisor_type,
                priority=entry.priority,
                attempt_count=entry.attempt_count,
                max_attempts=entry.max_attempts,
                expires_at=entry.expires_at.isoformat(),
                execution_id=entry.execution_id,
                error_message=entry.error_message,
                created_at=entry.created_at.isoformat(),
                updated_at=entry.updated_at.isoformat()
            ))

        return QueueProcessResponse(
            processed_count=len(entry_responses),
            entries=entry_responses
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process queue: {str(e)}"
        )


@router.get("/stats", response_model=QueueStatsResponse)
async def get_queue_stats(
    user_id: Optional[str] = Query(None, description="Filter by user"),
    db: Session = Depends(get_db)
):
    """
    Get queue statistics.

    Optionally filter by user ID.
    """
    service = SupervisedQueueService(db)

    try:
        stats = await service.get_queue_stats(user_id)

        return QueueStatsResponse(**stats)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue stats: {str(e)}"
        )


@router.post("/mark-expired", response_model=SuccessResponse)
async def mark_expired_entries(
    db: Session = Depends(get_db)
):
    """
    Mark expired queue entries as failed (for testing).

    Normally called by background worker.
    """
    service = SupervisedQueueService(db)

    try:
        count = await service.mark_expired_queues()

        return SuccessResponse(
            success=True,
            message=f"Marked {count} expired entries as failed"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark expired entries: {str(e)}"
        )


@router.get("/{queue_id}", response_model=QueueEntryResponse)
async def get_queue_entry(
    queue_id: str,
    db: Session = Depends(get_db)
):
    """Get details of a specific queue entry."""
    from core.models import SupervisedExecutionQueue

    entry = db.query(SupervisedExecutionQueue).filter(
        SupervisedExecutionQueue.id == queue_id
    ).first()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue entry not found: {queue_id}"
        )

    # Get agent name
    from core.models import AgentRegistry
    agent = db.query(AgentRegistry).filter(
        AgentRegistry.id == entry.agent_id
    ).first()

    return QueueEntryResponse(
        id=entry.id,
        agent_id=entry.agent_id,
        agent_name=agent.name if agent else None,
        user_id=entry.user_id,
        trigger_type=entry.trigger_type,
        status=entry.status.value,
        supervisor_type=entry.supervisor_type,
        priority=entry.priority,
        attempt_count=entry.attempt_count,
        max_attempts=entry.max_attempts,
        expires_at=entry.expires_at.isoformat(),
        execution_id=entry.execution_id,
        error_message=entry.error_message,
        created_at=entry.created_at.isoformat(),
        updated_at=entry.updated_at.isoformat()
    )
