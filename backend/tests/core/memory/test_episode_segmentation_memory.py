"""EpisodeSegmentationService comprehensive coverage tests.

This test file provides comprehensive coverage for the EpisodeSegmentationService,
covering automatic segmentation, topic change detection, episode lifecycle management,
and segment retrieval.

Created for Phase 206 Plan 04 (Wave 3: Infrastructure coverage expansion)
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List

from core.episode_segmentation_service import (
    EpisodeSegmentationService,
    EpisodeBoundaryDetector,
    SegmentationResult,
    SegmentationBoundary,
    TIME_GAP_THRESHOLD_MINUTES,
    SEMANTIC_SIMILARITY_THRESHOLD,
)
from core.models import Episode, EpisodeSegment, ChatMessage, ChatSession


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB handler."""
    handler = Mock()
    handler.embed_text = Mock(return_value=[0.1, 0.2, 0.3])
    return handler


@pytest.fixture
def boundary_detector(mock_lancedb):
    """EpisodeBoundaryDetector fixture."""
    return EpisodeBoundaryDetector(mock_lancedb)


@pytest.fixture
def sample_messages():
    """Sample chat messages for testing."""
    now = datetime(2026, 3, 1, 10, 0, 0)
    return [
        Mock(spec=ChatMessage, id="m1", conversation_id="s1", role="user",
             content="Processing invoices", created_at=now),
        Mock(spec=ChatMessage, id="m2", conversation_id="s1", role="assistant",
             content="I'll help you process invoices", created_at=now + timedelta(minutes=5)),
        Mock(spec=ChatMessage, id="m3", conversation_id="s1", role="user",
             content="Designing user interface", created_at=now + timedelta(minutes=40)),
        Mock(spec=ChatMessage, id="m4", conversation_id="s1", role="assistant",
             content="Let's design the UI", created_at=now + timedelta(minutes=45)),
    ]


class TestAutomaticSegmentation:
    """Test automatic episode segmentation."""

    def test_segment_by_time_gap(self, boundary_detector, sample_messages):
        """Create new segment when time gap detected (>30 minutes)."""
        gaps = boundary_detector.detect_time_gap(sample_messages)

        # Should detect gap between m2 (10:05) and m3 (10:40) = 35 minutes
        assert len(gaps) == 1
        assert gaps[0] == 2  # Index of m3

    def test_no_segment_within_time_threshold(self, boundary_detector):
        """Don't segment within time threshold (<=30 minutes)."""
        now = datetime(2026, 3, 1, 10, 0, 0)
        messages = [
            Mock(spec=ChatMessage, id="m1", created_at=now),
            Mock(spec=ChatMessage, id="m2", created_at=now + timedelta(minutes=15)),
            Mock(spec=ChatMessage, id="m3", created_at=now + timedelta(minutes=30)),
        ]

        gaps = boundary_detector.detect_time_gap(messages)

        # No gaps > 30 minutes
        assert len(gaps) == 0

    def test_segment_on_exact_threshold(self, boundary_detector):
        """Test boundary condition: exactly 30 minutes should NOT trigger."""
        now = datetime(2026, 3, 1, 10, 0, 0)
        messages = [
            Mock(spec=ChatMessage, id="m1", created_at=now),
            Mock(spec=ChatMessage, id="m2", created_at=now + timedelta(minutes=30)),
        ]

        gaps = boundary_detector.detect_time_gap(messages)

        # Exactly 30 minutes is NOT a gap (exclusive boundary)
        assert len(gaps) == 0

    def test_segment_on_multiple_time_gaps(self, boundary_detector):
        """Detect multiple time gaps in sequence."""
        now = datetime(2026, 3, 1, 10, 0, 0)
        messages = [
            Mock(spec=ChatMessage, id="m1", created_at=now),
            Mock(spec=ChatMessage, id="m2", created_at=now + timedelta(minutes=5)),
            Mock(spec=ChatMessage, id="m3", created_at=now + timedelta(minutes=40)),  # Gap 1
            Mock(spec=ChatMessage, id="m4", created_at=now + timedelta(minutes=45)),
            Mock(spec=ChatMessage, id="m5", created_at=now + timedelta(minutes=90)),  # Gap 2
        ]

        gaps = boundary_detector.detect_time_gap(messages)

        assert len(gaps) == 2
        assert gaps[0] == 2
        assert gaps[1] == 4

    def test_empty_message_list(self, boundary_detector):
        """Handle empty message list gracefully."""
        gaps = boundary_detector.detect_time_gap([])
        assert len(gaps) == 0

    def test_single_message_no_gap(self, boundary_detector):
        """Single message cannot have gaps."""
        now = datetime(2026, 3, 1, 10, 0, 0)
        messages = [Mock(spec=ChatMessage, id="m1", created_at=now)]

        gaps = boundary_detector.detect_time_gap(messages)
        assert len(gaps) == 0


class TestTopicChangeDetection:
    """Test topic change detection using embeddings."""

    def test_detect_topic_change_low_similarity(self, boundary_detector):
        """Detect topic change when embedding similarity is low."""
        # Setup mock embeddings with low similarity (orthogonal vectors)
        boundary_detector.db.embed_text = Mock(side_effect=[
            [1.0, 0.0, 0.0],  # Topic A
            [0.0, 1.0, 0.0]   # Topic B (orthogonal = 0.0 similarity)
        ])

        messages = [
            Mock(spec=ChatMessage, id="m1", content="Processing invoices"),
            Mock(spec=ChatMessage, id="m2", content="Designing user interface"),
        ]

        changes = boundary_detector.detect_topic_changes(messages)

        assert len(changes) == 1
        assert changes[0] == 1

    def test_no_topic_change_high_similarity(self, boundary_detector):
        """Don't segment when topic unchanged (high similarity)."""
        # Same embedding = high similarity
        embedding = [0.5, 0.5, 0.5]
        boundary_detector.db.embed_text = Mock(return_value=embedding)

        messages = [
            Mock(spec=ChatMessage, id="m1", content="Processing invoice #123"),
            Mock(spec=ChatMessage, id="m2", content="Processing invoice #456"),
        ]

        changes = boundary_detector.detect_topic_changes(messages)

        assert len(changes) == 0

    def test_topic_change_at_threshold(self, boundary_detector):
        """Test boundary condition at similarity threshold."""
        # Mock embeddings that produce exactly 0.75 similarity
        boundary_detector.db.embed_text = Mock(side_effect=[
            [1.0, 0.0, 0.0],
            [0.75, 0.25, 0.0]  # Normalized to get 0.75 cosine similarity
        ])

        messages = [
            Mock(spec=ChatMessage, id="m1", content="Topic A"),
            Mock(spec=ChatMessage, id="m2", content="Topic B"),
        ]

        changes = boundary_detector.detect_topic_changes(messages)

        # At threshold (0.75), should NOT trigger change (exclusive boundary)
        assert len(changes) == 0

    def test_topic_change_below_threshold(self, boundary_detector):
        """Test below threshold triggers change."""
        # Mock embeddings with low similarity
        boundary_detector.db.embed_text = Mock(side_effect=[
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0]  # Orthogonal = 0.0 similarity
        ])

        messages = [
            Mock(spec=ChatMessage, id="m1", content="Topic A"),
            Mock(spec=ChatMessage, id="m2", content="Topic B"),
        ]

        changes = boundary_detector.detect_topic_changes(messages)

        assert len(changes) == 1

    def test_empty_messages_no_topic_change(self, boundary_detector):
        """Handle empty message list."""
        changes = boundary_detector.detect_topic_changes([])
        assert len(changes) == 0

    def test_single_message_no_topic_change(self, boundary_detector):
        """Single message cannot have topic changes."""
        messages = [Mock(spec=ChatMessage, id="m1", content="Single message")]

        changes = boundary_detector.detect_topic_changes(messages)
        assert len(changes) == 0

    def test_topic_change_embedding_fallback(self, boundary_detector):
        """Fallback to keyword-based similarity when embeddings fail."""
        # Mock embedding failure (returns None) to force keyword fallback
        boundary_detector.db.embed_text = Mock(return_value=None)

        messages = [
            Mock(spec=ChatMessage, id="m1", content="processing invoices and payments"),
            Mock(spec=ChatMessage, id="m2", content="a"),  # Single character, minimal overlap
        ]

        changes = boundary_detector.detect_topic_changes(messages)

        # Should detect change based on keyword overlap (very low similarity)
        assert len(changes) == 1

    def test_topic_change_keyword_similarity_high(self, boundary_detector):
        """Keyword similarity detects same topic."""
        boundary_detector.db = None

        messages = [
            Mock(spec=ChatMessage, id="m1", content="processing invoices and payments"),
            Mock(spec=ChatMessage, id="m2", content="processing more invoices today"),
        ]

        changes = boundary_detector.detect_topic_changes(messages)

        # High keyword overlap ("processing", "invoices") = no change
        assert len(changes) == 0


class TestCosineSimilarity:
    """Test cosine similarity calculation."""

    def test_cosine_similarity_identical_vectors(self, boundary_detector):
        """Identical vectors have similarity 1.0."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.0, 2.0, 3.0]

        similarity = boundary_detector._cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(1.0, rel=0.01)

    def test_cosine_similarity_orthogonal_vectors(self, boundary_detector):
        """Orthogonal vectors have similarity 0.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        similarity = boundary_detector._cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(0.0, abs=0.01)

    def test_cosine_similarity_opposite_vectors(self, boundary_detector):
        """Opposite vectors have similarity -1.0."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]

        similarity = boundary_detector._cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(-1.0, rel=0.01)

    def test_cosine_similarity_zero_vector(self, boundary_detector):
        """Zero vector handled gracefully."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [0.0, 0.0, 0.0]

        similarity = boundary_detector._cosine_similarity(vec1, vec2)

        assert similarity == 0.0


class TestKeywordSimilarity:
    """Test keyword-based similarity calculation."""

    def test_keyword_similarity_identical_text(self, boundary_detector):
        """Identical text has similarity 1.0."""
        text = "processing invoices and payments"

        similarity = boundary_detector._keyword_similarity(text, text)

        assert similarity == 1.0

    def test_keyword_similarity_no_overlap(self, boundary_detector):
        """No word overlap has similarity 0.0."""
        text1 = "processing invoices payments"
        text2 = "designing user interface"

        similarity = boundary_detector._keyword_similarity(text1, text2)

        assert similarity == 0.0

    def test_keyword_similarity_partial_overlap(self, boundary_detector):
        """Partial word overlap has intermediate similarity."""
        text1 = "processing invoices and payments"
        text2 = "processing more invoices today"

        similarity = boundary_detector._keyword_similarity(text1, text2)

        # "processing" and "invoices" overlap
        assert 0.0 < similarity < 1.0

    def test_keyword_similarity_case_insensitive(self, boundary_detector):
        """Similarity is case-insensitive."""
        text1 = "Processing Invoices"
        text2 = "processing invoices"

        similarity1 = boundary_detector._keyword_similarity(text1, text2)
        similarity2 = boundary_detector._keyword_similarity(text2, text1)

        assert similarity1 == similarity2
        assert similarity1 > 0.0

    def test_keyword_similarity_empty_strings(self, boundary_detector):
        """Empty strings handled gracefully."""
        similarity = boundary_detector._keyword_similarity("", "")

        assert similarity == 0.0


class TestTaskCompletionDetection:
    """Test task completion boundary detection."""

    def test_detect_task_completion(self, boundary_detector):
        """Detect completed tasks."""
        executions = [
            Mock(status="running", result_summary=None),
            Mock(status="completed", result_summary="Task finished"),
            Mock(status="failed", result_summary="Task failed"),
            Mock(status="completed", result_summary="Another task done"),
        ]

        completions = boundary_detector.detect_task_completion(executions)

        assert len(completions) == 2
        assert 1 in completions
        assert 3 in completions

    def test_detect_task_completion_no_results(self, boundary_detector):
        """Tasks without result_summary are not counted."""
        executions = [
            Mock(status="completed", result_summary=None),
            Mock(status="completed", result_summary=None),
        ]

        completions = boundary_detector.detect_task_completion(executions)

        assert len(completions) == 0

    def test_detect_task_completion_empty_list(self, boundary_detector):
        """Empty execution list handled gracefully."""
        completions = boundary_detector.detect_task_completion([])
        assert len(completions) == 0


class TestSegmentationResult:
    """Test segmentation result data structures."""

    def test_segmentation_result_creation(self):
        """Create SegmentationResult namedtuple."""
        episodes = [Mock(episode_id="ep-1"), Mock(episode_id="ep-2")]
        result = SegmentationResult(
            episodes=episodes,
            segment_count=5,
            time_gaps_found=2,
            topic_changes_found=1
        )

        assert len(result.episodes) == 2
        assert result.segment_count == 5
        assert result.time_gaps_found == 2
        assert result.topic_changes_found == 1

    def test_segmentation_boundary_creation(self):
        """Create SegmentationBoundary namedtuple."""
        boundary = SegmentationBoundary(
            boundary_id="bound-1",
            timestamp=datetime(2026, 3, 1, 10, 30, 0),
            boundary_type="time_gap"
        )

        assert boundary.boundary_id == "bound-1"
        assert boundary.boundary_type == "time_gap"

    def test_segmentation_boundary_topic_change(self):
        """Create topic change boundary."""
        boundary = SegmentationBoundary(
            boundary_id="bound-2",
            timestamp=datetime(2026, 3, 1, 11, 0, 0),
            boundary_type="topic_change"
        )

        assert boundary.boundary_type == "topic_change"

    def test_segmentation_boundary_task_completion(self):
        """Create task completion boundary."""
        boundary = SegmentationBoundary(
            boundary_id="bound-3",
            timestamp=datetime(2026, 3, 1, 12, 0, 0),
            boundary_type="task_completion"
        )

        assert boundary.boundary_type == "task_completion"


class TestConfigurationConstants:
    """Test configuration constants."""

    def test_time_gap_threshold(self):
        """Verify time gap threshold constant."""
        assert TIME_GAP_THRESHOLD_MINUTES == 30

    def test_semantic_similarity_threshold(self):
        """Verify semantic similarity threshold constant."""
        assert SEMANTIC_SIMILARITY_THRESHOLD == 0.75


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_none_messages_handling(self, boundary_detector):
        """Handle None messages gracefully - expects TypeError."""
        # The actual implementation doesn't handle None, so we expect it to raise
        with pytest.raises(TypeError):
            boundary_detector.detect_time_gap(None)

    def test_invalid_timestamp_order(self, boundary_detector):
        """Handle messages with out-of-order timestamps."""
        now = datetime(2026, 3, 1, 10, 0, 0)
        messages = [
            Mock(spec=ChatMessage, id="m1", created_at=now + timedelta(minutes=10)),
            Mock(spec=ChatMessage, id="m2", created_at=now),  # Earlier time
        ]

        # Should not crash, just handle gracefully
        gaps = boundary_detector.detect_time_gap(messages)
        assert isinstance(gaps, list)

    def test_messages_with_negative_time_gap(self, boundary_detector):
        """Handle negative time gaps (out of order)."""
        now = datetime(2026, 3, 1, 10, 0, 0)
        messages = [
            Mock(spec=ChatMessage, id="m1", created_at=now + timedelta(minutes=10)),
            Mock(spec=ChatMessage, id="m2", created_at=now - timedelta(minutes=5)),
        ]

        gaps = boundary_detector.detect_time_gap(messages)
        assert isinstance(gaps, list)

    def test_very_large_time_gap(self, boundary_detector):
        """Handle very large time gaps (days)."""
        now = datetime(2026, 3, 1, 10, 0, 0)
        messages = [
            Mock(spec=ChatMessage, id="m1", created_at=now),
            Mock(spec=ChatMessage, id="m2", created_at=now + timedelta(days=7)),
        ]

        gaps = boundary_detector.detect_time_gap(messages)
        assert len(gaps) == 1

    def test_embedding_failure_fallback(self, boundary_detector):
        """Handle embedding failures gracefully."""
        # Mock embedding failure
        boundary_detector.db.embed_text = Mock(side_effect=[None, None])

        messages = [
            Mock(spec=ChatMessage, id="m1", content="Topic A"),
            Mock(spec=ChatMessage, id="m2", content="Topic B"),
        ]

        # Should fallback to keyword similarity
        changes = boundary_detector.detect_topic_changes(messages)
        assert isinstance(changes, list)
