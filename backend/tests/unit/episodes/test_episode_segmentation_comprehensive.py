"""
Comprehensive Episode Creation Flow Tests

Tests the complete episode creation pipeline from create_episode_from_session
through segmentation, canvas/feedback linkage, and LanceDB archival.

Target: 45%+ coverage on EpisodeSegmentationService (up from 17.1%)
"""

import pytest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from sqlalchemy.orm import Session

from core.episode_segmentation_service import EpisodeSegmentationService
from core.models import (
    AgentExecution,
    AgentFeedback,
    AgentRegistry,
    AgentStatus,
    CanvasAudit,
    ChatMessage,
    ChatSession,
    Episode,
    EpisodeSegment,
)


# ========================================================================
# TestEpisodeCreationFlow - Full Episode Creation Tests
# ========================================================================

class TestEpisodeCreationFlow:
    """Test complete episode creation flow from session"""

    @pytest.mark.asyncio
    async def test_create_episode_from_session_full_flow(
        self, segmentation_service_mocked, episode_test_session,
        episode_test_messages, episode_test_executions
    ):
        """Should create episode with full flow including segmentation"""
        db = segmentation_service_mocked.db
        session_id = episode_test_session.id
        agent_id = episode_test_executions[0].agent_id

        # Add test data to database
        for msg in episode_test_messages:
            db.add(msg)
        for exec in episode_test_executions:
            db.add(exec)
        db.commit()

        # Mock canvas and feedback queries to return empty
        with patch.object(db, 'query') as mock_query:
            # Setup mock query chain
            mock_query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            mock_query.return_value.filter.return_value.filter.return_value.all.return_value = []

            # Call create_episode_from_session
            episode = await segmentation_service_mocked.create_episode_from_session(
                session_id=session_id,
                agent_id=agent_id,
                force_create=True
            )

            # Verify episode created
            assert episode is not None
            assert episode.status == "completed"
            assert episode.agent_id == agent_id
            assert episode.session_id == session_id
            assert episode.user_id == episode_test_session.user_id

            # Verify timestamps
            assert episode.started_at is not None
            assert episode.ended_at is not None
            assert episode.duration_seconds is not None

            # Verify topics and entities extracted
            assert isinstance(episode.topics, list)
            assert isinstance(episode.entities, list)

            # Verify maturity captured
            assert episode.maturity_at_time in ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]

    @pytest.mark.asyncio
    async def test_create_episode_from_session_with_boundaries(
        self, segmentation_service_mocked, episode_test_session
    ):
        """Should create segments at time gap boundaries"""
        db = segmentation_service_mocked.db
        session_id = episode_test_session.id
        agent_id = str(uuid.uuid4())

        # Create messages with 35-minute gap (exceeds 30-min threshold)
        now = datetime.now(timezone.utc)
        messages = [
            ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id=session_id,
                role="user",
                content="First message",
                created_at=now - timedelta(minutes=70)
            ),
            ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id=session_id,
                role="assistant",
                content="Response 1",
                created_at=now - timedelta(minutes=65)
            ),
            # 35-minute gap here
            ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id=session_id,
                role="user",
                content="Second message after gap",
                created_at=now - timedelta(minutes=30)
            ),
            ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id=session_id,
                role="assistant",
                content="Response 2",
                created_at=now - timedelta(minutes=25)
            ),
        ]

        for msg in messages:
            db.add(msg)
        db.commit()

        # Mock canvas and feedback to return empty
        with patch.object(db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            mock_query.return_value.filter.return_value.filter.return_value.all.return_value = []

            # Create episode
            episode = await segmentation_service_mocked.create_episode_from_session(
                session_id=session_id,
                agent_id=agent_id,
                force_create=True
            )

            # Verify episode created
            assert episode is not None

            # Query segments to verify boundary detection
            segments = db.query(EpisodeSegment).filter(
                EpisodeSegment.episode_id == episode.id
            ).all()

            # Should have created segments
            assert len(segments) > 0

            # Verify sequence ordering
            sequence_orders = [s.sequence_order for s in segments]
            assert sequence_orders == sorted(sequence_orders)

    @pytest.mark.asyncio
    async def test_create_episode_from_session_too_small(
        self, segmentation_service_mocked, episode_test_session
    ):
        """Should return None for sessions with < 2 items (without force_create)"""
        db = segmentation_service_mocked.db
        session_id = episode_test_session.id
        agent_id = str(uuid.uuid4())

        # Create session with only 1 message
        now = datetime.now(timezone.utc)
        message = ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=session_id,
            role="user",
            content="Single message",
            created_at=now
        )
        db.add(message)
        db.commit()

        # Mock queries
        with patch.object(db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            mock_query.return_value.filter.return_value.filter.return_value.all.return_value = []

            # Call without force_create - should return None
            episode = await segmentation_service_mocked.create_episode_from_session(
                session_id=session_id,
                agent_id=agent_id,
                force_create=False
            )

            assert episode is None

            # Call with force_create=True - should create episode
            episode = await segmentation_service_mocked.create_episode_from_session(
                session_id=session_id,
                agent_id=agent_id,
                force_create=True
            )

            assert episode is not None
            assert episode.status == "completed"

    @pytest.mark.asyncio
    async def test_create_episode_from_session_session_not_found(
        self, segmentation_service_mocked
    ):
        """Should return None when session_id doesn't exist"""
        db = segmentation_service_mocked.db

        # Mock query to return None (session not found)
        with patch.object(db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.first.return_value = None

            # Call with non-existent session_id
            session_id = str(uuid.uuid4())
            agent_id = str(uuid.uuid4())

            episode = await segmentation_service_mocked.create_episode_from_session(
                session_id=session_id,
                agent_id=agent_id
            )

            assert episode is None

    def test_create_episode_from_session_title_generation(
        self, segmentation_service
    ):
        """Should generate title from first user message"""
        now = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id="session1",
                role="user",
                content="Analyze the sales data for Q4",
                created_at=now
            ),
            ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id="session1",
                role="assistant",
                content="OK",
                created_at=now
            ),
        ]

        title = segmentation_service._generate_title(messages, [])

        # Should use first user message
        assert "Analyze the sales data for Q4" in title

        # Test truncation at 50 chars
        long_message = ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id="session1",
            role="user",
            content="This is a very long message that exceeds fifty characters and should be truncated",
            created_at=now
        )

        title = segmentation_service._generate_title([long_message], [])
        assert len(title) <= 50
        assert title.endswith("...")

    def test_create_episode_from_session_title_fallback(
        self, segmentation_service
    ):
        """Should fall back to timestamp when no user messages"""
        title = segmentation_service._generate_title([], [])

        assert "Episode from" in title
        # Should include current date
        assert datetime.now().strftime('%Y-%m-%d') in title



# ========================================================================
# TestCanvasFeedbackLinkage - Canvas and Feedback Linkage Tests
# ========================================================================

class TestCanvasFeedbackLinkage:
    """Test canvas and feedback context linkage in episodes"""

    @pytest.mark.asyncio
    async def test_create_episode_with_canvas_context(
        self, segmentation_service_mocked, episode_test_session,
        episode_test_messages, episode_test_canvas_audit
    ):
        """Should link canvas context to episode"""
        db = segmentation_service_mocked.db
        session_id = episode_test_session.id
        agent_id = str(uuid.uuid4())

        # Add messages and canvas
        for msg in episode_test_messages[:3]:  # Use 3 messages
            db.add(msg)
        db.add(episode_test_canvas_audit)
        db.commit()

        # Mock canvas query to return our canvas
        def mock_canvas_query_side_effect(*args, **kwargs):
            # Return canvas when querying CanvasAudit
            mock_result = MagicMock()
            mock_result.all.return_value = [episode_test_canvas_audit]
            return mock_result

        with patch.object(db, 'query') as mock_query:
            # Setup canvas query
            mock_query.return_value.filter.return_value.order_by.return_value.all.side_effect = mock_canvas_query_side_effect
            # Mock feedback query to return empty
            mock_query.return_value.filter.return_value.filter.return_value.all.return_value = []

            # Create episode
            episode = await segmentation_service_mocked.create_episode_from_session(
                session_id=session_id,
                agent_id=agent_id,
                force_create=True
            )

            # Verify canvas linkage
            assert episode is not None
            assert len(episode.canvas_ids) > 0
            assert episode_test_canvas_audit.id in episode.canvas_ids
            assert episode.canvas_action_count == 1

            # Verify back-linkage (CanvasAudit.episode_id set)
            db.refresh(episode_test_canvas_audit)
            assert episode_test_canvas_audit.episode_id == episode.id

    @pytest.mark.asyncio
    async def test_create_episode_with_feedback_context(
        self, segmentation_service_mocked, episode_test_session,
        episode_test_messages, episode_test_executions, episode_test_feedback
    ):
        """Should link feedback context to episode"""
        db = segmentation_service_mocked.db
        session_id = episode_test_session.id
        agent_id = episode_test_executions[0].agent_id

        # Add messages, executions, and feedback
        for msg in episode_test_messages[:3]:
            db.add(msg)
        for exec in episode_test_executions:
            db.add(exec)
        db.add(episode_test_feedback)
        db.commit()

        # Mock feedback query to return our feedback
        def mock_feedback_query_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            mock_result.all.return_value = [episode_test_feedback]
            return mock_result

        with patch.object(db, 'query') as mock_query:
            # Setup canvas query to return empty
            mock_query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            # Setup feedback query
            mock_query.return_value.filter.return_value.filter.return_value.all.side_effect = mock_feedback_query_side_effect

            # Create episode
            episode = await segmentation_service_mocked.create_episode_from_session(
                session_id=session_id,
                agent_id=agent_id,
                force_create=True
            )

            # Verify feedback linkage
            assert episode is not None
            assert len(episode.feedback_ids) > 0
            assert episode_test_feedback.id in episode.feedback_ids
            assert episode.aggregate_feedback_score is not None

            # Verify back-linkage (AgentFeedback.episode_id set)
            db.refresh(episode_test_feedback)
            assert episode_test_feedback.episode_id == episode.id

    def test_fetch_canvas_context(
        self, segmentation_service, episode_test_session
    ):
        """Should fetch canvas audits for session"""
        db = segmentation.db
        session_id = episode_test_session.id

        # Create 3 canvas audits
        now = datetime.now(timezone.utc)
        canvases = [
            CanvasAudit(
                id=str(uuid.uuid4()),
                session_id=session_id,
                canvas_type="sheets",
                action="present",
                component_name=f"table_{i}",
                audit_metadata={"index": i},
                created_at=now - timedelta(minutes=10 - i)
            )
            for i in range(3)
        ]

        # Add to database
        for canvas in canvases:
            db.add(canvas)
        db.commit()

        # Fetch canvas context
        result = segmentation._fetch_canvas_context(session_id)

        # Verify returns 3 canvases ordered by created_at
        assert len(result) == 3
        # Should be ordered by created_at asc
        assert result[0].created_at <= result[1].created_at <= result[2].created_at

        # Test empty results
        empty_result = segmentation._fetch_canvas_context(str(uuid.uuid4()))
        assert empty_result == []

    def test_extract_canvas_context(
        self, segmentation_service
    ):
        """Should extract context from canvas audit metadata"""
        now = datetime.now(timezone.utc)

        canvas = CanvasAudit(
            id=str(uuid.uuid4()),
            session_id="session1",
            canvas_type="sheets",
            action="present",
            component_name="SalesChart",
            audit_metadata={
                "component": "SalesChart",
                "revenue": 1000000,
                "approval_status": "approved"
            },
            created_at=now
        )

        context = segmentation_service._extract_canvas_context([canvas])

        # Verify extracted fields
        assert context is not None
        assert context.get("canvas_type") == "sheets"
        assert "presentation_summary" in context
        assert "visual_elements" in context
        assert isinstance(context.get("critical_data_points"), dict)

    def test_filter_canvas_context_detail(
        self, segmentation_service
    ):
        """Should filter canvas context by detail level"""
        full_context = {
            "canvas_type": "sheets",
            "presentation_summary": "Sales data table with Q4 results",
            "visual_elements": ["table", "chart"],
            "user_interaction": "presented",
            "critical_data_points": {
                "revenue": 1000000,
                "approval_status": "approved"
            }
        }

        # Test "summary" detail level
        summary_context = segmentation_service._filter_canvas_context_detail(
            full_context, "summary"
        )
        assert "presentation_summary" in summary_context
        assert "visual_elements" not in summary_context
        assert "critical_data_points" not in summary_context

        # Test "standard" detail level
        standard_context = segmentation_service._filter_canvas_context_detail(
            full_context, "standard"
        )
        assert "presentation_summary" in standard_context
        assert "critical_data_points" in standard_context

        # Test "full" detail level
        full_result = segmentation_service._filter_canvas_context_detail(
            full_context, "full"
        )
        assert "presentation_summary" in full_result
        assert "visual_elements" in full_result
        assert "critical_data_points" in full_result

    def test_calculate_feedback_score(
        self, segmentation_service, episode_test_session
    ):
        """Should calculate aggregate feedback score"""
        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())

        # Create feedbacks: thumbs_up (+1.0), rating 4 (+0.5), thumbs_down (-1.0)
        feedbacks = [
            AgentFeedback(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                agent_execution_id=execution_id,
                user_id="user1",
                feedback_type="thumbs_up",
                thumbs_up_down=True,
                created_at=now
            ),
            AgentFeedback(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                agent_execution_id=execution_id,
                user_id="user1",
                feedback_type="rating",
                rating=4,  # Normalized to +0.5
                created_at=now
            ),
            AgentFeedback(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                agent_execution_id=execution_id,
                user_id="user1",
                feedback_type="thumbs_down",
                thumbs_up_down=False,
                created_at=now
            ),
        ]

        score = segmentation_service._calculate_feedback_score(feedbacks)

        # Aggregate: (1.0 + 0.5 - 1.0) / 3 = 0.5 / 3 ≈ 0.167
        assert score is not None
        assert abs(score - 0.167) < 0.01  # Allow small floating point error

        # Test empty list
        empty_score = segmentation_service._calculate_feedback_score([])
        assert empty_score is None



# ========================================================================
# TestSegmentCreationAndArchival - Segment Creation and LanceDB Archival
# ========================================================================

class TestSegmentCreationAndArchival:
    """Test episode segment creation and LanceDB archival"""

    @pytest.mark.asyncio
    async def test_create_segments_with_boundaries(
        self, segmentation_service, episode_test_session
    ):
        """Should create segments at boundary positions"""
        db = segmentation.db
        now = datetime.now(timezone.utc)
        session_id = episode_test_session.id

        # Create episode
        episode = Episode(
            id=str(uuid.uuid4()),
            title="Test Episode",
            agent_id="agent1",
            user_id="user1",
            session_id=session_id,
            status="completed",
            started_at=now - timedelta(hours=1),
            ended_at=now,
            created_at=now
        )
        db.add(episode)
        db.commit()

        # Create 5 messages
        messages = [
            ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id=session_id,
                role="user",
                content=f"Message {i}",
                created_at=now - timedelta(minutes=50 - i*10)
            )
            for i in range(5)
        ]

        # Set boundaries at positions 2 and 4
        boundaries = {2, 4}

        # Create segments
        await segmentation._create_segments(
            episode, messages, [], boundaries, {}
        )

        # Verify 3 segments created (0-1, 2-3, 4)
        segments = db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()

        assert len(segments) == 3

        # Verify sequence_order
        sequence_orders = [s.sequence_order for s in segments]
        assert sequence_orders == [0, 1, 2]

        # Verify segment type
        for segment in segments:
            assert segment.segment_type == "conversation"

    @pytest.mark.asyncio
    async def test_create_segments_with_executions(
        self, segmentation_service, episode_test_session
    ):
        """Should create execution segments with correct type"""
        db = segmentation.db
        now = datetime.now(timezone.utc)
        session_id = episode_test_session.id
        agent_id = "agent1"

        # Create episode
        episode = Episode(
            id=str(uuid.uuid4()),
            title="Test Episode",
            agent_id=agent_id,
            user_id="user1",
            session_id=session_id,
            status="completed",
            started_at=now - timedelta(hours=1),
            ended_at=now,
            created_at=now
        )
        db.add(episode)
        db.commit()

        # Create 2 executions
        executions = [
            AgentExecution(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                status="completed",
                input_summary=f"Task {i}",
                started_at=now - timedelta(minutes=30 - i*10)
            )
            for i in range(2)
        ]

        # Create segments
        await segmentation._create_segments(
            episode, [], executions, set(), {}
        )

        # Verify execution segments created
        segments = db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()

        assert len(segments) == 2

        # Verify segment types
        for segment in segments:
            assert segment.segment_type == "execution"
            assert segment.source_type == "agent_execution"

    @pytest.mark.asyncio
    async def test_create_segments_with_canvas_context(
        self, segmentation_service, episode_test_session
    ):
        """Should include canvas context in segment metadata"""
        db = segmentation.db
        now = datetime.now(timezone.utc)
        session_id = episode_test_session.id

        # Create episode
        episode = Episode(
            id=str(uuid.uuid4()),
            title="Test Episode",
            agent_id="agent1",
            user_id="user1",
            session_id=session_id,
            status="completed",
            started_at=now - timedelta(hours=1),
            ended_at=now,
            created_at=now
        )
        db.add(episode)
        db.commit()

        # Create messages
        messages = [
            ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id=session_id,
                role="user",
                content="Test message",
                created_at=now
            )
        ]

        # Create canvas context
        canvas_context = {
            "presentation_summary": "Agent presented sales chart"
        }

        # Create segments
        await segmentation._create_segments(
            episode, messages, [], set(), canvas_context
        )

        # Verify canvas context in segments
        segments = db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()

        assert len(segments) == 1
        segment = segments[0]

        # Verify canvas_context in metadata
        assert segment.canvas_context is not None
        assert "presentation_summary" in segment.canvas_context

    @pytest.mark.asyncio
    async def test_archive_to_lancedb(
        self, segmentation_service, mock_lancedb
    ):
        """Should archive episode to LanceDB"""
        now = datetime.now(timezone.utc)

        # Create episode
        episode = Episode(
            id=str(uuid.uuid4()),
            title="Test Episode",
            description="Test description",
            summary="Test summary",
            agent_id="agent1",
            user_id="user1",
            session_id="session1",
            status="completed",
            topics=["topic1", "topic2"],
            maturity_at_time="SUPERVISED",
            started_at=now - timedelta(hours=1),
            ended_at=now,
            created_at=now
        )

        # Mock LanceDB table doesn't exist yet
        mock_lancedb.db.table_names.return_value = []

        # Archive to LanceDB
        await segmentation._archive_to_lancedb(episode)

        # Verify create_table called
        mock_lancedb.create_table.assert_called_once_with("episodes")

        # Verify add_document called
        mock_lancedb.add_document.assert_called_once()
        call_args = mock_lancedb.add_document.call_args

        # Verify arguments
        assert call_args[1]["table_name"] == "episodes"
        assert "Test Episode" in call_args[1]["text"]
        assert "Test summary" in call_args[1]["text"]

        metadata = call_args[1]["metadata"]
        assert metadata["episode_id"] == episode.id
        assert metadata["agent_id"] == episode.agent_id
        assert metadata["status"] == "completed"
        assert "topic1" in metadata["topics"]
        assert metadata["maturity_at_time"] == "SUPERVISED"

    @pytest.mark.asyncio
    async def test_archive_to_lancedb_unavailable(
        self, segmentation_service
    ):
        """Should handle LanceDB unavailability gracefully"""
        now = datetime.now(timezone.utc)

        # Create episode
        episode = Episode(
            id=str(uuid.uuid4()),
            title="Test Episode",
            agent_id="agent1",
            user_id="user1",
            session_id="session1",
            status="completed",
            started_at=now - timedelta(hours=1),
            ended_at=now,
            created_at=now
        )

        # Mock LanceDB as unavailable
        segmentation.lancedb.db = None

        # Should not raise error
        await segmentation._archive_to_lancedb(episode)

        # Episode should still exist
        assert episode.id is not None

    def test_format_messages(
        self, segmentation_service
    ):
        """Should format messages as text"""
        now = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id="m1",
                conversation_id="s1",
                role="user",
                content="Hello",
                created_at=now
            ),
            ChatMessage(
                id="m2",
                conversation_id="s1",
                role="assistant",
                content="Hi there",
                created_at=now
            ),
        ]

        formatted = segmentation_service._format_messages(messages)

        assert "user: Hello" in formatted
        assert "assistant: Hi there" in formatted

    def test_summarize_messages(
        self, segmentation_service
    ):
        """Should summarize messages with truncation"""
        now = datetime.now(timezone.utc)

        # Single message
        single_msg = [ChatMessage(
            id="m1",
            conversation_id="s1",
            role="user",
            content="Single message",
            created_at=now
        )]

        summary = segmentation_service._summarize_messages(single_msg)
        assert "Single message" in summary

        # Multiple messages
        multi_msgs = [
            ChatMessage(
                id=f"m{i}",
                conversation_id="s1",
                role="user",
                content=f"Message {i}",
                created_at=now
            )
            for i in range(5)
        ]

        summary = segmentation_service._summarize_messages(multi_msgs)
        assert "Message 0" in summary
        assert "5 messages" in summary



# ========================================================================
# TestEpisodeHelperMethods - Episode Helper Method Tests
# ========================================================================

class TestEpisodeHelperMethods:
    """Test episode helper methods for topics, entities, importance"""

    def test_extract_topics_from_messages(
        self, segmentation_service
    ):
        """Should extract topics from message content"""
        now = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id="m1",
                conversation_id="s1",
                role="user",
                content="I need help with data analysis and machine learning",
                created_at=now
            ),
            ChatMessage(
                id="m2",
                conversation_id="s1",
                role="assistant",
                content="I can help with analytics",
                created_at=now
            ),
        ]

        topics = segmentation_service._extract_topics(messages, [])

        # Should return words > 4 chars
        assert isinstance(topics, list)
        # Topics should include relevant keywords
        assert len(topics) > 0

        # Should be limited to 5 topics
        assert len(topics) <= 5

    def test_extract_topics_empty(
        self, segmentation_service
    ):
        """Should return empty list for no messages"""
        topics = segmentation_service._extract_topics([], [])
        assert topics == []

    def test_extract_entities_from_messages(
        self, segmentation_service
    ):
        """Should extract email, phone, URL from messages"""
        now = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id="m1",
                conversation_id="s1",
                role="user",
                content="Contact john@example.com or call 555-123-4567. Visit https://example.com",
                created_at=now
            ),
        ]

        entities = segmentation_service._extract_entities(messages, [])

        # Should extract email, phone, URL
        assert isinstance(entities, list)
        assert len(entities) > 0

        # Check for specific entities
        entity_str = " ".join(entities)
        assert "john@example.com" in entity_str or "555-123-4567" in entity_str or "example.com" in entity_str

    def test_extract_entities_from_executions(
        self, segmentation_service
    ):
        """Should extract capitalized words from task descriptions"""
        now = datetime.now(timezone.utc)

        executions = [
            AgentExecution(
                id="exec1",
                agent_id="agent1",
                status="completed",
                input_summary="Create SalesReport for Marketing Team",
                started_at=now
            ),
        ]

        entities = segmentation_service._extract_entities([], executions)

        # Should extract capitalized words
        assert isinstance(entities, list)
        # Check for capitalized entities
        entity_str = " ".join(entities)
        # Should have some capitalized words
        assert len(entities) > 0

    def test_calculate_importance(
        self, segmentation_service
    ):
        """Should calculate importance score based on activity"""
        now = datetime.now(timezone.utc)

        # High importance: 15 messages
        many_messages = [
            ChatMessage(
                id=f"m{i}",
                conversation_id="s1",
                role="user",
                content=f"Message {i}",
                created_at=now
            )
            for i in range(15)
        ]

        score_high = segmentation_service._calculate_importance(many_messages, [])
        assert score_high > 0.5

        # Medium importance: 5 messages + 1 execution
        medium_messages = [
            ChatMessage(
                id=f"m{i}",
                conversation_id="s1",
                role="user",
                content=f"Message {i}",
                created_at=now
            )
            for i in range(5)
        ]

        execution = AgentExecution(
            id="exec1",
            agent_id="agent1",
            status="completed",
            started_at=now
        )

        score_medium = segmentation_service._calculate_importance(medium_messages, [execution])
        assert 0.0 <= score_medium <= 1.0

        # Low importance: 2 messages
        few_messages = [
            ChatMessage(
                id=f"m{i}",
                conversation_id="s1",
                role="user",
                content=f"Message {i}",
                created_at=now
            )
            for i in range(2)
        ]

        score_low = segmentation_service._calculate_importance(few_messages, [])
        assert 0.0 <= score_low <= 1.0

    def test_calculate_duration(
        self, segmentation_service
    ):
        """Should calculate duration from messages and executions"""
        now = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id="m1",
                conversation_id="s1",
                role="user",
                content="Start",
                created_at=now - timedelta(seconds=300)
            ),
            ChatMessage(
                id="m2",
                conversation_id="s1",
                role="assistant",
                content="End",
                created_at=now
            ),
        ]

        duration = segmentation_service._calculate_duration(messages, [])

        assert duration == 300  # 5 minutes in seconds

    def test_get_agent_maturity(
        self, segmentation_service, db_session
    ):
        """Should get agent maturity level"""
        agent_id = "test_agent"

        # Create agent with SUPERVISED status
        agent = AgentRegistry(
            id=agent_id,
            name="Test Agent",
            status=AgentStatus.SUPERVISED
        )
        db_session.add(agent)
        db_session.commit()

        maturity = segmentation_service._get_agent_maturity(agent_id)

        assert maturity == "supervised"  # Value, not enum

    def test_count_interventions(
        self, segmentation_service
    ):
        """Should count human interventions from executions"""
        now = datetime.now(timezone.utc)

        executions = [
            AgentExecution(
                id="exec1",
                agent_id="agent1",
                status="completed",
                input_summary="Task 1",
                started_at=now,
                metadata_json={"human_intervention": True}
            ),
            AgentExecution(
                id="exec2",
                agent_id="agent1",
                status="completed",
                input_summary="Task 2",
                started_at=now,
                metadata_json={"human_intervention": False}
            ),
            AgentExecution(
                id="exec3",
                agent_id="agent1",
                status="completed",
                input_summary="Task 3",
                started_at=now,
                metadata_json={}
            ),
        ]

        count = segmentation_service._count_interventions(executions)

        # Only exec1 has human_intervention=True
        assert count == 1


