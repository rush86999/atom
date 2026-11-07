"""Durable claim/receipt helpers for approved outbound effects.

This reuses the existing ``task_operation_records`` arbiter (the same table
TaskLifecycle uses for assignment operations) instead of introducing a second
send-state mechanism. The database uniqueness constraint is what makes two
racing retries collapse to one effect.

The same table now also arbitrates generic agent mutations: a server-owned
logical operation id is claimed before the handler runs, the complete frozen
execution identity is bound into the payload hash, and a replay can only
re-read/report that claim (never dispatch a second effect).

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


def _factory(db_factory=None):
    if db_factory is not None:
        return db_factory
    from core.database import get_db_session

    return get_db_session


def operation_payload_sha256(
    *,
    workspace_id: str,
    tenant_id: Optional[str],
    actor_id: Optional[str],
    agent_id: Optional[str],
    execution_id: Optional[str],
    action: str,
    frozen_args: Dict[str, Any],
    actor_kind: Optional[str] = None,
    execution_kind: Optional[str] = None,
) -> str:
    """Canonical hash of a generic agent operation's authorized material.

    Unlike :func:`payload_sha256` (the approval-flow shape), this binds the
    complete execution identity so the same logical operation cannot drift to
    a different action, actor, workspace, or argument set between dispatches.
    ``actor_kind`` / ``execution_kind`` record what the identity actually is,
    so an agent namespace is never silently presented as a user principal.
    """
    body = {
        "workspace_id": str(workspace_id or ""),
        "tenant_id": str(tenant_id or ""),
        "actor_id": str(actor_id or ""),
        "actor_kind": str(actor_kind or ""),
        "agent_id": str(agent_id or ""),
        "execution_id": str(execution_id or ""),
        "execution_kind": str(execution_kind or ""),
        "action": str(action or ""),
        "frozen_args": frozen_args or {},
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


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


def claim_generic_operation(
    *,
    workspace_id: str,
    tenant_id: Optional[str],
    operation_id: str,
    action: str,
    payload_hash: str,
    execution_id: Optional[str] = None,
    scope_id: Optional[str] = None,
    db_factory=None,
) -> Dict[str, Any]:
    """Atomically claim one generic-agent logical operation.

    The durable scope is the server-owned execution (``run_id``); the
    idempotency key is the logical operation id. The same logical operation
    presented by a restarted process or a cold continuation of the SAME
    execution therefore collapses to one row, while a genuinely new execution
    is a legitimate new intent (not forever payload-deduplicated). When no
    execution exists, an optional ``scope_id`` supplies the legacy dispatch
    scope (otherwise the operation id is the scope). The complete execution
    identity (including action and frozen args) is part of the payload hash, so
    the same key with changed material/action is a conflict and never a replay.

    A missing workspace is NOT defaulted: generic operations must carry their
    real scope, and inventing ``default`` would cross ownership boundaries.
    """
    from sqlalchemy.exc import IntegrityError, OperationalError

    from core.models import TaskOperationRecord

    if not str(workspace_id or "").strip() or not str(operation_id or "").strip():
        return {
            "won": False,
            "status": "unsupported",
            "error": "generic operation requires an explicit workspace and operation id",
        }
    execution = str(execution_id or "").strip()
    run_id = execution or str(scope_id or "").strip() or (
        f"operation:{str(operation_id).strip()}")
    key = str(operation_id).strip()
    record_id = str(uuid.uuid4())
    try:
        with _factory(db_factory)() as db:
            try:
                db.add(TaskOperationRecord(
                    id=record_id,
                    workspace_id=str(workspace_id or ""),
                    tenant_id=tenant_id,
                    run_id=run_id,
                    idempotency_key=key,
                    payload_sha256=payload_hash,
                    operation_id=str(operation_id),
                    operation_type=f"generic:agent:{str(action or '').strip()}",
                    status=CLAIMED,
                ))
                db.commit()
                return {"won": True, "status": CLAIMED,
                        "record_id": record_id, "payload_sha256": payload_hash,
                        "operation_id": str(operation_id)}
            except IntegrityError:
                db.rollback()
            except OperationalError as exc:
                db.rollback()
                logger.debug("generic operation claim contention: %s", exc)
            row = (
                db.query(TaskOperationRecord)
                .filter(
                    TaskOperationRecord.workspace_id == str(workspace_id or ""),
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
                    "operation_id": str(operation_id),
                    "error": "operation id is bound to different material",
                }
            return {"won": False, **_row_dict(row)}
    except Exception as exc:  # noqa: BLE001 — fail closed, no transport
        logger.error("generic operation claim failed: %s", exc)
        return {"won": False, "status": "unavailable", "error": str(exc)[:500]}


def mark_status(
    record_id: str,
    status: str,
    *,
    expected_status: Optional[Any] = None,
    db_factory=None,
) -> bool:
    """Persist a claim status transition. Never raises.

    When ``expected_status`` is supplied the transition is a database-level
    compare-and-swap: the conditional UPDATE binds the primary key, the
    currently allowed status, and the row's immutable payload digest. A peer
    that commits first makes the UPDATE match zero rows, so the stale writer
    cannot overwrite it. The ORM identity map is expired before commit and the
    UPDATE uses ``synchronize_session=False`` so no dirty-flush path can bypass
    the condition.

    Existing callers that pass no expectation keep the historical
    unconditional primary-key update; that path is NOT a CAS.
    """
    from core.models import TaskOperationRecord

    allowed = None
    if expected_status is not None:
        if isinstance(expected_status, (str, bytes)):
            allowed = {str(expected_status)}
        else:
            allowed = {str(item) for item in expected_status}
    try:
        with _factory(db_factory)() as db:
            row = db.query(TaskOperationRecord).filter(
                TaskOperationRecord.id == record_id).first()
            if row is None:
                return False
            if allowed is not None:
                from sqlalchemy import update

                payload_hash = row.payload_sha256
                db.expire_all()
                stmt = update(TaskOperationRecord).where(
                    TaskOperationRecord.id == record_id,
                    TaskOperationRecord.status.in_(allowed),
                    TaskOperationRecord.payload_sha256 == payload_hash,
                ).values(status=status).execution_options(
                    synchronize_session=False)
                result = db.execute(stmt)
                db.expire_all()
                db.commit()
                return int(result.rowcount or 0) == 1
            row.status = status
            db.commit()
            return True
    except Exception as exc:  # noqa: BLE001
        logger.error("outbound claim status update failed (%s): %s", status, exc)
        return False


def current(workspace_id: str, approval_id: str, *, db_factory=None) -> Optional[Dict[str, Any]]:
    from core.models import TaskOperationRecord

    try:
        with _factory(db_factory)() as db:
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


def generic_operations(
    workspace_id: str, operation_id: str, *, db_factory=None,
    strict: bool = False,
) -> list:
    """Return the durable generic-operation rows for one logical operation.

    Used by a cold-resumed agent to reload its own authoritative pending /
    uncertain state without inventing a second lifecycle store. Never raises
    unless ``strict`` is set (so callers can distinguish unreadable from
    authoritative zero rows).
    """
    from core.models import TaskOperationRecord

    try:
        with _factory(db_factory)() as db:
            rows = (
                db.query(TaskOperationRecord)
                .filter(
                    TaskOperationRecord.workspace_id == str(workspace_id or ""),
                    TaskOperationRecord.operation_id == str(operation_id or ""),
                    TaskOperationRecord.operation_type.like("generic:agent%"),
                )
                .all()
            )
            return [_row_dict(row) for row in rows]
    except Exception as exc:  # noqa: BLE001
        if strict:
            raise
        logger.debug("generic operation reload failed: %s", exc)
        return []


def generic_operations_for_execution(
    workspace_id: str, execution_id: str, *, db_factory=None,
    strict: bool = False,
) -> list:
    """Return every generic-operation row scoped to one durable execution.

    ``run_id`` is the server-owned execution identity, so a cold continuation
    can reload all unresolved claims without knowing the model's tool args.
    Never raises unless ``strict`` is set.
    """
    from core.models import TaskOperationRecord

    if not str(execution_id or "").strip():
        return []
    try:
        with _factory(db_factory)() as db:
            rows = (
                db.query(TaskOperationRecord)
                .filter(
                    TaskOperationRecord.workspace_id == str(workspace_id or ""),
                    TaskOperationRecord.run_id == str(execution_id),
                    TaskOperationRecord.operation_type.like("generic:agent%"),
                )
                .all()
            )
            return [_row_dict(row) for row in rows]
    except Exception as exc:  # noqa: BLE001
        if strict:
            raise
        logger.debug("generic execution reload failed: %s", exc)
        return []
