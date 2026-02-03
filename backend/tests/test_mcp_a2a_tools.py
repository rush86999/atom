from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from integrations.mcp_service import MCPService


@pytest.mark.asyncio
async def test_list_agents_tool():
    """Test that list_agents returns both templates and registered agents"""
    mcp = MCPService()
    
    # Mock database session and registry
    mock_agent = MagicMock()
    mock_agent.id = "reg_agent_1"
    mock_agent.name = "Registered Agent"
    mock_agent.description = "A registered agent"
    mock_agent.category = "Testing"
    
    with patch('core.database.SessionLocal') as mock_session_local:
        mock_db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.all.return_value = [mock_agent]
        
        result = await mcp.execute_tool("local-tools", "list_agents", {})
        
        assert "templates" in result
        assert "registered" in result
        assert len(result["registered"]) == 1
        assert result["registered"][0]["id"] == "reg_agent_1"
        assert "finance_analyst" in result["templates"]

@pytest.mark.asyncio
async def test_bridge_agent_delegate_tool():
    """Test that bridge_agent_delegate correctly calls the bridge"""
    mcp = MCPService()
    
    mock_bridge = AsyncMock()
    mock_bridge.process_incoming_message.return_value = {"status": "success", "message": "Task delegated"}
    
    with patch('integrations.universal_webhook_bridge.universal_webhook_bridge', mock_bridge):
        arguments = {
            "target_agent": "Intel Agent",
            "message": "Analyze competitor X"
        }
        context = {"agent_id": "manager_agent", "workspace_id": "test_ws"}
        
        result = await mcp.execute_tool("local-tools", "bridge_agent_delegate", arguments, context)
        
        assert result["status"] == "success"
        mock_bridge.process_incoming_message.assert_called_once()
        
        # Verify bridge was called with platform="agent"
        call_args = mock_bridge.process_incoming_message.call_args
        assert call_args[0][0] == "agent"
        payload = call_args[0][1]
        assert payload["target_id"] == "Intel Agent"
        assert payload["agent_id"] == "manager_agent"

@pytest.mark.asyncio
async def test_a2a_feedback_loop():
    """Test the complete A2A feedback loop: gateway -> bridge"""
    import sys
    from unittest.mock import MagicMock

    # Mock 'instructor' which is missing in this env but used deep in imports
    sys.modules['instructor'] = MagicMock()
    
    from core.agent_integration_gateway import ActionType, agent_integration_gateway

    # Mock the bridge and governance to avoid DB calls
    mock_bridge = AsyncMock()
    mock_bridge.process_incoming_message.return_value = {"status": "success"}
    
    with patch('integrations.universal_webhook_bridge.universal_webhook_bridge', mock_bridge), \
         patch('core.agent_integration_gateway.contact_governance.is_external_contact', return_value=False):
        # Params as they would come from agent_routes.py after a task finishes
        params = {
            "source_platform": "agent",
            "recipient_id": "manager_agent", # The creator
            "sender_agent_id": "worker_agent", # The one who finished
            "content": "✅ *Worker* finished task:\nAnalysis complete."
        }
        
        result = await agent_integration_gateway.execute_action(
            ActionType.SEND_MESSAGE,
            "agent",
            params
        )
        
        assert result["status"] == "success"
        mock_bridge.process_incoming_message.assert_called_once()
        
        # Verify the bridge was called with the right loopback info
        call_args = mock_bridge.process_incoming_message.call_args
        assert call_args[0][0] == "agent"
        payload = call_args[0][1]
        assert payload["agent_id"] == "worker_agent"
        assert payload["target_id"] == "manager_agent"
        assert "Analysis complete" in payload["message"]
