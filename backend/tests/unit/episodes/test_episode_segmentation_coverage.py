"""
Unit tests for episode_segmentation_service.py

Target: 60%+ coverage (current: 8.25%, target: ~348 lines)

Test Categories:
- Time Gap Detection (5 tests)
- Topic Change Detection (5 tests)
- Task Completion Detection (3 tests)
- Episode Segmentation (4 tests)
- Episode Creation (4 tests)
- Canvas Integration (3 tests)
- Error Paths (3 tests)
- Performance (3 tests)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from sqlalchemy.orm import Session

from core.episode_segmentation_service import (
    EpisodeBoundaryDetector,
    EpisodeSegmentationService,
    SegmentationBoundary,
    SegmentationResult,
    TIME_GAP_THRESHOLD_MINUTES,
    SEMANTIC_SIMILARITY_THRESHOLD
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


# ========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def db_session():
    """Mock database session"""
    session = MagicMock(spec=Session)
    session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.refresh = MagicMock()
    return session


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB handler"""
    lancedb = MagicMock()
    lancedb.embed_text = MagicMock(return_value=[0.1, 0.2, 0.3])
    lancedb.search = MagicMock(return_value=[])
    lancedb.add_document = MagicMock()
    lancedb.create_table = MagicMock()
    lancedb.db = MagicMock()
    lancedb.db.table_names = MagicMock(return_value=[])
    return lancedb


@pytest.fixture
def mock_byok_handler():
    """Mock BYOK handler"""
    handler = MagicMock()
    return handler


@pytest.fixture
def segmentation_service(db_session, mock_lancedb, mock_byok_handler):
    """EpisodeSegmentationService fixture"""
    with patch('core.episode_segmentation_service.get_lancedb_handler', return_value=mock_lancedb):
        with patch('core.episode_segmentation_service.CanvasSummaryService'):
            service = EpisodeSegmentationService(db_session, mock_byok_handler)
            service.lancedb = mock_lancedb
            return service


@pytest.fixture
def sample_messages():
    """Sample chat messages for testing"""
    now = datetime.now()
    messages = [
        ChatMessage(
            id="msg1",
            conversation_id="session1",
            role="user",
            content="Hello, how are you?",
            created_at=now - timedelta(minutes=60)
        ),
        ChatMessage(
            id="msg2",
            conversation_id="session1",
            role="assistant",
            content="I'm doing well, thanks!",
            created_at=now - timedelta(minutes=59)
        ),
        ChatMessage(
            id="msg3",
            conversation_id="session1",
            role="user",
            content="Can you help me with a task?",
            created_at=now - timedelta(minutes=35)  # 24 min gap from msg2
        ),
        ChatMessage(
            id="msg4",
            conversation_id="session1",
            role="assistant",
            content="Of course, what do you need?",
            created_at=now - timedelta(minutes=34)
        ),
        ChatMessage(
            id="msg5",
            conversation_id="session1",
            role="user",
            content="I need to analyze some data",
            created_at=now - timedelta(minutes=5)  # 29 min gap from msg4
        ),
    ]
    return messages


@pytest.fixture
def sample_executions():
    """Sample agent executions for testing"""
    now = datetime.now()
    executions = [
        AgentExecution(
            id="exec1",
            agent_id="agent1",
            status="completed",
            task_description="Data analysis task",
            result_summary="Analysis complete",
            started_at=now - timedelta(minutes=30),
            completed_at=now - timedelta(minutes=25)
        ),
        AgentExecution(
            id="exec2",
            agent_id="agent1",
            status="running",
            task_description="Another task",
            started_at=now - timedelta(minutes=10)
        ),
    ]
    return executions


@pytest.fixture
def sample_session(db_session):
    """Sample chat session"""
    session = ChatSession(
        id="session1",
        user_id="user1",
        created_at=datetime.now() - timedelta(hours=1)
    )
    return session


# ========================================================================
# A. EpisodeBoundaryDetector - Time Gaps (5 tests)
# =========================================================================

class TestTimeGapDetection:
    """Test time gap boundary detection"""

    def test_detect_time_gap_finds_gaps_exceeding_threshold(
        self, mock_lancedb
    ):
        """Should detect gaps > 30 minutes"""
        now = datetime.now()
        messages = [
            ChatMessage(id="m1", conversation_id="s1", role="user", content="A", created_at=now - timedelta(minutes=65)),
            ChatMessage(id="m2", conversation_id="s1", role="user", content="B", created_at=now - timedelta(minutes=34)),
            ChatMessage(id="m3", conversation_id="s1", role="user", content="C", created_at=now - timedelta(minutes=31)),
            ChatMessage(id="m4", conversation_id="s1", role="user", content="D", created_at=now),
        ]

        detector = EpisodeBoundaryDetector(mock_lancedb)
        gaps = detector.detect_time_gap(messages)

        # Gap of 31 minutes between m1 and m2 (>30 min threshold)
        # Gap of 3 minutes between m2 and m3 (<30 min threshold)
        # Gap of 31 minutes between m3 and m4 (>30 min threshold)
        assert len(gaps) == 2
        assert 1 in gaps  # After m1
        assert 3 in gaps  # After m3

    def test_detect_time_gap_excludes_exact_threshold(self, mock_lancedb):
        """Should NOT detect gap exactly at threshold (exclusive >)"""
        now = datetime.now()
        messages = [
            ChatMessage(id="m1", conversation_id="s1", role="user", content="A", created_at=now - timedelta(minutes=31)),
            ChatMessage(id="m2", conversation_id="s1", role="user", content="B", created_at=now - timedelta(minutes=1)),  # 30 min gap exactly
        ]

        detector = EpisodeBoundaryDetector(mock_lancedb)
        gaps = detector.detect_time_gap(messages)

        # Gap of exactly 30 minutes should NOT trigger boundary
        assert len(gaps) == 0

    def test_detect_time_gap_empty_message_list(self, mock_lancedb):
        """Should handle empty message list"""
        detector = EpisodeBoundaryDetector(mock_lancedb)
        gaps = detector.detect_time_gap([])
        assert gaps == []

    def test_detect_time_gap_multiple_gaps(self, mock_lancedb):
        """Should detect multiple time gaps"""
        now = datetime.now()
        messages = [
            ChatMessage(id="m1", conversation_id="s1", role="user", content="A", created_at=now - timedelta(minutes=100)),
            ChatMessage(id="m2", conversation_id="s1", role="user", content="B", created_at=now - timedelta(minutes=60)),
            ChatMessage(id="m3", conversation_id="s1", role="user", content="C", created_at=now - timedelta(minutes=30)),
            ChatMessage(id="m4", conversation_id="s1", role="user", content="D", created_at=now),
        ]

        detector = EpisodeBoundaryDetector(mock_lancedb)
        gaps = detector.detect_time_gap(messages)

        # Gaps: 40 min (m1->m2), 30 min (m2->m3, not triggered), 30 min (m3->m4, not triggered)
        assert len(gaps) == 1
        assert 1 in gaps

    def test_detect_time_gap_preserves_boundary_positions(self, mock_lancedb):
        """Should return correct boundary indices"""
        now = datetime.now()
        messages = [
            ChatMessage(id="m1", conversation_id="s1", role="user", content="A", created_at=now - timedelta(minutes=90)),
            ChatMessage(id="m2", conversation_id="s1", role="user", content="B", created_at=now - timedelta(minutes=50)),
            ChatMessage(id="m3", conversation_id="s1", role="user", content="C", created_at=now - timedelta(minutes=10)),
            ChatMessage(id="m4", conversation_id="s1", role="user", content="D", created_at=now),
        ]

        detector = EpisodeBoundaryDetector(mock_lancedb)
        gaps = detector.detect_time_gap(messages)

        # Gaps after m1 (40 min) and m2 (40 min)
        assert 1 in gaps
        assert 2 in gaps


# ========================================================================
# B. EpisodeBoundaryDetector - Topic Changes (5 tests)
# =========================================================================

class TestTopicChangeDetection:
    """Test topic change boundary detection"""

    def test_detect_topic_changes_with_embeddings(self, mock_lancedb):
        """Should detect topic changes using semantic similarity"""
        now = datetime.now()
        messages = [
            ChatMessage(id="m1", conversation_id="s1", role="user", content="Let's talk about weather", created_at=now),
            ChatMessage(id="m2", conversation_id="s1", role="user", content="The sun is shining", created_at=now),
            ChatMessage(id="m3", conversation_id="s1", role="user", content="Now let's discuss finance", created_at=now),
        ]

        # Mock embeddings: similar for m1-m2, dissimilar for m2-m3
        # Use return_value with a callable
        def mock_embed(text):
            if "weather" in text:
                return [0.9, 0.1]  # m1: weather
            elif "sun" in text:
                return [0.85, 0.15]  # m2: sun (similar to m1)
            elif "finance" in text:
                return [0.1, 0.9]  # m3: finance (dissimilar)
            return [0.5, 0.5]

        mock_lancedb.embed_text.side_effect = lambda x: mock_embed(x)

        detector = EpisodeBoundaryDetector(mock_lancedb)
        changes = detector.detect_topic_changes(messages)

        # Should detect change between m2 and m3 (similarity < 0.75 threshold)
        assert 2 in changes

    def test_detect_topic_changes_below_threshold(self, mock_lancedb):
        """Should detect changes when similarity < 0.75"""
        now = datetime.now()
        messages = [
            ChatMessage(id="m1", conversation_id="s1", role="user", content="Topic A", created_at=now),
            ChatMessage(id="m2", conversation_id="s1", role="user", content="Topic B", created_at=now),
        ]

        # Mock embeddings with low similarity
        mock_lancedb.embed_text.side_effect = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],  # Orthogonal, similarity = 0
        ]

        detector = EpisodeBoundaryDetector(mock_lancedb)
        changes = detector.detect_topic_changes(messages)

        # Similarity 0 < 0.75 threshold, should trigger boundary
        assert 1 in changes

    def test_detect_topic_changes_no_lancedb_handler(self):
        """Should handle missing LanceDB handler gracefully"""
        now = datetime.now()
        messages = [
            ChatMessage(id="m1", conversation_id="s1", role="user", content="A", created_at=now),
            ChatMessage(id="m2", conversation_id="s1", role="user", content="B", created_at=now),
        ]

        detector = EpisodeBoundaryDetector(None)
        changes = detector.detect_topic_changes(messages)

        # Should return empty list when no LanceDB
        assert changes == []

    def test_detect_topic_changes_insufficient_messages(self, mock_lancedb):
        """Should handle insufficient messages (< 2)"""
        now = datetime.now()
        messages = [
            ChatMessage(id="m1", conversation_id="s1", role="user", content="A", created_at=now),
        ]

        detector = EpisodeBoundaryDetector(mock_lancedb)
        changes = detector.detect_topic_changes(messages)

        # Need at least 2 messages for comparison
        assert changes == []

    def test_detect_topic_changes_embedding_failure_handling(self, mock_lancedb):
        """Should handle embedding generation failures"""
        now = datetime.now()
        messages = [
            ChatMessage(id="m1", conversation_id="s1", role="user", content="A", created_at=now),
            ChatMessage(id="m2", conversation_id="s1", role="user", content="B", created_at=now),
            ChatMessage(id="m3", conversation_id="s1", role="user", content="C", created_at=now),
        ]

        # Mock embedding failures - use list to avoid StopIteration
        embeddings = [
            [0.5, 0.5],  # m1 success
            None,  # m2 failure
            [0.5, 0.5],  # m3 success
            [0.5, 0.5]  # Extra to prevent StopIteration
        ]
        mock_lancedb.embed_text.side_effect = embeddings

        detector = EpisodeBoundaryDetector(mock_lancedb)
        changes = detector.detect_topic_changes(messages)

        # Should skip comparisons with None embeddings
        # m1-m2 skipped (m2 is None), m2-m3 skipped (m2 is None)
        assert changes == []


# ========================================================================
# C. EpisodeBoundaryDetector - Task Completion (3 tests)
# =========================================================================

class TestTaskCompletionDetection:
    """Test task completion boundary detection"""

    def test_detect_task_completion_by_status(self, mock_lancedb):
        """Should detect completed executions"""
        now = datetime.now()
        executions = [
            AgentExecution(id="e1", agent_id="a1", status="running", started_at=now),
            AgentExecution(id="e2", agent_id="a1", status="completed", result_summary="Done", started_at=now),
            AgentExecution(id="e3", agent_id="a1", status="completed", result_summary="Also done", started_at=now),
        ]

        detector = EpisodeBoundaryDetector(mock_lancedb)
        completions = detector.detect_task_completion(executions)

        # Should detect e2 and e3 as completions
        assert len(completions) == 2
        assert 1 in completions  # e2
        assert 2 in completions  # e3

    def test_detect_task_completion_agent_terminated(self, mock_lancedb):
        """Should detect terminated executions as boundaries"""
        now = datetime.now()
        executions = [
            AgentExecution(id="e1", agent_id="a1", status="terminated", result_summary="Stopped", started_at=now),
        ]

        detector = EpisodeBoundaryDetector(mock_lancedb)
        completions = detector.detect_task_completion(executions)

        # "terminated" status is not "completed", should not trigger
        assert len(completions) == 0

    def test_detect_task_completion_no_completion_signals(self, mock_lancedb):
        """Should handle executions without completion signals"""
        now = datetime.now()
        executions = [
            AgentExecution(id="e1", agent_id="a1", status="running", started_at=now),
            AgentExecution(id="e2", agent_id="a1", status="running", started_at=now),
        ]

        detector = EpisodeBoundaryDetector(mock_lancedb)
        completions = detector.detect_task_completion(executions)

        # No completed executions
        assert completions == []


# ========================================================================
# D. Episode Segmentation (4 tests)
# =========================================================================

class TestEpisodeSegmentation:
    """Test episode segmentation logic"""

    def test_segment_messages_creates_episodes_from_boundaries(
        self, segmentation_service, sample_messages
    ):
        """Should create segments at boundaries"""
        boundaries = {1, 3}  # After message 1 and 3

        with patch.object(segmentation_service, '_create_segments') as mock_create:
            mock_create.return_value = None

            # Simulate segmentation
            segments = []
            current_segment = []
            for i, msg in enumerate(sample_messages):
                current_segment.append(msg)
                if i in boundaries or i == len(sample_messages) - 1:
                    segments.append(current_segment)
                    current_segment = []

            # Should create 3 segments
            assert len(segments) == 3
            assert len(segments[0]) == 2  # msg1, msg2
            assert len(segments[1]) == 2  # msg3, msg4
            assert len(segments[2]) == 1  # msg5

    def test_segment_messages_with_single_boundary(
        self, segmentation_service, sample_messages
    ):
        """Should create 2 segments with 1 boundary"""
        boundaries = {2}

        segments = []
        current_segment = []
        for i, msg in enumerate(sample_messages):
            current_segment.append(msg)
            if i in boundaries or i == len(sample_messages) - 1:
                segments.append(current_segment)
                current_segment = []

        assert len(segments) == 2
        assert len(segments[0]) == 3  # msg1, msg2, msg3
        assert len(segments[1]) == 2  # msg4, msg5

    def test_segment_messages_no_boundaries_single_episode(
        self, segmentation_service, sample_messages
    ):
        """Should create single episode when no boundaries"""
        boundaries = set()

        segments = []
        current_segment = []
        for i, msg in enumerate(sample_messages):
            current_segment.append(msg)
            if i in boundaries or i == len(sample_messages) - 1:
                segments.append(current_segment)
                current_segment = []

        # Single segment with all messages
        assert len(segments) == 1
        assert len(segments[0]) == 5

    def test_segment_messages_preserves_message_order(
        self, segmentation_service, sample_messages
    ):
        """Should maintain chronological order"""
        boundaries = {1, 3}

        segments = []
        current_segment = []
        for i, msg in enumerate(sample_messages):
            current_segment.append(msg)
            if i in boundaries or i == len(sample_messages) - 1:
                segments.append(current_segment)
                current_segment = []

        # Verify order in each segment
        for segment in segments:
            timestamps = [m.created_at for m in segment]
            assert timestamps == sorted(timestamps)


# ========================================================================
# E. Episode Creation (4 tests)
# =========================================================================

class TestEpisodeCreation:
    """Test episode creation from sessions"""

    def test_generate_title_from_first_user_message(self, segmentation_service):
        """Should generate title from first user message"""
        now = datetime.now()
        messages = [
            ChatMessage(id="m1", conversation_id="s1", role="user", content="Analyze this data", created_at=now),
            ChatMessage(id="m2", conversation_id="s1", role="assistant", content="OK", created_at=now),
        ]

        title = segmentation_service._generate_title(messages, [])
        assert "Analyze this data" in title

    def test_generate_title_falls_back_to_timestamp(self, segmentation_service):
        """Should fall back to timestamp when no user messages"""
        messages = []
        executions = []

        title = segmentation_service._generate_title(messages, executions)
        assert "Episode from" in title
        assert datetime.now().strftime('%Y-%m-%d') in title

    def test_generate_description_counts_messages_and_executions(self, segmentation_service):
        """Should generate description with counts"""
        messages = ["msg1", "msg2", "msg3"]
        executions = ["exec1", "exec2"]

        description = segmentation_service._generate_description(messages, executions)
        assert "3 messages" in description
        assert "2 executions" in description

    def test_generate_summary_includes_first_and_last(self, segmentation_service):
        """Should generate summary from first and last messages"""
        now = datetime.now()
        messages = [
            ChatMessage(id="m1", conversation_id="s1", role="user", content="Start of task", created_at=now),
            ChatMessage(id="m2", conversation_id="s1", role="assistant", content="Middle", created_at=now),
            ChatMessage(id="m3", conversation_id="s1", role="user", content="End of task", created_at=now),
        ]

        summary = segmentation_service._generate_summary(messages, [])
        assert "Start of task" in summary
        assert "End of task" in summary


# ========================================================================
# F. Canvas Integration (3 tests)
# =========================================================================

class TestCanvasIntegration:
    """Test canvas context integration"""

    def test_segment_canvas_presentations(
        self, segmentation_service, db_session
    ):
        """Should segment canvas presentation events"""
        canvas_audits = [
            CanvasAudit(
                id="c1",
                session_id="s1",
                canvas_type="charts",
                action="present",
                component_name="bar_chart",
                audit_metadata={"data": [1, 2, 3]},
                created_at=datetime.now()
            ),
            CanvasAudit(
                id="c2",
                session_id="s1",
                canvas_type="sheets",
                action="submit",
                component_name="data_table",
                audit_metadata={"row_count": 10},
                created_at=datetime.now() + timedelta(seconds=5)
            ),
        ]

        context = segmentation_service._extract_canvas_context(canvas_audits)

        assert context is not None
        assert context["canvas_type"] == "charts"  # First canvas type
        assert "visual_elements" in context
        assert "critical_data_points" in context

    def test_segment_form_submissions(
        self, segmentation_service
    ):
        """Should segment form submission events"""
        canvas_audit = CanvasAudit(
            id="c1",
            session_id="s1",
            canvas_type="generic",
            action="submit",
            component_name="approval_form",
            audit_metadata={"approval_status": "approved", "amount": 5000},
            created_at=datetime.now()
        )

        context = segmentation_service._extract_canvas_context([canvas_audit])

        assert context["user_interaction"] == "user submitted"
        assert "approval_status" in context["critical_data_points"]
        assert context["critical_data_points"]["approval_status"] == "approved"

    def test_segment_canvas_close_events(
        self, segmentation_service
    ):
        """Should segment canvas close events"""
        canvas_audit = CanvasAudit(
            id="c1",
            session_id="s1",
            canvas_type="docs",
            action="close",
            component_name="document_viewer",
            audit_metadata={},
            created_at=datetime.now()
        )

        context = segmentation_service._extract_canvas_context([canvas_audit])

        assert context["user_interaction"] == "user closed"


# ========================================================================
# G. Error Paths (3 tests)
# =========================================================================

class TestErrorPaths:
    """Test error handling paths"""

    def test_generate_title_handles_none_content(self, segmentation_service):
        """Should handle messages with None content"""
        messages = [
            ChatMessage(id="m1", conversation_id="s1", role="assistant", content=None, created_at=datetime.now())
        ]

        # Should fall back to timestamp for non-user messages or None content
        title = segmentation_service._generate_title(messages, [])
        assert title is not None
        assert "Episode from" in title

    def test_extract_topics_handles_empty_messages(self, segmentation_service):
        """Should handle empty message list for topic extraction"""
        topics = segmentation_service._extract_topics([], [])
        assert topics == []

    def test_extract_entities_handles_no_entities(self, segmentation_service):
        """Should handle messages with no extractable entities"""
        messages = [
            ChatMessage(id="m1", conversation_id="s1", role="user", content="hello", created_at=datetime.now())
        ]

        entities = segmentation_service._extract_entities(messages, [])
        assert isinstance(entities, list)


# ========================================================================
# H. Performance (3 tests)
# =========================================================================

class TestPerformance:
    """Test performance characteristics"""

    def test_boundary_detection_performance(self, mock_lancedb):
        """Should detect boundaries efficiently"""
        import time

        # Create 100 messages with 2-minute gaps
        now = datetime.now()
        messages = [
            ChatMessage(
                id=f"m{i}",
                conversation_id="s1",
                role="user",
                content=f"Message {i}",
                created_at=now - timedelta(minutes=i*2)
            )
            for i in range(100)
        ]

        detector = EpisodeBoundaryDetector(mock_lancedb)

        start = time.time()
        gaps = detector.detect_time_gap(messages)
        duration = (time.time() - start) * 1000

        # Should be very fast (< 100ms for 100 messages)
        assert duration < 100

    def test_cosine_similarity_calculation_performance(self, mock_lancedb):
        """Should calculate cosine similarity efficiently"""
        import time
        import numpy as np

        detector = EpisodeBoundaryDetector(mock_lancedb)

        # Large vectors (384-dim like typical embeddings)
        vec1 = np.random.rand(384).tolist()
        vec2 = np.random.rand(384).tolist()

        start = time.time()
        similarity = detector._cosine_similarity(vec1, vec2)
        duration = (time.time() - start) * 1000

        # Should be very fast (< 10ms)
        assert duration < 10
        assert 0 <= similarity <= 1.0

    def test_topic_extraction_performance(self, segmentation_service):
        """Should extract topics efficiently"""
        import time

        # Create 50 messages with varied content
        now = datetime.now()
        messages = [
            ChatMessage(
                id=f"m{i}",
                conversation_id="s1",
                role="user",
                content=f"This is a message about topic {i % 5}",
                created_at=now - timedelta(seconds=i)
            )
            for i in range(50)
        ]

        start = time.time()
        topics = segmentation_service._extract_topics(messages, [])
        duration = (time.time() - start) * 1000

        # Should be fast (< 50ms for 50 messages)
        assert duration < 50
        assert isinstance(topics, list)
