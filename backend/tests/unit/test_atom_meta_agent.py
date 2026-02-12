"""
Baseline unit tests for AtomMetaAgent class

Tests cover:
- Initialization and configuration
- Agent execution lifecycle
- ReAct loop step generation
- Tool execution with governance
- Agent spawning and delegation
- Memory query functionality
- Error handling and edge cases
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call
from datetime import datetime
from typing import Dict, Any
import uuid

from core.atom_meta_agent import (
    AtomMetaAgent,
    AgentTriggerMode,
    SpecialtyAgentTemplate,
)
from core.models import AgentRegistry, AgentStatus, User


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_user():
    """Mock user for testing"""
    user = MagicMock(spec=User)
    user.id = "test-user-123"
    user.email = "test@example.com"
    user.metadata_json = {"communication_style": {"enable_personalization": False}}
    return user


@pytest.fixture
def mock_world_model():
    """Mock WorldModelService for testing"""
    world_model = AsyncMock()
    world_model.recall_experiences = AsyncMock(return_value={
        "experiences": [],
        "knowledge": [],
        "formulas": [],
        "business_facts": []
    })
    world_model.record_experience = AsyncMock()
    return world_model


@pytest.fixture
def mock_mcp_service():
    """Mock MCP service for testing"""
    mcp = AsyncMock()
    mcp.get_all_tools = AsyncMock(return_value=[
        {"name": "mcp_tool_search", "description": "Search for tools"},
        {"name": "save_business_fact", "description": "Save business fact"},
        {"name": "ingest_knowledge_from_text", "description": "Ingest knowledge"},
        {"name": "trigger_workflow", "description": "Trigger workflow"},
        {"name": "delegate_task", "description": "Delegate task"},
        {"name": "canvas_tool", "description": "Canvas tool"}
    ])
    mcp.search_tools = AsyncMock(return_value=[
        {"name": "new_tool", "description": "A new tool"}
    ])
    mcp.call_tool = AsyncMock(return_value="Tool execution result")
    return mcp


@pytest.fixture
def mock_byok_handler():
    """Mock BYOKHandler for testing"""
    byok = AsyncMock()
    byok.generate_structured_response = AsyncMock(return_value=None)
    byok.generate_response = AsyncMock(return_value="Test response")
    return byok


@pytest.fixture
def atom_agent(mock_world_model, mock_mcp_service, mock_byok_handler):
    """Create AtomMetaAgent instance with mocked dependencies"""
    with patch('core.atom_meta_agent.WorldModelService', return_value=mock_world_model), \
         patch('core.atom_meta_agent.mcp_service', mock_mcp_service), \
         patch('core.atom_meta_agent.BYOKHandler', return_value=mock_byok_handler), \
         patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator'):

        agent = AtomMetaAgent(workspace_id="test-workspace-123")
        agent.world_model = mock_world_model
        agent.mcp = mock_mcp_service
        agent.llm = mock_byok_handler
        yield agent


# =============================================================================
# TEST CLASS: AtomMetaAgentInit
# Tests for initialization and configuration
# =============================================================================

class TestAtomMetaAgentInit:
    """Test AtomMetaAgent initialization and setup"""

    def test_initialization_with_defaults(self):
        """Test agent initialization with default parameters"""
        with patch('core.atom_meta_agent.WorldModelService'), \
             patch('core.atom_meta_agent.mcp_service'), \
             patch('core.atom_meta_agent.BYOKHandler'), \
             patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator'):

            agent = AtomMetaAgent()

            assert agent.workspace_id == "default"
            assert agent.user is None
            assert agent._spawned_agents == {}
            assert agent.session_tools == []

    def test_initialization_with_workspace_id(self):
        """Test agent initialization with custom workspace ID"""
        with patch('core.atom_meta_agent.WorldModelService'), \
             patch('core.atom_meta_agent.mcp_service'), \
             patch('core.atom_meta_agent.BYOKHandler'), \
             patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator'):

            agent = AtomMetaAgent(workspace_id="custom-workspace")

            assert agent.workspace_id == "custom-workspace"

    def test_initialization_with_user(self, mock_user):
        """Test agent initialization with user context"""
        with patch('core.atom_meta_agent.WorldModelService'), \
             patch('core.atom_meta_agent.mcp_service'), \
             patch('core.atom_meta_agent.BYOKHandler'), \
             patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator'):

            agent = AtomMetaAgent(user=mock_user)

            assert agent.user is not None
            assert agent.user.id == mock_user.id

    def test_core_tools_names_defined(self):
        """Test that CORE_TOOLS_NAMES is properly defined"""
        # Verify core tools are defined (actual list may have duplicates or additional items)
        assert len(AtomMetaAgent.CORE_TOOLS_NAMES) > 0
        assert "mcp_tool_search" in AtomMetaAgent.CORE_TOOLS_NAMES
        assert "save_business_fact" in AtomMetaAgent.CORE_TOOLS_NAMES
        assert "trigger_workflow" in AtomMetaAgent.CORE_TOOLS_NAMES
        assert "delegate_task" in AtomMetaAgent.CORE_TOOLS_NAMES
        assert "canvas_tool" in AtomMetaAgent.CORE_TOOLS_NAMES

    def test_specialty_agent_templates_defined(self):
        """Test that specialty agent templates are defined"""
        templates = SpecialtyAgentTemplate.TEMPLATES

        assert "finance_analyst" in templates
        assert "sales_assistant" in templates
        assert "ops_coordinator" in templates
        assert "hr_assistant" in templates
        assert "procurement_specialist" in templates
        assert "knowledge_analyst" in templates
        assert "marketing_analyst" in templates

        # Check template structure
        finance = templates["finance_analyst"]
        assert "name" in finance
        assert "category" in finance
        assert "description" in finance
        assert "capabilities" in finance
        assert "default_params" in finance


# =============================================================================
# TEST CLASS: AtomMetaAgentExecution
# Tests for main execution lifecycle
# =============================================================================

class TestAtomMetaAgentExecution:
    """Test AtomMetaAgent execution methods"""

    @pytest.mark.asyncio
    async def test_execute_simple_request(self, atom_agent):
        """Test execution of a simple request"""
        # Mock the database session and governance
        with patch('core.atom_meta_agent.get_db_session'), \
             patch('core.atom_meta_agent.AgentGovernanceService'):

            from core.react_models import ReActStep

            mock_response = ReActStep(
                thought="I should respond to the user",
                final_answer="Hello! How can I help you today?"
            )
            atom_agent.llm.generate_structured_response = AsyncMock(return_value=mock_response)

            result = await atom_agent.execute("Hello")

            assert result is not None
            assert "status" in result
            assert "final_output" in result
            assert result["final_output"] == "Hello! How can I help you today?"

    @pytest.mark.asyncio
    async def test_execute_with_context(self, atom_agent):
        """Test execution with additional context"""
        with patch('core.atom_meta_agent.get_db_session'), \
             patch('core.atom_meta_agent.AgentGovernanceService'):

            from core.react_models import ReActStep

            mock_response = ReActStep(
                thought="Processing with context",
                final_answer="Done"
            )
            atom_agent.llm.generate_structured_response = AsyncMock(return_value=mock_response)

            context = {"user_id": "test-user", "additional": "data"}
            result = await atom_agent.execute("Test", context=context)

            assert result["final_output"] == "Done"

    @pytest.mark.asyncio
    async def test_execute_with_different_trigger_modes(self, atom_agent):
        """Test execution with different trigger modes"""
        with patch('core.atom_meta_agent.get_db_session'), \
             patch('core.atom_meta_agent.AgentGovernanceService'):

            from core.react_models import ReActStep

            mock_response = ReActStep(
                thought="Test",
                final_answer="Result"
            )
            atom_agent.llm.generate_structured_response = AsyncMock(return_value=mock_response)

            # Test MANUAL trigger
            result = await atom_agent.execute(
                "Test",
                trigger_mode=AgentTriggerMode.MANUAL
            )
            assert result["status"] == "success"

            # Test DATA_EVENT trigger
            result = await atom_agent.execute(
                "Test",
                trigger_mode=AgentTriggerMode.DATA_EVENT
            )
            assert result["status"] == "success"

            # Test SCHEDULED trigger
            result = await atom_agent.execute(
                "Test",
                trigger_mode=AgentTriggerMode.SCHEDULED
            )
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_with_custom_execution_id(self, atom_agent):
        """Test execution with custom execution ID"""
        with patch('core.atom_meta_agent.get_db_session'), \
             patch('core.atom_meta_agent.AgentGovernanceService'):

            from core.react_models import ReActStep

            mock_response = ReActStep(
                thought="Test",
                final_answer="Result"
            )
            atom_agent.llm.generate_structured_response = AsyncMock(return_value=mock_response)

            custom_id = "custom-execution-123"
            result = await atom_agent.execute("Test", execution_id=custom_id)

            assert result["status"] == "success"


# =============================================================================
# TEST CLASS: TestAtomMetaAgentOrchestration
# Tests for orchestration methods
# =============================================================================

class TestAtomMetaAgentOrchestration:
    """Test AtomMetaAgent orchestration and delegation"""

    @pytest.mark.asyncio
    async def test_react_step_generation(self, atom_agent):
        """Test ReAct step generation"""
        from core.react_models import ReActStep

        mock_step = ReActStep(
            thought="I need to search for information",
            action=None,
            final_answer="Not enough info"
        )
        atom_agent.llm.generate_structured_response = AsyncMock(return_value=mock_step)

        result = await atom_agent._react_step(
            request="Find information",
            memory_context={},
            tool_descriptions="Tool descriptions",
            execution_history="",
            context={}
        )

        assert result.thought == "I need to search for information"
        assert result.final_answer == "Not enough info"

    @pytest.mark.asyncio
    async def test_execute_delegation_success(self, atom_agent):
        """Test successful task delegation"""
        # Mock the business_agents module at import location
        with patch('core.business_agents.get_specialized_agent') as mock_get_agent:
            # Mock specialized agent
            mock_specialized = MagicMock()
            mock_specialized.name = "accounting"
            mock_specialized.execute = AsyncMock(return_value={
                "final_output": "Accounting task completed"
            })
            mock_get_agent.return_value = mock_specialized

            result = await atom_agent._execute_delegation(
                agent_name="accounting",
                task="Reconcile accounts",
                context={}
            )

            assert "Accounting task completed" in result
            assert mock_specialized.execute.called

    @pytest.mark.asyncio
    async def test_execute_delegation_agent_not_found(self, atom_agent):
        """Test delegation when agent is not found"""
        with patch('core.business_agents.get_specialized_agent', return_value=None):
            result = await atom_agent._execute_delegation(
                agent_name="unknown",
                task="Do something",
                context={}
            )

            assert "not found" in result
            assert "Available agents" in result

    @pytest.mark.asyncio
    async def test_query_memory_experiences(self, atom_agent):
        """Test querying memory for experiences"""
        mock_experiences = [
            MagicMock(input_summary="Task 1", outcome="completed"),
            MagicMock(input_summary="Task 2", outcome="failed")
        ]
        atom_agent.world_model.recall_experiences = AsyncMock(return_value={
            "experiences": mock_experiences,
            "knowledge": [],
            "formulas": [],
            "business_facts": []
        })

        result = await atom_agent.query_memory("test query", scope="experiences")

        assert "experiences" in result
        assert len(result["experiences"]) == 2

    @pytest.mark.asyncio
    async def test_query_memory_all(self, atom_agent):
        """Test querying memory for all data"""
        atom_agent.world_model.recall_experiences = AsyncMock(return_value={
            "experiences": [MagicMock()],
            "knowledge": [{"text": "Knowledge item"}],
            "formulas": [{"name": "Formula 1"}],
            "business_facts": []
        })

        result = await atom_agent.query_memory("test query", scope="all")

        assert "experiences" in result
        assert "knowledge" in result
        assert "formulas" in result


# =============================================================================
# TEST CLASS: TestAtomMetaAgentErrorHandling
# Tests for error handling scenarios
# =============================================================================

class TestAtomMetaAgentErrorHandling:
    """Test AtomMetaAgent error handling"""

    @pytest.mark.asyncio
    async def test_execute_with_llm_unavailable(self, atom_agent):
        """Test execution when LLM is unavailable"""
        with patch('core.atom_meta_agent.get_db_session'), \
             patch('core.atom_meta_agent.AgentGovernanceService'):

            from core.react_models import ReActStep

            # Mock LLM to return error response
            error_response = ReActStep(
                thought="System encountered an issue",
                final_answer="Unable to process request - AI provider unavailable"
            )
            atom_agent.llm.generate_structured_response = AsyncMock(return_value=error_response)
            atom_agent.llm.generate_response = AsyncMock(return_value="Service not initialized")

            result = await atom_agent.execute("Test")

            assert "Unable to process request" in result["final_output"]

    @pytest.mark.asyncio
    async def test_spawn_agent_from_template(self, atom_agent):
        """Test spawning agent from predefined template"""
        with patch('core.atom_meta_agent.AgentGovernanceService'):
            agent = await atom_agent.spawn_agent(
                template_name="finance_analyst",
                persist=False
            )

            assert agent is not None
            assert agent.name == "Finance Analyst"
            assert agent.category == "Finance"
            assert agent.status == AgentStatus.STUDENT.value
            assert agent.confidence_score == 0.5

    @pytest.mark.asyncio
    async def test_spawn_agent_unknown_template(self, atom_agent):
        """Test spawning agent with unknown template raises error"""
        with pytest.raises(ValueError, match="Unknown agent template"):
            await atom_agent.spawn_agent("unknown_template")

    @pytest.mark.asyncio
    async def test_spawn_agent_custom_params(self, atom_agent):
        """Test spawning agent with custom parameters"""
        custom_params = {
            "name": "Custom Agent",
            "category": "Custom",
            "description": "A custom agent",
            "capabilities": ["custom_capability"]
        }

        agent = await atom_agent.spawn_agent(
            template_name="custom",
            custom_params=custom_params,
            persist=False
        )

        assert agent.name == "Custom Agent"
        assert agent.category == "Custom"

    @pytest.mark.asyncio
    async def test_get_atom_registry(self, atom_agent):
        """Test _get_atom_registry returns proper AgentRegistry"""
        registry = atom_agent._get_atom_registry()

        assert isinstance(registry, AgentRegistry)
        assert registry.id == "atom_main"
        assert registry.name == "Atom"
        assert registry.category == "Meta"
        assert registry.status == AgentStatus.AUTONOMOUS.value
        assert registry.confidence_score == 1.0


# =============================================================================
# TEST CLASS: TestCommunicationInstruction
# Tests for communication style handling
# =============================================================================

class TestCommunicationInstruction:
    """Test communication style instruction generation"""

    def test_get_communication_instruction_no_user(self, atom_agent):
        """Test communication instruction when no user provided"""
        result = atom_agent._get_communication_instruction({})

        assert result == ""

    def test_get_communication_instruction_no_user_id(self, atom_agent):
        """Test communication instruction when user_id is not in context"""
        result = atom_agent._get_communication_instruction({"other_key": "value"})

        assert result == ""

    def test_get_communication_instruction_with_user(self, atom_agent, mock_user):
        """Test communication instruction when user is set on agent"""
        # Create user with communication style
        user_with_style = MagicMock(spec=User)
        user_with_style.id = "test-user-123"
        user_with_style.metadata_json = {
            "communication_style": {
                "enable_personalization": True,
                "style_guide": "Be concise and professional"
            }
        }
        atom_agent.user = user_with_style

        # Mock the database session
        with patch('core.atom_meta_agent.get_db_session') as mock_db:
            mock_db_session = MagicMock()
            mock_query = MagicMock()
            mock_query.first.return_value = user_with_style
            mock_db_session.query.return_value.filter.return_value = mock_query
            mock_db.return_value.__enter__.return_value = mock_db_session

            result = atom_agent._get_communication_instruction({})

        assert "COMMUNICATION STYLE" in result
        assert "Be concise and professional" in result

    def test_get_communication_instruction_disabled(self, atom_agent, mock_user):
        """Test communication instruction when personalization is disabled"""
        mock_user.metadata_json = {
            "communication_style": {"enable_personalization": False}
        }
        atom_agent.user = mock_user

        result = atom_agent._get_communication_instruction({})

        assert result == ""


# =============================================================================
# TEST CLASS: TestAgentTriggerMode
# Tests for AgentTriggerMode enum
# =============================================================================

class TestAgentTriggerMode:
    """Test AgentTriggerMode enum values"""

    def test_trigger_mode_manual(self):
        """Test MANUAL trigger mode"""
        assert AgentTriggerMode.MANUAL.value == "manual"

    def test_trigger_mode_data_event(self):
        """Test DATA_EVENT trigger mode"""
        assert AgentTriggerMode.DATA_EVENT.value == "data_event"

    def test_trigger_mode_scheduled(self):
        """Test SCHEDULED trigger mode"""
        assert AgentTriggerMode.SCHEDULED.value == "scheduled"

    def test_trigger_mode_workflow(self):
        """Test WORKFLOW trigger mode"""
        assert AgentTriggerMode.WORKFLOW.value == "workflow"
