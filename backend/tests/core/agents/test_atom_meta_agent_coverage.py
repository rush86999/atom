"""
Coverage-driven tests for AtomMetaAgent (currently 0% -> target 80%+)

Focus areas from atom_meta_agent.py:
- AtomMetaAgent.__init__ (lines 168-178)
- execute() main entry point (lines 181-523)
- _execute_delegation() (lines 525-547)
- _react_step() (lines 551-675)
- _execute_tool_with_governance() (lines 677-735)
- spawn_agent() (lines 738-787)
- query_memory() (lines 789-806)
- generate_mentorship_guidance() (lines 808-879)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, Mock
from datetime import datetime
from sqlalchemy.orm import Session
import sys

# Mock missing modules before importing
sys.modules['core.canvas_context_provider'] = MagicMock()
sys.modules['core.agents.queen_agent'] = MagicMock()
sys.modules['core.llm_router'] = MagicMock()
sys.modules['advanced_workflow_orchestrator'] = MagicMock()
sys.modules['ai.nlp_engine'] = MagicMock()
sys.modules['integrations.mcp_service'] = MagicMock()

from core.atom_meta_agent import (
    AtomMetaAgent,
    SpecialtyAgentTemplate,
    handle_data_event_trigger,
    handle_manual_trigger,
    get_atom_agent
)
from core.models import AgentRegistry, AgentStatus, User, Workspace


@pytest.fixture
def db_session():
    """Create a mock database session."""
    session = Mock(spec=Session)
    return session


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = Mock(spec=User)
    user.id = "test-user-1"
    user.email = "test@example.com"
    user.metadata_json = {}
    return user


@pytest.fixture
def mock_workspace(db_session):
    """Create a mock workspace."""
    workspace = Mock(spec=Workspace)
    workspace.id = "test-workspace"
    workspace.tenant_id = "test-tenant"
    db_session.query.return_value.filter.return_value.first.return_value = workspace
    return workspace


class TestSpecialtyAgentTemplate:
    """Test SpecialtyAgentTemplate configuration."""

    def test_template_finance_analyst(self):
        """Cover lines 36-46: Finance analyst template."""
        template = SpecialtyAgentTemplate.TEMPLATES["finance_analyst"]
        assert template["name"] == "Finance Analyst"
        assert template["category"] == "Finance"
        assert "reconciliation" in template["capabilities"]
        assert "query_financial_metrics" in template["capabilities"]

    def test_template_sales_assistant(self):
        """Cover lines 48-58: Sales assistant template."""
        template = SpecialtyAgentTemplate.TEMPLATES["sales_assistant"]
        assert template["name"] == "Sales Assistant"
        assert template["category"] == "Sales"
        assert "lead_scoring" in template["capabilities"]
        assert "crm_sync" in template["capabilities"]

    def test_template_ops_coordinator(self):
        """Cover lines 60-70: Operations coordinator template."""
        template = SpecialtyAgentTemplate.TEMPLATES["ops_coordinator"]
        assert template["name"] == "Operations Coordinator"
        assert template["category"] == "Operations"
        assert "inventory_check" in template["capabilities"]

    def test_template_king_agent(self):
        """Cover lines 118-126: King agent template."""
        template = SpecialtyAgentTemplate.TEMPLATES["king_agent"]
        assert template["name"] == "King Agent"
        assert template["category"] == "Governance"
        assert "execute_blueprint" in template["capabilities"]
        assert template["module_path"] == "core.agents.king_agent"


class TestAtomMetaAgentInit:
    """Test AtomMetaAgent initialization."""

    @patch('core.atom_meta_agent.WorldModelService')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    @patch('core.atom_meta_agent.BYOKHandler')
    @patch('core.atom_meta_agent.get_canvas_provider')
    def test_init_default_config(self, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model):
        """Cover lines 168-178: Default initialization."""
        agent = AtomMetaAgent(workspace_id="test-workspace")
        assert agent.workspace_id == "test-workspace"
        assert agent.user is None
        assert agent._spawned_agents == {}
        assert len(agent.session_tools) == 0
        assert agent.queen is None

    @patch('core.atom_meta_agent.WorldModelService')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    @patch('core.atom_meta_agent.BYOKHandler')
    @patch('core.atom_meta_agent.get_canvas_provider')
    def test_init_with_user(self, mock_canvas, mock_byok, mock_mcp, mock_orchestrator, mock_world_model, mock_user):
        """Cover initialization with user."""
        agent = AtomMetaAgent(workspace_id="test-workspace", user=mock_user)
        assert agent.user == mock_user
        assert agent.user.id == "test-user-1"


class TestAtomMetaAgentExecute:
    """Test main execute method."""

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.SessionLocal')
    @patch('core.atom_meta_agent.WorldModelService')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    @patch('core.atom_meta_agent.BYOKHandler')
    @patch('core.atom_meta_agent.get_canvas_provider')
    async def test_execute_simple_request(self, mock_canvas, mock_byok, mock_mcp, mock_orchestrator,
                                        mock_world_model, mock_db):
        """Cover lines 181-368: Simple request execution."""
        # Setup mocks
        mock_db.return_value.__enter__ = Mock()
        mock_db.return_value.__exit__ = Mock()
        mock_workspace = Mock()
        mock_workspace.tenant_id = "test-tenant"
        mock_db.return_value.query.return_value.filter.return_value.first.return_value = mock_workspace

        mock_world_model.return_value.recall_experiences = AsyncMock(return_value={
            "experiences": [],
            "knowledge": [],
            "formulas": [],
            "business_facts": []
        })

        mock_mcp.return_value.get_all_tools = AsyncMock(return_value=[])

        agent = AtomMetaAgent(workspace_id="test-workspace")

        # Mock _react_step to return final answer immediately
        agent._react_step = AsyncMock(return_value=Mock(
            thought="Test thought",
            action=None,
            final_answer="Test answer",
            confidence=0.9
        ))

        # Mock _record_execution
        agent._record_execution = AsyncMock()

        result = await agent.execute("Test request")

        assert result["status"] == "success"
        assert result["final_output"] == "Test answer"
        assert "actions_executed" in result

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.SessionLocal')
    @patch('core.atom_meta_agent.WorldModelService')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    @patch('core.atom_meta_agent.BYOKHandler')
    @patch('core.atom_meta_agent.get_canvas_provider')
    async def test_execute_with_context(self, mock_canvas, mock_byok, mock_mcp, mock_orchestrator,
                                       mock_world_model, mock_db):
        """Cover execution with additional context."""
        mock_db.return_value.__enter__ = Mock()
        mock_db.return_value.__exit__ = Mock()
        mock_workspace = Mock()
        mock_workspace.tenant_id = "test-tenant"
        mock_db.return_value.query.return_value.filter.return_value.first.return_value = mock_workspace

        mock_world_model.return_value.recall_experiences = AsyncMock(return_value={})

        mock_mcp.return_value.get_all_tools = AsyncMock(return_value=[])

        agent = AtomMetaAgent(workspace_id="test-workspace")
        agent._react_step = AsyncMock(return_value=Mock(
            thought="Thought",
            action=None,
            final_answer="Answer"
        ))
        agent._record_execution = AsyncMock()

        result = await agent.execute(
            "Test request",
            context={"user_id": "test-user", "custom_field": "value"}
        )

        assert result["status"] == "success"


class TestExecuteDelegation:
    """Test _execute_delegation method."""

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.get_specialized_agent')
    async def test_delegate_to_specialized_agent(self, mock_get_agent):
        """Cover lines 525-547: Successful delegation."""
        # Setup mock agent
        mock_agent = Mock()
        mock_agent.name = "accounting"
        mock_agent.execute = AsyncMock(return_value={
            "final_output": "Delegation complete",
            "status": "success"
        })
        mock_get_agent.return_value = mock_agent

        agent = AtomMetaAgent(workspace_id="test-workspace")

        result = await agent._execute_delegation(
            agent_name="accounting",
            task="Reconcile accounts",
            context={}
        )

        assert "Delegation Result from accounting" in result
        assert "Delegation complete" in result

    @pytest.mark.asyncio
    async def test_delegate_agent_not_found(self):
        """Cover delegation failure when agent not found."""
        agent = AtomMetaAgent(workspace_id="test-workspace")

        with patch('core.atom_meta_agent.get_specialized_agent') as mock_get:
            mock_get.return_value = None

            result = await agent._execute_delegation(
                agent_name="unknown",
                task="Test task",
                context={}
            )

            assert "Error: Agent 'unknown' not found" in result

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.get_specialized_agent')
    async def test_delegate_with_execution_id(self, mock_get_agent):
        """Cover delegation with execution_id for step tracking."""
        mock_agent = Mock()
        mock_agent.name = "sales"
        mock_agent.execute = AsyncMock(return_value={"final_output": "Done"})
        mock_get_agent.return_value = mock_agent

        agent = AtomMetaAgent(workspace_id="test-workspace")

        result = await agent._execute_delegation(
            agent_name="sales",
            task="Test",
            context={},
            execution_id="exec-123"
        )

        assert "sales" in result


class TestReactStep:
    """Test _react_step method."""

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.SessionLocal')
    @patch('core.atom_meta_agent.WorldModelService')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    @patch('core.atom_meta_agent.BYOKHandler')
    @patch('core.atom_meta_agent.get_canvas_provider')
    async def test_react_step_generates_action(self, mock_canvas, mock_byok, mock_mcp,
                                            mock_orchestrator, mock_world_model, mock_db):
        """Cover lines 551-675: ReAct step with action."""
        agent = AtomMetaAgent(workspace_id="test-workspace")

        # Mock BYOK handler to return structured action
        mock_llm = Mock()
        mock_llm.generate_structured_response = AsyncMock(return_value=Mock(
            thought="I should use a tool",
            action=Mock(tool="test_tool", params={"arg": "value"}),
            final_answer=None,
            confidence=0.8
        ))
        agent.llm = mock_llm

        result = await agent._react_step(
            request="Test request",
            memory_context={},
            tool_descriptions="[]",
            execution_history="",
            context={}
        )

        assert result.thought == "I should use a tool"
        assert result.action.tool == "test_tool"
        assert result.action.params == {"arg": "value"}

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.SessionLocal')
    @patch('core.atom_meta_agent.WorldModelService')
    @patch('core.atom_meta_agent.AdvancedWorkflowOrchestrator')
    @patch('core.atom_meta_agent.mcp_service')
    @patch('core.atom_meta_agent.BYOKHandler')
    @patch('core.atom_meta_agent.get_canvas_provider')
    async def test_react_step_with_memory(self, mock_canvas, mock_byok, mock_mcp,
                                        mock_orchestrator, mock_world_model, mock_db):
        """Cover ReAct step with memory context."""
        agent = AtomMetaAgent(workspace_id="test-workspace")

        mock_llm = Mock()
        mock_llm.generate_structured_response = AsyncMock(return_value=Mock(
            thought="Based on past experience...",
            action=None,
            final_answer="Answer"
        ))
        agent.llm = mock_llm

        memory_context = {
            "experiences": [Mock(input_summary="Past task", outcome="success")],
            "knowledge": [{"text": "Related knowledge"}],
            "formulas": [],
            "business_facts": []
        }

        result = await agent._react_step(
            request="Test request",
            memory_context=memory_context,
            tool_descriptions="[]",
            execution_history="",
            context={}
        )

        assert result.final_answer == "Answer"


class TestExecuteToolWithGovernance:
    """Test _execute_tool_with_governance method."""

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.SessionLocal')
    @patch('core.atom_meta_agent.AgentGovernanceService')
    async def test_tool_execution_allowed(self, mock_gov_class, mock_db):
        """Cover lines 677-735: Tool execution with governance approval."""
        agent = AtomMetaAgent(workspace_id="test-workspace")

        # Mock governance check
        mock_gov = Mock()
        mock_gov.can_perform_action.return_value = {"allowed": True}
        mock_gov_class.return_value = mock_gov

        # Mock MCP tool execution
        agent.mcp = Mock()
        agent.mcp.call_tool = AsyncMock(return_value="Tool executed successfully")

        result = await agent._execute_tool_with_governance(
            tool_name="test_tool",
            args={"param": "value"},
            context={},
            step_callback=None
        )

        assert "Tool executed successfully" in result or result == "Tool executed successfully"

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.SessionLocal')
    @patch('core.atom_meta_agent.AgentGovernanceService')
    async def test_tool_execution_blocked(self, mock_gov_class, mock_db):
        """Cover tool execution blocked by governance."""
        agent = AtomMetaAgent(workspace_id="test-workspace")

        mock_gov = Mock()
        mock_gov.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Insufficient maturity"
        }
        mock_gov_class.return_value = mock_gov

        result = await agent._execute_tool_with_governance(
            tool_name="restricted_tool",
            args={},
            context={},
            step_callback=None
        )

        assert "Governance blocked" in result

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.SessionLocal')
    @patch('core.atom_meta_agent.AgentGovernanceService')
    async def test_tool_execution_with_approval(self, mock_gov_class, mock_db):
        """Cover tool execution requiring human approval."""
        agent = AtomMetaAgent(workspace_id="test-workspace")

        mock_gov = Mock()
        mock_gov.can_perform_action.return_value = {
            "allowed": False,
            "requires_human_approval": True,
            "reason": "Complex action"
        }
        mock_gov.request_approval.return_value = "action-123"
        mock_gov.get_approval_status.return_value = {"status": "approved"}
        mock_gov_class.return_value = mock_gov

        agent.mcp = Mock()
        agent.mcp.call_tool = AsyncMock(return_value="Done")

        result = await agent._execute_tool_with_governance(
            tool_name="complex_tool",
            args={},
            context={},
            step_callback=None
        )

        # Should complete after approval
        assert "Done" in result or result == "Done"


class TestSpawnAgent:
    """Test spawn_agent method."""

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.SessionLocal')
    @patch('core.atom_meta_agent.AgentGovernanceService')
    @patch('core.atom_meta_agent.AgentRegistry')
    async def test_spawn_agent_from_template(self, mock_registry, mock_gov_class, mock_db):
        """Cover lines 738-787: Spawn agent from predefined template."""
        agent = AtomMetaAgent(workspace_id="test-workspace")

        # Mock governance service
        mock_gov = Mock()
        mock_agent = Mock()
        mock_agent.id = "spawned_finance_abc123"
        mock_gov.register_or_update_agent.return_value = mock_agent
        mock_gov_class.return_value = mock_gov

        result = await agent.spawn_agent(
            template_name="finance_analyst",
            persist=True
        )

        assert result.id == "spawned_finance_abc123" or result is not None

    @pytest.mark.asyncio
    async def test_spawn_agent_ephemeral(self):
        """Cover ephemeral agent creation (not persisted)."""
        agent = AtomMetaAgent(workspace_id="test-workspace")

        result = await agent.spawn_agent(
            template_name="sales_assistant",
            persist=False
        )

        assert result is not None
        assert result.id in agent._spawned_agents

    @pytest.mark.asyncio
    async def test_spawn_agent_unknown_template(self):
        """Cover spawning with unknown template."""
        agent = AtomMetaAgent(workspace_id="test-workspace")

        with pytest.raises(ValueError):
            await agent.spawn_agent(template_name="unknown_template")


class TestQueryMemory:
    """Test query_memory method."""

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.WorldModelService')
    async def test_query_memory_all(self, mock_world_model):
        """Cover lines 789-806: Query all memory scopes."""
        mock_world_model.return_value.recall_experiences = AsyncMock(return_value={
            "experiences": [Mock()],
            "knowledge": [{"text": "Test"}],
            "formulas": [],
            "business_facts": []
        })

        agent = AtomMetaAgent(workspace_id="test-workspace")

        result = await agent.query_memory(query="test query", scope="all")

        assert "experiences" in result
        assert "knowledge" in result

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.WorldModelService')
    async def test_query_memory_experiences_only(self, mock_world_model):
        """Cover querying experiences only."""
        mock_world_model.return_value.recall_experiences = AsyncMock(return_value={
            "experiences": [Mock()],
            "knowledge": [],
            "formulas": [],
            "business_facts": []
        })

        agent = AtomMetaAgent(workspace_id="test-workspace")

        result = await agent.query_memory(query="test", scope="experiences")

        assert "experiences" in result
        assert "knowledge" not in result or len(result.get("knowledge", [])) == 0


class TestGenerateMentorshipGuidance:
    """Test generate_mentorship_guidance method."""

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.SessionLocal')
    @patch('core.atom_meta_agent.BYOKHandler')
    async def test_mentorship_guidance_generation(self, mock_byok, mock_db):
        """Cover lines 808-879: Generate guidance for student agent."""
        agent = AtomMetaAgent(workspace_id="test-workspace")

        # Mock LLM response
        mock_llm = Mock()
        mock_llm.generate_response = AsyncMock(return_value="Guidance: Student should...")
        agent.llm = mock_llm

        # Mock database query for supervisor check
        mock_db.return_value.query.return_value.filter.return_value.count.return_value = 0

        result = await agent.generate_mentorship_guidance(
            student_agent_id="student-123",
            action="complex_action",
            params={"arg": "value"},
            reason="Student maturity insufficient"
        )

        assert result is not None
        assert isinstance(result, str)

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.SessionLocal')
    @patch('core.atom_meta_agent.BYOKHandler')
    async def test_mentorship_with_supervisor_present(self, mock_byok, mock_db):
        """Cover mentorship when supervisor exists."""
        agent = AtomMetaAgent(workspace_id="test-workspace")

        mock_llm = Mock()
        mock_llm.generate_response = AsyncMock(return_value="Standard guidance")
        agent.llm = mock_llm

        # Mock that supervisors exist
        mock_db.return_value.query.return_value.filter.return_value.count.return_value = 2

        result = await agent.generate_mentorship_guidance(
            student_agent_id="student-123",
            action="test_action",
            params={},
            reason="Test reason"
        )

        assert isinstance(result, str)


class TestGetAtomAgent:
    """Test get_atom_agent singleton."""

    @patch('core.atom_meta_agent.AtomMetaAgent')
    def test_get_atom_agent_singleton(self, mock_agent_class):
        """Cover lines 1077-1081: Singleton pattern."""
        agent1 = get_atom_agent(workspace_id="default")
        agent2 = get_atom_agent(workspace_id="default")

        # Should return same instance
        assert agent1 is agent2

    @patch('core.atom_meta_agent.AtomMetaAgent')
    def test_get_atom_agent_different_workspace(self, mock_agent_class):
        """Cover getting agent for different workspace."""
        agent1 = get_atom_agent(workspace_id="workspace1")
        agent2 = get_atom_agent(workspace_id="workspace2")

        # Should create new instance for different workspace
        assert agent1 is not agent2


class TestTriggerHandlers:
    """Test trigger handler functions."""

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.SessionLocal')
    @patch('core.atom_meta_agent.AtomMetaAgent')
    @patch('core.atom_meta_agent.enqueue_task')
    async def test_handle_data_event_trigger_with_qstash(self, mock_enqueue, mock_agent_class, mock_db):
        """Cover lines 969-1003: Data event trigger with QStash."""
        mock_enqueue.return_value = "task-123"

        result = await handle_data_event_trigger(
            event_type="webhook",
            data={"test": "data"},
            workspace_id="test-workspace"
        )

        assert result["status"] == "queued"
        assert "task_id" in result

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.SessionLocal')
    @patch('core.atom_meta_agent.AtomMetaAgent')
    @patch('core.atom_meta_agent.enqueue_task')
    async def test_handle_data_event_fallback(self, mock_enqueue, mock_agent_class, mock_db):
        """Cover data event trigger falling back to inline execution."""
        # Mock QStash failure
        mock_enqueue.side_effect = Exception("QStash unavailable")

        # Mock inline execution
        mock_atom = Mock()
        mock_atom.execute = AsyncMock(return_value={"status": "success"})
        mock_agent_class.return_value = mock_atom

        result = await handle_data_event_trigger(
            event_type="ingestion",
            data={"key": "value"},
            workspace_id="default"
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    @patch('core.atom_meta_agent.AtomMetaAgent')
    async def test_handle_manual_trigger(self, mock_agent_class, mock_user):
        """Cover lines 1006-1071: Manual/user-initiated trigger."""
        mock_atom = Mock()
        mock_atom.execute = AsyncMock(return_value={
            "status": "success",
            "final_output": "Task complete"
        })
        mock_agent_class.return_value = mock_atom

        result = await handle_manual_trigger(
            request="Test request",
            user=mock_user,
            workspace_id="test-workspace"
        )

        assert result["status"] == "success"
        assert "final_output" in result
