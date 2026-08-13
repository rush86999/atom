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

Gated by ``ATOM_EXECUTION_RECOVERY_ENABLED`` (default true).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

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


def _recover_agent_executions(session: Session) -> int:
    """Mark orphaned running AgentExecution rows as failed.

    Returns the count recovered.
    """
    rows = (
        session.query(AgentExecution)
        .filter(AgentExecution.status == ExecutionStatus.RUNNING.value)
        .all()
    )
    now = datetime.now(timezone.utc)
    recovered = 0
    for row in rows:
        row.status = ExecutionStatus.FAILED.value
        row.error_message = _CRASH_ERROR_MESSAGE
        row.completed_at = now
        # Stamp a recovery marker in metadata_json (JSON-stored) so operators
        # can distinguish crash-recovered failures from genuine logic failures
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
        meta["recovery"] = {"crashed": True, "recovered_at": now.isoformat()}
        row.metadata_json = meta
        recovered += 1
    return recovered


def reconcile_orphaned_executions() -> dict:
    """Find and fail executions orphaned by a process crash.

    Runs once at startup. Idempotent: only touches rows still in a running
    state, so re-running is a no-op once they've been reconciled.

    Returns:
        ``{"workflow_recovered": int, "agent_recovered": int, "enabled": bool}``
    """
    if not RECOVERY_ENABLED:
        logger.info("Execution recovery disabled (ATOM_EXECUTION_RECOVERY_ENABLED=false)")
        return {"workflow_recovered": 0, "agent_recovered": 0, "enabled": False}

    session: Session = SessionLocal()
    try:
        wf_count = _recover_workflow_executions(session)
        agent_count = _recover_agent_executions(session)
        session.commit()
        if wf_count or agent_count:
            logger.warning(
                f"Crash recovery: reconciled {wf_count} workflow execution(s) and "
                f"{agent_count} agent execution(s) orphaned in a running state"
            )
        else:
            logger.info("Crash recovery: no orphaned executions found")
        return {
            "workflow_recovered": wf_count,
            "agent_recovered": agent_count,
            "enabled": True,
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Execution recovery sweep failed: {e}")
        return {"workflow_recovered": 0, "agent_recovered": 0, "enabled": True, "error": str(e)}
    finally:
        session.close()
