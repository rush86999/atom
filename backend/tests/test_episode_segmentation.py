"""
Tests for Episode Segmentation Service
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from core.episode_segmentation_service import (
    EpisodeSegmentationService,
    EpisodeBoundaryDetector
)
from core.models import Episode, EpisodeSegment, ChatMessage, AgentExecution


@pytest.fixture
def db_session():
    """Mock database session"""
    return Mock()


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB handler"""
    handler = Mock()
    handler.embed_text = Mock(return_value=[0.1, 0.2, 0.3])
    return handler


@pytest.fixture
def detector(mock_lancedb):
    """Episode boundary detector fixture"""
    return EpisodeBoundaryDetector(mock_lancedb)


@pytest.fixture
def segmentation_service(db_session):
    """Episode segmentation service fixture"""
    service = EpisodeSegmentationService(db_session)
    service.lancedb = Mock()
    service.lancedb.embed_text = Mock(return_value=[0.1, 0.2, 0.3])
    return service


class TestEpisodeBoundaryDetector:
    """Tests for episode boundary detection"""

    def test_detect_time_gap(self, detector):
        """Test time gap detection between messages"""
        now = datetime.now()

        messages = [
            ChatMessage(
                id="1", content="First", role="user", created_at=now
            ),
            ChatMessage(
                id="2", content="Second", role="assistant",
                created_at=now + timedelta(minutes=15)
            ),
            ChatMessage(
                id="3", content="Third", role="user",
                created_at=now + timedelta(minutes=45)  # 30 min gap
            ),
        ]

        gaps = detector.detect_time_gap(messages)
        assert len(gaps) == 1
        assert gaps[0] == 2  # Gap before message 3

    def test_detect_time_gap_no_gap(self, detector):
        """Test time gap detection with no gaps"""
        now = datetime.now()

        messages = [
            ChatMessage(
                id="1", content="First", role="user", created_at=now
            ),
            ChatMessage(
                id="2", content="Second", role="assistant",
                created_at=now + timedelta(minutes=10)
            ),
        ]

        gaps = detector.detect_time_gap(messages)
        assert len(gaps) == 0

    def test_cosine_similarity(self, detector):
        """Test cosine similarity calculation"""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        vec3 = [0.0, 1.0, 0.0]

        # Identical vectors
        sim1 = detector._cosine_similarity(vec1, vec2)
        assert abs(sim1 - 1.0) < 0.001

        # Orthogonal vectors
        sim2 = detector._cosine_similarity(vec1, vec3)
        assert abs(sim2 - 0.0) < 0.001


class TestEpisodeSegmentationService:
    """Tests for episode segmentation service"""

    @patch('core.episode_segmentation_service.get_lancedb_handler')
    def test_generate_title(self, mock_get_lancedb, db_session):
        """Test episode title generation"""
        service = EpisodeSegmentationService(db_session)

        messages = [
            ChatMessage(id="1", content="Create a workflow for invoices", role="user", created_at=datetime.now()),
            ChatMessage(id="2", content="I'll help you create that workflow", role="assistant", created_at=datetime.now()),
        ]

        title = service._generate_title(messages, [])
        assert "Create a workflow for invoices" in title

    @patch('core.episode_segmentation_service.get_lancedb_handler')
    def test_calculate_duration(self, mock_get_lancedb, db_session):
        """Test episode duration calculation"""
        service = EpisodeSegmentationService(db_session)

        now = datetime.now()
        messages = [
            ChatMessage(id="1", content="First", role="user", created_at=now),
            ChatMessage(id="2", content="Second", role="assistant", created_at=now + timedelta(seconds=30)),
        ]

        duration = service._calculate_duration(messages, [])
        assert duration == 30

    @patch('core.episode_segmentation_service.get_lancedb_handler')
    def test_calculate_importance(self, mock_get_lancedb, db_session):
        """Test importance score calculation"""
        service = EpisodeSegmentationService(db_session)

        # Many messages should increase importance
        many_messages = [
            ChatMessage(id=str(i), content=f"Message {i}", role="user", created_at=datetime.now())
            for i in range(15)
        ]

        score1 = service._calculate_importance(many_messages, [])
        assert score1 > 0.6

        # Few messages should have lower importance
        few_messages = [
            ChatMessage(id="1", content="Message", role="user", created_at=datetime.now())
        ]

        score2 = service._calculate_importance(few_messages, [])
        assert score2 < 0.6
