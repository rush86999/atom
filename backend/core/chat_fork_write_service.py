"""Verified chat-session fork decisions.

The fork route previously copied the source conversation into a new
``ChatSession`` and committed with no current-principal binding, exact source
snapshot, audit receipt or replay protection. This module keeps the same
lineage/prefix semantics but binds the actor and source material in one
transaction with the new session, copied messages and audit receipt.
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
    AuditEventType,
    AuditLog,
    ChatMessage,
    ChatSession,
    SecurityLevel,
    User,
)
from core.personal_scope import resolve_tenant_id, resolve_workspace_id

logger = logging.getLogger(__name__)

REVIEW_SCHEMA = "atom-chat-fork-1"
_OPERATION_PREFIX = "chat-fork"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_ACTION_FORK = "chat_session_forked"


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


def _operation_id(supplied: Optional[str]) -> str:
    supplied = str(supplied or "").strip()
    candidate = supplied or f"{_OPERATION_PREFIX}:{uuid.uuid4().hex}"
    prefix = f"{_OPERATION_PREFIX}:"
    if not candidate.startswith(prefix):
        candidate = f"{prefix}{candidate}"
    if not _SAFE_OPERATION_RE.fullmatch(candidate):
        raise ValueError("operation_id is malformed")
    return candidate


def _refused(
    message: str, *, http_status: int = 403,
    error_code: str = "AUTHORITY_REQUIRED",
) -> Dict[str, Any]:
    return {
        "status": "refused",
        "error": message,
        "error_code": error_code,
        "http_status": int(http_status),
        "verification": {"status": "not_attempted", "effect": "none"},
    }


def _no_effect(data: Dict[str, Any], message: str) -> Dict[str, Any]:
    return {
        "status": "no_effect",
        "data": data,
        "message": message,
        "verification": {"status": "no_change", "effect": "none"},
    }


def _conflict(message: str, *, code: str = "STALE_SOURCE") -> Dict[str, Any]:
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
        "error_code": "CHAT_FORK_TRANSACTION_ROLLED_BACK",
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
            "The chat fork committed but its audit/target readback did not "
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
            "The chat fork may have committed, but confirmation was lost. "
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


def _actor_refusal(actor: Dict[str, Any]) -> Dict[str, Any]:
    return _refused(
        str(actor.get("message") or "Authentication required"),
        http_status=int(actor.get("http_status") or 401),
        error_code=str(actor.get("error_code") or "UNAUTHENTICATED"))


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
                "is_active": bool(row.is_active),
                "tenant_id": str(resolve_tenant_id(row)),
                "raw_tenant_id": row.tenant_id,
                "workspace_id": str(resolve_workspace_id(row)),
            }
    except Exception as exc:  # noqa: BLE001 — unreadable authority fails closed
        logger.warning(
            "chat-fork authority read failed: actor=%s error_class=%s",
            actor_id, type(exc).__name__)
        return {
            "ok": False, "http_status": 503,
            "error_code": "AUTHORITY_UNAVAILABLE",
            "message": "Authorization could not be confirmed; retry",
        }


def _exact(column, value: Any):
    return column.is_(None) if value is None else column == value


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


def _message_state(row: ChatMessage) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id or ""),
        "role": str(row.role or ""),
        "content": str(row.content or ""),
        "agent_id": None if row.agent_id is None else str(row.agent_id),
        "metadata_json": row.metadata_json,
    }


def _session_state(row: ChatSession) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id or ""),
        "title": str(row.title or ""),
        "metadata_json": row.metadata_json or {},
        "message_count": int(row.message_count or 0),
    }


def _source_digest(
    source: Optional[ChatSession], rows: list,
) -> str:
    return _fingerprint(
        "chat-fork-source",
        _canonical(_session_state(source)) if source is not None else "",
        _canonical([_message_state(row) for row in rows]))


def _result_digest(
    fork: ChatSession, messages: list,
) -> str:
    ordered = sorted(messages, key=lambda row: str(row.id))
    return _fingerprint(
        "chat-fork-result",
        _canonical(_session_state(fork)),
        _canonical([_message_state(row) for row in ordered]))


def _load_source(db: Session, session_id: str) -> Optional[ChatSession]:
    with _fresh_session(db) as fresh:
        return fresh.query(ChatSession).filter(
            ChatSession.id == str(session_id)).populate_existing().first()


def _load_source_messages(db: Session, session_id: str) -> list:
    with _fresh_session(db) as fresh:
        return (
            fresh.query(ChatMessage)
            .filter(ChatMessage.conversation_id == str(session_id))
            .order_by(
                ChatMessage.created_at.asc(),
                ChatMessage.role.desc(),
            )
            .all()
        )


def _claim_source(
    db: Session, source: Optional[ChatSession],
) -> bool:
    if source is None:
        return True
    result = db.execute(
        update(ChatSession)
        .where(
            ChatSession.id == str(source.id),
            ChatSession.user_id == source.user_id,
            _exact(ChatSession.title, source.title),
            _exact(ChatSession.metadata_json, source.metadata_json),
            ChatSession.message_count == source.message_count,
        )
        .values(updated_at=ChatSession.updated_at)
    )
    return result.rowcount == 1


def _load_fork(
    db: Session, fork_id: str,
) -> tuple[Optional[ChatSession], list]:
    with _fresh_session(db) as fresh:
        fork = fresh.query(ChatSession).filter(
            ChatSession.id == str(fork_id)).populate_existing().first()
        messages = (
            fresh.query(ChatMessage)
            .filter(ChatMessage.conversation_id == str(fork_id))
            .all()
        )
        return fork, messages


def _audit_expected(
    *, operation_id: str, source_session_id: str, target_id: str,
    prior_digest: str, result_digest: str, request_digest: str,
    actor: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "operation_id": str(operation_id),
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_FORK,
        "event_type": AuditEventType.CREATE.value,
        "target_id": str(target_id),
        "source_session_id": str(source_session_id),
        "prior_digest": str(prior_digest),
        "result_digest": str(result_digest),
        "request_digest": str(request_digest),
        "actor_id": actor["id"],
        "actor_role": actor["role"],
        "tenant_id": actor["tenant_id"],
        "resource": f"chat_session:{target_id}",
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
        "source_session_id": expected["source_session_id"],
        "prior_digest": expected["prior_digest"],
        "result_digest": expected["result_digest"],
        "request_digest": expected["request_digest"],
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
        workspace_id=actor["workspace_id"],
        resource=expected["resource"],
        action=expected["action"],
        description="Chat-session fork recorded",
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
                "target_id", "source_session_id", "prior_digest",
                "result_digest", "request_digest", "actor_id",
                "actor_role", "tenant_id",
            )
            for key in string_fields:
                if key not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                if not isinstance(metadata[key], str):
                    return {"status": "refuted", "audit_id": audit_id}
                if metadata[key] != expected[key]:
                    return {"status": "refuted", "audit_id": audit_id}
            return {"status": "verified", "audit_id": audit_id}
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "chat-fork audit read-back failed: operation_id=%s "
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
        "source_session_id": metadata.get("source_session_id"),
        "prior_digest": metadata.get("prior_digest"),
        "result_digest": metadata.get("result_digest"),
        "request_digest": metadata.get("request_digest"),
        "actor_id": metadata.get("actor_id"),
        "actor_role": metadata.get("actor_role"),
        "tenant_id": metadata.get("tenant_id"),
        "resource": f"chat_session:{metadata.get('target_id')}",
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
                or metadata.get("source_session_id")
                != expected["source_session_id"]
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
            fork, messages = _load_fork(db, audit_expected["target_id"])
            target_ok = (
                fork is not None
                and _result_digest(fork, messages)
                == audit_expected["result_digest"]
            )
            data = _legacy_success(
                fork, audit_expected["source_session_id"])
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
                    "message": "This chat fork was already applied.",
                    "operation_id": operation_id,
                    "audit_id": audit_expected["operation_id"],
                    "target_id": audit_expected["target_id"],
                }
            return _committed_unverified(
                operation_id, audit_state,
                target_id=audit_expected["target_id"])
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "chat-fork replay read failed: operation_id=%s error_class=%s",
            operation_id, type(exc).__name__)
        return _committed_unverified(
            operation_id, {"status": "unavailable"},
            target_id=str(expected.get("target_id") or ""))


def _legacy_success(
    fork: Optional[ChatSession], source_session_id: str,
) -> Dict[str, Any]:
    if fork is None:
        return {
            "success": True,
            "session_id": None,
            "forked_from": source_session_id,
            "messages_copied": 0,
            "title": None,
        }
    return {
        "success": True,
        "session_id": str(fork.id),
        "forked_from": source_session_id,
        "messages_copied": int(fork.message_count or 0),
        "title": str(fork.title or ""),
    }


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
        replay = _replay(db, operation_id, expected, authority=authority)
        if replay is not None:
            return replay
        return _not_applied(
            "The chat fork was rolled back; no effect was applied")
    except Exception as exc:  # noqa: BLE001 — commit outcome unknown
        db.rollback()
        logger.error(
            "chat-fork outcome unknown: operation_id=%s target=%s "
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
            "message": "Chat fork committed and verified.",
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": target_id,
        }
    return _committed_unverified(
        operation_id, audit_state, target_id=target_id)


def fork_chat_session(
    db: Session, *, actor: Any, session_id: str,
    up_to_message_id: Optional[str] = None,
    source_title_hint: Optional[str] = None,
    operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    authority = _resolve_actor(db, actor)
    if not authority.get("ok"):
        return _actor_refusal(authority)
    try:
        operation_id = _operation_id(operation_id)
    except ValueError as exc:
        return _refused(str(exc), http_status=422, error_code="VALIDATION_ERROR")

    source = _load_source(db, session_id)
    if source is not None and str(source.user_id or "") != authority["id"]:
        return _refused(
            "Access denied", http_status=403,
            error_code="AUTHORITY_REQUIRED")

    rows = _load_source_messages(db, session_id)
    if not rows:
        return _no_effect(
            {"success": False, "error": "Session not found"},
            "Chat session has no messages to fork")
    if up_to_message_id:
        index = next(
            (i for i, row in enumerate(rows)
             if str(row.id) == str(up_to_message_id)), None)
        if index is None:
            return _no_effect(
                {
                    "success": False,
                    "error": (
                        f"up_to_message_id {up_to_message_id} not found in "
                        "session"),
                },
                "Fork boundary not found")
        rows = rows[: index + 1]

    source_title = (
        (source.title if source is not None else None)
        or source_title_hint or "Chat")
    request_digest = _fingerprint(
        "chat-fork-request", str(session_id), str(up_to_message_id or ""))
    expected_base = {
        "operation_id": operation_id,
        "schema": REVIEW_SCHEMA,
        "action": _ACTION_FORK,
        "event_type": AuditEventType.CREATE.value,
        "source_session_id": str(session_id),
        "request_digest": request_digest,
        "actor_id": authority["id"],
    }
    replay = _replay(db, operation_id, expected_base, authority=authority)
    if replay is not None:
        return replay

    prior_digest = _source_digest(source, rows)
    if not _claim_actor(db, authority):
        db.rollback()
        return _conflict(
            "fork authority changed; refresh and retry",
            code="AUTHORITY_CHANGED")
    if not _claim_source(db, source):
        db.rollback()
        return _conflict(
            "source chat session changed; refresh and retry",
            code="STALE_SOURCE")

    # The session-row claim does not bind message rows. Re-read the snapshot
    # after the claim (the claim holds the SQLite write lock) and refuse if a
    # concurrent message edit changed the conversation the fork would copy.
    post_claim_rows = _load_source_messages(db, session_id)
    if up_to_message_id:
        post_index = next(
            (i for i, row in enumerate(post_claim_rows)
             if str(row.id) == str(up_to_message_id)), None)
        if post_index is None:
            db.rollback()
            return _conflict(
                "source chat session changed; refresh and retry",
                code="STALE_SOURCE")
        post_claim_rows = post_claim_rows[: post_index + 1]
    if _source_digest(source, post_claim_rows) != prior_digest:
        db.rollback()
        return _conflict(
            "source chat session changed; refresh and retry",
            code="STALE_SOURCE")
    rows = post_claim_rows

    fork_id = str(uuid.uuid4())
    forked_at = _now_iso()
    fork = ChatSession(
        id=fork_id,
        user_id=authority["id"],
        title=f"Fork: {source_title}",
        metadata_json={
            "forked_from": str(session_id),
            "forked_at": forked_at,
        },
        message_count=len(rows),
    )
    db.add(fork)

    copied: list = []
    default_tenant = (
        getattr(source, "tenant_id", None) if source is not None else None
    ) or "default"
    for row in rows:
        copied_row = ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=fork_id,
            tenant_id=row.tenant_id or default_tenant,
            role=row.role,
            content=row.content,
            agent_id=row.agent_id,
            metadata_json=row.metadata_json,
        )
        db.add(copied_row)
        copied.append(copied_row)
    db.flush()

    result_digest = _result_digest(fork, copied)
    expected = _audit_expected(
        operation_id=operation_id, source_session_id=str(session_id),
        target_id=fork_id, prior_digest=prior_digest,
        result_digest=result_digest, request_digest=request_digest,
        actor=authority)
    audit_row = _audit_row(expected=expected, actor=authority)
    return _commit_and_verify(
        db, expected=expected, audit_row=audit_row,
        target_check=lambda: (
            (loaded := _load_fork(db, fork_id))[0] is not None
            and _result_digest(loaded[0], loaded[1]) == result_digest),
        success_data=_legacy_success(fork, str(session_id)),
        authority=authority)


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
