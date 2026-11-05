"""Reviewed tool-mutation decisions with durable material binding.

The Auto-Dev review surface already exposes pending Memento skill candidates and
AlphaEvolver tool mutations. Skill candidates use the reviewed-improvement
contract; tool mutations previously had a direct, unconditional status write.
This module gives the two tool-mutation decision routes the same local safety
properties without adding a second review engine:

- TEAM_LEAD+ tenant-scoped authority is frozen and conditionally claimed;
- the exact mutation material (tool, lineage, code, prior sandbox status and
  execution error) is bound by a guarded UPDATE;
- the decision and a safe AuditLog receipt commit atomically;
- same-operation replay is idempotent, changed material conflicts, later material
  changes are unverified, a confirmed local rollback is ``effect=none`` and a
  genuinely lost confirmation is ``effect_unknown``;
- the parallel sandbox writer may only advance ``pending``/``failed`` and can
  never overwrite an approved/rejected decision.

No raw mutated code, execution-error text, SQL parameters or exception messages
are stored in the receipt or returned in responses/logs.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.auto_dev.models import ToolMutation
from core.auth import SECRET_KEY
from core.models import (
    AuditEventType,
    AuditLog,
    SecurityLevel,
    User,
    UserRole,
)
from core.security.rbac import role_level

logger = logging.getLogger(__name__)

REVIEW_SCHEMA = "atom-tool-mutation-review-1"
_OPERATION_PREFIX = "autodev:tool-mutation"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")

_APPROVE = "approved"
_REJECT = "rejected"
_DECISIONS = {_APPROVE, _REJECT}
_AUDIT_ACTIONS = {
    _APPROVE: "tool_mutation_approved",
    _REJECT: "tool_mutation_rejected",
}
_APPROVE_PRIOR = ("pending", "passed")
_REJECT_PRIOR = ("pending", "passed", "failed")


# ---------------------------------------------------------------------------
# Safe material and result envelopes
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


def _new_operation_id(supplied: Optional[str]) -> str:
    supplied = str(supplied or "").strip()
    candidate = supplied or f"{_OPERATION_PREFIX}:{uuid.uuid4().hex}"
    if not candidate.startswith(f"{_OPERATION_PREFIX}:"):
        candidate = f"{_OPERATION_PREFIX}:{candidate}"
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
        "error_code": "TOOL_MUTATION_TRANSACTION_ROLLED_BACK",
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
            "The tool-mutation decision committed but its audit/target "
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
            "The tool-mutation decision may have committed, but confirmation "
            "was lost. Reconcile the original operation; do not decide again "
            "blindly."),
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


# ---------------------------------------------------------------------------
# Authority and material
# ---------------------------------------------------------------------------

def _actor_snapshot(actor: User) -> Dict[str, Any]:
    return {
        "id": str(actor.id),
        "email": str(actor.email or ""),
        "role": str(actor.role or ""),
        "status": str(actor.status or ""),
        "is_active": bool(actor.is_active),
        "tenant_id": (
            None if actor.tenant_id is None else str(actor.tenant_id)),
    }


def _actor_authorized(actor: Dict[str, Any], tenant_id: str) -> bool:
    if not actor["is_active"] or actor["status"].strip().lower() != "active":
        return False
    if role_level(actor["role"]) < role_level(UserRole.TEAM_LEAD):
        return False
    if actor["tenant_id"] and str(actor["tenant_id"]) != str(tenant_id):
        return False
    return True


def _actor_predicates(actor: Dict[str, Any]):
    allowed = [
        role.value for role in UserRole
        if role_level(role) >= role_level(UserRole.TEAM_LEAD)
    ]
    return [
        User.id == actor["id"],
        User.is_active.is_(True),
        User.status == "active",
        User.role.in_(allowed),
        _exact_nullable(User.tenant_id, actor["tenant_id"]),
    ]


def _claim_actor(db: Session, actor: Dict[str, Any]) -> bool:
    """Lock the actor row and require current TEAM_LEAD+ active authority."""
    result = db.execute(
        update(User)
        .where(*_actor_predicates(actor))
        .values(updated_at=User.updated_at)
    )
    return result.rowcount == 1


def _code_digest(code: str) -> str:
    return _fingerprint("tool-mutation-code", code or "")


def _error_digest(error: Optional[str]) -> str:
    return _fingerprint("tool-mutation-error", error or "")


def _material(
    *,
    mutation_id: str,
    tenant_id: str,
    tool_name: str,
    parent_tool_id: Optional[str],
    code: str,
    execution_error: Optional[str],
    prior_status: str,
    decision: str,
) -> Dict[str, Any]:
    return {
        "schema": REVIEW_SCHEMA,
        "mutation_id": str(mutation_id),
        "tenant_id": str(tenant_id),
        "tool_name": str(tool_name or ""),
        "parent_tool_id": (
            None if parent_tool_id is None else str(parent_tool_id)),
        "code_digest": _code_digest(code),
        "error_digest": _error_digest(execution_error),
        "prior_status": str(prior_status),
        "decision": str(decision),
    }


def _material_from_row(
    row: ToolMutation, *, prior_status: str, decision: str,
) -> Dict[str, Any]:
    return _material(
        mutation_id=str(row.id),
        tenant_id=str(row.tenant_id),
        tool_name=str(row.tool_name or ""),
        parent_tool_id=row.parent_tool_id,
        code=str(row.mutated_code or ""),
        execution_error=row.execution_error,
        prior_status=prior_status,
        decision=decision,
    )


def _material_digest(material: Dict[str, Any]) -> str:
    return _fingerprint("tool-mutation-material", _canonical(material))


def _result_digest(
    mutation_id: str, decision: str, material_digest: str,
) -> str:
    return _fingerprint(
        "tool-mutation-result", mutation_id, decision, material_digest)


def _audit_expected(
    *, operation_id: str, decision: str, prior_status: str,
    actor: Dict[str, Any], tenant_id: str, material: Dict[str, Any],
    material_digest: str, result_digest: str,
) -> Dict[str, Any]:
    return {
        "operation_id": str(operation_id),
        "schema": REVIEW_SCHEMA,
        "decision": str(decision),
        "prior_status": str(prior_status),
        "result_status": str(decision),
        "target_id": str(material["mutation_id"]),
        "tenant_id": str(tenant_id),
        "actor_id": actor["id"],
        "actor_role": actor["role"],
        "tool_name": material["tool_name"],
        "parent_tool_id": material["parent_tool_id"],
        "code_digest": material["code_digest"],
        "error_digest": material["error_digest"],
        "material_digest": str(material_digest),
        "result_digest": str(result_digest),
        "event_type": AuditEventType.UPDATE.value,
        "audit_action": _AUDIT_ACTIONS[decision],
        "resource": f"tool_mutation:{material['mutation_id']}",
    }


def _audit_row(
    *, expected: Dict[str, Any], actor: Dict[str, Any], tenant_id: str,
) -> AuditLog:
    metadata = {
        "schema": expected["schema"],
        "operation_id": expected["operation_id"],
        "decision": expected["decision"],
        "prior_status": expected["prior_status"],
        "result_status": expected["result_status"],
        "target_id": expected["target_id"],
        "tenant_id": expected["tenant_id"],
        "actor_id": expected["actor_id"],
        "actor_role": expected["actor_role"],
        "tool_name": expected["tool_name"],
        "parent_tool_id": expected["parent_tool_id"],
        "code_digest": expected["code_digest"],
        "error_digest": expected["error_digest"],
        "material_digest": expected["material_digest"],
        "result_digest": expected["result_digest"],
    }
    return AuditLog(
        id=expected["operation_id"],
        event_type=expected["event_type"],
        security_level=SecurityLevel.HIGH.value,
        threat_level="none",
        user_id=actor["id"],
        user_email=actor["email"],
        tenant_id=str(tenant_id),
        workspace_id=None,
        resource=expected["resource"],
        action=expected["audit_action"],
        description=(
            f"Tool mutation {expected['target_id']} "
            f"{expected['decision']}"),
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
            if str(row.action or "") != expected["audit_action"]:
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
                "schema", "operation_id", "decision", "prior_status",
                "result_status", "target_id", "tenant_id", "actor_id",
                "actor_role", "tool_name", "code_digest", "error_digest",
                "material_digest", "result_digest",
            )
            for key in string_fields:
                if key not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                if not isinstance(metadata[key], str):
                    return {"status": "refuted", "audit_id": audit_id}
                if metadata[key] != expected[key]:
                    return {"status": "refuted", "audit_id": audit_id}
            if "parent_tool_id" not in metadata:
                return {"status": "unavailable", "audit_id": audit_id}
            parent = metadata["parent_tool_id"]
            if parent is not None and not isinstance(parent, str):
                return {"status": "refuted", "audit_id": audit_id}
            if parent != expected["parent_tool_id"]:
                return {"status": "refuted", "audit_id": audit_id}
            return {"status": "verified", "audit_id": audit_id}
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "tool-mutation audit read-back failed: operation_id=%s "
            "error_class=%s", audit_id, type(exc).__name__)
        return {"status": "unavailable", "audit_id": audit_id}


def _fresh_session(db: Session) -> Session:
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=db.get_bind())()


def _read_mutation(
    db: Session, tenant_id: str, mutation_id: str,
) -> Optional[ToolMutation]:
    with _fresh_session(db) as fresh:
        return fresh.query(ToolMutation).filter(
            ToolMutation.id == str(mutation_id),
            ToolMutation.tenant_id == str(tenant_id),
        ).first()


def _target_matches(
    row: Optional[ToolMutation], expected: Dict[str, Any],
) -> bool:
    if row is None:
        return False
    if str(row.tenant_id) != expected["tenant_id"]:
        return False
    if str(row.sandbox_status or "") != expected["result_status"]:
        return False
    try:
        material = _material_from_row(
            row, prior_status=expected["prior_status"],
            decision=expected["decision"])
    except Exception:
        return False
    return _material_digest(material) == expected["material_digest"]


def _expected_from_audit(
    row: AuditLog, *, operation_id: str,
) -> Optional[Dict[str, Any]]:
    try:
        metadata = json.loads(row.metadata_json or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(metadata, dict):
        return None
    return {
        "operation_id": str(operation_id),
        "schema": metadata.get("schema"),
        "decision": metadata.get("decision"),
        "prior_status": metadata.get("prior_status"),
        "result_status": metadata.get("result_status"),
        "target_id": metadata.get("target_id"),
        "tenant_id": metadata.get("tenant_id"),
        "actor_id": metadata.get("actor_id"),
        "actor_role": metadata.get("actor_role"),
        "tool_name": metadata.get("tool_name"),
        "parent_tool_id": metadata.get("parent_tool_id"),
        "code_digest": metadata.get("code_digest"),
        "error_digest": metadata.get("error_digest"),
        "material_digest": metadata.get("material_digest"),
        "result_digest": metadata.get("result_digest"),
        "event_type": AuditEventType.UPDATE.value,
        "audit_action": _AUDIT_ACTIONS.get(
            str(metadata.get("decision") or ""), ""),
        "resource": f"tool_mutation:{metadata.get('target_id')}",
    }


def _replay(
    db: Session, operation_id: str, expected: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Reconcile an existing receipt; None when no receipt exists."""
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(AuditLog).filter(
                AuditLog.id == str(operation_id)).first()
            if row is None:
                return None
            audit_expected = _expected_from_audit(row, operation_id=operation_id)
            if audit_expected is None:
                return _committed_unverified(
                    operation_id, {"status": "unavailable"}, target_id=(
                        expected.get("target_id") or ""))
            if (
                audit_expected["decision"] != expected["decision"]
                or audit_expected["target_id"] != expected["target_id"]
                or audit_expected["tenant_id"] != expected["tenant_id"]
                or audit_expected["actor_id"] != expected["actor_id"]
                or (
                    "material_digest" in expected
                    and audit_expected["material_digest"]
                    != expected["material_digest"]
                )
            ):
                return _conflict(
                    "operation_id is bound to a different decision/material",
                    code="OPERATION_CONFLICT")
            audit_state = _verify_audit(db, audit_expected)
            current = _read_mutation(
                db, audit_expected["tenant_id"],
                str(audit_expected["target_id"]))
            target_ok = _target_matches(current, audit_expected)
            if audit_state["status"] == "verified" and not target_ok:
                audit_state = {
                    "status": "refuted",
                    "audit_id": audit_expected["operation_id"],
                }
            if audit_state["status"] == "verified" and target_ok:
                return {
                    "status": "already_applied",
                    "data": {
                        "id": str(audit_expected["target_id"]),
                        "status": audit_expected["result_status"],
                        "verification": {
                            "status": "already_applied",
                            "effect": "committed",
                            "replay": "do_not_repeat",
                            "audit_id": audit_expected["operation_id"],
                        },
                        "operation_id": operation_id,
                        "audit_id": audit_expected["operation_id"],
                    },
                    "message": (
                        "This tool-mutation decision was already applied."),
                    "operation_id": operation_id,
                    "audit_id": audit_expected["operation_id"],
                    "target_id": str(audit_expected["target_id"]),
                }
            return _committed_unverified(
                operation_id, audit_state,
                target_id=str(audit_expected["target_id"]))
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "tool-mutation replay read failed: operation_id=%s error_class=%s",
            operation_id, type(exc).__name__)
        return _committed_unverified(
            operation_id, {"status": "unavailable"},
            target_id=str(expected.get("target_id") or ""))


def _commit_and_verify(
    db: Session, *, expected: Dict[str, Any], audit_row: AuditLog,
) -> Dict[str, Any]:
    target_id = str(expected["target_id"])
    operation_id = expected["operation_id"]
    try:
        db.add(audit_row)
        db.commit()
    except IntegrityError:
        db.rollback()
        replay = _replay(db, operation_id, expected)
        if replay is not None:
            return replay
        # The target was flushed before the audit row. A commit-time
        # IntegrityError with no original receipt is a confirmed local
        # rollback (for example an audit NOT NULL/FK failure), not a
        # post-commit uncertainty.
        return _not_applied(
            "The tool-mutation decision was rolled back; no effect was applied")
    except Exception as exc:  # noqa: BLE001 — commit outcome unknown
        db.rollback()
        logger.error(
            "tool-mutation decision outcome unknown: operation_id=%s "
            "target=%s error_class=%s",
            operation_id, target_id, type(exc).__name__)
        return _effect_unknown(operation_id, target_id)

    audit_state = _verify_audit(db, expected)
    current = _read_mutation(db, expected["tenant_id"], target_id)
    target_ok = _target_matches(current, expected)
    if audit_state["status"] == "verified" and not target_ok:
        audit_state = {"status": "refuted", "audit_id": operation_id}
    if audit_state["status"] == "verified" and target_ok:
        return {
            "status": "verified",
            "data": {
                "id": target_id,
                "status": expected["result_status"],
                "verification": {
                    "status": "verified",
                    "effect": "committed",
                    "audit_id": operation_id,
                },
                "operation_id": operation_id,
                "audit_id": operation_id,
            },
            "message": (
                f"Tool mutation {expected['result_status']}"),
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": target_id,
        }
    return _committed_unverified(
        operation_id, audit_state, target_id=target_id)


# ---------------------------------------------------------------------------
# Public review operation
# ---------------------------------------------------------------------------

def review_tool_mutation(
    db: Session, *,
    actor: User,
    tenant_id: str,
    mutation_id: str,
    decision: str,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Approve or reject one tool mutation with a durable decision receipt."""
    decision = str(decision or "").strip().lower()
    if decision not in _DECISIONS:
        return _refused(
            "decision must be approved or rejected",
            http_status=422, error_code="VALIDATION_ERROR",
            field="decision")
    try:
        operation_id = _new_operation_id(operation_id)
    except ValueError as exc:
        return _refused(
            str(exc), http_status=422, error_code="VALIDATION_ERROR",
            field="operation_id")

    actor_row = db.query(User).filter(User.id == str(actor.id)).first()
    if actor_row is None:
        return _refused(
            "Reviewer not found", http_status=404, error_code="NOT_FOUND")
    actor_snapshot = _actor_snapshot(actor_row)
    if not _actor_authorized(actor_snapshot, tenant_id):
        return _refused(
            "Reviewer authority changed; refresh and retry",
            http_status=403, error_code="AUTHORITY_CHANGED")

    mutation = db.query(ToolMutation).filter(
        ToolMutation.id == str(mutation_id),
        ToolMutation.tenant_id == str(tenant_id),
    ).populate_existing().first()
    if mutation is None:
        return _refused(
            "Mutation not found", http_status=404, error_code="NOT_FOUND")

    prior_status = str(mutation.sandbox_status or "pending")
    if prior_status in (_APPROVE, _REJECT):
        replay = _replay(
            db, operation_id,
            {
                "operation_id": operation_id,
                "decision": decision,
                "target_id": str(mutation.id),
                "tenant_id": str(tenant_id),
                "actor_id": actor_snapshot["id"],
            })
        if replay is not None:
            return replay
        return _conflict(
            "tool mutation is already reviewed; refresh and retry",
            code="ALREADY_REVIEWED")

    if decision == _APPROVE and prior_status == "failed":
        return _refused(
            "a sandbox-failed mutation cannot be approved",
            http_status=409, error_code="CONFLICT", field="status")
    allowed = _APPROVE_PRIOR if decision == _APPROVE else _REJECT_PRIOR
    if prior_status not in allowed:
        return _refused(
            f"tool mutation status {prior_status!r} cannot be {decision}",
            http_status=409, error_code="CONFLICT", field="status")

    material = _material_from_row(
        mutation, prior_status=prior_status, decision=decision)
    material_digest = _material_digest(material)
    result_digest = _result_digest(
        str(mutation.id), decision, material_digest)
    expected = _audit_expected(
        operation_id=operation_id, decision=decision,
        prior_status=prior_status, actor=actor_snapshot,
        tenant_id=str(tenant_id), material=material,
        material_digest=material_digest, result_digest=result_digest)

    replay = _replay(db, operation_id, expected)
    if replay is not None:
        return replay

    if not _claim_actor(db, actor_snapshot):
        db.rollback()
        return _conflict(
            "reviewer authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    try:
        result = db.execute(
            update(ToolMutation)
            .where(
                ToolMutation.id == str(mutation.id),
                ToolMutation.tenant_id == str(tenant_id),
                ToolMutation.sandbox_status == prior_status,
                ToolMutation.tool_name == str(mutation.tool_name or ""),
                _exact_nullable(
                    ToolMutation.parent_tool_id, mutation.parent_tool_id),
                _exact_nullable(
                    ToolMutation.execution_error, mutation.execution_error),
                ToolMutation.mutated_code == str(mutation.mutated_code or ""),
            )
            .values(sandbox_status=decision)
        )
        if result.rowcount != 1:
            db.rollback()
            now = _read_mutation(db, tenant_id, str(mutation.id))
            if now is not None and str(now.sandbox_status or "") in (
                    _APPROVE, _REJECT):
                return _conflict(
                    "tool mutation is already reviewed; refresh and retry",
                    code="ALREADY_REVIEWED")
            return _conflict(
                "tool mutation material changed; refresh and retry",
                code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        replay = _replay(db, operation_id, expected)
        return replay or _conflict(
            "tool mutation decision conflicts with current state",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "tool-mutation decision failed before commit: operation_id=%s "
            "target=%s error_class=%s",
            operation_id, mutation.id, type(exc).__name__)
        return _not_applied(
            "The tool-mutation decision could not be applied; no effect "
            "was committed")

    audit_row = _audit_row(
        expected=expected, actor=actor_snapshot, tenant_id=str(tenant_id))
    return _commit_and_verify(db, expected=expected, audit_row=audit_row)


def _exact_nullable(column, value: Any):
    if value is None:
        return column.is_(None)
    return column == str(value)
