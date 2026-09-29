"""Execution crash-recovery sweep.

On startup, find executions that were ``RUNNING`` when the process died and
mark them as failed so they become visible to failure dashboards and retry
logic. Without this, a process crash mid-run orphans the row in ``RUNNING``
forever — neither completed, failed, nor retried (the "ghost run" problem).

This is **reconcile-only** (safe): it marks crashed runs as ``FAILED``; it
does NOT auto-resume them. Re-entering a crashed run risks double-firing
side effects (emails sent, cards charged) from a partially-completed step.
The workflow engine already has resume-skip logic
(workflow_engine.py:614, :253) for the future auto-resume path, but that
should only be enabled once steps declare idempotency.

A row whose owner is VERIFIED ALIVE is left alone, and a row whose ownership
cannot be established is also left alone -- this sweep must never fail another
live worker's execution, and "I cannot see who owns this" is not evidence that it
died. Only a VERIFIED dead owner (no such pid, or a confirmed pid reuse) is
reconciled. Ownership is recorded on every ORM insert by
``core.execution_ownership``; rows it cannot account for are reported in
``agent_unknown_detail`` rather than acted on.

Gated by ``ATOM_EXECUTION_RECOVERY_ENABLED`` (default true).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import AgentExecution, ExecutionStatus, WorkflowExecution, WorkflowExecutionStatus

logger = logging.getLogger(__name__)

RECOVERY_ENABLED = os.getenv("ATOM_EXECUTION_RECOVERY_ENABLED", "true").lower() == "true"

_CRASH_ERROR_MESSAGE = "Process restarted while execution was running (crashed)"


def _recover_workflow_executions(session: Session) -> int:
    """Mark orphaned RUNNING WorkflowExecution rows as FAILED.

    Returns the count recovered.
    """
    rows = (
        session.query(WorkflowExecution)
        .filter(WorkflowExecution.status == WorkflowExecutionStatus.RUNNING.value)
        .all()
    )
    now = datetime.now(timezone.utc)
    recovered = 0
    for row in rows:
        row.status = WorkflowExecutionStatus.FAILED.value
        row.error = _CRASH_ERROR_MESSAGE
        row.completed_at = now
        # Stamp a recovery marker in context (JSON-stored) so operators can
        # distinguish crash-recovered failures from genuine logic failures.
        ctx = {}
        if row.context:
            try:
                ctx = json.loads(row.context) if isinstance(row.context, str) else dict(row.context)
            except (ValueError, TypeError):
                ctx = {}
        ctx.setdefault("recovery", {})
        ctx["recovery"] = {"crashed": True, "recovered_at": now.isoformat()}
        row.context = json.dumps(ctx)
        recovered += 1
    return recovered


def _recover_agent_executions(session: Session) -> Tuple[int, int, List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """Mark orphaned running AgentExecution rows as failed.

    Returns ``(recovered, untouched, detail, unknown, recovered_ids)``.

    Three verdicts, from `core.execution_ownership.owner_liveness`:

    * VERIFIED live owner (``live`` / ``self``) -> untouched. A second process
      on this database must never fail a turn another live process is running.
    * VERIFIED dead owner (``dead``: no such pid, or a CONFIRMED pid reuse) ->
      reconciled.
    * Anything else (``unknown``) -> untouched AND reported. A missing stamp, an
      owner on another host, and a failed liveness inspection are all "cannot
      tell". Treating them as dead is how a running turn gets failed by a
      process that simply could not see who owned it -- and the earlier version
      of this function did exactly that for the first two cases.

    Only reconciled ids reach `_release_crashed_chat_requests`, so a key is never
    released on the strength of an unverified owner.
    """
    from core.execution_ownership import owner_liveness

    rows = (
        session.query(AgentExecution)
        .filter(AgentExecution.status == ExecutionStatus.RUNNING.value)
        .all()
    )
    now = datetime.now(timezone.utc)
    recovered: List[str] = []
    untouched: List[Dict[str, Any]] = []
    unknown: List[Dict[str, Any]] = []
    for row in rows:
        state, info = owner_liveness(row.metadata_json)
        if state == "unknown":
            unknown.append({"execution_id": row.id, "owner_state": state, **info})
            continue
        if state in ("live", "self"):
            untouched.append({"execution_id": row.id, "owner_state": state, **info})
            continue
        row.status = ExecutionStatus.FAILED.value
        row.error_message = _CRASH_ERROR_MESSAGE
        row.completed_at = now
        # Stamp a recovery marker in metadata_json (JSON-stored) so operators can
        # distinguish crash-recovered failures from genuine logic failures
        # — mirroring the workflow path which stamps ``context``. Without this,
        # recovered runs are indistinguishable from real failures.
        meta = {}
        if row.metadata_json:
            try:
                # dict(...) copies so the stamped dict is a NEW object; mutating
                # and re-assigning the ORM's own JSON dict in place does not
                # register a change, so the recovery marker would never persist.
                meta = dict(row.metadata_json)
            except (ValueError, TypeError):
                meta = {}
        meta.setdefault("recovery", {})
        meta["recovery"] = {"crashed": True, "recovered_at": now.isoformat(),
                            "owner_state": state}
        row.metadata_json = meta
        recovered.append(row.id)
    return len(recovered), len(untouched), untouched, unknown, recovered


def _metadata_value(metadata: Any, key: str) -> Any:
    """Read one key out of a metadata blob of unknown shape.

    `metadata_json` is a JSON column, so it can be a dict, a JSON *string*, or
    (in rows written by older code) a scalar. Every reader here has to survive
    all three; the recovery path below already does, and a helper keeps the
    attribution path from being the one that raises on a weird row.
    """
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (ValueError, TypeError):
            return None
    if isinstance(metadata, dict):
        return metadata.get(key)
    return None


def _release_crashed_chat_requests(session: Session, recovered_ids: List[str]) -> int:
    """Resolve keyed chat requests whose execution this sweep just terminated.

    `ChatRequestRecord` deliberately holds `in_progress` rather than risk
    repeating a possibly-completed side effect when a turn dies mid-flight --
    the documented client contract was "mint a fresh request_id". That policy is
    sound on its own, but it collides with the sweep: once the sweep marks the
    execution failed, the truth is known (this turn did not complete here) while
    the key stays `in_progress` forever, so a client retrying the SAME id is told
    "already in progress" indefinitely. An indefinite in-progress answer is not a
    recovery policy, it is the absence of one.

    So the key moves to the terminal `crashed` state carrying that truth. It is
    deliberately NOT a successful pin: the sweep cannot know whether a side
    effect landed before the crash, so it must not hand back a response claiming
    one, and it must not re-execute. `chat_transport.check` turns a `crashed`
    record into an explicit 409, so a same-id retry is told the truth and a fresh
    id starts a new turn.

    ATTRIBUTION, NOT RECENCY. `ChatRequestRecord.execution_id` is written only at
    finalization, so a crashed turn's key has NULL there and cannot be joined on
    it. The join is on the request id the turn recorded at claim time
    (`metadata_json.request_id`). A recovered execution with no recorded request
    id releases nothing rather than guessing -- a key resolved on a guess would
    tell a client its turn crashed when it may have completed under another id.

    Idempotent: only rows still `in_progress` are touched.
    """
    if not recovered_ids:
        return 0
    try:
        from core.chat_transport import CRASHED, IN_PROGRESS
        from core.models import AgentExecution, ChatRequestRecord
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"crashed chat-request release skipped: {exc}")
        return 0
    request_ids = [
        rid for rid in (
            _metadata_value(row.metadata_json, "request_id")
            for row in session.query(AgentExecution)
            .filter(AgentExecution.id.in_(recovered_ids)).all()
        ) if rid
    ]
    if not request_ids:
        return 0
    released = 0
    now = datetime.now(timezone.utc)
    for record in (session.query(ChatRequestRecord)
                   .filter(ChatRequestRecord.request_id.in_(request_ids))
                   .all()):
        if record.state != IN_PROGRESS:
            continue
        record.state = CRASHED
        record.error = ("the process restarted while this turn was in flight; "
                        "it did not complete. Send a new request_id to try again.")
        record.updated_at = now
        released += 1
    return released



def reconcile_orphaned_executions() -> dict:
    """Find and fail executions orphaned by a process crash.

    Runs once at startup. Idempotent: only touches rows still in a running
    state, so re-running is a no-op once they've been reconciled.

    Returns:
        ``{"workflow_recovered": int, "agent_recovered": int,
           "agent_untouched_live": int, "agent_untouched_detail": [...],
           "agent_unknown_owner": int, "agent_unknown_detail": [...],
           "chat_requests_released": int, "enabled": bool}``
    """
    if not RECOVERY_ENABLED:
        logger.info("Execution recovery disabled (ATOM_EXECUTION_RECOVERY_ENABLED=false)")
        return {"workflow_recovered": 0, "agent_recovered": 0,
                "agent_untouched_live": 0, "agent_untouched_detail": [],
                "agent_unknown_owner": 0, "agent_unknown_detail": [],
                "chat_requests_released": 0, "enabled": False}

    session: Session = SessionLocal()
    try:
        wf_count = _recover_workflow_executions(session)
        (agent_count, untouched, untouched_detail,
         unknown, recovered_ids) = _recover_agent_executions(session)
        released = _release_crashed_chat_requests(session, recovered_ids)
        session.commit()
        if wf_count or agent_count or released:
            logger.warning(
                f"Crash recovery: reconciled {wf_count} workflow execution(s) and "
                f"{agent_count} agent execution(s) with a VERIFIED dead owner; "
                f"released {released} in-progress chat request(s); left "
                f"{untouched} alone (live owner) and {len(unknown)} UNKNOWN "
                f"(ownership not established -- not touched, not declared crashed)"
            )
        else:
            logger.info("Crash recovery: no orphaned executions found")
        if unknown:
            # Loud on purpose: these are rows this process cannot account for.
            # They are NOT reconciled, so somebody has to be able to see them.
            for row in unknown:
                logger.warning(
                    "Crash recovery: ownership UNKNOWN, left running and NOT "
                    "declared crashed: execution=%s reason=%s owner=%s",
                    row.get("execution_id"), row.get("reason"),
                    {k: row.get(k) for k in ("pid", "host", "token")})
        return {
            "workflow_recovered": wf_count,
            "agent_recovered": agent_count,
            "agent_untouched_live": untouched,
            "agent_untouched_detail": untouched_detail,
            "agent_unknown_owner": len(unknown),
            "agent_unknown_detail": unknown,
            "chat_requests_released": released,
            "enabled": True,
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Execution recovery sweep failed: {e}")
        return {"workflow_recovered": 0, "agent_recovered": 0,
                "agent_untouched_live": 0, "agent_untouched_detail": [],
                "agent_unknown_owner": 0, "agent_unknown_detail": [],
                "chat_requests_released": 0, "enabled": True, "error": str(e)}
    finally:
        session.close()
