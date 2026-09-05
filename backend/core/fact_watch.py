"""Fact-watch: proactive re-checking of live facts an agent grounded on.

Why this exists (live 2026-09-04): the Sales Assistant quoted
"WG-350DSAV — In Stock" on a customer email after a live Zoho Inventory
lookup showed stock_on_hand = 1. One sale later the draft is wrong, and
nobody — user or agent — learns about it until someone re-asks. The same
shape exists for EVERY provider an agent can ground on: a CRM deal stage,
an invoice status, a ticket SLA, a calendar slot. The honest-draft
contract ("data-dependent edits decline without evidence") covers the
moment of writing; this covers every moment AFTER.

General mechanism, provider-agnostic:

- A WATCH binds (provider, entity_type, entity_id, field) to the artifact
  context it grounded (canvas, user, agent, conversation) plus the last
  seen value.
- A CHECKER re-reads the live value. Providers register checkers in
  CHECKERS — one async function per (provider, entity_type); adding an
  app is adding a row, not new plumbing.
- An EXTRACTOR spots watchable facts inside raw tool-evidence text.
  Providers register extractors in EXTRACTORS — one function per service
  name, returning (entity_type, entity_id, field) tuples. Extraction is
  gated on a checker existing: no checker, nothing watchable, zero cost.
- poll_once() re-reads every watch, emits an event per CHANGED value
  (websocket to the owning user + a canvas_audit row so the artifact's
  trail carries the alert), and updates last_value. Cooldown suppresses
  duplicate notifications for the same state.

Watches are in-memory by design: they re-register naturally the next time
an agent grounds an edit on the same artifact (the evidence lookup runs
on every data-dependent edit), and process restarts start clean instead
of polling stale bindings.

Pure core: no provider imports. Providers register themselves from the
integrations side (see integrations/fact_watch_providers.py).
"""
import asyncio
import logging
import re
import time
from dataclasses import dataclass, field as dc_field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# (provider, entity_type) -> async (entity_id, user_id) -> value-or-None
Checker = Callable[[str, Optional[str]], Awaitable[Any]]
CHECKERS: Dict[Tuple[str, str], Checker] = {}

# service name (chat tool planner names) -> (text) -> [(entity_type, entity_id, field)]
Extractor = Callable[[str], List[Tuple[str, str, str]]]
EXTRACTORS: Dict[str, Extractor] = {}

_ID_IN_TEXT_RE = re.compile(
    r"[\"']?(?:item_id|id|entity_id)[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9\-]{4,})")


def register_checker(provider: str, entity_type: str, checker: Checker) -> None:
    CHECKERS[(provider, entity_type)] = checker


def register_extractor(service: str, extractor: Extractor) -> None:
    EXTRACTORS[service] = extractor


def extract_watchable_facts(service: str, evidence_text: str) -> List[Tuple[str, str, str]]:
    """Watchable (entity_type, entity_id, field) facts inside one tool
    result — only for services that have BOTH an extractor and a checker.
    Deduped, order-preserving. Without a checker for the service the
    extractor is not run at all: no checker, nothing watchable, zero cost."""
    extractor = EXTRACTORS.get(service)
    if not extractor:
        return []
    if not any(provider == service for provider, _entity_type in CHECKERS):
        return []
    seen: List[Tuple[str, str, str]] = []
    for entity_type, entity_id, fact_field in extractor(evidence_text or ""):
        if (service, entity_type) not in CHECKERS:
            continue
        key = (entity_type, entity_id, fact_field)
        if key not in seen:
            seen.append(key)
    return seen


@dataclass
class FactWatch:
    provider: str
    entity_type: str
    entity_id: str
    fact_field: str
    canvas_id: Optional[str]
    user_id: Optional[str]
    agent_id: Optional[str]
    conversation_id: Optional[str]
    last_value: Any = None
    last_state_notified: Any = dc_field(default=None)
    last_notified_at: float = 0.0
    registered_at: float = dc_field(default_factory=time.time)


@dataclass
class FactChangeEvent:
    watch: FactWatch
    old_value: Any
    new_value: Any


class FactWatchService:
    """Registry + poller for grounded facts. One instance per process
    (get_fact_watch_service). poll_once is the unit everything else
    composes; start/stop wrap it in a bounded asyncio loop."""

    def __init__(self, notify_cooldown_seconds: int = 1800):
        self._watches: Dict[str, FactWatch] = {}
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._notify_cooldown_seconds = notify_cooldown_seconds

    @staticmethod
    def _key(provider: str, entity_type: str, entity_id: str, fact_field: str) -> str:
        return f"{provider}|{entity_type}|{entity_id}|{fact_field}"

    async def register(
        self,
        provider: str,
        entity_type: str,
        entity_id: str,
        fact_field: str,
        canvas_id: Optional[str] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        current_value: Any = None,
    ) -> bool:
        """Register (or refresh the context of) one watch. Returns True when
        a NEW watch was created — refreshing an existing one keeps its
        last_value so a re-grounding doesn't self-notify."""
        if not provider or not entity_type or not entity_id or not fact_field:
            return False
        if (provider, entity_type) not in CHECKERS:
            return False
        async with self._lock:
            key = self._key(provider, entity_type, entity_id, fact_field)
            existing = self._watches.get(key)
            if existing:
                # Re-grounding on the same artifact: refresh bindings only.
                existing.canvas_id = canvas_id or existing.canvas_id
                existing.user_id = user_id or existing.user_id
                existing.agent_id = agent_id or existing.agent_id
                existing.conversation_id = conversation_id or existing.conversation_id
                return False
            self._watches[key] = FactWatch(
                provider=provider, entity_type=entity_type, entity_id=entity_id,
                fact_field=fact_field, canvas_id=canvas_id, user_id=user_id,
                agent_id=agent_id, conversation_id=conversation_id,
                last_value=current_value,
            )
        logger.info(
            f"fact watch registered: {provider}/{entity_type}/{entity_id}"
            f"/{fact_field} canvas={canvas_id} user={user_id}")
        return True

    async def register_from_trace(
        self,
        trace: Optional[Dict[str, Any]],
        canvas_id: Optional[str] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> int:
        """Register watches for every watchable fact inside one tool
        evidence trace ({service, block}). Returns the number of NEW
        watches. Best-effort by contract — never raises."""
        if not trace:
            return 0
        try:
            service = str(trace.get("service") or "")
            block = str(trace.get("block") or "")
            created = 0
            for entity_type, entity_id, fact_field in extract_watchable_facts(
                    service, block):
                if await self.register(
                        provider=self._provider_for(service),
                        entity_type=entity_type, entity_id=entity_id,
                        fact_field=fact_field, canvas_id=canvas_id,
                        user_id=user_id, agent_id=agent_id,
                        conversation_id=conversation_id):
                    created += 1
            return created
        except Exception as e:  # noqa: BLE001 — watching must never break editing
            logger.warning(f"fact watch registration skipped: {e}")
            return 0

    @staticmethod
    def _provider_for(service: str) -> str:
        """Chat tool service name -> checker provider name. Today they are
        identical; the seam exists because one provider can expose several
        tool services."""
        return service

    async def discard(self, provider: str, entity_type: str, entity_id: str,
                      fact_field: str) -> bool:
        """Remove one watch (verification tooling; user-facing unwatch can
        build on it). True when a watch was removed."""
        async with self._lock:
            return self._watches.pop(
                self._key(provider, entity_type, entity_id, fact_field),
                None) is not None

    def watches(self) -> List[FactWatch]:
        return list(self._watches.values())

    async def poll_once(self) -> List[FactChangeEvent]:
        """One re-check sweep over all watches. Events fire on any CHANGED
        value (stock 1→0, 0→1, deal stage moves, ...) — the subscriber
        decides what matters. Checkers run concurrently; one failing
        checker skips its watch for this tick."""
        async with self._lock:
            watches = list(self._watches.values())
        if not watches:
            return []

        async def _check(watch: FactWatch) -> Tuple[FactWatch, Any]:
            checker = CHECKERS.get((watch.provider, watch.entity_type))
            if not checker:
                return watch, None
            try:
                return watch, await checker(watch.entity_id, watch.user_id)
            except Exception as e:  # noqa: BLE001 — skip this tick
                logger.warning(
                    f"fact watch check failed for {watch.provider}/"
                    f"{watch.entity_id}: {e}")
                return watch, None

        results = await asyncio.gather(*(_check(w) for w in watches))
        events: List[FactChangeEvent] = []
        for watch, value in results:
            if value is None:
                continue
            if watch.last_value is not None and value != watch.last_value:
                events.append(FactChangeEvent(watch, watch.last_value, value))
            watch.last_value = value
        for event in events:
            await self._notify(event)
        return events

    async def _notify(self, event: FactChangeEvent) -> None:
        """Real-time notification leg: websocket to the owning user plus a
        canvas_audit row (the artifact trail the email-canvas API serves).
        Cooldown suppresses re-notifying the same state transition."""
        watch = event.watch
        now = time.time()
        state_key = (event.old_value, event.new_value)
        if (watch.last_state_notified == state_key
                and now - watch.last_notified_at < self._notify_cooldown_seconds):
            return
        watch.last_state_notified = state_key
        watch.last_notified_at = now

        payload = {
            "provider": watch.provider,
            "entity_type": watch.entity_type,
            "entity_id": watch.entity_id,
            "field": watch.fact_field,
            "old_value": event.old_value,
            "new_value": event.new_value,
            "canvas_id": watch.canvas_id,
            "message": (
                f"{watch.entity_type} {watch.entity_id} changed on "
                f"{watch.provider}: {watch.fact_field} "
                f"{event.old_value!r} -> {event.new_value!r}. A grounded "
                f"draft may need to be re-checked."),
        }
        try:
            from core.websockets import manager as ws_manager
            if watch.user_id:
                await ws_manager.broadcast_event(
                    f"user:{watch.user_id}", "fact_watch_alert", payload)
        except Exception as e:  # noqa: BLE001 — persistence leg still runs
            logger.warning(f"fact watch websocket skipped: {e}")
        try:
            if watch.canvas_id:
                from core.database import get_db_session
                from core.models import CanvasAudit
                import json as _json
                with get_db_session() as db:
                    db.add(CanvasAudit(
                        canvas_id=watch.canvas_id,
                        tenant_id="default",
                        action_type="fact_watch_alert",
                        agent_id=watch.agent_id,
                        canvas_type="email",
                        details_json=_json.dumps(payload),
                    ))
        except Exception as e:  # noqa: BLE001 — websocket leg still ran
            logger.warning(f"fact watch audit row skipped: {e}")

    async def start(self, interval_seconds: int = 300) -> None:
        """Bounded poll loop. Interval 0 disables (tests register + call
        poll_once directly)."""
        if self._task is not None:
            return
        if interval_seconds <= 0:
            logger.info("fact watch poller disabled (interval <= 0)")
            return

        async def _loop():
            while True:
                await asyncio.sleep(interval_seconds)
                try:
                    await self.poll_once()
                except Exception as e:  # noqa: BLE001 — the loop survives
                    logger.warning(f"fact watch poll tick failed: {e}")

        self._task = asyncio.create_task(_loop())
        logger.info(f"fact watch poller started (every {interval_seconds}s)")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None


_service: Optional[FactWatchService] = None


def get_fact_watch_service() -> FactWatchService:
    global _service
    if _service is None:
        _service = FactWatchService()
    return _service
