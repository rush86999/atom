"""Durable user-task operations shared by chat and the Tasks API.

The existing ``UserTask`` table is the only local task store. This module
factors the active-user, workspace/project authority and commit/readback rules
so chat consumers cannot create an in-memory or provider-fallback task that
the ordinary task API cannot list.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import update
from sqlalchemy.orm import Session

from core.models import User, UserStatus, UserTask, Workspace
from core.personal_scope import resolve_tenant_id, resolve_workspace_id
from service_delivery.models import Project

_MAX_TITLE_LENGTH = 255
_MAX_PROJECT_REF_LENGTH = 128
_DEFAULT_COLOR = "#3182CE"
_IDEMPOTENCY_KEY = "_task_idempotency_key"
_IDEMPOTENCY_DIGEST = "_task_idempotency_material_sha256"
_INTERNAL_METADATA = {_IDEMPOTENCY_KEY, _IDEMPOTENCY_DIGEST}


class TaskServiceError(Exception):
    """Base class for durable task refusals."""


class TaskAuthorityError(TaskServiceError):
    """Missing, inactive, ambiguous or foreign caller authority."""


class TaskValidationError(TaskServiceError):
    """Caller-supplied task material is invalid."""


class TaskProjectNotFound(TaskServiceError):
    """A requested project is unavailable in the caller's workspace."""


class TaskNotFound(TaskServiceError):
    """The owned task does not exist for this caller."""


class TaskCommitError(TaskServiceError):
    """The durable write could not be confirmed."""


def resolve_active_user(db: Session, actor: Any) -> User:
    """Resolve the authoritative active User row, never a caller object."""
    user_id = getattr(actor, "id", actor)
    if not isinstance(user_id, str) or not user_id.strip():
        raise TaskAuthorityError("An authenticated user is required")
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .populate_existing()
        .first()
    )
    if user is None:
        raise TaskAuthorityError("An authenticated user is required")
    status = getattr(user.status, "value", user.status)
    if str(status or "") != UserStatus.ACTIVE.value or user.is_active is not True:
        raise TaskAuthorityError("The current user is not active")
    return user


def _exact(column: Any, value: Any):
    return column.is_(None) if value is None else column == value


def claim_active_user(db: Session, user: User) -> User:
    """Conditionally claim the exact current User row before a task write.

    The no-op UPDATE is the same general actor-claim pattern used by the
    existing scoped write services. A peer deactivation, role/scope move or
    credential change committed before this statement makes it match zero
    rows; everything in the caller's transaction is rolled back.
    """
    snapshot = {
        name: getattr(user, name) for name in (
            "id", "email", "status", "is_active", "role",
            "tenant_id", "workspace_id", "hashed_password")
    }
    status = getattr(user.status, "value", user.status)
    if (str(status or "") != UserStatus.ACTIVE.value
            or snapshot["is_active"] is not True):
        db.rollback()
        raise TaskAuthorityError("The current user is not active")
    claimed = db.execute(
        update(User)
        .where(
            User.id == snapshot["id"],
            _exact(User.email, snapshot["email"]),
            User.status == snapshot["status"],
            User.is_active.is_(True),
            User.role == snapshot["role"],
            _exact(User.tenant_id, snapshot["tenant_id"]),
            _exact(User.workspace_id, snapshot["workspace_id"]),
            _exact(User.hashed_password, snapshot["hashed_password"]),
        )
        .values(updated_at=User.updated_at)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise TaskAuthorityError(
            "The current user authority changed; no task was written")
    return user


def current_workspace_id(db: Session, user: User) -> str:
    """Resolve a workspace in the same tenant as the current user."""
    workspace_id = str(resolve_workspace_id(user))
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id)
        .first()
    )
    if workspace is None or (
        resolve_tenant_id(workspace) != resolve_tenant_id(user)
    ):
        raise TaskProjectNotFound("Workspace is unavailable")
    return workspace_id


def authorized_project(
    db: Session, project_id: Any, user: User
) -> Optional[Project]:
    return (
        db.query(Project)
        .filter(
            Project.id == str(project_id),
            Project.workspace_id == current_workspace_id(db, user),
        )
        .first()
    )


def resolve_task_project_ref(
    db: Session, user: User, payload: Dict[str, Any]
) -> Tuple[Optional[str], bool]:
    """Validate a project reference before any task write."""
    has_project = "project" in payload
    has_project_id = "projectId" in payload
    if not has_project and not has_project_id:
        return None, False
    if has_project and has_project_id:
        left = payload.get("project")
        right = payload.get("projectId")
        left = left.strip() if isinstance(left, str) else left
        right = right.strip() if isinstance(right, str) else right
        if left != right:
            raise TaskValidationError("project and projectId must agree")
        raw = payload.get("project")
    elif has_project:
        raw = payload.get("project")
    else:
        raw = payload.get("projectId")

    if raw is None:
        return None, True
    if not isinstance(raw, str):
        raise TaskValidationError("project must be a project id string or null")
    project_id = raw.strip()
    if not project_id:
        return None, True
    if len(project_id) > _MAX_PROJECT_REF_LENGTH:
        raise TaskValidationError("project reference is invalid")
    project = authorized_project(db, project_id, user)
    if project is None:
        raise TaskProjectNotFound("Project not found in the current workspace")
    return str(project.id), True


def _title(payload: Dict[str, Any]) -> str:
    raw = payload.get("title")
    if not isinstance(raw, str) or not raw.strip():
        raise TaskValidationError("title is required")
    title = raw.strip()
    if len(title) > _MAX_TITLE_LENGTH:
        raise TaskValidationError(
            f"title must be at most {_MAX_TITLE_LENGTH} characters")
    return title


def _parse_due(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise TaskValidationError("dueDate must be an ISO date or null")


def _hours(payload: Dict[str, Any], key: str, default: float = 0.0) -> float:
    if key not in payload:
        return default
    try:
        return float(payload.get(key) or 0)
    except (TypeError, ValueError):
        raise TaskValidationError(f"{key} must be a number")


def _idempotent_task_id(user_id: str, key: str) -> str:
    material = f"{user_id}\0{key}".encode("utf-8")
    return "task-" + hashlib.sha256(material).hexdigest()[:40]


def _idempotency_key(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("idempotencyKey", "idempotency_key"):
        value = payload.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise TaskValidationError("idempotency key must be a non-empty string")
        value = value.strip()
        if len(value) > 256:
            raise TaskValidationError("idempotency key is too long")
        return value
    return None


def _public_metadata(metadata: Any) -> Dict[str, Any]:
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise TaskValidationError("metadata must be an object")
    return {
        str(key): value for key, value in metadata.items()
        if str(key) not in _INTERNAL_METADATA
    }


def _canonical_due(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is not None:
            normalized = normalized.astimezone(timezone.utc).replace(tzinfo=None)
        return normalized.isoformat(timespec="microseconds")
    return str(value)


def _material_digest(material: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            material, sort_keys=True, separators=(",", ":"), default=str,
        ).encode("utf-8")
    ).hexdigest()


def _creation_material(
    *,
    title: str,
    description: Any,
    project_id: Optional[str],
    status: str,
    priority: str,
    due_date: Any,
    tags: Any,
    estimated_hours: float,
    actual_hours: float,
    color: str,
    metadata: Any,
) -> Dict[str, Any]:
    return {
        "title": title,
        "description": description,
        "project_id": project_id,
        "status": status,
        "priority": priority,
        "due_date": _canonical_due(due_date),
        "tags": list(tags or []),
        "estimated_hours": estimated_hours,
        "actual_hours": actual_hours,
        "color": color,
        "metadata": _public_metadata(metadata),
    }


def _task_material(task: UserTask) -> Dict[str, Any]:
    return _creation_material(
        title=task.title,
        description=task.description,
        project_id=task.project_id,
        status=str(task.status or "todo"),
        priority=str(task.priority or "medium"),
        due_date=task.due_date,
        tags=task.tags or [],
        estimated_hours=float(task.estimated_hours or 0),
        actual_hours=float(task.actual_hours or 0),
        color=str(task.color or _DEFAULT_COLOR),
        metadata=task.metadata_json or {},
    )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise TaskCommitError("The task write could not be confirmed")


def _existing_idempotent(
    db: Session,
    user_id: str,
    task_id: str,
    key: str,
    material_digest: str,
) -> Optional[UserTask]:
    existing = (
        db.query(UserTask)
        .filter(UserTask.id == task_id, UserTask.user_id == user_id)
        .populate_existing()
        .first()
    )
    if existing is None:
        return None
    metadata = existing.metadata_json if isinstance(
        existing.metadata_json, dict) else {}
    if (
        metadata.get(_IDEMPOTENCY_KEY) != key
        or metadata.get(_IDEMPOTENCY_DIGEST) != material_digest
    ):
        raise TaskValidationError(
            "idempotency key was already used for a different task material")
    if _material_digest(_task_material(existing)) != material_digest:
        raise TaskValidationError(
            "task material changed after the original idempotent creation")
    return existing


def create_user_task(
    db: Session,
    actor: Any,
    payload: Dict[str, Any],
) -> UserTask:
    """Create one durable UserTask for the claimed active caller."""
    user = resolve_active_user(db, actor)
    claim_active_user(db, user)
    try:
        title = _title(payload)
        project_id, _supplied = resolve_task_project_ref(db, user, payload)
        description = payload.get("description")
        status = str(payload.get("status") or "todo")
        priority = str(payload.get("priority") or "medium")
        due_date = _parse_due(
            payload.get("dueDate") or payload.get("due_date"))
        tags = list(payload.get("tags") or [])
        estimated_hours = _hours(payload, "estimatedHours")
        actual_hours = _hours(payload, "actualHours")
        color = str(payload.get("color") or _DEFAULT_COLOR)
        metadata = _public_metadata(payload.get("metadata"))
        material = _creation_material(
            title=title,
            description=description,
            project_id=project_id,
            status=status,
            priority=priority,
            due_date=due_date,
            tags=tags,
            estimated_hours=estimated_hours,
            actual_hours=actual_hours,
            color=color,
            metadata=metadata,
        )
        material_digest = _material_digest(material)
        key = _idempotency_key(payload)
        task_id = _idempotent_task_id(str(user.id), key) if key else None
        if task_id:
            existing = _existing_idempotent(
                db, str(user.id), task_id, key, material_digest)
            if existing is not None:
                _commit(db)
                db.refresh(existing)
                return existing

        metadata_json = dict(metadata)
        if key:
            metadata_json[_IDEMPOTENCY_KEY] = key
            metadata_json[_IDEMPOTENCY_DIGEST] = material_digest
        task = UserTask(
            id=task_id or None,
            tenant_id=resolve_tenant_id(user),
            user_id=str(user.id),
            project_id=project_id,
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_date=due_date,
            tags=tags,
            estimated_hours=estimated_hours,
            actual_hours=actual_hours,
            color=color,
            metadata_json=metadata_json,
        )
        db.add(task)
        try:
            _commit(db)
            db.refresh(task)
            return task
        except TaskCommitError:
            if task_id:
                try:
                    db.rollback()
                    existing = _existing_idempotent(
                        db, str(user.id), task_id, key, material_digest)
                    if existing is not None:
                        db.refresh(existing)
                        return existing
                except TaskServiceError:
                    raise
            raise
    except TaskServiceError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise TaskCommitError("The task write could not be confirmed")


def list_user_tasks(
    db: Session,
    actor: Any,
    *,
    limit: int = 50,
    offset: int = 0,
) -> List[UserTask]:
    user = resolve_active_user(db, actor)
    return (
        db.query(UserTask)
        .filter(UserTask.user_id == str(user.id))
        .order_by(UserTask.created_at.desc(), UserTask.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def _owned_task_for_user(db: Session, user: User, task_id: str) -> UserTask:
    task = (
        db.query(UserTask)
        .filter(
            UserTask.id == str(task_id),
            UserTask.user_id == str(user.id),
        )
        .populate_existing()
        .first()
    )
    if task is None:
        raise TaskNotFound("Task not found")
    return task


def get_owned_task(db: Session, actor: Any, task_id: str) -> UserTask:
    user = resolve_active_user(db, actor)
    return _owned_task_for_user(db, user, task_id)


def update_user_task(
    db: Session,
    actor: Any,
    task_id: str,
    payload: Dict[str, Any],
) -> UserTask:
    user = resolve_active_user(db, actor)
    claim_active_user(db, user)
    try:
        task = _owned_task_for_user(db, user, task_id)
        project_id, project_supplied = resolve_task_project_ref(
            db, user, payload)

        if "title" in payload:
            task.title = _title(payload)
        for incoming, attr in (
            ("description", "description"),
            ("status", "status"),
            ("priority", "priority"),
            ("tags", "tags"),
            ("color", "color"),
        ):
            if incoming in payload:
                setattr(task, attr, payload[incoming])
        if "metadata" in payload:
            merged = _public_metadata(payload.get("metadata"))
            current = task.metadata_json if isinstance(
                task.metadata_json, dict) else {}
            for internal in _INTERNAL_METADATA:
                if internal in current:
                    merged[internal] = current[internal]
            task.metadata_json = merged
        if project_supplied:
            task.project_id = project_id
        if "dueDate" in payload or "due_date" in payload:
            task.due_date = _parse_due(
                payload.get("dueDate") or payload.get("due_date"))
        if "estimatedHours" in payload:
            task.estimated_hours = _hours(payload, "estimatedHours")
        if "actualHours" in payload:
            task.actual_hours = _hours(payload, "actualHours")

        _commit(db)
        db.refresh(task)
        return task
    except TaskServiceError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise TaskCommitError("The task update could not be confirmed")


def delete_user_task(db: Session, actor: Any, task_id: str) -> None:
    user = resolve_active_user(db, actor)
    claim_active_user(db, user)
    try:
        task = _owned_task_for_user(db, user, task_id)
        db.delete(task)
        _commit(db)
    except TaskServiceError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise TaskCommitError("The task delete could not be confirmed")
