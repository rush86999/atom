"""
Integration tests for LLM canvas summary generation in episodes.

Tests end-to-end episode creation with LLM-generated canvas context,
quality validation, and fallback behavior.

Ported to the current schema/API:
- CanvasAudit business fields (canvas_type, metadata) now live flat inside
  ``details_json``; the action column is ``action_type``.
- ``EpisodeSegmentationService(byok_handler=...)`` adapts the handler's
  ``generate_response`` to the ``generate`` interface CanvasSummaryService
  calls.
- On LLM failure the extraction is marked ``summary_source="metadata"`` and
  ``summary_verification="unverified"``.
- ``CanvasSummaryService`` takes ``llm_service=`` (no byok_handler kwarg).
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta


def _canvas_audit_mock(canvas_id, canvas_type, action, details):
    """Build a CanvasAudit mock matching the current flat details_json schema."""
    from core.models import CanvasAudit

    payload = {"canvas_type": canvas_type, **details}
    return Mock(
        spec=CanvasAudit,
        id=canvas_id,
        canvas_id=f"{canvas_id}-fk",
        action_type=action,
        details_json=payload,
    )


class TestLLMEpisodeIntegration:
    """Test LLM canvas summary integration with episode creation"""

    @pytest.fixture
    def db_session(self):
        """Mock database session"""
        from sqlalchemy.orm import Session
        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        return db

    @pytest.fixture
    def mock_byok_handler(self):
        """Mock BYOK handler for testing"""
        handler = Mock()
        handler.generate_response = AsyncMock(
            return_value=(
                "Agent presented Q4 revenue chart showing $1.2M in sales "
                "with 15% growth from Q3, highlighting December spike "
                "and requesting budget approval for Q1."
            )
        )
        return handler

    @pytest.fixture
    def segmentation_service(self, db_session, mock_byok_handler):
        """Create EpisodeSegmentationService with mocked dependencies"""
        from core.episode_segmentation_service import EpisodeSegmentationService

        # Mock lancedb handler
        with patch('core.episode_segmentation_service.get_lancedb_handler') as mock_lancedb:
            mock_lancedb.return_value = None
            service = EpisodeSegmentationService(db_session, byok_handler=mock_byok_handler)
            return service

    @pytest.mark.asyncio
    async def test_episode_creation_with_llm_summary(
        self, segmentation_service, mock_byok_handler, db_session
    ):
        """Test episode creation uses LLM-generated canvas summary"""
        mock_canvas = _canvas_audit_mock(
            "canvas-1",
            "sheets",
            "present",
            {
                "revenue": "1200000",
                "growth": "15",
                "components": [{"type": "line_chart"}]
            },
        )

        # Extract context with LLM
        result = await segmentation_service._extract_canvas_context_llm(
            canvas_audit=mock_canvas,
            agent_task="Review Q4 revenue"
        )

        # Verify LLM summary
        assert result["canvas_type"] == "sheets"
        assert result["summary_source"] == "llm"
        assert len(result["presentation_summary"]) > 20
        # Check that critical data was extracted
        assert "critical_data_points" in result
        assert result["critical_data_points"].get("revenue") == "1200000"

    @pytest.mark.asyncio
    async def test_llm_fallback_on_error(
        self, segmentation_service, db_session
    ):
        """Test episode creation falls back to metadata on LLM error"""
        import asyncio

        # Mock BYOK handler that fails
        failing_handler = Mock()
        failing_handler.generate_response = AsyncMock(
            side_effect=asyncio.TimeoutError("LLM timeout")
        )

        # Create service with failing BYOK
        with patch('core.episode_segmentation_service.get_lancedb_handler'):
            from core.episode_segmentation_service import EpisodeSegmentationService
            service = EpisodeSegmentationService(db_session, byok_handler=failing_handler)

        mock_canvas = _canvas_audit_mock(
            "canvas-2",
            "terminal",
            "present",
            {"command": "pytest", "exit_code": "0"},
        )

        # Should fallback to metadata-style summary
        result = await service._extract_canvas_context_llm(
            canvas_audit=mock_canvas
        )

        # The current implementation marks fallback summaries as
        # metadata-sourced and unverified
        assert result["summary_source"] == "metadata"
        assert result["summary_verification"] == "unverified"
        assert result["canvas_type"] == "terminal"
        # Verify it's a metadata-style summary (shorter, factual)
        assert len(result["presentation_summary"]) < 200  # Metadata summaries are shorter

    @pytest.mark.asyncio
    async def test_all_7_canvas_types_generate_summaries(
        self, segmentation_service, mock_byok_handler
    ):
        """Test that all 7 canvas types generate valid summaries"""
        canvas_types = [
            ("generic", {"content": "test"}),
            ("docs", {"word_count": 500, "title": "Spec"}),
            ("email", {"to": "user@example.com", "subject": "Test"}),
            ("sheets", {"revenue": "1000000"}),
            ("orchestration", {"workflow_id": "wf-123"}),
            ("terminal", {"command": "ls", "exit_code": "0"}),
            ("coding", {"language": "python", "line_count": 50})
        ]

        for canvas_type, metadata in canvas_types:
            mock_canvas = _canvas_audit_mock(
                f"canvas-{canvas_type}", canvas_type, "present", metadata
            )

            result = await segmentation_service._extract_canvas_context_llm(
                canvas_audit=mock_canvas
            )

            assert result["canvas_type"] == canvas_type
            assert "presentation_summary" in result
            assert len(result["presentation_summary"]) > 20
            assert result["summary_source"] == "llm"

    @pytest.mark.asyncio
    async def test_summary_quality_validation(
        self, segmentation_service, mock_byok_handler
    ):
        """Test LLM summaries meet quality thresholds"""
        mock_canvas = _canvas_audit_mock(
            "canvas-quality",
            "orchestration",
            "present",
            {
                "workflow_id": "wf-budget",
                "approval_amount": 100000,
                "approvers": ["manager", "director"]
            },
        )

        result = await segmentation_service._extract_canvas_context_llm(
            canvas_audit=mock_canvas,
            agent_task="Approve budget"
        )

        summary = result["presentation_summary"]

        # Quality checks:
        # 1. Business context (amount, workflow)
        assert any(term in summary.lower() for term in ["100000", "100", "wf-budget", "budget"])

        # 2. Conciseness (50-100 words, but allow flexibility)
        word_count = len(summary.split())
        assert 10 <= word_count <= 200  # Allow reasonable range

        # 3. No empty summary
        assert len(summary.strip()) > 0

    @pytest.mark.asyncio
    async def test_canvas_context_includes_critical_data(
        self, segmentation_service, mock_byok_handler
    ):
        """Test that critical data points are extracted"""
        mock_canvas = _canvas_audit_mock(
            "canvas-critical",
            "sheets",
            "submit",
            {
                "revenue": "5000000",
                "growth": "25",
                "components": [{"type": "bar_chart"}, {"type": "data_table"}]
            },
        )

        result = await segmentation_service._extract_canvas_context_llm(
            canvas_audit=mock_canvas
        )

        # Check critical data points
        assert "critical_data_points" in result
        critical_data = result["critical_data_points"]

        # Should include revenue and growth
        assert "revenue" in critical_data or "growth" in critical_data

        # Check visual elements
        assert "visual_elements" in result
        assert len(result["visual_elements"]) > 0

    @pytest.mark.asyncio
    async def test_user_interaction_mapping(
        self, segmentation_service, mock_byok_handler
    ):
        """Test user interaction is correctly mapped"""
        interactions = ["present", "submit", "close", "update", "execute"]

        for action in interactions:
            mock_canvas = _canvas_audit_mock(
                f"canvas-{action}", "generic", action, {}
            )

            result = await segmentation_service._extract_canvas_context_llm(
                canvas_audit=mock_canvas
            )

            # Should have user interaction mapped
            assert "user_interaction" in result
            assert len(result["user_interaction"]) > 0


class TestSemanticRichnessMetrics:
    """Test semantic richness quality metrics"""

    def test_semantic_richness_scoring(self):
        """Test semantic richness scoring algorithm"""
        from core.llm.canvas_summary_service import CanvasSummaryService

        service = CanvasSummaryService(llm_service=Mock())

        # Rich summary (business context + intent + decision)
        rich = (
            "Agent presented $1.2M workflow approval requiring board consent "
            "due to budget exceeding $1M threshold, with Q4 revenue chart "
            "showing 15% growth, highlighting 3 pending stakeholder responses "
            "and requesting immediate user decision."
        )

        # Poor summary (minimal information)
        poor = "Agent presented form with chart."

        rich_score = service._calculate_semantic_richness(rich)
        poor_score = service._calculate_semantic_richness(poor)

        assert rich_score > 0.5  # Rich summaries score high
        assert poor_score < rich_score  # Poor summaries score lower


class TestHallucinationDetection:
    """Test hallucination detection in LLM summaries"""

    def test_detect_hallucination_fabricated_facts(self):
        """Test hallucination detection catches fabricated facts"""
        from core.llm.canvas_summary_service import CanvasSummaryService

        service = CanvasSummaryService(llm_service=Mock())

        summary = "Agent presented workflow wf-999 with $1M approval."  # Wrong ID
        canvas_state = {"workflow_id": "wf-123", "approval_amount": "50000"}

        assert service._detect_hallucination(summary, canvas_state) is True

    def test_no_hallucination_accurate_summary(self):
        """Test no hallucination when summary matches state"""
        from core.llm.canvas_summary_service import CanvasSummaryService

        service = CanvasSummaryService(llm_service=Mock())

        summary = "Agent presented workflow wf-123 with $50K approval."
        canvas_state = {"workflow_id": "wf-123", "approval_amount": "50000"}

        assert service._detect_hallucination(summary, canvas_state) is False


class TestConsistencyValidation:
    """Test summary consistency across multiple runs"""

    @pytest.mark.asyncio
    async def test_consistency_same_state_same_summary(self):
        """Test same canvas state generates consistent summary"""
        from core.llm.canvas_summary_service import CanvasSummaryService

        mock_llm = Mock()
        mock_llm.generate = AsyncMock(
            return_value="Agent presented workflow wf-123 with $50K approval."
        )

        service = CanvasSummaryService(llm_service=mock_llm)

        canvas_state = {"workflow_id": "wf-123", "approval_amount": "50000"}

        # Generate summary 5 times
        summaries = []
        for _ in range(5):
            result = await service.generate_summary(
                canvas_type="orchestration",
                canvas_state=canvas_state
            )
            summaries.append(result)

        # All should be identical (temperature=0, cached)
        assert len(set(summaries)) == 1
