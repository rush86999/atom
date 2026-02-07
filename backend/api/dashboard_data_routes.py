"""
Dashboard Data API Routes
Provides real dashboard data by querying database models
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import (
    WorkflowExecution,
    ChatProcess,
    AuditLog,
    AgentJob,
    User,
    Team,
    AgentRegistry
)

router = BaseAPIRouter(prefix="/api/dashboard", tags=["Dashboard"])

# =============================================================================
# Pydantic Models for Response
# =============================================================================

class CalendarEventResponse(BaseModel):
    id: str
    title: str
    start: str
    end: str
    description: Optional[str] = None
    location: Optional[str] = None
    status: str

class TaskResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None
    priority: str
    status: str
    created_at: str
    updated_at: str

class MessageResponse(BaseModel):
    id: str
    platform: str
    from_user: Optional[str] = None
    subject: str
    preview: str
    timestamp: str
    unread: bool = False
    priority: str = "normal"

class DashboardStatsResponse(BaseModel):
    upcoming_events: int
    overdue_tasks: int
    unread_messages: int
    completed_tasks: int
    active_workflows: int
    total_agents: int

class DashboardDataResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    stats: DashboardStatsResponse
    timestamp: str


# =============================================================================
# Helper Functions
# =============================================================================

def get_user_upcoming_events(db: Session, user_id: Optional[str], limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get upcoming calendar events for the user.
    For now, we'll use WorkflowExecution with scheduled start times as calendar events.
    """
    try:
        query = db.query(
            WorkflowExecution.execution_id,
            WorkflowExecution.workflow_id,
            WorkflowExecution.created_at,
            WorkflowExecution.status
        )

        if user_id:
            query = query.filter(
                or_(
                    WorkflowExecution.user_id == user_id,
                    WorkflowExecution.owner_id == user_id
                )
            )

        # Get recent executions as "events"
        executions = query.order_by(WorkflowExecution.created_at.desc()).limit(limit).all()

        events = []
        for exec in executions:
            # Calculate start/end times based on created_at
            start_time = exec.created_at
            end_time = exec.created_at + timedelta(hours=1)

            events.append({
                "id": exec.execution_id,
                "title": f"Workflow: {exec.workflow_id}",
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "description": f"Execution status: {exec.status}",
                "location": None,
                "status": "confirmed" if exec.status == "completed" else "tentative"
            })

        return events

    except Exception as e:
        # Return empty list on error
        return []


def get_user_tasks(db: Session, user_id: Optional[str], limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get tasks for the user from WorkflowExecution and AgentJob.
    """
    try:
        tasks = []

        # Get workflow executions as tasks
        workflow_query = db.query(WorkflowExecution)

        if user_id:
            workflow_query = workflow_query.filter(
                or_(
                    WorkflowExecution.user_id == user_id,
                    WorkflowExecution.owner_id == user_id
                )
            )

        workflow_executions = workflow_query.order_by(
            WorkflowExecution.created_at.desc()
        ).limit(limit).all()

        for exec in workflow_executions:
            # Determine priority based on status
            priority = "high" if exec.status == "failed" else "medium"
            if exec.status == "completed":
                priority = "low"

            tasks.append({
                "id": exec.execution_id,
                "title": f"Execute Workflow: {exec.workflow_id}",
                "description": exec.input_data[:200] if exec.input_data else None,
                "due_date": exec.updated_at.isoformat() if exec.updated_at else None,
                "priority": priority,
                "status": exec.status,
                "created_at": exec.created_at.isoformat(),
                "updated_at": exec.updated_at.isoformat() if exec.updated_at else exec.created_at.isoformat()
            })

        # Get agent jobs as tasks
        job_query = db.query(AgentJob)

        if user_id:
            job_query = job_query.filter(AgentJob.user_id == user_id)

        agent_jobs = job_query.order_by(AgentJob.created_at.desc()).limit(limit // 2).all()

        for job in agent_jobs:
            # Determine status
            status = "todo"
            if job.completed_at:
                status = "completed"
            elif job.started_at:
                status = "in-progress"

            # Calculate priority
            priority = "medium"
            if job.status == "failed":
                priority = "high"
            elif status == "completed":
                priority = "low"

            tasks.append({
                "id": job.job_id,
                "title": f"Agent Job: {job.agent_name}",
                "description": job.input_data[:200] if job.input_data else None,
                "due_date": job.created_at.isoformat(),
                "priority": priority,
                "status": status,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat() if job.updated_at else job.created_at.isoformat()
            })

        # Sort by created_at and limit
        tasks.sort(key=lambda x: x["created_at"], reverse=True)
        return tasks[:limit]

    except Exception as e:
        return []


def get_user_messages(db: Session, user_id: Optional[str], limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get messages for the user from AuditLog and other sources.
    """
    try:
        messages = []

        # Get audit logs as messages
        audit_query = db.query(AuditLog)

        if user_id:
            audit_query = audit_query.filter(AuditLog.user_id == user_id)

        audit_logs = audit_query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

        for log in audit_logs:
            # Determine priority based on threat level
            priority = "normal"
            if log.threat_level in ["high", "critical"]:
                priority = "high"
            elif log.threat_level == "low":
                priority = "low"

            messages.append({
                "id": log.id,
                "platform": "system",
                "from_user": log.user_email,
                "subject": f"{log.event_type}",
                "preview": log.event_type,
                "timestamp": log.timestamp.isoformat(),
                "unread": False,
                "priority": priority
            })

        return messages

    except Exception as e:
        return []


def calculate_dashboard_stats(db: Session, user_id: Optional[str]) -> Dict[str, Any]:
    """
    Calculate dashboard statistics.
    """
    try:
        # Count upcoming events (recent workflow executions)
        events_query = db.query(func.count(WorkflowExecution.execution_id))
        if user_id:
            events_query = events_query.filter(
                or_(
                    WorkflowExecution.user_id == user_id,
                    WorkflowExecution.owner_id == user_id
                )
            )
        upcoming_events = events_query.scalar() or 0

        # Count overdue tasks (failed or stuck workflows)
        tasks_query = db.query(func.count(WorkflowExecution.execution_id)).filter(
            WorkflowExecution.status.in_(["failed", "stuck", "error"])
        )
        if user_id:
            tasks_query = tasks_query.filter(
                or_(
                    WorkflowExecution.user_id == user_id,
                    WorkflowExecution.owner_id == user_id
                )
            )
        overdue_tasks = tasks_query.scalar() or 0

        # Count unread messages (recent audit logs)
        messages_query = db.query(func.count(AuditLog.id))
        if user_id:
            messages_query = messages_query.filter(AuditLog.user_id == user_id)
        unread_messages = messages_query.scalar() or 0

        # Count completed workflows
        completed_query = db.query(func.count(WorkflowExecution.execution_id)).filter(
            WorkflowExecution.status == "completed"
        )
        if user_id:
            completed_query = completed_query.filter(
                or_(
                    WorkflowExecution.user_id == user_id,
                    WorkflowExecution.owner_id == user_id
                )
            )
        completed_tasks = completed_query.scalar() or 0

        # Count active workflows
        active_query = db.query(func.count(ChatProcess.id)).filter(
            ChatProcess.status == "active"
        )
        if user_id:
            active_query = active_query.filter(
                or_(
                    ChatProcess.user_id == user_id,
                    ChatProcess.owner_id == user_id
                )
            )
        active_workflows = active_query.scalar() or 0

        # Count total agents
        total_agents = db.query(func.count(AgentRegistry.id)).scalar() or 0

        return {
            "upcoming_events": upcoming_events,
            "overdue_tasks": overdue_tasks,
            "unread_messages": unread_messages,
            "completed_tasks": completed_tasks,
            "active_workflows": active_workflows,
            "total_agents": total_agents
        }

    except Exception as e:
        # Return zero stats on error
        return {
            "upcoming_events": 0,
            "overdue_tasks": 0,
            "unread_messages": 0,
            "completed_tasks": 0,
            "active_workflows": 0,
            "total_agents": 0
        }


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/data", response_model=DashboardDataResponse)
async def get_dashboard_data(
    user_id: Optional[str] = Query(None, description="User ID to filter data"),
    limit: int = Query(20, description="Maximum number of items per category", ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive dashboard data including calendar events, tasks, messages, and statistics.

    Query Parameters:
    - user_id: Optional user ID to filter data for specific user
    - limit: Maximum number of items per category (default: 20, max: 100)

    Returns real dashboard data from the database.
    """
    try:
        # Fetch all data
        calendar_events = get_user_upcoming_events(db, user_id, limit)
        tasks = get_user_tasks(db, user_id, limit)
        messages = get_user_messages(db, user_id, limit)
        stats = calculate_dashboard_stats(db, user_id)

        return DashboardDataResponse(
            success=True,
            data={
                "calendar": calendar_events,
                "tasks": tasks,
                "messages": messages
            },
            stats=DashboardStatsResponse(**stats),
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch dashboard data: {str(e)}"
        )


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    user_id: Optional[str] = Query(None, description="User ID to filter stats"),
    db: Session = Depends(get_db)
):
    """
    Get dashboard statistics only (faster than full data endpoint).

    Query Parameters:
    - user_id: Optional user ID to filter stats for specific user

    Returns dashboard statistics.
    """
    try:
        stats = calculate_dashboard_stats(db, user_id)
        return DashboardStatsResponse(**stats)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch dashboard stats: {str(e)}"
        )


@router.get("/events", response_model=List[CalendarEventResponse])
async def get_calendar_events(
    user_id: Optional[str] = Query(None, description="User ID to filter events"),
    limit: int = Query(10, description="Maximum number of events", ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get calendar events for the user."""
    try:
        events = get_user_upcoming_events(db, user_id, limit)
        return [CalendarEventResponse(**event) for event in events]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch calendar events: {str(e)}"
        )


@router.get("/tasks", response_model=List[TaskResponse])
async def get_tasks(
    user_id: Optional[str] = Query(None, description="User ID to filter tasks"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, description="Maximum number of tasks", ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get tasks for the user with optional status filter."""
    try:
        all_tasks = get_user_tasks(db, user_id, limit * 2)  # Get more for filtering

        # Filter by status if provided
        if status:
            all_tasks = [t for t in all_tasks if t["status"] == status]

        return [TaskResponse(**task) for task in all_tasks[:limit]]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch tasks: {str(e)}"
        )


@router.get("/messages", response_model=List[MessageResponse])
async def get_messages(
    user_id: Optional[str] = Query(None, description="User ID to filter messages"),
    unread_only: bool = Query(False, description="Only return unread messages"),
    limit: int = Query(20, description="Maximum number of messages", ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get messages for the user."""
    try:
        all_messages = get_user_messages(db, user_id, limit * 2)

        # Filter by unread status if requested
        if unread_only:
            all_messages = [m for m in all_messages if m["unread"]]

        return [MessageResponse(**msg) for msg in all_messages[:limit]]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch messages: {str(e)}"
        )


@router.get("/health")
async def dashboard_health():
    """Health check for dashboard data API."""
    return {
        "status": "healthy",
        "service": "dashboard-data",
        "timestamp": datetime.utcnow().isoformat()
    }
