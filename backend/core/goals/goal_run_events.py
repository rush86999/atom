"""Event ingestion for waiting GoalRuns
(docs/architecture/GOAL_RUN_ORCHESTRATION.md §3.3 waits, §3.4, slice 4).

A waiting run sleeps on a ``waiting_on`` spec; this module is the door the
outside world knocks on:

- :func:`ingest_event` — an inbound event (email reply, integration webhook,
  human input). Matches it against every waiting run in the workspace;
  consumed-once per the service; each woken run immediately advances one
  loop turn with the event in the router's context ("changes direction
  based on the event" applies across days, not just across steps).
- :func:`check_due_waits` — the timer half: runs whose wait deadline has
  passed (e.g. "no reply in 3 days → follow up"). Called from the sleep-time
  maintenance cycle.

Fault-isolated throughout: one broken run never blocks the others, and
ingestion never raises into the caller (an inbound email handler must not
fail because a goal run hiccuped).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Stalled-ACTIVE sweep threshold (maintenance cycle): a run whose status is
# 'active' but whose row shows no progress (updated_at) for longer than
# this is interrupted for the supervisor — the fire-and-forget driver
# (delegated agent objective loop, spawned task) died without a decision
# boundary. Generous by default (long delegated steps are legitimate);
# env-overridable in minutes.
STALE_ACTIVE_ENV = "ATOM_GOAL_RUN_STALE_MINUTES"
DEFAULT_STALE_ACTIVE_MINUTES = 360


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _stale_active_minutes() -> float:
    raw = os.environ.get(STALE_ACTIVE_ENV, "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
        logger.warning(
            f"{STALE_ACTIVE_ENV}={raw!r} is not a positive number — using "
            f"the default ({DEFAULT_STALE_ACTIVE_MINUTES} min)")
    return DEFAULT_STALE_ACTIVE_MINUTES


async def ingest_event(event: Dict[str, Any],
                       workspace_id: str = "default",
                       tenant_id: str = "default",
                       session_factory=None) -> Dict[str, Any]:
    """Deliver an event to the workspace's waiting runs. Returns which runs
    woke ({woke: [run_id…], skipped: n})."""
    from core.goals.goal_run_service import GoalRunService
    svc = GoalRunService(workspace_id=workspace_id, tenant_id=tenant_id,
                         session_factory=session_factory)
    woke: List[str] = []
    skipped = 0
    for run in svc.list_runs(status="waiting", include_terminal=False):
        try:
            result = svc.consume_wake(run["id"], event)
            if not result.get("consumed"):
                skipped += 1
                continue
            woke.append(run["id"])
            await svc.advance(run["id"], event=event)
        except Exception as exc:
            skipped += 1
            logger.warning(f"goal run {run['id']}: event advance failed: {exc}")
    return {"woke": woke, "skipped": skipped}


def due_timer_runs(workspace_id: str = "default", tenant_id: str = "default",
                   session_factory=None, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Waiting runs whose timer deadline has passed (spec: waiting_on.event
    == 'timer' with an ISO deadline). Malformed deadlines are reported, not
    raised."""
    from core.goals.goal_run_service import GoalRunService
    svc = GoalRunService(workspace_id=workspace_id, tenant_id=tenant_id,
                         session_factory=session_factory)
    now = now or _now()
    due: List[Dict[str, Any]] = []
    for run in svc.list_runs(status="waiting", include_terminal=False):
        spec = run.get("waiting_on") or {}
        if str(spec.get("event") or "").lower() != "timer":
            continue
        deadline = _parse_deadline(spec.get("deadline"))
        if deadline is None:
            continue
        if deadline <= now:
            due.append(run)
    return due


async def check_due_waits(workspace_id: str = "default",
                          tenant_id: str = "default",
                          session_factory=None,
                          now: Optional[datetime] = None) -> Dict[str, Any]:
    """Wake every due timer run and advance it one loop turn. The wake
    event names the deadline so the router's rationale can reference it."""
    from core.goals.goal_run_service import GoalRunService
    svc = GoalRunService(workspace_id=workspace_id, tenant_id=tenant_id,
                         session_factory=session_factory)
    woke: List[str] = []
    for run in due_timer_runs(workspace_id, tenant_id, session_factory, now):
        try:
            deadline = (run.get("waiting_on") or {}).get("deadline")
            wake = svc.consume_wake(run["id"], {
                "event": "timer", "source": "deadline", "deadline": deadline,
            })
            if wake.get("consumed"):
                woke.append(run["id"])
                await svc.advance(run["id"], event={
                    "event": "timer", "source": "deadline",
                    "summary": f"wait deadline reached ({deadline})",
                })
        except Exception as exc:
            logger.warning(f"goal run {run['id']}: timer wake failed: {exc}")
    return {"woke": woke}


def due_watchdog_runs(workspace_id: str = "default", tenant_id: str = "default",
                      session_factory=None, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Waiting runs whose NON-timer wait carried a deadline that has passed
    (spec: event != 'timer' with an ISO deadline — the operator/
    computer-use watchdog). The wake source for these waits is an
    in-memory registry pushed from a spawned fire-and-forget task, so a
    restart loses the wake and the run would sleep FOREVER without this
    deadline (timer wakes only fire event=='timer')."""
    from core.goals.goal_run_service import GoalRunService
    svc = GoalRunService(workspace_id=workspace_id, tenant_id=tenant_id,
                         session_factory=session_factory)
    now = now or _now()
    due: List[Dict[str, Any]] = []
    for run in svc.list_runs(status="waiting", include_terminal=False):
        spec = run.get("waiting_on") or {}
        if str(spec.get("event") or "").lower() == "timer":
            continue  # the timer path owns timer deadlines
        if not spec.get("deadline"):
            continue
        deadline = _parse_deadline(spec.get("deadline"))
        if deadline is not None and deadline <= now:
            due.append(run)
    return due


async def check_due_watchdog_wakes(workspace_id: str = "default",
                                   tenant_id: str = "default",
                                   session_factory=None,
                                   now: Optional[datetime] = None) -> Dict[str, Any]:
    """Wake every watchdog-expired run and advance it one loop turn. The
    wake event carries the wait's own match keys (so consume_wake accepts
    it) and names the expiry honestly — the router re-decides with the
    failed step in context; the decision log records why."""
    from core.goals.goal_run_service import GoalRunService
    svc = GoalRunService(workspace_id=workspace_id, tenant_id=tenant_id,
                         session_factory=session_factory)
    woke: List[str] = []
    for run in due_watchdog_runs(workspace_id, tenant_id, session_factory, now):
        spec = run.get("waiting_on") or {}
        event = {"event": str(spec.get("event") or "any"),
                 "source": "watchdog",
                 "summary": (f"watchdog deadline reached "
                             f"({spec.get('deadline')}) waiting for "
                             f"'{spec.get('event')}' — treating the step "
                             f"as interrupted")}
        event.update({str(k): v for k, v in (spec.get("match") or {}).items()})
        try:
            wake = svc.consume_wake(run["id"], event)
            if not wake.get("consumed"):
                continue
            woke.append(run["id"])
            svc.append_decision(run["id"], {
                "kind": "wait_deadline_reached",
                "rationale": event["summary"],
            })
            await svc.advance(run["id"], event=event)
        except Exception as exc:
            logger.warning(f"goal run {run['id']}: watchdog wake failed: {exc}")
    return {"woke": woke}


def interrupt_stalled_runs_all_workspaces(session_factory=None,
                                          now: Optional[datetime] = None) -> Dict[str, Any]:
    """Maintenance sweep: runs stuck ACTIVE with no row progress
    (updated_at) beyond the stale threshold are marked INTERRUPTED for
    their supervisor — ``paused_hitl`` plus an honest pending ASK_HUMAN
    decision resolved through the normal resume flow. NOT auto-cancelled:
    the state is surfaced, the human decides (a long delegated step may be
    legitimate; raise ATOM_GOAL_RUN_STALE_MINUTES if so). Covers the
    crash-of-a-fire-and-forget-driver case (canvas-work delegation is a
    spawned task — its death left the run 'active' with no driver)."""
    from core.database import get_db_session
    from core.models import GoalRun
    from core.goals.goal_run_service import GoalRunService

    now = now or _now()
    cutoff = now - timedelta(minutes=_stale_active_minutes())
    try:
        sessions = session_factory or get_db_session
        with sessions() as db:
            rows = db.query(GoalRun).filter(
                GoalRun.status == "active").all()
            stalled = [r for r in rows
                       if _as_utc(r.updated_at) is not None
                       and _as_utc(r.updated_at) < cutoff]
    except Exception as exc:
        logger.warning(f"goal-run stalled scan failed: {exc}")
        return {"interrupted": [], "error": str(exc)}
    interrupted: List[str] = []
    for row in stalled:
        try:
            svc = GoalRunService(
                workspace_id=row.workspace_id or "default",
                tenant_id=row.tenant_id or "default",
                session_factory=session_factory)
            svc.interrupt_stalled(
                row.id,
                reason=(f"no progress for over "
                        f"{_stale_active_minutes():g} minutes while "
                        f"'active' — the run's driver (delegated agent "
                        f"work or spawned task) appears to have died; "
                        f"review and resume or cancel"))
            interrupted.append(row.id)
        except Exception as exc:
            logger.warning(f"goal run {row.id}: stall interrupt failed: {exc}")
    if interrupted:
        logger.info(f"goal runs interrupted as stalled: {interrupted}")
    return {"interrupted": interrupted}


def _parse_deadline(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        deadline = datetime.fromisoformat(text)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return deadline
    except ValueError:
        logger.warning(f"unparseable goal-run wait deadline: {value!r}")
        return None


async def notify_canvas_done(canvas_id: str, reason: Optional[str] = None,
                             summary: Optional[str] = None) -> Dict[str, Any]:
    """Canvas done-signal → the owning goal run re-decides its next
    direction (§3.3). Called fire-and-forget from the chat orchestrator
    after a canvas edit cycle (`no_change` = "already reflects the goal" is
    a done-signal like any other). Fault-isolated end to end: a chat turn
    must never fail because the run loop hiccuped, and canvases without a
    goal-run link are a no-op."""
    from core.database import get_db_session
    from core.goals.goal_run_service import GoalRunService
    from core.models import Canvas
    try:
        with get_db_session() as db:
            canvas = db.query(Canvas).filter(Canvas.id == str(canvas_id)).first()
            if not canvas or not canvas.goal_run_id:
                return {"advanced": False, "reason": "no goal-run link"}
            run_id = canvas.goal_run_id
            workspace = canvas.workspace_id or "default"
            tenant = canvas.tenant_id or "default"
            digest = {"canvas_id": str(canvas_id),
                      "canvas_type": canvas.canvas_type,
                      "reason": reason,
                      "summary": (summary or "")[:500]}
        svc = GoalRunService(workspace_id=workspace, tenant_id=tenant)
        return await svc.advance(run_id, step_digest=digest)
    except Exception as exc:
        logger.warning(f"goal run advance on canvas done failed: {exc}")
        return {"advanced": False, "error": str(exc)}


async def wake_due_runs_all_workspaces(session_factory=None) -> Dict[str, Any]:
    """Timer + watchdog half for the sleep-time maintenance cycle: check
    EVERY workspace with waiting runs — timer deadlines (follow-ups) and
    watchdog deadlines (bounded non-timer waits, e.g. operator work). One
    broken workspace never blocks the rest."""
    from core.database import get_db_session
    from core.models import GoalRun
    pairs = set()
    try:
        with get_db_session() as db:
            rows = db.query(GoalRun.workspace_id, GoalRun.tenant_id).filter(
                GoalRun.status == "waiting").all()
            pairs = {(ws or "default", tn or "default") for ws, tn in rows}
    except Exception as exc:
        logger.warning(f"goal-run timer scan failed: {exc}")
        return {"woke": [], "error": str(exc)}
    woke: List[str] = []
    for workspace, tenant in sorted(pairs):
        try:
            result = await check_due_waits(workspace, tenant, session_factory)
            woke.extend(result.get("woke") or [])
        except Exception as exc:
            logger.warning(f"goal-run timer wake failed for {workspace}: {exc}")
        try:
            result = await check_due_watchdog_wakes(
                workspace, tenant, session_factory)
            woke.extend(result.get("woke") or [])
        except Exception as exc:
            logger.warning(f"goal-run watchdog wake failed for {workspace}: {exc}")
    return {"woke": woke}
