"""
Extraction Queue — drains prompts before truncation drops facts.

Design:
  - In-memory ``asyncio.Queue`` (sufficient for Personal Edition and tests).
  - Background consumer drains with bounded concurrency; one LLM call per item.
  - ``enqueue()`` is non-blocking and never raises — a queue failure must not
    delay the user-visible response (the truncation itself already happened).
  - Worker calls ``TurnFactExtractor.extract_from_prompt_before_truncation``.
  - Idempotent start: calling ``ensure_worker()`` multiple times is safe.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from core.turn_fact_extractor import (
    TURN_FACT_PRE_COMPRESS_ENABLED,
    get_turn_fact_extractor,
)

logger = logging.getLogger(__name__)


@dataclass
class _PendingExtraction:
    prompt: str
    workspace_id: str
    tenant_id: str = "default"
    execution_id: Optional[str] = None
    episode_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    model: Optional[str] = None


class ExtractionQueue:
    """
    Bounded in-memory queue. Background worker drains items one at a time
    (rate-limit-friendly); extraction is classification, not latency-sensitive.
    """

    def __init__(self, maxsize: int = 100):
        self._q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._worker_task: Optional[asyncio.Task] = None
        self._started = False
        self._drained_count = 0
        self._dropped_count = 0

    # ------------------------------------------------------------------ public

    def enqueue(
        self,
        prompt: str,
        workspace_id: str,
        execution_id: Optional[str] = None,
        tenant_id: str = "default",
        episode_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> bool:
        """
        Non-blocking enqueue. Returns True if queued, False if dropped
        (queue full or flag disabled). NEVER raises.
        """
        if not TURN_FACT_PRE_COMPRESS_ENABLED:
            return False
        if not prompt or not workspace_id:
            return False
        item = _PendingExtraction(
            prompt=prompt,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            execution_id=execution_id,
            episode_id=episode_id,
            session_id=session_id,
            user_id=user_id,
            model=model,
        )
        try:
            self._q.put_nowait(item)
            return True
        except asyncio.QueueFull:
            self._dropped_count += 1
            logger.warning(
                "turn_fact extraction queue full — dropped item "
                "(dropped_total=%d)", self._dropped_count
            )
            return False

    def ensure_worker(self) -> None:
        """Start the background consumer if not already running. Idempotent."""
        if self._started:
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                return
            self._worker_task = loop.create_task(self._worker_loop())
            self._started = True
            logger.info("turn_fact extraction worker started")
        except RuntimeError:
            # No running loop (e.g., called from sync context) — defer start
            logger.debug("turn_fact worker start deferred (no running loop)")

    async def drain_once(self) -> int:
        """Process one item. Returns count extracted (for tests)."""
        try:
            item = self._q.get_nowait()
        except asyncio.QueueEmpty:
            return 0
        return await self._process(item)

    def stats(self) -> dict:
        return {
            "queued": self._q.qsize(),
            "drained": self._drained_count,
            "dropped": self._dropped_count,
            "worker_started": self._started,
        }

    # ------------------------------------------------------------------ worker

    async def _worker_loop(self) -> None:
        """Drain the queue forever. Each item → one extraction call."""
        while True:
            try:
                item = await self._q.get()
                await self._process(item)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Worker must never die — log and continue
                logger.warning("turn_fact worker iteration failed: %s", e)
                await asyncio.sleep(0.1)

    async def _process(self, item: _PendingExtraction) -> int:
        try:
            extractor = get_turn_fact_extractor(
                workspace_id=item.workspace_id,
                tenant_id=item.tenant_id,
            )
            rows = await extractor.extract_from_prompt_before_truncation(
                prompt=item.prompt,
                execution_id=item.execution_id,
                episode_id=item.episode_id,
                session_id=item.session_id,
                user_id=item.user_id,
            )
            self._drained_count += 1
            if rows:
                logger.info(
                    "turn_fact pre-compress extracted %d facts (ws=%s)",
                    len(rows), item.workspace_id,
                )
            return len(rows)
        except Exception as e:
            # Never raise — extraction is best-effort
            logger.warning("turn_fact pre-compress extraction failed: %s", e)
            return 0


# ---------------------------------------------------------------------------
# Module-level singleton + lazy accessor
# ---------------------------------------------------------------------------
_queue: Optional[ExtractionQueue] = None


def get_extraction_queue() -> ExtractionQueue:
    """Lazy singleton. Safe to call from any context."""
    global _queue
    if _queue is None:
        _queue = ExtractionQueue(
            maxsize=int(os.getenv("TURN_FACT_QUEUE_MAXSIZE", "100"))
        )
    return _queue
