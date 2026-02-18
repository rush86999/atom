"""
Integration tests for LLM canvas summary generation in episodes.

Tests the integration between CanvasSummaryService and
EpisodeSegmentationService for LLM-generated canvas context.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime


class TestCanvasSummaryLLMIntegration:
    """Test LLM canvas summary integration with episode creation"""

    @pytest.fixture
    def db_session(self):
        """Mock database session"""
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.add = Mock()
        db.commit = Mock()
        return db

    @pytest.fixture
    def mock_byok_handler(self):
        """Mock BYOK handler for LLM generation"""
        handler = Mock()
        handler.generate_response = AsyncMock(return_value=(
            "Agent presented Q4 revenue chart showing $1.2M in sales, "
            "15% growth from Q3, highlighting December spike and "
            "requesting approval for Q1 budget."
        ))
        return handler

    def test_canvas_summary_service_initialization(self, db_session, mock_byok_handler):
        """Test CanvasSummaryService is initialized in EpisodeSegmentationService"""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.llm.byok_handler import BYOKHandler

        # Create service with BYOK handler
        service = EpisodeSegmentationService(db_session, byok_handler=mock_byok_handler)

        assert hasattr(service, 'canvas_summary_service')
        assert hasattr(service, 'byok_handler')

    @pytest.mark.asyncio
    async def test_llm_canvas_context_extraction(self, db_session, mock_byok_handler):
        """Test LLM-generated canvas context extraction"""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import CanvasAudit

        service = EpisodeSegmentationService(db_session, byok_handler=mock_byok_handler)

        # Create mock canvas audit
        canvas_audit = CanvasAudit(
            id="test-canvas-1",
            canvas_type="sheets",
            action="present",
            audit_metadata={
                "revenue": "1200000",
                "growth": "15%",
                "components": [{"type": "line_chart"}]
            }
        )

        # Extract context with LLM
        result = await service._extract_canvas_context_llm(
            canvas_audit=canvas_audit,
            agent_task="Review Q4 revenue"
        )

        # Verify result structure
        assert result["canvas_type"] == "sheets"
        assert "presentation_summary" in result
        assert result["summary_source"] == "llm"
        assert "visual_elements" in result
        assert "critical_data_points" in result

    @pytest.mark.asyncio
    async def test_llm_fallback_to_metadata_on_timeout(self, db_session):
        """Test fallback to metadata when LLM times out"""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import CanvasAudit
        import asyncio

        # Mock BYOK handler that times out
        mock_byok_handler = Mock()
        mock_byok_handler.generate_response = AsyncMock(
            side_effect=asyncio.TimeoutError("LLM timeout")
        )

        service = EpisodeSegmentationService(db_session, byok_handler=mock_byok_handler)

        canvas_audit = CanvasAudit(
            id="test-canvas-2",
            canvas_type="terminal",
            action="present",
            audit_metadata={"command": "pytest tests/", "exit_code": "0"}
        )

        # Should fallback to metadata
        result = await service._extract_canvas_context_llm(canvas_audit=canvas_audit)

        assert result["summary_source"] == "metadata"
        assert "terminal" in result["canvas_type"]

    def test_all_7_canvas_types_have_prompts(self, db_session, mock_byok_handler):
        """Test that all 7 canvas types have specialized prompts"""
        from core.episode_segmentation_service import EpisodeSegmentationService

        service = EpisodeSegmentationService(db_session, byok_handler=mock_byok_handler)

        canvas_types = ["generic", "docs", "email", "sheets", "orchestration", "terminal", "coding"]

        for canvas_type in canvas_types:
            # Verify prompt exists in CanvasSummaryService
            prompts = service.canvas_summary_service._CANVAS_PROMPTS
            assert canvas_type in prompts, f"Missing prompt for {canvas_type}"

    @pytest.mark.asyncio
    async def test_canvas_context_includes_critical_data(self, db_session, mock_byok_handler):
        """Test that critical data points are extracted from canvas state"""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import CanvasAudit

        service = EpisodeSegmentationService(db_session, byok_handler=mock_byok_handler)

        canvas_audit = CanvasAudit(
            id="test-canvas-3",
            canvas_type="orchestration",
            action="present",
            audit_metadata={
                "workflow_id": "wf-123",
                "approval_amount": 50000,
                "approvers": ["manager", "director"]
            }
        )

        result = await service._extract_canvas_context_llm(canvas_audit=canvas_audit)

        # Verify critical data extracted
        critical_data = result["critical_data_points"]
        assert "workflow_id" in critical_data or "approval_amount" in critical_data

    @pytest.mark.asyncio
    async def test_llm_summary_caching(self, db_session, mock_byok_handler):
        """Test that LLM summaries are cached to avoid redundant generation"""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import CanvasAudit

        # Track how many times generate_response is called
        call_count = [0]
        async def counting_response(*args, **kwargs):
            call_count[0] += 1
            return "Cached summary"

        mock_byok_handler.generate_response = AsyncMock(side_effect=counting_response)

        service = EpisodeSegmentationService(db_session, byok_handler=mock_byok_handler)

        canvas_audit = CanvasAudit(
            id="test-canvas-4",
            canvas_type="sheets",
            action="present",
            audit_metadata={"revenue": "1000000"}
        )

        # Call twice with same canvas
        await service._extract_canvas_context_llm(canvas_audit=canvas_audit)
        await service._extract_canvas_context_llm(canvas_audit=canvas_audit)

        # Should cache and only call LLM once
        assert call_count[0] == 1, f"Expected 1 LLM call, got {call_count[0]}"

    @pytest.mark.asyncio
    async def test_metadata_fallback_on_exception(self, db_session):
        """Test fallback to metadata when LLM raises exception"""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import CanvasAudit

        # Mock BYOK handler that raises exception
        mock_byok_handler = Mock()
        mock_byok_handler.generate_response = AsyncMock(
            side_effect=Exception("LLM API error")
        )

        service = EpisodeSegmentationService(db_session, byok_handler=mock_byok_handler)

        canvas_audit = CanvasAudit(
            id="test-canvas-5",
            canvas_type="docs",
            action="present",
            audit_metadata={"title": "Test Doc", "word_count": 500}
        )

        result = await service._extract_canvas_context_llm(canvas_audit=canvas_audit)

        # Should fallback to metadata
        assert result["summary_source"] == "metadata"
        assert result["canvas_type"] == "docs"

    @pytest.mark.asyncio
    async def test_user_interaction_extraction(self, db_session, mock_byok_handler):
        """Test that user interaction is properly mapped"""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import CanvasAudit

        service = EpisodeSegmentationService(db_session, byok_handler=mock_byok_handler)

        # Test different interaction types
        interactions = ["present", "submit", "close", "update", "execute"]

        for action in interactions:
            canvas_audit = CanvasAudit(
                id=f"test-canvas-{action}",
                canvas_type="generic",
                action=action,
                audit_metadata={}
            )

            result = await service._extract_canvas_context_llm(canvas_audit=canvas_audit)

            # Verify interaction was extracted
            assert "user_interaction" in result
            assert result["user_interaction"]

    @pytest.mark.asyncio
    async def test_visual_elements_extraction(self, db_session, mock_byok_handler):
        """Test that visual elements are extracted from components"""
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.models import CanvasAudit

        service = EpisodeSegmentationService(db_session, byok_handler=mock_byok_handler)

        canvas_audit = CanvasAudit(
            id="test-canvas-visual",
            canvas_type="sheets",
            action="present",
            audit_metadata={
                "components": [
                    {"type": "line_chart"},
                    {"type": "bar_chart"},
                    {"type": "data_table"}
                ]
            }
        )

        result = await service._extract_canvas_context_llm(canvas_audit=canvas_audit)

        # Verify visual elements extracted (limited to 5)
        assert "visual_elements" in result
        assert len(result["visual_elements"]) <= 5
        assert "line_chart" in result["visual_elements"]
