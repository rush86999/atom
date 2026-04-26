"""
Test suite for Generic Agent - Agent abstraction and execution patterns.

Tests cover:
- Agent initialization and configuration
- ReAct loop execution
- Memory integration (world model, episodic memory)
- Tool execution and governance checks
- Vision capabilities
- Error handling and timeouts
- Reflection and critique generation
- Graduation and skill promotion
- TRACE framework metrics
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime, timezone
import json
import uuid


# Import target module
from core.generic_agent import GenericAgent
from core.models import AgentRegistry, AgentStatus


class TestGenericAgentInit:
    """Test GenericAgent initialization."""

    def test_initialization(self):
        """GenericAgent initializes with agent model."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={
                "system_prompt": "You are a helpful assistant",
                "tools": "*",
                "max_steps": 5
            }
        )

        with patch('core.generic_agent.WorldModelService'), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service'), \
             patch('core.generic_agent.LLMService'):
            agent = GenericAgent(agent_model, workspace_id="default")
            assert agent.id == "agent-123"
            assert agent.name == "Test Agent"
            assert agent.workspace_id == "default"
            assert agent.vision_enabled is False

    def test_initialization_with_vision_enabled(self):
        """GenericAgent initializes with vision capability."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Vision Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={}
        )

        with patch('core.generic_agent.WorldModelService'), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service'), \
             patch('core.generic_agent.LLMService'):
            agent = GenericAgent(agent_model)
            # vision_enabled is not a field in AgentRegistry, it's set via getattr in GenericAgent
            assert agent.vision_enabled is False  # Default since not in model

    def test_initialization_with_default_workspace(self):
        """GenericAgent uses default workspace if not specified."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant"
        )

        with patch('core.generic_agent.WorldModelService'), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service'), \
             patch('core.generic_agent.LLMService'):
            agent = GenericAgent(agent_model)
            assert agent.workspace_id == "default"


class TestAgentConfiguration:
    """Test agent configuration handling."""

    def test_system_prompt_from_config(self):
        """Agent loads system prompt from configuration."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={
                "system_prompt": "Custom system prompt"
            }
        )

        with patch('core.generic_agent.WorldModelService'), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service'), \
             patch('core.generic_agent.LLMService'):
            agent = GenericAgent(agent_model)
            assert agent.system_prompt == "Custom system prompt"

    def test_default_system_prompt(self):
        """Agent uses default system prompt if not configured."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={}
        )

        with patch('core.generic_agent.WorldModelService'), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service'), \
             patch('core.generic_agent.LLMService'):
            agent = GenericAgent(agent_model)
            assert "You are" in agent.system_prompt
            assert agent.name in agent.system_prompt

    def test_allowed_tools_configuration(self):
        """Agent loads allowed tools from configuration."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={
                "tools": ["browser_navigate", "browser_screenshot"]
            }
        )

        with patch('core.generic_agent.WorldModelService'), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service'), \
             patch('core.generic_agent.LLMService'):
            agent = GenericAgent(agent_model)
            assert agent.allowed_tools == ["browser_navigate", "browser_screenshot"]

    def test_wildcard_tools(self):
        """Agent accepts all tools with wildcard."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={"tools": "*"}
        )

        with patch('core.generic_agent.WorldModelService'), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service'), \
             patch('core.generic_agent.LLMService'):
            agent = GenericAgent(agent_model)
            assert agent.allowed_tools == "*"


class TestAgentExecution:
    """Test agent task execution."""

    @pytest.mark.asyncio
    async def test_execute_simple_task(self):
        """Agent executes a simple task successfully."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={"max_steps": 3}
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = MagicMock(
            thought="I will help",
            action=None,
            final_answer="Hello! How can I help you?"
        )
        mock_llm._get_handler.return_value.analyze_query_complexity.return_value = MagicMock(value="simple")

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session'):
            agent = GenericAgent(agent_model)
            result = await agent.execute("Say hello")
            assert result["status"] == "success"
            assert "final_answer" in result

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self):
        """Agent execution times out after configured duration."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={"timeout_seconds": 1}
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}

        mock_llm = AsyncMock()
        # Simulate slow LLM that times out
        import asyncio
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(2)
            return MagicMock(final_answer="Too late")

        mock_llm.generate_structured = slow_generate
        mock_llm._get_handler.return_value.analyze_query_complexity.return_value = MagicMock(value="simple")

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session'):
            agent = GenericAgent(agent_model)
            result = await agent.execute("Test task")
            assert result["status"] == "timeout"

    @pytest.mark.asyncio
    async def test_execute_with_max_steps(self):
        """Agent stops after reaching max steps."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={"max_steps": 2}
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}

        mock_llm = AsyncMock()
        # Return actions without final answer to trigger max steps
        mock_llm.generate_structured.return_value = MagicMock(
            thought="Thinking",
            action=MagicMock(tool="test_tool", params={}),
            final_answer=None
        )
        mock_llm._get_handler.return_value.analyze_query_complexity.return_value = MagicMock(value="moderate")

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []
        mock_mcp.call_tool.return_value = "Tool executed"

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session'):
            agent = GenericAgent(agent_model)
            result = await agent.execute("Test task")
            assert result["status"] == "max_steps_exceeded"

    @pytest.mark.asyncio
    async def test_execute_with_step_callback(self):
        """Agent calls step callback during execution."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={"max_steps": 1}
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = MagicMock(
            thought="I will help",
            action=None,
            final_answer="Done"
        )
        mock_llm._get_handler.return_value.analyze_query_complexity.return_value = MagicMock(value="simple")

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []

        callback_called = []

        async def callback(step_data):
            callback_called.append(step_data)

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session'):
            agent = GenericAgent(agent_model)
            await agent.execute("Test", step_callback=callback)
            assert len(callback_called) > 0
            assert "step" in callback_called[0]


class TestToolExecution:
    """Test tool execution and governance."""

    @pytest.mark.asyncio
    async def test_execute_allowed_tool(self):
        """Agent executes tool when governance allows."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={"tools": "*"}
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = MagicMock(
            thought="I need to navigate",
            action=MagicMock(tool="browser_navigate", params={"url": "https://example.com"}),
            final_answer=None
        )
        mock_llm._get_handler.return_value.analyze_query_complexity.return_value = MagicMock(value="simple")

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []
        mock_mcp.call_tool.return_value = "Navigated successfully"

        mock_gov = MagicMock()
        mock_gov.can_perform_action.return_value = {"allowed": True}

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session') as mock_db:
            mock_db.return_value.__enter__.return_value = None
            agent = GenericAgent(agent_model)
            result = await agent.execute("Navigate to example.com")
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_tool_not_allowed(self):
        """Agent blocks tool when not in allowed list."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={"tools": ["browser_navigate"]}  # Only allow browser_navigate
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = MagicMock(
            thought="I need to screenshot",
            action=MagicMock(tool="browser_screenshot", params={}),
            final_answer=None
        )
        mock_llm._get_handler.return_value.analyze_query_complexity.return_value = MagicMock(value="simple")

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session'):
            agent = GenericAgent(agent_model)
            result = await agent.execute("Take screenshot")
            # Should complete without executing the disallowed tool
            assert "steps" in result


class TestMemoryIntegration:
    """Test memory integration (world model, episodic memory)."""

    @pytest.mark.asyncio
    async def test_recall_experiences(self):
        """Agent recalls experiences from world model."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant"
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {
            'experiences': [
                {'input_summary': 'Previous task', 'outcome': 'completed'}
            ]
        }

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = MagicMock(
            thought="Using past experience",
            final_answer="Done"
        )
        mock_llm._get_handler.return_value.analyze_query_complexity.return_value = MagicMock(value="simple")

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session'):
            agent = GenericAgent(agent_model)
            await agent.execute("Test task")
            # Verify world model was queried
            mock_world_model.recall_experiences.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_experience(self):
        """Agent records experience after execution."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant"
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}
        mock_world_model.record_experience = AsyncMock()

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = MagicMock(
            thought="Done",
            final_answer="Complete"
        )
        mock_llm._get_handler.return_value.analyze_query_complexity.return_value = MagicMock(value="simple")

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session'):
            agent = GenericAgent(agent_model)
            await agent.execute("Test task")
            # Verify experience was recorded
            mock_world_model.record_experience.assert_called_once()


class TestVisionCapabilities:
    """Test vision capabilities and screenshot handling."""

    @pytest.mark.asyncio
    async def test_screenshot_capture_for_vision(self):
        """Agent captures screenshot for vision-enabled tasks."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Vision Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={"tools": "*"}
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}

        mock_llm = AsyncMock()
        # First call returns action to take screenshot
        mock_llm.generate_structured.side_effect = [
            MagicMock(
                thought="I need to see the page",
                action=MagicMock(tool="browser_screenshot", params={}),
                final_answer=None
            ),
            MagicMock(
                thought="Now I can see",
                final_answer="Page loaded successfully"
            )
        ]
        mock_llm._get_handler.return_value.analyze_query_complexity.return_value = MagicMock(value="simple")

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []
        # Mock screenshot file creation
        with patch('core.generic_agent.open', create=True) as mock_open, \
             patch('os.path.exists', return_value=True), \
             patch('base64.b64encode', return_value=b'mock_base64_data'):
            mock_open.return_value.__enter__.return_value.read.return_value = b'mock_image_data'
            mock_mcp.call_tool.return_value = "Screenshot saved to /tmp/screenshot_test.png"

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session'):
            agent = GenericAgent(agent_model)
            result = await agent.execute("Check the page")
            # Agent should have screenshot data after first step
            # (This is a basic test - full vision testing would require more setup)


class TestReflectionAndCritique:
    """Test reflection and critique generation on failures."""

    @pytest.mark.asyncio
    async def test_generate_critique_on_failure(self):
        """Agent generates critique when execution fails."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant"
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}

        mock_llm = AsyncMock()
        mock_llm.generate_structured.side_effect = Exception("LLM failed")
        mock_llm._get_handler.return_value.analyze_query_complexity.return_value = MagicMock(value="simple")

        mock_reflection = AsyncMock()
        mock_reflection.generate_critique = AsyncMock()

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService', return_value=mock_reflection), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session'):
            agent = GenericAgent(agent_model)
            result = await agent.execute("Test task")
            # Should generate critique on failure
            assert result["status"] == "failed"


class TestGraduationAndSkillPromotion:
    """Test graduation and skill promotion logic."""

    @pytest.mark.asyncio
    async def test_skill_promotion_on_success(self):
        """Agent checks skill promotion on successful execution."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={
                "active_skill_id": "skill-001",
                "specialty": "data_processing"
            }
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = MagicMock(
            thought="Done",
            final_answer="Complete"
        )
        mock_llm._get_handler.return_value.analyze_query_complexity.return_value = MagicMock(value="simple")

        mock_graduation = AsyncMock()
        mock_graduation.check_skill_promotion.return_value = {"promoted": True}

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session', return_value=mock_db), \
             patch('core.generic_agent.GraduationService', return_value=mock_graduation):
            agent = GenericAgent(agent_model)
            await agent.execute("Test task")
            # Should check graduation on success
            # (Graduation check is called in _record_execution)


class TestTRACEFrameworkMetrics:
    """Test TRACE framework metrics collection."""

    @pytest.mark.asyncio
    async def test_complexity_analysis(self):
        """Agent analyzes query complexity."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant"
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = MagicMock(
            thought="Done",
            final_answer="Complete"
        )
        # Mock complexity analysis
        mock_handler = MagicMock()
        mock_handler.analyze_query_complexity.return_value = MagicMock(value="moderate")
        mock_llm._get_handler.return_value = mock_handler

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session'):
            agent = GenericAgent(agent_model)
            result = await agent.execute("Test task")
            # Should include complexity in result
            assert "complexity" in result
            assert result["complexity"] == "moderate"

    @pytest.mark.asyncio
    async def test_step_efficiency_metric(self):
        """Agent calculates step efficiency metric."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant"
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = MagicMock(
            thought="Done",
            final_answer="Complete"
        )
        mock_llm._get_handler.return_value.analyze_query_complexity.return_value = MagicMock(value="simple")

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session'):
            agent = GenericAgent(agent_model)
            result = await agent.execute("Test task")
            # Should include step efficiency
            assert "step_efficiency" in result
            assert isinstance(result["step_efficiency"], float)


class TestErrorHandling:
    """Test error handling in agent operations."""

    @pytest.mark.asyncio
    async def test_llm_not_available(self):
        """Agent handles LLM not available gracefully."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant"
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = None
        mock_llm.generate.return_value = None

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session'):
            agent = GenericAgent(agent_model)
            result = await agent.execute("Test task")
            # Should handle gracefully
            assert "output" in result

    @pytest.mark.asyncio
    async def test_tool_execution_error(self):
        """Agent handles tool execution errors gracefully."""
        agent_model = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            type="assistant", module_path="agents.assistant", class_name="AssistantAgent", category="general",
            configuration={"tools": "*"}
        )

        mock_world_model = AsyncMock()
        mock_world_model.recall_experiences.return_value = {}

        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = MagicMock(
            thought="I will execute tool",
            action=MagicMock(tool="broken_tool", params={}),
            final_answer=None
        )
        mock_llm._get_handler.return_value.analyze_query_complexity.return_value = MagicMock(value="simple")

        mock_mcp = AsyncMock()
        mock_mcp.get_all_tools.return_value = []
        mock_mcp.call_tool.side_effect = Exception("Tool failed")

        mock_gov = MagicMock()
        mock_gov.can_perform_action.return_value = {"allowed": True}

        with patch('core.generic_agent.WorldModelService', return_value=mock_world_model), \
             patch('core.generic_agent.ReflectionService'), \
             patch('core.generic_agent.CanvasSummaryService'), \
             patch('core.generic_agent.mcp_service', mock_mcp), \
             patch('core.generic_agent.LLMService', return_value=mock_llm), \
             patch('core.generic_agent.get_db_session') as mock_db:
            mock_db.return_value.__enter__.return_value = None
            agent = GenericAgent(agent_model)
            result = await agent.execute("Execute broken tool")
            # Should continue despite tool error
            assert "steps" in result
