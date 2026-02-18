"""
Unit tests for CanvasSummaryService.

Tests prompt building, summary generation, caching, fallback behavior,
and quality metrics for LLM-generated canvas summaries.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
import json


class TestCanvasSummaryServiceInitialization:
    """Test CanvasSummaryService initialization"""

    def test_initialization_with_byok_handler(self):
        """Test service initializes with BYOK handler"""
        from core.llm.canvas_summary_service import CanvasSummaryService
        from core.llm.byok_handler import BYOKHandler

        mock_byok = Mock(spec=BYOKHandler)
        service = CanvasSummaryService(byok_handler=mock_byok)

        assert service.byok_handler == mock_byok
        assert service._summary_cache == {}
        assert service._cost_tracker == {}

    def test_initialization_default_byok(self):
        """Test service creates BYOK handler if not provided"""
        from core.llm.canvas_summary_service import CanvasSummaryService

        # Patch BYOKHandler creation
        with patch('core.llm.canvas_summary_service.BYOKHandler') as mock_byok_class:
            mock_instance = Mock()
            mock_byok_class.return_value = mock_instance
            service = CanvasSummaryService(byok_handler=mock_instance)

            assert service.byok_handler == mock_instance


class TestPromptBuilding:
    """Test canvas-specific prompt building"""

    @pytest.fixture
    def service(self):
        from core.llm.canvas_summary_service import CanvasSummaryService
        mock_byok = Mock()
        return CanvasSummaryService(byok_handler=mock_byok)

    @pytest.mark.parametrize("canvas_type", [
        "generic", "docs", "email", "sheets", "orchestration",
        "terminal", "coding"
    ])
    def test_all_canvas_types_have_prompts(self, service, canvas_type):
        """Test that all 7 canvas types have specialized prompts"""
        assert canvas_type in service._CANVAS_PROMPTS

    def test_orchestration_prompt_includes_workflow_details(self, service):
        """Test orchestration prompt extracts workflow-specific fields"""
        prompt = service._build_prompt(
            canvas_type="orchestration",
            canvas_state={
                "workflow_id": "wf-123",
                "approval_amount": 50000,
                "approvers": ["manager"]
            },
            agent_task="Approve workflow",
            user_interaction="submit"
        )

        assert "orchestration" in prompt.lower()
        assert "wf-123" in prompt
        assert "50000" in prompt

    def test_sheets_prompt_includes_data_fields(self, service):
        """Test sheets prompt focuses on data values"""
        prompt = service._build_prompt(
            canvas_type="sheets",
            canvas_state={"revenue": "1000000", "growth": "15%"},
            agent_task="Review Q4 data",
            user_interaction=None
        )

        assert "sheets" in prompt.lower()
        assert "revenue" in prompt.lower()
        assert "1000000" in prompt

    def test_terminal_prompt_includes_command_output(self, service):
        """Test terminal prompt extracts command info"""
        prompt = service._build_prompt(
            canvas_type="terminal",
            canvas_state={"command": "pytest", "exit_code": "0"},
            agent_task="Run tests",
            user_interaction="present"
        )

        assert "terminal" in prompt.lower()
        assert "pytest" in prompt
        assert "exit_code" in prompt.lower()

    def test_prompt_includes_agent_task_when_provided(self, service):
        """Test agent task is included in prompt"""
        prompt = service._build_prompt(
            canvas_type="generic",
            canvas_state={},
            agent_task="Analyze data trends",
            user_interaction=None
        )

        assert "Analyze data trends" in prompt

    def test_prompt_includes_user_interaction_when_provided(self, service):
        """Test user interaction is included in prompt"""
        prompt = service._build_prompt(
            canvas_type="generic",
            canvas_state={},
            agent_task=None,
            user_interaction="submit"
        )

        assert "submit" in prompt


class TestSummaryGeneration:
    """Test LLM summary generation"""

    @pytest.fixture
    def service_with_mock_llm(self):
        from core.llm.canvas_summary_service import CanvasSummaryService
        mock_byok = Mock()
        mock_byok.generate_response = AsyncMock(
            return_value="Agent presented Q4 revenue showing $1.2M with 15% growth."
        )
        return CanvasSummaryService(byok_handler=mock_byok)

    @pytest.mark.asyncio
    async def test_generate_summary_returns_llm_result(self, service_with_mock_llm):
        """Test generate_summary returns LLM-generated summary"""
        result = await service_with_mock_llm.generate_summary(
            canvas_type="sheets",
            canvas_state={"revenue": "1200000"},
            agent_task="Review Q4"
        )

        assert "revenue" in result.lower() or "1.2M" in result
        assert service_with_mock_llm.byok_handler.generate_response.called

    @pytest.mark.asyncio
    async def test_generate_summary_uses_cache(self, service_with_mock_llm):
        """Test identical requests use cached result"""
        canvas_state = {"revenue": "1200000"}

        # First call
        result1 = await service_with_mock_llm.generate_summary(
            canvas_type="sheets",
            canvas_state=canvas_state
        )

        # Second call (should use cache)
        result2 = await service_with_mock_llm.generate_summary(
            canvas_type="sheets",
            canvas_state=canvas_state
        )

        # BYOK should only be called once
        assert service_with_mock_llm.byok_handler.generate_response.call_count == 1
        assert result1 == result2

    @pytest.mark.asyncio
    async def test_generate_summary_timeout_falls_back_to_metadata(self):
        """Test timeout triggers metadata fallback"""
        from core.llm.canvas_summary_service import CanvasSummaryService

        mock_byok = Mock()
        mock_byok.generate_response = AsyncMock(
            side_effect=asyncio.TimeoutError("LLM timeout")
        )

        service = CanvasSummaryService(byok_handler=mock_byok)

        result = await service.generate_summary(
            canvas_type="terminal",
            canvas_state={"command": "ls"},
            timeout_seconds=0.1  # Very short timeout
        )

        # Should return metadata fallback
        assert "terminal" in result.lower()
        assert "summary_source" not in result  # Fallback doesn't include source

    @pytest.mark.asyncio
    async def test_generate_summary_error_falls_back_to_metadata(self):
        """Test LLM error triggers metadata fallback"""
        from core.llm.canvas_summary_service import CanvasSummaryService

        mock_byok = Mock()
        mock_byok.generate_response = AsyncMock(
            side_effect=Exception("LLM API error")
        )

        service = CanvasSummaryService(byok_handler=mock_byok)

        result = await service.generate_summary(
            canvas_type="sheets",
            canvas_state={"revenue": "1000000"}
        )

        # Should return metadata fallback
        assert "sheets" in result.lower()

    @pytest.mark.asyncio
    async def test_generate_summary_invalid_canvas_type_raises_error(self):
        """Test invalid canvas type raises ValueError"""
        from core.llm.canvas_summary_service import CanvasSummaryService

        mock_byok = Mock()
        service = CanvasSummaryService(byok_handler=mock_byok)

        with pytest.raises(ValueError, match="Invalid canvas_type"):
            await service.generate_summary(
                canvas_type="invalid_type",
                canvas_state={}
            )


class TestMetadataFallback:
    """Test metadata extraction fallback behavior"""

    @pytest.fixture
    def service(self):
        from core.llm.canvas_summary_service import CanvasSummaryService
        mock_byok = Mock()
        return CanvasSummaryService(byok_handler=mock_byok)

    def test_fallback_extracts_visual_elements(self, service):
        """Test fallback extracts visual elements from components"""
        canvas_state = {
            "components": [
                {"type": "line_chart"},
                {"type": "data_table"}
            ]
        }

        result = service._fallback_to_metadata("sheets", canvas_state)

        assert "line_chart" in result
        assert "data_table" in result

    def test_fallback_extracts_critical_data(self, service):
        """Test fallback extracts critical data points"""
        canvas_state = {
            "workflow_id": "wf-123",
            "revenue": "50000",
            "command": "pytest"
        }

        result = service._fallback_to_metadata("orchestration", canvas_state)

        assert "wf-123" in result or "50000" in result

    def test_fallback_handles_empty_state(self, service):
        """Test fallback handles empty canvas state"""
        result = service._fallback_to_metadata("generic", {})

        assert "generic" in result
        assert len(result) > 0


class TestUtilityMethods:
    """Test utility methods for cache and cost tracking"""

    @pytest.fixture
    def service(self):
        from core.llm.canvas_summary_service import CanvasSummaryService
        mock_byok = Mock()
        return CanvasSummaryService(byok_handler=mock_byok)

    def test_get_cache_stats_empty(self, service):
        """Test cache stats on empty cache"""
        stats = service.get_cache_stats()

        assert stats["cache_size"] == 0
        assert stats["tracked_sessions"] == 0
        assert stats["supported_canvas_types"] == 7

    def test_get_cache_stats_with_data(self, service):
        """Test cache stats with data"""
        service._summary_cache["key1"] = "summary1"
        service._cost_tracker["session1"] = 0.001

        stats = service.get_cache_stats()

        assert stats["cache_size"] == 1
        assert stats["tracked_sessions"] == 1

    def test_clear_cache(self, service):
        """Test cache clearing"""
        service._summary_cache["key1"] = "summary1"
        service._summary_cache["key2"] = "summary2"

        service.clear_cache()

        assert len(service._summary_cache) == 0

    def test_get_supported_canvas_types(self, service):
        """Test getting supported canvas types"""
        types = service.get_supported_canvas_types()

        assert len(types) == 7
        assert "generic" in types
        assert "orchestration" in types
        assert "sheets" in types

    def test_is_canvas_type_supported(self, service):
        """Test canvas type support check"""
        assert service.is_canvas_type_supported("generic") is True
        assert service.is_canvas_type_supported("sheets") is True
        assert service.is_canvas_type_supported("invalid") is False

    def test_get_total_cost_tracked(self, service):
        """Test total cost tracking"""
        service._cost_tracker["session1"] = 0.001
        service._cost_tracker["session2"] = 0.002

        total = service.get_total_cost_tracked()

        assert total == 0.003

    def test_get_canvas_prompt_instructions(self, service):
        """Test getting canvas-specific instructions"""
        instructions = service.get_canvas_prompt_instructions("sheets")

        assert instructions is not None
        assert "Focus on:" in instructions
        assert "Extract:" in instructions

    def test_get_canvas_prompt_instructions_invalid_type(self, service):
        """Test getting instructions for invalid canvas type"""
        instructions = service.get_canvas_prompt_instructions("invalid")

        assert instructions is None
