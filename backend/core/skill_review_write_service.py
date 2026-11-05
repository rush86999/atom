"""Verified TEAM_LEAD+ decisions for community skills.

The two community-skill routes previously called ``SkillRegistryService``
directly: any authenticated caller could promote or delete any
``SkillExecution`` row with ``skill_source="community"``, with no role check,
material binding or audit receipt.

This module makes the decision explicit and durable:

- TEAM_LEAD+ actor authority is frozen and conditionally claimed;
- the exact community `SkillExecution` material is bound by a guarded UPDATE
  or DELETE (id, status, source, target skill id, row scope and the JSON
  input/scan payload, plus sandbox flag);
- one safe ``AuditLog`` receipt commits in the same transaction;
- same-operation replay is idempotent, changed material conflicts, a later
  revision is unverified, a confirmed rollback is ``effect=none`` and a lost
  confirmation is ``effect_unknown``.

No raw skill body, generated code, package list or scan payload is stored in
the receipt or returned in logs. Cloud execution rows are never visible to
these decisions.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from typing import Any, Callable, Dict, Optional

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
    UserRole,
)
from core.personal_scope import resolve_tenant_id
from core.security.rbac import role_level

logger = logging.getLogger(__name__)

REVIEW_SCHEMA = "atom-community-skill-review-1"
_OPERATION_PREFIX = "skill"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_ACTION_PROMOTE = "community_skill_promoted"
_ACTION_DELETE = "community_skill_deleted"
_SOURCE = "community"
_ACTIVE = "Active"
_UNTRUSTED = "Untrusted"


# ---------------------------------------------------------------------------
# Safe envelopes
# ---------------------------------------------------------------------------

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
    message: str, *, http_status: int = 409,
    error_code: str = "CONFLICT", field: Optional[str] = None,
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
        "error_code": "SKILL_TRANSACTION_ROLLED_BACK",
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
            "The community-skill decision committed but its audit/target "
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
            "The community-skill decision may have committed, but "
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


# ---------------------------------------------------------------------------
# Sessions / actor / material
# ---------------------------------------------------------------------------

def _fresh_session(db: Session) -> Session:
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=db.get_bind())()


def _actor_refusal(actor: Dict[str, Any]) -> Dict[str, Any]:
    return _refused(
        str(actor.get("message") or "TEAM_LEAD+ reviewer authority is required"),
        http_status=int(actor.get("http_status") or 403),
        error_code=str(actor.get("error_code") or "AUTHORITY_REQUIRED"),
    )


def _resolve_actor(db: Session, actor: Any) -> Dict[str, Any]:
    """Resolve the authoritative User row before any decision.

    The request-entry User object is a snapshot. A concurrent deactivation,
    demotion or tenant reassignment must not let a decision commit under stale
    authority. The frozen status/is_active/role/raw tenant are later bound in
    the guarded no-op UPDATE in the same transaction as the target CAS.
    """
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
                    "message": "TEAM_LEAD+ reviewer authority is required",
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
            }
    except Exception as exc:  # noqa: BLE001 — unreadable authority fails closed
        logger.warning(
            "community-skill authority read failed: actor=%s error_class=%s",
            actor_id, type(exc).__name__)
        return {
            "ok": False, "http_status": 503,
            "error_code": "AUTHORITY_UNAVAILABLE",
            "message": "Authorization could not be confirmed; retry",
        }


def _claim_actor(db: Session, actor: Dict[str, Any]) -> bool:
    """Bind the frozen principal in the decision transaction.

    A zero-match means the User row was deactivated, demoted or moved after the
    service resolved it. The caller rolls back all attempted target/audit work.
    """
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


def _load_skill(
    db: Session, skill_id: str,
) -> Optional[SkillExecution]:
    with _fresh_session(db) as fresh:
        return fresh.query(SkillExecution).filter(
            SkillExecution.id == str(skill_id),
            SkillExecution.skill_source == _SOURCE,
        ).populate_existing().first()


def _skill_name(row: SkillExecution) -> str:
    params = row.input_params if isinstance(row.input_params, dict) else {}
    return str(params.get("skill_name") or "Unknown")


def _request_material(row: SkillExecution) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "skill_source": str(row.skill_source or ""),
        "target_skill_id": str(row.skill_id or ""),
        "row_tenant_id": str(row.tenant_id or ""),
        "row_agent_id": str(row.agent_id or ""),
        "row_workspace_id": (
            None if row.workspace_id is None else str(row.workspace_id)),
        "input_digest": _fingerprint(
            "skill-input", _canonical(row.input_params or {})),
        "scan_digest": _fingerprint(
            "skill-scan", _canonical(row.security_scan_result or {})),
        "sandbox_enabled": bool(row.sandbox_enabled),
    }


def _request_digest(action: str, material: Dict[str, Any]) -> str:
    return _fingerprint(
        "skill-request", str(action), _canonical(material))


def _state_digest(material: Dict[str, Any], status: str) -> str:
    return _fingerprint(
        "skill-state", str(status), _canonical(material))


def _exact(column, value: Any):
    if value is None:
        return column.is_(None)
    return column == value


def _row_predicates(row: SkillExecution, prior_status: str):
    return [
        SkillExecution.id == str(row.id),
        SkillExecution.skill_source == _SOURCE,
        SkillExecution.status == str(prior_status),
        SkillExecution.skill_id == str(row.skill_id),
        SkillExecution.tenant_id == str(row.tenant_id),
        SkillExecution.agent_id == str(row.agent_id),
        _exact(SkillExecution.workspace_id, row.workspace_id),
        SkillExecution.input_params == row.input_params,
        SkillExecution.security_scan_result == row.security_scan_result,
        _exact(SkillExecution.sandbox_enabled, row.sandbox_enabled),
    ]


# ---------------------------------------------------------------------------
# Audit ledger
# ---------------------------------------------------------------------------

def _audit_expected(
    *, operation_id: str, action: str, event_type: str,
    row: SkillExecution, prior_status: str, result_status: str,
    request_digest: str, prior_digest: str, result_digest: str,
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "operation_id": str(operation_id),
        "schema": REVIEW_SCHEMA,
        "action": str(action),
        "event_type": str(event_type),
        "target_id": str(row.id),
        "target_skill_id": str(row.skill_id or ""),
        "target_tenant_id": str(row.tenant_id or ""),
        "row_agent_id": str(row.agent_id or ""),
        "row_workspace_id": (
            None if row.workspace_id is None else str(row.workspace_id)),
        "skill_name": _skill_name(row),
        "prior_status": str(prior_status),
        "result_status": str(result_status),
        "request_digest": str(request_digest),
        "prior_digest": str(prior_digest),
        "result_digest": str(result_digest),
        "actor_id": actor["id"],
        "actor_role": actor["role"],
        "tenant_id": actor["tenant_id"],
        "resource": f"community_skill:{row.id}",
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
        "target_skill_id": expected["target_skill_id"],
        "target_tenant_id": expected["target_tenant_id"],
        "row_agent_id": expected["row_agent_id"],
        "row_workspace_id": expected["row_workspace_id"],
        "skill_name": expected["skill_name"],
        "prior_status": expected["prior_status"],
        "result_status": expected["result_status"],
        "request_digest": expected["request_digest"],
        "prior_digest": expected["prior_digest"],
        "result_digest": expected["result_digest"],
        "actor_id": expected["actor_id"],
        "actor_role": expected["actor_role"],
        "tenant_id": expected["tenant_id"],
    }
    return AuditLog(
        id=expected["operation_id"],
        event_type=expected["event_type"],
        security_level=SecurityLevel.HIGH.value,
        threat_level="none",
        user_id=actor["id"],
        user_email=actor["email"],
        tenant_id=expected["tenant_id"],
        workspace_id=None,
        resource=expected["resource"],
        action=expected["action"],
        description="Community skill review recorded",
        metadata_json=json.dumps(metadata, sort_keys=True),
        success=True,
    )


def _verify_audit(
    db: Session, expected: Dict[str, Any],
) -> Dict[str, Any]:
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
            if row.workspace_id is not None:
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
                "target_id", "target_skill_id", "target_tenant_id",
                "row_agent_id", "skill_name", "prior_status",
                "result_status", "request_digest", "prior_digest",
                "result_digest", "actor_id", "actor_role", "tenant_id",
            )
            for key in string_fields:
                if key not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                if not isinstance(metadata[key], str):
                    return {"status": "refuted", "audit_id": audit_id}
                if metadata[key] != expected[key]:
                    return {"status": "refuted", "audit_id": audit_id}
            if "row_workspace_id" not in metadata:
                return {"status": "unavailable", "audit_id": audit_id}
            workspace = metadata["row_workspace_id"]
            if workspace is not None and not isinstance(workspace, str):
                return {"status": "refuted", "audit_id": audit_id}
            if workspace != expected["row_workspace_id"]:
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
        "target_id": metadata.get("target_id"),
        "target_skill_id": metadata.get("target_skill_id"),
        "target_tenant_id": metadata.get("target_tenant_id"),
        "row_agent_id": metadata.get("row_agent_id"),
        "row_workspace_id": metadata.get("row_workspace_id"),
        "skill_name": metadata.get("skill_name"),
        "prior_status": metadata.get("prior_status"),
        "result_status": metadata.get("result_status"),
        "request_digest": metadata.get("request_digest"),
        "prior_digest": metadata.get("prior_digest"),
        "result_digest": metadata.get("result_digest"),
        "actor_id": metadata.get("actor_id"),
        "actor_role": metadata.get("actor_role"),
        "tenant_id": metadata.get("tenant_id"),
        "resource": f"community_skill:{metadata.get('target_id')}",
    }


def _replay(
    db: Session, operation_id: str, expected: Dict[str, Any],
    *, action: str, compare_request: bool = True,
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
            if (
                metadata.get("schema") != expected["schema"]
                or metadata.get("action") != expected["action"]
                or metadata.get("event_type") != expected["event_type"]
                or metadata.get("target_id") != expected["target_id"]
                or metadata.get("actor_id") != expected["actor_id"]
            ):
                return _conflict(
                    "operation_id is bound to a different skill decision",
                    code="OPERATION_CONFLICT")
            if compare_request and (
                metadata.get("target_skill_id")
                != expected["target_skill_id"]
                or metadata.get("request_digest")
                != expected["request_digest"]
            ):
                return _conflict(
                    "operation_id is bound to a different skill decision",
                    code="OPERATION_CONFLICT")
            audit_expected = _expected_from_metadata(
                metadata, operation_id=operation_id)
            audit_state = _verify_audit(db, audit_expected)
            current = _load_skill(db, str(metadata.get("target_id") or ""))
            if action == _ACTION_DELETE:
                target_ok = current is None
                data = {"skill_id": audit_expected["target_id"],
                        "deleted": True,
                        "skill_name": audit_expected["skill_name"]}
            else:
                target_ok = (
                    current is not None
                    and str(current.status or "") == _ACTIVE
                    and _state_digest(
                        _request_material(current), _ACTIVE)
                    == audit_expected["result_digest"]
                )
                data = {
                    "status": _ACTIVE,
                    "previous_status": audit_expected["prior_status"],
                    "skill_id": audit_expected["target_id"],
                    "skill_name": audit_expected["skill_name"],
                }
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
                    "message": "This community-skill decision was already applied.",
                    "operation_id": operation_id,
                    "audit_id": audit_expected["operation_id"],
                    "target_id": audit_expected["target_id"],
                }
            return _committed_unverified(
                operation_id, audit_state,
                target_id=audit_expected["target_id"])
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "community-skill replay read failed: operation_id=%s "
            "error_class=%s", operation_id, type(exc).__name__)
        return _committed_unverified(
            operation_id, {"status": "unavailable"},
            target_id=str(expected.get("target_id") or ""))


def _commit_and_verify(
    db: Session, *, expected: Dict[str, Any], audit_row: AuditLog,
    target_check: Callable[[], bool],
    success_data: Dict[str, Any],
) -> Dict[str, Any]:
    operation_id = expected["operation_id"]
    target_id = expected["target_id"]
    try:
        db.add(audit_row)
        db.commit()
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected, action=expected["action"])
        if replay is not None:
            return replay
        return _not_applied(
            "The community-skill decision was rolled back; no effect was "
            "applied")
    except Exception as exc:  # noqa: BLE001 — commit outcome unknown
        db.rollback()
        logger.error(
            "community-skill decision outcome unknown: operation_id=%s "
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
            "message": "Community-skill decision committed and verified.",
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": target_id,
        }
    return _committed_unverified(
        operation_id, audit_state, target_id=target_id)


# ---------------------------------------------------------------------------
# Public decisions
# ---------------------------------------------------------------------------

def promote_community_skill(
    db: Session, *, actor: Any, skill_id: str,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    skill_id = str(skill_id or "").strip()
    if not skill_id:
        return _refused("skill_id must be non-empty", field="skill_id")
    actor_snapshot = _resolve_actor(db, actor)
    if not actor_snapshot.get("ok"):
        return _actor_refusal(actor_snapshot)
    try:
        operation_id = _operation_id("promote", operation_id)
    except ValueError as exc:
        return _refused(str(exc), field="operation_id")

    row = _load_skill(db, skill_id)
    if row is None:
        replay = _replay(
            db, operation_id,
            {
                "schema": REVIEW_SCHEMA,
                "action": _ACTION_PROMOTE,
                "event_type": AuditEventType.UPDATE.value,
                "target_id": skill_id,
                "actor_id": actor_snapshot["id"],
                "target_skill_id": "",
                "request_digest": "",
            },
            action=_ACTION_PROMOTE, compare_request=False)
        if replay is not None:
            return replay
        return _refused(
            f"Community skill not found: {skill_id}", http_status=404,
            error_code="NOT_FOUND")

    prior_status = str(row.status or "")
    request_material = _request_material(row)
    request_digest = _request_digest(_ACTION_PROMOTE, request_material)
    expected_base = _audit_expected(
        operation_id=operation_id, action=_ACTION_PROMOTE,
        event_type=AuditEventType.UPDATE.value, row=row,
        prior_status=prior_status, result_status=_ACTIVE,
        request_digest=request_digest, prior_digest="", result_digest="",
        actor=actor_snapshot)

    replay = _replay(
        db, operation_id, expected_base, action=_ACTION_PROMOTE)
    if replay is not None:
        return replay

    if prior_status == _ACTIVE:
        return {
            "status": "no_change",
            "data": {
                "status": _ACTIVE,
                "previous_status": _ACTIVE,
                "skill_id": str(row.id),
                "skill_name": _skill_name(row),
                "verification": {
                    "status": "no_change",
                    "effect": "none",
                },
            },
            "message": "Skill is already Active",
        }
    if prior_status != _UNTRUSTED:
        return _refused(
            f"community skill status {prior_status!r} cannot be promoted",
            http_status=409, error_code="UNSUPPORTED_STATUS",
            field="status")

    prior_digest = _state_digest(request_material, prior_status)
    result_digest = _state_digest(request_material, _ACTIVE)
    expected = dict(expected_base)
    expected["prior_digest"] = prior_digest
    expected["result_digest"] = result_digest

    if not _claim_actor(db, actor_snapshot):
        db.rollback()
        return _conflict(
            "reviewer authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    try:
        updated = db.execute(
            update(SkillExecution)
            .where(*_row_predicates(row, prior_status))
            .values(status=_ACTIVE))
        if updated.rowcount != 1:
            db.rollback()
            now = _load_skill(db, skill_id)
            if now is not None and str(now.status or "") == _ACTIVE:
                return _conflict(
                    "community skill is already Active",
                    code="ALREADY_PROMOTED")
            return _conflict(
                "community skill material changed; refresh and retry",
                code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected_base, action=_ACTION_PROMOTE)
        return replay or _conflict(
            "community skill decision conflicts with current state",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "community-skill promote failed before commit: operation_id=%s "
            "target=%s error_class=%s",
            operation_id, row.id, type(exc).__name__)
        return _not_applied(
            "The community skill could not be promoted; no effect was "
            "committed")

    audit_row = _audit_row(expected=expected, actor=actor_snapshot)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (now := _load_skill(db, skill_id)) is not None
            and str(now.status or "") == _ACTIVE
            and _state_digest(_request_material(now), _ACTIVE)
            == result_digest),
        success_data={
            "status": _ACTIVE,
            "previous_status": prior_status,
            "skill_id": str(row.id),
            "skill_name": _skill_name(row),
        })


def delete_community_skill(
    db: Session, *, actor: Any, skill_id: str,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    skill_id = str(skill_id or "").strip()
    if not skill_id:
        return _refused("skill_id must be non-empty", field="skill_id")
    actor_snapshot = _resolve_actor(db, actor)
    if not actor_snapshot.get("ok"):
        return _actor_refusal(actor_snapshot)
    try:
        operation_id = _operation_id("delete", operation_id)
    except ValueError as exc:
        return _refused(str(exc), field="operation_id")

    row = _load_skill(db, skill_id)
    if row is None:
        replay = _replay(
            db, operation_id,
            {
                "schema": REVIEW_SCHEMA,
                "action": _ACTION_DELETE,
                "event_type": AuditEventType.DELETE.value,
                "target_id": skill_id,
                "actor_id": actor_snapshot["id"],
                "target_skill_id": "",
                "request_digest": "",
            },
            action=_ACTION_DELETE, compare_request=False)
        if replay is not None:
            return replay
        return _refused(
            f"Community skill not found: {skill_id}", http_status=404,
            error_code="NOT_FOUND")

    prior_status = str(row.status or "")
    request_material = _request_material(row)
    request_digest = _request_digest(_ACTION_DELETE, request_material)
    prior_digest = _state_digest(request_material, prior_status)
    deleted_digest = _fingerprint(
        "skill-deleted", request_digest, prior_digest)
    expected_base = _audit_expected(
        operation_id=operation_id, action=_ACTION_DELETE,
        event_type=AuditEventType.DELETE.value, row=row,
        prior_status=prior_status, result_status="deleted",
        request_digest=request_digest, prior_digest=prior_digest,
        result_digest=deleted_digest, actor=actor_snapshot)

    replay = _replay(
        db, operation_id, expected_base, action=_ACTION_DELETE)
    if replay is not None:
        return replay

    if not _claim_actor(db, actor_snapshot):
        db.rollback()
        return _conflict(
            "reviewer authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    try:
        deleted = db.execute(
            delete(SkillExecution)
            .where(*_row_predicates(row, prior_status)))
        if deleted.rowcount != 1:
            db.rollback()
            return _conflict(
                "community skill material changed; refresh and retry",
                code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        return _conflict(
            "community skill could not be deleted; refresh and retry",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "community-skill delete failed before commit: operation_id=%s "
            "target=%s error_class=%s",
            operation_id, row.id, type(exc).__name__)
        return _not_applied(
            "The community skill could not be deleted; no effect was "
            "committed")

    audit_row = _audit_row(expected=expected_base, actor=actor_snapshot)
    return _commit_and_verify(
        db, expected=expected_base, audit_row=audit_row,
        target_check=lambda: _load_skill(db, skill_id) is None,
        success_data={
            "skill_id": str(row.id),
            "deleted": True,
            "skill_name": _skill_name(row),
        })
