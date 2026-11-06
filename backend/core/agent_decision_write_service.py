"""Verified agent update/promote decisions.

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
from typing import Any, Callable, Dict, Optional

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.auth import SECRET_KEY
from core.models import (
    AgentRegistry,
    AgentStatus,
    AuditEventType,
    AuditLog,
    SecurityLevel,
    User,
    UserRole,
)
from core.personal_scope import resolve_tenant_id
from core.security.rbac import role_level

logger = logging.getLogger(__name__)

REVIEW_SCHEMA = "atom-agent-decision-1"
_OPERATION_PREFIX = "agent"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_ACTION_UPDATE = "agent_updated"
_ACTION_PROMOTE = "agent_promoted"


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


def _committed_unverified(
    operation_id: str, audit_state: Dict[str, Any], *, target_id: str,
) -> Dict[str, Any]:
    return {
        "status": "committed_unverified",
        "data": None,
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
            if role_level(row.role) < role_level(UserRole.WORKSPACE_ADMIN):
                return {
                    "ok": False, "http_status": 403,
                    "error_code": "AUTHORITY_REQUIRED",
                    "message": "AGENT_MANAGE authority is required",
                }
            return {
                "ok": True,
                "id": actor_id,
                "email": str(row.email or ""),
                "role": str(row.role or ""),
                "status": str(row.status or ""),
                "tenant_id": str(resolve_tenant_id(row)),
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
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    return {
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
            current = _load_agent(
                db, str(metadata.get("target_id") or ""))
            target_ok = (
                current is not None
                and _state_digest(_state_material(current))
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

    result_status = AgentStatus.AUTONOMOUS.value
    prior_material = _state_material(agent)
    result_material = _state_material(agent, status=result_status)
    expected = _audit_expected(
        operation_id=operation_id, action=_ACTION_PROMOTE,
        event_type=AuditEventType.UPDATE.value, agent=agent,
        prior_status=prior_status, result_status=result_status,
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
            .values(status=result_status))
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

    audit_row = _audit_row(expected=expected, actor=actor_snapshot)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (now := _load_agent(db, agent_id)) is not None
            and _state_digest(_state_material(now))
            == expected["result_digest"]),
        success_data={
            "agent_status": result_status,
            "agent_id": str(agent.id),
        },
        authority=actor_snapshot)
