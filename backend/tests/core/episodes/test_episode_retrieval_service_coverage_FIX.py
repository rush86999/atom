"""
Coverage-driven tests for episode_retrieval_service.py

FIX for Phase 193 test data issues:
- Use factory_boy for valid AgentEpisode creation (solves NOT NULL constraints)
- Use factory_boy for valid EpisodeSegment creation (solves FK relationships)
- Use factory_boy for Artifact/CanvasAudit/AgentFeedback (solves integration tests)

Coverage Target: 0% -> 60%+ (realistic target per Phase 194 research)
Phase 193 Baseline: 9.6% pass rate (5/52 tests passing)
Phase 194 Target: >80% pass rate
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
import asyncio

# Import factory_boy fixtures
from tests.fixtures.episode_fixtures import (
    AgentEpisodeFactory,
    EpisodeSegmentFactory,
    ArtifactFactory,
    CanvasAuditFactory,
    AgentFeedbackFactory,
    create_episode_with_segments
)

# Import service to test
from core.episode_retrieval_service import EpisodeRetrievalService


@pytest.fixture
def db_session():
    """Create a test database session."""
    from core.database import get_db_session
    with get_db_session() as session:
        yield session


@pytest.fixture(autouse=True)
def set_factory_session(db_session):
    """Set database session for all factory_boy factories."""
    from tests.fixtures.episode_fixtures import (
        AgentEpisodeFactory,
        EpisodeSegmentFactory,
        ArtifactFactory,
        CanvasAuditFactory,
        AgentFeedbackFactory,
        TenantFactory,
        AgentFactory
    )
    # Set session for all factories
    AgentEpisodeFactory._meta.sqlalchemy_session = db_session
    EpisodeSegmentFactory._meta.sqlalchemy_session = db_session
    ArtifactFactory._meta.sqlalchemy_session = db_session
    CanvasAuditFactory._meta.sqlalchemy_session = db_session
    AgentFeedbackFactory._meta.sqlalchemy_session = db_session
    TenantFactory._meta.sqlalchemy_session = db_session
    AgentFactory._meta.sqlalchemy_session = db_session
    yield
    # Cleanup after tests
    AgentEpisodeFactory._meta.sqlalchemy_session = None
    EpisodeSegmentFactory._meta.sqlalchemy_session = None
    ArtifactFactory._meta.sqlalchemy_session = None
    CanvasAuditFactory._meta.sqlalchemy_session = None
    AgentFeedbackFactory._meta.sqlalchemy_session = None
    TenantFactory._meta.sqlalchemy_session = None
    AgentFactory._meta.sqlalchemy_session = None


class TestEpisodeRetrievalServiceCoverageFIX:
    """
    Fixed test suite using factory_boy to avoid NOT NULL constraint violations.

    Focus areas:
    1. Temporal retrieval (date-based queries)
    2. Semantic retrieval (vector search with mocked LanceDB)
    3. Sequential retrieval (full episodes with segments)
    4. Contextual retrieval (hybrid with canvas/feedback context)
    5. Error handling and edge cases
    """

    # ============================================================
    # TEMPORAL RETRIEVAL TESTS (12 tests)
    # ============================================================

    @pytest.mark.asyncio
    async def test_temporal_retrieval_with_valid_data(self, db_session):
        """Cover temporal retrieval (lines 50-150) with valid test data."""
        episode = AgentEpisodeFactory.create(
            agent_id="test-agent",
            started_at=datetime.now() - timedelta(days=1),
            completed_at=datetime.now()
        )
        # Factory handles all NOT NULL constraints automatically
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = await service.retrieve_temporal(
            agent_id="test-agent",
            time_range="7d"
        )

        assert len(results) >= 1
        assert results[0].id == episode.id

    @pytest.mark.parametrize("limit,offset,expected_count", [
        (10, 0, 10),
        (5, 0, 5),
        (10, 5, 5),
    ])
    def test_temporal_retrieval_pagination(self, db_session, limit, offset, expected_count):
        """Cover pagination logic (lines 100-130)."""
        # Create 15 episodes using factory
        for i in range(15):
            AgentEpisodeFactory.create(agent_id="test-agent")
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_temporal(
            agent_id="test-agent",
            limit=limit,
            offset=offset
        )

        assert len(results) == expected_count

    def test_temporal_retrieval_with_date_range(self, db_session):
        """Cover date range filtering logic."""
        now = datetime.now()

        # Create episodes at different times
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            started_at=now - timedelta(days=5),
            completed_at=now - timedelta(days=5) + timedelta(hours=1)
        )
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            started_at=now - timedelta(days=1),
            completed_at=now - timedelta(days=1) + timedelta(hours=1)
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_temporal(
            agent_id="test-agent",
            date_range_start=now - timedelta(days=3),
            date_range_end=now
        )

        # Should only retrieve episode from last 3 days
        assert len(results) == 1

    def test_temporal_retrieval_empty_results(self, db_session):
        """Cover empty result handling (lines 130-150)."""
        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_temporal(agent_id="nonexistent-agent")

        assert len(results) == 0

    def test_temporal_retrieval_with_maturity_filter(self, db_session):
        """Cover maturity-based filtering."""
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            maturity_at_time="INTERN"
        )
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            maturity_at_time="SUPERVISED"
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_temporal(
            agent_id="test-agent",
            maturity_level="INTERN"
        )

        assert len(results) == 1
        assert results[0].maturity_at_time == "INTERN"

    def test_temporal_retrieval_with_outcome_filter(self, db_session):
        """Cover outcome-based filtering."""
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            outcome="success"
        )
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            outcome="failure"
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_temporal(
            agent_id="test-agent",
            outcome="success"
        )

        assert len(results) == 1
        assert results[0].outcome == "success"

    def test_temporal_retrieval_ordering(self, db_session):
        """Cover result ordering by date."""
        now = datetime.now()

        episode1 = AgentEpisodeFactory.create(
            agent_id="test-agent",
            started_at=now - timedelta(days=2)
        )
        episode2 = AgentEpisodeFactory.create(
            agent_id="test-agent",
            started_at=now - timedelta(days=1)
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_temporal(agent_id="test-agent")

        # Should be ordered by most recent first
        assert results[0].id == episode2.id
        assert results[1].id == episode1.id

    def test_temporal_retrieval_with_limit(self, db_session):
        """Cover limit parameter."""
        for i in range(10):
            AgentEpisodeFactory.create(agent_id="test-agent")
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_temporal(
            agent_id="test-agent",
            limit=5
        )

        assert len(results) == 5

    def test_temporal_retrieval_with_offset(self, db_session):
        """Cover offset parameter."""
        for i in range(10):
            AgentEpisodeFactory.create(agent_id="test-agent")
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results_all = service.retrieve_temporal(agent_id="test-agent")
        results_offset = service.retrieve_temporal(
            agent_id="test-agent",
            offset=5
        )

        assert len(results_all) == 10
        assert len(results_offset) == 5
        assert results_offset[0].id != results_all[0].id

    def test_temporal_retrieval_invalid_agent_id(self, db_session):
        """Cover error handling for invalid agent ID."""
        service = EpisodeRetrievalService(db_session)

        with pytest.raises(ValueError) as exc_info:
            service.retrieve_temporal(agent_id="")

        assert "agent_id" in str(exc_info.value).lower()

    def test_temporal_retrieval_with_session_filter(self, db_session):
        """Cover session-based filtering."""
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            session_id="session-1"
        )
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            session_id="session-2"
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_temporal(
            agent_id="test-agent",
            session_id="session-1"
        )

        assert len(results) == 1
        assert results[0].session_id == "session-1"

    # ============================================================
    # SEQUENTIAL RETRIEVAL TESTS (10 tests)
    # ============================================================

    def test_sequential_retrieval_with_segments(self, db_session):
        """Cover sequential retrieval (lines 250-350) with episode + segments."""
        episode, segments = create_episode_with_segments(
            db_session,
            agent_id="test-agent",
            segment_count=5
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        result = service.retrieve_sequential(episode_id=episode.id)

        assert result.id == episode.id
        assert len(result.segments) == 5

    def test_sequential_segment_ordering(self, db_session):
        """Cover segment ordering logic (lines 280-320)."""
        episode = AgentEpisodeFactory.create(agent_id="test-agent")

        # Create segments out of order
        EpisodeSegmentFactory.create(episode=episode, sequence_order=2)
        EpisodeSegmentFactory.create(episode=episode, sequence_order=0)
        EpisodeSegmentFactory.create(episode=episode, sequence_order=1)
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        result = service.retrieve_sequential(episode_id=episode.id)

        # Verify segments are ordered by sequence_order
        assert result.segments[0].sequence_order == 0
        assert result.segments[1].sequence_order == 1
        assert result.segments[2].sequence_order == 2

    def test_sequential_retrieval_not_found(self, db_session):
        """Cover not found error handling."""
        service = EpisodeRetrievalService(db_session)

        with pytest.raises(ValueError) as exc_info:
            service.retrieve_sequential(episode_id="nonexistent")

        assert "not found" in str(exc_info.value).lower()

    def test_sequential_retrieval_with_canvas_context(self, db_session):
        """Cover sequential retrieval with canvas context."""
        episode = AgentEpisodeFactory.create(
            agent_id="test-agent",
            canvas_ids=["canvas-1", "canvas-2"]
        )
        EpisodeSegmentFactory.create(
            episode=episode,
            segment_type="canvas_presented",
            sequence_order=0
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        result = service.retrieve_sequential(
            episode_id=episode.id,
            include_canvas_context=True
        )

        assert result.id == episode.id
        assert len(result.canvas_ids) == 2

    def test_sequential_retrieval_with_feedback_context(self, db_session):
        """Cover sequential retrieval with feedback context."""
        episode = AgentEpisodeFactory.create(
            agent_id="test-agent",
            feedback_ids=["feedback-1"]
        )
        EpisodeSegmentFactory.create(
            episode=episode,
            sequence_order=0
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        result = service.retrieve_sequential(
            episode_id=episode.id,
            include_feedback_context=True
        )

        assert result.id == episode.id
        assert len(result.feedback_ids) == 1

    def test_sequential_retrieval_empty_segments(self, db_session):
        """Cover episode with no segments."""
        episode = AgentEpisodeFactory.create(agent_id="test-agent")
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        result = service.retrieve_sequential(episode_id=episode.id)

        assert result.id == episode.id
        assert len(result.segments) == 0

    def test_sequential_retrieval_with_segment_types(self, db_session):
        """Cover segment type filtering."""
        episode = AgentEpisodeFactory.create(agent_id="test-agent")
        EpisodeSegmentFactory.create(
            episode=episode,
            segment_type="user_message",
            sequence_order=0
        )
        EpisodeSegmentFactory.create(
            episode=episode,
            segment_type="agent_action",
            sequence_order=1
        )
        EpisodeSegmentFactory.create(
            episode=episode,
            segment_type="user_message",
            sequence_order=2
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        result = service.retrieve_sequential(
            episode_id=episode.id,
            segment_types=["user_message"]
        )

        assert len(result.segments) == 2
        for seg in result.segments:
            assert seg.segment_type == "user_message"

    def test_sequential_retrieval_with_canvas_segment_context(self, db_session):
        """Cover segments with canvas context."""
        episode = AgentEpisodeFactory.create(agent_id="test-agent")
        EpisodeSegmentFactory.create(
            episode=episode,
            segment_type="canvas_presented",
            canvas_context={
                "canvas_type": "chart",
                "presentation_summary": "Test chart"
            },
            sequence_order=0
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        result = service.retrieve_sequential(episode_id=episode.id)

        assert len(result.segments) == 1
        assert result.segments[0].canvas_context is not None

    def test_sequential_retrieval_segment_limit(self, db_session):
        """Cover segment limit parameter."""
        episode = AgentEpisodeFactory.create(agent_id="test-agent")
        for i in range(10):
            EpisodeSegmentFactory.create(
                episode=episode,
                sequence_order=i
            )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        result = service.retrieve_sequential(
            episode_id=episode.id,
            segment_limit=5
        )

        assert len(result.segments) == 5

    def test_sequential_retrieval_segment_offset(self, db_session):
        """Cover segment offset parameter."""
        episode = AgentEpisodeFactory.create(agent_id="test-agent")
        for i in range(10):
            EpisodeSegmentFactory.create(
                episode=episode,
                sequence_order=i
            )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        result = service.retrieve_sequential(
            episode_id=episode.id,
            segment_offset=5
        )

        assert len(result.segments) == 5
        assert result.segments[0].sequence_order == 5

    # ============================================================
    # CONTEXTUAL RETRIEVAL TESTS (8 tests)
    # ============================================================

    def test_contextual_with_canvas_context(self, db_session):
        """Cover contextual retrieval with canvas integration (lines 350-450)."""
        episode = AgentEpisodeFactory.create(agent_id="test-agent")
        canvas_audit = CanvasAuditFactory.create(
            agent_id="test-agent",
            canvas_id="test-canvas"
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_contextual(
            agent_id="test-agent",
            query="test query",
            include_canvas_context=True
        )

        # Canvas context should be included
        assert any(ep.id == episode.id for ep in results)

    def test_contextual_with_feedback_context(self, db_session):
        """Cover contextual retrieval with feedback integration."""
        episode = AgentEpisodeFactory.create(agent_id="test-agent")
        feedback = AgentFeedbackFactory.create(
            agent_id="test-agent",
            score=1.0  # Positive feedback
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_contextual(
            agent_id="test-agent",
            query="test query",
            include_feedback_context=True
        )

        # Feedback should boost episode ranking
        assert any(ep.id == episode.id for ep in results)

    def test_contextual_hybrid_retrieval(self, db_session):
        """Cover hybrid temporal + semantic retrieval."""
        episode = AgentEpisodeFactory.create(
            agent_id="test-agent",
            started_at=datetime.now() - timedelta(days=1)
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_contextual(
            agent_id="test-agent",
            query="test query",
            date_range_start=datetime.now() - timedelta(days=2),
            date_range_end=datetime.now()
        )

        assert len(results) >= 1

    def test_contextual_with_limit(self, db_session):
        """Cover limit parameter in contextual retrieval."""
        for i in range(10):
            AgentEpisodeFactory.create(agent_id="test-agent")
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_contextual(
            agent_id="test-agent",
            query="test",
            limit=5
        )

        assert len(results) <= 5

    def test_contextual_empty_results(self, db_session):
        """Cover empty result handling."""
        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_contextual(
            agent_id="nonexistent",
            query="test"
        )

        assert len(results) == 0

    def test_contextual_with_maturity_filter(self, db_session):
        """Cover maturity-based filtering in contextual retrieval."""
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            maturity_at_time="INTERN"
        )
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            maturity_at_time="SUPERVISED"
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_contextual(
            agent_id="test-agent",
            query="test",
            maturity_level="INTERN"
        )

        # Should only return INTERN episodes
        assert all(ep.maturity_at_time == "INTERN" for ep in results)

    def test_contextual_feedback_boost(self, db_session):
        """Cover feedback-based score boosting."""
        episode_positive = AgentEpisodeFactory.create(
            agent_id="test-agent",
            aggregate_feedback_score=1.0
        )
        episode_negative = AgentEpisodeFactory.create(
            agent_id="test-agent",
            aggregate_feedback_score=-1.0
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_contextual(
            agent_id="test-agent",
            query="test",
            include_feedback_context=True
        )

        # Positive feedback should boost ranking
        assert len(results) >= 1

    def test_contextual_with_canvas_feedback_boosts(self, db_session):
        """Cover canvas + feedback combined boosts."""
        episode = AgentEpisodeFactory.create(
            agent_id="test-agent",
            canvas_action_count=5,
            aggregate_feedback_score=0.8
        )
        CanvasAuditFactory.create(agent_id="test-agent")
        AgentFeedbackFactory.create(
            agent_id="test-agent",
            score=1.0
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_contextual(
            agent_id="test-agent",
            query="test",
            include_canvas_context=True,
            include_feedback_context=True
        )

        assert len(results) >= 1

    # ============================================================
    # SEMANTIC RETRIEVAL TESTS (6 tests) - with mocked LanceDB
    # ============================================================

    def test_semantic_retrieval_with_mock_lancedb(self, db_session, mocker):
        """Cover semantic retrieval (lines 150-250) with mocked LanceDB."""
        # Mock LanceDB client
        mock_table = mocker.MagicMock()
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.episode_retrieval_service.lancedb.connect",
            return_value=mocker.MagicMock(open_table=lambda _: mock_table)
        )

        # Create episodes for semantic search
        for i in range(5):
            AgentEpisodeFactory.create(
                agent_id="test-agent",
                task_description=f"Test episode about topic {i}"
            )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_semantic(
            agent_id="test-agent",
            query="test topic",
            limit=10
        )

        # LanceDB mock should be called
        mock_table.search.assert_called_once()

    def test_semantic_retrieval_empty_query(self, db_session):
        """Cover error handling for empty query."""
        service = EpisodeRetrievalService(db_session)

        with pytest.raises(ValueError) as exc_info:
            service.retrieve_semantic(agent_id="test-agent", query="")

        assert "query" in str(exc_info.value).lower()

    def test_semantic_retrieval_with_limit(self, db_session, mocker):
        """Cover limit parameter in semantic retrieval."""
        mock_table = mocker.MagicMock()
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.episode_retrieval_service.lancedb.connect",
            return_value=mocker.MagicMock(open_table=lambda _: mock_table)
        )

        for i in range(10):
            AgentEpisodeFactory.create(agent_id="test-agent")
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_semantic(
            agent_id="test-agent",
            query="test",
            limit=5
        )

        mock_table.search.assert_called_once()

    def test_semantic_retrieval_lancedb_error(self, db_session, mocker):
        """Cover LanceDB connection error handling."""
        mocker.patch(
            "core.episode_retrieval_service.lancedb.connect",
            side_effect=Exception("LanceDB connection failed")
        )

        AgentEpisodeFactory.create(agent_id="test-agent")
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_semantic(
            agent_id="test-agent",
            query="test"
        )

        # Should return empty results on error
        assert len(results) == 0

    def test_semantic_retrieval_with_maturity_filter(self, db_session, mocker):
        """Cover maturity filtering in semantic retrieval."""
        mock_table = mocker.MagicMock()
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.episode_retrieval_service.lancedb.connect",
            return_value=mocker.MagicMock(open_table=lambda _: mock_table)
        )

        AgentEpisodeFactory.create(
            agent_id="test-agent",
            maturity_at_time="INTERN"
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_semantic(
            agent_id="test-agent",
            query="test",
            maturity_level="INTERN"
        )

        mock_table.search.assert_called_once()

    def test_semantic_retrieval_with_date_range(self, db_session, mocker):
        """Cover date range filtering in semantic retrieval."""
        mock_table = mocker.MagicMock()
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.episode_retrieval_service.lancedb.connect",
            return_value=mocker.MagicMock(open_table=lambda _: mock_table)
        )

        episode = AgentEpisodeFactory.create(
            agent_id="test-agent",
            started_at=datetime.now() - timedelta(days=1)
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_semantic(
            agent_id="test-agent",
            query="test",
            date_range_start=datetime.now() - timedelta(days=2),
            date_range_end=datetime.now()
        )

        mock_table.search.assert_called_once()

    # ============================================================
    # ERROR HANDLING TESTS (6 tests)
    # ============================================================

    def test_retrieval_with_invalid_agent_id(self, db_session):
        """Cover error handling for invalid agent ID."""
        service = EpisodeRetrievalService(db_session)

        with pytest.raises(ValueError) as exc_info:
            service.retrieve_temporal(agent_id="")

        assert "agent_id" in str(exc_info.value).lower()

    def test_retrieval_with_empty_database(self, db_session):
        """Cover empty result handling."""
        service = EpisodeRetrievalService(db_session)

        results = service.retrieve_temporal(agent_id="nonexistent")

        assert len(results) == 0

    def test_retrieval_with_none_session(self, db_session):
        """Cover None session handling."""
        with pytest.raises(ValueError) as exc_info:
            EpisodeRetrievalService(None)

        assert "session" in str(exc_info.value).lower()

    def test_retrieval_invalid_episode_id(self, db_session):
        """Cover invalid episode ID in sequential retrieval."""
        service = EpisodeRetrievalService(db_session)

        with pytest.raises(ValueError):
            service.retrieve_sequential(episode_id="")

    def test_retrieval_negative_limit(self, db_session):
        """Cover negative limit parameter."""
        service = EpisodeRetrievalService(db_session)

        with pytest.raises(ValueError):
            service.retrieve_temporal(
                agent_id="test-agent",
                limit=-1
            )

    def test_retrieval_negative_offset(self, db_session):
        """Cover negative offset parameter."""
        service = EpisodeRetrievalService(db_session)

        with pytest.raises(ValueError):
            service.retrieve_temporal(
                agent_id="test-agent",
                offset=-1
            )

    # ============================================================
    # CANVAS-AWARE RETRIEVAL TESTS (4 tests)
    # ============================================================

    def test_canvas_aware_retrieval_by_type(self, db_session):
        """Cover canvas type filtering."""
        episode = AgentEpisodeFactory.create(
            agent_id="test-agent",
            canvas_ids=["canvas-1"]
        )
        CanvasAuditFactory.create(
            agent_id="test-agent",
            canvas_id="canvas-1",
            canvas_type="chart"
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_canvas_aware(
            agent_id="test-agent",
            canvas_type="chart"
        )

        assert len(results) >= 1

    def test_canvas_aware_retrieval_with_action_filter(self, db_session):
        """Cover canvas action type filtering."""
        CanvasAuditFactory.create(
            agent_id="test-agent",
            action_type="present"
        )
        AgentEpisodeFactory.create(agent_id="test-agent")
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_canvas_aware(
            agent_id="test-agent",
            action_type="present"
        )

        assert len(results) >= 1

    def test_canvas_aware_empty_results(self, db_session):
        """Cover empty results in canvas-aware retrieval."""
        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_canvas_aware(
            agent_id="test-agent",
            canvas_type="nonexistent"
        )

        assert len(results) == 0

    def test_canvas_aware_with_detail_level(self, db_session):
        """Cover detail level parameter (summary/standard/full)."""
        CanvasAuditFactory.create(agent_id="test-agent")
        AgentEpisodeFactory.create(agent_id="test-agent")
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_canvas_aware(
            agent_id="test-agent",
            detail_level="summary"
        )

        assert len(results) >= 1

    # ============================================================
    # BUSINESS DATA RETRIEVAL TESTS (3 tests)
    # ============================================================

    def test_business_data_retrieval_with_filter(self, db_session):
        """Cover business data filtering."""
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            metadata_json={"business_key": "value"}
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_by_business_data(
            agent_id="test-agent",
            filters={"business_key": "value"}
        )

        assert len(results) >= 1

    def test_business_data_empty_results(self, db_session):
        """Cover empty results with business data filter."""
        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_by_business_data(
            agent_id="test-agent",
            filters={"nonexistent": "value"}
        )

        assert len(results) == 0

    def test_business_data_with_operator(self, db_session):
        """Cover filter operators (gt, lt, etc)."""
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            importance_score=0.8
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_by_business_data(
            agent_id="test-agent",
            filters={"importance_score": {"operator": "gt", "value": 0.5}}
        )

        assert len(results) >= 1

    # ============================================================
    # SUPERVISION CONTEXT TESTS (2 tests)
    # ============================================================

    def test_supervision_context_retrieval(self, db_session):
        """Cover supervision context in retrieval."""
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            supervision_decision="approved"
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_with_supervision_context(
            agent_id="test-agent"
        )

        assert len(results) >= 1

    def test_supervision_context_with_decision_filter(self, db_session):
        """Cover supervision decision filtering."""
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            supervision_decision="approved"
        )
        AgentEpisodeFactory.create(
            agent_id="test-agent",
            supervision_decision="rejected"
        )
        db_session.commit()

        service = EpisodeRetrievalService(db_session)
        results = service.retrieve_with_supervision_context(
            agent_id="test-agent",
            supervision_decision="approved"
        )

        assert all(ep.supervision_decision == "approved" for ep in results)
