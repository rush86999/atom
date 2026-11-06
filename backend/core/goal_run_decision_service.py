"""Verified goal-run supervision and cancellation decisions.

The mode/cancel routes already had supervisor/owner/workspace guards, but the
effect was a direct service mutation with no exact revision binding, receipt or
replay protection. This module binds the current principal and the run's
``material_revision`` in guarded DML in the same transaction as one safe
``AuditLog`` receipt.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.auth import SECRET_KEY
from core.goals.goal_run_service import (
    GOAL_RUN_TRANSITIONS,
    SUPERVISION_MODES,
)
from core.models import (
    AuditEventType,
    AuditLog,
    GoalRun,
    SecurityLevel,
    User,
    UserRole,
)
from core.personal_scope import resolve_tenant_id
from core.security.rbac import role_level

logger = logging.getLogger(__name__)

REVIEW_SCHEMA = "atom-goal-run-decision-1"
_OPERATION_PREFIX = "goal-run"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_ACTION_MODE = "goal_run_mode_changed"
_ACTION_CANCEL = "goal_run_cancelled"


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
    message: str, *, http_status: int = 403,
    error_code: str = "AUTHORITY_REQUIRED", field: Optional[str] = None,
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
        "error_code": "GOAL_RUN_TRANSACTION_ROLLED_BACK",
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
            "The goal-run decision committed but its audit/target readback "
            "did not verify. Reconcile the original operation."),
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
            "The goal-run decision may have committed, but confirmation was "
            "lost. Reconcile the original operation; do not repeat it "
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
        str(actor.get("message") or "Supervisor authority is required"),
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
            return {
                "ok": True,
                "id": actor_id,
                "email": str(row.email or ""),
                "role": str(row.role or ""),
                "status": str(row.status or ""),
                "tenant_id": str(resolve_tenant_id(row)),
                "raw_tenant_id": row.tenant_id,
            }
    except Exception as exc:  # noqa: BLE001 — unreadable authority fails closed
        logger.warning(
            "goal-run authority read failed: actor=%s error_class=%s",
            actor_id, type(exc).__name__)
        return {
            "ok": False, "http_status": 503,
            "error_code": "AUTHORITY_UNAVAILABLE",
            "message": "Authorization could not be confirmed; retry",
        }


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


def _exact(column, value: Any):
    return column.is_(None) if value is None else column == str(value)


def _load_run(
    db: Session, workspace_id: str, run_id: str,
) -> Optional[GoalRun]:
    with _fresh_session(db) as fresh:
        return fresh.query(GoalRun).filter(
            GoalRun.id == str(run_id),
            GoalRun.workspace_id == str(workspace_id),
        ).populate_existing().first()


def _run_state(
    run: GoalRun, *, status: Optional[str] = None,
    mode: Optional[str] = None, revision: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "id": str(run.id),
        "workspace_id": str(run.workspace_id or ""),
        "status": str(status if status is not None else run.status or ""),
        "supervision_mode": str(
            mode if mode is not None else run.supervision_mode or ""),
        "material_revision": int(
            revision if revision is not None
            else run.material_revision or 0),
    }


def _state_digest(state: Dict[str, Any]) -> str:
    return _fingerprint("goal-run-state", _canonical(state))


def _request_digest(
    action: str, run_id: str, change: Dict[str, Any],
) -> str:
    return _fingerprint(
        "goal-run-request", str(action), str(run_id),
        _canonical(change))


def _audit_expected(
    *, operation_id: str, action: str, run: GoalRun,
    prior_status: str, result_status: str,
    prior_mode: str, result_mode: str,
    prior_revision: int, result_revision: int,
    request_digest: str, prior_digest: str, result_digest: str,
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "operation_id": str(operation_id),
        "schema": REVIEW_SCHEMA,
        "action": str(action),
        "event_type": AuditEventType.UPDATE.value,
        "target_id": str(run.id),
        "target_workspace_id": str(run.workspace_id or ""),
        "prior_status": str(prior_status),
        "result_status": str(result_status),
        "prior_mode": str(prior_mode),
        "result_mode": str(result_mode),
        "prior_revision": int(prior_revision),
        "result_revision": int(result_revision),
        "request_digest": str(request_digest),
        "prior_digest": str(prior_digest),
        "result_digest": str(result_digest),
        "actor_id": actor["id"],
        "actor_role": actor["role"],
        "tenant_id": actor["tenant_id"],
        "resource": f"goal_run:{run.id}",
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
        "target_workspace_id": expected["target_workspace_id"],
        "prior_status": expected["prior_status"],
        "result_status": expected["result_status"],
        "prior_mode": expected["prior_mode"],
        "result_mode": expected["result_mode"],
        "prior_revision": expected["prior_revision"],
        "result_revision": expected["result_revision"],
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
        user_id=expected["actor_id"],
        user_email=actor["email"],
        tenant_id=expected["tenant_id"],
        workspace_id=expected["target_workspace_id"],
        resource=expected["resource"],
        action=expected["action"],
        description="Goal-run decision recorded",
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
            if str(row.workspace_id or "") != expected["target_workspace_id"]:
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
                "target_id", "target_workspace_id", "prior_status",
                "result_status", "prior_mode", "result_mode",
                "request_digest", "prior_digest", "result_digest",
                "actor_id", "actor_role", "tenant_id",
            )
            for key in string_fields:
                if key not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                if not isinstance(metadata[key], str):
                    return {"status": "refuted", "audit_id": audit_id}
                if metadata[key] != expected[key]:
                    return {"status": "refuted", "audit_id": audit_id}
            for key in ("prior_revision", "result_revision"):
                if key not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                if not isinstance(metadata[key], int):
                    return {"status": "refuted", "audit_id": audit_id}
                if metadata[key] != expected[key]:
                    return {"status": "refuted", "audit_id": audit_id}
            return {"status": "verified", "audit_id": audit_id}
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "goal-run audit read-back failed: operation_id=%s error_class=%s",
            audit_id, type(exc).__name__)
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
        "target_workspace_id": metadata.get("target_workspace_id"),
        "prior_status": metadata.get("prior_status"),
        "result_status": metadata.get("result_status"),
        "prior_mode": metadata.get("prior_mode"),
        "result_mode": metadata.get("result_mode"),
        "prior_revision": metadata.get("prior_revision"),
        "result_revision": metadata.get("result_revision"),
        "request_digest": metadata.get("request_digest"),
        "prior_digest": metadata.get("prior_digest"),
        "result_digest": metadata.get("result_digest"),
        "actor_id": metadata.get("actor_id"),
        "actor_role": metadata.get("actor_role"),
        "tenant_id": metadata.get("tenant_id"),
        "resource": f"goal_run:{metadata.get('target_id')}",
    }


def _replay(
    db: Session, operation_id: str, expected: Dict[str, Any],
    *, authority: Dict[str, Any],
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
            current = _load_run(
                db, str(metadata.get("target_workspace_id") or ""),
                str(metadata.get("target_id") or ""))
            target_ok = (
                current is not None
                and _state_digest(_run_state(current))
                == audit_expected["result_digest"]
            )
            data = (
                _run_state(current) if current is not None
                else {
                    "id": audit_expected["target_id"],
                    "status": audit_expected["result_status"],
                    "supervision_mode": audit_expected["result_mode"],
                    "material_revision": audit_expected["result_revision"],
                }
            )
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
                    "message": "This goal-run decision was already applied.",
                    "operation_id": operation_id,
                    "audit_id": audit_expected["operation_id"],
                    "target_id": audit_expected["target_id"],
                }
            return _committed_unverified(
                operation_id, audit_state,
                target_id=audit_expected["target_id"])
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "goal-run replay read failed: operation_id=%s error_class=%s",
            operation_id, type(exc).__name__)
        return _committed_unverified(
            operation_id, {"status": "unavailable"},
            target_id=str(expected.get("target_id") or ""))


def _commit_and_verify(
    db: Session, *, expected: Dict[str, Any], audit_row: AuditLog,
    target_check: Callable[[], bool], success_data: Dict[str, Any],
    authority: Dict[str, Any],
) -> Dict[str, Any]:
    operation_id = expected["operation_id"]
    target_id = expected["target_id"]
    try:
        db.add(audit_row)
        db.commit()
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected, authority=authority)
        if replay is not None:
            return replay
        return _not_applied(
            "The goal-run decision was rolled back; no effect was applied")
    except Exception as exc:  # noqa: BLE001 — commit outcome unknown
        db.rollback()
        logger.error(
            "goal-run decision outcome unknown: operation_id=%s target=%s "
            "error_class=%s", operation_id, target_id,
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
            "message": "Goal-run decision committed and verified.",
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": target_id,
        }
    return _committed_unverified(
        operation_id, audit_state, target_id=target_id)


def set_supervision_mode(
    db: Session, *, actor: Any, workspace_id: str, run_id: str, mode: str,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    authority = _resolve_actor(db, actor)
    if not authority.get("ok"):
        return _actor_refusal(authority)
    mode = str(mode or "").strip().lower()
    if mode not in SUPERVISION_MODES:
        return _refused(
            f"supervision_mode must be one of {SUPERVISION_MODES}",
            http_status=422, error_code="VALIDATION_ERROR",
            field="supervision_mode")
    if role_level(authority["role"]) < role_level(UserRole.TEAM_LEAD):
        return _refused(
            "Supervisor authority is required", http_status=403,
            error_code="AUTHORITY_REQUIRED")
    try:
        operation_id = _operation_id("mode", operation_id)
    except ValueError as exc:
        return _refused(
            str(exc), http_status=422, error_code="VALIDATION_ERROR",
            field="operation_id")

    request_digest = _request_digest(
        _ACTION_MODE, str(run_id), {"supervision_mode": mode})
    expected_base = {
        "operation_id": operation_id,
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_MODE,
        "event_type": AuditEventType.UPDATE.value,
        "target_id": str(run_id),
        "request_digest": request_digest,
        "actor_id": authority["id"],
    }
    replay = _replay(db, operation_id, expected_base, authority=authority)
    if replay is not None:
        return replay

    run = _load_run(db, workspace_id, run_id)
    if run is None:
        return _refused(
            f"GoalRun not found: {run_id}", http_status=404,
            error_code="NOT_FOUND")
    prior_status = str(run.status or "")
    prior_mode = str(run.supervision_mode or "")
    prior_revision = int(run.material_revision or 0)
    if prior_mode == mode:
        return _no_change(
            _run_state(run), "Goal run already uses that supervision mode")

    result_revision = prior_revision + 1
    prior_digest = _state_digest(_run_state(run))
    result_digest = _state_digest(_run_state(
        run, status=prior_status, mode=mode, revision=result_revision))
    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_MODE, run=run,
        prior_status=prior_status, result_status=prior_status,
        prior_mode=prior_mode, result_mode=mode,
        prior_revision=prior_revision, result_revision=result_revision,
        request_digest=request_digest, prior_digest=prior_digest,
        result_digest=result_digest, actor=authority)

    if not _claim_actor(db, authority):
        db.rollback()
        return _conflict(
            "reviewer authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    try:
        updated = db.execute(
            update(GoalRun)
            .where(
                GoalRun.id == str(run.id),
                GoalRun.workspace_id == str(workspace_id),
                GoalRun.material_revision == prior_revision,
                GoalRun.status == prior_status,
                GoalRun.supervision_mode == prior_mode,
            )
            .values(supervision_mode=mode, material_revision=result_revision))
        if updated.rowcount != 1:
            db.rollback()
            return _conflict(
                "goal run changed; refresh and retry", code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        replay = _replay(db, operation_id, expected, authority=authority)
        return replay or _conflict(
            "goal-run decision conflicts with current state",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "goal-run mode change failed before commit: operation_id=%s "
            "target=%s error_class=%s", operation_id, run_id,
            type(exc).__name__)
        return _not_applied(
            "The goal-run mode change could not be applied; no effect was "
            "committed")

    audit_row = _audit_row(expected=expected, actor=authority)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (now := _load_run(db, workspace_id, run_id)) is not None
            and _state_digest(_run_state(now)) == result_digest),
        success_data=_run_state(
            run, status=prior_status, mode=mode,
            revision=result_revision),
        authority=authority)


def cancel_goal_run(
    db: Session, *, actor: Any, workspace_id: str, run_id: str,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    authority = _resolve_actor(db, actor)
    if not authority.get("ok"):
        return _actor_refusal(authority)
    try:
        operation_id = _operation_id("cancel", operation_id)
    except ValueError as exc:
        return _refused(
            str(exc), http_status=422, error_code="VALIDATION_ERROR",
            field="operation_id")

    request_digest = _request_digest(
        _ACTION_CANCEL, str(run_id), {"reason": "cancelled by user"})
    expected_base = {
        "operation_id": operation_id,
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_CANCEL,
        "event_type": AuditEventType.UPDATE.value,
        "target_id": str(run_id),
        "request_digest": request_digest,
        "actor_id": authority["id"],
    }
    replay = _replay(db, operation_id, expected_base, authority=authority)
    if replay is not None:
        return replay

    run = _load_run(db, workspace_id, run_id)
    if run is None:
        return _refused(
            f"GoalRun not found: {run_id}", http_status=404,
            error_code="NOT_FOUND")
    is_supervisor = role_level(authority["role"]) >= role_level(
        UserRole.TEAM_LEAD)
    if not is_supervisor and str(run.created_by or "") != authority["id"]:
        return _refused(
            "Only the run's owner or a supervisor can cancel it",
            http_status=403, error_code="AUTHORITY_REQUIRED")

    prior_status = str(run.status or "")
    if "cancelled" not in GOAL_RUN_TRANSITIONS.get(prior_status, set()):
        return _conflict(
            f"goal run status {prior_status!r} cannot be cancelled",
            code="UNSUPPORTED_STATUS")
    prior_mode = str(run.supervision_mode or "")
    prior_revision = int(run.material_revision or 0)
    result_revision = prior_revision + 1
    log = list(run.decision_log or [])
    log.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": "cancelled",
        "rationale": "cancelled by user",
    })
    prior_digest = _state_digest(_run_state(run))
    result_digest = _state_digest(_run_state(
        run, status="cancelled", revision=result_revision))
    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_CANCEL, run=run,
        prior_status=prior_status, result_status="cancelled",
        prior_mode=prior_mode, result_mode=prior_mode,
        prior_revision=prior_revision, result_revision=result_revision,
        request_digest=request_digest, prior_digest=prior_digest,
        result_digest=result_digest, actor=authority)

    if not _claim_actor(db, authority):
        db.rollback()
        return _conflict(
            "reviewer authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    try:
        updated = db.execute(
            update(GoalRun)
            .where(
                GoalRun.id == str(run.id),
                GoalRun.workspace_id == str(workspace_id),
                GoalRun.material_revision == prior_revision,
                GoalRun.status == prior_status,
            )
            .values(
                status="cancelled", waiting_on=None,
                decision_log=log, material_revision=result_revision))
        if updated.rowcount != 1:
            db.rollback()
            return _conflict(
                "goal run changed; refresh and retry", code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        replay = _replay(db, operation_id, expected, authority=authority)
        return replay or _conflict(
            "goal-run decision conflicts with current state",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "goal-run cancel failed before commit: operation_id=%s target=%s "
            "error_class=%s", operation_id, run_id, type(exc).__name__)
        return _not_applied(
            "The goal run could not be cancelled; no effect was committed")

    audit_row = _audit_row(expected=expected, actor=authority)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (now := _load_run(db, workspace_id, run_id)) is not None
            and _state_digest(_run_state(now)) == result_digest),
        success_data=_run_state(
            run, status="cancelled", revision=result_revision),
        authority=authority)
