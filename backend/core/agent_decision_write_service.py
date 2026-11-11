"""Verified agent update/promote/delete decisions.

The two routes previously loaded an ``AgentRegistry`` row by id and committed
the requested fields/status directly. Any caller with the permission could
therefore mutate an agent in another tenant/workspace, with no exact prior
material binding, audit receipt or replay protection.

This module makes the decision explicit:

- the current User row is resolved and its status/is_active/role/raw tenant/
  workspace are bound in a guarded no-op UPDATE in the decision transaction;
- the target agent is resolved under the caller's tenant/workspace policy;
- the exact prior agent material is bound in guarded UPDATE DML;
- one safe ``AuditLog`` receipt commits in the same transaction;
- same-operation replay is idempotent, changed material conflicts, a later
  revision is unverified, a confirmed rollback is ``effect=none`` and a lost
  confirmation is ``effect_unknown``.

No raw configuration, capability list, secret or SQL parameter is stored in the
receipt or logs.
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

from sqlalchemy import null, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.auth import SECRET_KEY
from core.governance_tier import canonical_governance_tier
from core.models import (
    AgentJob,
    AgentJobStatus,
    AgentRegistry,
    AgentStatus,
    NEW_AGENT_CONFIDENCE,
    AuditEventType,
    AuditLog,
    SecurityLevel,
    User,
    UserRole,
)
from core.personal_scope import resolve_tenant_id, resolve_workspace_id
from core.security.rbac import role_level

logger = logging.getLogger(__name__)

REVIEW_SCHEMA = "atom-agent-decision-1"
_OPERATION_PREFIX = "agent"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_ACTION_UPDATE = "agent_updated"
_ACTION_PROMOTE = "agent_promoted"
_ACTION_DELETE = "agent_deleted"
_ACTION_RUN = "agent_run_admitted"
_ACTION_REPLACE = "agent_replaced"
_ACTION_STOP = "agent_stopped"
_ACTION_CREATE = "agent_created"


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
        "error_code": "AGENT_TRANSACTION_ROLLED_BACK",
        "http_status": 409,
        "verification": {
            "status": "refused",
            "effect": "none",
            "replay": "safe_after_refresh",
        },
    }


def _state_unavailable(operation_id: str, target_id: str) -> Dict[str, Any]:
    """Pre-dispatch task-state read failed; no cancellation was attempted."""
    return {
        "status": "state_unavailable",
        "data": None,
        "error": (
            "The agent task state is unavailable; no cancellation was "
            "attempted. Refresh the authoritative state and retry."
        ),
        "error_code": "AGENT_TASK_STATE_UNAVAILABLE",
        "http_status": 503,
        "operation_id": operation_id,
        "target_id": target_id,
        "verification": {
            "status": "unavailable",
            "effect": "none",
            "replay": "safe_after_refresh",
        },
    }


def _committed_unverified(
    operation_id: str, audit_state: Dict[str, Any], *, target_id: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "status": "committed_unverified",
        "data": data,
        "message": (
            "The agent decision committed but its audit/target readback did "
            "not verify. Reconcile the original operation."),
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
            "The agent decision may have committed, but confirmation was "
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
    result["verification"] = {
        "status": "no_change",
        "effect": "none",
    }
    return {"status": "no_change", "data": result, "message": message}


# ---------------------------------------------------------------------------
# Sessions / principal / scope
# ---------------------------------------------------------------------------

def _fresh_session(db: Session) -> Session:
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=db.get_bind())()


def _actor_refusal(actor: Dict[str, Any]) -> Dict[str, Any]:
    return _refused(
        str(actor.get("message") or "AGENT_MANAGE authority is required"),
        http_status=int(actor.get("http_status") or 403),
        error_code=str(actor.get("error_code") or "AUTHORITY_REQUIRED"),
    )


def _resolve_actor(
    db: Session, actor: Any, *,
    minimum_role: UserRole = UserRole.WORKSPACE_ADMIN,
    authority_label: str = "AGENT_MANAGE",
) -> Dict[str, Any]:
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
            if role_level(row.role) < role_level(minimum_role):
                return {
                    "ok": False, "http_status": 403,
                    "error_code": "AUTHORITY_REQUIRED",
                    "message": (
                        f"{authority_label} authority is required"),
                }
            return {
                "ok": True,
                "id": actor_id,
                "email": str(row.email or ""),
                "role": str(row.role or ""),
                "status": str(row.status or ""),
                "tenant_id": str(resolve_tenant_id(row)),
                "workspace_id": str(resolve_workspace_id(row)),
                "raw_tenant_id": row.tenant_id,
                "raw_workspace_id": row.workspace_id,
            }
    except Exception as exc:  # noqa: BLE001 — unreadable authority fails closed
        logger.warning(
            "agent authority read failed: actor=%s error_class=%s",
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
            _exact(User.workspace_id, actor["raw_workspace_id"]),
        )
        .values(updated_at=User.updated_at)
    )
    return result.rowcount == 1


def _load_agent(db: Session, agent_id: str) -> Optional[AgentRegistry]:
    with _fresh_session(db) as fresh:
        return fresh.query(AgentRegistry).filter(
            AgentRegistry.id == str(agent_id)).populate_existing().first()


def _agent_visible(actor: Dict[str, Any], agent: AgentRegistry) -> bool:
    """Apply the bounded tenant/workspace target policy.

    - A real foreign tenant is never visible.
    - Legacy tenant-less rows remain visible to a tenant-bound actor.
    - A workspace-bound actor below ADMIN sees only the same workspace or a
      legacy workspace-less row; ADMIN+ may cross workspaces inside the tenant.
    - An unscoped/platform actor keeps the existing global-legacy policy.
    """
    if actor["raw_tenant_id"] is not None:
        if agent.tenant_id is not None and str(agent.tenant_id) != str(
                actor["raw_tenant_id"]):
            return False
    if role_level(actor["role"]) < role_level(UserRole.ADMIN):
        actor_workspace = actor["raw_workspace_id"]
        if (
            actor_workspace is not None
            and agent.workspace_id is not None
            and str(agent.workspace_id) != str(actor_workspace)
        ):
            return False
    return True


def _public_agent(agent: AgentRegistry) -> Dict[str, Any]:
    return {
        "id": str(agent.id),
        "name": str(agent.name or ""),
        "description": agent.description,
        "capabilities": list(agent.capabilities or []),
        "promotion_episode_floor": agent.promotion_episode_floor,
        "status": str(agent.status or ""),
    }


def _normalize_changes(changes: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    if changes.get("name") is not None:
        normalized["name"] = str(changes["name"])
    if changes.get("description") is not None:
        normalized["description"] = str(changes["description"])
    if changes.get("capabilities") is not None:
        normalized["capabilities"] = list(changes["capabilities"] or [])
    if changes.get("promotion_episode_floor") is not None:
        normalized["promotion_episode_floor"] = max(
            1, int(changes["promotion_episode_floor"]))
    return normalized


def _change_material(changes: Dict[str, Any]) -> Dict[str, Any]:
    material: Dict[str, Any] = {}
    if "name" in changes:
        material["name"] = changes["name"]
    if "description" in changes:
        material["description"] = changes["description"]
    if "capabilities" in changes:
        material["capabilities_digest"] = _fingerprint(
            "agent-capabilities", _canonical(changes["capabilities"]))
    if "promotion_episode_floor" in changes:
        material["promotion_episode_floor"] = changes[
            "promotion_episode_floor"]
    return material


def caller_work_pending(db: Session, owned: tuple = ()) -> bool:
    """True when the caller's session holds work outside ``owned``.

    Shared gate writers must never commit or roll back another caller's
    pending work. They refuse/return unresolved instead; the owner of the
    transaction decides when to commit. ``owned`` excludes only unflushed
    ORM objects; flushed writes are conservatively caller-owned because the
    transaction marker does not attribute individual rows.
    """
    from sqlalchemy.orm import Session as SASession

    if not isinstance(db, SASession):
        # Unit tests sometimes pass a Mock session; there is no real caller
        # transaction to preserve.
        return False
    info = getattr(db, "info", None)
    if not isinstance(info, dict):
        # Mock(spec=Session) passes isinstance but has no real Session.info.
        return False
    if info.get("atom_uncommitted_writes"):
        # A prior flush already moved caller work into the transaction;
        # Session.dirty is empty but committing would still persist it.
        return True
    owned_ids = {id(obj) for obj in owned}
    pending = list(db.new) + list(db.dirty) + list(db.deleted)
    return any(id(obj) not in owned_ids for obj in pending)


def _state_material(
    agent: AgentRegistry, *, status: Optional[str] = None,
    changes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    material = {
        "id": str(agent.id),
        "tenant_id": (
            None if agent.tenant_id is None else str(agent.tenant_id)),
        "workspace_id": (
            None if agent.workspace_id is None
            else str(agent.workspace_id)),
        "name": str(agent.name or ""),
        "description": (
            None if agent.description is None else str(agent.description)),
        "capabilities_digest": _fingerprint(
            "agent-capabilities", _canonical(agent.capabilities or [])),
        "promotion_episode_floor": agent.promotion_episode_floor,
        "status": str(status if status is not None else agent.status or ""),
    }
    if changes:
        material.update(changes)
    return material


def _promotion_state_material(agent: AgentRegistry) -> Dict[str, Any]:
    """One result snapshot for promotion commit and exact-operation replay."""
    material = _state_material(agent)
    material["last_exam_id"] = agent.last_exam_id
    material["promotion_count"] = int(getattr(agent, "promotion_count", 0) or 0)
    return material


def _state_digest(material: Dict[str, Any]) -> str:
    return _fingerprint("agent-state", _canonical(material))


def _request_digest(
    action: str, agent_id: str, changes: Optional[Dict[str, Any]] = None,
) -> str:
    return _fingerprint(
        "agent-request", str(action), str(agent_id),
        _canonical(changes or {}))


def _exact(column, value: Any):
    if value is None:
        return column.is_(None)
    return column == value


def _agent_predicates(agent: AgentRegistry, prior_status: str):
    return [
        AgentRegistry.id == str(agent.id),
        _exact(AgentRegistry.tenant_id, agent.tenant_id),
        _exact(AgentRegistry.workspace_id, agent.workspace_id),
        AgentRegistry.name == str(agent.name or ""),
        _exact(AgentRegistry.description, agent.description),
        AgentRegistry.capabilities == agent.capabilities,
        _exact(AgentRegistry.promotion_episode_floor,
               agent.promotion_episode_floor),
        _exact(AgentRegistry.last_exam_id, agent.last_exam_id),
        _exact(AgentRegistry.exam_eligible_at, agent.exam_eligible_at),
        AgentRegistry.status == str(prior_status),
    ]


def _changes_match(agent: AgentRegistry, changes: Dict[str, Any]) -> bool:
    for key, value in changes.items():
        if key == "capabilities":
            if list(agent.capabilities or []) != list(value or []):
                return False
        else:
            if getattr(agent, key, None) != value:
                return False
    return True


# ---------------------------------------------------------------------------
# Audit ledger
# ---------------------------------------------------------------------------

def _audit_expected(
    *, operation_id: str, action: str, event_type: str,
    agent: AgentRegistry, prior_status: str, result_status: str,
    request_digest: str, prior_digest: str, result_digest: str,
    actor: Dict[str, Any], extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    expected = {
        "operation_id": str(operation_id),
        "schema": REVIEW_SCHEMA,
        "action": str(action),
        "event_type": str(event_type),
        "target_id": str(agent.id),
        "target_tenant_id": (
            None if agent.tenant_id is None else str(agent.tenant_id)),
        "target_workspace_id": (
            None if agent.workspace_id is None
            else str(agent.workspace_id)),
        "agent_name": str(agent.name or ""),
        "prior_status": str(prior_status),
        "result_status": str(result_status),
        "request_digest": str(request_digest),
        "prior_digest": str(prior_digest),
        "result_digest": str(result_digest),
        "actor_id": actor["id"],
        "actor_role": actor["role"],
        "tenant_id": actor["tenant_id"],
        "resource": f"agent:{agent.id}",
    }
    if extra:
        # Audit metadata is durable JSON. Normalize with the file's canonical
        # semantics (_canonical: sorted keys, default=str) so non-JSON types
        # in decision material — e.g. the qualification assessment's
        # policy_row_updated_at datetime — serialize at _audit_row and match
        # the JSON-parsed material during _verify_audit read-back.
        expected["extra"] = json.loads(_canonical(extra))
    return expected


def _audit_row(
    *, expected: Dict[str, Any], actor: Dict[str, Any],
) -> AuditLog:
    metadata = {
        "schema": expected["schema"],
        "operation_id": expected["operation_id"],
        "action": expected["action"],
        "event_type": expected["event_type"],
        "target_id": expected["target_id"],
        "target_tenant_id": expected["target_tenant_id"],
        "target_workspace_id": expected["target_workspace_id"],
        "agent_name": expected["agent_name"],
        "prior_status": expected["prior_status"],
        "result_status": expected["result_status"],
        "request_digest": expected["request_digest"],
        "prior_digest": expected["prior_digest"],
        "result_digest": expected["result_digest"],
        "actor_id": expected["actor_id"],
        "actor_role": expected["actor_role"],
        "tenant_id": expected["tenant_id"],
    }
    if expected.get("extra"):
        metadata["extra"] = expected["extra"]
    return AuditLog(
        id=expected["operation_id"],
        event_type=expected["event_type"],
        security_level=SecurityLevel.HIGH.value,
        threat_level="none",
        user_id=expected["actor_id"],
        user_email=actor["email"],
        tenant_id=expected["tenant_id"],
        workspace_id=None,
        resource=expected["resource"],
        action=expected["action"],
        description="Agent decision recorded",
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
                "target_id", "agent_name", "prior_status",
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
            for key in ("target_tenant_id", "target_workspace_id"):
                if key not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                value = metadata[key]
                if value is not None and not isinstance(value, str):
                    return {"status": "refuted", "audit_id": audit_id}
                if value != expected[key]:
                    return {"status": "refuted", "audit_id": audit_id}
            if expected.get("extra"):
                if metadata.get("extra") != expected["extra"]:
                    return {"status": "refuted", "audit_id": audit_id}
            return {"status": "verified", "audit_id": audit_id}
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "agent audit read-back failed: operation_id=%s error_class=%s",
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
        "target_tenant_id": metadata.get("target_tenant_id"),
        "target_workspace_id": metadata.get("target_workspace_id"),
        "agent_name": metadata.get("agent_name"),
        "prior_status": metadata.get("prior_status"),
        "result_status": metadata.get("result_status"),
        "request_digest": metadata.get("request_digest"),
        "prior_digest": metadata.get("prior_digest"),
        "result_digest": metadata.get("result_digest"),
        "actor_id": metadata.get("actor_id"),
        "actor_role": metadata.get("actor_role"),
        "tenant_id": metadata.get("tenant_id"),
        "resource": f"agent:{metadata.get('target_id')}",
        "extra": metadata.get("extra") or {},
    }


def _replay(
    db: Session, operation_id: str, expected: Dict[str, Any],
    *, authority: Dict[str, Any],
    target_check: Optional[Callable[[Dict[str, Any]], bool]] = None,
    success_data: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    authority_check: Optional[Callable[[Dict[str, Any]], bool]] = None,
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
            if (
                authority_check is not None
                and not authority_check(audit_expected)
            ):
                return _conflict(
                    "agent authority changed; refresh and retry",
                    code="AUTHORITY_CHANGED")
            audit_state = _verify_audit(db, audit_expected)
            if target_check is not None:
                target_ok = bool(target_check(audit_expected))
                data = (
                    success_data(audit_expected)
                    if success_data is not None
                    else {
                        "agent_id": audit_expected["target_id"],
                        "agent_status": audit_expected["result_status"],
                    })
            else:
                current = _load_agent(
                    db, str(metadata.get("target_id") or ""))
                target_ok = (
                    current is not None
                    and _state_digest(
                        _promotion_state_material(current)
                        if audit_expected["action"] == _ACTION_PROMOTE
                        else _state_material(current))
                    == audit_expected["result_digest"]
                )
                data = (
                    _public_agent(current) if current is not None
                    else {
                        "agent_id": audit_expected["target_id"],
                        "agent_status": audit_expected["result_status"],
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
                    "message": "This agent decision was already applied.",
                    "operation_id": operation_id,
                    "audit_id": audit_expected["operation_id"],
                    "target_id": audit_expected["target_id"],
                }
            return _committed_unverified(
                operation_id, audit_state,
                target_id=audit_expected["target_id"])
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "agent replay read failed: operation_id=%s error_class=%s",
            operation_id, type(exc).__name__)
        return _committed_unverified(
            operation_id, {"status": "unavailable"},
            target_id=str(expected.get("target_id") or ""))


def _commit_and_verify(
    db: Session, *, expected: Dict[str, Any], audit_row: AuditLog,
    target_check: Callable[[], bool], success_data: Dict[str, Any],
    authority: Dict[str, Any],
    replay_check: Optional[Callable[[Dict[str, Any]], bool]] = None,
    replay_data: Optional[
        Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    authority_check: Optional[Callable[[Dict[str, Any]], bool]] = None,
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
            target_check=replay_check, success_data=replay_data,
            authority_check=authority_check)
        if replay is not None:
            return replay
        return _not_applied(
            "The agent decision was rolled back; no effect was applied")
    except Exception as exc:  # noqa: BLE001 — commit outcome unknown
        db.rollback()
        logger.error(
            "agent decision outcome unknown: operation_id=%s target=%s "
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
            "message": "Agent decision committed and verified.",
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": target_id,
        }
    return _committed_unverified(
        operation_id, audit_state, target_id=target_id)


# ---------------------------------------------------------------------------
# Public decisions
# ---------------------------------------------------------------------------

def _create_config_digest(value: Any) -> str:
    return _fingerprint("agent-configuration", _canonical(value))


def _create_schedule_digest(value: Any) -> str:
    return _fingerprint("agent-schedule", _canonical(value))


def _same_scalar(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return str(a) == str(b)


def _same_float(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is None and b is None
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return False


def _create_parent_receipt(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(snapshot.get("id") or ""),
        "tenant_id": snapshot.get("tenant_id"),
        "workspace_id": snapshot.get("workspace_id"),
        "status": snapshot.get("status"),
        "confidence_score": (
            None if snapshot.get("confidence_score") is None
            else float(snapshot["confidence_score"])),
        "enabled": snapshot.get("enabled"),
        "last_exam_id": snapshot.get("last_exam_id"),
        "configuration_digest": _create_config_digest(
            snapshot.get("configuration")),
        "capabilities_digest": _fingerprint(
            "agent-capabilities",
            _canonical(snapshot.get("capabilities") or [])),
    }


def _claim_parent_authority(
    db: Session, snapshot: Dict[str, Any],
) -> bool:
    """Conditionally claim the exact acting-agent material in this transaction."""
    result = db.execute(
        update(AgentRegistry)
        .where(
            AgentRegistry.id == str(snapshot.get("id") or ""),
            _exact(AgentRegistry.tenant_id, snapshot.get("tenant_id")),
            _exact(AgentRegistry.workspace_id, snapshot.get("workspace_id")),
            _exact(AgentRegistry.status, snapshot.get("status")),
            _exact(
                AgentRegistry.confidence_score,
                snapshot.get("confidence_score")),
            _exact(AgentRegistry.enabled, snapshot.get("enabled")),
            _exact(AgentRegistry.last_exam_id, snapshot.get("last_exam_id")),
            _exact(AgentRegistry.capabilities, snapshot.get("capabilities")),
            _exact(AgentRegistry.configuration, snapshot.get("configuration")),
        )
        .values(updated_at=AgentRegistry.updated_at)
    )
    return result.rowcount == 1


def _parent_authority_matches(
    db: Session, receipt: Dict[str, Any],
) -> bool:
    if not isinstance(receipt, dict) or not receipt.get("id"):
        return False
    with _fresh_session(db) as fresh:
        row = (
            fresh.query(AgentRegistry)
            .filter(AgentRegistry.id == str(receipt["id"]))
            .populate_existing()
            .first()
        )
        if row is None:
            return False
        return (
            _same_scalar(row.tenant_id, receipt.get("tenant_id"))
            and _same_scalar(row.workspace_id, receipt.get("workspace_id"))
            and _same_scalar(row.status, receipt.get("status"))
            and _same_float(
                row.confidence_score, receipt.get("confidence_score"))
            and _same_scalar(row.enabled, receipt.get("enabled"))
            and _same_scalar(row.last_exam_id, receipt.get("last_exam_id"))
            and _create_config_digest(_stored_json_value(row.configuration))
            == receipt.get("configuration_digest")
            and _fingerprint(
                "agent-capabilities",
                _canonical(row.capabilities or []))
            == receipt.get("capabilities_digest")
        )


def _create_authority_check(
    db: Session, actor_snapshot: Dict[str, Any],
    parent_authority: Optional[Dict[str, Any]],
):
    def check(expected: Dict[str, Any]) -> bool:
        if str(actor_snapshot.get("workspace_id") or "") != str(
                expected.get("target_workspace_id") or ""):
            return False
        receipt = (expected.get("extra") or {}).get("parent_authority")
        if parent_authority is not None and not isinstance(receipt, dict):
            return False
        if receipt is not None:
            return _parent_authority_matches(db, receipt)
        return True

    return check


def _stored_json_value(value: Any) -> Any:
    """Return the physical JSON material, preserving an explicit NULL.

    ``create_agent`` inserts ``null()`` for a request that omitted the field
    so NULL and ``{}`` stay distinct. Before flush the ORM attribute is a
    SQL ``Null`` expression; after readback it is ``None``.
    """
    from sqlalchemy.sql.elements import Null

    if value is None or isinstance(value, Null):
        return None
    return value


def _create_state_material(
    agent: AgentRegistry, *, extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    material = {
        "id": str(agent.id),
        "tenant_id": (
            None if agent.tenant_id is None else str(agent.tenant_id)),
        "workspace_id": (
            None if agent.workspace_id is None
            else str(agent.workspace_id)),
        "name": str(agent.name or ""),
        "description": (
            None if agent.description is None else str(agent.description)),
        "category": str(agent.category or ""),
        "configuration_digest": _create_config_digest(
            _stored_json_value(agent.configuration)),
        "schedule_digest": _create_schedule_digest(
            _stored_json_value(agent.schedule_config)),
        "module_path": str(agent.module_path or ""),
        "class_name": str(agent.class_name or ""),
        "status": str(agent.status or ""),
        "confidence_score": float(agent.confidence_score or 0.0),
    }
    if extra:
        material.update(extra)
    return material


def _create_target_check(db: Session):
    def check(expected: Dict[str, Any]) -> bool:
        current = _load_agent(db, str(expected.get("target_id") or ""))
        audit_extra = expected.get("extra") or {}
        state_extra = {
            key: audit_extra[key]
            for key in ("user_id", "parent_agent_id", "capabilities_digest")
            if key in audit_extra
        }
        return (
            current is not None
            and _state_digest(_create_state_material(
                current, extra=state_extra))
            == expected["result_digest"])

    return check


def _create_success_data(expected: Dict[str, Any]) -> Dict[str, Any]:
    extra = expected.get("extra") or {}
    return {
        "agent_id": str(expected.get("target_id") or ""),
        "agent_status": str(expected.get("result_status") or ""),
        "agent_name": str(expected.get("agent_name") or ""),
        "category": str(extra.get("category") or ""),
        "tenant_id": expected.get("target_tenant_id"),
        "workspace_id": expected.get("target_workspace_id"),
    }


def create_agent(
    db: Session, *, actor: Any, name: str, category: str,
    description: Optional[str] = None,
    configuration: Optional[Dict[str, Any]] = None,
    schedule_config: Optional[Dict[str, Any]] = None,
    confidence_score: Optional[float] = None,
    user_id: Optional[str] = None,
    parent_agent_id: Optional[str] = None,
    parent_authority: Optional[Dict[str, Any]] = None,
    capabilities: Optional[Any] = None,
    minimum_role: UserRole = UserRole.WORKSPACE_ADMIN,
    authority_label: str = "AGENT_MANAGE",
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create one STUDENT agent with an exact actor/material receipt.

    The public create alias previously inserted directly with no operation
    identity, audit receipt, replay, or commit-time actor claim. This uses the
    same resolved-actor/claim/AuditLog pattern as the other agent decisions.
    A create remains a create (no name-based upsert or uniqueness policy).
    """
    actor_snapshot = _resolve_actor(
        db, actor, minimum_role=minimum_role,
        authority_label=authority_label)
    if not actor_snapshot.get("ok"):
        return _actor_refusal(actor_snapshot)
    try:
        operation_id = _operation_id("create", operation_id)
    except ValueError as exc:
        return _refused(
            str(exc), http_status=422, error_code="VALIDATION_ERROR",
            field="operation_id")

    try:
        effective_confidence = (
            NEW_AGENT_CONFIDENCE if confidence_score is None
            else float(confidence_score))
    except (TypeError, ValueError):
        return _refused(
            "confidence_score must be numeric", http_status=422,
            error_code="VALIDATION_ERROR", field="confidence_score")
    if not (0.0 <= effective_confidence < 0.5):
        return _refused(
            "confidence_score must be below the INTERN qualification floor",
            http_status=422, error_code="VALIDATION_ERROR",
            field="confidence_score")

    if parent_authority is not None:
        snapshot_id = str(parent_authority.get("id") or "")
        if not snapshot_id:
            return _refused(
                "parent authority snapshot is missing id",
                http_status=422, error_code="VALIDATION_ERROR",
                field="parent_authority")
        if parent_agent_id is not None and str(parent_agent_id) != snapshot_id:
            return _refused(
                "parent authority snapshot does not match parent_agent_id",
                http_status=422, error_code="VALIDATION_ERROR",
                field="parent_authority")
        parent_agent_id = snapshot_id

    target_id = str(uuid.uuid5(uuid.NAMESPACE_URL, operation_id))
    configuration_digest = _create_config_digest(configuration)
    schedule_digest = _create_schedule_digest(schedule_config)
    state_extra: Dict[str, Any] = {}
    if user_id is not None:
        state_extra["user_id"] = str(user_id)
    if parent_agent_id is not None:
        state_extra["parent_agent_id"] = str(parent_agent_id)
    if capabilities is not None:
        state_extra["capabilities_digest"] = _fingerprint(
            "agent-capabilities", _canonical(capabilities))
    request_material = {
        "name": str(name or ""),
        "category": str(category or ""),
        "description": None if description is None else str(description),
        "configuration_digest": configuration_digest,
        "schedule_config_digest": schedule_digest,
        "status": AgentStatus.STUDENT.value,
        "confidence_score": effective_confidence,
        "module_path": "core.generic_agent",
        "class_name": "GenericAgent",
        **state_extra,
    }
    parent_receipt = (
        _create_parent_receipt(parent_authority)
        if parent_authority is not None else None)
    request_digest = _request_digest(
        _ACTION_CREATE, target_id, request_material)
    authority_check = _create_authority_check(
        db, actor_snapshot, parent_authority)
    expected_base = {
        "operation_id": operation_id,
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_CREATE,
        "event_type": AuditEventType.CREATE.value,
        "target_id": target_id,
        "request_digest": request_digest,
        "actor_id": actor_snapshot["id"],
    }
    replay = _replay(
        db, operation_id, expected_base, authority=actor_snapshot,
        target_check=_create_target_check(db),
        success_data=_create_success_data,
        authority_check=authority_check)
    if replay is not None:
        return replay

    if not _claim_actor(db, actor_snapshot):
        db.rollback()
        return _conflict(
            "actor authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")
    if (
        parent_authority is not None
        and not _claim_parent_authority(db, parent_authority)
    ):
        db.rollback()
        return _conflict(
            "acting agent authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    agent = AgentRegistry(
        id=target_id,
        name=str(name or ""),
        description=description,
        category=str(category or ""),
        configuration=null() if configuration is None else configuration,
        schedule_config=(
            null() if schedule_config is None else schedule_config),
        module_path="core.generic_agent",
        class_name="GenericAgent",
        status=AgentStatus.STUDENT.value,
        confidence_score=effective_confidence,
        user_id=user_id,
        parent_agent_id=parent_agent_id,
        capabilities=capabilities,
        workspace_id=actor_snapshot["workspace_id"],
        tenant_id=actor_snapshot["tenant_id"],
    )
    db.add(agent)
    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_CREATE,
        event_type=AuditEventType.CREATE.value, agent=agent,
        prior_status="", result_status=AgentStatus.STUDENT.value,
        request_digest=request_digest,
        prior_digest=_state_digest({"absent": True}),
        result_digest=_state_digest(_create_state_material(
            agent, extra=state_extra)),
        actor=actor_snapshot,
        extra={
            "category": str(category or ""),
            "module_path": "core.generic_agent",
            "class_name": "GenericAgent",
            "configuration_digest": configuration_digest,
            "schedule_config_digest": schedule_digest,
            **state_extra,
            **({"parent_authority": parent_receipt}
               if parent_receipt is not None else {}),
        })

    return _commit_and_verify(
        db, expected=expected, audit_row=_audit_row(
            expected=expected, actor=actor_snapshot),
        target_check=lambda: _create_target_check(db)(expected),
        success_data=_create_success_data(expected),
        authority=actor_snapshot,
        replay_check=_create_target_check(db),
        replay_data=_create_success_data,
        authority_check=authority_check,
    )


def update_agent(
    db: Session, *, actor: Any, agent_id: str, changes: Dict[str, Any],
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    actor_snapshot = _resolve_actor(db, actor)
    if not actor_snapshot.get("ok"):
        return _actor_refusal(actor_snapshot)
    try:
        operation_id = _operation_id("update", operation_id)
    except ValueError as exc:
        return _refused(
            str(exc), http_status=422, error_code="VALIDATION_ERROR",
            field="operation_id")

    normalized = _normalize_changes(changes or {})
    request_digest = _request_digest(
        _ACTION_UPDATE, str(agent_id), _change_material(normalized))
    expected_base = {
        "operation_id": operation_id,
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_UPDATE,
        "event_type": AuditEventType.UPDATE.value,
        "target_id": str(agent_id),
        "request_digest": request_digest,
        "actor_id": actor_snapshot["id"],
    }
    replay = _replay(
        db, operation_id, expected_base, authority=actor_snapshot)
    if replay is not None:
        return replay

    agent = _load_agent(db, agent_id)
    if agent is None or not _agent_visible(actor_snapshot, agent):
        return _refused(
            f"Agent not found: {agent_id}", http_status=404,
            error_code="NOT_FOUND")
    if not normalized:
        return _no_change(_public_agent(agent), "No agent changes requested")
    if _changes_match(agent, normalized):
        return _no_change(_public_agent(agent), "Agent already matches request")

    prior_status = str(agent.status or "")
    prior_material = _state_material(agent)
    result_material = _state_material(agent, changes=_change_material(normalized))
    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_UPDATE,
        event_type=AuditEventType.UPDATE.value, agent=agent,
        prior_status=prior_status, result_status=prior_status,
        request_digest=request_digest,
        prior_digest=_state_digest(prior_material),
        result_digest=_state_digest(result_material),
        actor=actor_snapshot)

    if not _claim_actor(db, actor_snapshot):
        db.rollback()
        return _conflict(
            "reviewer authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    try:
        updated = db.execute(
            update(AgentRegistry)
            .where(*_agent_predicates(agent, prior_status))
            .values(**normalized))
        if updated.rowcount != 1:
            db.rollback()
            return _conflict(
                "agent material changed; refresh and retry",
                code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected, authority=actor_snapshot)
        return replay or _conflict(
            "agent decision conflicts with current state",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "agent update failed before commit: operation_id=%s target=%s "
            "error_class=%s", operation_id, agent_id,
            type(exc).__name__)
        return _not_applied(
            "The agent update could not be applied; no effect was committed")

    response_data = _public_agent(agent)
    response_data.update(normalized)
    audit_row = _audit_row(expected=expected, actor=actor_snapshot)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (now := _load_agent(db, agent_id)) is not None
            and _state_digest(_state_material(now))
            == expected["result_digest"]),
        success_data=response_data,
        authority=actor_snapshot)


def promote_agent(
    db: Session, *, actor: Any, agent_id: str,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    if caller_work_pending(db):
        return _not_applied(
            "Manual promotion refused: the caller transaction has unrelated "
            "pending work. Commit or roll it back first.")
    actor_snapshot = _resolve_actor(db, actor)
    if not actor_snapshot.get("ok"):
        return _actor_refusal(actor_snapshot)
    try:
        operation_id = _operation_id("promote", operation_id)
    except ValueError as exc:
        return _refused(
            str(exc), http_status=422, error_code="VALIDATION_ERROR",
            field="operation_id")

    request_digest = _request_digest(_ACTION_PROMOTE, str(agent_id))
    expected_base = {
        "operation_id": operation_id,
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_PROMOTE,
        "event_type": AuditEventType.UPDATE.value,
        "target_id": str(agent_id),
        "request_digest": request_digest,
        "actor_id": actor_snapshot["id"],
    }
    replay = _replay(
        db, operation_id, expected_base, authority=actor_snapshot)
    if replay is not None:
        return replay

    agent = _load_agent(db, agent_id)
    if agent is None or not _agent_visible(actor_snapshot, agent):
        return _refused(
            f"Agent not found: {agent_id}", http_status=404,
            error_code="NOT_FOUND")
    prior_status = str(agent.status or "")
    if prior_status == AgentStatus.AUTONOMOUS.value:
        return _no_change(
            {"agent_status": prior_status, "agent_id": str(agent.id)},
            "Agent is already autonomous")

    from core.agent_graduation_service import evaluate_qualification_gate

    qualification_gate = evaluate_qualification_gate(
        db, agent, "AUTONOMOUS", manual=True)
    if not qualification_gate.get("allowed"):
        return {
            "status": "unresolved",
            "assessment": qualification_gate,
            "error": "Capability qualification is unresolved for this manual promotion.",
            "error_code": "QUALIFICATION_REQUIRED",
            "http_status": 409,
            "verification": {"status": "refused", "effect": "none"},
        }
    receipt_id = (
        qualification_gate.get("receipt_id")
        if qualification_gate.get("state") == "valid"
        else agent.last_exam_id
    )
    new_promotion_count = int(getattr(agent, "promotion_count", 0) or 0) + 1

    result_status = AgentStatus.AUTONOMOUS.value
    prior_material = _promotion_state_material(agent)
    result_material = _state_material(agent, status=result_status)
    result_material["last_exam_id"] = receipt_id
    result_material["promotion_count"] = new_promotion_count
    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_PROMOTE,
        event_type=AuditEventType.UPDATE.value, agent=agent,
        prior_status=prior_status, result_status=result_status,
        request_digest=request_digest,
        prior_digest=_state_digest(prior_material),
        result_digest=_state_digest(result_material),
        actor=actor_snapshot,
        extra={"assessment": qualification_gate})

    if not _claim_actor(db, actor_snapshot):
        db.rollback()
        return _conflict(
            "reviewer authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    try:
        updated = db.execute(
            update(AgentRegistry)
            .where(*_agent_predicates(agent, prior_status))
            .values(
                status=result_status,
                last_exam_id=receipt_id,
                promotion_count=new_promotion_count,
                updated_at=datetime.now(timezone.utc),
            ))
        if updated.rowcount != 1:
            db.rollback()
            return _conflict(
                "agent material changed; refresh and retry",
                code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected, authority=actor_snapshot)
        return replay or _conflict(
            "agent decision conflicts with current state",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "agent promote failed before commit: operation_id=%s target=%s "
            "error_class=%s", operation_id, agent_id,
            type(exc).__name__)
        return _not_applied(
            "The agent promotion could not be applied; no effect was "
            "committed")

    from core.models import PromotionHistory

    history = PromotionHistory(
        id=str(uuid.uuid4()),
        agent_id=str(agent.id),
        tenant_id=resolve_tenant_id(agent),
        from_level=prior_status,
        to_level=result_status,
        promotion_type="manual",
        readiness_score=0.0,
        exam_id=receipt_id if qualification_gate.get("state") == "valid" else None,
        promoted_by=str(actor_snapshot["id"]),
        justification=(
            "manual owner promotion; assessment="
            f"{qualification_gate.get('state')}"),
        promoted_at=datetime.now(timezone.utc),
    )
    db.add(history)
    audit_row = _audit_row(expected=expected, actor=actor_snapshot)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (now := _load_agent(db, agent_id)) is not None
            and _state_digest(_promotion_state_material(now))
            == expected["result_digest"]),
        success_data={
            "agent_status": result_status,
            "agent_id": str(agent.id),
            "assessment": qualification_gate,
            "promotion_history_id": history.id,
        },
        authority=actor_snapshot)


# ---------------------------------------------------------------------------
# Delete decision
# ---------------------------------------------------------------------------

def _delete_agent_predicates(agent: AgentRegistry, prior_status: str):
    """Exact prior material for a delete claim.

    The shared update/promote predicates bind identity and review material.
    Delete additionally binds configuration and enabled because they decide
    the demo tombstone and the cleanup target.
    """
    return list(_agent_predicates(agent, prior_status)) + [
        _exact(AgentRegistry.configuration, agent.configuration),
        AgentRegistry.enabled == bool(agent.enabled),
    ]


def _dependent_counts(db: Session, agent_id: str) -> Dict[str, int]:
    from sqlalchemy import inspect as sa_inspect

    counts: Dict[str, int] = {}
    with _fresh_session(db) as fresh:
        inspector = sa_inspect(fresh.bind)
        for table in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns(table)}
            if "agent_id" not in cols or table == AgentRegistry.__tablename__:
                continue
            value = fresh.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE agent_id = :aid"),
                {"aid": str(agent_id)},
            ).scalar()
            counts[table] = int(value or 0)
    return counts


def _cleanup_dependents(db: Session, agent_id: str) -> Dict[str, int]:
    from sqlalchemy import inspect as sa_inspect

    cleaned: Dict[str, int] = {}
    inspector = sa_inspect(db.bind)
    for table in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns(table)}
        if "agent_id" not in cols or table == AgentRegistry.__tablename__:
            continue
        result = db.execute(
            text(f"DELETE FROM {table} WHERE agent_id = :aid"),
            {"aid": str(agent_id)},
        )
        if result.rowcount:
            cleaned[table] = int(result.rowcount)
    return cleaned


def _running_task_count(agent_id: str) -> int:
    try:
        from core.agent_task_registry import agent_task_registry
        return len(agent_task_registry.get_agent_tasks(str(agent_id)))
    except Exception:  # noqa: BLE001 — unavailable task state is not a block
        return 0


def _write_demo_tombstone(db: Session, agent: AgentRegistry) -> bool:
    configuration = (
        agent.configuration if isinstance(agent.configuration, dict) else {})
    if not bool(configuration.get("demo_agent")):
        return False
    from core.admin_bootstrap import DEMO_AGENT_TOMBSTONE_KEY
    from core.models import RuntimeSetting

    payload = {
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "agent_id": str(agent.id),
    }
    tombstone = db.get(RuntimeSetting, DEMO_AGENT_TOMBSTONE_KEY)
    if tombstone is not None:
        tombstone.value_json = payload
        tombstone.updated_by = "system"
    else:
        db.add(RuntimeSetting(
            key=DEMO_AGENT_TOMBSTONE_KEY,
            value_json=payload,
            updated_by="system",
        ))
    return True


def _delete_result_digest(
    agent_id: str, prior_digest: str, rows_cleaned: Dict[str, int],
    demo_tombstone: bool,
) -> str:
    return _fingerprint(
        "agent-deleted", str(agent_id), str(prior_digest),
        _canonical(rows_cleaned), bool(demo_tombstone))


def _delete_target_check(db: Session):
    def check(expected: Dict[str, Any]) -> bool:
        target_id = str(expected.get("target_id") or "")
        if _load_agent(db, target_id) is not None:
            return False
        if any(_dependent_counts(db, target_id).values()):
            return False
        extra = expected.get("extra") or {}
        if extra.get("demo_tombstone"):
            from core.admin_bootstrap import DEMO_AGENT_TOMBSTONE_KEY
            from core.models import RuntimeSetting

            with _fresh_session(db) as fresh:
                row = fresh.get(RuntimeSetting, DEMO_AGENT_TOMBSTONE_KEY)
                if row is None:
                    return False
                value = (
                    row.value_json if isinstance(row.value_json, dict) else {})
                if str(value.get("agent_id") or "") != target_id:
                    return False
        return True
    return check


def _delete_success_data(expected: Dict[str, Any]) -> Dict[str, Any]:
    extra = expected.get("extra") or {}
    return {
        "agent_id": str(expected.get("target_id") or ""),
        "agent_name": str(expected.get("agent_name") or ""),
        "rows_cleaned": dict(extra.get("rows_cleaned") or {}),
        "demo_tombstone": bool(extra.get("demo_tombstone")),
    }


def delete_agent(
    db: Session, *, actor: Any, agent_id: str,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    actor_snapshot = _resolve_actor(db, actor)
    if not actor_snapshot.get("ok"):
        return _actor_refusal(actor_snapshot)

    agent_id = str(agent_id or "").strip()
    if not agent_id:
        return _refused(
            "agent_id must be non-empty", http_status=422,
            error_code="VALIDATION_ERROR", field="agent_id")
    try:
        operation_id = _operation_id("delete", operation_id)
    except ValueError as exc:
        return _refused(
            str(exc), http_status=422, error_code="VALIDATION_ERROR",
            field="operation_id")

    if agent_id == "atom_main":
        return _refused(
            "The main agent (atom_main) cannot be deleted.",
            http_status=400, error_code="CANNOT_DELETE_MAIN_AGENT")

    request_digest = _request_digest(_ACTION_DELETE, agent_id)
    expected_base = {
        "operation_id": operation_id,
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_DELETE,
        "event_type": AuditEventType.DELETE.value,
        "target_id": agent_id,
        "request_digest": request_digest,
        "actor_id": actor_snapshot["id"],
    }
    replay = _replay(
        db, operation_id, expected_base, authority=actor_snapshot,
        target_check=_delete_target_check(db),
        success_data=_delete_success_data)
    if replay is not None:
        return replay

    agent = _load_agent(db, agent_id)
    if agent is None or not _agent_visible(actor_snapshot, agent):
        return _refused(
            f"Agent not found: {agent_id}", http_status=404,
            error_code="NOT_FOUND")
    if _running_task_count(agent_id):
        return _refused(
            "Cannot delete agent with running task(s)",
            http_status=400, error_code="AGENT_HAS_RUNNING_TASKS")

    prior_status = str(agent.status or "")
    prior_digest = _state_digest(_state_material(agent))

    if not _claim_actor(db, actor_snapshot):
        db.rollback()
        return _conflict(
            "reviewer authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")
    if _running_task_count(agent_id):
        db.rollback()
        return _refused(
            "Cannot delete agent with running task(s)",
            http_status=400, error_code="AGENT_HAS_RUNNING_TASKS")

    try:
        claimed = db.execute(
            update(AgentRegistry)
            .where(*_delete_agent_predicates(agent, prior_status))
            .values(updated_at=AgentRegistry.updated_at))
        if claimed.rowcount != 1:
            db.rollback()
            return _conflict(
                "agent material changed; refresh and retry",
                code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        return _conflict(
            "agent decision conflicts with current state",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "agent delete claim failed before commit: operation_id=%s "
            "target=%s error_class=%s", operation_id, agent_id,
            type(exc).__name__)
        return _not_applied(
            "The agent deletion could not be applied; no effect was "
            "committed")

    try:
        rows_cleaned = _cleanup_dependents(db, agent_id)
        db.execute(
            text("DELETE FROM agent_registry WHERE id = :aid"),
            {"aid": agent_id})
        demo_tombstone = _write_demo_tombstone(db, agent)
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "agent delete cleanup failed before commit: operation_id=%s "
            "target=%s error_class=%s", operation_id, agent_id,
            type(exc).__name__)
        return _not_applied(
            "The agent deletion could not be applied; no effect was "
            "committed")

    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_DELETE,
        event_type=AuditEventType.DELETE.value, agent=agent,
        prior_status=prior_status, result_status="deleted",
        request_digest=request_digest, prior_digest=prior_digest,
        result_digest=_delete_result_digest(
            agent_id, prior_digest, rows_cleaned, demo_tombstone),
        actor=actor_snapshot,
        extra={
            "rows_cleaned": rows_cleaned,
            "demo_tombstone": bool(demo_tombstone),
        })
    audit_row = _audit_row(expected=expected, actor=actor_snapshot)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: _delete_target_check(db)(expected),
        success_data=_delete_success_data(expected),
        authority=actor_snapshot,
        replay_check=_delete_target_check(db),
        replay_data=_delete_success_data)


# ---------------------------------------------------------------------------
# Run admission decision
# ---------------------------------------------------------------------------

_RUN_ACTIVE_STATUSES = (
    AgentJobStatus.PENDING.value,
    AgentJobStatus.RUNNING.value,
)


def _run_agent_predicates(agent: AgentRegistry, prior_status: str):
    return list(_agent_predicates(agent, prior_status)) + [
        _exact(AgentRegistry.configuration, agent.configuration),
        AgentRegistry.enabled == bool(agent.enabled),
    ]


def _load_job(db: Session, job_id: str) -> Optional[AgentJob]:
    with _fresh_session(db) as fresh:
        return fresh.query(AgentJob).filter(
            AgentJob.id == str(job_id)).populate_existing().first()


def _active_job(db: Session, agent_id: str) -> Optional[AgentJob]:
    with _fresh_session(db) as fresh:
        return fresh.query(AgentJob).filter(
            AgentJob.agent_id == str(agent_id),
            AgentJob.status.in_(_RUN_ACTIVE_STATUSES),
        ).order_by(AgentJob.start_time.desc()).first()


def _job_operation_id(job: Optional[AgentJob]) -> str:
    if job is None:
        return ""
    try:
        payload = json.loads(job.result_summary or "{}")
    except (TypeError, ValueError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("operation_id") or "")


def _run_target_check(db: Session):
    def check(expected: Dict[str, Any]) -> bool:
        extra = expected.get("extra") or {}
        job = _load_job(db, extra.get("job_id") or "")
        if job is None:
            return False
        return _job_operation_id(job) == str(
            expected.get("operation_id") or "")
    return check


def _run_success_data(db: Session):
    def build(expected: Dict[str, Any]) -> Dict[str, Any]:
        extra = expected.get("extra") or {}
        job = _load_job(db, extra.get("job_id") or "")
        return {
            "agent_id": str(expected.get("target_id") or ""),
            "job_id": str(extra.get("job_id") or ""),
            "job_status": (
                str(job.status) if job is not None
                else str(extra.get("job_status") or "running")),
            "prior_status": str(expected.get("prior_status") or ""),
        }
    return build


def admit_agent_run(
    db: Session, *, actor: Any, agent_id: str,
    parameters: Optional[Dict[str, Any]] = None,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Admit one agent run before dispatch.

    The admission binds the current actor, exact agent material, a durable
    ``AgentJob`` row and one audit receipt. It does not execute the agent;
    the route dispatches the existing task only after this transaction
    commits.
    """
    authority = _resolve_actor(
        db, actor, minimum_role=UserRole.MEMBER,
        authority_label="AGENT_RUN")
    if not authority.get("ok"):
        return _actor_refusal(authority)

    agent_id = str(agent_id or "").strip()
    if not agent_id:
        return _refused(
            "agent_id must be non-empty", http_status=422,
            error_code="VALIDATION_ERROR", field="agent_id")
    try:
        operation_id = _operation_id("run", operation_id)
    except ValueError as exc:
        return _refused(
            str(exc), http_status=422, error_code="VALIDATION_ERROR",
            field="operation_id")

    parameters = dict(parameters or {})
    parameters_digest = _fingerprint(
        "agent-run-parameters", _canonical(parameters))
    request_digest = _fingerprint(
        "agent-run-request", agent_id, parameters_digest)
    expected_base = {
        "operation_id": operation_id,
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_RUN,
        "event_type": AuditEventType.UPDATE.value,
        "target_id": agent_id,
        "request_digest": request_digest,
        "actor_id": authority["id"],
    }
    replay = _replay(
        db, operation_id, expected_base, authority=authority,
        target_check=_run_target_check(db),
        success_data=_run_success_data(db))
    if replay is not None:
        return replay

    agent = _load_agent(db, agent_id)
    if agent is None or not _agent_visible(authority, agent):
        return _refused(
            f"Agent not found: {agent_id}", http_status=404,
            error_code="NOT_FOUND")

    prior_status = str(agent.status or "")
    if prior_status in (
        AgentStatus.DEPRECATED.value, AgentStatus.PAUSED.value,
    ):
        return _refused(
            f"Agent is {prior_status}", http_status=400,
            error_code="AGENT_INVALID_STATE", field="status")
    if prior_status == "running":
        return _conflict(
            "Agent is already running", code="ALREADY_RUNNING")
    # Capture the SERVER-owned maturity BEFORE the admission flips the row to
    # ``running``. Runtime/execution labels are NOT governance tiers. Known
    # canonical maturity is carried into the durable job/receipt; a legacy or
    # unknown label is admitted under an explicit restricted (student) ceiling
    # rather than being rejected outright or promoted from runtime state.
    governance_tier = canonical_governance_tier(prior_status)
    governance_tier_source = (
        "admission" if governance_tier is not None else "legacy_unverified")
    active = _active_job(db, agent_id)
    if active is not None:
        return _conflict(
            "Agent is already running", code="ALREADY_RUNNING")

    prior_digest = _state_digest(_state_material(agent))

    if not _claim_actor(db, authority):
        db.rollback()
        return _conflict(
            "run authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    try:
        claimed = db.execute(
            update(AgentRegistry)
            .where(*_run_agent_predicates(agent, prior_status))
            .values(status="running"))
        if claimed.rowcount != 1:
            db.rollback()
            now = _load_agent(db, agent_id)
            if now is not None and str(now.status or "") == "running":
                return _conflict(
                    "Agent is already running", code="ALREADY_RUNNING")
            return _conflict(
                "agent material changed; refresh and retry",
                code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        return _conflict(
            "agent run admission conflicts with current state",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "agent run claim failed before commit: operation_id=%s "
            "target=%s error_class=%s", operation_id, agent_id,
            type(exc).__name__)
        return _not_applied(
            "The agent run could not be admitted; no effect was committed")

    job_id = str(uuid.uuid4())
    job = AgentJob(
        id=job_id,
        tenant_id=(
            agent.tenant_id
            if agent.tenant_id is not None
            else authority["raw_tenant_id"]),
        agent_id=agent_id,
        status=AgentJobStatus.RUNNING.value,
        result_summary=json.dumps({
            "operation_id": operation_id,
            "parameters_digest": parameters_digest,
            # Server-owned maturity captured before the status CAS above.
            # Dispatch re-reads this durable material; it is never inferred
            # from the transient ``running`` row. ``None`` means only the
            # restricted legacy ceiling was available, not a wider tier.
            "governance_tier": governance_tier,
            "governance_tier_source": governance_tier_source,
            "prior_status": prior_status,
        }, sort_keys=True),
    )
    db.add(job)

    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_RUN,
        event_type=AuditEventType.UPDATE.value, agent=agent,
        prior_status=prior_status, result_status="running",
        request_digest=request_digest, prior_digest=prior_digest,
        result_digest=_fingerprint(
            "agent-run", agent_id, prior_digest, job_id,
            parameters_digest),
        actor=authority,
        extra={
            "job_id": job_id,
            "parameters_digest": parameters_digest,
            "job_status": AgentJobStatus.RUNNING.value,
            # Same server-owned maturity as the durable job material. The
            # dispatch path requires the two to agree; ``None`` carries the
            # explicit legacy/restricted ceiling, never an inferred tier.
            "governance_tier": governance_tier,
            "governance_tier_source": governance_tier_source,
            "prior_status": prior_status,
        })
    audit_row = _audit_row(expected=expected, actor=authority)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: _run_target_check(db)(expected),
        success_data={
            "agent_id": agent_id,
            "job_id": job_id,
            "job_status": AgentJobStatus.RUNNING.value,
            "prior_status": prior_status,
        },
        authority=authority,
        replay_check=_run_target_check(db),
        replay_data=_run_success_data(db))


# ---------------------------------------------------------------------------
# Full replacement decision (PUT)
# ---------------------------------------------------------------------------

def _replace_config_digest(value: Any) -> str:
    return _fingerprint("agent-configuration", _canonical(value))


def _replace_schedule_digest(value: Any) -> str:
    return _fingerprint("agent-schedule", _canonical(value))


def _replace_state_material(
    agent: AgentRegistry, values: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    material = {
        "id": str(agent.id),
        "tenant_id": (
            None if agent.tenant_id is None else str(agent.tenant_id)),
        "workspace_id": (
            None if agent.workspace_id is None
            else str(agent.workspace_id)),
        "name": str(agent.name or ""),
        "description": (
            None if agent.description is None else str(agent.description)),
        "category": str(agent.category or ""),
        "configuration_digest": _replace_config_digest(agent.configuration),
        "schedule_digest": _replace_schedule_digest(agent.schedule_config),
        "status": str(agent.status or ""),
        "enabled": bool(agent.enabled),
    }
    if values:
        for key in ("name", "description", "category"):
            if key in values:
                material[key] = values[key]
        if "configuration" in values:
            material["configuration_digest"] = _replace_config_digest(
                values["configuration"])
        if "schedule_config" in values:
            material["schedule_digest"] = _replace_schedule_digest(
                values["schedule_config"])
    return material


def _load_replace_source(db: Session, agent_id: str):
    """Load the ORM row and its physical nullable JSON in one snapshot."""
    with _fresh_session(db) as fresh:
        raw = fresh.execute(
            text(
                "SELECT configuration, schedule_config "
                "FROM agent_registry WHERE id = :aid"),
            {"aid": str(agent_id)},
        ).first()
        agent = fresh.query(AgentRegistry).filter(
            AgentRegistry.id == str(agent_id)).populate_existing().first()
    if raw is None or agent is None:
        return None, None, None
    return agent, raw[0], raw[1]


def _raw_json_state(
    db: Session, agent_id: str,
) -> tuple[Any, Any]:
    """Return the physical stored JSON text/NULL for the two nullable fields.

    ORM decoding maps both SQL NULL and JSON null to ``None``; the guarded
    claim must compare the physical value so an unchanged null is not
    misclassified as a concurrent edit.
    """
    with _fresh_session(db) as fresh:
        row = fresh.execute(
            text(
                "SELECT configuration, schedule_config "
                "FROM agent_registry WHERE id = :aid"),
            {"aid": str(agent_id)},
        ).first()
    if row is None:
        return None, None
    return row[0], row[1]


def _raw_json_predicate(
    column_name: str, raw_value: Any, params: Dict[str, Any],
):
    column = getattr(AgentRegistry, column_name)
    if raw_value is None:
        return column.is_(None)
    if isinstance(raw_value, str):
        key = f"raw_{column_name}"
        params[key] = raw_value
        return text(
            f"{AgentRegistry.__tablename__}.{column_name} = :{key}")
    return column == raw_value


def _replace_agent_predicates(
    agent: AgentRegistry, raw_configuration: Any = None,
    raw_schedule: Any = None,
):
    params: Dict[str, Any] = {}
    predicates = [
        AgentRegistry.id == str(agent.id),
        _exact(AgentRegistry.tenant_id, agent.tenant_id),
        _exact(AgentRegistry.workspace_id, agent.workspace_id),
        AgentRegistry.name == str(agent.name or ""),
        _exact(AgentRegistry.description, agent.description),
        AgentRegistry.category == str(agent.category or ""),
        _raw_json_predicate("configuration", raw_configuration, params),
        _raw_json_predicate("schedule_config", raw_schedule, params),
        AgentRegistry.status == str(agent.status or ""),
        AgentRegistry.enabled == bool(agent.enabled),
        _exact(AgentRegistry.last_exam_id, agent.last_exam_id),
        _exact(AgentRegistry.exam_eligible_at, agent.exam_eligible_at),
    ]
    return predicates, params


def _replace_changes_match(
    agent: AgentRegistry, changes: Dict[str, Any],
) -> bool:
    for key, value in changes.items():
        current = getattr(agent, key, None)
        if current != value:
            return False
    return True


def _replace_target_check(db: Session):
    def check(expected: Dict[str, Any]) -> bool:
        current = _load_agent(db, str(expected.get("target_id") or ""))
        return (
            current is not None
            and _state_digest(_replace_state_material(current))
            == expected["result_digest"])

    return check


def _replace_success_data(db: Session):
    def build(expected: Dict[str, Any]) -> Dict[str, Any]:
        current = _load_agent(db, str(expected.get("target_id") or ""))
        return {
            "agent_id": str(expected.get("target_id") or ""),
            "name": str(getattr(current, "name", "") or ""),
            "category": str(getattr(current, "category", "") or ""),
            "schedule_active": bool(
                (getattr(current, "schedule_config", None) or {}).get(
                    "active")),
        }

    return build


def replace_agent(
    db: Session, *, actor: Any, agent_id: str, changes: Dict[str, Any],
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Full PUT replacement with current authority and exact prior material."""
    actor_snapshot = _resolve_actor(db, actor)
    if not actor_snapshot.get("ok"):
        return _actor_refusal(actor_snapshot)

    agent_id = str(agent_id or "").strip()
    if not agent_id:
        return _refused(
            "agent_id must be non-empty", http_status=422,
            error_code="VALIDATION_ERROR", field="agent_id")

    normalized: Dict[str, Any] = {}
    if changes.get("name") is not None:
        normalized["name"] = str(changes["name"])
    if "description" in changes:
        normalized["description"] = (
            None if changes["description"] is None
            else str(changes["description"]))
    if changes.get("category") is not None:
        normalized["category"] = str(changes["category"])
    if changes.get("configuration") is not None:
        normalized["configuration"] = dict(changes["configuration"])
    if changes.get("schedule_config") is not None:
        normalized["schedule_config"] = dict(changes["schedule_config"])
    if not normalized.get("name") or not normalized.get("category"):
        return _refused(
            "name and category are required", http_status=422,
            error_code="VALIDATION_ERROR", field="name")

    try:
        operation_id = _operation_id("replace", operation_id)
    except ValueError as exc:
        return _refused(
            str(exc), http_status=422, error_code="VALIDATION_ERROR",
            field="operation_id")

    request_material: Dict[str, Any] = {
        "name": normalized["name"],
        "description": normalized.get("description"),
        "category": normalized["category"],
    }
    if "configuration" in normalized:
        request_material["configuration_digest"] = _replace_config_digest(
            normalized["configuration"])
    if "schedule_config" in normalized:
        request_material["schedule_digest"] = _replace_schedule_digest(
            normalized["schedule_config"])
    request_digest = _request_digest(
        _ACTION_REPLACE, agent_id, request_material)
    expected_base = {
        "operation_id": operation_id,
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_REPLACE,
        "event_type": AuditEventType.UPDATE.value,
        "target_id": agent_id,
        "request_digest": request_digest,
        "actor_id": actor_snapshot["id"],
    }
    replay = _replay(
        db, operation_id, expected_base, authority=actor_snapshot,
        target_check=_replace_target_check(db),
        success_data=_replace_success_data(db))
    if replay is not None:
        return replay

    agent, raw_configuration, raw_schedule = _load_replace_source(
        db, agent_id)
    if agent is None or not _agent_visible(actor_snapshot, agent):
        return _refused(
            f"Agent not found: {agent_id}", http_status=404,
            error_code="NOT_FOUND")
    if _replace_changes_match(agent, normalized):
        return _no_change(
            {
                "agent_id": agent_id,
                "schedule_active": bool(
                    (normalized.get("schedule_config") or {}).get("active")),
            },
            "Agent already matches the requested replacement")

    prior_status = str(agent.status or "")
    prior_digest = _state_digest(_replace_state_material(agent))
    result_digest = _state_digest(
        _replace_state_material(agent, normalized))
    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_REPLACE,
        event_type=AuditEventType.UPDATE.value, agent=agent,
        prior_status=prior_status, result_status=prior_status,
        request_digest=request_digest, prior_digest=prior_digest,
        result_digest=result_digest, actor=actor_snapshot)

    if not _claim_actor(db, actor_snapshot):
        db.rollback()
        return _conflict(
            "reviewer authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    predicates, predicate_params = _replace_agent_predicates(
        agent, raw_configuration, raw_schedule)
    try:
        updated = db.execute(
            update(AgentRegistry)
            .where(*predicates)
            .values(**normalized),
            predicate_params)
        if updated.rowcount != 1:
            db.rollback()
            return _conflict(
                "agent material changed; refresh and retry",
                code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected, authority=actor_snapshot)
        return replay or _conflict(
            "agent replacement conflicts with current state",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "agent replace failed before commit: operation_id=%s target=%s "
            "error_class=%s", operation_id, agent_id,
            type(exc).__name__)
        return _not_applied(
            "The agent replacement could not be applied; no effect was "
            "committed")

    success_data = {
        "agent_id": agent_id,
        "name": normalized["name"],
        "category": normalized["category"],
        "schedule_active": bool(
            (normalized.get("schedule_config") or {}).get("active")),
    }
    audit_row = _audit_row(expected=expected, actor=actor_snapshot)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (now := _load_agent(db, agent_id)) is not None
            and _state_digest(_replace_state_material(now))
            == result_digest),
        success_data=success_data,
        authority=actor_snapshot,
        replay_check=_replace_target_check(db),
        replay_data=_replace_success_data(db))


# ---------------------------------------------------------------------------
# Stop/cancel decision
# ---------------------------------------------------------------------------

def _stop_target_check(db: Session):
    def check(expected: Dict[str, Any]) -> bool:
        current = _load_agent(db, str(expected.get("target_id") or ""))
        return (
            current is not None
            and _state_digest(_state_material(current))
            == expected["result_digest"])

    return check


def _stop_success_data(expected: Dict[str, Any]) -> Dict[str, Any]:
    extra = expected.get("extra") or {}
    return {
        "agent_id": str(expected.get("target_id") or ""),
        "cancelled_tasks": int(extra.get("cancelled_tasks") or 0),
    }


def _active_task_state(agent_id: str) -> Dict[str, Any]:
    """Read the preflight task set without turning failure into emptiness."""
    try:
        from core.agent_task_registry import agent_task_registry
        tasks = agent_task_registry.get_agent_tasks(str(agent_id))
        return {"status": "available", "count": len(tasks)}
    except Exception as exc:  # noqa: BLE001 — unreadable is not empty
        logger.warning(
            "agent stop task-state read failed: target=%s error_class=%s",
            agent_id, type(exc).__name__)
        return {"status": "unavailable", "error": type(exc).__name__}


async def stop_agent(
    db: Session, *, actor: Any, agent_id: str,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Cancel an agent's active tasks with current scope and a durable receipt."""
    authority = _resolve_actor(
        db, actor, minimum_role=UserRole.MEMBER,
        authority_label="AGENT_RUN")
    if not authority.get("ok"):
        return _actor_refusal(authority)

    agent_id = str(agent_id or "").strip()
    if not agent_id:
        return _refused(
            "agent_id must be non-empty", http_status=422,
            error_code="VALIDATION_ERROR", field="agent_id")
    try:
        operation_id = _operation_id("stop", operation_id)
    except ValueError as exc:
        return _refused(
            str(exc), http_status=422, error_code="VALIDATION_ERROR",
            field="operation_id")

    agent = _load_agent(db, agent_id)
    if agent is None or not _agent_visible(authority, agent):
        return _refused(
            f"Agent not found: {agent_id}", http_status=404,
            error_code="NOT_FOUND")
    prior_status = str(agent.status or "")
    prior_digest = _state_digest(_state_material(agent))

    request_digest = _fingerprint("agent-stop-request", agent_id)
    expected_base = {
        "operation_id": operation_id,
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_STOP,
        "event_type": AuditEventType.UPDATE.value,
        "target_id": agent_id,
        "request_digest": request_digest,
        "actor_id": authority["id"],
    }
    replay = _replay(
        db, operation_id, expected_base, authority=authority,
        target_check=_stop_target_check(db),
        success_data=_stop_success_data)
    if replay is not None:
        return replay

    task_state = _active_task_state(agent_id)
    if task_state["status"] == "unavailable":
        return _state_unavailable(operation_id, agent_id)
    if task_state["count"] == 0:
        return _no_change(
            {"agent_id": agent_id, "cancelled_tasks": 0},
            "No running tasks found for this agent")

    if not _claim_actor(db, authority):
        db.rollback()
        return _conflict(
            "run authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")

    try:
        claimed = db.execute(
            update(AgentRegistry)
            .where(*_run_agent_predicates(agent, prior_status))
            .values(updated_at=AgentRegistry.updated_at))
        if claimed.rowcount != 1:
            db.rollback()
            return _conflict(
                "agent material changed; refresh and retry",
                code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "agent stop claim failed before cancel: operation_id=%s "
            "target=%s error_class=%s", operation_id, agent_id,
            type(exc).__name__)
        return _not_applied(
            "The agent stop could not be admitted; no task was cancelled")

    try:
        from core.agent_task_registry import agent_task_registry
        cancelled = int(
            await agent_task_registry.cancel_agent_tasks(agent_id) or 0)
    except Exception as exc:  # noqa: BLE001 — call began, confirmation lost
        db.rollback()
        logger.error(
            "agent stop cancellation outcome unknown: operation_id=%s "
            "target=%s error_class=%s", operation_id, agent_id,
            type(exc).__name__)
        result = _effect_unknown(operation_id, agent_id)
        result["message"] = (
            "The agent stop may have cancelled tasks, but confirmation was "
            "lost. Reconcile the original operation; do not repeat it "
            "blindly.")
        result["verification"]["error"] = "CANCEL_CONFIRMATION_UNKNOWN"
        result["data"] = {"agent_id": agent_id}
        return result

    if cancelled == 0:
        db.rollback()
        return _no_change(
            {"agent_id": agent_id, "cancelled_tasks": 0},
            "No running tasks found for this agent")

    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_STOP,
        event_type=AuditEventType.UPDATE.value, agent=agent,
        prior_status=prior_status, result_status=prior_status,
        request_digest=request_digest, prior_digest=prior_digest,
        result_digest=prior_digest, actor=authority,
        extra={"cancelled_tasks": cancelled})
    audit_row = _audit_row(expected=expected, actor=authority)
    try:
        db.add(audit_row)
        db.commit()
    except Exception as exc:  # noqa: BLE001 — cancellation already occurred
        db.rollback()
        logger.error(
            "agent stop receipt failed after cancellation: operation_id=%s "
            "target=%s error_class=%s", operation_id, agent_id,
            type(exc).__name__)
        result = _effect_unknown(operation_id, agent_id)
        result["data"] = {
            "agent_id": agent_id,
            "cancelled_tasks": cancelled,
        }
        return result

    audit_state = _verify_audit(db, expected)
    current = _load_agent(db, agent_id)
    target_ok = (
        current is not None
        and _state_digest(_state_material(current)) == prior_digest)
    if audit_state["status"] == "verified" and not target_ok:
        audit_state = {"status": "refuted", "audit_id": operation_id}
    if audit_state["status"] == "verified" and target_ok:
        return {
            "status": "verified",
            "data": _with_receipt(
                {"agent_id": agent_id, "cancelled_tasks": cancelled},
                operation_id=operation_id, audit_id=operation_id),
            "message": f"Successfully stopped {cancelled} running task(s)",
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": agent_id,
        }
    return _committed_unverified(
        operation_id, audit_state, target_id=agent_id,
        data={"agent_id": agent_id, "cancelled_tasks": cancelled})

# Episodic graduation shares the decision ledger; manual promotion retains its
# separate permission/readiness semantics above.
def _graduation_material(
    agent: AgentRegistry, *, status=None, configuration=None,
    last_exam_id=None, promotion_count=None,
):
    material = _replace_state_material(agent)
    material.update(_state_material(agent))
    material["configuration_digest"] = _replace_config_digest(
        agent.configuration if configuration is None else configuration)
    if status is not None:
        material["status"] = status
    material["last_exam_id"] = (
        agent.last_exam_id if last_exam_id is None else last_exam_id)
    material["exam_eligible_at"] = (
        None if getattr(agent, "exam_eligible_at", None) is None
        else str(agent.exam_eligible_at))
    material["promotion_count"] = (
        int(getattr(agent, "promotion_count", 0) or 0)
        if promotion_count is None else int(promotion_count))
    for field in ("module_path", "class_name", "user_id", "confidence_score",
                  "required_role_for_autonomy"):
        material[field] = getattr(agent, field)
    return material


def _graduation_target_matches(db: Session, expected: Dict[str, Any]) -> bool:
    current = _load_agent(db, expected["target_id"])
    return (current is not None
            and _state_digest(_graduation_material(current)) == expected["result_digest"])


def graduation_request(
    *, operation_id, agent_id, target_status, actor, tenant_id, workspace_id,
    assessment_receipt_id=None, policy_revision=None,
):
    request_material = {
        "agent_id": str(agent_id), "target_status": target_status,
        "tenant_id": tenant_id, "workspace_id": workspace_id,
    }
    # Only new qualified callers add these keys; older requests keep their
    # exact digest so an in-flight replay is not broken by the join.
    if assessment_receipt_id is not None:
        request_material["assessment_receipt_id"] = str(assessment_receipt_id)
    return {
        "operation_id": operation_id, "schema": REVIEW_SCHEMA,
        "action": "agent_graduated", "event_type": AuditEventType.UPDATE.value,
        "target_id": str(agent_id), "actor_id": actor["id"],
        "request_digest": _fingerprint(
            "graduation-request", _canonical(request_material)),
    }


def replay_graduation(db: Session, *, request, actor):
    return _replay(db, request["operation_id"], request, authority=actor,
                   target_check=lambda expected: _graduation_target_matches(db, expected))


def commit_graduation(db: Session, *, reviewed, actor, request, predicates,
                      claim_params, target_status, configuration,
                      last_exam_id=None, promotion_count=None,
                      promotion_history=None, extra_success=None,
                      audit_extra=None):
    resolved_last_exam_id = (
        reviewed.last_exam_id if last_exam_id is None else last_exam_id)
    resolved_promotion_count = (
        int(getattr(reviewed, "promotion_count", 0) or 0)
        if promotion_count is None else int(promotion_count))
    expected = _audit_expected(
        operation_id=request["operation_id"], action=request["action"],
        event_type=AuditEventType.UPDATE.value, agent=reviewed,
        prior_status=str(reviewed.status), result_status=target_status,
        request_digest=request["request_digest"],
        prior_digest=_state_digest(_graduation_material(reviewed)),
        result_digest=_state_digest(_graduation_material(
            reviewed, status=target_status, configuration=configuration,
            last_exam_id=resolved_last_exam_id,
            promotion_count=resolved_promotion_count)), actor=actor,
        extra=audit_extra)
    try:
        if not _claim_actor(db, actor):
            db.rollback()
            return _conflict("Supervisor authority changed", code="AUTHORITY_CHANGED")
        changed = db.execute(update(AgentRegistry).where(*predicates).values(
            status=target_status, updated_at=datetime.now(timezone.utc),
            configuration=configuration, last_exam_id=resolved_last_exam_id,
            promotion_count=resolved_promotion_count
        ).execution_options(synchronize_session=False), claim_params)
        if changed.rowcount != 1:
            db.rollback()
            # A peer may have committed this exact operation after our first
            # replay read. Reconcile its durable receipt, never re-dispatch.
            # The rollback released the actor claim: confirm authority again.
            from types import SimpleNamespace
            current_actor = _resolve_actor(
                db, SimpleNamespace(id=actor["id"]),
                minimum_role=UserRole.TEAM_LEAD, authority_label="GRADUATION")
            binding = ("id", "role", "status", "raw_tenant_id", "raw_workspace_id")
            if not current_actor.get("ok") or any(
                    current_actor.get(key) != actor.get(key) for key in binding):
                return _conflict("Supervisor authority changed", code="AUTHORITY_CHANGED")
            replay = replay_graduation(db, request=request, actor=current_actor)
            if replay is not None:
                return replay
            return _conflict("Reviewed agent changed", code="STALE_TARGET")
    except Exception as exc:
        db.rollback()
        logger.warning("Graduation claim failed: error_class=%s", type(exc).__name__)
        return _not_applied("Graduation was not applied")
    if promotion_history is not None:
        db.add(promotion_history)
    success_data = {"agent_id": str(reviewed.id), "agent_status": target_status}
    if extra_success:
        success_data.update(extra_success)
    return _commit_and_verify(
        db, expected=expected, audit_row=_audit_row(expected=expected, actor=actor),
        target_check=lambda: _graduation_target_matches(db, expected),
        replay_check=lambda value: _graduation_target_matches(db, value),
        success_data=success_data,
        authority=actor)
