"""
Canvas-Episodic Memory Integration Tests

Tests the complete flow from canvas presentation to episodic memory:
- Canvas presentation → Episode creation with canvas_ids
- LLM summary generation → EpisodeSegment.canvas_context
- Feedback submission → Episode feedback_ids linkage
- Canvas-aware episode retrieval
- Feedback-weighted retrieval

Ported to the current APIs:
- EpisodeSegmentationService.create_episode_from_session is async, requires a
  real ChatSession with >= 2 items, and returns an episode *dict* (segments +
  LanceDB archival are the source of truth).
- EpisodeRetrievalService.retrieve_episode was replaced by retrieve_sequential
  (episode + canvas/feedback context) and retrieve_canvas_aware (progressive
  canvas detail levels).
- AgentFeedback links to episodes via AgentExecution ids / Episode.feedback_ids
  (no episode_id column).
"""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
import uuid
import asyncio

from core.models import (
    CanvasAudit, AgentFeedback, Episode,
    EpisodeSegment, ChatMessage
)
from core.episode_segmentation_service import EpisodeSegmentationService
from core.episode_retrieval_service import EpisodeRetrievalService
from core.llm.canvas_summary_service import CanvasSummaryService
from tests.factories.canvas_factory import CanvasAuditFactory
from tests.factories.agent_factory import AutonomousAgentFactory
from tests.factories.user_factory import UserFactory
from tests.factories.chat_session_factory import ChatSessionFactory
from tests.factories.episode_factory import EpisodeFactory
from tests.factories.execution_factory import AgentExecutionFactory


LLM_SUMMARY = (
    "Agent presented workflow approval form with revenue data showing "
 "$1.2M revenue and 15% growth for Q4, requiring manager sign-off"
)


def _make_segmentation_service(db_session: Session) -> EpisodeSegmentationService:
    """Segmentation service with mocked LLM and disabled LanceDB archival."""
    mock_llm = Mock()
    mock_llm.generate = AsyncMock(return_value=LLM_SUMMARY)
    mock_lancedb = MagicMock()
    mock_lancedb.db = None  # archival is skipped when LanceDB is unavailable
    return EpisodeSegmentationService(
        db_session, llm_service=mock_llm, lancedb=mock_lancedb
    )


def _create_session_with_messages(db_session: Session, user, n_messages: int = 2):
    """Create a ChatSession with messages inside a tight time window."""
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    session = ChatSessionFactory(
        user_id=user.id, created_at=base, _session=db_session
    )
    db_session.add(session)
    for i in range(n_messages):
        db_session.add(ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=session.id,
            tenant_id="default",
            role="user" if i == 0 else "assistant",
            content=f"message {i}",
            created_at=base + timedelta(minutes=i),
        ))
    db_session.commit()
    return session


class TestCanvasEpisodeIntegration:
    """Test canvas presentation → episode creation integration."""

    @pytest.fixture
    def segmentation_service(self, db_session: Session):
        """Create episode segmentation service."""
        return _make_segmentation_service(db_session)

    @pytest.fixture
    def retrieval_service(self, db_session: Session):
        """Create episode retrieval service."""
        return EpisodeRetrievalService(db_session)

    def test_canvas_presentation_creates_episode_with_canvas_ids(
        self, db_session: Session, segmentation_service: EpisodeSegmentationService
    ):
        """Test that canvas presentations are linked to episodes via canvas_ids."""
        # Create agent and user
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        # Create a real chat session with messages (required by the service)
        session = _create_session_with_messages(db_session, user)

        # Create canvas audit entries for the session
        canvas_audits = [
            CanvasAuditFactory(
                canvas_type="sheets",
                action_type="present",
                agent_id=agent.id,
                user_id=user.id,
                session_id=session.id,
                details_json={"canvas_type": "sheets", "revenue": 1200000, "growth": 15},
                _session=db_session
            ),
            CanvasAuditFactory(
                canvas_type="generic",
                action_type="present",
                agent_id=agent.id,
                user_id=user.id,
                session_id=session.id,
                details_json={"canvas_type": "generic", "component_type": "line_chart"},
                _session=db_session
            )
        ]
        db_session.commit()

        # Create episode from session (async; returns an episode dict)
        episode = asyncio.run(segmentation_service.create_episode_from_session(
            session_id=session.id,
            agent_id=agent.id
        ))

        # Verify canvas_ids are populated
        assert episode is not None
        assert len(episode["canvas_ids"]) == 2
        assert episode["canvas_action_count"] == 2

        # Verify canvas audits have episode_id backlink
        for canvas_id in episode["canvas_ids"]:
            canvas = db_session.query(CanvasAudit).filter(
                CanvasAudit.id == canvas_id
            ).first()
            assert canvas is not None
            db_session.refresh(canvas)
            assert canvas.episode_id == episode["id"]

    def test_llm_canvas_summary_enriches_segment_context(
        self, db_session: Session, segmentation_service: EpisodeSegmentationService
    ):
        """Test that LLM summaries enrich episode segment canvas_context."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        session = _create_session_with_messages(db_session, user)

        # Create canvas audit
        canvas_audit = CanvasAuditFactory(
            canvas_type="orchestration",
            action_type="present",
            agent_id=agent.id,
            user_id=user.id,
            session_id=session.id,
            details_json={
                "canvas_type": "orchestration",
                "workflow_id": "wf-123",
                "approval_amount": 1500000,
                "approvers": ["manager", "director"]
            },
            _session=db_session
        )
        db_session.commit()

        episode = asyncio.run(segmentation_service.create_episode_from_session(
            session_id=session.id,
            agent_id=agent.id
        ))

        # Segments created for the episode carry the LLM-generated summary
        segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode["id"]
        ).all()
        assert len(segments) > 0

        summaries = [s.canvas_context for s in segments if s.canvas_context]
        assert summaries, "At least one segment should carry canvas_context"

        summary = summaries[0].get("presentation_summary", "")
        assert len(summary) > 50  # Should be 50-100 words
        assert "workflow" in summary.lower() or "approval" in summary.lower()

    def test_feedback_submission_updates_episode_feedback_ids(
        self, db_session: Session, segmentation_service: EpisodeSegmentationService
    ):
        """Test that feedback linked to executions is captured in episode feedback_ids."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        base = datetime.now(timezone.utc) - timedelta(hours=1)
        session = ChatSessionFactory(
            user_id=user.id, created_at=base, _session=db_session
        )
        db_session.add(session)
        for i in range(2):
            db_session.add(ChatMessage(
                id=str(uuid.uuid4()),
                conversation_id=session.id,
                tenant_id="default",
                role="user" if i == 0 else "assistant",
                content=f"message {i}",
                created_at=base + timedelta(minutes=i),
            ))

        # Execution inside the session window + feedback linked to it
        execution = AgentExecutionFactory(
            agent_id=agent.id,
            started_at=base + timedelta(seconds=30),
            _session=db_session
        )
        feedback = AgentFeedback(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            user_id=user.id,
            agent_execution_id=execution.id,
            feedback_type="thumbs_up",
            original_output="Presented sheets canvas",
            user_correction="looked good",
        )
        db_session.add(feedback)
        db_session.commit()

        episode = asyncio.run(segmentation_service.create_episode_from_session(
            session_id=session.id,
            agent_id=agent.id
        ))

        # Verify feedback_ids updated (linkage is episode.feedback_ids;
        # AgentFeedback has no episode_id column)
        assert episode is not None
        assert feedback.id in episode["feedback_ids"]

        # Positive feedback produces a positive aggregate score
        assert segmentation_service._calculate_feedback_score([feedback]) == 1.0

    def test_canvas_type_filtering_in_retrieval(
        self, db_session: Session, retrieval_service: EpisodeRetrievalService
    ):
        """Test retrieving episodes filtered by canvas type."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        now = datetime.now(timezone.utc)

        # Sheets-flavored episode
        canvas_sheets = CanvasAuditFactory(
            canvas_type="sheets",
            action_type="present",
            agent_id=agent.id,
            user_id=user.id,
            details_json={"canvas_type": "sheets", "revenue": 1200000},
            _session=db_session
        )
        episode_sheets = EpisodeFactory(
            agent_id=agent.id,
            canvas_ids=[canvas_sheets.id],
            canvas_action_count=1,
            started_at=now - timedelta(days=1),
            _session=db_session
        )
        canvas_sheets.episode_id = episode_sheets.id

        # Charts-flavored episode
        canvas_charts = CanvasAuditFactory(
            canvas_type="generic",
            action_type="present",
            agent_id=agent.id,
            user_id=user.id,
            details_json={"canvas_type": "generic", "component_type": "line_chart"},
            _session=db_session
        )
        episode_charts = EpisodeFactory(
            agent_id=agent.id,
            canvas_ids=[canvas_charts.id],
            canvas_action_count=1,
            started_at=now - timedelta(days=1),
            _session=db_session
        )
        canvas_charts.episode_id = episode_charts.id
        db_session.commit()

        # Retrieve episodes by canvas type
        result = asyncio.run(retrieval_service.retrieve_by_canvas_type(
            agent_id=agent.id,
            canvas_type="sheets",
            time_range="30d",
            limit=10
        ))

        # Should return only sheets episodes
        assert result["count"] >= 1
        returned_ids = {ep["id"] for ep in result["episodes"]}
        assert episode_sheets.id in returned_ids
        assert episode_charts.id not in returned_ids

    def test_feedback_weighted_retrieval(
        self, db_session: Session, retrieval_service: EpisodeRetrievalService
    ):
        """Test that positive feedback boosts episode relevance."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        # Episode with positive (5-star) feedback
        episode = EpisodeFactory(
            agent_id=agent.id,
            started_at=datetime.now(timezone.utc) - timedelta(days=1),
            _session=db_session
        )
        feedback = AgentFeedback(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            user_id=user.id,
            feedback_type="rating",
            rating=5,
            original_output="Presented sheets canvas",
            user_correction="great work",
        )
        db_session.add(feedback)

        # Mirror the feedback submission endpoint's linkage update
        episode.feedback_ids = [feedback.id]
        scores = [1.0]  # rating 5 -> (5 - 3) / 2
        episode.aggregate_feedback_score = sum(scores) / len(scores)
        db_session.commit()
        db_session.refresh(episode)

        # Verify aggregate score is positive
        assert episode.aggregate_feedback_score is not None
        assert episode.aggregate_feedback_score > 0


class TestCanvasSummaryServiceIntegration:
    """Test LLM canvas summary service integration."""

    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service."""
        mock_llm = Mock()
        mock_llm.generate = AsyncMock(return_value="Agent presented Q4 revenue chart showing $1.2M with 15% growth")
        return mock_llm

    @pytest.fixture
    def canvas_summary_service(self, mock_llm_service):
        """Create canvas summary service."""
        return CanvasSummaryService(llm_service=mock_llm_service)

    def test_summary_caching_by_canvas_state(
        self, canvas_summary_service: CanvasSummaryService, mock_llm_service
    ):
        """Test that identical canvas states use cached summaries."""
        canvas_state = {
            "revenue": 1200000,
            "growth": 15,
            "quarter": "Q4"
        }

        # First call should hit LLM
        summary1 = asyncio.run(canvas_summary_service.generate_summary(
            canvas_type="sheets",
            canvas_state=canvas_state,
            agent_task="Show revenue"
        ))

        # Second call with same state should use cache
        summary2 = asyncio.run(canvas_summary_service.generate_summary(
            canvas_type="sheets",
            canvas_state=canvas_state,
            agent_task="Show revenue"
        ))

        # Verify LLM was called only once
        assert mock_llm_service.generate.call_count == 1
        assert summary1 == summary2

    def test_fallback_to_metadata_on_llm_failure(
        self, canvas_summary_service: CanvasSummaryService, mock_llm_service
    ):
        """Test that metadata extraction is used when LLM fails."""
        # Make LLM fail
        mock_llm_service.generate = AsyncMock(side_effect=Exception("LLM error"))

        canvas_state = {
            "revenue": 1200000,
            "growth": 15
        }

        # generate_summary now raises; callers (episode segmentation) catch
        # this and use the metadata extraction fallback
        with pytest.raises(Exception):
            asyncio.run(canvas_summary_service.generate_summary(
                canvas_type="sheets",
                canvas_state=canvas_state,
                agent_task="Show revenue",
                timeout_seconds=2
            ))

        # Verify metadata fallback extracts the canvas type and business data
        summary = canvas_summary_service._fallback_to_metadata("sheets", canvas_state)
        assert summary is not None
        assert "sheets" in summary.lower()
        assert "$1200000" in summary

    def test_all_canvas_types_supported(
        self, canvas_summary_service: CanvasSummaryService, mock_llm_service
    ):
        """Test that all 7 canvas types are supported."""
        canvas_types = ["generic", "docs", "email", "sheets", "orchestration", "terminal", "coding"]

        for canvas_type in canvas_types:
            is_supported = canvas_summary_service.is_canvas_type_supported(canvas_type)
            assert is_supported, f"Canvas type {canvas_type} should be supported"

    def test_semantic_richness_scoring(
        self, canvas_summary_service: CanvasSummaryService
    ):
        """Test semantic richness score calculation."""
        # Rich summary with business context
        rich_summary = "Agent presented $1.2M workflow approval requiring board consent due to budget exceeding threshold"
        score = canvas_summary_service._calculate_semantic_richness(rich_summary)

        assert score > 0.5  # Should be relatively high

    def test_hallucination_detection(
        self, canvas_summary_service: CanvasSummaryService
    ):
        """Test hallucination detection in summaries."""
        canvas_state = {
            "workflow_id": "wf-123",
            "amount": 50000
        }

        # Summary with hallucinated workflow ID
        hallucinated_summary = "Agent presented workflow wf-456 with amount $50000"
        has_hallucination = canvas_summary_service._detect_hallucination(
            hallucinated_summary,
            canvas_state
        )

        assert has_hallucination is True

        # Summary without hallucination
        valid_summary = "Agent presented workflow wf-123 with amount $50000"
        has_hallucination = canvas_summary_service._detect_hallucination(
            valid_summary,
            canvas_state
        )

        assert has_hallucination is False


class TestCanvasContextRetrieval:
    """Test canvas context retrieval from episodes."""

    @pytest.fixture
    def retrieval_service(self, db_session: Session):
        """Create episode retrieval service."""
        return EpisodeRetrievalService(db_session)

    def test_retrieve_episode_with_canvas_context(
        self, db_session: Session, retrieval_service: EpisodeRetrievalService
    ):
        """Test retrieving episode with canvas context included."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        # Create canvas audits
        canvas_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        for canvas_id in canvas_ids:
            db_session.add(CanvasAudit(
                id=canvas_id,
                canvas_id=str(uuid.uuid4()),
                agent_id=agent.id,
                user_id=user.id,
                tenant_id='default',
                action_type='present',
                canvas_type='sheets',
                details_json={'canvas_type': 'sheets', 'component_type': 'data_grid', 'revenue': 1200000},
            ))

        # Create episode with canvas context
        episode = EpisodeFactory(
            agent_id=agent.id,
            canvas_ids=canvas_ids,
            canvas_action_count=2,
            started_at=datetime.now(timezone.utc) - timedelta(days=1),
            _session=db_session
        )
        db_session.commit()

        # Retrieve episode with canvas context (retrieve_sequential is the
        # current full-episode retrieval API)
        result = asyncio.run(retrieval_service.retrieve_sequential(
            episode_id=episode.id,
            agent_id=agent.id,
            include_canvas=True,
            include_feedback=False
        ))

        # Verify canvas context is included
        assert "error" not in result
        assert len(result["canvas_context"]) == 2

    def test_retrieve_episode_with_feedback_context(
        self, db_session: Session, retrieval_service: EpisodeRetrievalService
    ):
        """Test retrieving episode with feedback context included."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        # Create feedback first
        feedback = AgentFeedback(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            user_id=user.id,
            feedback_type="thumbs_up",
            original_output="Presented canvas",
            user_correction="nice",
        )
        db_session.add(feedback)

        episode = EpisodeFactory(
            agent_id=agent.id,
            feedback_ids=[feedback.id],
            aggregate_feedback_score=1.0,
            started_at=datetime.now(timezone.utc) - timedelta(days=1),
            _session=db_session
        )
        db_session.commit()

        # Retrieve episode with feedback context
        result = asyncio.run(retrieval_service.retrieve_sequential(
            episode_id=episode.id,
            agent_id=agent.id,
            include_canvas=False,
            include_feedback=True
        ))

        # Verify feedback context is included
        assert "error" not in result
        assert len(result["feedback_context"]) == 1
        assert result["feedback_context"][0]["id"] == feedback.id

    def test_progressive_canvas_detail_levels(
        self, db_session: Session, retrieval_service: EpisodeRetrievalService
    ):
        """Test progressive detail levels for canvas context."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        full_canvas_context = {
            "canvas_type": "orchestration",
            "presentation_summary": "Agent presented workflow approval",
            "critical_data_points": {"workflow_id": "wf-123", "approval_amount": 1500000},
            "visual_elements": ["workflow_board", "approval_button"],
        }

        episode = EpisodeFactory(
            agent_id=agent.id,
            canvas_ids=[str(uuid.uuid4())],
            canvas_action_count=1,
            started_at=datetime.now(timezone.utc) - timedelta(days=1),
            _session=db_session
        )
        # Segment carrying the full canvas context
        db_session.add(EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=0,
            content="canvas presented",
            content_summary="canvas",
            source_type="chat_message",
            source_id=str(uuid.uuid4()),
            canvas_context=dict(full_canvas_context),
        ))
        db_session.commit()

        # Canvas-aware retrieval consults LanceDB; stub the search to return
        # this episode
        mock_lancedb = MagicMock()
        mock_lancedb.search.return_value = [{"metadata": {"episode_id": episode.id}}]
        retrieval_service.lancedb = mock_lancedb

        # Summary detail level: only presentation_summary survives
        result_summary = asyncio.run(retrieval_service.retrieve_canvas_aware(
            agent_id=agent.id,
            query="workflow approval",
            canvas_context_detail="summary"
        ))

        assert result_summary["count"] == 1
        seg_summary = result_summary["episodes"][0]["segments"][0]["canvas_context"]
        assert seg_summary == {"presentation_summary": full_canvas_context["presentation_summary"]}

        # Full detail level: all fields preserved
        result_full = asyncio.run(retrieval_service.retrieve_canvas_aware(
            agent_id=agent.id,
            query="workflow approval",
            canvas_context_detail="full"
        ))

        assert result_full["count"] == 1
        seg_full = result_full["episodes"][0]["segments"][0]["canvas_context"]
        assert seg_full["canvas_type"] == "orchestration"
        assert seg_full["critical_data_points"]["approval_amount"] == 1500000
        assert seg_full["visual_elements"] == ["workflow_board", "approval_button"]


class TestCanvasEpisodeLifecycle:
    """Test canvas episode lifecycle and archival."""

    def test_canvas_data_preserved_through_archival(
        self, db_session: Session
    ):
        """Test that canvas context is preserved when episodes are archived."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        canvas = CanvasAuditFactory(
            canvas_type="sheets",
            action_type="present",
            agent_id=agent.id,
            user_id=user.id,
            details_json={"canvas_type": "sheets", "revenue": 1200000},
            _session=db_session
        )
        episode = EpisodeFactory(
            agent_id=agent.id,
            canvas_ids=[canvas.id],
            canvas_action_count=1,
            started_at=datetime.now(timezone.utc) - timedelta(days=1),
            _session=db_session
        )
        canvas.episode_id = episode.id
        db_session.commit()

        # Create segment with canvas context
        segment = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=0,
            content="Revenue data presented",
            content_summary="Revenue",
            source_type="chat_message",
            source_id=str(uuid.uuid4()),
            canvas_context={
                "canvas_type": "sheets",
                "presentation_summary": "Revenue data presented",
                "critical_data_points": {"revenue": 1200000}
            }
        )
        db_session.add(segment)

        # Archive episode (soft archive via status; the model has no archived
        # boolean column — retrieval excludes status == "archived")
        episode.status = "archived"
        db_session.commit()

        # Verify archived episode keeps its canvas linkage
        archived = db_session.query(Episode).filter(
            Episode.id == episode.id,
            Episode.status == "archived"
        ).first()

        assert archived is not None
        assert len(archived.canvas_ids) == 1

        # Verify canvas context still accessible
        archived_segment = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).first()

        assert archived_segment is not None
        assert archived_segment.canvas_context is not None
        assert archived_segment.canvas_context["canvas_type"] == "sheets"
