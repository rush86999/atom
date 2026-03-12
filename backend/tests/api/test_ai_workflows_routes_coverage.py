"""
AI Workflows Routes Test Coverage

Target: api/ai_workflows_routes.py (182 lines, 3 endpoints)
Goal: 75%+ line coverage with TestClient-based integration tests

Endpoints Covered:
- POST /api/ai-workflows/nlu/parse - Natural language understanding
- GET /api/ai-workflows/providers - List available AI providers
- POST /api/ai-workflows/complete - Text completion generation
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI


@pytest.fixture
def mock_ai_service():
    """
    Mock AI service for enhanced_ai_workflow_endpoints.ai_service.
    Provides AsyncMock methods for NLU and completion operations.
    """
    mock = MagicMock()
    mock.process_with_nlu = AsyncMock(return_value={
        'intent': 'scheduling',
        'entities': [{'type': 'email', 'value': 'user@example.com'}],
        'confidence': 0.85,
        'ai_provider_used': 'deepseek'
    })
    mock.analyze_text = AsyncMock(return_value="This is a sample completion response.")
    mock.openai_api_key = "sk-test-openai"
    mock.anthropic_api_key = "sk-test-anthropic"
    mock.deepseek_api_key = "sk-test-deepseek"
    mock.google_api_key = "test-google-key"
    return mock


@pytest.fixture
def ai_workflows_client(mock_ai_service):
    """
    TestClient with isolated FastAPI app for AI workflows routes.
    Uses per-file app pattern to avoid SQLAlchemy metadata conflicts.
    """
    from api.ai_workflows_routes import router

    app = FastAPI()
    app.include_router(router)

    # Patch ai_service at module level
    with patch('api.ai_workflows_routes.ai_service', mock_ai_service):
        yield TestClient(app)


@pytest.fixture
def sample_nlu_request():
    """Factory for valid NLUParseRequest data."""
    return {
        "text": "Schedule a meeting with user@example.com",
        "provider": "deepseek",
        "intent_only": False
    }


@pytest.fixture
def sample_completion_request():
    """Factory for valid CompletionRequest data."""
    return {
        "prompt": "Complete this text for me",
        "provider": "deepseek",
        "max_tokens": 500,
        "temperature": 0.7
    }


@pytest.fixture
def nlu_parse_response_data():
    """Expected NLU parse response structure."""
    return {
        "request_id": "nlu_20260312_123456",
        "text": "Schedule a meeting",
        "intent": "scheduling",
        "entities": [{"type": "email", "value": "user@example.com"}],
        "tasks": ["Process: Schedule a meeting"],
        "confidence": 0.85,
        "provider_used": "deepseek",
        "processing_time_ms": 50.0
    }


@pytest.fixture
def completion_response_data():
    """Expected completion response structure."""
    return {
        "completion": "This is a sample completion response.",
        "provider_used": "deepseek",
        "tokens_used": 10,
        "processing_time_ms": 100.0
    }
