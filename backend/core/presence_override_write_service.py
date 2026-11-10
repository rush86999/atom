"""Verified manual presence override decisions.

The public override routes previously wrote UserActivity directly and returned
the service object with no operation identity, audit receipt or independent
readback. This module keeps the existing UserActivity table and
UserActivityService but binds actor/target/request material and the audit row
in one transaction, uses CAS on the prior activity state, then verifies the
result from a fresh session.

No new store, engine, router or review lifecycle is added.
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

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from core.auth import SECRET_KEY
from core.models import (
    AuditEventType,
    AuditLog,
    SecurityLevel,
    User,
    UserActivity,
    UserActivitySession,
    UserState,
)
from core.user_activity_service import UserActivityService

logger = logging.getLogger(__name__)

SCHEMA = "atom-presence-override-1"
OPERATION_PREFIX = "presence"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_ACTION_SET = "presence_override_set"
_ACTION_CLEAR = "presence_override_cleared"


def normalize_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Return an aware UTC datetime; naive values are interpreted as UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_expiry(value: Optional[str]) -> Optional[datetime]:
    if value is None or str(value).strip() == "":
        return None
    parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    return normalize_utc(parsed)


def iso_utc(value: Optional[datetime]) -> Optional[str]:
    normalized = normalize_utc(value)
    return normalized.isoformat() if normalized is not None else None


def _db_dt(value: Optional[datetime]) -> Optional[datetime]:
    normalized = normalize_utc(value)
    return normalized.replace(tzinfo=None) if normalized is not None else None


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _operation_id(supplied: Optional[str]) -> str:
    supplied = str(supplied or "").strip()
    candidate = supplied or f"{OPERATION_PREFIX}:{uuid.uuid4().hex}"
    prefix = f"{OPERATION_PREFIX}:"
    if not candidate.startswith(prefix):
        candidate = f"{prefix}{candidate}"
    if not _SAFE_OPERATION_RE.fullmatch(candidate):
        raise ValueError("operation_id is malformed")
    return candidate


def _fresh_session(db: Session) -> Session:
    return sessionmaker(bind=db.get_bind())()


def _activity_data(activity: Optional[UserActivity]) -> Dict[str, Any]:
    if activity is None:
        return {
            "user_id": None,
            "state": UserState.offline.value,
            "last_activity_at": datetime.now(timezone.utc).isoformat(),
            "manual_override": False,
            "manual_override_expires_at": None,
        }
    return {
        "user_id": str(activity.user_id),
        "state": activity.state.value,
        "last_activity_at": iso_utc(activity.last_activity_at),
        "manual_override": bool(activity.manual_override),
        "manual_override_expires_at": iso_utc(
            activity.manual_override_expires_at),
    }


def _data_digest(data: Dict[str, Any]) -> str:
    return _digest({
        "user_id": str(data.get("user_id") or ""),
        "state": str(data.get("state") or ""),
        "manual_override": bool(data.get("manual_override")),
        "manual_override_expires_at": data.get("manual_override_expires_at"),
    })


def _refused(message: str, *, http_status: int = 403,
             code: str = "AUTHORITY_REQUIRED") -> Dict[str, Any]:
    return {
        "status": "refused", "error": message, "error_code": code,
        "http_status": http_status,
        "verification": {"status": "not_attempted", "effect": "none"},
    }


def _conflict(message: str, *, code: str = "STALE_TARGET") -> Dict[str, Any]:
    return {
        "status": "conflict", "error": message, "error_code": code,
        "http_status": 409,
        "verification": {"status": "refuted", "effect": "none",
                         "replay": "safe_after_refresh"},
    }


def _not_applied(message: str) -> Dict[str, Any]:
    return {
        "status": "not_applied", "error": message,
        "error_code": "PRESENCE_TRANSACTION_ROLLED_BACK",
        "http_status": 409,
        "verification": {"status": "refused", "effect": "none",
                         "replay": "safe_after_refresh"},
    }


def _committed_unverified(operation_id: str, audit_state: Dict[str, Any],
                          data: Optional[Dict[str, Any]],
                          target: str,
                          target_status: Optional[str] = None) -> Dict[str, Any]:
    status = audit_state.get("status", "unavailable")
    if status == "verified" and target_status:
        status = target_status
    return {
        "status": "committed_unverified",
        "data": data,
        "message": "The presence change committed but its readback did not verify.",
        "operation_id": operation_id,
        "audit_id": audit_state.get("audit_id"),
        "target_id": target,
        "verification": {
            "status": status,
            "effect": "committed",
            "replay": "do_not_repeat",
            "audit_id": audit_state.get("audit_id"),
        },
    }


def _effect_unknown(operation_id: str, target: str) -> Dict[str, Any]:
    return {
        "status": "effect_unknown",
        "data": None,
        "message": ("The presence change may have committed but confirmation "
                    "was lost. Reconcile the operation; do not repeat blindly."),
        "operation_id": operation_id,
        "audit_id": None,
        "target_id": target,
        "verification": {
            "status": "unavailable", "effect": "unknown",
            "replay": "do_not_repeat", "error": "COMMIT_OUTCOME_UNKNOWN",
        },
    }


def _with_receipt(data: Dict[str, Any], *, operation_id: str,
                  audit_id: Optional[str], verification_status: str,
                  effect: str = "committed",
                  replay: Optional[str] = None) -> Dict[str, Any]:
    result = dict(data)
    result["data"] = dict(data)
    result["status"] = verification_status
    verification = {"status": verification_status, "effect": effect,
                    "audit_id": audit_id}
    if replay:
        verification["replay"] = replay
    result["verification"] = verification
    result["operation_id"] = operation_id
    result["audit_id"] = audit_id
    return result


def _resolve_actor(db: Session, actor: Any) -> Dict[str, Any]:
    actor_id = str(getattr(actor, "id", "") or "")
    if not actor_id:
        return {"ok": False, "http_status": 401,
                "error_code": "UNAUTHENTICATED",
                "message": "Authentication required"}
    row = db.query(User).filter(User.id == actor_id).first()
    if row is None or not bool(row.is_active) or str(row.status or "") != "active":
        return {"ok": False, "http_status": 403,
                "error_code": "ACCOUNT_INACTIVE",
                "message": "This account is not active; refresh and sign in again"}
    return {
        "ok": True, "id": actor_id, "email": str(row.email or ""),
        "role": str(row.role or ""), "status": str(row.status or ""),
        "tenant_id": str(row.tenant_id or ""),
        "workspace_id": str(row.workspace_id or ""),
        "raw_tenant_id": row.tenant_id,
        "raw_workspace_id": row.workspace_id,
    }


def _exact(column, value: Any):
    return column.is_(None) if value is None else column == str(value)


def _claim_actor(db: Session, actor: Dict[str, Any]) -> bool:
    """Pin the validated raw actor snapshot in this transaction.

    A read-only resolve is not enough: the current user row must still have
    the same id, active flag, status, raw tenant/workspace and role when the
    target CAS and audit receipt commit.
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


def _require_own(actor: Dict[str, Any], target_id: str) -> Optional[Dict[str, Any]]:
    if str(target_id) != str(actor.get("id") or ""):
        return _refused("Cannot manage another user's activity state")
    return None


def _prior_data(activity: Optional[UserActivity]) -> Dict[str, Any]:
    return _activity_data(activity) if activity is not None else {
        "user_id": None, "state": UserState.offline.value,
        "manual_override": False, "manual_override_expires_at": None,
    }


def _audit_expected(*, operation_id: str, action: str, target: str,
                    request_digest: str, prior_digest: str,
                    result_digest: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema": SCHEMA,
        "operation_id": operation_id,
        "action": action,
        "event_type": AuditEventType.UPDATE.value,
        "target_id": target,
        "request_digest": request_digest,
        "prior_digest": prior_digest,
        "result_digest": result_digest,
        "actor_id": actor["id"],
        "actor_role": actor["role"],
        "tenant_id": actor["tenant_id"],
        "workspace_id": actor["workspace_id"],
        "resource": f"user_activity:{target}",
    }


def _audit_row(expected: Dict[str, Any], actor: Dict[str, Any],
               description: str) -> AuditLog:
    metadata = {
        key: expected[key] for key in (
            "schema", "operation_id", "action", "event_type", "target_id",
            "request_digest", "prior_digest", "result_digest", "actor_id",
            "actor_role", "tenant_id", "workspace_id")
    }
    return AuditLog(
        id=expected["operation_id"],
        event_type=expected["event_type"],
        security_level=SecurityLevel.HIGH.value,
        threat_level="none",
        user_id=expected["actor_id"],
        user_email=actor["email"],
        tenant_id=expected["tenant_id"],
        workspace_id=actor["workspace_id"],
        resource=expected["resource"],
        action=expected["action"],
        description=description,
        metadata_json=json.dumps(metadata, sort_keys=True),
        success=True,
    )


def _verify_audit(db: Session, expected: Dict[str, Any]) -> Dict[str, Any]:
    operation_id = expected["operation_id"]
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(AuditLog).filter(
                AuditLog.id == operation_id).first()
            if row is None:
                return {"status": "unavailable", "audit_id": operation_id}
            if (str(row.event_type or "") != expected["event_type"]
                    or str(row.action or "") != expected["action"]
                    or str(row.user_id or "") != expected["actor_id"]
                    or str(row.tenant_id or "") != expected["tenant_id"]
                    or str(row.resource or "") != expected["resource"]
                    or row.success is not True):
                return {"status": "refuted", "audit_id": operation_id}
            metadata = json.loads(row.metadata_json or "{}")
            if not isinstance(metadata, dict):
                return {"status": "unavailable", "audit_id": operation_id}
            for key in ("schema", "operation_id", "action", "event_type",
                        "target_id", "request_digest", "prior_digest",
                        "result_digest", "actor_id", "actor_role",
                        "tenant_id", "workspace_id"):
                if metadata.get(key) != expected[key]:
                    return {"status": "refuted", "audit_id": operation_id}
            return {"status": "verified", "audit_id": operation_id}
    except Exception as exc:  # noqa: BLE001
        logger.warning("presence audit readback failed: %s %s",
                       operation_id, type(exc).__name__)
        return {"status": "unavailable", "audit_id": operation_id}


def _verify_activity(db: Session, target: str,
                     expected_digest: str) -> Dict[str, Any]:
    try:
        with _fresh_session(db) as fresh:
            activity = fresh.query(UserActivity).filter(
                UserActivity.user_id == target).first()
            data = _activity_data(activity)
            return {"status": "verified" if _data_digest(data) == expected_digest
                    else "refuted", "data": data}
    except Exception as exc:  # noqa: BLE001
        logger.warning("presence target readback failed: %s %s",
                       target, type(exc).__name__)
        return {"status": "unavailable", "data": None}


def _expected_from_metadata(metadata: Dict[str, Any], operation_id: str) -> Dict[str, Any]:
    return {
        **{key: metadata.get(key) for key in (
            "schema", "event_type", "target_id", "request_digest",
            "prior_digest", "result_digest", "actor_id", "actor_role",
            "tenant_id", "workspace_id")},
        "operation_id": operation_id,
        "action": metadata.get("action"),
        "resource": f"user_activity:{metadata.get('target_id')}",
    }


def _replay(db: Session, operation_id: str, expected: Dict[str, Any],
            *, actor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _claim_actor(db, actor):
        db.rollback()
        return _refused(
            "current user authority changed; refresh and retry",
            http_status=403, code="AUTHORITY_CHANGED")
    with _fresh_session(db) as fresh:
        row = fresh.query(AuditLog).filter(AuditLog.id == operation_id).first()
        if row is None:
            return None
        try:
            metadata = json.loads(row.metadata_json or "{}")
        except (TypeError, ValueError):
            metadata = None
        if not isinstance(metadata, dict):
            return _committed_unverified(
                operation_id, {"status": "unavailable", "audit_id": operation_id},
                None, str(expected.get("target_id") or ""))
        if (
            metadata.get("schema") != expected["schema"]
            or metadata.get("action") != expected["action"]
            or metadata.get("target_id") != expected["target_id"]
            or metadata.get("request_digest") != expected["request_digest"]
            or metadata.get("actor_id") != expected["actor_id"]
            or metadata.get("actor_role") != actor["role"]
            or metadata.get("tenant_id") != actor["tenant_id"]
            or metadata.get("workspace_id") != actor["workspace_id"]
        ):
            if metadata.get("actor_id") == actor["id"] and (
                metadata.get("actor_role") != actor["role"]
                or metadata.get("tenant_id") != actor["tenant_id"]
                or metadata.get("workspace_id") != actor["workspace_id"]
            ):
                return _refused(
                    "current user authority changed; refresh and retry",
                    http_status=403, code="AUTHORITY_CHANGED")
            return _conflict(
                "operation_id is bound to different request material or actor",
                code="OPERATION_CONFLICT")
        audit_expected = _expected_from_metadata(metadata, operation_id)
        audit_state = _verify_audit(db, audit_expected)
        target_state = _verify_activity(
            db, audit_expected["target_id"], audit_expected["result_digest"])
        if audit_state["status"] == "verified" and target_state["status"] == "verified":
            return _with_receipt(
                target_state["data"] or {}, operation_id=operation_id,
                audit_id=operation_id, verification_status="already_applied",
                replay="do_not_repeat")
        return _committed_unverified(
            operation_id, audit_state, target_state.get("data"),
            audit_expected["target_id"], target_state.get("status"))


def _expiry_condition(column, value: Optional[datetime]):
    return column.is_(None) if value is None else column == _db_dt(value)


def _load_activity(db: Session, target: str) -> Optional[UserActivity]:
    return db.query(UserActivity).filter(
        UserActivity.user_id == target).first()


def _same_override(activity: Optional[UserActivity], state: UserState,
                   expiry: Optional[datetime]) -> bool:
    if activity is None or not activity.manual_override:
        return False
    return (activity.state == state
            and normalize_utc(activity.manual_override_expires_at)
            == normalize_utc(expiry))


async def _commit_set(db: Session, *, target: str, state: UserState,
                      expiry: Optional[datetime], operation_id: str,
                      expected: Dict[str, Any], actor: Dict[str, Any],
                      activity: Optional[UserActivity]) -> Dict[str, Any]:
    prior = _prior_data(activity)
    prior_digest = _data_digest(prior)
    expected["prior_digest"] = prior_digest
    if _same_override(activity, state, expiry):
        data = _activity_data(activity)
        expected["result_digest"] = _data_digest(data)
        db.add(_audit_row(expected, actor, "Presence override set (no change)"))
        try:
            db.commit()
        except Exception:
            db.rollback()
            return _effect_unknown(operation_id, target)
        audit_state = _verify_audit(db, expected)
        target_state = _verify_activity(db, target, expected["result_digest"])
        if audit_state["status"] == "verified" and target_state["status"] == "verified":
            return _with_receipt(
                target_state["data"] or data, operation_id=operation_id,
                audit_id=operation_id, verification_status="no_change",
                effect="none", replay="safe_after_refresh")
        return _committed_unverified(
            operation_id, audit_state, target_state.get("data"), target,
            target_state.get("status"))

    now = datetime.now(timezone.utc)
    result_data = {
        "user_id": target, "state": state.value,
        "last_activity_at": iso_utc(activity.last_activity_at) if activity else iso_utc(now),
        "manual_override": True,
        "manual_override_expires_at": iso_utc(expiry),
    }
    result_digest = _data_digest(result_data)
    expected["result_digest"] = result_digest
    try:
        if activity is None:
            db.add(UserActivity(
                id=f"ua_{uuid.uuid4()}", user_id=target, state=state,
                last_activity_at=_db_dt(now), manual_override=True,
                manual_override_expires_at=_db_dt(expiry),
                created_at=_db_dt(now), updated_at=_db_dt(now)))
        else:
            prior_expiry = activity.manual_override_expires_at
            prior_bool = bool(activity.manual_override)
            prior_state = activity.state
            updated = db.execute(
                update(UserActivity)
                .where(
                    UserActivity.id == activity.id,
                    UserActivity.user_id == target,
                    UserActivity.manual_override == prior_bool,
                    UserActivity.state == prior_state,
                    _expiry_condition(
                        UserActivity.manual_override_expires_at, prior_expiry))
                .values(
                    state=state, manual_override=True,
                    manual_override_expires_at=_db_dt(expiry),
                    updated_at=_db_dt(now)))
            if updated.rowcount != 1:
                db.rollback()
                return _conflict("presence changed; refresh and retry")
        db.add(_audit_row(expected, actor, "Presence override set"))
        try:
            db.commit()
        except IntegrityError:
            raise
        except Exception:
            db.rollback()
            return _effect_unknown(operation_id, target)
    except IntegrityError:
        db.rollback()
        replayed = _replay(db, operation_id, expected, actor=actor)
        return replayed or _conflict(
            "presence operation conflicts with current state",
            code="STALE_TARGET")
    except Exception:
        db.rollback()
        return _not_applied("presence transaction did not commit")

    audit_state = _verify_audit(db, expected)
    target_state = _verify_activity(db, target, result_digest)
    if audit_state["status"] == "verified" and target_state["status"] == "verified":
        return _with_receipt(
            target_state["data"] or result_data, operation_id=operation_id,
            audit_id=operation_id, verification_status="verified")
    return _committed_unverified(
        operation_id, audit_state, target_state.get("data"), target,
        target_state.get("status"))


async def verified_set_override(
    db: Session, *, actor: Any, target_user_id: str, state: UserState,
    expires_at: Optional[datetime], operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    actor_info = _resolve_actor(db, actor)
    if not actor_info.get("ok"):
        return _refused(
            str(actor_info.get("message") or "Authentication required"),
            http_status=int(actor_info.get("http_status") or 401),
            code=str(actor_info.get("error_code") or "UNAUTHENTICATED"))
    own_refusal = _require_own(actor_info, target_user_id)
    if own_refusal:
        return own_refusal
    try:
        op_id = _operation_id(operation_id)
    except ValueError as exc:
        return _refused(str(exc), http_status=422, code="VALIDATION_ERROR")
    expiry = normalize_utc(expires_at)
    request_digest = _digest({
        "action": _ACTION_SET, "target": target_user_id,
        "state": state.value, "expires_at": iso_utc(expiry),
        "actor_id": actor_info["id"], "actor_role": actor_info["role"],
        "tenant_id": actor_info["tenant_id"],
    })
    expected = _audit_expected(
        operation_id=op_id, action=_ACTION_SET, target=target_user_id,
        request_digest=request_digest, prior_digest="", result_digest="",
        actor=actor_info)
    if not _claim_actor(db, actor_info):
        db.rollback()
        return _refused(
            "current user authority changed; refresh and retry",
            http_status=403, code="AUTHORITY_CHANGED")
    replayed = _replay(db, op_id, expected, actor=actor_info)
    if replayed is not None:
        return replayed
    activity = _load_activity(db, target_user_id)
    return await _commit_set(
        db, target=target_user_id, state=state, expiry=expiry,
        operation_id=op_id, expected=expected, actor=actor_info,
        activity=activity)


async def verified_clear_override(
    db: Session, *, actor: Any, target_user_id: str,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    actor_info = _resolve_actor(db, actor)
    if not actor_info.get("ok"):
        return _refused(
            str(actor_info.get("message") or "Authentication required"),
            http_status=int(actor_info.get("http_status") or 401),
            code=str(actor_info.get("error_code") or "UNAUTHENTICATED"))
    own_refusal = _require_own(actor_info, target_user_id)
    if own_refusal:
        return own_refusal
    try:
        op_id = _operation_id(operation_id)
    except ValueError as exc:
        return _refused(str(exc), http_status=422, code="VALIDATION_ERROR")
    request_digest = _digest({
        "action": _ACTION_CLEAR, "target": target_user_id,
        "actor_id": actor_info["id"], "actor_role": actor_info["role"],
        "tenant_id": actor_info["tenant_id"],
    })
    expected = _audit_expected(
        operation_id=op_id, action=_ACTION_CLEAR, target=target_user_id,
        request_digest=request_digest, prior_digest="", result_digest="",
        actor=actor_info)
    if not _claim_actor(db, actor_info):
        db.rollback()
        return _refused(
            "current user authority changed; refresh and retry",
            http_status=403, code="AUTHORITY_CHANGED")
    replayed = _replay(db, op_id, expected, actor=actor_info)
    if replayed is not None:
        return replayed
    activity = _load_activity(db, target_user_id)
    if activity is None:
        return _refused("UserActivity not found", http_status=404,
                        code="NOT_FOUND")
    prior = _activity_data(activity)
    expected["prior_digest"] = _data_digest(prior)
    if not activity.manual_override and activity.manual_override_expires_at is None:
        expected["result_digest"] = _data_digest(prior)
        db.add(_audit_row(expected, actor_info,
                          "Presence override cleared (no change)"))
        try:
            db.commit()
        except Exception:
            db.rollback()
            return _effect_unknown(operation_id, target)
        audit_state = _verify_audit(db, expected)
        target_state = _verify_activity(
            db, target_user_id, expected["result_digest"])
        if audit_state["status"] == "verified" and target_state["status"] == "verified":
            return _with_receipt(
                target_state["data"] or prior, operation_id=op_id,
                audit_id=op_id, verification_status="no_change",
                effect="none", replay="safe_after_refresh")
        return _committed_unverified(
            op_id, audit_state, target_state.get("data"), target_user_id,
            target_state.get("status"))

    prior_expiry = activity.manual_override_expires_at
    now = datetime.now(timezone.utc)
    try:
        updated = db.execute(
            update(UserActivity)
            .where(
                UserActivity.id == activity.id,
                UserActivity.user_id == target_user_id,
                UserActivity.manual_override.is_(True),
                _expiry_condition(
                    UserActivity.manual_override_expires_at, prior_expiry))
            .values(manual_override=False,
                    manual_override_expires_at=None,
                    updated_at=_db_dt(now)))
        if updated.rowcount != 1:
            db.rollback()
            return _conflict("presence changed; refresh and retry")
        activity = _load_activity(db, target_user_id)
        await UserActivityService(db)._recalculate_activity_state(activity, commit=False)
        result_data = _activity_data(activity)
        expected["result_digest"] = _data_digest(result_data)
        db.add(_audit_row(expected, actor_info, "Presence override cleared"))
        try:
            db.commit()
        except IntegrityError:
            raise
        except Exception:
            db.rollback()
            return _effect_unknown(op_id, target_user_id)
    except IntegrityError:
        db.rollback()
        replayed = _replay(db, op_id, expected, actor=actor_info)
        return replayed or _conflict("presence operation conflicts with current state")
    except Exception:
        db.rollback()
        return _not_applied("presence transaction did not commit")

    audit_state = _verify_audit(db, expected)
    target_state = _verify_activity(
        db, target_user_id, expected["result_digest"])
    if audit_state["status"] == "verified" and target_state["status"] == "verified":
        return _with_receipt(
            target_state["data"] or result_data, operation_id=op_id,
            audit_id=op_id, verification_status="verified")
    return _committed_unverified(
        op_id, audit_state, target_state.get("data"), target_user_id,
        target_state.get("status"))


async def expire_manual_overrides(db: Session,
                                  now: Optional[datetime] = None) -> int:
    now = normalize_utc(now or datetime.now(timezone.utc))
    activities = db.query(UserActivity).filter(
        UserActivity.manual_override.is_(True),
        UserActivity.manual_override_expires_at.isnot(None)).all()
    expired = 0
    for activity in activities:
        expiry = normalize_utc(activity.manual_override_expires_at)
        if expiry is not None and now >= expiry:
            prior_expiry = activity.manual_override_expires_at
            updated = db.execute(
                update(UserActivity)
                .where(
                    UserActivity.id == activity.id,
                    UserActivity.manual_override.is_(True),
                    _expiry_condition(
                        UserActivity.manual_override_expires_at, prior_expiry))
                .values(manual_override=False,
                        manual_override_expires_at=None,
                        updated_at=_db_dt(now)))
            if updated.rowcount == 1:
                expired += 1
                fresh = _load_activity(db, activity.user_id)
                await UserActivityService(db)._recalculate_activity_state(fresh, commit=False)
    if expired:
        db.commit()
    return expired


async def verified_get_state(db: Session, *, actor: Any,
                             target_user_id: str) -> Dict[str, Any]:
    actor_info = _resolve_actor(db, actor)
    if not actor_info.get("ok"):
        return _refused(
            str(actor_info.get("message") or "Authentication required"),
            http_status=int(actor_info.get("http_status") or 401),
            code=str(actor_info.get("error_code") or "UNAUTHENTICATED"))
    await expire_manual_overrides(db)
    activity = _load_activity(db, target_user_id)
    if activity is None:
        return {
            "status": "verified",
            "data": {
                "user_id": target_user_id,
                "state": UserState.offline.value,
                "last_activity_at": datetime.now(timezone.utc).isoformat(),
                "manual_override": False,
                "manual_override_expires_at": None,
            },
            "verification": {"status": "verified", "effect": "none"},
        }
    # Reuse the existing state calculation; it must normalize SQLite's naive
    # expiry timestamps before comparing.
    await UserActivityService(db).get_user_state(target_user_id)
    db.refresh(activity)
    return {
        "status": "verified",
        "data": _activity_data(activity),
        "verification": {"status": "verified", "effect": "none"},
    }
