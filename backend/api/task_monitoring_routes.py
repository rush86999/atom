"""
Task Monitoring Routes

Provides endpoints for monitoring and managing background tasks.
Allows users to check status, list scheduled tasks, and cancel jobs.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import SocialPostHistory, User
from core.task_queue import get_task_queue

router = BaseAPIRouter(prefix="/api/v1/tasks", tags=["task-monitoring"])
logger = logging.getLogger(__name__)


# Response Models
class TaskStatusResponse(BaseModel):
    """Task status response"""
    post_id: str
    status: str
    scheduled_for: Optional[datetime] = None
    job_status: Optional[str] = None
    job_id: Optional[str] = None
    platform_results: Optional[dict] = None


class ScheduledPostResponse(BaseModel):
    """Scheduled post response"""
    post_id: str
    content: str
    platforms: List[str]
    scheduled_for: datetime
    status: str
    job_id: Optional[str] = None
    created_at: datetime


class QueueInfoResponse(BaseModel):
    """Queue information response"""
    queue_name: str
    count: int
    failed_job_count: int
    finished_job_count: int
    started_job_count: int
    deferred_job_count: int


class AllQueuesInfoResponse(BaseModel):
    """All queues information response"""
    queues: dict
    task_queue_enabled: bool


# Helper Functions
def get_current_user_from_request(request, db: Session) -> User:
    """Get current user from request (simplified version)"""
    # Try X-User-ID header
    user_id = request.headers.get("X-User-ID")
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return user

    # Try X-User-Email header
    user_email = request.headers.get("X-User-Email")
    if user_email:
        user = db.query(User).filter(User.email == user_email).first()
        if user:
            return user

    # If no user found, raise error
    raise HTTPException(
        status_code=401,
        detail="Unauthorized: Valid authentication required"
    )


# Endpoints
@router.get("/scheduled-posts", response_model=List[ScheduledPostResponse])
async def list_scheduled_posts(
    request,
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """
    List all scheduled posts for the current user.

    Query Parameters:
    - status_filter: Optional filter by status (scheduled, posting, posted, partial, failed, cancelled)

    Returns:
        List of scheduled posts with their status
    """
    try:
        current_user = get_current_user_from_request(request, db)

        query = db.query(SocialPostHistory).filter(
            SocialPostHistory.user_id == current_user.id,
            SocialPostHistory.scheduled_for.isnot(None)
        )

        if status_filter:
            query = query.filter(SocialPostHistory.status == status_filter)

        posts = query.order_by(SocialPostHistory.scheduled_for).all()

        return [
            ScheduledPostResponse(
                post_id=p.post_id,
                content=p.content,
                platforms=p.platforms,
                scheduled_for=p.scheduled_for,
                status=p.status,
                job_id=p.job_id,
                created_at=p.created_at
            )
            for p in posts
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list scheduled posts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduled-posts/{post_id}/status", response_model=TaskStatusResponse)
async def get_scheduled_post_status(
    post_id: str,
    request,
    db: Session = Depends(get_db)
):
    """
    Get the status of a scheduled post.

    Path Parameters:
    - post_id: The unique post identifier

    Returns:
        Post status including job status if applicable
    """
    try:
        current_user = get_current_user_from_request(request, db)

        # Get post history
        history = db.query(SocialPostHistory).filter(
            SocialPostHistory.post_id == post_id,
            SocialPostHistory.user_id == current_user.id
        ).first()

        if not history:
            raise HTTPException(status_code=404, detail="Post not found")

        # Get job status from task queue if job_id exists
        job_status = None
        if history.job_id:
            task_queue = get_task_queue()
            job_info = task_queue.get_job_status(history.job_id)
            job_status = job_info.get("status") if job_info else None

        return TaskStatusResponse(
            post_id=post_id,
            status=history.status,
            scheduled_for=history.scheduled_for,
            job_status=job_status,
            job_id=history.job_id,
            platform_results=history.platform_results
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get post status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scheduled-posts/{post_id}/cancel")
async def cancel_scheduled_post(
    post_id: str,
    request,
    db: Session = Depends(get_db)
):
    """
    Cancel a scheduled post.

    Path Parameters:
    - post_id: The unique post identifier

    Returns:
        Success message if canceled
    """
    try:
        current_user = get_current_user_from_request(request, db)

        # Get post history
        history = db.query(SocialPostHistory).filter(
            SocialPostHistory.post_id == post_id,
            SocialPostHistory.user_id == current_user.id
        ).first()

        if not history:
            raise HTTPException(status_code=404, detail="Scheduled post not found")

        # Can only cancel scheduled posts
        if history.status not in ["scheduled", "pending"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel post with status: {history.status}"
            )

        # Cancel job if job_id exists
        if history.job_id:
            task_queue = get_task_queue()

            if not task_queue.enabled:
                raise HTTPException(
                    status_code=503,
                    detail="Task queue is not available. Cannot cancel scheduled post."
                )

            canceled = task_queue.cancel_job(history.job_id)

            if not canceled:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to cancel job. It may have already started processing."
                )

        # Update status
        history.status = "cancelled"
        db.commit()

        logger.info(f"Cancelled scheduled post {post_id} for user {current_user.id}")

        return {
            "message": "Post canceled successfully",
            "post_id": post_id,
            "status": "cancelled"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel scheduled post: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queues", response_model=AllQueuesInfoResponse)
async def get_all_queues_info():
    """
    Get information about all task queues.

    Returns statistics for all queues including job counts.
    """
    try:
        task_queue = get_task_queue()

        if not task_queue.enabled:
            return AllQueuesInfoResponse(
                queues={},
                task_queue_enabled=False
            )

        queues_info = task_queue.get_all_queues_info()

        return AllQueuesInfoResponse(
            queues=queues_info,
            task_queue_enabled=True
        )

    except Exception as e:
        logger.error(f"Failed to get queues info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queues/{queue_name}", response_model=QueueInfoResponse)
async def get_queue_info(queue_name: str):
    """
    Get information about a specific queue.

    Path Parameters:
    - queue_name: Name of the queue (default, social_media, workflows)

    Returns:
        Queue statistics and job counts
    """
    try:
        task_queue = get_task_queue()

        if not task_queue.enabled:
            raise HTTPException(
                status_code=503,
                detail="Task queue is not available"
            )

        queue_info = task_queue.get_queue_info(queue_name)

        if "error" in queue_info:
            raise HTTPException(status_code=404, detail=queue_info["error"])

        return QueueInfoResponse(**queue_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get queue info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def task_queue_health():
    """
    Check task queue health status.

    Returns:
        Task queue availability and Redis connection status
    """
    try:
        task_queue = get_task_queue()

        return {
            "status": "healthy" if task_queue.enabled else "unavailable",
            "enabled": task_queue.enabled,
            "redis_available": task_queue._redis_conn is not None if task_queue else False,
            "queues": list(task_queue._queues.keys()) if task_queue else []
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "enabled": False,
            "error": str(e)
        }
