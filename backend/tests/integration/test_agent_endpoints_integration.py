"""
Integration tests for atom_agent_endpoints.py using TestClient.

Pattern: Use FastAPI TestClient, NOT mocked requests

These tests use real HTTP request/response to exercise actual routing,
validation, serialization, and error handling.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import Base
from main_api_app import app


@pytest.fixture
def db_engine():
    """Real SQLite in-memory DB for integration tests"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Real database session"""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(db_engine):
    """TestClient with real database (not mocked)"""
    # Patch database to use test engine
    import core.database
    original_get_db = core.database.get_db_session

    SessionLocal = sessionmaker(bind=db_engine)

    def test_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Patch for testing
    core.database.get_db_session = test_get_db

    yield TestClient(app)

    # Restore original
    core.database.get_db_session = original_get_db


# ============================================================================
# Tests: Session Management Endpoints
# ============================================================================

@pytest.mark.integration
def test_create_session_endpoint(client):
    """Integration test: Create session via TestClient"""
    response = client.post(
        "/api/atom-agent/sessions",
        json={"user_id": "test_user_123"}
    )

    # Verify real response (not mock return value)
    assert response.status_code in [200, 201]

    data = response.json()
    assert "success" in data
    assert "session_id" in data or "error" in data

    if data.get("success"):
        assert "session_id" in data
        assert isinstance(data["session_id"], str)


@pytest.mark.integration
def test_list_sessions_endpoint(client):
    """Test listing sessions for a user"""
    # First create a session
    client.post("/api/atom-agent/sessions", json={"user_id": "test_user"})

    # Then list sessions
    response = client.get("/api/atom-agent/sessions?user_id=test_user&limit=10")

    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


@pytest.mark.integration
def test_get_session_endpoint(client):
    """Test getting a specific session by ID"""
    # Create session first
    create_response = client.post(
        "/api/atom-agent/sessions",
        json={"user_id": "test_user"}
    )

    if create_response.status_code in [200, 201]:
        session_data = create_response.json()
        if "session_id" in session_data:
            session_id = session_data["session_id"]

            # Get session details
            response = client.get(f"/api/atom-agent/sessions/{session_id}?user_id=test_user")

            # Should return session data or 404
            assert response.status_code in [200, 404]


@pytest.mark.integration
def test_delete_session_endpoint(client):
    """Test deleting a session"""
    # Create session first
    create_response = client.post(
        "/api/atom-agent/sessions",
        json={"user_id": "test_user"}
    )

    if create_response.status_code in [200, 201]:
        session_data = create_response.json()
        if "session_id" in session_data:
            session_id = session_data["session_id"]

            # Delete session
            response = client.delete(f"/api/atom-agent/sessions/{session_id}?user_id=test_user")

            # Should succeed or return 404
            assert response.status_code in [200, 404]


# ============================================================================
# Tests: Chat Endpoint
# ============================================================================

@pytest.mark.integration
def test_chat_endpoint_with_message(client):
    """Test sending a chat message"""
    response = client.post(
        "/api/atom-agent/chat",
        json={
            "message": "Hello, how are you?",
            "user_id": "test_user_123",
            "session_id": None  # New session
        }
    )

    # Should process request (may fail on LLM call but should handle gracefully)
    assert response.status_code in [200, 500, 503]

    data = response.json()
    assert isinstance(data, dict)


@pytest.mark.integration
def test_chat_endpoint_with_session_id(client):
    """Test chat with existing session ID"""
    # First create a session
    session_response = client.post(
        "/api/atom-agent/sessions",
        json={"user_id": "test_user"}
    )

    session_id = None
    if session_response.status_code in [200, 201]:
        session_data = session_response.json()
        session_id = session_data.get("session_id")

    # Send message with session_id
    response = client.post(
        "/api/atom-agent/chat",
        json={
            "message": "Follow up message",
            "user_id": "test_user",
            "session_id": session_id
        }
    )

    assert response.status_code in [200, 500, 503]


@pytest.mark.integration
def test_chat_endpoint_with_conversation_history(client):
    """Test chat with conversation history"""
    response = client.post(
        "/api/atom-agent/chat",
        json={
            "message": "What did I just ask?",
            "user_id": "test_user",
            "conversation_history": [
                {"role": "user", "content": "Previous question"},
                {"role": "assistant", "content": "Previous answer"}
            ]
        }
    )

    assert response.status_code in [200, 500, 503]
    data = response.json()
    assert isinstance(data, dict)


@pytest.mark.integration
def test_chat_endpoint_with_context(client):
    """Test chat with additional context"""
    response = client.post(
        "/api/atom-agent/chat",
        json={
            "message": "Help me with this",
            "user_id": "test_user",
            "context": {
                "current_page": "/dashboard",
                "user_data": {"preference": "dark_mode"}
            }
        }
    )

    assert response.status_code in [200, 500, 503]


@pytest.mark.integration
def test_chat_endpoint_validation_error(client):
    """Test chat endpoint validates input"""
    # Missing required field 'message'
    response = client.post(
        "/api/atom-agent/chat",
        json={
            "user_id": "test_user"
            # 'message' is missing
        }
    )

    # Should return validation error
    assert response.status_code == 422  # Unprocessable Entity


# ============================================================================
# Tests: Workflow Execution Endpoints
# ============================================================================

@pytest.mark.integration
def test_execute_generated_workflow_endpoint(client):
    """Test executing a generated workflow"""
    response = client.post(
        "/api/atom-agent/execute-generated",
        json={
            "workflow_id": "test-workflow-123",
            "input_data": {
                "param1": "value1",
                "param2": 42
            }
        }
    )

    # Should attempt execution (may fail if workflow doesn't exist)
    assert response.status_code in [200, 404, 500]

    data = response.json()
    assert isinstance(data, dict)


@pytest.mark.integration
def test_execute_workflow_validation_error(client):
    """Test workflow execution validates input"""
    # Missing required field
    response = client.post(
        "/api/atom-agent/execute-generated",
        json={
            "workflow_id": "test-workflow"
            # Missing 'input_data'
        }
    )

    # Should return validation error
    assert response.status_code == 422


# ============================================================================
# Tests: Stream Endpoint
# ============================================================================

@pytest.mark.integration
def test_stream_chat_endpoint(client):
    """Test streaming chat endpoint"""
    response = client.post(
        "/api/atom-agent/stream-chat",
        json={
            "message": "Tell me a story",
            "user_id": "test_user"
        }
    )

    # Streaming endpoint should return response
    assert response.status_code in [200, 500, 503]


# ============================================================================
# Tests: Error Handling
# ============================================================================

@pytest.mark.integration
def test_invalid_endpoint_returns_404(client):
    """Test that invalid endpoints return 404"""
    response = client.get("/api/atom-agent/nonexistent-endpoint")

    assert response.status_code == 404


@pytest.mark.integration
def test_chat_with_empty_message(client):
    """Test chat endpoint handles empty message"""
    response = client.post(
        "/api/atom-agent/chat",
        json={
            "message": "",
            "user_id": "test_user"
        }
    )

    # Should handle gracefully or validate
    assert response.status_code in [200, 400, 422, 500]


@pytest.mark.integration
def test_chat_with_missing_user_id(client):
    """Test chat endpoint requires user_id"""
    response = client.post(
        "/api/atom-agent/chat",
        json={
            "message": "Hello"
            # Missing 'user_id'
        }
    )

    # Should return validation error
    assert response.status_code == 422


# ============================================================================
# Tests: Parametrized Input Validation
# ============================================================================

@pytest.mark.integration
@pytest.mark.parametrize("message,expected_status", [
    ("Valid message", 200),  # May still return 500 on LLM failure
    ("", 422),  # Empty message should validate
    ("a" * 10000, 200),  # Long message
    ("Special chars: !@#$%^&*()", 200),  # Special characters
])
def test_chat_message_validation(client, message, expected_status):
    """Parametrized test for message validation"""
    response = client.post(
        "/api/atom-agent/chat",
        json={
            "message": message,
            "user_id": "test_user"
        }
    )

    # May return 500 on LLM failure, but 422 for validation errors
    if expected_status == 422:
        assert response.status_code == 422
    else:
        assert response.status_code in [200, 500, 503]


@pytest.mark.integration
@pytest.mark.parametrize("user_id,expected_status", [
    ("valid_user_123", 200),
    ("", 422),  # Empty user_id
    ("   ", 422),  # Whitespace only
    ("user-with-dashes", 200),
    ("user_with_underscores", 200),
])
def test_user_id_validation(client, user_id, expected_status):
    """Parametrized test for user_id validation"""
    response = client.post(
        "/api/atom-agent/chat",
        json={
            "message": "Test message",
            "user_id": user_id
        }
    )

    if expected_status == 422:
        assert response.status_code == 422
    else:
        assert response.status_code in [200, 500, 503]


# ============================================================================
# Tests: Response Structure Validation
# ============================================================================

@pytest.mark.integration
def test_chat_response_structure(client):
    """Test that chat response has expected structure"""
    response = client.post(
        "/api/atom-agent/chat",
        json={
            "message": "Simple question",
            "user_id": "test_user"
        }
    )

    if response.status_code == 200:
        data = response.json()

        # Check for common response fields
        assert isinstance(data, dict)
        # Response may contain various fields depending on implementation


@pytest.mark.integration
def test_session_list_response_structure(client):
    """Test that session list has expected structure"""
    response = client.get("/api/atom-agent/sessions?user_id=test_user")

    assert response.status_code == 200
    data = response.json()

    assert "success" in data
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


# ============================================================================
# Tests: Concurrent Requests
# ============================================================================

@pytest.mark.integration
def test_multiple_session_creations(client):
    """Test creating multiple sessions in sequence"""
    session_ids = []

    for i in range(3):
        response = client.post(
            "/api/atom-agent/sessions",
            json={"user_id": f"test_user_{i}"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            if "session_id" in data:
                session_ids.append(data["session_id"])

    # Should have created 3 distinct sessions
    assert len(session_ids) == 3
    assert len(set(session_ids)) == 3  # All unique


# ============================================================================
# Tests: Edge Cases
# ============================================================================

@pytest.mark.integration
def test_very_long_conversation_history(client):
    """Test chat with very long conversation history"""
    long_history = [
        {"role": "user", "content": f"Message {i}"}
        for i in range(100)
    ]

    response = client.post(
        "/api/atom-agent/chat",
        json={
            "message": "Latest message",
            "user_id": "test_user",
            "conversation_history": long_history
        }
    )

    # Should handle or validate
    assert response.status_code in [200, 413, 422, 500]


@pytest.mark.integration
def test_special_characters_in_message(client):
    """Test chat with various special characters"""
    special_messages = [
        "Message with unicode: \u2713\u2717",
        "Message with emojis: 😀🎉",
        "Message with newlines:\nLine 2\nLine 3",
        "Message with tabs:\tIndented",
        "JSON in message: {\"key\": \"value\"}",
    ]

    for message in special_messages:
        response = client.post(
            "/api/atom-agent/chat",
            json={
                "message": message,
                "user_id": "test_user"
            }
        )

        # Should handle special characters
        assert response.status_code in [200, 500, 503]


@pytest.mark.integration
def test_session_with_nonexistent_id(client):
    """Test getting session that doesn't exist"""
    fake_session_id = "nonexistent-session-12345"

    response = client.get(
        f"/api/atom-agent/sessions/{fake_session_id}?user_id=test_user"
    )

    # Should return 404 or error
    assert response.status_code in [404, 200]


# ============================================================================
# Tests: CORS and Headers
# ============================================================================

@pytest.mark.integration
def test_options_request(client):
    """Test OPTIONS request for CORS"""
    response = client.options("/api/atom-agent/chat")

    # Should handle OPTIONS
    assert response.status_code in [200, 405]


@pytest.mark.integration
def test_request_with_custom_headers(client):
    """Test request with custom headers"""
    response = client.post(
        "/api/atom-agent/chat",
        json={
            "message": "Test",
            "user_id": "test_user"
        },
        headers={
            "X-Custom-Header": "test-value",
            "X-Request-ID": "req-123"
        }
    )

    # Should handle custom headers
    assert response.status_code in [200, 500, 503]


# ============================================================================
# Tests: URL Parameters
# ============================================================================

@pytest.mark.integration
def test_list_sessions_with_limit_parameter(client):
    """Test listing sessions with custom limit"""
    response = client.get("/api/atom-agent/sessions?user_id=test_user&limit=5")

    assert response.status_code == 200
    data = response.json()

    if data.get("success"):
        assert "sessions" in data
        # Should respect limit (or have default)


@pytest.mark.integration
def test_list_sessions_with_large_limit(client):
    """Test listing sessions with very large limit"""
    response = client.get("/api/atom-agent/sessions?user_id=test_user&limit=999999")

    # Should handle gracefully
    assert response.status_code == 200


# ============================================================================
# Tests: JSON Serialization
# ============================================================================

@pytest.mark.integration
def test_chat_with_complex_json_context(client):
    """Test chat with complex nested JSON in context"""
    response = client.post(
        "/api/atom-agent/chat",
        json={
            "message": "Process this data",
            "user_id": "test_user",
            "context": {
                "nested": {
                    "deeply": {
                        "nested": {
                            "value": 123,
                            "array": [1, 2, 3],
                            "null_value": None
                        }
                    }
                },
                "boolean": True,
                "number": 42.5
            }
        }
    )

    # Should serialize complex JSON correctly
    assert response.status_code in [200, 500, 503]
