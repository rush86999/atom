"""
JIT Verification Background Worker

Periodic background worker that proactively verifies business facts
and policy citations to keep the cache warm and ensure compliance.

Features:
- Periodic verification of all citations (configurable interval)
- Priority-based verification (frequently accessed first)
- Automatic cache updates
- Verification status tracking
- Health monitoring and metrics

Usage:
    worker = JITVerificationWorker()
    await worker.start()
    # ... worker runs in background ...
    await worker.stop()
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
import os

from core.jit_verification_cache import get_jit_verification_cache, CitationVerificationResult
from core.agent_world_model import WorldModelService, BusinessFact

logger = logging.getLogger(__name__)


@dataclass
class VerificationJob:
    """A single verification job"""
    fact_id: str
    citation: str
    priority: int = 0  # Higher = more important
    last_checked: Optional[datetime] = None
    check_count: int = 0

    def __hash__(self):
        return hash((self.fact_id, self.citation))


@dataclass
class WorkerMetrics:
    """Metrics for verification worker"""
    total_citations: int = 0
    verified_count: int = 0
    failed_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    last_run_time: Optional[datetime] = None
    last_run_duration: float = 0.0
    average_verification_time: float = 0.0
    stale_facts: int = 0  # Facts with outdated citations
    outdated_facts: int = 0  # Facts with missing citations


class JITVerificationWorker:
    """
    Background worker for proactive citation verification.

    Runs periodically to:
    1. Fetch all business facts with citations
    2. Verify citations (with cache checking)
    3. Update verification status in WorldModel
    4. Update JIT cache
    5. Track metrics
    """

    def __init__(
        self,
        workspace_id: str = "default",
        check_interval_seconds: int = 3600,  # 1 hour default
        batch_size: int = 50,
        max_concurrent: int = 10
    ):
        """
        Initialize verification worker.

        Args:
            workspace_id: Workspace to verify facts for
            check_interval_seconds: How often to run verification (default 1 hour)
            batch_size: How many citations to verify per run
            max_concurrent: Max parallel verifications
        """
        self.workspace_id = workspace_id
        self.check_interval = check_interval_seconds
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._cache = get_jit_verification_cache()

        # Metrics tracking
        self._metrics = WorkerMetrics()
        self._verification_times: List[float] = []

        # Priority tracking (access count per citation)
        self._citation_access_count: Dict[str, int] = defaultdict(int)

    async def start(self):
        """Start background verification worker"""
        if self._running:
            logger.warning("Verification worker already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._verification_loop())
        logger.info(f"JIT Verification Worker started (interval: {self.check_interval}s)")

    async def stop(self):
        """Stop background verification worker"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("JIT Verification Worker stopped")

    async def _verification_loop(self):
        """Main verification loop"""
        while self._running:
            try:
                await self._run_verification_cycle()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Verification cycle error: {e}")
                await asyncio.sleep(60)  # Wait before retry

    async def _run_verification_cycle(self):
        """Run a single verification cycle"""
        start_time = datetime.now()
        logger.info("Starting verification cycle")

        try:
            # 1. Fetch all business facts
            wm = WorldModelService(self.workspace_id)
            facts = await wm.list_all_facts(limit=10000)  # Get all facts

            # 2. Extract unique citations with priority
            jobs = self._prioritize_citations(facts)
            self._metrics.total_citations = len(jobs)

            # 3. Select batch to verify (highest priority first)
            batch = sorted(jobs, key=lambda j: j.priority, reverse=True)[:self.batch_size]

            if not batch:
                logger.info("No citations to verify")
                return

            # 4. Verify batch with concurrency control
            verified = await self._verify_batch(batch)

            # 5. Update metrics
            duration = (datetime.now() - start_time).total_seconds()
            self._metrics.last_run_time = datetime.now()
            self._metrics.last_run_duration = duration

            logger.info(
                f"Verification cycle completed: "
                f"{verified}/{len(batch)} citations verified in {duration:.2f}s"
            )

        except Exception as e:
            logger.error(f"Verification cycle failed: {e}")
            raise

    def _prioritize_citations(self, facts: List[BusinessFact]) -> List[VerificationJob]:
        """
        Prioritize citations based on access patterns and staleness.

        Priority factors:
        - Access frequency (higher = more important)
        - Time since last verification (older = more important)
        - Verification status (unverified > verified > outdated)
        """
        jobs = []
        now = datetime.now()

        for fact in facts:
            # Skip deleted facts
            if fact.verification_status == "deleted":
                continue

            for citation in fact.citations:
                # Calculate priority
                access_count = self._citation_access_count.get(citation, 0)
                age_hours = (now - fact.last_verified).total_seconds() / 3600

                # Base priority from access count
                priority = access_count * 10

                # Boost old citations
                if age_hours > 24:  # More than a day old
                    priority += int(age_hours / 24) * 5

                # Boost unverified citations
                if fact.verification_status == "unverified":
                    priority += 20

                jobs.append(VerificationJob(
                    fact_id=fact.id,
                    citation=citation,
                    priority=priority,
                    last_checked=fact.last_verified,
                    check_count=0
                ))

        return jobs

    async def _verify_batch(self, jobs: List[VerificationJob]) -> int:
        """
        Verify a batch of citations with concurrency control.

        Returns:
            Number of successfully verified citations
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)
        verified_count = 0

        async def verify_with_semaphore(job: VerificationJob) -> bool:
            async with semaphore:
                return await self._verify_single_citation(job)

        # Run verifications in parallel with semaphore limiting
        tasks = [verify_with_semaphore(job) for job in jobs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Verification failed for {jobs[i].citation}: {result}")
                self._metrics.failed_count += 1
            elif result:
                verified_count += 1

        return verified_count

    async def _verify_single_citation(self, job: VerificationJob) -> bool:
        """
        Verify a single citation and update all dependent facts.

        Returns:
            True if verification succeeded, False otherwise
        """
        start = datetime.now()

        try:
            # Verify citation (uses cache automatically)
            result = await self._cache.verify_citation(job.citation)

            # Track timing
            duration = (datetime.now() - start).total_seconds()
            self._verification_times.append(duration)
            if len(self._verification_times) > 100:
                self._verification_times.pop(0)
            self._metrics.average_verification_time = sum(self._verification_times) / len(self._verification_times)

            # Update access count for priority
            self._citation_access_count[job.citation] += 1

            # Update all facts that use this citation
            wm = WorldModelService(self.workspace_id)
            facts = await wm.list_all_facts(limit=10000)

            updated_count = 0
            for fact in facts:
                if job.citation in fact.citations:
                    # Update verification status
                    new_status = "verified" if result.exists else "outdated"
                    await wm.update_fact_verification(fact.id, new_status)
                    updated_count += 1

            # Update metrics
            if result.exists:
                self._metrics.verified_count += 1
                logger.debug(f"Citation verified: {job.citation} (updated {updated_count} facts)")
            else:
                self._metrics.stale_facts += updated_count
                logger.warning(f"Citation outdated: {job.citation} (marked {updated_count} facts as outdated)")

            return True

        except Exception as e:
            logger.error(f"Failed to verify citation {job.citation}: {e}")
            self._metrics.failed_count += 1
            return False

    async def verify_fact_citations(self, fact_id: str) -> Dict[str, CitationVerificationResult]:
        """
        Verify all citations for a specific fact.

        Args:
            fact_id: ID of the fact to verify

        Returns:
            Dictionary mapping citation to verification result
        """
        wm = WorldModelService(self.workspace_id)
        fact = await wm.get_fact_by_id(fact_id)

        if not fact:
            logger.warning(f"Fact {fact_id} not found")
            return {}

        # Verify all citations
        results = {}
        for citation in fact.citations:
            result = await self._cache.verify_citation(citation, force_refresh=True)
            results[citation] = result

            # Update fact status
            if not result.exists:
                await wm.update_fact_verification(fact_id, "outdated")

        # Update access counts
        for citation in fact.citations:
            self._citation_access_count[citation] += 1

        return results

    def get_metrics(self) -> Dict[str, Any]:
        """Get current worker metrics"""
        return {
            "running": self._running,
            "total_citations": self._metrics.total_citations,
            "verified_count": self._metrics.verified_count,
            "failed_count": self._metrics.failed_count,
            "stale_facts": self._metrics.stale_facts,
            "outdated_facts": self._metrics.outdated_facts,
            "last_run_time": self._metrics.last_run_time.isoformat() if self._metrics.last_run_time else None,
            "last_run_duration": self._metrics.last_run_duration,
            "average_verification_time": self._metrics.average_verification_time,
            "cache_stats": self._cache.get_stats(),
            "top_citations": [
                {"citation": c, "access_count": count}
                for c, count in sorted(
                    self._citation_access_count.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            ]
        }

    def reset_metrics(self):
        """Reset metrics counters"""
        self._metrics = WorkerMetrics()
        self._verification_times.clear()


# Global worker instance
_worker: Optional[JITVerificationWorker] = None


def get_jit_verification_worker() -> JITVerificationWorker:
    """Get global JIT verification worker instance"""
    global _worker
    if _worker is None:
        interval = int(os.getenv("JIT_VERIFICATION_INTERVAL_SECONDS", "3600"))
        _worker = JITVerificationWorker(check_interval_seconds=interval)
    return _worker


async def start_jit_verification_worker():
    """Start the global JIT verification worker"""
    worker = get_jit_verification_worker()
    await worker.start()
    return worker


async def stop_jit_verification_worker():
    """Stop the global JIT verification worker"""
    global _worker
    if _worker:
        await _worker.stop()
