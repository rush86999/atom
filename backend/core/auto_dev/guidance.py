"""Auto-Dev guidance & notifications — the user-facing half of the
evolution harness.

Journey gap (2026-09-02): the harness detected recurring tool failures and
created pending fix candidates, but the supervisor only found out by opening
Agent Studio. Guidance now flows to the user two ways:

  1. Durable — ``AgentFeedEvent`` rows (importance=2) surfaced by
     GET /api/autodev/guidance and the AutoDevReviewPanel banner.
  2. Live — a ``autodev_guidance`` websocket broadcast on the workspace
     channel so an open Agent Studio refreshes immediately.

Two guidance moments:
  - ``notify_tool_error_pattern`` — a tool keeps failing (fired once per
    signature per hour at the chokepoint, before any proposal exists).
  - ``notify_proposal`` — a fix candidate was proposed and awaits review.

Fault-isolated by contract: guidance must never break the pipeline that
produces it.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

EVENT_TYPE = "autodev_guidance"
# One tool-error guidance per signature per hour — repeated failures of the
# same tool are one message, not N.
_REPEAT_SUPPRESSION = timedelta(hours=1)
_notified: Dict[str, datetime] = {}


def notify_tool_error_pattern(
    agent_id: str,
    tenant_id: str,
    signature: str,
    count: int,
    last_error: str,
) -> None:
    """Tell the supervisor a tool keeps failing for their agent."""
    _emit(
        tenant_id=tenant_id,
        agent_id=agent_id,
        kind="tool_error_pattern",
        title=f"{signature} has failed {count}× recently",
        detail=(last_error or "")[:300],
        data={"signature": signature, "count": count},
        dedupe_key=f"tool_error:{agent_id}:{signature}",
    )


def notify_proposal(
    agent_id: str,
    tenant_id: str,
    kind: str,
    name: str,
    candidate_id: str,
    failure_summary: str = "",
) -> None:
    """Tell the supervisor a fix was proposed and awaits their review."""
    label = "Tool fix" if kind == "mutation" else "New skill"
    _emit(
        tenant_id=tenant_id,
        agent_id=agent_id,
        kind="proposal",
        title=f"{label} proposed: {name}",
        detail=(failure_summary or "")[:300],
        data={"candidate_kind": kind, "candidate_id": candidate_id, "name": name},
        dedupe_key=None,
    )


def _emit(
    tenant_id: str,
    agent_id: str,
    kind: str,
    title: str,
    detail: str,
    data: Dict[str, Any],
    dedupe_key: Optional[str] = None,
) -> None:
    try:
        if dedupe_key:
            now = datetime.now(timezone.utc)
            last = _notified.get(dedupe_key)
            if last and now - last < _REPEAT_SUPPRESSION:
                return
            _notified[dedupe_key] = now

        from core.database import SessionLocal
        from core.models import AgentFeedEvent

        with SessionLocal() as db:
            db.add(AgentFeedEvent(
                tenant_id=tenant_id,
                agent_id=agent_id,
                event_type=EVENT_TYPE,
                message=title,
                data={"kind": kind, "detail": detail, **data},
                importance=2,
            ))
            db.commit()

        try:
            import asyncio

            # Create the coroutine ONLY when a loop is running — building it
            # in a sync context (scripts/tests) leaks an un-awaited warning.
            loop = asyncio.get_running_loop()
            from core.websockets import manager as ws_manager

            payload = {
                "agent_id": agent_id,
                "kind": kind,
                "title": title,
                "detail": detail,
                **data,
            }
            loop.create_task(ws_manager.broadcast_event(
                "workspace:default", EVENT_TYPE, payload
            ))
        except RuntimeError:
            # No running loop (sync caller) — durable record is enough.
            pass
        except Exception as ws_err:
            logger.debug(f"autodev guidance websocket skipped: {ws_err}")
    except Exception as e:
        logger.debug(f"autodev guidance skipped: {e}")
