
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from core.generic_agent import GenericAgent
from core.models import AgentRegistry, AgentStatus


@pytest.fixture
def mock_agent_registry():
    return AgentRegistry(
        id="test_agent",
        name="Test Agent",
        category="Test",
        status=AgentStatus.STUDENT.value,
        configuration={"tools": ["calculator"], "max_steps": 5}
    )

@pytest.fixture
def generic_agent(mock_agent_registry):
    # Mock WorldModelService to avoid DB interaction
    with patch("core.generic_agent.WorldModelService") as MockWM:
        mock_wm = MockWM.return_value
        mock_wm.recall_experiences = AsyncMock(return_value={"experiences": []})
        mock_wm.record_experience = AsyncMock()
        
        # Mock BYOKHandler
        with patch("core.generic_agent.BYOKHandler") as MockLLM:
            agent = GenericAgent(mock_agent_registry)
            agent.llm = MockLLM.return_value
            agent.llm.generate_response = AsyncMock()
            
            # Mock MCP tool execution
            agent._step_act = AsyncMock(return_value="42")
            
            yield agent

@pytest.mark.integration
@pytest.mark.asyncio
async def test_react_loop_reasoning(generic_agent):
    """
    Test a 2-step ReAct loop:
    1. Thought + Action (Calculator)
    2. Observation (Result) -> Thought + Final Answer
    """
    
    # Sequence of LLM responses
    # Turn 1: Decide to use tool
    response_1 = """
    Thought: I need to calculate 21 + 21.
    Action: {"tool": "calculator", "params": {"expression": "21 + 21"}}
    """
    
    # Turn 2: Reasoning after observation (observation is injected by loop) -> Final Answer
    response_2 = """
    Thought: The result is 42.
    Final Answer: The answer is 42.
    """
    
    generic_agent.llm.generate_response.side_effect = [response_1, response_2]
    
    # Execute
    result = await generic_agent.execute("What is 21 + 21?")
    
    # Verifications
    assert result["output"] == "The answer is 42."
    assert len(result["steps"]) == 2
    
    # Step 1 Check
    step1 = result["steps"][0]
    assert step1["thought"] == "I need to calculate 21 + 21."
    assert step1["action"]["tool"] == "calculator"
    assert step1["output"] == "42" # From mock act
    
    # Step 2 Check
    step2 = result["steps"][1]
    assert step2["final_answer"] == "The answer is 42."
    
    # Check that record_experience was called
    generic_agent.world_model.record_experience.assert_called_once()

@pytest.mark.integration
@pytest.mark.asyncio
async def test_react_loop_max_steps(generic_agent):
    """Test that loop terminates after max_steps"""
    generic_agent.config["max_steps"] = 3
    
    # Always return just thought, no answer
    generic_agent.llm.generate_response.return_value = "Thought: Still thinking..."
    
    result = await generic_agent.execute("Infinite loop?")
    
    assert result["status"] == "timeout_forced_answer"
    # Or "timeout_forced_answer" depending on implementation logic for last step
    # My logic: "if current_step == max_steps ... final_answer = llm_response"
    # status = "timeout_forced_answer"
    
    assert result["status"] == "timeout_forced_answer"
    assert len(result["steps"]) == 3
