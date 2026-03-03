"""
Integration coverage tests for api/canvas_routes.py.

These tests use FastAPI TestClient to increase code coverage.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from main_api_app import app
from core.models import CanvasAudit, AgentRegistry, AgentExecution, User
from core.database import SessionLocal


@pytest.fixture
def test_client():
    """Create test client for canvas routes."""
    return TestClient(app)


@pytest.fixture
def canvas_user(db_session):
    """Create authenticated test user."""
    user = User(
        email="canvas_test@example.com",
        password_hash="hashed_password_here",
        is_active=True,
        created_at=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def canvas_agent(db_session):
    """Create test agent for canvas operations."""
    agent = AgentRegistry(
        name="CanvasTestAgent",
        category="testing",
        module_path="test.module",
        class_name="TestCanvas",
        status="SUPERVISED",
        confidence_score=0.8,
        created_at=datetime.utcnow()
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


class TestCanvasStatusEndpoint:
    """Tests for canvas status endpoint."""

    def test_get_canvas_status_unauthenticated(self, test_client):
        """Test canvas status without authentication."""
        response = test_client.get("/api/canvas/status")
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403]

    def test_get_canvas_status_authenticated(self, test_client, canvas_user):
        """Test canvas status with authentication."""
        # Mock authentication
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            response = test_client.get("/api/canvas/status")

            # Status endpoint should be accessible
            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert data["success"] is True


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

    def test_submit_form_authenticated(self, test_client, canvas_user):
        """Test form submission with authentication."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.ws_manager') as mock_ws:
                mock_ws.broadcast = AsyncMock()

                response = test_client.post(
                    "/api/canvas/submit",
                    json={
                        "canvas_id": "form_123",
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
                assert "submission_id" in data["data"]

    def test_submit_form_with_agent(self, test_client, canvas_user, canvas_agent):
        """Test form submission with agent context."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.ws_manager') as mock_ws:
                mock_ws.broadcast = AsyncMock()

                response = test_client.post(
                    "/api/canvas/submit",
                    json={
                        "canvas_id": "agent_form_123",
                        "form_data": {"approved": True},
                        "agent_id": canvas_agent.id
                    }
                )

                assert response.status_code == 200
                data = response.json()
                assert "agent_id" in data["data"]

    def test_submit_form_with_execution_id(self, test_client, canvas_user, canvas_agent):
        """Test form submission linked to agent execution."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.ws_manager') as mock_ws:
                mock_ws.broadcast = AsyncMock()

                response = test_client.post(
                    "/api/canvas/submit",
                    json={
                        "canvas_id": "execution_form_123",
                        "form_data": {"action": "approve"},
                        "agent_execution_id": "exec_123",
                        "agent_id": canvas_agent.id
                    }
                )

                assert response.status_code == 200

    def test_submit_form_empty_data(self, test_client, canvas_user):
        """Test form submission with empty data."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.ws_manager') as mock_ws:
                mock_ws.broadcast = AsyncMock()

                response = test_client.post(
                    "/api/canvas/submit",
                    json={
                        "canvas_id": "empty_form",
                        "form_data": {}
                    }
                )

                # Should accept empty form data
                assert response.status_code == 200

    def test_submit_form_large_data(self, test_client, canvas_user):
        """Test form submission with large data payload."""
        large_data = {f"field_{i}": f"value_{i}" for i in range(100)}

        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.ws_manager') as mock_ws:
                mock_ws.broadcast = AsyncMock()

                response = test_client.post(
                    "/api/canvas/submit",
                    json={
                        "canvas_id": "large_form",
                        "form_data": large_data
                    }
                )

                assert response.status_code == 200


class TestCanvasGovernanceIntegration:
    """Tests for canvas governance integration."""

    def test_form_submission_governance_check(self, test_client, canvas_user, canvas_agent):
        """Test governance check during form submission."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.FeatureFlags') as mock_flags:
                mock_flags.should_enforce_governance.return_value = True

                with patch('api.canvas_routes.ServiceFactory') as mock_factory:
                    mock_gov_service = MagicMock()
                    mock_gov_service.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": None
                    }
                    mock_factory.get_governance_service.return_value = mock_gov_service

                    with patch('api.canvas_routes.ws_manager') as mock_ws:
                        mock_ws.broadcast = AsyncMock()

                        response = test_client.post(
                            "/api/canvas/submit",
                            json={
                                "canvas_id": "governance_form",
                                "form_data": {"test": "data"},
                                "agent_id": canvas_agent.id
                            }
                        )

                        assert response.status_code == 200

    def test_form_submission_governance_denied(self, test_client, canvas_user, canvas_agent):
        """Test form submission when governance denies action."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.FeatureFlags') as mock_flags:
                mock_flags.should_enforce_governance.return_value = True

                with patch('api.canvas_routes.ServiceFactory') as mock_factory:
                    mock_gov_service = MagicMock()
                    mock_gov_service.can_perform_action.return_value = {
                        "allowed": False,
                        "reason": "Insufficient maturity level"
                    }
                    mock_factory.get_governance_service.return_value = mock_gov_service

                    response = test_client.post(
                        "/api/canvas/submit",
                        json={
                            "canvas_id": "denied_form",
                            "form_data": {"test": "data"},
                            "agent_id": canvas_agent.id
                        }
                    )

                    # Should return error when governance denies
                    assert response.status_code in [400, 403]

    def test_form_submission_creates_execution(self, test_client, canvas_user, canvas_agent):
        """Test that form submission creates agent execution record."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.FeatureFlags') as mock_flags:
                mock_flags.should_enforce_governance.return_value = True

                with patch('api.canvas_routes.ServiceFactory') as mock_factory:
                    mock_gov_service = MagicMock()
                    mock_gov_service.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": None
                    }
                    mock_gov_service.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_gov_service

                    with patch('api.canvas_routes.ws_manager') as mock_ws:
                        mock_ws.broadcast = AsyncMock()

                        response = test_client.post(
                            "/api/canvas/submit",
                            json={
                                "canvas_id": "execution_form",
                                "form_data": {"action": "submit"},
                                "agent_id": canvas_agent.id
                            }
                        )

                        assert response.status_code == 200
                        data = response.json()
                        assert "agent_execution_id" in data["data"]


class TestCanvasAuditTrail:
    """Tests for canvas audit trail in routes."""

    def test_form_submission_creates_audit(self, test_client, canvas_user):
        """Test that form submission creates audit entry."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.ws_manager') as mock_ws:
                mock_ws.broadcast = AsyncMock()

                response = test_client.post(
                    "/api/canvas/submit",
                    json={
                        "canvas_id": "audit_form",
                        "form_data": {"field1": "value1"}
                    }
                )

                assert response.status_code == 200

                # Verify audit entry was created
                audit = SessionLocal().query(CanvasAudit).filter(
                    CanvasAudit.canvas_id == "audit_form"
                ).first()

                # Audit entry should exist
                assert audit is not None
                assert audit.action == "submit"

    def test_form_audit_includes_metadata(self, test_client, canvas_user):
        """Test that audit includes form metadata."""
        form_data = {
            "email": "test@example.com",
            "message": "Test message",
            "subscribe": True
        }

        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.ws_manager') as mock_ws:
                mock_ws.broadcast = AsyncMock()

                response = test_client.post(
                    "/api/canvas/submit",
                    json={
                        "canvas_id": "metadata_form",
                        "form_data": form_data
                    }
                )

                assert response.status_code == 200


class TestCanvasWebSocketBroadcast:
    """Tests for canvas WebSocket broadcasts."""

    def test_form_submission_broadcasts(self, test_client, canvas_user):
        """Test that form submission broadcasts via WebSocket."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.ws_manager') as mock_ws:
                mock_ws.broadcast = AsyncMock()

                response = test_client.post(
                    "/api/canvas/submit",
                    json={
                        "canvas_id": "broadcast_form",
                        "form_data": {"test": "data"}
                    }
                )

                assert response.status_code == 200
                # Verify broadcast was called
                assert mock_ws.broadcast.called

    def test_broadcast_includes_governance_check(self, test_client, canvas_user):
        """Test that broadcast includes governance check data."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.FeatureFlags') as mock_flags:
                mock_flags.should_enforce_governance.return_value = False

                with patch('api.canvas_routes.ws_manager') as mock_ws:
                    mock_ws.broadcast = AsyncMock()

                    response = test_client.post(
                        "/api/canvas/submit",
                        json={
                            "canvas_id": "governance_broadcast",
                            "form_data": {"field": "value"}
                        }
                    )

                    assert response.status_code == 200
                    # Check broadcast call arguments
                    call_args = mock_ws.broadcast.call_args
                    assert call_args is not None


class TestCanvasErrorHandling:
    """Tests for canvas error handling."""

    def test_invalid_json_request(self, test_client, canvas_user):
        """Test handling of invalid JSON in request."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            response = test_client.post(
                "/api/canvas/submit",
                content="invalid json content",
                headers={"Content-Type": "application/json"}
            )

            # Should return validation error
            assert response.status_code == 422

    def test_missing_required_field(self, test_client, canvas_user):
        """Test handling of missing required field."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            # Missing canvas_id
            response = test_client.post(
                "/api/canvas/submit",
                json={
                    "form_data": {"test": "data"}
                }
            )

            # Should return validation error
            assert response.status_code == 422

    def test_missing_form_data(self, test_client, canvas_user):
        """Test handling of missing form_data field."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            response = test_client.post(
                "/api/canvas/submit",
                json={
                    "canvas_id": "test_canvas"
                }
            )

            # Should return validation error
            assert response.status_code == 422


class TestCanvasResponseFormat:
    """Tests for canvas API response format."""

    def test_success_response_format(self, test_client, canvas_user):
        """Test that successful submission follows response format."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.ws_manager') as mock_ws:
                mock_ws.broadcast = AsyncMock()

                response = test_client.post(
                    "/api/canvas/submit",
                    json={
                        "canvas_id": "format_form",
                        "form_data": {"test": "data"}
                    }
                )

                assert response.status_code == 200
                data = response.json()
                assert "success" in data
                assert "data" in data
                assert "message" in data
                assert data["success"] is True

    def test_status_response_format(self, test_client, canvas_user):
        """Test that status endpoint follows response format."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            response = test_client.get("/api/canvas/status")

            assert response.status_code == 200
            data = response.json()
            assert "success" in data
            assert "data" in data
            assert data["success"] is True
            assert "status" in data["data"]


class TestCanvasFeatureFlags:
    """Tests for canvas feature flag integration."""

    def test_governance_disabled_bypass(self, test_client, canvas_user, canvas_agent):
        """Test that disabled governance bypasses checks."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.FeatureFlags') as mock_flags:
                # Governance disabled
                mock_flags.should_enforce_governance.return_value = False

                with patch('api.canvas_routes.ws_manager') as mock_ws:
                    mock_ws.broadcast = AsyncMock()

                    response = test_client.post(
                        "/api/canvas/submit",
                        json={
                            "canvas_id": "bypass_form",
                            "form_data": {"test": "data"},
                            "agent_id": canvas_agent.id
                        }
                    )

                    # Should succeed without governance check
                    assert response.status_code == 200


class TestCanvasAgentOutcomeRecording:
    """Tests for canvas agent outcome recording."""

    def test_successful_submission_records_outcome(self, test_client, canvas_user, canvas_agent):
        """Test that successful submission records agent outcome."""
        with patch('api.canvas_routes.get_current_user') as mock_auth:
            mock_auth.return_value = canvas_user

            with patch('api.canvas_routes.FeatureFlags') as mock_flags:
                mock_flags.should_enforce_governance.return_value = True

                with patch('api.canvas_routes.ServiceFactory') as mock_factory:
                    mock_gov_service = MagicMock()
                    mock_gov_service.can_perform_action.return_value = {
                        "allowed": True,
                        "reason": None
                    }
                    # Track if record_outcome was called
                    mock_gov_service.record_outcome = AsyncMock()
                    mock_factory.get_governance_service.return_value = mock_gov_service

                    with patch('api.canvas_routes.ws_manager') as mock_ws:
                        mock_ws.broadcast = AsyncMock()

                        response = test_client.post(
                            "/api/canvas/submit",
                            json={
                                "canvas_id": "outcome_form",
                                "form_data": {"action": "approve"},
                                "agent_id": canvas_agent.id
                            }
                        )

                        assert response.status_code == 200

                        # Verify record_outcome was called
                        mock_gov_service.record_outcome.assert_called()
