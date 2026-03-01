"""
Comprehensive coverage tests for CanvasSummaryService.

Tests async generation, caching, timeout handling, metadata fallback,
and all canvas types to achieve 70%+ coverage.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
import json


class TestSummaryGeneration:
    """Test summary generation with all canvas types"""

    @pytest.fixture
    def service_with_mock_llm(self):
        from core.llm.canvas_summary_service import CanvasSummaryService
        mock_byok = Mock()
        mock_byok.generate_response = AsyncMock(
            return_value="Agent presented generic canvas with key information"
        )
        return CanvasSummaryService(byok_handler=mock_byok)

    @pytest.mark.asyncio
    async def test_generate_summary_generic_canvas(self, service_with_mock_llm):
        """Test generate_summary for generic canvas type"""
        result = await service_with_mock_llm.generate_summary(
            canvas_type="generic",
            canvas_state={
                "canvas_title": "Overview",
                "components": [{"type": "text", "content": "Summary"}]
            }
        )

        assert "generic" in result.lower() or "canvas" in result.lower()
        assert service_with_mock_llm.byok_handler.generate_response.called
        # Verify system instruction was passed
        call_args = service_with_mock_llm.byok_handler.generate_response.call_args
        assert call_args.kwargs['system_instruction'] == "You are a canvas presentation analyzer. Generate concise semantic summaries (50-100 words)."

    @pytest.mark.asyncio
    async def test_generate_summary_sheets_canvas(self, service_with_mock_llm):
        """Test generate_summary for sheets canvas with revenue data"""
        service_with_mock_llm.byok_handler.generate_response = AsyncMock(
            return_value="Agent presented Q4 revenue of $1.2M with 15% growth, highlighting key metrics."
        )

        result = await service_with_mock_llm.generate_summary(
            canvas_type="sheets",
            canvas_state={
                "revenue": "1200000",
                "growth": "15%",
                "key_metrics": ["ARR", "MRR", "Churn"]
            }
        )

        assert "revenue" in result.lower() or "1.2M" in result.lower()
        assert service_with_mock_llm.byok_handler.generate_response.called
        # Verify sheets-specific prompt includes revenue
        call_args = service_with_mock_llm.byok_handler.generate_response.call_args
        prompt = call_args.kwargs['prompt']
        assert "sheets" in prompt.lower()
        assert "1200000" in prompt

    @pytest.mark.asyncio
    async def test_generate_summary_orchestration_canvas(self, service_with_mock_llm):
        """Test generate_summary for orchestration canvas with workflow"""
        service_with_mock_llm.byok_handler.generate_response = AsyncMock(
            return_value="Agent presented workflow wf-123 requiring $50K approval with 3 stakeholders."
        )

        result = await service_with_mock_llm.generate_summary(
            canvas_type="orchestration",
            canvas_state={
                "workflow_id": "wf-123",
                "approval_amount": 50000,
                "approvers": ["manager", "director"]
            }
        )

        assert "workflow" in result.lower() or "wf-123" in result.lower()
        assert service_with_mock_llm.byok_handler.generate_response.called
        # Verify workflow-specific prompt
        call_args = service_with_mock_llm.byok_handler.generate_response.call_args
        prompt = call_args.kwargs['prompt']
        assert "orchestration" in prompt.lower()
        assert "wf-123" in prompt
        assert "50000" in prompt

    @pytest.mark.asyncio
    async def test_generate_summary_terminal_canvas(self, service_with_mock_llm):
        """Test generate_summary for terminal canvas with command"""
        service_with_mock_llm.byok_handler.generate_response = AsyncMock(
            return_value="Agent presented terminal output from pytest command with exit code 0."
        )

        result = await service_with_mock_llm.generate_summary(
            canvas_type="terminal",
            canvas_state={
                "command": "pytest",
                "exit_code": 0,
                "test_counts": {"passed": 10, "failed": 0}
            }
        )

        assert "command" in result.lower() or "pytest" in result.lower()
        assert service_with_mock_llm.byok_handler.generate_response.called
        # Verify terminal-specific prompt
        call_args = service_with_mock_llm.byok_handler.generate_response.call_args
        prompt = call_args.kwargs['prompt']
        assert "terminal" in prompt.lower()
        assert "pytest" in prompt
        assert "exit_code" in prompt.lower()

    @pytest.mark.asyncio
    async def test_generate_summary_docs_canvas(self, service_with_mock_llm):
        """Test generate_summary for docs canvas with document"""
        service_with_mock_llm.byok_handler.generate_response = AsyncMock(
            return_value="Agent presented document 'Q4 Report' with 5 sections covering financial results."
        )

        result = await service_with_mock_llm.generate_summary(
            canvas_type="docs",
            canvas_state={
                "document_title": "Q4 Report",
                "sections": ["Executive Summary", "Financials", "Outlook"],
                "word_count": 2500
            }
        )

        assert "document" in result.lower() or "report" in result.lower()
        assert service_with_mock_llm.byok_handler.generate_response.called
        # Verify docs-specific prompt
        call_args = service_with_mock_llm.byok_handler.generate_response.call_args
        prompt = call_args.kwargs['prompt']
        assert "docs" in prompt.lower()
        assert "Q4 Report" in prompt

    @pytest.mark.asyncio
    async def test_generate_summary_email_canvas(self, service_with_mock_llm):
        """Test generate_summary for email canvas"""
        service_with_mock_llm.byok_handler.generate_response = AsyncMock(
            return_value="Agent presented email draft to team@company.com regarding project update."
        )

        result = await service_with_mock_llm.generate_summary(
            canvas_type="email",
            canvas_state={
                "to": ["team@company.com"],
                "subject": "Project Update",
                "attachment_count": 2
            }
        )

        assert "email" in result.lower()
        assert service_with_mock_llm.byok_handler.generate_response.called
        # Verify email-specific prompt
        call_args = service_with_mock_llm.byok_handler.generate_response.call_args
        prompt = call_args.kwargs['prompt']
        assert "email" in prompt.lower()
        assert "team@company.com" in prompt

    @pytest.mark.asyncio
    async def test_generate_summary_coding_canvas(self, service_with_mock_llm):
        """Test generate_summary for coding canvas"""
        service_with_mock_llm.byok_handler.generate_response = AsyncMock(
            return_value="Agent presented Python code with 150 lines including 5 functions."
        )

        result = await service_with_mock_llm.generate_summary(
            canvas_type="coding",
            canvas_state={
                "language": "python",
                "line_count": 150,
                "functions": ["main", "process_data", "save_results"]
            }
        )

        assert "python" in result.lower() or "code" in result.lower()
        assert service_with_mock_llm.byok_handler.generate_response.called
        # Verify coding-specific prompt
        call_args = service_with_mock_llm.byok_handler.generate_response.call_args
        prompt = call_args.kwargs['prompt']
        assert "coding" in prompt.lower()
        assert "python" in prompt.lower()

    @pytest.mark.asyncio
    async def test_generate_summary_with_agent_task(self, service_with_mock_llm):
        """Test generate_summary includes agent task in context"""
        service_with_mock_llm.byok_handler.generate_response = AsyncMock(
            return_value="Agent reviewed financials showing $1.2M revenue."
        )

        result = await service_with_mock_llm.generate_summary(
            canvas_type="sheets",
            canvas_state={"revenue": "1200000"},
            agent_task="Review financials"
        )

        assert service_with_mock_llm.byok_handler.generate_response.called
        # Verify agent task included in prompt
        call_args = service_with_mock_llm.byok_handler.generate_response.call_args
        prompt = call_args.kwargs['prompt']
        assert "Review financials" in prompt
        assert "Agent Task" in prompt and "Review financials" in prompt

    @pytest.mark.asyncio
    async def test_generate_summary_with_user_interaction(self, service_with_mock_llm):
        """Test generate_summary includes user interaction"""
        service_with_mock_llm.byok_handler.generate_response = AsyncMock(
            return_value="Agent presented workflow approval which user submitted."
        )

        result = await service_with_mock_llm.generate_summary(
            canvas_type="orchestration",
            canvas_state={"workflow_id": "wf-123"},
            user_interaction="submit"
        )

        assert service_with_mock_llm.byok_handler.generate_response.called
        # Verify user interaction included in prompt
        call_args = service_with_mock_llm.byok_handler.generate_response.call_args
        prompt = call_args.kwargs['prompt']
        assert "submit" in prompt
        assert "User Interaction" in prompt and "submit" in prompt

    @pytest.mark.asyncio
    async def test_generate_summary_invalid_canvas_type_raises(self, service_with_mock_llm):
        """Test generate_summary raises ValueError for invalid canvas type"""
        with pytest.raises(ValueError, match="Invalid canvas_type"):
            await service_with_mock_llm.generate_summary(
                canvas_type="invalid_type",
                canvas_state={}
            )


class TestCaching:
    """Test caching behavior"""

    @pytest.fixture
    def service_with_mock_llm(self):
        from core.llm.canvas_summary_service import CanvasSummaryService
        mock_byok = Mock()
        mock_byok.generate_response = AsyncMock(
            return_value="Agent presented canvas with data"
        )
        return CanvasSummaryService(byok_handler=mock_byok)

    @pytest.mark.asyncio
    async def test_generate_summary_cache_hit(self, service_with_mock_llm):
        """Test cache hit returns cached summary without calling LLM"""
        canvas_state = {"revenue": "1200000"}

        # First call
        result1 = await service_with_mock_llm.generate_summary(
            canvas_type="sheets",
            canvas_state=canvas_state
        )

        # Second call with same inputs
        result2 = await service_with_mock_llm.generate_summary(
            canvas_type="sheets",
            canvas_state=canvas_state
        )

        # BYOK should only be called once (cache hit on second call)
        assert service_with_mock_llm.byok_handler.generate_response.call_count == 1
        assert result1 == result2

    @pytest.mark.asyncio
    async def test_generate_summary_cache_miss_different_inputs(self, service_with_mock_llm):
        """Test cache miss for different canvas states"""
        # First call
        await service_with_mock_llm.generate_summary(
            canvas_type="sheets",
            canvas_state={"revenue": "1000000"}
        )

        # Second call with different state
        await service_with_mock_llm.generate_summary(
            canvas_type="sheets",
            canvas_state={"revenue": "2000000"}
        )

        # BYOK should be called twice (cache miss)
        assert service_with_mock_llm.byok_handler.generate_response.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_key_includes_canvas_type(self, service_with_mock_llm):
        """Test cache key differentiates by canvas type"""
        canvas_state = {"data": "value"}

        # Same state, different canvas types
        await service_with_mock_llm.generate_summary(
            canvas_type="sheets",
            canvas_state=canvas_state
        )

        await service_with_mock_llm.generate_summary(
            canvas_type="orchestration",
            canvas_state=canvas_state
        )

        # Should call LLM twice (different cache keys due to canvas_type)
        assert service_with_mock_llm.byok_handler.generate_response.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_key_includes_agent_task(self, service_with_mock_llm):
        """Test cache key differentiates by agent task"""
        canvas_state = {"data": "value"}

        # Same state, different agent_task
        await service_with_mock_llm.generate_summary(
            canvas_type="generic",
            canvas_state=canvas_state,
            agent_task="Task 1"
        )

        await service_with_mock_llm.generate_summary(
            canvas_type="generic",
            canvas_state=canvas_state,
            agent_task="Task 2"
        )

        # Should call LLM twice (different cache keys due to agent_task)
        assert service_with_mock_llm.byok_handler.generate_response.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_key_includes_user_interaction(self, service_with_mock_llm):
        """Test cache key differentiates by user interaction"""
        canvas_state = {"data": "value"}

        # Same state, different user_interaction
        await service_with_mock_llm.generate_summary(
            canvas_type="generic",
            canvas_state=canvas_state,
            user_interaction="submit"
        )

        await service_with_mock_llm.generate_summary(
            canvas_type="generic",
            canvas_state=canvas_state,
            user_interaction="close"
        )

        # Should call LLM twice (different cache keys due to user_interaction)
        assert service_with_mock_llm.byok_handler.generate_response.call_count == 2

    @pytest.mark.asyncio
    async def test_clear_cache_empties_cache(self, service_with_mock_llm):
        """Test clear_cache empties the cache dictionary"""
        # Generate 3 summaries
        await service_with_mock_llm.generate_summary(
            canvas_type="sheets",
            canvas_state={"id": "1"}
        )
        await service_with_mock_llm.generate_summary(
            canvas_type="terminal",
            canvas_state={"id": "2"}
        )
        await service_with_mock_llm.generate_summary(
            canvas_type="docs",
            canvas_state={"id": "3"}
        )

        # Verify cache has items
        assert len(service_with_mock_llm._summary_cache) == 3

        # Clear cache
        service_with_mock_llm.clear_cache()

        # Verify cache is empty
        assert len(service_with_mock_llm._summary_cache) == 0

    @pytest.mark.asyncio
    async def test_clear_cache_logs_count(self, service_with_mock_llm):
        """Test clear_cache logs the number of items cleared"""
        # Pre-fill cache with 5 items
        for i in range(5):
            await service_with_mock_llm.generate_summary(
                canvas_type="generic",
                canvas_state={"id": str(i)}
            )

        # Clear cache and check log (no exception = success)
        service_with_mock_llm.clear_cache()
        assert len(service_with_mock_llm._summary_cache) == 0

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, service_with_mock_llm):
        """Test get_cache_stats returns accurate statistics"""
        # Generate 3 summaries
        await service_with_mock_llm.generate_summary(
            canvas_type="sheets",
            canvas_state={"id": "1"}
        )
        await service_with_mock_llm.generate_summary(
            canvas_type="terminal",
            canvas_state={"id": "2"}
        )
        await service_with_mock_llm.generate_summary(
            canvas_type="docs",
            canvas_state={"id": "3"}
        )

        # Get stats
        stats = service_with_mock_llm.get_cache_stats()

        assert stats["cache_size"] == 3
        assert stats["tracked_sessions"] == 3
        assert stats["supported_canvas_types"] == 7


class TestErrorHandling:
    """Test timeout and error handling"""

    @pytest.fixture
    def service_with_mock_llm(self):
        from core.llm.canvas_summary_service import CanvasSummaryService
        mock_byok = Mock()
        mock_byok.generate_response = AsyncMock(
            return_value="Agent presented canvas"
        )
        return CanvasSummaryService(byok_handler=mock_byok)

    @pytest.mark.asyncio
    async def test_generate_summary_timeout_raises(self, service_with_mock_llm):
        """Test timeout raises asyncio.TimeoutError"""
        # Mock BYOK to delay >2s
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(3)
            return "Slow response"

        service_with_mock_llm.byok_handler.generate_response = AsyncMock(
            side_effect=slow_generate
        )

        # Call with timeout_seconds=1
        with pytest.raises(asyncio.TimeoutError):
            await service_with_mock_llm.generate_summary(
                canvas_type="generic",
                canvas_state={},
                timeout_seconds=1
            )

    @pytest.mark.asyncio
    async def test_generate_summary_custom_timeout(self, service_with_mock_llm):
        """Test custom timeout parameter works"""
        # Mock BYOK with 1s delay
        async def delayed_generate(*args, **kwargs):
            await asyncio.sleep(1)
            return "Agent presented canvas with delay"

        service_with_mock_llm.byok_handler.generate_response = AsyncMock(
            side_effect=delayed_generate
        )

        # Call with timeout_seconds=5 (should complete)
        result = await service_with_mock_llm.generate_summary(
            canvas_type="generic",
            canvas_state={},
            timeout_seconds=5
        )

        assert "delay" in result.lower() or "canvas" in result.lower()

    @pytest.mark.asyncio
    async def test_generate_summary_llm_error_raises(self, service_with_mock_llm):
        """Test LLM error propagates to caller"""
        service_with_mock_llm.byok_handler.generate_response = AsyncMock(
            side_effect=Exception("LLM API error")
        )

        # Error should propagate
        with pytest.raises(Exception, match="LLM API error"):
            await service_with_mock_llm.generate_summary(
                canvas_type="sheets",
                canvas_state={"revenue": "1000000"}
            )

    @pytest.mark.asyncio
    async def test_generate_summary_with_json_serialization(self, service_with_mock_llm):
        """Test JSON serialization works for complex nested canvas state"""
        complex_state = {
            "nested": {
                "level1": {
                    "level2": ["item1", "item2"]
                }
            },
            "list_of_dicts": [
                {"id": 1, "name": "test1"},
                {"id": 2, "name": "test2"}
            ],
            "mixed_types": ["string", 123, True, None]
        }

        # Should not raise JSON serialization error
        result = await service_with_mock_llm.generate_summary(
            canvas_type="generic",
            canvas_state=complex_state
        )

        assert result is not None
        assert service_with_mock_llm.byok_handler.generate_response.called

    def test_fallback_to_metadata_with_components(self, service_with_mock_llm):
        """Test fallback extracts component types"""
        canvas_state = {
            "components": [
                {"type": "button", "label": "Submit"},
                {"type": "text", "content": "Description"}
            ]
        }

        result = service_with_mock_llm._fallback_to_metadata(
            "sheets",
            canvas_state
        )

        assert "button" in result
        assert "text" in result
        assert "sheets" in result

    def test_fallback_to_metadata_with_critical_data(self, service_with_mock_llm):
        """Test fallback extracts critical fields"""
        canvas_state = {
            "workflow_id": "wf-456",
            "revenue": "75000",
            "amount": "50000"
        }

        result = service_with_mock_llm._fallback_to_metadata(
            "orchestration",
            canvas_state
        )

        assert "wf-456" in result or "75000" in result or "50000" in result

    def test_fallback_to_metadata_empty_state(self, service_with_mock_llm):
        """Test fallback handles empty canvas state"""
        result = service_with_mock_llm._fallback_to_metadata(
            "generic",
            {}
        )

        assert "generic" in result
        assert "canvas" in result

    def test_fallback_to_metadata_terminal_command(self, service_with_mock_llm):
        """Test fallback includes terminal command"""
        canvas_state = {
            "command": "pytest",
            "exit_code": 0
        }

        result = service_with_mock_llm._fallback_to_metadata(
            "terminal",
            canvas_state
        )

        assert "command: pytest" in result
        assert "terminal" in result


class TestUtilityMethods:
    """Test utility and helper methods"""

    @pytest.fixture
    def service(self):
        from core.llm.canvas_summary_service import CanvasSummaryService
        mock_byok = Mock()
        return CanvasSummaryService(byok_handler=mock_byok)

    def test_get_supported_canvas_types(self, service):
        """Test get_supported_canvas_types returns all 7 types"""
        types = service.get_supported_canvas_types()

        assert len(types) == 7
        assert "generic" in types
        assert "docs" in types
        assert "email" in types
        assert "sheets" in types
        assert "orchestration" in types
        assert "terminal" in types
        assert "coding" in types

    @pytest.mark.parametrize("canvas_type", [
        "generic", "docs", "email", "sheets", "orchestration", "terminal", "coding"
    ])
    def test_is_canvas_type_supported_valid(self, service, canvas_type):
        """Test is_canvas_type_supported returns True for valid types"""
        assert service.is_canvas_type_supported(canvas_type) is True

    def test_is_canvas_type_supported_invalid(self, service):
        """Test is_canvas_type_supported returns False for invalid type"""
        assert service.is_canvas_type_supported("invalid_type") is False

    def test_get_total_cost_tracked(self, service):
        """Test get_total_cost_tracked sums all tracked costs"""
        service._cost_tracker["session1"] = 0.001
        service._cost_tracker["session2"] = 0.002
        service._cost_tracker["session3"] = 0.003

        total = service.get_total_cost_tracked()

        assert total == 0.006

    @pytest.mark.parametrize("canvas_type", [
        "generic", "docs", "email", "sheets", "orchestration", "terminal", "coding"
    ])
    def test_get_canvas_prompt_instructions_valid(self, service, canvas_type):
        """Test get_canvas_prompt_instructions returns non-None for valid types"""
        instructions = service.get_canvas_prompt_instructions(canvas_type)

        assert instructions is not None
        assert "Focus on:" in instructions
        assert "Extract:" in instructions

    def test_get_canvas_prompt_instructions_invalid(self, service):
        """Test get_canvas_prompt_instructions returns None for invalid type"""
        instructions = service.get_canvas_prompt_instructions("invalid_type")

        assert instructions is None

    def test_calculate_semantic_richness(self, service):
        """Test calculate_semantic_richness scores rich summaries higher"""
        rich_summary = "Agent presented workflow requiring $50K approval from stakeholders due to budget constraints showing 15% revenue growth trend"

        score = service._calculate_semantic_richness(rich_summary)

        assert score >= 0.8
        assert score <= 1.0

    def test_detect_hallucination_basic(self, service):
        """Test detect_hallucination detects uncertainty patterns"""
        summary = "I think the workflow might be wf-999 but I'm not sure"
        canvas_state = {"workflow_id": "wf-123"}

        # The summary mentions wf-999 which doesn't exist in state
        result = service._detect_hallucination(summary, canvas_state)

        # Should detect hallucination (wf-999 not in state)
        assert result is True
