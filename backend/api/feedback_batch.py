"""
Batch Feedback Operations API

Provides endpoints for bulk operations on feedback data.
Includes batch approval, rejection, export, and status updates.

Endpoints:
- POST /api/feedback/batch/approve - Batch approve multiple feedback entries
- POST /api/feedback/batch/reject - Batch reject multiple feedback entries
- POST /api/feedback/batch/update-status - Batch update feedback status
- GET /api/feedback/batch/pending - Get pending feedback awaiting adjudication
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import AgentFeedback, User

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/feedback/batch", tags=["Feedback Batch"])


# ============================================================================
# Request/Response Models
# ============================================================================

class BatchOperationRequest(BaseModel):
    """Request for batch feedback operations."""
    feedback_ids: List[str] = Field(..., description="List of feedback IDs to process")
    user_id: str = Field(..., description="User performing the batch operation")
    reason: Optional[str] = Field(None, description="Reason for the batch decision")


class BatchOperationResponse(BaseModel):
    """Response from batch operations."""
    success: bool
    processed: int
    failed: int
    failed_ids: List[str]
    message: str


class BulkStatusUpdateRequest(BaseModel):
    """Request to bulk update feedback status."""
    feedback_ids: List[str] = Field(..., description="List of feedback IDs")
    new_status: str = Field(..., description="New status (approved, rejected, pending)")
    user_id: str = Field(..., description="User performing the update")
    ai_reasoning: Optional[str] = Field(None, description="AI reasoning for the decision")


class PendingFeedbackItem(BaseModel):
    """Single pending feedback item."""
    id: str
    agent_id: str
    agent_name: str
    user_id: str
    feedback_type: Optional[str]
    thumbs_up_down: Optional[bool]
    rating: Optional[int]
    original_output: str
    user_correction: str
    created_at: datetime


class PendingFeedbackResponse(BaseModel):
    """Response with pending feedback items."""
    total: int
    items: List[PendingFeedbackItem]


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/approve", response_model=BatchOperationResponse)
async def batch_approve_feedback(
    request: BatchOperationRequest,
    db: Session = Depends(get_db)
):
    """
    Batch approve multiple feedback entries.

    Updates the status of all specified feedback entries to 'approved'
    and records the adjudication reason.

    Args:
        request: Batch operation request with feedback IDs and user context
        db: Database session

    Returns:
        BatchOperationResponse with processing results

    Raises:
        HTTPException: If validation fails
    """
    if not request.feedback_ids:
        raise router.validation_error(
            field="feedback_ids",
            message="No feedback IDs provided"
        )

    processed = 0
    failed = 0
    failed_ids = []

    for feedback_id in request.feedback_ids:
        try:
            feedback = db.query(AgentFeedback).filter(
                AgentFeedback.id == feedback_id
            ).first()

            if not feedback:
                failed += 1
                failed_ids.append(feedback_id)
                continue

            # Update status
            feedback.status = "approved"
            feedback.adjudicated_at = datetime.now()

            if request.reason:
                feedback.ai_reasoning = request.reason

            processed += 1

        except Exception as e:
            logger.error(f"Failed to approve feedback {feedback_id}: {e}")
            failed += 1
            failed_ids.append(feedback_id)

    db.commit()

    logger.info(
        f"Batch approve completed: {processed} processed, {failed} failed, "
        f"user={request.user_id}"
    )

    return router.success_response(
        data=BatchOperationResponse(
            success=True,
            processed=processed,
            failed=failed,
            failed_ids=failed_ids,
            message=f"Processed {processed} feedback entries"
        ),
        message=f"Batch approve completed: {processed} processed"
    )


@router.post("/reject", response_model=BatchOperationResponse)
async def batch_reject_feedback(
    request: BatchOperationRequest,
    db: Session = Depends(get_db)
):
    """
    Batch reject multiple feedback entries.

    Updates the status of all specified feedback entries to 'rejected'
    and records the reason for rejection.

    Args:
        request: Batch operation request with feedback IDs and user context
        db: Database session

    Returns:
        BatchOperationResponse with processing results

    Raises:
        HTTPException: If validation fails
    """
    if not request.feedback_ids:
        raise router.validation_error(
            field="feedback_ids",
            message="No feedback IDs provided"
        )

    processed = 0
    failed = 0
    failed_ids = []

    for feedback_id in request.feedback_ids:
        try:
            feedback = db.query(AgentFeedback).filter(
                AgentFeedback.id == feedback_id
            ).first()

            if not feedback:
                failed += 1
                failed_ids.append(feedback_id)
                continue

            # Update status
            feedback.status = "rejected"
            feedback.adjudicated_at = datetime.now()

            if request.reason:
                feedback.ai_reasoning = f"Rejected: {request.reason}"

            processed += 1

        except Exception as e:
            logger.error(f"Failed to reject feedback {feedback_id}: {e}")
            failed += 1
            failed_ids.append(feedback_id)

    db.commit()

    logger.info(
        f"Batch reject completed: {processed} processed, {failed} failed, "
        f"user={request.user_id}"
    )

    return BatchOperationResponse(
        success=True,
        processed=processed,
        failed=failed,
        failed_ids=failed_ids,
        message=f"Processed {processed} feedback entries"
    )


@router.post("/update-status", response_model=BatchOperationResponse)
async def batch_update_feedback_status(
    request: BulkStatusUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Batch update feedback status to any state.

    Allows bulk status updates to approved, rejected, or pending.

    Args:
        request: Bulk status update request
        db: Database session

    Returns:
        BatchOperationResponse with processing results

    Raises:
        HTTPException: If validation fails
    """
    valid_statuses = ["approved", "rejected", "pending", "expired"]

    if request.new_status not in valid_statuses:
        raise router.validation_error(
            field="new_status",
            message=f"Invalid status. Must be one of {valid_statuses}",
            details={"provided": request.new_status, "valid_options": valid_statuses}
        )

    if not request.feedback_ids:
        raise router.validation_error(
            field="feedback_ids",
            message="No feedback IDs provided"
        )

    processed = 0
    failed = 0
    failed_ids = []

    for feedback_id in request.feedback_ids:
        try:
            feedback = db.query(AgentFeedback).filter(
                AgentFeedback.id == feedback_id
            ).first()

            if not feedback:
                failed += 1
                failed_ids.append(feedback_id)
                continue

            # Update status
            feedback.status = request.new_status

            if request.new_status in ["approved", "rejected"]:
                feedback.adjudicated_at = datetime.now()

            if request.ai_reasoning:
                feedback.ai_reasoning = request.ai_reasoning

            processed += 1

        except Exception as e:
            logger.error(f"Failed to update feedback {feedback_id}: {e}")
            failed += 1
            failed_ids.append(feedback_id)

    db.commit()

    logger.info(
        f"Batch status update completed: {processed} processed, {failed} failed, "
        f"new_status={request.new_status}, user={request.user_id}"
    )

    return BatchOperationResponse(
        success=True,
        processed=processed,
        failed=failed,
        failed_ids=failed_ids,
        message=f"Updated {processed} feedback entries to '{request.new_status}'"
    )


@router.get("/pending", response_model=PendingFeedbackResponse)
async def get_pending_feedback(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    feedback_type: Optional[str] = Query(None, description="Filter by feedback type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Get all feedback pending adjudication.

    Returns feedback entries that are awaiting review and approval.
    Can be filtered by agent and feedback type.

    Args:
        agent_id: Optional filter for specific agent
        feedback_type: Optional filter for feedback type
        limit: Maximum number of items to return
        offset: Offset for pagination
        db: Database session

    Returns:
        PendingFeedbackResponse with pending feedback items
    """
    query = db.query(AgentFeedback).filter(
        AgentFeedback.status == "pending"
    )

    # Apply filters
    if agent_id:
        query = query.filter(AgentFeedback.agent_id == agent_id)

    if feedback_type:
        query = query.filter(AgentFeedback.feedback_type == feedback_type)

    # Get total count
    total = query.count()

    # Get paginated results with agent info
    feedback_items = query.order_by(
        AgentFeedback.created_at.desc()
    ).offset(offset).limit(limit).all()

    # Build response with agent names
    items = []
    for feedback in feedback_items:
        # Get agent name
        agent_name = "Unknown"
        if feedback.agent:
            agent_name = feedback.agent.name

        items.append(PendingFeedbackItem(
            id=feedback.id,
            agent_id=feedback.agent_id,
            agent_name=agent_name,
            user_id=feedback.user_id,
            feedback_type=feedback.feedback_type,
            thumbs_up_down=feedback.thumbs_up_down,
            rating=feedback.rating,
            original_output=feedback.original_output,
            user_correction=feedback.user_correction,
            created_at=feedback.created_at
        ))

    return router.success_response(
        data=PendingFeedbackResponse(
            total=total,
            items=items
        ),
        message=f"Retrieved {len(items)} pending feedback items"
    )


@router.get("/stats")
async def get_batch_operation_stats(
    db: Session = Depends(get_db)
):
    """
    Get statistics about feedback awaiting batch processing.

    Returns counts of pending feedback by status, type, and agent.

    Args:
        db: Database session

    Returns:
        Dictionary with batch operation statistics
    """
    # Count by status
    status_counts = {}
    for status in ["pending", "approved", "rejected", "expired"]:
        count = db.query(AgentFeedback).filter(
            AgentFeedback.status == status
        ).count()
        status_counts[status] = count

    # Count by feedback type
    type_counts = {}
    feedback_types = db.query(AgentFeedback.feedback_type).filter(
        AgentFeedback.feedback_type.isnot(None)
    ).distinct().all()

    for (feedback_type,) in feedback_types:
        count = db.query(AgentFeedback).filter(
            AgentFeedback.feedback_type == feedback_type
        ).count()
        type_counts[feedback_type] = count

    # Pending feedback by agent
    pending_by_agent = []
    agents_with_pending = db.query(
        AgentFeedback.agent_id
    ).filter(
        AgentFeedback.status == "pending"
    ).distinct().all()

    for (agent_id,) in agents_with_pending:
        count = db.query(AgentFeedback).filter(
            AgentFeedback.agent_id == agent_id,
            AgentFeedback.status == "pending"
        ).count()

        # Get agent name
        agent = db.query(AgentFeedback).filter(
            AgentFeedback.agent_id == agent_id
        ).first()

        agent_name = agent.agent.name if agent and agent.agent else "Unknown"

        pending_by_agent.append({
            "agent_id": agent_id,
            "agent_name": agent_name,
            "pending_count": count
        })

    # Sort by pending count
    pending_by_agent.sort(key=lambda x: x["pending_count"], reverse=True)

    return router.success_response(
        data={
            "status_counts": status_counts,
            "type_counts": type_counts,
            "pending_by_agent": pending_by_agent[:20],  # Top 20
            "total_pending": status_counts.get("pending", 0)
        },
        message="Batch operation statistics retrieved"
    )
