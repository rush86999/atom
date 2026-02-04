"""
Test AI Enhanced Routes - FastAPI Migration

Tests that AI enhanced API routes:
- Use FastAPI (not Flask)
- Have proper Pydantic request models
- Validate input parameters
- Return structured responses
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from pydantic import ValidationError
from fastapi import FastAPI

from core.models import AgentRegistry, AgentStatus, User


# Create test app with AI router
from integrations.ai_enhanced_api_routes import router as ai_router

app = FastAPI()
app.include_router(ai_router)


@pytest.fixture
def client():
    """Get test client"""
    return TestClient(app)


class TestAIEnhancedHealth:
    """Test AI enhanced health check endpoint"""

    def test_health_check_endpoint_exists(self, client: TestClient):
        """Health check endpoint should exist and respond"""
        response = client.post("/api/integrations/ai/enhanced_health")

        # Should return 200 (FastAPI style, not Flask)
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "timestamp" in data
        assert "service" in data

    def test_health_check_returns_service_status(self, client: TestClient):
        """Health check should return service availability"""
        response = client.post("/api/integrations/ai/enhanced_health")

        data = response.json()
        # Health check may fail validation if env vars not set, but should still return valid structure
        assert "ok" in data or "detail" in data  # Either success or error response
        if "ok" in data and data["ok"]:
            assert "data" in data
            assert "services" in data["data"]
            assert "status" in data["data"]


class TestAnalyzeMessageEndpoint:
    """Test /analyze_message endpoint"""

    def test_analyze_message_requires_content(self, client: TestClient):
        """Should reject requests without content"""
        response = client.post("/api/integrations/ai/analyze_message", json={
            "platform": "slack"
        })

        # FastAPI validates with Pydantic - should return 422
        assert response.status_code == 422

    def test_analyze_message_with_valid_data(self, client: TestClient):
        """Should analyze message with valid data"""
        response = client.post("/api/integrations/ai/analyze_message", json={
            "content": "This is a test message",
            "platform": "slack",
            "user_id": "test_user"
        })

        # Should succeed
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "analysis" in data["data"]

    def test_analyze_message_returns_structured_response(self, client: TestClient):
        """Should return properly structured response"""
        response = client.post("/api/integrations/ai/analyze_message", json={
            "content": "Test message for sentiment analysis",
            "platform": "slack",
            "user_id": "test_user",
            "analysis_types": ["sentiment", "topics"]
        })

        data = response.json()
        assert "ok" in data
        assert "timestamp" in data
        assert "data" in data
        assert "analysis" in data["data"]
        assert "confidence" in data["data"]


class TestIntelligentSearchEndpoint:
    """Test /intelligent_search endpoint"""

    def test_intelligent_search_requires_query(self, client: TestClient):
        """Should reject requests without query"""
        response = client.post("/api/integrations/ai/intelligent_search", json={
            "user_id": "test_user"
        })

        # FastAPI validates with Pydantic - should return 422
        assert response.status_code == 422

    def test_intelligent_search_with_valid_query(self, client: TestClient):
        """Should perform search with valid query"""
        response = client.post("/api/integrations/ai/intelligent_search", json={
            "query": "test search query",
            "user_id": "test_user",
            "limit": 10
        })

        # Should succeed
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "results" in data["data"]


class TestConversationEndpoints:
    """Test conversation management endpoints"""

    def test_start_conversation_requires_user_and_platform(self, client: TestClient):
        """Should reject requests without user_id and platform"""
        response = client.post("/api/integrations/ai/conversation/start", json={
            "workspace_id": "test_workspace"
        })

        # FastAPI validates with Pydantic - should return 422
        assert response.status_code == 422

    def test_start_conversation_with_valid_data(self, client: TestClient):
        """Should start conversation with valid data"""
        response = client.post("/api/integrations/ai/conversation/start", json={
            "user_id": "test_user",
            "platform": "slack"
        })

        # Should succeed
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "conversation_id" in data["data"]

    def test_continue_conversation_requires_conversation_id(self, client: TestClient):
        """Should reject requests without conversation_id"""
        response = client.post("/api/integrations/ai/conversation/continue", json={
            "message": "Hello",
            "user_id": "test_user"
        })

        # FastAPI validates with Pydantic - should return 422
        assert response.status_code == 422


class TestContentGenerationEndpoints:
    """Test content generation endpoints"""

    def test_generate_content_requires_content_request(self, client: TestClient):
        """Should reject requests without content_request"""
        response = client.post("/api/integrations/ai/content/generate", json={
            "user_id": "test_user"
        })

        # FastAPI validates with Pydantic - should return 422
        assert response.status_code == 422

    def test_generate_content_with_valid_data(self, client: TestClient):
        """Should generate content with valid data"""
        response = client.post("/api/integrations/ai/content/generate", json={
            "content_request": {
                "type": "message",
                "topic": "test topic"
            },
            "user_id": "test_user"
        })

        # Should succeed
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "generated_content" in data["data"]

    def test_enhance_content_requires_content(self, client: TestClient):
        """Should reject requests without content"""
        response = client.post("/api/integrations/ai/content/enhance", json={
            "user_id": "test_user"
        })

        # FastAPI validates with Pydantic - should return 422
        assert response.status_code == 422


class TestAnalyticsEndpoints:
    """Test analytics endpoints"""

    def test_performance_metrics_returns_metrics(self, client: TestClient):
        """Should return performance metrics"""
        response = client.post("/api/integrations/ai/analytics/performance", json={
            "include_detailed": False
        })

        # Should succeed
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "performance_metrics" in data["data"]


class TestFastAPIValidation:
    """Test that FastAPI validation is working"""

    def test_invalid_model_type_rejected(self, client: TestClient):
        """Should reject invalid model types"""
        response = client.post("/api/integrations/ai/analyze_message", json={
            "content": "test",
            "platform": "slack",
            "user_id": "test_user",
            "model_type": "invalid_model_type"
        })

        # Our validation should catch this
        # Either Pydantic validation (422) or our custom validation (400)
        assert response.status_code in [400, 422]

    def test_invalid_service_type_rejected(self, client: TestClient):
        """Should reject invalid service types"""
        response = client.post("/api/integrations/ai/analyze_message", json={
            "content": "test",
            "platform": "slack",
            "user_id": "test_user",
            "service_type": "invalid_service"
        })

        # Our validation should catch this
        # Either Pydantic validation (422) or our custom validation (400)
        assert response.status_code in [400, 422]


class TestResponseStructure:
    """Test that all responses follow standard structure"""

    def test_all_responses_have_ok_field(self, client: TestClient):
        """All successful responses should have 'ok' field"""
        endpoints = [
            ("/api/integrations/ai/enhanced_health", "POST", {}),
            ("/api/integrations/ai/analyze_message", "POST", {
                "content": "test",
                "platform": "slack",
                "user_id": "test"
            }),
        ]

        for endpoint, method, payload in endpoints:
            if method == "POST":
                response = client.post(endpoint, json=payload)
            else:
                response = client.get(endpoint)

            if response.status_code == 200:
                data = response.json()
                assert "ok" in data, f"Missing 'ok' field in response from {endpoint}"

    def test_all_responses_have_timestamp(self, client: TestClient):
        """All responses should have timestamp"""
        response = client.post("/api/integrations/ai/enhanced_health")

        if response.status_code == 200:
            data = response.json()
            assert "timestamp" in data

    def test_error_responses_have_error_field(self, client: TestClient):
        """Error responses should have error field"""
        response = client.post("/api/integrations/ai/analyze_message", json={
            "platform": "slack"
        })

        # Should get validation error
        if response.status_code in [400, 422, 500]:
            data = response.json()
            # FastAPI validation errors have 'detail', our custom errors have 'error'
            assert "detail" in data or "error" in data


def test_ai_enhanced_routes_use_fastapi():
    """Verify that AI enhanced routes are using FastAPI, not Flask"""

    # Import the router and check it's an APIRouter
    try:
        from integrations.ai_enhanced_api_routes import router
        from fastapi.routing import APIRouter

        assert isinstance(router, APIRouter), "AI enhanced routes should use FastAPI APIRouter"
        assert router.prefix == "/api/integrations/ai", "Router should have correct prefix"
    except ImportError:
        pytest.fail("Could not import ai_enhanced_api_routes")


def test_pydantic_models_exist():
    """Verify that Pydantic models are defined for request validation"""

    try:
        from integrations.ai_enhanced_api_routes import (
            AnalyzeMessageRequest,
            SummarizeMessagesRequest,
            IntelligentSearchRequest,
            StartConversationRequest
        )

        # Check that they are Pydantic models
        from pydantic import BaseModel
        assert issubclass(AnalyzeMessageRequest, BaseModel)
        assert issubclass(SummarizeMessagesRequest, BaseModel)
        assert issubclass(IntelligentSearchRequest, BaseModel)
        assert issubclass(StartConversationRequest, BaseModel)
    except ImportError as e:
        pytest.fail(f"Could not import Pydantic models: {e}")


class TestFeatureFlags:
    """Test feature flag behavior"""

    def test_ai_enhanced_flag_exists(self):
        """Verify AI_ENHANCED_ENABLED feature flag exists"""
        from integrations.ai_enhanced_api_routes import AI_ENHANCED_ENABLED

        # Should be a boolean
        assert isinstance(AI_ENHANCED_ENABLED, bool)
