from unittest.mock import AsyncMock, patch
import pytest
from enhanced_ai_workflow_endpoints import RealAIWorkflowService


@pytest.mark.asyncio
async def test_system_prompt_structure(mock_env_vars):
    """Test that the system prompt contains the Service Registry"""
    # Mock ClientSession
    with patch('aiohttp.ClientSession', return_value=AsyncMock()) as mock_session_cls:
        service = RealAIWorkflowService()
        await service.initialize_sessions()
        
        # We need to inspect the 'call_openai_api' arguments to see the system prompt
        # We'll stick a mock there and check call_args
        with patch.object(service, 'call_openai_api', return_value={
            'content': '{"intent": "test"}', 
            'confidence': 1.0, 
            'provider': 'openai'
        }) as mock_call:
            
            await service.process_with_nlu("test input", provider="openai")
            
            # Check arguments passed to call_openai_api(prompt, system_prompt)
            args, kwargs = mock_call.call_args
            system_prompt = args[1] # 2nd arg
            
            # Verify Service Registry is present
            # Verify Service Registry is present
            assert "**AVAILABLE SERVICES & ACTIONS" in system_prompt
            assert "slack: post_message" in system_prompt
            assert "salesforce: create_lead" in system_prompt
            
            # Verify Few-Shot Examples
            assert "**EXAMPLES:**" in system_prompt

@pytest.mark.asyncio
async def test_prompt_rendering_empty_input(mock_env_vars):
    """Test handling of empty input string"""
    with patch('aiohttp.ClientSession', return_value=AsyncMock()):
        service = RealAIWorkflowService()
        await service.initialize_sessions()
        
        with patch.object(service, 'call_openai_api', return_value={
            'content': '{"intent": "empty"}', 
            'confidence': 1.0, 
            'provider': 'openai'
        }) as mock_call:
            await service.process_with_nlu("", provider="openai")
            args, _ = mock_call.call_args
            user_prompt = args[0]
            assert "Analyze this request: " in user_prompt

@pytest.mark.asyncio
async def test_prompt_rendering_large_input(mock_env_vars):
    """Test handling of very large input string (context window)"""
    large_input = "word " * 10000 
    
    with patch('aiohttp.ClientSession', return_value=AsyncMock()):
        service = RealAIWorkflowService()
        await service.initialize_sessions()
        
        # We just want to ensure it doesn't crash before calling API
        # Real limiting happens at API level usually, or if we truncate.
        # enhanced_ai_workflow_endpoints.py doesn't seem to explicitly truncate input BEFORE call_openai_api?
        # Actually in logic: user_prompt = f"Analyze this request: {text}"
        
        with patch.object(service, 'call_openai_api', return_value={
            'content': '{"intent": "large"}', 
            'confidence': 1.0, 
            'provider': 'openai'
        }) as mock_call:
            
            try:
                await service.process_with_nlu(large_input, provider="openai")
            except Exception as e:
                pytest.fail(f"Large input caused crash: {e}")
                
            args, _ = mock_call.call_args
            assert len(args[0]) > 10000
