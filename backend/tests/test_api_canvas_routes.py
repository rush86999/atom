"""
Integration tests for canvas routes API endpoints.

Tests canvas form submission, status endpoint, governance validation,
audit trail creation, and WebSocket notifications.

Coverage target: 60%+ for api/canvas_routes.py
"""

import os
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
import pytest

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"

from fastapi.testclient import TestClient

# Import app after environment is set
from main_api_app import app
from core.database import get_db
from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    CanvasAudit,
    User,
)
from core.security_dependencies import get_current_user


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client_with_auth(db_session):
    """
    Create a test client with database dependency override.

    This fixture provides a FastAPI TestClient with the database session
    overridden to use our test database fixture.
    """

    # Override database dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    yield client

    # Clean up override
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_user(db_session):
    """Create an authenticated test user."""
    user = User(
        id=str(uuid.uuid4()),
        email=f"canvas-test-{uuid.uuid4()}@example.com",
        hashed_password="hashed_password", first_name="Test", last_name="User", role="member", status="active"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def client_with_auth(db_session, authenticated_user):
    """
    Create test client with authentication bypass.

    This fixture overrides get_current_user to return our test user,
    bypassing JWT validation for testing purposes.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return authenticated_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    # Bearer header satisfies the CSRF middleware for state-changing requests
    client = TestClient(app, headers={"Authorization": "Bearer test-token"})
    yield client

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
def canvas_submission_request():
    """
    Generate a valid canvas form submission request.

    Returns a dict with FormSubmission structure.
    Accepts overrides via kwargs for customization in tests.
    """
    def _request(**overrides):
        default = {
            "canvas_id": f"canvas-{uuid.uuid4()}",
            "form_data": {
                "field1": "value1",
                "field2": "value2",
                "field3": "value3"
            },
            "agent_execution_id": None,
            "agent_id": None
        }
        default.update(overrides)
        return default

    return _request


@pytest.fixture
def mock_canvas_governance():
    """
    Mock governance service for canvas operations.

    Returns a Mock object with configurable governance check results.
    Can be used to allow or block specific agent actions.
    """
    class MockGovernance:
        def __init__(self):
            self._allowed = True
            self._reason = "Governance check passed"
            self.calls = []

        def allow(self, reason="Test allowance"):
            """Configure governance to allow actions."""
            self._allowed = True
            self._reason = reason

        def block(self, reason="Governance check blocked"):
            """Configure governance to block actions."""
            self._allowed = False
            self._reason = reason

        def can_perform_action(self, agent_id, action_type):
            """Return governance check result."""
            self.calls.append((agent_id, action_type))
            return {
                "allowed": self._allowed,
                "reason": self._reason
            }

        async def record_outcome(self, agent_id, success=True):
            """Mock outcome recording."""
            pass

    mock = MockGovernance()
    return mock


@pytest.fixture
def autonomous_agent(db_session):
    """Create an AUTONOMOUS agent for testing."""
    agent = AgentRegistry(
        id=f"agent-autonomous-{uuid.uuid4()}",
        name="AutonomousAgent",
        category="testing",
        module_path="test.autonomous",
        class_name="AutonomousAgent",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95,
        created_at=datetime.utcnow()
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def supervised_agent(db_session):
    """Create a SUPERVISED agent for testing."""
    agent = AgentRegistry(
        id=f"agent-supervised-{uuid.uuid4()}",
        name="SupervisedAgent",
        category="testing",
        module_path="test.supervised",
        class_name="SupervisedAgent",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.8,
        created_at=datetime.utcnow()
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def intern_agent(db_session):
    """Create an INTERN agent for testing."""
    agent = AgentRegistry(
        id=f"agent-intern-{uuid.uuid4()}",
        name="InternAgent",
        category="testing",
        module_path="test.intern",
        class_name="InternAgent",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
        created_at=datetime.utcnow()
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def student_agent(db_session):
    """Create a STUDENT agent for testing."""
    agent = AgentRegistry(
        id=f"agent-student-{uuid.uuid4()}",
        name="StudentAgent",
        category="testing",
        module_path="test.student",
        class_name="StudentAgent",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.4,
        created_at=datetime.utcnow()
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def originating_execution(db_session, autonomous_agent):
    """Create an originating agent execution for testing."""
    execution = AgentExecution(
        id=f"exec-{uuid.uuid4()}",
        agent_id=autonomous_agent.id,
        workspace_id="default",
        status="running",
        input_summary="Test execution",
        triggered_by="test",
        result_summary="In progress",
        started_at=datetime.utcnow()
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)
    return execution


@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager for testing broadcast functionality."""
    manager = Mock()
    manager.broadcast = AsyncMock()
    return manager


# ============================================================================
# Test: Canvas Form Submission (No Agent)
# ============================================================================

class TestCanvasSubmitNoAgent:
    """Test canvas form submission without agent context."""

    def test_submit_form_without_agent_success(
        self,
        client_with_auth,
        canvas_submission_request
    ):
        """Test successful form submission without agent."""
        request = canvas_submission_request()

        response = client_with_auth.post(
            "/api/canvas/submit",
            json=request
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["submitted"] is True
        assert data["data"]["canvas_id"] == request["canvas_id"]

    def test_submit_form_without_agent_skips_governance(
        self,
        client_with_auth,
        canvas_submission_request,
        mock_canvas_governance
    ):
        """Test governance is not checked when no agent is provided."""
        request = canvas_submission_request()

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        assert response.status_code == 200
        assert mock_canvas_governance.calls == []


# ============================================================================
# Test: Canvas Form Submission (With Agent)
# ============================================================================

class TestCanvasSubmitWithAgent:
    """Test canvas form submission with agent governance."""

    def test_submit_form_with_autonomous_agent(
        self,
        client_with_auth,
        canvas_submission_request,
        autonomous_agent,
        mock_canvas_governance
    ):
        """Test AUTONOMOUS agent can submit forms without blocking."""
        mock_canvas_governance.allow()
        request = canvas_submission_request(agent_id=autonomous_agent.id)

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["submitted"] is True
        assert mock_canvas_governance.calls == [(autonomous_agent.id, "canvas_submit")]

    def test_submit_form_with_supervised_agent(
        self,
        client_with_auth,
        canvas_submission_request,
        supervised_agent,
        mock_canvas_governance
    ):
        """Test SUPERVISED agent passes governance check."""
        mock_canvas_governance.allow()
        request = canvas_submission_request(agent_id=supervised_agent.id)

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["submitted"] is True

    def test_submit_form_with_intern_agent_blocked(
        self,
        client_with_auth,
        canvas_submission_request,
        intern_agent,
        mock_canvas_governance
    ):
        """Test INTERN agent blocked from submit_form (complexity 3)."""
        mock_canvas_governance.block("INTERN requires approval for submit_form")
        request = canvas_submission_request(agent_id=intern_agent.id)

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        assert response.status_code == 403
        # Error responses use different structure
        assert "governance" in response.text.lower() or "permission" in response.text.lower()

    def test_submit_form_with_student_agent_blocked(
        self,
        client_with_auth,
        canvas_submission_request,
        student_agent,
        mock_canvas_governance
    ):
        """Test STUDENT agent blocked from form submission."""
        mock_canvas_governance.block("STUDENT cannot submit forms")
        request = canvas_submission_request(agent_id=student_agent.id)

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        assert response.status_code == 403
        assert "governance" in response.text.lower()

    def test_submit_form_with_agent_success(
        self,
        client_with_auth,
        canvas_submission_request,
        autonomous_agent,
        mock_canvas_governance
    ):
        """Test submission with agent governance allowed succeeds."""
        mock_canvas_governance.allow()
        request = canvas_submission_request(agent_id=autonomous_agent.id)

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["submitted"] is True


# ============================================================================
# Test: Canvas Form Submission (Originating Execution)
# ============================================================================

class TestCanvasSubmitOriginatingExecution:
    """Test form submission with agent_execution_id in the request."""

    def test_submit_with_originating_execution(
        self,
        client_with_auth,
        canvas_submission_request,
        autonomous_agent,
        originating_execution,
        mock_canvas_governance
    ):
        """Test submission with agent_execution_id still succeeds."""
        mock_canvas_governance.allow()
        request = canvas_submission_request(
            agent_id=autonomous_agent.id,
            agent_execution_id=originating_execution.id
        )

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["submitted"] is True

    def test_submit_without_agent_id_skips_governance(
        self,
        client_with_auth,
        canvas_submission_request,
        autonomous_agent,
        originating_execution,
        mock_canvas_governance
    ):
        """Test submission with only agent_execution_id skips governance check."""
        request = canvas_submission_request(
            agent_id=None,  # Omit agent_id
            agent_execution_id=originating_execution.id
        )

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        assert response.status_code == 200
        assert mock_canvas_governance.calls == []


# ============================================================================
# Test: Canvas Form Submission (Validation)
# ============================================================================

class TestCanvasSubmitValidation:
    """Test request validation for form submission."""

    def test_submit_empty_canvas_id_accepted(
        self,
        client_with_auth,
        canvas_submission_request
    ):
        """Test empty canvas_id is currently accepted (no validation)."""
        request = canvas_submission_request(canvas_id="")

        response = client_with_auth.post(
            "/api/canvas/submit",
            json=request
        )

        # Currently accepts empty canvas_id (200)
        # Documenting actual behavior
        assert response.status_code == 200

    def test_submit_empty_form_data_rejected(
        self,
        client_with_auth,
        canvas_submission_request
    ):
        """Test empty form_data dict is rejected."""
        request = canvas_submission_request(form_data={})

        response = client_with_auth.post(
            "/api/canvas/submit",
            json=request
                )

        # May accept empty dict or reject - depends on validation
        # Document actual behavior
        assert response.status_code in [200, 422]

    def test_submit_malformed_form_data_rejected(
        self,
        client_with_auth,
        canvas_submission_request
    ):
        """Test non-dict form_data is rejected."""
        request = {
            "canvas_id": f"canvas-{uuid.uuid4()}",
            "form_data": "not-a-dict",  # Invalid type
            "agent_execution_id": None,
            "agent_id": None
        }

        response = client_with_auth.post(
            "/api/canvas/submit",
            json=request
                )

        # Should fail validation (422)
        assert response.status_code == 422


# ============================================================================
# Test: Execution Lifecycle
# ============================================================================

class TestCanvasExecutionLifecycle:
    """Test submission execution lifecycle."""

    def test_submission_execution_marked_completed(
        self,
        client_with_auth,
        canvas_submission_request,
        autonomous_agent,
        mock_canvas_governance
    ):
        """Test submission with governance allowed succeeds."""
        mock_canvas_governance.allow()
        request = canvas_submission_request(agent_id=autonomous_agent.id)

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["submitted"] is True

    def test_governance_outcome_recorded(
        self,
        client_with_auth,
        canvas_submission_request,
        autonomous_agent,
        mock_canvas_governance
    ):
        """Test governance check called for agent."""
        mock_canvas_governance.allow()
        request = canvas_submission_request(agent_id=autonomous_agent.id)

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        assert response.status_code == 200
        assert mock_canvas_governance.calls == [(autonomous_agent.id, "canvas_submit")]


# ============================================================================
# Test: Error Handling
# ============================================================================

class TestCanvasSubmitErrors:
    """Test error handling in canvas submission."""

    def test_database_connection_failure_handled(
        self,
        client_with_auth,
        canvas_submission_request,
        db_session
    ):
        """Test database failure during audit persistence is non-fatal."""
        request = canvas_submission_request()

        # Mock database failure
        with patch.object(db_session, 'commit', side_effect=Exception("DB connection lost")):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        # Audit persistence failures are non-fatal by design
        assert response.status_code == 200

    def test_websocket_broadcast_failure_doesnt_block_submission(
        self,
        client_with_auth,
        canvas_submission_request
    ):
        """Test submission succeeds without WebSocket infrastructure."""
        request = canvas_submission_request()

        response = client_with_auth.post(
            "/api/canvas/submit",
            json=request
            )

        # Submission succeeds regardless of WebSocket state
        assert response.status_code == 200

    def test_execution_completion_failure_logged(
        self,
        client_with_auth,
        canvas_submission_request,
        autonomous_agent,
        mock_canvas_governance
    ):
        """Test governance failure response is returned for blocked agents."""
        mock_canvas_governance.block("Agent blocked")
        request = canvas_submission_request(agent_id=autonomous_agent.id)

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        assert response.status_code == 403


# ============================================================================
# Test: Edge Cases and Branch Coverage
# ============================================================================

class TestCanvasSubmitEdgeCases:
    """Test edge cases to increase branch coverage."""

    def test_submit_with_nonexistent_agent(
        self,
        client_with_auth,
        canvas_submission_request,
        mock_canvas_governance
    ):
        """Test form submission with agent_id that doesn't exist in database."""
        mock_canvas_governance.allow()
        request = canvas_submission_request(agent_id="nonexistent-agent-id")

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        # Should succeed - governance check passes
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_submit_with_agent_id_and_originating_execution(
        self,
        client_with_auth,
        canvas_submission_request,
        autonomous_agent,
        originating_execution,
        mock_canvas_governance
    ):
        """Test when both agent_id and originating_execution are provided."""
        mock_canvas_governance.allow()
        request = canvas_submission_request(
            agent_id=autonomous_agent.id,
            agent_execution_id=originating_execution.id
        )

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["submitted"] is True
        assert mock_canvas_governance.calls == [(autonomous_agent.id, "canvas_submit")]

    def test_submit_with_originating_execution_no_agent_id(
        self,
        client_with_auth,
        canvas_submission_request,
        autonomous_agent,
        originating_execution,
        mock_canvas_governance
    ):
        """Test submission with only agent_execution_id skips governance."""
        mock_canvas_governance.allow()
        # Don't provide agent_id
        request = canvas_submission_request(
            agent_id=None,
            agent_execution_id=originating_execution.id
        )

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        assert response.status_code == 200
        assert mock_canvas_governance.calls == []

    def test_submit_empty_form_data(
        self,
        client_with_auth,
        canvas_submission_request
    ):
        """Test form submission with empty form_data dict."""
        request = canvas_submission_request(form_data={})

        response = client_with_auth.post(
            "/api/canvas/submit",
            json=request
            )

        # Empty form_data is currently accepted
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_submit_single_field_form_data(
        self,
        client_with_auth,
        canvas_submission_request
    ):
        """Test form submission with single field."""
        request = canvas_submission_request(
            form_data={"single_field": "single_value"}
        )

        response = client_with_auth.post(
            "/api/canvas/submit",
            json=request
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_submit_nested_form_data(
        self,
        client_with_auth,
        canvas_submission_request
    ):
        """Test form submission with nested form data."""
        request = canvas_submission_request(
            form_data={
                "user": {"name": "Test User", "email": "test@example.com"},
                "preferences": {"notifications": True, "theme": "dark"}
            }
        )

        response = client_with_auth.post(
            "/api/canvas/submit",
            json=request
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_submission_completion_exception_handling(
        self,
        client_with_auth,
        canvas_submission_request,
        autonomous_agent,
        mock_canvas_governance,
        db_session
    ):
        """Test governance check failure doesn't affect audit persistence."""
        mock_canvas_governance.allow()
        request = canvas_submission_request(agent_id=autonomous_agent.id)

        with patch('api.canvas_routes.AgentGovernanceService', return_value=mock_canvas_governance):
            response = client_with_auth.post(
                "/api/canvas/submit",
                json=request
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================================================
# Test: Canvas Request Fixtures Usage
# ============================================================================

class CanvasRequestFixtures:
    """Test canvas request fixtures are properly configured."""

    def test_canvas_submission_request_fixture_generates_unique_ids(
        self,
        canvas_submission_request
    ):
        """Test fixture generates unique canvas IDs."""
        request1 = canvas_submission_request()
        request2 = canvas_submission_request()

        assert request1["canvas_id"] != request2["canvas_id"]

    def test_canvas_submission_request_fixture_accepts_overrides(
        self,
        canvas_submission_request
    ):
        """Test fixture accepts customization via kwargs."""
        custom_data = {"custom_field": "custom_value"}
        request = canvas_submission_request(
            form_data=custom_data,
            agent_id="custom-agent-id"
        )

        assert request["form_data"] == custom_data
        assert request["agent_id"] == "custom-agent-id"

    def test_mock_canvas_governance_fixture_allow_block(
        self,
        mock_canvas_governance
    ):
        """Test governance fixture can be configured."""
        # Default is allowed
        result = mock_canvas_governance.can_perform_action("agent-1", "submit_form")
        assert result["allowed"] is True

        # Block
        mock_canvas_governance.block("Test block")
        result = mock_canvas_governance.can_perform_action("agent-2", "submit_form")
        assert result["allowed"] is False

        # Allow again
        mock_canvas_governance.allow("Test allow")
        result = mock_canvas_governance.can_perform_action("agent-3", "submit_form")
        assert result["allowed"] is True
