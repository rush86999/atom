import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Ensure backend module is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock external dependencies globally for grey-box tests"""
    with patch('core.byok_endpoints.get_byok_manager') as mock_byok_get:
        mock_byok_manager = MagicMock()
        mock_byok_manager.get_api_key.return_value = "sk-mock-key"
        mock_byok_get.return_value = mock_byok_manager
        
        with patch('dotenv.load_dotenv'):
            yield

@pytest.fixture
def mock_ai_service():
    """Mock the RealAIWorkflowService to avoid real API calls"""
    # This fixture mocks the CLASS itself if requested, but some tests instantiate the class.
    # The autouse mock_dependencies handles the init logic.
    with patch('enhanced_ai_workflow_endpoints.RealAIWorkflowService') as MockService:
        service = MockService.return_value
        
        # Default successful responses
        service.call_openai_api = AsyncMock(return_value={
            'content': '{"intent": "test", "tasks": ["task1"]}',
            'confidence': 0.9,
            'token_usage': {},
            'provider': 'openai'
        })
        service.call_deepseek_api = AsyncMock(return_value={
            'content': '{"intent": "test", "tasks": ["task1"]}',
            'confidence': 0.9,
            'token_usage': {},
            'provider': 'deepseek'
        })
        
        yield service

@pytest.fixture
def mock_http_clients():
    """Mock aiohttp/httpx clients to intercept external tool calls"""
    with patch('aiohttp.ClientSession.post') as mock_post:
        yield mock_post

@pytest.fixture
def mock_env_vars():
    """Set dummy API keys for testing"""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "sk-dummy",
        "DEEPSEEK_API_KEY": "sk-dummy",
        "ANTHROPIC_API_KEY": "sk-dummy"
    }):
        yield
