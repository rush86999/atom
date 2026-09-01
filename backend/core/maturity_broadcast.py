"""
Real-time maturity broadcast helper.

Learning only counts if the user can SEE the agent evolving. Every
confidence/tier change — outcome drips, feedback adjudication, canvas
corrections, training completions, graduation promotions — is pushed to the
workspace over the same WebSocket channels the chat UI already subscribes to
(`workspace:default` + tenant-scoped). The Redis ActivityPublisher is a
separate, optional path that degrades to a NO-OP without Redis; this module
is the always-on in-process surface.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Keep references to scheduled tasks so the loop doesn't garbage-collect
# them mid-flight (a bare create_task without a saved reference can).
_pending_tasks: set = set()


def workspace_channels(workspace_id: Optional[str]) -> List[str]:
    """Channels maturity events are broadcast to.

    Mirrors ``ChatOrchestrator._workspace_channels``: the chat UI subscribes
    to ``workspace:default``; the tenant-scoped channel keeps
    workspace-filtered listeners working.
    """
    channels = ["workspace:default"]
    if workspace_id and workspace_id != "default":
        channels.append(f"workspace:{workspace_id}")
    return channels


async def broadcast_maturity_update(
    workspace_id: Optional[str],
    agent_id: str,
    previous_confidence: Optional[float] = None,
    confidence: Optional[float] = None,
    previous_tier: Optional[str] = None,
    tier: Optional[str] = None,
    source: str = "outcome",
) -> None:
    """Push one ``maturity_update`` frame to the workspace UI.

    Never raises: a broken/absent WebSocket layer must not break the
    learning write that triggered it.
    """
    try:
        from core.websockets import get_connection_manager

        payload: Dict[str, Any] = {
            "agent_id": agent_id,
            "confidence": confidence,
            "previous_confidence": previous_confidence,
            "tier": tier,
            "previous_tier": previous_tier,
            "transition": bool(tier and previous_tier and tier != previous_tier),
            "source": source,
            "timestamp": datetime.now().isoformat(),
        }
        manager = get_connection_manager()
        for channel in workspace_channels(workspace_id):
            await manager.broadcast_event(channel, "maturity_update", payload)
    except Exception as e:  # noqa: BLE001 — never break the learning path
        logger.debug(f"maturity broadcast skipped for {agent_id}: {e}")


def schedule_maturity_broadcast(
    workspace_id: Optional[str],
    agent_id: str,
    previous_confidence: Optional[float] = None,
    confidence: Optional[float] = None,
    previous_tier: Optional[str] = None,
    tier: Optional[str] = None,
    source: str = "outcome",
) -> None:
    """Fire-and-forget entry point for SYNC learning code paths.

    Governance scoring, training completion, and correction penalties are
    synchronous DB writes that run inside async request handlers, so the
    broadcast is scheduled on the running loop. When no loop exists (a
    thread/CLI caller), the broadcast is skipped — the durable confidence
    write already happened and the UI reconciles on next fetch.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug(f"maturity broadcast skipped for {agent_id}: no running loop")
        return
    task = loop.create_task(
        broadcast_maturity_update(
            workspace_id=workspace_id,
            agent_id=agent_id,
            previous_confidence=previous_confidence,
            confidence=confidence,
            previous_tier=previous_tier,
            tier=tier,
            source=source,
        )
    )
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)
