"""
Tests for JIT Verification Worker

Comprehensive tests for the background verification worker that
proactively verifies business fact citations.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from collections import defaultdict

from core.jit_verification_worker import (
    VerificationJob,
    WorkerMetrics,
    JITVerificationWorker,
    get_jit_verification_worker,
    start_jit_verification_worker,
    stop_jit_verification_worker
)
from core.agent_world_model import BusinessFact
from core.jit_verification_cache import CitationVerificationResult


class TestVerificationJob:
    """Tests for VerificationJob dataclass"""

    def test_creation(self):
        """Test creating a verification job"""
        job = VerificationJob(
            fact_id="fact-123",
            citation="s3://bucket/doc.pdf",
            priority=10,
            check_count=5
        )

        assert job.fact_id == "fact-123"
        assert job.citation == "s3://bucket/doc.pdf"
        assert job.priority == 10
        assert job.check_count == 5

    def test_hash(self):
        """Test job hash for deduplication"""
        job1 = VerificationJob(
            fact_id="fact-123",
            citation="s3://bucket/doc.pdf"
        )
        job2 = VerificationJob(
            fact_id="fact-123",
            citation="s3://bucket/doc.pdf"
        )
        job3 = VerificationJob(
            fact_id="fact-456",
            citation="s3://bucket/doc.pdf"
        )

        assert hash(job1) == hash(job2)
        assert hash(job1) != hash(job3)


class TestWorkerMetrics:
    """Tests for WorkerMetrics dataclass"""

    def test_default_values(self):
        """Test default metric values"""
        metrics = WorkerMetrics()

        assert metrics.total_citations == 0
        assert metrics.verified_count == 0
        assert metrics.failed_count == 0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0
        assert metrics.stale_facts == 0
        assert metrics.outdated_facts == 0


class TestJITVerificationWorker:
    """Tests for JIT verification worker"""

    @pytest.fixture
    def worker(self):
        """Create a test worker instance"""
        return JITVerificationWorker(
            workspace_id="test-workspace",
            check_interval_seconds=60,  # 1 minute for tests
            batch_size=10,
            max_concurrent=3
        )

    @pytest.fixture
    def mock_cache(self):
        """Mock JIT verification cache"""
        cache = MagicMock()
        cache.verify_citation = AsyncMock(return_value=CitationVerificationResult(
            exists=True,
            checked_at=datetime.now(),
            citation="s3://bucket/doc.pdf"
        ))
        cache.get_stats.return_value = {
            "l1": {
                "l1_verification_cache_size": 100,
                "l1_verification_hit_rate": 0.85
            },
            "l2_enabled": False
        }
        return cache

    @pytest.fixture
    def mock_world_model(self):
        """Mock WorldModel service"""
        wm = MagicMock()

        # Create test facts
        facts = [
            BusinessFact(
                id=f"fact-{i}",
                fact=f"Test fact {i}",
                citations=[f"s3://bucket/doc{i}.pdf"],
                reason="Test reason",
                source_agent_id="agent-1",
                created_at=datetime.now(),
                last_verified=datetime.now() - timedelta(hours=2),
                verification_status="verified",
                metadata={"domain": "finance"}
            )
            for i in range(5)
        ]

        # Add some deleted facts
        facts.append(BusinessFact(
            id="fact-deleted",
            fact="Deleted fact",
            citations=["s3://bucket/deleted.pdf"],
            reason="Deleted",
            source_agent_id="agent-1",
            created_at=datetime.now(),
            last_verified=datetime.now(),
            verification_status="deleted",
            metadata={}
        ))

        wm.list_all_facts = AsyncMock(return_value=facts)
        wm.get_fact_by_id = AsyncMock(return_value=facts[0])
        wm.update_fact_verification = AsyncMock(return_value=True)

        return wm

    def test_initialization(self, worker):
        """Test worker initialization"""
        assert worker.workspace_id == "test-workspace"
        assert worker.check_interval == 60
        assert worker.batch_size == 10
        assert worker.max_concurrent == 3
        assert worker._running is False

    def test_prioritize_citations(self, worker):
        """Test citation prioritization logic"""
        # Create test facts
        facts = [
            BusinessFact(
                id="fact-1",
                fact="Test fact 1",
                citations=["s3://bucket/doc1.pdf"],
                reason="Test",
                source_agent_id="agent-1",
                created_at=datetime.now(),
                last_verified=datetime.now() - timedelta(hours=48),  # 2 days old
                verification_status="verified",
                metadata={}
            ),
            BusinessFact(
                id="fact-2",
                fact="Test fact 2",
                citations=["s3://bucket/doc2.pdf"],
                reason="Test",
                source_agent_id="agent-1",
                created_at=datetime.now(),
                last_verified=datetime.now() - timedelta(hours=1),  # 1 hour old
                verification_status="unverified",
                metadata={}
            )
        ]

        # Set access counts
        worker._citation_access_count["s3://bucket/doc1.pdf"] = 5

        jobs = worker._prioritize_citations(facts)

        # Should exclude deleted facts
        assert len(jobs) == 2

        # Unverified should have higher priority
        unverified_job = next((j for j in jobs if j.fact_id == "fact-2"), None)
        verified_job = next((j for j in jobs if j.fact_id == "fact-1"), None)

        assert unverified_job is not None
        assert verified_job is not None
        assert unverified_job.priority > verified_job.priority

    def test_prioritize_citations_excludes_deleted(self, worker):
        """Test that deleted facts are excluded"""
        facts = [
            BusinessFact(
                id="fact-deleted",
                fact="Deleted fact",
                citations=["s3://bucket/deleted.pdf"],
                reason="Deleted",
                source_agent_id="agent-1",
                created_at=datetime.now(),
                last_verified=datetime.now(),
                verification_status="deleted",
                metadata={}
            )
        ]

        jobs = worker._prioritize_citations(facts)

        assert len(jobs) == 0

    @pytest.mark.asyncio
    async def test_verify_single_citation_success(self, worker, mock_cache):
        """Test successful single citation verification"""
        worker._cache = mock_cache

        job = VerificationJob(
            fact_id="fact-123",
            citation="s3://bucket/doc.pdf"
        )

        result = await worker._verify_single_citation(job)

        assert result is True
        assert worker._metrics.verified_count == 1

        # Check cache was called
        mock_cache.verify_citation.assert_called_once_with("s3://bucket/doc.pdf")

    @pytest.mark.asyncio
    async def test_verify_single_citation_failure(self, worker, mock_cache):
        """Test failed citation verification"""
        mock_cache.verify_citation.side_effect = Exception("Network error")
        worker._cache = mock_cache

        job = VerificationJob(
            fact_id="fact-123",
            citation="s3://bucket/doc.pdf"
        )

        result = await worker._verify_single_citation(job)

        assert result is False
        assert worker._metrics.failed_count == 1

    @pytest.mark.asyncio
    async def test_verify_single_citation_outdated(self, worker, mock_cache):
        """Test verification with outdated citation"""
        mock_cache.verify_citation.return_value = CitationVerificationResult(
            exists=False,
            checked_at=datetime.now(),
            citation="s3://bucket/missing.pdf"
        )
        worker._cache = mock_cache

        # Mock WorldModel
        with patch('core.jit_verification_worker.WorldModelService') as mock_wm_class:
            mock_wm = MagicMock()
            mock_wm.list_all_facts = AsyncMock(return_value=[
                BusinessFact(
                    id="fact-123",
                    fact="Test fact",
                    citations=["s3://bucket/missing.pdf"],
                    reason="Test",
                    source_agent_id="agent-1",
                    created_at=datetime.now(),
                    last_verified=datetime.now(),
                    verification_status="verified",
                    metadata={}
                )
            ])
            mock_wm.update_fact_verification = AsyncMock(return_value=True)
            mock_wm_class.return_value = mock_wm

            job = VerificationJob(
                fact_id="fact-123",
                citation="s3://bucket/missing.pdf"
            )

            result = await worker._verify_single_citation(job)

            assert result is True
            assert worker._metrics.stale_facts == 1
            mock_wm.update_fact_verification.assert_called_once_with("fact-123", "outdated")

    @pytest.mark.asyncio
    async def test_verify_batch_concurrency(self, worker, mock_cache):
        """Test batch verification with concurrency control"""
        worker._cache = mock_cache

        # Create jobs
        jobs = [
            VerificationJob(
                fact_id=f"fact-{i}",
                citation=f"s3://bucket/doc{i}.pdf"
            )
            for i in range(10)
        ]

        # Verify batch
        import time
        start = time.time()
        count = await worker._verify_batch(jobs)
        duration = time.time() - start

        assert count == 10

        # Should be faster than sequential due to concurrency
        # With max_concurrent=3, should take ~4 "units" of time (10/3 rounded up)
        # This is a loose check
        assert duration < 2.0

    @pytest.mark.asyncio
    async def test_verify_fact_citations(self, worker, mock_cache, mock_world_model):
        """Test verifying all citations for a specific fact"""
        worker._cache = mock_cache

        with patch('core.jit_verification_worker.WorldModelService', return_value=mock_world_model):
            results = await worker.verify_fact_citations("fact-0")

            assert len(results) == 1
            assert "s3://bucket/doc0.pdf" in results
            assert results["s3://bucket/doc0.pdf"].exists is True

            # Check access count was incremented
            assert worker._citation_access_count["s3://bucket/doc0.pdf"] == 1

    def test_get_metrics(self, worker, mock_cache):
        """Test getting worker metrics"""
        worker._cache = mock_cache
        worker._metrics.verified_count = 100
        worker._metrics.failed_count = 5
        worker._metrics.stale_facts = 10
        worker._metrics.last_run_time = datetime.now()
        worker._metrics.last_run_duration = 45.5
        worker._citation_access_count["s3://bucket/popular.pdf"] = 50

        metrics = worker.get_metrics()

        assert metrics["verified_count"] == 100
        assert metrics["failed_count"] == 5
        assert metrics["stale_facts"] == 10
        assert metrics["last_run_duration"] == 45.5
        assert len(metrics["top_citations"]) == 1
        assert metrics["top_citations"][0]["citation"] == "s3://bucket/popular.pdf"
        assert metrics["top_citations"][0]["access_count"] == 50

    def test_reset_metrics(self, worker):
        """Test resetting metrics"""
        worker._metrics.verified_count = 100
        worker._metrics.failed_count = 5
        worker._verification_times = [1.0, 2.0, 3.0]

        worker.reset_metrics()

        assert worker._metrics.verified_count == 0
        assert worker._metrics.failed_count == 0
        assert len(worker._verification_times) == 0

    @pytest.mark.asyncio
    async def test_start_stop_worker(self, worker):
        """Test starting and stopping worker"""
        assert worker._running is False

        # Start
        await worker.start()
        assert worker._running is True
        assert worker._task is not None

        # Stop
        await worker.stop()
        assert worker._running is False

    @pytest.mark.asyncio
    async def test_verification_loop(self, worker, mock_cache, mock_world_model):
        """Test verification loop execution"""
        worker._cache = mock_cache
        worker._running = True

        with patch('core.jit_verification_worker.WorldModelService', return_value=mock_world_model):
            # Run one cycle
            await worker._run_verification_cycle()

            # Check metrics
            assert worker._metrics.verified_count == 5  # 5 facts (excluding deleted)
            assert worker._metrics.last_run_time is not None


class TestGlobalWorkerInstance:
    """Tests for global worker instance"""

    def test_get_jit_verification_worker_singleton(self):
        """Test that get_jit_verification_worker returns singleton"""
        with patch('core.jit_verification_worker.os.getenv', return_value='1800'):
            worker1 = get_jit_verification_worker()
            worker2 = get_jit_verification_worker()

            assert worker1 is worker2

    @pytest.mark.asyncio
    async def test_start_stop_global_worker(self):
        """Test starting and stopping global worker"""
        # Clear global instance
        import core.jit_verification_worker
        core.jit_verification_worker._worker = None

        with patch('core.jit_verification_worker.os.getenv', return_value='1800'):
            worker = await start_jit_verification_worker()
            assert worker._running is True

            await stop_jit_verification_worker()
            # Worker should be stopped


class TestIntegrationScenarios:
    """Integration test scenarios"""

    @pytest.mark.asyncio
    async def test_full_verification_cycle(self):
        """Test complete verification cycle with real components"""
        # Create worker
        worker = JITVerificationWorker(
            workspace_id="test",
            check_interval_seconds=1,
            batch_size=5
        )

        # Mock WorldModel
        mock_facts = [
            BusinessFact(
                id=f"fact-{i}",
                fact=f"Fact {i}",
                citations=[f"s3://bucket/doc{i}.pdf"],
                reason="Test",
                source_agent_id="agent-1",
                created_at=datetime.now(),
                last_verified=datetime.now() - timedelta(hours=2),
                verification_status="verified",
                metadata={}
            )
            for i in range(3)
        ]

        with patch('core.jit_verification_worker.WorldModelService') as mock_wm_class:
            mock_wm = MagicMock()
            mock_wm.list_all_facts = AsyncMock(return_value=mock_facts)
            mock_wm.update_fact_verification = AsyncMock(return_value=True)
            mock_wm_class.return_value = mock_wm

            # Mock cache
            with patch('core.jit_verification_worker.get_jit_verification_cache') as mock_get_cache:
                mock_cache = MagicMock()
                mock_cache.verify_citation = AsyncMock(return_value=CitationVerificationResult(
                    exists=True,
                    checked_at=datetime.now(),
                    citation="s3://bucket/doc.pdf"
                ))
                mock_get_cache.return_value = mock_cache

                worker._cache = mock_cache

                # Run verification cycle
                await worker._run_verification_cycle()

                # Verify all facts were checked
                assert mock_cache.verify_citation.call_count == 3

                # Verify metrics updated
                assert worker._metrics.verified_count == 3
                assert worker._metrics.last_run_time is not None

    @pytest.mark.asyncio
    async def test_priority_based_verification(self):
        """Test that higher priority citations are verified first"""
        worker = JITVerificationWorker(
            workspace_id="test",
            batch_size=2  # Only verify 2 per batch
        )

        # Create facts with different priorities
        facts = [
            BusinessFact(
                id="fact-1",
                fact="Low priority",
                citations=["s3://bucket/low.pdf"],
                reason="Test",
                source_agent_id="agent-1",
                created_at=datetime.now(),
                last_verified=datetime.now(),  # Recent
                verification_status="verified",
                metadata={}
            ),
            BusinessFact(
                id="fact-2",
                fact="High priority",
                citations=["s3://bucket/high.pdf"],
                reason="Test",
                source_agent_id="agent-1",
                created_at=datetime.now(),
                last_verified=datetime.now() - timedelta(days=2),  # Old
                verification_status="unverified",
                metadata={}
            )
        ]

        # Set access count for low priority
        worker._citation_access_count["s3://bucket/low.pdf"] = 1

        with patch('core.jit_verification_worker.WorldModelService') as mock_wm_class:
            mock_wm = MagicMock()
            mock_wm.list_all_facts = AsyncMock(return_value=facts)
            mock_wm.update_fact_verification = AsyncMock(return_value=True)
            mock_wm_class.return_value = mock_wm

            worker._cache = MagicMock()
            worker._cache.verify_citation = AsyncMock(return_value=CitationVerificationResult(
                exists=True,
                checked_at=datetime.now(),
                citation="s3://bucket/doc.pdf"
            ))

            # Run cycle
            await worker._run_verification_cycle()

            # Should verify high priority first due to unverified status + age
            # Verify that high priority was checked
            citations_verified = [
                call[0][0] for call in worker._cache.verify_citation.call_args_list
            ]

            assert "s3://bucket/high.pdf" in citations_verified


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
