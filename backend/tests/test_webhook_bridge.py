import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Mock problematic dependencies
sys.modules["instructor"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["lancedb"] = MagicMock()

import asyncio
from datetime import datetime

import core.agent_integration_gateway
from integrations.universal_webhook_bridge import UnifiedIncomingMessage, universal_webhook_bridge


@pytest.mark.asyncio
async def test_slack_message_routing():
    """Test that Slack messages are correctly routed and response sent back"""
    mock_orchestrator = AsyncMock()
    mock_orchestrator.process_chat_message.return_value = {"message": "Hello from Orchestrator"}
    mock_gateway_action = AsyncMock()
    
    with patch.object(universal_webhook_bridge, '_get_orchestrator', return_value=mock_orchestrator), \
         patch('core.agent_integration_gateway.AgentIntegrationGateway.execute_action', mock_gateway_action):
        
        slack_payload = {
            "type": "message",
            "user": "U12345",
            "channel": "C67890",
            "text": "Hello ATOM",
            "ts": "1234567890.123456"
        }
        
        result = await universal_webhook_bridge.process_incoming_message("slack", slack_payload)
        
        assert result["status"] == "success"
        mock_orchestrator.process_chat_message.assert_called_once()
        
        # Verify response sent back
        mock_gateway_action.assert_called_once()
        args, kwargs = mock_gateway_action.call_args
        assert args[1] == "slack"
        assert args[2]["content"] == "Hello from Orchestrator"
        assert args[2]["channel"] == "C67890"

@pytest.mark.asyncio
async def test_whatsapp_message_routing():
    """Test that WhatsApp messages are correctly routed and response sent back"""
    mock_orchestrator = AsyncMock()
    mock_orchestrator.process_chat_message.return_value = {"message": "Hello from WhatsApp"}
    mock_gateway_action = AsyncMock()
    
    with patch.object(universal_webhook_bridge, '_get_orchestrator', return_value=mock_orchestrator), \
         patch('core.agent_integration_gateway.AgentIntegrationGateway.execute_action', mock_gateway_action):
        
        whatsapp_payload = {
            "from": "1234567890",
            "id": "msg_001",
            "type": "text",
            "text": {"body": "Hi from WhatsApp"}
        }
        
        result = await universal_webhook_bridge.process_incoming_message("whatsapp", whatsapp_payload)
        
        assert result["status"] == "success"
        mock_orchestrator.process_chat_message.assert_called_once()
        
        # Verify response sent back
        mock_gateway_action.assert_called_once()
        args, kwargs = mock_gateway_action.call_args
        assert args[1] == "whatsapp"
        assert args[2]["content"] == "Hello from WhatsApp"
        assert args[2]["recipient_id"] == "1234567890"

@pytest.mark.asyncio
async def test_run_command_trigger():
    """Test that the /run command triggers an agent execution and routes results back"""
    mock_execute_task = AsyncMock()
    mock_execute_action = AsyncMock()
    
    with patch('api.agent_routes.execute_agent_task', mock_execute_task), \
         patch('core.agent_integration_gateway.AgentIntegrationGateway.execute_action', mock_execute_action), \
         patch.object(universal_webhook_bridge, '_get_agent_id_by_name', return_value="agent_123"):

        slack_command_payload = {
            "type": "message",
            "user": "U12345",
            "channel": "C67890",
            "text": "/run researcher find nuclear fusion news",
            "ts": "1234567890.123456"
        }

        result = await universal_webhook_bridge.process_incoming_message("slack", slack_command_payload)

        assert result["status"] == "command_triggered"
        assert result["command"] == "run"

        # Verify execute_agent_task was called with correct context
        mock_execute_task.assert_called_once()
        args, kwargs = mock_execute_task.call_args
        assert args[1]["source_platform"] == "slack"
        assert args[1]["recipient_id"] == "C67890"

@pytest.mark.asyncio
async def test_workflow_command_trigger():
    """Test that the /workflow command triggers a workflow"""
    mock_orchestrator = AsyncMock()
    mock_execute_action = AsyncMock()
    
    with patch('advanced_workflow_orchestrator.AdvancedWorkflowOrchestrator.trigger_event', new_callable=AsyncMock) as mock_trigger, \
         patch('core.agent_integration_gateway.AgentIntegrationGateway.execute_action', mock_execute_action):
        
        payload = {
            "type": "message",
            "user": "U12345",
            "channel": "C67890",
            "text": "/workflow intake_process"
        }
        
        result = await universal_webhook_bridge.process_incoming_message("slack", payload)
        
        assert result["status"] == "command_triggered"
        mock_trigger.assert_called_once()
        assert "intake_process" in mock_trigger.call_args[0][0]

@pytest.mark.asyncio
async def test_status_command():
    """Test the /status command"""
    mock_execute_action = AsyncMock()
    
    with patch('core.agent_integration_gateway.AgentIntegrationGateway.execute_action', mock_execute_action):
        payload = {
            "type": "message",
            "user": "U12345",
            "channel": "C67890",
            "text": "/status"
        }
        
        result = await universal_webhook_bridge.process_incoming_message("slack", payload)
        
        assert result["status"] == "status_sent"
        mock_execute_action.assert_called_once()
        assert "Online" in mock_execute_action.call_args[0][2]["content"]

@pytest.mark.asyncio
async def test_agents_command():
    """Test the /agents command listing"""
    mock_execute_action = AsyncMock()
    mock_agent = MagicMock()
    mock_agent.name = "Custom Research Agent"
    mock_agent.id = "custom_res_001"
    mock_agent.description = "Deep research agent"
    
    with patch('core.agent_integration_gateway.AgentIntegrationGateway.execute_action', mock_execute_action), \
         patch('core.database.SessionLocal') as mock_session_local:
        
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.return_value.all.return_value = [mock_agent]
        
        payload = {
            "type": "message",
            "user": "U12345",
            "channel": "C67890",
            "text": "/agents"
        }
        
        result = await universal_webhook_bridge.process_incoming_message("slack", payload)
        
        assert result["status"] == "agents_listed"
        mock_execute_action.assert_called_once()
        content = mock_execute_action.call_args[0][2]["content"]
        assert "Custom Research Agent" in content
        assert "Finance Analyst" in content # From templates

@pytest.mark.asyncio
async def test_help_command():
    """Test the /help command"""
    mock_execute_action = AsyncMock()
    
    with patch('core.agent_integration_gateway.AgentIntegrationGateway.execute_action', mock_execute_action):
        payload = {
            "type": "message",
            "user": "U12345",
            "channel": "C67890",
            "text": "/help"
        }
        
        result = await universal_webhook_bridge.process_incoming_message("slack", payload)
        
        assert result["status"] == "help_sent"
        mock_execute_action.assert_called_once()
        assert "/run" in mock_execute_action.call_args[0][2]["content"]

@pytest.mark.asyncio
async def test_agent_to_agent_loop():
    """Test direct messaging between agents via the bridge"""
    mock_orchestrator = AsyncMock()
    mock_orchestrator.process_chat_message.return_value = {"message": "Confirmed, agent A."}
    mock_execute_action = AsyncMock()
    
    # Patch the CLASS and ensure _get_orchestrator returns the instance
    # Also patch the gateway to avoid DB errors when sending response back
    with patch('integrations.universal_webhook_bridge.UniversalWebhookBridge._get_orchestrator', return_value=mock_orchestrator), \
         patch('core.agent_integration_gateway.AgentIntegrationGateway.execute_action', mock_execute_action):
        
        agent_payload = {
            "agent_id": "agent_alpha",
            "target_id": "agent_beta",
            "message": "Protocol check"
        }
        
        result = await universal_webhook_bridge.process_incoming_message("agent", agent_payload)
        
        assert result["status"] == "success"
        mock_orchestrator.process_chat_message.assert_called_once()
        # Verify it was called with the right message (handle both args and kwargs)
        call_kwargs = mock_orchestrator.process_chat_message.call_args.kwargs
        assert call_kwargs["message"] == "Protocol check"

@pytest.mark.asyncio
async def test_fuzzy_agent_lookup():
    """Test smarter agent lookup by name"""
    mock_agent = MagicMock()
    mock_agent.name = "Competitive Intel Agent"
    mock_agent.id = "comp_intel_001"
    
    with patch('core.database.SessionLocal') as mock_session_local:
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        # We need 4 return values for 2 agents looked up (exact then fuzzy for each)
        mock_db.query.return_value.filter.return_value.first.side_effect = [None, mock_agent, None, None]
        
        # Test fuzzy registry match
        agent_id = await universal_webhook_bridge._get_agent_id_by_name("Intel")
        assert agent_id == "comp_intel_001"
        
        # Test template match (registry returns None for both exact and fuzzy)
        agent_id = await universal_webhook_bridge._get_agent_id_by_name("Finance")
        assert agent_id == "finance_analyst"

@pytest.mark.asyncio
async def test_ignored_events():
    """Test that bot messages and non-message events are ignored"""
    slack_bot_payload = {
        "type": "message",
        "subtype": "bot_message",
        "text": "I am a bot"
    }
    
    result = await universal_webhook_bridge.process_incoming_message("slack", slack_bot_payload)
    assert result["status"] == "ignored"

    unknown_payload = {"type": "reaction_added"}
    result = await universal_webhook_bridge.process_incoming_message("slack", unknown_payload)
    assert result["status"] == "ignored"
