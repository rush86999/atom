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
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Body, Depends, Query
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.personal_scope import resolve_tenant_id, resolve_workspace_id

logger = logging.getLogger(__name__)

router = BaseAPIRouter(tags=["Nav Stubs"])

_DEFAULT_PROJECT_COLOR = "#3182CE"
_HEX_COLOR_RE = re.compile(
    r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$"
)
_MAX_PROJECT_NAME_LENGTH = 255
_MAX_PROJECT_REF_LENGTH = 128


def _fail_validation(message: str) -> None:
    raise router.error_response(
        error_code="VALIDATION_ERROR",
        message=message,
        status_code=422,
    )


def _database_failure(message: str) -> None:
    raise router.error_response(
        error_code="DATABASE_ERROR",
        message=message,
        status_code=500,
    )


def _commit_or_fail(db: Session, message: str) -> None:
    try:
        db.commit()
    except Exception:
        logger.warning(message)
        try:
            db.rollback()
        except Exception:
            logger.warning("Rollback failed after: %s", message)
        _database_failure(message)


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


def _current_workspace_id(current_user: User) -> str:
    """The canonical workspace scope, including personal-workspace defaults."""
    return str(resolve_workspace_id(current_user))


def _authorized_project(db: Session, project_id: Any, current_user: User):
    from service_delivery.models import Project

    return (
        db.query(Project)
        .filter(
            Project.id == str(project_id),
            Project.workspace_id == _current_workspace_id(current_user),
        )
        .first()
    )


def _project_name(value: Any) -> str:
    if not isinstance(value, str):
        _fail_validation("name must be a non-empty string")
    name = value.strip()
    if not name:
        _fail_validation("name must be a non-empty string")
    if len(name) > _MAX_PROJECT_NAME_LENGTH:
        _fail_validation(f"name must be at most {_MAX_PROJECT_NAME_LENGTH} characters")
    return name


def _project_description(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail_validation("description must be a string or null")
    return value


def _normalize_project_color(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail_validation("color must be a hex color string or null")
    color = value.strip()
    if not color or not _HEX_COLOR_RE.fullmatch(color):
        _fail_validation("color must be a bounded hex color such as #3182CE")
    return color


def _project_metadata(project: Any) -> Dict[str, Any]:
    metadata = getattr(project, "metadata_json", None)
    return dict(metadata) if isinstance(metadata, dict) else {}


def _project_payload(project: Any, tasks: Optional[List[Any]] = None) -> Dict[str, Any]:
    task_rows = list(tasks or [])
    metadata = _project_metadata(project)
    color = metadata.get("color")
    if not isinstance(color, str) or not _HEX_COLOR_RE.fullmatch(color.strip()):
        color = _DEFAULT_PROJECT_COLOR
    else:
        color = color.strip()

    completed = sum(
        1
        for task in task_rows
        if str(getattr(task, "status", "")).lower() in ("completed", "done")
    )
    progress = int(round((completed / len(task_rows)) * 100)) if task_rows else 0

    return {
        "id": str(project.id),
        "name": project.name,
        "description": getattr(project, "description", None),
        "color": color,
        "tasks": [_task_payload(task) for task in task_rows],
        "progress": progress,
    }


def _nullish_project_ref(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def _resolve_task_project_ref(
    db: Session, current_user: User, payload: Dict[str, Any]
) -> tuple[Optional[str], bool]:
    """Validate a task's project reference before any task is mutated.

    Returns (project_id_or_None, was_supplied). A null reference is a valid
    unlink, but a non-null reference must resolve to a Project in the caller's
    current workspace.
    """
    has_project = "project" in payload
    has_project_id = "projectId" in payload
    if not has_project and not has_project_id:
        return None, False

    if has_project and has_project_id:
        if _nullish_project_ref(payload.get("project")) != _nullish_project_ref(
            payload.get("projectId")
        ):
            _fail_validation("project and projectId must agree")
        raw = payload.get("project")
    elif has_project:
        raw = payload.get("project")
    else:
        raw = payload.get("projectId")

    if raw is None:
        return None, True
    if not isinstance(raw, str):
        _fail_validation("project must be a project id string or null")
    project_id = raw.strip()
    if not project_id:
        return None, True
    if len(project_id) > _MAX_PROJECT_REF_LENGTH:
        _fail_validation("project reference is invalid")

    try:
        project = _authorized_project(db, project_id, current_user)
    except Exception:
        logger.warning("Project reference lookup failed")
        try:
            db.rollback()
        except Exception:
            logger.warning("Rollback failed after project reference lookup")
        _database_failure("Unable to validate project")

    if project is None:
        raise router.error_response(
            error_code="PROJECT_NOT_FOUND",
            message="Project not found in the current workspace",
            status_code=404,
        )
    return str(project.id), True


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
            .order_by(UserTask.created_at.desc(), UserTask.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {"tasks": [_task_payload(t) for t in tasks]}
    except Exception:
        logger.warning("Task list query failed")
        try:
            db.rollback()
        except Exception:
            logger.warning("Rollback failed after task list query")
        _database_failure("Unable to load tasks")


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

    raw_title = payload.get("title")
    if not isinstance(raw_title, str) or not raw_title.strip():
        _fail_validation("title is required")
    title = raw_title.strip()

    project_id, _ = _resolve_task_project_ref(db, current_user, payload)

    try:
        estimated_hours = float(payload.get("estimatedHours") or 0)
        actual_hours = float(payload.get("actualHours") or 0)
    except (TypeError, ValueError):
        _fail_validation("estimatedHours and actualHours must be numbers")

    task = UserTask(
        tenant_id=resolve_tenant_id(current_user),
        user_id=str(current_user.id),
        project_id=project_id,
        title=title,
        description=payload.get("description"),
        status=str(payload.get("status") or "todo"),
        priority=str(payload.get("priority") or "medium"),
        due_date=_parse_due(payload.get("dueDate") or payload.get("due_date")),
        tags=payload.get("tags") or [],
        estimated_hours=estimated_hours,
        actual_hours=actual_hours,
        color=str(payload.get("color") or "#3182CE"),
        metadata_json=payload.get("metadata") or {},
    )
    db.add(task)
    _commit_or_fail(db, "Unable to create task")
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

    project_id, project_supplied = _resolve_task_project_ref(db, current_user, payload)

    title_update = None
    if "title" in payload:
        raw_title = payload.get("title")
        if not isinstance(raw_title, str) or not raw_title.strip():
            _fail_validation("title must be a non-empty string")
        title_update = raw_title.strip()

    try:
        estimated_hours = (
            float(payload.get("estimatedHours") or 0)
            if "estimatedHours" in payload
            else None
        )
        actual_hours = (
            float(payload.get("actualHours") or 0)
            if "actualHours" in payload
            else None
        )
    except (TypeError, ValueError):
        _fail_validation("estimatedHours and actualHours must be numbers")

    if title_update is not None:
        task.title = title_update
    for incoming, attr in (
        ("description", "description"),
        ("status", "status"),
        ("priority", "priority"),
        ("tags", "tags"),
        ("color", "color"),
        ("metadata", "metadata_json"),
    ):
        if incoming in payload:
            setattr(task, attr, payload[incoming])
    if project_supplied:
        task.project_id = project_id
    if "dueDate" in payload or "due_date" in payload:
        task.due_date = _parse_due(payload.get("dueDate") or payload.get("due_date"))
    if estimated_hours is not None:
        task.estimated_hours = estimated_hours
    if actual_hours is not None:
        task.actual_hours = actual_hours

    _commit_or_fail(db, "Unable to update task")
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
    _commit_or_fail(db, "Unable to delete task")
    return {"success": True, "deleted": task_id}


def _tasks_for_project(db: Session, user_id: str, project_id: Any) -> List[Any]:
    from core.models import UserTask

    return (
        db.query(UserTask)
        .filter(
            UserTask.user_id == user_id,
            UserTask.project_id == str(project_id),
        )
        .order_by(UserTask.created_at.desc(), UserTask.id.desc())
        .all()
    )


@router.get("/api/v1/projects")
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List projects in the caller's current workspace."""
    try:
        from core.models import UserTask
        from service_delivery.models import Project

        projects = (
            db.query(Project)
            .filter(Project.workspace_id == _current_workspace_id(current_user))
            .order_by(Project.created_at.desc())
            .all()
        )
        project_ids = {str(project.id) for project in projects}
        tasks = (
            db.query(UserTask)
            .filter(UserTask.user_id == str(current_user.id))
            .order_by(UserTask.created_at.desc(), UserTask.id.desc())
            .all()
        )
        tasks_by_project: Dict[str, List[Any]] = {}
        for task in tasks:
            if task.project_id and str(task.project_id) in project_ids:
                tasks_by_project.setdefault(str(task.project_id), []).append(task)

        return {
            "projects": [
                _project_payload(
                    project, tasks_by_project.get(str(project.id), [])
                )
                for project in projects
            ]
        }
    except Exception:
        logger.warning("Project list query failed")
        try:
            db.rollback()
        except Exception:
            logger.warning("Rollback failed after project list query")
        _database_failure("Unable to load projects")


@router.post("/api/v1/projects")
async def create_project(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a workspace-scoped Project owned by the existing service model."""
    from service_delivery.models import Project

    name = _project_name(payload.get("name"))
    description = _project_description(payload.get("description"))
    color = (
        _normalize_project_color(payload.get("color"))
        if "color" in payload
        else None
    )
    metadata = {"color": color} if color else None

    project = Project(
        workspace_id=_current_workspace_id(current_user),
        name=name,
        description=description,
        metadata_json=metadata,
    )
    db.add(project)
    _commit_or_fail(db, "Unable to create project")
    try:
        db.refresh(project)
    except Exception:
        logger.warning("Project refresh failed after create")
        _database_failure("Unable to create project")
    return {"success": True, "project": _project_payload(project)}


@router.put("/api/v1/projects/{project_id}")
async def update_project(
    project_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update editable Project fields without touching financial/status data."""
    try:
        project = _authorized_project(db, project_id, current_user)
    except Exception:
        logger.warning("Project lookup failed")
        try:
            db.rollback()
        except Exception:
            logger.warning("Rollback failed after project lookup")
        _database_failure("Unable to load project")

    if project is None:
        raise router.not_found_error("Project", project_id)

    name = _project_name(payload.get("name")) if "name" in payload else None
    description = (
        _project_description(payload.get("description"))
        if "description" in payload
        else None
    )
    color = (
        _normalize_project_color(payload.get("color"))
        if "color" in payload
        else None
    )

    if name is not None:
        project.name = name
    if "description" in payload:
        project.description = description
    if "color" in payload:
        metadata = _project_metadata(project)
        if color is None:
            metadata.pop("color", None)
        else:
            metadata["color"] = color
        project.metadata_json = metadata or None

    try:
        tasks = _tasks_for_project(db, str(current_user.id), project.id)
    except Exception:
        logger.warning("Project task lookup failed")
        try:
            db.rollback()
        except Exception:
            logger.warning("Rollback failed after project task lookup")
        _database_failure("Unable to update project")

    result = _project_payload(project, tasks)
    _commit_or_fail(db, "Unable to update project")
    return {"success": True, "project": result}


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
