import pytest
from unittest.mock import AsyncMock, patch
from enhanced_ai_workflow_endpoints import RealAIWorkflowService
import json

@pytest.mark.asyncio
async def test_routing_logic_sales(mock_env_vars):
    """Test that the system routes to SALES logic when LLM returns Sales intent"""
    # Mock ClientSession
    with patch('aiohttp.ClientSession', return_value=AsyncMock()) as mock_session_cls:
        service = RealAIWorkflowService()
        await service.initialize_sessions()
        
        # Inject a FIXED response from the LLM
        mock_response = {
            "intent": "Create a new lead",
            "workflow_suggestion": {
                "nodes": [
                    {"service": "salesforce", "action": "create_lead", "params": {"name": "Test Lead"}}
                ]
            },
            "confidence": 0.99,
            "ai_provider_used": "mock_provider"
        }
        
        fixed_json_string = json.dumps(mock_response)
        
        # Mock OpenAI call to return this JSON
        # We assume logic tries OpenAI first or we force it
        with patch.object(service, 'call_openai_api', return_value={
            'content': fixed_json_string,
            'confidence': 0.99,
            'token_usage': {},
            'provider': 'openai'
        }):
            # Act
            result = await service.process_with_nlu("This input does not matter", provider="openai")
            
            # Assert
            assert result['intent'] == "Create a new lead"
            nodes = result['workflow_suggestion']['nodes']
            assert nodes[0]['service'] == 'salesforce'
            assert nodes[0]['action'] == 'create_lead'

@pytest.mark.asyncio
async def test_malformed_llm_response(mock_env_vars):
    """Test behavior when LLM returns garbage non-JSON"""
    # Mock ClientSession
    with patch('aiohttp.ClientSession', return_value=AsyncMock()) as mock_session_cls:
        service = RealAIWorkflowService()
        await service.initialize_sessions()
        
        with patch.object(service, 'call_openai_api', return_value={
            'content': "I am not returning JSON, I am just chatting.",
            'confidence': 0.5,
            'token_usage': {},
            'provider': 'openai'
        }):
            # Act
            # The system should fall back to creating a structured task from the raw text body
            result = await service.process_with_nlu("test", provider="openai")
            
            # Assert
            # System typically creates an "intent" from the content if JSON parsing fails
            assert "intent" in result
            assert "tasks" in result
            assert result['ai_provider_used'] == 'openai'
