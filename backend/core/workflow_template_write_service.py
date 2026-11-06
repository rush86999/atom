"""Verified workflow-template create/update decisions.

The two routes previously constructed a ``WorkflowTemplate`` and wrote the
backing JSON file directly. Any caller with ``WORKFLOW_MANAGE`` could therefore
overwrite a peer edit, with no exact prior-material binding, audit receipt or
replay protection.

This module binds the current principal and the exact canonical template
material under a per-template lock, writes the JSON file atomically, and adds
one safe ``AuditLog`` receipt in the same transaction boundary. A confirmed
database failure restores the prior file (or removes a newly created one); a
lost confirmation is reported as ``effect_unknown``.
"""
from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import logging
import os
import re
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.auth import SECRET_KEY
from core.models import AuditEventType, AuditLog, SecurityLevel, User, UserRole
from core.personal_scope import resolve_tenant_id, resolve_workspace_id
from core.security.rbac import role_level
from core.workflow_template_system import (
    TemplateParameter,
    TemplateStep,
    WorkflowTemplate,
    WorkflowTemplateManager,
)

logger = logging.getLogger(__name__)

REVIEW_SCHEMA = "atom-workflow-template-decision-1"
_OPERATION_PREFIX = "workflow-template"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_SAFE_TEMPLATE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_ACTION_CREATE = "workflow_template_created"
_ACTION_UPDATE = "workflow_template_updated"
_ALLOWED_UPDATE_FIELDS = ("name", "description", "steps", "inputs", "tags")


def _fingerprint(*parts: Any) -> str:
    message = "|".join(
        str(part if part is not None else "") for part in parts)
    return hmac.new(
        str(SECRET_KEY).encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str)


def _operation_id(action: str, supplied: Optional[str]) -> str:
    supplied = str(supplied or "").strip()
    candidate = supplied or f"{_OPERATION_PREFIX}:{action}:{uuid.uuid4().hex}"
    prefix = f"{_OPERATION_PREFIX}:{action}:"
    if not candidate.startswith(prefix):
        candidate = f"{prefix}{candidate}"
    if not _SAFE_OPERATION_RE.fullmatch(candidate):
        raise ValueError("operation_id is malformed")
    return candidate


def _refused(
    message: str, *, http_status: int = 422,
    error_code: str = "VALIDATION_ERROR", field: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "status": "refused",
        "error": message,
        "error_code": error_code,
        "field": field,
        "http_status": int(http_status),
        "verification": {"status": "not_attempted", "effect": "none"},
    }


def _conflict(message: str, *, code: str = "STALE_TARGET") -> Dict[str, Any]:
    return {
        "status": "conflict",
        "error": message,
        "error_code": code,
        "http_status": 409,
        "verification": {"status": "refuted", "effect": "none"},
    }


def _not_applied(message: str) -> Dict[str, Any]:
    return {
        "status": "not_applied",
        "error": message,
        "error_code": "WORKFLOW_TEMPLATE_TRANSACTION_ROLLED_BACK",
        "http_status": 409,
        "verification": {
            "status": "refused",
            "effect": "none",
            "replay": "safe_after_refresh",
        },
    }


def _committed_unverified(
    operation_id: str, audit_state: Dict[str, Any], *, target_id: str,
) -> Dict[str, Any]:
    return {
        "status": "committed_unverified",
        "data": None,
        "message": (
            "The workflow-template decision committed but its audit/target "
            "readback did not verify. Reconcile the original operation."),
        "operation_id": operation_id,
        "audit_id": audit_state.get("audit_id"),
        "target_id": target_id,
        "verification": {
            "status": audit_state.get("status", "unavailable"),
            "effect": "committed",
            "replay": "do_not_repeat",
            "audit_id": audit_state.get("audit_id"),
        },
    }


def _effect_unknown(operation_id: str, target_id: str) -> Dict[str, Any]:
    return {
        "status": "effect_unknown",
        "data": None,
        "message": (
            "The workflow-template decision may have committed, but "
            "confirmation was lost. Reconcile the original operation; do not "
            "repeat it blindly."),
        "operation_id": operation_id,
        "audit_id": None,
        "target_id": target_id,
        "verification": {
            "status": "unavailable",
            "effect": "unknown",
            "replay": "do_not_repeat",
            "error": "COMMIT_OUTCOME_UNKNOWN",
        },
    }


def _with_receipt(
    data: Dict[str, Any], *, operation_id: str, audit_id: Optional[str],
    verification_status: str = "verified",
    effect: str = "committed",
    replay: Optional[str] = None,
) -> Dict[str, Any]:
    result = dict(data)
    verification = {
        "status": verification_status,
        "effect": effect,
        "audit_id": audit_id,
    }
    if replay:
        verification["replay"] = replay
    result["verification"] = verification
    result["operation_id"] = operation_id
    result["audit_id"] = audit_id
    return result


def _no_change(data: Dict[str, Any], message: str) -> Dict[str, Any]:
    result = dict(data)
    result["verification"] = {"status": "no_change", "effect": "none"}
    return {"status": "no_change", "data": result, "message": message}


def _fresh_session(db: Session) -> Session:
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=db.get_bind())()


def _actor_refusal(actor: Dict[str, Any]) -> Dict[str, Any]:
    return _refused(
        str(actor.get("message") or "WORKFLOW_MANAGE authority is required"),
        http_status=int(actor.get("http_status") or 403),
        error_code=str(actor.get("error_code") or "AUTHORITY_REQUIRED"),
    )


def _resolve_actor(db: Session, actor: Any) -> Dict[str, Any]:
    actor_id = str(getattr(actor, "id", "") or "")
    if not actor_id:
        return {
            "ok": False, "http_status": 401,
            "error_code": "UNAUTHENTICATED",
            "message": "Authentication required",
        }
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(User).filter(User.id == actor_id).first()
            if row is None:
                return {
                    "ok": False, "http_status": 401,
                    "error_code": "UNAUTHENTICATED",
                    "message": "Authentication required",
                }
            if not bool(row.is_active) or str(row.status or "") != "active":
                return {
                    "ok": False, "http_status": 403,
                    "error_code": "ACCOUNT_INACTIVE",
                    "message": (
                        "This account is not active; refresh and sign in "
                        "again"),
                }
            if role_level(row.role) < role_level(UserRole.TEAM_LEAD):
                return {
                    "ok": False, "http_status": 403,
                    "error_code": "AUTHORITY_REQUIRED",
                    "message": "WORKFLOW_MANAGE authority is required",
                }
            return {
                "ok": True,
                "id": actor_id,
                "email": str(row.email or ""),
                "role": str(row.role or ""),
                "status": str(row.status or ""),
                "is_active": bool(row.is_active),
                "tenant_id": str(resolve_tenant_id(row)),
                "raw_tenant_id": row.tenant_id,
                "workspace_id": str(resolve_workspace_id(row)),
            }
    except Exception as exc:  # noqa: BLE001 — unreadable authority fails closed
        logger.warning(
            "workflow-template authority read failed: actor=%s error_class=%s",
            actor_id, type(exc).__name__)
        return {
            "ok": False, "http_status": 503,
            "error_code": "AUTHORITY_UNAVAILABLE",
            "message": "Authorization could not be confirmed; retry",
        }


def _exact(column, value: Any):
    return column.is_(None) if value is None else column == value


def _claim_actor(db: Session, actor: Dict[str, Any]) -> bool:
    result = db.execute(
        update(User)
        .where(
            User.id == actor["id"],
            User.is_active.is_(True),
            User.status == actor["status"],
            User.role == actor["role"],
            _exact(User.tenant_id, actor["raw_tenant_id"]),
        )
        .values(updated_at=User.updated_at)
    )
    return result.rowcount == 1


# ---------------------------------------------------------------------------
# Template material / filesystem primitives
# ---------------------------------------------------------------------------

def _template_dir(manager: WorkflowTemplateManager) -> Path:
    return Path(getattr(manager, "template_dir", "workflow_templates"))


def _safe_template_id(template_id: str) -> Optional[str]:
    value = str(template_id or "").strip()
    if not _SAFE_TEMPLATE_ID_RE.fullmatch(value):
        return None
    return value


def _template_path(directory: Path, template_id: str) -> Optional[Path]:
    safe = _safe_template_id(template_id)
    if safe is None:
        return None
    return directory / f"{safe}.json"


def _template_payload(template: WorkflowTemplate) -> Dict[str, Any]:
    return template.model_dump(mode="json")


def _stable_payload(template: WorkflowTemplate) -> Dict[str, Any]:
    """Canonical payload after nested validators have been applied twice.

    ``WorkflowTemplate`` accepts nested step/parameter dicts, and a nested
    ``TemplateParameter`` label default is materialized only on the second
    parse. Stabilizing here makes the written file, prior digest and read-back
    digest describe the same material.
    """
    first = _template_payload(template)
    return _template_payload(
        WorkflowTemplate(**json.loads(json.dumps(first, default=str))))


def _payload_digest(payload: Dict[str, Any]) -> str:
    return _fingerprint("workflow-template-payload", _canonical(payload))


def _template_bytes(payload: Dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, default=str) + "\n").encode(
        "utf-8")


def _read_payload(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if path is None or not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return None
        return data
    except Exception:  # noqa: BLE001 — unreadable is not a valid payload
        return None


def _read_template_payload(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    data = _read_payload(path)
    if data is None:
        return None
    try:
        return _stable_payload(WorkflowTemplate(**data))
    except Exception:  # noqa: BLE001 — unreadable is not a valid template
        return None


@contextmanager
def _template_lock(directory: Path, template_id: str):
    directory.mkdir(parents=True, exist_ok=True)
    lock_path = directory / f".{template_id}.lock"
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _atomic_replace(path: Path, data: bytes) -> None:
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def _atomic_create(path: Path, data: bytes) -> None:
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temp, path)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def _restore_file(path: Optional[Path], prior_bytes: Optional[bytes]) -> bool:
    if path is None:
        return False
    try:
        if prior_bytes is None:
            if path.exists():
                path.unlink()
            return True
        _atomic_replace(path, prior_bytes)
        return True
    except Exception as exc:  # noqa: BLE001 — restoration is best effort
        logger.error(
            "workflow-template restore failed: path=%s error_class=%s",
            path.name if path else "", type(exc).__name__)
        return False


def _current_template(
    directory: Path, template_id: str,
) -> Optional[WorkflowTemplate]:
    manager = WorkflowTemplateManager(template_dir=str(directory))
    return manager.get_template(template_id)


def _current_status(directory: Path, template_id: str) -> str:
    payload = _read_template_payload(
        _template_path(directory, template_id))
    if payload is None:
        return "missing"
    return str(payload.get("updated_at") or "present")


def _normalize_steps(steps: Optional[list]) -> list:
    normalized = []
    for index, step in enumerate(steps or []):
        if not isinstance(step, dict):
            continue
        value = dict(step)
        if "step_id" not in value and "id" in value:
            value["step_id"] = value["id"]
        normalized.append(value)
    return normalized


def _normalize_inputs(inputs: Optional[list]) -> list:
    return [dict(item) for item in (inputs or []) if isinstance(item, dict)]


def _apply_updates(
    template: WorkflowTemplate, updates: Dict[str, Any],
) -> WorkflowTemplate:
    updated = template.model_copy(deep=True)
    for field in _ALLOWED_UPDATE_FIELDS:
        if field not in updates or updates[field] is None:
            continue
        value = updates[field]
        if field == "steps":
            updated.steps = [
                TemplateStep(**step) for step in _normalize_steps(value)
            ]
        elif field == "inputs":
            updated.inputs = [
                TemplateParameter(**item) for item in _normalize_inputs(value)
            ]
        else:
            setattr(updated, field, value)
    updated.calculate_estimated_duration()
    return updated


def _build_template(payload: Dict[str, Any]) -> WorkflowTemplate:
    template = WorkflowTemplate(
        name=str(payload.get("name") or ""),
        description=str(payload.get("description") or ""),
        category=payload.get("category") or "automation",
        complexity=payload.get("complexity") or "intermediate",
        tags=list(payload.get("tags") or []),
        steps=list(payload.get("steps") or []),
    )
    template.calculate_estimated_duration()
    return template


# ---------------------------------------------------------------------------
# Audit ledger
# ---------------------------------------------------------------------------

def _audit_expected(
    *, operation_id: str, action: str, template_id: str,
    prior_digest: str, result_digest: str, request_digest: str,
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "operation_id": str(operation_id),
        "schema": REVIEW_SCHEMA,
        "action": str(action),
        "event_type": AuditEventType.UPDATE.value,
        "target_id": str(template_id),
        "prior_digest": str(prior_digest),
        "result_digest": str(result_digest),
        "request_digest": str(request_digest),
        "actor_id": actor["id"],
        "actor_role": actor["role"],
        "tenant_id": actor["tenant_id"],
        "resource": f"workflow_template:{template_id}",
    }


def _audit_row(
    *, expected: Dict[str, Any], actor: Dict[str, Any],
) -> AuditLog:
    metadata = {
        "schema": expected["schema"],
        "operation_id": expected["operation_id"],
        "action": expected["action"],
        "event_type": expected["event_type"],
        "target_id": expected["target_id"],
        "prior_digest": expected["prior_digest"],
        "result_digest": expected["result_digest"],
        "request_digest": expected["request_digest"],
        "actor_id": expected["actor_id"],
        "actor_role": expected["actor_role"],
        "tenant_id": expected["tenant_id"],
    }
    return AuditLog(
        id=expected["operation_id"],
        event_type=expected["event_type"],
        security_level=SecurityLevel.HIGH.value,
        threat_level="none",
        user_id=expected["actor_id"],
        user_email=actor["email"],
        tenant_id=expected["tenant_id"],
        workspace_id=actor["workspace_id"],
        resource=expected["resource"],
        action=expected["action"],
        description="Workflow-template decision recorded",
        metadata_json=json.dumps(metadata, sort_keys=True),
        success=True,
    )


def _verify_audit(db: Session, expected: Dict[str, Any]) -> Dict[str, Any]:
    audit_id = expected["operation_id"]
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(AuditLog).filter(
                AuditLog.id == audit_id).first()
            if row is None:
                return {"status": "unavailable", "audit_id": audit_id}
            if str(row.event_type or "") != expected["event_type"]:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.action or "") != expected["action"]:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.user_id or "") != expected["actor_id"]:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.tenant_id or "") != expected["tenant_id"]:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.resource or "") != expected["resource"]:
                return {"status": "refuted", "audit_id": audit_id}
            if row.success is not True:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.security_level or "") != SecurityLevel.HIGH.value:
                return {"status": "refuted", "audit_id": audit_id}
            try:
                metadata = json.loads(row.metadata_json or "{}")
            except (TypeError, ValueError):
                return {"status": "unavailable", "audit_id": audit_id}
            if not isinstance(metadata, dict):
                return {"status": "unavailable", "audit_id": audit_id}
            string_fields = (
                "schema", "operation_id", "action", "event_type",
                "target_id", "prior_digest", "result_digest",
                "request_digest", "actor_id", "actor_role", "tenant_id",
            )
            for key in string_fields:
                if key not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                if not isinstance(metadata[key], str):
                    return {"status": "refuted", "audit_id": audit_id}
                if metadata[key] != expected[key]:
                    return {"status": "refuted", "audit_id": audit_id}
            return {"status": "verified", "audit_id": audit_id}
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "workflow-template audit read-back failed: operation_id=%s "
            "error_class=%s", audit_id, type(exc).__name__)
        return {"status": "unavailable", "audit_id": audit_id}


def _expected_from_metadata(
    metadata: Dict[str, Any], *, operation_id: str,
) -> Dict[str, Any]:
    return {
        "operation_id": str(operation_id),
        "schema": metadata.get("schema"),
        "action": metadata.get("action"),
        "event_type": metadata.get("event_type"),
        "target_id": metadata.get("target_id"),
        "prior_digest": metadata.get("prior_digest"),
        "result_digest": metadata.get("result_digest"),
        "request_digest": metadata.get("request_digest"),
        "actor_id": metadata.get("actor_id"),
        "actor_role": metadata.get("actor_role"),
        "tenant_id": metadata.get("tenant_id"),
        "resource": f"workflow_template:{metadata.get('target_id')}",
    }


def _replay(
    db: Session, operation_id: str, expected: Dict[str, Any],
    *, authority: Dict[str, Any], directory: Path,
) -> Optional[Dict[str, Any]]:
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(AuditLog).filter(
                AuditLog.id == str(operation_id)).first()
            if row is None:
                return None
            try:
                metadata = json.loads(row.metadata_json or "{}")
            except (TypeError, ValueError):
                metadata = None
            if not isinstance(metadata, dict):
                return _committed_unverified(
                    operation_id, {"status": "unavailable"},
                    target_id=str(expected.get("target_id") or ""))
            expected_target = expected.get("target_id")
            if (
                metadata.get("schema") != expected["schema"]
                or metadata.get("action") != expected["action"]
                or metadata.get("event_type") != expected["event_type"]
                or (
                    expected_target is not None
                    and metadata.get("target_id") != expected_target
                )
                or metadata.get("request_digest")
                != expected["request_digest"]
                or metadata.get("actor_id") != expected["actor_id"]
                or metadata.get("actor_role") != authority["role"]
                or metadata.get("tenant_id") != authority["tenant_id"]
            ):
                return _conflict(
                    "operation_id is bound to a different decision or "
                    "changed authority",
                    code="OPERATION_CONFLICT")
            audit_expected = _expected_from_metadata(
                metadata, operation_id=operation_id)
            audit_state = _verify_audit(db, audit_expected)
            payload = _read_template_payload(
                _template_path(directory, audit_expected["target_id"]))
            target_ok = (
                payload is not None
                and _payload_digest(payload)
                == audit_expected["result_digest"]
            )
            data: Dict[str, Any] = {
                "template_id": audit_expected["target_id"],
            }
            if audit_expected["action"] == _ACTION_UPDATE and payload:
                data["template"] = payload
            if audit_state["status"] == "verified" and not target_ok:
                audit_state = {
                    "status": "refuted",
                    "audit_id": audit_expected["operation_id"],
                }
            if audit_state["status"] == "verified" and target_ok:
                return {
                    "status": "already_applied",
                    "data": _with_receipt(
                        data, operation_id=operation_id,
                        audit_id=audit_expected["operation_id"],
                        verification_status="already_applied",
                        replay="do_not_repeat"),
                    "message": "This workflow-template decision was already "
                               "applied.",
                    "operation_id": operation_id,
                    "audit_id": audit_expected["operation_id"],
                    "target_id": audit_expected["target_id"],
                }
            return _committed_unverified(
                operation_id, audit_state,
                target_id=audit_expected["target_id"])
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "workflow-template replay read failed: operation_id=%s "
            "error_class=%s", operation_id, type(exc).__name__)
        return _committed_unverified(
            operation_id, {"status": "unavailable"},
            target_id=str(expected.get("target_id") or ""))


def _commit_and_verify(
    db: Session, *, expected: Dict[str, Any], audit_row: AuditLog,
    target_check: Callable[[], bool], success_data: Dict[str, Any],
    authority: Dict[str, Any], directory: Path,
    path: Optional[Path], prior_bytes: Optional[bytes],
    created: bool,
) -> Dict[str, Any]:
    operation_id = expected["operation_id"]
    target_id = expected["target_id"]
    try:
        db.add(audit_row)
        db.commit()
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected, authority=authority,
            directory=directory)
        if replay is not None and replay.get("status") == "already_applied":
            return replay
        restored = _restore_file(path, None if created else prior_bytes)
        if replay is not None:
            return replay
        if restored:
            return _not_applied(
                "The workflow-template decision was rolled back; the prior "
                "template was restored")
        return _effect_unknown(operation_id, target_id)
    except Exception as exc:  # noqa: BLE001 — commit outcome unknown
        db.rollback()
        logger.error(
            "workflow-template decision outcome unknown: operation_id=%s "
            "target=%s error_class=%s", operation_id, target_id,
            type(exc).__name__)
        return _effect_unknown(operation_id, target_id)

    audit_state = _verify_audit(db, expected)
    try:
        target_ok = bool(target_check())
    except Exception:  # noqa: BLE001 — unreadable is not verified
        target_ok = False
    if audit_state["status"] == "verified" and not target_ok:
        audit_state = {"status": "refuted", "audit_id": operation_id}
    if audit_state["status"] == "verified" and target_ok:
        return {
            "status": "verified",
            "data": _with_receipt(
                success_data, operation_id=operation_id,
                audit_id=operation_id),
            "message": "Workflow-template decision committed and verified.",
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": target_id,
        }
    return _committed_unverified(
        operation_id, audit_state, target_id=target_id)


# ---------------------------------------------------------------------------
# Public decisions
# ---------------------------------------------------------------------------

def create_template(
    db: Session, *, actor: Any, payload: Dict[str, Any],
    operation_id: Optional[str] = None,
    manager: Optional[WorkflowTemplateManager] = None,
) -> Dict[str, Any]:
    authority = _resolve_actor(db, actor)
    if not authority.get("ok"):
        return _actor_refusal(authority)
    try:
        operation_id = _operation_id("create", operation_id)
    except ValueError as exc:
        return _refused(str(exc), field="operation_id")

    if manager is None:
        manager = WorkflowTemplateManager()
    directory = _template_dir(manager)
    request_digest = _fingerprint(
        "workflow-template-request", "create", _canonical(payload))
    expected_base = {
        "operation_id": operation_id,
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_CREATE,
        "event_type": AuditEventType.UPDATE.value,
        "request_digest": request_digest,
        "actor_id": authority["id"],
    }
    replay = _replay(
        db, operation_id, expected_base, authority=authority,
        directory=directory)
    if replay is not None:
        return replay

    try:
        template = _build_template(payload)
    except Exception as exc:  # noqa: BLE001 — invalid input is not a write
        logger.warning(
            "workflow-template create validation failed: %s",
            type(exc).__name__)
        return _refused(
            "Invalid workflow template", error_code="VALIDATION_ERROR")

    template_id = _safe_template_id(template.template_id)
    if template_id is None:
        return _refused(
            "template_id is malformed", field="template_id",
            error_code="VALIDATION_ERROR")
    path = _template_path(directory, template_id)
    result_payload = _stable_payload(template)
    result_digest = _payload_digest(result_payload)

    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_CREATE,
        template_id=template_id, prior_digest="",
        result_digest=result_digest, request_digest=request_digest,
        actor=authority)

    try:
        with _template_lock(directory, template_id):
            if path is not None and path.exists():
                db.rollback()
                return _conflict(
                    "A template with this id already exists",
                    code="TEMPLATE_EXISTS")
            if not _claim_actor(db, authority):
                db.rollback()
                return _conflict(
                    "workflow authority changed; refresh and retry",
                    code="AUTHORITY_CHANGED")
            try:
                _atomic_create(path, _template_bytes(result_payload))
            except FileExistsError:
                db.rollback()
                return _conflict(
                    "A template with this id already exists",
                    code="TEMPLATE_EXISTS")
            except Exception as exc:  # noqa: BLE001 — no file effect
                db.rollback()
                logger.error(
                    "workflow-template create write failed: target=%s "
                    "error_class=%s", template_id, type(exc).__name__)
                return _not_applied(
                    "The workflow template could not be created; no effect "
                    "was committed")
    except Exception as exc:  # noqa: BLE001 — lock or directory failure
        db.rollback()
        logger.error(
            "workflow-template create lock failed: target=%s error_class=%s",
            template_id, type(exc).__name__)
        return _not_applied(
            "The workflow template could not be created; no effect was "
            "committed")

    audit_row = _audit_row(expected=expected, actor=authority)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (now := _read_template_payload(path)) is not None
            and _payload_digest(now) == result_digest),
        success_data={"template_id": template_id},
        authority=authority, directory=directory, path=path,
        prior_bytes=None, created=True)


def update_template(
    db: Session, *, actor: Any, template_id: str,
    updates: Dict[str, Any], operation_id: Optional[str] = None,
    manager: Optional[WorkflowTemplateManager] = None,
) -> Dict[str, Any]:
    authority = _resolve_actor(db, actor)
    if not authority.get("ok"):
        return _actor_refusal(authority)
    safe_id = _safe_template_id(template_id)
    if safe_id is None:
        return _refused(
            f"Template not found: {template_id}", http_status=404,
            error_code="NOT_FOUND")
    try:
        operation_id = _operation_id("update", operation_id)
    except ValueError as exc:
        return _refused(str(exc), field="operation_id")

    normalized_updates = {
        key: value for key, value in (updates or {}).items()
        if key in _ALLOWED_UPDATE_FIELDS and value is not None
    }
    if not normalized_updates:
        return _refused("No updates provided", field="updates")

    if manager is None:
        manager = WorkflowTemplateManager()
    directory = _template_dir(manager)
    template = _current_template(directory, safe_id)
    if template is None:
        return _refused(
            f"Template not found: {template_id}", http_status=404,
            error_code="NOT_FOUND")

    prior_payload = _stable_payload(template)
    prior_digest = _payload_digest(prior_payload)
    request_digest = _fingerprint(
        "workflow-template-request", "update", safe_id,
        _canonical(normalized_updates))
    expected_base = {
        "operation_id": operation_id,
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_UPDATE,
        "event_type": AuditEventType.UPDATE.value,
        "target_id": safe_id,
        "request_digest": request_digest,
        "actor_id": authority["id"],
    }
    replay = _replay(
        db, operation_id, expected_base, authority=authority,
        directory=directory)
    if replay is not None:
        return replay

    try:
        updated = _apply_updates(template, normalized_updates)
    except Exception as exc:  # noqa: BLE001 — invalid input is not a write
        logger.warning(
            "workflow-template update validation failed: %s",
            type(exc).__name__)
        return _refused(
            "Invalid workflow template update", error_code="VALIDATION_ERROR")
    changed_payload = _stable_payload(updated)
    if _canonical(changed_payload) == _canonical(prior_payload):
        return _no_change(
            {"template_id": safe_id, "template": prior_payload},
            "Workflow template already matches the request")

    updated.updated_at = datetime.now()
    result_payload = _stable_payload(updated)
    result_digest = _payload_digest(result_payload)

    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_UPDATE,
        template_id=safe_id, prior_digest=prior_digest,
        result_digest=result_digest, request_digest=request_digest,
        actor=authority)

    path = _template_path(directory, safe_id)
    prior_bytes = None
    if path is not None and path.exists():
        try:
            prior_bytes = path.read_bytes()
        except Exception:  # noqa: BLE001 — cannot bind exact prior bytes
            return _not_applied(
                "The workflow template could not be read; no effect was "
                "committed")

    try:
        with _template_lock(directory, safe_id):
            current = _current_template(directory, safe_id)
            if current is None:
                db.rollback()
                return _refused(
                    f"Template not found: {template_id}", http_status=404,
                    error_code="NOT_FOUND")
            current_payload = _stable_payload(current)
            if _canonical(current_payload) != _canonical(prior_payload):
                db.rollback()
                return _conflict(
                    "workflow template changed; refresh and retry",
                    code="STALE_TARGET")
            if not _claim_actor(db, authority):
                db.rollback()
                return _conflict(
                    "workflow authority changed; refresh and retry",
                    code="AUTHORITY_CHANGED")
            try:
                _atomic_replace(path, _template_bytes(result_payload))
            except Exception as exc:  # noqa: BLE001 — no file effect
                db.rollback()
                logger.error(
                    "workflow-template update write failed: target=%s "
                    "error_class=%s", safe_id, type(exc).__name__)
                return _not_applied(
                    "The workflow template could not be updated; no effect "
                    "was committed")
    except Exception as exc:  # noqa: BLE001 — lock or directory failure
        db.rollback()
        logger.error(
            "workflow-template update lock failed: target=%s error_class=%s",
            safe_id, type(exc).__name__)
        return _not_applied(
            "The workflow template could not be updated; no effect was "
            "committed")

    audit_row = _audit_row(expected=expected, actor=authority)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (now := _read_template_payload(path)) is not None
            and _payload_digest(now) == result_digest),
        success_data={"template_id": safe_id, "template": result_payload},
        authority=authority, directory=directory, path=path,
        prior_bytes=prior_bytes, created=False)
