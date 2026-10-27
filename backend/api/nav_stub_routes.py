"""
Sidebar navigation endpoint stubs for missing nav routes.

These endpoints provide the response shapes the frontend pages expect, so
every sidebar nav item resolves end-to-end. They query real data where models
exist (UserTask, SupportTicket) and return structured empty defaults where the
underlying data layer isn't wired yet (communication analytics).

Response shapes match what the consuming frontend components parse:
- TaskManagement.tsx expects { tasks: [...] }
- useLiveSupport.ts expects { tickets: [...] } or [...]
- CommunicationCommandCenter.tsx expects { success, analytics: {...} }
- IntegrationsPage expects per-provider health-check endpoints
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Body, Depends, Query
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.personal_scope import resolve_tenant_id

logger = logging.getLogger(__name__)

router = BaseAPIRouter(tags=["Nav Stubs"])


# ============================================================================
# Tasks — /api/v1/tasks (Tasks sidebar nav)
# ============================================================================

def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)


def _parse_due(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _task_payload(task: Any) -> Dict[str, Any]:
    """The camelCase shape components/shared/TaskManagement.tsx consumes."""
    return {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "dueDate": _iso(task.due_date),
        "priority": task.priority,
        "status": task.status,
        "project": task.project_id,
        "tags": task.tags or [],
        "estimatedHours": task.estimated_hours or 0,
        "actualHours": task.actual_hours or 0,
        "color": task.color or "#3182CE",
        "metadata": task.metadata_json or {},
        "createdAt": _iso(task.created_at),
        "updatedAt": _iso(task.updated_at),
    }


def _owned_task(db: Session, task_id: str, user_id: str):
    from core.models import UserTask

    return (
        db.query(UserTask)
        .filter(UserTask.id == task_id, UserTask.user_id == user_id)
        .first()
    )


@router.get("/api/v1/tasks")
async def list_tasks(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List tasks for the current user."""
    try:
        from core.models import UserTask
        tasks = (
            db.query(UserTask)
            .filter(UserTask.user_id == str(current_user.id))
            .order_by(UserTask.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {"tasks": [_task_payload(t) for t in tasks]}
    except Exception as e:
        logger.warning(f"Task list query failed, returning empty: {e}")
        return {"tasks": []}


@router.post("/api/v1/tasks")
async def create_task(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a durable task.

    The Tasks page used to POST here against a GET-only stub, so every create
    returned 405 while the UI optimistically showed "Task created" and the
    row vanished on reload. Persist to `tasks` (UserTask) so reload and a
    backend restart both keep it.
    """
    from core.models import UserTask

    title = str(payload.get("title") or "").strip()
    if not title:
        raise router.error_response(
            error_code="VALIDATION_ERROR",
            message="title is required",
            status_code=422,
        )
    task = UserTask(
        tenant_id=resolve_tenant_id(current_user),
        user_id=str(current_user.id),
        project_id=payload.get("project") or payload.get("projectId"),
        title=title,
        description=payload.get("description"),
        status=str(payload.get("status") or "todo"),
        priority=str(payload.get("priority") or "medium"),
        due_date=_parse_due(payload.get("dueDate") or payload.get("due_date")),
        tags=payload.get("tags") or [],
        estimated_hours=float(payload.get("estimatedHours") or 0),
        actual_hours=float(payload.get("actualHours") or 0),
        color=str(payload.get("color") or "#3182CE"),
        metadata_json=payload.get("metadata") or {},
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"success": True, "task": _task_payload(task)}


@router.put("/api/v1/tasks/{task_id}")
async def update_task(
    task_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    task = _owned_task(db, task_id, str(current_user.id))
    if task is None:
        raise router.not_found_error("Task", task_id)

    for incoming, attr in (
        ("title", "title"),
        ("description", "description"),
        ("status", "status"),
        ("priority", "priority"),
        ("project", "project_id"),
        ("projectId", "project_id"),
        ("tags", "tags"),
        ("color", "color"),
        ("metadata", "metadata_json"),
    ):
        if incoming in payload:
            value = payload[incoming]
            if attr == "title":
                value = str(value or "").strip()
                if not value:
                    continue
            setattr(task, attr, value)
    if "dueDate" in payload or "due_date" in payload:
        task.due_date = _parse_due(payload.get("dueDate") or payload.get("due_date"))
    if "estimatedHours" in payload:
        task.estimated_hours = float(payload.get("estimatedHours") or 0)
    if "actualHours" in payload:
        task.actual_hours = float(payload.get("actualHours") or 0)

    db.commit()
    db.refresh(task)
    return {"success": True, "task": _task_payload(task)}


@router.delete("/api/v1/tasks/{task_id}")
async def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    task = _owned_task(db, task_id, str(current_user.id))
    if task is None:
        raise router.not_found_error("Task", task_id)
    db.delete(task)
    db.commit()
    return {"success": True, "deleted": task_id}


@router.get("/api/v1/projects")
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List projects for the current user."""
    return {"projects": []}


# ============================================================================
# Support Tickets — /api/atom/communication/live/support/tickets
# ============================================================================

@router.get("/api/atom/communication/live/support/tickets")
async def list_support_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List support tickets."""
    try:
        from core.models import SupportTicket
        tickets = (
            db.query(SupportTicket)
            .filter(SupportTicket.user_id == str(current_user.id))
            .order_by(SupportTicket.created_at.desc())
            .limit(50)
            .all()
        )
        return {
            "tickets": [
                {
                    "id": str(t.id),
                    "subject": getattr(t, "subject", ""),
                    "status": getattr(t, "status", "open"),
                    "priority": getattr(t, "priority", "medium"),
                    "created_at": t.created_at.isoformat() if hasattr(t, "created_at") and t.created_at else None,
                }
                for t in tickets
            ]
        }
    except Exception as e:
        logger.warning(f"Support ticket query failed, returning empty: {e}")
        return {"tickets": []}


# ============================================================================
# Communication Analytics — /api/atom/communication/memory/analytics
# ============================================================================

@router.get("/api/atom/communication/memory/analytics")
async def communication_analytics(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Communication memory analytics for the Communication Command Center."""
    return {
        "success": True,
        "analytics": {
            "status_distribution": {
                "unread": 0,
                "read": 0,
                "responded": 0,
            },
            "summary": {
                "unique_apps": 0,
                "total_messages": 0,
            },
            "performance": {
                "response_rate": 0.0,
                "avg_response_time": "0m",
            },
        },
    }


@router.get("/api/atom/communication/memory/apps")
async def communication_apps(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """List configured communication apps."""
    return {"apps": []}


# ============================================================================
# Integration Health — /api/integrations/{provider}/health
# ============================================================================

@router.get("/api/integrations/{provider}/health")
async def integration_health(
    provider: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Health check for a specific integration provider."""
    return {
        "provider": provider,
        "status": "not_configured",
        "health": "unknown",
        "message": f"{provider} integration is not configured",
    }
