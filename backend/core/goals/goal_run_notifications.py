"""User guidance + notifications for GoalRuns (§6 "nothing silent").

Every state change a supervisor might need to act on is pushed through the
canonical in-app notification path — NotificationService.send_notification
(the same store the bell dropdown polls) — with the GUIDANCE embedded in the
message: what happened, what it means, and what to do next. Approval moments
reuse the "approval_needed" type so opted-in users also get email.

Recipient: the run's creator (the supervising user). No creator → no
notification (agent-internal runs stay silent). Fault-isolated end to end:
a notification glitch never blocks the run loop, mirroring the workflow
engine's best-effort fan-out (workflow_engine._notify_workflow_paused).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_RUN_PAGE = "/goal-runs/{run_id}"


def schedule_notification(coro) -> None:
    """Fire-and-forget an async notification from sync or async code:
    create_task inside a running loop; a private loop otherwise (direct
    service calls in tests/scripts). Exceptions are logged, never raised."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None:
        loop.create_task(_swallow(coro))
    else:
        try:
            asyncio.run(_swallow(coro))
        except Exception as exc:  # asyncio.run re-raises loop errors only
            logger.warning(f"goal run notification failed: {exc}")


async def _swallow(coro) -> None:
    try:
        await coro
    except Exception as exc:
        logger.warning(f"goal run notification failed: {exc}")


async def notify_run_event(kind: str, run: Dict[str, Any],
                           decision: Optional[Dict[str, Any]] = None,
                           step_title: Optional[str] = None,
                           deadline: Optional[str] = None,
                           event_desc: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Send one guidance-bearing notification for a run state change."""
    recipient = run.get("created_by")
    if not recipient:
        return None
    run_id = str(run.get("id") or "")
    base = {
        "workspace_id": run.get("workspace_id") or "default",
        "tenant_id": run.get("tenant_id") or "default",
        "action_url": _RUN_PAGE.format(run_id=run_id),
        "action_label": "Open goal run",
        "goal_run_id": run_id,
    }
    role = run.get("role") or "agent"
    if kind == "decision_held":
        what = (decision or {}).get("decision") or "a decision"
        rationale = ((decision or {}).get("rationale") or "")[:300]
        payload = {**base,
                   "title": f"Goal run needs your approval ({role})",
                   "message": (f"The agent decided to {what}: {rationale} — "
                               f"approve to continue, or override with guidance "
                               f"(an override teaches the agent instantly)."),
                   "priority": "high"}
        ntype = "approval_needed"
    elif kind == "checkpoint":
        payload = {**base,
                   "title": f"Checkpoint: {step_title or 'human approval'} ({role})",
                   "message": (f"The run paused at a process checkpoint "
                               f"({step_title or 'approval'}). Approve to continue — "
                               f"the agent cannot proceed without you."),
                   "priority": "high"}
        ntype = "approval_needed"
    elif kind == "waiting":
        until = f", next wake by {deadline}" if deadline else ""
        payload = {**base,
                   "title": f"Goal run is waiting ({role})",
                   "message": (f"Sleeping until {event_desc or 'an external event'}"
                               f"{until}. Nothing to do — you'll be notified when "
                               f"it wakes.")}
        ntype = "goal_run_waiting"
    elif kind == "achieved":
        payload = {**base,
                   "title": f"Goal achieved ({role})",
                   "message": (f"The run reached its goal after "
                               f"{run.get('steps_executed') or 0} steps and "
                               f"{run.get('replan_count') or 0} replans. Distill it "
                               f"into a playbook draft from the run page so the "
                               f"whole role learns from it.")}
        ntype = "goal_run_achieved"
    elif kind == "stopped":
        payload = {**base,
                   "title": f"Goal run {run.get('status')} ({role})",
                   "message": "The run stopped before reaching its goal. Its "
                              "decision log shows the path taken."}
        ntype = "goal_run_stopped"
    else:
        logger.warning(f"unknown goal-run notification kind {kind!r}")
        return None

    from core.notification_service import NotificationService
    return await NotificationService().send_notification(recipient, ntype, payload)
