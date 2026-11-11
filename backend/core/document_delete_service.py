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
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import text as sa_text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.auth import SECRET_KEY
from core.local_paths import resolve_local_path
from core.models import (
    AuditEventType, AuditLog, IngestedDocument, SecurityLevel,
)
from core.personal_scope import resolve_tenant_id

logger = logging.getLogger(__name__)

DOCUMENT_DELETE_SCHEMA = "atom-document-delete-1"
EFFECTS_VERSION = "document-delete-2"
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
    effects: Optional[Dict[str, Any]] = None,
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
        "effects_version": EFFECTS_VERSION,
        "sql_effect": (effects or {}).get("sql"),
        "sql_pre_rows": (effects or {}).get("sql_pre_rows", 0),
        "sql_post_rows": (effects or {}).get("sql_post_rows", 0),
        "fts_effect": (effects or {}).get("fts"),
        "file_effect": (effects or {}).get("file"),
        "file_shared": (effects or {}).get("file_shared", False),
        "complete": bool((effects or {}).get("complete")),
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
# SQL mirror / FTS / materialized-file effects
# ---------------------------------------------------------------------------

def _fts_probe(session: Session, doc_id: str) -> Dict[str, Any]:
    try:
        if session.bind is None or session.bind.dialect.name != "sqlite":
            return {"fts_present": None, "fts_rowid": None, "fts_pre": 0}
        table = session.execute(
            sa_text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name='ingested_documents_fts'"
            )
        ).first()
        if table is None:
            return {"fts_present": False, "fts_rowid": None, "fts_pre": 0}
        rowid = session.execute(
            sa_text("SELECT rowid FROM ingested_documents WHERE id = :id"),
            {"id": doc_id},
        ).first()
        if rowid is None:
            return {"fts_present": True, "fts_rowid": None, "fts_pre": 0}
        count = session.execute(
            sa_text(
                "SELECT COUNT(*) FROM ingested_documents_fts WHERE rowid = :r"
            ),
            {"r": rowid[0]},
        ).first()
        return {
            "fts_present": True,
            "fts_rowid": int(rowid[0]),
            "fts_pre": int(count[0] if count else 0),
        }
    except Exception as exc:  # noqa: BLE001 - unreadable is not absence
        logger.warning(
            "document FTS preflight failed: doc=%s error_class=%s",
            doc_id, type(exc).__name__)
        return {"fts_present": None, "fts_rowid": None, "fts_pre": 0}


def _sql_target(
    db: Session, *, doc_id: str, workspace_id: Optional[str],
    tenant_id: str,
) -> Dict[str, Any]:
    """Capture the exact scoped SQL mirror row before any effect."""
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(IngestedDocument).filter(
                IngestedDocument.id == str(doc_id)).first()
            if row is None:
                return {"state": "absent"}
            if workspace_id and str(row.workspace_id) != str(workspace_id):
                return {"state": "foreign"}
            if (tenant_id and row.tenant_id is not None
                    and str(row.tenant_id) != str(tenant_id)):
                return {"state": "foreign"}
            file_path = str(row.file_path or "")
            freshness = str(getattr(row, "freshness_status", "") or "").lower()
            shared = False
            if file_path:
                shared = fresh.query(IngestedDocument).filter(
                    IngestedDocument.file_path == file_path,
                    IngestedDocument.id != str(doc_id),
                ).first() is not None
            target = {
                "state": "present",
                "doc_id": str(doc_id),
                "workspace_id": str(row.workspace_id),
                "file_path": file_path,
                "version": (
                    str(row.source_content_hash)
                    if row.source_content_hash is not None else None),
                "shared": bool(shared),
                "freshness": freshness,
            }
            if freshness in ("removed", "superseded"):
                target["state"] = "removed"
            target.update(_fts_probe(fresh, str(doc_id)))
            return target
    except Exception as exc:  # noqa: BLE001 - unreadable is not free
        logger.warning(
            "document SQL mirror preflight failed: doc=%s error_class=%s",
            doc_id, type(exc).__name__)
        return {"state": "unavailable"}


def _delete_sql_target(db: Session, target: Dict[str, Any]) -> str:
    """Conditional exact-version revocation; keep a terminal SQL tombstone.

    Deleting the row would let a queued/stale producer recreate it as fresh.
    ``freshness_status='removed'`` is the existing durable revocation marker;
    lexical/action/VFS consumers filter it, and writers must refuse the same
    source version.
    """
    try:
        with _fresh_session(db) as fresh:
            query = fresh.query(IngestedDocument).filter(
                IngestedDocument.id == target["doc_id"],
                IngestedDocument.workspace_id == target["workspace_id"],
            )
            if target.get("version") is not None:
                query = query.filter(
                    IngestedDocument.source_content_hash == target["version"])
            row = query.first()
            if row is None:
                existing = fresh.query(IngestedDocument).filter(
                    IngestedDocument.id == target["doc_id"],
                    IngestedDocument.workspace_id == target["workspace_id"],
                ).first()
                return "version_conflict" if existing is not None else "absent"
            if str(getattr(row, "freshness_status", "") or "").lower() in (
                    "removed", "superseded"):
                return "already_removed"
            row.freshness_status = "removed"
            fresh.commit()
            return "revoked"
    except Exception as exc:  # noqa: BLE001 - effect is now unknown
        logger.warning(
            "document SQL mirror revocation failed: doc=%s error_class=%s",
            target.get("doc_id"), type(exc).__name__)
        return "delete_failed"


def _sql_count(
    db: Session, *, doc_id: str, workspace_id: Optional[str],
) -> Optional[int]:
    """Count ACTIVE (non-terminal) SQL content for this document id."""
    try:
        from core.doc_freshness_service import NON_FRESH_STATUSES

        with _fresh_session(db) as fresh:
            query = fresh.query(IngestedDocument).filter(
                IngestedDocument.id == str(doc_id))
            if workspace_id:
                query = query.filter(
                    IngestedDocument.workspace_id == str(workspace_id))
            query = query.filter(
                ~IngestedDocument.freshness_status.in_(
                    tuple(NON_FRESH_STATUSES)))
            return int(query.count())
    except Exception:  # noqa: BLE001 - unreadable is not absence
        return None


def _fts_after(db: Session, target: Dict[str, Any]) -> str:
    if target.get("state") == "removed":
        return "revoked"
    if target.get("fts_present") is None:
        return "not_sqlite"
    if target.get("fts_present") is False:
        return "absent"
    rowid = target.get("fts_rowid")
    if rowid is None:
        return "deleted"
    try:
        with _fresh_session(db) as fresh:
            row = fresh.query(IngestedDocument).filter(
                IngestedDocument.id == target["doc_id"]).first()
            if row is not None and str(
                    getattr(row, "freshness_status", "") or "").lower() in (
                    "removed", "superseded"):
                return "revoked"
            count = fresh.execute(
                sa_text(
                    "SELECT COUNT(*) FROM ingested_documents_fts "
                    "WHERE rowid = :r"
                ),
                {"r": rowid},
            ).first()
            return "deleted" if int(count[0] if count else 0) == 0 else "remaining"
    except Exception:  # noqa: BLE001 - unreadable is not absence
        return "unavailable"


def _file_plan(target: Dict[str, Any], doc_id: str) -> Dict[str, Any]:
    file_path = str(target.get("file_path") or "")
    if not file_path:
        return {"effect": "absent"}
    if target.get("shared"):
        return {"effect": "shared"}
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = resolve_local_path(path)
        upload_root = resolve_local_path(
            os.getenv("ATOM_OFFICE_DIR") or "data/office") / "uploads"
        root_real = os.path.realpath(upload_root)
        path_real = os.path.realpath(path)
        if os.path.commonpath([path_real, root_real]) != root_real:
            return {"effect": "unsafe"}
        if path.is_symlink() or not path.name.startswith(f"{doc_id}."):
            return {"effect": "unsafe"}
        if not path.exists():
            return {"effect": "absent"}
        return {"effect": "pending", "path": str(path)}
    except Exception:  # noqa: BLE001 - never unlink an unproven path
        return {"effect": "unsafe"}


def _unlink_file(plan: Dict[str, Any]) -> str:
    if plan.get("effect") != "pending":
        return str(plan.get("effect") or "unsafe")
    try:
        Path(plan["path"]).unlink()
        return "deleted"
    except FileNotFoundError:
        return "absent"
    except Exception as exc:  # noqa: BLE001 - effect is now unknown
        logger.warning(
            "document materialized-file unlink failed: error_class=%s",
            type(exc).__name__)
        return "delete_failed"


def _file_present(plan: Dict[str, Any]) -> Optional[bool]:
    path = plan.get("path")
    if not path:
        return None
    try:
        return Path(path).exists()
    except Exception:  # noqa: BLE001
        return None


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
    effects: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "doc_id": doc_id,
        "workspace_id": workspace_id,
        "deleted": counts["post_base"] == 0 and counts["post_chunks"] == 0,
        "complete": bool((effects or {}).get("complete")),
        "already_applied": already_applied,
        "no_change": no_change,
        "counts": counts,
        "effects": effects or {},
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
            sql_current = _sql_count(
                db, doc_id=expected["doc_id"],
                workspace_id=expected["workspace_id"])
            effects = {
                "version": metadata.get("effects_version"),
                "sql": metadata.get("sql_effect"),
                "sql_pre_rows": int(metadata.get("sql_pre_rows") or 0),
                "sql_post_rows": int(metadata.get("sql_post_rows") or 0),
                "fts": metadata.get("fts_effect"),
                "file": metadata.get("file_effect"),
                "file_shared": bool(metadata.get("file_shared")),
                "complete": bool(metadata.get("complete")),
            }
            if current is not None and current == (0, 0):
                if audit_state["status"] != "verified":
                    return _committed_unverified(
                        operation_id, audit_state,
                        target_id=expected["doc_id"], effect="committed",
                        data=_data(
                            doc_id=expected["doc_id"],
                            workspace_id=expected["workspace_id"] or None,
                            counts=counts, already_applied=True,
                            effects=effects))
                if (
                    metadata.get("effects_version") != EFFECTS_VERSION
                    or not effects["complete"]
                    or sql_current != 0
                ):
                    return _committed_unverified(
                        operation_id, audit_state,
                        target_id=expected["doc_id"], effect="partial",
                        data=_data(
                            doc_id=expected["doc_id"],
                            workspace_id=expected["workspace_id"] or None,
                            counts=counts, effects=effects),
                        verification_status="committed_unverified",
                        message=(
                            "The original receipt did not prove every "
                            "supported effect (SQL/FTS/file); reconcile "
                            "without repeating the deletion."))
                return {
                    "status": "already_applied",
                    "data": _with_receipt(
                        _data(
                            doc_id=expected["doc_id"],
                            workspace_id=expected["workspace_id"] or None,
                            counts=counts, already_applied=True,
                            effects=effects),
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
                    counts=counts, effects=effects),
                verification_status=(
                    "committed_unverified" if effect == "partial"
                    else "unavailable"))
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

    sql_target = _sql_target(
        db, doc_id=doc_id, workspace_id=workspace_id,
        tenant_id=expected["tenant_id"])
    if sql_target.get("state") == "foreign":
        return _refused(
            "Document not found", http_status=404, error_code="NOT_FOUND")
    if sql_target.get("state") == "unavailable":
        return _refused(
            "The document authorization mirror could not be read; no effect "
            "was committed", http_status=503,
            error_code="DOCUMENT_READBACK_UNAVAILABLE")
    file_plan = (
        _file_plan(sql_target, doc_id)
        if sql_target.get("state") == "present" else {"effect": "absent"})

    try:
        pre = await _readback(handler, doc_id)
    except _ReadbackUnavailable:
        return _refused(
            "The document store could not be read; no effect was committed",
            http_status=503, error_code="DOCUMENT_READBACK_UNAVAILABLE")

    if pre == (0, 0) and sql_target.get("state") in ("absent", "removed"):
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

    # Durable SQL revocation first: the exact scoped/version row is removed
    # and the FTS trigger follows it. Vector/file cleanup is separate and
    # explicitly non-atomic.
    sql_effect = "absent"
    sql_pre_rows = 0
    sql_post_rows = 0
    if sql_target.get("state") == "present":
        sql_pre_rows = 1
        sql_effect = _delete_sql_target(db, sql_target)
        if sql_effect == "version_conflict":
            return _conflict(
                "Document source version changed; refresh and retry")
        sql_post_rows = _sql_count(
            db, doc_id=doc_id, workspace_id=workspace_id)
        if sql_post_rows is None:
            sql_post_rows = -1
    elif sql_target.get("state") == "removed":
        sql_pre_rows = 1
        sql_effect = "already_removed"
        sql_post_rows = 0

    base_ok: Optional[bool] = None
    family_ok: Optional[bool] = None

    if pre == (0, 0):
        base_ok = True
        family_ok = True
    elif pre[0] == 0:
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

    file_effect = _unlink_file(file_plan)

    try:
        post = await _readback(handler, doc_id)
    except _ReadbackUnavailable:
        post = None

    sql_post_rows = _sql_count(
        db, doc_id=doc_id, workspace_id=workspace_id)
    if sql_post_rows is None:
        sql_post_rows = -1
    fts_effect = (
        _fts_after(db, sql_target)
        if sql_target.get("state") in ("present", "removed") else "absent")

    vector_ok = post is not None and post == (0, 0)
    sql_ok = (
        sql_effect in ("absent", "deleted", "revoked", "already_removed")
        and sql_post_rows == 0)
    fts_ok = (
        sql_effect == "absent"
        or fts_effect in ("deleted", "not_sqlite", "absent", "revoked"))
    file_ok = file_effect in ("deleted", "absent", "shared")
    complete = bool(vector_ok and sql_ok and fts_ok and file_ok)

    if complete:
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

    effects = {
        "version": EFFECTS_VERSION,
        "sql": sql_effect,
        "sql_pre_rows": sql_pre_rows,
        "sql_post_rows": sql_post_rows,
        "fts": fts_effect,
        "file": file_effect,
        "file_shared": bool(sql_target.get("shared")),
        "complete": complete,
    }

    counts = _counts(
        pre, post if post is not None else (-1, -1))

    if counts["post_base"] < 0 or counts["post_chunks"] < 0:
        # Unknown counts are not "zero rows"; record them as -1 in the
        # receipt but keep the known pre state.
        counts["post_base"] = -1
        counts["post_chunks"] = -1

    receipt = _audit_row(
        expected=expected, outcome=outcome, counts=counts,
        delete_flags={"base": base_ok, "family": family_ok},
        effects=effects)
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
        doc_id=doc_id, workspace_id=workspace_id, counts=counts,
        effects=effects)
    if outcome == "verified" and verified_receipt["status"] == "verified":
        return {
            "status": "verified",
            "data": _with_receipt(
                data, operation_id=operation_id,
                audit_id=operation_id),
            "message": (
                f"Document '{doc_id}' deletion verified: vector rows, SQL "
                "mirror/FTS and materialized-file effects are absent or "
                "authorized elsewhere."),
            "operation_id": operation_id,
            "audit_id": operation_id,
            "target_id": doc_id,
        }
    if outcome == "effect_unknown":
        return _committed_unverified(
            operation_id, verified_receipt, target_id=doc_id,
            effect="unknown", data=data,
            verification_status="unavailable",
            message=(
                "The document deletion did not verify and its effect is "
                "unknown. Reconcile the original operation; do not repeat "
                "it."))
    return _committed_unverified(
        operation_id, verified_receipt, target_id=doc_id,
        effect="partial", data=data,
        verification_status="committed_unverified",
        message=(
            "The document deletion is incomplete across the vector, SQL/FTS "
            "or file effects. Reconcile the original operation; do not repeat "
            "it blindly."))
