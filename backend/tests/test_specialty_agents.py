
import pytest
from unittest.mock import MagicMock, patch
from core.models import AgentRegistry, AgentStatus
from core.generic_agent import GenericAgent
import uuid

@pytest.fixture
def mock_agent_model():
    return AgentRegistry(
        id=str(uuid.uuid4()),
        name="Test Agent",
        category="Test",
        configuration={
            "system_prompt": "You are a test agent.",
            "tools": ["web_search"]
        },
        schedule_config={"active": True, "cron_expression": "* * * * *"}
    )

@pytest.mark.asyncio
async def test_generic_agent_initialization(mock_agent_model):
    agent = GenericAgent(mock_agent_model)
    assert agent.name == "Test Agent"
    assert agent.system_prompt == "You are a test agent."
    assert agent.allowed_tools == ["web_search"]

@pytest.mark.asyncio
@patch("core.generic_agent.WorldModelService")
@patch("core.generic_agent.BYOKHandler")
async def test_generic_agent_execution(mock_llm_cls, mock_wm_cls, mock_agent_model):
    # Setup Mocks
    mock_wm = mock_wm_cls.return_value
    
    # helper for async return
    async def async_return(val):
        return val

    mock_wm.recall_experiences.side_effect = lambda *args, **kwargs: async_return({"experiences": []})
    mock_wm.record_experience.side_effect = lambda *args, **kwargs: async_return(None)
    
    mock_llm = mock_llm_cls.return_value
    mock_llm.generate_response.side_effect = lambda *args, **kwargs: async_return("I have completed the task.")
    
    # Execute
    agent = GenericAgent(mock_agent_model)
    result = await agent.execute("Do something")
    
    # Verify
    assert result["status"] == "success"
    assert result["output"] == "I have completed the task."
    
    # Verify interaction with Memory
    mock_wm.recall_experiences.assert_called_once()
    mock_wm.record_experience.assert_called_once()

@patch("core.atom_meta_agent.AgentRegistry")
@patch("core.atom_meta_agent.SessionLocal")
@patch("core.atom_meta_agent.AtomMetaAgent._record_execution")
@patch("core.generic_agent.GenericAgent.execute")
@pytest.mark.asyncio
async def test_meta_agent_execution_flow(mock_execute, mock_record, mock_db, mock_registry_cls):
    from core.atom_meta_agent import AtomMetaAgent, AgentTriggerMode
    
    # Setup
    meta_agent = AtomMetaAgent()
    meta_agent.user = MagicMock(id="user1")
    
    # Mock specific agent registry return
    mock_registry_instance = MagicMock()
    mock_registry_instance.module_path = "core.generic_agent"
    mock_registry_instance.class_name = "GenericAgent"
    # Populate the _spawned_agents dict effectively
    meta_agent._spawned_agents["spawned_agent_123"] = mock_registry_instance
    
    # Mock plan execution to trigger an agent
    # We override _execute_plan behavior by mocking where it calls execute
    # Ideally we'd test _execute_plan directly, let's do that.
    
    plan = {
        "actions": [{
            "type": "spawn_agent",
            "template": "finance_analyst"
        }]
    }
    
    # Mock spawn_agent
    with patch.object(meta_agent, "spawn_agent", new_callable=MagicMock) as mock_spawn:
        mock_agent = MagicMock()
        mock_agent.id = "spawned_agent_123"
        mock_agent.name = "Finance Agent"
        mock_spawn.return_value = mock_agent
        
        # We also need to ensure the agent is in the _spawned_agents map or DB for execution logic
        # Our modified code checks _spawned_agents.get(id)
        
        # Let's side_effect the spawn request to populate the dict
        async def side_effect_spawn(*args, **kwargs):
            meta_agent._spawned_agents["spawned_agent_123"] = mock_registry_instance
            return mock_agent
        mock_spawn.side_effect = side_effect_spawn

        mock_execute.return_value = {"output": "Simulated Result"}

        # Run
        result = await meta_agent._execute_plan(plan, {}, AgentTriggerMode.MANUAL)
        
        # Verify
        assert "spawned_agent" in result
        assert result["final_output"] == "Simulated Result"
