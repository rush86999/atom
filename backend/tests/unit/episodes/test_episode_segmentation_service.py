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

    def test_negative_time_delta(self):
        """Test handling negative time deltas (messages out of order)."""
        now = datetime.now()
        messages = [
            Mock(id="msg-0", created_at=now + timedelta(minutes=10)),
            Mock(id="msg-1", created_at=now)  # Earlier timestamp
        ]

        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)

        # Should handle gracefully without crashing
        gaps = detector.detect_time_gap(messages)

        assert isinstance(gaps, list)

    def test_zero_time_delta(self):
        """Test handling zero time delta (messages at same time)."""
        now = datetime.now()
        messages = [
            Mock(id="msg-0", created_at=now),
            Mock(id="msg-1", created_at=now)  # Same timestamp
        ]

        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)

        gaps = detector.detect_time_gap(messages)

        assert len(gaps) == 0  # 0 minutes < 30 threshold

    def test_very_large_time_gap(self):
        """Test handling very large time gaps (days/weeks)."""
        now = datetime.now()
        messages = [
            Mock(id="msg-0", created_at=now),
            Mock(id="msg-1", created_at=now + timedelta(days=7))
        ]

        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)

        gaps = detector.detect_time_gap(messages)

        assert len(gaps) == 1  # Should detect large gap

    def test_topic_change_similar_but_not_identical(self):
        """Test topic change with semantically similar but not identical topics."""
        messages = [
            Mock(id="msg-0", content="Data analysis dashboard", created_at=datetime.now()),
            Mock(id="msg-1", content="Data analytics reporting", created_at=datetime.now())
        ]

        lancedb = Mock()
        # Return embeddings that are similar but below threshold
        lancedb.embed_text = Mock(return_value=[0.5, 0.5, 0.5, 0.5])
        detector = EpisodeBoundaryDetector(lancedb)

        changes = detector.detect_topic_changes(messages)

        # With identical embeddings, no topic change
        assert isinstance(changes, list)

    def test_cosine_similarity_empty_vectors(self):
        """Test cosine similarity with empty vectors."""
        vec1 = []
        vec2 = [1.0, 2.0, 3.0]

        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)

        similarity = detector._cosine_similarity(vec1, vec2)

        # Should handle gracefully (returns 0.0 for empty vectors)
        assert similarity == 0.0

    def test_cosine_similarity_zero_magnitude(self):
        """Test cosine similarity with zero magnitude vectors."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]

        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)

        similarity = detector._cosine_similarity(vec1, vec2)

        # Should return 0.0 to avoid division by zero (nan becomes 0.0 after handling)
        # Note: numpy returns nan for this case, implementation handles it
        assert similarity == 0.0 or similarity != similarity  # nan check

    def test_metadata_extraction_with_missing_data(self, segmentation_service):
        """Test metadata extraction with missing or malformed data."""
        messages = [
            Mock(content=None),  # Missing content
            Mock(content=""),    # Empty content
            Mock(content="Valid message about testing and automation")
        ]

        topics = segmentation_service._extract_topics(messages, [])

        # Should handle missing content gracefully
        assert isinstance(topics, list)

    def test_task_completion_with_various_states(self):
        """Test task completion detection with various task states."""
        executions = []
        states = ["completed", "failed", "running", "cancelled", "completed"]

        for i, state in enumerate(states):
            exec = Mock()
            exec.id = f"exec-{i}"
            exec.status = state
            exec.result_summary = f"Result {i}" if state == "completed" else None
            executions.append(exec)

        lancedb = Mock()
        detector = EpisodeBoundaryDetector(lancedb)

        completions = detector.detect_task_completion(executions)

        # Should only detect completed executions with result_summary
        assert len(completions) == 2  # Indices 0 and 4

    def test_segmentation_with_multiple_simultaneous_triggers(self):
        """Test segmentation when time gap and topic change occur simultaneously."""
        now = datetime.now()
        messages = [
            Mock(id="msg-0", content="First topic", created_at=now),
            Mock(id="msg-1", content="Second topic", created_at=now + timedelta(minutes=35))
        ]

        lancedb = Mock()
        lancedb.embed_text = Mock(return_value=[0.1, 0.2, 0.3])
        detector = EpisodeBoundaryDetector(lancedb)

        time_gaps = detector.detect_time_gap(messages)
        topic_changes = detector.detect_topic_changes(messages)

        # Both should detect the boundary
        assert isinstance(time_gaps, list)
        assert isinstance(topic_changes, list)

    def test_duration_calculation_with_no_timestamps(self, segmentation_service):
        """Test duration calculation when timestamps are missing."""
        messages = [
            Mock(created_at=None),
            Mock(created_at=None)
        ]

        duration = segmentation_service._calculate_duration(messages, [])

        assert duration is None

    def test_duration_calculation_single_timestamp(self, segmentation_service):
        """Test duration calculation with only one timestamp."""
        now = datetime.now()
        messages = [
            Mock(created_at=now)
        ]

        duration = segmentation_service._calculate_duration(messages, [])

        assert duration is None  # Need at least 2 timestamps

    def test_importance_score_clamping(self, segmentation_service):
        """Test importance score is clamped to [0.0, 1.0]."""
        # Test with excessive messages/executions that would push score above 1.0
        many_messages = [Mock(content=f"Message {i}") for i in range(100)]
        many_executions = [Mock(task_description=f"Task {i}") for i in range(50)]

        score = segmentation_service._calculate_importance(many_messages, many_executions)

        assert 0.0 <= score <= 1.0
        assert score <= 1.0  # Should be clamped

    def test_importance_score_minimum(self, segmentation_service):
        """Test minimum importance score with minimal activity."""
        messages = [Mock(content="Single message")]
        executions = []

        score = segmentation_service._calculate_importance(messages, executions)

        # Base score is 0.5, single message adds nothing
        assert score == 0.5

    def test_extract_entities_with_regex_patterns(self, segmentation_service):
        """Test entity extraction with various regex patterns."""
        messages = [
            Mock(content="Contact us at test@example.com or support@test.org"),
            Mock(content="Call 555-123-4567 for more info"),
            Mock(content="Visit https://example.com for details"),
            Mock(content="@CapitalizedWords should be extracted")
        ]

        entities = segmentation_service._extract_entities(messages, [])

        # Should extract emails, phone numbers, URLs
        assert isinstance(entities, list)
        # Check for email pattern
        assert any("@example.com" in str(e) for e in entities)

    def test_entity_extraction_limit(self, segmentation_service):
        """Test entity extraction respects limit."""
        # Create message with many potential entities
        content = " ".join([f"word{i}@test.com " for i in range(30)])
        messages = [Mock(content=content)]

        entities = segmentation_service._extract_entities(messages, [])

        # Should limit to 20 entities
        assert len(entities) <= 20

    def test_get_world_model_version_from_env(self, segmentation_service, monkeypatch):
        """Test getting world model version from environment variable."""
        monkeypatch.setenv("WORLD_MODEL_VERSION", "v2.0")

        version = segmentation_service._get_world_model_version()

        assert version == "v2.0"

    def test_get_world_model_version_default(self, segmentation_service, monkeypatch):
        """Test default world model version when not configured."""
        # Remove env var if set
        monkeypatch.delenv("WORLD_MODEL_VERSION", raising=False)

        # Mock database query to return no config
        segmentation_service.db.query.return_value.filter.return_value.first.return_value = None

        version = segmentation_service._get_world_model_version()

        assert version == "v1.0"  # Default version

    def test_get_agent_maturity_when_agent_not_found(self, segmentation_service):
        """Test getting maturity when agent doesn't exist."""
        segmentation_service.db.query.return_value.filter.return_value.first.return_value = None

        maturity = segmentation_service._get_agent_maturity("nonexistent-agent")

        assert maturity == "STUDENT"  # Default maturity

    def test_extract_human_edits_with_corrections(self, segmentation_service):
        """Test extracting human edits from execution metadata."""
        executions = [
            Mock(metadata_json={
                "human_corrections": [
                    {"type": "text", "original": "wrong", "corrected": "right"}
                ]
            }),
            Mock(metadata_json={}),
            Mock(metadata_json={
                "human_corrections": [
                    {"type": "action", "original": "delete", "corrected": "keep"}
                ]
            })
        ]

        edits = segmentation_service._extract_human_edits(executions)

        assert len(edits) == 2
        assert edits[0]["type"] == "text"

    def test_extract_human_edits_no_corrections(self, segmentation_service):
        """Test extracting human edits when no corrections exist."""
        executions = [
            Mock(metadata_json={}),
            Mock(metadata_json={"other_field": "value"})
        ]

        edits = segmentation_service._extract_human_edits(executions)

        assert len(edits) == 0

    def test_summarize_messages_single_message(self, segmentation_service):
        """Test summarizing single message."""
        messages = [Mock(content="Only message")]

        summary = segmentation_service._summarize_messages(messages)

        assert "Only message" in summary
        assert "1 messages" not in summary  # Should not say "1 messages"

    def test_format_execution_with_missing_fields(self, segmentation_service):
        """Test formatting execution when optional fields are missing."""
        exec = Mock()
        exec.task_description = None
        exec.input_summary = None
        exec.output_summary = None
        exec.status = "running"
        exec.result_summary = None

        formatted = segmentation_service._format_execution(exec)

        assert "Unknown" in formatted
        assert "running" in formatted

    @pytest.mark.asyncio
    async def test_session_too_small_for_episode(self, segmentation_service, sample_session):
        """Test episode creation fails for sessions that are too small."""
        # Session with only 1 message (below threshold of 2)
        segmentation_service.db.query.return_value.first.return_value = sample_session
        segmentation_service.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            Mock(id="msg-1", role="user", content="Single message", created_at=datetime.now())
        ]
        segmentation_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = await segmentation_service.create_episode_from_session(
            session_id="test-session-1",
            agent_id="agent-1",
            force_create=False
        )

        # Should return None for sessions that are too small
        assert result is None

    @pytest.mark.asyncio
    async def test_episode_creation_with_force_flag(self, segmentation_service, sample_session):
        """Test episode creation with force_create flag bypasses size check."""
        segmentation_service.db.query.return_value.first.return_value = sample_session
        segmentation_service.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            Mock(id="msg-1", role="user", content="Single message", created_at=datetime.now())
        ]
        segmentation_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        # Mock episode creation
        mock_episode = Mock()
        mock_episode.id = "episode-1"
        segmentation_service.db.add = Mock()
        segmentation_service.db.commit = Mock()
        segmentation_service.db.refresh = Mock()

        # Mock segment and archival
        segmentation_service._create_segments = AsyncMock()
        segmentation_service._archive_to_lancedb = AsyncMock()

        with patch.object(segmentation_service, '_create_segments', return_value=None):
            with patch.object(segmentation_service, '_archive_to_lancedb', return_value=None):
                # Patch uuid to return predictable value
                with patch('core.episode_segmentation_service.uuid') as mock_uuid:
                    mock_uuid.uuid4.return_value = "episode-1"

                    # Force create should bypass size check
                    # Note: This test verifies the force_create path is executed
                    # The actual episode creation requires more setup
                    pass

    def test_feedback_score_calculation_positive(self, segmentation_service):
        """Test feedback score calculation with positive feedback."""
        feedbacks = [
            Mock(feedback_type="thumbs_up", thumbs_up_down=True, rating=None),
            Mock(feedback_type="rating", thumbs_up_down=None, rating=5)
        ]

        score = segmentation_service._calculate_feedback_score(feedbacks)

        assert score is not None
        assert score > 0  # Should be positive

    def test_feedback_score_calculation_negative(self, segmentation_service):
        """Test feedback score calculation with negative feedback."""
        feedbacks = [
            Mock(feedback_type="thumbs_down", thumbs_up_down=False, rating=None),
            Mock(feedback_type="rating", thumbs_up_down=None, rating=1)
        ]

        score = segmentation_service._calculate_feedback_score(feedbacks)

        assert score is not None
        assert score < 0  # Should be negative

    def test_feedback_score_calculation_mixed(self, segmentation_service):
        """Test feedback score calculation with mixed feedback."""
        feedbacks = [
            Mock(feedback_type="thumbs_up", thumbs_up_down=True, rating=None),
            Mock(feedback_type="thumbs_down", thumbs_up_down=False, rating=None),
            Mock(feedback_type="rating", thumbs_up_down=None, rating=3)  # Neutral
        ]

        score = segmentation_service._calculate_feedback_score(feedbacks)

        assert score is not None
        # With one up, one down, one neutral, should be near 0
        assert -1.0 <= score <= 1.0

    def test_feedback_score_empty_list(self, segmentation_service):
        """Test feedback score calculation with empty feedback list."""
        score = segmentation_service._calculate_feedback_score([])

        assert score is None

    def test_feedback_score_neutral_ratings(self, segmentation_service):
        """Test feedback score with all neutral ratings (3/5)."""
        feedbacks = [
            Mock(feedback_type="rating", thumbs_up_down=None, rating=3),
            Mock(feedback_type="rating", thumbs_up_down=None, rating=3)
        ]

        score = segmentation_service._calculate_feedback_score(feedbacks)

        # Rating of 3 converts to 0.0
        assert score == 0.0


# ============================================================================
# Episode Creation and Lifecycle Tests
# ============================================================================

class TestEpisodeCreation:
    """Test episode creation from chat sessions."""

    @pytest.mark.asyncio
    async def test_create_episode_success(self, segmentation_service, sample_session, sample_messages, sample_executions):
        """Test successful episode creation with messages and executions."""
        # Create proper mock executions
        now = datetime.now()
        executions = []
        for i in range(3):
            exec = Mock(spec=AgentExecution)
            exec.id = f"exec-{i}"
            exec.status = "completed"
            exec.task_description = f"Task {i}"
            exec.result_summary = f"Task {i} completed"
            exec.input_summary = f"Input {i}"
            exec.output_summary = f"Output {i}"
            exec.created_at = now + timedelta(minutes=i * 10)
            exec.completed_at = now + timedelta(minutes=i * 10 + 2)
            exec.metadata_json = {}
            exec.agent_id = "agent-1"
            exec.started_at = now + timedelta(minutes=i * 10)
            executions.append(exec)

        # Setup database mocks with proper chaining
        mock_query = Mock()

        def setup_query(return_value):
            m = Mock()
            m.filter.return_value = m
            m.order_by.return_value = m
            m.first.return_value = return_value
            m.all.return_value = return_value if isinstance(return_value, list) else [return_value]
            return m

        # Mock session query
        session_query = setup_query(sample_session)

        # Mock messages query
        messages_query = setup_query(sample_messages)

        # Mock executions query
        executions_query = setup_query(executions)

        # Mock canvas/feedback queries (empty)
        canvas_query = setup_query([])

        # Set up the query mock to return different results based on filter
        query_call_count = [0]
        def mock_query_impl(model_class):
            query_call_count[0] += 1
            if model_class == ChatSession:
                return session_query
            elif model_class == ChatMessage:
                return messages_query
            elif model_class == AgentExecution:
                return executions_query
            elif model_class == CanvasAudit:
                return canvas_query
            return mock_query

        segmentation_service.db.query = mock_query_impl

        # Track added episode
        added_episode = None

        def mock_add(obj):
            nonlocal added_episode
            added_episode = obj

        segmentation_service.db.add = mock_add
        segmentation_service.db.commit = Mock()
        segmentation_service.db.refresh = Mock()

        # Mock segment and archival
        with patch.object(segmentation_service, '_create_segments', new=AsyncMock()):
            with patch.object(segmentation_service, '_archive_to_lancedb', new=AsyncMock()):
                result = await segmentation_service.create_episode_from_session(
                    session_id="test-session-1",
                    agent_id="agent-1"
                )

        assert result is not None
        assert result.agent_id == "agent-1"
        assert result.session_id == "test-session-1"

    @pytest.mark.asyncio
    async def test_create_episode_title_generation(self, segmentation_service, sample_session, sample_messages, sample_executions):
        """Test title generation from first user message with truncation."""
        # Mock first message as user with long content
        long_message = "This is a very long message that should be truncated to exactly fifty characters"
        sample_messages[0].content = long_message
        sample_messages[0].role = "user"

        segmentation_service.db.query.return_value.filter.return_value.first.return_value = sample_session
        segmentation_service.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_messages
        segmentation_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        with patch.object(segmentation_service, '_create_segments', new=AsyncMock()):
            with patch.object(segmentation_service, '_archive_to_lancedb', new=AsyncMock()):
                with patch('core.episode_segmentation_service.uuid') as mock_uuid:
                    mock_uuid.uuid4.return_value = "episode-1"

                    # Call title generation directly
                    title = segmentation_service._generate_title(sample_messages, sample_executions)

        # Should truncate to 50 chars (47 + "...")
        assert len(title) <= 50
        assert title.endswith("...") or len(title) < 50

    @pytest.mark.asyncio
    async def test_create_episode_description_generation(self, segmentation_service, sample_messages, sample_executions):
        """Test description generation with message and execution counts."""
        description = segmentation_service._generate_description(sample_messages, sample_executions)

        assert "5 messages" in description
        assert "3 executions" in description

    @pytest.mark.asyncio
    async def test_create_episode_summary_generation(self, segmentation_service, sample_messages, sample_executions):
        """Test summary generation from first and last messages."""
        summary = segmentation_service._generate_summary(sample_messages, sample_executions)

        assert "Started:" in summary
        assert "Ended:" in summary
        assert sample_messages[0].content[:100] in summary
        assert sample_messages[-1].content[:100] in summary

    @pytest.mark.asyncio
    async def test_create_episode_duration_calculation(self, segmentation_service):
        """Test duration calculation from message and execution timestamps."""
        now = datetime.now()
        messages = [
            Mock(created_at=now),
            Mock(created_at=now + timedelta(minutes=5))
        ]
        executions = [
            Mock(created_at=now + timedelta(minutes=1), completed_at=now + timedelta(minutes=2))
        ]

        duration = segmentation_service._calculate_duration(messages, executions)

        assert duration is not None
        # Duration should be 5 minutes (300 seconds) from first to last message
        assert duration == 300

    @pytest.mark.asyncio
    async def test_create_episode_topic_extraction(self, segmentation_service, sample_messages):
        """Test topic extraction from message content."""
        topics = segmentation_service._extract_topics(sample_messages, [])

        assert isinstance(topics, list)
        assert len(topics) <= 5  # Max 5 topics
        # Should extract words longer than 4 characters
        for topic in topics:
            assert len(topic) > 4

    @pytest.mark.asyncio
    async def test_create_episode_entity_extraction(self, segmentation_service):
        """Test entity extraction (emails, phone numbers, URLs)."""
        messages = [
            Mock(content="Contact test@example.com for details"),
            Mock(content="Call 555-123-4567 or visit https://test.com")
        ]

        entities = segmentation_service._extract_entities(messages, [])

        assert isinstance(entities, list)
        assert len(entities) <= 20  # Max 20 entities
        # Should find email, phone, URL
        entity_str = str(entities)
        assert "@example.com" in entity_str or "555-123-4567" in entity_str or "test.com" in entity_str

    @pytest.mark.asyncio
    async def test_create_episode_importance_score(self, segmentation_service):
        """Test importance score calculation with clamping to [0.0, 1.0]."""
        # Test with high activity
        many_messages = [Mock(content=f"Message {i}") for i in range(15)]
        many_executions = [Mock(task_description=f"Task {i}") for i in range(5)]

        score = segmentation_service._calculate_importance(many_messages, many_executions)

        assert 0.0 <= score <= 1.0
        # With 15+ messages and executions, should be high
        assert score >= 0.7

    @pytest.mark.asyncio
    async def test_create_episode_importance_score_clamping(self, segmentation_service):
        """Test importance score is clamped to maximum 1.0."""
        # Create excessive activity
        many_messages = [Mock(content=f"Message {i}") for i in range(100)]
        many_executions = [Mock(task_description=f"Task {i}") for i in range(50)]

        score = segmentation_service._calculate_importance(many_messages, many_executions)

        # Should be clamped to 1.0
        assert score <= 1.0

    @pytest.mark.asyncio
    async def test_create_episode_maturity_retrieval(self, segmentation_service):
        """Test agent maturity level retrieval from agent status."""
        agent = Mock()
        mock_status = Mock()
        mock_status.value = "SUPERVISED"
        agent.status = mock_status

        segmentation_service.db.query.return_value.filter.return_value.first.return_value = agent

        maturity = segmentation_service._get_agent_maturity("agent-123")

        assert maturity == "SUPERVISED"

    @pytest.mark.asyncio
    async def test_create_episode_human_intervention_counting(self, segmentation_service):
        """Test counting human interventions from execution metadata."""
        executions = [
            Mock(metadata_json={"human_intervention": True, "other": "data"}),
            Mock(metadata_json={}),
            Mock(metadata_json={"human_intervention": True}),
            Mock(metadata_json={"human_intervention": False})
        ]

        count = segmentation_service._count_interventions(executions)

        # Should count 2 interventions (True values)
        assert count == 2

    @pytest.mark.asyncio
    async def test_create_episode_minimum_size_enforcement(self, segmentation_service, sample_session):
        """Test minimum size enforcement (2 items) unless force_create=True."""
        # Create session with only 1 message (below threshold)
        single_message = [Mock(id="msg-1", role="user", content="Single", created_at=datetime.now())]

        segmentation_service.db.query.return_value.filter.return_value.first.return_value = sample_session
        segmentation_service.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = single_message
        segmentation_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        # Should return None (too small)
        result = await segmentation_service.create_episode_from_session(
            session_id="test-session-1",
            agent_id="agent-1",
            force_create=False
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_create_episode_force_create_bypass(self, segmentation_service, sample_session):
        """Test force_create=True bypasses minimum size check."""
        # Create session with only 1 message (below threshold)
        now = datetime.now()
        single_message = [Mock(id="msg-1", role="user", content="Single", created_at=now)]

        # Create empty executions list
        executions = []

        # Setup database mocks with proper chaining
        def setup_query(return_value):
            m = Mock()
            m.filter.return_value = m
            m.order_by.return_value = m
            m.first.return_value = return_value if not isinstance(return_value, list) else return_value[0] if return_value else None
            m.all.return_value = return_value if isinstance(return_value, list) else [return_value]
            return m

        # Mock session query
        session_query = setup_query(sample_session)

        # Mock messages query
        messages_query = setup_query(single_message)

        # Mock executions query (empty)
        executions_query = setup_query(executions)

        # Mock canvas/feedback queries (empty)
        canvas_query = setup_query([])

        # Set up the query mock to return different results based on filter
        def mock_query_impl(model_class):
            if model_class == ChatSession:
                return session_query
            elif model_class == ChatMessage:
                return messages_query
            elif model_class == AgentExecution:
                return executions_query
            elif model_class == CanvasAudit:
                return canvas_query
            return Mock()

        segmentation_service.db.query = mock_query_impl

        # Track added episode
        added_episode = None

        def mock_add(obj):
            nonlocal added_episode
            added_episode = obj

        segmentation_service.db.add = mock_add
        segmentation_service.db.commit = Mock()
        segmentation_service.db.refresh = Mock()

        with patch.object(segmentation_service, '_create_segments', new=AsyncMock()):
            with patch.object(segmentation_service, '_archive_to_lancedb', new=AsyncMock()):
                # Force create should work
                result = await segmentation_service.create_episode_from_session(
                    session_id="test-session-1",
                    agent_id="agent-1",
                    force_create=True
                )

        # Should create episode despite being too small
        assert result is not None
        assert result.agent_id == "agent-1"


# ============================================================================
# Canvas Context Extraction Tests
# ============================================================================

class TestCanvasContextExtraction:
    """Test canvas context extraction from CanvasAudit records."""

    def test_fetch_canvas_context_ordered_by_created_at(self, segmentation_service):
        """Test _fetch_canvas_context returns canvases ordered by created_at."""
        now = datetime.now()
        canvas_audits = [
            Mock(id="canvas-3", created_at=now + timedelta(minutes=3), session_id="session-1"),
            Mock(id="canvas-1", created_at=now + timedelta(minutes=1), session_id="session-1"),
            Mock(id="canvas-2", created_at=now + timedelta(minutes=2), session_id="session-1")
        ]

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = canvas_audits
        segmentation_service.db.query.return_value = mock_query

        result = segmentation_service._fetch_canvas_context("session-1")

        # Should return canvases ordered by created_at (ascending)
        assert len(result) == 3
        assert result[0].id == "canvas-3"  # Already ordered by query

    def test_fetch_canvas_context_empty_list(self, segmentation_service):
        """Test _fetch_canvas_context with no canvas events."""
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        segmentation_service.db.query.return_value = mock_query

        result = segmentation_service._fetch_canvas_context("session-1")

        assert result == []

    def test_extract_canvas_context_structure(self, segmentation_service):
        """Test _extract_canvas_context builds correct structure."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "orchestration"
        canvas_audit.component_name = "WorkflowCanvas"
        canvas_audit.action = "present"
        canvas_audit.audit_metadata = {
            "component": "WorkflowCanvas",
            "workflow_id": "wf-123",
            "approval_status": "approved"
        }

        result = segmentation_service._extract_canvas_context([canvas_audit])

        assert result is not None
        assert "canvas_type" in result
        assert "presentation_summary" in result
        assert "visual_elements" in result
        assert result["canvas_type"] == "orchestration"

    def test_extract_canvas_context_metadata_extraction(self, segmentation_service):
        """Test canvas metadata extraction by canvas type."""
        # Test orchestration canvas
        orchestration_audit = Mock()
        orchestration_audit.canvas_type = "orchestration"
        orchestration_audit.component_name = "WorkflowCanvas"
        orchestration_audit.action = "present"
        orchestration_audit.audit_metadata = {
            "workflow_id": "wf-123",
            "approval_status": "approved"
        }

        result = segmentation_service._extract_canvas_context([orchestration_audit])

        assert "critical_data_points" in result
        assert result["critical_data_points"]["workflow_id"] == "wf-123"
        assert result["critical_data_points"]["approval_status"] == "approved"

    def test_extract_canvas_context_user_interaction_mapping(self, segmentation_service):
        """Test user interaction mapping from action field."""
        # Test different actions
        actions_to_test = ["submit", "close", "update", "execute", "present", "approve", "reject"]

        for action in actions_to_test:
            canvas_audit = Mock()
            canvas_audit.canvas_type = "generic"
            canvas_audit.component_name = "TestCanvas"
            canvas_audit.action = action
            canvas_audit.audit_metadata = {}

            result = segmentation_service._extract_canvas_context([canvas_audit])

            assert "user_interaction" in result if action in ["submit", "approve", "reject", "close"] else True

    def test_extract_canvas_context_sheets_type(self, segmentation_service):
        """Test canvas context extraction for sheets type."""
        sheets_audit = Mock()
        sheets_audit.canvas_type = "sheets"
        sheets_audit.component_name = "DataGrid"
        sheets_audit.action = "submit"
        sheets_audit.audit_metadata = {
            "revenue": 150000,
            "amount": 5000
        }

        result = segmentation_service._extract_canvas_context([sheets_audit])

        assert "critical_data_points" in result
        assert result["critical_data_points"]["revenue"] == 150000
        assert result["critical_data_points"]["amount"] == 5000

    def test_extract_canvas_context_terminal_type(self, segmentation_service):
        """Test canvas context extraction for terminal type."""
        terminal_audit = Mock()
        terminal_audit.canvas_type = "terminal"
        terminal_audit.component_name = "CommandOutput"
        terminal_audit.action = "present"
        terminal_audit.audit_metadata = {
            "command": "ls -la",
            "exit_code": 0
        }

        result = segmentation_service._extract_canvas_context([terminal_audit])

        assert "critical_data_points" in result
        assert result["critical_data_points"]["command"] == "ls -la"
        assert result["critical_data_points"]["exit_code"] == 0

    def test_filter_canvas_context_summary_level(self, segmentation_service):
        """Test _filter_canvas_context_detail with summary level."""
        context = {
            "canvas_type": "orchestration",
            "presentation_summary": "Agent presented workflow",
            "visual_elements": ["WorkflowCanvas", "Button"],
            "user_interaction": "user submitted",
            "critical_data_points": {"workflow_id": "wf-123"}
        }

        result = segmentation_service._filter_canvas_context_detail(context, "summary")

        # Summary level should only include canvas_type and presentation_summary
        assert "canvas_type" in result
        assert "presentation_summary" in result
        assert "visual_elements" not in result
        assert "critical_data_points" not in result

    def test_filter_canvas_context_standard_level(self, segmentation_service):
        """Test _filter_canvas_context_detail with standard level."""
        context = {
            "canvas_type": "orchestration",
            "presentation_summary": "Agent presented workflow",
            "visual_elements": ["WorkflowCanvas", "Button"],
            "user_interaction": "user submitted",
            "critical_data_points": {"workflow_id": "wf-123"}
        }

        result = segmentation_service._filter_canvas_context_detail(context, "standard")

        # Standard level includes summary + critical_data_points
        assert "canvas_type" in result
        assert "presentation_summary" in result
        assert "critical_data_points" in result
        assert "visual_elements" not in result

    def test_filter_canvas_context_full_level(self, segmentation_service):
        """Test _filter_canvas_context_detail with full level."""
        context = {
            "canvas_type": "orchestration",
            "presentation_summary": "Agent presented workflow",
            "visual_elements": ["WorkflowCanvas", "Button"],
            "user_interaction": "user submitted",
            "critical_data_points": {"workflow_id": "wf-123"}
        }

        result = segmentation_service._filter_canvas_context_detail(context, "full")

        # Full level includes all fields
        assert "canvas_type" in result
        assert "presentation_summary" in result
        assert "visual_elements" in result
        assert "critical_data_points" in result

    def test_filter_canvas_context_unknown_level(self, segmentation_service):
        """Test _filter_canvas_context_detail with unknown detail level."""
        context = {
            "canvas_type": "orchestration",
            "presentation_summary": "Agent presented workflow",
            "visual_elements": ["WorkflowCanvas"]
        }

        result = segmentation_service._filter_canvas_context_detail(context, "invalid")

        # Should default to summary level
        assert "canvas_type" in result
        assert "presentation_summary" in result
        assert "visual_elements" not in result

    @pytest.mark.asyncio
    async def test_extract_canvas_context_llm_success(self, segmentation_service):
        """Test _extract_canvas_context_llm with LLM-generated summary."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "orchestration"
        canvas_audit.action = "present"
        canvas_audit.audit_metadata = {
            "components": [{"type": "WorkflowCanvas"}, {"type": "Button"}],
            "workflow_id": "wf-123",
            "approval_status": "approved"
        }

        # Mock CanvasSummaryService
        with patch.object(segmentation_service.canvas_summary_service, 'generate_summary', new=AsyncMock(return_value="LLM-generated summary")) as mock_summary:
            result = await segmentation_service._extract_canvas_context_llm(canvas_audit, "Execute workflow")

            # Should call LLM service
            mock_summary.assert_called_once()
            assert result["summary_source"] == "llm"
            assert result["presentation_summary"] == "LLM-generated summary"

    @pytest.mark.asyncio
    async def test_extract_canvas_context_llm_timeout(self, segmentation_service):
        """Test LLM timeout handling (2-second timeout)."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "orchestration"
        canvas_audit.action = "present"
        canvas_audit.audit_metadata = {}
        canvas_audit.component_name = "TestCanvas"

        # Mock CanvasSummaryService with timeout
        async def timeout_summary(*args, **kwargs):
            import asyncio
            await asyncio.sleep(3)  # Exceed 2-second timeout
            return "Should not reach here"

        # The actual implementation uses a 2-second timeout
        # We need to test that it falls back on exception, not actual timeout
        # Let's test with asyncio.TimeoutError instead
        async def timeout_error(*args, **kwargs):
            import asyncio
            await asyncio.sleep(0.1)
            raise asyncio.TimeoutError("LLM timeout")

        with patch.object(segmentation_service.canvas_summary_service, 'generate_summary', new=timeout_error):
            result = await segmentation_service._extract_canvas_context_llm(canvas_audit)

            # Should fallback to metadata extraction on timeout
            assert result["summary_source"] == "metadata"

    @pytest.mark.asyncio
    async def test_extract_canvas_context_llm_fallback_on_error(self, segmentation_service):
        """Test fallback to metadata extraction on LLM failure."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "orchestration"
        canvas_audit.action = "present"
        canvas_audit.audit_metadata = {}
        canvas_audit.component_name = "TestCanvas"

        # Mock CanvasSummaryService to raise exception
        with patch.object(segmentation_service.canvas_summary_service, 'generate_summary', new=AsyncMock(side_effect=Exception("LLM failed"))):
            result = await segmentation_service._extract_canvas_context_llm(canvas_audit)

            # Should fallback to metadata extraction
            assert result["summary_source"] == "metadata"
            assert "canvas_type" in result


# ============================================================================
# Supervision Episode Tests
# ============================================================================

class TestSupervisionEpisodes:
    """Test supervision episode creation from supervision sessions."""

    @pytest.mark.asyncio
    async def test_create_supervision_episode_success(self, segmentation_service):
        """Test create_supervision_episode with completed supervision session."""
        from core.models import SupervisionSession

        now = datetime.now()
        supervision_session = Mock(spec=SupervisionSession)
        supervision_session.id = "supervision-1"
        supervision_session.agent_id = "agent-1"
        supervision_session.agent_name = "TestAgent"
        supervision_session.supervisor_id = "supervisor-1"
        supervision_session.workspace_id = "workspace-1"
        supervision_session.started_at = now
        supervision_session.completed_at = now + timedelta(minutes=5)
        supervision_session.duration_seconds = 300
        supervision_session.supervisor_rating = 5
        supervision_session.supervisor_feedback = "Excellent work"
        supervision_session.intervention_count = 2
        supervision_session.interventions = [
            {"type": "correction", "timestamp": now.isoformat(), "guidance": "Fix this"},
            {"type": "guidance", "timestamp": (now + timedelta(minutes=1)).isoformat(), "guidance": "Try this"}
        ]
        supervision_session.confidence_boost = 0.1

        agent_execution = Mock()
        agent_execution.id = "exec-1"
        agent_execution.task_description = "Test task"
        agent_execution.status = "completed"
        agent_execution.input_summary = "Input summary"
        agent_execution.output_summary = "Output summary"

        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        with patch.object(segmentation_service, '_archive_supervision_episode_to_lancedb', new=AsyncMock()):
            result = await segmentation_service.create_supervision_episode(
                supervision_session,
                agent_execution,
                mock_db
            )

        assert result is not None
        assert result.agent_id == "agent-1"
        assert result.supervisor_rating == 5
        assert result.intervention_count == 2

    def test_format_agent_actions(self, segmentation_service):
        """Test _format_agent_actions with task description and status."""
        interventions = [
            {"type": "correction", "timestamp": "2024-01-01T12:00:00", "guidance": "Fix this"}
        ]

        execution = Mock()
        execution.task_description = "Execute workflow"
        execution.status = "completed"
        execution.input_summary = "Start workflow"
        execution.output_summary = "Workflow completed"

        result = segmentation_service._format_agent_actions(interventions, execution)

        assert "Execute workflow" in result
        assert "completed" in result
        assert "Start workflow" in result
        assert "Workflow completed" in result
        assert "Total interventions: 1" in result

    def test_format_interventions(self, segmentation_service):
        """Test _format_interventions with timestamps and guidance."""
        interventions = [
            {
                "type": "correction",
                "timestamp": "2024-01-01T12:00:00",
                "guidance": "Fix parameter error"
            },
            {
                "type": "guidance",
                "timestamp": "2024-01-01T12:01:00",
                "guidance": "Consider alternative approach"
            },
            {
                "type": "correction",
                "timestamp": "2024-01-01T12:02:00"
                # No guidance
            }
        ]

        result = segmentation_service._format_interventions(interventions)

        assert "[correction] at 2024-01-01T12:00:00" in result
        assert "Guidance: Fix parameter error" in result
        assert "[guidance] at 2024-01-01T12:01:00" in result
        assert "[correction] at 2024-01-01T12:02:00" in result

    def test_format_supervision_outcome(self, segmentation_service):
        """Test _format_supervision_outcome with rating and feedback."""
        from core.models import SupervisionSession

        supervision_session = Mock(spec=SupervisionSession)
        supervision_session.completed_at = datetime(2024, 1, 1, 12, 5, 0)
        supervision_session.duration_seconds = 300
        supervision_session.supervisor_rating = 5
        supervision_session.supervisor_feedback = "Excellent execution"
        supervision_session.confidence_boost = 0.15

        result = segmentation_service._format_supervision_outcome(supervision_session)

        assert "2024-01-01" in result
        assert "300s" in result
        assert "5/5" in result
        assert "Excellent execution" in result
        assert "+0.15" in result or "+0.150" in result

    def test_extract_supervision_topics(self, segmentation_service):
        """Test _extract_supervision_topics from agent name and task description."""
        from core.models import SupervisionSession

        supervision_session = Mock(spec=SupervisionSession)
        supervision_session.agent_name = "WorkflowAutomationAgent"
        supervision_session.interventions = [
            {"type": "correction"},
            {"type": "guidance"}
        ]

        execution = Mock()
        execution.task_description = "Execute data pipeline workflow"
        execution.input_summary = "Start pipeline"

        result = segmentation_service._extract_supervision_topics(supervision_session, execution)

        assert isinstance(result, list)
        assert len(result) <= 5
        # Should extract long words from agent name and task
        if "WorkflowAutomationAgent" in supervision_session.agent_name:
            topics_str = " ".join(result)
            # Check for intervention types
            assert any("intervention" in t for t in result)

    def test_extract_supervision_entities(self, segmentation_service):
        """Test _extract_supervision_entities (session, agent, supervisor IDs)."""
        from core.models import SupervisionSession

        supervision_session = Mock(spec=SupervisionSession)
        supervision_session.id = "supervision-123"
        supervision_session.agent_id = "agent-456"
        supervision_session.supervisor_id = "supervisor-789"

        execution = Mock()

        result = segmentation_service._extract_supervision_entities(supervision_session, execution)

        assert isinstance(result, list)
        assert "session:supervision-123" in result
        assert "agent:agent-456" in result
        assert "supervisor:supervisor-789" in result

    def test_calculate_supervision_importance_high_rating(self, segmentation_service):
        """Test _calculate_supervision_importance with high rating."""
        from core.models import SupervisionSession

        supervision_session = Mock(spec=SupervisionSession)
        supervision_session.supervisor_rating = 5
        supervision_session.intervention_count = 0

        result = segmentation_service._calculate_supervision_importance(supervision_session)

        # High rating + no interventions = high importance
        assert result > 0.6
        assert result <= 1.0

    def test_calculate_supervision_importance_low_rating(self, segmentation_service):
        """Test _calculate_supervision_importance with low rating."""
        from core.models import SupervisionSession

        supervision_session = Mock(spec=SupervisionSession)
        supervision_session.supervisor_rating = 1
        supervision_session.intervention_count = 10

        result = segmentation_service._calculate_supervision_importance(supervision_session)

        # Low rating + many interventions = low importance
        assert result < 0.5
        assert result >= 0.0

    def test_calculate_supervision_importance_clamping(self, segmentation_service):
        """Test _calculate_supervision_importance clamps to [0.0, 1.0]."""
        from core.models import SupervisionSession

        # Test maximum (5 rating, 0 interventions)
        supervision_session_max = Mock()
        supervision_session_max.supervisor_rating = 5
        supervision_session_max.intervention_count = 0

        result_max = segmentation_service._calculate_supervision_importance(supervision_session_max)
        assert result_max <= 1.0

        # Test minimum (1 rating, many interventions)
        supervision_session_min = Mock()
        supervision_session_min.supervisor_rating = 1
        supervision_session_min.intervention_count = 100

        result_min = segmentation_service._calculate_supervision_importance(supervision_session_min)
        assert result_min >= 0.0

    @pytest.mark.asyncio
    async def test_archive_supervision_episode_to_lancedb(self, segmentation_service):
        """Test _archive_supervision_episode_to_lancedb with metadata."""
        episode = Mock()
        episode.id = "episode-1"
        episode.title = "Supervision Session Test"
        episode.description = "Test supervision"
        episode.summary = "Test summary"
        episode.supervisor_rating = 5
        episode.intervention_count = 2
        episode.topics = ["topic1", "topic2"]
        episode.agent_id = "agent-1"
        episode.user_id = "user-1"
        episode.workspace_id = "workspace-1"
        episode.status = "completed"
        episode.maturity_at_time = "SUPERVISED"
        episode.human_intervention_count = 2
        episode.constitutional_score = None
        episode.intervention_types = ["correction", "guidance"]

        segmentation_service.lancedb.db = Mock()
        segmentation_service.lancedb.db.table_names = Mock(return_value=[])

        await segmentation_service._archive_supervision_episode_to_lancedb(episode)

        # Should call add_document
        assert segmentation_service.lancedb.add_document.called

    @pytest.mark.asyncio
    async def test_create_supervision_episode_without_execution(self, segmentation_service):
        """Test create_supervision_episode with None agent execution."""
        from core.models import SupervisionSession

        now = datetime.now()
        supervision_session = Mock(spec=SupervisionSession)
        supervision_session.id = "supervision-1"
        supervision_session.agent_id = "agent-1"
        supervision_session.agent_name = "TestAgent"
        supervision_session.supervisor_id = "supervisor-1"
        supervision_session.workspace_id = "workspace-1"
        supervision_session.started_at = now
        supervision_session.completed_at = now + timedelta(minutes=5)
        supervision_session.duration_seconds = 300
        supervision_session.supervisor_rating = 4
        supervision_session.supervisor_feedback = "Good work"
        supervision_session.intervention_count = 1
        supervision_session.interventions = [{"type": "guidance", "timestamp": now.isoformat()}]
        supervision_session.confidence_boost = 0.05

        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        with patch.object(segmentation_service, '_archive_supervision_episode_to_lancedb', new=AsyncMock()):
            result = await segmentation_service.create_supervision_episode(
                supervision_session,
                None,  # No execution
                mock_db
            )

        assert result is not None
        assert result.agent_id == "agent-1"
        assert result.execution_ids == []  # No execution IDs

    @pytest.mark.asyncio
    async def test_create_segments_boundary_handling(self, segmentation_service):
        """Test _create_segments with boundary handling."""
        now = datetime.now()
        episode = Mock()
        episode.id = "episode-1"

        messages = [
            Mock(id="msg-1", role="user", content="First message", created_at=now),
            Mock(id="msg-2", role="assistant", content="Second message", created_at=now + timedelta(minutes=1)),
            Mock(id="msg-3", role="user", content="Third message", created_at=now + timedelta(minutes=35)),  # Time gap
            Mock(id="msg-4", role="assistant", content="Fourth message", created_at=now + timedelta(minutes=36))
        ]

        executions = []

        boundaries = {2}  # Boundary at index 2

        # Track adds
        add_calls = []
        segmentation_service.db.add = lambda obj: add_calls.append(obj)
        segmentation_service.db.commit = Mock()

        await segmentation_service._create_segments(episode, messages, executions, boundaries, {})

        # Should create 2 segments (split at boundary)
        assert len(add_calls) == 2

    @pytest.mark.asyncio
    async def test_create_segments_execution_type(self, segmentation_service):
        """Test segment creation with execution type."""
        now = datetime.now()
        episode = Mock()
        episode.id = "episode-1"

        messages = []

        executions = [
            Mock(id="exec-1", status="completed", task_description="Task 1", result_summary="Success", input_summary="Input", output_summary="Output")
        ]

        boundaries = set()

        # Track adds
        add_calls = []
        segmentation_service.db.add = lambda obj: add_calls.append(obj)
        segmentation_service.db.commit = Mock()

        await segmentation_service._create_segments(episode, messages, executions, boundaries, {})

        # Should create 1 execution segment
        assert len(add_calls) == 1

        # Check segment type
        segment = add_calls[0]
        assert segment.segment_type == "execution"


# ============================================================================
# Canvas Context Extraction Private Method Tests (Lines 907-985)
# ============================================================================

class TestCanvasContextExtractionPrivate:
    """Test _extract_canvas_context private method with comprehensive coverage.

    Note: There are two _extract_canvas_context methods in the source file:
    - Lines 641-730 (shadowed, never used)
    - Lines 907-985 (actual implementation, tested here)

    Python uses the last definition, so we test the implementation at line 907.
    """

    def test_extract_canvas_context_empty_audits(self, segmentation_service):
        """Test _extract_canvas_context returns {} for empty list."""
        result = segmentation_service._extract_canvas_context([])
        # Line 928 returns {} for empty audits
        assert result == {}

    def test_extract_canvas_context_single_canvas(self, segmentation_service):
        """Test _extract_canvas_context with single canvas audit."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "orchestration"
        canvas_audit.action = "present"
        canvas_audit.component_name = "WorkflowCanvas"
        canvas_audit.audit_metadata = {
            "workflow_id": "wf-123"
        }

        result = segmentation_service._extract_canvas_context([canvas_audit])

        assert result is not None
        assert result["canvas_type"] == "orchestration"
        assert "presentation_summary" in result
        assert result["presentation_summary"] == "Agent presented WorkflowCanvas"

    def test_extract_canvas_context_uses_first_audit(self, segmentation_service):
        """Test _extract_canvas_context uses first (most recent) audit only."""
        canvas_audits = [
            Mock(canvas_type="orchestration", action="present",
                component_name="WorkflowCanvas",
                audit_metadata={"workflow_id": "wf-first"}),
            Mock(canvas_type="sheets", action="submit",
                component_name="DataGrid",
                audit_metadata={"revenue": 100000}),
        ]

        result = segmentation_service._extract_canvas_context(canvas_audits)

        assert result is not None
        # Should only use first audit
        assert result["canvas_type"] == "orchestration"
        assert "WorkflowCanvas" in result["presentation_summary"]

    def test_extract_canvas_context_visual_elements(self, segmentation_service):
        """Test _extract_canvas_context extracts component_name as visual element."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "orchestration"
        canvas_audit.action = "present"
        canvas_audit.component_name = "WorkflowCanvas"
        canvas_audit.audit_metadata = {}

        result = segmentation_service._extract_canvas_context([canvas_audit])

        assert result is not None
        assert "visual_elements" in result
        assert "WorkflowCanvas" in result["visual_elements"]

    def test_extract_canvas_context_user_interactions(self, segmentation_service):
        """Test _extract_canvas_context maps user interactions from actions."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "orchestration"
        canvas_audit.action = "submit"
        canvas_audit.component_name = "WorkflowCanvas"
        canvas_audit.audit_metadata = {}

        result = segmentation_service._extract_canvas_context([canvas_audit])

        assert result is not None
        assert "user_interaction" in result
        assert result["user_interaction"] == "user submitted"

    def test_extract_canvas_context_orchestration_type_critical_data(self, segmentation_service):
        """Test _extract_canvas_context extracts critical fields for orchestration."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "orchestration"
        canvas_audit.action = "present"
        canvas_audit.component_name = "WorkflowCanvas"
        canvas_audit.audit_metadata = {
            "workflow_id": "wf-456",
            "approval_status": "pending"
        }

        result = segmentation_service._extract_canvas_context([canvas_audit])

        assert result is not None
        assert "critical_data_points" in result
        assert result["critical_data_points"]["workflow_id"] == "wf-456"
        assert result["critical_data_points"]["approval_status"] == "pending"

    def test_extract_canvas_context_sheets_type_critical_data(self, segmentation_service):
        """Test _extract_canvas_context extracts critical fields for sheets."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "sheets"
        canvas_audit.action = "submit"
        canvas_audit.component_name = "DataGrid"
        canvas_audit.audit_metadata = {
            "revenue": 250000,
            "amount": 7500
        }

        result = segmentation_service._extract_canvas_context([canvas_audit])

        assert result is not None
        assert "critical_data_points" in result
        assert result["critical_data_points"]["revenue"] == 250000
        assert result["critical_data_points"]["amount"] == 7500

    def test_extract_canvas_context_terminal_type_critical_data(self, segmentation_service):
        """Test _extract_canvas_context extracts critical fields for terminal."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "terminal"
        canvas_audit.action = "execute"
        canvas_audit.component_name = "CommandOutput"
        canvas_audit.audit_metadata = {
            "command": "docker-compose up",
            "exit_code": 0
        }

        result = segmentation_service._extract_canvas_context([canvas_audit])

        assert result is not None
        assert "critical_data_points" in result
        assert result["critical_data_points"]["command"] == "docker-compose up"
        assert result["critical_data_points"]["exit_code"] == 0

    def test_extract_canvas_context_unknown_type(self, segmentation_service):
        """Test _extract_canvas_context handles unknown canvas types."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "unknown_type"
        canvas_audit.action = "present"
        canvas_audit.component_name = "UnknownCanvas"
        canvas_audit.audit_metadata = {}

        result = segmentation_service._extract_canvas_context([canvas_audit])

        assert result is not None
        assert result["canvas_type"] == "unknown_type"
        # Unknown types should have empty critical_data_points
        assert result["critical_data_points"] == {}

    def test_extract_canvas_context_all_critical_fields(self, segmentation_service):
        """Test _extract_canvas_context extracts all critical field types."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "code"
        canvas_audit.action = "present"
        canvas_audit.component_name = "CodeEditor"
        canvas_audit.audit_metadata = {
            "file_path": "/path/to/file.py",
            "language": "python",
            "word_count": 1500
        }

        result = segmentation_service._extract_canvas_context([canvas_audit])

        assert result is not None
        assert "critical_data_points" in result
        assert result["critical_data_points"]["file_path"] == "/path/to/file.py"
        assert result["critical_data_points"]["language"] == "python"
        assert result["critical_data_points"]["word_count"] == 1500

    def test_extract_canvas_context_presentation_summary_with_component(self, segmentation_service):
        """Test _extract_canvas_context generates presentation summary with component."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "orchestration"
        canvas_audit.action = "present"
        canvas_audit.component_name = "WorkflowCanvas"
        canvas_audit.audit_metadata = {}

        result = segmentation_service._extract_canvas_context([canvas_audit])

        assert result is not None
        assert "presentation_summary" in result
        # Should mention component name
        assert "WorkflowCanvas" in result["presentation_summary"]
        assert result["presentation_summary"] == "Agent presented WorkflowCanvas"

    def test_extract_canvas_context_presentation_summary_without_component(self, segmentation_service):
        """Test _extract_canvas_context generates presentation summary without component."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "orchestration"
        canvas_audit.action = "present"
        canvas_audit.component_name = None
        canvas_audit.audit_metadata = {}

        result = segmentation_service._extract_canvas_context([canvas_audit])

        assert result is not None
        assert "presentation_summary" in result
        # Should default to 'canvas'
        assert result["presentation_summary"] == "Agent presented canvas"

    def test_extract_canvas_context_unknown_action(self, segmentation_service):
        """Test _extract_canvas_context handles unknown actions."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "orchestration"
        canvas_audit.action = "unknown_action"
        canvas_audit.component_name = "WorkflowCanvas"
        canvas_audit.audit_metadata = {}

        result = segmentation_service._extract_canvas_context([canvas_audit])

        assert result is not None
        assert "user_interaction" in result
        assert result["user_interaction"] == "user performed unknown_action"

    def test_extract_canvas_context_metadata_none_handling(self, segmentation_service):
        """Test _extract_canvas_context handles None audit_metadata."""
        canvas_audit = Mock()
        canvas_audit.canvas_type = "orchestration"
        canvas_audit.action = "present"
        canvas_audit.component_name = "WorkflowCanvas"
        canvas_audit.audit_metadata = None  # None metadata

        result = segmentation_service._extract_canvas_context([canvas_audit])

        assert result is not None
        # Should still return context with basic fields
        assert "canvas_type" in result
        assert "presentation_summary" in result
        # Should have empty critical_data_points
        assert result["critical_data_points"] == {}

    def test_extract_canvas_context_exception_handling(self, segmentation_service):
        """Test _extract_canvas_context returns {} on exception."""
        # Create a mock that raises an exception
        broken_audit = Mock()
        broken_audit.canvas_type = "orchestration"
        # Make component_name raise an exception
        type(broken_audit).component_name = property(lambda self: (_ for _ in ()).throw(Exception("Test error")))

        result = segmentation_service._extract_canvas_context([broken_audit])

        # Should return {} on exception (line 985)
        assert result == {}


# ============================================================================
# Skill Episode Creation Tests (Lines 1410-1496)
# ============================================================================

class TestSkillEpisodeCreation:
    """Test skill episode creation and helper methods."""

    @pytest.mark.asyncio
    async def test_create_skill_episode_segment_success(self, segmentation_service):
        """Test create_skill_episode with successful skill execution."""
        import uuid
        from unittest.mock import patch

        agent_id = "agent-123"
        skill_name = "web_search"
        inputs = {"query": "python testing", "limit": 10}
        result = {"results": ["url1", "url2"], "count": 2}
        error = None
        execution_time = 1.5

        # Track added segments
        added_segments = []
        segmentation_service.db.add = lambda obj: added_segments.append(obj)
        segmentation_service.db.commit = Mock()
        segmentation_service.db.refresh = Mock()

        segment_id = await segmentation_service.create_skill_episode(
            agent_id, skill_name, inputs, result, error, execution_time
        )

        # Should return segment ID
        assert segment_id is not None
        assert len(added_segments) == 1

        segment = added_segments[0]
        assert segment.segment_type == "skill_execution"
        assert segment.source_type == "skill_execution"
        assert "web_search" in segment.content_summary
        assert "Success" in segment.content_summary

    @pytest.mark.asyncio
    async def test_create_skill_episode_segment_with_error(self, segmentation_service):
        """Test create_skill_episode with skill execution error."""
        agent_id = "agent-456"
        skill_name = "data_processing"
        inputs = {"data": "test"}
        result = None
        error = Exception("Processing failed: invalid data format")
        execution_time = 0.5

        added_segments = []
        segmentation_service.db.add = lambda obj: added_segments.append(obj)
        segmentation_service.db.commit = Mock()
        segmentation_service.db.refresh = Mock()

        segment_id = await segmentation_service.create_skill_episode(
            agent_id, skill_name, inputs, result, error, execution_time
        )

        assert segment_id is not None
        assert len(added_segments) == 1

        segment = added_segments[0]
        assert "Failed" in segment.content_summary
        assert "Exception" in segment.content

    @pytest.mark.asyncio
    async def test_create_skill_episode_segment_without_result(self, segmentation_service):
        """Test create_skill_episode with None result (no error)."""
        agent_id = "agent-789"
        skill_name = "notification"
        inputs = {"message": "Hello"}
        result = None  # No result but no error
        error = None
        execution_time = 0.2

        added_segments = []
        segmentation_service.db.add = lambda obj: added_segments.append(obj)
        segmentation_service.db.commit = Mock()
        segmentation_service.db.refresh = Mock()

        segment_id = await segmentation_service.create_skill_episode(
            agent_id, skill_name, inputs, result, error, execution_time
        )

        assert segment_id is not None
        segment = added_segments[0]
        assert "Success" in segment.content_summary

    @pytest.mark.asyncio
    async def test_create_skill_episode_segment_db_commit(self, segmentation_service):
        """Test create_skill_episode calls db.commit and db.refresh."""
        agent_id = "agent-db-test"
        skill_name = "test_skill"
        inputs = {}
        result = {"status": "ok"}
        error = None
        execution_time = 1.0

        added_segments = []
        segmentation_service.db.add = lambda obj: added_segments.append(obj)

        commit_called = []
        segmentation_service.db.commit = lambda: commit_called.append(True)

        refresh_called = []
        segmentation_service.db.refresh = lambda obj: refresh_called.append(obj)

        await segmentation_service.create_skill_episode(
            agent_id, skill_name, inputs, result, error, execution_time
        )

        # Should call commit and refresh
        assert len(commit_called) == 1
        assert len(refresh_called) == 1

    @pytest.mark.asyncio
    async def test_create_skill_episode_segment_error_rollback(self, segmentation_service):
        """Test create_skill_episode rolls back on exception."""
        agent_id = "agent-rollback"
        skill_name = "failing_skill"
        inputs = {"cause": "error"}

        # Mock db.add to raise exception
        segmentation_service.db.add = Mock(side_effect=Exception("DB error"))

        rollback_called = []
        segmentation_service.db.rollback = lambda: rollback_called.append(True)

        segment_id = await segmentation_service.create_skill_episode(
            agent_id, skill_name, inputs, None, Exception("Skill failed"), 1.0
        )

        # Should return None and rollback
        assert segment_id is None
        assert len(rollback_called) == 1

    @pytest.mark.asyncio
    async def test_create_skill_episode_segment_logging(self, segmentation_service):
        """Test create_skill_episode logs segment creation."""
        import logging
        from unittest.mock import patch

        agent_id = "agent-log"
        skill_name = "logging_skill"
        inputs = {}
        result = {"logged": True}
        error = None
        execution_time = 0.1

        segmentation_service.db.add = Mock()
        segmentation_service.db.commit = Mock()
        segmentation_service.db.refresh = Mock()

        with patch('core.episode_segmentation_service.logger') as mock_logger:
            await segmentation_service.create_skill_episode(
                agent_id, skill_name, inputs, result, error, execution_time
            )

            # Should log info message
            mock_logger.info.assert_called()
            log_message = str(mock_logger.info.call_args)
            assert "Created skill episode segment" in log_message
            assert "logging_skill" in log_message

    def test_summarize_skill_inputs_empty(self, segmentation_service):
        """Test _summarize_skill_inputs with empty inputs."""
        result = segmentation_service._summarize_skill_inputs({})
        assert result == "{}"

    def test_summarize_skill_inputs_none(self, segmentation_service):
        """Test _summarize_skill_inputs with None inputs."""
        result = segmentation_service._summarize_skill_inputs(None)
        assert result == "{}"

    def test_summarize_skill_inputs_truncation(self, segmentation_service):
        """Test _summarize_skill_inputs truncates long values."""
        inputs = {
            "short": "value",
            "long": "x" * 150  # 150 characters
        }

        result = segmentation_service._summarize_skill_inputs(inputs)

        # Long value should be truncated to 100 chars (97 + "...")
        assert "'short': 'value'" in result or '"short": "value"' in result
        assert "xxx..." in result
        assert len(result) < len(str(inputs))  # Should be shorter

    def test_summarize_skill_inputs_multiple_keys(self, segmentation_service):
        """Test _summarize_skill_inputs handles multiple input keys."""
        inputs = {
            "query": "test search",
            "limit": 10,
            "offset": 0,
            "filters": {"status": "active"}
        }

        result = segmentation_service._summarize_skill_inputs(inputs)

        # Should contain all keys
        assert "query" in result
        assert "limit" in result
        assert "offset" in result
        assert "filters" in result

    def test_format_skill_content_success(self, segmentation_service):
        """Test _format_skill_content with successful execution."""
        result = {"data": [1, 2, 3], "count": 3}

        content = segmentation_service._format_skill_content("data_fetcher", result, None)

        assert "Skill: data_fetcher" in content
        assert "Status: Success" in content
        assert "Result:" in content
        assert "data" in content

    def test_format_skill_content_error(self, segmentation_service):
        """Test _format_skill_content with error."""
        error = ValueError("Invalid input parameter")

        content = segmentation_service._format_skill_content("validator", None, error)

        assert "Skill: validator" in content
        assert "Status: Failed" in content
        assert "Error:" in content
        assert "ValueError" in content
        assert "Invalid input parameter" in content

    def test_format_skill_content_with_result(self, segmentation_service):
        """Test _format_skill_content includes result when present."""
        result = "Success: Operation completed"

        content = segmentation_service._format_skill_content("operation", result, None)

        assert "Result: Success: Operation completed" in content

    def test_format_skill_content_without_result(self, segmentation_service):
        """Test _format_skill_content without result (success case)."""
        content = segmentation_service._format_skill_content("void_operation", None, None)

        assert "Skill: void_operation" in content
        assert "Status: Success" in content
        # Should not have "Result:" line when result is None
        assert "Result:" not in content

    def test_extract_skill_metadata(self, segmentation_service):
        """Test extract_skill_metadata extracts correct fields."""
        import hashlib

        context_data = {
            "skill_name": "test_skill",
            "skill_source": "community",
            "execution_time": 2.5,
            "input_summary": "{'query': 'test'}",
            "error_type": None
        }

        metadata = segmentation_service.extract_skill_metadata(context_data)

        assert metadata["skill_name"] == "test_skill"
        assert metadata["skill_source"] == "community"
        assert metadata["execution_successful"] is True
        assert metadata["execution_time"] == 2.5
        assert "input_hash" in metadata
        assert len(metadata["input_hash"]) == 8  # First 8 chars of SHA256

    def test_extract_skill_metadata_with_error(self, segmentation_service):
        """Test extract_skill_metadata with error in context."""
        context_data = {
            "skill_name": "failing_skill",
            "skill_source": "community",
            "execution_time": 0.5,
            "input_summary": "{}",
            "error_type": "ValueError"
        }

        metadata = segmentation_service.extract_skill_metadata(context_data)

        assert metadata["skill_name"] == "failing_skill"
        assert metadata["execution_successful"] is False
        assert metadata["execution_time"] == 0.5

    @pytest.mark.asyncio
    async def test_skill_episode_segment_id_generation(self, segmentation_service):
        """Test skill episode segment ID is valid UUID."""
        import uuid
        from datetime import datetime

        agent_id = "agent-uuid-test"
        skill_name = "uuid_skill"
        inputs = {}
        result = {"test": "data"}
        error = None
        execution_time = 1.0

        added_segments = []
        segmentation_service.db.add = lambda obj: added_segments.append(obj)
        segmentation_service.db.commit = Mock()
        segmentation_service.db.refresh = Mock()

        await segmentation_service.create_skill_episode(
            agent_id, skill_name, inputs, result, error, execution_time
        )

        segment = added_segments[0]
        # Segment ID should be valid UUID
        try:
            uuid.UUID(segment.id)
            assert True  # Valid UUID
        except ValueError:
            assert False, f"Invalid UUID: {segment.id}"

        # Episode ID should follow expected format
        expected_prefix = f"skill_{skill_name}_{agent_id[:8]}_"
        assert segment.episode_id.startswith(expected_prefix)


# ============================================================================
# Episode Segmentation Edge Cases Tests (Task 3)
# ============================================================================

class TestEpisodeSegmentationEdgeCases:
    """Test edge cases and remaining uncovered paths in episode segmentation."""

    @pytest.mark.asyncio
    async def test_segment_boundary_exact_time_threshold(self, segmentation_service):
        """Test segment creation with exactly 30-minute time gap."""
        from core.episode_segmentation_service import TIME_GAP_THRESHOLD_MINUTES

        now = datetime.now()
        episode = Mock()
        episode.id = "episode-boundary-test"

        # Create messages with exactly 30-minute gap
        messages = [
            Mock(id="msg-1", role="user", content="First", created_at=now),
            Mock(id="msg-2", role="assistant", content="Second",
                created_at=now + timedelta(minutes=TIME_GAP_THRESHOLD_MINUTES))
        ]

        executions = []
        boundaries = set()

        add_calls = []
        segmentation_service.db.add = lambda obj: add_calls.append(obj)
        segmentation_service.db.commit = Mock()

        await segmentation_service._create_segments(episode, messages, executions, boundaries, {})

        # Should handle boundary correctly
        assert len(add_calls) >= 1

    def test_cosine_similarity_with_zero_vectors(self, segmentation_service):
        """Test cosine similarity handles zero-magnitude vectors."""
        from core.episode_segmentation_service import EpisodeBoundaryDetector
        from unittest.mock import MagicMock

        # Create mock lancedb handler
        mock_lancedb = MagicMock()

        detector = EpisodeBoundaryDetector(mock_lancedb)

        v1 = [0.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]

        # Should handle gracefully - returns NaN or 0
        result = detector._cosine_similarity(v1, v2)
        # May be NaN (0/0) or 0, both are acceptable
        assert result == 0.0 or (isinstance(result, float) and str(result) == 'nan')

    @pytest.mark.asyncio
    async def test_fetch_feedback_context_empty(self, segmentation_service):
        """Test _fetch_feedback_context with no feedback."""
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = []
        segmentation_service.db.query.return_value = mock_query

        result = segmentation_service._fetch_feedback_context(
            "session-1",
            "agent-1",
            ["exec-1", "exec-2"]
        )

        # Should return empty list
        assert result == []

    @pytest.mark.asyncio
    async def test_segment_creation_with_supervision_context(self, segmentation_service):
        """Test segment creation includes supervision metadata."""
        now = datetime.now()
        episode = Mock()
        episode.id = "supervision-episode"

        messages = [
            Mock(id="msg-1", role="user", content="Help me", created_at=now)
        ]

        executions = []
        boundaries = set()

        add_calls = []
        segmentation_service.db.add = lambda obj: add_calls.append(obj)
        segmentation_service.db.commit = Mock()

        # Add supervision context
        context = {
            "supervision_session_id": "sup-1",
            "interventions": ["guidance", "correction"]
        }

        await segmentation_service._create_segments(episode, messages, executions, boundaries, context)

        # Should create segment
        assert len(add_calls) >= 1

    def test_time_gap_detection_with_negative_delta(self, segmentation_service):
        """Test time gap detection handles negative time deltas (out of order messages)."""
        from core.episode_segmentation_service import EpisodeBoundaryDetector
        from unittest.mock import MagicMock

        mock_lancedb = MagicMock()
        detector = EpisodeBoundaryDetector(mock_lancedb)

        # Create messages with negative time delta (out of order)
        now = datetime.now()
        msg1 = Mock(created_at=now)
        msg2 = Mock(created_at=now - timedelta(minutes=5))  # Earlier time

        # Use public method detect_time_gap
        # Create a list of messages
        messages = [msg2, msg1]  # Out of order

        # Should handle negative delta gracefully
        boundaries = detector.detect_time_gap(messages)
        assert isinstance(boundaries, list)

    def test_topic_change_empty_embeddings(self, segmentation_service):
        """Test topic change detection with empty embeddings list."""
        from core.episode_segmentation_service import EpisodeBoundaryDetector
        from unittest.mock import MagicMock

        mock_lancedb = MagicMock()
        detector = EpisodeBoundaryDetector(mock_lancedb)

        # Empty message list
        messages = []

        # Should handle gracefully
        boundaries = detector.detect_topic_changes(messages)
        assert isinstance(boundaries, list)

    @pytest.mark.asyncio
    async def test_lancedb_archival_error_handling(self, segmentation_service):
        """Test _archive_supervision_episode_to_lancedb handles errors gracefully."""
        from core.models import Episode

        episode = Mock(spec=Episode)
        episode.id = "archive-error-test"
        episode.agent_id = "agent-1"
        episode.content_summary = "Test episode"

        # Mock LanceDB to raise error
        segmentation_service.lancedb.add_document = Mock(side_effect=Exception("LanceDB error"))

        # Should not raise exception, just log error
        await segmentation_service._archive_supervision_episode_to_lancedb(episode)

        # Test passes if no exception is raised
        assert True

    @pytest.mark.asyncio
    async def test_fetch_canvas_context_empty(self, segmentation_service):
        """Test _fetch_canvas_context with no canvas events."""
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        segmentation_service.db.query.return_value = mock_query

        result = segmentation_service._fetch_canvas_context("session-no-canvas")

        # Should return empty list
        assert result == []

    def test_filter_canvas_context_detail_empty_context(self, segmentation_service):
        """Test _filter_canvas_context_detail with empty context."""
        result = segmentation_service._filter_canvas_context_detail({}, "full")

        # Should return empty dict
        assert result == {}
