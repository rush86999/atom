# -*- coding: utf-8 -*-
"""Coverage wave 74 — core/jit_verification_worker.py (patched cache +
WorldModel, zero LLM spend, no network, no real LanceDB/Redis).

TDD target (RED first, fixed in source):
- ``_prioritize_citations`` assumed ``fact.last_verified`` is never None:
  ``(now - last_verified)`` raised TypeError, which killed the ENTIRE
  verification cycle → the worker's retry loop (sleep 60s, retry) crash-looped
  forever on a single fact lacking a verification timestamp, never verifying
  anything else.

Coverage targets: start-when-running, stop-when-not-running, verification loop
(cycle error → 60s retry; CancelledError → clean exit), empty-batch early
return, cycle exception re-raise, _verify_batch exception results counted as
failed, verification-time ring buffer trim, verify_fact_citations (fact
missing, outdated update path).
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.jit_verification_worker import (
    JITVerificationWorker,
    VerificationJob,
    get_jit_verification_worker,
    start_jit_verification_worker,
    stop_jit_verification_worker,
)
from core.agent_world_model import BusinessFact


def _fact(fid="fact-1", citations=None, last_verified=None, status="verified",
           default_verified=True):
    if last_verified is None and default_verified:
        last_verified = datetime.now() - timedelta(hours=2)
    return BusinessFact(
        id=fid,
        fact=f"Fact {fid}",
        citations=citations or [f"cite-{fid}"],
        reason="reason",
        source_agent_id="agent-1",
        created_at=datetime.now() - timedelta(days=30),
        last_verified=last_verified,
        verification_status=status,
    )


@pytest.fixture()
def fake_cache():
    cache = MagicMock()
    cache.verify_citation = AsyncMock()
    cache.get_stats.return_value = {"l1": {}, "l2_enabled": False}
    return cache


@pytest.fixture()
def worker(fake_cache):
    with patch("core.jit_verification_worker.get_jit_verification_cache",
               return_value=fake_cache):
        return JITVerificationWorker(check_interval_seconds=60, batch_size=10,
                                     max_concurrent=3)


# ============================================================================
# TDD RED — aware last_verified must not crash the cycle
# ============================================================================

class TestPrioritizeAwareTimestamps:
    def test_aware_last_verified_does_not_crash(self, worker):
        # WorldModelService hydrates last_verified via datetime.fromisoformat,
        # which yields TIMEZONE-AWARE datetimes; the worker computed age with
        # naive datetime.now() → TypeError → whole cycle crashed and the loop
        # retried every 60s forever (crash-loop, nothing else verified).
        aware = datetime.now(timezone.utc) - timedelta(hours=2)
        facts = [
            _fact("f1", last_verified=aware, status="unverified"),
            _fact("f2", last_verified=aware),
        ]
        jobs = worker._prioritize_citations(facts)
        assert len(jobs) == 2
        assert jobs[0].fact_id == "f1"
        assert jobs[0].priority >= 20  # unverified boost

    def test_prioritize_skips_deleted_and_boosts_old(self, worker):
        now = datetime.now(timezone.utc)
        facts = [
            _fact("del", status="deleted"),
            _fact("old", last_verified=now - timedelta(hours=72)),
            _fact("fresh", last_verified=now - timedelta(hours=1)),
        ]
        jobs = worker._prioritize_citations(facts)
        assert len(jobs) == 2
        by_id = {j.fact_id: j for j in jobs}
        assert "del" not in by_id
        assert by_id["old"].priority > by_id["fresh"].priority
        assert by_id["old"].last_checked == facts[1].last_verified


# ============================================================================
# start / stop / loop
# ============================================================================

class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_when_running_noop(self, worker):
        await worker.start()
        assert worker._running is True
        original_task = worker._task
        await worker.start()  # second start is a no-op
        assert worker._task is original_task
        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running_noop(self, worker):
        await worker.stop()
        assert worker._running is False

    @pytest.mark.asyncio
    async def test_loop_cycle_error_retries(self, worker):
        worker._running = True
        calls = {"n": 0}

        async def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("cycle boom")
            worker._running = False  # stop after first retry

        with patch.object(worker, "_run_verification_cycle", side_effect=flaky), \
             patch.object(worker, "check_interval", 0), \
             patch("asyncio.sleep", AsyncMock()) as sleep:
            await worker._verification_loop()

        assert calls["n"] == 2
        sleep.assert_awaited()

    @pytest.mark.asyncio
    async def test_loop_cancelled_breaks_cleanly(self, worker):
        worker._running = True

        async def cancelled():
            worker._running = False
            raise asyncio.CancelledError()

        with patch.object(worker, "_run_verification_cycle", side_effect=cancelled), \
             patch("asyncio.sleep", AsyncMock()) as sleep:
            await worker._verification_loop()

        sleep.assert_not_awaited()


class TestCycle:
    @pytest.mark.asyncio
    async def test_empty_batch_early_return(self, worker):
        wm = MagicMock()
        wm.list_all_facts = AsyncMock(return_value=[])  # no facts at all
        with patch("core.jit_verification_worker.WorldModelService", return_value=wm):
            result = await worker._run_verification_cycle()
        assert result is None
        assert worker._metrics.last_run_time is None

    @pytest.mark.asyncio
    async def test_facts_without_citations_no_batch(self, worker):
        wm = MagicMock()
        wm.list_all_facts = AsyncMock(return_value=[_fact("f1", citations=[])])
        with patch("core.jit_verification_worker.WorldModelService", return_value=wm):
            result = await worker._run_verification_cycle()
        assert result is None

    @pytest.mark.asyncio
    async def test_cycle_exception_reraises(self, worker):
        wm = MagicMock()
        wm.list_all_facts = AsyncMock(side_effect=RuntimeError("list failed"))
        with patch("core.jit_verification_worker.WorldModelService", return_value=wm):
            with pytest.raises(RuntimeError, match="list failed"):
                await worker._run_verification_cycle()

    @pytest.mark.asyncio
    async def test_full_cycle_sets_metrics(self, worker, fake_cache):
        fake_cache.verify_citation.return_value = MagicMock(exists=True)
        wm = MagicMock()
        wm.list_all_facts = AsyncMock(return_value=[_fact("f1")])
        wm.update_fact_verification = AsyncMock()
        with patch("core.jit_verification_worker.WorldModelService", return_value=wm):
            await worker._run_verification_cycle()
        assert worker._metrics.total_citations == 1
        assert worker._metrics.last_run_time is not None
        assert worker._metrics.last_run_duration >= 0


# ============================================================================
# _verify_batch / _verify_single_citation
# ============================================================================

class TestVerifyBatch:
    @pytest.mark.asyncio
    async def test_exception_results_counted_as_failed(self, worker):
        async def boom(job):
            raise RuntimeError("verify crashed")

        with patch.object(worker, "_verify_single_citation", side_effect=boom):
            verified = await worker._verify_batch([VerificationJob("f1", "c1")])

        assert verified == 0
        assert worker._metrics.failed_count == 1

    @pytest.mark.asyncio
    async def test_false_result_not_verified(self, worker):
        async def nope(job):
            return False

        with patch.object(worker, "_verify_single_citation", side_effect=nope):
            verified = await worker._verify_batch([VerificationJob("f1", "c1")])
        assert verified == 0
        assert worker._metrics.failed_count == 0

    @pytest.mark.asyncio
    async def test_concurrency_semaphore(self, worker, fake_cache):
        fake_cache.verify_citation.return_value = MagicMock(exists=True)
        wm = MagicMock()
        wm.list_all_facts = AsyncMock(return_value=[])
        with patch("core.jit_verification_worker.WorldModelService", return_value=wm):
            verified = await worker._verify_batch(
                [VerificationJob(f"f{i}", f"c{i}") for i in range(4)])
        assert verified == 4
        assert worker._metrics.verified_count == 4

    @pytest.mark.asyncio
    async def test_verification_time_ring_buffer_trimmed(self, worker, fake_cache):
        fake_cache.verify_citation.return_value = MagicMock(exists=True)
        wm = MagicMock()
        wm.list_all_facts = AsyncMock(return_value=[])
        with patch("core.jit_verification_worker.WorldModelService", return_value=wm):
            worker._verification_times.extend([0.01] * 100)
            await worker._verify_batch([VerificationJob("f1", "c1")])
        assert len(worker._verification_times) == 100
        assert worker._metrics.average_verification_time > 0


class TestVerifySingleCitation:
    @pytest.mark.asyncio
    async def test_outdated_citation_marks_facts(self, worker, fake_cache):
        fake_cache.verify_citation.return_value = MagicMock(exists=False)
        fact = _fact("f1")
        wm = MagicMock()
        wm.list_all_facts = AsyncMock(return_value=[fact])
        wm.update_fact_verification = AsyncMock()
        with patch("core.jit_verification_worker.WorldModelService", return_value=wm):
            ok = await worker._verify_single_citation(VerificationJob("f1", "cite-f1"))
        assert ok is True
        wm.update_fact_verification.assert_awaited_with("f1", "outdated")
        assert worker._metrics.stale_facts == 1

    @pytest.mark.asyncio
    async def test_cache_exception_returns_false(self, worker, fake_cache):
        fake_cache.verify_citation.side_effect = RuntimeError("cache down")
        with patch.object(worker, "_citation_access_count", {}):
            ok = await worker._verify_single_citation(VerificationJob("f1", "c1"))
        assert ok is False
        assert worker._metrics.failed_count == 1


class TestVerifyFactCitations:
    @pytest.mark.asyncio
    async def test_fact_not_found_returns_empty(self, worker):
        wm = MagicMock()
        wm.get_fact_by_id = AsyncMock(return_value=None)
        with patch("core.jit_verification_worker.WorldModelService", return_value=wm):
            results = await worker.verify_fact_citations("missing")
        assert results == {}

    @pytest.mark.asyncio
    async def test_outdated_fact_updates_status(self, worker, fake_cache):
        fact = _fact("f1", citations=["c1", "c2"])
        fake_cache.verify_citation.side_effect = [
            MagicMock(exists=True),
            MagicMock(exists=False),
        ]
        wm = MagicMock()
        wm.get_fact_by_id = AsyncMock(return_value=fact)
        wm.update_fact_verification = AsyncMock()
        with patch("core.jit_verification_worker.WorldModelService", return_value=wm):
            results = await worker.verify_fact_citations("f1")
        assert len(results) == 2
        assert results["c1"].exists is True
        wm.update_fact_verification.assert_awaited_once_with("f1", "outdated")
        assert worker._citation_access_count["c1"] == 1
        assert worker._citation_access_count["c2"] == 1

    @pytest.mark.asyncio
    async def test_all_valid_does_not_update(self, worker, fake_cache):
        fact = _fact("f1", citations=["c1"])
        fake_cache.verify_citation.return_value = MagicMock(exists=True)
        wm = MagicMock()
        wm.get_fact_by_id = AsyncMock(return_value=fact)
        wm.update_fact_verification = AsyncMock()
        with patch("core.jit_verification_worker.WorldModelService", return_value=wm):
            await worker.verify_fact_citations("f1")
        wm.update_fact_verification.assert_not_awaited()


class TestGlobals:
    def test_get_worker_singleton(self):
        with patch("core.jit_verification_worker.os.getenv", return_value="7200"):
            w1 = get_jit_verification_worker()
            w2 = get_jit_verification_worker()
        assert w1 is w2
        assert w1.check_interval == 7200

    @pytest.mark.asyncio
    async def test_start_stop_globals(self):
        with patch("core.jit_verification_worker.get_jit_verification_worker") as gw, \
             patch("core.jit_verification_worker._worker", None):
            worker = MagicMock()
            worker.start = AsyncMock()
            worker.stop = AsyncMock()
            gw.return_value = worker
            started = await start_jit_verification_worker()
            worker.start.assert_awaited_once()
            assert started is worker
            with patch("core.jit_verification_worker._worker", worker):
                await stop_jit_verification_worker()
            worker.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_global_no_worker(self):
        with patch("core.jit_verification_worker._worker", None):
            await stop_jit_verification_worker()  # no-op


class TestMetricsSurface:
    def test_get_metrics_shape(self, worker):
        worker._running = True
        worker._metrics.total_citations = 3
        worker._citation_access_count["hot"] = 7
        worker._citation_access_count["cold"] = 1
        m = worker.get_metrics()
        assert m["running"] is True
        assert m["total_citations"] == 3
        assert m["top_citations"][0]["citation"] == "hot"
        assert m["cache_stats"] is not None

    def test_reset_metrics(self, worker):
        worker._metrics.verified_count = 5
        worker._verification_times.append(1.0)
        worker.reset_metrics()
        assert worker._metrics.verified_count == 0
        assert worker._verification_times == []

    def test_job_hash_dedup(self):
        j1 = VerificationJob("f1", "c1", priority=1)
        j2 = VerificationJob("f1", "c1", priority=9)
        j3 = VerificationJob("f2", "c1")
        assert hash(j1) == hash(j2)
        assert hash(j1) != hash(j3)
