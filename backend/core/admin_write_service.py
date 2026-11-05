"""Verified writes for the seven bounded admin privilege/budget routes.

The platform admin role/user rows are global; tenant billing is tenant-scoped.
This module freezes the acting administrator's authority and the exact target
material before the database claim, writes the mutation and one safe
``AuditLog`` operation receipt in the same transaction, then reads the audit and
target back from a fresh session. It does not add a second authorization or
approval engine.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import delete, exists, insert, literal, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from core.auth import SECRET_KEY
from core.models import (
    AdminRole,
    AdminUser,
    AuditEventType,
    AuditLog,
    SecurityLevel,
    Tenant,
    TenantSetting,
    User,
    UserRole,
)

logger = logging.getLogger(__name__)

OPERATION_PREFIX = "admin"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_PLATFORM_SCOPE = "platform"
_TENANT_SCOPE = "tenant"


# ---------------------------------------------------------------------------
# Safe identities and result envelopes
# ---------------------------------------------------------------------------

def _fingerprint(*parts: Any) -> str:
    message = "|".join(str(part if part is not None else "") for part in parts)
    return hmac.new(
        str(SECRET_KEY).encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return _fingerprint("state", _canonical_json(value))


def _new_operation_id(kind: str, supplied: Optional[str]) -> str:
    supplied = str(supplied or "").strip()
    if supplied.startswith(f"{OPERATION_PREFIX}:"):
        candidate = supplied
    elif supplied:
        candidate = f"{OPERATION_PREFIX}:{kind}:{supplied}"
    else:
        candidate = f"{OPERATION_PREFIX}:{kind}:{uuid.uuid4().hex}"
    if not _SAFE_OPERATION_RE.fullmatch(candidate):
        raise AdminWriteRefused(
            "operation_id is malformed", http_status=422,
            error_code="VALIDATION_ERROR", field="operation_id")
    return candidate


class AdminWriteRefused(Exception):
    def __init__(
        self, message: str, *, http_status: int = 422,
        error_code: str = "VALIDATION_ERROR", field: Optional[str] = None,
    ):
        self.message = str(message)
        self.http_status = int(http_status)
        self.error_code = str(error_code)
        self.field = field
        super().__init__(self.message)


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


def _effect_unknown(
    operation_id: str, *, target_type: str, target_id: str, stage: str,
) -> Dict[str, Any]:
    return {
        "status": "effect_unknown",
        "data": None,
        "message": (
            "The admin mutation may have committed but confirmation was lost. "
            "Retry with the same operation id; do not create a new operation."),
        "operation_id": operation_id,
        "audit_id": None,
        "target_type": target_type,
        "target_id": target_id,
        "verification": {
            "status": "unavailable",
            "effect": "unknown",
            "replay": "do_not_repeat",
            "stage": stage,
            "error": "COMMIT_OUTCOME_UNKNOWN",
        },
    }


def _committed_unverified(
    operation_id: str, *, audit_state: Dict[str, Any],
    target_type: str, target_id: str,
) -> Dict[str, Any]:
    return {
        "status": "committed_unverified",
        "data": None,
        "message": (
            "The admin mutation committed but its audit/target readback did "
            "not verify. Use the original operation id to reconcile."),
        "operation_id": operation_id,
        "audit_id": audit_state.get("audit_id"),
        "target_type": target_type,
        "target_id": target_id,
        "verification": {
            "status": audit_state.get("status", "unavailable"),
            "effect": "committed",
            "replay": "do_not_repeat",
            "audit_id": audit_state.get("audit_id"),
        },
    }


def _fresh_session(db: Session) -> Session:
    bind = db.get_bind()
    return sessionmaker(bind=bind)()


def _actor_snapshot(actor: User) -> Dict[str, Any]:
    return {
        "id": str(actor.id),
        "role": str(actor.role or ""),
        "status": str(actor.status or ""),
        "is_active": bool(actor.is_active),
        "tenant_id": actor.tenant_id,
        "workspace_id": actor.workspace_id,
    }


def _actor_digest(actor: Dict[str, Any]) -> str:
    return _fingerprint(
        "admin-actor", actor["id"], actor["role"], actor["status"],
        "1" if actor["is_active"] else "0")


def _actor_current_ok(
    db: Session, actor: User, *, required: str = "super_admin",
) -> bool:
    """Read the current authority without writing (replay-safe gate)."""
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(User).filter(User.id == str(actor.id)).first()
            if row is None:
                return False
            if not bool(row.is_active):
                return False
            if str(row.status or "").strip().lower() != "active":
                return False
            if required == "super_admin":
                return str(row.role or "") == UserRole.SUPER_ADMIN.value
            from core.security.rbac import user_meets_role
            return user_meets_role(row, UserRole.WORKSPACE_ADMIN)
    except Exception:  # noqa: BLE001 — unreadable authority is denied
        return False


def _claim_actor(
    db: Session, actor: User, *, required: str = "super_admin",
) -> bool:
    """Conditional no-op update: the actor row must still match the snapshot."""
    snapshot = _actor_snapshot(actor)
    if required == "super_admin":
        if snapshot["role"] not in (
                UserRole.SUPER_ADMIN.value, "super_admin"):
            return False
    elif required == "workspace_admin":
        from core.security.rbac import user_meets_role
        if not user_meets_role(actor, UserRole.WORKSPACE_ADMIN):
            return False
    predicates = [
        User.id == snapshot["id"],
        User.role == snapshot["role"],
        User.status == snapshot["status"],
        User.is_active.is_(snapshot["is_active"]),
    ]
    try:
        result = db.execute(
            update(User).where(*predicates).values(status=User.status))
        return result.rowcount == 1
    except Exception:
        return False


def _begin_operation(
    db: Session, actor: User, kind: str, supplied: Optional[str],
    *, required: str = "super_admin",
):
    """Validate the operation id and current authority before any work."""
    try:
        operation_id = _new_operation_id(kind, supplied)
    except AdminWriteRefused as exc:
        return None, _refused(
            exc.message, http_status=exc.http_status,
            error_code=exc.error_code, field=exc.field)
    if not _actor_current_ok(db, actor, required=required):
        return None, _refused(
            "administrator authority changed; refresh and retry",
            http_status=403, error_code="AUTHORITY_CHANGED")
    return operation_id, None


def _today_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Audit ledger / operation receipt
# ---------------------------------------------------------------------------

def _audit_expected(
    *, operation_id: str, kind: str, actor: Dict[str, Any],
    scope: str, target_type: str, target_id: str,
    material_digest: str, result_digest: str,
    tenant_id: Optional[str], event_type: str, audit_action: str,
    resource: str,
) -> Dict[str, Any]:
    return {
        "operation_id": str(operation_id),
        "kind": str(kind),
        "actor_id": str(actor["id"]),
        "actor_role": str(actor["role"]),
        "scope": str(scope),
        "target_type": str(target_type),
        "target_id": str(target_id),
        "material_digest": str(material_digest),
        "result_digest": str(result_digest),
        "tenant_id": tenant_id,
        "event_type": str(event_type),
        "audit_action": str(audit_action),
        "resource": str(resource),
    }


def _audit_row(
    *, operation_id: str, expected: Dict[str, Any], actor: User,
    tenant_id: Optional[str], description: str,
) -> AuditLog:
    metadata = {
        "operation_id": expected["operation_id"],
        "kind": expected["kind"],
        "actor_id": expected["actor_id"],
        "actor_role": expected["actor_role"],
        "scope": expected["scope"],
        "target_type": expected["target_type"],
        "target_id": expected["target_id"],
        "material_digest": expected["material_digest"],
        "result_digest": expected["result_digest"],
        "tenant_id": expected["tenant_id"],
    }
    return AuditLog(
        id=expected["operation_id"],
        event_type=expected["event_type"],
        security_level=SecurityLevel.HIGH.value,
        threat_level="none",
        user_id=str(actor.id),
        user_email=getattr(actor, "email", None),
        tenant_id=tenant_id,
        workspace_id=None,
        resource=expected["resource"],
        action=expected["audit_action"],
        description=description,
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
            if str(row.action or "") != expected["audit_action"]:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.user_id or "") != expected["actor_id"]:
                return {"status": "refuted", "audit_id": audit_id}
            if row.workspace_id is not None:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.security_level or "") != SecurityLevel.HIGH.value:
                return {"status": "refuted", "audit_id": audit_id}
            if row.success is not True:
                return {"status": "refuted", "audit_id": audit_id}
            if (row.tenant_id or None) != (expected["tenant_id"] or None):
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.resource or "") != expected["resource"]:
                return {"status": "refuted", "audit_id": audit_id}
            try:
                metadata = json.loads(row.metadata_json or "{}")
            except (TypeError, ValueError):
                return {"status": "unavailable", "audit_id": audit_id}
            if not isinstance(metadata, dict):
                return {"status": "unavailable", "audit_id": audit_id}
            string_fields = (
                "operation_id", "kind", "actor_id", "actor_role", "scope",
                "target_type", "target_id", "material_digest",
                "result_digest",
            )
            for key in string_fields:
                if key not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                if not isinstance(metadata[key], str):
                    return {"status": "refuted", "audit_id": audit_id}
                if metadata[key] != expected[key]:
                    return {"status": "refuted", "audit_id": audit_id}
            if "tenant_id" not in metadata:
                return {"status": "unavailable", "audit_id": audit_id}
            if expected["tenant_id"] is None:
                if metadata["tenant_id"] is not None:
                    return {"status": "refuted", "audit_id": audit_id}
            else:
                if not isinstance(metadata["tenant_id"], str) or (
                        metadata["tenant_id"] != expected["tenant_id"]):
                    return {"status": "refuted", "audit_id": audit_id}
            return {"status": "verified", "audit_id": audit_id}
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "admin audit read-back failed: operation_id=%s error_class=%s",
            audit_id, type(exc).__name__)
        return {"status": "unavailable", "audit_id": audit_id}


def _existing_operation(
    db: Session, operation_id: str,
) -> Optional[Dict[str, Any]]:
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(AuditLog).filter(
                AuditLog.id == operation_id).first()
            if row is None:
                return None
            try:
                metadata = json.loads(row.metadata_json or "{}")
            except (TypeError, ValueError):
                metadata = {}
            return {
                "id": row.id,
                "event_type": row.event_type,
                "action": row.action,
                "user_id": row.user_id,
                "tenant_id": row.tenant_id,
                "resource": row.resource,
                "success": row.success,
                "metadata": metadata if isinstance(metadata, dict) else {},
            }
    except Exception:
        return None


def _with_existing_result_digest(
    expected: Dict[str, Any], existing: Dict[str, Any],
) -> Dict[str, Any]:
    metadata = existing.get("metadata") or {}
    replay_expected = dict(expected)
    replay_expected["result_digest"] = str(
        metadata.get("result_digest") or "")
    return replay_expected


def _replay(
    db: Session, operation_id: str, expected: Dict[str, Any],
    *, target_type: str, target_id: str, target_verified: bool,
) -> Dict[str, Any]:
    existing = _existing_operation(db, operation_id)
    if existing is None:
        return _committed_unverified(
            operation_id, audit_state={"status": "unavailable"},
            target_type=target_type, target_id=target_id)
    metadata = existing.get("metadata") or {}
    if (
        str(metadata.get("material_digest") or "")
        != expected["material_digest"]
        or str(metadata.get("kind") or "") != expected["kind"]
        or str(metadata.get("actor_id") or "") != expected["actor_id"]
        or str(metadata.get("target_type") or "") != expected["target_type"]
        or str(metadata.get("target_id") or "") != expected["target_id"]
        or (metadata.get("tenant_id") or None) != expected["tenant_id"]
    ):
        return _conflict(
            "operation_id is bound to different material",
            code="OPERATION_CONFLICT")
    audit_state = _verify_audit(db, expected)
    if audit_state["status"] == "verified" and not target_verified:
        audit_state = {
            "status": "refuted", "audit_id": expected["operation_id"]}
    if audit_state["status"] == "verified" and target_verified:
        return {
            "status": "already_applied",
            "data": None,
            "message": "This admin operation was already applied.",
            "operation_id": operation_id,
            "audit_id": expected["operation_id"],
            "target_type": target_type,
            "target_id": target_id,
            "verification": {
                "status": "already_applied",
                "effect": "committed",
                "replay": "do_not_repeat",
                "audit_id": expected["operation_id"],
            },
        }
    return _committed_unverified(
        operation_id, audit_state=audit_state,
        target_type=target_type, target_id=target_id)


def _commit_and_verify(
    db: Session, *, expected: Dict[str, Any], audit_row: AuditLog,
    target_check, target_type: str, target_id: str,
    integrity_conflict: Optional[tuple] = None,
) -> Dict[str, Any]:
    try:
        db.add(audit_row)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _existing_operation(db, expected["operation_id"])
        if existing is not None:
            try:
                target_verified = bool(target_check())
            except Exception:  # noqa: BLE001 — unreadable is not verified
                target_verified = False
            return _replay(
                db, expected["operation_id"], expected,
                target_type=target_type, target_id=target_id,
                target_verified=target_verified)
        return _committed_unverified(
            expected["operation_id"],
            audit_state={"status": "unavailable"},
            target_type=target_type, target_id=target_id)
    except Exception as exc:  # noqa: BLE001 — commit outcome unknown
        db.rollback()
        logger.error(
            "admin write outcome unknown: operation_id=%s target=%s "
            "stage=commit error_class=%s",
            expected["operation_id"], target_id, type(exc).__name__)
        return _effect_unknown(
            expected["operation_id"], target_type=target_type,
            target_id=target_id, stage="commit")
    audit_state = _verify_audit(db, expected)
    try:
        target_verified = bool(target_check())
    except Exception:  # noqa: BLE001 — unreadable is not verified
        target_verified = False
    if audit_state["status"] == "verified" and not target_verified:
        audit_state = {
            "status": "refuted", "audit_id": expected["operation_id"]}
    if audit_state["status"] == "verified" and target_verified:
        return {
            "status": "verified",
            "data": None,
            "message": "Admin mutation committed and verified.",
            "operation_id": expected["operation_id"],
            "audit_id": expected["operation_id"],
            "target_type": target_type,
            "target_id": target_id,
            "verification": {
                "status": "verified",
                "effect": "committed",
                "audit_id": expected["operation_id"],
            },
        }
    return _committed_unverified(
        expected["operation_id"], audit_state=audit_state,
        target_type=target_type, target_id=target_id)


# ---------------------------------------------------------------------------
# Target states
# ---------------------------------------------------------------------------

def _role_state(row: AdminRole) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "name": str(row.name or ""),
        "permissions": dict(row.permissions or {}),
        "description": row.description,
    }


def _admin_user_state(row: AdminUser) -> Dict[str, Any]:
    """Mutable identity material; timestamps are not CAS/receipt material."""
    return {
        "id": str(row.id),
        "email": str(row.email or ""),
        "name": str(row.name or ""),
        "role_id": str(row.role_id or ""),
        "status": str(row.status or ""),
    }


def _admin_user_response(row: AdminUser) -> Dict[str, Any]:
    state = _admin_user_state(row)
    state["last_login"] = (
        row.last_login.isoformat() if row.last_login else None)
    state["created_at"] = (
        row.created_at.isoformat() if row.created_at else None)
    return state


def _budget_setting_state(row: Optional[TenantSetting]) -> Optional[str]:
    return None if row is None else str(row.setting_value or "")


def _read_role(db: Session, role_id: str) -> Optional[Dict[str, Any]]:
    with _fresh_session(db) as fresh:
        row = fresh.query(AdminRole).filter(
            AdminRole.id == str(role_id)).first()
        return _role_state(row) if row else None


def _read_admin_user(db: Session, admin_id: str) -> Optional[Dict[str, Any]]:
    with _fresh_session(db) as fresh:
        row = fresh.query(AdminUser).filter(
            AdminUser.id == str(admin_id)).first()
        return _admin_user_state(row) if row else None


def _read_admin_user_response(
    db: Session, admin_id: str,
) -> Optional[Dict[str, Any]]:
    with _fresh_session(db) as fresh:
        row = fresh.query(AdminUser).filter(
            AdminUser.id == str(admin_id)).first()
        return _admin_user_response(row) if row else None


def _assigned_admin_count(db: Session, role_id: str) -> int:
    with _fresh_session(db) as fresh:
        return fresh.query(AdminUser).filter(
            AdminUser.role_id == str(role_id)).count()


def _read_budget_setting(db: Session, tenant_id: str) -> Optional[str]:
    with _fresh_session(db) as fresh:
        row = fresh.query(TenantSetting).filter(
            TenantSetting.tenant_id == str(tenant_id),
            TenantSetting.setting_key == "billing",
        ).first()
        return _budget_setting_state(row)


# ---------------------------------------------------------------------------
# Role operations
# ---------------------------------------------------------------------------

_ROLE_AUDIT_ACTIONS = {
    "create": "admin_role_created",
    "update": "admin_role_updated",
    "delete": "admin_role_deleted",
}


def create_admin_role(
    db: Session, *, actor: User, name: str, permissions: Dict[str, bool],
    description: Optional[str], operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    operation_id, refusal = _begin_operation(
        db, actor, "role-create", operation_id)
    if refusal:
        return refusal
    actor_snapshot = _actor_snapshot(actor)
    request = {
        "kind": "role_create", "name": str(name),
        "permissions": dict(permissions or {}),
        "description": description,
    }
    material_digest = _fingerprint(
        "admin-material", actor_snapshot["id"], _canonical_json(request))
    result_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{operation_id}:role"))
    result_state = {
        "id": result_id, "name": request["name"],
        "permissions": request["permissions"], "description": description,
    }
    result_digest = _digest(result_state)
    expected = _audit_expected(
        operation_id=operation_id, kind="role_create",
        actor=actor_snapshot, scope=_PLATFORM_SCOPE,
        target_type="admin_role", target_id=result_id,
        material_digest=material_digest, result_digest=result_digest,
        tenant_id=None, event_type=AuditEventType.CREATE.value,
        audit_action=_ROLE_AUDIT_ACTIONS["create"],
        resource=f"admin_role:{result_id}")
    existing = _existing_operation(db, operation_id)
    if existing is not None:
        replay = _replay(
            db, operation_id, expected, target_type="admin_role",
            target_id=result_id,
            target_verified=_read_role(db, result_id) is not None
            and _digest(_read_role(db, result_id)) == result_digest)
        if replay["status"] == "already_applied":
            replay["data"] = _read_role(db, result_id) or result_state
        return replay
    if not _claim_actor(db, actor):
        db.rollback()
        return _conflict(
            "administrator authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")
    try:
        db.add(AdminRole(
            id=result_id, name=request["name"],
            permissions=request["permissions"], description=description))
        # Flush here so unique conflicts are caught before the audit insert.
        db.flush()
    except IntegrityError:
        db.rollback()
        existing_now = _existing_operation(db, operation_id)
        if existing_now is not None:
            current = _read_role(db, result_id)
            replay = _replay(
                db, operation_id, expected, target_type="admin_role",
                target_id=result_id,
                target_verified=(
                    current is not None
                    and _digest(current) == result_digest))
            if replay["status"] == "already_applied":
                replay["data"] = current or result_state
            return replay
        if _read_role(db, result_id) is not None:
            return _committed_unverified(
                operation_id, audit_state={"status": "unavailable"},
                target_type="admin_role", target_id=result_id)
        return _conflict(
            "Role with this name already exists", code="DUPLICATE_NAME")
    audit_row = _audit_row(
        operation_id=operation_id, expected=expected, actor=actor,
        tenant_id=None,
        description=f"Admin role {result_id} created")
    result = _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            _read_role(db, result_id) is not None
            and _digest(_read_role(db, result_id)) == result_digest),
        target_type="admin_role", target_id=result_id)
    if result["status"] in ("verified", "already_applied"):
        result["data"] = _read_role(db, result_id) or result_state
    return result


def update_admin_role(
    db: Session, *, actor: User, role_id: str,
    changes: Dict[str, Any], operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    operation_id, refusal = _begin_operation(
        db, actor, "role-update", operation_id)
    if refusal:
        return refusal
    effective_changes = {
        key: value for key, value in (changes or {}).items()
        if value is not None
    }
    changes = effective_changes
    actor_snapshot = _actor_snapshot(actor)
    request = {
        "kind": "role_update", "role_id": str(role_id),
        "changes": changes,
    }
    material_digest = _fingerprint(
        "admin-material", actor_snapshot["id"], _canonical_json(request))
    expected_base = _audit_expected(
        operation_id=operation_id, kind="role_update",
        actor=actor_snapshot, scope=_PLATFORM_SCOPE,
        target_type="admin_role", target_id=str(role_id),
        material_digest=material_digest, result_digest="",
        tenant_id=None, event_type=AuditEventType.UPDATE.value,
        audit_action=_ROLE_AUDIT_ACTIONS["update"],
        resource=f"admin_role:{role_id}")
    existing = _existing_operation(db, operation_id)
    if existing is not None:
        expected_replay = _with_existing_result_digest(
            expected_base, existing)
        current_now = _read_role(db, role_id)
        target_verified = (
            current_now is not None
            and _digest(current_now) == expected_replay["result_digest"])
        replay = _replay(
            db, operation_id, expected_replay,
            target_type="admin_role", target_id=str(role_id),
            target_verified=target_verified)
        if replay["status"] == "already_applied":
            replay["data"] = current_now or {}
        return replay
    current = _read_role(db, role_id)
    if current is None:
        return _refused(
            f"AdminRole not found: {role_id}", http_status=404,
            error_code="NOT_FOUND")
    if not effective_changes:
        return {
            "status": "no_change",
            "data": current,
            "message": "No admin role changes requested.",
            "operation_id": None,
            "audit_id": None,
            "verification": {"status": "no_change", "effect": "none"},
        }
    new_state = dict(current)
    for key in ("name", "permissions", "description"):
        if key in changes and changes[key] is not None:
            new_state[key] = changes[key]
    result_digest = _digest(new_state)
    expected = dict(expected_base)
    expected["result_digest"] = result_digest
    if not _claim_actor(db, actor):
        db.rollback()
        return _conflict(
            "administrator authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")
    predicates = [
        AdminRole.id == str(role_id),
        AdminRole.name == current["name"],
        AdminRole.permissions == current["permissions"],
        AdminRole.description == current["description"],
    ]
    values = {
        key: changes[key] for key in ("name", "permissions", "description")
        if changes.get(key) is not None
    }
    try:
        result = db.execute(
            update(AdminRole).where(*predicates).values(**values))
        if result.rowcount != 1:
            db.rollback()
            now = _read_role(db, role_id)
            if now is None:
                return _refused(
                    f"AdminRole not found: {role_id}", http_status=404,
                    error_code="NOT_FOUND")
            return _conflict(
                "admin role changed; refresh and retry",
                code="STALE_TARGET")
        db.flush()
    except IntegrityError:
        db.rollback()
        return _conflict(
            "Role with this name already exists", code="DUPLICATE_NAME")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "admin role update failed: operation_id=%s stage=update "
            "error_class=%s", operation_id, type(exc).__name__)
        return _conflict(
            "Admin role update could not be applied",
            code="STALE_TARGET")
    audit_row = _audit_row(
        operation_id=operation_id, expected=expected, actor=actor,
        tenant_id=None,
        description=f"Admin role {role_id} updated")
    result = _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            _read_role(db, role_id) is not None
            and _digest(_read_role(db, role_id)) == result_digest),
        target_type="admin_role", target_id=str(role_id),
        integrity_conflict=(
            "Role with this name already exists", "DUPLICATE_NAME"))
    if result["status"] in ("verified", "already_applied"):
        result["data"] = _read_role(db, role_id) or new_state
    return result


def delete_admin_role(
    db: Session, *, actor: User, role_id: str,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    operation_id, refusal = _begin_operation(
        db, actor, "role-delete", operation_id)
    if refusal:
        return refusal
    actor_snapshot = _actor_snapshot(actor)
    request = {
        "kind": "role_delete", "role_id": str(role_id),
    }
    material_digest = _fingerprint(
        "admin-material", actor_snapshot["id"], _canonical_json(request))
    expected_base = _audit_expected(
        operation_id=operation_id, kind="role_delete",
        actor=actor_snapshot, scope=_PLATFORM_SCOPE,
        target_type="admin_role", target_id=str(role_id),
        material_digest=material_digest,
        result_digest=_digest({"deleted": role_id}),
        tenant_id=None, event_type=AuditEventType.DELETE.value,
        audit_action=_ROLE_AUDIT_ACTIONS["delete"],
        resource=f"admin_role:{role_id}")
    existing = _existing_operation(db, operation_id)
    if existing is not None:
        expected_replay = _with_existing_result_digest(
            expected_base, existing)
        target_verified = (
            _read_role(db, role_id) is None
            and _assigned_admin_count(db, role_id) == 0)
        replay = _replay(
            db, operation_id, expected_replay,
            target_type="admin_role", target_id=str(role_id),
            target_verified=target_verified)
        if replay["status"] == "already_applied":
            replay["data"] = {"message": "Admin role deleted successfully"}
        return replay
    current = _read_role(db, role_id)
    if current is None:
        return _refused(
            f"AdminRole not found: {role_id}", http_status=404,
            error_code="NOT_FOUND")
    expected = dict(expected_base)
    if not _claim_actor(db, actor):
        db.rollback()
        return _conflict(
            "administrator authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")
    assigned = db.query(AdminUser).filter(
        AdminUser.role_id == str(role_id)).count()
    if assigned:
        db.rollback()
        return _conflict(
            f"Cannot delete role: {assigned} admin user(s) still assigned",
            code="ROLE_IN_USE")
    predicates = [
        AdminRole.id == str(role_id),
        AdminRole.name == current["name"],
        AdminRole.permissions == current["permissions"],
        AdminRole.description == current["description"],
        ~exists().where(AdminUser.role_id == str(role_id)),
    ]
    try:
        result = db.execute(delete(AdminRole).where(*predicates))
    except IntegrityError:
        db.rollback()
        return _conflict(
            "Cannot delete role: admin users are still assigned",
            code="ROLE_IN_USE")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "admin role delete failed: operation_id=%s stage=delete "
            "error_class=%s", operation_id, type(exc).__name__)
        return _conflict(
            "admin role delete could not be applied",
            code="STALE_TARGET")
    if result.rowcount != 1:
        db.rollback()
        now = _read_role(db, role_id)
        if now is None:
            return _refused(
                f"AdminRole not found: {role_id}", http_status=404,
                error_code="NOT_FOUND")
        return _conflict(
            "admin role changed or is in use; refresh and retry",
            code="STALE_TARGET")
    audit_row = _audit_row(
        operation_id=operation_id, expected=expected, actor=actor,
        tenant_id=None,
        description=f"Admin role {role_id} deleted")
    result = _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            _read_role(db, role_id) is None
            and _assigned_admin_count(db, role_id) == 0),
        target_type="admin_role", target_id=str(role_id))
    if result["status"] in ("verified", "already_applied"):
        result["data"] = {"message": "Admin role deleted successfully"}
    return result


# ---------------------------------------------------------------------------
# Admin user operations
# ---------------------------------------------------------------------------

_USER_AUDIT_ACTIONS = {
    "create": "admin_user_created",
    "update": "admin_user_updated",
    "delete": "admin_user_deleted",
}


def _password_fingerprint(password: str) -> str:
    return _fingerprint("admin-password", password)


def create_admin_user(
    db: Session, *, actor: User, email: str, name: str, password: str,
    role_id: str, operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    operation_id, refusal = _begin_operation(
        db, actor, "user-create", operation_id)
    if refusal:
        return refusal
    actor_snapshot = _actor_snapshot(actor)
    request = {
        "kind": "user_create", "email": str(email), "name": str(name),
        "role_id": str(role_id),
        "password_material": _password_fingerprint(password),
    }
    material_digest = _fingerprint(
        "admin-material", actor_snapshot["id"], _canonical_json(request))
    result_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{operation_id}:user"))
    result_state = {
        "id": result_id, "email": request["email"], "name": request["name"],
        "role_id": request["role_id"], "status": "active",
    }
    result_digest = _digest(result_state)
    expected = _audit_expected(
        operation_id=operation_id, kind="user_create",
        actor=actor_snapshot, scope=_PLATFORM_SCOPE,
        target_type="admin_user", target_id=result_id,
        material_digest=material_digest, result_digest=result_digest,
        tenant_id=None, event_type=AuditEventType.CREATE.value,
        audit_action=_USER_AUDIT_ACTIONS["create"],
        resource=f"admin_user:{result_id}")
    existing = _existing_operation(db, operation_id)
    if existing is not None:
        now = _read_admin_user(db, result_id)
        replay = _replay(
            db, operation_id, expected, target_type="admin_user",
            target_id=result_id,
            target_verified=(
                now is not None and _digest(now) == result_digest))
        if replay["status"] == "already_applied":
            replay["data"] = (
                _read_admin_user_response(db, result_id) or result_state)
        return replay
    if _read_role(db, role_id) is None:
        return _refused(
            f"AdminRole not found: {role_id}", http_status=404,
            error_code="NOT_FOUND", field="role_id")
    if not _claim_actor(db, actor):
        db.rollback()
        return _conflict(
            "administrator authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")
    from core.auth import get_password_hash
    password_hash = get_password_hash(password)
    # The role existence check is part of the INSERT itself, so a concurrent
    # role deletion cannot leave a dangling assignment in SQLite where FK
    # enforcement may be off. The unique email constraint is the duplicate
    # arbiter.
    conditional_insert = insert(AdminUser).from_select(
        ["id", "email", "name", "password_hash", "role_id", "status"],
        select(
            literal(result_id), literal(request["email"]),
            literal(request["name"]), literal(password_hash),
            literal(request["role_id"]), literal("active"),
        ).where(exists().where(AdminRole.id == request["role_id"])),
    )
    try:
        inserted = db.execute(conditional_insert)
        if inserted.rowcount != 1:
            db.rollback()
            if _read_role(db, request["role_id"]) is None:
                return _refused(
                    f"AdminRole not found: {request['role_id']}",
                    http_status=404, error_code="NOT_FOUND",
                    field="role_id")
            return _conflict(
                "admin role changed; refresh and retry",
                code="STALE_TARGET")
        db.flush()
    except IntegrityError:
        db.rollback()
        existing_now = _existing_operation(db, operation_id)
        if existing_now is not None:
            current = _read_admin_user(db, result_id)
            replay = _replay(
                db, operation_id, expected, target_type="admin_user",
                target_id=result_id,
                target_verified=(
                    current is not None
                    and _digest(current) == result_digest))
            if replay["status"] == "already_applied":
                replay["data"] = (
                    _read_admin_user_response(db, result_id)
                    or result_state)
            return replay
        if _read_admin_user(db, result_id) is not None:
            return _committed_unverified(
                operation_id, audit_state={"status": "unavailable"},
                target_type="admin_user", target_id=result_id)
        return _conflict(
            "Admin user with this email already exists",
            code="DUPLICATE_EMAIL")
    audit_row = _audit_row(
        operation_id=operation_id, expected=expected, actor=actor,
        tenant_id=None,
        description=f"Admin user {result_id} created")
    result = _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            _read_admin_user(db, result_id) is not None
            and _digest(_read_admin_user(db, result_id)) == result_digest),
        target_type="admin_user", target_id=result_id)
    if result["status"] in ("verified", "already_applied"):
        result["data"] = (
            _read_admin_user_response(db, result_id) or result_state)
    return result


def update_admin_user(
    db: Session, *, actor: User, admin_id: str,
    changes: Dict[str, Any], operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    operation_id, refusal = _begin_operation(
        db, actor, "user-update", operation_id)
    if refusal:
        return refusal
    effective_changes = {
        key: value for key, value in (changes or {}).items()
        if value is not None
    }
    changes = effective_changes
    actor_snapshot = _actor_snapshot(actor)
    request = {
        "kind": "user_update", "admin_id": str(admin_id),
        "changes": changes,
    }
    material_digest = _fingerprint(
        "admin-material", actor_snapshot["id"], _canonical_json(request))
    expected_base = _audit_expected(
        operation_id=operation_id, kind="user_update",
        actor=actor_snapshot, scope=_PLATFORM_SCOPE,
        target_type="admin_user", target_id=str(admin_id),
        material_digest=material_digest, result_digest="",
        tenant_id=None, event_type=AuditEventType.UPDATE.value,
        audit_action=_USER_AUDIT_ACTIONS["update"],
        resource=f"admin_user:{admin_id}")
    existing = _existing_operation(db, operation_id)
    if existing is not None:
        expected_replay = _with_existing_result_digest(
            expected_base, existing)
        now = _read_admin_user(db, admin_id)
        target_verified = (
            now is not None
            and _digest(now) == expected_replay["result_digest"])
        replay = _replay(
            db, operation_id, expected_replay,
            target_type="admin_user", target_id=str(admin_id),
            target_verified=target_verified)
        if replay["status"] == "already_applied":
            replay["data"] = (
                _read_admin_user_response(db, admin_id) or now or {})
        return replay
    target = db.query(AdminUser).filter(
        AdminUser.id == str(admin_id)).first()
    if target is None:
        return _refused(
            f"AdminUser not found: {admin_id}", http_status=404,
            error_code="NOT_FOUND")
    if changes.get("role_id") is not None and _read_role(
            db, changes["role_id"]) is None:
        return _refused(
            f"AdminRole not found: {changes['role_id']}",
            http_status=404, error_code="NOT_FOUND", field="role_id")
    current = _admin_user_state(target)
    if not effective_changes:
        return {
            "status": "no_change",
            "data": (_read_admin_user_response(db, admin_id) or current),
            "message": "No admin user changes requested.",
            "operation_id": None,
            "audit_id": None,
            "verification": {"status": "no_change", "effect": "none"},
        }
    new_state = dict(current)
    for key in ("name", "role_id", "status"):
        if changes.get(key) is not None:
            new_state[key] = changes[key]
    result_digest = _digest(new_state)
    expected = dict(expected_base)
    expected["result_digest"] = result_digest
    if not _claim_actor(db, actor):
        db.rollback()
        return _conflict(
            "administrator authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")
    predicates = [
        AdminUser.id == str(admin_id),
        AdminUser.email == current["email"],
        AdminUser.name == current["name"],
        AdminUser.role_id == current["role_id"],
        AdminUser.status == current["status"],
    ]
    if new_state["role_id"] != current["role_id"]:
        predicates.append(
            exists().where(AdminRole.id == new_state["role_id"]))
    values = {
        key: new_state[key] for key in ("name", "role_id", "status")
        if changes.get(key) is not None
    }
    try:
        result = db.execute(
            update(AdminUser).where(*predicates).values(**values))
    except IntegrityError:
        db.rollback()
        return _conflict(
            "admin user changed; refresh and retry",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "admin user update failed: operation_id=%s stage=update "
            "error_class=%s", operation_id, type(exc).__name__)
        return _conflict(
            "Admin user update could not be applied",
            code="STALE_TARGET")
    if result.rowcount != 1:
        db.rollback()
        now = _read_admin_user(db, admin_id)
        if now is None:
            return _refused(
                f"AdminUser not found: {admin_id}", http_status=404,
                error_code="NOT_FOUND")
        if changes.get("role_id") is not None and _read_role(
                db, changes["role_id"]) is None:
            return _refused(
                f"AdminRole not found: {changes['role_id']}",
                http_status=404, error_code="NOT_FOUND", field="role_id")
        return _conflict(
            "admin user changed; refresh and retry",
            code="STALE_TARGET")
    audit_row = _audit_row(
        operation_id=operation_id, expected=expected, actor=actor,
        tenant_id=None,
        description=f"Admin user {admin_id} updated")
    result = _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            _read_admin_user(db, admin_id) is not None
            and _digest(_read_admin_user(db, admin_id)) == result_digest),
        target_type="admin_user", target_id=str(admin_id))
    if result["status"] in ("verified", "already_applied"):
        result["data"] = (
            _read_admin_user_response(db, admin_id) or new_state)
    return result


def delete_admin_user(
    db: Session, *, actor: User, admin_id: str,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    operation_id, refusal = _begin_operation(
        db, actor, "user-delete", operation_id)
    if refusal:
        return refusal
    actor_snapshot = _actor_snapshot(actor)
    request = {
        "kind": "user_delete", "admin_id": str(admin_id),
    }
    material_digest = _fingerprint(
        "admin-material", actor_snapshot["id"], _canonical_json(request))
    expected_base = _audit_expected(
        operation_id=operation_id, kind="user_delete",
        actor=actor_snapshot, scope=_PLATFORM_SCOPE,
        target_type="admin_user", target_id=str(admin_id),
        material_digest=material_digest,
        result_digest=_digest({"deleted": admin_id}),
        tenant_id=None, event_type=AuditEventType.DELETE.value,
        audit_action=_USER_AUDIT_ACTIONS["delete"],
        resource=f"admin_user:{admin_id}")
    existing = _existing_operation(db, operation_id)
    if existing is not None:
        expected_replay = _with_existing_result_digest(
            expected_base, existing)
        replay = _replay(
            db, operation_id, expected_replay, target_type="admin_user",
            target_id=str(admin_id),
            target_verified=_read_admin_user(db, admin_id) is None)
        if replay["status"] == "already_applied":
            replay["data"] = {"message": "Admin user deleted successfully"}
        return replay
    target = db.query(AdminUser).filter(
        AdminUser.id == str(admin_id)).first()
    if target is None:
        return _refused(
            f"AdminUser not found: {admin_id}", http_status=404,
            error_code="NOT_FOUND")
    current = _admin_user_state(target)
    expected = dict(expected_base)
    if not _claim_actor(db, actor):
        db.rollback()
        return _conflict(
            "administrator authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")
    predicates = [
        AdminUser.id == str(admin_id),
        AdminUser.email == current["email"],
        AdminUser.name == current["name"],
        AdminUser.role_id == current["role_id"],
        AdminUser.status == current["status"],
    ]
    try:
        result = db.execute(delete(AdminUser).where(*predicates))
    except IntegrityError:
        db.rollback()
        return _conflict(
            "admin user changed; refresh and retry",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "admin user delete failed: operation_id=%s stage=delete "
            "error_class=%s", operation_id, type(exc).__name__)
        return _conflict(
            "Admin user delete could not be applied",
            code="STALE_TARGET")
    if result.rowcount != 1:
        db.rollback()
        now = _read_admin_user(db, admin_id)
        if now is None:
            return _refused(
                f"AdminUser not found: {admin_id}", http_status=404,
                error_code="NOT_FOUND")
        return _conflict(
            "admin user changed; refresh and retry",
            code="STALE_TARGET")
    audit_row = _audit_row(
        operation_id=operation_id, expected=expected, actor=actor,
        tenant_id=None,
        description=f"Admin user {admin_id} deleted")
    result = _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: _read_admin_user(db, admin_id) is None,
        target_type="admin_user", target_id=str(admin_id))
    if result["status"] in ("verified", "already_applied"):
        result["data"] = {"message": "Admin user deleted successfully"}
    return result


# ---------------------------------------------------------------------------
# Tenant budget
# ---------------------------------------------------------------------------

def update_tenant_budget(
    db: Session, *, actor: User, tenant_id: str,
    budget_limit_usd: Optional[float] = None,
    enforcement_mode: Optional[str] = None,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    from core.budget_enforcement_service import BudgetEnforcementMode

    operation_id, refusal = _begin_operation(
        db, actor, "budget-update", operation_id,
        required="workspace_admin")
    if refusal:
        return refusal
    actor_snapshot = _actor_snapshot(actor)

    if budget_limit_usd is not None:
        try:
            budget_limit_usd = float(budget_limit_usd)
        except (TypeError, ValueError):
            return _refused(
                "budget_limit_usd must be a finite number",
                field="budget_limit_usd")
        if not math.isfinite(budget_limit_usd) or budget_limit_usd < 0:
            return _refused(
                "budget_limit_usd must be a finite non-negative number",
                field="budget_limit_usd")
    if enforcement_mode is not None and enforcement_mode not in set(
            BudgetEnforcementMode.ALL):
        return _refused(
            "Invalid enforcement_mode", field="enforcement_mode")

    tenant = db.query(Tenant).filter(Tenant.id == str(tenant_id)).first()
    if tenant is None:
        return _refused(
            f"Tenant not found: {tenant_id}", http_status=404,
            error_code="NOT_FOUND")

    if budget_limit_usd is None and enforcement_mode is None:
        row = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == str(tenant_id),
            TenantSetting.setting_key == "billing",
        ).first()
        try:
            billing = json.loads(
                (row.setting_value if row else None) or "{}")
        except (TypeError, ValueError):
            billing = {}
        if not isinstance(billing, dict):
            billing = {}
        return {
            "status": "no_change",
            "data": {"tenant_id": str(tenant_id), "billing": billing},
            "message": "No budget changes requested.",
            "operation_id": None,
            "audit_id": None,
            "verification": {"status": "no_change", "effect": "none"},
        }

    requested = {
        "budget_limit_usd": budget_limit_usd,
        "enforcement_mode": enforcement_mode,
    }
    request = {
        "kind": "budget_update", "tenant_id": str(tenant_id),
        "changes": requested,
    }
    material_digest = _fingerprint(
        "admin-material", actor_snapshot["id"], _canonical_json(request))

    existing = _existing_operation(db, operation_id)
    if existing is not None:
        metadata = existing.get("metadata") or {}
        result_digest = str(metadata.get("result_digest") or "")
        expected = _audit_expected(
            operation_id=operation_id, kind="budget_update",
            actor=actor_snapshot, scope=_TENANT_SCOPE,
            target_type="tenant_budget", target_id=str(tenant_id),
            material_digest=material_digest, result_digest=result_digest,
            tenant_id=str(tenant_id), event_type=AuditEventType.UPDATE.value,
            audit_action="tenant_budget_updated",
            resource=f"tenant:{tenant_id}:budget")
        current_setting = _read_budget_setting(db, tenant_id)
        target_verified = (
            current_setting is not None
            and _digest({"setting_value": current_setting}) == result_digest)
        replay = _replay(
            db, operation_id, expected, target_type="tenant_budget",
            target_id=str(tenant_id), target_verified=target_verified)
        if replay["status"] == "already_applied":
            try:
                replay_billing = json.loads(current_setting or "{}")
            except (TypeError, ValueError):
                replay_billing = {}
            if not isinstance(replay_billing, dict):
                replay_billing = {}
            replay["data"] = {
                "tenant_id": str(tenant_id),
                "billing": replay_billing,
            }
        return replay

    row = db.query(TenantSetting).filter(
        TenantSetting.tenant_id == str(tenant_id),
        TenantSetting.setting_key == "billing",
    ).first()
    current_value = None if row is None else str(row.setting_value or "")
    try:
        billing = json.loads(current_value or "{}")
    except (TypeError, ValueError):
        return _refused(
            "billing setting is unreadable; refresh before updating",
            http_status=409, error_code="STALE_TARGET")
    if not isinstance(billing, dict):
        return _refused(
            "billing setting is unreadable; refresh before updating",
            http_status=409, error_code="STALE_TARGET")
    new_billing = dict(billing)
    if budget_limit_usd is not None:
        new_billing["budget_limit_usd"] = float(budget_limit_usd)
    if enforcement_mode is not None:
        enforcement = new_billing.get("enforcement")
        if not isinstance(enforcement, dict):
            enforcement = {}
        enforcement["mode"] = enforcement_mode
        new_billing["enforcement"] = enforcement
    new_value = json.dumps(new_billing, sort_keys=True)
    result_digest = _digest({"setting_value": new_value})
    expected = _audit_expected(
        operation_id=operation_id, kind="budget_update",
        actor=actor_snapshot, scope=_TENANT_SCOPE,
        target_type="tenant_budget", target_id=str(tenant_id),
        material_digest=material_digest, result_digest=result_digest,
        tenant_id=str(tenant_id), event_type=AuditEventType.UPDATE.value,
        audit_action="tenant_budget_updated",
        resource=f"tenant:{tenant_id}:budget")

    if not _claim_actor(db, actor, required="workspace_admin"):
        db.rollback()
        return _conflict(
            "administrator authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    try:
        if row is not None:
            result = db.execute(
                update(TenantSetting)
                .where(
                    TenantSetting.id == row.id,
                    TenantSetting.tenant_id == str(tenant_id),
                    TenantSetting.setting_key == "billing",
                    TenantSetting.setting_value == current_value,
                )
                .values(setting_value=new_value))
            if result.rowcount != 1:
                db.rollback()
                return _conflict(
                    "tenant budget changed; refresh and retry",
                    code="STALE_TARGET")
        else:
            db.add(TenantSetting(
                tenant_id=str(tenant_id), setting_key="billing",
                setting_value=new_value))
            db.flush()
    except IntegrityError:
        db.rollback()
        return _conflict(
            "tenant budget changed; refresh and retry",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "admin budget update failed: operation_id=%s stage=update "
            "error_class=%s", operation_id, type(exc).__name__)
        return _conflict(
            "tenant budget update could not be applied",
            code="STALE_TARGET")

    audit_row = _audit_row(
        operation_id=operation_id, expected=expected, actor=actor,
        tenant_id=str(tenant_id),
        description=f"Tenant {tenant_id} budget updated")
    result = _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            _read_budget_setting(db, tenant_id) == new_value),
        target_type="tenant_budget", target_id=str(tenant_id),
        integrity_conflict=(
            "tenant budget changed; refresh and retry", "STALE_TARGET"))
    if result["status"] in ("verified", "already_applied"):
        result["data"] = {
            "tenant_id": str(tenant_id),
            "billing": new_billing,
        }
    return result
