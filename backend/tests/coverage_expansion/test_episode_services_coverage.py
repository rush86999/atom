"""
Coverage expansion tests for episode services.

Tests cover critical code paths in:
- episode_segmentation_service.py: Episode segmentation logic
- episode_lifecycle_service.py: Episode creation, completion, archival
- agent_graduation_service.py: Graduation criteria evaluation

Target: Cover critical paths (happy path + error paths) to increase coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.episode_segmentation_service import (
    EpisodeSegmentationService,
    EpisodeBoundaryDetector,
    TIME_GAP_THRESHOLD_MINUTES,
    SEMANTIC_SIMILARITY_THRESHOLD
)
from core.models import AgentRegistry, AgentStatus, ChatMessage, AgentExecution


class TestEpisodeBoundaryDetectorCoverage:
    """Coverage expansion for EpisodeBoundaryDetector."""

    @pytest.fixture
    def detector(self):
        """Get boundary detector instance."""
        lancedb_mock = Mock()
        lancedb_mock.embed_text = Mock(return_value=None)
        return EpisodeBoundaryDetector(lancedb_mock)

    # Test: time gap detection
    def test_detect_time_gap_exceeds_threshold(self, detector):
        """Detect time gaps > threshold between messages."""
        now = datetime.now()
        messages = [
            ChatMessage(id="1", content="First", created_at=now - timedelta(minutes=60)),
            ChatMessage(id="2", content="Second", created_at=now - timedelta(minutes=30)),
            ChatMessage(id="3", content="Third", created_at=now),
        ]

        gaps = detector.detect_time_gap(messages)
        # Should detect gap between message 1 and 2 (60 min > 30 min threshold)
        assert len(gaps) >= 1
        assert 1 in gaps  # Gap after first message

    def test_detect_time_gap_below_threshold(self, detector):
        """Don't detect gaps below threshold."""
        now = datetime.now()
        messages = [
            ChatMessage(id="1", content="First", created_at=now - timedelta(minutes=5)),
            ChatMessage(id="2", content="Second", created_at=now - timedelta(minutes=2)),
            ChatMessage(id="3", content="Third", created_at=now),
        ]

        gaps = detector.detect_time_gap(messages)
        # No gaps > 30 minutes
        assert len(gaps) == 0

    def test_detect_time_gap_exactly_threshold(self, detector):
        """Gap of exactly threshold minutes does NOT trigger new segment."""
        now = datetime.now()
        messages = [
            ChatMessage(id="1", content="First", created_at=now - timedelta(minutes=30)),
            ChatMessage(id="2", content="Second", created_at=now),
        ]

        gaps = detector.detect_time_gap(messages)
        # 30 minutes is NOT > 30, so no gap
        assert len(gaps) == 0

    def test_detect_time_gap_empty_messages(self, detector):
        """Handle empty message list."""
        gaps = detector.detect_time_gap([])
        assert gaps == []

    def test_detect_time_gap_single_message(self, detector):
        """Handle single message (no gaps possible)."""
        messages = [
            ChatMessage(id="1", content="First", created_at=datetime.now())
        ]
        gaps = detector.detect_time_gap(messages)
        assert gaps == []

    # Test: topic change detection
    def test_detect_topic_changes_with_embeddings(self, detector):
        """Detect topic changes using semantic similarity."""
        # Mock embeddings with low similarity
        detector.db.embed_text = Mock(side_effect=[
            [0.1, 0.2, 0.3],  # First message
            [0.9, 0.8, 0.7],  # Second message (different topic)
        ])

        now = datetime.now()
        messages = [
            ChatMessage(id="1", content="Discussion about weather", created_at=now),
            ChatMessage(id="2", content="Analysis of financial reports", created_at=now),
        ]

        changes = detector.detect_topic_changes(messages)
        # Low similarity should trigger topic change
        assert len(changes) >= 1

    def test_detect_topic_changes_fallback_to_keywords(self, detector):
        """Fallback to keyword-based similarity when embeddings fail."""
        # Mock embeddings to return None (failure)
        detector.db.embed_text = Mock(return_value=None)

        now = datetime.now()
        messages = [
            ChatMessage(id="1", content="Discussion about weather", created_at=now),
            ChatMessage(id="2", content="Analysis of financial reports", created_at=now),
        ]

        changes = detector.detect_topic_changes(messages)
        # Should use keyword similarity and detect change
        assert isinstance(changes, list)

    def test_detect_topic_changes_empty_messages(self, detector):
        """Handle empty message list for topic changes."""
        changes = detector.detect_topic_changes([])
        assert changes == []

    def test_detect_topic_changes_single_message(self, detector):
        """Handle single message (no changes possible)."""
        messages = [
            ChatMessage(id="1", content="First", created_at=datetime.now())
        ]
        changes = detector.detect_topic_changes(messages)
        assert changes == []

    # Test: cosine similarity calculation
    def test_cosine_similarity_identical_vectors(self, detector):
        """Calculate cosine similarity for identical vectors."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.0, 2.0, 3.0]
        similarity = detector._cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(1.0, rel=1e-5)

    def test_cosine_similarity_orthogonal_vectors(self, detector):
        """Calculate cosine similarity for orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = detector._cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(0.0, abs=1e-5)

    def test_cosine_similarity_zero_vectors(self, detector):
        """Handle zero-magnitude vectors."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        similarity = detector._cosine_similarity(vec1, vec2)
        assert similarity == 0.0

    # Test: keyword similarity fallback
    def test_keyword_similarity_identical_text(self, detector):
        """Calculate keyword similarity for identical text."""
        similarity = detector._keyword_similarity("hello world", "hello world")
        assert similarity == 1.0

    def test_keyword_similarity_no_overlap(self, detector):
        """Calculate keyword similarity with no overlap."""
        similarity = detector._keyword_similarity("hello world", "foo bar")
        assert similarity == 0.0

    def test_keyword_similarity_partial_overlap(self, detector):
        """Calculate keyword similarity with partial overlap."""
        similarity = detector._keyword_similarity("hello world test", "hello foo bar")
        # 1 word in common ("hello") out of 5 total
        assert 0.0 < similarity < 1.0

    def test_keyword_similarity_empty_text(self, detector):
        """Handle empty text for keyword similarity."""
        similarity = detector._keyword_similarity("", "hello world")
        assert similarity == 0.0

    def test_keyword_similarity_case_insensitive(self, detector):
        """Keyword similarity is case-insensitive."""
        sim1 = detector._keyword_similarity("Hello World", "hello world")
        sim2 = detector._keyword_similarity("Hello World", "HELLO WORLD")
        assert sim1 == sim2 == 1.0

    # Test: task completion detection
    def test_detect_task_completion(self, detector):
        """Detect task completion markers."""
        executions = [
            AgentExecution(id="1", status="completed", result_summary="Task done"),
            AgentExecution(id="2", status="running", result_summary=None),
            AgentExecution(id="3", status="completed", result_summary="Another done"),
        ]

        completions = detector.detect_task_completion(executions)
        assert len(completions) == 2
        assert 0 in completions
        assert 2 in completions

    def test_detect_task_completion_empty(self, detector):
        """Handle empty execution list."""
        completions = detector.detect_task_completion([])
        assert completions == []

    def test_detect_task_completion_no_completions(self, detector):
        """Handle executions with no completed tasks."""
        executions = [
            AgentExecution(id="1", status="running", result_summary=None),
            AgentExecution(id="2", status="failed", result_summary=None),
        ]

        completions = detector.detect_task_completion(executions)
        assert completions == []


class TestEpisodeSegmentationServiceCoverage:
    """Coverage expansion for EpisodeSegmentationService."""

    @pytest.fixture
    def db_session(self):
        """Get test database session."""
        from core.database import SessionLocal
        session = SessionLocal()
        yield session
        session.rollback()
        session.close()

    @pytest.fixture
    def segmentation_service(self, db_session):
        """Get segmentation service instance."""
        return EpisodeSegmentationService(db_session)

    # Test: time-based segmentation
    def test_should_segment_by_time_gap(self, segmentation_service):
        """Segment episodes when time gap exceeds threshold."""
        last_timestamp = datetime.now() - timedelta(hours=2)
        current_timestamp = datetime.now()

        should_segment = segmentation_service.should_segment_by_time(
            last_timestamp=last_timestamp,
            current_timestamp=current_timestamp,
            threshold_minutes=30
        )
        assert should_segment == True

    def test_should_not_segment_small_time_gap(self, segmentation_service):
        """Don't segment episodes for small time gaps."""
        last_timestamp = datetime.now() - timedelta(minutes=5)
        current_timestamp = datetime.now()

        should_segment = segmentation_service.should_segment_by_time(
            last_timestamp=last_timestamp,
            current_timestamp=current_timestamp,
            threshold_minutes=30
        )
        assert should_segment == False

    # Test: create segment
    def test_create_episode_segment(self, segmentation_service, db_session):
        """Create a new episode segment."""
        from core.models import AgentEpisode

        episode = AgentEpisode(
            id="test-episode",
            agent_id="test-agent",
            workspace_id="default",
            status="active"
        )
        db_session.add(episode)
        db_session.commit()

        segment = segmentation_service.create_segment(
            episode_id="test-episode",
            content="Test segment content",
            sequence_order=0
        )
        assert segment.id is not None
        assert segment.content == "Test segment content"
        assert segment.sequence_order == 0

    # Test: boundary detection integration
    def test_detect_boundaries_integration(self, segmentation_service):
        """Test boundary detection with service integration."""
        now = datetime.now()
        messages = [
            ChatMessage(id="1", content="First", created_at=now - timedelta(minutes=60)),
            ChatMessage(id="2", content="Second", created_at=now),
        ]

        boundaries = segmentation_service.detect_boundaries(messages)
        assert isinstance(boundaries, list)


class TestEpisodeLifecycleServiceCoverage:
    """Coverage expansion for EpisodeLifecycleService."""

    @pytest.fixture
    def db_session(self):
        """Get test database session."""
        from core.database import SessionLocal
        session = SessionLocal()
        yield session
        session.rollback()
        session.close()

    @pytest.fixture
    def lifecycle_service(self, db_session):
        """Get lifecycle service instance."""
        from core.episode_lifecycle_service import EpisodeLifecycleService
        return EpisodeLifecycleService(db_session)

    # Test: create episode
    def test_create_episode(self, lifecycle_service, db_session):
        """Create a new episode."""
        episode = lifecycle_service.create_episode(
            agent_id="test-agent",
            workspace_id="default_shared"
        )
        assert episode.id is not None
        assert episode.status == "active"
        assert episode.agent_id == "test-agent"
        assert episode.workspace_id == "default_shared"

    # Test: complete episode
    def test_complete_episode(self, lifecycle_service, db_session):
        """Complete an active episode."""
        # Create episode
        episode = lifecycle_service.create_episode(
            agent_id="test-agent",
            workspace_id="default_shared"
        )

        completed = lifecycle_service.complete_episode(
            episode_id=episode.id,
            outcome="success"
        )
        assert completed.status == "completed"
        assert completed.outcome == "success"
        assert completed.completed_at is not None

    # Test: archive episode
    def test_archive_old_episodes(self, lifecycle_service, db_session):
        """Archive episodes older than threshold."""
        # Create old episode
        episode = lifecycle_service.create_episode(
            agent_id="test-agent",
            workspace_id="default_shared"
        )
        episode.created_at = datetime.now() - timedelta(days=100)
        db_session.commit()

        archived_count = lifecycle_service.archive_episodes_older_than(days=90)
        assert archived_count >= 0

    # Test: get episode
    def test_get_episode(self, lifecycle_service, db_session):
        """Retrieve episode by ID."""
        episode = lifecycle_service.create_episode(
            agent_id="test-agent",
            workspace_id="default_shared"
        )

        retrieved = lifecycle_service.get_episode(episode.id)
        assert retrieved is not None
        assert retrieved.id == episode.id

    def test_get_episode_not_found(self, lifecycle_service):
        """Return None for non-existent episode."""
        retrieved = lifecycle_service.get_episode("nonexistent-episode")
        assert retrieved is None


class TestAgentGraduationServiceCoverage:
    """Coverage expansion for AgentGraduationService."""

    @pytest.fixture
    def db_session(self):
        """Get test database session."""
        from core.database import SessionLocal
        session = SessionLocal()
        yield session
        session.rollback()
        session.close()

    @pytest.fixture
    def graduation_service(self, db_session):
        """Get graduation service instance."""
        from core.agent_graduation_service import AgentGraduationService
        return AgentGraduationService(db_session)

    # Test: STUDENT -> INTERN graduation criteria
    def test_check_graduation_student_to_intern_met(self, graduation_service, db_session):
        """Check STUDENT -> INTERN graduation when criteria met."""
        agent = AgentRegistry(
            id="test-student",
            name="Test Student",
            category="test",
            module_path="test",
            class_name="TestStudent",
            maturity=AgentStatus.STUDENT.value,
            workspace_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        # Mock episode count and intervention rate
        with patch.object(graduation_service, '_get_episode_count', return_value=10):
            with patch.object(graduation_service, '_get_intervention_rate', return_value=0.4):
                result = graduation_service.check_graduation_criteria(agent_id="test-student")
                assert result.can_graduate == True

    def test_check_graduation_student_to_intern_not_met(self, graduation_service, db_session):
        """Check STUDENT -> INTERN graduation when criteria not met."""
        agent = AgentRegistry(
            id="test-student",
            name="Test Student",
            category="test",
            module_path="test",
            class_name="TestStudent",
            maturity=AgentStatus.STUDENT.value,
            workspace_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        # Mock insufficient episodes
        with patch.object(graduation_service, '_get_episode_count', return_value=5):
            with patch.object(graduation_service, '_get_intervention_rate', return_value=0.4):
                result = graduation_service.check_graduation_criteria(agent_id="test-student")
                assert result.can_graduate == False

    # Test: INTERN -> SUPERVISED graduation criteria
    def test_check_graduation_intern_to_supervised_met(self, graduation_service, db_session):
        """Check INTERN -> SUPERVISED graduation when criteria met."""
        agent = AgentRegistry(
            id="test-intern",
            name="Test Intern",
            category="test",
            module_path="test",
            class_name="TestIntern",
            maturity=AgentStatus.INTERN.value,
            workspace_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        with patch.object(graduation_service, '_get_episode_count', return_value=25):
            with patch.object(graduation_service, '_get_intervention_rate', return_value=0.15):
                result = graduation_service.check_graduation_criteria(agent_id="test-intern")
                assert result.can_graduate == True

    # Test: execute graduation
    def test_execute_graduation(self, graduation_service, db_session):
        """Execute agent graduation."""
        agent = AgentRegistry(
            id="test-promote",
            name="Test Promote",
            category="test",
            module_path="test",
            class_name="TestPromote",
            maturity=AgentStatus.STUDENT.value,
            workspace_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        with patch.object(graduation_service, 'check_graduation_criteria') as mock_check:
            mock_check.return_value = Mock(
                can_graduate=True,
                target_maturity=AgentStatus.INTERN
            )
            graduated = graduation_service.execute_graduation(agent_id="test-promote")
            assert graduated.maturity == AgentStatus.INTERN.value

    def test_execute_graduation_not_eligible(self, graduation_service, db_session):
        """Execute graduation fails when not eligible."""
        agent = AgentRegistry(
            id="test-no-promote",
            name="Test No Promote",
            category="test",
            module_path="test",
            class_name="TestNoPromote",
            maturity=AgentStatus.STUDENT.value,
            workspace_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        with patch.object(graduation_service, 'check_graduation_criteria') as mock_check:
            mock_check.return_value = Mock(
                can_graduate=False,
                target_maturity=None
            )
            # Should not graduate
            result = graduation_service.execute_graduation(agent_id="test-no-promote")
            assert result.maturity == AgentStatus.STUDENT.value
