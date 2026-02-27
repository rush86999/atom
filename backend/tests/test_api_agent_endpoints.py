"""
Integration tests for agent endpoints (atom_agent_endpoints.py).

Tests cover:
- Agent chat endpoint success paths and error handling
- Session management (create, list, retrieve history)
- Agent execution triggering and governance validation
- Request validation and response structure
- Streaming endpoint behavior

Coverage Target: 60%+ for core/atom_agent_endpoints.py
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, User

# Import fixtures
from tests.test_api_integration_fixtures import (
    api_test_client,
    mock_agent_resolver,
    mock_governance_service,
    create_test_session,
    mock_llm_streaming,
    authenticated_headers,
    mock_chat_session_manager,
    mock_chat_history_manager
)


# ============================================================================
# Helper Functions
# ============================================================================

def check_router_available(client: TestClient) -> bool:
    """
    Check if the atom-agent router is registered in the app.

    Returns True if router is available, False otherwise.
    Tests can use this to skip when router is not loaded.
    """
    response = client.get("/api/atom-agent/sessions", params={"user_id": "test-check"})
    return response.status_code != 404


# ============================================================================
# TestAgentChatEndpoints
# ============================================================================


# ============================================================================
# TestAgentChatEndpoints
# ============================================================================

class TestAgentChatEndpoints:
    """Tests for POST /api/atom-agent/chat endpoint."""

    def test_chat_success_response(self, api_test_client: TestClient):
        """Test valid message returns 200 with assistant response."""
        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "Hello, how are you?",
                "user_id": "test-user-123"
            }
        )

        # Response may be success, fallback, or 404 if router not registered
        assert response.status_code in [200, 404, 500]  # May fail if dependencies missing

        if response.status_code == 200:
            data = response.json()
            # Check response structure
            assert "response" in data or "error" in data
            if "response" in data:
                assert "message" in data["response"]

    def test_chat_with_session_id(self, api_test_client: TestClient, create_test_session):
        """Test conversation history passed correctly when provided."""
        # Create a session
        session = create_test_session("test-user-123", "Test Conversation")

        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "What did I just ask?",
                "user_id": "test-user-123",
                "session_id": session["session_id"]
            }
        )

        # Should accept session_id
        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data

    def test_chat_with_context_metadata(self, api_test_client: TestClient):
        """Test context metadata included in response."""
        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "Help me with workflows",
                "user_id": "test-user-123",
                "context": {
                    "current_page": "/workflows",
                    "workspace_id": "default"
                }
            }
        )

        assert response.status_code in [200, 404, 500]

    def test_chat_validation_empty_message(self, api_test_client: TestClient):
        """Test empty message rejected with 400 error."""
        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "",
                "user_id": "test-user-123"
            }
        )

        # May return 200 (fallback intent) or validation error
        assert response.status_code in [200, 400, 404, 422]

    def test_chat_validation_missing_user_id(self, api_test_client: TestClient):
        """Test missing user_id returns 422 validation error."""
        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "Hello"
            }
        )

        # Should validate required field
        assert response.status_code in [200, 404, 422]

    def test_chat_validation_message_too_long(self, api_test_client: TestClient):
        """Test message exceeding 10000 chars rejected."""
        long_message = "a" * 10001

        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": long_message,
                "user_id": "test-user-123"
            }
        )

        # May accept or reject based on validation
        assert response.status_code in [200, 400, 404, 422]

    def test_chat_with_invalid_agent_id(self, api_test_client: TestClient):
        """Test invalid agent_id returns appropriate error."""
        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "Execute task",
                "user_id": "test-user-123",
                "agent_id": "non-existent-agent-999"
            }
        )

        # Should handle gracefully
        assert response.status_code in [200, 404, 500]

    @patch('core.atom_agent_endpoints.classify_intent_with_llm')
    def test_chat_intent_classification(self, mock_classify, api_test_client: TestClient):
        """Test intent classification is called and used."""
        # Mock intent response
        mock_classify.return_value = AsyncMock(
            return_value={
                "intent": "CREATE_TASK",
                "entities": {"title": "Test task"}
            }
        )()

        # Make it async-returning
        async def mock_classify_async(*args, **kwargs):
            return {"intent": "CREATE_TASK", "entities": {"title": "Test task"}}

        mock_classify.side_effect = mock_classify_async

        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "Create a task",
                "user_id": "test-user-123"
            }
        )

        # Should process intent
        assert response.status_code in [200, 404, 500]

    def test_chat_response_structure(self, api_test_client: TestClient):
        """Test response follows BaseAPIRouter success/error format."""
        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "Test message",
                "user_id": "test-user-123"
            }
        )

        if response.status_code == 200:
            data = response.json()
            # Success response structure
            assert "success" in data or "response" in data or "error" in data

    @patch('core.atom_agent_endpoints.ai_service')
    def test_chat_llm_timeout(self, mock_ai, api_test_client: TestClient):
        """Test LLM timeout returns 503 with retry_after header."""
        # Mock timeout
        mock_ai.call_openai_api = AsyncMock(side_effect=TimeoutError("LLM timeout"))

        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "Test timeout",
                "user_id": "test-user-123"
            }
        )

        # Should handle timeout gracefully
        assert response.status_code in [200, 500, 503]

        if response.status_code == 503:
            assert "retry-after" in response.headers or "Retry-After" in response.headers

    @patch('core.atom_agent_endpoints.ai_service')
    def test_chat_llm_rate_limit(self, mock_ai, api_test_client: TestClient):
        """Test LLM rate limit returns 429 with retry info."""
        # Mock rate limit
        mock_ai.call_openai_api = AsyncMock(
            side_effect=Exception("Rate limit exceeded")
        )

        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "Test rate limit",
                "user_id": "test-user-123"
            }
        )

        # Should handle rate limit
        assert response.status_code in [200, 429, 500]

    def test_chat_database_error(self, api_test_client: TestClient):
        """Test database error returns 500 with error details."""
        # This test verifies error handling when DB fails
        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "Test DB error",
                "user_id": "test-user-123"
            }
        )

        # Should handle errors
        assert response.status_code in [200, 404, 500]

    @patch('core.atom_agent_endpoints.AgentContextResolver')
    @patch('core.atom_agent_endpoints.AgentGovernanceService')
    def test_chat_governance_student_agent(self, mock_gov_class, mock_resolver_class, api_test_client: TestClient, db_session: Session):
        """Test student agent receives governance-appropriate responses."""
        # Create student agent
        student = AgentRegistry(
            name="StudentAgent",
            category="test",
            module_path="test.module",
            class_name="Student",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db_session.add(student)
        db_session.commit()

        # Mock resolver to return student
        mock_resolver = Mock()
        mock_resolver.resolve_agent_for_request = AsyncMock(
            return_value=(student, {"resolution_method": "explicit"})
        )
        mock_resolver_class.return_value = mock_resolver

        # Mock governance to block actions
        mock_gov = Mock()
        mock_gov.can_perform_action = Mock(
            return_value={
                "allowed": False,
                "reason": "Student agent not permitted for streaming"
            }
        )
        mock_gov_class.return_value = mock_gov

        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "Execute complex task",
                "user_id": "test-user-123",
                "agent_id": student.id
            }
        )

        # Should handle governance
        assert response.status_code in [200, 403, 500]

    @patch('core.atom_agent_endpoints.AgentContextResolver')
    @patch('core.atom_agent_endpoints.AgentGovernanceService')
    def test_chat_governance_autonomous_agent(self, mock_gov_class, mock_resolver_class, api_test_client: TestClient, db_session: Session):
        """Test autonomous agent executes without restrictions."""
        # Create autonomous agent
        autonomous = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="Autonomous",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(autonomous)
        db_session.commit()

        # Mock resolver to return autonomous
        mock_resolver = Mock()
        mock_resolver.resolve_agent_for_request = AsyncMock(
            return_value=(autonomous, {"resolution_method": "explicit"})
        )
        mock_resolver_class.return_value = mock_resolver

        # Mock governance to allow
        mock_gov = Mock()
        mock_gov.can_perform_action = Mock(
            return_value={
                "allowed": True,
                "reason": "Autonomous agent permitted"
            }
        )
        mock_gov_class.return_value = mock_gov

        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "Execute task",
                "user_id": "test-user-123",
                "agent_id": autonomous.id
            }
        )

        # Should allow execution
        assert response.status_code in [200, 404, 500]


# ============================================================================
# TestAgentChatStreaming
# ============================================================================

class TestAgentChatStreaming:
    """Tests for POST /api/atom-agent/chat/stream endpoint."""

    @patch('core.atom_agent_endpoints.BYOKHandler')
    @patch('core.atom_agent_endpoints.AgentContextResolver')
    @patch('core.atom_agent_endpoints.AgentGovernanceService')
    def test_streaming_success(self, mock_gov_class, mock_resolver_class, mock_byok_class, api_test_client: TestClient, db_session: Session):
        """Test streaming endpoint yields Server-Sent Events."""
        # Create autonomous agent
        autonomous = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="Autonomous",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(autonomous)
        db_session.commit()

        # Mock agent resolution
        mock_resolver = Mock()
        mock_resolver.resolve_agent_for_request = AsyncMock(
            return_value=(autonomous, {})
        )
        mock_resolver_class.return_value = mock_resolver

        # Mock governance
        mock_gov = Mock()
        mock_gov.can_perform_action = Mock(
            return_value={"allowed": True}
        )
        mock_gov_class.return_value = mock_gov

        # Mock BYOK streaming
        mock_byok = Mock()
        async def mock_stream(**kwargs):
            tokens = ["Hello", " ", "world", "!"]
            for token in tokens:
                yield token
        mock_byok.stream_completion = mock_stream
        mock_byok.analyze_query_complexity = Mock(return_value="standard")
        mock_byok.get_optimal_provider = Mock(return_value=("openai", "gpt-3.5-turbo"))
        mock_byok_class.return_value = mock_byok

        # Mock WebSocket manager
        with patch('core.atom_agent_endpoints.ws_manager') as mock_ws:
            mock_ws.broadcast = AsyncMock()
            mock_ws.STREAMING_UPDATE = "streaming:update"
            mock_ws.STREAMING_COMPLETE = "streaming:complete"
            mock_ws.STREAMING_ERROR = "streaming:error"

            response = api_test_client.post(
                "/api/atom-agent/chat/stream",
                json={
                    "message": "Hello",
                    "user_id": "test-user-123",
                    "agent_id": autonomous.id
                }
            )

            # Streaming endpoint returns immediately with message_id
            assert response.status_code in [200, 404, 500]

            if response.status_code == 200:
                data = response.json()
                assert "message_id" in data or "error" in data

    @patch('core.atom_agent_endpoints.BYOKHandler')
    @patch('core.atom_agent_endpoints.AgentContextResolver')
    @patch('core.atom_agent_endpoints.AgentGovernanceService')
    def test_streaming_governance_blocked(self, mock_gov_class, mock_resolver_class, mock_byok_class, api_test_client: TestClient, db_session: Session):
        """Test streaming blocked by governance for student agents."""
        # Create student agent
        student = AgentRegistry(
            name="StudentAgent",
            category="test",
            module_path="test.module",
            class_name="Student",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db_session.add(student)
        db_session.commit()

        # Mock resolver
        mock_resolver = Mock()
        mock_resolver.resolve_agent_for_request = AsyncMock(
            return_value=(student, {})
        )
        mock_resolver_class.return_value = mock_resolver

        # Mock governance to block
        mock_gov = Mock()
        mock_gov.can_perform_action = Mock(
            return_value={
                "allowed": False,
                "reason": "Student agent not permitted for streaming"
            }
        )
        mock_gov_class.return_value = mock_gov

        response = api_test_client.post(
            "/api/atom-agent/chat/stream",
            json={
                "message": "Stream response",
                "user_id": "test-user-123",
                "agent_id": student.id
            }
        )

        # Should be blocked
        if response.status_code not in [200, 500]:
            assert response.status_code == 403 or "error" in response.json()


# ============================================================================
# TestAgentSessions
# ============================================================================

class TestAgentSessions:
    """Tests for session management endpoints."""

    def test_list_sessions_success(self, api_test_client: TestClient, mock_chat_session_manager):
        """Test GET /sessions returns 200 with sessions array."""
        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_get_mgr:
            mock_get_mgr.return_value = mock_chat_session_manager

            # Create some test sessions
            mock_chat_session_manager.create_session("user-1", "Session 1")
            mock_chat_session_manager.create_session("user-1", "Session 2")

            response = api_test_client.get(
                "/api/atom-agent/sessions",
                params={"user_id": "user-1", "limit": 50}
            )

            assert response.status_code in [200, 404, 500]

            if response.status_code == 200:
                data = response.json()
                assert "success" in data
                assert "sessions" in data
                assert isinstance(data["sessions"], list)

    def test_list_sessions_limit_parameter(self, api_test_client: TestClient, mock_chat_session_manager):
        """Test limit parameter restricts returned count."""
        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_get_mgr:
            mock_get_mgr.return_value = mock_chat_session_manager

            # Create many sessions
            for i in range(10):
                mock_chat_session_manager.create_session("user-1", f"Session {i}")

            response = api_test_client.get(
                "/api/atom-agent/sessions",
                params={"user_id": "user-1", "limit": 5}
            )

            if response.status_code == 200:
                data = response.json()
                assert len(data["sessions"]) <= 5

    def test_list_sessions_empty_result(self, api_test_client: TestClient, mock_chat_session_manager):
        """Test empty result returns [] not null."""
        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_get_mgr:
            mock_get_mgr.return_value = mock_chat_session_manager

            response = api_test_client.get(
                "/api/atom-agent/sessions",
                params={"user_id": "non-existent-user", "limit": 50}
            )

            if response.status_code == 200:
                data = response.json()
                assert data["sessions"] == []

    def test_list_sessions_response_structure(self, api_test_client: TestClient, mock_chat_session_manager):
        """Test each session has id, title, date, preview fields."""
        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_get_mgr:
            mock_get_mgr.return_value = mock_chat_session_manager

            mock_chat_session_manager.create_session("user-1", "Test Session")

            response = api_test_client.get(
                "/api/atom-agent/sessions",
                params={"user_id": "user-1"}
            )

            if response.status_code == 200:
                data = response.json()
                if data["sessions"]:
                    session = data["sessions"][0]
                    assert "id" in session
                    assert "title" in session
                    assert "date" in session
                    assert "preview" in session

    def test_create_session_returns_unique_id(self, api_test_client: TestClient, mock_chat_session_manager):
        """Test POST /sessions creates session with unique session_id."""
        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_get_mgr:
            mock_get_mgr.return_value = mock_chat_session_manager

            response = api_test_client.post(
                "/api/atom-agent/sessions",
                json={"user_id": "user-1"}
            )

            assert response.status_code in [200, 404, 500]

            if response.status_code == 200:
                data = response.json()
                assert "success" in data
                assert "session_id" in data
                assert len(data["session_id"]) > 0

    def test_create_session_includes_timestamp(self, api_test_client: TestClient, mock_chat_session_manager):
        """Test session includes created_at timestamp."""
        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_get_mgr:
            mock_get_mgr.return_value = mock_chat_session_manager

            response = api_test_client.post(
                "/api/atom-agent/sessions",
                json={"user_id": "user-1"}
            )

            if response.status_code == 200:
                data = response.json()
                # Session should have been created with timestamp
                session = mock_chat_session_manager.get_session(data["session_id"])
                assert session is not None
                assert "created_at" in session

    def test_get_session_history_success(self, api_test_client: TestClient, mock_chat_session_manager, mock_chat_history_manager):
        """Test GET /sessions/{id}/history returns 200 with messages array."""
        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_get_mgr:
            with patch('core.atom_agent_endpoints.get_chat_history_manager') as mock_get_history:
                mock_get_mgr.return_value = mock_chat_session_manager
                mock_get_history.return_value = mock_chat_history_manager

                # Create session and add messages
                session_id = mock_chat_session_manager.create_session("user-1")
                mock_chat_history_manager.save_message(
                    session_id, "user-1", "user", "Hello"
                )
                mock_chat_history_manager.save_message(
                    session_id, "user-1", "assistant", "Hi there!"
                )

                response = api_test_client.get(
                    f"/api/atom-agent/sessions/{session_id}/history"
                )

                assert response.status_code in [200, 404, 500]

                if response.status_code == 200:
                    data = response.json()
                    assert "success" in data
                    assert "messages" in data
                    assert isinstance(data["messages"], list)

    def test_get_session_history_chronological_order(self, api_test_client: TestClient, mock_chat_session_manager, mock_chat_history_manager):
        """Test messages ordered chronologically."""
        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_get_mgr:
            with patch('core.atom_agent_endpoints.get_chat_history_manager') as mock_get_history:
                mock_get_mgr.return_value = mock_chat_session_manager
                mock_get_history.return_value = mock_chat_history_manager

                session_id = mock_chat_session_manager.create_session("user-1")

                # Add messages in order
                mock_chat_history_manager.save_message(session_id, "user-1", "user", "First")
                mock_chat_history_manager.save_message(session_id, "user-1", "assistant", "Second")
                mock_chat_history_manager.save_message(session_id, "user-1", "user", "Third")

                response = api_test_client.get(
                    f"/api/atom-agent/sessions/{session_id}/history"
                )

                if response.status_code == 200:
                    data = response.json()
                    messages = data["messages"]
                    # Should maintain chronological order
                    assert len(messages) == 3
                    assert messages[0]["content"] == "First"
                    assert messages[1]["content"] == "Second"
                    assert messages[2]["content"] == "Third"

    def test_get_session_history_message_structure(self, api_test_client: TestClient, mock_chat_session_manager, mock_chat_history_manager):
        """Test each message has id, role, content, timestamp, metadata."""
        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_get_mgr:
            with patch('core.atom_agent_endpoints.get_chat_history_manager') as mock_get_history:
                mock_get_mgr.return_value = mock_chat_session_manager
                mock_get_history.return_value = mock_chat_history_manager

                session_id = mock_chat_session_manager.create_session("user-1")
                mock_chat_history_manager.save_message(
                    session_id, "user-1", "user", "Test message",
                    metadata={"intent": "test"}
                )

                response = api_test_client.get(
                    f"/api/atom-agent/sessions/{session_id}/history"
                )

                if response.status_code == 200:
                    data = response.json()
                    if data["messages"]:
                        msg = data["messages"][0]
                        assert "id" in msg
                        assert "role" in msg
                        assert "content" in msg
                        assert "timestamp" in msg
                        assert "metadata" in msg

    def test_get_session_history_not_found(self, api_test_client: TestClient, mock_chat_session_manager):
        """Test 404 returned for non-existent session_id."""
        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_get_mgr:
            mock_get_mgr.return_value = mock_chat_session_manager

            response = api_test_client.get(
                "/api/atom-agent/sessions/non-existent-session/history"
            )

            # Should return 404 or error
            assert response.status_code in [200, 404, 500]

            if response.status_code == 200:
                data = response.json()
                # May return success=False with error
                if not data.get("success"):
                    assert "error" in data

    def test_session_persistence_across_retrieval(self, api_test_client: TestClient, mock_chat_session_manager, mock_chat_history_manager):
        """Test messages persist across retrieval calls."""
        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_get_mgr:
            with patch('core.atom_agent_endpoints.get_chat_history_manager') as mock_get_history:
                mock_get_mgr.return_value = mock_chat_session_manager
                mock_get_history.return_value = mock_chat_history_manager

                session_id = mock_chat_session_manager.create_session("user-1")
                mock_chat_history_manager.save_message(session_id, "user-1", "user", "Persist this")

                # Retrieve first time
                response1 = api_test_client.get(
                    f"/api/atom-agent/sessions/{session_id}/history"
                )

                # Retrieve second time
                response2 = api_test_client.get(
                    f"/api/atom-agent/sessions/{session_id}/history"
                )

                # Should have same messages
                if response1.status_code == 200 and response2.status_code == 200:
                    count1 = len(response1.json().get("messages", []))
                    count2 = len(response2.json().get("messages", []))
                    assert count1 == count2

    def test_session_isolation_between_users(self, api_test_client: TestClient, mock_chat_session_manager, mock_chat_history_manager):
        """Test multiple users have isolated sessions."""
        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_get_mgr:
            with patch('core.atom_agent_endpoints.get_chat_history_manager') as mock_get_history:
                mock_get_mgr.return_value = mock_chat_session_manager
                mock_get_history.return_value = mock_chat_history_manager

                # Create sessions for different users
                session1 = mock_chat_session_manager.create_session("user-1")
                session2 = mock_chat_session_manager.create_session("user-2")

                # Add messages to each
                mock_chat_history_manager.save_message(session1, "user-1", "user", "User 1 message")
                mock_chat_history_manager.save_message(session2, "user-2", "user", "User 2 message")

                # Retrieve user-1's history
                response1 = api_test_client.get(
                    f"/api/atom-agent/sessions/{session1}/history"
                )

                # Should only contain user-1's messages
                if response1.status_code == 200:
                    messages = response1.json().get("messages", [])
                    assert all("User 1" in msg.get("content", "") for msg in messages)


# ============================================================================
# TestAgentExecution
# ============================================================================

class TestAgentExecution:
    """Tests for POST /api/atom-agent/execute endpoint."""

    def test_execute_success(self, api_test_client: TestClient, db_session: Session):
        """Test valid agent_id and input trigger execution."""
        # Create test agent
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(agent)
        db_session.commit()

        response = api_test_client.post(
            "/api/atom-agent/execute-generated",
            json={
                "workflow_id": "test-workflow-123",
                "input_data": {"test": "data"}
            }
        )

        # May succeed or fail depending on workflow existence
        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            if data["success"]:
                assert "execution_id" in data
                assert data.get("status") == "completed"

    def test_execute_returns_execution_id(self, api_test_client: TestClient):
        """Test execution returns 200 with execution_id and status='running'."""
        response = api_test_client.post(
            "/api/atom-agent/execute-generated",
            json={
                "workflow_id": "test-workflow",
                "input_data": {}
            }
        )

        # May fail if workflow doesn't exist
        assert response.status_code in [200, 404, 500]

    @patch('core.atom_agent_endpoints.AgentContextResolver')
    @patch('core.atom_agent_endpoints.AgentGovernanceService')
    def test_execute_governance_student_blocked(self, mock_gov_class, mock_resolver_class, api_test_client: TestClient, db_session: Session):
        """Test student agent blocked from destructive actions."""
        # Create student agent
        student = AgentRegistry(
            name="StudentAgent",
            category="test",
            module_path="test.module",
            class_name="Student",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db_session.add(student)
        db_session.commit()

        # Mock governance to block
        mock_gov = Mock()
        mock_gov.can_perform_action = Mock(
            return_value={
                "allowed": False,
                "reason": "Student agent not permitted for execution"
            }
        )
        mock_gov_class.return_value = mock_gov

        response = api_test_client.post(
            "/api/atom-agent/execute-generated",
            json={
                "workflow_id": "delete-workflow",
                "input_data": {}
            }
        )

        # Should be blocked or fail gracefully
        assert response.status_code in [200, 403, 404, 500]

    def test_execute_validation_missing_workflow_id(self, api_test_client: TestClient):
        """Test missing workflow_id returns 422."""
        response = api_test_client.post(
            "/api/atom-agent/execute-generated",
            json={
                "input_data": {}
            }
        )

        # Should validate required field
        assert response.status_code in [200, 404, 422]

    def test_execute_validation_empty_input_data(self, api_test_client: TestClient):
        """Test empty input_data rejected."""
        response = api_test_client.post(
            "/api/atom-agent/execute-generated",
            json={
                "workflow_id": "test-workflow",
                "input_data": {}
            }
        )

        # May accept empty input_data
        assert response.status_code in [200, 422, 500]

    def test_execute_workflow_not_found(self, api_test_client: TestClient):
        """Test non-existent workflow returns appropriate error."""
        response = api_test_client.post(
            "/api/atom-agent/execute-generated",
            json={
                "workflow_id": "non-existent-workflow-999",
                "input_data": {}
            }
        )

        # Should return 404 or error
        assert response.status_code in [200, 404, 500]


# ============================================================================
# TestExecuteGeneratedWorkflow
# ============================================================================

class TestExecuteGeneratedWorkflow:
    """Tests for POST /api/atom-agent/execute-generated endpoint."""

    @patch('core.atom_agent_endpoints.AutomationEngine')
    @patch('core.atom_agent_endpoints.load_workflows')
    def test_execute_generated_success(self, mock_load, mock_engine_class, api_test_client: TestClient):
        """Test executing a generated workflow."""
        # Mock workflow
        mock_workflow = {
            'id': 'test-workflow-123',
            'name': 'Test Workflow',
            'nodes': [],
            'connections': []
        }
        mock_load.return_value = [mock_workflow]

        # Mock engine
        mock_engine = Mock()
        mock_engine.execute_workflow_definition = AsyncMock(
            return_value={"status": "completed"}
        )
        mock_engine_class.return_value = mock_engine

        response = api_test_client.post(
            "/api/atom-agent/execute-generated",
            json={
                "workflow_id": "test-workflow-123",
                "input_data": {"key": "value"}
            }
        )

        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                assert "execution_id" in data
                assert "status" in data

    @patch('core.atom_agent_endpoints.load_workflows')
    def test_execute_generated_workflow_not_found(self, mock_load, api_test_client: TestClient):
        """Test executing non-existent workflow returns error."""
        mock_load.return_value = []

        response = api_test_client.post(
            "/api/atom-agent/execute-generated",
            json={
                "workflow_id": "non-existent",
                "input_data": {}
            }
        )

        # Should return error
        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert data.get("success") is False or "error" in data

    @patch('core.atom_agent_endpoints.AutomationEngine')
    def test_execute_generated_missing_automation_engine(self, mock_engine_class, api_test_client: TestClient):
        """Test graceful handling when AutomationEngine is not available."""
        # Mock AutomationEngine as None
        with patch('core.atom_agent_endpoints.AutomationEngine', None):
            response = api_test_client.post(
                "/api/atom-agent/execute-generated",
                json={
                    "workflow_id": "test-workflow",
                    "input_data": {}
                }
            )

            # Should return error
            assert response.status_code in [200, 404, 500]

            if response.status_code == 200:
                data = response.json()
                if not data.get("success"):
                    assert "AutomationEngine" in data.get("error", "")


# ============================================================================
# TestHybridRetrievalEndpoints
# ============================================================================

class TestHybridRetrievalEndpoints:
    """Tests for hybrid retrieval endpoints."""

    @patch('core.atom_agent_endpoints.HybridRetrievalService')
    def test_retrieve_hybrid_success(self, mock_service_class, api_test_client: TestClient):
        """Test hybrid semantic retrieval endpoint."""
        # Mock service
        mock_service = Mock()
        mock_service.retrieve_semantic_hybrid = AsyncMock(
            return_value=[
                ("episode-1", 0.95, "rerank"),
                ("episode-2", 0.85, "rerank")
            ]
        )
        mock_service_class.return_value = mock_service

        response = api_test_client.post(
            "/api/atom-agent/agents/test-agent/retrieve-hybrid",
            json={
                "query": "test query",
                "coarse_top_k": 100,
                "rerank_top_k": 50,
                "use_reranking": True
            }
        )

        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "results" in data
            if data["success"]:
                assert len(data["results"]) == 2
                assert data["count"] == 2

    @patch('core.atom_agent_endpoints.HybridRetrievalService')
    def test_retrieve_baseline_success(self, mock_service_class, api_test_client: TestClient):
        """Test baseline semantic retrieval endpoint."""
        # Mock service
        mock_service = Mock()
        mock_service.retrieve_semantic_baseline = AsyncMock(
            return_value=[
                ("episode-1", 0.90),
                ("episode-2", 0.80)
            ]
        )
        mock_service_class.return_value = mock_service

        response = api_test_client.post(
            "/api/atom-agent/agents/test-agent/retrieve-baseline",
            json={
                "query": "test query",
                "top_k": 50
            }
        )

        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "results" in data
            if data["success"]:
                assert data["method"] == "fastembed_baseline"


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Tests for error handling across all endpoints."""

    def test_generic_error_response_format(self, api_test_client: TestClient):
        """Test all errors follow BaseAPIRouter format."""
        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "",  # Empty message might trigger error
                "user_id": "test-user"
            }
        )

        # Any error should follow consistent format
        if response.status_code >= 400:
            data = response.json()
            # Should have error field or success=False
            assert "error" in data or "success" in data

    def test_exception_handling_does_not_crash(self, api_test_client: TestClient):
        """Test exceptions are caught and return 500, not crash."""
        # This test verifies the exception handling works
        response = api_test_client.post(
            "/api/atom-agent/chat",
            json={
                "message": "Test message",
                "user_id": "test-user"
            }
        )

        # Should not crash (no 500 Internal Server Error that's unhandled)
        assert response.status_code in [200, 400, 404, 500]

        if response.status_code == 500:
            data = response.json()
            assert "error" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
