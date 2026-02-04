
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from core.atom_meta_agent import AgentTriggerMode, AtomMetaAgent
from core.models import User


@pytest.fixture
def mock_atom_agent():
    with patch("core.atom_meta_agent.WorldModelService") as MockWM, \
         patch("core.atom_meta_agent.BYOKHandler") as MockLLM, \
         patch("core.atom_meta_agent.AdvancedWorkflowOrchestrator") as MockOrch:
         
         agent = AtomMetaAgent()
         
         # Mock dependencies
         agent.world_model = MockWM.return_value
         agent.world_model.recall_experiences = AsyncMock(return_value={"experiences": []})
         agent.world_model.record_experience = AsyncMock()
         
         agent.llm = MockLLM.return_value
         agent.llm.generate_response = AsyncMock()
         
         # Mock Spawn
         agent.spawn_agent = AsyncMock()
         
         yield agent

@pytest.mark.asyncio
async def test_atom_react_spawn_flow(mock_atom_agent):
    """
    Test Atom reasoning to spawn a finance agent.
    """
    # 1. Thought: Need finance agent -> Action: spawn_agent
    response_1 = """
    Thought: The user wants to analyze expenses. I should spawn a Finance Analyst.
    Action: {"tool": "spawn_agent", "params": {"template": "finance_analyst", "task": "Analyze Q3 expenses"}}
    """
    
    # 2. Thought: Agent finished -> Final Answer
    response_2 = """
    Thought: The finance analyst has completed the analysis.
    Final Answer: The Q3 expenses execution is complete. See report.
    """
    
    mock_atom_agent.llm.generate_response.side_effect = [response_1, response_2]
    
    # Mock the internal GenericAgent execution that happens inside _step_act for spawn_agent
    # Since we mocked spawn_agent method itself, we need to ensure _step_act logic is tested 
    # OR we let spawn_agent be real and mock GenericAgent.
    
    # Let's unmock spawn_agent to test _step_act logic, but mock GenericAgent
    with patch("core.atom_meta_agent.AtomMetaAgent.spawn_agent", side_effect=mock_atom_agent.spawn_agent) as mock_spawn:
        # Actually, if I mocked the method on the instance in fixture, 
        # I should restore it if I want to test _step_act calling it?
        # The _step_act calls self.spawn_agent. The fixture mocked it. 
        # That's fine, we want to see it called.
        
        # But _step_act ALSO instantiates GenericAgent and calls execute.
        with patch("core.generic_agent.GenericAgent") as MockGeneric:
            mock_runner = MockGeneric.return_value
            mock_runner.execute = AsyncMock(return_value={"output": "Expense Report Generated"})
            
            # Since we mocked spawn_agent in fixture, it won't actually return an agent object 
            # unless we tell it to.
            mock_agent_obj = MagicMock()
            mock_agent_obj.name = "Finance Bot"
            mock_atom_agent.spawn_agent.return_value = mock_agent_obj
            
            # Execute
            result = await mock_atom_agent.execute("Analyze my Q3 expenses")
            
            # Verify
            assert result["final_output"] == "The Q3 expenses execution is complete. See report."
            assert len(result["actions_executed"]) == 2
            
            # Verify Tool Call
            mock_atom_agent.spawn_agent.assert_called_with("finance_analyst", persist=False)
            mock_runner.execute.assert_called()

@pytest.mark.asyncio
async def test_atom_react_integration_flow(mock_atom_agent):
    """Test Atom reasoning to call integration directly"""
    
    response_1 = """
    Thought: I need to search for 'Atom' on web.
    Action: {"tool": "call_integration", "params": {"service": "web_search", "action": "search", "params": {"q": "Atom"}}}
    """
    
    response_2 = """
    Final Answer: Search complete.
    """
    
    mock_atom_agent.llm.generate_response.side_effect = [response_1, response_2]
    mock_atom_agent.call_integration = AsyncMock(return_value={"result": "Found it"})
    
    result = await mock_atom_agent.execute("Search for Atom")
    
    mock_atom_agent.call_integration.assert_called_with("web_search", "search", {"q": "Atom"})
    assert result["final_output"] == "Search complete."
