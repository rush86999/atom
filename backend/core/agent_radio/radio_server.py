"""Async in-process relay for the Agent Radio layer.

The DB (``radio_service``) is the source of truth; this server adds only the
*wakeup* mechanics so a working agent does not poll. Two primitives:

- ``publish``  — fire-and-forget: enqueue a just-persisted message's wakeups.
- ``wait_for_mention`` — bounded, agent-initiated block (drain-then-wait).

Passive awareness is NOT here — it is a cheap non-blocking DB drain at the
top of each ReAct iteration (``radio_service.inbox_drain_text``). Blocking
waits are strictly agent-initiated and timeout-bounded so a blocked peer can
never stall the team (paper: an agent that is working cannot also be
listening — the system must not force it to).

Redis: intentionally out of scope for v1 (Atom uses Redis for WS fan-out
only; cross-worker delivery can be layered on later without touching the
service API).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional, Tuple

from core.agent_radio import radio_config, radio_service
from core.models import LateralMessage

logger = logging.getLogger(__name__)


class RadioServer:
    """Singleton async relay. Safe to call from any running event loop."""

    def __init__(self) -> None:
        self._queues: Dict[str, Dict[str, "asyncio.Queue[str]"]] = {}
        self._events: Dict[str, Dict[str, "asyncio.Event"]] = {}

    async def publish(self, message: LateralMessage) -> None:
        """Wake every mentioned agent (non-blocking, never raises)."""
        try:
            thread_id = message.thread_id
            for agent_id in (message.mentions or []):
                q = self._queues.setdefault(thread_id, {}).get(agent_id)
                if q is not None:
                    q.put_nowait(message.id)
                ev = self._events.setdefault(thread_id, {}).get(agent_id)
                if ev is not None:
                    ev.set()
        except Exception as e:  # pragma: no cover - relay must never raise
            logger.debug(f"radio publish failed: {e}")

    def _register_listener(self, thread_id: str, agent_id: str) -> Tuple["asyncio.Queue[str]", "asyncio.Event"]:
        q = self._queues.setdefault(thread_id, {}).get(agent_id)
        if q is None:
            q = asyncio.Queue()
            self._queues.setdefault(thread_id, {})[agent_id] = q
        ev = self._events.setdefault(thread_id, {}).get(agent_id)
        if ev is None:
            ev = asyncio.Event()
            self._events.setdefault(thread_id, {})[agent_id] = ev
        return q, ev

    async def wait_for_mention(
        self,
        thread_id: str,
        agent_id: str,
        timeout: Optional[int] = None,
        *,
        db=None,
    ) -> Optional[LateralMessage]:
        """Bounded, agent-initiated block for a mention.

        Drains any already-pending DB mentions first (no lost messages), then
        waits up to ``timeout`` seconds (hard-capped by config) for a new
        mention. Returns the message, or ``None`` on timeout. Never raises.
        """
        max_wait = min(timeout or radio_config.wait_timeout_seconds(),
                       radio_config.wait_timeout_seconds())
        try:
            if db is not None:
                pending = radio_service.get_pending_mentions(
                    db, thread_id, agent_id, limit=1
                )
                if pending:
                    radio_service.mark_read(db, pending[0], agent_id)
                    return pending[0]

            q, ev = self._register_listener(thread_id, agent_id)
            # Drain queued wakeup tokens first (published between DB check and listen).
            if not q.empty():
                try:
                    q.get_nowait()
                except Exception:
                    pass
                if db is not None:
                    pending = radio_service.get_pending_mentions(
                        db, thread_id, agent_id, limit=1
                    )
                    if pending:
                        radio_service.mark_read(db, pending[0], agent_id)
                        return pending[0]

            ev.clear()
            try:
                await asyncio.wait_for(ev.wait(), timeout=max_wait)
            except asyncio.TimeoutError:
                return None
            if db is not None:
                pending = radio_service.get_pending_mentions(
                    db, thread_id, agent_id, limit=1
                )
                if pending:
                    radio_service.mark_read(db, pending[0], agent_id)
                    return pending[0]
            return None
        except Exception as e:  # pragma: no cover - defensive
            logger.debug(f"radio wait_for_mention failed: {e}")
            return None


_server: Optional[RadioServer] = None


def get_radio_server() -> RadioServer:
    global _server
    if _server is None:
        _server = RadioServer()
    return _server


def reset_radio_server() -> None:
    """Test-only reset so suites get a clean relay."""
    global _server
    _server = None
