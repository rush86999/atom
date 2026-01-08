
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.generic_agent import GenericAgent
from core.models import AgentRegistry
from integrations.mcp_service import MCPService

@pytest.fixture
def mock_agent_registry():
    return AgentRegistry(
        id="test_agent",
        name="Integration Tester",
        configuration={
            "tools": ["call_integration", "search_integration"],
            "system_prompt": "You are a test agent."
        }
    )

@pytest.fixture
def mock_integration_service():
    with patch("integrations.universal_integration_service.UniversalIntegrationService") as MockService:
        instance = MockService.return_value
        instance.execute = AsyncMock(return_value={"status": "success", "id": "123"})
        instance.search = AsyncMock(return_value=[{"id": "123", "name": "Test Entry"}])
        yield instance

@pytest.mark.asyncio
async def test_agent_calls_integration_tool(mock_agent_registry, mock_integration_service):
    """Test that GenericAgent can call 'call_integration' via MCP"""
    
    agent = GenericAgent(mock_agent_registry)
    
    # Mock LLM to return a tool call
    with patch.object(agent.llm, "generate_response", new_callable=AsyncMock) as mock_llm:
        # First response is a Thought + Action
        # Second response is Final Answer
        mock_llm.side_effect = [
            'Thought: I need to create a contact.\nAction: {"tool": "call_integration", "params": {"service": "salesforce", "action": "create", "params": {"entity": "contact", "data": {"LastName": "Doe"}}}}',
            'Final Answer: Contact created.'
        ]
        
        # Execute
        result = await agent.execute("Create contact Doe in Salesforce", context={"user_id": "test_user"})
        
        # Verify result
        assert result["status"] == "success"
        assert "Contact created" in result["output"]
        
        # Verify Universal Service Call
        mock_integration_service.execute.assert_called_once()
        call_args = mock_integration_service.execute.call_args[1]
        assert call_args["service"] == "salesforce"
        assert call_args["action"] == "create"
        assert call_args["params"]["entity"] == "contact"
        assert call_args["context"]["user_id"] == "test_user"

@pytest.mark.asyncio
async def test_agent_searches_integration(mock_agent_registry, mock_integration_service):
    """Test that GenericAgent can call 'search_integration' via MCP"""
    
    agent = GenericAgent(mock_agent_registry)
    
    with patch.object(agent.llm, "generate_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = [
            'Thought: I need to search for a contact.\nAction: {"tool": "search_integration", "params": {"service": "hubspot", "query": "Acme", "entity_type": "company"}}',
            'Final Answer: Found Acme.'
        ]
        
        result = await agent.execute("Search for Acme in HubSpot", context={"user_id": "test_user"})
        
        assert result["status"] == "success"
        
        mock_integration_service.search.assert_called_once()
        call_args = mock_integration_service.search.call_args[1]
        assert call_args["service"] == "hubspot"
        assert call_args["query"] == "Acme"
