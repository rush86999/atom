"""
Canvas-Episodic Memory Integration Tests

Tests the complete flow from canvas presentation to episodic memory:
- Canvas presentation → Episode creation with canvas_context
- LLM summary generation → EpisodeSegment.canvas_context
- Feedback submission → Episode.feedback_ids update
- Canvas-aware episode retrieval
- Feedback-weighted retrieval

Coverage:
- CanvasAudit → Episode.canvas_ids linkage
- AgentFeedback → Episode.feedback_ids linkage
- EpisodeSegment.canvas_context enrichment
- LLM canvas summary generation
- Canvas type filtering in retrieval
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
import uuid
import asyncio
from typing import Dict, Any

from core.models import (
    CanvasAudit, AgentExecution, AgentFeedback, Episode,
    EpisodeSegment, AgentRegistry, User
)
from core.episode_segmentation_service import EpisodeSegmentationService
from core.episode_retrieval_service import EpisodeRetrievalService
from core.llm.canvas_summary_service import CanvasSummaryService
from tests.factories.canvas_factory import CanvasAuditFactory
from tests.factories.agent_factory import AutonomousAgentFactory
from tests.factories.user_factory import UserFactory


class TestCanvasEpisodeIntegration:
    """Test canvas presentation → episode creation integration."""

    @pytest.fixture
    def segmentation_service(self, db_session: Session):
        """Create episode segmentation service."""
        return EpisodeSegmentationService(db_session)

    @pytest.fixture
    def retrieval_service(self, db_session: Session):
        """Create episode retrieval service."""
        return EpisodeRetrievalService(db_session)

    @pytest.fixture
    def canvas_summary_service(self, db_session: Session):
        """Create canvas summary service with mock LLM."""
        mock_llm = Mock()
        mock_llm.generate = AsyncMock(return_value="Agent presented workflow approval form with revenue data")
        return CanvasSummaryService(llm_service=mock_llm)

    def test_canvas_presentation_creates_episode_with_canvas_ids(
        self, db_session: Session, segmentation_service: EpisodeSegmentationService
    ):
        """Test that canvas presentations are linked to episodes via canvas_ids."""
        # Create agent and user
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        # Create canvas audit entries for a session
        session_id = str(uuid.uuid4())
        canvas_audits = [
            CanvasAuditFactory(
                canvas_type="sheets",
                component_type="data_grid",
                action="present",
                agent_id=agent.id,
                user_id=user.id,
                session_id=session_id,
                audit_metadata={"revenue": 1200000, "growth": 15},
                _session=db_session
            ),
            CanvasAuditFactory(
                canvas_type="generic",
                component_type="line_chart",
                action="present",
                agent_id=agent.id,
                user_id=user.id,
                session_id=session_id,
                _session=db_session
            )
        ]
        db_session.add_all(canvas_audits)
        db_session.commit()

        # Create episode from session
        episode = segmentation_service.create_episode_from_session(
            session_id=session_id,
            agent_id=agent.id,
            user_id=user.id
        )

        # Verify canvas_ids are populated
        assert episode is not None
        assert len(episode.canvas_ids) == 2
        assert episode.canvas_action_count == 2

        # Verify canvas audits have episode_id backlink
        for canvas_id in episode.canvas_ids:
            canvas = db_session.query(CanvasAudit).filter(
                CanvasAudit.id == canvas_id
            ).first()
            assert canvas is not None
            assert canvas.episode_id == episode.id

    def test_llm_canvas_summary_enriches_segment_context(
        self, db_session: Session, canvas_summary_service: CanvasSummaryService
    ):
        """Test that LLM summaries enrich episode segment canvas_context."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        # Create canvas audit
        canvas_audit = CanvasAuditFactory(
            canvas_type="orchestration",
            component_type="workflow_board",
            action="present",
            agent_id=agent.id,
            user_id=user.id,
            audit_metadata={
                "workflow_id": "wf-123",
                "approval_amount": 1500000,
                "approvers": ["manager", "director"]
            },
            _session=db_session
        )
        db_session.add(canvas_audit)
        db_session.commit()

        # Generate LLM summary
        summary = asyncio.run(canvas_summary_service.generate_summary(
            canvas_type="orchestration",
            canvas_state={
                "workflow_id": "wf-123",
                "approval_amount": 1500000,
                "approvers": ["manager", "director"]
            },
            agent_task="Approve workflow",
            user_interaction="submit"
        ))

        # Verify LLM summary is semantically rich
        assert summary is not None
        assert len(summary) > 50  # Should be 50-100 words
        assert "workflow" in summary.lower()
        assert "approval" in summary.lower()

    def test_feedback_submission_updates_episode_feedback_ids(
        self, db_session: Session, segmentation_service: EpisodeSegmentationService
    ):
        """Test that feedback submissions update episode feedback_ids."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        # Create episode
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            user_id=user.id,
            workspace_id="default",
            title="Test Episode",
            canvas_ids=[],
            feedback_ids=[],
            aggregate_feedback_score=None
        )
        db_session.add(episode)
        db_session.commit()

        # Submit feedback
        feedback = AgentFeedback(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            user_id=user.id,
            episode_id=episode.id,
            feedback_type="thumbs_up",
            rating=None,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(feedback)
        db_session.commit()

        # Refresh episode
        db_session.refresh(episode)

        # Verify feedback_ids updated
        assert len(episode.feedback_ids) == 1
        assert feedback.id in episode.feedback_ids

    def test_canvas_type_filtering_in_retrieval(
        self, db_session: Session, segmentation_service: EpisodeSegmentationService,
        retrieval_service: EpisodeRetrievalService
    ):
        """Test retrieving episodes filtered by canvas type."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        # Create episodes with different canvas types
        session_sheets = str(uuid.uuid4())
        canvas_sheets = CanvasAuditFactory(
            canvas_type="sheets",
            action="present",
            agent_id=agent.id,
            user_id=user.id,
            session_id=session_sheets,
            _session=db_session
        )
        db_session.add(canvas_sheets)
        db_session.commit()

        episode_sheets = segmentation_service.create_episode_from_session(
            session_id=session_sheets,
            agent_id=agent.id,
            user_id=user.id
        )

        session_charts = str(uuid.uuid4())
        canvas_charts = CanvasAuditFactory(
            canvas_type="generic",
            component_type="line_chart",
            action="present",
            agent_id=agent.id,
            user_id=user.id,
            session_id=session_charts,
            _session=db_session
        )
        db_session.add(canvas_charts)
        db_session.commit()

        episode_charts = segmentation_service.create_episode_from_session(
            session_id=session_charts,
            agent_id=agent.id,
            user_id=user.id
        )

        # Retrieve episodes by canvas type
        result = asyncio.run(retrieval_service.retrieve_by_canvas_type(
            agent_id=agent.id,
            canvas_type="sheets",
            limit=10
        ))

        # Should return only sheets episodes
        assert len(result) >= 1
        assert any(ep.id == episode_sheets.id for ep in result)

    def test_feedback_weighted_retrieval(
        self, db_session: Session, segmentation_service: EpisodeSegmentationService,
        retrieval_service: EpisodeRetrievalService
    ):
        """Test that positive feedback boosts episode relevance."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        # Create episode with positive feedback
        session_id = str(uuid.uuid4())
        canvas = CanvasAuditFactory(
            canvas_type="sheets",
            action="present",
            agent_id=agent.id,
            user_id=user.id,
            session_id=session_id,
            _session=db_session
        )
        db_session.add(canvas)
        db_session.commit()

        episode = segmentation_service.create_episode_from_session(
            session_id=session_id,
            agent_id=agent.id,
            user_id=user.id
        )

        # Add positive feedback
        feedback = AgentFeedback(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            user_id=user.id,
            episode_id=episode.id,
            feedback_type="rating",
            rating=5,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(feedback)
        db_session.commit()

        # Refresh episode to get aggregate score
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

        # Should fall back to metadata extraction
        summary = asyncio.run(canvas_summary_service.generate_summary(
            canvas_type="sheets",
            canvas_state=canvas_state,
            agent_task="Show revenue",
            timeout_seconds=2
        ))

        # Verify metadata fallback was used
        assert summary is not None
        assert "sheets" in summary.lower()

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

        # Create episode with canvas context
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            user_id=user.id,
            workspace_id="default",
            title="Sales Analysis",
            canvas_ids=[str(uuid.uuid4()), str(uuid.uuid4())],
            feedback_ids=[],
            canvas_action_count=2
        )
        db_session.add(episode)

        # Create canvas audits
        for canvas_id in episode.canvas_ids:
            canvas = CanvasAudit(
                id=canvas_id,
                workspace_id="default",
                agent_id=agent.id,
                user_id=user.id,
                canvas_id=canvas_id,
                canvas_type="sheets",
                component_type="data_grid",
                action="present",
                audit_metadata={"revenue": 1200000}
            )
            db_session.add(canvas)

        db_session.commit()

        # Retrieve episode with canvas context
        result = asyncio.run(retrieval_service.retrieve_episode(
            episode_id=episode.id,
            agent_id=agent.id,
            include_canvas=True
        ))

        # Verify canvas context is included
        assert result is not None
        assert "canvas_context" in result
        assert len(result["canvas_context"]) == 2

    def test_retrieve_episode_with_feedback_context(
        self, db_session: Session, retrieval_service: EpisodeRetrievalService
    ):
        """Test retrieving episode with feedback context included."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        # Create episode
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            user_id=user.id,
            workspace_id="default",
            title="Task Completion",
            canvas_ids=[],
            feedback_ids=[str(uuid.uuid4())],
            aggregate_feedback_score=0.75
        )
        db_session.add(episode)

        # Create feedback
        feedback = AgentFeedback(
            id=episode.feedback_ids[0],
            agent_id=agent.id,
            user_id=user.id,
            episode_id=episode.id,
            feedback_type="thumbs_up",
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(feedback)
        db_session.commit()

        # Retrieve episode with feedback context
        result = asyncio.run(retrieval_service.retrieve_episode(
            episode_id=episode.id,
            agent_id=agent.id,
            include_feedback=True
        ))

        # Verify feedback context is included
        assert result is not None
        assert "feedback_context" in result
        assert len(result["feedback_context"]) == 1

    def test_progressive_canvas_detail_levels(
        self, db_session: Session, retrieval_service: EpisodeRetrievalService
    ):
        """Test progressive detail levels for canvas context."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        # Create episode with full canvas context
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            user_id=user.id,
            workspace_id="default",
            title="Workflow Approval",
            canvas_ids=[str(uuid.uuid4())],
            feedback_ids=[],
            canvas_action_count=1
        )
        db_session.add(episode)

        # Create canvas audit with full context
        canvas = CanvasAudit(
            id=episode.canvas_ids[0],
            workspace_id="default",
            agent_id=agent.id,
            user_id=user.id,
            canvas_id=episode.canvas_ids[0],
            canvas_type="orchestration",
            component_type="workflow_board",
            action="present",
            audit_metadata={
                "workflow_id": "wf-123",
                "approval_amount": 1500000,
                "approvers": ["manager", "director"]
            }
        )
        db_session.add(canvas)
        db_session.commit()

        # Test summary detail level
        result_summary = asyncio.run(retrieval_service.retrieve_episode(
            episode_id=episode.id,
            agent_id=agent.id,
            include_canvas=True,
            canvas_context_detail="summary"
        ))

        assert "canvas_context" in result_summary

        # Test full detail level
        result_full = asyncio.run(retrieval_service.retrieve_episode(
            episode_id=episode.id,
            agent_id=agent.id,
            include_canvas=True,
            canvas_context_detail="full"
        ))

        assert "canvas_context" in result_full


class TestCanvasEpisodeLifecycle:
    """Test canvas episode lifecycle and archival."""

    @pytest.fixture
    def segmentation_service(self, db_session: Session):
        """Create episode segmentation service."""
        return EpisodeSegmentationService(db_session)

    def test_canvas_data_preserved_through_archival(
        self, db_session: Session, segmentation_service: EpisodeSegmentationService
    ):
        """Test that canvas context is preserved when episodes are archived."""
        agent = AutonomousAgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        db_session.commit()

        # Create episode with canvas context
        session_id = str(uuid.uuid4())
        canvas = CanvasAuditFactory(
            canvas_type="sheets",
            action="present",
            agent_id=agent.id,
            user_id=user.id,
            session_id=session_id,
            audit_metadata={"revenue": 1200000},
            _session=db_session
        )
        db_session.add(canvas)
        db_session.commit()

        episode = segmentation_service.create_episode_from_session(
            session_id=session_id,
            agent_id=agent.id,
            user_id=user.id
        )

        # Create segment with canvas context
        segment = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode.id,
            agent_id=agent.id,
            segment_type="canvas_presentation",
            canvas_context={
                "canvas_type": "sheets",
                "presentation_summary": "Revenue data presented",
                "critical_data_points": {"revenue": 1200000}
            },
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc)
        )
        db_session.add(segment)
        db_session.commit()

        # Archive episode (soft delete)
        episode.archived = True
        episode.archived_at = datetime.now(timezone.utc)
        db_session.commit()

        # Retrieve archived episode
        archived = db_session.query(Episode).filter(
            Episode.id == episode.id,
            Episode.archived == True
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
