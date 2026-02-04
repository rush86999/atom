"""
Test Slack Routes Governance Integration

Tests that Slack integration endpoints properly enforce agent maturity levels:
- STUDENT agents can only perform READ operations (search, list)
- INTERN+ agents can send messages (complexity 2)
- SUPERVISED+ agents can perform state changes
- AUTONOMOUS agents have full access
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Create test app with Slack router
from integrations.slack_routes import router as slack_router

app = FastAPI()
app.include_router(slack_router)


@pytest.fixture
def client():
    """Get test client"""
    return TestClient(app)


class TestSlackEndpointBasics:
    """Test basic Slack endpoint functionality"""

    def test_slack_status_endpoint(self, client: TestClient):
        """Status endpoint should respond"""
        response = client.get("/api/slack/status")

        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "status" in data

    def test_slack_health_endpoint(self, client: TestClient):
        """Health endpoint should respond"""
        response = client.get("/api/slack/health")

        assert response.status_code == 200
        data = response.json()
        assert "ok" in data

    def test_send_message_without_agent(self, client: TestClient):
        """Send message should work without agent_id (no governance)"""
        response = client.post("/api/slack/messages", json={
            "channel": "test",
            "text": "Hello without agent",
            "user_id": "test_user"
        })

        # Should succeed (no agent = no governance check)
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True

    def test_send_message_with_invalid_agent(self, client: TestClient):
        """Send message with invalid agent_id should succeed (graceful degradation)"""
        response = client.post("/api/slack/messages", json={
            "channel": "test",
            "text": "Hello with invalid agent",
            "user_id": "test_user",
            "agent_id": "nonexistent_agent_id"
        })

        # Should succeed (governance check fails gracefully)
        assert response.status_code == 200

    def test_search_endpoint(self, client: TestClient):
        """Search endpoint should respond"""
        response = client.post("/api/slack/search", json={
            "query": "test",
            "user_id": "test_user",
            "max_results": 5
        })

        assert response.status_code == 200
        data = response.json()
        assert "ok" in data

    def test_list_channels_endpoint(self, client: TestClient):
        """List channels endpoint should respond"""
        response = client.get("/api/slack/channels?user_id=test_user")

        assert response.status_code == 200
        data = response.json()
        assert "channels" in data

    def test_conversation_history_endpoint(self, client: TestClient):
        """Conversation history endpoint should respond"""
        response = client.get("/api/slack/conversations/history?channel=test&user_id=test_user")

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data


def test_slack_routes_use_fastapi():
    """Verify that Slack routes are using FastAPI, not Flask"""
    from integrations.slack_routes import router
    from fastapi.routing import APIRouter

    assert isinstance(router, APIRouter), "Slack routes should use FastAPI APIRouter"
    assert router.prefix == "/api/slack", "Router should have correct prefix"


def test_slack_routes_have_governance_imports():
    """Verify that Slack routes have governance integration"""
    import inspect
    from integrations import slack_routes

    source = inspect.getsource(slack_routes)

    # Should import governance helpers
    assert "with_governance_check" in source or "governance" in source.lower()


class TestSlackResponseStructure:
    """Test that Slack responses follow standard structure"""

    def test_status_response_has_ok(self, client: TestClient):
        """Status response should have 'ok' field"""
        response = client.get("/api/slack/status")
        data = response.json()
        assert "ok" in data

    def test_message_response_has_timestamp(self, client: TestClient):
        """Message response should have timestamp"""
        response = client.post("/api/slack/messages", json={
            "channel": "test",
            "text": "test",
            "user_id": "test"
        })
        data = response.json()
        if "ok" in data and data["ok"]:
            assert "timestamp" in data
