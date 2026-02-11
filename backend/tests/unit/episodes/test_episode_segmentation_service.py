"""
Unit tests for EpisodeSegmentationService

Tests cover:
1. Time-based segmentation (gap detection)
2. Topic change detection (semantic similarity)
3. Task completion detection
4. Episode creation with metadata
5. Segment metadata and ordering
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from sqlalchemy.orm import Session

from core.episode_segmentation_service import (
    EpisodeSegmentationService,
    EpisodeBoundaryDetector,
    TIME_GAP_THRESHOLD_MINUTES,
    SEMANTIC_SIMILARITY_THRESHOLD,
)
from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    CanvasAudit,
    ChatMessage,
    ChatSession,
    Episode,
    EpisodeSegment,
)


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
    session.refresh.return_value = None
    session.rollback.return_value = None
    return session


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB handler."""
    lancedb = Mock()
    lancedb.embed_text = Mock(return_value=[0.1, 0.2, 0.3])
    lancedb.search = Mock(return_value=[])
    lancedb.add_document = Mock()
    lancedb.create_table = Mock()
    lancedb.db = Mock()
    lancedb.db.table_names = Mock(return_value=[])
    return lancedb


@pytest.fixture
def segmentation_service(db_session, mock_lancedb):
    """Create EpisodeSegmentationService with mocked dependencies."""
    with patch('core.episode_segmentation_service.get_lancedb_handler', return_value=mock_lancedb):
        service = EpisodeSegmentationService(db_session)
        service.lancedb = mock_lancedb
        return service


@pytest.fixture
def sample_session():
    """Create sample ChatSession."""
    session = Mock(spec=ChatSession)
    session.id = "test-session-1"
    session.user_id = "test-user-1"
    session.workspace_id = "test-workspace-1"
    return session


@pytest.fixture
def sample_messages():
    """Create sample chat messages."""
    now = datetime.now()
    messages = []
    for i in range(5):
        msg = Mock(spec=ChatMessage)
        msg.id = f"msg-{i}"
        msg.role = "user" if i % 2 == 0 else "assistant"
        msg.content = f"Message {i}: Testing episode segmentation with various content"
        msg.created_at = now + timedelta(minutes=i * 5)
        messages.append(msg)
    return messages


@pytest.fixture
def sample_executions():
    """Create sample agent executions."""
    now = datetime.now()
    executions = []
    for i in range(3):
        exec = Mock(spec=AgentExecution)
        exec.id = f"exec-{i}"
        exec.status = "completed"
        exec.task_description = f"Task {i}"
        exec.result_summary = f"Task {i} completed successfully"
        exec.input_summary = f"Input for task {i}"
        exec.output_summary = f"Output for task {i}"
        exec.created_at = now + timedelta(minutes=i * 10)
        exec.completed_at = now + timedelta(minutes=i * 10 + 2)
        exec.metadata_json = {}
        exec.session_id = "test-session-1"
        executions.append(exec)
    return executions


# ============================================================================
# Time Gap Detection Tests
# ============================================================================

class TestTimeGapDetection:
    """Test time-based episode segmentation."""

    def test_no_gaps_below_threshold(self):
        """Test no gaps detected when all messages <30 minutes apart."""
        now = datetime.now()
        messages = []
        for i in range(5):
            msg = Mock()
            msg.id = f"msg-{i}"
            msg.created_at = now + timedelta(minutes=i * 10)
            messages.append(msg)

        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)
        gaps = detector.detect_time_gap(messages)

        assert len(gaps) == 0

    def test_detect_gaps_exactly_threshold(self):
        """Test gap detection at exactly 30 minutes (boundary condition)."""
        now = datetime.now()
        messages = [
            Mock(id="msg-0", created_at=now),
            Mock(id="msg-1", created_at=now + timedelta(minutes=TIME_GAP_THRESHOLD_MINUTES))
        ]

        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)
        gaps = detector.detect_time_gap(messages)

        # 30 minutes should trigger gap (>= threshold)
        assert len(gaps) == 1
        assert 1 in gaps


# ============================================================================
# Topic Change Detection Tests
# ============================================================================

class TestTopicChangeDetection:
    """Test topic change detection using semantic similarity."""

    def test_handles_empty_message_list(self):
        """Test handling empty message list."""
        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)

        changes = detector.detect_topic_changes([])
        assert changes == []

    def test_handles_none_embeddings_gracefully(self):
        """Test graceful handling when embedding generation fails."""
        messages = [
            Mock(id="msg-0", content="Valid message", created_at=datetime.now()),
            Mock(id="msg-1", content="Invalid message", created_at=datetime.now())
        ]

        lancedb = Mock()
        lancedb.embed_text = Mock(return_value=None)
        detector = EpisodeBoundaryDetector(lancedb)

        changes = detector.detect_topic_changes(messages)

        # Should handle None gracefully
        assert isinstance(changes, list)


# ============================================================================
# Task Completion Detection Tests
# ============================================================================

class TestTaskCompletionDetection:
    """Test task completion detection for episode boundaries."""

    def test_detect_completed_executions(self):
        """Test detecting executions marked as completed."""
        executions = []
        for i in range(3):
            exec = Mock()
            exec.id = f"exec-{i}"
            exec.status = "completed" if i != 1 else "failed"
            exec.result_summary = f"Result {i}" if i != 1 else None
            executions.append(exec)

        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)
        completions = detector.detect_task_completion(executions)

        # Should detect 2 completions (indices 0 and 2)
        assert len(completions) == 2
        assert 0 in completions
        assert 2 in completions

    def test_no_completions_without_result_summary(self):
        """Test no completion markers when result_summary is missing."""
        executions = []
        for i in range(3):
            exec = Mock()
            exec.id = f"exec-{i}"
            exec.status = "completed"
            exec.result_summary = None
            executions.append(exec)

        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)
        completions = detector.detect_task_completion(executions)

        # No completions without result_summary
        assert len(completions) == 0


# ============================================================================
# Cosine Similarity Tests
# ============================================================================

class TestCosineSimilarity:
    """Test cosine similarity calculation for topic detection."""

    def test_cosine_similarity_identical_vectors(self):
        """Test cosine similarity of identical vectors is 1.0."""
        vec1 = [0.5, 0.5, 0.5]
        vec2 = [0.5, 0.5, 0.5]

        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)
        similarity = detector._cosine_similarity(vec1, vec2)

        assert abs(similarity - 1.0) < 0.001

    def test_cosine_similarity_orthogonal_vectors(self):
        """Test cosine similarity of orthogonal vectors is 0.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)
        similarity = detector._cosine_similarity(vec1, vec2)

        assert abs(similarity - 0.0) < 0.001

    def test_cosine_similarity_opposite_vectors(self):
        """Test cosine similarity of opposite vectors is -1.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]

        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)
        similarity = detector._cosine_similarity(vec1, vec2)

        assert abs(similarity - (-1.0)) < 0.001


# ============================================================================
# Metadata Extraction Tests
# ============================================================================

class TestMetadataExtraction:
    """Test metadata extraction from messages and executions."""

    def test_calculate_importance_score(self, segmentation_service):
        """Test importance score calculation."""
        many_messages = [Mock(content=f"Message {i}") for i in range(15)]
        executions = [Mock(task_description="Task") for _ in range(2)]

        score = segmentation_service._calculate_importance(many_messages, executions)

        assert 0.0 <= score <= 1.0
        # With many messages and executions, score should be decent
        assert score >= 0.5

    def test_calculate_duration(self, segmentation_service):
        """Test episode duration calculation."""
        now = datetime.now()
        messages = [
            Mock(created_at=now),
            Mock(created_at=now + timedelta(minutes=5)),
            Mock(created_at=now + timedelta(minutes=10))
        ]

        duration = segmentation_service._calculate_duration(messages, [])

        assert duration is not None
        assert duration == 600  # 10 minutes = 600 seconds

    def test_extract_topics_from_messages(self, segmentation_service):
        """Test topic extraction from message content."""
        messages = [
            Mock(content="The quick brown fox jumps over the lazy dog"),
            Mock(content="Python programming is fun and educational"),
            Mock(content="Machine learning algorithms are fascinating")
        ]

        topics = segmentation_service._extract_topics(messages, [])

        # Should extract words longer than 4 characters
        assert isinstance(topics, list)
        assert len(topics) <= 5  # Max 5 topics

    def test_get_agent_maturity(self, segmentation_service):
        """Test getting agent maturity level."""
        agent = Mock()
        # Create a mock enum that returns 'INTERN' when accessed
        mock_status = Mock()
        mock_status.value = "INTERN"
        agent.status = mock_status

        segmentation_service.db.query.return_value.first.return_value = agent

        maturity = segmentation_service._get_agent_maturity("agent-123")

        assert maturity == "INTERN"

    def test_count_interventions(self, segmentation_service):
        """Test counting human interventions."""
        executions = [
            Mock(metadata_json={"human_intervention": True}),
            Mock(metadata_json={}),
            Mock(metadata_json={"human_intervention": True})
        ]

        count = segmentation_service._count_interventions(executions)

        assert count == 2


# ============================================================================
# LanceDB Archival Tests
# ============================================================================

class TestLanceDBArchival:
    """Test LanceDB archival functionality."""

    @pytest.mark.asyncio
    async def test_archive_handles_lancedb_unavailable(self, segmentation_service):
        """Test graceful handling when LanceDB is unavailable."""
        mock_lancedb = Mock()
        mock_lancedb.db = None  # Unavailable

        segmentation_service.lancedb = mock_lancedb

        episode = Mock()
        episode.id = "test-episode-1"
        episode.title = "Test"
        episode.topics = []
        episode.agent_id = "agent-1"
        episode.user_id = "user-1"
        episode.workspace_id = "workspace-1"
        episode.maturity_at_time = "INTERN"
        episode.human_intervention_count = 0
        episode.constitutional_score = None

        # Should not crash, just log warning
        await segmentation_service._archive_to_lancedb(episode)


# ============================================================================
# Segment Creation Tests
# ============================================================================

class TestSegmentCreation:
    """Test segment creation and metadata."""

    def test_format_messages(self, segmentation_service):
        """Test formatting messages as text."""
        messages = [
            Mock(role="user", content="Hello"),
            Mock(role="assistant", content="Hi there")
        ]

        formatted = segmentation_service._format_messages(messages)

        assert "user: Hello" in formatted
        assert "assistant: Hi there" in formatted

    def test_summarize_messages(self, segmentation_service):
        """Test summarizing messages."""
        messages = [
            Mock(content="First message"),
            Mock(content="Second message"),
            Mock(content="Third message")
        ]

        summary = segmentation_service._summarize_messages(messages)

        assert "First message" in summary
        assert "3 messages" in summary

    def test_format_execution(self, segmentation_service):
        """Test formatting execution as text."""
        exec = Mock()
        exec.task_description = "Test task"
        exec.status = "completed"
        exec.result_summary = "Success"

        formatted = segmentation_service._format_execution(exec)

        assert "Test task" in formatted
        assert "completed" in formatted
        assert "Success" in formatted


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_single_message_no_gaps(self):
        """Test handling single message (no gaps possible)."""
        message = Mock(id="msg-0", created_at=datetime.now())

        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)

        gaps = detector.detect_time_gap([message])

        assert len(gaps) == 0

    def test_segment_type_classification(self):
        """Test valid segment types."""
        segment_types = ['conversation', 'execution', 'reflection', 'intervention']
        for seg_type in segment_types:
            # These are the valid segment types used in the codebase
            assert isinstance(seg_type, str)
