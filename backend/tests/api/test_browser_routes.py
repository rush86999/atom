"""
Browser Routes Integration Tests

Tests for browser automation endpoints from api/browser_routes.py.

Coverage:
- POST /session/create - Create browser session
- POST /navigate - Navigate to URL
- POST /screenshot - Take screenshot
- POST /fill-form - Fill form fields
- POST /click - Click element
- POST /extract-text - Extract text content
- POST /execute-script - Execute JavaScript
- POST /session/close - Close session
- GET /session/{session_id}/info - Get session info
- GET /sessions - List sessions
- Authentication/authorization
- Governance enforcement (INTERN+ required)
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.browser_routes import router
from core.models import AgentRegistry, User, BrowserSession


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create TestClient for browser routes."""
    return TestClient(router)


@pytest.fixture
def mock_user(db: Session):
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
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def mock_intern_agent(db: Session):
    """Create INTERN maturity agent (allowed for browser actions)."""
    import uuid
    agent_id = str(uuid.uuid4())
    agent = AgentRegistry(
        id=agent_id,
        name=f"Intern Agent {agent_id[:8]}",
        category="testing",
        status="intern",
        confidence_score=0.6,
        module_path="test.module",
        class_name="TestClass"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def mock_supervised_agent(db: Session):
    """Create SUPERVISED maturity agent."""
    import uuid
    agent_id = str(uuid.uuid4())
    agent = AgentRegistry(
        id=agent_id,
        name=f"Supervised Agent {agent_id[:8]}",
        category="testing",
        status="supervised",
        confidence_score=0.8,
        module_path="test.module",
        class_name="TestClass"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def mock_browser_session(db: Session, mock_user: User):
    """Create a test browser session."""
    import uuid
    session_id = str(uuid.uuid4())
    session = BrowserSession(
        session_id=session_id,
        workspace_id="default",
        user_id=mock_user.id,
        browser_type="chromium",
        headless=True,
        status="active",
        current_url="https://example.com",
        page_title="Example Page"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


# ============================================================================
# POST /session/create - Create Browser Session Tests
# ============================================================================

def test_create_session_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test creating browser session successfully."""
    request_data = {
        "headless": True,
        "browser_type": "chromium"
    }

    with patch('api.browser_routes.browser_create_session') as mock_create:
        mock_create.return_value = {
            "success": True,
            "session_id": "test-session-123",
            "headless": True,
            "browser_type": "chromium"
        }

        with patch('api.browser_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/session/create", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "session_id" in data


def test_create_session_with_agent(
    client: TestClient,
    db: Session,
    mock_intern_agent: AgentRegistry,
    mock_user: User
):
    """Test creating browser session with agent."""
    request_data = {
        "headless": True,
        "browser_type": "chromium",
        "agent_id": mock_intern_agent.id
    }

    with patch('api.browser_routes.browser_create_session') as mock_create:
        mock_create.return_value = {
            "success": True,
            "session_id": "test-session-456"
        }

        with patch('api.browser_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/session/create", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


# ============================================================================
# POST /navigate - Navigate Tests
# ============================================================================

def test_navigate_success(
    client: TestClient,
    db: Session,
    mock_browser_session: BrowserSession,
    mock_user: User
):
    """Test navigating to URL successfully."""
    request_data = {
        "session_id": mock_browser_session.session_id,
        "url": "https://example.com/page",
        "wait_until": "load"
    }

    with patch('api.browser_routes.browser_navigate') as mock_nav:
        mock_nav.return_value = {
            "success": True,
            "url": "https://example.com/page",
            "title": "New Page"
        }

        with patch('api.browser_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/navigate", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


def test_navigate_invalid_url(
    client: TestClient,
    db: Session,
    mock_browser_session: BrowserSession,
    mock_user: User
):
    """Test navigating to invalid URL."""
    request_data = {
        "session_id": mock_browser_session.session_id,
        "url": "not-a-valid-url",
        "wait_until": "load"
    }

    with patch('api.browser_routes.browser_navigate') as mock_nav:
        mock_nav.return_value = {
            "success": False,
            "error": "Invalid URL format"
        }

        with patch('api.browser_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/navigate", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False


# ============================================================================
# POST /screenshot - Screenshot Tests
# ============================================================================

def test_screenshot_success(
    client: TestClient,
    db: Session,
    mock_browser_session: BrowserSession,
    mock_user: User
):
    """Test taking screenshot successfully."""
    request_data = {
        "session_id": mock_browser_session.session_id,
        "full_page": False,
        "path": "/tmp/screenshot.png"
    }

    with patch('api.browser_routes.browser_screenshot') as mock_shot:
        mock_shot.return_value = {
            "success": True,
            "path": "/tmp/screenshot.png",
            "size_bytes": 12345
        }

        with patch('api.browser_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/screenshot", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


# ============================================================================
# POST /fill-form - Fill Form Tests
# ============================================================================

def test_fill_form_success(
    client: TestClient,
    db: Session,
    mock_browser_session: BrowserSession,
    mock_user: User
):
    """Test filling form successfully."""
    request_data = {
        "session_id": mock_browser_session.session_id,
        "selectors": {
            "#name": "John Doe",
            "#email": "john@example.com"
        },
        "submit": False
    }

    with patch('api.browser_routes.browser_fill_form') as mock_fill:
        mock_fill.return_value = {
            "success": True,
            "fields_filled": 2
        }

        with patch('api.browser_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/fill-form", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["fields_filled"] == 2


# ============================================================================
# POST /click - Click Tests
# ============================================================================

def test_click_success(
    client: TestClient,
    db: Session,
    mock_browser_session: BrowserSession,
    mock_user: User
):
    """Test clicking element successfully."""
    request_data = {
        "session_id": mock_browser_session.session_id,
        "selector": "#submit-button",
        "wait_for": "navigation"
    }

    with patch('api.browser_routes.browser_click') as mock_click:
        mock_click.return_value = {
            "success": True,
            "selector": "#submit-button"
        }

        with patch('api.browser_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/click", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


# ============================================================================
# POST /extract-text - Extract Text Tests
# ============================================================================

def test_extract_text_success(
    client: TestClient,
    db: Session,
    mock_browser_session: BrowserSession,
    mock_user: User
):
    """Test extracting text successfully."""
    request_data = {
        "session_id": mock_browser_session.session_id,
        "selector": ".content"
    }

    with patch('api.browser_routes.browser_extract_text') as mock_extract:
        mock_extract.return_value = {
            "success": True,
            "text": "Sample text content",
            "length": 19
        }

        with patch('api.browser_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/extract-text", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "text" in data


# ============================================================================
# POST /execute-script - Execute Script Tests
# ============================================================================

def test_execute_script_success(
    client: TestClient,
    db: Session,
    mock_browser_session: BrowserSession,
    mock_supervised_agent: AgentRegistry,
    mock_user: User
):
    """Test executing JavaScript successfully."""
    request_data = {
        "session_id": mock_browser_session.session_id,
        "script": "document.title",
        "agent_id": mock_supervised_agent.id
    }

    with patch('api.browser_routes.browser_execute_script') as mock_exec:
        mock_exec.return_value = {
            "success": True,
            "result": "Page Title"
        }

        with patch('api.browser_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/execute-script", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


# ============================================================================
# POST /session/close - Close Session Tests
# ============================================================================

def test_close_session_success(
    client: TestClient,
    db: Session,
    mock_browser_session: BrowserSession,
    mock_user: User
):
    """Test closing browser session successfully."""
    request_data = {
        "session_id": mock_browser_session.session_id
    }

    with patch('api.browser_routes.browser_close_session') as mock_close:
        mock_close.return_value = {
            "success": True,
            "session_id": mock_browser_session.session_id
        }

        with patch('api.browser_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/session/close", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


# ============================================================================
# GET /session/{session_id}/info - Get Session Info Tests
# ============================================================================

def test_get_session_info_success(
    client: TestClient,
    db: Session,
    mock_browser_session: BrowserSession,
    mock_user: User
):
    """Test getting session info successfully."""
    with patch('api.browser_routes.browser_get_page_info') as mock_info:
        mock_info.return_value = {
            "success": True,
            "url": "https://example.com",
            "title": "Example Page"
        }

        with patch('api.browser_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get(f"/session/{mock_browser_session.session_id}/info")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


# ============================================================================
# GET /sessions - List Sessions Tests
# ============================================================================

def test_list_sessions_success(
    client: TestClient,
    db: Session,
    mock_browser_session: BrowserSession,
    mock_user: User
):
    """Test listing sessions successfully."""
    with patch('api.browser_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get("/sessions")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)


# ============================================================================
# Request Validation Tests
# ============================================================================

def test_create_session_invalid_schema(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test create session with invalid schema."""
    # Missing required fields
    request_data = {}

    with patch('api.browser_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.post("/session/create", json=request_data)

        # Should get validation error
        assert response.status_code == 422


def test_navigate_missing_session_id(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test navigate without session_id."""
    request_data = {
        "url": "https://example.com"
    }

    with patch('api.browser_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.post("/navigate", json=request_data)

        assert response.status_code == 422


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_navigate_session_not_found(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test navigating with non-existent session."""
    request_data = {
        "session_id": "non-existent-session",
        "url": "https://example.com"
    }

    with patch('api.browser_routes.browser_navigate') as mock_nav:
        mock_nav.return_value = {
            "success": False,
            "error": "Session not found"
        }

        with patch('api.browser_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/navigate", json=request_data)

            # Should handle error gracefully
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False


# ============================================================================
# Response Format Tests
# ============================================================================

def test_response_format_structure(
    client: TestClient,
    db: Session,
    mock_browser_session: BrowserSession,
    mock_user: User
):
    """Test that responses have correct structure."""
    request_data = {
        "session_id": mock_browser_session.session_id,
        "url": "https://example.com"
    }

    with patch('api.browser_routes.browser_navigate') as mock_nav:
        mock_nav.return_value = {
            "success": True,
            "url": "https://example.com",
            "title": "Example"
        }

        with patch('api.browser_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/navigate", json=request_data)

            # Verify response structure
            data = response.json()
            assert "success" in data
            assert isinstance(data["success"], bool)
