"""Durable verified writes for the five direct auth/2FA mutation routes.

The routes already use real ``pyotp``, the existing ``User`` factor fields,
``HITLAction`` and ``AuditLog``. This module adds the missing commit-boundary
state: factor revision, TOTP time-step replay fencing, conditional backup-code
consumption, durable HITL resolver attribution and safe operation receipts.

It does not add a second authentication, OTP, review or approval engine. All
mutations use conditional database writes; a losing/revoked request matches
zero rows and leaves factor/action/audit state unchanged.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, Optional

import pyotp
from sqlalchemy import String, cast, or_, update
from sqlalchemy.exc import IntegrityError

from core.audit_service import audit_service
from core.auth import SECRET_KEY
from core.database import get_db_session
from core.models import (
    AuditEventType,
    AuditLog,
    AuthTwoFactorBackupCode,
    AuthTwoFactorOperation,
    HITLAction,
    SecurityLevel,
    User,
)

logger = logging.getLogger(__name__)

ISSUER_NAME = "Atom AI (Upstream)"
BACKUP_CODE_COUNT = 5
_OPERATION_PREFIX = "auth2fa"

_AUDIT_ACTIONS = {
    "setup": "2fa_setup_initiated",
    "enable": "2fa_enabled",
    "disable": "2fa_disabled",
    "backup_verify": "2fa_backup_code_used",
    "verify_action": "hitl_action_verified_2fa",
}
#: Only operations with a durable target row require target evidence. Setup,
#: enable and disable are genuinely targetless; inventing a target for them
#: would make the audit contract stricter than the operation.
_AUDIT_TARGET_REQUIRED = {"backup_verify", "verify_action"}


# ---------------------------------------------------------------------------
# Safe material helpers
# ---------------------------------------------------------------------------

def _fingerprint(*parts: Any) -> str:
    """Keyed HMAC over operation material; never stores raw codes."""
    message = "|".join(str(part if part is not None else "") for part in parts)
    return hmac.new(
        str(SECRET_KEY).encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_backup_codes(n: int = BACKUP_CODE_COUNT) -> list:
    """Generate the existing 4x4 recovery-code format."""
    codes = []
    for _ in range(n):
        raw = secrets.token_hex(8).upper()
        codes.append("-".join(
            [raw[i:i + 4] for i in range(0, 16, 4)]))
    return codes


def _code_fingerprint(user_id: str, code: str) -> str:
    return _fingerprint("code", user_id, code)


def _operation_material(
    action: str,
    user: User,
    factor_revision: int,
    code: str = "",
    target_id: str = "",
) -> str:
    return _fingerprint(
        "material",
        user.id,
        user.tenant_id or "",
        user.workspace_id or "",
        action,
        int(factor_revision or 0),
        target_id or "",
        _code_fingerprint(user.id, code) if code else "",
    )


def _current_step() -> int:
    return int(time.time()) // 30


def _new_operation_id() -> str:
    return f"{_OPERATION_PREFIX}:{uuid.uuid4().hex}"


def _scope_value_allowed(observed: Any, expected: Any) -> bool:
    """Mirror the accepted legacy null/empty/default scope policy."""
    observed = str(observed or "").strip()
    expected = str(expected or "").strip()
    if not observed:
        return True
    if expected:
        return observed == expected
    return observed.lower() == "default"


def _raw_scope(value: Any) -> Optional[str]:
    """Preserve the raw nullable scope representation for exact binding."""
    return None if value is None else str(value)


def _exact_nullable(column, value: Any):
    """Bind NULL, empty and concrete values exactly, never as aliases."""
    if value is None:
        return column.is_(None)
    return column == str(value)


def _json_exact(column, value: Any):
    """Bind a JSON value exactly, including SQL NULL vs JSON null."""
    if value is None:
        return or_(column.is_(None), cast(column, String) == "null")
    return column == value


# ---------------------------------------------------------------------------
# Frozen authority / target snapshots
# ---------------------------------------------------------------------------

def _actor_snapshot(user: User) -> Dict[str, Any]:
    return {
        "user_id": str(user.id),
        "user_email": str(user.email or ""),
        "tenant_id": _raw_scope(user.tenant_id),
        "workspace_id": _raw_scope(user.workspace_id),
        "role": str(user.role or ""),
        "status": str(user.status or ""),
        "is_active": bool(user.is_active),
        "factor_enabled": bool(user.two_factor_enabled),
        "factor_secret": user.two_factor_secret,
        "factor_revision": int(user.two_factor_revision or 0),
        "last_totp_step": (
            int(user.two_factor_last_totp_step)
            if user.two_factor_last_totp_step is not None else None
        ),
    }


def _actor_digest(actor: Dict[str, Any]) -> str:
    """Digest the authority fields that make the original actor valid."""
    return _fingerprint(
        "actor",
        actor["user_id"],
        actor["tenant_id"],
        actor["workspace_id"],
        actor["role"],
        actor["status"],
        "1" if actor["is_active"] else "0",
    )


def _actor_authorized(actor: Dict[str, Any]) -> bool:
    return bool(
        actor["is_active"]
        and str(actor["status"] or "").strip().lower() == "active"
    )


def _user_authority_predicates(actor: Dict[str, Any]):
    """Conditional-write predicates for the frozen actor authority."""
    return [
        User.is_active.is_(True),
        _exact_nullable(User.status, actor["status"]),
        _exact_nullable(User.role, actor["role"]),
        _exact_nullable(User.tenant_id, actor["tenant_id"]),
        _exact_nullable(User.workspace_id, actor["workspace_id"]),
    ]


def _factor_disabled_predicate():
    # Legacy rows may carry NULL for "not enabled"; both mean disabled.
    return or_(
        User.two_factor_enabled.is_(False),
        User.two_factor_enabled.is_(None),
    )


def _action_snapshot(action: HITLAction) -> Dict[str, Any]:
    return {
        "action_id": str(action.id),
        "tenant_id": _raw_scope(action.tenant_id),
        "workspace_id": _raw_scope(action.workspace_id),
        "action_type": str(action.action_type or ""),
        "platform": str(action.platform or ""),
        "params": action.params,
        "context_snapshot": action.context_snapshot,
        "priority": str(action.priority or ""),
        "user_id": _raw_scope(action.user_id),
        "required_role": _raw_scope(action.required_role),
        "required_confidence": (
            float(action.required_confidence)
            if action.required_confidence is not None else None
        ),
        "chain_id": _raw_scope(action.chain_id),
        "agent_id": _raw_scope(action.agent_id),
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str)


def _action_digest(action: Dict[str, Any]) -> str:
    """Digest the exact reviewed target, policy and material snapshot."""
    return _fingerprint(
        "action",
        action["action_id"],
        action["tenant_id"],
        action["workspace_id"],
        action["action_type"],
        action["platform"],
        _canonical_json(action["params"]),
        _canonical_json(action["context_snapshot"]),
        action["priority"],
        action["user_id"],
        action["required_role"],
        action["required_confidence"],
        action["chain_id"],
        action["agent_id"],
    )


def _action_predicates(action: Dict[str, Any]):
    """Bind the claim to the exact action target/policy/material snapshot."""
    predicates = [
        HITLAction.id == action["action_id"],
        HITLAction.status.in_(["pending", "pending_2fa"]),
        _exact_nullable(HITLAction.tenant_id, action["tenant_id"]),
        _exact_nullable(HITLAction.workspace_id, action["workspace_id"]),
        _exact_nullable(HITLAction.action_type, action["action_type"]),
        _exact_nullable(HITLAction.platform, action["platform"]),
        _json_exact(HITLAction.params, action["params"]),
        _json_exact(
            HITLAction.context_snapshot, action["context_snapshot"]),
        _exact_nullable(HITLAction.priority, action["priority"]),
        _exact_nullable(HITLAction.user_id, action["user_id"]),
        _exact_nullable(HITLAction.required_role, action["required_role"]),
        _exact_nullable(HITLAction.chain_id, action["chain_id"]),
        _exact_nullable(HITLAction.agent_id, action["agent_id"]),
    ]
    if action["required_confidence"] is None:
        predicates.append(HITLAction.required_confidence.is_(None))
    else:
        predicates.append(
            HITLAction.required_confidence == action["required_confidence"])
    return predicates


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

def _refused(
    error: str, *, field: Optional[str] = None,
    http_status: int = 422, error_code: str = "VALIDATION_ERROR",
) -> Dict[str, Any]:
    return {
        "status": "refused",
        "error": error,
        "error_code": error_code,
        "field": field,
        "http_status": int(http_status),
        "verification": {"status": "not_attempted", "effect": "none"},
    }


def _effect_unknown(
    operation_id: str, *, action_id: Optional[str] = None,
    stage: str = "commit",
) -> Dict[str, Any]:
    """Truthful uncertainty without raw exception text or bound parameters."""
    return {
        "status": "effect_unknown",
        "data": None,
        "message": (
            "The 2FA effect may have committed but confirmation was lost. "
            "Do not repeat the effect blindly."),
        "operation_id": operation_id,
        "audit_id": None,
        "action_id": action_id,
        "verification": {
            "status": "unavailable",
            "effect": "unknown",
            "replay": "do_not_repeat",
            "error": "COMMIT_OUTCOME_UNKNOWN",
            "stage": stage,
        },
    }


def _parse_receipt(raw: Optional[str]) -> Dict[str, Any]:
    try:
        receipt = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return receipt if isinstance(receipt, dict) else {}


def _operation_conflict() -> Dict[str, Any]:
    return _refused(
        "operation_id already used with different material",
        field="operation_id",
        http_status=409,
        error_code="CONFLICT",
    )


def _existing_operation(
    session, user_id: str, operation_id: str,
) -> Optional[AuthTwoFactorOperation]:
    return (
        session.query(AuthTwoFactorOperation)
        .filter(
            AuthTwoFactorOperation.id == str(operation_id),
            AuthTwoFactorOperation.user_id == str(user_id),
        )
        .first()
    )


def _operation_matches(
    row: AuthTwoFactorOperation,
    action: str,
    user: User,
    code: str = "",
    target_id: str = "",
) -> bool:
    """Bind a retry to the exact action/material/revision of the receipt."""
    if row.action != action:
        return False
    expected = _operation_material(
        action, user, row.factor_revision, code, target_id)
    return row.material_fingerprint == expected


def _load_user(session, user_id: str) -> Optional[User]:
    return session.query(User).filter(User.id == str(user_id)).first()


# ---------------------------------------------------------------------------
# Audit: frozen expectation, exact readback, no aliases
# ---------------------------------------------------------------------------

def _audit_resource(action: str, user_id: str, target_id: Optional[str]) -> str:
    if action == "verify_action":
        return f"hitl:{target_id}"
    return f"user:{user_id}:2fa"


def _audit_expected(
    *,
    audit_action: str,
    resource: str,
    user_id: str,
    tenant_id: Any,
    workspace_id: Any,
    operation_id: str,
    factor_revision: int,
    target_id: Optional[str] = None,
    target_required: bool = False,
) -> Dict[str, Any]:
    """Freeze every applicable audit field before the logger is called."""
    return {
        "event_type": AuditEventType.UPDATE.value,
        "audit_action": str(audit_action),
        "resource": str(resource),
        "user_id": str(user_id),
        "workspace_id": _raw_scope(workspace_id),
        "operation_id": str(operation_id),
        "tenant_id": str(tenant_id or ""),
        "workspace_meta": str(workspace_id or ""),
        "factor_revision": int(factor_revision or 0),
        "target_id": str(target_id) if target_required else None,
        "target_required": bool(target_required),
    }


def _find_audit_id(expected: Dict[str, Any]) -> Optional[str]:
    """Recover an independently written audit row when the return id was lost.

    This is not a logger-return shortcut: the row is found by its exact
    action/actor/scope/resource and must still pass the full field comparison.
    """
    try:
        with get_db_session() as db:
            candidates = (
                db.query(AuditLog)
                .filter(
                    AuditLog.action == expected["audit_action"],
                    AuditLog.user_id == expected["user_id"],
                    AuditLog.resource == expected["resource"],
                    _exact_nullable(
                        AuditLog.workspace_id, expected["workspace_id"]),
                )
                .order_by(AuditLog.timestamp.desc())
                .limit(20)
                .all()
            )
            matches = []
            for row in candidates:
                try:
                    metadata = json.loads(row.metadata_json or "{}")
                except (TypeError, ValueError):
                    continue
                if isinstance(metadata, dict) and (
                        str(metadata.get("operation_id"))
                        == expected["operation_id"]):
                    matches.append(str(row.id))
            return matches[0] if len(matches) == 1 else None
    except Exception as exc:  # noqa: BLE001 — recovery is best-effort
        logger.warning(
            "2FA audit recovery failed: operation_id=%s error_class=%s",
            expected.get("operation_id"), type(exc).__name__)
        return None


def _verify_audit_observation(
    audit_id: Optional[str], expected: Dict[str, Any],
) -> Dict[str, Any]:
    """Independently read one audit row and compare its exact namespace.

    Missing required evidence is ``unavailable``; present-but-contradictory
    evidence is ``refuted``. A logger return value is never accepted as proof.
    """
    if not audit_id:
        audit_id = _find_audit_id(expected)
    if not audit_id:
        return {"status": "unavailable", "audit_id": None}
    audit_id = str(audit_id)
    try:
        with get_db_session() as db:
            row = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
            if row is None:
                return {"status": "unavailable", "audit_id": audit_id}

            if not isinstance(row.event_type, str) or (
                    row.event_type != expected["event_type"]):
                return {"status": "refuted", "audit_id": audit_id}
            if not isinstance(row.action, str) or (
                    row.action != expected["audit_action"]):
                return {"status": "refuted", "audit_id": audit_id}
            if not isinstance(row.user_id, str) or (
                    row.user_id != expected["user_id"]):
                return {"status": "refuted", "audit_id": audit_id}
            if _raw_scope(row.workspace_id) != expected["workspace_id"]:
                return {"status": "refuted", "audit_id": audit_id}
            if _raw_scope(row.resource) != expected["resource"]:
                return {"status": "refuted", "audit_id": audit_id}
            if row.success is not True:
                return {"status": "refuted", "audit_id": audit_id}
            if not isinstance(row.security_level, str) or (
                    row.security_level != SecurityLevel.HIGH.value):
                return {"status": "refuted", "audit_id": audit_id}

            try:
                metadata = json.loads(row.metadata_json or "{}")
            except (TypeError, ValueError):
                return {"status": "unavailable", "audit_id": audit_id}
            if not isinstance(metadata, dict):
                return {"status": "unavailable", "audit_id": audit_id}

            required = (
                "operation_id", "tenant_id", "workspace_id",
                "factor_revision",
            )
            if any(key not in metadata for key in required):
                return {"status": "unavailable", "audit_id": audit_id}

            if not isinstance(metadata["operation_id"], str) or (
                    metadata["operation_id"] != expected["operation_id"]):
                return {"status": "refuted", "audit_id": audit_id}
            if not isinstance(metadata["tenant_id"], str) or (
                    metadata["tenant_id"] != expected["tenant_id"]):
                return {"status": "refuted", "audit_id": audit_id}
            if not isinstance(metadata["workspace_id"], str) or (
                    metadata["workspace_id"] != expected["workspace_meta"]):
                return {"status": "refuted", "audit_id": audit_id}
            observed_revision = metadata["factor_revision"]
            if isinstance(observed_revision, bool) or not isinstance(
                    observed_revision, int) or (
                    observed_revision != expected["factor_revision"]):
                return {"status": "refuted", "audit_id": audit_id}

            if expected["target_required"]:
                if "target_id" not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                if not isinstance(metadata["target_id"], str) or (
                        metadata["target_id"] != expected["target_id"]):
                    return {"status": "refuted", "audit_id": audit_id}

            return {"status": "verified", "audit_id": audit_id}
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "2FA audit read-back failed: operation_id=%s error_class=%s",
            expected.get("operation_id"), type(exc).__name__)
        return {"status": "unavailable", "audit_id": audit_id}


def _audit(
    *,
    audit_logger,
    expected: Dict[str, Any],
    description: str,
    user_email: str,
    request,
    metadata_extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write the frozen audit observation, then verify it independently."""
    metadata = {
        "operation_id": expected["operation_id"],
        "factor_revision": expected["factor_revision"],
        "tenant_id": expected["tenant_id"],
        "workspace_id": expected["workspace_meta"],
    }
    if expected["target_required"]:
        metadata["target_id"] = expected["target_id"]
    if metadata_extra:
        metadata.update(metadata_extra)

    audit_id = None
    try:
        with get_db_session() as audit_db:
            audit_id = audit_logger.log_event(
                audit_db,
                event_type=expected["event_type"],
                action=expected["audit_action"],
                description=description,
                user_id=expected["user_id"],
                user_email=user_email,
                workspace_id=expected["workspace_id"],
                security_level=SecurityLevel.HIGH.value,
                resource=expected["resource"],
                metadata=metadata,
                request=request,
            )
    except Exception as exc:  # noqa: BLE001 — state already committed
        logger.warning(
            "2FA audit write failed: operation_id=%s error_class=%s",
            expected["operation_id"], type(exc).__name__)
        audit_id = None
    return _verify_audit_observation(audit_id, expected)


def _write_audit(
    *,
    audit_logger,
    actor: Dict[str, Any],
    action: str,
    operation_id: str,
    factor_revision: int,
    description: str,
    request,
    audit_action: Optional[str] = None,
    target_id: Optional[str] = None,
    target_required: bool = False,
    metadata_extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    expected = _audit_expected(
        audit_action=audit_action or _AUDIT_ACTIONS[action],
        resource=_audit_resource(action, actor["user_id"], target_id),
        user_id=actor["user_id"],
        tenant_id=actor["tenant_id"],
        workspace_id=actor["workspace_id"],
        operation_id=operation_id,
        factor_revision=factor_revision,
        target_id=target_id,
        target_required=target_required,
    )
    return _audit(
        audit_logger=audit_logger,
        expected=expected,
        description=description,
        user_email=actor["user_email"],
        request=request,
        metadata_extra=metadata_extra,
    )


def _expected_for_operation(snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    action = snapshot["action"]
    audit_action = _AUDIT_ACTIONS.get(action)
    if not audit_action:
        return None
    target_required = action in _AUDIT_TARGET_REQUIRED
    target_id = snapshot["target_id"] if target_required else None
    return _audit_expected(
        audit_action=audit_action,
        resource=_audit_resource(action, snapshot["user_id"], target_id),
        user_id=snapshot["user_id"],
        tenant_id=snapshot["tenant_id"],
        workspace_id=snapshot["workspace_id"],
        operation_id=snapshot["operation_id"],
        factor_revision=snapshot["factor_revision"],
        target_id=target_id,
        target_required=target_required,
    )


def _link_operation_audit(
    user_id: str, operation_id: str, audit_id: Optional[str],
) -> None:
    """Best-effort correlation of the safe audit observation to the receipt."""
    if not audit_id:
        return
    try:
        with get_db_session() as db:
            db.execute(
                update(AuthTwoFactorOperation)
                .where(
                    AuthTwoFactorOperation.id == str(operation_id),
                    AuthTwoFactorOperation.user_id == str(user_id),
                )
                .values(audit_id=str(audit_id))
            )
            db.commit()
    except Exception as exc:  # noqa: BLE001 — receipt remains valid
        logger.warning(
            "Could not link 2FA operation audit id: operation_id=%s "
            "error_class=%s",
            operation_id, type(exc).__name__)


def _verification(
    state: Dict[str, Any], *, effect: str, state_ok: bool = True,
) -> Dict[str, Any]:
    if not state_ok:
        return {
            "status": "refuted",
            "effect": effect,
            "replay": "do_not_repeat",
            "audit_id": state.get("audit_id"),
        }
    status = str(state.get("status") or "unavailable")
    result = {
        "status": status,
        "effect": effect,
        "audit_id": state.get("audit_id"),
    }
    if status != "verified":
        result["replay"] = "do_not_repeat"
    return result


def _verify_operation(
    user_id: str, operation_id: str, action: str,
) -> bool:
    with get_db_session() as db:
        row = db.query(AuthTwoFactorOperation).filter(
            AuthTwoFactorOperation.id == str(operation_id),
            AuthTwoFactorOperation.user_id == str(user_id),
            AuthTwoFactorOperation.action == action,
        ).first()
        return row is not None and str(row.status or "") == "committed"


def _verify_user_state(
    user_id: str, *,
    enabled: bool,
    revision: int,
    secret_present: Optional[bool] = None,
    secret_equals: Optional[str] = None,
    backup_codes_len: Optional[int] = None,
    last_step_min: Optional[int] = None,
) -> bool:
    with get_db_session() as db:
        user = db.query(User).filter(User.id == str(user_id)).first()
        if user is None:
            return False
        if bool(user.two_factor_enabled) is not bool(enabled):
            return False
        if int(user.two_factor_revision or 0) != int(revision):
            return False
        if secret_present is not None and (
                bool(user.two_factor_secret) is not bool(secret_present)):
            return False
        if secret_equals is not None and str(
                user.two_factor_secret or "") != str(secret_equals):
            return False
        if backup_codes_len is not None and len(
                user.two_factor_backup_codes or []) != int(backup_codes_len):
            return False
        if last_step_min is not None and (
                user.two_factor_last_totp_step is None
                or int(user.two_factor_last_totp_step) < int(last_step_min)):
            return False
        return True


def _verify_backup_rows(
    user_id: str, revision: int, *, total: int,
    consumed: int = 0,
) -> bool:
    with get_db_session() as db:
        rows = db.query(AuthTwoFactorBackupCode).filter(
            AuthTwoFactorBackupCode.user_id == str(user_id),
            AuthTwoFactorBackupCode.factor_revision == int(revision),
        ).all()
        if len(rows) != int(total):
            return False
        consumed_count = sum(1 for row in rows if row.consumed_at is not None)
        return consumed_count == int(consumed)


def _verify_backup_consumed(
    user_id: str, row_id: str, operation_id: str,
    code: Optional[str] = None,
) -> bool:
    with get_db_session() as db:
        row = db.query(AuthTwoFactorBackupCode).filter(
            AuthTwoFactorBackupCode.id == str(row_id),
            AuthTwoFactorBackupCode.user_id == str(user_id),
        ).first()
        if row is None or row.consumed_at is None:
            return False
        if str(row.operation_id or "") != str(operation_id):
            return False
        if code is not None:
            user = db.query(User).filter(User.id == str(user_id)).first()
            if user is None:
                return False
            current = [str(c) for c in (user.two_factor_backup_codes or [])]
            if str(code) in current:
                return False
        return True


# ---------------------------------------------------------------------------
# Reconcile the original operation for a retry
# ---------------------------------------------------------------------------

def _reconcile_operation(
    user_id: str, operation_id: str,
) -> Dict[str, Any]:
    """Recompute the original operation's verification from durable state.

    A retry never creates a new authentication event. It may acknowledge the
    original result only when the effect, actor authority and audit evidence
    all still reconcile.
    """
    with get_db_session() as db:
        row = db.query(AuthTwoFactorOperation).filter(
            AuthTwoFactorOperation.id == str(operation_id),
            AuthTwoFactorOperation.user_id == str(user_id),
        ).first()
        if row is None:
            return {
                "status": "unavailable",
                "effect": "unknown",
                "audit_id": None,
                "operation_id": str(operation_id),
                "target_id": None,
            }
        snapshot = {
            "operation_id": str(row.id),
            "user_id": str(row.user_id),
            "action": str(row.action or ""),
            "target_id": (
                str(row.target_id) if row.target_id is not None else None),
            "factor_revision": int(row.factor_revision or 0),
            "tenant_id": _raw_scope(row.tenant_id),
            "workspace_id": _raw_scope(row.workspace_id),
            "audit_id": str(row.audit_id) if row.audit_id else None,
            "receipt": _parse_receipt(row.response_json),
        }

        actor_row = db.query(User).filter(User.id == str(user_id)).first()
        actor_ok = bool(
            actor_row is not None
            and snapshot["receipt"].get("actor_digest")
            and _actor_digest(_actor_snapshot(actor_row))
            == snapshot["receipt"]["actor_digest"]
        )

        effect_status = "verified"
        action = snapshot["action"]
        if action == "backup_verify":
            consumed = db.query(AuthTwoFactorBackupCode).filter(
                AuthTwoFactorBackupCode.id == str(snapshot["target_id"]),
                AuthTwoFactorBackupCode.user_id == str(user_id),
                AuthTwoFactorBackupCode.consumed_at.is_not(None),
                AuthTwoFactorBackupCode.operation_id
                == snapshot["operation_id"],
            ).first()
            if consumed is None:
                existing = db.query(AuthTwoFactorBackupCode).filter(
                    AuthTwoFactorBackupCode.id == str(snapshot["target_id"]),
                    AuthTwoFactorBackupCode.user_id == str(user_id),
                ).first()
                effect_status = "unavailable" if existing is None else "refuted"
        elif action == "verify_action":
            action_row = db.query(HITLAction).filter(
                HITLAction.id == str(snapshot["target_id"])).first()
            if action_row is None:
                effect_status = "unavailable"
            elif (
                str(action_row.status or "") != "approved"
                or str(action_row.reviewed_by or "") != str(user_id)
                or action_row.reviewed_at is None
            ):
                effect_status = "refuted"
            elif not snapshot["receipt"].get("target_digest"):
                effect_status = "unavailable"
            elif _action_digest(_action_snapshot(action_row)) != (
                    snapshot["receipt"]["target_digest"]):
                effect_status = "refuted"
        elif action == "enable":
            user_row = db.query(User).filter(User.id == str(user_id)).first()
            if user_row is None:
                effect_status = "unavailable"
            elif (
                not bool(user_row.two_factor_enabled)
                or int(user_row.two_factor_revision or 0)
                != snapshot["factor_revision"]
            ):
                effect_status = "refuted"
            else:
                code_count = db.query(AuthTwoFactorBackupCode).filter(
                    AuthTwoFactorBackupCode.user_id == str(user_id),
                    AuthTwoFactorBackupCode.factor_revision
                    == snapshot["factor_revision"],
                ).count()
                if code_count != BACKUP_CODE_COUNT:
                    effect_status = "refuted"
        elif action == "disable":
            user_row = db.query(User).filter(User.id == str(user_id)).first()
            if user_row is None:
                effect_status = "unavailable"
            elif (
                bool(user_row.two_factor_enabled)
                or user_row.two_factor_secret is not None
                or user_row.two_factor_backup_codes is not None
                or int(user_row.two_factor_revision or 0)
                != snapshot["factor_revision"]
            ):
                effect_status = "refuted"
            else:
                code_count = db.query(AuthTwoFactorBackupCode).filter(
                    AuthTwoFactorBackupCode.user_id == str(user_id),
                    AuthTwoFactorBackupCode.factor_revision
                    == snapshot["factor_revision"],
                ).count()
                if code_count != 0:
                    effect_status = "refuted"
        elif action == "setup":
            user_row = db.query(User).filter(User.id == str(user_id)).first()
            if user_row is None:
                effect_status = "unavailable"
            elif (
                bool(user_row.two_factor_enabled)
                or not user_row.two_factor_secret
                or int(user_row.two_factor_revision or 0)
                != snapshot["factor_revision"]
            ):
                effect_status = "refuted"
        else:
            effect_status = "unavailable"

    expected = _expected_for_operation(snapshot)
    if expected is None:
        audit_status = "unavailable"
    else:
        audit_status = _verify_audit_observation(
            snapshot["audit_id"], expected)["status"]

    statuses = [effect_status, audit_status]
    if not actor_ok:
        statuses.append("refuted")
    if "refuted" in statuses:
        status = "refuted"
    elif "unavailable" in statuses:
        status = "unavailable"
    else:
        status = "verified"
    return {
        "status": status,
        "effect": "committed",
        "audit_id": snapshot["audit_id"],
        "operation_id": snapshot["operation_id"],
        "target_id": snapshot["target_id"],
    }


def _already_applied(
    user_id: str,
    operation_id: str,
    *,
    data: Optional[Dict[str, Any]] = None,
    message: str = "This 2FA operation was already applied.",
    action_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Acknowledge a mutation only when the original operation reconciles.

    Authentication grants must not turn an unverified original outcome into a
    success just because a receipt row exists.
    """
    state = _reconcile_operation(user_id, operation_id)
    if state["status"] == "verified":
        return {
            "status": "already_applied",
            "data": data,
            "message": message,
            "operation_id": operation_id,
            "audit_id": state.get("audit_id"),
            "action_id": action_id,
            "verification": {
                "status": "already_applied",
                "effect": "committed",
                "replay": "do_not_repeat",
                "audit_id": state.get("audit_id"),
            },
        }
    return {
        "status": "committed_unverified",
        "data": data,
        "message": (
            "The original 2FA effect is committed but remains unverified; "
            "do not repeat it blindly."),
        "operation_id": operation_id,
        "audit_id": state.get("audit_id"),
        "action_id": action_id,
        "verification": {
            "status": state["status"],
            "effect": "committed",
            "replay": "do_not_repeat",
            "audit_id": state.get("audit_id"),
        },
    }


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def setup_2fa_verified(
    *, user_id: str, request, operation_id: Optional[str] = None,
    audit_logger=audit_service,
) -> Dict[str, Any]:
    operation_id = str(operation_id or "").strip() or _new_operation_id()
    with get_db_session() as db:
        user = _load_user(db, user_id)
        if user is None:
            return _refused(
                "User not found", http_status=404, error_code="NOT_FOUND")
        actor = _actor_snapshot(user)
        if not _actor_authorized(actor):
            return _refused(
                "Account is not active", http_status=403,
                error_code="PERMISSION_DENIED")
        if user.two_factor_enabled:
            return _refused(
                "2FA is already enabled", http_status=409,
                error_code="CONFLICT")

        revision = actor["factor_revision"]
        existing = _existing_operation(db, user.id, operation_id)
        if existing is not None:
            if not _operation_matches(
                    existing, "setup", user, target_id="setup"):
                return _operation_conflict()
            if user.two_factor_enabled:
                return _refused(
                    "2FA is already enabled", http_status=409,
                    error_code="CONFLICT")
            if user.two_factor_secret:
                secret = user.two_factor_secret
                return {
                    "status": "already_pending",
                    "secret": secret,
                    "otpauth_url": pyotp.TOTP(secret).provisioning_uri(
                        name=user.email, issuer_name=ISSUER_NAME),
                    "operation_id": operation_id,
                    "audit_id": existing.audit_id,
                    "verification": {
                        "status": "already_pending",
                        "effect": "none",
                        "replay": "do_not_repeat",
                    },
                }
            return _operation_conflict()

        if user.two_factor_secret:
            secret = user.two_factor_secret
            state = _write_audit(
                audit_logger=audit_logger,
                actor=actor,
                action="setup",
                audit_action="2fa_setup_replayed",
                operation_id=operation_id,
                factor_revision=revision,
                description=f"2FA setup replayed for user: {user.email}",
                request=request,
            )
            return {
                "status": "already_pending",
                "secret": secret,
                "otpauth_url": pyotp.TOTP(secret).provisioning_uri(
                    name=user.email, issuer_name=ISSUER_NAME),
                "operation_id": operation_id,
                "audit_id": state.get("audit_id"),
                "verification": _verification(state, effect="none"),
            }

        secret = pyotp.random_base32()
        new_revision = revision + 1
        insert_material = _operation_material(
            "setup", user, new_revision, target_id="setup")
        actor_digest = _actor_digest(actor)
        statement = (
            update(User)
            .where(
                User.id == actor["user_id"],
                _factor_disabled_predicate(),
                User.two_factor_secret.is_(None),
                User.two_factor_revision == revision,
                *_user_authority_predicates(actor),
            )
            .values(
                two_factor_secret=secret,
                two_factor_revision=new_revision,
                two_factor_last_totp_step=None,
                two_factor_backup_codes=None,
            )
        )
        try:
            with db.no_autoflush:
                result = db.execute(statement)
                if result.rowcount != 1:
                    db.rollback()
                    return _refused(
                        "2FA setup changed concurrently; retry to recover "
                        "the pending enrollment",
                        http_status=409,
                        error_code="CONFLICT",
                    )
                db.query(AuthTwoFactorBackupCode).filter(
                    AuthTwoFactorBackupCode.user_id == user.id).delete()
                db.add(AuthTwoFactorOperation(
                    id=operation_id,
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    workspace_id=user.workspace_id,
                    action="setup",
                    target_id="setup",
                    factor_revision=new_revision,
                    material_fingerprint=insert_material,
                    status="committed",
                    response_json=json.dumps({
                        "revision": new_revision,
                        "actor_digest": actor_digest,
                    }),
                ))
                db.commit()
        except IntegrityError:
            db.rollback()
            existing = _existing_operation(db, user.id, operation_id)
            if existing is not None and _operation_matches(
                    existing, "setup", user, target_id="setup"):
                return _refused(
                    "2FA setup is already committed; retry to recover the "
                    "pending enrollment",
                    http_status=409,
                    error_code="CONFLICT",
                )
            return _operation_conflict()
        except Exception as exc:  # noqa: BLE001 — commit outcome unknown
            logger.error(
                "2FA setup write outcome unknown: operation_id=%s "
                "stage=setup_commit error_class=%s",
                operation_id, type(exc).__name__)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            return _effect_unknown(operation_id, stage="setup_commit")

        state = _write_audit(
            audit_logger=audit_logger,
            actor=actor,
            action="setup",
            operation_id=operation_id,
            factor_revision=new_revision,
            description=f"2FA setup initiated for user: {user.email}",
            request=request,
        )
        _link_operation_audit(user.id, operation_id, state.get("audit_id"))
        state_ok = (
            _verify_user_state(
                user.id, enabled=False, revision=new_revision,
                secret_equals=secret)
            and _verify_operation(user.id, operation_id, "setup")
        )
        verification = _verification(
            state, effect="committed", state_ok=state_ok)
        return {
            "status": "verified" if state_ok and state["status"] == "verified"
            else "committed_unverified",
            "secret": secret,
            "otpauth_url": pyotp.TOTP(secret).provisioning_uri(
                name=user.email, issuer_name=ISSUER_NAME),
            "operation_id": operation_id,
            "audit_id": state.get("audit_id"),
            "verification": verification,
        }


# ---------------------------------------------------------------------------
# Enable / disable
# ---------------------------------------------------------------------------

def enable_2fa_verified(
    *, user_id: str, code: str, request,
    operation_id: Optional[str] = None, audit_logger=audit_service,
) -> Dict[str, Any]:
    operation_id = str(operation_id or "").strip() or _new_operation_id()
    with get_db_session() as db:
        user = _load_user(db, user_id)
        if user is None:
            return _refused(
                "User not found", http_status=404, error_code="NOT_FOUND")
        actor = _actor_snapshot(user)
        revision = actor["factor_revision"]
        existing = _existing_operation(db, user.id, operation_id)
        if existing is not None:
            if not _operation_matches(existing, "enable", user, code):
                return _operation_conflict()
            return _already_applied(
                user.id,
                operation_id,
                data={"backup_codes": None, "already_applied": True},
            )
        if not _actor_authorized(actor):
            return _refused(
                "Account is not active", http_status=403,
                error_code="PERMISSION_DENIED")
        if user.two_factor_enabled:
            return _refused(
                "2FA is already enabled", http_status=409,
                error_code="CONFLICT")
        if not actor["factor_secret"]:
            return _refused(
                "2FA setup not initiated", field="two_factor_secret")
        totp = pyotp.TOTP(actor["factor_secret"])
        if not totp.verify(code):
            return _refused("Invalid verification code", field="code")
        step = _current_step()
        codes = generate_backup_codes(BACKUP_CODE_COUNT)
        new_revision = revision + 1
        insert_material = _operation_material(
            "enable", user, new_revision, code)
        actor_digest = _actor_digest(actor)
        statement = (
            update(User)
            .where(
                User.id == actor["user_id"],
                _factor_disabled_predicate(),
                User.two_factor_revision == revision,
                or_(
                    User.two_factor_last_totp_step.is_(None),
                    User.two_factor_last_totp_step < step,
                ),
                *_user_authority_predicates(actor),
            )
            .values(
                two_factor_enabled=True,
                two_factor_backup_codes=codes,
                two_factor_revision=new_revision,
                two_factor_last_totp_step=step,
            )
        )
        try:
            with db.no_autoflush:
                result = db.execute(statement)
                if result.rowcount != 1:
                    db.rollback()
                    return _refused(
                        "Factor state changed or this code was already used",
                        field="code", http_status=409,
                        error_code="CONFLICT")
                db.query(AuthTwoFactorBackupCode).filter(
                    AuthTwoFactorBackupCode.user_id == user.id).delete()
                for backup_code in codes:
                    db.add(AuthTwoFactorBackupCode(
                        user_id=user.id,
                        tenant_id=user.tenant_id,
                        workspace_id=user.workspace_id,
                        code_fingerprint=_code_fingerprint(
                            user.id, backup_code),
                        factor_revision=new_revision,
                    ))
                db.add(AuthTwoFactorOperation(
                    id=operation_id,
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    workspace_id=user.workspace_id,
                    action="enable",
                    factor_revision=new_revision,
                    material_fingerprint=insert_material,
                    status="committed",
                    response_json=json.dumps({
                        "backup_codes_delivered": True,
                        "actor_digest": actor_digest,
                    }),
                ))
                db.commit()
        except IntegrityError:
            db.rollback()
            existing = _existing_operation(db, user.id, operation_id)
            if existing is not None and _operation_matches(
                    existing, "enable", user, code):
                return _already_applied(
                    user.id,
                    operation_id,
                    data={"backup_codes": None, "already_applied": True},
                )
            return _operation_conflict()
        except Exception as exc:  # noqa: BLE001 — commit outcome unknown
            logger.error(
                "2FA enable write outcome unknown: operation_id=%s "
                "stage=enable_commit error_class=%s",
                operation_id, type(exc).__name__)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            return _effect_unknown(operation_id, stage="enable_commit")

        state = _write_audit(
            audit_logger=audit_logger,
            actor=actor,
            action="enable",
            operation_id=operation_id,
            factor_revision=new_revision,
            description=f"2FA enabled for user: {user.email}",
            request=request,
        )
        _link_operation_audit(user.id, operation_id, state.get("audit_id"))
        state_ok = (
            _verify_user_state(
                user.id, enabled=True, revision=new_revision,
                secret_present=True,
                backup_codes_len=BACKUP_CODE_COUNT,
                last_step_min=step)
            and _verify_operation(user.id, operation_id, "enable")
            and _verify_backup_rows(
                user.id, new_revision, total=BACKUP_CODE_COUNT)
        )
        verification = _verification(
            state, effect="committed", state_ok=state_ok)
        status = "verified" if state_ok and state["status"] == "verified" else (
            "committed_unverified")
        return {
            "status": status,
            "data": {"backup_codes": codes if state_ok else None},
            "message": "2FA enabled successfully",
            "operation_id": operation_id,
            "audit_id": state.get("audit_id"),
            "verification": verification,
        }


def disable_2fa_verified(
    *, user_id: str, code: str, request,
    operation_id: Optional[str] = None, audit_logger=audit_service,
) -> Dict[str, Any]:
    operation_id = str(operation_id or "").strip() or _new_operation_id()
    with get_db_session() as db:
        user = _load_user(db, user_id)
        if user is None:
            return _refused(
                "User not found", http_status=404, error_code="NOT_FOUND")
        actor = _actor_snapshot(user)
        revision = actor["factor_revision"]
        existing = _existing_operation(db, user.id, operation_id)
        if existing is not None:
            if not _operation_matches(existing, "disable", user, code):
                return _operation_conflict()
            return _already_applied(
                user.id, operation_id, data={},
                message="2FA already disabled.")
        if not _actor_authorized(actor):
            return _refused(
                "Account is not active", http_status=403,
                error_code="PERMISSION_DENIED")
        if not user.two_factor_enabled:
            return _refused(
                "2FA is not enabled", field="two_factor_enabled")
        if not actor["factor_secret"]:
            return _refused(
                "2FA is not enabled", field="two_factor_enabled")
        totp = pyotp.TOTP(actor["factor_secret"])
        if not totp.verify(code):
            return _refused("Invalid verification code", field="code")
        step = _current_step()
        new_revision = revision + 1
        insert_material = _operation_material(
            "disable", user, new_revision, code)
        actor_digest = _actor_digest(actor)
        statement = (
            update(User)
            .where(
                User.id == actor["user_id"],
                User.two_factor_enabled.is_(True),
                User.two_factor_revision == revision,
                or_(
                    User.two_factor_last_totp_step.is_(None),
                    User.two_factor_last_totp_step < step,
                ),
                *_user_authority_predicates(actor),
            )
            .values(
                two_factor_enabled=False,
                two_factor_secret=None,
                two_factor_backup_codes=None,
                two_factor_revision=new_revision,
                two_factor_last_totp_step=None,
            )
        )
        try:
            with db.no_autoflush:
                result = db.execute(statement)
                if result.rowcount != 1:
                    db.rollback()
                    return _refused(
                        "Factor state changed or this code was already used",
                        field="code", http_status=409,
                        error_code="CONFLICT")
                db.query(AuthTwoFactorBackupCode).filter(
                    AuthTwoFactorBackupCode.user_id == user.id).delete()
                db.add(AuthTwoFactorOperation(
                    id=operation_id,
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    workspace_id=user.workspace_id,
                    action="disable",
                    factor_revision=new_revision,
                    material_fingerprint=insert_material,
                    status="committed",
                    response_json=json.dumps({
                        "actor_digest": actor_digest,
                    }),
                ))
                db.commit()
        except IntegrityError:
            db.rollback()
            existing = _existing_operation(db, user.id, operation_id)
            if existing is not None and _operation_matches(
                    existing, "disable", user, code):
                return _already_applied(
                    user.id, operation_id, data={},
                    message="2FA already disabled.")
            return _operation_conflict()
        except Exception as exc:  # noqa: BLE001 — commit outcome unknown
            logger.error(
                "2FA disable write outcome unknown: operation_id=%s "
                "stage=disable_commit error_class=%s",
                operation_id, type(exc).__name__)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            return _effect_unknown(operation_id, stage="disable_commit")

        state = _write_audit(
            audit_logger=audit_logger,
            actor=actor,
            action="disable",
            operation_id=operation_id,
            factor_revision=new_revision,
            description=f"2FA disabled for user: {user.email}",
            request=request,
        )
        _link_operation_audit(user.id, operation_id, state.get("audit_id"))
        state_ok = (
            _verify_user_state(
                user.id, enabled=False, revision=new_revision,
                secret_present=False, backup_codes_len=0)
            and _verify_operation(user.id, operation_id, "disable")
            and _verify_backup_rows(user.id, new_revision, total=0)
        )
        verification = _verification(
            state, effect="committed", state_ok=state_ok)
        return {
            "status": "verified" if state_ok and state["status"] == "verified"
            else "committed_unverified",
            "data": {},
            "message": "2FA disabled successfully",
            "operation_id": operation_id,
            "audit_id": state.get("audit_id"),
            "verification": verification,
        }


# ---------------------------------------------------------------------------
# Backup code consumption
# ---------------------------------------------------------------------------

def _backfill_backup_rows(db, user: User) -> Optional[User]:
    """One-time compatibility projection for pre-repair plaintext codes.

    Only runs when no durable rows exist at all. Partial/stale mirrors must
    never create a fresh row for a code that was already consumed.
    """
    existing = db.query(AuthTwoFactorBackupCode).filter(
        AuthTwoFactorBackupCode.user_id == user.id).first()
    if existing is not None:
        return user
    revision = int(user.two_factor_revision or 0)
    for code in user.two_factor_backup_codes or []:
        db.add(AuthTwoFactorBackupCode(
            user_id=user.id,
            tenant_id=user.tenant_id,
            workspace_id=user.workspace_id,
            code_fingerprint=_code_fingerprint(user.id, str(code)),
            factor_revision=revision,
        ))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return db.query(User).filter(User.id == user.id).first()
    return user


def verify_backup_code_verified(
    *, user_id: str, code: str, request,
    operation_id: Optional[str] = None, audit_logger=audit_service,
) -> Dict[str, Any]:
    operation_id = str(operation_id or "").strip() or _new_operation_id()
    with get_db_session() as db:
        user = _load_user(db, user_id)
        if user is None:
            return _refused(
                "User not found", http_status=404, error_code="NOT_FOUND")
        actor = _actor_snapshot(user)
        revision = actor["factor_revision"]
        existing = _existing_operation(db, user.id, operation_id)
        if existing is not None:
            if not _operation_matches(
                    existing, "backup_verify", user, code):
                return _operation_conflict()
            return _already_applied(
                user.id,
                operation_id,
                data={"remaining_codes": None, "already_applied": True},
            )
        if not _actor_authorized(actor):
            return _refused(
                "Account is not active", http_status=403,
                error_code="PERMISSION_DENIED")
        if not user.two_factor_enabled:
            return _refused(
                "2FA is not enabled", field="two_factor_enabled")
        user = _backfill_backup_rows(db, user)
        if user is None:
            return _refused(
                "User not found", http_status=404, error_code="NOT_FOUND")
        fingerprint = _code_fingerprint(user.id, code)
        row = (
            db.query(AuthTwoFactorBackupCode)
            .filter(
                AuthTwoFactorBackupCode.user_id == user.id,
                AuthTwoFactorBackupCode.factor_revision == revision,
                AuthTwoFactorBackupCode.code_fingerprint == fingerprint,
            )
            .first()
        )
        if row is None:
            return _refused("Invalid backup code", field="code")
        original_codes = [
            str(c) for c in (user.two_factor_backup_codes or [])]
        remaining = [c for c in original_codes if c != str(code)]
        insert_material = _operation_material(
            "backup_verify", user, revision, code)
        actor_digest = _actor_digest(actor)
        try:
            with db.no_autoflush:
                consumed = db.execute(
                    update(AuthTwoFactorBackupCode)
                    .where(
                        AuthTwoFactorBackupCode.id == row.id,
                        AuthTwoFactorBackupCode.user_id == user.id,
                        AuthTwoFactorBackupCode.factor_revision == revision,
                        AuthTwoFactorBackupCode.code_fingerprint
                        == fingerprint,
                        AuthTwoFactorBackupCode.consumed_at.is_(None),
                    )
                    .values(
                        consumed_at=datetime.now(timezone.utc),
                        operation_id=operation_id,
                    )
                )
                if consumed.rowcount != 1:
                    db.rollback()
                    return _refused(
                        "Backup code was already consumed",
                        field="code", http_status=409,
                        error_code="CONFLICT")
                updated_user = db.execute(
                    update(User)
                    .where(
                        User.id == user.id,
                        User.two_factor_enabled.is_(True),
                        User.two_factor_revision == revision,
                        _json_exact(
                            User.two_factor_backup_codes, original_codes),
                        *_user_authority_predicates(actor),
                    )
                    .values(two_factor_backup_codes=remaining)
                )
                if updated_user.rowcount != 1:
                    db.rollback()
                    return _refused(
                        "Factor state changed during backup-code consumption",
                        field="code", http_status=409,
                        error_code="CONFLICT")
                db.add(AuthTwoFactorOperation(
                    id=operation_id,
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    workspace_id=user.workspace_id,
                    action="backup_verify",
                    target_id=row.id,
                    factor_revision=revision,
                    material_fingerprint=insert_material,
                    status="committed",
                    response_json=json.dumps({
                        "remaining_codes": len(remaining),
                        "actor_digest": actor_digest,
                    }),
                ))
                db.commit()
        except IntegrityError:
            db.rollback()
            existing = _existing_operation(db, user.id, operation_id)
            if existing is not None and _operation_matches(
                    existing, "backup_verify", user, code):
                return _already_applied(
                    user.id,
                    operation_id,
                    data={"remaining_codes": None, "already_applied": True},
                )
            return _operation_conflict()
        except Exception as exc:  # noqa: BLE001 — commit outcome unknown
            logger.error(
                "2FA backup-code write outcome unknown: operation_id=%s "
                "stage=backup_commit error_class=%s",
                operation_id, type(exc).__name__)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            return _effect_unknown(operation_id, stage="backup_commit")

        state = _write_audit(
            audit_logger=audit_logger,
            actor=actor,
            action="backup_verify",
            operation_id=operation_id,
            factor_revision=revision,
            target_id=row.id,
            target_required=True,
            description=f"2FA backup code used for user: {user.email}",
            request=request,
            metadata_extra={"remaining_codes": len(remaining)},
        )
        _link_operation_audit(user.id, operation_id, state.get("audit_id"))
        state_ok = (
            _verify_backup_consumed(
                user.id, row.id, operation_id, code=code)
            and _verify_operation(user.id, operation_id, "backup_verify")
        )
        verification = _verification(
            state, effect="committed", state_ok=state_ok)
        return {
            "status": "verified" if state_ok and state["status"] == "verified"
            else "committed_unverified",
            "data": {
                "remaining_codes": len(remaining) if state_ok else None
            },
            "message": "Backup code verified and consumed",
            "operation_id": operation_id,
            "audit_id": state.get("audit_id"),
            "verification": verification,
        }


# ---------------------------------------------------------------------------
# Verify a high-stakes HITL action
# ---------------------------------------------------------------------------

async def verify_action_2fa_verified(
    *, user_id: str, action_id: str, code: str, request,
    operation_id: Optional[str] = None, audit_logger=audit_service,
) -> Dict[str, Any]:
    from types import SimpleNamespace

    from core.hitl_service import hitl_service
    from core.intervention_service import intervention_service

    operation_id = str(operation_id or "").strip() or _new_operation_id()
    with get_db_session() as db:
        user = _load_user(db, user_id)
        if user is None:
            return _refused(
                "User not found", http_status=404, error_code="NOT_FOUND")
        actor = _actor_snapshot(user)
        revision = actor["factor_revision"]
        existing = _existing_operation(db, user.id, operation_id)
        if existing is not None:
            if not _operation_matches(
                    existing, "verify_action", user, code, str(action_id)):
                return _operation_conflict()
            return _already_applied(
                user.id,
                operation_id,
                data={"status": "approved", "already_applied": True},
                action_id=str(action_id),
            )
        if not _actor_authorized(actor):
            return _refused(
                "Account is not active", http_status=403,
                error_code="PERMISSION_DENIED")
        if not user.two_factor_enabled or not actor["factor_secret"]:
            return _refused(
                "2FA is not enabled for your account",
                field="two_factor_enabled")
        action = db.query(HITLAction).filter(
            HITLAction.id == str(action_id)).first()
        if action is None:
            return _refused(
                "HITL action not found", http_status=404,
                error_code="NOT_FOUND")
        action_snapshot = _action_snapshot(action)
        if not _scope_value_allowed(action.tenant_id, user.tenant_id):
            return _refused(
                "HITL action belongs to a different tenant",
                http_status=403, error_code="PERMISSION_DENIED")
        if not _scope_value_allowed(action.workspace_id, user.workspace_id):
            return _refused(
                "HITL action belongs to a different workspace",
                http_status=403, error_code="PERMISSION_DENIED")
        denial = intervention_service._required_role_denial(
            db, action, user.id)
        if denial:
            return _refused(
                denial, http_status=403, error_code="PERMISSION_DENIED")
        required_column = str(getattr(action, "required_role", "") or "").strip()
        if required_column:
            try:
                from core.models import UserRole
                from core.security.rbac import user_meets_role

                required_role = UserRole(required_column.lower())
                if not user_meets_role(user, required_role):
                    return _refused(
                        f"Approver role is below the required role "
                        f"{required_role.value}",
                        http_status=403, error_code="PERMISSION_DENIED")
            except ValueError:
                return _refused(
                    "Action requires an unreadable role; decision denied",
                    http_status=403, error_code="PERMISSION_DENIED")

        if action.status in ("approved", "rejected", "expired"):
            return _refused(
                f"HITL action is already {action.status}",
                http_status=409, error_code="CONFLICT")

        totp = pyotp.TOTP(actor["factor_secret"])
        if not totp.verify(code):
            return _refused("Invalid verification code", field="code")
        step = _current_step()
        now = datetime.now(timezone.utc)
        insert_material = _operation_material(
            "verify_action", user, revision, code, target_id=action.id)
        actor_digest = _actor_digest(actor)
        target_digest = _action_digest(action_snapshot)
        try:
            with db.no_autoflush:
                step_update = db.execute(
                    update(User)
                    .where(
                        User.id == actor["user_id"],
                        User.two_factor_enabled.is_(True),
                        User.two_factor_revision == revision,
                        or_(
                            User.two_factor_last_totp_step.is_(None),
                            User.two_factor_last_totp_step < step,
                        ),
                        *_user_authority_predicates(actor),
                    )
                    .values(two_factor_last_totp_step=step)
                )
                if step_update.rowcount != 1:
                    db.rollback()
                    return _refused(
                        "This code/time-step was already used or the factor "
                        "changed",
                        field="code", http_status=409,
                        error_code="CONFLICT")
                action_update = db.execute(
                    update(HITLAction)
                    .where(*_action_predicates(action_snapshot))
                    .values(
                        status="approved",
                        reviewed_by=actor["user_id"],
                        reviewed_at=now,
                    )
                )
                if action_update.rowcount != 1:
                    db.rollback()
                    return _refused(
                        "HITL action was already resolved or its scope moved",
                        http_status=409, error_code="CONFLICT")
                db.add(AuthTwoFactorOperation(
                    id=operation_id,
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    workspace_id=user.workspace_id,
                    action="verify_action",
                    target_id=action.id,
                    factor_revision=revision,
                    material_fingerprint=insert_material,
                    status="committed",
                    response_json=json.dumps({
                        "action_id": action.id,
                        "resolution": "approved",
                        "actor_digest": actor_digest,
                        "target_digest": target_digest,
                    }),
                ))
                db.commit()
        except IntegrityError:
            db.rollback()
            existing = _existing_operation(db, user.id, operation_id)
            if existing is not None and _operation_matches(
                    existing, "verify_action", user, code, action.id):
                return _already_applied(
                    user.id,
                    operation_id,
                    data={"status": "approved", "already_applied": True},
                    action_id=action.id,
                )
            return _operation_conflict()
        except Exception as exc:  # noqa: BLE001 — commit outcome unknown
            logger.error(
                "2FA action-resolution write outcome unknown: "
                "operation_id=%s stage=action_commit error_class=%s",
                operation_id, type(exc).__name__)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            return _effect_unknown(
                operation_id, action_id=action.id, stage="action_commit")

        state = _write_audit(
            audit_logger=audit_logger,
            actor=actor,
            action="verify_action",
            operation_id=operation_id,
            factor_revision=revision,
            target_id=action.id,
            target_required=True,
            description=(
                f"HITL Action {action.id} approved via 2FA by {user.email}"),
            request=request,
        )
        _link_operation_audit(user.id, operation_id, state.get("audit_id"))

        # Durable readback: exact action material, resolver identity and scope.
        with get_db_session() as read_db:
            persisted = read_db.query(HITLAction).filter(
                HITLAction.id == action.id).first()
            persisted_ok = bool(
                persisted is not None
                and str(persisted.status or "") == "approved"
                and str(persisted.reviewed_by or "") == str(actor["user_id"])
                and persisted.reviewed_at is not None
                and _action_digest(_action_snapshot(persisted))
                == target_digest
            )
        state_ok = bool(
            persisted_ok
            and _verify_user_state(
                user.id, enabled=True, revision=revision,
                last_step_min=step)
            and _verify_operation(user.id, operation_id, "verify_action")
        )
        verification = _verification(
            state, effect="committed", state_ok=state_ok)
        if not state_ok:
            return {
                "status": "committed_unverified",
                "data": None,
                "message": "HITL action committed but readback did not match.",
                "operation_id": operation_id,
                "audit_id": state.get("audit_id"),
                "action_id": action.id,
                "verification": verification,
            }

        if state["status"] == "verified":
            # Dispatch the exact approved snapshot, never a re-read that may
            # have changed after the claim. A verified replay does not call
            # this path, so no duplicate callback is dispatched.
            try:
                await hitl_service._resume_workflow(SimpleNamespace(
                    id=action_snapshot["action_id"],
                    params=action_snapshot["params"],
                    resolver_id=actor["user_id"],
                ))
            except Exception as exc:  # noqa: BLE001 — decision stands
                logger.warning(
                    "HITL %s approved but resume callback failed: "
                    "error_class=%s",
                    action.id, type(exc).__name__)
            return {
                "status": "verified",
                "data": {"status": "approved"},
                "message": "Action approved successfully via 2FA",
                "operation_id": operation_id,
                "audit_id": state.get("audit_id"),
                "action_id": action.id,
                "verification": verification,
            }
        return {
            "status": "committed_unverified",
            "data": None,
            "message": "HITL action committed but audit was not verified.",
            "operation_id": operation_id,
            "audit_id": state.get("audit_id"),
            "action_id": action.id,
            "verification": verification,
        }
