"""
Integration coverage tests for api/canvas_routes.py.

NOTE (Session 2026-08-15, wave 120): rewritten against the current
api/canvas_routes.py contract:
- Auth is enforced via FastAPI `Depends(get_current_user)`, which cannot be
  patched by replacing the module attribute — the tests now use
  `app.dependency_overrides[get_current_user]`.
- `/api/canvas/status` does not exist (the old suite's central endpoint) —
  replaced with the real list surface `GET /api/canvas/`.
- `ws_manager` / `FeatureFlags` mocks removed — the submit endpoint has no
  WebSocket broadcast; its real side effect is a `CanvasAudit` row.
- Governance runs through the REAL `AgentGovernanceService` against the
  dev DB (the fixture DB is in-memory and invisible to the app), so agents
  are seeded via `SessionLocal()`.
- Response shape: `data = {canvas_id, submitted, timestamp}` (no
  submission_id / agent_execution_id in the payload).
"""
import pytest
import uuid
from fastapi.testclient import TestClient
from datetime import datetime

from main_api_app import app
from core.auth import get_current_user
from core.models import CanvasAudit, AgentRegistry, User, UserStatus
from core.database import SessionLocal


@pytest.fixture
def test_client():
    """Create test client for canvas routes."""
    return TestClient(app)


@pytest.fixture
def canvas_user():
    """Create a user in the app's dev DB (the app reads it for auth/audit)."""
    db = SessionLocal()
    try:
        user = User(
            email=f"canvas_test-{uuid.uuid4()}@example.com",
            hashed_password="hashed_password_here",
            status=UserStatus.ACTIVE.value,
            created_at=datetime.utcnow(),
            first_name="Test",
            last_name="User",
            role="member",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


@pytest.fixture
def authenticated_client(test_client, canvas_user):
    """Test client with the real get_current_user dependency overridden."""
    app.dependency_overrides[get_current_user] = lambda: canvas_user
    try:
        yield test_client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def canvas_agent():
    """Create a SUPERVISED test agent in the app's dev DB (governance reads it)."""
    db = SessionLocal()
    try:
        agent = AgentRegistry(
            name="CanvasTestAgent",
            category="testing",
            module_path="test.module",
            class_name="TestCanvas",
            status="supervised",
            confidence_score=0.8,
            workspace_id="default",
            created_at=datetime.utcnow(),
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        return agent
    finally:
        db.close()


class TestCanvasListEndpoint:
    """Tests for the real canvas list surface (GET /api/canvas/)."""

    def test_get_canvases_unauthenticated(self, test_client):
        """Test canvas list without authentication."""
        response = test_client.get("/api/canvas/")
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403]

    def test_get_canvases_authenticated(self, authenticated_client, canvas_user):
        """Test canvas list with authentication."""
        response = authenticated_client.get("/api/canvas/")

        # List endpoint should be accessible
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "canvases" in data
        assert "count" in data
        assert isinstance(data["canvases"], list)


class TestCanvasFormSubmission:
    """Tests for canvas form submission endpoint."""

    def test_submit_form_unauthenticated(self, test_client):
        """Test form submission without authentication."""
        response = test_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": "test_canvas",
                "form_data": {"email": "test@example.com"}
            }
        )
        # Should require authentication
        assert response.status_code in [401, 403]

    def test_submit_form_authenticated(self, authenticated_client, canvas_user):
        """Test form submission with authentication."""
        response = authenticated_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": f"form_{uuid.uuid4().hex[:8]}",
                "form_data": {
                    "email": "user@example.com",
                    "message": "Test message"
                }
            }
        )

        # Should accept submission
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["submitted"] is True
        assert "canvas_id" in data["data"]

    def test_submit_form_with_agent(self, authenticated_client, canvas_user, canvas_agent):
        """Test form submission with agent context (governance allowed)."""
        response = authenticated_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": f"agent_form_{uuid.uuid4().hex[:8]}",
                "form_data": {"approved": True},
                "agent_id": canvas_agent.id
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["submitted"] is True

    def test_submit_form_with_execution_id(self, authenticated_client, canvas_user, canvas_agent):
        """Test form submission linked to agent execution."""
        response = authenticated_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": f"execution_form_{uuid.uuid4().hex[:8]}",
                "form_data": {"action": "approve"},
                "agent_execution_id": "exec_123",
                "agent_id": canvas_agent.id
            }
        )

        assert response.status_code == 200

    def test_submit_form_empty_data(self, authenticated_client, canvas_user):
        """Test form submission with empty data."""
        response = authenticated_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": f"empty_form_{uuid.uuid4().hex[:8]}",
                "form_data": {}
            }
        )

        # Should accept empty form data
        assert response.status_code == 200

    def test_submit_form_large_data(self, authenticated_client, canvas_user):
        """Test form submission with large data payload."""
        large_data = {f"field_{i}": f"value_{i}" for i in range(100)}

        response = authenticated_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": f"large_form_{uuid.uuid4().hex[:8]}",
                "form_data": large_data
            }
        )

        assert response.status_code == 200


class TestCanvasGovernanceIntegration:
    """Tests for canvas governance integration (real AgentGovernanceService)."""

    def test_form_submission_governance_check(self, authenticated_client, canvas_user, canvas_agent):
        """Test governance check during form submission (allowed for SUPERVISED agent)."""
        response = authenticated_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": f"governance_form_{uuid.uuid4().hex[:8]}",
                "form_data": {"test": "data"},
                "agent_id": canvas_agent.id
            }
        )

        assert response.status_code == 200

    def test_form_submission_governance_denied(self, authenticated_client, canvas_user):
        """Test form submission when governance denies action (unknown agent)."""
        response = authenticated_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": f"denied_form_{uuid.uuid4().hex[:8]}",
                "form_data": {"test": "data"},
                "agent_id": "nonexistent-agent"
            }
        )

        # Governance denial surfaces as 403 GOVERNANCE_DENIED
        assert response.status_code == 403
        data = response.json()
        assert "error" in data or "detail" in data


class TestCanvasAuditTrail:
    """Tests for canvas audit trail in routes."""

    def test_form_submission_creates_audit(self, authenticated_client, canvas_user):
        """Test that form submission creates an audit entry (the real side effect)."""
        canvas_id = f"audit_form_{uuid.uuid4().hex[:8]}"

        response = authenticated_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": canvas_id,
                "form_data": {"field1": "value1"}
            }
        )

        assert response.status_code == 200

        # Verify audit entry was created in the app DB
        db = SessionLocal()
        try:
            audit = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id
            ).first()

            # Audit entry should exist with the real column names
            assert audit is not None
            assert audit.action_type == "submit"
            assert audit.canvas_type == "form"
            assert audit.user_id == str(canvas_user.id)
        finally:
            db.close()

    def test_form_audit_includes_metadata(self, authenticated_client, canvas_user):
        """Test that audit includes form metadata."""
        form_data = {
            "email": "test@example.com",
            "message": "Test message",
            "subscribe": True
        }
        canvas_id = f"metadata_form_{uuid.uuid4().hex[:8]}"

        response = authenticated_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": canvas_id,
                "form_data": form_data
            }
        )

        assert response.status_code == 200

        db = SessionLocal()
        try:
            audit = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id
            ).first()
            assert audit is not None
            details = audit.details_json or {}
            assert details.get("form_data") == form_data
        finally:
            db.close()


class TestCanvasErrorHandling:
    """Tests for canvas error handling."""

    def test_invalid_json_request(self, authenticated_client, canvas_user):
        """Test handling of invalid JSON in request."""
        response = authenticated_client.post(
            "/api/canvas/submit",
            content="invalid json content",
            headers={"Content-Type": "application/json"}
        )

        # Should return validation error
        assert response.status_code == 422

    def test_missing_required_field(self, authenticated_client, canvas_user):
        """Test handling of missing required field."""
        # Missing canvas_id
        response = authenticated_client.post(
            "/api/canvas/submit",
            json={
                "form_data": {"test": "data"}
            }
        )

        # Should return validation error
        assert response.status_code == 422

    def test_missing_form_data(self, authenticated_client, canvas_user):
        """Test handling of missing form_data field."""
        response = authenticated_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": f"test_canvas_{uuid.uuid4().hex[:8]}"
            }
        )

        # Should return validation error
        assert response.status_code == 422


class TestCanvasResponseFormat:
    """Tests for canvas API response format."""

    def test_success_response_format(self, authenticated_client, canvas_user):
        """Test that successful submission follows response format."""
        response = authenticated_client.post(
            "/api/canvas/submit",
            json={
                "canvas_id": f"format_form_{uuid.uuid4().hex[:8]}",
                "form_data": {"test": "data"}
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
        assert data["success"] is True
        assert "timestamp" in data
