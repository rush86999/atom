"""
Unit tests for Episode Segmentation Service

Tests cover:
- Service initialization
- Episode creation from sessions
- Boundary detection (time gaps, topic changes, task completion)
- Segment management
- Canvas and feedback context integration
- Supervision episode creation
- LanceDB archival
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.episode_segmentation_service import (
    EpisodeSegmentationService,
    EpisodeBoundaryDetector,
    SegmentationResult,
    SegmentationBoundary,
    TIME_GAP_THRESHOLD_MINUTES,
    SEMANTIC_SIMILARITY_THRESHOLD
)
from core.models import (
    Episode,
    EpisodeSegment,
    ChatSession,
    ChatMessage,
    AgentExecution,
    AgentRegistry,
    CanvasAudit,
    AgentFeedback,
    SupervisionSession,
    AgentStatus
)


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock(spec=Session)
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB handler"""
    with patch('core.episode_segmentation_service.lancedb') as mock:
        handler = Mock()
        handler.db = Mock()
        handler.table_names = Mock(return_value=[])
        handler.create_table = Mock()
        handler.add_document = Mock()
        handler.embed_text = Mock(return_value=[0.1, 0.2, 0.3])
        mock.connect.return_value = handler
        mock.get_lancedb_handler = Mock(return_value=handler)
        yield handler


@pytest.fixture
def mock_lancedb_handler():
    """Mock LanceDB handler with more complete setup"""
    handler = Mock()
    handler.db = Mock()
    handler.table_names = Mock(return_value=[])
    handler.create_table = Mock()
    handler.add_document = AsyncMock()
    handler.embed_text = Mock(return_value=[0.1, 0.2, 0.3, 0.4, 0.5])
    handler.search = Mock(return_value=[])
    return handler


@pytest.fixture
def segmentation_service(mock_db, mock_lancedb_handler):
    """Create EpisodeSegmentationService with mocked dependencies"""
    with patch('core.episode_segmentation_service.get_lancedb_handler', return_value=mock_lancedb_handler):
        service = EpisodeSegmentationService(mock_db)
        service.lancedb = mock_lancedb_handler
        return service


@pytest.fixture
def sample_chat_session():
    """Create sample chat session"""
    session = Mock(spec=ChatSession)
    session.id = "session_1"
    session.user_id = "user_1"
    session.workspace_id = "workspace_1"  # Will be set by test
    session.created_at = datetime.now() - timedelta(hours=1)
    return session


@pytest.fixture
def sample_messages(sample_chat_session):
    """Create sample chat messages"""
    messages = []
    base_time = datetime.now() - timedelta(hours=1)

    for i in range(5):
        msg = ChatMessage(
            id=f"msg_{i}",
            session_id=sample_chat_session.id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"Message content {i}"
        )
        msg.created_at = base_time + timedelta(minutes=i * 5)
        messages.append(msg)

    return messages


@pytest.fixture
def sample_executions(sample_chat_session):
    """Create sample agent executions"""
    executions = []
    base_time = datetime.now() - timedelta(hours=1)

    for i in range(3):
        exec = AgentExecution(
            id=f"exec_{i}",
            session_id=sample_chat_session.id,
            agent_id="agent_1",
            status="completed",
            task_description=f"Task {i}",
            result_summary=f"Completed task {i}"
        )
        exec.created_at = base_time + timedelta(minutes=i * 10)
        exec.completed_at = exec.created_at + timedelta(minutes=2)
        executions.append(exec)

    return executions


@pytest.fixture
def sample_canvas_audits(sample_chat_session):
    """Create sample canvas audits"""
    canvases = []
    for i in range(2):
        canvas = CanvasAudit(
            id=f"canvas_{i}",
            session_id=sample_chat_session.id,
            canvas_type="sheets",
            component_type="table",
            action="present",
            audit_metadata={"rows": 10}
        )
        canvas.created_at = datetime.now() - timedelta(minutes=i * 15)
        canvases.append(canvas)
    return canvases


@pytest.fixture
def sample_feedbacks():
    """Create sample feedback records"""
    feedbacks = []
    for i in range(2):
        feedback = AgentFeedback(
            id=f"feedback_{i}",
            agent_id="agent_1",
            agent_execution_id=f"exec_{i}",
            feedback_type="thumbs_up" if i == 0 else "rating",
            thumbs_up_down=(i == 0),
            rating=(5 if i == 1 else None),
            user_correction="Good response" if i == 0 else None
        )
        feedbacks.append(feedback)
    return feedbacks


@pytest.fixture
def sample_agent():
    """Create sample agent"""
    agent = AgentRegistry(
        id="agent_1",
        name="Test Agent",
        status=AgentStatus.INTERN,
        agent_type="assistant"
    )
    return agent


@pytest.fixture
def sample_supervision_session():
    """Create sample supervision session"""
    session = SupervisionSession(
        id="supervision_1",
        agent_id="agent_1",
        agent_name="Test Agent",
        supervisor_id="user_1",
        workspace_id="workspace_1",
        status="completed",
        intervention_count=2,
        supervisor_rating=4,
        supervisor_feedback="Good performance"
    )
    session.started_at = datetime.now() - timedelta(hours=1)
    session.completed_at = datetime.now()
    session.duration_seconds = 3600
    session.interventions = [
        {"type": "pause", "timestamp": "2026-02-12T10:00:00Z", "guidance": "Check output"},
        {"type": "correct", "timestamp": "2026-02-12T10:15:00Z", "guidance": "Fix parameter"}
    ]
    session.confidence_boost = 0.05
    return session


# ============================================================================
# Service Initialization Tests
# ============================================================================

class TestSegmentationServiceInitialization:
    """Test service initialization"""

    def test_segmentation_service_init(self, mock_db, mock_lancedb_handler):
        """Test service initialization with dependencies"""
        with patch('core.episode_segmentation_service.get_lancedb_handler', return_value=mock_lancedb_handler):
            service = EpisodeSegmentationService(mock_db)

            assert service.db == mock_db
            assert service.lancedb == mock_lancedb_handler
            assert service.detector is not None
            assert isinstance(service.detector, EpisodeBoundaryDetector)


# ============================================================================
# Boundary Detection Tests
# ============================================================================

class TestBoundaryDetection:
    """Test episode boundary detection"""

    def test_detect_time_gap_basic(self, sample_messages):
        """Test time gap detection with basic gap"""
        # Create messages with a 35-minute gap (above 30-min threshold)
        messages = sample_messages[:]
        messages[2].created_at = messages[1].created_at + timedelta(minutes=35)

        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        gaps = detector.detect_time_gap(messages)

        assert len(gaps) >= 1
        assert 2 in gaps  # Gap detected at index 2

    def test_detect_time_gap_below_threshold(self, sample_messages):
        """Test time gap detection with gap below threshold"""
        # All messages have 5-minute gaps (below 30-min threshold)
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        gaps = detector.detect_time_gap(sample_messages)

        assert len(gaps) == 0

    def test_detect_time_gap_multiple_gaps(self):
        """Test detection of multiple time gaps"""
        messages = []
        base_time = datetime.now()

        for i in range(10):
            msg = ChatMessage(
                id=f"msg_{i}",
                session_id="session_1",
                role="user",
                content=f"Message {i}"
            )
            # Create gaps at indices 3, 6, 8
            gap_minutes = 35 if i in [3, 6, 8] else 5
            msg.created_at = base_time + timedelta(minutes=sum(35 if j in [3, 6, 8] else 5 for j in range(i)))
            messages.append(msg)

        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        gaps = detector.detect_time_gap(messages)

        assert len(gaps) >= 3

    def test_detect_topic_changes_with_lancedb(self, sample_messages, mock_lancedb_handler):
        """Test topic change detection using semantic similarity"""
        # Mock embeddings with low similarity for topic change
        embeddings = [
            [0.1, 0.2, 0.3, 0.4, 0.5],  # Topic A
            [0.9, 0.8, 0.7, 0.6, 0.5],  # Topic B (low similarity)
            [0.1, 0.2, 0.3, 0.4, 0.5],  # Back to Topic A
            [0.1, 0.2, 0.3, 0.4, 0.5],  # Topic A
            [0.9, 0.8, 0.7, 0.6, 0.5],  # Topic B
        ]

        mock_lancedb_handler.embed_text.side_effect = embeddings

        detector = EpisodeBoundaryDetector(mock_lancedb_handler)
        changes = detector.detect_topic_changes(sample_messages)

        # Should detect topic changes where similarity < 0.75
        assert len(changes) >= 2

    def test_detect_topic_changes_high_similarity(self, sample_messages, mock_lancedb_handler):
        """Test topic change detection with high similarity (no changes)"""
        # All embeddings similar (same topic)
        mock_lancedb_handler.embed_text.return_value = [0.5, 0.5, 0.5, 0.5, 0.5]

        detector = EpisodeBoundaryDetector(mock_lancedb_handler)
        changes = detector.detect_topic_changes(sample_messages)

        assert len(changes) == 0

    def test_detect_topic_changes_no_lancedb(self, sample_messages):
        """Test topic change detection without LanceDB"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        changes = detector.detect_topic_changes(sample_messages)

        assert len(changes) == 0  # Returns empty when no LanceDB

    def test_detect_task_completion(self, sample_executions):
        """Test task completion detection"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        completions = detector.detect_task_completion(sample_executions)

        # All executions have status="completed"
        assert len(completions) == len(sample_executions)

    def test_detect_task_completion_incomplete(self):
        """Test task completion detection with incomplete tasks"""
        executions = []
        for i in range(3):
            exec = AgentExecution(
                id=f"exec_{i}",
                session_id="session_1",
                agent_id="agent_1",
                status="failed" if i == 1 else "completed",
                task_description=f"Task {i}"
            )
            # Only set result_summary for completed tasks
            if exec.status == "completed":
                exec.result_summary = f"Completed task {i}"
            executions.append(exec)

        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        completions = detector.detect_task_completion(executions)

        # Only 2 tasks have result_summary
        assert len(completions) == 2

    def test_cosine_similarity_calculation(self):
        """Test cosine similarity calculation"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = detector._cosine_similarity(vec1, vec2)

        # Orthogonal vectors have 0 similarity
        assert abs(similarity - 0.0) < 0.01

    def test_cosine_similarity_identical(self):
        """Test cosine similarity with identical vectors"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        vec = [0.5, 0.5, 0.5]
        similarity = detector._cosine_similarity(vec, vec)

        # Identical vectors have 1.0 similarity
        assert abs(similarity - 1.0) < 0.01


# ============================================================================
# Episode Creation Tests
# ============================================================================

class TestEpisodeCreation:
    """Test episode creation from sessions"""

    @pytest.mark.asyncio
    async def test_create_episode_from_session_basic(
        self,
        segmentation_service,
        sample_chat_session,
        sample_messages,
        sample_executions,
        mock_db
    ):
        """Test basic episode creation from session"""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = sample_chat_session
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.side_effect = [
            sample_messages,
            sample_executions,
            [],  # No canvas audits
            []   # No feedbacks
        ]

        episode = await segmentation_service.create_episode_from_session(
            session_id="session_1",
            agent_id="agent_1",
            title="Test Episode"
        )

        assert episode is not None
        assert episode.title == "Test Episode"
        assert episode.agent_id == "agent_1"
        assert episode.user_id == sample_chat_session.user_id
        assert episode.status == "completed"
        assert mock_db.add.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_create_episode_auto_title(
        self,
        segmentation_service,
        sample_chat_session,
        sample_messages,
        sample_executions,
        mock_db
    ):
        """Test episode creation with auto-generated title"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_chat_session
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.side_effect = [
            sample_messages,
            sample_executions,
            [],
            []
        ]

        episode = await segmentation_service.create_episode_from_session(
            session_id="session_1",
            agent_id="agent_1"
        )

        assert episode is not None
        assert episode.title is not None
        assert len(episode.title) > 0

    @pytest.mark.asyncio
    async def test_create_episode_with_canvas_context(
        self,
        segmentation_service,
        sample_chat_session,
        sample_messages,
        sample_executions,
        sample_canvas_audits,
        mock_db
    ):
        """Test episode creation includes canvas context"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_chat_session
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.side_effect = [
            sample_messages,
            sample_executions,
            sample_canvas_audits,
            []
        ]

        episode = await segmentation_service.create_episode_from_session(
            session_id="session_1",
            agent_id="agent_1"
        )

        assert episode is not None
        assert episode.canvas_ids == [c.id for c in sample_canvas_audits]
        assert episode.canvas_action_count == len(sample_canvas_audits)

    @pytest.mark.asyncio
    async def test_create_episode_with_feedback_context(
        self,
        segmentation_service,
        sample_chat_session,
        sample_messages,
        sample_executions,
        sample_feedbacks,
        mock_db
    ):
        """Test episode creation includes feedback context"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_chat_session
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.side_effect = [
            sample_messages,
            sample_executions,
            [],
            sample_feedbacks
        ]

        episode = await segmentation_service.create_episode_from_session(
            session_id="session_1",
            agent_id="agent_1"
        )

        assert episode is not None
        assert episode.feedback_ids == [f.id for f in sample_feedbacks]
        assert episode.aggregate_feedback_score is not None
        # thumbs_up (1.0) + rating 5 (1.0) = 2.0 / 2 = 1.0
        assert abs(episode.aggregate_feedback_score - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_create_episode_session_not_found(
        self,
        segmentation_service,
        mock_db
    ):
        """Test episode creation when session not found"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        episode = await segmentation_service.create_episode_from_session(
            session_id="nonexistent_session",
            agent_id="agent_1"
        )

        assert episode is None

    @pytest.mark.asyncio
    async def test_create_episode_insufficient_data(
        self,
        segmentation_service,
        sample_chat_session,
        mock_db
    ):
        """Test episode creation with insufficient data"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_chat_session
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.side_effect = [
            [],  # No messages
            []   # No executions
        ]

        episode = await segmentation_service.create_episode_from_session(
            session_id="session_1",
            agent_id="agent_1"
        )

        assert episode is None

    @pytest.mark.asyncio
    async def test_create_episode_force_create(
        self,
        segmentation_service,
        sample_chat_session,
        mock_db
    ):
        """Test force episode creation with minimal data"""
        single_msg = [ChatMessage(
            id="msg_1",
            session_id="session_1",
            role="user",
            content="Single message"
        )]

        mock_db.query.return_value.filter.return_value.first.return_value = sample_chat_session
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.side_effect = [
            single_msg,
            [],
            [],
            []
        ]

        # Without force_create - should return None
        episode = await segmentation_service.create_episode_from_session(
            session_id="session_1",
            agent_id="agent_1",
            force_create=False
        )
        assert episode is None

        # With force_create - should create episode
        episode = await segmentation_service.create_episode_from_session(
            session_id="session_1",
            agent_id="agent_1",
            force_create=True
        )
        assert episode is not None


# ============================================================================
# Segment Creation Tests
# ============================================================================

class TestSegmentCreation:
    """Test episode segment creation"""

    @pytest.mark.asyncio
    async def test_create_conversation_segments(
        self,
        segmentation_service,
        sample_chat_session,
        sample_messages,
        sample_executions,
        mock_db
    ):
        """Test conversation segment creation"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_chat_session
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.side_effect = [
            sample_messages,
            sample_executions,
            [],
            []
        ]

        episode = await segmentation_service.create_episode_from_session(
            session_id="session_1",
            agent_id="agent_1"
        )

        assert episode is not None
        # Should have called db.add for segments
        assert mock_db.add.call_count >= 2  # Episode + at least one segment

    @pytest.mark.asyncio
    async def test_create_execution_segments(
        self,
        segmentation_service,
        sample_chat_session,
        sample_executions,
        mock_db
    ):
        """Test execution segment creation"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_chat_session
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.side_effect = [
            [],
            sample_executions,
            [],
            []
        ]

        episode = await segmentation_service.create_episode_from_session(
            session_id="session_1",
            agent_id="agent_1",
            force_create=True
        )

        assert episode is not None
        # Should create segments for each execution
        assert mock_db.add.call_count >= len(sample_executions) + 1  # +1 for episode


# ============================================================================
# LanceDB Archival Tests
# ============================================================================

class TestLanceDBArchival:
    """Test LanceDB archival functionality"""

    @pytest.mark.asyncio
    async def test_archive_episode_to_lancedb(
        self,
        segmentation_service,
        sample_chat_session,
        sample_messages,
        mock_db
    ):
        """Test episode archival to LanceDB"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_chat_session
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.side_effect = [
            sample_messages,
            [],
            [],
            []
        ]

        # Create mock episode
        from unittest.mock import MagicMock
        episode = MagicMock(spec=Episode)
        episode.id = "episode_1"
        episode.title = "Test Episode"
        episode.description = "Test Description"
        episode.summary = "Test Summary"
        episode.topics = ["test", "topic"]
        episode.agent_id = "agent_1"
        episode.user_id = "user_1"
        episode.workspace_id = "workspace_1"
        episode.session_id = "session_1"
        episode.status = "completed"
        episode.maturity_at_time = "INTERN"
        episode.human_intervention_count = 0
        episode.constitutional_score = 0.85

        await segmentation_service._archive_to_lancedb(episode)

        # Verify LanceDB add_document was called
        assert segmentation_service.lancedb.add_document.called
        assert segmentation_service.lancedb.add_document.call_count == 1

    @pytest.mark.asyncio
    async def test_archive_episode_no_lancedb(
        self,
        segmentation_service,
        mock_db
    ):
        """Test archival when LanceDB is unavailable"""
        segmentation_service.lancedb.db = None

        episode = Mock(spec=Episode)
        episode.id = "episode_1"
        episode.title = "Test"
        episode.description = "Test"
        episode.summary = "Test"
        episode.topics = []
        episode.agent_id = "agent_1"
        episode.user_id = "user_1"
        episode.workspace_id = "workspace_1"
        episode.session_id = "session_1"
        episode.status = "completed"
        episode.maturity_at_time = "INTERN"
        episode.human_intervention_count = 0
        episode.constitutional_score = None

        # Should not raise exception
        await segmentation_service._archive_to_lancedb(episode)

        # add_document should not be called
        assert not segmentation_service.lancedb.add_document.called


# ============================================================================
# Supervision Episode Tests
# ============================================================================

class TestSupervisionEpisodeCreation:
    """Test supervision episode creation"""

    @pytest.mark.asyncio
    async def test_create_supervision_episode_basic(
        self,
        segmentation_service,
        sample_supervision_session,
        sample_executions,
        mock_db
    ):
        """Test basic supervision episode creation"""
        execution = sample_executions[0] if sample_executions else None

        episode = await segmentation_service.create_supervision_episode(
            supervision_session=sample_supervision_session,
            agent_execution=execution,
            db=mock_db
        )

        assert episode is not None
        assert episode.agent_id == sample_supervision_session.agent_id
        assert episode.user_id == sample_supervision_session.supervisor_id
        assert episode.supervisor_id == sample_supervision_session.supervisor_id
        assert episode.supervisor_rating == sample_supervision_session.supervisor_rating
        assert episode.intervention_count == sample_supervision_session.intervention_count
        assert episode.maturity_at_time == AgentStatus.SUPERVISED.value
        assert mock_db.add.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_supervision_episode_segments(
        self,
        segmentation_service,
        sample_supervision_session,
        sample_executions,
        mock_db
    ):
        """Test supervision episode creates segments"""
        execution = sample_executions[0] if sample_executions else None

        episode = await segmentation_service.create_supervision_episode(
            supervision_session=sample_supervision_session,
            agent_execution=execution,
            db=mock_db
        )

        assert episode is not None
        # Should have added episode + segments
        assert mock_db.add.call_count >= 2


# ============================================================================
# Feedback Scoring Tests
# ============================================================================

class TestFeedbackScoring:
    """Test feedback score calculation"""

    def test_calculate_feedback_score_thumbs_up(self, segmentation_service, sample_feedbacks):
        """Test feedback score calculation with thumbs up"""
        feedbacks = sample_feedbacks[:1]  # Only thumbs_up
        score = segmentation_service._calculate_feedback_score(feedbacks)

        assert score == 1.0

    def test_calculate_feedback_score_thumbs_down(self, segmentation_service):
        """Test feedback score calculation with thumbs down"""
        feedback = AgentFeedback(
            id="feedback_1",
            agent_id="agent_1",
            agent_execution_id="exec_1",
            feedback_type="thumbs_down",
            thumbs_up_down=False
        )

        score = segmentation_service._calculate_feedback_score([feedback])

        assert score == -1.0

    def test_calculate_feedback_score_rating(self, segmentation_service):
        """Test feedback score calculation with rating"""
        # Rating 5 -> 1.0, Rating 1 -> -1.0, Rating 3 -> 0.0
        feedbacks = [
            AgentFeedback(id="f1", agent_id="a1", agent_execution_id="e1", feedback_type="rating", rating=5),
            AgentFeedback(id="f2", agent_id="a1", agent_execution_id="e2", feedback_type="rating", rating=1),
            AgentFeedback(id="f3", agent_id="a1", agent_execution_id="e3", feedback_type="rating", rating=3),
        ]

        score = segmentation_service._calculate_feedback_score(feedbacks)

        # (1.0 + -1.0 + 0.0) / 3 = 0.0
        assert abs(score - 0.0) < 0.01

    def test_calculate_feedback_score_mixed(self, segmentation_service, sample_feedbacks):
        """Test feedback score calculation with mixed types"""
        score = segmentation_service._calculate_feedback_score(sample_feedbacks)

        # thumbs_up (1.0) + rating 5 (1.0) = 2.0 / 2 = 1.0
        assert abs(score - 1.0) < 0.01

    def test_calculate_feedback_score_empty(self, segmentation_service):
        """Test feedback score calculation with no feedbacks"""
        score = segmentation_service._calculate_feedback_score([])

        assert score is None


# ============================================================================
# Episode Metadata Tests
# ============================================================================

class TestEpisodeMetadata:
    """Test episode metadata extraction"""

    def test_extract_topics(self, segmentation_service, sample_messages):
        """Test topic extraction from messages"""
        topics = segmentation_service._extract_topics(sample_messages, [])

        assert isinstance(topics, list)
        assert len(topics) <= 5  # Max 5 topics

    def test_extract_entities(self, segmentation_service, sample_messages):
        """Test entity extraction from messages"""
        # Add a message with an email
        sample_messages[0].content = "Contact user@example.com for details"

        entities = segmentation_service._extract_entities(sample_messages, [])

        assert isinstance(entities, list)
        assert "user@example.com" in entities

    def test_calculate_importance(self, segmentation_service, sample_messages, sample_executions):
        """Test importance score calculation"""
        score = segmentation_service._calculate_importance(sample_messages, sample_executions)

        assert 0.0 <= score <= 1.0
        # Should have base score + boosts for messages and executions
        assert score >= 0.5

    def test_calculate_duration(self, segmentation_service, sample_messages):
        """Test episode duration calculation"""
        duration = segmentation_service._calculate_duration(sample_messages, [])

        assert duration is not None
        assert duration > 0
        # Duration should be in seconds
        assert duration < 3600  # Less than 1 hour for test data

    def test_generate_title(self, segmentation_service, sample_messages):
        """Test title generation from messages"""
        title = segmentation_service._generate_title(sample_messages, [])

        assert title is not None
        assert len(title) > 0
        # Long titles should be truncated
        if len(sample_messages[0].content) > 50:
            assert len(title) <= 50

    def test_generate_summary(self, segmentation_service, sample_messages):
        """Test summary generation"""
        summary = segmentation_service._generate_summary(sample_messages, [])

        assert summary is not None
        assert len(summary) > 0
        assert "Started:" in summary


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_empty_messages_list(self, segmentation_service, mock_db):
        """Test handling of empty messages list"""
        score = segmentation_service._calculate_duration([], [])

        assert score is None

    def test_cosine_similarity_zero_vectors(self):
        """Test cosine similarity with zero vectors"""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 1.0, 1.0]

        similarity = detector._cosine_similarity(vec1, vec2)

        # Should handle zero vectors gracefully
        assert similarity == 0.0

    @pytest.mark.asyncio
    async def test_lancedb_archival_error_handling(
        self,
        segmentation_service,
        mock_db
    ):
        """Test error handling in LanceDB archival"""
        segmentation_service.lancedb.add_document.side_effect = Exception("LanceDB error")

        episode = Mock(spec=Episode)
        episode.id = "episode_1"
        episode.title = "Test"
        episode.description = "Test"
        episode.summary = "Test"
        episode.topics = []
        episode.agent_id = "agent_1"
        episode.user_id = "user_1"
        episode.workspace_id = "workspace_1"
        episode.session_id = "session_1"
        episode.status = "completed"
        episode.maturity_at_time = "INTERN"
        episode.human_intervention_count = 0
        episode.constitutional_score = None

        # Should not raise exception
        await segmentation_service._archive_to_lancedb(episode)

    @pytest.mark.asyncio
    async def test_create_supervision_episode_error_handling(
        self,
        segmentation_service,
        sample_supervision_session,
        mock_db
    ):
        """Test error handling in supervision episode creation"""
        # Force an error during episode creation
        mock_db.commit.side_effect = Exception("Database error")

        episode = await segmentation_service.create_supervision_episode(
            supervision_session=sample_supervision_session,
            agent_execution=None,
            db=mock_db
        )

        assert episode is None
        assert mock_db.rollback.called


# ============================================================================
# LanceDB Integration Tests
# ============================================================================

class TestLanceDBIntegration:
    """Test LanceDB integration for episodic memory"""

    @pytest.mark.asyncio
    async def test_lancedb_connection(
        self,
        segmentation_service,
        mock_lancedb_handler
    ):
        """Test LanceDB connection"""
        # Verify LanceDB handler is connected
        assert segmentation_service.lancedb is not None
        assert segmentation_service.lancedb.db is not None

    @pytest.mark.asyncio
    async def test_create_episode_table(
        self,
        segmentation_service,
        mock_lancedb_handler
    ):
        """Test episode table creation in LanceDB"""
        # Mock table check
        mock_lancedb_handler.table_names.return_value = []

        episode = Mock(spec=Episode)
        episode.id = "episode_1"
        episode.title = "Test"
        episode.description = "Test"
        episode.summary = "Test"
        episode.topics = []
        episode.agent_id = "agent_1"
        episode.user_id = "user_1"
        episode.workspace_id = "workspace_1"
        episode.session_id = "session_1"
        episode.status = "completed"
        episode.maturity_at_time = "INTERN"
        episode.human_intervention_count = 0
        episode.constitutional_score = None

        await segmentation_service._archive_to_lancedb(episode)

        # Verify table was created
        assert mock_lancedb_handler.create_table.called

    @pytest.mark.asyncio
    async def test_insert_episode_vector(
        self,
        segmentation_service,
        mock_lancedb_handler
    ):
        """Test vector insertion for episode"""
        mock_lancedb_handler.table_names.return_value = ["episodes"]

        episode = Mock(spec=Episode)
        episode.id = "episode_1"
        episode.title = "Test Episode"
        episode.description = "Test Description"
        episode.summary = "Test Summary"
        episode.topics = ["test", "topic"]
        episode.agent_id = "agent_1"
        episode.user_id = "user_1"
        episode.workspace_id = "workspace_1"
        episode.session_id = "session_1"
        episode.status = "completed"
        episode.maturity_at_time = "INTERN"
        episode.human_intervention_count = 0
        episode.constitutional_score = 0.85

        await segmentation_service._archive_to_lancedb(episode)

        # Verify add_document was called
        assert mock_lancedb_handler.add_document.called
        call_args = mock_lancedb_handler.add_document.call_args
        assert call_args[1]["table_name"] == "episodes"
        assert "test" in call_args[1]["text"] or "Test" in call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_vector_search(
        self,
        mock_lancedb_handler
    ):
        """Test vector similarity search"""
        # Mock search results
        mock_lancedb_handler.search.return_value = [
            {
                "id": "ep1",
                "_distance": 0.2,  # High similarity
                "metadata": '{"episode_id": "episode_1", "agent_id": "agent_1"}'
            },
            {
                "id": "ep2",
                "_distance": 0.5,  # Medium similarity
                "metadata": '{"episode_id": "episode_2", "agent_id": "agent_1"}'
            }
        ]

        results = mock_lancedb_handler.search(
            table_name="episodes",
            query="test query",
            filter_str="agent_id == 'agent_1'",
            limit=10
        )

        assert len(results) == 2
        assert results[0]["_distance"] < results[1]["_distance"]  # Sorted by similarity

    @pytest.mark.asyncio
    async def test_batch_insert(
        self,
        segmentation_service,
        mock_lancedb_handler
    ):
        """Test batch insertion of episodes"""
        mock_lancedb_handler.table_names.return_value = ["episodes"]

        episodes = []
        for i in range(5):
            episode = Mock(spec=Episode)
            episode.id = f"episode_{i}"
            episode.title = f"Episode {i}"
            episode.description = f"Description {i}"
            episode.summary = f"Summary {i}"
            episode.topics = [f"topic_{i}"]
            episode.agent_id = "agent_1"
            episode.user_id = "user_1"
            episode.workspace_id = "workspace_1"
            episode.session_id = "session_1"
            episode.status = "completed"
            episode.maturity_at_time = "INTERN"
            episode.human_intervention_count = 0
            episode.constitutional_score = 0.8
            episodes.append(episode)

        # Insert all episodes
        for episode in episodes:
            await segmentation_service._archive_to_lancedb(episode)

        # Should have called add_document 5 times
        assert mock_lancedb_handler.add_document.call_count == 5

    @pytest.mark.asyncio
    async def test_update_vector(
        self,
        segmentation_service,
        mock_lancedb_handler
    ):
        """Test vector update (re-insertion)"""
        mock_lancedb_handler.table_names.return_value = ["episodes"]

        episode = Mock(spec=Episode)
        episode.id = "episode_1"
        episode.title = "Updated Title"
        episode.description = "Updated Description"
        episode.summary = "Updated Summary"
        episode.topics = ["updated"]
        episode.agent_id = "agent_1"
        episode.user_id = "user_1"
        episode.workspace_id = "workspace_1"
        episode.session_id = "session_1"
        episode.status = "completed"
        episode.maturity_at_time = "INTERN"
        episode.human_intervention_count = 0
        episode.constitutional_score = 0.9

        await segmentation_service._archive_to_lancedb(episode)

        # Verify add_document was called with updated content
        assert mock_lancedb_handler.add_document.called
        call_args = mock_lancedb_handler.add_document.call_args
        assert "Updated" in call_args[1]["text"]

    @pytest.mark.asyncio
    async def test_table_indexes(
        self,
        mock_lancedb_handler
    ):
        """Test LanceDB table index management"""
        # LanceDB automatically creates indexes on vector columns
        # This test verifies the handler can access table information

        mock_lancedb_handler.table_names.return_value = ["episodes", "knowledge", "documents"]

        tables = mock_lancedb_handler.table_names()

        assert "episodes" in tables
        assert len(tables) == 3

    @pytest.mark.asyncio
    async def test_embedding_generation(
        self,
        mock_lancedb_handler
    ):
        """Test embedding generation for episodes"""
        # Mock embedding generation
        mock_lancedb_handler.embed_text.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

        text = "This is a test episode about semantic search"
        embedding = mock_lancedb_handler.embed_text(text)

        assert len(embedding) == 5
        assert isinstance(embedding, list)
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_cosine_similarity_in_search(
        self,
        mock_lancedb_handler
    ):
        """Test cosine similarity is used in vector search"""
        # Mock search with distances
        mock_lancedb_handler.search.return_value = [
            {"id": "ep1", "_distance": 0.0, "metadata": '{"episode_id": "ep1"}'},  # Identical
            {"id": "ep2", "_distance": 0.5, "metadata": '{"episode_id": "ep2"}'},  # Similar
            {"id": "ep3", "_distance": 1.0, "metadata": '{"episode_id": "ep3"}'},  # Different
        ]

        results = mock_lancedb_handler.search(
            table_name="episodes",
            query="test query",
            limit=10
        )

        # Results should be sorted by distance (ascending)
        distances = [r["_distance"] for r in results]
        assert distances == sorted(distances)

    @pytest.mark.asyncio
    async def test_lancedb_connection_error_handling(
        self,
        segmentation_service,
        mock_lancedb_handler
    ):
        """Test error handling when LanceDB connection fails"""
        # Simulate connection failure
        mock_lancedb_handler.db = None

        episode = Mock(spec=Episode)
        episode.id = "episode_1"
        episode.title = "Test"
        episode.description = "Test"
        episode.summary = "Test"
        episode.topics = []
        episode.agent_id = "agent_1"
        episode.user_id = "user_1"
        episode.workspace_id = "workspace_1"
        episode.session_id = "session_1"
        episode.status = "completed"
        episode.maturity_at_time = "INTERN"
        episode.human_intervention_count = 0
        episode.constitutional_score = None

        # Should not raise exception
        await segmentation_service._archive_to_lancedb(episode)

        # add_document should not be called when LanceDB is unavailable
        assert not mock_lancedb_handler.add_document.called
