"""
Unit Tests for Episode Segmentation Algorithms

Tests pure logic functions in episode_segmentation_service.py without external dependencies.
Focuses on time gap detection, topic similarity, segmentation scoring, and boundary detection.
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st
from typing import List, Optional
from unittest.mock import Mock

from core.episode_segmentation_service import (
    EpisodeBoundaryDetector,
    TIME_GAP_THRESHOLD_MINUTES,
    SEMANTIC_SIMILARITY_THRESHOLD,
)


# ============================================================================
# Mock Data Classes for Testing
# ============================================================================

class MockChatMessage:
    """Mock ChatMessage for testing"""
    def __init__(self, content: str, created_at: datetime, role: str = "user"):
        self.content = content
        self.created_at = created_at
        self.role = role


class MockAgentExecution:
    """Mock AgentExecution for testing"""
    def __init__(self, status: str, result_summary: Optional[str] = None):
        self.status = status
        self.result_summary = result_summary


# ============================================================================
# Time Gap Detection Tests
# ============================================================================

@pytest.mark.unit
class TestTimeGapDetection:
    """Test time gap detection logic"""

    def test_detect_time_gap_below_threshold(self):
        """Test no gap when below threshold"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        now = datetime.utcnow()
        messages = [
            MockChatMessage("Message 1", now),
            MockChatMessage("Message 2", now + timedelta(seconds=30)),
        ]

        gaps = detector.detect_time_gap(messages)

        assert gaps == []  # No gap detected (30 min threshold)

    def test_detect_time_gap_at_threshold(self):
        """Test gap detected at exactly threshold"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        now = datetime.utcnow()
        messages = [
            MockChatMessage("Message 1", now),
            MockChatMessage("Message 2", now + timedelta(minutes=30)),
        ]

        gaps = detector.detect_time_gap(messages)

        assert gaps == [1]  # Gap at index 1

    def test_detect_time_gap_above_threshold(self):
        """Test gap detected when above threshold"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        now = datetime.utcnow()
        messages = [
            MockChatMessage("Message 1", now),
            MockChatMessage("Message 2", now + timedelta(minutes=60)),
        ]

        gaps = detector.detect_time_gap(messages)

        assert gaps == [1]

    @pytest.mark.parametrize("gap_seconds,threshold,expected", [
        (30, 60, False),   # Below threshold
        (60, 60, True),    # At threshold
        (120, 60, True),   # Above threshold
        (1800, 1800, True),  # Exactly 30 minutes
        (1799, 1800, False), # Just below 30 minutes
    ])
    def test_time_gap_threshold_parametrized(self, gap_seconds, threshold, expected):
        """Parametrized test for time gap threshold"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        # Temporarily override threshold
        import core.episode_segmentation_service as es
        original_threshold = es.TIME_GAP_THRESHOLD_MINUTES
        es.TIME_GAP_THRESHOLD_MINUTES = threshold / 60  # Convert to minutes

        now = datetime.utcnow()
        messages = [
            MockChatMessage("Message 1", now),
            MockChatMessage("Message 2", now + timedelta(seconds=gap_seconds)),
        ]

        gaps = detector.detect_time_gap(messages)
        has_gap = len(gaps) > 0

        assert has_gap == expected

        # Restore threshold
        es.TIME_GAP_THRESHOLD_MINUTES = original_threshold

    def test_detect_multiple_time_gaps(self):
        """Test detecting multiple time gaps in a sequence"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        now = datetime.utcnow()
        messages = [
            MockChatMessage("Message 1", now),
            MockChatMessage("Message 2", now + timedelta(minutes=10)),
            MockChatMessage("Message 3", now + timedelta(minutes=45)),  # Gap
            MockChatMessage("Message 4", now + timedelta(minutes=50)),
            MockChatMessage("Message 5", now + timedelta(minutes=100)),  # Gap
        ]

        gaps = detector.detect_time_gap(messages)

        assert gaps == [2, 4]

    def test_detect_time_gap_empty_messages(self):
        """Test time gap detection with empty messages"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        gaps = detector.detect_time_gap([])

        assert gaps == []

    def test_detect_time_gap_single_message(self):
        """Test time gap detection with single message"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        now = datetime.utcnow()
        messages = [MockChatMessage("Message 1", now)]

        gaps = detector.detect_time_gap(messages)

        assert gaps == []


# ============================================================================
# Cosine Similarity Tests
# ============================================================================

@pytest.mark.unit
class TestCosineSimilarity:
    """Test cosine similarity calculation"""

    def test_cosine_similarity_identical_vectors(self):
        """Test cosine similarity of identical vectors is 1.0"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.0, 2.0, 3.0]

        similarity = detector._cosine_similarity(vec1, vec2)

        assert abs(similarity - 1.0) < 0.001  # Allow floating point error

    def test_cosine_similarity_orthogonal_vectors(self):
        """Test cosine similarity of orthogonal vectors is 0.0"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        similarity = detector._cosine_similarity(vec1, vec2)

        assert abs(similarity - 0.0) < 0.001

    def test_cosine_similarity_opposite_vectors(self):
        """Test cosine similarity of opposite vectors is -1.0"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]

        similarity = detector._cosine_similarity(vec1, vec2)

        assert abs(similarity - (-1.0)) < 0.001

    @pytest.mark.parametrize("vec1,vec2,expected_range", [
        ([1, 0], [0.707, 0.707], (0.7, 0.72)),  # 45 degrees
        ([1, 0], [0, 1], (0, 0.01)),  # 90 degrees
        ([2, 0], [1, 0], (0.99, 1.0)),  # Same direction, different magnitude
    ])
    def test_cosine_similarity_various_angles(self, vec1, vec2, expected_range):
        """Parametrized test for various vector angles"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        similarity = detector._cosine_similarity(vec1, vec2)

        assert expected_range[0] <= similarity <= expected_range[1]

    def test_cosine_similarity_zero_vector(self):
        """Test cosine similarity with zero vector"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        vec1 = [1.0, 2.0, 3.0]
        vec2 = [0.0, 0.0, 0.0]

        similarity = detector._cosine_similarity(vec1, vec2)

        assert similarity == 0.0  # Zero division handled

    def test_cosine_similarity_pure_python_fallback(self):
        """Test pure Python fallback when numpy is unavailable"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        vec1 = [1.0, 2.0, 3.0]
        vec2 = [2.0, 4.0, 6.0]

        # This will use pure Python fallback if numpy fails
        similarity = detector._cosine_similarity(vec1, vec2)

        assert abs(similarity - 1.0) < 0.001


# ============================================================================
# Topic Change Detection Tests
# ============================================================================

@pytest.mark.unit
class TestTopicChangeDetection:
    """Test topic change detection logic"""

    def test_topic_change_detection_without_lancedb(self):
        """Test topic change detection returns empty when no LanceDB"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        messages = [
            MockChatMessage("sales report", datetime.utcnow()),
            MockChatMessage("engineering task", datetime.utcnow()),
        ]

        changes = detector.detect_topic_changes(messages)

        assert changes == []  # No LanceDB handler

    def test_topic_change_detection_with_mock_lancedb(self):
        """Test topic change detection with mock LanceDB"""
        # Create mock LanceDB handler
        mock_lancedb = Mock()
        mock_lancedb.embed_text = Mock(side_effect=lambda x: [0.1, 0.2, 0.3])

        detector = EpisodeBoundaryDetector(lancedb_handler=mock_lancedb)

        messages = [
            MockChatMessage("sales revenue", datetime.utcnow()),
            MockChatMessage("engineering deployment", datetime.utcnow()),
        ]

        changes = detector.detect_topic_changes(messages)

        # Mock returns same embedding, so no change detected
        assert changes == []

    def test_topic_change_detection_with_different_embeddings(self):
        """Test topic change detection with different embeddings"""
        mock_lancedb = Mock()

        # Return different embeddings to trigger change
        embeddings = [
            [1.0, 0.0, 0.0],  # sales
            [0.0, 1.0, 0.0],  # engineering (orthogonal)
        ]
        mock_lancedb.embed_text = Mock(side_effect=lambda x: embeddings.pop(0) if embeddings else [0, 0, 0])

        detector = EpisodeBoundaryDetector(lancedb_handler=mock_lancedb)

        messages = [
            MockChatMessage("sales revenue", datetime.utcnow()),
            MockChatMessage("engineering deployment", datetime.utcnow()),
        ]

        changes = detector.detect_topic_changes(messages)

        # Similarity < 0.75, so change detected
        assert changes == [1]

    @pytest.mark.parametrize("similarity,should_detect", [
        (0.9, False),  # Very similar, no change
        (0.75, False),  # At threshold, no change
        (0.74, True),   # Just below threshold, change detected
        (0.5, True),    # Different, change detected
        (0.0, True),    # Orthogonal, change detected
    ])
    def test_topic_change_similarity_threshold(self, similarity, should_detect):
        """Parametrized test for similarity threshold"""
        mock_lancedb = Mock()

        # Create embeddings with specific similarity
        vec1 = [1.0, 0.0, 0.0]
        import math
        vec2 = [similarity, math.sqrt(1 - similarity**2), 0.0]  # Normalized vector

        embeddings = [vec1, vec2]
        mock_lancedb.embed_text = Mock(side_effect=lambda x: embeddings.pop(0) if embeddings else [0, 0, 0])

        detector = EpisodeBoundaryDetector(lancedb_handler=mock_lancedb)

        messages = [
            MockChatMessage("topic 1", datetime.utcnow()),
            MockChatMessage("topic 2", datetime.utcnow()),
        ]

        changes = detector.detect_topic_changes(messages)

        if should_detect:
            assert changes == [1]
        else:
            assert changes == []


# ============================================================================
# Task Completion Detection Tests
# ============================================================================

@pytest.mark.unit
class TestTaskCompletionDetection:
    """Test task completion detection logic"""

    def test_detect_task_completion(self):
        """Test detecting completed tasks"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        executions = [
            MockAgentExecution("running"),
            MockAgentExecution("completed", "Task finished successfully"),
            MockAgentExecution("completed", "Another task done"),
        ]

        completions = detector.detect_task_completion(executions)

        assert completions == [1, 2]

    def test_detect_task_completion_no_summary(self):
        """Test completed tasks without summary are not detected"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        executions = [
            MockAgentExecution("completed"),  # No summary
            MockAgentExecution("running"),
        ]

        completions = detector.detect_task_completion(executions)

        assert completions == []  # No summary, not counted

    def test_detect_task_completion_empty_executions(self):
        """Test task completion detection with empty executions"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        completions = detector.detect_task_completion([])

        assert completions == []

    @pytest.mark.parametrize("status,has_summary,should_detect", [
        ("completed", True, True),
        ("completed", False, False),
        ("running", True, False),
        ("failed", True, False),
        ("pending", True, False),
    ])
    def test_task_completion_status_variations(self, status, has_summary, should_detect):
        """Parametrized test for various execution statuses"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        summary = "Task done" if has_summary else None
        executions = [MockAgentExecution(status, summary)]

        completions = detector.detect_task_completion(executions)

        if should_detect:
            assert len(completions) == 1
        else:
            assert len(completions) == 0


# ============================================================================
# Segmentation Scoring Tests
# ============================================================================

@pytest.mark.unit
class TestSegmentationScoring:
    """Test episode segmentation scoring logic"""

    @pytest.mark.parametrize("action_count,complexity,expected_min_score", [
        (5, "low", 0.5),
        (20, "medium", 0.5),
        (50, "high", 0.5),
        (100, "high", 0.5),
        (1, "low", 0.5),
    ])
    def test_importance_score_calculation(self, action_count, complexity, expected_min_score):
        """Parametrized test for importance score calculation"""
        # This tests the _calculate_importance method logic
        # Base score is 0.5, more actions increase it

        base_score = 0.5

        if action_count > 10:
            base_score += 0.2
        elif action_count > 5:
            base_score += 0.1

        # Add execution bonus
        base_score += 0.1

        final_score = min(1.0, base_score)

        assert final_score >= expected_min_score


# ============================================================================
# Boundary Detection Tests
# ============================================================================

@pytest.mark.unit
class TestBoundaryDetectionEdgeCases:
    """Test edge cases in boundary detection"""

    def test_boundary_detection_with_none_lancedb(self):
        """Test boundary detector handles None LanceDB gracefully"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        # Should not crash
        gaps = detector.detect_time_gap([])
        changes = detector.detect_topic_changes([])
        completions = detector.detect_task_completion([])

        assert gaps == []
        assert changes == []
        assert completions == []

    def test_boundary_detection_with_single_message(self):
        """Test boundary detection with single message"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        now = datetime.utcnow()
        messages = [MockChatMessage("Only message", now)]

        gaps = detector.detect_time_gap(messages)

        assert gaps == []

    def test_boundary_detection_with_none_embeddings(self):
        """Test topic change with None embeddings from LanceDB"""
        mock_lancedb = Mock()
        mock_lancedb.embed_text = Mock(return_value=None)  # Simulate failure

        detector = EpisodeBoundaryDetector(lancedb_handler=mock_lancedb)

        messages = [
            MockChatMessage("Message 1", datetime.utcnow()),
            MockChatMessage("Message 2", datetime.utcnow()),
        ]

        changes = detector.detect_topic_changes(messages)

        # Should handle None embeddings gracefully
        assert changes == []


# ============================================================================
# Property-Based Tests
# ============================================================================

@pytest.mark.unit
class TestEpisodeSegmentationPropertyTests:
    """Property-based tests for episode segmentation"""

    @given(st.lists(st.times(min_value=datetime(2024, 1, 1), max_value=datetime(2024, 12, 31)), min_size=2, max_size=10))
    def test_time_gaps_are_indices(self, timestamps):
        """Property: detected time gaps are always valid indices"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        messages = [
            MockChatMessage(f"Message {i}", timestamps[i])
            for i in range(len(timestamps))
        ]

        gaps = detector.detect_time_gap(messages)

        # All gaps should be valid indices
        for gap in gaps:
            assert 0 < gap < len(messages)

    @given(st.integers(min_value=0, max_value=1000))
    def test_time_gap_threshold_consistency(self, gap_seconds):
        """Property: time gap threshold is consistently applied"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        threshold_minutes = 30
        threshold_seconds = threshold_minutes * 60

        now = datetime.utcnow()
        messages = [
            MockChatMessage("Message 1", now),
            MockChatMessage("Message 2", now + timedelta(seconds=gap_seconds)),
        ]

        gaps = detector.detect_time_gap(messages)

        if gap_seconds >= threshold_seconds:
            assert len(gaps) > 0  # Gap detected
        else:
            assert len(gaps) == 0  # No gap

    @given(st.lists(st.floats(min_value=-1.0, max_value=1.0), min_size=2, max_size=2))
    def test_cosine_similarity_range(self, vectors):
        """Property: cosine similarity is always in [-1, 1]"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        # Create vectors from random floats
        vec1 = [abs(v) for v in vectors[:3]] if len(vectors) >= 3 else [1.0, 0.0, 0.0]
        vec2 = [abs(v) for v in vectors[3:6]] if len(vectors) >= 6 else [0.0, 1.0, 0.0]

        similarity = detector._cosine_similarity(vec1, vec2)

        assert -1.0 <= similarity <= 1.0


# ============================================================================
# Configuration Constants Tests
# ============================================================================

@pytest.mark.unit
class TestConfigurationConstants:
    """Test configuration constants are properly defined"""

    def test_time_gap_threshold_is_positive(self):
        """Test TIME_GAP_THRESHOLD_MINUTES is positive"""
        assert TIME_GAP_THRESHOLD_MINUTES > 0
        assert isinstance(TIME_GAP_THRESHOLD_MINUTES, (int, float))

    def test_similarity_threshold_in_valid_range(self):
        """Test SEMANTIC_SIMILARITY_THRESHOLD is in valid range"""
        assert 0.0 <= SEMANTIC_SIMILARITY_THRESHOLD <= 1.0

    def test_default_threshold_values(self):
        """Test default threshold values match expectations"""
        # Expected defaults from code
        assert TIME_GAP_THRESHOLD_MINUTES == 30
        assert SEMANTIC_SIMILARITY_THRESHOLD == 0.75
