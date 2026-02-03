from unittest.mock import AsyncMock, patch
import pytest
from enhanced_ai_workflow_endpoints import RealAIWorkflowService


@pytest.mark.asyncio
async def test_tool_failure_500(mock_env_vars):
    """Test that that a 500 error from an AI provider is handled gracefully"""
    # Mock ClientSession to prevent real socket creation
    with patch('aiohttp.ClientSession', return_value=AsyncMock()) as mock_session_cls:
        service = RealAIWorkflowService()
        await service.initialize_sessions()
        
        # Mock the specific provider call to raise an exception
        # We patch the instance method directly on the service object
        with patch.object(service, 'call_openai_api', side_effect=Exception("API Error 500")):
            # Mock ALL other providers to fail too, to force exception bubbling or simple handling
            service.call_anthropic_api = AsyncMock(side_effect=Exception("Anthropic 500"))
            service.call_deepseek_api = AsyncMock(side_effect=Exception("DeepSeek 500"))
            service.call_google_api = AsyncMock(side_effect=Exception("Google 500"))
            service.call_glm_api = AsyncMock(side_effect=Exception("GLM 500"))
            
            # process_with_nlu should raise an exception saying "All AI providers failed"
            with pytest.raises(Exception) as excinfo:
                await service.process_with_nlu("test", provider="openai")
            
            assert "All AI providers failed" in str(excinfo.value)

@pytest.mark.asyncio
async def test_tool_timeout(mock_env_vars):
    """Test that a timeout is handled and fallback works"""
    # Mock ClientSession
    with patch('aiohttp.ClientSession', return_value=AsyncMock()) as mock_session_cls:
        service = RealAIWorkflowService()
        await service.initialize_sessions()
        
        # Simulate timeout on OpenAI
        with patch.object(service, 'call_openai_api', side_effect=TimeoutError("Connection Timed Out")):
            # Mock Fallback to DeepSeek succeeding WITH VALID JSON
            service.call_deepseek_api = AsyncMock(return_value={
                'content': '{"intent": "Fallback Success", "workflow_suggestion": {}}',
                'confidence': 0.8,
                'provider': 'deepseek',
                'token_usage': {}
            })
            
            # If we ask for openai, it fails.
            # Then it tries openai (dup), anthropic (fail/mock), deepseek (success).
            
            # Mock Anthropic to fail
            service.call_anthropic_api = AsyncMock(side_effect=Exception("Anthropic Key Invalid"))
            
            result = await service.process_with_nlu("test", provider="openai")
            
            # It should eventually hit DeepSeek
            assert result['ai_provider_used'] == 'deepseek'
            # Assert INTENT, not content content which is parsed away
            assert result['intent'] == 'Fallback Success'
