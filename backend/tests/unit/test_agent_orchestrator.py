"""
Unit Tests for Agent Orchestrator

Tests autonomous agent loop orchestration:
- ReAct pattern implementation
- Tool execution and observation
- Loop termination and final answers
- Error handling in reasoning loops

Target Coverage: 80%
Target Branch Coverage: 50%+
Pass Rate Target: 95%+
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from core.agent_orchestrator import (
    AgentOrchestrator,
    AgentExecutionResponse
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_llm_service():
    """Create mock LLM service."""
    llm = Mock()
    llm.generate_structured = AsyncMock()
    return llm


@pytest.fixture
def simple_toolbox():
    """Create simple toolbox for testing."""
    return {
        "add": lambda a, b: a + b,
        "multiply": lambda a, b: a * b,
        "get_time": lambda: datetime.now().isoformat()
    }


@pytest.fixture
def async_toolbox():
    """Create async toolbox for testing."""
    async def async_add(a, b):
        await asyncio.sleep(0.001)
        return a + b

    async def async_multiply(a, b):
        await asyncio.sleep(0.001)
        return a * b

    return {
        "async_add": async_add,
        "async_multiply": async_multiply
    }


# =============================================================================
# Test Class: AgentOrchestrator - Initialization
# =============================================================================

class TestAgentOrchestratorInit:
    """Tests for AgentOrchestrator initialization."""

    def test_initialization_with_defaults(self, mock_llm_service):
        """RED: Test orchestrator initialization with default parameters."""
        orchestrator = AgentOrchestrator(llm_service=mock_llm_service)

        assert orchestrator.llm_service == mock_llm_service
        assert orchestrator.model == "quality"
        assert orchestrator.max_loops == 10
        assert orchestrator.history == []
        assert "autonomous AI agent" in orchestrator.system_instruction.lower()

    def test_initialization_with_custom_params(self, mock_llm_service):
        """RED: Test initialization with custom parameters."""
        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            model="fast",
            max_loops=5,
            system_instruction="Custom instruction"
        )

        assert orchestrator.model == "fast"
        assert orchestrator.max_loops == 5
        assert orchestrator.system_instruction == "Custom instruction"


# =============================================================================
# Test Class: AgentOrchestrator - Run
# =============================================================================

class TestAgentOrchestratorRun:
    """Tests for run method."""

    @pytest.mark.asyncio
    async def test_executes_simple_task(self, mock_llm_service, simple_toolbox):
        """RED: Test simple task execution."""
        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            max_loops=3
        )

        # Mock LLM to return final answer immediately
        mock_step = Mock()
        mock_step.thought = "I need to add 2 and 3"
        mock_step.action = None
        mock_step.final_answer = "2 + 3 = 5"

        mock_llm_service.generate_structured = AsyncMock(return_value=mock_step)

        result = await orchestrator.run(
            task="What is 2 + 3?",
            toolbox=simple_toolbox
        )

        assert result.status == "completed"
        assert result.final_answer == "2 + 3 = 5"
        assert result.total_loops == 1

    @pytest.mark.asyncio
    async def test_executes_tool_and_observes(self, mock_llm_service, simple_toolbox):
        """RED: Test tool execution with observation."""
        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            max_loops=3
        )

        # First loop: use tool
        mock_step1 = Mock()
        mock_step1.thought = "I need to add 2 and 3"
        mock_step1.action = Mock(tool="add", params={"a": 2, "b": 3})
        mock_step1.final_answer = None

        # Second loop: final answer
        mock_step2 = Mock()
        mock_step2.thought = "The result is 5"
        mock_step2.action = None
        mock_step2.final_answer = "The answer is 5"

        mock_llm_service.generate_structured = AsyncMock(
            side_effect=[mock_step1, mock_step2]
        )

        result = await orchestrator.run(
            task="Add 2 and 3",
            toolbox=simple_toolbox
        )

        assert result.status == "completed"
        assert result.total_loops == 2
        assert result.final_answer == "The answer is 5"

    @pytest.mark.asyncio
    async def test_handles_async_tool_functions(self, mock_llm_service, async_toolbox):
        """RED: Test handling of async tool functions."""
        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            max_loops=2
        )

        # Use async tool then final answer
        mock_step1 = Mock()
        mock_step1.thought = "Add numbers asynchronously"
        mock_step1.action = Mock(tool="async_add", params={"a": 10, "b": 20})
        mock_step1.final_answer = None

        mock_step2 = Mock()
        mock_step2.thought = "Got result"
        mock_step2.action = None
        mock_step2.final_answer = "Result is 30"

        mock_llm_service.generate_structured = AsyncMock(
            side_effect=[mock_step1, mock_step2]
        )

        result = await orchestrator.run(
            task="Add 10 and 20",
            toolbox=async_toolbox
        )

        assert result.status == "completed"
        assert result.total_loops == 2

    @pytest.mark.asyncio
    async def test_handles_missing_tool(self, mock_llm_service, simple_toolbox):
        """RED: Test handling when tool is not in toolbox."""
        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            max_loops=2
        )

        # Try to use non-existent tool
        mock_step = Mock()
        mock_step.thought = "I'll use the missing_tool"
        mock_step.action = Mock(tool="missing_tool", params={})
        mock_step.final_answer = None

        mock_llm_service.generate_structured = AsyncMock(return_value=mock_step)

        result = await orchestrator.run(
            task="Try missing tool",
            toolbox=simple_toolbox
        )

        # Should handle gracefully with error observation
        assert "not found" in result.steps[0]["result"].lower()

    @pytest.mark.asyncio
    async def test_handles_tool_execution_error(self, mock_llm_service, simple_toolbox):
        """RED: Test handling of tool execution errors."""
        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            max_loops=2
        )

        # Create toolbox with error-prone tool
        error_toolbox = {
            "error_tool": lambda: 1/0  # Division by zero
        }

        mock_step = Mock()
        mock_step.thought = "Use error tool"
        mock_step.action = Mock(tool="error_tool", params={})
        mock_step.final_answer = None

        mock_llm_service.generate_structured = AsyncMock(return_value=mock_step)

        result = await orchestrator.run(
            task="Use error tool",
            toolbox=error_toolbox
        )

        # Should handle tool error gracefully
        assert "error" in result.steps[0]["result"].lower()

    @pytest.mark.asyncio
    async def test_stops_at_max_loops(self, mock_llm_service, simple_toolbox):
        """RED: Test that loop stops at max_loops without final answer."""
        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            max_loops=2
        )

        # Always return action (no final answer)
        mock_step = Mock()
        mock_step.thought = "Keep thinking"
        mock_step.action = Mock(tool="add", params={"a": 1, "b": 1})
        mock_step.final_answer = None

        mock_llm_service.generate_structured = AsyncMock(return_value=mock_step)

        result = await orchestrator.run(
            task="Keep going",
            toolbox=simple_toolbox
        )

        assert result.status == "exhausted"
        assert result.total_loops == 2

    @pytest.mark.asyncio
    async def test_handles_llm_reasoning_failure(self, mock_llm_service, simple_toolbox):
        """RED: Test handling of LLM reasoning failure."""
        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            max_loops=3
        )

        # LLM raises exception
        mock_llm_service.generate_structured = AsyncMock(
            side_effect=Exception("LLM API error")
        )

        result = await orchestrator.run(
            task="Test task",
            toolbox=simple_toolbox
        )

        assert result.status == "failed"
        assert "error" in result.lower()
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_includes_context_in_execution(self, mock_llm_service, simple_toolbox):
        """RED: Test that context is included in execution."""
        orchestrator = AgentOrchestrator(
            llm_service=mock_llm_service,
            max_loops=1
        )

        context = {"user_id": "user123", "session_id": "session456"}

        mock_step = Mock()
        mock_step.thought = "Context aware"
        mock_step.action = None
        mock_step.final_answer = "Done"

        mock_llm_service.generate_structured = AsyncMock(return_value=mock_step)

        result = await orchestrator.run(
            task="Use context",
            toolbox=simple_toolbox,
            context=context
        )

        assert result.status == "completed"


# =============================================================================
# Test Class: AgentExecutionResponse
# =============================================================================

class TestAgentExecutionResponse:
    """Tests for AgentExecutionResponse model."""

    def test_response_with_default_values(self):
        """RED: Test response initialization with defaults."""
        response = AgentExecutionResponse()

        assert response.status == "completed"
        assert response.final_answer is None
        assert response.steps == []
        assert response.execution_time_ms == 0.0
        assert response.total_loops == 0
        assert response.error is None

    def test_response_with_custom_values(self):
        """RED: Test response with custom values."""
        response = AgentExecutionResponse(
            status="failed",
            final_answer="Could not complete",
            steps=[{"loop": 1}],
            execution_time_ms=150.5,
            total_loops=1,
            error="Tool error"
        )

        assert response.status == "failed"
        assert response.final_answer == "Could not complete"
        assert response.steps == [{"loop": 1}]
        assert response.execution_time_ms == 150.5
        assert response.total_loops == 1
        assert response.error == "Tool error"


# =============================================================================
# Test Class: Tool Descriptions
# =============================================================================

class TestGenerateToolDescriptions:
    """Tests for _generate_tool_descriptions method."""

    def test_generates_descriptions_from_docstrings(self, mock_llm_service):
        """RED: Test generating tool descriptions from docstrings."""

        def documented_tool():
            """This is a documented tool."""
            pass

        toolbox = {
            "documented_tool": documented_tool
        }

        orchestrator = AgentOrchestrator(llm_service=mock_llm_service)
        descriptions = orchestrator._generate_tool_descriptions(toolbox)

        assert "documented_tool:" in descriptions
        assert "documented tool" in descriptions.lower()

    def test_handles_missing_docstrings(self, mock_llm_service):
        """RED: Test handling tools without docstrings."""
        toolbox = {
            "undocumented_tool": lambda x: x
        }

        orchestrator = AgentOrchestrator(llm_service=mock_llm_service)
        descriptions = orchestrator._generate_tool_descriptions(toolbox)

        assert "undocumented_tool:" in descriptions
        assert "no description available" in descriptions.lower()


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
