"""
Canvas Routes Integration Tests

Tests for canvas presentation and form submission endpoints from api/canvas_routes.py.

Coverage:
- POST /submit - Form submission with governance
- GET /status - Canvas status check
- Authentication/authorization
- Governance enforcement (SUPERVISED+ required for form submission)
- Request validation
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy.orm import Session

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
    from core.security_dependencies import get_current_user

    def override_get_db():
        yield db

    def override_get_current_user():
        return _current_test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

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
    """Test form submission with SUPERVISED agent (allowed)."""
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

    # Mock dependencies
    with patch('api.canvas_routes.ws_manager') as mock_ws:
        mock_ws.broadcast = AsyncMock()

        with patch('api.canvas_routes.FeatureFlags') as mock_ff:
            mock_ff.should_enforce_governance.return_value = True

            with patch('api.canvas_routes.ServiceFactory') as mock_sf:
                mock_governance = MagicMock()
                mock_governance.can_perform_action.return_value = {
                    "allowed": True,
                    "reason": None
                }
                mock_governance.record_outcome = AsyncMock()
                mock_sf.get_governance_service.return_value = mock_governance

                response = client.post("/api/canvas/submit", json=form_data)

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "submission_id" in data["data"]
                assert data["data"]["agent_id"] == mock_supervised_agent.id
                assert "governance_check" in data["data"]

                # Verify WebSocket broadcast was called
                mock_ws.broadcast.assert_called_once()

                # Verify governance check was performed
                mock_governance.can_perform_action.assert_called_once_with(
                    agent_id=mock_supervised_agent.id,
                    action_type="submit_form"
                )

                # Verify outcome was recorded
                mock_governance.record_outcome.assert_called_once_with(
                    mock_supervised_agent.id,
                    success=True
                )


def test_submit_form_success_autonomous_agent(
    client: TestClient,
    db: Session,
    mock_autonomous_agent: AgentRegistry,
    mock_user: User
):
    """Test form submission with AUTONOMOUS agent (allowed)."""
    form_data = {
        "canvas_id": "test-canvas-456",
        "form_data": {
            "product": "Widget",
            "quantity": 10
        },
        "agent_id": mock_autonomous_agent.id
    }

    with patch('api.canvas_routes.ws_manager') as mock_ws:
        mock_ws.broadcast = AsyncMock()

        with patch('api.canvas_routes.FeatureFlags') as mock_ff:
            mock_ff.should_enforce_governance.return_value = True

            with patch('api.canvas_routes.ServiceFactory') as mock_sf:
                mock_governance = MagicMock()
                mock_governance.can_perform_action.return_value = {
                    "allowed": True,
                    "reason": None
                }
                mock_governance.record_outcome = AsyncMock()
                mock_sf.get_governance_service.return_value = mock_governance

                global _current_test_user
                _current_test_user = mock_user

                response = client.post("/api/canvas/submit", json=form_data)

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["data"]["agent_id"] == mock_autonomous_agent.id


def test_submit_form_blocked_student_agent(
    client: TestClient,
    db: Session,
    mock_student_agent: AgentRegistry,
    mock_user: User
):
    """Test form submission with STUDENT agent (blocked - requires SUPERVISED+)."""
    form_data = {
        "canvas_id": "test-canvas-789",
        "form_data": {
            "field1": "value1"
        },
        "agent_id": mock_student_agent.id
    }

    with patch('api.canvas_routes.FeatureFlags') as mock_ff:
        mock_ff.should_enforce_governance.return_value = True

        with patch('api.canvas_routes.ServiceFactory') as mock_sf:
            mock_governance = MagicMock()
            mock_governance.can_perform_action.return_value = {
                "allowed": False,
                "reason": "Agent maturity level STUDENT cannot perform action submit_form (requires SUPERVISED)"
            }
            mock_sf.get_governance_service.return_value = mock_governance

            with patch('api.canvas_routes.get_current_user') as mock_auth:
                mock_auth.return_value = mock_user

                response = client.post("/api/canvas/submit", json=form_data)

                # Should be blocked with 403 Forbidden
                assert response.status_code == 403
                data = response.json()
                assert data["success"] is False
                assert "governance" in data["error"].lower() or "permission" in data["error"].lower()


def test_submit_form_blocked_intern_agent(
    client: TestClient,
    db: Session,
    mock_intern_agent: AgentRegistry,
    mock_user: User
):
    """Test form submission with INTERN agent (blocked - requires SUPERVISED+)."""
    form_data = {
        "canvas_id": "test-canvas-101",
        "form_data": {
            "field1": "value1"
        },
        "agent_id": mock_intern_agent.id
    }

    with patch('api.canvas_routes.FeatureFlags') as mock_ff:
        mock_ff.should_enforce_governance.return_value = True

        with patch('api.canvas_routes.ServiceFactory') as mock_sf:
            mock_governance = MagicMock()
            mock_governance.can_perform_action.return_value = {
                "allowed": False,
                "reason": "Agent maturity level INTERN cannot perform action submit_form (requires SUPERVISED)"
            }
            mock_sf.get_governance_service.return_value = mock_governance

            with patch('api.canvas_routes.get_current_user') as mock_auth:
                mock_auth.return_value = mock_user

                response = client.post("/api/canvas/submit", json=form_data)

                assert response.status_code == 403
                data = response.json()
                assert data["success"] is False


def test_submit_form_no_agent(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test form submission without agent (user-initiated, allowed)."""
    form_data = {
        "canvas_id": "test-canvas-202",
        "form_data": {
            "name": "Jane Doe",
            "email": "jane@example.com"
        }
        # No agent_id provided - user is submitting directly
    }

    with patch('api.canvas_routes.ws_manager') as mock_ws:
        mock_ws.broadcast = AsyncMock()

        with patch('api.canvas_routes.FeatureFlags') as mock_ff:
            mock_ff.should_enforce_governance.return_value = True

            with patch('api.canvas_routes.get_current_user') as mock_auth:
                mock_auth.return_value = mock_user

                response = client.post("/api/canvas/submit", json=form_data)

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["data"]["agent_id"] is None

                # Verify WebSocket broadcast was called
                mock_ws.broadcast.assert_called_once()


def test_submit_form_invalid_schema(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test form submission with invalid request schema."""
    # Missing required field 'canvas_id'
    form_data = {
        "form_data": {
            "field1": "value1"
        }
    }

    with patch('api.canvas_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.post("/api/canvas/submit", json=form_data)

        # FastAPI validation error
        assert response.status_code == 422


def test_submit_form_empty_form_data(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test form submission with empty form data."""
    form_data = {
        "canvas_id": "test-canvas-303",
        "form_data": {}
    }

    with patch('api.canvas_routes.ws_manager') as mock_ws:
        mock_ws.broadcast = AsyncMock()

        with patch('api.canvas_routes.FeatureFlags') as mock_ff:
            mock_ff.should_enforce_governance.return_value = True

            with patch('api.canvas_routes.get_current_user') as mock_auth:
                mock_auth.return_value = mock_user

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

    form_data = {
        "canvas_id": "test-canvas-404",
        "form_data": {
            "action": "approve"
        },
        "agent_id": mock_supervised_agent.id,
        "agent_execution_id": execution_id
    }

    with patch('api.canvas_routes.ws_manager') as mock_ws:
        mock_ws.broadcast = AsyncMock()

        with patch('api.canvas_routes.FeatureFlags') as mock_ff:
            mock_ff.should_enforce_governance.return_value = True

            with patch('api.canvas_routes.ServiceFactory') as mock_sf:
                mock_governance = MagicMock()
                mock_governance.can_perform_action.return_value = {
                    "allowed": True,
                    "reason": None
                }
                mock_governance.record_outcome = AsyncMock()
                mock_sf.get_governance_service.return_value = mock_governance

                global _current_test_user
                _current_test_user = mock_user

                response = client.post("/api/canvas/submit", json=form_data)

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True


# ============================================================================
# GET /status - Canvas Status Tests
# ============================================================================

def test_get_canvas_status_authenticated(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test getting canvas status for authenticated user."""
    with patch('api.canvas_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get("/api/canvas/status")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "active"
        assert data["data"]["user_id"] == mock_user.id
        assert "features" in data["data"]
        assert isinstance(data["data"]["features"], list)
        assert "markdown" in data["data"]["features"]
        assert "form" in data["data"]["features"]


def test_get_canvas_status_features_list(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test that canvas status returns expected features."""
    expected_features = [
        "markdown",
        "status_panel",
        "form",
        "line_chart",
        "bar_chart",
        "pie_chart"
    ]

    with patch('api.canvas_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get("/api/canvas/status")

        assert response.status_code == 200
        data = response.json()
        returned_features = data["data"]["features"]

        # Verify all expected features are present
        for feature in expected_features:
            assert feature in returned_features, f"Expected feature '{feature}' not found"


# ============================================================================
# Authentication Tests
# ============================================================================

def test_submit_form_unauthenticated(
    client: TestClient
):
    """Test form submission without authentication."""
    form_data = {
        "canvas_id": "test-canvas-505",
        "form_data": {
            "field1": "value1"
        }
    }

    # Don't mock get_current_user - should fail auth
    response = client.post("/api/canvas/submit", json=form_data)

    # Should get authentication error (422 because dependency can't be resolved)
    assert response.status_code in [401, 403, 422]


def test_get_status_unauthenticated(
    client: TestClient
):
    """Test getting canvas status without authentication."""
    # Don't mock get_current_user
    response = client.get("/status")

    # Should get authentication error
    assert response.status_code in [401, 403, 422]


# ============================================================================
# Governance Bypass Tests
# ============================================================================

def test_submit_form_governance_disabled(
    client: TestClient,
    db: Session,
    mock_student_agent: AgentRegistry,
    mock_user: User
):
    """Test form submission with governance disabled."""
    form_data = {
        "canvas_id": "test-canvas-606",
        "form_data": {
            "field1": "value1"
        },
        "agent_id": mock_student_agent.id
    }

    with patch('api.canvas_routes.ws_manager') as mock_ws:
        mock_ws.broadcast = AsyncMock()

        with patch('api.canvas_routes.FeatureFlags') as mock_ff:
            # Governance disabled - should allow STUDENT agent
            mock_ff.should_enforce_governance.return_value = False

            with patch('api.canvas_routes.get_current_user') as mock_auth:
                mock_auth.return_value = mock_user

                response = client.post("/api/canvas/submit", json=form_data)

                # Should succeed when governance disabled
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_submit_form_database_error(
    client: TestClient,
    db: Session,
    mock_supervised_agent: AgentRegistry,
    mock_user: User
):
    """Test form submission with database error."""
    form_data = {
        "canvas_id": "test-canvas-707",
        "form_data": {
            "field1": "value1"
        },
        "agent_id": mock_supervised_agent.id
    }

    with patch('api.canvas_routes.FeatureFlags') as mock_ff:
        mock_ff.should_enforce_governance.return_value = True

        with patch('api.canvas_routes.ServiceFactory') as mock_sf:
            mock_governance = MagicMock()
            mock_governance.can_perform_action.side_effect = Exception("Database connection failed")
            mock_sf.get_governance_service.return_value = mock_governance

            with patch('api.canvas_routes.get_current_user') as mock_auth:
                mock_auth.return_value = mock_user

                response = client.post("/api/canvas/submit", json=form_data)

                # Should handle error gracefully
                assert response.status_code == 500
                data = response.json()
                assert data["success"] is False


def test_submit_form_websocket_error(
    client: TestClient,
    db: Session,
    mock_supervised_agent: AgentRegistry,
    mock_user: User
):
    """Test form submission with WebSocket broadcast error."""
    form_data = {
        "canvas_id": "test-canvas-808",
        "form_data": {
            "field1": "value1"
        },
        "agent_id": mock_supervised_agent.id
    }

    with patch('api.canvas_routes.ws_manager') as mock_ws:
        # WebSocket broadcast fails but submission should still succeed
        mock_ws.broadcast = AsyncMock(side_effect=Exception("WebSocket connection failed"))

        with patch('api.canvas_routes.FeatureFlags') as mock_ff:
            mock_ff.should_enforce_governance.return_value = True

            with patch('api.canvas_routes.ServiceFactory') as mock_sf:
                mock_governance = MagicMock()
                mock_governance.can_perform_action.return_value = {
                    "allowed": True,
                    "reason": None
                }
                mock_governance.record_outcome = AsyncMock()
                mock_sf.get_governance_service.return_value = mock_governance

                global _current_test_user
                _current_test_user = mock_user

                response = client.post("/api/canvas/submit", json=form_data)

                # Form submission should succeed even if WebSocket fails
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True


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
    form_data = {
        "canvas_id": "test-canvas-909",
        "form_data": {
            "name": "Test User",
            "email": "test@example.com"
        },
        "agent_id": mock_supervised_agent.id
    }

    with patch('api.canvas_routes.ws_manager') as mock_ws:
        mock_ws.broadcast = AsyncMock()

        with patch('api.canvas_routes.FeatureFlags') as mock_ff:
            mock_ff.should_enforce_governance.return_value = True

            with patch('api.canvas_routes.ServiceFactory') as mock_sf:
                mock_governance = MagicMock()
                mock_governance.can_perform_action.return_value = {
                    "allowed": True,
                    "reason": None
                }
                mock_governance.record_outcome = AsyncMock()
                mock_sf.get_governance_service.return_value = mock_governance

                global _current_test_user
                _current_test_user = mock_user

                response = client.post("/api/canvas/submit", json=form_data)

                # Verify response structure
                assert "success" in response.json()
                assert "data" in response.json()
                assert "message" in response.json()

                data = response.json()["data"]
                assert "submission_id" in data
                assert isinstance(data["submission_id"], str)
                assert "governance_check" in data


def test_get_status_response_structure(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test that canvas status response has correct structure."""
    with patch('api.canvas_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get("/api/canvas/status")

        # Verify response structure
        data = response.json()
        assert "success" in data
        assert "data" in data
        assert "message" in data

        assert isinstance(data["data"], dict)
        assert "status" in data["data"]
        assert "user_id" in data["data"]
        assert "features" in data["data"]
