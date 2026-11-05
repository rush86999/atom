"""Scoped durable memory and session-context writes.

The memory surface previously used process-global dictionaries keyed only by a
user-supplied key or session id. This module replaces that effect with the
existing tenant-scoped ``TenantSetting`` key/value store and writes one
``AuditLog`` receipt in the same transaction.

Scope is always ``(tenant_id, user_id, agent_id)``. The setting key is a keyed
digest of that exact scope plus the memory key/session id, and the stored JSON
document carries the scope again for defence in depth. A different tenant,
user or agent cannot read, search, overwrite or delete the entry.

Replay is bound to the request material only (not the prior value), so the same
operation id is idempotent while a changed request, a competing write or a
later revision is refused or reported as unverified. Confirmed rollback reports
``effect=none``; a lost commit confirmation reports ``effect=unknown``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.auth import SECRET_KEY
from core.models import (
    AuditEventType,
    AuditLog,
    SecurityLevel,
    TenantSetting,
    User,
)
from core.personal_scope import resolve_tenant_id

logger = logging.getLogger(__name__)

MEMORY_SCHEMA = "atom-memory-entry-1"
CONTEXT_SCHEMA = "atom-memory-context-1"
OPERATION_SCHEMA = "atom-memory-operation-1"
_OPERATION_PREFIX = "memory"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_MEMORY_PREFIX = "memory:v1:"
_CONTEXT_PREFIX = "memory-context:v1:"
_ACTION_STORE = "memory_stored"
_ACTION_CONTEXT = "memory_context_updated"
_ACTION_DELETE = "memory_deleted"
_ACTIONS = {_ACTION_STORE, _ACTION_CONTEXT, _ACTION_DELETE}


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


def _digest(value: Any) -> str:
    return _fingerprint("memory-digest", value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        "error_code": "MEMORY_TRANSACTION_ROLLED_BACK",
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
            "The memory write committed but its audit/target readback did not "
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
            "The memory write may have committed, but confirmation was lost. "
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


# ---------------------------------------------------------------------------
# Sessions and scope
# ---------------------------------------------------------------------------

def _fresh_session(db: Session) -> Session:
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=db.get_bind())()


def _authority_refusal(authority: Dict[str, Any]) -> Dict[str, Any]:
    return _refused(
        str(authority.get("message") or "Authentication required"),
        http_status=int(authority.get("http_status") or 401),
        error_code=str(authority.get("error_code") or "UNAUTHENTICATED"),
    )


def _authority_changed() -> Dict[str, Any]:
    return {
        "status": "conflict",
        "error": (
            "Authorization or scope changed; refresh and sign in again "
            "before retrying"),
        "error_code": "AUTHORITY_CHANGED",
        "http_status": 409,
        "verification": {"status": "refused", "effect": "none"},
    }


def _resolve_authority(db: Session, actor: Any) -> Dict[str, Any]:
    """Resolve the current principal and its effective personal scope.

    The request-entry User object is a snapshot. A concurrent deactivation or
    tenant reassignment must not let a mutation commit under stale authority,
    so this reads the authoritative row and freezes the claim material. The
    mutation later binds the same material in guarded DML in its own
    transaction (``_claim_authority``).
    """
    actor_id = str(getattr(actor, "id", "") or "")
    if not actor_id:
        return {
            "ok": False,
            "http_status": 401,
            "error_code": "UNAUTHENTICATED",
            "message": "Authentication required",
        }
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(User).filter(User.id == actor_id).first()
            if row is None:
                return {
                    "ok": False,
                    "http_status": 401,
                    "error_code": "UNAUTHENTICATED",
                    "message": "Authentication required",
                }
            raw_status = str(row.status or "")
            raw_is_active = row.is_active is True
            if raw_status != "active" or not raw_is_active:
                return {
                    "ok": False,
                    "http_status": 403,
                    "error_code": "ACCOUNT_INACTIVE",
                    "message": (
                        "This account is not active; refresh and sign in "
                        "again"),
                }
            raw_tenant_id = row.tenant_id
            return {
                "ok": True,
                "id": actor_id,
                "email": str(row.email or ""),
                "role": str(row.role or ""),
                "tenant_id": str(resolve_tenant_id(row)),
                "raw_status": raw_status,
                "raw_is_active": raw_is_active,
                "raw_tenant_id": raw_tenant_id,
            }
    except Exception as exc:  # noqa: BLE001 — unreadable authority fails closed
        logger.warning(
            "memory authority read failed: actor=%s error_class=%s",
            actor_id, type(exc).__name__)
        return {
            "ok": False,
            "http_status": 503,
            "error_code": "AUTHORITY_UNAVAILABLE",
            "message": "Authorization could not be confirmed; retry",
        }


def _claim_authority(db: Session, authority: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Bind the frozen principal in the same transaction as the effect.

    A zero-match means the User row was deactivated, moved or deleted after
    the request-entry snapshot. Roll back everything and refuse with
    effect=none; do not let a later target/audit commit stand.
    """
    try:
        claimed = db.execute(
            update(User)
            .where(
                User.id == authority["id"],
                User.status == authority["raw_status"],
                User.is_active == authority["raw_is_active"],
                User.tenant_id == authority["raw_tenant_id"],
            )
            .values(status=User.status))
        if claimed.rowcount != 1:
            db.rollback()
            return _authority_changed()
        return None
    except Exception as exc:  # noqa: BLE001 — unconfirmed authority fails closed
        db.rollback()
        logger.error(
            "memory authority claim failed: actor=%s error_class=%s",
            authority.get("id"), type(exc).__name__)
        return _not_applied(
            "The memory operation could not confirm current authorization; "
            "no effect was committed")


def _scope(actor: Dict[str, Any], agent_id: Optional[str]) -> Dict[str, Any]:
    return {
        "tenant_id": actor["tenant_id"],
        "user_id": actor["id"],
        "agent_id": str(agent_id) if agent_id else None,
    }


def _scope_json(scope: Dict[str, Any]) -> str:
    return _canonical(scope)


def _target_digest(kind: str, scope: Dict[str, Any], target: str) -> str:
    return _fingerprint(
        "memory-target", kind, _scope_json(scope), str(target))


def _scope_hash(scope: Dict[str, Any]) -> str:
    return _fingerprint("memory-scope", _scope_json(scope))


def _setting_key(kind: str, scope: Dict[str, Any], target: str) -> str:
    prefix = _MEMORY_PREFIX if kind == "memory" else _CONTEXT_PREFIX
    return (
        f"{prefix}{_scope_hash(scope)}:"
        + _fingerprint("memory-setting", kind, str(target))
    )


def _scope_prefix(kind: str, scope: Dict[str, Any]) -> str:
    prefix = _MEMORY_PREFIX if kind == "memory" else _CONTEXT_PREFIX
    return f"{prefix}{_scope_hash(scope)}:"


def _read_setting(
    db: Session, tenant_id: str, setting_key: str,
) -> Optional[Dict[str, Any]]:
    with _fresh_session(db) as fresh:
        row = fresh.query(TenantSetting).filter(
            TenantSetting.tenant_id == str(tenant_id),
            TenantSetting.setting_key == str(setting_key),
        ).first()
        if row is None:
            return None
        return {
            "id": str(row.id),
            "setting_value": str(row.setting_value or ""),
        }


def _read_settings_by_prefix(
    db: Session, tenant_id: str, prefix: str,
) -> List[str]:
    with _fresh_session(db) as fresh:
        rows = fresh.query(TenantSetting).filter(
            TenantSetting.tenant_id == str(tenant_id),
            TenantSetting.setting_key.like(f"{prefix}%"),
        ).all()
        return [str(row.setting_value or "") for row in rows]


def _parse_document(
    value: Optional[str], schema: str, scope: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    try:
        document = json.loads(value)
    except (TypeError, ValueError):
        return None
    if not isinstance(document, dict):
        return None
    if document.get("schema") != schema:
        return None
    if document.get("scope") != scope:
        return None
    return document


def _public_entry(document: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "key": str(document.get("key") or ""),
        "value": document.get("value"),
        "metadata": document.get("metadata") or {},
        "timestamp": str(document.get("timestamp") or ""),
    }


def _public_context(document: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "session_id": str(document.get("session_id") or ""),
        "context": document.get("context") or {},
        "timestamp": str(document.get("updated_at") or ""),
    }


# ---------------------------------------------------------------------------
# Audit ledger
# ---------------------------------------------------------------------------

def _audit_expected(
    *, operation_id: str, action: str, event_type: str,
    scope: Dict[str, Any], setting_key: str, target_digest: str,
    request_digest: str, prior_digest: str, result_digest: str,
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "operation_id": str(operation_id),
        "schema": OPERATION_SCHEMA,
        "action": str(action),
        "event_type": str(event_type),
        "scope_json": _scope_json(scope),
        "setting_key": str(setting_key),
        "target_digest": str(target_digest),
        "request_digest": str(request_digest),
        "prior_digest": str(prior_digest),
        "result_digest": str(result_digest),
        "actor_id": actor["id"],
        "actor_role": actor["role"],
        "tenant_id": scope["tenant_id"],
        "user_id": scope["user_id"],
        "agent_id": scope["agent_id"],
        "resource": f"memory:{target_digest}",
    }


def _audit_row(
    *, expected: Dict[str, Any], actor: Dict[str, Any],
) -> AuditLog:
    metadata = {
        "schema": expected["schema"],
        "operation_id": expected["operation_id"],
        "action": expected["action"],
        "event_type": expected["event_type"],
        "scope_json": expected["scope_json"],
        "setting_key": expected["setting_key"],
        "target_digest": expected["target_digest"],
        "request_digest": expected["request_digest"],
        "prior_digest": expected["prior_digest"],
        "result_digest": expected["result_digest"],
        "actor_id": expected["actor_id"],
        "actor_role": expected["actor_role"],
        "tenant_id": expected["tenant_id"],
        "user_id": expected["user_id"],
        "agent_id": expected["agent_id"],
    }
    return AuditLog(
        id=expected["operation_id"],
        event_type=expected["event_type"],
        security_level=SecurityLevel.HIGH.value,
        threat_level="none",
        user_id=expected["user_id"],
        user_email=actor["email"],
        tenant_id=expected["tenant_id"],
        workspace_id=None,
        resource=expected["resource"],
        action=expected["action"],
        description="Memory operation recorded",
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
            if str(row.user_id or "") != expected["user_id"]:
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
                "scope_json", "setting_key", "target_digest",
                "request_digest", "prior_digest", "result_digest",
                "actor_id", "actor_role", "tenant_id", "user_id",
            )
            for key in string_fields:
                if key not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                if not isinstance(metadata[key], str):
                    return {"status": "refuted", "audit_id": audit_id}
                if metadata[key] != expected[key]:
                    return {"status": "refuted", "audit_id": audit_id}
            if "agent_id" not in metadata:
                return {"status": "unavailable", "audit_id": audit_id}
            agent_id = metadata["agent_id"]
            if agent_id is not None and not isinstance(agent_id, str):
                return {"status": "refuted", "audit_id": audit_id}
            if agent_id != expected["agent_id"]:
                return {"status": "refuted", "audit_id": audit_id}
            return {"status": "verified", "audit_id": audit_id}
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "memory audit read-back failed: operation_id=%s error_class=%s",
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
        "scope_json": metadata.get("scope_json"),
        "setting_key": metadata.get("setting_key"),
        "target_digest": metadata.get("target_digest"),
        "request_digest": metadata.get("request_digest"),
        "prior_digest": metadata.get("prior_digest"),
        "result_digest": metadata.get("result_digest"),
        "actor_id": metadata.get("actor_id"),
        "actor_role": metadata.get("actor_role"),
        "tenant_id": metadata.get("tenant_id"),
        "user_id": metadata.get("user_id"),
        "agent_id": metadata.get("agent_id"),
        "resource": f"memory:{metadata.get('target_digest')}",
    }


def _replay(
    db: Session, operation_id: str, expected: Dict[str, Any],
    *, replay_data: Callable[[Optional[Dict[str, Any]]], Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Reconcile an existing receipt; None when no receipt exists."""
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
                or metadata.get("scope_json") != expected["scope_json"]
                or metadata.get("setting_key") != expected["setting_key"]
                or metadata.get("target_digest") != expected["target_digest"]
                or metadata.get("request_digest") != expected["request_digest"]
                or metadata.get("actor_id") != expected["actor_id"]
            ):
                return _conflict(
                    "operation_id is bound to a different memory request",
                    code="OPERATION_CONFLICT")
            audit_expected = _expected_from_metadata(
                metadata, operation_id=operation_id)
            audit_state = _verify_audit(db, audit_expected)
            current = _read_setting(
                db, str(metadata.get("tenant_id") or ""),
                str(metadata.get("setting_key") or ""))
            if audit_expected["action"] == _ACTION_DELETE:
                target_ok = current is None
                data = replay_data(None)
            else:
                target_ok = (
                    current is not None
                    and _digest(current["setting_value"])
                    == audit_expected["result_digest"]
                )
                data = replay_data(current) if target_ok else {}
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
                    "message": "This memory operation was already applied.",
                    "operation_id": operation_id,
                    "audit_id": audit_expected["operation_id"],
                    "target_id": audit_expected["target_digest"],
                }
            return _committed_unverified(
                operation_id, audit_state,
                target_id=audit_expected["target_digest"])
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "memory replay read failed: operation_id=%s error_class=%s",
            operation_id, type(exc).__name__)
        return _committed_unverified(
            operation_id, {"status": "unavailable"},
            target_id=str(expected.get("target_digest") or ""))


def _commit_and_verify(
    db: Session, *, expected: Dict[str, Any], audit_row: AuditLog,
    target_check: Callable[[], bool],
    success_data: Dict[str, Any],
) -> Dict[str, Any]:
    operation_id = expected["operation_id"]
    target_id = expected["target_digest"]
    try:
        db.add(audit_row)
        db.commit()
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected,
            replay_data=lambda _current: success_data)
        if replay is not None:
            return replay
        return _not_applied(
            "The memory write was rolled back; no effect was applied")
    except Exception as exc:  # noqa: BLE001 — commit outcome unknown
        db.rollback()
        logger.error(
            "memory write outcome unknown: operation_id=%s target=%s "
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
            "message": "Memory operation committed and verified.",
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": target_id,
        }
    return _committed_unverified(
        operation_id, audit_state, target_id=target_id)


# ---------------------------------------------------------------------------
# Public operations
# ---------------------------------------------------------------------------

def store_memory(
    db: Session, *, actor: Any, key: str, value: Any,
    metadata: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    key = str(key or "").strip()
    if not key:
        return _refused("key must be non-empty", field="key")
    if metadata is not None and not isinstance(metadata, dict):
        return _refused("metadata must be an object", field="metadata")
    authority = _resolve_authority(db, actor)
    if not authority.get("ok"):
        return _authority_refusal(authority)
    actor_snapshot = authority
    try:
        operation_id = _operation_id("store", operation_id)
    except ValueError as exc:
        return _refused(str(exc), field="operation_id")

    scope = _scope(actor_snapshot, agent_id)
    setting_key = _setting_key("memory", scope, key)
    target_digest = _target_digest("memory", scope, key)
    request_digest = _fingerprint(
        "memory-request", "memory_store", _scope_json(scope), key,
        _canonical(value), _canonical(metadata or {}))
    expected_base = _audit_expected(
        operation_id=operation_id, action=_ACTION_STORE,
        event_type=AuditEventType.UPDATE.value, scope=scope,
        setting_key=setting_key, target_digest=target_digest,
        request_digest=request_digest, prior_digest="",
        result_digest="", actor=actor_snapshot)

    def replay_data(current: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if current is None:
            return {}
        document = _parse_document(
            current["setting_value"], MEMORY_SCHEMA, scope)
        return _public_entry(document) if document else {}

    replay = _replay(
        db, operation_id, expected_base, replay_data=replay_data)
    if replay is not None:
        claim = _claim_authority(db, authority)
        if claim is not None:
            return claim
        db.rollback()
        return replay

    current = _read_setting(
        db, scope["tenant_id"], setting_key)
    claim = _claim_authority(db, authority)
    if claim is not None:
        return claim
    prior_value = current["setting_value"] if current else None
    prior_document = (
        _parse_document(prior_value, MEMORY_SCHEMA, scope)
        if prior_value else None
    )
    if prior_value is not None and prior_document is None:
        return _conflict(
            "memory entry is unreadable; refresh and retry",
            code="STALE_TARGET")
    prior_digest = _digest(prior_value) if prior_value is not None else ""
    revision = int((prior_document or {}).get("revision") or 0) + 1
    timestamp = _now()
    document = {
        "schema": MEMORY_SCHEMA,
        "scope": scope,
        "key": key,
        "value": value,
        "metadata": metadata or {},
        "revision": revision,
        "timestamp": timestamp,
    }
    new_value = _canonical(document)
    result_digest = _digest(new_value)
    expected = dict(expected_base)
    expected["prior_digest"] = prior_digest
    expected["result_digest"] = result_digest

    try:
        if current is None:
            db.add(TenantSetting(
                tenant_id=scope["tenant_id"],
                setting_key=setting_key,
                setting_value=new_value))
            db.flush()
        else:
            updated = db.execute(
                update(TenantSetting)
                .where(
                    TenantSetting.id == current["id"],
                    TenantSetting.tenant_id == scope["tenant_id"],
                    TenantSetting.setting_key == setting_key,
                    TenantSetting.setting_value == prior_value,
                )
                .values(setting_value=new_value))
            if updated.rowcount != 1:
                db.rollback()
                return _conflict(
                    "memory entry changed; refresh and retry",
                    code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected_base, replay_data=replay_data)
        if replay is not None:
            claim = _claim_authority(db, authority)
            if claim is not None:
                return claim
            db.rollback()
            return replay
        return _conflict(
            "memory entry changed; refresh and retry",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "memory store failed before commit: operation_id=%s "
            "target=%s error_class=%s",
            operation_id, target_digest, type(exc).__name__)
        return _not_applied(
            "The memory entry could not be stored; no effect was committed")

    audit_row = _audit_row(expected=expected, actor=actor_snapshot)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (row := _read_setting(
                db, scope["tenant_id"], setting_key)) is not None
            and _digest(row["setting_value"]) == result_digest),
        success_data=_public_entry(document))


def update_context(
    db: Session, *, actor: Any, session_id: str,
    context: Dict[str, Any],
    agent_id: Optional[str] = None,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    session_id = str(session_id or "").strip()
    if not session_id:
        return _refused("session_id must be non-empty", field="session_id")
    if not isinstance(context, dict):
        return _refused("context must be an object", field="context")
    authority = _resolve_authority(db, actor)
    if not authority.get("ok"):
        return _authority_refusal(authority)
    actor_snapshot = authority
    try:
        operation_id = _operation_id("context", operation_id)
    except ValueError as exc:
        return _refused(str(exc), field="operation_id")

    scope = _scope(actor_snapshot, agent_id)
    setting_key = _setting_key("context", scope, session_id)
    target_digest = _target_digest("context", scope, session_id)
    request_digest = _fingerprint(
        "memory-request", "memory_context", _scope_json(scope),
        session_id, _canonical(context))
    expected_base = _audit_expected(
        operation_id=operation_id, action=_ACTION_CONTEXT,
        event_type=AuditEventType.UPDATE.value, scope=scope,
        setting_key=setting_key, target_digest=target_digest,
        request_digest=request_digest, prior_digest="",
        result_digest="", actor=actor_snapshot)

    def replay_data(current: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if current is None:
            return {}
        document = _parse_document(
            current["setting_value"], CONTEXT_SCHEMA, scope)
        return _public_context(document) if document else {}

    replay = _replay(
        db, operation_id, expected_base, replay_data=replay_data)
    if replay is not None:
        claim = _claim_authority(db, authority)
        if claim is not None:
            return claim
        db.rollback()
        return replay

    current = _read_setting(
        db, scope["tenant_id"], setting_key)
    claim = _claim_authority(db, authority)
    if claim is not None:
        return claim
    prior_value = current["setting_value"] if current else None
    prior_document = (
        _parse_document(prior_value, CONTEXT_SCHEMA, scope)
        if prior_value else None
    )
    if prior_value is not None and prior_document is None:
        return _conflict(
            "memory context is unreadable; refresh and retry",
            code="STALE_TARGET")
    prior_context = (
        prior_document.get("context")
        if isinstance(prior_document, dict)
        and isinstance(prior_document.get("context"), dict)
        else {}
    )
    prior_digest = _digest(prior_value) if prior_value is not None else ""
    revision = int((prior_document or {}).get("revision") or 0) + 1
    timestamp = _now()
    merged = {**prior_context, **context, "_updated_at": timestamp}
    document = {
        "schema": CONTEXT_SCHEMA,
        "scope": scope,
        "session_id": session_id,
        "context": merged,
        "revision": revision,
        "updated_at": timestamp,
    }
    new_value = _canonical(document)
    result_digest = _digest(new_value)
    expected = dict(expected_base)
    expected["prior_digest"] = prior_digest
    expected["result_digest"] = result_digest

    try:
        if current is None:
            db.add(TenantSetting(
                tenant_id=scope["tenant_id"],
                setting_key=setting_key,
                setting_value=new_value))
            db.flush()
        else:
            updated = db.execute(
                update(TenantSetting)
                .where(
                    TenantSetting.id == current["id"],
                    TenantSetting.tenant_id == scope["tenant_id"],
                    TenantSetting.setting_key == setting_key,
                    TenantSetting.setting_value == prior_value,
                )
                .values(setting_value=new_value))
            if updated.rowcount != 1:
                db.rollback()
                return _conflict(
                    "memory context changed; refresh and retry",
                    code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        replay = _replay(
            db, operation_id, expected_base, replay_data=replay_data)
        if replay is not None:
            claim = _claim_authority(db, authority)
            if claim is not None:
                return claim
            db.rollback()
            return replay
        return _conflict(
            "memory context changed; refresh and retry",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "memory context update failed before commit: operation_id=%s "
            "target=%s error_class=%s",
            operation_id, target_digest, type(exc).__name__)
        return _not_applied(
            "The memory context could not be updated; no effect was committed")

    audit_row = _audit_row(expected=expected, actor=actor_snapshot)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (row := _read_setting(
                db, scope["tenant_id"], setting_key)) is not None
            and _digest(row["setting_value"]) == result_digest),
        success_data=_public_context(document))


def delete_memory(
    db: Session, *, actor: Any, key: str,
    agent_id: Optional[str] = None,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    key = str(key or "").strip()
    if not key:
        return _refused("key must be non-empty", field="key")
    authority = _resolve_authority(db, actor)
    if not authority.get("ok"):
        return _authority_refusal(authority)
    actor_snapshot = authority
    try:
        operation_id = _operation_id("delete", operation_id)
    except ValueError as exc:
        return _refused(str(exc), field="operation_id")

    scope = _scope(actor_snapshot, agent_id)
    setting_key = _setting_key("memory", scope, key)
    target_digest = _target_digest("memory", scope, key)
    request_digest = _fingerprint(
        "memory-request", "memory_delete", _scope_json(scope), key)
    deleted_digest = _fingerprint(
        "memory-deleted", setting_key, target_digest)
    expected_base = _audit_expected(
        operation_id=operation_id, action=_ACTION_DELETE,
        event_type=AuditEventType.DELETE.value, scope=scope,
        setting_key=setting_key, target_digest=target_digest,
        request_digest=request_digest, prior_digest="",
        result_digest=deleted_digest, actor=actor_snapshot)

    def replay_data(_current: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return {"key": key, "deleted": True}

    replay = _replay(
        db, operation_id, expected_base, replay_data=replay_data)
    if replay is not None:
        claim = _claim_authority(db, authority)
        if claim is not None:
            return claim
        db.rollback()
        return replay

    current = _read_setting(db, scope["tenant_id"], setting_key)
    if current is None:
        return _refused(
            f"Memory key not found: {key}", http_status=404,
            error_code="NOT_FOUND")
    claim = _claim_authority(db, authority)
    if claim is not None:
        return claim
    prior_value = current["setting_value"]
    prior_document = _parse_document(prior_value, MEMORY_SCHEMA, scope)
    if prior_document is None:
        return _conflict(
            "memory entry is unreadable; refresh and retry",
            code="STALE_TARGET")
    expected = dict(expected_base)
    expected["prior_digest"] = _digest(prior_value)

    try:
        deleted = db.execute(
            delete(TenantSetting)
            .where(
                TenantSetting.id == current["id"],
                TenantSetting.tenant_id == scope["tenant_id"],
                TenantSetting.setting_key == setting_key,
                TenantSetting.setting_value == prior_value,
            ))
        if deleted.rowcount != 1:
            db.rollback()
            return _conflict(
                "memory entry changed; refresh and retry",
                code="STALE_TARGET")
    except IntegrityError:
        db.rollback()
        return _conflict(
            "memory entry could not be deleted; refresh and retry",
            code="STALE_TARGET")
    except Exception as exc:  # noqa: BLE001 — mutation did not commit
        db.rollback()
        logger.error(
            "memory delete failed before commit: operation_id=%s "
            "target=%s error_class=%s",
            operation_id, target_digest, type(exc).__name__)
        return _not_applied(
            "The memory entry could not be deleted; no effect was committed")

    audit_row = _audit_row(expected=expected, actor=actor_snapshot)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: _read_setting(
            db, scope["tenant_id"], setting_key) is None,
        success_data={"key": key, "deleted": True})


# ---------------------------------------------------------------------------
# Scoped read/search consumers
# ---------------------------------------------------------------------------

def read_memory(
    db: Session, *, actor: Any, key: str,
    agent_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    authority = _resolve_authority(db, actor)
    if not authority.get("ok"):
        return None
    actor_snapshot = authority
    scope = _scope(actor_snapshot, agent_id)
    current = _read_setting(
        db, scope["tenant_id"],
        _setting_key("memory", scope, str(key or "")))
    if current is None:
        return None
    document = _parse_document(
        current["setting_value"], MEMORY_SCHEMA, scope)
    return _public_entry(document) if document else None


def search_memory(
    db: Session, *, actor: Any, q: str, limit: int = 10,
    agent_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    authority = _resolve_authority(db, actor)
    if not authority.get("ok"):
        return []
    actor_snapshot = authority
    scope = _scope(actor_snapshot, agent_id)
    query_text = str(q or "").lower()
    results: List[Dict[str, Any]] = []
    for raw in _read_settings_by_prefix(
            db, scope["tenant_id"], _scope_prefix("memory", scope)):
        document = _parse_document(raw, MEMORY_SCHEMA, scope)
        if document is None:
            continue
        if query_text not in str(document.get("value", "")).lower():
            continue
        results.append(_public_entry(document))
    results.sort(
        key=lambda item: (str(item.get("timestamp") or ""),
                          str(item.get("key") or "")))
    return results[:max(1, min(int(limit or 10), 100))]


def read_context(
    db: Session, *, actor: Any, session_id: str,
    agent_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    authority = _resolve_authority(db, actor)
    if not authority.get("ok"):
        return None
    actor_snapshot = authority
    scope = _scope(actor_snapshot, agent_id)
    current = _read_setting(
        db, scope["tenant_id"],
        _setting_key("context", scope, str(session_id or "")))
    if current is None:
        return None
    document = _parse_document(
        current["setting_value"], CONTEXT_SCHEMA, scope)
    return _public_context(document) if document else None
