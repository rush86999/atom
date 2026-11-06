"""Verified writes for the global community-skill registry.

Imported community skills are ``SkillExecution`` rows with
``skill_source="community"``. The legacy promote/delete service methods write
the ORM row unconditionally and have no receipt or replay binding. This module
keeps the global registry but makes the two review decisions exact-material
CAS operations with one same-transaction ``AuditLog`` receipt.

The review material includes the parsed skill body/packages held in
``input_params``. Only keyed digests of that material enter the receipt; raw
skill content never does.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.auth import SECRET_KEY
from core.models import (
    AuditEventType,
    AuditLog,
    SecurityLevel,
    SkillExecution,
    User,
)
from core.personal_scope import resolve_tenant_id

logger = logging.getLogger(__name__)

COMMUNITY_SOURCE = "community"
_PLATFORM_SCOPE = {
    "registry": "community",
    "tenant_id": "system",
    "workspace_id": "default",
}
_OPERATION_PREFIX = "community-skill"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_ACTION_PROMOTE = "community_skill_promoted"
_ACTION_DELETE = "community_skill_deleted"


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


def _digest(value: Any) -> str:
    return _fingerprint("community-skill-digest", value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _operation_id(action: str, supplied: Optional[str]) -> str:
    supplied = str(supplied or "").strip()
    prefix = f"{_OPERATION_PREFIX}:{action}:"
    candidate = supplied or f"{prefix}{uuid.uuid4().hex}"
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


def _conflict(message: str, *, code: str = "STALE_COMMUNITY_SKILL") -> Dict[str, Any]:
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
        "error_code": "COMMUNITY_SKILL_TRANSACTION_ROLLED_BACK",
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
            "The community-skill mutation committed but its audit/target "
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
            "The community-skill mutation may have committed, but "
            "confirmation was lost. Reconcile the original operation; do "
            "not repeat it blindly."),
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


def _fresh_session(db: Session) -> Session:
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=db.get_bind())()


def _actor_snapshot(actor: Any) -> Dict[str, Any]:
    return {
        "id": str(getattr(actor, "id", "") or ""),
        "email": str(getattr(actor, "email", "") or ""),
        "role": str(getattr(actor, "role", "") or ""),
        "tenant_id": str(resolve_tenant_id(actor)),
    }


def _target_digest(skill_id: str) -> str:
    return _fingerprint("community-skill-target", str(skill_id))


def _read_skill(db: Session, skill_id: str) -> Optional[Dict[str, Any]]:
    with _fresh_session(db) as fresh:
        row = fresh.query(SkillExecution).filter(
            SkillExecution.id == str(skill_id),
            SkillExecution.skill_source == COMMUNITY_SOURCE,
        ).first()
        if row is None:
            return None
        return {
            "id": str(row.id),
            "agent_id": str(row.agent_id or ""),
            "tenant_id": str(row.tenant_id or ""),
            "workspace_id": str(row.workspace_id or ""),
            "skill_id": str(row.skill_id or ""),
            "status": str(row.status or ""),
            "input_params": row.input_params if isinstance(
                row.input_params, dict) else {},
            "security_scan_result": row.security_scan_result if isinstance(
                row.security_scan_result, dict) else {},
            "sandbox_enabled": bool(row.sandbox_enabled),
            "skill_source": str(row.skill_source or ""),
        }


def _material(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "agent_id": row.get("agent_id"),
        "tenant_id": row.get("tenant_id"),
        "workspace_id": row.get("workspace_id"),
        "skill_id": row.get("skill_id"),
        "status": row.get("status"),
        "input_params": row.get("input_params") or {},
        "security_scan_result": row.get("security_scan_result") or {},
        "sandbox_enabled": bool(row.get("sandbox_enabled")),
        "skill_source": row.get("skill_source"),
    }


def _material_digest(row: Dict[str, Any]) -> str:
    return _digest(_canonical(_material(row)))


def _skill_name(row: Dict[str, Any]) -> str:
    params = row.get("input_params") or {}
    name = params.get("skill_name") if isinstance(params, dict) else None
    return str(name or "Unknown")


def _promote_data(row: Dict[str, Any], previous_status: str) -> Dict[str, Any]:
    return {
        "skill_id": row["id"],
        "skill_name": _skill_name(row),
        "status": "Active",
        "previous_status": previous_status,
        "message": f"Skill promoted from {previous_status} to Active",
    }


def _delete_data(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "skill_id": row["id"],
        "skill_name": _skill_name(row),
        "deleted": True,
        "message": f"Skill '{_skill_name(row)}' deleted successfully",
    }


def _audit_expected(
    *, operation_id: str, action: str, event_type: str,
    target_digest: str, material_digest: str, request_digest: str,
    prior_digest: str, result_digest: str, actor: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "operation_id": str(operation_id),
        "schema": "atom-community-skill-operation-1",
        "action": str(action),
        "event_type": str(event_type),
        "target_digest": str(target_digest),
        "material_digest": str(material_digest),
        "request_digest": str(request_digest),
        "prior_digest": str(prior_digest),
        "result_digest": str(result_digest),
        "actor_id": actor["id"],
        "actor_role": actor["role"],
        "tenant_id": None,
        "workspace_id": None,
        "scope_json": _canonical(_PLATFORM_SCOPE),
        "resource": f"community-skill:{target_digest}",
    }


def _audit_row(*, expected: Dict[str, Any], actor: Dict[str, Any]) -> AuditLog:
    metadata = {
        "schema": expected["schema"],
        "operation_id": expected["operation_id"],
        "action": expected["action"],
        "event_type": expected["event_type"],
        "target_digest": expected["target_digest"],
        "material_digest": expected["material_digest"],
        "request_digest": expected["request_digest"],
        "prior_digest": expected["prior_digest"],
        "result_digest": expected["result_digest"],
        "actor_id": expected["actor_id"],
        "actor_role": expected["actor_role"],
        "scope_json": expected["scope_json"],
    }
    return AuditLog(
        id=expected["operation_id"],
        event_type=expected["event_type"],
        security_level=SecurityLevel.HIGH.value,
        threat_level="none",
        user_id=expected["actor_id"],
        user_email=actor["email"],
        tenant_id=None,
        workspace_id=None,
        resource=expected["resource"],
        action=expected["action"],
        description="Community skill review decision recorded",
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
            if row.tenant_id is not None or row.workspace_id is not None:
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
            for key in (
                "schema", "operation_id", "action", "event_type",
                "target_digest", "material_digest", "request_digest",
                "prior_digest", "result_digest", "actor_id", "actor_role",
                "scope_json",
            ):
                if key not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                if not isinstance(metadata[key], str):
                    return {"status": "refuted", "audit_id": audit_id}
                if metadata[key] != expected[key]:
                    return {"status": "refuted", "audit_id": audit_id}
            if metadata.get("scope_json") != _canonical(_PLATFORM_SCOPE):
                return {"status": "refuted", "audit_id": audit_id}
            return {"status": "verified", "audit_id": audit_id}
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "community-skill audit read-back failed: operation_id=%s "
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
        "target_digest": metadata.get("target_digest"),
        "material_digest": metadata.get("material_digest"),
        "request_digest": metadata.get("request_digest"),
        "prior_digest": metadata.get("prior_digest"),
        "result_digest": metadata.get("result_digest"),
        "actor_id": metadata.get("actor_id"),
        "actor_role": metadata.get("actor_role"),
        "scope_json": metadata.get("scope_json"),
        "resource": f"community-skill:{metadata.get('target_digest')}",
    }


def _replay(
    db: Session, operation_id: str, expected: Dict[str, Any],
    *, target_check,
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
                    target_id=str(expected.get("target_digest") or ""))
            if (
                metadata.get("schema") != expected["schema"]
                or metadata.get("action") != expected["action"]
                or metadata.get("event_type") != expected["event_type"]
                or metadata.get("target_digest") != expected["target_digest"]
                or metadata.get("request_digest") != expected["request_digest"]
                or metadata.get("actor_id") != expected["actor_id"]
            ):
                return _conflict(
                    "operation_id is bound to a different community-skill request",
                    code="OPERATION_CONFLICT")
            audit_expected = _expected_from_metadata(
                metadata, operation_id=operation_id)
            audit_state = _verify_audit(db, audit_expected)
            try:
                target_ok = bool(target_check(audit_expected))
            except Exception:  # noqa: BLE001
                target_ok = False
            if audit_state["status"] == "verified" and not target_ok:
                audit_state = {
                    "status": "refuted",
                    "audit_id": audit_expected["operation_id"],
                }
            if audit_state["status"] == "verified" and target_ok:
                return {
                    "status": "already_applied",
                    "data": None,
                    "message": "This community-skill operation was already applied.",
                    "operation_id": operation_id,
                    "audit_id": audit_expected["operation_id"],
                    "target_id": audit_expected["target_digest"],
                }
            return _committed_unverified(
                operation_id, audit_state,
                target_id=audit_expected["target_digest"])
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "community-skill replay read failed: operation_id=%s "
            "error_class=%s", operation_id, type(exc).__name__)
        return _committed_unverified(
            operation_id, {"status": "unavailable"},
            target_id=str(expected.get("target_digest") or ""))


def _commit_and_verify(
    db: Session, *, expected: Dict[str, Any], audit_row: AuditLog,
    target_check, success_data: Dict[str, Any],
) -> Dict[str, Any]:
    operation_id = expected["operation_id"]
    target_id = expected["target_digest"]
    try:
        db.add(audit_row)
        db.commit()
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected, target_check=target_check)
        if replay is not None:
            return replay
        return _not_applied(
            "The community-skill write was rolled back; no effect was applied")
    except Exception as exc:  # noqa: BLE001 — commit outcome unknown
        db.rollback()
        logger.error(
            "community-skill write outcome unknown: operation_id=%s "
            "target=%s error_class=%s", operation_id, target_id,
            type(exc).__name__)
        return _effect_unknown(operation_id, target_id)

    audit_state = _verify_audit(db, expected)
    try:
        target_ok = bool(target_check(expected))
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
            "message": "Community-skill operation committed and verified.",
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": target_id,
        }
    return _committed_unverified(
        operation_id, audit_state, target_id=target_id)


def promote_skill(
    db: Session, *, actor: Any, skill_id: str,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    skill_id = str(skill_id or "").strip()
    if not skill_id:
        return _refused("skill_id must be non-empty", field="skill_id")
    actor_snapshot = _actor_snapshot(actor)
    if not actor_snapshot["id"]:
        return _refused(
            "Authentication required", http_status=401,
            error_code="UNAUTHENTICATED")
    try:
        operation_id = _operation_id("promote", operation_id)
    except ValueError as exc:
        return _refused(str(exc), field="operation_id")

    target = _target_digest(skill_id)
    request_digest = _fingerprint(
        "community-skill-request", "promote", skill_id)
    expected_base = _audit_expected(
        operation_id=operation_id, action=_ACTION_PROMOTE,
        event_type=AuditEventType.UPDATE.value, target_digest=target,
        material_digest="", request_digest=request_digest,
        prior_digest="", result_digest="", actor=actor_snapshot)

    def target_check(expected: Dict[str, Any]) -> bool:
        row = _read_skill(db, skill_id)
        if row is None or row["status"] != "Active":
            return False
        return _digest(_canonical(_material(row))) == expected["result_digest"]

    replay = _replay(
        db, operation_id, expected_base, target_check=target_check)
    if replay is not None:
        if replay["status"] == "already_applied":
            row = _read_skill(db, skill_id)
            if row is not None:
                replay["data"] = _with_receipt(
                    _promote_data(row, "Active"),
                    operation_id=operation_id,
                    audit_id=replay.get("audit_id"),
                    verification_status="already_applied",
                    replay="do_not_repeat")
        return replay

    current = _read_skill(db, skill_id)
    if current is None:
        return _refused(
            f"Community skill not found: {skill_id}", http_status=404,
            error_code="NOT_FOUND")
    prior_material = _material(current)
    prior_digest = _digest(_canonical(prior_material))
    expected_base["material_digest"] = prior_digest
    expected_base["prior_digest"] = prior_digest

    if current["status"] == "Active":
        return {
            "status": "already_applied",
            "data": _with_receipt(
                _promote_data(current, "Active"),
                operation_id=operation_id, audit_id=None,
                verification_status="already_applied", effect="none",
                replay="none"),
            "message": "Skill is already Active",
            "operation_id": operation_id,
            "audit_id": None,
            "target_id": target,
        }
    if current["status"] != "Untrusted":
        return _conflict(
            "community skill is not in a promotable state; refresh and retry")

    result_material = dict(current)
    result_material["status"] = "Active"
    result_digest = _digest(_canonical(_material(result_material)))
    expected = dict(expected_base)
    expected["result_digest"] = result_digest

    try:
        updated = db.execute(
            update(SkillExecution)
            .where(
                SkillExecution.id == skill_id,
                SkillExecution.skill_source == COMMUNITY_SOURCE,
                SkillExecution.status == current["status"],
                SkillExecution.input_params == current["input_params"],
                SkillExecution.security_scan_result == current[
                    "security_scan_result"],
                SkillExecution.sandbox_enabled == current["sandbox_enabled"],
            )
            .values(status="Active"))
        if updated.rowcount != 1:
            db.rollback()
            return _conflict(
                "community skill changed; refresh and retry")
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected_base, target_check=target_check)
        return replay or _conflict(
            "community skill changed; refresh and retry")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "community-skill promote failed before commit: operation_id=%s "
            "target=%s error_class=%s", operation_id, target,
            type(exc).__name__)
        return _not_applied(
            "The community skill could not be promoted; no effect was committed")

    audit_row = _audit_row(expected=expected, actor=actor_snapshot)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=target_check,
        success_data=_promote_data(result_material, current["status"]))


def delete_skill(
    db: Session, *, actor: Any, skill_id: str,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    skill_id = str(skill_id or "").strip()
    if not skill_id:
        return _refused("skill_id must be non-empty", field="skill_id")
    actor_snapshot = _actor_snapshot(actor)
    if not actor_snapshot["id"]:
        return _refused(
            "Authentication required", http_status=401,
            error_code="UNAUTHENTICATED")
    try:
        operation_id = _operation_id("delete", operation_id)
    except ValueError as exc:
        return _refused(str(exc), field="operation_id")

    target = _target_digest(skill_id)
    request_digest = _fingerprint(
        "community-skill-request", "delete", skill_id)
    expected_base = _audit_expected(
        operation_id=operation_id, action=_ACTION_DELETE,
        event_type=AuditEventType.DELETE.value, target_digest=target,
        material_digest="", request_digest=request_digest,
        prior_digest="", result_digest="", actor=actor_snapshot)

    def target_check(_expected: Dict[str, Any]) -> bool:
        return _read_skill(db, skill_id) is None

    replay = _replay(
        db, operation_id, expected_base, target_check=target_check)
    if replay is not None:
        if replay["status"] == "already_applied":
            row = _read_skill(db, skill_id)
            data = _delete_data(row) if row is not None else {
                "skill_id": skill_id, "deleted": True,
                "message": "Skill already deleted",
            }
            replay["data"] = _with_receipt(
                data, operation_id=operation_id,
                audit_id=replay.get("audit_id"),
                verification_status="already_applied",
                replay="do_not_repeat")
        return replay

    current = _read_skill(db, skill_id)
    if current is None:
        return _refused(
            f"Community skill not found: {skill_id}", http_status=404,
            error_code="NOT_FOUND")
    prior_digest = _digest(_canonical(_material(current)))
    deleted_digest = _fingerprint(
        "community-skill-deleted", target, prior_digest)
    expected_base["material_digest"] = prior_digest
    expected_base["prior_digest"] = prior_digest
    expected_base["result_digest"] = deleted_digest

    try:
        deleted = db.execute(
            delete(SkillExecution)
            .where(
                SkillExecution.id == skill_id,
                SkillExecution.skill_source == COMMUNITY_SOURCE,
                SkillExecution.status == current["status"],
                SkillExecution.input_params == current["input_params"],
                SkillExecution.security_scan_result == current[
                    "security_scan_result"],
                SkillExecution.sandbox_enabled == current["sandbox_enabled"],
            ))
        if deleted.rowcount != 1:
            db.rollback()
            return _conflict(
                "community skill changed; refresh and retry")
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected_base, target_check=target_check)
        return replay or _conflict(
            "community skill changed; refresh and retry")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "community-skill delete failed before commit: operation_id=%s "
            "target=%s error_class=%s", operation_id, target,
            type(exc).__name__)
        return _not_applied(
            "The community skill could not be deleted; no effect was committed")

    audit_row = _audit_row(expected=expected_base, actor=actor_snapshot)
    return _commit_and_verify(
        db, expected=expected_base, audit_row=audit_row,
        target_check=target_check,
        success_data=_delete_data(current))
