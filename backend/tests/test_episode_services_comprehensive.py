"""
Comprehensive integration tests for episode services.

Tests call actual service class methods to increase coverage metrics.
Target: 17-18 tests covering EpisodeSegmentationService, EpisodeRetrievalService, EpisodeLifecycleService.
"""

import pytest
from datetime import datetime, timezone, timedelta
from core.database import get_db_session, SessionLocal
from core.episode_segmentation_service import EpisodeSegmentationService
from core.episode_retrieval_service import EpisodeRetrievalService
from core.episode_lifecycle_service import EpisodeLifecycleService
from core.models import Episode, EpisodeSegment, ChatSession, ChatMessage, AgentRegistry, AgentExecution


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def db_session():
    """Create a fresh database session for each test"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def segmentation_service(db_session):
    """Create EpisodeSegmentationService instance"""
    return EpisodeSegmentationService(db_session)


@pytest.fixture
def retrieval_service(db_session):
    """Create EpisodeRetrievalService instance"""
    return EpisodeRetrievalService(db_session)


@pytest.fixture
def lifecycle_service(db_session):
    """Create EpisodeLifecycleService instance"""
    return EpisodeLifecycleService(db_session)


@pytest.fixture
def test_agent(db_session):
    """Create test agent for episode tests"""
    import uuid
    agent = AgentRegistry(
        id=f"test_agent_{uuid.uuid4().hex[:8]}",
        name="Test Episode Agent",
        status="AUTONOMOUS",
        category="general",
        module_path="test.module",
        class_name="TestAgent",
        description="Test agent for episode service integration tests"
    )
    db_session.add(agent)
    db_session.commit()
    return agent


@pytest.fixture
def test_user(db_session):
    """Create test user"""
    from core.models import User
    import uuid
    user = User(
        id=f"test_user_{uuid.uuid4().hex[:8]}",
        email=f"episode_{uuid.uuid4().hex[:8]}@test.com",
        role="member"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_session(db_session, test_user):
    """Create test chat session"""
    import uuid
    session = ChatSession(
        id=f"test_session_{uuid.uuid4().hex[:8]}",
        user_id=test_user.id,
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(session)
    db_session.commit()
    return session


# =============================================================================
# Episode Segmentation Service Tests
# =============================================================================

class TestEpisodeSegmentationService:
    """Integration tests for EpisodeSegmentationService"""

    def test_segmentation_detector_initialization(self, segmentation_service):
        """Test EpisodeBoundaryDetector initialization"""
        assert segmentation_service.detector is not None
        assert segmentation_service.lancedb is not None
        assert segmentation_service.byok_handler is not None
        assert segmentation_service.canvas_summary_service is not None

    def test_segmentation_topic_extraction(self, segmentation_service):
        """Test _extract_topics method"""
        messages = []
        for i in range(3):
            msg = ChatMessage(
                id=f"topic_msg_{i}",
                conversation_id="test",
                role="user",
                content=f"Discussion about important topics and subjects {i}",
                created_at=datetime.now(timezone.utc)
            )
            messages.append(msg)

        topics = segmentation_service._extract_topics(messages, [])

        assert isinstance(topics, list)
        # Should extract long words (>4 chars)
        assert any("discussion" in t or "important" in t for t in topics)

    def test_segmentation_entity_extraction(self, segmentation_service):
        """Test _extract_entities method"""
        messages = []
        msg = ChatMessage(
            id="entity_msg",
            conversation_id="test",
            role="user",
            content="Contact test@example.com or call 555-123-4567. Visit https://example.com",
            created_at=datetime.now(timezone.utc)
        )
        messages.append(msg)

        entities = segmentation_service._extract_entities(messages, [])

        assert isinstance(entities, list)
        # Should extract email
        assert any("test@example.com" in e for e in entities)
        # Should extract phone
        assert any("555-123-4567" in e or "555" in e for e in entities)
        # Should extract URL
        assert any("example.com" in e for e in entities)

    def test_segmentation_importance_calculation(self, segmentation_service):
        """Test _calculate_importance method"""
        # Few messages, no executions
        importance1 = segmentation_service._calculate_importance([], [])
        assert 0.0 <= importance1 <= 1.0

        # Many messages
        many_messages = [ChatMessage(
            id=f"msg_{i}",
            conversation_id="test",
            role="user",
            content=f"Message {i}",
            created_at=datetime.now(timezone.utc)
        ) for i in range(15)]

        importance2 = segmentation_service._calculate_importance(many_messages, [])
        assert importance2 > importance1  # More messages = higher importance

    def test_segmentation_duration_calculation(self, segmentation_service):
        """Test _calculate_duration method"""
        msg1 = ChatMessage(
            id="dur1",
            conversation_id="test",
            role="user",
            content="Start",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=5)
        )
        msg2 = ChatMessage(
            id="dur2",
            conversation_id="test",
            role="user",
            content="End",
            created_at=datetime.now(timezone.utc)
        )

        duration = segmentation_service._calculate_duration([msg1, msg2], [])

        assert duration is not None
        assert duration >= 250  # At least 4.1 minutes (250 seconds)
        assert duration <= 400  # Less than 6.6 minutes

    def test_segmentation_canvas_context_extraction(self, segmentation_service, test_session, test_user):
        """Test _extract_canvas_context method"""
        from core.models import CanvasAudit
        import uuid

        canvas = CanvasAudit(
            id=f"test_canvas_{uuid.uuid4().hex[:8]}",
            session_id=test_session.id,
            user_id=test_user.id,
            canvas_type="sheets",
            component_type="grid",
            component_name="DataGrid",
            action="present",
            audit_metadata={"revenue": 1000000, "approval_status": "approved"},
            created_at=datetime.now(timezone.utc)
        )
        segmentation_service.db.add(canvas)
        segmentation_service.db.commit()

        context = segmentation_service._extract_canvas_context([canvas])

        assert context is not None
        assert context["canvas_type"] == "sheets"
        assert "critical_data_points" in context
        assert context["critical_data_points"].get("revenue") == 1000000

    def test_segmentation_feedback_score_calculation(self, segmentation_service):
        """Test _calculate_feedback_score method"""
        from core.models import AgentFeedback

        feedback1 = AgentFeedback(
            id="fb1",
            agent_id="test_agent",
            feedback_type="thumbs_up",
            thumbs_up_down=True,
            created_at=datetime.now(timezone.utc)
        )
        feedback2 = AgentFeedback(
            id="fb2",
            agent_id="test_agent",
            feedback_type="rating",
            rating=5,
            created_at=datetime.now(timezone.utc)
        )

        score = segmentation_service._calculate_feedback_score([feedback1, feedback2])

        assert score is not None
        assert 0.0 <= score <= 1.0  # Normalized to 0-1 range
        assert score > 0.5  # Both positive feedbacks


# =============================================================================
# Episode Retrieval Service Tests
# =============================================================================

class TestEpisodeRetrievalService:
    """Integration tests for EpisodeRetrievalService"""

    def test_retrieval_service_initialization(self, retrieval_service):
        """Test EpisodeRetrievalService initialization"""
        assert retrieval_service.db is not None
        assert retrieval_service.lancedb is not None
        assert retrieval_service.governance is not None

    def test_retrieval_serialize_episode(self, retrieval_service, test_agent):
        """Test _serialize_episode method"""
        import uuid
        episode = Episode(
            id=f"serialize_test_ep_{uuid.uuid4().hex[:8]}",
            agent_id=test_agent.id,
            user_id="test_user",
            workspace_id="default",
            title="Serialization Test",
            description="Test episode serialization",
            status="completed",
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            topics=["test"],
            entities=["test"],
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            importance_score=0.8
        )
        retrieval_service.db.add(episode)
        retrieval_service.db.commit()

        serialized = retrieval_service._serialize_episode(episode)

        assert serialized["id"] == episode.id
        assert serialized["title"] == episode.title
        assert serialized["status"] == episode.status
        assert serialized["importance_score"] == 0.8
        assert "maturity_at_time" in serialized

    def test_retrieval_serialize_segment(self, retrieval_service):
        """Test _serialize_segment method"""
        import uuid
        segment = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id="test_ep",
            segment_type="conversation",
            sequence_order=0,
            content="Test segment content",
            content_summary="Test summary",
            source_type="chat_message",
            source_id="msg1",
            canvas_context={"canvas_type": "sheets"}
        )
        retrieval_service.db.add(segment)
        retrieval_service.db.commit()

        serialized = retrieval_service._serialize_segment(segment)

        assert serialized["id"] == segment.id
        assert serialized["segment_type"] == segment.segment_type
        assert serialized["content"] == segment.content
        assert "canvas_context" in serialized
        assert serialized["canvas_context"]["canvas_type"] == "sheets"


# =============================================================================
# Episode Lifecycle Service Tests
# =============================================================================

class TestEpisodeLifecycleService:
    """Integration tests for EpisodeLifecycleService"""

    def test_lifecycle_service_initialization(self, lifecycle_service):
        """Test EpisodeLifecycleService initialization"""
        assert lifecycle_service.db is not None
        assert lifecycle_service.lancedb is not None

    def test_lifecycle_decay_old_episodes(self, lifecycle_service, test_agent):
        """Test decay_old_episodes through EpisodeLifecycleService"""
        import asyncio
        import uuid

        # Create old episode (use naive datetime to match lifecycle service)
        old_episode = Episode(
            id=f"decay_test_ep_{uuid.uuid4().hex[:8]}",
            agent_id=test_agent.id,
            user_id="test_user",
            workspace_id="default",
            title="Decay Test Episode",
            description="Test episode for decay",
            status="completed",
            started_at=datetime.now() - timedelta(days=100),
            ended_at=datetime.now() - timedelta(days=100),
            topics=["test"],
            entities=["test"],
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            decay_score=1.0,
            access_count=0
        )
        lifecycle_service.db.add(old_episode)
        lifecycle_service.db.commit()

        # Apply decay
        result = asyncio.run(lifecycle_service.decay_old_episodes(days_threshold=90))

        assert "affected" in result
        assert "archived" in result
        assert result["affected"] >= 1

        # Verify decay score updated
        lifecycle_service.db.refresh(old_episode)
        assert old_episode.decay_score < 1.0  # Should be decayed
        assert old_episode.access_count >= 1  # Access count incremented

    def test_lifecycle_archive_to_cold_storage(self, lifecycle_service, test_agent):
        """Test archive_to_cold_storage through EpisodeLifecycleService"""
        import asyncio
        import uuid

        episode = Episode(
            id=f"archive_test_ep_{uuid.uuid4().hex[:8]}",
            agent_id=test_agent.id,
            user_id="test_user",
            workspace_id="default",
            title="Archive Test Episode",
            description="Test episode for archival",
            status="completed",
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            topics=["test"],
            entities=["test"],
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0
        )
        lifecycle_service.db.add(episode)
        lifecycle_service.db.commit()

        # Archive
        result = asyncio.run(lifecycle_service.archive_to_cold_storage(episode.id))

        assert result is True

        # Verify status updated
        lifecycle_service.db.refresh(episode)
        assert episode.status == "archived"
        assert episode.archived_at is not None

    def test_lifecycle_update_importance_scores(self, lifecycle_service, test_agent):
        """Test update_importance_scores through EpisodeLifecycleService"""
        import asyncio
        import uuid

        episode = Episode(
            id=f"importance_test_ep_{uuid.uuid4().hex[:8]}",
            agent_id=test_agent.id,
            user_id="test_user",
            workspace_id="default",
            title="Importance Test Episode",
            description="Test episode for importance update",
            status="completed",
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            topics=["test"],
            entities=["test"],
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            importance_score=0.5
        )
        lifecycle_service.db.add(episode)
        lifecycle_service.db.commit()

        # Update importance with positive feedback
        result = asyncio.run(lifecycle_service.update_importance_scores(
            episode_id=episode.id,
            user_feedback=1.0  # Maximum positive feedback
        ))

        assert result is True

        # Verify importance updated
        lifecycle_service.db.refresh(episode)
        assert episode.importance_score > 0.5  # Should increase

    def test_lifecycle_batch_update_access_counts(self, lifecycle_service, test_agent):
        """Test batch_update_access_counts through EpisodeLifecycleService"""
        import asyncio
        import uuid

        # Create test episodes
        ep1 = Episode(
            id=f"access_ep1_{uuid.uuid4().hex[:8]}",
            agent_id=test_agent.id,
            user_id="test_user",
            workspace_id="default",
            title="Access Test 1",
            description="Test",
            status="completed",
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            topics=["test"],
            entities=["test"],
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            access_count=0
        )
        ep2 = Episode(
            id=f"access_ep2_{uuid.uuid4().hex[:8]}",
            agent_id=test_agent.id,
            user_id="test_user",
            workspace_id="default",
            title="Access Test 2",
            description="Test",
            status="completed",
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            topics=["test"],
            entities=["test"],
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            access_count=0
        )
        lifecycle_service.db.add(ep1)
        lifecycle_service.db.add(ep2)
        lifecycle_service.db.commit()

        # Batch update access counts
        result = asyncio.run(lifecycle_service.batch_update_access_counts([
            ep1.id,
            ep2.id
        ]))

        assert "updated" in result
        assert result["updated"] == 2

        # Verify counts incremented
        lifecycle_service.db.refresh(ep1)
        lifecycle_service.db.refresh(ep2)
        assert ep1.access_count == 1
        assert ep2.access_count == 1
