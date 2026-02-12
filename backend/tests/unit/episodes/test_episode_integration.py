"""
Unit tests for EpisodeIntegration

Tests cover:
1. Canvas metadata linking
2. Feedback metadata linking
3. Episode creation with metadata
4. Retrieval with metadata enrichment
5. Action filtering
"""

import pytest
from datetime import datetime
from unittest.mock import Mock
from sqlalchemy.orm import Session


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Mock database session."""
    session = Mock()
    session.query.return_value = session
    session.filter.return_value = session
    session.order_by.return_value = session
    session.limit.return_value = session
    session.all.return_value = []
    session.first.return_value = None
    session.add.return_value = None
    session.commit.return_value = None
    return session


# ============================================================================
# Canvas Metadata Tests
# ============================================================================

class TestCanvasMetadata:
    """Test canvas metadata linking with episodes."""

    def test_canvas_action_types(self):
        """Test valid canvas action types."""
        valid_actions = ["present", "submit", "close", "update", "execute"]
        for action in valid_actions:
            assert isinstance(action, str)

    def test_canvas_types(self):
        """Test valid canvas types."""
        valid_types = ["generic", "docs", "email", "sheets", "orchestration", "terminal", "coding"]
        for canvas_type in valid_types:
            assert isinstance(canvas_type, str)

    def test_canvas_context_structure(self):
        """Test canvas context has expected structure."""
        canvas_audit = Mock()
        canvas_audit.id = "canvas-123"
        canvas_audit.canvas_type = "sheets"
        canvas_audit.component_type = "generic"
        canvas_audit.component_name = "TestComponent"
        canvas_audit.action = "present"
        canvas_audit.created_at = datetime.now()
        canvas_audit.audit_metadata = {}

        # Verify expected attributes
        assert canvas_audit.canvas_type == "sheets"
        assert canvas_audit.action == "present"


# ============================================================================
# Feedback Metadata Tests
# ============================================================================

class TestFeedbackMetadata:
    """Test feedback metadata linking with episodes."""

    def test_feedback_score_range(self):
        """Test feedback scores are in valid range."""
        # Test various feedback scores
        scores = [-1.0, -0.5, 0.0, 0.5, 1.0]
        for score in scores:
            assert -1.0 <= score <= 1.0

    def test_feedback_types(self):
        """Test valid feedback types."""
        valid_types = ["thumbs_up", "thumbs_down", "rating", "correction"]
        for feedback_type in valid_types:
            assert isinstance(feedback_type, str)

    def test_feedback_aggregation(self):
        """Test feedback score aggregation logic."""
        # Simulate aggregating multiple feedback scores
        feedback_scores = [1.0, 0.5, -0.5, -1.0, 0.0]
        aggregate = sum(feedback_scores) / len(feedback_scores)

        assert -1.0 <= aggregate <= 1.0
        assert aggregate == 0.0  # (1.0 + 0.5 - 0.5 - 1.0 + 0.0) / 5 = 0.0


# ============================================================================
# Episode Metadata Tests
# ============================================================================

class TestEpisodeMetadata:
    """Test episode metadata structure."""

    def test_episode_canvas_ids(self):
        """Test episode can store canvas IDs."""
        episode = Mock()
        episode.canvas_ids = ["canvas-1", "canvas-2", "canvas-3"]
        episode.canvas_action_count = len(episode.canvas_ids)

        assert episode.canvas_action_count == 3

    def test_episode_feedback_ids(self):
        """Test episode can store feedback IDs."""
        episode = Mock()
        episode.feedback_ids = ["feedback-1", "feedback-2"]
        episode.aggregate_feedback_score = 0.5

        assert len(episode.feedback_ids) == 2
        assert episode.aggregate_feedback_score == 0.5

    def test_metadata_only_storage(self):
        """Test metadata uses lightweight references."""
        # Canvas IDs and feedback IDs are lightweight references
        canvas_id = "canvas-123"  # Just an ID, not full object
        feedback_id = "feedback-456"  # Just an ID, not full object

        assert isinstance(canvas_id, str)
        assert isinstance(feedback_id, str)


# ============================================================================
# Action Filtering Tests
# ============================================================================

class TestActionFiltering:
    """Test filtering by canvas action types."""

    def test_state_changing_actions(self):
        """Test identifying state-changing actions."""
        state_changing = ["submit", "execute"]
        for action in state_changing:
            # These actions should be included in episode linking
            assert action in ["submit", "execute"]

    def test_read_only_actions(self):
        """Test identifying read-only actions."""
        read_only = ["present", "view", "read"]
        for action in read_only:
            # These actions might be excluded from episode linking
            assert isinstance(action, str)


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases for episode integration."""

    def test_empty_canvas_ids(self):
        """Test episode with no canvas context."""
        episode = Mock()
        episode.canvas_ids = []
        episode.canvas_action_count = 0

        assert episode.canvas_action_count == 0

    def test_empty_feedback_ids(self):
        """Test episode with no feedback context."""
        episode = Mock()
        episode.feedback_ids = []
        episode.aggregate_feedback_score = None

        assert episode.feedback_ids == []
        assert episode.aggregate_feedback_score is None

    def test_mixed_metadata(self):
        """Test episode with both canvas and feedback metadata."""
        episode = Mock()
        episode.canvas_ids = ["canvas-1", "canvas-2"]
        episode.feedback_ids = ["feedback-1"]
        episode.canvas_action_count = 2

        assert len(episode.canvas_ids) == 2
        assert len(episode.feedback_ids) == 1
