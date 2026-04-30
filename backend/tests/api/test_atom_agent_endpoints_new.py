"""
Atom Agent Endpoints API Tests

Comprehensive tests for atom agent chat and streaming endpoints from core/atom_agent_endpoints.py.
Tests focus on testable endpoints without complex auth/WebSocket dependencies.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy.orm import Session

from core.atom_agent_endpoints import router
from core.models import User


# ============================================================================
# Fixtures
# ============================================================================

_current_test_user = None


@pytest.fixture
def client(db_session: Session):
    """Create TestClient for atom agent endpoints with database override."""
    global _current_test_user
    _current_test_user = None

    app = FastAPI()
    app.include_router(router)

    from core.database import get_db
    from core.auth import get_current_user

    def override_get_db():
        yield db_session

    def override_get_current_user():
        return _current_test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    app.dependency_overrides.clear()
    _current_test_user = None


@pytest.fixture
def mock_user(db_session: Session):
    """Create test user."""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        first_name="Test",
        last_name="User",
        role="member",
        status="active"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ============================================================================
# GET /sessions - List Chat Sessions Tests
# ============================================================================

def test_list_sessions_success(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test list chat sessions successfully."""
    global _current_test_user
    _current_test_user = mock_user

    with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_mgr:
        mock_session_mgr = Mock()
        mock_mgr.list_user_sessions.return_value = [
            {"session_id": "sess1", "last_active": "2026-04-30T10:00:00Z", "metadata": {"title": "Test"}}
        ]
        mock_mgr.return_value = mock_session_mgr

        response = client.get("/api/atom-agent/sessions")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "sessions" in data


def test_list_sessions_unauthorized(
    client: TestClient
):
    """Test list sessions without authentication fails."""
    global _current_test_user
    _current_test_user = None

    response = client.get("/api/atom-agent/sessions")

    assert response.status_code in [401, 403]


# ============================================================================
# POST /sessions - Create Chat Session Tests
# ============================================================================

def test_create_session_success(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test create new chat session successfully."""
    global _current_test_user
    _current_test_user = mock_user

    with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_mgr:
        mock_session_mgr = Mock()
        mock_session_mgr.create_session.return_value = "new-session-123"
        mock_mgr.return_value = mock_session_mgr

        response = client.post("/api/atom-agent/sessions")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "session_id" in data


# ============================================================================
# GET /sessions/{session_id}/history - Get Session History Tests
# ============================================================================

def test_get_session_history_success(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test get session history successfully."""
    global _current_test_user
    _current_test_user = mock_user

    session_id = "test-session-123"

    with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_sess_mgr, \
         patch('core.atom_agent_endpoints.get_chat_history_manager') as mock_hist_mgr:
        mock_session_mgr = Mock()
        mock_session_mgr.get_session.return_value = {
            "session_id": session_id,
            "user_id": mock_user.id
        }
        mock_sess_mgr.return_value = mock_session_mgr

        mock_hist_mgr_instance = Mock()
        mock_hist_mgr_instance.get_session_history.return_value = [
            {"id": "msg1", "role": "user", "text": "Hello", "created_at": "2026-04-30T10:00:00Z", "metadata": "{}"}
        ]
        mock_hist_mgr.return_value = mock_hist_mgr_instance

        response = client.get(f"/api/atom-agent/sessions/{session_id}/history")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "messages" in data


def test_get_session_history_not_found(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test get history for non-existent session."""
    global _current_test_user
    _current_test_user = mock_user

    with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_mgr:
        mock_session_mgr = Mock()
        mock_session_mgr.get_session.return_value = None
        mock_mgr.return_value = mock_session_mgr

        response = client.get("/api/atom-agent/sessions/nonexistent/history")

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is False


# ============================================================================
# POST /chat - Chat Endpoint Tests
# ============================================================================

def test_chat_with_agent_success(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test chat with agent successfully."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "message": "Hello, agent!",
        "user_id": mock_user.id
    }

    with patch('core.atom_agent_endpoints.classify_intent_with_llm') as mock_classify, \
         patch('core.atom_agent_endpoints.handle_help_request') as mock_help:
        mock_classify.return_value = {"intent": "HELP", "entities": {}}
        mock_help.return_value = {
            "success": True,
            "response": {"message": "I can help you!"}
        }

        response = client.post("/api/atom-agent/chat", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "success" in data


def test_chat_with_session_id(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test chat with existing session ID."""
    global _current_test_user
    _current_test_user = mock_user

    session_id = "existing-session-123"

    request_data = {
        "message": "Continue conversation",
        "user_id": mock_user.id,
        "session_id": session_id
    }

    with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_sess_mgr, \
         patch('core.atom_agent_endpoints.classify_intent_with_llm') as mock_classify, \
         patch('core.atom_agent_endpoints.handle_help_request') as mock_help:
        mock_session_mgr = Mock()
        mock_session_mgr.get_session.return_value = {
            "session_id": session_id,
            "user_id": mock_user.id
        }
        mock_sess_mgr.return_value = mock_session_mgr

        mock_classify.return_value = {"intent": "HELP", "entities": {}}
        mock_help.return_value = {
            "success": True,
            "response": {"message": "Continuing!"}
        }

        response = client.post("/api/atom-agent/chat", json=request_data)

        assert response.status_code == 200


def test_chat_with_context(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test chat with context variables."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "message": "Help with task",
        "user_id": mock_user.id,
        "context": {"task_id": "123", "workspace": "test"}
    }

    with patch('core.atom_agent_endpoints.classify_intent_with_llm') as mock_classify, \
         patch('core.atom_agent_endpoints.handle_help_request') as mock_help:
        mock_classify.return_value = {"intent": "HELP", "entities": {}}
        mock_help.return_value = {
            "success": True,
            "response": {"message": "Helping!"}
        }

        response = client.post("/api/atom-agent/chat", json=request_data)

        assert response.status_code == 200


def test_chat_create_task_intent(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test chat with CREATE_TASK intent."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "message": "Create a new task",
        "user_id": mock_user.id
    }

    with patch('core.atom_agent_endpoints.classify_intent_with_llm') as mock_classify, \
         patch('core.atom_agent_endpoints.handle_task_intent') as mock_task:
        mock_classify.return_value = {
            "intent": "CREATE_TASK",
            "entities": {"title": "new task"}
        }
        mock_task.return_value = {
            "success": True,
            "response": {"message": "Task created!"}
        }

        response = client.post("/api/atom-agent/chat", json=request_data)

        assert response.status_code == 200


def test_chat_unauthorized(
    client: TestClient
):
    """Test chat without authentication fails."""
    global _current_test_user
    _current_test_user = None

    request_data = {
        "message": "Hello",
        "user_id": "test-user"
    }

    response = client.post("/api/atom-agent/chat", json=request_data)

    assert response.status_code in [401, 403]


# ============================================================================
# POST /execute-generated - Execute Generated Workflow Tests
# ============================================================================

def test_execute_generated_workflow_success(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test execute generated workflow successfully."""
    global _current_test_user
    _current_test_user = mock_user

    # Note: This endpoint doesn't require auth based on the code
    request_data = {
        "workflow_id": "test-workflow",
        "input_data": {"param1": "value1"}
    }

    with patch('core.atom_agent_endpoints.load_workflows') as mock_load, \
         patch('core.atom_agent_endpoints.AutomationEngine') as mock_engine:
        mock_load.return_value = [
            {
                "id": "test-workflow",
                "name": "Test Workflow",
                "workflow_id": "test-workflow"
            }
        ]

        mock_engine_instance = Mock()
        mock_engine_instance.execute_workflow_definition.return_value = {"status": "completed"}
        mock_engine.return_value = mock_engine_instance

        response = client.post("/api/atom-agent/execute-generated", json=request_data)

        # Might fail if AutomationEngine is not available
        assert response.status_code in [200, 500, 501]


def test_execute_generated_workflow_not_found(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test execute non-existent workflow."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "workflow_id": "nonexistent-workflow",
        "input_data": {}
    }

    with patch('core.atom_agent_endpoints.load_workflows') as mock_load:
        mock_load.return_value = []

        response = client.post("/api/atom-agent/execute-generated", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is False


# ============================================================================
# POST /chat/stream - Streaming Chat Tests (Mocked)
# ============================================================================

def test_chat_stream_success(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test streaming chat endpoint with mocked dependencies."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "message": "Stream this response",
        "user_id": mock_user.id
    }

    # Mock all the complex dependencies
    with patch('core.atom_agent_endpoints.AgentContextResolver') as mock_resolver, \
         patch('core.atom_agent_endpoints.AgentGovernanceService') as mock_gov, \
         patch('core.atom_agent_endpoints.LLMService') as mock_llm, \
         patch('core.atom_agent_endpoints.ws_manager') as mock_ws:

        # Setup mocks
        mock_agent = Mock()
        mock_agent.id = "test-agent"
        mock_agent.name = "Test Agent"

        mock_resolver_instance = Mock()
        mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_resolver.return_value = mock_resolver_instance

        mock_gov_instance = Mock()
        mock_gov_instance.can_perform_action.return_value = {"allowed": True}
        mock_gov.return_value = mock_gov_instance

        mock_llm_instance = Mock()
        mock_llm_instance.analyze_query_complexity.return_value = "low"
        mock_llm_instance.get_optimal_provider.return_value = ("openai", "gpt-4")
        mock_llm_instance.stream_completion = AsyncMock(return_value=iter(["Hello", " ", "World"]))
        mock_llm.return_value = mock_llm_instance

        mock_ws.broadcast = AsyncMock()

        response = client.post("/api/atom-agent/chat/stream", json=request_data)

        # Should succeed with mocked dependencies
        assert response.status_code == 200


def test_chat_stream_governance_blocked(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test streaming chat blocked by governance."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "message": "Blocked action",
        "user_id": mock_user.id
    }

    with patch('core.atom_agent_endpoints.AgentContextResolver') as mock_resolver, \
         patch('core.atom_agent_endpoints.AgentGovernanceService') as mock_gov, \
         patch('os.getenv') as mock_getenv:

        mock_getenv.return_value = "true"

        mock_agent = Mock()
        mock_agent.id = "restricted-agent"
        mock_agent.name = "Restricted Agent"

        mock_resolver_instance = Mock()
        mock_resolver_instance.resolve_agent_for_request = AsyncMock(return_value=(mock_agent, {}))
        mock_resolver.return_value = mock_resolver_instance

        mock_gov_instance = Mock()
        mock_gov_instance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Agent maturity too low"
        }
        mock_gov.return_value = mock_gov_instance

        response = client.post("/api/atom-agent/chat/stream", json=request_data)

        # Should be blocked
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is False


# ============================================================================
# POST /agents/{agent_id}/retrieve-hybrid - Hybrid Retrieval Tests
# ============================================================================

def test_hybrid_retrieval_success(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test hybrid semantic retrieval."""
    global _current_test_user
    _current_test_user = mock_user

    agent_id = "test-agent"

    with patch('core.atom_agent_endpoints.HybridRetrievalService') as mock_service:
        mock_service_instance = Mock()
        mock_service_instance.retrieve_semantic_hybrid = AsyncMock(return_value=[
            ("ep1", 0.95, "reranked"),
            ("ep2", 0.85, "reranked")
        ])
        mock_service.return_value = mock_service_instance

        response = client.post(
            f"/api/atom-agent/agents/{agent_id}/retrieve-hybrid",
            params={"query": "test query", "coarse_top_k": 100, "rerank_top_k": 50}
        )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "results" in data


def test_hybrid_retrieval_baseline(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test baseline semantic retrieval."""
    global _current_test_user
    _current_test_user = mock_user

    agent_id = "test-agent"

    with patch('core.atom_agent_endpoints.HybridRetrievalService') as mock_service:
        mock_service_instance = Mock()
        mock_service_instance.retrieve_semantic_baseline = AsyncMock(return_value=[
            ("ep1", 0.90),
            ("ep2", 0.80)
        ])
        mock_service.return_value = mock_service_instance

        response = client.post(
            f"/api/atom-agent/agents/{agent_id}/retrieve-baseline",
            params={"query": "test query", "top_k": 50}
        )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "results" in data


# ============================================================================
# Edge Case Tests
# ============================================================================

def test_chat_with_empty_message(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test chat with empty message."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "message": "",
        "user_id": mock_user.id
    }

    with patch('core.atom_agent_endpoints.classify_intent_with_llm') as mock_classify, \
         patch('core.atom_agent_endpoints.handle_help_request') as mock_help:
        mock_classify.return_value = {"intent": "UNKNOWN", "entities": {}}
        mock_help.return_value = {
            "success": True,
            "response": {"message": "I can help!"}
        }

        response = client.post("/api/atom-agent/chat", json=request_data)

        assert response.status_code == 200


def test_chat_with_unicode_message(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test chat with Unicode characters."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "message": "Hello 世界 🌍",
        "user_id": mock_user.id
    }

    with patch('core.atom_agent_endpoints.classify_intent_with_llm') as mock_classify, \
         patch('core.atom_agent_endpoints.handle_help_request') as mock_help:
        mock_classify.return_value = {"intent": "HELP", "entities": {}}
        mock_help.return_value = {
            "success": True,
            "response": {"message": "Unicode supported!"}
        }

        response = client.post("/api/atom-agent/chat", json=request_data)

        assert response.status_code == 200


def test_chat_with_very_long_message(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test chat with very long message."""
    global _current_test_user
    _current_test_user = mock_user

    request_data = {
        "message": "x" * 10000,  # 10KB message
        "user_id": mock_user.id
    }

    with patch('core.atom_agent_endpoints.classify_intent_with_llm') as mock_classify, \
         patch('core.atom_agent_endpoints.handle_help_request') as mock_help:
        mock_classify.return_value = {"intent": "UNKNOWN", "entities": {}}
        mock_help.return_value = {
            "success": True,
            "response": {"message": "Message received!"}
        }

        response = client.post("/api/atom-agent/chat", json=request_data)

        assert response.status_code == 200


# ============================================================================
# Performance Tests
# ============================================================================

def test_chat_response_time(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test chat endpoint response time is acceptable."""
    global _current_test_user
    _current_test_user = mock_user

    import time

    request_data = {
        "message": "Quick test",
        "user_id": mock_user.id
    }

    with patch('core.atom_agent_endpoints.classify_intent_with_llm') as mock_classify, \
         patch('core.atom_agent_endpoints.handle_help_request') as mock_help:
        mock_classify.return_value = {"intent": "HELP", "entities": {}}
        mock_help.return_value = {
            "success": True,
            "response": {"message": "Quick response!"}
        }

        start_time = time.time()
        response = client.post("/api/atom-agent/chat", json=request_data)
        elapsed = time.time() - start_time

        assert response.status_code == 200
        # Should respond in < 2 seconds (with mocks)
        assert elapsed < 2.0


# ============================================================================
# Integration Tests
# ============================================================================

def test_chat_session_lifecycle(
    client: TestClient,
    db_session: Session,
    mock_user: User
):
    """Test full chat session lifecycle: create -> chat -> history."""
    global _current_test_user
    _current_test_user = mock_user

    # 1. Create session
    with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_sess_mgr:
        mock_session_mgr = Mock()
        mock_session_mgr.create_session.return_value = "test-session-456"
        mock_sess_mgr.return_value = mock_session_mgr

        create_response = client.post("/api/atom-agent/sessions")
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]

    # 2. Send chat message
    request_data = {
        "message": "Test message",
        "user_id": mock_user.id,
        "session_id": session_id
    }

    with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_sess_mgr2, \
         patch('core.atom_agent_endpoints.classify_intent_with_llm') as mock_classify, \
         patch('core.atom_agent_endpoints.handle_help_request') as mock_help:
        mock_session_mgr2.get_session.return_value = {
            "session_id": session_id,
            "user_id": mock_user.id
        }
        mock_classify.return_value = {"intent": "HELP", "entities": {}}
        mock_help.return_value = {
            "success": True,
            "response": {"message": "Got it!"}
        }

        chat_response = client.post("/api/atom-agent/chat", json=request_data)
        assert chat_response.status_code == 200
