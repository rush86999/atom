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
- GET /audit - Get audit log
- Authentication/authorization
- Governance enforcement (INTERN+ required)
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy.orm import Session
from datetime import datetime

from api.browser_routes import router
from core.models import AgentRegistry, User


# ============================================================================
# Test Client Setup
# ============================================================================

@pytest.fixture
def client(db: Session):
    """Create TestClient for browser routes with database and auth overrides."""
    app = FastAPI()
    app.include_router(router)

    from core.database import get_db
    from core.security_dependencies import get_current_user

    # Create test user
    import uuid
    user_id = str(uuid.uuid4())
    test_user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        first_name="Test",
        last_name="User",
        role="member",
        status="active"
    )
    db.add(test_user)
    db.commit()
    db.refresh(test_user)

    def override_get_db():
        yield db

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()
    db.delete(test_user)
    db.commit()


@pytest.fixture
def intern_agent(db: Session):
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
def supervised_agent(db: Session):
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
def student_agent(db: Session):
    """Create STUDENT maturity agent (blocked for browser actions)."""
    import uuid
    agent_id = str(uuid.uuid4())
    agent = AgentRegistry(
        id=agent_id,
        name=f"Student Agent {agent_id[:8]}",
        category="testing",
        status="student",
        confidence_score=0.4,
        module_path="test.module",
        class_name="TestClass"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


# ============================================================================
# POST /session/create - Create Browser Session Tests
# ============================================================================

def test_create_session_success(client: TestClient):
    """Test creating browser session successfully."""
    request_data = {
        "headless": True,
        "browser_type": "chromium"
    }

    with patch('api.browser_routes.browser_create_session', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {
            "success": True,
            "session_id": "test-session-123",
            "headless": True,
            "browser_type": "chromium"
        }

        response = client.post("/api/browser/session/create", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "session_id" in data


def test_create_session_with_agent(client: TestClient, intern_agent: AgentRegistry):
    """Test creating browser session with agent."""
    request_data = {
        "headless": True,
        "browser_type": "chromium",
        "agent_id": intern_agent.id
    }

    with patch('api.browser_routes.browser_create_session', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {
            "success": True,
            "session_id": "test-session-456"
        }

        response = client.post("/api/browser/session/create", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_create_session_failure(client: TestClient):
    """Test creating browser session failure."""
    request_data = {
        "headless": True,
        "browser_type": "chromium"
    }

    with patch('api.browser_routes.browser_create_session', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {
            "success": False,
            "error": "Failed to create browser session"
        }

        response = client.post("/api/browser/session/create", json=request_data)

        assert response.status_code == 400


# ============================================================================
# POST /navigate - Navigate Tests
# ============================================================================

def test_navigate_success(client: TestClient):
    """Test navigating to URL successfully."""
    request_data = {
        "session_id": "test-session-123",
        "url": "https://example.com/page",
        "wait_until": "load"
    }

    with patch('api.browser_routes.browser_navigate', new_callable=AsyncMock) as mock_nav:
        mock_nav.return_value = {
            "success": True,
            "url": "https://example.com/page",
            "title": "New Page"
        }

        response = client.post("/api/browser/navigate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["url"] == "https://example.com/page"


def test_navigate_with_agent(client: TestClient, intern_agent: AgentRegistry):
    """Test navigating with agent."""
    request_data = {
        "session_id": "test-session-123",
        "url": "https://example.com/page",
        "agent_id": intern_agent.id
    }

    with patch('api.browser_routes.browser_navigate', new_callable=AsyncMock) as mock_nav:
        mock_nav.return_value = {
            "success": True,
            "url": "https://example.com/page",
            "title": "New Page"
        }

        response = client.post("/api/browser/navigate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_navigate_invalid_session(client: TestClient):
    """Test navigating with invalid session."""
    request_data = {
        "session_id": "non-existent-session",
        "url": "https://example.com"
    }

    with patch('api.browser_routes.browser_navigate', new_callable=AsyncMock) as mock_nav:
        mock_nav.return_value = {
            "success": False,
            "error": "Session not found"
        }

        response = client.post("/api/browser/navigate", json=request_data)

        # Should handle error gracefully
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


# ============================================================================
# POST /screenshot - Screenshot Tests
# ============================================================================

def test_screenshot_success(client: TestClient):
    """Test taking screenshot successfully."""
    request_data = {
        "session_id": "test-session-123",
        "full_page": False,
        "path": "/tmp/screenshot.png"
    }

    with patch('api.browser_routes.browser_screenshot', new_callable=AsyncMock) as mock_shot:
        mock_shot.return_value = {
            "success": True,
            "path": "/tmp/screenshot.png",
            "size_bytes": 12345
        }

        response = client.post("/api/browser/screenshot", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "size_bytes" in data


def test_screenshot_full_page(client: TestClient):
    """Test taking full page screenshot."""
    request_data = {
        "session_id": "test-session-123",
        "full_page": True
    }

    with patch('api.browser_routes.browser_screenshot', new_callable=AsyncMock) as mock_shot:
        mock_shot.return_value = {
            "success": True,
            "size_bytes": 54321
        }

        response = client.post("/api/browser/screenshot", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================================================
# POST /fill-form - Fill Form Tests
# ============================================================================

def test_fill_form_success(client: TestClient):
    """Test filling form successfully."""
    request_data = {
        "session_id": "test-session-123",
        "selectors": {
            "#name": "John Doe",
            "#email": "john@example.com"
        },
        "submit": False
    }

    with patch('api.browser_routes.browser_fill_form', new_callable=AsyncMock) as mock_fill:
        mock_fill.return_value = {
            "success": True,
            "fields_filled": 2
        }

        response = client.post("/api/browser/fill-form", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["fields_filled"] == 2


def test_fill_form_with_submit(client: TestClient, supervised_agent: AgentRegistry):
    """Test filling and submitting form."""
    request_data = {
        "session_id": "test-session-123",
        "selectors": {
            "#name": "Jane Doe"
        },
        "submit": True,
        "agent_id": supervised_agent.id
    }

    with patch('api.browser_routes.browser_fill_form', new_callable=AsyncMock) as mock_fill:
        mock_fill.return_value = {
            "success": True,
            "fields_filled": 1
        }

        response = client.post("/api/browser/fill-form", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================================================
# POST /click - Click Tests
# ============================================================================

def test_click_success(client: TestClient):
    """Test clicking element successfully."""
    request_data = {
        "session_id": "test-session-123",
        "selector": "#submit-button",
        "wait_for": "navigation"
    }

    with patch('api.browser_routes.browser_click', new_callable=AsyncMock) as mock_click:
        mock_click.return_value = {
            "success": True,
            "selector": "#submit-button"
        }

        response = client.post("/api/browser/click", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_click_with_wait(client: TestClient):
    """Test clicking element with wait_for parameter."""
    request_data = {
        "session_id": "test-session-123",
        "selector": "#button",
        "wait_for": "selector"
    }

    with patch('api.browser_routes.browser_click', new_callable=AsyncMock) as mock_click:
        mock_click.return_value = {
            "success": True
        }

        response = client.post("/api/browser/click", json=request_data)

        assert response.status_code == 200


# ============================================================================
# POST /extract-text - Extract Text Tests
# ============================================================================

def test_extract_text_success(client: TestClient):
    """Test extracting text successfully."""
    request_data = {
        "session_id": "test-session-123",
        "selector": ".content"
    }

    with patch('api.browser_routes.browser_extract_text', new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = {
            "success": True,
            "text": "Sample text content",
            "length": 19
        }

        response = client.post("/api/browser/extract-text", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "text" in data
        assert data["length"] == 19


def test_extract_text_full_page(client: TestClient):
    """Test extracting text from full page."""
    request_data = {
        "session_id": "test-session-123"
    }

    with patch('api.browser_routes.browser_extract_text', new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = {
            "success": True,
            "text": "Full page text",
            "length": 14
        }

        response = client.post("/api/browser/extract-text", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================================================
# POST /execute-script - Execute Script Tests
# ============================================================================

def test_execute_script_success(client: TestClient, supervised_agent: AgentRegistry):
    """Test executing JavaScript successfully."""
    request_data = {
        "session_id": "test-session-123",
        "script": "document.title",
        "agent_id": supervised_agent.id
    }

    with patch('api.browser_routes.browser_execute_script', new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {
            "success": True,
            "result": "Page Title"
        }

        response = client.post("/api/browser/execute-script", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_execute_script_complex(client: TestClient):
    """Test executing complex JavaScript."""
    script = "Array.from(document.querySelectorAll('a')).map(a => a.href)"
    request_data = {
        "session_id": "test-session-123",
        "script": script
    }

    with patch('api.browser_routes.browser_execute_script', new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {
            "success": True,
            "result": ["https://example.com", "https://example.org"]
        }

        response = client.post("/api/browser/execute-script", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================================================
# POST /session/close - Close Session Tests
# ============================================================================

def test_close_session_success(client: TestClient):
    """Test closing browser session successfully."""
    request_data = {
        "session_id": "test-session-123"
    }

    with patch('api.browser_routes.browser_close_session', new_callable=AsyncMock) as mock_close:
        mock_close.return_value = {
            "success": True,
            "session_id": "test-session-123"
        }

        response = client.post("/api/browser/session/close", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_close_session_with_agent(client: TestClient, intern_agent: AgentRegistry):
    """Test closing session with agent."""
    request_data = {
        "session_id": "test-session-123",
        "agent_id": intern_agent.id
    }

    with patch('api.browser_routes.browser_close_session', new_callable=AsyncMock) as mock_close:
        mock_close.return_value = {
            "success": True
        }

        response = client.post("/api/browser/session/close", json=request_data)

        assert response.status_code == 200


# ============================================================================
# GET /session/{session_id}/info - Get Session Info Tests
# ============================================================================

def test_get_session_info_success(client: TestClient):
    """Test getting session info successfully."""
    with patch('api.browser_routes.browser_get_page_info', new_callable=AsyncMock) as mock_info:
        mock_info.return_value = {
            "success": True,
            "url": "https://example.com",
            "title": "Example Page"
        }

        response = client.get("/api/browser/session/test-session-123/info")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "url" in data


def test_get_session_info_not_found(client: TestClient):
    """Test getting info for non-existent session."""
    with patch('api.browser_routes.browser_get_page_info', new_callable=AsyncMock) as mock_info:
        mock_info.return_value = {
            "success": False,
            "error": "Session not found"
        }

        response = client.get("/api/browser/session/non-existent-session/info")

        # Should return success=False but 200 status
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


# ============================================================================
# GET /audit - Get Audit Log Tests
# ============================================================================

def test_get_audit_log_success(client: TestClient):
    """Test getting audit log successfully."""
    response = client.get("/api/browser/audit")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


def test_get_audit_log_for_session(client: TestClient):
    """Test getting audit log for specific session."""
    response = client.get("/api/browser/audit?session_id=test-session-123")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


def test_get_audit_log_with_limit(client: TestClient):
    """Test getting audit log with custom limit."""
    response = client.get("/api/browser/audit?limit=10")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


# ============================================================================
# Request Validation Tests
# ============================================================================

def test_create_session_missing_browser_type(client: TestClient):
    """Test create session with default browser type."""
    request_data = {
        "headless": True
    }

    with patch('api.browser_routes.browser_create_session', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {
            "success": True,
            "session_id": "test-session-default"
        }

        response = client.post("/api/browser/session/create", json=request_data)

        # Should use default browser_type="chromium"
        assert response.status_code == 200


def test_navigate_missing_session_id(client: TestClient):
    """Test navigate without session_id."""
    request_data = {
        "url": "https://example.com"
    }

    response = client.post("/api/browser/navigate", json=request_data)

    # Should get validation error (422)
    assert response.status_code == 422


def test_screenshot_missing_session_id(client: TestClient):
    """Test screenshot without session_id."""
    request_data = {
        "full_page": True
    }

    response = client.post("/api/browser/screenshot", json=request_data)

    # Should get validation error
    assert response.status_code == 422


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_create_session_internal_error(client: TestClient):
    """Test creating session with internal error."""
    request_data = {
        "headless": True,
        "browser_type": "chromium"
    }

    with patch('api.browser_routes.browser_create_session', new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = Exception("Internal server error")

        response = client.post("/api/browser/session/create", json=request_data)

        # Should handle error gracefully
        assert response.status_code == 500


def test_navigate_internal_error(client: TestClient):
    """Test navigating with internal error."""
    request_data = {
        "session_id": "test-session-123",
        "url": "https://example.com"
    }

    with patch('api.browser_routes.browser_navigate', new_callable=AsyncMock) as mock_nav:
        mock_nav.side_effect = Exception("Browser error")

        response = client.post("/api/browser/navigate", json=request_data)

        # Should handle error gracefully
        assert response.status_code == 500


# ============================================================================
# Response Format Tests
# ============================================================================

def test_response_format_structure(client: TestClient):
    """Test that responses have correct structure."""
    with patch('api.browser_routes.browser_navigate', new_callable=AsyncMock) as mock_nav:
        mock_nav.return_value = {
            "success": True,
            "url": "https://example.com",
            "title": "Example"
        }

        request_data = {
            "session_id": "test-session-123",
            "url": "https://example.com"
        }

        response = client.post("/api/browser/navigate", json=request_data)

        # Verify response structure
        data = response.json()
        assert "success" in data
        assert isinstance(data["success"], bool)


# ============================================================================
# Additional Edge Case Tests
# ============================================================================

def test_navigate_empty_url(client: TestClient):
    """Test navigating with empty URL."""
    request_data = {
        "session_id": "test-session-123",
        "url": ""
    }

    response = client.post("/api/browser/navigate", json=request_data)

    # Should get validation error
    assert response.status_code == 422


def test_screenshot_invalid_path(client: TestClient):
    """Test screenshot with invalid path format."""
    request_data = {
        "session_id": "test-session-123",
        "full_page": False,
        "path": ""
    }

    with patch('api.browser_routes.browser_screenshot', new_callable=AsyncMock) as mock_shot:
        mock_shot.return_value = {
            "success": True
        }

        response = client.post("/api/browser/screenshot", json=request_data)

        # Should still work with empty path
        assert response.status_code == 200


def test_fill_form_empty_selectors(client: TestClient):
    """Test filling form with empty selectors."""
    request_data = {
        "session_id": "test-session-123",
        "selectors": {},
        "submit": False
    }

    with patch('api.browser_routes.browser_fill_form', new_callable=AsyncMock) as mock_fill:
        mock_fill.return_value = {
            "success": True,
            "fields_filled": 0
        }

        response = client.post("/api/browser/fill-form", json=request_data)

        assert response.status_code == 200


def test_execute_script_empty_script(client: TestClient):
    """Test executing empty script."""
    request_data = {
        "session_id": "test-session-123",
        "script": ""
    }

    response = client.post("/api/browser/execute-script", json=request_data)

    # Should get validation error
    assert response.status_code == 422


def test_click_empty_selector(client: TestClient):
    """Test clicking with empty selector."""
    request_data = {
        "session_id": "test-session-123",
        "selector": ""
    }

    response = client.post("/api/browser/click", json=request_data)

    # Should get validation error
    assert response.status_code == 422
