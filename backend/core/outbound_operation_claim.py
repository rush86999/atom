"""Durable claim/receipt helpers for approved outbound effects.

This reuses the existing ``task_operation_records`` arbiter (the same table
TaskLifecycle uses for assignment operations) instead of introducing a second
send-state mechanism. The database uniqueness constraint is what makes two
racing retries collapse to one effect.

Statuses are deliberately distinct:

``claimed``
    The row exists; no dispatch decision has been made yet.
``dispatching``
    The caller may have reached the external transport. A retry must NOT
    resend; it is an in-progress/uncertain case until reconciled.
``succeeded``
    The transport confirmed success and the receipt was persisted.
``failed_before_effect``
    A dispatch attempt is known to have failed before any external effect.
``uncertain_effect``
    Dispatch may have applied an effect but success/receipt persistence did
    not complete. Human reconciliation is required; never auto-resend.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CLAIMED = "claimed"
DISPATCHING = "dispatching"
SUCCEEDED = "succeeded"
FAILED_BEFORE_EFFECT = "failed_before_effect"
UNCERTAIN_EFFECT = "uncertain_effect"

_TERMINAL_NO_RESEND = {DISPATCHING, SUCCEEDED, FAILED_BEFORE_EFFECT, UNCERTAIN_EFFECT}


def payload_sha256(
    *,
    workspace_id: str,
    approval_id: str,
    action_type: str,
    platform: str,
    params: Dict[str, Any],
) -> str:
    """Canonical hash of the COMPLETE approved operation payload."""
    body = {
        "workspace_id": str(workspace_id or ""),
        "approval_id": str(approval_id or ""),
        "action_type": str(action_type or ""),
        "platform": str(platform or ""),
        "params": params or {},
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _factory():
    from core.database import get_db_session

    return get_db_session


def _row_dict(row) -> Dict[str, Any]:
    return {
        "record_id": row.id,
        "workspace_id": row.workspace_id,
        "run_id": row.run_id,
        "idempotency_key": row.idempotency_key,
        "payload_sha256": row.payload_sha256,
        "operation_id": row.operation_id,
        "operation_type": row.operation_type,
        "status": row.status,
    }


def claim_or_replay(
    *,
    workspace_id: str,
    tenant_id: Optional[str],
    approval_id: str,
    payload_hash: str,
    operation_type: str = "outbound_send",
) -> Dict[str, Any]:
    """Atomically claim the approved operation, or return its current state.

    The claim is inserted and committed BEFORE any transport call. The
    unique constraint ``(workspace_id, run_id, idempotency_key)`` is the
    arbiter; a second caller can only observe the winner's row.
    """
    from sqlalchemy.exc import IntegrityError, OperationalError

    from core.models import TaskOperationRecord

    run_id = str(approval_id)
    key = str(approval_id)
    record_id = str(uuid.uuid4())
    try:
        with _factory()() as db:
            try:
                db.add(TaskOperationRecord(
                    id=record_id,
                    workspace_id=str(workspace_id or "default"),
                    tenant_id=tenant_id,
                    run_id=run_id,
                    idempotency_key=key,
                    payload_sha256=payload_hash,
                    operation_id=record_id,
                    operation_type=operation_type,
                    status=CLAIMED,
                ))
                db.commit()
                return {"won": True, "status": CLAIMED,
                        "record_id": record_id, "payload_sha256": payload_hash}
            except IntegrityError:
                db.rollback()
            except OperationalError as exc:
                # SQLite may report a locked database while the winner is
                # committing. Treat it as "not won"; the caller retries the
                # read, never the transport.
                db.rollback()
                logger.debug("outbound claim contention: %s", exc)
            row = (
                db.query(TaskOperationRecord)
                .filter(
                    TaskOperationRecord.workspace_id == str(workspace_id or "default"),
                    TaskOperationRecord.run_id == run_id,
                    TaskOperationRecord.idempotency_key == key,
                )
                .first()
            )
            if row is None:
                return {"won": False, "status": "unavailable",
                        "error": "claim not visible after contention"}
            if row.payload_sha256 != payload_hash:
                return {
                    "won": False,
                    "status": "conflict",
                    "record_id": row.id,
                    "error": "idempotency key is bound to a different payload",
                }
            return {"won": False, **_row_dict(row)}
    except Exception as exc:  # noqa: BLE001 — fail closed, no transport
        logger.error("outbound claim failed: %s", exc)
        return {"won": False, "status": "unavailable", "error": str(exc)[:500]}


def mark_status(record_id: str, status: str) -> bool:
    """Persist a claim status transition. Never raises."""
    from core.models import TaskOperationRecord

    try:
        with _factory()() as db:
            row = db.query(TaskOperationRecord).filter(
                TaskOperationRecord.id == record_id).first()
            if row is None:
                return False
            row.status = status
            db.commit()
            return True
    except Exception as exc:  # noqa: BLE001
        logger.error("outbound claim status update failed (%s): %s", status, exc)
        return False


def current(workspace_id: str, approval_id: str) -> Optional[Dict[str, Any]]:
    from core.models import TaskOperationRecord

    try:
        with _factory()() as db:
            row = (
                db.query(TaskOperationRecord)
                .filter(
                    TaskOperationRecord.workspace_id == str(workspace_id or "default"),
                    TaskOperationRecord.run_id == str(approval_id),
                    TaskOperationRecord.idempotency_key == str(approval_id),
                )
                .first()
            )
            return _row_dict(row) if row is not None else None
    except Exception:
        return None
