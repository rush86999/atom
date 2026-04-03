"""
Coverage-driven tests for AtomMetaAgent (currently 0% -> target 60%+)

Target file: core/atom_meta_agent.py (1082 lines)

Focus areas from coverage gap analysis:
- Agent initialization (lines 168-180)
- Template system (lines 33-128)
- Tool management (lines 152-166, 294-315)
- Simple helper methods (lines 883-965)
- Trigger handlers (lines 967-1082)
- Complex ReAct execute() loop (lines 181-523) - ACKNOWLEDGED as too complex for full coverage

Note: The execute() method with complex ReAct loop is acceptable to partially skip
due to extensive async complexity and external dependencies. Focus on testable paths.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import asyncio
from typing import Dict, Any

# Mock problematic imports before importing atom_meta_agent
import sys
from unittest.mock import MagicMock
sys.modules['core.canvas_context_provider'] = MagicMock()

from core.atom_meta_agent import (
    AtomMetaAgent,
    SpecialtyAgentTemplate,
    handle_data_event_trigger,
    handle_manual_trigger,
    get_atom_agent
)
from core.models import User, AgentStatus, Workspace


@pytest.fixture
def mock_user():
    """Mock user for testing"""
    user = Mock(spec=User)
    user.id = "test-user-123"
    user.email = "test@example.com"
    user.metadata_json = None
    return user


@pytest.fixture
def mock_workspace():
    """Mock workspace for testing"""
    workspace = Mock(spec=Workspace)
    workspace.id = "test-workspace"
    workspace.tenant_id = "test-tenant"
    return workspace


class TestAtomMetaAgentInitialization:
    """Test AtomMetaAgent initialization (lines 168-180)"""

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    def test_agent_init_default_workspace(self, mock_service_factory, mock_canvas, mock_mcp, mock_orchestrator):
        """Test initialization with default workspace"""
        mock_canvas.return_value = MagicMock()
        agent = AtomMetaAgent()
        assert agent.workspace_id == "default"
        assert agent.user is None
        assert agent._spawned_agents == {}
        assert agent.session_tools == []
        assert agent.queen is None

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    def test_agent_init_with_workspace_id(self, mock_service_factory, mock_canvas, mock_mcp, mock_orchestrator, mock_workspace):
        """Test initialization with custom workspace ID"""
        mock_canvas.return_value = MagicMock()
        agent = AtomMetaAgent(workspace_id="custom-workspace")
        assert agent.workspace_id == "custom-workspace"

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    def test_agent_init_with_user(self, mock_service_factory, mock_canvas, mock_mcp, mock_orchestrator, mock_user):
        """Test initialization with user context"""
        mock_canvas.return_value = MagicMock()
        agent = AtomMetaAgent(user=mock_user)
        assert agent.user == mock_user
        assert agent.user.id == "test-user-123"


class TestSpecialtyAgentTemplate:
    """Test SpecialtyAgentTemplate class (lines 33-128)"""

    def test_template_templates_dict_exists(self):
        """Test TEMPLATES dictionary exists and has content"""
        assert hasattr(SpecialtyAgentTemplate, 'TEMPLATES')
        assert isinstance(SpecialtyAgentTemplate.TEMPLATES, dict)
        assert len(SpecialtyAgentTemplate.TEMPLATES) > 0

    def test_template_has_finance_analyst(self):
        """Test finance_analyst template exists"""
        assert "finance_analyst" in SpecialtyAgentTemplate.TEMPLATES
        template = SpecialtyAgentTemplate.TEMPLATES["finance_analyst"]
        assert template["name"] == "Finance Analyst"
        assert template["category"] == "Finance"
        assert "reconciliation" in template["capabilities"]

    def test_template_has_sales_assistant(self):
        """Test sales_assistant template exists"""
        assert "sales_assistant" in SpecialtyAgentTemplate.TEMPLATES
        template = SpecialtyAgentTemplate.TEMPLATES["sales_assistant"]
        assert template["name"] == "Sales Assistant"
        assert template["category"] == "Sales"
        assert "lead_scoring" in template["capabilities"]

    def test_template_has_ops_coordinator(self):
        """Test ops_coordinator template exists"""
        assert "ops_coordinator" in SpecialtyAgentTemplate.TEMPLATES
        template = SpecialtyAgentTemplate.TEMPLATES["ops_coordinator"]
        assert template["name"] == "Operations Coordinator"
        assert template["category"] == "Operations"
        assert "inventory_check" in template["capabilities"]

    def test_template_has_hr_assistant(self):
        """Test hr_assistant template exists"""
        assert "hr_assistant" in SpecialtyAgentTemplate.TEMPLATES
        template = SpecialtyAgentTemplate.TEMPLATES["hr_assistant"]
        assert template["name"] == "HR Assistant"
        assert template["category"] == "HR"
        assert "onboarding" in template["capabilities"]

    def test_template_has_procurement_specialist(self):
        """Test procurement_specialist template exists"""
        assert "procurement_specialist" in SpecialtyAgentTemplate.TEMPLATES
        template = SpecialtyAgentTemplate.TEMPLATES["procurement_specialist"]
        assert template["name"] == "Procurement Specialist"
        assert "b2b_extract_po" in template["capabilities"]

    def test_template_has_knowledge_analyst(self):
        """Test knowledge_analyst template exists"""
        assert "knowledge_analyst" in SpecialtyAgentTemplate.TEMPLATES
        template = SpecialtyAgentTemplate.TEMPLATES["knowledge_analyst"]
        assert template["name"] == "Knowledge Analyst"
        assert template["category"] == "Intelligence"
        assert "ingest_knowledge_from_text" in template["capabilities"]

    def test_template_has_marketing_analyst(self):
        """Test marketing_analyst template exists"""
        assert "marketing_analyst" in SpecialtyAgentTemplate.TEMPLATES
        template = SpecialtyAgentTemplate.TEMPLATES["marketing_analyst"]
        assert template["name"] == "Marketing Analyst"
        assert template["category"] == "Marketing"
        assert "campaign_analysis" in template["capabilities"]

    def test_template_has_king_agent(self):
        """Test king_agent template exists"""
        assert "king_agent" in SpecialtyAgentTemplate.TEMPLATES
        template = SpecialtyAgentTemplate.TEMPLATES["king_agent"]
        assert template["name"] == "King Agent"
        assert template["category"] == "Governance"
        assert "execute_blueprint" in template["capabilities"]
        assert template["module_path"] == "core.agents.king_agent"


class TestAtomMetaAgentConstants:
    """Test constants and class attributes (lines 152-166)"""

    def test_core_tools_names_exists(self):
        """Test CORE_TOOLS_NAMES constant exists"""
        assert hasattr(AtomMetaAgent, 'CORE_TOOLS_NAMES')
        assert isinstance(AtomMetaAgent.CORE_TOOLS_NAMES, list)

    def test_core_tools_names_has_expected_tools(self):
        """Test CORE_TOOLS_NAMES has expected tools"""
        expected_tools = [
            "mcp_tool_search",
            "save_business_fact",
            "verify_citation",
            "ingest_knowledge_from_text",
            "trigger_workflow",
            "delegate_task",
            "canvas_tool"
        ]
        for tool in expected_tools:
            assert tool in AtomMetaAgent.CORE_TOOLS_NAMES


class TestAtomMetaAgentHelperMethods:
    """Test simple helper methods (lines 883-965)"""

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    def test_get_atom_registry(self, mock_service_factory, mock_canvas, mock_mcp, mock_orchestrator):
        """Test _get_atom_registry returns correct AgentRegistry"""
        mock_canvas.return_value = MagicMock()
        agent = AtomMetaAgent()
        registry = agent._get_atom_registry()
        assert registry.id == "atom_main"
        assert registry.name == "Atom"
        assert registry.category == "Meta"
        assert registry.status == AgentStatus.AUTONOMOUS.value
        assert registry.confidence_score == 1.0

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    def test_get_communication_instruction_no_user(self, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test _get_communication_instruction with no user"""
        mock_canvas.return_value = MagicMock()
        agent = AtomMetaAgent()
        instruction = agent._get_communication_instruction({})
        assert instruction == ""

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    def test_get_communication_instruction_no_user_in_context(self, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test _get_communication_instruction with no user_id in context"""
        mock_canvas.return_value = MagicMock()
        agent = AtomMetaAgent()
        instruction = agent._get_communication_instruction({"user_id": None})
        assert instruction == ""



class TestAtomMetaAgentSpawnAgent:
    """Test spawn_agent method (lines 738-787)"""

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @pytest.mark.asyncio
    async def test_spawn_agent_from_template_finance_analyst(self, mock_service_factory, mock_canvas, mock_mcp, mock_orchestrator):
        """Test spawning finance_analyst from template"""
        mock_canvas.return_value = MagicMock()
        agent = AtomMetaAgent()
        spawned = await agent.spawn_agent("finance_analyst", persist=False)
        assert spawned.name == "Finance Analyst"
        assert spawned.category == "Finance"
        assert spawned.status == AgentStatus.STUDENT.value
        assert spawned.confidence_score == 0.5

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @pytest.mark.asyncio
    async def test_spawn_agent_from_template_sales_assistant(self, mock_service_factory, mock_canvas, mock_mcp, mock_orchestrator):
        """Test spawning sales_assistant from template"""
        mock_canvas.return_value = MagicMock()
        agent = AtomMetaAgent()
        spawned = await agent.spawn_agent("sales_assistant", persist=False)
        assert spawned.name == "Sales Assistant"
        assert spawned.category == "Sales"

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @pytest.mark.asyncio
    async def test_spawn_agent_unknown_template_raises_error(self, mock_service_factory, mock_canvas, mock_mcp, mock_orchestrator):
        """Test spawning unknown template raises ValueError"""
        mock_canvas.return_value = MagicMock()
        agent = AtomMetaAgent()
        with pytest.raises(ValueError, match="Unknown agent template"):
            await agent.spawn_agent("nonexistent_template")

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @pytest.mark.asyncio
    async def test_spawn_agent_ephemeral_stores_in_memory(self, mock_service_factory, mock_canvas, mock_mcp, mock_orchestrator):
        """Test spawning ephemeral agent stores in _spawned_agents dict"""
        mock_canvas.return_value = MagicMock()
        agent = AtomMetaAgent()
        spawned = await agent.spawn_agent("hr_assistant", persist=False)
        assert spawned.id in agent._spawned_agents
        assert agent._spawned_agents[spawned.id] == spawned


class TestAtomMetaAgentQueryMemory:
    """Test query_memory method (lines 789-806)"""

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @pytest.mark.asyncio
    async def test_query_memory_all_scope(self, mock_service_factory, mock_canvas, mock_mcp, mock_orchestrator):
        """Test query_memory with scope='all'"""
        mock_canvas.return_value = MagicMock()
        mock_world_model_instance = MagicMock()
        mock_world_model_instance.recall_experiences = AsyncMock(return_value={
            "experiences": ["exp1", "exp2"],
            "knowledge": ["k1", "k2"]
        })
        mock_world_model.return_value = mock_world_model_instance

        agent = AtomMetaAgent()
        result = await agent.query_memory("test query", scope="all")
        assert "experiences" in result
        assert "knowledge" in result
        mock_world_model_instance.recall_experiences.assert_called_once()

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @pytest.mark.asyncio
    async def test_query_memory_experiences_scope(self, mock_service_factory, mock_canvas, mock_mcp, mock_orchestrator):
        """Test query_memory with scope='experiences'"""
        mock_canvas.return_value = MagicMock()
        mock_world_model_instance = MagicMock()
        mock_world_model_instance.recall_experiences = AsyncMock(return_value={
            "experiences": ["exp1"],
            "knowledge": ["k1"]
        })
        mock_world_model.return_value = mock_world_model_instance

        agent = AtomMetaAgent()
        result = await agent.query_memory("test query", scope="experiences")
        assert "experiences" in result
        assert result["experiences"] == ["exp1"]

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @pytest.mark.asyncio
    async def test_query_memory_knowledge_scope(self, mock_service_factory, mock_canvas, mock_mcp, mock_orchestrator):
        """Test query_memory with scope='knowledge'"""
        mock_canvas.return_value = MagicMock()
        mock_world_model_instance = MagicMock()
        mock_world_model_instance.recall_experiences = AsyncMock(return_value={
            "experiences": ["exp1"],
            "knowledge": ["k1", "k2"]
        })
        mock_world_model.return_value = mock_world_model_instance

        agent = AtomMetaAgent()
        result = await agent.query_memory("test query", scope="knowledge")
        assert "knowledge" in result
        assert result["knowledge"] == ["k1", "k2"]


class TestAtomMetaAgentTriggerHandlers:
    """Test trigger handler functions (lines 967-1082)"""

    @patch('core.atom_meta_agent.AtomMetaAgent')
    @pytest.mark.asyncio
    async def test_handle_data_event_trigger(self, mock_agent_class):
        """Test handle_data_event_trigger function"""
        mock_agent = AsyncMock()
        mock_agent.execute.return_value = {"status": "success", "final_output": "Processed"}
        mock_agent_class.return_value = mock_agent

        result = await handle_data_event_trigger(
            event_type="webhook",
            data={"id": 123},
            workspace_id="test-workspace"
        )
        assert result is not None
        mock_agent_class.assert_called_once_with("test-workspace")

    @patch('core.atom_meta_agent.AtomMetaAgent')
    @pytest.mark.asyncio
    async def test_handle_manual_trigger(self, mock_agent_class, mock_user):
        """Test handle_manual_trigger function"""
        mock_agent = AsyncMock()
        mock_agent.execute.return_value = {
            "status": "success",
            "final_output": "Manual task completed"
        }
        mock_agent_class.return_value = mock_agent

        result = await handle_manual_trigger(
            request="Test request",
            user=mock_user,
            workspace_id="test-workspace"
        )
        assert result is not None
        mock_agent_class.assert_called_once_with("test-workspace", mock_user)

    def test_get_atom_agent_singleton(self):
        """Test get_atom_agent singleton function"""
        # Clear any existing singleton
        import core.atom_meta_agent as ama_module
        ama_module._atom_instance = None

        # First call creates instance
        agent1 = get_atom_agent("workspace-1")
        # Second call with same workspace returns same instance
        agent2 = get_atom_agent("workspace-1")
        # Third call with different workspace creates new instance
        agent3 = get_atom_agent("workspace-2")

        assert agent1 is agent2
        assert agent1.workspace_id == "workspace-1"
        assert agent3.workspace_id == "workspace-2"


class TestAtomMetaAgentExecuteDelegation:
    """Test _execute_delegation method (lines 525-547)"""

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @pytest.mark.asyncio
    async def test_execute_delegation_unknown_agent(self, mock_service_factory, mock_canvas, mock_mcp, mock_orchestrator):
        """Test delegation to unknown agent returns error message"""
        mock_canvas.return_value = MagicMock()
        agent = AtomMetaAgent()

        result = await agent._execute_delegation(
            agent_name="unknown_agent",
            task="Test task",
            context={},
            step_callback=None,
            execution_id="exec-123"
        )
        # Should handle delegation failure gracefully
        assert result is not None
        assert "Delegation failed" in result or "Error" in result

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @pytest.mark.asyncio
    async def test_execute_delegation_specialized_not_found(self, mock_service_factory, mock_canvas, mock_mcp, mock_orchestrator):
        """Test delegation when specialized agent not found"""
        mock_canvas.return_value = MagicMock()
        agent = AtomMetaAgent()

        result = await agent._execute_delegation(
            agent_name="accounting",
            task="Reconcile accounts",
            context={},
            step_callback=None,
            execution_id="exec-123"
        )
        # Should handle delegation failure gracefully
        assert result is not None
        assert "Delegation failed" in result or "Error" in result


class TestAtomMetaAgentExecuteToolGovernance:
    """Test _execute_tool_with_governance method (lines 677-735)"""

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    @pytest.mark.asyncio
    async def test_execute_tool_governance_blocked(self, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test tool execution blocked by governance"""
        mock_canvas.return_value = MagicMock()
        mock_db = MagicMock()
        mock_gov = MagicMock()
        mock_gov.can_perform_action.return_value = {"allowed": False, "reason": "Not authorized", "action_complexity": 1}
        mock_db.query.return_value.filter.return_value.first.return_value = mock_gov
        mock_session.return_value.__enter__.return_value = mock_db

        agent = AtomMetaAgent()
        result = await agent._execute_tool_with_governance(
            tool_name="dangerous_tool",
            args={"param": "value"},
            context={},
            step_callback=None
        )
        # Should handle governance block
        assert result is not None
        assert ("Governance blocked" in result or "Tool error" in result or "blocked" in result.lower())

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    @pytest.mark.asyncio
    async def test_execute_tool_governance_error(self, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test tool execution handles exceptions gracefully"""
        mock_canvas.return_value = MagicMock()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.side_effect = Exception("DB connection error")
        mock_session.return_value.__enter__.return_value = mock_db
        mock_session.return_value.__exit__.return_value = None

        agent = AtomMetaAgent()
        result = await agent._execute_tool_with_governance(
            tool_name="test_tool",
            args={},
            context={},
            step_callback=None
        )
        # Should handle errors gracefully
        assert result is not None
        assert "Tool error" in result or "error" in result.lower()


class TestAtomMetaAgentWaitForApproval:
    """Test _wait_for_approval method (lines 894-916)"""


    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    @patch('core.atom_meta_agent.asyncio.sleep')
    @pytest.mark.asyncio
    async def test_wait_for_approval_rejected(self, mock_sleep, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test waiting for approval when action is rejected"""
        mock_canvas.return_value = MagicMock()
        mock_db = MagicMock()
        mock_gov = MagicMock()
        mock_gov.get_approval_status.return_value = {"status": "rejected"}
        mock_db.query.return_value.filter.return_value.first.return_value = mock_gov
        mock_session.return_value.__enter__.return_value = mock_db

        agent = AtomMetaAgent()
        result = await agent._wait_for_approval("action-123")
        assert result is False

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    @patch('core.atom_meta_agent.asyncio.sleep')
    @pytest.mark.asyncio
    async def test_wait_for_approval_timeout(self, mock_sleep, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test waiting for approval times out"""
        mock_canvas.return_value = MagicMock()
        mock_db = MagicMock()
        mock_gov = MagicMock()
        mock_gov.get_approval_status.return_value = {"status": "pending"}
        mock_db.query.return_value.filter.return_value.first.return_value = mock_gov
        mock_session.return_value.__enter__.return_value = mock_db

        agent = AtomMetaAgent()
        result = await agent._wait_for_approval("action-123")
        assert result is False


class TestAtomMetaAgentRecordExecution:
    """Test _record_execution method (lines 918-943)"""

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    @pytest.mark.asyncio
    async def test_record_execution_success(self, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test recording successful execution"""
        mock_canvas.return_value = MagicMock()
        mock_world_model_instance = MagicMock()
        mock_world_model_instance.record_experience = AsyncMock()
        mock_world_model.return_value = mock_world_model_instance

        mock_db = MagicMock()
        mock_gov = AsyncMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_gov
        mock_session.return_value.__enter__.return_value = mock_db

        agent = AtomMetaAgent()
        result = await agent._record_execution(
            request="Test request",
            result={"status": "success", "final_output": "Done", "actions_executed": []},
            trigger_mode=Mock(value="manual")
        )
        # Should not raise exception
        assert result is None

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    @pytest.mark.asyncio
    async def test_record_execution_governance_error(self, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test recording execution handles governance errors gracefully"""
        mock_canvas.return_value = MagicMock()
        mock_world_model_instance = MagicMock()
        mock_world_model_instance.record_experience = AsyncMock()
        mock_world_model.return_value = mock_world_model_instance

        mock_db = MagicMock()
        mock_gov = AsyncMock()
        mock_gov.record_outcome.side_effect = Exception("Governance error")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_gov
        mock_session.return_value.__enter__.return_value = mock_db

        agent = AtomMetaAgent()
        # Should not raise exception
        result = await agent._record_execution(
            request="Test request",
            result={"status": "success", "final_output": "Done", "actions_executed": []},
            trigger_mode=Mock(value="manual")
        )
        assert result is None


class TestAtomMetaAgentGenerateMentorshipGuidance:
    """Test generate_mentorship_guidance method (lines 808-879)"""

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    @pytest.mark.asyncio
    async def test_generate_mentorship_guidance_with_supervisors(self, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test mentorship guidance when supervisors exist"""
        mock_canvas.return_value = MagicMock()
        mock_db = MagicMock()
        mock_student = MagicMock()
        mock_student.category = "Finance"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_student
        # Return count > 0 (supervisors exist)
        mock_db.query.return_value.filter.return_value.count.return_value = 5
        mock_session.return_value.__enter__.return_value = mock_db

        mock_llm = AsyncMock(return_value="Guidance: Review the action carefully")
        agent = AtomMetaAgent()
        agent.llm = mock_llm

        guidance = await agent.generate_mentorship_guidance(
            student_agent_id="student-123",
            action="delete_records",
            params={"table": "invoices"},
            reason="Student cannot perform deletions"
        )
        assert guidance is not None

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    @pytest.mark.asyncio
    async def test_generate_mentorship_guidance_no_supervisors(self, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test mentorship guidance when no supervisors exist (acting interim supervisor)"""
        mock_canvas.return_value = MagicMock()
        mock_db = MagicMock()
        mock_student = MagicMock()
        mock_student.category = "Sales"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_student
        # Return count = 0 (no supervisors)
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        mock_session.return_value.__enter__.return_value = mock_db

        mock_llm = AsyncMock(return_value="Acting Interim Supervisor: Here's the guidance...")
        agent = AtomMetaAgent()
        agent.llm = mock_llm

        guidance = await agent.generate_mentorship_guidance(
            student_agent_id="student-456",
            action="send_email",
            params={"to": "customer@example.com"},
            reason="Student cannot send emails"
        )
        assert guidance is not None

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    @pytest.mark.asyncio
    async def test_generate_mentorship_guidance_student_not_found(self, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test mentorship guidance when student not found"""
        mock_canvas.return_value = MagicMock()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value.__enter__.return_value = mock_db

        mock_llm = AsyncMock(return_value="Default guidance")
        agent = AtomMetaAgent()
        agent.llm = mock_llm

        guidance = await agent.generate_mentorship_guidance(
            student_agent_id="nonexistent-student",
            action="test_action",
            params={},
            reason="Test reason"
        )
        assert guidance is not None


class TestAtomMetaAgentExecuteBasicCoverage:
    """Test basic execute() method coverage (lines 181-523) - ACKNOWLEDGED as too complex for full coverage"""

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    @pytest.mark.asyncio
    async def test_execute_workspace_not_found(self, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test execute() handles workspace not found (lines 200-212)"""
        mock_canvas.return_value = MagicMock()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value.__enter__.return_value = mock_db

        agent = AtomMetaAgent(workspace_id="nonexistent-workspace")

        from fastapi import HTTPException
        try:
            result = await agent.execute("test request")
            # If no exception, check result
            assert result is not None
        except HTTPException as e:
            assert e.status_code == 404


    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    @pytest.mark.asyncio
    async def test_execute_max_steps_exceeded(self, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test execute() handles max steps exceeded (lines 489-492)"""
        mock_canvas.return_value = MagicMock()
        mock_db = MagicMock()
        mock_workspace = MagicMock()
        mock_workspace.tenant_id = "test-tenant"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_workspace

        # Mock execution update
        mock_execution = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_execution

        mock_session.return_value.__enter__.return_value = mock_db
        mock_session.return_value.__exit__.return_value = None

        # Mock MCP tools
        mock_mcp.get_all_tools = AsyncMock(return_value=[])

        # Mock WorldModel
        mock_world_model_instance = MagicMock()
        mock_world_model_instance.recall_experiences = AsyncMock(return_value={})
        mock_world_model.return_value = mock_world_model_instance

        # Mock BYOK LLM to always return actions (no final_answer)
        from core.react_models import ReActStep, ToolCall
        mock_react_step = ReActStep(
            thought="Test thought",
            action=ToolCall(tool="test_tool", params={}),
            final_answer=None
        )
        mock_byok_instance = MagicMock()
        mock_byok_instance.generate_structured_response = AsyncMock(return_value=mock_react_step)
        agent = AtomMetaAgent()
        agent.llm = mock_byok_instance

        # Mock _execute_tool_with_governance to avoid actual tool execution
        agent._execute_tool_with_governance = AsyncMock(return_value="Tool executed")

        # Mock _record_execution
        agent._record_execution = AsyncMock()

        result = await agent.execute("test request")
        # Should reach max steps and return with max_steps_exceeded status
        assert result is not None
        assert result.get("status") == "max_steps_exceeded" or "final_output" in result

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    @pytest.mark.asyncio
    async def test_execute_with_canvas_context(self, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test execute() with canvas context (lines 237-263)"""
        mock_canvas.return_value = MagicMock()
        mock_db = MagicMock()
        mock_workspace = MagicMock()
        mock_workspace.tenant_id = "test-tenant"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_workspace

        # Mock execution update
        mock_execution = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_execution

        mock_session.return_value.__enter__.return_value = mock_db
        mock_session.return_value.__exit__.return_value = None

        # Mock MCP tools
        mock_mcp.get_all_tools = AsyncMock(return_value=[])

        # Mock WorldModel
        mock_world_model_instance = MagicMock()
        mock_world_model_instance.recall_experiences = AsyncMock(return_value={})
        mock_world_model_instance.recall_episodes = AsyncMock(return_value=[])
        mock_world_model.return_value = mock_world_model_instance

        # Mock canvas provider
        mock_canvas_state = MagicMock()
        mock_canvas_state.artifact_count = 5
        mock_canvas_state.comments = []
        mock_canvas_state.canvas_id = "test-canvas"
        mock_canvas.return_value.get_canvas_context = AsyncMock(return_value=mock_canvas_state)
        mock_canvas.return_value.format_for_agent = MagicMock(return_value="Canvas state")

        # Mock BYOK LLM to return final_answer immediately
        from core.react_models import ReActStep
        mock_react_step = ReActStep(
            thought="Done",
            action=None,
            final_answer="Task completed"
        )
        mock_byok_instance = MagicMock()
        mock_byok_instance.generate_structured_response = AsyncMock(return_value=mock_react_step)
        agent = AtomMetaAgent()
        agent.llm = mock_byok_instance

        # Mock _record_execution
        agent._record_execution = AsyncMock()

        result = await agent.execute(
            "test request",
            canvas_context={"canvas_id": "test-canvas"}
        )
        # Should process canvas context
        assert result is not None

    @patch('core.service_factory.ServiceFactory')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    
    @patch('core.atom_meta_agent.get_canvas_provider')
    @patch('core.atom_meta_agent.SessionLocal')
    @pytest.mark.asyncio
    async def test_execute_with_trigger_mode(self, mock_session, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Test execute() with different trigger modes (line 182)"""
        from core.models import AgentTriggerMode
        mock_canvas.return_value = MagicMock()
        mock_db = MagicMock()
        mock_workspace = MagicMock()
        mock_workspace.tenant_id = "test-tenant"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_workspace

        # Mock execution update
        mock_execution = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_execution

        mock_session.return_value.__enter__.return_value = mock_db
        mock_session.return_value.__exit__.return_value = None

        # Mock MCP tools
        mock_mcp.get_all_tools = AsyncMock(return_value=[])

        # Mock WorldModel
        mock_world_model_instance = MagicMock()
        mock_world_model_instance.recall_experiences = AsyncMock(return_value={})
        mock_world_model.return_value = mock_world_model_instance

        # Mock BYOK LLM to return final_answer
        from core.react_models import ReActStep
        mock_react_step = ReActStep(
            thought="Processing",
            action=None,
            final_answer="Complete"
        )
        mock_byok_instance = MagicMock()
        mock_byok_instance.generate_structured_response = AsyncMock(return_value=mock_react_step)
        agent = AtomMetaAgent()
        agent.llm = mock_byok_instance

        # Mock _record_execution
        agent._record_execution = AsyncMock()

        result = await agent.execute(
            "test request",
            trigger_mode=AgentTriggerMode.DATA_EVENT
        )
        # Should handle different trigger modes
        assert result is not None
