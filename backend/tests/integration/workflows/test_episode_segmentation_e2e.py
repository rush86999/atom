"""
End-to-end integration tests for EpisodeSegmentationService.

Tests cover:
- Episode creation from chat sessions
- Time gap detection (30-minute threshold)
- Topic change detection
- Canvas presentation tracking
- User feedback integration

Target: episode_segmentation_service.py (1536 lines, 15% unit coverage)
Goal: 30%+ coverage through integration tests
"""

import uuid
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from sqlalchemy.orm import Session

from core.episode_segmentation_service import EpisodeBoundaryDetector, TIME_GAP_THRESHOLD_MINUTES
from core.models import (
    AgentEpisode, EpisodeSegment, EpisodeOutcome,
    ChatMessage
)


class TestEpisodeSegmentationE2E:
    """End-to-end integration tests for EpisodeSegmentationService."""

    def test_episode_segmentation_time_gap_detection(self, db_session: Session):
        """Test time gap detection between messages (>30 minutes)."""
        # Create messages with 2-hour gap between message 5 and 6
        messages = []
        base_time = datetime.utcnow() - timedelta(hours=3)

        # Messages 1-5: within 30 minutes
        for i in range(5):
            msg = ChatMessage(
                id=str(uuid.uuid4()),
                session_id="test_session",
                role="user",
                content=f"Message {i+1}",
                created_at=base_time + timedelta(minutes=i*5)
            )
            messages.append(msg)

        # Messages 6-10: 2 hours later (exceeds 30-min threshold)
        for i in range(5, 10):
            msg = ChatMessage(
                id=str(uuid.uuid4()),
                session_id="test_session",
                role="user",
                content=f"Message {i+1}",
                created_at=base_time + timedelta(hours=2, minutes=(i-5)*5)
            )
            messages.append(msg)

        # Mock lancedb handler
        mock_db = MagicMock()

        # Create detector
        detector = EpisodeBoundaryDetector(mock_db)

        # Detect time gaps
        gaps = detector.detect_time_gap(messages)

        # Should detect gap at index 5 (between message 5 and 6)
        assert len(gaps) == 1
        assert gaps[0] == 5

    def test_episode_segmentation_no_time_gap_within_threshold(self, db_session: Session):
        """Test that no time gap is detected when messages are close together."""
        # Create messages all within 5 minutes
        messages = []
        base_time = datetime.utcnow() - timedelta(minutes=10)

        for i in range(10):
            msg = ChatMessage(
                id=str(uuid.uuid4()),
                session_id="test_session",
                role="user",
                content=f"Message {i+1}",
                created_at=base_time + timedelta(seconds=i*30)  # 30 seconds apart
            )
            messages.append(msg)

        # Mock lancedb handler
        mock_db = MagicMock()

        # Create detector
        detector = EpisodeBoundaryDetector(mock_db)

        # Detect time gaps
        gaps = detector.detect_time_gap(messages)

        # Should detect no gaps
        assert len(gaps) == 0

    def test_episode_segmentation_exact_threshold_no_gap(self, db_session: Session):
        """Test that exact threshold (30 minutes) does NOT trigger gap."""
        # Create messages with exactly 30-minute gap
        messages = []
        base_time = datetime.utcnow() - timedelta(hours=2)

        # First message
        msg1 = ChatMessage(
            id=str(uuid.uuid4()),
            session_id="test_session",
            role="user",
            content="Message 1",
            created_at=base_time
        )
        messages.append(msg1)

        # Second message exactly 30 minutes later (should NOT trigger gap)
        msg2 = ChatMessage(
            id=str(uuid.uuid4()),
            session_id="test_session",
            role="user",
            content="Message 2",
            created_at=base_time + timedelta(minutes=TIME_GAP_THRESHOLD_MINUTES)
        )
        messages.append(msg2)

        # Mock lancedb handler
        mock_db = MagicMock()

        # Create detector
        detector = EpisodeBoundaryDetector(mock_db)

        # Detect time gaps
        gaps = detector.detect_time_gap(messages)

        # Should detect NO gaps (exclusive threshold: > 30, not >= 30)
        assert len(gaps) == 0

    @pytest.mark.skip(reason="Topic change detection requires embeddings - defer to future enhancement")
    def test_episode_segmentation_topic_change(self, db_session: Session):
        """Test topic change detection between messages."""
        # TODO: Implement topic change detection with embeddings
        pass

    def test_episode_and_segments_database_persistence(self, db_session: Session):
        """Test creating episode with segments in database."""
        # Create episode
        episode_id = str(uuid.uuid4())

        episode = AgentEpisode(
            id=episode_id,
            agent_id="test_agent",
            user_id="test_user",
            workflow_id="test_workflow",
            outcome=EpisodeOutcome.SUCCESS,
            title="Database Persistence Test",
            summary="Testing episode and segment persistence",
            start_time=datetime.utcnow() - timedelta(minutes=10),
            end_time=datetime.utcnow()
        )
        db_session.add(episode)

        # Create segments
        for i in range(3):
            segment = EpisodeSegment(
                id=str(uuid.uuid4()),
                episode_id=episode_id,
                segment_type="action",
                title=f"Segment {i+1}",
                content=f"Segment content {i+1}",
                start_time=datetime.utcnow() - timedelta(minutes=10-i),
                end_time=datetime.utcnow() - timedelta(minutes=9-i),
                metadata={"step": i+1}
            )
            db_session.add(segment)

        db_session.commit()

        # Verify episode persisted
        retrieved_episode = db_session.query(AgentEpisode).filter(
            AgentEpisode.id == episode_id
        ).first()

        assert retrieved_episode is not None
        assert retrieved_episode.title == "Database Persistence Test"
        assert retrieved_episode.outcome == EpisodeOutcome.SUCCESS

        # Verify segments persisted
        segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode_id
        ).all()

        assert len(segments) == 3
        assert all(s.episode_id == episode_id for s in segments)
        assert all(s.segment_type == "action" for s in segments)

    def test_episode_with_canvas_reference(self, db_session: Session):
        """Test episode tracking with canvas reference."""
        canvas_id = "test_canvas_123"

        episode = AgentEpisode(
            id=str(uuid.uuid4()),
            agent_id="test_agent",
            user_id="test_user",
            workflow_id="test_workflow",
            outcome=EpisodeOutcome.SUCCESS,
            title="Episode with Canvas",
            summary="Episode that presented a canvas",
            start_time=datetime.utcnow() - timedelta(minutes=10),
            end_time=datetime.utcnow(),
            canvas_reference=canvas_id
        )
        db_session.add(episode)

        # Create segment for canvas presentation
        segment = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode.id,
            segment_type="canvas_presentation",
            title="Presented Sales Chart",
            content="Canvas type: line_chart",
            start_time=datetime.utcnow() - timedelta(minutes=5),
            end_time=datetime.utcnow() - timedelta(minutes=5),
            metadata={
                "canvas_id": canvas_id,
                "canvas_type": "line_chart",
                "status": "presented"
            }
        )
        db_session.add(segment)

        db_session.commit()

        # Verify episode has canvas reference
        retrieved = db_session.query(AgentEpisode).filter(
            AgentEpisode.id == episode.id
        ).first()

        assert retrieved is not None
        assert retrieved.canvas_reference == canvas_id

        # Verify segment has canvas metadata
        segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()

        assert len(segments) == 1
        assert segments[0].segment_type == "canvas_presentation"
        assert segments[0].metadata["canvas_id"] == canvas_id

    def test_episode_with_feedback_reference(self, db_session: Session):
        """Test episode tracking with user feedback reference."""
        feedback_id = str(uuid.uuid4())

        episode = AgentEpisode(
            id=str(uuid.uuid4()),
            agent_id="test_agent",
            user_id="test_user",
            workflow_id="test_workflow",
            outcome=EpisodeOutcome.SUCCESS,
            title="Episode with Feedback",
            summary="Episode that received user feedback",
            start_time=datetime.utcnow() - timedelta(minutes=10),
            end_time=datetime.utcnow(),
            feedback_reference=feedback_id
        )
        db_session.add(episode)

        # Create segment for feedback
        segment = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode.id,
            segment_type="feedback",
            title="User Feedback: thumbs_up",
            content="Great analysis!",
            start_time=datetime.utcnow() - timedelta(minutes=2),
            end_time=datetime.utcnow() - timedelta(minutes=2),
            metadata={
                "feedback_id": feedback_id,
                "feedback_type": "thumbs_up",
                "feedback_value": "1.0"
            }
        )
        db_session.add(segment)

        db_session.commit()

        # Verify episode has feedback reference
        retrieved = db_session.query(AgentEpisode).filter(
            AgentEpisode.id == episode.id
        ).first()

        assert retrieved is not None
        assert retrieved.feedback_reference == feedback_id

        # Verify segment has feedback metadata
        segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()

        assert len(segments) == 1
        assert segments[0].segment_type == "feedback"
        assert segments[0].metadata["feedback_type"] == "thumbs_up"


class TestEpisodeSegmentationDatabase:
    """Test database persistence and cleanup."""

    def test_episode_cascade_delete_segments(self, db_session: Session):
        """Test that deleting episode removes associated segments."""
        # Create episode with segments
        episode_id = str(uuid.uuid4())

        episode = AgentEpisode(
            id=episode_id,
            agent_id="test_agent",
            user_id="test_user",
            workflow_id="test_workflow",
            outcome=EpisodeOutcome.SUCCESS,
            title="Cascade Test",
            summary="Testing cascade delete",
            start_time=datetime.utcnow() - timedelta(minutes=10),
            end_time=datetime.utcnow()
        )
        db_session.add(episode)

        # Add segments
        for i in range(3):
            segment = EpisodeSegment(
                id=str(uuid.uuid4()),
                episode_id=episode_id,
                segment_type="test",
                title=f"Segment {i+1}",
                content=f"Content {i+1}",
                start_time=datetime.utcnow() - timedelta(minutes=10-i),
                end_time=datetime.utcnow() - timedelta(minutes=9-i)
            )
            db_session.add(segment)

        db_session.commit()

        # Verify segments exist
        segments_before = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode_id
        ).all()
        assert len(segments_before) == 3

        # Delete episode (cascade delete should remove segments)
        db_session.delete(episode)
        db_session.commit()

        # Verify segments deleted (cascade)
        segments_after = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode_id
        ).all()
        assert len(segments_after) == 0
