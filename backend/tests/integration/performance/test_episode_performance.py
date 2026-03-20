"""
Episode Segmentation Performance Benchmarks

Measures execution time for EpisodeSegmentationService critical paths using pytest-benchmark.
These tests establish baseline performance and enable regression detection through historical tracking.

Target Metrics:
- Time gap detection <10ms P50
- Topic change detection <50ms P50 (requires embedding comparison)
- Episode creation (10 messages) <200ms P50
- Episode creation (50 messages) <500ms P50
- Episode segmentation <100ms P50

Reference: Phase 208 Plan 03 - Performance Benchmarking
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import MagicMock, AsyncMock, patch

from core.models import ChatMessage, ChatSession, AgentExecution, AgentFeedback, CanvasAudit

# Try to import pytest_benchmark, but don't fail if not available
try:
    import pytest_benchmark
    BENCHMARK_AVAILABLE = True
except ImportError:
    BENCHMARK_AVAILABLE = False

# Skip tests if pytest-benchmark not available
pytestmark = pytest.mark.skipif(
    not BENCHMARK_AVAILABLE,
    reason="pytest-benchmark plugin not installed. Install with: pip install pytest-benchmark"
)


class TestEpisodePerformance:
    """Test episode segmentation performance benchmarks."""

    @pytest.fixture
    def sample_messages(self):
        """Create sample messages for testing."""
        base_time = datetime.utcnow()
        messages = []

        for i in range(10):
            msg = ChatMessage(
                id=f"msg_{i}",
                conversation_id=f"session_{i}",
                role="user" if i % 2 == 0 else "assistant",
                content=f"Test message {i} with some content for testing",
                created_at=base_time + timedelta(minutes=i * 5),
                agent_id=f"agent_{i}"
            )
            messages.append(msg)

        return messages

    @pytest.fixture
    def messages_with_time_gap(self):
        """Create messages with 2-hour gap."""
        base_time = datetime.utcnow()
        messages = []

        # First message
        messages.append(ChatMessage(
            id="msg_0",
            conversation_id="session_1",
            role="user",
            content="First message",
            created_at=base_time,
            agent_id="agent_1"
        ))

        # Second message 2 hours later
        messages.append(ChatMessage(
            id="msg_1",
            conversation_id="session_1",
            role="assistant",
            content="Second message after gap",
            created_at=base_time + timedelta(hours=2),
            agent_id="agent_1"
        ))

        return messages

    @pytest.fixture
    def messages_with_topic_change(self):
        """Create messages with topic shift."""
        base_time = datetime.utcnow()
        messages = []

        # First 10 messages about topic A
        for i in range(10):
            messages.append(ChatMessage(
                id=f"msg_{i}",
                conversation_id="session_1",
                role="user" if i % 2 == 0 else "assistant",
                content=f"Discussion about accounting and financial reports {i}",
                created_at=base_time + timedelta(minutes=i),
                agent_id="agent_1"
            ))

        # Next 10 messages about topic B
        for i in range(10, 20):
            messages.append(ChatMessage(
                id=f"msg_{i}",
                conversation_id="session_1",
                role="user" if i % 2 == 0 else "assistant",
                content=f"Discussion about engineering and software development {i}",
                created_at=base_time + timedelta(minutes=i),
                agent_id="agent_1"
            ))

        return messages

    @pytest.mark.benchmark(group="episode-detection")
    def test_should_create_new_episode_time_gap(self, benchmark, messages_with_time_gap):
        """
        Benchmark time gap detection.

        Target: <10ms P50 (time comparison is fast)
        Input: 2 messages with 2-hour gap
        Verify: Returns gap index
        """
        from core.episode_segmentation_service import EpisodeBoundaryDetector, TIME_GAP_THRESHOLD_MINUTES

        # Mock LanceDB handler (not needed for time gap detection)
        mock_db = MagicMock()

        detector = EpisodeBoundaryDetector(mock_db)

        def detect_gap():
            gaps = detector.detect_time_gap(messages_with_time_gap)
            # Should detect gap at index 1 (2-hour gap > 30-min threshold)
            assert len(gaps) > 0
            assert 1 in gaps
            return gaps

        result = benchmark(detect_gap)
        assert len(result) > 0

    @pytest.mark.benchmark(group="episode-detection")
    def test_should_create_new_episode_topic_change(self, benchmark, messages_with_topic_change):
        """
        Benchmark topic change detection with mocked embeddings.

        Target: <50ms P50 (requires similarity comparison)
        Input: 20 messages with topic shift
        Verify: Returns change indices
        Mock: LLM embedding call (return fixed vector)
        """
        from core.episode_segmentation_service import EpisodeBoundaryDetector

        # Mock LanceDB handler with embedding
        mock_db = MagicMock()
        # Return different embeddings for different topics (low similarity)
        mock_db.embed_text = MagicMock(side_effect=lambda text: [0.1] * 384 if "accounting" in text else [0.9] * 384)

        detector = EpisodeBoundaryDetector(mock_db)

        def detect_topic_change():
            changes = detector.detect_topic_changes(messages_with_topic_change)
            # Should detect topic change around index 10
            assert len(changes) > 0
            return changes

        result = benchmark(detect_topic_change)
        assert len(result) > 0

    @pytest.mark.benchmark(group="episode-detection")
    def test_cosine_similarity_calculation(self, benchmark):
        """
        Benchmark cosine similarity calculation (pure Python).

        Target: <1ms P50 (vector math is fast)
        Input: Two 384-dim vectors
        Verify: Returns similarity score
        """
        from core.episode_segmentation_service import EpisodeBoundaryDetector

        mock_db = MagicMock()
        detector = EpisodeBoundaryDetector(mock_db)

        vec1 = [0.1] * 384
        vec2 = [0.2] * 384

        def calculate_similarity():
            similarity = detector._cosine_similarity(vec1, vec2)
            assert 0.0 <= similarity <= 1.0
            return similarity

        result = benchmark(calculate_similarity)
        assert 0.0 <= result <= 1.0

    @pytest.mark.benchmark(group="episode-creation")
    def test_create_episode_10_messages(self, benchmark, sample_messages):
        """
        Benchmark episode creation with 10 messages.

        Target: <200ms P50 (includes summary generation)
        Input: Sample episode context with 10 messages
        Verify: Episode dict created
        Mock: LLM summary generation
        """
        # Mock database
        mock_db = MagicMock()
        mock_session = ChatSession(
            id="session_1",
            agent_id="agent_1",
            created_at=datetime.utcnow()
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_messages

        # Mock BYOK handler for summary generation
        mock_byok = MagicMock()
        mock_byok.generate_summary.return_value = "Test episode summary for benchmarking"

        # Mock LanceDB
        mock_lancedb = MagicMock()
        mock_lancedb.embed_text.return_value = [0.1] * 384

        with patch('core.episode_segmentation_service.get_lancedb_handler', return_value=mock_lancedb):
            from core.episode_segmentation_service import EpisodeSegmentationService

            service = EpisodeSegmentationService(mock_db, byok_handler=mock_byok)

            # Mock canvas and feedback context
            service._fetch_canvas_context = MagicMock(return_value=[])
            service._fetch_feedback_context = MagicMock(return_value=[])

            async def create_episode():
                episode = await service.create_episode_from_session(
                    session_id="session_1",
                    agent_id="agent_1",
                    force_create=True
                )
                assert episode is not None
                assert "id" in episode
                return episode

            # Run async benchmark
            result = benchmark(lambda: pytest.asyncio.run(create_episode()))
            assert result is not None

    @pytest.mark.benchmark(group="episode-creation")
    def test_create_episode_50_messages(self, benchmark):
        """
        Benchmark episode creation with 50 messages (large episode).

        Target: <500ms P50 (scales linearly)
        Input: Large episode context with 50 messages
        Verify: Episode dict created
        Mock: LLM summary generation
        """
        # Create 50 messages
        base_time = datetime.utcnow()
        messages = []

        for i in range(50):
            messages.append(ChatMessage(
                id=f"msg_{i}",
                conversation_id="session_1",
                role="user" if i % 2 == 0 else "assistant",
                content=f"Test message {i} with some content for large episode testing",
                created_at=base_time + timedelta(minutes=i),
                agent_id="agent_1"
            ))

        # Mock database
        mock_db = MagicMock()
        mock_session = ChatSession(
            id="session_1",
            agent_id="agent_1",
            created_at=datetime.utcnow()
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = messages

        # Mock BYOK handler
        mock_byok = MagicMock()
        mock_byok.generate_summary.return_value = "Test episode summary for large episode benchmarking"

        # Mock LanceDB
        mock_lancedb = MagicMock()
        mock_lancedb.embed_text.return_value = [0.1] * 384

        with patch('core.episode_segmentation_service.get_lancedb_handler', return_value=mock_lancedb):
            from core.episode_segmentation_service import EpisodeSegmentationService

            service = EpisodeSegmentationService(mock_db, byok_handler=mock_byok)

            # Mock canvas and feedback context
            service._fetch_canvas_context = MagicMock(return_value=[])
            service._fetch_feedback_context = MagicMock(return_value=[])

            async def create_episode():
                episode = await service.create_episode_from_session(
                    session_id="session_1",
                    agent_id="agent_1",
                    force_create=True
                )
                assert episode is not None
                assert "id" in episode
                return episode

            # Run async benchmark
            result = benchmark(lambda: pytest.asyncio.run(create_episode()))
            assert result is not None

    @pytest.mark.benchmark(group="episode-segmentation")
    def test_segment_episode_by_time(self, benchmark):
        """
        Benchmark segment episode by time gaps.

        Target: <100ms P50 (batch processing)
        Input: 50 messages with various time gaps
        Verify: Returns 3-5 episode segments
        """
        # Create 50 messages with time gaps every 10 messages
        base_time = datetime.utcnow()
        messages = []

        for i in range(50):
            # Add 30-min gap every 10 messages
            if i % 10 == 0:
                time_offset = i * 30
            else:
                time_offset = i * 2

            messages.append(ChatMessage(
                id=f"msg_{i}",
                conversation_id="session_1",
                role="user" if i % 2 == 0 else "assistant",
                content=f"Test message {i}",
                created_at=base_time + timedelta(minutes=time_offset),
                agent_id="agent_1"
            ))

        from core.episode_segmentation_service import EpisodeBoundaryDetector

        mock_db = MagicMock()
        detector = EpisodeBoundaryDetector(mock_db)

        def segment_by_time():
            gaps = detector.detect_time_gap(messages)
            # Should detect 4-5 gaps (every 10 messages)
            assert len(gaps) >= 4
            return gaps

        result = benchmark(segment_by_time)
        assert len(result) >= 4


class TestEpisodeEdgeCases:
    """Test edge cases and error handling performance."""

    @pytest.mark.benchmark(group="episode-detection")
    def test_empty_messages_list(self, benchmark):
        """
        Benchmark boundary detection with empty messages.

        Target: <1ms P50 (should be instant)
        Input: Empty message list
        Verify: Returns empty list (no errors)
        """
        from core.episode_segmentation_service import EpisodeBoundaryDetector

        mock_db = MagicMock()
        detector = EpisodeBoundaryDetector(mock_db)

        def detect_empty():
            gaps = detector.detect_time_gap([])
            assert gaps == []
            return gaps

        result = benchmark(detect_empty)
        assert result == []

    @pytest.mark.benchmark(group="episode-detection")
    def test_single_message(self, benchmark):
        """
        Benchmark boundary detection with single message.

        Target: <1ms P50 (should be instant)
        Input: Single message
        Verify: Returns empty list (no boundaries possible)
        """
        from core.episode_segmentation_service import EpisodeBoundaryDetector

        mock_db = MagicMock()
        detector = EpisodeBoundaryDetector(mock_db)

        message = ChatMessage(
            id="msg_1",
            conversation_id="session_1",
            role="user",
            content="Single message",
            created_at=datetime.utcnow(),
            agent_id="agent_1"
        )

        def detect_single():
            gaps = detector.detect_time_gap([message])
            assert gaps == []
            return gaps

        result = benchmark(detect_single)
        assert result == []

    @pytest.mark.benchmark(group="episode-creation")
    def test_keyword_similarity_fallback(self, benchmark):
        """
        Benchmark keyword similarity calculation (fallback).

        Target: <5ms P50 (string operations are fast)
        Input: Two text strings
        Verify: Returns similarity score
        """
        from core.episode_segmentation_service import EpisodeBoundaryDetector

        mock_db = MagicMock()
        detector = EpisodeBoundaryDetector(mock_db)

        text1 = "Discussion about accounting and financial reports"
        text2 = "Discussion about engineering and software development"

        def calculate_similarity():
            similarity = detector._keyword_similarity(text1, text2)
            assert 0.0 <= similarity <= 1.0
            return similarity

        result = benchmark(calculate_similarity)
        assert 0.0 <= result <= 1.0

    @pytest.mark.benchmark(group="episode-detection")
    def test_identical_messages(self, benchmark):
        """
        Benchmark topic detection with identical messages.

        Target: <10ms P50 (high similarity, no boundary)
        Input: 10 identical messages
        Verify: Returns empty list (no topic changes)
        """
        from core.episode_segmentation_service import EpisodeBoundaryDetector

        mock_db = MagicMock()
        # Return identical embeddings
        mock_db.embed_text = MagicMock(return_value=[0.5] * 384)

        detector = EpisodeBoundaryDetector(mock_db)

        base_time = datetime.utcnow()
        messages = []

        for i in range(10):
            messages.append(ChatMessage(
                id=f"msg_{i}",
                conversation_id="session_1",
                role="user",
                content="Same message repeated",
                created_at=base_time + timedelta(minutes=i),
                agent_id="agent_1"
            ))

        def detect_topic():
            changes = detector.detect_topic_changes(messages)
            # No topic changes (identical messages)
            assert len(changes) == 0
            return changes

        result = benchmark(detect_topic)
        assert len(result) == 0
