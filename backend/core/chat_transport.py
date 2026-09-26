"""Keyed transport idempotency for chat turns (work order Step 3).

Stripe-style contract: the client mints one request_id per submitted turn
and reuses it ONLY for network retries of that same turn.

- reserve: first sight inserts an in_progress record transactionally. The
  UNIQUE constraint arbitrates concurrent duplicates to one executor.
- replay: same identity + same payload after completion returns the stored
  finalized response without execution, retrieval, rendering, or duplicate
  history rows.
- conflict: same identity + different payload is rejected (409).
- in_progress: same identity while running returns an explicit
  in-progress result; a second execution never launches.
- crash: a dead turn retains in-progress state rather than risk repeating
  a possibly completed side effect; the client mints a fresh ID next.

Requests without an ID keep the legacy no-dedup behavior.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

IN_PROGRESS = "in_progress"
COMPLETED = "completed"


def payload_hash(*, message: str, session_id: Optional[str],
                 user_id: str, context: Optional[Dict[str, Any]],
                 agent_id: Optional[str] = None,
                 images: Optional[list] = None) -> str:
    """Hash of the accepted request payload (entire request incl. context)."""
    canonical = json.dumps({
        "message": message or "",
        "session_id": session_id,
        "user_id": user_id or "",
        "context": context or {},
        "agent_id": agent_id,
        "images": images or [],
    }, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def check(db, *, tenant_id: str, user_id: str, session_id: Optional[str],
          request_id: str, digest: str, payload_text: str
          ) -> Tuple[str, Any]:
    """Reserve or resolve a keyed request. Returns (action, record) with
    action in {"execute", "replay", "conflict", "in_progress"}."""
    from sqlalchemy.exc import IntegrityError

    from core.models import ChatRequestRecord

    existing = (
        db.query(ChatRequestRecord)
        .filter(
            ChatRequestRecord.tenant_id == tenant_id,
            ChatRequestRecord.user_id == user_id,
            ChatRequestRecord.session_id == (session_id or ""),
            ChatRequestRecord.request_id == request_id,
        )
        .first()
    )
    if existing is not None:
        if existing.state == COMPLETED:
            if (existing.payload_sha256 or "") == digest:
                return "replay", existing
            return "conflict", existing
        return "in_progress", existing
    record = ChatRequestRecord(
        tenant_id=tenant_id, user_id=user_id,
        session_id=session_id or "", request_id=request_id,
        payload_sha256=digest, request_payload=payload_text[:20000],
        state=IN_PROGRESS,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        # Lost the race: a concurrent reserve won. Re-read and resolve.
        try:
            db.rollback()
        except Exception:
            pass
        winner = (
            db.query(ChatRequestRecord)
            .filter(
                ChatRequestRecord.tenant_id == tenant_id,
                ChatRequestRecord.user_id == user_id,
                ChatRequestRecord.session_id == (session_id or ""),
                ChatRequestRecord.request_id == request_id,
            )
            .first()
        )
        if winner is None:
            return "execute", record
        if winner.state == COMPLETED:
            if (winner.payload_sha256 or "") == digest:
                return "replay", winner
            return "conflict", winner
        return "in_progress", winner
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(f"transport reserve skipped: {exc}")
        return "execute", record
    return "execute", record


def complete(db, record: Any, *, execution_id: Optional[str] = None,
             assistant_message_id: Optional[str] = None,
             finalized: Optional[Dict[str, Any]] = None) -> None:
    """Persist completion together with the finalized response.

    APPEND-ONLY with respect to the pinned response: a record that is
    already COMPLETED keeps the response it was pinned with. The pin is
    the client's retry contract — same request id must return the same
    bytes — so a later re-finalization of the same message row (which the
    task's delivery ledger records as a NEW delivery event) must never
    overwrite what this request id already promised. History lives in the
    ledger; the pin stays stable.

    Best-effort after delivery; failures are logged, never raised into the
    response.
    """
    try:
        if getattr(record, "state", None) == COMPLETED:
            logger.info(
                "transport completion already pinned for request %s; "
                "leaving the original response in place",
                getattr(record, "request_id", None))
            return
        record.state = COMPLETED
        if execution_id:
            record.execution_id = str(execution_id)
        if assistant_message_id:
            record.assistant_message_id = str(assistant_message_id)
        if finalized is not None:
            record.finalized_response = json.dumps(finalized)[:60000]
        db.commit()
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(f"transport completion skipped: {exc}")


def stored_response(record: Any) -> Optional[Dict[str, Any]]:
    """The stored finalized payload, or None when absent/unparseable."""
    try:
        payload = json.loads(getattr(record, "finalized_response", None) or "{}")
    except Exception:
        return None
    return payload if isinstance(payload, dict) and payload else None
