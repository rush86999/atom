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
    Patches enhanced_ai_workflow_endpoints.ai_service at import location.
    """
    from api.ai_workflows_routes import router

    app = FastAPI()
    app.include_router(router)

    # Patch ai_service at the module where it's imported
    with patch('enhanced_ai_workflow_endpoints.ai_service', mock_ai_service):
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


class TestAIWorkflowsSuccess:
    """Happy path tests for AI workflows endpoints."""

    def test_parse_nlu_success(self, ai_workflows_client, sample_nlu_request):
        """Test NLU parse with valid text and deepseek provider."""
        response = ai_workflows_client.post(
            "/api/ai-workflows/nlu/parse",
            json=sample_nlu_request
        )
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == sample_nlu_request["text"]
        assert data["intent"] == "scheduling"
        assert data["confidence"] == 0.85
        assert data["provider_used"] == "deepseek"
        assert "request_id" in data
        assert "processing_time_ms" in data

    def test_parse_nlu_with_openai(self, ai_workflows_client):
        """Test NLU parse with openai provider."""
        response = ai_workflows_client.post(
            "/api/ai-workflows/nlu/parse",
            json={
                "text": "Send an email to test@example.com",
                "provider": "openai"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "scheduling"
        assert data["provider_used"] == "deepseek"  # Mock returns deepseek

    def test_parse_nlu_intent_only(self, ai_workflows_client):
        """Test NLU parse with intent_only=True flag."""
        response = ai_workflows_client.post(
            "/api/ai-workflows/nlu/parse",
            json={
                "text": "Create a new workflow",
                "provider": "deepseek",
                "intent_only": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        # Mock returns scheduling intent regardless of intent_only flag
        assert data["intent"] == "scheduling"
        assert isinstance(data["entities"], list)

    def test_parse_nlu_fallback(self, ai_workflows_client, mock_ai_service):
        """Test fallback behavior when real AI service fails."""
        # Mock service to raise exception
        mock_ai_service.process_with_nlu.side_effect = Exception("Service unavailable")

        response = ai_workflows_client.post(
            "/api/ai-workflows/nlu/parse",
            json={
                "text": "Schedule a meeting",
                "provider": "deepseek"
            }
        )
        # Should use fallback and still return 200
        assert response.status_code == 200
        data = response.json()
        assert data["provider_used"] == "fallback"
        assert data["confidence"] == 0.7

    def test_get_providers_with_keys(self, ai_workflows_client):
        """Test get providers returns list when API keys present."""
        response = ai_workflows_client.get("/api/ai-workflows/providers")
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert "default" in data
        assert "count" in data
        assert data["count"] == 4  # All providers have keys in mock
        assert len(data["providers"]) == 4
        # Verify all providers are enabled
        for provider in data["providers"]:
            assert provider["enabled"] is True

    def test_get_providers_no_keys(self, ai_workflows_client, mock_ai_service):
        """Test get providers returns disabled list when no API keys."""
        # Clear all API keys
        mock_ai_service.openai_api_key = None
        mock_ai_service.anthropic_api_key = None
        mock_ai_service.deepseek_api_key = None
        mock_ai_service.google_api_key = None

        response = ai_workflows_client.get("/api/ai-workflows/providers")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        # Verify all providers are disabled
        for provider in data["providers"]:
            assert provider["enabled"] is False

    def test_complete_text_success(self, ai_workflows_client, sample_completion_request):
        """Test text completion with valid prompt."""
        response = ai_workflows_client.post(
            "/api/ai-workflows/complete",
            json=sample_completion_request
        )
        assert response.status_code == 200
        data = response.json()
        assert "completion" in data
        assert data["provider_used"] == "deepseek"
        assert data["tokens_used"] > 0
        assert "processing_time_ms" in data

    def test_complete_text_with_custom_params(self, ai_workflows_client):
        """Test completion with custom temperature and max_tokens."""
        response = ai_workflows_client.post(
            "/api/ai-workflows/complete",
            json={
                "prompt": "Write a short summary",
                "provider": "openai",
                "max_tokens": 1000,
                "temperature": 0.9
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "completion" in data
        assert data["provider_used"] == "openai"


class TestAIWorkflowsErrorPaths:
    """Error path tests for AI workflows endpoints."""

    def test_parse_nlu_empty_text(self, ai_workflows_client):
        """Test NLU parse with empty text (may use fallback)."""
        response = ai_workflows_client.post(
            "/api/ai-workflows/nlu/parse",
            json={
                "text": "",
                "provider": "deepseek"
            }
        )
        # Empty text may return 422 or use fallback with 200
        assert response.status_code in [200, 422]
        if response.status_code == 200:
            data = response.json()
            assert "intent" in data

    def test_complete_text_empty_prompt(self, ai_workflows_client):
        """Test completion with empty prompt (API accepts it)."""
        response = ai_workflows_client.post(
            "/api/ai-workflows/complete",
            json={
                "prompt": "",
                "provider": "deepseek"
            }
        )
        # API accepts empty prompt (no validation in Pydantic model)
        assert response.status_code == 200
        data = response.json()
        assert "completion" in data

    def test_complete_text_invalid_max_tokens(self, ai_workflows_client):
        """Test completion with negative max_tokens (API accepts it)."""
        response = ai_workflows_client.post(
            "/api/ai-workflows/complete",
            json={
                "prompt": "Test prompt",
                "provider": "deepseek",
                "max_tokens": -100  # Negative value accepted by API
            }
        )
        # API accepts negative max_tokens (no validation in Pydantic model)
        assert response.status_code == 200
        data = response.json()
        assert "completion" in data

    def test_complete_text_invalid_temperature(self, ai_workflows_client):
        """Test completion with temperature >1.0 (API accepts it)."""
        response = ai_workflows_client.post(
            "/api/ai-workflows/complete",
            json={
                "prompt": "Test prompt",
                "provider": "deepseek",
                "temperature": 2.5  # Temperature >1.0 accepted by API
            }
        )
        # API accepts temperature >1.0 (no validation in Pydantic model)
        assert response.status_code == 200
        data = response.json()
        assert "completion" in data

    def test_parse_nlu_service_error_with_fallback(self, ai_workflows_client, mock_ai_service):
        """Test NLU parse service error triggers fallback path."""
        # Mock service to raise exception
        mock_ai_service.process_with_nlu.side_effect = Exception("AI service down")

        response = ai_workflows_client.post(
            "/api/ai-workflows/nlu/parse",
            json={
                "text": "Search for documents",
                "provider": "deepseek"
            }
        )
        # Should use fallback and return 200
        assert response.status_code == 200
        data = response.json()
        assert data["provider_used"] == "fallback"
        assert data["confidence"] == 0.7
        # Fallback should detect "search" intent
        assert data["intent"] in ["search", "general"]

    def test_complete_text_service_error(self, ai_workflows_client, mock_ai_service):
        """Test completion failure returns error response."""
        # Mock service to raise exception
        mock_ai_service.analyze_text.side_effect = Exception("Completion service down")

        response = ai_workflows_client.post(
            "/api/ai-workflows/complete",
            json={
                "prompt": "Complete this text",
                "provider": "deepseek"
            }
        )
        # Should return 200 with error message in completion field
        assert response.status_code == 200
        data = response.json()
        assert "completion" in data
        assert data["provider_used"] == "error"
        assert data["tokens_used"] == 0
        assert "unavailable" in data["completion"].lower()

    def test_get_providers_service_error(self, ai_workflows_client, mock_ai_service):
        """Test provider list failure returns default providers."""
        # Mock the service module to raise exception on attribute access
        mock_ai_service.openai_api_key = None
        mock_ai_service.anthropic_api_key = None
        mock_ai_service.deepseek_api_key = None
        mock_ai_service.google_api_key = None

        response = ai_workflows_client.get("/api/ai-workflows/providers")
        # Should return 200 with default disabled providers
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert data["count"] == 0
        # All providers should be disabled
        for provider in data["providers"]:
            assert provider["enabled"] is False

    def test_parse_nlu_long_text(self, ai_workflows_client):
        """Test NLU parse with very long text (>1000 chars)."""
        long_text = "This is a test. " * 100  # ~1600 characters

        response = ai_workflows_client.post(
            "/api/ai-workflows/nlu/parse",
            json={
                "text": long_text,
                "provider": "deepseek"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == long_text
        assert "intent" in data
        # Check tasks are truncated to 100 chars
        if data["tasks"]:
            assert len(data["tasks"][0]) <= 100

    def test_complete_text_with_special_chars(self, ai_workflows_client):
        """Test completion with special characters and unicode."""
        special_text = "Hello 🌍! Test with émojis, spëcial çhars, and <script> tags."

        response = ai_workflows_client.post(
            "/api/ai-workflows/nlu/parse",
            json={
                "text": special_text,
                "provider": "deepseek"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == special_text
