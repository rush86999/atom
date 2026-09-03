"""Tool-error signals — the feedstock the evolution harness was blind to.

Live anchor (2026-09-02): the sales hire's outlook search 400'd inside
``search_emails``, which swallowed it and returned ``[]``. The turn "succeeded",
the episode recorded outcome=success, and Memento/AlphaEvolver — which only
consume FAILED episodes — never saw a failure to fix. The whole evolution
harness (ReflectionEngine → Memento skills → AlphaEvolver tool mutations)
was downstream of a signal that died at the tool layer.

This module makes tool error responses first-class:

  - ``record_tool_error`` appends a structured entry to the agent's CURRENT
    RUNNING ``AgentExecution.metadata_json["tool_errors"]`` (episode
    finalization merges execution metadata, so the signal rides into the
    episode and TaskEvent without any new plumbing), and counts repeats in
    an in-process ring for cheap threshold checks.
  - ``effective_outcome`` downgrades a nominal success to a partial when
    tool errors are attached — a turn whose tools errored is not a clean
    success, whatever the transcript looks like.
  - ``summarize_tool_errors`` renders the entries for TaskEvent.error_trace
    so Memento's failure analysis sees the ACTUAL tool error text.

Fault-isolated by contract: recording must never break the tool call it
observes.
"""
import logging
from collections import deque
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Per-agent in-process ring of recent error signatures (repeat detection
# without a DB round-trip). Bounded; resets on restart is acceptable — the
# durable copy lives on the execution metadata.
_RECENT_ERRORS: Dict[str, deque] = defaultdict(lambda: deque(maxlen=32))
_RECENT_MAX_AGE = timedelta(minutes=60)


def tool_error_signature(service: str, action: str) -> str:
    """Stable per-tool signature ('outlook.search_emails') for repeat
    counting — the error text varies; the tool that produced it doesn't."""
    return f"{(service or '?').lower()}.{(action or '?').lower()}"


def record_tool_error(
    agent_id: Optional[str],
    service: str,
    action: str,
    error_detail: str,
    execution_id: Optional[str] = None,
    tenant_id: str = "default",
    user_id: Optional[str] = None,
) -> bool:
    """Attach a structured tool-error entry to the agent's current running
    execution and the in-process ring. Returns True when persisted.

    Never raises — a broken recorder must not break the tool call it
    observes."""
    entry = {
        "service": service,
        "action": action,
        "error": str(error_detail or "")[:500],
        "signature": tool_error_signature(service, action),
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    try:
        now = datetime.now(timezone.utc)
        ring = _RECENT_ERRORS[agent_id or (user_id or "unknown")]
        ring.append((now, entry["signature"]))
        # Guidance: tell the supervisor once per signature per hour that a
        # tool keeps failing — BEFORE any fix proposal exists.
        if agent_id:
            cutoff = now - _RECENT_MAX_AGE
            repeats = sum(1 for ts, sig in ring if sig == entry["signature"] and ts >= cutoff)
            if repeats >= 2:
                from core.auto_dev.guidance import notify_tool_error_pattern

                notify_tool_error_pattern(
                    agent_id=agent_id,
                    tenant_id=tenant_id,
                    signature=entry["signature"],
                    count=repeats,
                    last_error=entry["error"],
                )
    except Exception:
        pass
    try:
        from core.database import SessionLocal
        from core.models import AgentExecution

        target_id = execution_id
        if not target_id and agent_id:
            with SessionLocal() as db:
                running = (
                    db.query(AgentExecution)
                    .filter(
                        AgentExecution.agent_id == agent_id,
                        AgentExecution.status == "running",
                    )
                    .order_by(AgentExecution.started_at.desc())
                    .first()
                )
                target_id = str(running.id) if running else None
        if not target_id:
            return False

        with SessionLocal() as db:
            execution = (
                db.query(AgentExecution)
                .filter(AgentExecution.id == target_id)
                .first()
            )
            if execution is None:
                return False
            meta = dict(execution.metadata_json or {})
            errors = list(meta.get("tool_errors") or [])
            errors.append(entry)
            meta["tool_errors"] = errors[-10:]
            execution.metadata_json = meta
            db.commit()
            return True
    except Exception as e:
        logger.debug(f"tool error recording skipped: {e}")
        return False


# Live-evolution trigger reservation: one real-time dispatch per
# (agent, signature) per suppression window, so a long-running task that
# hits the same tool error 20 times spawns ONE fix candidate, not 20.
_LIVE_TRIGGERED: Dict[str, datetime] = {}
_LIVE_SUPPRESSION = timedelta(minutes=30)


def should_trigger_live(
    agent_id: Optional[str],
    signature: str,
    min_repeats: int = 2,
    suppression_minutes: int = 30,
) -> bool:
    """True exactly once per (agent, signature) per suppression window when
    the error ring shows ≥ min_repeats repeats — the caller's reservation
    for dispatching a REAL-TIME evolution trigger on an active task (before
    episode finalization)."""
    if not agent_id:
        return False
    now = datetime.now(timezone.utc)
    key = f"{agent_id}:{signature}"
    last = _LIVE_TRIGGERED.get(key)
    if last and now - last < timedelta(minutes=suppression_minutes):
        return False
    cutoff = now - _RECENT_MAX_AGE
    ring = _RECENT_ERRORS.get(agent_id)
    if not ring:
        return False
    repeats = sum(
        1 for ts, sig in ring if sig == signature and ts >= cutoff
    )
    if repeats < min_repeats:
        return False
    _LIVE_TRIGGERED[key] = now
    return True


def recent_error_count(
    agent_id: Optional[str],
    signature: Optional[str] = None,
    max_age_minutes: int = 60,
) -> int:
    """How many times this agent hit (this tool's) errors recently — the
    ReflectionEngine's repeat threshold input."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    ring = _RECENT_ERRORS.get(agent_id or "",)
    if not ring:
        return 0
    return sum(
        1
        for ts, sig in ring
        if ts >= cutoff and (signature is None or sig == signature)
    )


def effective_outcome(
    success: bool,
    outcome: str,
    execution_metadata: Optional[Dict[str, Any]],
) -> tuple:
    """Downgrade a nominal success when tools errored during the turn.

    A transcript can read as success while every tool call inside it failed
    (errors swallowed into empty results). Episodes must not record that as
    a clean success — Memento/AlphaEvolver only see failures."""
    errors = (execution_metadata or {}).get("tool_errors") or []
    if success and errors:
        return False, "partial"
    return success, outcome or ("success" if success else "failure")


def summarize_tool_errors(execution_metadata: Optional[Dict[str, Any]]) -> str:
    """One-line-per-error summary for TaskEvent.error_trace — this is what
    Memento's analyze_episode reads as the failure description."""
    errors = (execution_metadata or {}).get("tool_errors") or []
    lines = []
    for e in errors[-5:]:
        if isinstance(e, dict):
            lines.append(
                f"{e.get('signature') or e.get('service')}: {e.get('error')}"
            )
    return "\n".join(lines)
