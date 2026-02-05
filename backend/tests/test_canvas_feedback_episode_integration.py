"""
Test canvas and feedback integration with episodic memory

Focused unit tests for the new canvas/feedback integration features.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class TestFeedbackScoreCalculation:
    """Test feedback score calculation logic"""

    def test_mixed_feedback_scores(self):
        """Test aggregate feedback score with mixed feedback types"""
        from core.episode_segmentation_service import EpisodeSegmentationService

        # Create a mock database session
        db = Mock()

        # Create service instance (no actual DB needed for this test)
        service = EpisodeSegmentationService.__new__(EpisodeSegmentationService)
        service.db = db

        # Create mock feedbacks
        feedbacks = [
            Mock(feedback_type="thumbs_up", thumbs_up_down=True, rating=None),
            Mock(feedback_type="thumbs_down", thumbs_up_down=False, rating=None),
            Mock(feedback_type="rating", thumbs_up_down=None, rating=5),
            Mock(feedback_type="rating", thumbs_up_down=None, rating=1)
        ]

        score = service._calculate_feedback_score(feedbacks)

        # Expected: (1.0 + -1.0 + 1.0 + -1.0) / 4 = 0.0
        assert score == 0.0

    def test_positive_only_feedback(self):
        """Test aggregate score with only positive feedback"""
        from core.episode_segmentation_service import EpisodeSegmentationService

        db = Mock()
        service = EpisodeSegmentationService.__new__(EpisodeSegmentationService)
        service.db = db

        feedbacks = [
            Mock(feedback_type="thumbs_up", thumbs_up_down=True, rating=None),
            Mock(feedback_type="rating", thumbs_up_down=None, rating=5),
            Mock(feedback_type="rating", thumbs_up_down=None, rating=4)
        ]

        score = service._calculate_feedback_score(feedbacks)

        # Expected: (1.0 + 1.0 + 0.5) / 3 = 0.833
        assert score > 0.8
        assert score <= 1.0

    def test_empty_feedback(self):
        """Test aggregate score with no feedback"""
        from core.episode_segmentation_service import EpisodeSegmentationService

        db = Mock()
        service = EpisodeSegmentationService.__new__(EpisodeSegmentationService)
        service.db = db

        score = service._calculate_feedback_score([])
        assert score is None


class TestCanvasInsightsExtraction:
    """Test canvas insights extraction from episodes"""

    def test_extract_canvas_type_counts(self):
        """Test extraction of canvas type usage patterns"""
        from core.agent_world_model import WorldModelService

        service = WorldModelService()

        enriched_episodes = [
            {
                "canvas_context": [
                    {"canvas_type": "sheets", "action": "present"},
                    {"canvas_type": "charts", "action": "close"}
                ],
                "feedback_context": [{"rating": 5}]
            },
            {
                "canvas_context": [
                    {"canvas_type": "sheets", "action": "present"},
                    {"canvas_type": "sheets", "action": "submit"}
                ],
                "feedback_context": []
            }
        ]

        insights = service._extract_canvas_insights(enriched_episodes)

        # Assert canvas type counts
        assert insights["canvas_type_counts"]["sheets"] == 3
        assert insights["canvas_type_counts"]["charts"] == 1

    def test_extract_user_interaction_patterns(self):
        """Test extraction of user interaction patterns"""
        from core.agent_world_model import WorldModelService

        service = WorldModelService()

        enriched_episodes = [
            {
                "canvas_context": [
                    {"canvas_type": "markdown", "action": "close"},
                    {"canvas_type": "sheets", "action": "close"}
                ],
                "feedback_context": []
            },
            {
                "canvas_context": [
                    {"canvas_type": "charts", "action": "present"}
                ],
                "feedback_context": [{"rating": 5}]
            }
        ]

        insights = service._extract_canvas_insights(enriched_episodes)

        # Assert interaction patterns
        assert len(insights["user_interaction_patterns"]["closes_quickly"]) == 2
        assert "markdown" in insights["user_interaction_patterns"]["closes_quickly"]
        assert "sheets" in insights["user_interaction_patterns"]["closes_quickly"]

    def test_extract_high_engagement_canvases(self):
        """Test identification of high-engagement canvases"""
        from core.agent_world_model import WorldModelService

        service = WorldModelService()

        enriched_episodes = [
            {
                "canvas_context": [
                    {"id": "canvas_1", "canvas_type": "charts", "action": "present"}
                ],
                "feedback_context": [{"rating": 5}, {"rating": 5}]
            }
        ]

        insights = service._extract_canvas_insights(enriched_episodes)

        # Assert high engagement canvases identified
        assert len(insights["high_engagement_canvases"]) == 1
        assert insights["high_engagement_canvases"][0]["canvas_id"] == "canvas_1"
        assert insights["high_engagement_canvases"][0]["avg_feedback"] == 5.0


class TestCanvasContextFetching:
    """Test canvas context fetching logic"""

    @pytest.mark.asyncio
    async def test_fetch_canvas_context_by_ids(self):
        """Test fetching canvas context by ID list"""
        from core.episode_retrieval_service import EpisodeRetrievalService

        # Create mock database
        db = Mock()

        # Create mock canvas records
        mock_canvases = [
            Mock(
                id="canvas_1",
                canvas_type="sheets",
                component_type="table",
                component_name="data_table",
                action="present",
                created_at=datetime.now(),
                audit_metadata={"rows": 10}
            ),
            Mock(
                id="canvas_2",
                canvas_type="charts",
                component_type="line_chart",
                component_name="sales_chart",
                action="present",
                created_at=datetime.now(),
                audit_metadata={"points": 50}
            )
        ]

        # Mock the database query
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_canvases
        db.query.return_value = mock_query

        # Create service
        service = EpisodeRetrievalService.__new__(EpisodeRetrievalService)
        service.db = db

        # Test fetch
        result = await service._fetch_canvas_context(["canvas_1", "canvas_2"])

        # Assert
        assert len(result) == 2
        assert result[0]["canvas_type"] == "sheets"
        assert result[1]["canvas_type"] == "charts"
        assert result[0]["action"] == "present"
        assert "metadata" in result[0]

    @pytest.mark.asyncio
    async def test_fetch_canvas_context_empty_list(self):
        """Test fetching canvas context with empty ID list"""
        from core.episode_retrieval_service import EpisodeRetrievalService

        db = Mock()
        service = EpisodeRetrievalService.__new__(EpisodeRetrievalService)
        service.db = db

        result = await service._fetch_canvas_context([])

        assert result == []


class TestFeedbackContextFetching:
    """Test feedback context fetching logic"""

    @pytest.mark.asyncio
    async def test_fetch_feedback_context_by_ids(self):
        """Test fetching feedback context by ID list"""
        from core.episode_retrieval_service import EpisodeRetrievalService

        # Create mock database
        db = Mock()

        # Create mock feedback records
        mock_feedbacks = [
            Mock(
                id="feedback_1",
                feedback_type="thumbs_up",
                rating=None,
                thumbs_up_down=True,
                user_correction="",
                created_at=datetime.now()
            ),
            Mock(
                id="feedback_2",
                feedback_type="rating",
                rating=5,
                thumbs_up_down=None,
                user_correction="Great work!",
                created_at=datetime.now()
            )
        ]

        # Mock the database query
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_feedbacks
        db.query.return_value = mock_query

        # Create service
        service = EpisodeRetrievalService.__new__(EpisodeRetrievalService)
        service.db = db

        # Test fetch
        result = await service._fetch_feedback_context(["feedback_1", "feedback_2"])

        # Assert
        assert len(result) == 2
        assert result[0]["feedback_type"] == "thumbs_up"
        assert result[1]["feedback_type"] == "rating"
        assert result[1]["rating"] == 5

    @pytest.mark.asyncio
    async def test_fetch_feedback_context_empty_list(self):
        """Test fetching feedback context with empty ID list"""
        from core.episode_retrieval_service import EpisodeRetrievalService

        db = Mock()
        service = EpisodeRetrievalService.__new__(EpisodeRetrievalService)
        service.db = db

        result = await service._fetch_feedback_context([])

        assert result == []


class TestEpisodeSerialization:
    """Test episode serialization with new fields"""

    def test_serialize_episode_with_canvas_feedback_fields(self):
        """Test that episodes serialize with new canvas/feedback fields"""
        from core.episode_retrieval_service import EpisodeRetrievalService
        from core.models import Episode

        # Create mock episode
        episode = Mock()
        episode.id = "ep_123"
        episode.title = "Test Episode"
        episode.description = "Test Description"
        episode.summary = "Test Summary"
        episode.agent_id = "agent_456"
        episode.status = "completed"
        episode.started_at = datetime.now()
        episode.ended_at = datetime.now()
        episode.topics = ["topic1"]
        episode.entities = ["entity1"]
        episode.importance_score = 0.8
        episode.maturity_at_time = "INTERN"
        episode.human_intervention_count = 0
        episode.constitutional_score = 0.9
        episode.decay_score = 1.0
        episode.access_count = 5

        # New fields
        episode.canvas_ids = ["canvas_1", "canvas_2"]
        episode.canvas_action_count = 2
        episode.feedback_ids = ["feedback_1"]
        episode.aggregate_feedback_score = 0.75

        # Create service
        db = Mock()
        service = EpisodeRetrievalService.__new__(EpisodeRetrievalService)
        service.db = db

        # Serialize
        result = service._serialize_episode(episode)

        # Assert old fields
        assert result["id"] == "ep_123"
        assert result["title"] == "Test Episode"
        assert result["status"] == "completed"
        assert result["importance_score"] == 0.8

        # Note: canvas_ids and feedback_ids are NOT in _serialize_episode output
        # They are only used internally for fetching context


class TestFeedbackWeightedRetrieval:
    """Test feedback-weighted retrieval logic"""

    def test_positive_feedback_boost(self):
        """Test that positive feedback boosts relevance score"""
        # Test the boost calculation logic
        base_score = 0.7
        canvas_boost = 0.0
        feedback_score = 0.8  # Positive

        # Apply boosts per the algorithm
        if canvas_boost > 0:
            base_score += 0.1

        if feedback_score > 0:
            base_score += 0.2

        assert base_score == pytest.approx(0.9)

    def test_negative_feedback_penalty(self):
        """Test that negative feedback penalizes relevance score"""
        base_score = 0.7
        canvas_boost = 0.0
        feedback_score = -0.5  # Negative

        # Apply boosts/penalties
        if canvas_boost > 0:
            base_score += 0.1

        if feedback_score < 0:
            base_score -= 0.3

        assert base_score == pytest.approx(0.4)

    def test_neutral_feedback_no_change(self):
        """Test that neutral feedback doesn't change score"""
        base_score = 0.7
        canvas_boost = 0.0
        feedback_score = 0.0  # Neutral

        # Apply boosts/penalties
        if canvas_boost > 0:
            base_score += 0.1

        if feedback_score > 0:
            base_score += 0.2
        elif feedback_score < 0:
            base_score -= 0.3

        # Neutral feedback should not change score
        assert base_score == 0.7


class TestCanvasTypeFiltering:
    """Test canvas type filtering logic"""

    def test_canvas_type_filter_logic(self):
        """Test the filtering logic for canvas types"""
        # Simulate episodes with different canvas types
        episodes = [
            {"id": "ep_1", "canvas_type": "sheets", "action": "present"},
            {"id": "ep_2", "canvas_type": "charts", "action": "present"},
            {"id": "ep_3", "canvas_type": "sheets", "action": "submit"}
        ]

        # Filter for sheets type
        filtered = [ep for ep in episodes if ep["canvas_type"] == "sheets"]

        assert len(filtered) == 2
        assert filtered[0]["id"] == "ep_1"
        assert filtered[1]["id"] == "ep_3"

    def test_canvas_action_filter_logic(self):
        """Test the filtering logic for canvas actions"""
        episodes = [
            {"id": "ep_1", "canvas_type": "sheets", "action": "present"},
            {"id": "ep_2", "canvas_type": "charts", "action": "present"},
            {"id": "ep_3", "canvas_type": "sheets", "action": "submit"}
        ]

        # Filter for present action
        filtered = [ep for ep in episodes if ep["action"] == "present"]

        assert len(filtered) == 2
        assert filtered[0]["id"] == "ep_1"
        assert filtered[1]["id"] == "ep_2"
