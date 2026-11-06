"""Verified knowledge-document deletion.

``DELETE /api/documents/{doc_id}`` used to delete the exact base row and then
attempt the ``<doc_id>::`` chunk-family cleanup as "best effort": a raising or
``False`` prefix delete was logged and ignored, the caller got a clean success,
and orphaned chunks stayed retrievable in LanceDB. There was no operation
identity, receipt, count or readback.

This service keeps the existing ``LanceDBHandler`` deletion methods and adds
the repo's established durable-operation pattern: one ``AuditLog`` receipt
keyed by ``operation_id``, an exact request/target digest, a fresh readback,
same-operation replay and a truthful partial/unknown outcome.

LanceDB and SQL are separate stores. Nothing here claims one atomic
transaction: the receipt records the observed LanceDB effect *after* it
happened. A failed receipt after a known effect is reported as
``effect_unknown`` with ``replay=do_not_repeat``; a partial chunk cleanup is
reported as ``committed_unverified`` with the known base-row effect preserved.
Reconciliation re-reads the store and never blindly repeats the deletion.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.auth import SECRET_KEY
from core.models import AuditEventType, AuditLog, SecurityLevel
from core.personal_scope import resolve_tenant_id

logger = logging.getLogger(__name__)

DOCUMENT_DELETE_SCHEMA = "atom-document-delete-1"
_OPERATION_PREFIX = "document"
_SAFE_OPERATION_RE = re.compile(r"^[A-Za-z0-9:_-]{1,180}$")
_ACTION = "document_deleted"
_RESOURCE_PREFIX = "document:"
_TABLE = "documents"


class _ReadbackUnavailable(Exception):
    """The store could not be read, so absence is not established."""


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


def _operation_id(supplied: Optional[str]) -> str:
    supplied = str(supplied or "").strip()
    candidate = supplied or f"{_OPERATION_PREFIX}:delete:{uuid.uuid4().hex}"
    prefix = f"{_OPERATION_PREFIX}:delete:"
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


def _conflict(message: str) -> Dict[str, Any]:
    return {
        "status": "conflict",
        "error": message,
        "error_code": "OPERATION_CONFLICT",
        "http_status": 409,
        "verification": {"status": "refuted", "effect": "none"},
    }


def _committed_unverified(
    operation_id: str, audit_state: Dict[str, Any], *, target_id: str,
    effect: str, data: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
    verification_status: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "status": "committed_unverified",
        "data": data,
        "message": message or (
            "The document deletion committed but its complete effect could "
            "not be verified. Reconcile the original operation; do not "
            "repeat it."),
        "operation_id": operation_id,
        "audit_id": audit_state.get("audit_id"),
        "target_id": target_id,
        "verification": {
            "status": (
                verification_status
                or audit_state.get("status", "unavailable")),
            "audit_status": audit_state.get("status", "unavailable"),
            "effect": effect,
            "replay": "do_not_repeat",
            "audit_id": audit_state.get("audit_id"),
        },
    }


def _effect_unknown(
    operation_id: str, target_id: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "status": "effect_unknown",
        "data": data,
        "message": (
            "The document deletion may have committed, but confirmation was "
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


def _no_change(
    operation_id: Optional[str], *, target_id: str, data: Dict[str, Any],
    message: str,
) -> Dict[str, Any]:
    return {
        "status": "no_change",
        "data": data,
        "message": message,
        "operation_id": operation_id,
        "audit_id": None,
        "target_id": target_id,
        "verification": {"status": "no_change", "effect": "none"},
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
# Sessions / receipt identity
# ---------------------------------------------------------------------------

def _fresh_session(db: Session) -> Session:
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=db.get_bind())()


def _expected(
    *, operation_id: str, actor: Any, workspace_id: Optional[str],
    doc_id: str,
) -> Dict[str, Any]:
    ws = str(workspace_id) if workspace_id else ""
    actor_id = str(getattr(actor, "id", "") or "")
    tenant_id = str(
        getattr(actor, "tenant_id", None)
        or resolve_tenant_id(actor)
        or "")
    return {
        "operation_id": operation_id,
        "schema": DOCUMENT_DELETE_SCHEMA,
        "action": _ACTION,
        "event_type": AuditEventType.DELETE.value,
        "actor_id": actor_id,
        "actor_email": str(getattr(actor, "email", "") or ""),
        "actor_role": str(getattr(actor, "role", "") or ""),
        "tenant_id": tenant_id,
        "workspace_id": ws,
        "doc_id": str(doc_id),
        "target_digest": _fingerprint(
            "document-target", ws, str(doc_id)),
        "request_digest": _fingerprint(
            "document-delete-request", ws, str(doc_id)),
        "resource": f"{_RESOURCE_PREFIX}{doc_id}",
    }


def _audit_row(
    *, expected: Dict[str, Any], outcome: str,
    counts: Dict[str, int], delete_flags: Dict[str, Optional[bool]],
) -> AuditLog:
    metadata = {
        "schema": expected["schema"],
        "operation_id": expected["operation_id"],
        "action": expected["action"],
        "event_type": expected["event_type"],
        "actor_id": expected["actor_id"],
        "actor_email": expected["actor_email"],
        "actor_role": expected["actor_role"],
        "tenant_id": expected["tenant_id"],
        "workspace_id": expected["workspace_id"],
        "doc_id": expected["doc_id"],
        "target_digest": expected["target_digest"],
        "request_digest": expected["request_digest"],
        "outcome": outcome,
        "pre_base_rows": int(counts["pre_base"]),
        "pre_chunk_rows": int(counts["pre_chunks"]),
        "post_base_rows": int(counts["post_base"]),
        "post_chunk_rows": int(counts["post_chunks"]),
        "base_delete_ok": delete_flags.get("base"),
        "family_delete_ok": delete_flags.get("family"),
    }
    success = outcome == "verified"
    return AuditLog(
        id=expected["operation_id"],
        event_type=expected["event_type"],
        security_level=SecurityLevel.HIGH.value,
        threat_level="none",
        user_id=expected["actor_id"] or None,
        user_email=expected["actor_email"] or None,
        tenant_id=expected["tenant_id"] or None,
        workspace_id=expected["workspace_id"] or None,
        resource=expected["resource"],
        action=expected["action"],
        description=f"Document deletion ({outcome})",
        metadata_json=json.dumps(metadata, sort_keys=True),
        success=success,
        error_message=None if success else f"outcome={outcome}",
    )


def _verify_audit(
    db: Session, expected: Dict[str, Any], outcome: str,
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
            if str(row.user_id or "") != expected["actor_id"]:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.tenant_id or "") != expected["tenant_id"]:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.workspace_id or "") != expected["workspace_id"]:
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.resource or "") != expected["resource"]:
                return {"status": "refuted", "audit_id": audit_id}
            if bool(row.success) != (outcome == "verified"):
                return {"status": "refuted", "audit_id": audit_id}
            if str(row.security_level or "") != SecurityLevel.HIGH.value:
                return {"status": "refuted", "audit_id": audit_id}
            try:
                metadata = json.loads(row.metadata_json or "{}")
            except (TypeError, ValueError):
                return {"status": "unavailable", "audit_id": audit_id}
            if not isinstance(metadata, dict):
                return {"status": "unavailable", "audit_id": audit_id}
            for key in (
                "schema", "operation_id", "action", "event_type",
                "actor_id", "tenant_id", "workspace_id", "doc_id",
                "target_digest", "request_digest",
            ):
                if key not in metadata:
                    return {"status": "unavailable", "audit_id": audit_id}
                if not isinstance(metadata[key], str):
                    return {"status": "refuted", "audit_id": audit_id}
                if metadata[key] != expected[key]:
                    return {"status": "refuted", "audit_id": audit_id}
            if metadata.get("outcome") != outcome:
                return {"status": "refuted", "audit_id": audit_id}
            for key in (
                "pre_base_rows", "pre_chunk_rows",
                "post_base_rows", "post_chunk_rows",
            ):
                if not isinstance(metadata.get(key), int):
                    return {"status": "refuted", "audit_id": audit_id}
            return {"status": "verified", "audit_id": audit_id}
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "document delete receipt read-back failed: operation_id=%s "
            "error_class=%s", audit_id, type(exc).__name__)
        return {"status": "unavailable", "audit_id": audit_id}


# ---------------------------------------------------------------------------
# Store readback / effect
# ---------------------------------------------------------------------------

async def _readback(handler: Any, doc_id: str) -> tuple[int, int]:
    """Return ``(exact base rows, chunk-family rows)`` or raise.

    Uses the handler's exact counters when available. The fallback keeps this
    service compatible with the small handlers used in route tests: presence
    is one row, and the family probe already returns the ids.
    """
    count_id = getattr(handler, "count_document_rows_by_id", None)
    count_prefix = getattr(handler, "count_document_rows_by_prefix", None)
    try:
        if count_id is not None and count_prefix is not None:
            base = await asyncio.to_thread(
                count_id, _TABLE, str(doc_id))
            chunks = await asyncio.to_thread(
                count_prefix, _TABLE, f"{doc_id}::")
            if base is None or chunks is None or base < 0 or chunks < 0:
                raise _ReadbackUnavailable("count unavailable")
            return int(base), int(chunks)
        base_row = await asyncio.to_thread(
            handler.get_document_by_id, _TABLE, str(doc_id))
        family_ids = await asyncio.to_thread(
            handler.get_document_ids_by_prefix, _TABLE, f"{doc_id}::")
        return (1 if base_row else 0), len(family_ids or [])
    except _ReadbackUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 — unreadable is not absence
        raise _ReadbackUnavailable(type(exc).__name__) from exc


async def _delete_exact(handler: Any, doc_id: str) -> bool:
    try:
        return bool(await asyncio.to_thread(
            handler.delete_documents_by_id, _TABLE, str(doc_id)))
    except Exception as exc:  # noqa: BLE001 — effect is now unknown
        logger.warning(
            "document base-row delete failed: doc=%s error_class=%s",
            doc_id, type(exc).__name__)
        return False


async def _delete_family(handler: Any, doc_id: str) -> bool:
    try:
        return bool(await asyncio.to_thread(
            handler.delete_documents_by_prefix, _TABLE, f"{doc_id}::"))
    except Exception as exc:  # noqa: BLE001 — effect is now unknown
        logger.warning(
            "document chunk-family delete failed: doc=%s error_class=%s",
            doc_id, type(exc).__name__)
        return False


def _counts(
    pre: tuple[int, int], post: tuple[int, int],
) -> Dict[str, int]:
    return {
        "pre_base": pre[0], "pre_chunks": pre[1],
        "post_base": post[0], "post_chunks": post[1],
    }


def _data(
    *, doc_id: str, workspace_id: Optional[str], counts: Dict[str, int],
    already_applied: bool = False, no_change: bool = False,
) -> Dict[str, Any]:
    return {
        "doc_id": doc_id,
        "workspace_id": workspace_id,
        "deleted": counts["post_base"] == 0 and counts["post_chunks"] == 0,
        "already_applied": already_applied,
        "no_change": no_change,
        "counts": counts,
    }


def _prior_receipt_exists(
    db: Session, *, workspace_id: Optional[str], doc_id: str,
) -> bool:
    try:
        with _fresh_session(db) as fresh:
            query = fresh.query(AuditLog).filter(
                AuditLog.action == _ACTION,
                AuditLog.resource == f"{_RESOURCE_PREFIX}{doc_id}",
            )
            if workspace_id:
                query = query.filter(
                    AuditLog.workspace_id == str(workspace_id))
            else:
                query = query.filter(AuditLog.workspace_id.is_(None))
            return query.first() is not None
    except Exception as exc:  # noqa: BLE001 — absence of proof means 404
        logger.warning(
            "document delete receipt lookup failed: doc=%s error_class=%s",
            doc_id, type(exc).__name__)
        return False


async def _replay(
    db: Session, operation_id: str, expected: Dict[str, Any],
    handler: Any,
) -> Optional[Dict[str, Any]]:
    """Reconcile an existing receipt. ``None`` when no receipt exists."""
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
                    operation_id, {"status": "unavailable", "audit_id": None},
                    target_id=expected["doc_id"],
                    effect="unknown")
            for key in (
                "schema", "action", "event_type", "workspace_id",
                "doc_id", "target_digest", "request_digest", "actor_id",
            ):
                if metadata.get(key) != expected[key]:
                    return _conflict(
                        "operation_id is bound to a different document "
                        "deletion request")
            outcome = str(metadata.get("outcome") or "")
            audit_state = _verify_audit(db, expected, outcome)
            counts = {
                "pre_base": int(metadata.get("pre_base_rows") or 0),
                "pre_chunks": int(metadata.get("pre_chunk_rows") or 0),
                "post_base": int(metadata.get("post_base_rows") or 0),
                "post_chunks": int(metadata.get("post_chunk_rows") or 0),
            }
            try:
                current = await _readback(handler, expected["doc_id"])
            except _ReadbackUnavailable:
                current = None
            if current is not None:
                counts["post_base"], counts["post_chunks"] = current
            if current is not None and current == (0, 0):
                if audit_state["status"] != "verified":
                    return _committed_unverified(
                        operation_id, audit_state,
                        target_id=expected["doc_id"], effect="committed",
                        data=_data(
                            doc_id=expected["doc_id"],
                            workspace_id=expected["workspace_id"] or None,
                            counts=counts, already_applied=True))
                return {
                    "status": "already_applied",
                    "data": _with_receipt(
                        _data(
                            doc_id=expected["doc_id"],
                            workspace_id=expected["workspace_id"] or None,
                            counts=counts, already_applied=True),
                        operation_id=operation_id,
                        audit_id=expected["operation_id"],
                        verification_status="already_applied",
                        replay="do_not_repeat"),
                    "message": (
                        "This document deletion was already applied; the "
                        "original receipt was returned without another "
                        "deletion."),
                    "operation_id": operation_id,
                    "audit_id": expected["operation_id"],
                    "target_id": expected["doc_id"],
                }
            effect = "partial" if current and current[0] == 0 else "unknown"
            return _committed_unverified(
                operation_id, audit_state,
                target_id=expected["doc_id"], effect=effect,
                data=_data(
                    doc_id=expected["doc_id"],
                    workspace_id=expected["workspace_id"] or None,
                    counts=counts),
                verification_status=(
                    "committed_unverified" if effect == "partial" else None))
    except Exception as exc:  # noqa: BLE001 — unreadable is not verified
        logger.warning(
            "document delete replay read failed: operation_id=%s "
            "error_class=%s", operation_id, type(exc).__name__)
        return _committed_unverified(
            operation_id, {"status": "unavailable", "audit_id": None},
            target_id=expected["doc_id"], effect="unknown")


# ---------------------------------------------------------------------------
# Public operation
# ---------------------------------------------------------------------------

async def delete_document_verified(
    db: Session, *, actor: Any, workspace_id: Optional[str], doc_id: str,
    handler: Any, operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Delete one exact document id and its ``<id>::`` chunk family.

    The receipt is committed after the LanceDB effect. Outcomes:
    ``verified`` (fresh readback shows both gone), ``already_applied`` (same
    operation replay), ``no_change`` (already absent and a prior receipt
    covers it), ``committed_unverified`` (base effect known, family not),
    ``effect_unknown`` (confirmation lost), ``conflict`` (same operation id,
    different material) and ``refused`` (unknown/foreign/malformed).
    """
    doc_id = str(doc_id or "")
    if not doc_id.strip():
        return _refused("doc_id must be non-empty", field="doc_id")
    try:
        operation_id = _operation_id(operation_id)
    except ValueError as exc:
        return _refused(str(exc), field="operation_id")

    expected = _expected(
        operation_id=operation_id, actor=actor,
        workspace_id=workspace_id, doc_id=doc_id)
    # Replay is checked before any probe or delete: the same logical
    # operation never performs a second deletion.
    replay = await _replay(db, operation_id, expected, handler)
    if replay is not None:
        return replay

    try:
        pre = await _readback(handler, doc_id)
    except _ReadbackUnavailable:
        return _refused(
            "The document store could not be read; no effect was committed",
            http_status=503, error_code="DOCUMENT_READBACK_UNAVAILABLE")

    if pre == (0, 0):
        if _prior_receipt_exists(
                db, workspace_id=workspace_id, doc_id=doc_id):
            return _no_change(
                operation_id, target_id=doc_id,
                data=_data(
                    doc_id=doc_id, workspace_id=workspace_id,
                    counts=_counts(pre, pre), no_change=True),
                message=(
                    f"Document '{doc_id}' is already absent; an earlier "
                    "deletion receipt was found and no new receipt was "
                    "created."))
        return _refused(
            "Document not found", http_status=404, error_code="NOT_FOUND")

    base_ok: Optional[bool] = None
    family_ok: Optional[bool] = None

    if pre[0] == 0:
        # Chunk-only family (parent already gone) — deletable, not a 404.
        base_ok = True
        family_ok = await _delete_family(handler, doc_id)
    else:
        base_ok = await _delete_exact(handler, doc_id)
        if base_ok:
            family_ok = await _delete_family(handler, doc_id)
        else:
            # A raised/false base delete may still have applied. Read back
            # before deciding whether compensation is safe; never blind
            # replay the base delete.
            try:
                mid = await _readback(handler, doc_id)
            except _ReadbackUnavailable:
                mid = None
            if mid is not None and mid[0] == 0:
                family_ok = await _delete_family(handler, doc_id)

    try:
        post = await _readback(handler, doc_id)
    except _ReadbackUnavailable:
        post = None

    if post is not None and post == (0, 0):
        outcome = "verified"
    elif post is not None and post[0] == 0:
        outcome = "committed_unverified"
    elif post is None and base_ok:
        # The base delete reported success but the final readback is
        # unavailable. Keep the known base effect and do not claim either a
        # clean success or a rollback.
        outcome = "committed_unverified"
    else:
        outcome = "effect_unknown"

    if outcome == "verified" and pre == (0, 0):
        # Defensive race path: both probes disagree about presence. Do not
        # invent a receipt for an effect we cannot attribute.
        return _no_change(
            operation_id, target_id=doc_id,
            data=_data(
                doc_id=doc_id, workspace_id=workspace_id,
                counts=_counts(pre, (0, 0)), no_change=True),
            message=f"Document '{doc_id}' is already absent; no change.")

    counts = _counts(
        pre, post if post is not None else (-1, -1))

    if counts["post_base"] < 0 or counts["post_chunks"] < 0:
        # Unknown counts are not "zero rows"; record them as -1 in the
        # receipt but keep the known pre state.
        counts["post_base"] = -1
        counts["post_chunks"] = -1

    receipt = _audit_row(
        expected=expected, outcome=outcome, counts=counts,
        delete_flags={"base": base_ok, "family": family_ok})
    try:
        db.add(receipt)
        db.commit()
    except IntegrityError:
        db.rollback()
        replay = await _replay(db, operation_id, expected, handler)
        if replay is not None:
            return replay
        return _committed_unverified(
            operation_id, {"status": "unavailable", "audit_id": None},
            target_id=doc_id, effect="unknown",
            data=_data(
                doc_id=doc_id, workspace_id=workspace_id, counts=counts))
    except Exception as exc:  # noqa: BLE001 — commit outcome unknown
        db.rollback()
        logger.error(
            "document deletion receipt commit failed: operation_id=%s "
            "doc=%s error_class=%s",
            operation_id, doc_id, type(exc).__name__)
        return _effect_unknown(
            operation_id, doc_id,
            data=_data(
                doc_id=doc_id, workspace_id=workspace_id, counts=counts))

    verified_receipt = _verify_audit(db, expected, outcome)
    data = _data(
        doc_id=doc_id, workspace_id=workspace_id, counts=counts)
    if outcome == "verified" and verified_receipt["status"] == "verified":
        return {
            "status": "verified",
            "data": _with_receipt(
                data, operation_id=operation_id,
                audit_id=operation_id),
            "message": (
                f"Document '{doc_id}' deletion verified: base row and "
                "chunk family are absent."),
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": doc_id,
        }
    if outcome == "effect_unknown":
        return _committed_unverified(
            operation_id, verified_receipt, target_id=doc_id,
            effect="unknown", data=data,
            message=(
                "The document deletion did not verify and its effect is "
                "unknown. Reconcile the original operation; do not repeat "
                "it."))
    return _committed_unverified(
        operation_id, verified_receipt, target_id=doc_id,
        effect="partial", data=data,
        verification_status="committed_unverified",
        message=(
            "The base row was removed but the chunk family still exists. "
            "Reconcile the original operation; do not repeat it blindly."))
