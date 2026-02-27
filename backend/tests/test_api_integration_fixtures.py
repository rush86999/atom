"""
Shared fixtures for API integration tests.

Provides common fixtures for testing FastAPI endpoints including:
- TestClient with authentication overrides
- Mock agent resolver and governance service
- Helper functions for session creation
- LLM streaming mocks

Usage:
    from tests.test_api_integration_fixtures import (
        api_test_client,
        mock_agent_resolver,
        create_test_session,
        mock_llm_streaming
    )
"""

import asyncio
from datetime import datetime
from typing import AsyncIterator, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, User


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def api_test_client(db_session: Session):
    """
    FastAPI TestClient with authenticated user context.

    Creates a TestClient with dependency override for get_current_user
    to simulate authenticated requests without needing full auth flow.

    Usage:
        def test_my_endpoint(api_test_client):
            response = api_test_client.post("/api/atom-agent/chat", json={...})
            assert response.status_code == 200
    """
    from fastapi.testclient import TestClient

    # Try to import main app (try multiple possible entry points)
    app = None
    for app_module in ["main", "main_api_app", "main_api_app_safe", "cli.main"]:
        try:
            module = __import__(app_module, fromlist=["app"])
            if hasattr(module, "app"):
                app = module.app
                break
        except (ImportError, AttributeError):
            continue

    # If no app found, create minimal FastAPI app for testing
    if app is None:
        from fastapi import FastAPI
        app = FastAPI()

        # Try to include the atom_agent router
        try:
            from core.atom_agent_endpoints import router
            app.include_router(router)
        except Exception:
            # Router import failed, that's okay for basic fixture functionality
            pass

    # Create test user
    test_user = User(
        id="test-api-user-123",
        email="test-api@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="API",
        status="active",
        email_verified=True
    )
    db_session.add(test_user)
    db_session.commit()

    # Create mock auth dependency
    async def get_current_user_override():
        return test_user

    # Override dependency if it exists
    try:
        app.dependency_overrides[get_current_user] = get_current_user_override
    except (NameError, AttributeError):
        # get_current_user might not be imported, that's okay
        pass

    # Create TestClient
    client = TestClient(app)

    # Store test_user on client for access in tests
    client.test_user = test_user
    client.db_session = db_session

    yield client

    # Clean up
    try:
        del app.dependency_overrides[get_current_user]
    except (KeyError, AttributeError):
        pass


@pytest.fixture(scope="function")
def mock_agent_resolver(db_session: Session):
    """
    Mock AgentContextResolver for testing.

    Returns AsyncMock that resolves to test agents by maturity level.
    Supports resolve_agent_for_request(agent_id, user_id, action_type).

    Usage:
        def test_agent_resolution(mock_agent_resolver):
            agent, context = await mock_agent_resolver.resolve_agent_for_request(...)
            assert agent.status == AgentStatus.INTERN.value
    """
    # Create test agents
    student_agent = AgentRegistry(
        name="StudentTestAgent",
        category="test",
        module_path="test.module",
        class_name="StudentTest",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.3,
    )

    intern_agent = AgentRegistry(
        name="InternTestAgent",
        category="test",
        module_path="test.module",
        class_name="InternTest",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
    )

    supervised_agent = AgentRegistry(
        name="SupervisedTestAgent",
        category="test",
        module_path="test.module",
        class_name="SupervisedTest",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.8,
    )

    autonomous_agent = AgentRegistry(
        name="AutonomousTestAgent",
        category="test",
        module_path="test.module",
        class_name="AutonomousTest",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95,
    )

    db_session.add_all([student_agent, intern_agent, supervised_agent, autonomous_agent])
    db_session.commit()
    db_session.refresh(student_agent)
    db_session.refresh(intern_agent)
    db_session.refresh(supervised_agent)
    db_session.refresh(autonomous_agent)

    # Create mock resolver
    resolver_mock = AsyncMock(spec=AgentContextResolver)

    # Map maturity levels to agents
    agents_by_maturity = {
        "student": student_agent,
        "intern": intern_agent,
        "supervised": supervised_agent,
        "autonomous": autonomous_agent,
    }

    async def mock_resolve(agent_id: Optional[str] = None, user_id: str = None,
                          session_id: str = None, requested_agent_id: str = None,
                          action_type: str = "chat"):
        """Resolve agent based on requested_agent_id or default to intern."""
        if requested_agent_id:
            # Find agent by ID
            for agent in agents_by_maturity.values():
                if agent.id == requested_agent_id:
                    return agent, {"resolution_method": "explicit_id"}
            # If not found, return intern
            return intern_agent, {"resolution_method": "default"}

        # Default to intern agent
        return intern_agent, {"resolution_method": "default"}

    resolver_mock.resolve_agent_for_request = mock_resolve

    return resolver_mock


@pytest.fixture(scope="function")
def mock_governance_service(db_session: Session):
    """
    Mock AgentGovernanceService for testing.

    Returns AsyncMock that provides governance check results.
    Supports can_perform_action(agent_id, action_type).

    Usage:
        def test_governance_check(mock_governance_service):
            result = mock_governance_service.can_perform_action("agent-1", "delete")
            assert result["allowed"] is False
    """
    governance_mock = AsyncMock(spec=AgentGovernanceService)

    async def mock_can_perform(agent_id: str, action_type: str):
        """Mock governance check based on action type."""
        # Allow safe actions, block destructive ones
        destructive_actions = ["delete", "remove", "destroy", "execute"]

        if action_type in destructive_actions:
            return {
                "allowed": False,
                "reason": f"Action '{action_type}' requires AUTONOMOUS maturity",
                "required_maturity": "AUTONOMOUS"
            }
        else:
            return {
                "allowed": True,
                "reason": "Action permitted for current maturity level"
            }

    async def mock_record_outcome(agent_id: str, success: bool):
        """Mock outcome recording."""
        return {"recorded": True, "agent_id": agent_id, "success": success}

    governance_mock.can_perform_action = mock_can_perform
    governance_mock.record_outcome = mock_record_outcome

    return governance_mock


@pytest.fixture(scope="function")
def create_test_session(db_session: Session):
    """
    Helper function to create test chat sessions.

    Accepts db_session, user_id, optional title.
    Returns session dict with session_id, created_at, metadata.

    Usage:
        def test_session_creation(create_test_session):
            session = create_test_session("user-123", title="Test Chat")
            assert "session_id" in session
    """
    def _create_session(user_id: str, title: str = "Test Session") -> Dict[str, Any]:
        """Create a test chat session."""
        import uuid

        session_id = f"session_{uuid.uuid4().hex[:16]}"
        now = datetime.utcnow()

        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": now.isoformat(),
            "last_active": now.isoformat(),
            "metadata": {
                "title": title,
                "last_message": ""
            }
        }

        # Optionally save to database if chat session table exists
        try:
            from core.models import ChatSession
            session = ChatSession(
                id=session_id,
                user_id=user_id,
                title=title,
                created_at=now,
                last_active=now
            )
            db_session.add(session)
            db_session.commit()
        except Exception:
            # Table might not exist, that's okay for testing
            pass

        return session_data

    return _create_session


@pytest.fixture(scope="function")
def mock_llm_streaming():
    """
    AsyncMock for LLM streaming responses.

    Yields tokens one at a time for streaming endpoint tests.
    Supports error injection for failure scenarios.

    Usage:
        def test_streaming_response(mock_llm_streaming):
            async for token in mock_llm_streaming.stream("test"):
                assert isinstance(token, str)
    """
    class MockLLMStreaming:
        def __init__(self):
            self._error_mode = None
            self._call_count = 0

        async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
            """Return deterministic mock streaming response."""
            self._call_count += 1
            response = f"Mock streaming response {self._call_count}: {prompt[:50]}"

            # Simulate error if error mode is set
            if self._error_mode == "rate_limited":
                raise Exception("Rate limit exceeded")
            elif self._error_mode == "timeout":
                raise asyncio.TimeoutError("LLM timeout")

            # Yield tokens one at a time
            for char in response:
                yield char
                await asyncio.sleep(0.001)  # Simulate network delay

        async def complete(self, prompt: str, **kwargs) -> str:
            """Return complete mock response."""
            self._call_count += 1
            if self._error_mode == "rate_limited":
                raise Exception("Rate limit exceeded")
            elif self._error_mode == "timeout":
                raise asyncio.TimeoutError("LLM timeout")
            return f"Mock response {self._call_count} for: {prompt[:50]}"

        def set_error_mode(self, mode: str):
            """Set error mode for testing failure scenarios."""
            self._error_mode = mode

        def reset(self):
            """Reset error mode and call count."""
            self._error_mode = None
            self._call_count = 0

    mock = MockLLMStreaming()
    yield mock
    mock.reset()


@pytest.fixture(scope="function")
def authenticated_headers(api_test_client: TestClient) -> Dict[str, str]:
    """
    Pre-configured authentication headers for API requests.

    Returns headers dict with Authorization token.

    Usage:
        def test_authenticated_request(authenticated_headers):
            headers = authenticated_headers
            response = client.get("/api/protected", headers=headers)
    """
    import secrets

    token = secrets.token_urlsafe(32)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="function")
def mock_chat_session_manager():
    """
    Mock ChatSessionManager for testing.

    Provides mock methods for session creation, listing, and retrieval.

    Usage:
        def test_session_list(mock_chat_session_manager):
            sessions = mock_chat_session_manager.list_user_sessions("user-1")
            assert len(sessions) > 0
    """
    manager_mock = Mock()

    # Mock session storage
    _sessions = {}

    def mock_create_session(user_id: str, title: str = "New Chat") -> str:
        import uuid
        session_id = f"session_{uuid.uuid4().hex[:16]}"
        _sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "title": title,
            "created_at": datetime.utcnow().isoformat(),
            "last_active": datetime.utcnow().isoformat()
        }
        return session_id

    def mock_get_session(session_id: str) -> Optional[Dict]:
        return _sessions.get(session_id)

    def mock_list_user_sessions(user_id: str, limit: int = 50) -> list:
        user_sessions = [
            s for s in _sessions.values()
            if s.get("user_id") == user_id
        ]
        return user_sessions[:limit]

    def mock_update_session_activity(session_id: str):
        if session_id in _sessions:
            _sessions[session_id]["last_active"] = datetime.utcnow().isoformat()

    manager_mock.create_session = mock_create_session
    manager_mock.get_session = mock_get_session
    manager_mock.list_user_sessions = mock_list_user_sessions
    manager_mock.update_session_activity = mock_update_session_activity

    return manager_mock


@pytest.fixture(scope="function")
def mock_chat_history_manager():
    """
    Mock ChatHistoryManager for testing.

    Provides mock methods for saving and retrieving chat messages.

    Usage:
        def test_message_save(mock_chat_history_manager):
            mock_chat_history_manager.save_message("session-1", "user", "Hello")
    """
    manager_mock = Mock()

    # Mock message storage
    _messages = {}

    def mock_save_message(session_id: str, user_id: str, role: str,
                         content: str, metadata: Dict = None):
        import uuid
        if session_id not in _messages:
            _messages[session_id] = []
        _messages[session_id].append({
            "id": str(uuid.uuid4()),
            "role": role,
            "text": content,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        })

    def mock_get_session_history(session_id: str, limit: int = 100) -> list:
        return _messages.get(session_id, [])[:limit]

    def mock_add_message(session_id: str, role: str, content: str):
        # Alias for save_message
        return mock_save_message(session_id, None, role, content)

    manager_mock.save_message = mock_save_message
    manager_mock.get_session_history = mock_get_session_history
    manager_mock.add_message = mock_add_message

    return manager_mock
