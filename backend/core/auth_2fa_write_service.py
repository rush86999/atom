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
from typing import Any, Dict, Optional, Tuple

import pyotp
from sqlalchemy import or_, update
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


def _action_scope_predicates(action: HITLAction):
    """Bind the HITL update to the exact scope snapshot read for this action."""
    tenant = str(action.tenant_id or "").strip()
    workspace = str(action.workspace_id or "").strip()
    predicates = [HITLAction.id == action.id]
    if tenant:
        predicates.append(HITLAction.tenant_id == tenant)
    else:
        predicates.append(or_(
            HITLAction.tenant_id.is_(None),
            HITLAction.tenant_id == "",
        ))
    if workspace:
        predicates.append(HITLAction.workspace_id == workspace)
    else:
        predicates.append(or_(
            HITLAction.workspace_id.is_(None),
            HITLAction.workspace_id == "",
        ))
    return predicates


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
    error: Optional[str] = None,
) -> Dict[str, Any]:
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
            "error": error,
        },
    }


def _already_applied(
    row: AuthTwoFactorOperation,
    *,
    data: Optional[Dict[str, Any]] = None,
    message: str = "This 2FA operation was already applied.",
) -> Dict[str, Any]:
    try:
        receipt = json.loads(row.response_json or "{}")
    except (TypeError, ValueError):
        receipt = {}
    return {
        "status": "already_applied",
        "data": data if data is not None else receipt,
        "message": message,
        "operation_id": row.id,
        "audit_id": row.audit_id,
        "verification": {
            "status": "already_applied",
            "effect": "committed",
            "replay": "do_not_repeat",
        },
    }


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


def _audit(
    *,
    audit_logger,
    action: str,
    description: str,
    user: User,
    request,
    metadata: Dict[str, Any],
    resource: Optional[str] = None,
) -> Dict[str, Any]:
    """Write then independently read back the audit observation.

    The factor/action state has already committed. A missing/unreadable audit
    row is reported honestly; it is never assumed from the logger's return.
    """
    audit_id = None
    try:
        with get_db_session() as audit_db:
            audit_id = audit_logger.log_event(
                audit_db,
                event_type=AuditEventType.UPDATE.value,
                action=action,
                description=description,
                user_id=user.id,
                user_email=user.email,
                workspace_id=user.workspace_id or "default",
                security_level=SecurityLevel.HIGH.value,
                resource=resource,
                metadata=metadata,
                request=request,
            )
    except Exception as exc:  # noqa: BLE001 — state already committed
        logger.warning("2FA audit write failed: %s", exc)
        audit_id = None
    if not audit_id:
        return {"status": "unavailable", "audit_id": None}
    audit_id = str(audit_id)
    try:
        with get_db_session() as db:
            row = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
            if row is None:
                return {"status": "unavailable", "audit_id": audit_id}
            if str(row.action or "") != action:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.user_id or "") != str(user.id):
                return {"status": "refuted", "audit_id": audit_id}
            expected_workspace = str(user.workspace_id or "default")
            if str(row.workspace_id or "") not in (
                    expected_workspace, "default"):
                return {"status": "refuted", "audit_id": audit_id}
            try:
                row_meta = json.loads(row.metadata_json or "{}")
            except (TypeError, ValueError):
                row_meta = {}
            if str(row_meta.get("operation_id") or "") != str(
                    metadata.get("operation_id") or ""):
                return {"status": "refuted", "audit_id": audit_id}
            expected_tenant = str(user.tenant_id or "")
            observed_tenant = str(row_meta.get("tenant_id") or "")
            if expected_tenant and observed_tenant and (
                    expected_tenant != observed_tenant):
                return {"status": "refuted", "audit_id": audit_id}
            return {"status": "verified", "audit_id": audit_id}
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning("2FA audit read-back failed: %s", exc)
        return {"status": "unavailable", "audit_id": audit_id}


def _audit_metadata(
    user: User, operation_id: str, factor_revision: int,
    **extra: Any,
) -> Dict[str, Any]:
    return {
        "operation_id": operation_id,
        "factor_revision": int(factor_revision or 0),
        "tenant_id": str(user.tenant_id or ""),
        "workspace_id": str(user.workspace_id or ""),
        **extra,
    }


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
        logger.warning("Could not link 2FA operation audit id: %s", exc)


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
    user_id: str, row_id: str, operation_id: str, remaining: list,
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
        user = db.query(User).filter(User.id == str(user_id)).first()
        if user is None:
            return False
        current = [str(c) for c in (user.two_factor_backup_codes or [])]
        return current == [str(c) for c in remaining]


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
        if user.two_factor_enabled:
            return _refused(
                "2FA is already enabled", http_status=409,
                error_code="CONFLICT")

        revision = int(user.two_factor_revision or 0)
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
            state = _audit(
                audit_logger=audit_logger,
                action="2fa_setup_replayed",
                description=f"2FA setup replayed for user: {user.email}",
                user=user,
                request=request,
                metadata=_audit_metadata(
                    user, operation_id, revision, target_id="setup"),
                resource=f"user:{user.id}:2fa",
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
        statement = (
            update(User)
            .where(
                User.id == user.id,
                User.two_factor_enabled.is_(False),
                User.two_factor_secret.is_(None),
                User.two_factor_revision == revision,
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
                    response_json=json.dumps({"revision": new_revision}),
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
            logger.exception("2FA setup write outcome unknown: %s", exc)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            return _effect_unknown(operation_id, error=str(exc))

        state = _audit(
            audit_logger=audit_logger,
            action="2fa_setup_initiated",
            description=f"2FA setup initiated for user: {user.email}",
            user=user,
            request=request,
            metadata=_audit_metadata(
                user, operation_id, new_revision, target_id="setup"),
            resource=f"user:{user.id}:2fa",
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
        revision = int(user.two_factor_revision or 0)
        existing = _existing_operation(db, user.id, operation_id)
        if existing is not None:
            if not _operation_matches(existing, "enable", user, code):
                return _operation_conflict()
            return _already_applied(
                existing,
                data={"backup_codes": None, "already_applied": True},
            )
        if user.two_factor_enabled:
            return _refused(
                "2FA is already enabled", http_status=409,
                error_code="CONFLICT")
        if not user.two_factor_secret:
            return _refused(
                "2FA setup not initiated", field="two_factor_secret")
        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(code):
            return _refused("Invalid verification code", field="code")
        step = _current_step()
        codes = generate_backup_codes(BACKUP_CODE_COUNT)
        new_revision = revision + 1
        insert_material = _operation_material(
            "enable", user, new_revision, code)
        statement = (
            update(User)
            .where(
                User.id == user.id,
                User.two_factor_enabled.is_(False),
                User.two_factor_revision == revision,
                or_(
                    User.two_factor_last_totp_step.is_(None),
                    User.two_factor_last_totp_step < step,
                ),
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
                    response_json=json.dumps(
                        {"backup_codes_delivered": True}),
                ))
                db.commit()
        except IntegrityError:
            db.rollback()
            existing = _existing_operation(db, user.id, operation_id)
            if existing is not None and _operation_matches(
                    existing, "enable", user, code):
                return _already_applied(
                    existing,
                    data={"backup_codes": None, "already_applied": True},
                )
            return _operation_conflict()
        except Exception as exc:  # noqa: BLE001 — commit outcome unknown
            logger.exception("2FA enable write outcome unknown: %s", exc)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            return _effect_unknown(operation_id, error=str(exc))

        state = _audit(
            audit_logger=audit_logger,
            action="2fa_enabled",
            description=f"2FA enabled for user: {user.email}",
            user=user,
            request=request,
            metadata=_audit_metadata(
                user, operation_id, new_revision, target_id="enable"),
            resource=f"user:{user.id}:2fa",
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
        revision = int(user.two_factor_revision or 0)
        existing = _existing_operation(db, user.id, operation_id)
        if existing is not None:
            if not _operation_matches(existing, "disable", user, code):
                return _operation_conflict()
            return _already_applied(
                existing, data={}, message="2FA already disabled.")
        if not user.two_factor_enabled:
            return _refused(
                "2FA is not enabled", field="two_factor_enabled")
        if not user.two_factor_secret:
            return _refused(
                "2FA is not enabled", field="two_factor_enabled")
        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(code):
            return _refused("Invalid verification code", field="code")
        step = _current_step()
        new_revision = revision + 1
        insert_material = _operation_material(
            "disable", user, new_revision, code)
        statement = (
            update(User)
            .where(
                User.id == user.id,
                User.two_factor_enabled.is_(True),
                User.two_factor_revision == revision,
                or_(
                    User.two_factor_last_totp_step.is_(None),
                    User.two_factor_last_totp_step < step,
                ),
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
                    response_json=json.dumps({}),
                ))
                db.commit()
        except IntegrityError:
            db.rollback()
            existing = _existing_operation(db, user.id, operation_id)
            if existing is not None and _operation_matches(
                    existing, "disable", user, code):
                return _already_applied(
                    existing, data={}, message="2FA already disabled.")
            return _operation_conflict()
        except Exception as exc:  # noqa: BLE001 — commit outcome unknown
            logger.exception("2FA disable write outcome unknown: %s", exc)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            return _effect_unknown(operation_id, error=str(exc))

        state = _audit(
            audit_logger=audit_logger,
            action="2fa_disabled",
            description=f"2FA disabled for user: {user.email}",
            user=user,
            request=request,
            metadata=_audit_metadata(
                user, operation_id, new_revision, target_id="disable"),
            resource=f"user:{user.id}:2fa",
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

def _backfill_backup_rows(db, user: User) -> User:
    """One-time compatibility projection for pre-repair plaintext codes.

    Concurrent first use is expected: both requests may see no rows and race
    to insert. The unique constraint picks one; the loser rolls back and
    reloads the winner's rows, then proceeds to the conditional consumption.
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
        revision = int(user.two_factor_revision or 0)
        existing = _existing_operation(db, user.id, operation_id)
        if existing is not None:
            if not _operation_matches(
                    existing, "backup_verify", user, code):
                return _operation_conflict()
            return _already_applied(
                existing,
                data={"remaining_codes": None, "already_applied": True},
            )
        if not user.two_factor_enabled:
            return _refused(
                "2FA is not enabled", field="two_factor_enabled")
        user = _backfill_backup_rows(db, user)
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
        remaining = [
            c for c in (user.two_factor_backup_codes or [])
            if str(c) != str(code)
        ]
        insert_material = _operation_material(
            "backup_verify", user, revision, code)
        try:
            with db.no_autoflush:
                consumed = db.execute(
                    update(AuthTwoFactorBackupCode)
                    .where(
                        AuthTwoFactorBackupCode.id == row.id,
                        AuthTwoFactorBackupCode.user_id == user.id,
                        AuthTwoFactorBackupCode.factor_revision == revision,
                        AuthTwoFactorBackupCode.code_fingerprint == fingerprint,
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
                    response_json=json.dumps(
                        {"remaining_codes": len(remaining)}),
                ))
                db.commit()
        except IntegrityError:
            db.rollback()
            existing = _existing_operation(db, user.id, operation_id)
            if existing is not None and _operation_matches(
                    existing, "backup_verify", user, code):
                return _already_applied(
                    existing,
                    data={"remaining_codes": None, "already_applied": True},
                )
            return _operation_conflict()
        except Exception as exc:  # noqa: BLE001 — commit outcome unknown
            logger.exception(
                "2FA backup-code write outcome unknown: %s", exc)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            return _effect_unknown(operation_id, error=str(exc))

        state = _audit(
            audit_logger=audit_logger,
            action="2fa_backup_code_used",
            description=f"2FA backup code used for user: {user.email}",
            user=user,
            request=request,
            metadata=_audit_metadata(
                user, operation_id, revision, target_id=row.id,
                remaining_codes=len(remaining)),
            resource=f"user:{user.id}:2fa",
        )
        _link_operation_audit(user.id, operation_id, state.get("audit_id"))
        state_ok = (
            _verify_backup_consumed(
                user.id, row.id, operation_id, remaining)
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
    from core.hitl_service import hitl_service
    from core.intervention_service import intervention_service

    operation_id = str(operation_id or "").strip() or _new_operation_id()
    with get_db_session() as db:
        user = _load_user(db, user_id)
        if user is None:
            return _refused(
                "User not found", http_status=404, error_code="NOT_FOUND")
        if not user.two_factor_enabled or not user.two_factor_secret:
            return _refused(
                "2FA is not enabled for your account",
                field="two_factor_enabled")
        action = db.query(HITLAction).filter(
            HITLAction.id == str(action_id)).first()
        if action is None:
            return _refused(
                "HITL action not found", http_status=404,
                error_code="NOT_FOUND")
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

        revision = int(user.two_factor_revision or 0)
        existing = _existing_operation(db, user.id, operation_id)
        if existing is not None:
            if not _operation_matches(
                    existing, "verify_action", user, code, action.id):
                return _operation_conflict()
            return _already_applied(
                existing,
                data={"status": action.status, "already_applied": True},
            )
        if action.status in ("approved", "rejected", "expired"):
            return _refused(
                f"HITL action is already {action.status}",
                http_status=409, error_code="CONFLICT")

        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(code):
            return _refused("Invalid verification code", field="code")
        step = _current_step()
        now = datetime.now(timezone.utc)
        insert_material = _operation_material(
            "verify_action", user, revision, code, target_id=action.id)
        try:
            with db.no_autoflush:
                step_update = db.execute(
                    update(User)
                    .where(
                        User.id == user.id,
                        User.two_factor_enabled.is_(True),
                        User.two_factor_revision == revision,
                        or_(
                            User.two_factor_last_totp_step.is_(None),
                            User.two_factor_last_totp_step < step,
                        ),
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
                    .where(
                        HITLAction.status.in_(["pending", "pending_2fa"]),
                        *_action_scope_predicates(action),
                    )
                    .values(
                        status="approved",
                        reviewed_by=user.id,
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
                    }),
                ))
                db.commit()
        except IntegrityError:
            db.rollback()
            existing = _existing_operation(db, user.id, operation_id)
            if existing is not None and _operation_matches(
                    existing, "verify_action", user, code, action.id):
                return _already_applied(
                    existing,
                    data={"status": "approved", "already_applied": True},
                )
            return _operation_conflict()
        except Exception as exc:  # noqa: BLE001 — commit outcome unknown
            logger.exception(
                "2FA action-resolution write outcome unknown: %s", exc)
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            return _effect_unknown(
                operation_id, action_id=action.id, error=str(exc))

        state = _audit(
            audit_logger=audit_logger,
            action="hitl_action_verified_2fa",
            description=(
                f"HITL Action {action.id} approved via 2FA by {user.email}"),
            user=user,
            request=request,
            metadata=_audit_metadata(
                user, operation_id, revision, target_id=action.id),
            resource=f"hitl:{action.id}",
        )
        _link_operation_audit(user.id, operation_id, state.get("audit_id"))
        verification = _verification(state, effect="committed")

        # Durable readback: action status, resolver identity and scope.
        with get_db_session() as read_db:
            persisted = read_db.query(HITLAction).filter(
                HITLAction.id == action.id).first()
            persisted_ok = bool(
                persisted is not None
                and str(persisted.status or "") == "approved"
                and str(persisted.reviewed_by or "") == str(user.id)
                and persisted.reviewed_at is not None
                and _scope_value_allowed(
                    persisted.tenant_id, user.tenant_id)
                and _scope_value_allowed(
                    persisted.workspace_id, user.workspace_id)
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
            # The action is durably approved and attributed. The callback is
            # best-effort and never turns a committed approval into a refusal.
            try:
                with get_db_session() as callback_db:
                    callback_action = callback_db.query(HITLAction).filter(
                        HITLAction.id == action.id).first()
                    if callback_action is not None:
                        callback_action.resolver_id = user.id
                        await hitl_service._resume_workflow(callback_action)
            except Exception as exc:  # noqa: BLE001 — decision stands
                logger.warning(
                    "HITL %s approved but resume callback failed: %s",
                    action.id, exc)
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
