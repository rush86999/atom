"""
Canvas Routes Integration Tests

Tests for canvas presentation and form submission endpoints from api/canvas_routes.py.

Coverage (ported to the current canvas API surface):
- POST /submit - Form submission with governance (AgentGovernanceService)
- GET /types - Canvas type discovery (replaces the removed GET /status endpoint)
- Authentication/authorization
- Governance enforcement (SUPERVISED+ required for canvas_submit)
- Request validation
- Error handling (governance failure, non-fatal audit persistence failure)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, HTTPException
from sqlalchemy.orm import Session

from api import canvas_routes
from api.canvas_routes import router
from core.models import AgentRegistry, User


# ============================================================================
# Fixtures
# ============================================================================

# Global storage for test user - modified by patches
_current_test_user = None


@pytest.fixture
def app_with_overrides(db: Session):
    """Create FastAPI app with dependency overrides for testing."""
    global _current_test_user
    _current_test_user = None

    app = FastAPI()
    app.include_router(router)

    from core.database import get_db

    def override_get_db():
        yield db

    def override_get_current_user():
        # Mirrors core.auth.get_current_user: no credentials -> 401
        if _current_test_user is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
        return _current_test_user

    app.dependency_overrides[get_db] = override_get_db
    # canvas_routes imports get_current_user from core.auth at module load,
    # so override the object the router actually registered.
    app.dependency_overrides[canvas_routes.get_current_user] = override_get_current_user

    yield app

    app.dependency_overrides.clear()
    _current_test_user = None


@pytest.fixture
def client(app_with_overrides: FastAPI):
    """Create TestClient with overridden dependencies."""
    return TestClient(app_with_overrides, raise_server_exceptions=False)


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
def mock_student_agent(db: Session):
    """Create STUDENT maturity agent."""
    import uuid
    agent_id = str(uuid.uuid4())
    agent = AgentRegistry(
        id=agent_id,
        name=f"Student Agent {agent_id[:8]}",
        category="testing",
        status="student",
        confidence_score=0.3,
        module_path="test.module",
        class_name="TestClass"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def mock_intern_agent(db: Session):
    """Create INTERN maturity agent."""
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
def mock_autonomous_agent(db: Session):
    """Create AUTONOMOUS maturity agent."""
    import uuid
    agent_id = str(uuid.uuid4())
    agent = AgentRegistry(
        id=agent_id,
        name=f"Autonomous Agent {agent_id[:8]}",
        category="testing",
        status="autonomous",
        confidence_score=0.95,
        module_path="test.module",
        class_name="TestClass"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


# ============================================================================
# POST /submit - Form Submission Tests
# ============================================================================

def test_submit_form_success_supervised_agent(
    client: TestClient,
    db: Session,
    mock_supervised_agent: AgentRegistry,
    mock_user: User
):
    """Test form submission with SUPERVISED agent (allowed: canvas_submit is complexity 3)."""
    global _current_test_user
    _current_test_user = mock_user

    form_data = {
        "canvas_id": "test-canvas-123",
        "form_data": {
            "name": "John Doe",
            "email": "john@example.com",
            "message": "Test message"
        },
        "agent_id": mock_supervised_agent.id
    }

    # Audit persistence opens its own session; failure is non-fatal, but stub
    # it so the test targets the route contract only.
    with patch('core.database.get_db_session') as mock_session_ctx:
        mock_session_ctx.return_value.__enter__.return_value = MagicMock()
        response = client.post("/api/canvas/submit", json=form_data)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["canvas_id"] == "test-canvas-123"
    assert data["data"]["submitted"] is True
    assert "timestamp" in data["data"]

    # The submission must have gone through the governance service
    with patch.object(
        canvas_routes.AgentGovernanceService,
        'can_perform_action',
        return_value={"allowed": False, "reason": "blocked"}
    ) as mock_check:
        blocked = client.post("/api/canvas/submit", json=form_data)
        assert blocked.status_code == 403
        mock_check.assert_called_once()


def test_submit_form_success_autonomous_agent(
    client: TestClient,
    db: Session,
    mock_autonomous_agent: AgentRegistry,
    mock_user: User
):
    """Test form submission with AUTONOMOUS agent (allowed)."""
    global _current_test_user
    _current_test_user = mock_user

    form_data = {
        "canvas_id": "test-canvas-456",
        "form_data": {
            "product": "Widget",
            "quantity": 10
        },
        "agent_id": mock_autonomous_agent.id
    }

    with patch('core.database.get_db_session') as mock_session_ctx:
        mock_session_ctx.return_value.__enter__.return_value = MagicMock()
        response = client.post("/api/canvas/submit", json=form_data)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["canvas_id"] == "test-canvas-456"


def test_submit_form_blocked_student_agent(
    client: TestClient,
    db: Session,
    mock_student_agent: AgentRegistry,
    mock_user: User
):
    """Test form submission with STUDENT agent (blocked - requires SUPERVISED+)."""
    global _current_test_user
    _current_test_user = mock_user

    form_data = {
        "canvas_id": "test-canvas-789",
        "form_data": {
            "field1": "value1"
        },
        "agent_id": mock_student_agent.id
    }

    response = client.post("/api/canvas/submit", json=form_data)

    # Should be blocked with 403 Forbidden
    assert response.status_code == 403
    data = response.json()
    # Error responses are wrapped in 'detail' key
    error_data = data.get("detail", data)
    assert error_data["success"] is False
    error_msg = error_data.get("error", {}).get("message", str(error_data))
    assert "governance" in error_msg.lower() or "permission" in error_msg.lower() or "maturity" in error_msg.lower()


def test_submit_form_blocked_intern_agent(
    client: TestClient,
    db: Session,
    mock_intern_agent: AgentRegistry,
    mock_user: User
):
    """Test form submission with INTERN agent (blocked - requires SUPERVISED+)."""
    global _current_test_user
    _current_test_user = mock_user

    form_data = {
        "canvas_id": "test-canvas-101",
        "form_data": {
            "field1": "value1"
        },
        "agent_id": mock_intern_agent.id
    }

    response = client.post("/api/canvas/submit", json=form_data)

    assert response.status_code == 403
    data = response.json()
    # Error responses are wrapped in 'detail' key
    error_data = data.get("detail", data)
    assert error_data["success"] is False


def test_submit_form_no_agent(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test form submission without agent (user-initiated, allowed)."""
    global _current_test_user
    _current_test_user = mock_user

    form_data = {
        "canvas_id": "test-canvas-202",
        "form_data": {
            "name": "Jane Doe",
            "email": "jane@example.com"
        }
        # No agent_id provided - user is submitting directly
    }

    with patch('core.database.get_db_session') as mock_session_ctx:
        mock_session_ctx.return_value.__enter__.return_value = MagicMock()
        response = client.post("/api/canvas/submit", json=form_data)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["submitted"] is True


def test_submit_form_invalid_schema(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test form submission with invalid request schema."""
    global _current_test_user
    _current_test_user = mock_user

    # Missing required field 'canvas_id'
    form_data = {
        "form_data": {
            "field1": "value1"
        }
    }

    response = client.post("/api/canvas/submit", json=form_data)

    # FastAPI validation error
    assert response.status_code == 422


def test_submit_form_empty_form_data(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test form submission with empty form data."""
    global _current_test_user
    _current_test_user = mock_user

    form_data = {
        "canvas_id": "test-canvas-303",
        "form_data": {}
    }

    with patch('core.database.get_db_session') as mock_session_ctx:
        mock_session_ctx.return_value.__enter__.return_value = MagicMock()
        response = client.post("/api/canvas/submit", json=form_data)

    # Empty form data should still succeed
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_submit_form_with_agent_execution_id(
    client: TestClient,
    db: Session,
    mock_supervised_agent: AgentRegistry,
    mock_user: User
):
    """Test form submission linked to an agent execution."""
    execution_id = "exec-12345"

    global _current_test_user
    _current_test_user = mock_user

    form_data = {
        "canvas_id": "test-canvas-404",
        "form_data": {
            "action": "approve"
        },
        "agent_id": mock_supervised_agent.id,
        "agent_execution_id": execution_id
    }

    with patch('core.database.get_db_session') as mock_session_ctx:
        mock_session_ctx.return_value.__enter__.return_value = MagicMock()
        response = client.post("/api/canvas/submit", json=form_data)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


# ============================================================================
# GET /types - Canvas Type Discovery Tests
# (ported from the removed GET /status endpoint; /types is the current
#  metadata/discovery endpoint on this router)
# ============================================================================

def test_get_canvas_types_authenticated(
    client: TestClient,
    db: Session,
    mock_student_agent: AgentRegistry
):
    """Test canvas type discovery with a valid agent (read access is STUDENT+)."""
    response = client.get(f"/api/canvas/types?agent_id={mock_student_agent.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "canvas_types" in data["data"]
    assert isinstance(data["data"]["canvas_types"], dict)
    assert "docs" in data["data"]["canvas_types"]
    assert "terminal" in data["data"]["canvas_types"]


def test_get_canvas_types_catalog(
    client: TestClient,
    db: Session,
    mock_student_agent: AgentRegistry
):
    """Test that canvas type discovery returns the expected catalog."""
    expected_types = [
        "generic",
        "docs",
        "email",
        "sheets",
        "orchestration",
        "terminal",
        "coding"
    ]

    response = client.get(f"/api/canvas/types?agent_id={mock_student_agent.id}")

    assert response.status_code == 200
    data = response.json()
    returned_types = data["data"]["canvas_types"]

    # Verify all expected types are present
    for canvas_type in expected_types:
        assert canvas_type in returned_types, f"Expected canvas type '{canvas_type}' not found"


# ============================================================================
# Authentication Tests
# ============================================================================

def test_submit_form_unauthenticated(
    client: TestClient
):
    """Test form submission without authentication."""
    # Don't set _current_test_user - auth dependency rejects the request
    form_data = {
        "canvas_id": "test-canvas-505",
        "form_data": {
            "field1": "value1"
        }
    }

    response = client.post("/api/canvas/submit", json=form_data)

    # Should get authentication error (401, matching core.auth behavior)
    assert response.status_code == 401


def test_list_canvases_unauthenticated(
    client: TestClient
):
    """Test listing canvases without authentication."""
    with patch('tools.canvas_crud_tool.list_canvases', new=AsyncMock(return_value=[])):
        response = client.get("/api/canvas/")

    # Should get authentication error (401, matching core.auth behavior)
    assert response.status_code == 401


# ============================================================================
# Governance Bypass Tests
# ============================================================================

# NOTE: the old governance-disabled test was removed together with the
# FeatureFlags.should_enforce_governance('form') switch: the current route
# always enforces governance when an agent_id is supplied.

# ============================================================================
# Error Handling Tests
# ============================================================================

def test_submit_form_database_error(
    client: TestClient,
    db: Session,
    mock_supervised_agent: AgentRegistry,
    mock_user: User
):
    """Test form submission when the governance lookup raises a database error."""
    global _current_test_user
    _current_test_user = mock_user

    form_data = {
        "canvas_id": "test-canvas-707",
        "form_data": {
            "field1": "value1"
        },
        "agent_id": mock_supervised_agent.id
    }

    with patch(
        'api.canvas_routes.AgentGovernanceService',
        side_effect=Exception("Database connection failed")
    ):
        response = client.post("/api/canvas/submit", json=form_data)

    # Unhandled governance failure surfaces as a 500
    assert response.status_code == 500


def test_submit_form_persistence_error(
    client: TestClient,
    db: Session,
    mock_supervised_agent: AgentRegistry,
    mock_user: User
):
    """Test form submission when audit persistence fails (must degrade gracefully).

    Ported from the old WebSocket-broadcast-error test: audit-trail persistence
    is the current side-channel, and the route documents it as non-fatal.
    """
    global _current_test_user
    _current_test_user = mock_user

    form_data = {
        "canvas_id": "test-canvas-808",
        "form_data": {
            "field1": "value1"
        },
        "agent_id": mock_supervised_agent.id
    }

    with patch(
        'core.database.get_db_session',
        side_effect=Exception("Audit store unavailable")
    ):
        response = client.post("/api/canvas/submit", json=form_data)

    # Persistence failure is non-fatal: submission still succeeds
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["submitted"] is True


# ============================================================================
# Response Format Tests
# ============================================================================

def test_submit_form_response_structure(
    client: TestClient,
    db: Session,
    mock_supervised_agent: AgentRegistry,
    mock_user: User
):
    """Test that form submission response has correct structure."""
    global _current_test_user
    _current_test_user = mock_user

    form_data = {
        "canvas_id": "test-canvas-909",
        "form_data": {
            "name": "Test User",
            "email": "test@example.com"
        },
        "agent_id": mock_supervised_agent.id
    }

    with patch('core.database.get_db_session') as mock_session_ctx:
        mock_session_ctx.return_value.__enter__.return_value = MagicMock()
        response = client.post("/api/canvas/submit", json=form_data)

    assert response.status_code == 200

    # Verify response structure
    body = response.json()
    assert "success" in body
    assert "data" in body
    assert "timestamp" in body

    data = body["data"]
    assert data["canvas_id"] == "test-canvas-909"
    assert data["submitted"] is True
    assert isinstance(data["timestamp"], str)


def test_get_types_response_structure(
    client: TestClient,
    db: Session,
    mock_student_agent: AgentRegistry
):
    """Test that canvas type discovery response has correct structure."""
    response = client.get(f"/api/canvas/types?agent_id={mock_student_agent.id}")

    # Verify response structure
    data = response.json()
    assert "success" in data
    assert "data" in data

    assert isinstance(data["data"], dict)
    assert "canvas_types" in data["data"]
