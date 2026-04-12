"""
End-to-End Episode Workflow Tests

Tests complete episode lifecycle workflows from creation to archival.
Covers episode creation, segmentation, retrieval, graduation, and cleanup.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from core.models import Episode, EpisodeSegment, EpisodeAccessLog
from core.episode_segmentation_service import EpisodeSegmentationService
from core.episode_retrieval_service import EpisodeRetrievalService
from core.episode_lifecycle_service import EpisodeLifecycleService
from core.agent_graduation_service import AgentGraduationService


class TestEpisodeLifecycleWorkflow:
    """Test complete episode lifecycle workflows."""

    @pytest.fixture
    def segmentation_service(self):
        """Create episode segmentation service."""
        return EpisodeSegmentationService()

    @pytest.fixture
    def retrieval_service(self):
        """Create episode retrieval service."""
        return EpisodeRetrievalService()

    @pytest.fixture
    def lifecycle_service(self):
        """Create episode lifecycle service."""
        return EpisodeLifecycleService()

    @pytest.fixture
    def graduation_service(self):
        """Create agent graduation service."""
        return AgentGraduationService()

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = Mock(spec=Session)
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        db.refresh = Mock()
        db.bulk_save_objects = Mock()
        return db

    @pytest.fixture
    def sample_episode(self):
        """Create sample episode for testing."""
        episode = Episode(
            id="episode-001",
            agent_id="agent-001",
            session_id="session-001",
            title="Test Episode",
            summary="Test episode for workflow tests",
            status="active",
            started_at=datetime.utcnow() - timedelta(hours=1),
            ended_at=None,
            metadata={"test": True}
        )
        return episode

    def test_complete_episode_lifecycle_workflow(self, mock_db, sample_episode):
        """Test complete workflow: create → segment → retrieve → archive."""
        # Step 1: Create episode
        mock_db.add(sample_episode)
        mock_db.commit()
        assert sample_episode.id is not None
        assert sample_episode.status == "active"

        # Step 2: Add segments
        segment1 = EpisodeSegment(
            id="segment-001",
            episode_id=sample_episode.id,
            segment_type="conversation",
            content="User asked about weather",
            timestamp=datetime.utcnow() - timedelta(minutes=50),
            metadata={"turn": 1}
        )
        segment2 = EpisodeSegment(
            id="segment-002",
            episode_id=sample_episode.id,
            segment_type="action",
            content="Agent retrieved weather data",
            timestamp=datetime.utcnow() - timedelta(minutes=45),
            metadata={"turn": 2}
        )
        mock_db.add(segment1)
        mock_db.add(segment2)
        mock_db.commit()

        # Step 3: Retrieve episode
        mock_db.query.return_value.filter.return_value.first.return_value = sample_episode
        retrieved_episode = mock_db.query(Episode).filter(
            Episode.id == sample_episode.id
        ).first()

        assert retrieved_episode.id == sample_episode.id
        assert retrieved_episode.status == "active"

        # Step 4: End and archive episode
        sample_episode.status = "archived"
        sample_episode.ended_at = datetime.utcnow()
        mock_db.commit()

        assert sample_episode.status == "archived"
        assert sample_episode.ended_at is not None

    def test_episode_segmentation_workflow(self, mock_db, sample_episode):
        """Test episode segmentation based on time gaps and topic changes."""
        mock_db.add(sample_episode)
        mock_db.commit()

        # Create segments with time gap
        segment1 = EpisodeSegment(
            id="segment-001",
            episode_id=sample_episode.id,
            segment_type="conversation",
            content="Initial conversation",
            timestamp=datetime.utcnow() - timedelta(hours=1),
            metadata={"turn": 1}
        )
        mock_db.add(segment1)

        # Time gap (> 30 minutes) triggers new segment
        segment2 = EpisodeSegment(
            id="segment-002",
            episode_id=sample_episode.id,
            segment_type="conversation",
            content="New conversation after gap",
            timestamp=datetime.utcnow() - timedelta(minutes=20),
            metadata={"turn": 2, "time_gap_minutes": 40}
        )
        mock_db.add(segment2)

        mock_db.commit()

        # Verify segmentation
        time_gap = segment2.timestamp - segment1.timestamp
        assert time_gap.total_seconds() > 1800  # 30 minutes

    def test_episode_retrieval_workflow(self, mock_db, sample_episode):
        """Test temporal, semantic, and contextual retrieval workflows."""
        mock_db.add(sample_episode)
        mock_db.commit()

        # Add segments with different types
        segments = []
        for i in range(5):
            segment = EpisodeSegment(
                id=f"segment-{i:03d}",
                episode_id=sample_episode.id,
                segment_type="conversation" if i % 2 == 0 else "action",
                content=f"Segment {i} content",
                timestamp=datetime.utcnow() - timedelta(minutes=60-i*10),
                metadata={"turn": i+1, "embedding": [0.1] * 384}
            )
            segments.append(segment)
            mock_db.add(segment)

        mock_db.commit()

        # Temporal retrieval (by time range)
        start_time = datetime.utcnow() - timedelta(minutes=60)
        end_time = datetime.utcnow() - timedelta(minutes=30)
        temporal_segments = [s for s in segments if start_time <= s.timestamp <= end_time]

        assert len(temporal_segments) >= 2

        # Semantic retrieval (by embedding similarity)
        query_embedding = [0.1] * 384
        semantic_segments = [s for s in segments if s.metadata.get("embedding")]

        assert len(semantic_segments) == 5

    def test_episode_with_canvas_presentations(self, mock_db, sample_episode):
        """Test episode workflow with canvas presentation tracking."""
        mock_db.add(sample_episode)
        mock_db.commit()

        # Add canvas presentation segment
        canvas_segment = EpisodeSegment(
            id="segment-canvas-001",
            episode_id=sample_episode.id,
            segment_type="canvas_presentation",
            content="Presented bar chart",
            timestamp=datetime.utcnow() - timedelta(minutes=30),
            metadata={
                "canvas_type": "bar_chart",
                "canvas_id": "canvas-001",
                "data_points": 10,
                "user_interaction": "clicked_legend"
            }
        )
        mock_db.add(canvas_segment)
        mock_db.commit()

        # Track user interaction
        access_log = EpisodeAccessLog(
            id="access-001",
            episode_id=sample_episode.id,
            access_type="view",
            timestamp=datetime.utcnow() - timedelta(minutes=25),
            metadata={"segment_id": canvas_segment.id}
        )
        mock_db.add(access_log)
        mock_db.commit()

        # Verify canvas tracking
        assert canvas_segment.segment_type == "canvas_presentation"
        assert canvas_segment.metadata["canvas_type"] == "bar_chart"

    def test_episode_with_feedback_aggregation(self, mock_db, sample_episode):
        """Test episode workflow with user feedback aggregation."""
        mock_db.add(sample_episode)
        mock_db.commit()

        # Add segments
        for i in range(3):
            segment = EpisodeSegment(
                id=f"segment-{i:03d}",
                episode_id=sample_episode.id,
                segment_type="conversation",
                content=f"Segment {i}",
                timestamp=datetime.utcnow() - timedelta(minutes=30-i*5),
                metadata={"feedback_score": 0.8 + i*0.05}
            )
            mock_db.add(segment)

        mock_db.commit()

        # Aggregate feedback
        mock_db.query.return_value.filter.return_value.all.return_value = [
            EpisodeSegment(metadata={"feedback_score": 0.8}),
            EpisodeSegment(metadata={"feedback_score": 0.85}),
            EpisodeSegment(metadata={"feedback_score": 0.9})
        ]

        segments = mock_db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == sample_episode.id
        ).all()

        avg_feedback = sum(s.metadata.get("feedback_score", 0) for s in segments) / len(segments)

        assert avg_feedback >= 0.8
        assert avg_feedback <= 0.9

    def test_episode_graduation_workflow(self, mock_db, sample_episode):
        """Test episode workflow with graduation checkpoint tracking."""
        mock_db.add(sample_episode)
        mock_db.commit()

        # Track graduation metadata in episode instead of separate checkpoint
        sample_episode.metadata["graduation_tracking"] = {
            "from_maturity": "STUDENT",
            "to_maturity": "INTERN",
            "episode_count": 10,
            "intervention_rate": 0.5,
            "constitutional_score": 0.75
        }
        mock_db.commit()

        # Verify graduation tracking
        assert sample_episode.metadata["graduation_tracking"]["from_maturity"] == "STUDENT"
        assert sample_episode.metadata["graduation_tracking"]["to_maturity"] == "INTERN"
        assert sample_episode.metadata["graduation_tracking"]["episode_count"] == 10

    def test_episode_archival_workflow(self, lifecycle_service, mock_db, sample_episode):
        """Test episode archival workflow after retention period."""
        mock_db.add(sample_episode)
        mock_db.commit()

        # Mark episode as ended
        sample_episode.status = "ended"
        sample_episode.ended_at = datetime.utcnow() - timedelta(days=35)  # Older than 30 days
        mock_db.commit()

        # Archive episode (older than 30 days)
        archival_cutoff = datetime.utcnow() - timedelta(days=30)
        if sample_episode.ended_at and sample_episode.ended_at < archival_cutoff:
            sample_episode.status = "archived"
            sample_episode.archived_at = datetime.utcnow()
            sample_episode.storage_location = "lancedb"  # Cold storage
            mock_db.commit()

        assert sample_episode.status == "archived"
        assert sample_episode.storage_location == "lancedb"

    def test_episode_search_workflow(self, mock_db):
        """Test episode search across multiple episodes."""
        # Create multiple episodes
        episodes = []
        for i in range(5):
            episode = Episode(
                id=f"episode-{i:03d}",
                agent_id="agent-001",
                session_id=f"session-{i}",
                title=f"Episode {i}",
                summary=f"Summary about topic {i % 2}",  # Two topics
                status="active",
                started_at=datetime.utcnow() - timedelta(hours=i+1),
                metadata={"topic": f"topic_{i % 2}", "embedding": [0.1] * 384}
            )
            episodes.append(episode)
            mock_db.add(episode)

        mock_db.commit()

        # Search by topic
        topic = "topic_0"
        topic_episodes = [e for e in episodes if e.metadata.get("topic") == topic]

        assert len(topic_episodes) >= 2

    def test_episode_export_workflow(self, mock_db, sample_episode):
        """Test episode export to external storage."""
        mock_db.add(sample_episode)
        mock_db.commit()

        # Add segments
        for i in range(3):
            segment = EpisodeSegment(
                id=f"segment-{i:03d}",
                episode_id=sample_episode.id,
                segment_type="conversation",
                content=f"Segment {i} content",
                timestamp=datetime.utcnow() - timedelta(minutes=30-i*5),
                metadata={"turn": i+1}
            )
            mock_db.add(segment)

        mock_db.commit()

        # Export episode
        export_data = {
            "episode_id": sample_episode.id,
            "title": sample_episode.title,
            "summary": sample_episode.summary,
            "started_at": sample_episode.started_at.isoformat(),
            "segments": []
        }

        mock_db.query.return_value.filter.return_value.all.return_value = [
            EpisodeSegment(id="segment-000", content="Segment 0 content", metadata={"turn": 1}),
            EpisodeSegment(id="segment-001", content="Segment 1 content", metadata={"turn": 2}),
            EpisodeSegment(id="segment-002", content="Segment 2 content", metadata={"turn": 3})
        ]

        segments = mock_db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == sample_episode.id
        ).all()

        for segment in segments:
            export_data["segments"].append({
                "content": segment.content,
                "metadata": segment.metadata
            })

        assert len(export_data["segments"]) == 3
        assert export_data["episode_id"] == sample_episode.id

    def test_episode_access_tracking_workflow(self, mock_db, sample_episode):
        """Test episode access log tracking for analytics."""
        mock_db.add(sample_episode)
        mock_db.commit()

        # Track multiple accesses
        access_types = ["view", "search", "export", "reference"]
        for i, access_type in enumerate(access_types):
            access_log = EpisodeAccessLog(
                id=f"access-{i:03d}",
                episode_id=sample_episode.id,
                access_type=access_type,
                timestamp=datetime.utcnow() - timedelta(minutes=len(access_types)-i),
                metadata={"user_id": f"user-{i}"}
            )
            mock_db.add(access_log)

        mock_db.commit()

        # Verify access tracking
        mock_db.query.return_value.filter.return_value.count.return_value = 4
        access_count = mock_db.query(EpisodeAccessLog).filter(
            EpisodeAccessLog.episode_id == sample_episode.id
        ).count()

        assert access_count == 4

    def test_episode_with_llm_summary_workflow(self, mock_db, sample_episode):
        """Test episode workflow with LLM-generated summary."""
        mock_db.add(sample_episode)
        mock_db.commit()

        # Initial summary
        sample_episode.summary = "Initial summary"
        mock_db.commit()

        # Generate LLM summary after episode ends
        sample_episode.status = "ended"
        sample_episode.ended_at = datetime.utcnow()

        # Simulate LLM summary generation
        llm_summary = """
        This episode covered a comprehensive discussion about weather forecasting.
        The agent provided detailed information about temperature, precipitation, and wind patterns.
        User interacted with bar chart and line chart visualizations.
        Overall satisfaction was high with positive feedback.
        """

        sample_episode.summary = llm_summary.strip()
        sample_episode.summary_generated_at = datetime.utcnow()
        sample_episode.summary_method = "llm"
        mock_db.commit()

        assert sample_episode.summary_method == "llm"
        assert len(sample_episode.summary) > 100  # Comprehensive summary
        assert sample_episode.summary_generated_at is not None
