"""
Memory Consolidation Worker (P2.1) — nightly sleep-time consolidation.

Runs consolidate_workspace() off the user-facing turn. Enable via
MEMORY_CONSOLIDATION_ENABLED (default true); interval via
MEMORY_CONSOLIDATION_INTERVAL_HOURS (default 24).
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MemoryConsolidationWorker:
    def __init__(self, interval_hours: float = 24.0):
        self.interval_seconds = interval_hours * 3600
        self.running = False
        self.last_run: datetime | None = None
        self.last_report: dict | None = None

    async def run(self) -> None:
        self.running = True
        logger.info("MemoryConsolidationWorker: starting (interval %.1fh)", self.interval_seconds / 3600)
        while self.running:
            # First run shortly after boot (staggered), then nightly.
            delay = 120 if self.last_run is None else self.interval_seconds
            await asyncio.sleep(delay)
            if not self.running:
                break
            try:
                from core.memory_consolidator import consolidate_with_llm, consolidate_workspace

                workspaces = {"default"}
                reports = {}
                for ws in workspaces:
                    report = await asyncio.to_thread(consolidate_workspace, ws)
                    llm_report = await consolidate_with_llm(ws)
                    report["llm_review"] = llm_report
                    reports[ws] = report
                self.last_run = datetime.utcnow()
                self.last_report = reports
                logger.info("MemoryConsolidationWorker: %s", reports)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("MemoryConsolidationWorker cycle failed: %s", e)
                await asyncio.sleep(60)

    def stop(self) -> None:
        self.running = False
