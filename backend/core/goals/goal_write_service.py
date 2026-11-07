"""Verified public writes for a persisted goal (POST / utility PUT / DELETE).

The goal routes already had role and workspace guards, but the guards read the
request-entry ``User`` snapshot and the effect was a direct mutation: a
concurrent demotion/deactivation/workspace reassignment, or a concurrent
metadata change, could still be overwritten after the check. This module binds
the current principal and the reviewed goal material in guarded DML in the same
transaction as one ``AuditLog`` receipt.

It deliberately reuses the family contract already used by
``goal_run_decision_service`` / ``memory_write_service`` — authoritative actor
snapshot, ``_claim_actor`` CAS, target CAS, receipts, replay and the
verified/committed_unverified/effect_unknown semantics — rather than adding a
new review engine, table or migration. Internal trusted lifecycle callers
(``action_registry`` / ``task_lifecycle`` / ``goal_engine``) keep using
``GoalService`` directly: an ordinary goal write never becomes a human prompt.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy import JSON as SAJSON
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.auth import SECRET_KEY
from core.goals.utility_target import normalize_utility_target
from core.models import (
    AuditEventType,
    AuditLog,
    GoalObjective,
    SecurityLevel,
    User,
    UserRole,
)
from core.personal_scope import resolve_tenant_id, resolve_workspace_id
from core.security.rbac import role_level

logger = logging.getLogger(__name__)

WRITE_SCHEMA = "atom-goal-write-1"
_OPERATION_PREFIX = "goal"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_ACTION_CREATE = "goal_created"
_ACTION_UTILITY_SET = "goal_utility_set"
_ACTION_UTILITY_CLEAR = "goal_utility_cleared"

_AUDIT_STRING_FIELDS = (
    "schema", "operation_id", "action", "event_type", "target_id",
    "target_workspace_id", "request_digest", "prior_digest", "result_digest",
    "actor_id", "actor_role", "actor_status", "actor_workspace_id",
    "tenant_id",
)


# --------------------------------------------------------------------- utils

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


def _no_change(data: Dict[str, Any], message: str) -> Dict[str, Any]:
    result = dict(data)
    result["verification"] = {"status": "no_change", "effect": "none"}
    return {"status": "no_change", "data": result, "message": message}


def _not_applied(message: str) -> Dict[str, Any]:
    return {
        "status": "not_applied",
        "error": message,
        "error_code": "GOAL_WRITE_TRANSACTION_ROLLED_BACK",
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
            "The goal write committed but its audit/target readback did not "
            "verify. Reconcile the original operation."),
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
            "The goal write may have committed, but confirmation was lost. "
            "Reconcile the original operation; do not repeat it blindly."),
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


def _exact(column, value: Any):
    return column.is_(None) if value is None else column == str(value)


# ----------------------------------------------------------------- authority

def _actor_refusal(actor: Dict[str, Any]) -> Dict[str, Any]:
    return _refused(
        str(actor.get("message") or "Authentication required"),
        http_status=int(actor.get("http_status") or 401),
        error_code=str(actor.get("error_code") or "UNAUTHENTICATED"),
    )


def _resolve_actor(db: Session, actor: Any) -> Dict[str, Any]:
    """Resolve the authoritative principal snapshot for this write.

    The request-entry User object is a snapshot. A concurrent deactivation,
    demotion or workspace reassignment must not let a goal mutation commit
    under stale authority, so the claim material is read from the row and
    frozen here, then bound in the same transaction as the effect.
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
            raw_status = str(row.status or "")
            raw_is_active = row.is_active is True
            if raw_status != "active" or not raw_is_active:
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
                "status": raw_status,
                "tenant_id": str(resolve_tenant_id(row)),
                "workspace_id": str(resolve_workspace_id(row)),
                "raw_tenant_id": row.tenant_id,
                "raw_workspace_id": row.workspace_id,
            }
    except Exception as exc:  # noqa: BLE001 — unreadable authority fails closed
        logger.warning(
            "goal-write authority read failed: actor=%s error_class=%s",
            actor_id, type(exc).__name__)
        return {
            "ok": False, "http_status": 503,
            "error_code": "AUTHORITY_UNAVAILABLE",
            "message": "Authorization could not be confirmed; retry",
        }


def _claim_actor(db: Session, actor: Dict[str, Any]) -> bool:
    """Bind the frozen principal in the same transaction as the effect.

    A zero-match means the User row was deactivated, demoted, moved or deleted
    after the request-entry snapshot. The caller rolls back and refuses with
    effect=none; no target or receipt commit can stand alone.
    """
    result = db.execute(
        update(User)
        .where(
            User.id == actor["id"],
            User.is_active.is_(True),
            User.status == actor["status"],
            User.role == actor["role"],
            _exact(User.tenant_id, actor["raw_tenant_id"]),
            _exact(User.workspace_id, actor["raw_workspace_id"]),
        )
        .values(updated_at=User.updated_at)
    )
    return result.rowcount == 1


def _require_role(actor: Dict[str, Any], minimum: UserRole) -> Optional[Dict[str, Any]]:
    if role_level(actor["role"]) >= role_level(minimum):
        return None
    return _refused(
        "Insufficient permissions. Required role: "
        f"{getattr(minimum, 'value', minimum)}",
        http_status=403, error_code="AUTHORITY_REQUIRED")


def _bind_intended_scope(
    actor: Dict[str, Any], *, workspace_id: str, tenant_id: str,
) -> Optional[Dict[str, Any]]:
    """Bind the scope the request was reviewed in, not a retargeted one.

    A workspace/tenant change committed after the route's review must refuse
    with effect=none; it must not silently move the already-reviewed write to
    the actor's new scope. The authoritative snapshot is compared with the
    request-entry scope frozen by the caller before the mutation.
    """
    if (
        str(actor.get("workspace_id") or "") != str(workspace_id or "")
        or str(actor.get("tenant_id") or "") != str(tenant_id or "")
    ):
        return _conflict(
            "authorization or workspace changed; refresh and retry",
            code="AUTHORITY_CHANGED")
    return None



# ---------------------------------------------------------------- target I/O

def _load_goal_snapshot(
    db: Session, workspace_id: str, goal_id: str,
) -> Optional[Tuple[GoalObjective, bool]]:
    """Load the goal and its physical SQL-NULL metadata state in one SELECT.

    ORM deserialization maps both a physical SQL NULL and a stored JSON null
    (``'null'``) to Python ``None``. A value-only read, or a flag read in a
    second statement, therefore cannot tell them apart and would let the CAS
    compare the wrong physical material. The flag is selected alongside the
    row here so the goal material, its exact nullable kind and the CAS
    predicate all come from the same snapshot.
    """
    statement = (
        select(
            GoalObjective,
            GoalObjective.metadata_json.is_(None).label(
                "metadata_is_sql_null"),
        )
        .where(
            GoalObjective.id == str(goal_id),
            GoalObjective.workspace_id == str(workspace_id),
        )
        .execution_options(populate_existing=True)
    )
    with _fresh_session(db) as fresh:
        row = fresh.execute(statement).first()
    if row is None:
        return None
    goal = row[0]
    return goal, bool(row[1])


def _goal_dict(goal: GoalObjective) -> Dict[str, Any]:
    return {
        "id": goal.id,
        "title": goal.title,
        "description": goal.description,
        "status": goal.status,
        "progress": goal.progress,
        "criteria": goal.criteria or [],
        "key_results": goal.key_results or [],
        "owner_id": goal.owner_id,
        "parent_goal_id": goal.parent_goal_id,
        "source": goal.source,
        "utility_target": (goal.metadata_json or {}).get("utility_target"),
        "target_date": (
            goal.target_date.isoformat() if goal.target_date else None),
        "created_at": (
            goal.created_at.isoformat() if goal.created_at else None),
    }


def _goal_utility_data(goal: GoalObjective) -> Dict[str, Any]:
    return {
        "goal_id": str(goal.id),
        "workspace_id": str(goal.workspace_id or ""),
        "utility_target": (goal.metadata_json or {}).get("utility_target"),
    }


def _metadata_material(
    metadata: Optional[Dict[str, Any]], *, sql_null: bool = False,
) -> Dict[str, Any]:
    """Distinguish SQL NULL / JSON null / empty object material.

    A physical SQL NULL and a stored JSON null both deserialize to ``None``.
    They are different stored material: a CAS that treated them as
    interchangeable would false-conflict an unchanged JSON-null row (its
    ``IS NULL`` predicate matches nothing) or silently overwrite a peer's
    null-to-empty-object transition. Object material keeps its original
    representation so receipts written before this distinction still replay;
    null material names its exact physical kind.
    """
    if sql_null:
        return {"present": False, "null_kind": "sql_null"}
    if metadata is None:
        return {"present": False, "null_kind": "json_null"}
    return {"present": True, "value": metadata}


def _metadata_digest(
    metadata: Optional[Dict[str, Any]], *, sql_null: bool = False,
) -> str:
    return _fingerprint(
        "goal-metadata",
        _canonical(_metadata_material(metadata, sql_null=sql_null)))


def _utility_state_digest(
    goal: GoalObjective, *, sql_null: bool = False,
) -> str:
    return _metadata_digest(goal.metadata_json, sql_null=sql_null)


def _metadata_cas_condition(
    prior_metadata: Optional[Dict[str, Any]], *, sql_null: bool = False,
):
    """The exact prior material to compare, including both null kinds."""
    if sql_null:
        return GoalObjective.metadata_json.is_(None)
    if prior_metadata is None:
        # A JSON null is stored as JSON text, not SQL NULL. ``IS NULL`` would
        # match zero rows and falsely report a stale target for unchanged
        # material; compare against SQLAlchemy's JSON-null sentinel instead.
        return GoalObjective.metadata_json == SAJSON.NULL
    return GoalObjective.metadata_json == prior_metadata


def _read_prior_metadata(
    goal: GoalObjective, *, sql_null: bool = False,
) -> Any:
    """Return the stored metadata value with its physical-null kind.

    ``None`` is valid for both SQL NULL and JSON null; callers carry the
    ``sql_null`` flag separately and must never normalize one into the other.
    """
    if sql_null:
        return None
    return goal.metadata_json


def _replay_target_digest(
    action: str, goal: GoalObjective, *, sql_null: bool = False,
) -> str:
    """The material digest the operation's receipt was written against."""
    if str(action) == _ACTION_CREATE:
        return _goal_material_digest(goal, sql_null=sql_null)
    return _utility_state_digest(goal, sql_null=sql_null)


def _goal_material_digest(
    goal: GoalObjective, *, sql_null: bool = False,
) -> str:
    material = {
        "id": str(goal.id),
        "workspace_id": str(goal.workspace_id or ""),
        "title": str(goal.title or ""),
        "description": str(goal.description or ""),
        "status": str(goal.status or ""),
        "progress": goal.progress,
        "criteria": goal.criteria or [],
        "key_results": goal.key_results or [],
        "metadata": goal.metadata_json or {},
        "owner_id": (
            str(goal.owner_id) if goal.owner_id is not None else None),
        "parent_goal_id": (
            str(goal.parent_goal_id)
            if goal.parent_goal_id is not None else None),
        "source": str(goal.source or ""),
        "target_date": (
            goal.target_date.isoformat() if goal.target_date else None),
    }
    if sql_null or goal.metadata_json is None:
        # Object material keeps its original shape (and therefore its
        # existing digest); null material records its exact physical kind so
        # SQL NULL, JSON null and {} never share a result/replay digest.
        material["metadata_kind"] = (
            "sql_null" if sql_null else "json_null")
    return _fingerprint("goal-material", _canonical(material))


def _request_digest(action: str, workspace_id: str, material: Any) -> str:
    return _fingerprint(
        "goal-request", str(action), str(workspace_id), _canonical(material))


# ------------------------------------------------------------------- receipts

def _audit_expected(
    *, operation_id: str, action: str, target_id: str,
    target_workspace_id: str, request_digest: str, prior_digest: str,
    result_digest: str, actor: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "operation_id": str(operation_id),
        "schema": WRITE_SCHEMA,
        "action": str(action),
        "event_type": AuditEventType.UPDATE.value,
        "target_id": str(target_id),
        "target_workspace_id": str(target_workspace_id),
        "request_digest": str(request_digest),
        "prior_digest": str(prior_digest),
        "result_digest": str(result_digest),
        "actor_id": actor["id"],
        "actor_role": actor["role"],
        "actor_status": actor["status"],
        "actor_workspace_id": actor["workspace_id"],
        "tenant_id": actor["tenant_id"],
        "resource": f"goal:{target_id}",
    }


def _audit_row(
    *, expected: Dict[str, Any], actor: Dict[str, Any],
    description: str,
) -> AuditLog:
    metadata = {key: expected[key] for key in _AUDIT_STRING_FIELDS}
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
            for key in _AUDIT_STRING_FIELDS:
                if key not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                if not isinstance(metadata[key], str):
                    return {"status": "refuted", "audit_id": audit_id}
                if metadata[key] != expected[key]:
                    return {"status": "refuted", "audit_id": audit_id}
            return {"status": "verified", "audit_id": audit_id}
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "goal-write audit read-back failed: operation_id=%s "
            "error_class=%s", audit_id, type(exc).__name__)
        return {"status": "unavailable", "audit_id": audit_id}


def _expected_from_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    expected = {key: metadata.get(key) for key in _AUDIT_STRING_FIELDS}
    expected["resource"] = f"goal:{metadata.get('target_id')}"
    return expected


def _replay(
    db: Session, operation_id: str, expected: Dict[str, Any],
    *, success_data: Callable[[GoalObjective], Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Return the receipted outcome of the same operation, or ``None``.

    A reused operation id is only safe when it names the same reviewed
    material and actor scope. A different material is an operation conflict;
    a committed operation whose target no longer matches its receipt is
    committed-unverified (never silently replayed).
    """
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
                metadata.get("schema") != WRITE_SCHEMA
                or metadata.get("action") != expected["action"]
                or metadata.get("event_type") != expected["event_type"]
                or metadata.get("request_digest")
                != expected["request_digest"]
                or metadata.get("actor_id") != expected["actor_id"]
                or metadata.get("actor_role") != expected["actor_role"]
                or metadata.get("tenant_id") != expected["tenant_id"]
                or metadata.get("actor_workspace_id")
                != expected["actor_workspace_id"]
                or (
                    expected.get("target_id") is not None
                    and metadata.get("target_id") != expected["target_id"]
                )
            ):
                return _conflict(
                    "operation_id is bound to different goal material or "
                    "changed authority",
                    code="OPERATION_CONFLICT")
            audit_expected = _expected_from_metadata(metadata)
            audit_state = _verify_audit(db, audit_expected)
            snapshot = _load_goal_snapshot(
                db,
                str(audit_expected["target_workspace_id"] or ""),
                str(audit_expected["target_id"] or ""))
            current = snapshot[0] if snapshot is not None else None
            current_is_null = snapshot[1] if snapshot is not None else False
            target_ok = (
                current is not None
                and _replay_target_digest(
                    expected["action"], current, sql_null=current_is_null)
                == audit_expected["result_digest"]
            )
            data = (
                success_data(current) if current is not None else
                {"target_id": audit_expected["target_id"]}
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
                    "message": "This goal write was already applied.",
                    "operation_id": operation_id,
                    "audit_id": audit_expected["operation_id"],
                    "target_id": audit_expected["target_id"],
                }
            return _committed_unverified(
                operation_id, audit_state,
                target_id=audit_expected["target_id"])
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "goal-write replay read failed: operation_id=%s error_class=%s",
            operation_id, type(exc).__name__)
        return _committed_unverified(
            operation_id, {"status": "unavailable"},
            target_id=str(expected.get("target_id") or ""))


def _commit_and_verify(
    db: Session, *, expected: Dict[str, Any], audit_row: AuditLog,
    target_check: Callable[[], bool], success_data: Dict[str, Any],
    operation_id: str,
) -> Dict[str, Any]:
    target_id = expected["target_id"]
    try:
        db.add(audit_row)
        db.commit()
    except IntegrityError:
        db.rollback()
        return _not_applied(
            "The goal write was rolled back; no effect was applied")
    except Exception as exc:  # noqa: BLE001 — commit outcome unknown
        db.rollback()
        logger.error(
            "goal write outcome unknown: operation_id=%s target=%s "
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
            "message": "Goal write committed and verified.",
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": target_id,
        }
    return _committed_unverified(
        operation_id, audit_state, target_id=target_id)


# ----------------------------------------------------------------- operations

def create_goal(
    db: Session, *, actor: Any, workspace_id: str, tenant_id: str,
    title: str, description: str = "",
    criteria: Optional[List[Dict[str, Any]]] = None,
    key_results: Optional[List[Dict[str, Any]]] = None,
    target_date: Optional[datetime] = None,
    utility_target: Optional[Dict[str, Any]] = None,
    source: str = "api",
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a goal under authoritative authority and one receipt."""
    authority = _resolve_actor(db, actor)
    if not authority.get("ok"):
        return _actor_refusal(authority)
    scope_conflict = _bind_intended_scope(
        authority, workspace_id=workspace_id, tenant_id=tenant_id)
    if scope_conflict is not None:
        return scope_conflict

    refusal = _require_role(authority, UserRole.MEMBER)
    if refusal is not None:
        return refusal
    enriched = bool(criteria or key_results or target_date
                    or utility_target is not None)
    if enriched:
        refusal = _require_role(authority, UserRole.TEAM_LEAD)
        if refusal is not None:
            return refusal

    title = str(title or "").strip()
    if not title:
        return _refused(
            "goal title is required", http_status=422,
            error_code="VALIDATION_ERROR", field="title")
    try:
        operation_id = _operation_id("create", operation_id)
    except ValueError as exc:
        return _refused(
            str(exc), http_status=422, error_code="VALIDATION_ERROR",
            field="operation_id")
    normalized_target = None
    if utility_target is not None:
        try:
            normalized_target = normalize_utility_target(utility_target)
        except ValueError as exc:
            return _refused(
                str(exc), http_status=422, error_code="VALIDATION_ERROR",
                field="utility_target")

    criteria = list(criteria or [])
    key_results = list(key_results or [])
    material = {
        "title": title,
        "description": str(description or ""),
        "criteria": criteria,
        "key_results": key_results,
        "target_date": target_date.isoformat() if target_date else None,
        "utility_target": normalized_target,
        "source": str(source or "api"),
    }
    request_digest = _request_digest(
        _ACTION_CREATE, authority["workspace_id"], material)
    expected_base = {
        "operation_id": operation_id,
        "schema": WRITE_SCHEMA,
        "action": _ACTION_CREATE,
        "event_type": AuditEventType.UPDATE.value,
        "target_id": None,
        "request_digest": request_digest,
        "actor_id": authority["id"],
        "actor_role": authority["role"],
        "tenant_id": authority["tenant_id"],
        "actor_workspace_id": authority["workspace_id"],
    }

    def success_data(goal: GoalObjective) -> Dict[str, Any]:
        return _goal_dict(goal)

    replay = _replay(
        db, operation_id, expected_base,
        success_data=success_data)
    if replay is not None:
        return replay

    if not _claim_actor(db, authority):
        db.rollback()
        return _conflict(
            "authorization or workspace changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    goal_id = str(uuid.uuid4())
    metadata: Dict[str, Any] = {}
    if normalized_target is not None:
        metadata["utility_target"] = normalized_target
    goal = GoalObjective(
        id=goal_id,
        tenant_id=authority["tenant_id"],
        workspace_id=authority["workspace_id"],
        title=title,
        description=material["description"],
        criteria=criteria,
        key_results=key_results,
        metadata_json=metadata,
        owner_id=authority["id"],
        target_date=target_date,
        source=material["source"],
    )
    try:
        db.add(goal)
        db.flush()
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected_base,
            success_data=success_data)
        return replay or _conflict(
            "goal creation conflicts with current state",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "goal create failed before commit: operation_id=%s "
            "error_class=%s", operation_id, type(exc).__name__)
        return _not_applied(
            "The goal could not be created; no effect was committed")

    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_CREATE, target_id=goal_id,
        target_workspace_id=authority["workspace_id"],
        request_digest=request_digest, prior_digest="",
        result_digest=_goal_material_digest(goal), actor=authority)
    audit_row = _audit_row(
        expected=expected, actor=authority, description="Goal created")
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (snapshot := _load_goal_snapshot(
                db, authority["workspace_id"], goal_id)) is not None
            and _goal_material_digest(
                snapshot[0], sql_null=snapshot[1])
            == expected["result_digest"]),
        success_data=success_data(goal), operation_id=operation_id)


def set_utility_target(
    db: Session, *, actor: Any, workspace_id: str, tenant_id: str,
    goal_id: str, target: Dict[str, Any],
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Attach an explicit utility target under actor and target CAS."""
    authority = _resolve_actor(db, actor)
    if not authority.get("ok"):
        return _actor_refusal(authority)
    scope_conflict = _bind_intended_scope(
        authority, workspace_id=workspace_id, tenant_id=tenant_id)
    if scope_conflict is not None:
        return scope_conflict
    refusal = _require_role(authority, UserRole.TEAM_LEAD)
    if refusal is not None:
        return refusal
    try:
        normalized = normalize_utility_target(target)
    except ValueError as exc:
        return _refused(
            str(exc), http_status=422, error_code="VALIDATION_ERROR",
            field="utility_target")
    try:
        operation_id = _operation_id("utility:set", operation_id)
    except ValueError as exc:
        return _refused(
            str(exc), http_status=422, error_code="VALIDATION_ERROR",
            field="operation_id")

    request_digest = _request_digest(
        _ACTION_UTILITY_SET, authority["workspace_id"],
        {"goal_id": str(goal_id), "utility_target": normalized})
    expected_base = {
        "operation_id": operation_id,
        "schema": WRITE_SCHEMA,
        "action": _ACTION_UTILITY_SET,
        "event_type": AuditEventType.UPDATE.value,
        "target_id": str(goal_id),
        "request_digest": request_digest,
        "actor_id": authority["id"],
        "actor_role": authority["role"],
        "tenant_id": authority["tenant_id"],
        "actor_workspace_id": authority["workspace_id"],
    }

    def success_data(goal: GoalObjective) -> Dict[str, Any]:
        return _goal_utility_data(goal)

    replay = _replay(
        db, operation_id, expected_base,
        success_data=success_data)
    if replay is not None:
        return replay

    snapshot = _load_goal_snapshot(db, authority["workspace_id"], goal_id)
    if snapshot is None:
        return _refused(
            f"goal {goal_id} not found", http_status=404,
            error_code="NOT_FOUND")
    goal, metadata_is_sql_null = snapshot
    prior_metadata = _read_prior_metadata(
        goal, sql_null=metadata_is_sql_null)
    if prior_metadata is not None and not isinstance(prior_metadata, dict):
        return _conflict(
            "goal metadata is unreadable; refresh and retry",
            code="STALE_TARGET")
    prior_target = (
        prior_metadata.get("utility_target")
        if isinstance(prior_metadata, dict) else None)
    if prior_target == normalized:
        return _no_change(
            _goal_utility_data(goal),
            "The goal already carries that utility target")
    result_metadata = (
        dict(prior_metadata) if isinstance(prior_metadata, dict) else {})
    result_metadata["utility_target"] = normalized
    prior_digest = _metadata_digest(
        prior_metadata, sql_null=metadata_is_sql_null)
    result_digest = _metadata_digest(result_metadata)
    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_UTILITY_SET,
        target_id=str(goal.id),
        target_workspace_id=authority["workspace_id"],
        request_digest=request_digest, prior_digest=prior_digest,
        result_digest=result_digest, actor=authority)

    if not _claim_actor(db, authority):
        db.rollback()
        return _conflict(
            "authorization or workspace changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    try:
        updated = db.execute(
            update(GoalObjective)
            .where(
                GoalObjective.id == str(goal.id),
                GoalObjective.workspace_id == authority["workspace_id"],
                _metadata_cas_condition(
                    prior_metadata, sql_null=metadata_is_sql_null),
            )
            .values(metadata_json=result_metadata))
        if updated.rowcount != 1:
            db.rollback()
            return _conflict(
                "goal metadata changed; refresh and retry",
                code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected_base,
            success_data=success_data)
        return replay or _conflict(
            "goal utility target conflicts with current state",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "goal utility set failed before commit: operation_id=%s "
            "target=%s error_class=%s", operation_id, goal_id,
            type(exc).__name__)
        return _not_applied(
            "The utility target could not be stored; no effect was committed")

    audit_row = _audit_row(
        expected=expected, actor=authority,
        description="Goal utility target set")
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (snapshot := _load_goal_snapshot(
                db, authority["workspace_id"], str(goal_id))) is not None
            and _metadata_digest(
                snapshot[0].metadata_json, sql_null=snapshot[1])
            == result_digest),
        success_data={"goal_id": str(goal_id),
                      "utility_target": normalized},
        operation_id=operation_id)


def clear_utility_target(
    db: Session, *, actor: Any, workspace_id: str, tenant_id: str,
    goal_id: str, operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Clear the utility target under actor and target CAS."""
    authority = _resolve_actor(db, actor)
    if not authority.get("ok"):
        return _actor_refusal(authority)
    scope_conflict = _bind_intended_scope(
        authority, workspace_id=workspace_id, tenant_id=tenant_id)
    if scope_conflict is not None:
        return scope_conflict
    refusal = _require_role(authority, UserRole.TEAM_LEAD)
    if refusal is not None:
        return refusal
    try:
        operation_id = _operation_id("utility:clear", operation_id)
    except ValueError as exc:
        return _refused(
            str(exc), http_status=422, error_code="VALIDATION_ERROR",
            field="operation_id")

    request_digest = _request_digest(
        _ACTION_UTILITY_CLEAR, authority["workspace_id"],
        {"goal_id": str(goal_id)})
    expected_base = {
        "operation_id": operation_id,
        "schema": WRITE_SCHEMA,
        "action": _ACTION_UTILITY_CLEAR,
        "event_type": AuditEventType.UPDATE.value,
        "target_id": str(goal_id),
        "request_digest": request_digest,
        "actor_id": authority["id"],
        "actor_role": authority["role"],
        "tenant_id": authority["tenant_id"],
        "actor_workspace_id": authority["workspace_id"],
    }

    def success_data(goal: GoalObjective) -> Dict[str, Any]:
        return _goal_utility_data(goal)

    replay = _replay(
        db, operation_id, expected_base,
        success_data=success_data)
    if replay is not None:
        return replay

    snapshot = _load_goal_snapshot(db, authority["workspace_id"], goal_id)
    if snapshot is None:
        return _refused(
            f"goal {goal_id} not found", http_status=404,
            error_code="NOT_FOUND")
    goal, metadata_is_sql_null = snapshot
    prior_metadata = _read_prior_metadata(
        goal, sql_null=metadata_is_sql_null)
    if prior_metadata is not None and not isinstance(prior_metadata, dict):
        return _conflict(
            "goal metadata is unreadable; refresh and retry",
            code="STALE_TARGET")
    if prior_metadata is None or "utility_target" not in prior_metadata:
        return _no_change(
            _goal_utility_data(goal),
            "The goal has no utility target to clear")
    result_metadata = dict(prior_metadata)
    result_metadata.pop("utility_target", None)
    prior_digest = _metadata_digest(
        prior_metadata, sql_null=metadata_is_sql_null)
    result_digest = _metadata_digest(result_metadata)
    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_UTILITY_CLEAR,
        target_id=str(goal.id),
        target_workspace_id=authority["workspace_id"],
        request_digest=request_digest, prior_digest=prior_digest,
        result_digest=result_digest, actor=authority)

    if not _claim_actor(db, authority):
        db.rollback()
        return _conflict(
            "authorization or workspace changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    try:
        updated = db.execute(
            update(GoalObjective)
            .where(
                GoalObjective.id == str(goal.id),
                GoalObjective.workspace_id == authority["workspace_id"],
                _metadata_cas_condition(
                    prior_metadata, sql_null=metadata_is_sql_null),
            )
            .values(metadata_json=result_metadata))
        if updated.rowcount != 1:
            db.rollback()
            return _conflict(
                "goal metadata changed; refresh and retry",
                code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected_base,
            success_data=success_data)
        return replay or _conflict(
            "goal utility target conflicts with current state",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "goal utility clear failed before commit: operation_id=%s "
            "target=%s error_class=%s", operation_id, goal_id,
            type(exc).__name__)
        return _not_applied(
            "The utility target could not be cleared; no effect was committed")

    audit_row = _audit_row(
        expected=expected, actor=authority,
        description="Goal utility target cleared")
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (snapshot := _load_goal_snapshot(
                db, authority["workspace_id"], str(goal_id))) is not None
            and _metadata_digest(
                snapshot[0].metadata_json, sql_null=snapshot[1])
            == result_digest),
        success_data={"goal_id": str(goal_id), "utility_target": None},
        operation_id=operation_id)
