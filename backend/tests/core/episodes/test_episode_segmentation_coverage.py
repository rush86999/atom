"""
Coverage-driven tests for EpisodeSegmentationService (currently 0% -> target 80%+)

Focus areas from episode_segmentation_service.py:
- EpisodeBoundaryDetector.__init__ (lines 67-68)
- detect_time_gap (lines 70-87) - 30-minute threshold, EXCLUSIVE boundary
- detect_topic_changes (lines 89-115) - 0.75 similarity threshold
- detect_task_completion (lines 117-124)
- _cosine_similarity (lines 126-160) - with numpy and fallback
- _keyword_similarity (lines 162-199) - Dice coefficient fallback
- Segment creation and lifecycle management
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, AsyncMock
from core.episode_segmentation_service import (
    EpisodeSegmentationService,
    EpisodeBoundaryDetector,
    SegmentationResult,
    SegmentationBoundary,
    TIME_GAP_THRESHOLD_MINUTES,
    SEMANTIC_SIMILARITY_THRESHOLD
)


class TestEpisodeBoundaryDetectorInit:
    """Test EpisodeBoundaryDetector initialization (lines 67-68)."""

    def test_init_with_lancedb_handler(self):
        """Cover lines 67-68: Initialize with LanceDB handler."""
        mock_db = MagicMock()
        detector = EpisodeBoundaryDetector(lancedb_handler=mock_db)

        assert detector.db is mock_db


class TestTimeGapDetection:
    """Test time gap detection (lines 70-87)."""

    def test_detect_time_gap_below_threshold(self):
        """Cover lines 70-87: Gap below 30 min threshold (no segmentation)."""
        from core.models import ChatMessage

        base_time = datetime.now(timezone.utc)
        messages = [
            ChatMessage(id="1", content="First", created_at=base_time, conversation_id="s1", tenant_id="t1", role="user"),
            ChatMessage(id="2", content="Second", created_at=base_time + timedelta(minutes=10), conversation_id="s1", tenant_id="t1", role="user"),
        ]

        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        gaps = detector.detect_time_gap(messages)

        assert len(gaps) == 0  # Below threshold

    @pytest.mark.parametrize("gap_minutes,should_segment", [
        (30, False),   # Exactly threshold: NO segment (EXCLUSIVE boundary)
        (31, True),    # Above threshold: YES segment
        (35, True),    # Well above threshold: YES segment
        (60, True),    # 1 hour gap: YES segment
        (120, True),   # 2 hour gap: YES segment
    ])
    def test_time_gap_threshold_boundary(self, gap_minutes, should_segment):
        """Cover line 84: EXCLUSIVE boundary (>) not inclusive (>=)."""
        from core.models import ChatMessage

        base_time = datetime.now(timezone.utc)
        messages = [
            ChatMessage(id="1", content="Before", created_at=base_time, conversation_id="s1", tenant_id="t1", role="user"),
            ChatMessage(id="2", content="After", created_at=base_time + timedelta(minutes=gap_minutes), conversation_id="s1", tenant_id="t1", role="user"),
        ]

        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        gaps = detector.detect_time_gap(messages)

        if should_segment:
            assert len(gaps) == 1
            assert gaps[0] == 1  # Index of second message
        else:
            assert len(gaps) == 0

    def test_detect_multiple_time_gaps(self):
        """Cover lines 79-85: Multiple gaps detected correctly."""
        from core.models import ChatMessage

        base_time = datetime.now(timezone.utc)
        messages = [
            ChatMessage(id="1", content="First", created_at=base_time, conversation_id="s1", tenant_id="t1", role="user"),
            ChatMessage(id="2", content="Second", created_at=base_time + timedelta(minutes=10), conversation_id="s1", tenant_id="t1", role="user"),
            ChatMessage(id="3", content="Third", created_at=base_time + timedelta(minutes=50), conversation_id="s1", tenant_id="t1", role="user"),
            ChatMessage(id="4", content="Fourth", created_at=base_time + timedelta(minutes=55), conversation_id="s1", tenant_id="t1", role="user"),
        ]

        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        gaps = detector.detect_time_gap(messages)

        # Should detect gap at index 2 (50 min gap from message 2)
        assert len(gaps) >= 1
        assert 2 in gaps

    def test_detect_time_gap_empty_list(self):
        """Cover lines 79-87: Empty list returns no gaps."""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        gaps = detector.detect_time_gap([])
        assert len(gaps) == 0

    def test_detect_time_gap_single_message(self):
        """Cover lines 79-87: Single message returns no gaps."""
        from core.models import ChatMessage

        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        messages = [ChatMessage(id="1", content="Only", created_at=datetime.now(timezone.utc), conversation_id="s1", tenant_id="t1", role="user")]
        gaps = detector.detect_time_gap(messages)
        assert len(gaps) == 0


class TestTopicChangeDetection:
    """Test topic change detection (lines 89-115)."""

    @pytest.mark.parametrize("similarity_score,expected_change", [
        (0.90, False),  # Very similar: same topic
        (0.75, False),  # At threshold: same topic
        (0.74, True),   # Below threshold: new topic
        (0.50, True),   # Different: new topic
        (0.30, True),   # Very different: new topic
    ])
    def test_topic_similarity_threshold(self, similarity_score, expected_change):
        """Cover line 112: Similarity < 0.75 triggers new segment."""
        from core.models import ChatMessage

        messages = [
            ChatMessage(id="1", content="First message", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user"),
            ChatMessage(id="2", content="Second message", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user"),
        ]

        mock_db = MagicMock()
        mock_db.embed_text = MagicMock(return_value=[0.1] * 384)  # Mock embedding

        detector = EpisodeBoundaryDetector(lancedb_handler=mock_db)

        with patch.object(detector, '_cosine_similarity', return_value=similarity_score):
            changes = detector.detect_topic_changes(messages)

            if expected_change:
                assert len(changes) >= 1
            else:
                assert len(changes) == 0

    def test_topic_change_with_embedding_failure(self):
        """Cover lines 105-107: Fallback to keyword similarity when embeddings fail."""
        from core.models import ChatMessage

        messages = [
            ChatMessage(id="1", content="python programming", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user"),
            ChatMessage(id="2", content="cooking recipes", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user"),
        ]

        mock_db = MagicMock()
        mock_db.embed_text = MagicMock(return_value=None)  # Embedding fails

        detector = EpisodeBoundaryDetector(lancedb_handler=mock_db)
        changes = detector.detect_topic_changes(messages)

        # Should use keyword fallback and detect topic change
        assert len(changes) >= 1

    def test_topic_change_empty_messages(self):
        """Cover lines 96-97: Empty list returns no changes."""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        changes = detector.detect_topic_changes([])
        assert len(changes) == 0

    def test_topic_change_no_db_handler(self):
        """Cover lines 96-97: None db handler returns no changes."""
        from core.models import ChatMessage

        messages = [
            ChatMessage(id="1", content="First", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user"),
            ChatMessage(id="2", content="Second", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user"),
        ]

        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        changes = detector.detect_topic_changes(messages)
        assert len(changes) == 0

    def test_topic_change_single_message(self):
        """Cover lines 96-97: Single message returns no changes."""
        from core.models import ChatMessage

        messages = [
            ChatMessage(id="1", content="Only", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user"),
        ]

        mock_db = MagicMock()
        mock_db.embed_text = MagicMock(return_value=[0.1] * 384)

        detector = EpisodeBoundaryDetector(lancedb_handler=mock_db)
        changes = detector.detect_topic_changes(messages)
        assert len(changes) == 0


class TestCosineSimilarity:
    """Test cosine similarity calculation (lines 126-160)."""

    @pytest.mark.parametrize("vec1,vec2,expected", [
        ([1, 0, 0], [1, 0, 0], 1.0),      # Identical vectors
        ([1, 0, 0], [0, 1, 0], 0.0),      # Orthogonal vectors
        ([1, 1, 1], [2, 2, 2], 1.0),      # Parallel vectors
        ([0, 0, 0], [1, 1, 1], 0.0),      # Zero magnitude vector
    ])
    def test_cosine_similarity_calculation(self, vec1, vec2, expected):
        """Cover lines 126-160: Cosine similarity with various vectors."""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        result = detector._cosine_similarity(vec1, vec2)
        assert abs(result - expected) < 0.001

    def test_cosine_similarity_numpy_fallback(self):
        """Cover lines 141-160: Pure Python fallback when numpy unavailable."""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)

        with patch.dict('sys.modules', {'numpy': None}):
            # Should use pure Python implementation
            result = detector._cosine_similarity([1, 2, 3], [4, 5, 6])
            assert 0 <= result <= 1.0

    def test_cosine_similarity_zero_magnitude(self):
        """Cover lines 134-138: Zero magnitude handling."""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        result = detector._cosine_similarity([0, 0, 0], [1, 1, 1])
        assert result == 0.0

    def test_cosine_similarity_different_lengths(self):
        """Cover cosine similarity with different length vectors."""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        # Should handle different lengths
        result = detector._cosine_similarity([1, 2], [3, 4, 5])
        # Only compare first 2 elements
        assert 0 <= result <= 1.0


class TestKeywordSimilarity:
    """Test keyword similarity fallback (lines 162-199)."""

    @pytest.mark.parametrize("text1,text2,expected_similarity", [
        ("hello world", "hello world", 1.0),           # Identical
        ("hello world", "hello there", 0.66),          # Partial overlap
        ("python code", "java code", 0.5),             # Some overlap
        ("completely different", "no match here", 0.0),  # No overlap
        ("", "text", 0.0),                             # Empty string
        ("text", "", 0.0),                             # Empty string
    ])
    def test_keyword_similarity_dice_coefficient(self, text1, text2, expected_similarity):
        """Cover lines 162-199: Dice coefficient calculation."""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        result = detector._keyword_similarity(text1, text2)
        assert abs(result - expected_similarity) < 0.2  # Allow some tolerance

    def test_keyword_similarity_case_insensitive(self):
        """Cover lines 171-172: Case insensitivity."""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        result = detector._keyword_similarity("Hello World", "hello world")
        assert result == 1.0

    def test_keyword_similarity_word_overlap(self):
        """Cover lines 179-193: Word overlap calculation."""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        # "python is great" vs "great python code"
        result = detector._keyword_similarity("python is great", "great python code")
        # Should detect overlap: python, great
        assert result > 0.5


class TestTaskCompletionDetection:
    """Test task completion detection (lines 117-124)."""

    @pytest.mark.parametrize("status,has_summary,should_detect", [
        ("completed", True, True),     # Completed with summary
        ("completed", False, False),   # Completed without summary
        ("failed", True, False),       # Failed status
        ("running", True, False),      # Still running
        ("pending", True, False),      # Not started
    ])
    def test_detect_task_completion(self, status, has_summary, should_detect):
        """Cover lines 117-124: Task completion marker detection."""
        from core.models import AgentExecution

        executions = [
            AgentExecution(
                id="1",
                status=status,
                result_summary="Task completed successfully" if has_summary else None,
                agent_id="agent1",
                input_summary="test task",
                started_at=datetime.now(),
            )
        ]

        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        completions = detector.detect_task_completion(executions)

        if should_detect:
            assert len(completions) == 1
            assert completions[0] == 0
        else:
            assert len(completions) == 0

    def test_detect_task_completion_empty_list(self):
        """Cover lines 119-124: Empty list returns no completions."""
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        completions = detector.detect_task_completion([])
        assert len(completions) == 0

    def test_detect_task_completion_multiple_tasks(self):
        """Cover lines 119-124: Multiple task detection."""
        from core.models import AgentExecution

        executions = [
            AgentExecution(
                id="1",
                status="completed",
                result_summary="First task",
                agent_id="agent1",
                input_summary="task1",
                started_at=datetime.now(),
            ),
            AgentExecution(
                id="2",
                status="running",
                result_summary=None,
                agent_id="agent1",
                input_summary="task2",
                started_at=datetime.now(),
            ),
            AgentExecution(
                id="3",
                status="completed",
                result_summary="Second task",
                agent_id="agent1",
                input_summary="task3",
                started_at=datetime.now(),
            ),
        ]

        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        completions = detector.detect_task_completion(executions)

        # Should detect 2 completions (indices 0 and 2)
        assert len(completions) == 2
        assert 0 in completions
        assert 2 in completions


class TestEpisodeSegmentationService:
    """Test main segmentation service methods."""

    def test_init(self, db_session):
        """Cover EpisodeSegmentationService initialization (lines 205-218)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session)

        assert service.db is db_session
        assert service.lancedb is not None
        assert service.detector is not None
        assert service.byok_handler is not None
        assert service.canvas_summary_service is not None

    def test_generate_title(self, db_session):
        """Cover _generate_title method (lines 331-343)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import ChatMessage

        service = EpisodeSegmentationService(db_session)

        # Test with user message
        messages = [
            ChatMessage(id="1", content="This is a very long message that should be truncated", role="user", created_at=datetime.now(), conversation_id="s1", tenant_id="t1")
        ]
        title = service._generate_title(messages, [])

        assert "This is a very long message that should be" in title
        assert "..." in title

    def test_generate_title_no_messages(self, db_session):
        """Cover _generate_title with no messages (lines 334, 343)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session)
        title = service._generate_title([], [])

        assert "Episode from" in title

    def test_generate_description(self, db_session):
        """Cover _generate_description method (lines 345-349)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import ChatMessage

        service = EpisodeSegmentationService(db_session)

        messages = [ChatMessage(id="1", content="Test", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user")]
        description = service._generate_description(messages, [])

        assert "1 messages" in description

    def test_generate_summary(self, db_session):
        """Cover _generate_summary method (lines 351-358)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import ChatMessage

        service = EpisodeSegmentationService(db_session)

        messages = [
            ChatMessage(id="1", content="First message", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user"),
            ChatMessage(id="2", content="Last message", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user"),
        ]
        summary = service._generate_summary(messages, [])

        assert "First message" in summary
        assert "Last message" in summary

    def test_extract_topics(self, db_session):
        """Cover _extract_topics method (lines 381-395)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import ChatMessage

        service = EpisodeSegmentationService(db_session)

        messages = [
            ChatMessage(id="1", content="python programming language tutorial", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user"),
        ]
        topics = service._extract_topics(messages, [])

        assert "python" in topics
        assert "programming" in topics

    def test_extract_topics_no_content(self, db_session):
        """Cover _extract_topics with None content (lines 388-389)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import ChatMessage

        service = EpisodeSegmentationService(db_session)

        messages = [
            ChatMessage(id="1", content=None, created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user"),
        ]
        topics = service._extract_topics(messages, [])

        assert topics == []

    def test_calculate_importance(self, db_session):
        """Cover _calculate_importance method (lines 456-471)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import ChatMessage

        service = EpisodeSegmentationService(db_session)

        # High importance (many messages + executions)
        messages = [ChatMessage(id=str(i), content=f"Message {i}", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user") for i in range(15)]
        importance = service._calculate_importance(messages, [MagicMock()])

        assert importance > 0.5

    def test_get_agent_maturity(self, db_session):
        """Cover _get_agent_maturity method (lines 473-484)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import AgentRegistry, AgentStatus

        service = EpisodeSegmentationService(db_session)

        # Test with non-existent agent (returns "STUDENT")
        maturity = service._get_agent_maturity("nonexistent-agent")
        assert maturity == "STUDENT"

    def test_count_interventions(self, db_session):
        """Cover _count_interventions method (lines 486-493)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import AgentExecution

        service = EpisodeSegmentationService(db_session)

        executions = [
            AgentExecution(
                id="1",
                status="completed",
                metadata_json={"human_intervention": True},
                agent_id="agent1",
                input_summary="test",
                started_at=datetime.now(),
            ),
            AgentExecution(
                id="2",
                status="completed",
                metadata_json=None,
                agent_id="agent1",
                input_summary="test",
                started_at=datetime.now(),
            ),
        ]

        count = service._count_interventions(executions)

        assert count == 1

    def test_extract_human_edits(self, db_session):
        """Cover _extract_human_edits method (lines 495-501)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import AgentExecution

        service = EpisodeSegmentationService(db_session)

        executions = [
            AgentExecution(
                id="1",
                status="completed",
                metadata_json={"human_corrections": ["edit1", "edit2"]},
                agent_id="agent1",
                input_summary="test",
                started_at=datetime.now(),
            ),
        ]

        edits = service._extract_human_edits(executions)

        assert len(edits) == 2

    def test_format_messages(self, db_session):
        """Cover _format_messages method (lines 579-584)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import ChatMessage

        service = EpisodeSegmentationService(db_session)

        messages = [
            ChatMessage(id="1", content="Hello", role="user", created_at=datetime.now(), conversation_id="s1", tenant_id="t1"),
            ChatMessage(id="2", content="Hi there", role="assistant", created_at=datetime.now(), conversation_id="s1", tenant_id="t1"),
        ]

        formatted = service._format_messages(messages)

        assert "user: Hello" in formatted
        assert "assistant: Hi there" in formatted

    def test_summarize_messages(self, db_session):
        """Cover _summarize_messages method (lines 586-594)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import ChatMessage

        service = EpisodeSegmentationService(db_session)

        messages = [
            ChatMessage(id="1", content="First message content here", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user"),
            ChatMessage(id="2", content="Second message content here", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user"),
        ]

        summary = service._summarize_messages(messages)

        assert "First message content here" in summary
        assert "2 messages" in summary

    def test_format_execution(self, db_session):
        """Cover _format_execution method (lines 596-609)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import AgentExecution

        service = EpisodeSegmentationService(db_session)

        exec = AgentExecution(
            id="1",
            status="completed",
            input_summary="Test task",
            result_summary="Task completed",
            agent_id="agent1",
            started_at=datetime.now(),
        )

        formatted = service._format_execution(exec)

        assert "Task: Test task" in formatted
        assert "Status: completed" in formatted
        assert "Result: Task completed" in formatted

    def test_extract_entities(self, db_session):
        """Cover _extract_entities method (lines 397-454)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import ChatMessage

        service = EpisodeSegmentationService(db_session)

        messages = [
            ChatMessage(id="1", content="Email test@example.com for support", created_at=datetime.now(), conversation_id="s1", tenant_id="t1", role="user"),
        ]

        entities = service._extract_entities(messages, [])

        assert "test@example.com" in entities

    def test_calculate_duration(self, db_session):
        """Cover _calculate_duration method (lines 360-379)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import ChatMessage

        service = EpisodeSegmentationService(db_session)

        base_time = datetime.now(timezone.utc)
        messages = [
            ChatMessage(id="1", content="First", created_at=base_time, conversation_id="s1", tenant_id="t1", role="user"),
            ChatMessage(id="2", content="Second", created_at=base_time + timedelta(seconds=30), conversation_id="s1", tenant_id="t1", role="user"),
        ]

        duration = service._calculate_duration(messages, [])

        assert duration == 30

    def test_calculate_duration_no_timestamps(self, db_session):
        """Cover _calculate_duration with no timestamps (lines 374-375)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session)

        duration = service._calculate_duration([], [])

        assert duration is None

class TestAsyncMethods:
    """Test async methods that need special handling."""

    @pytest.mark.asyncio
    async def test_create_episode_from_session_small_session(self, db_session):
        """Cover create_episode_from_session with small session (lines 278-286)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import ChatSession, ChatMessage

        service = EpisodeSegmentationService(db_session)

        # Create session
        session = ChatSession(
            id="session1",
            user_id="user1",
            tenant_id="t1",
            created_at=datetime.now()
        )
        db_session.add(session)
        db_session.commit()

        # Add small message (below threshold)
        msg = ChatMessage(
            id="msg1",
            content="Single message",
            role="user",
            conversation_id="session1",
            tenant_id="t1",
            created_at=datetime.now()
        )
        db_session.add(msg)
        db_session.commit()

        # Should return None for small session
        result = await service.create_episode_from_session("session1", "agent1", force_create=False)
        assert result is None

    @pytest.mark.asyncio
    async def test_create_episode_from_session_force_create(self, db_session):
        """Cover create_episode_from_session with force_create (lines 284-286)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import ChatSession, ChatMessage

        service = EpisodeSegmentationService(db_session)

        # Create session
        session = ChatSession(
            id="session2",
            user_id="user1",
            tenant_id="t1",
            created_at=datetime.now()
        )
        db_session.add(session)
        db_session.commit()

        # Add small message
        msg = ChatMessage(
            id="msg2",
            content="Single message",
            role="user",
            conversation_id="session2",
            tenant_id="t1",
            created_at=datetime.now()
        )
        db_session.add(msg)
        db_session.commit()

        # Force create should work
        result = await service.create_episode_from_session("session2", "agent1", force_create=True)
        assert result is not None
        assert "id" in result

    @pytest.mark.asyncio
    async def test_create_episode_nonexistent_session(self, db_session):
        """Cover create_episode_from_session with nonexistent session (lines 244-246)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session)

        result = await service.create_episode_from_session("nonexistent", "agent1")
        assert result is None

    def test_get_world_model_version_env_var(self, db_session, monkeypatch):
        """Cover _get_world_model_version from env var (lines 506-508)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        monkeypatch.setenv("WORLD_MODEL_VERSION", "v2.0")

        service = EpisodeSegmentationService(db_session)
        version = service._get_world_model_version()

        assert version == "v2.0"

    def test_get_world_model_version_default(self, db_session, monkeypatch):
        """Cover _get_world_model_version default (lines 522-523)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        monkeypatch.delenv("WORLD_MODEL_VERSION", raising=False)

        service = EpisodeSegmentationService(db_session)
        version = service._get_world_model_version()

        assert version == "v1.0"

    def test_extract_canvas_context_empty_list(self, db_session):
        """Cover _extract_canvas_context with empty list (lines 968-969)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session)
        result = service._extract_canvas_context([])

        assert result == {}

    def test_fetch_canvas_context_exception(self, db_session):
        """Cover _fetch_canvas_context exception handling (lines 678-680)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session)

        # Pass invalid session_id to trigger exception
        result = service._fetch_canvas_context("invalid-session-id")
        
        # Should return empty list on error
        assert result == []

    def test_fetch_feedback_context_empty_list(self, db_session):
        """Cover _fetch_feedback_context with empty list (lines 794-795)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session)
        result = service._fetch_feedback_context("session1", "agent1", [])

        assert result == []

    def test_calculate_feedback_score_none(self, db_session):
        """Cover _calculate_feedback_score with None feedback (lines 825-826)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session)
        score = service._calculate_feedback_score([])

        assert score is None

    def test_calculate_feedback_score_thumbs_up(self, db_session):
        """Cover _calculate_feedback_score thumbs_up (lines 831-832)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import AgentFeedback

        service = EpisodeSegmentationService(db_session)

        feedback = AgentFeedback(
            id="f1",
            agent_id="agent1",
            feedback_type="thumbs_up",
            thumbs_up_down=True,
            created_at=datetime.now()
        )

        score = service._calculate_feedback_score([feedback])

        assert score == 1.0

    def test_calculate_feedback_score_thumbs_down(self, db_session):
        """Cover _calculate_feedback_score thumbs_down (lines 833-834)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import AgentFeedback

        service = EpisodeSegmentationService(db_session)

        feedback = AgentFeedback(
            id="f2",
            agent_id="agent1",
            feedback_type="thumbs_down",
            thumbs_up_down=False,
            created_at=datetime.now()
        )

        score = service._calculate_feedback_score([feedback])

        assert score == -1.0

    def test_calculate_feedback_score_rating(self, db_session):
        """Cover _calculate_feedback_score rating (lines 835-838)."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import AgentFeedback

        service = EpisodeSegmentationService(db_session)

        # Test rating 5 -> +1.0
        feedback5 = AgentFeedback(
            id="f5",
            agent_id="agent1",
            feedback_type="rating",
            rating=5,
            created_at=datetime.now()
        )

        score = service._calculate_feedback_score([feedback5])

        assert score == 1.0

    def test_extract_canvas_context_metadata_basic(self, db_session):
        """Cover _extract_canvas_context_metadata basic case."""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import CanvasAudit

        service = EpisodeSegmentationService(db_session)

        audit = CanvasAudit(
            id="canvas1",
            canvas_type="sheets",
            action="present",
            created_at=datetime.now()
        )

        result = service._extract_canvas_context_metadata(audit, None)

        assert result["canvas_type"] == "sheets"
        assert result["summary_source"] == "metadata"

    def test_filter_canvas_context_detail_summary(self, db_session):
        """Cover _filter_canvas_context_detail with 'summary' (lines 1050-1055)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session)

        context = {
            "canvas_type": "sheets",
            "presentation_summary": "Test summary",
            "visual_elements": ["chart"],
            "critical_data_points": {"revenue": 1000}
        }

        result = service._filter_canvas_context_detail(context, "summary")

        assert result == {
            "canvas_type": "sheets",
            "presentation_summary": "Test summary"
        }

    def test_filter_canvas_context_detail_standard(self, db_session):
        """Cover _filter_canvas_context_detail with 'standard' (lines 1057-1063)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session)

        context = {
            "canvas_type": "sheets",
            "presentation_summary": "Test summary",
            "visual_elements": ["chart"],
            "critical_data_points": {"revenue": 1000}
        }

        result = service._filter_canvas_context_detail(context, "standard")

        assert result == {
            "canvas_type": "sheets",
            "presentation_summary": "Test summary",
            "critical_data_points": {"revenue": 1000}
        }

    def test_filter_canvas_context_detail_full(self, db_session):
        """Cover _filter_canvas_context_detail with 'full' (lines 1065-1067)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session)

        context = {
            "canvas_type": "sheets",
            "presentation_summary": "Test summary",
            "visual_elements": ["chart"],
            "critical_data_points": {"revenue": 1000}
        }

        result = service._filter_canvas_context_detail(context, "full")

        assert result == context

    def test_filter_canvas_context_detail_unknown(self, db_session):
        """Cover _filter_canvas_context_detail with unknown level (lines 1071-1072)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session)

        context = {
            "canvas_type": "sheets",
            "presentation_summary": "Test summary"
        }

        result = service._filter_canvas_context_detail(context, "unknown")

        # Should default to summary
        assert "presentation_summary" in result
        assert "canvas_type" in result

    def test_extract_skill_metadata(self, db_session):
        """Cover extract_skill_metadata method (lines 1430-1448)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session)

        context_data = {
            "skill_name": "test_skill",
            "skill_source": "community",
            "error_type": None,
            "execution_time": 1.5,
            "input_summary": "test input"
        }

        metadata = service.extract_skill_metadata(context_data)

        assert metadata["skill_name"] == "test_skill"
        assert metadata["skill_source"] == "community"
        assert metadata["execution_successful"] is True
        assert metadata["execution_time"] == 1.5

    def test_summarize_skill_inputs(self, db_session):
        """Cover _summarize_skill_inputs method (lines 1509-1521)."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session)

        inputs = {
            "param1": "short value",
            "param2": "x" * 200,  # Long value that should be truncated
            "param3": "normal value"
        }

        summary = service._summarize_skill_inputs(inputs)

        assert "param1" in summary
        assert len(summary["param2"]) < 100  # Should be truncated
        assert "..." in summary["param2"]
