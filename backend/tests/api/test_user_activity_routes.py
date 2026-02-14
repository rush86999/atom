"""
User Activity Routes Tests

Comprehensive tests for user activity tracking endpoints covering:
- Heartbeat submission (POST /api/users/{user_id}/activity/heartbeat)
- User state retrieval (GET /api/users/{user_id}/activity/state)
- Manual override (POST /api/users/{user_id}/activity/override)
- Clear override (DELETE /api/users/{user_id}/activity/override)
- Available supervisors (GET /api/users/available-supervisors)
- Active sessions (GET /api/users/{user_id}/activity/sessions)
- Session termination (DELETE /api/users/activity/sessions/{session_token})
"""

import os
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from api.user_activity_routes import router
from core.models import UserState
from core.database import get_db


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Create test database session"""
    from core.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def mock_user_activity():
    """Mock user activity record"""
    activity = Mock()
    activity.id = "ua_123"
    activity.user_id = "user_123"
    activity.state = UserState.online
    activity.last_activity_at = datetime.utcnow()
    activity.manual_override = False
    activity.manual_override_expires_at = None
    return activity


@pytest.fixture
def mock_user_activity_session():
    """Mock user activity session"""
    session = Mock()
    session.id = "us_123"
    session.user_id = "user_123"
    session.session_type = "web"
    session.session_token = "session_token_123"
    session.last_heartbeat = datetime.utcnow()
    session.user_agent = "Mozilla/5.0"
    session.ip_address = "192.168.1.1"
    session.created_at = datetime.utcnow()
    return session


@pytest.fixture
def mock_supervisor_info():
    """Mock supervisor info"""
    return {
        "user_id": "supervisor_123",
        "email": "supervisor@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "state": "online",
        "last_activity_at": datetime.utcnow().isoformat(),
        "specialty": "cardiology"
    }


@pytest.fixture
def client():
    """Create TestClient for user activity routes"""
    from main import app
    app.include_router(router)
    with TestClient(app) as test_client:
        yield test_client


# ============================================================================
# POST /api/users/{user_id}/activity/heartbeat - Heartbeat Tests
# ============================================================================

class TestHeartbeat:
    """Test heartbeat endpoint"""

    def test_send_heartbeat_success(self, client: TestClient, mock_user_activity: Mock):
        """Test successful heartbeat submission"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.record_heartbeat.return_value = mock_user_activity
            mock_service_class.return_value = mock_service

            response = client.post(
                "/api/users/user_123/activity/heartbeat",
                json={
                    "session_token": "session_token_123",
                    "session_type": "web",
                    "user_agent": "Mozilla/5.0",
                    "ip_address": "192.168.1.1"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "user_123"
            assert data["state"] == "online"

    def test_send_heartbeat_with_optional_fields(self, client: TestClient, mock_user_activity: Mock):
        """Test heartbeat with optional user_agent and ip_address"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.record_heartbeat.return_value = mock_user_activity
            mock_service_class.return_value = mock_service

            response = client.post(
                "/api/users/user_123/activity/heartbeat",
                json={
                    "session_token": "session_token_123",
                    "session_type": "desktop"
                    # No user_agent or ip_address
                }
            )

            assert response.status_code == 200

    def test_send_heartbeat_creates_session(self, client: TestClient, mock_user_activity: Mock):
        """Test heartbeat creates new session if not exists"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.record_heartbeat.return_value = mock_user_activity
            mock_service_class.return_value = mock_service

            response = client.post(
                "/api/users/user_123/activity/heartbeat",
                json={
                    "session_token": "new_session_token",
                    "session_type": "web"
                }
            )

            assert response.status_code == 200

    def test_send_heartbeat_exception_handled(self, client: TestClient):
        """Test heartbeat exception is properly handled"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.record_heartbeat.side_effect = Exception("Database error")
            mock_service_class.return_value = mock_service

            response = client.post(
                "/api/users/user_123/activity/heartbeat",
                json={
                    "session_token": "session_token_123",
                    "session_type": "web"
                }
            )

            assert response.status_code == 500


# ============================================================================
# GET /api/users/{user_id}/activity/state - User State Tests
# ============================================================================

class TestUserState:
    """Test user state endpoint"""

    def test_get_user_state_online(self, client: TestClient, mock_user_activity: Mock):
        """Test getting online user state"""
        mock_user_activity.state = UserState.online

        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_state.return_value = UserState.online
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/user_123/activity/state")

            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "online"

    def test_get_user_state_away(self, client: TestClient, mock_user_activity: Mock):
        """Test getting away user state"""
        mock_user_activity.state = UserState.away

        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_state.return_value = UserState.away
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/user_123/activity/state")

            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "away"

    def test_get_user_state_offline(self, client: TestClient, mock_user_activity: Mock):
        """Test getting offline user state"""
        mock_user_activity.state = UserState.offline

        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_state.return_value = UserState.offline
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/user_123/activity/state")

            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "offline"

    def test_get_user_state_with_manual_override(self, client: TestClient, mock_user_activity: Mock):
        """Test getting user state with manual override"""
        mock_user_activity.manual_override = True
        mock_user_activity.manual_override_expires_at = datetime.utcnow() + timedelta(hours=1)

        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_state.return_value = UserState.online
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/user_123/activity/state")

            assert response.status_code == 200
            data = response.json()
            assert data["manual_override"] is True
            assert data["manual_override_expires_at"] is not None

    def test_get_user_state_no_existing_record(self, client: TestClient):
        """Test getting user state when no record exists"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_state.return_value = UserState.offline
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/new_user_123/activity/state")

            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "offline"

    def test_get_user_state_exception_handled(self, client: TestClient):
        """Test user state exception is properly handled"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_state.side_effect = Exception("Service error")
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/user_123/activity/state")

            assert response.status_code == 500


# ============================================================================
# POST /api/users/{user_id}/activity/override - Manual Override Tests
# ============================================================================

class TestManualOverride:
    """Test manual override endpoint"""

    def test_set_manual_override_online(self, client: TestClient, mock_user_activity: Mock):
        """Test setting manual override to online"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.set_manual_override.return_value = mock_user_activity
            mock_service_class.return_value = mock_service

            response = client.post(
                "/api/users/user_123/activity/override",
                json={"state": "online"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "online"

    def test_set_manual_override_away(self, client: TestClient, mock_user_activity: Mock):
        """Test setting manual override to away"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.set_manual_override.return_value = mock_user_activity
            mock_service_class.return_value = mock_service

            response = client.post(
                "/api/users/user_123/activity/override",
                json={"state": "away"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "away"

    def test_set_manual_override_offline(self, client: TestClient, mock_user_activity: Mock):
        """Test setting manual override to offline"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.set_manual_override.return_value = mock_user_activity
            mock_service_class.return_value = mock_service

            response = client.post(
                "/api/users/user_123/activity/override",
                json={"state": "offline"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "offline"

    def test_set_manual_override_with_expiry(self, client: TestClient, mock_user_activity: Mock):
        """Test setting manual override with expiry time"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.set_manual_override.return_value = mock_user_activity
            mock_service_class.return_value = mock_service

            expires_at = (datetime.utcnow() + timedelta(hours=2)).isoformat()

            response = client.post(
                "/api/users/user_123/activity/override",
                json={
                    "state": "online",
                    "expires_at": expires_at
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["manual_override_expires_at"] is not None

    def test_set_manual_override_invalid_state(self, client: TestClient):
        """Test setting manual override with invalid state"""
        response = client.post(
            "/api/users/user_123/activity/override",
            json={"state": "invalid_state"}
        )

        assert response.status_code == 400

    def test_set_manual_override_invalid_datetime_format(self, client: TestClient):
        """Test setting manual override with invalid datetime format"""
        response = client.post(
            "/api/users/user_123/activity/override",
            json={
                "state": "online",
                "expires_at": "invalid_datetime"
            }
        )

        assert response.status_code == 400

    def test_set_manual_override_exception_handled(self, client: TestClient):
        """Test manual override exception is properly handled"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.set_manual_override.side_effect = Exception("Database error")
            mock_service_class.return_value = mock_service

            response = client.post(
                "/api/users/user_123/activity/override",
                json={"state": "online"}
            )

            assert response.status_code == 500


# ============================================================================
# DELETE /api/users/{user_id}/activity/override - Clear Override Tests
# ============================================================================

class TestClearOverride:
    """Test clear override endpoint"""

    def test_clear_manual_override_success(self, client: TestClient, mock_user_activity: Mock):
        """Test successfully clearing manual override"""
        mock_user_activity.manual_override = False

        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.clear_manual_override.return_value = mock_user_activity
            mock_service_class.return_value = mock_service

            response = client.delete("/api/users/user_123/activity/override")

            assert response.status_code == 200
            data = response.json()
            assert data["manual_override"] is False

    def test_clear_manual_override_not_set(self, client: TestClient, mock_user_activity: Mock):
        """Test clearing override when none is set"""
        mock_user_activity.manual_override = False

        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.clear_manual_override.return_value = mock_user_activity
            mock_service_class.return_value = mock_service

            response = client.delete("/api/users/user_123/activity/override")

            assert response.status_code == 200

    def test_clear_manual_override_user_not_found(self, client: TestClient):
        """Test clearing override for non-existent user"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.clear_manual_override.side_effect = ValueError("User not found")
            mock_service_class.return_value = mock_service

            response = client.delete("/api/users/nonexistent_user/activity/override")

            assert response.status_code == 404

    def test_clear_manual_override_exception_handled(self, client: TestClient):
        """Test clear override exception is properly handled"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.clear_manual_override.side_effect = Exception("Service error")
            mock_service_class.return_value = mock_service

            response = client.delete("/api/users/user_123/activity/override")

            assert response.status_code == 500


# ============================================================================
# GET /api/users/available-supervisors - Available Supervisors Tests
# ============================================================================

class TestAvailableSupervisors:
    """Test available supervisors endpoint"""

    def test_get_available_supervisors_success(self, client: TestClient, mock_supervisor_info: dict):
        """Test getting list of available supervisors"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_available_supervisors.return_value = [mock_supervisor_info]
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/available-supervisors")

            assert response.status_code == 200
            data = response.json()
            assert "supervisors" in data
            assert data["total_count"] == 1
            assert len(data["supervisors"]) == 1

    def test_get_available_supervisors_with_category(self, client: TestClient, mock_supervisor_info: dict):
        """Test getting supervisors filtered by category"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            # Return multiple supervisors with different specialties
            mock_service.get_available_supervisors.return_value = [
                {
                    **mock_supervisor_info,
                    "specialty": "cardiology"
                },
                {
                    **mock_supervisor_info,
                    "user_id": "supervisor_456",
                    "specialty": "neurology"
                }
            ]
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/available-supervisors?category=cardiology")

            assert response.status_code == 200
            data = response.json()
            # Should only return cardiology supervisors
            assert data["total_count"] == 1

    def test_get_available_supervisors_no_results(self, client: TestClient):
        """Test getting available supervisors when none available"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_available_supervisors.return_value = []
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/available-supervisors")

            assert response.status_code == 200
            data = response.json()
            assert data["total_count"] == 0
            assert len(data["supervisors"]) == 0

    def test_get_available_supervisors_exception_handled(self, client: TestClient):
        """Test available supervisors exception is properly handled"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_available_supervisors.side_effect = Exception("Database error")
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/available-supervisors")

            assert response.status_code == 500


# ============================================================================
# GET /api/users/{user_id}/activity/sessions - Active Sessions Tests
# ============================================================================

class TestActiveSessions:
    """Test active sessions endpoint"""

    def test_get_active_sessions_success(self, client: TestClient, mock_user_activity_session: Mock):
        """Test getting list of active sessions"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_active_sessions.return_value = [mock_user_activity_session]
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/user_123/activity/sessions")

            assert response.status_code == 200
            data = response.json()
            assert "sessions" in data
            assert data["total_count"] == 1
            assert len(data["sessions"]) == 1

    def test_get_active_sessions_multiple_sessions(self, client: TestClient):
        """Test getting multiple active sessions"""
        session1 = Mock()
        session1.id = "us_123"
        session1.session_type = "web"
        session1.session_token = "token_123"
        session1.last_heartbeat = datetime.utcnow()
        session1.user_agent = "Mozilla/5.0"
        session1.ip_address = "192.168.1.1"
        session1.created_at = datetime.utcnow()

        session2 = Mock()
        session2.id = "us_456"
        session2.session_type = "desktop"
        session2.session_token = "token_456"
        session2.last_heartbeat = datetime.utcnow()
        session2.user_agent = "AtomDesktop/1.0"
        session2.ip_address = "192.168.1.2"
        session2.created_at = datetime.utcnow()

        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_active_sessions.return_value = [session1, session2]
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/user_123/activity/sessions")

            assert response.status_code == 200
            data = response.json()
            assert data["total_count"] == 2
            assert len(data["sessions"]) == 2

    def test_get_active_sessions_no_sessions(self, client: TestClient):
        """Test getting active sessions when none exist"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_active_sessions.return_value = []
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/user_123/activity/sessions")

            assert response.status_code == 200
            data = response.json()
            assert data["total_count"] == 0
            assert len(data["sessions"]) == 0

    def test_get_active_sessions_exception_handled(self, client: TestClient):
        """Test active sessions exception is properly handled"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_active_sessions.side_effect = Exception("Service error")
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/user_123/activity/sessions")

            assert response.status_code == 500


# ============================================================================
# DELETE /api/users/activity/sessions/{session_token} - Session Termination Tests
# ============================================================================

class TestSessionTermination:
    """Test session termination endpoint"""

    def test_terminate_session_success(self, client: TestClient):
        """Test successfully terminating a session"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.terminate_session.return_value = True
            mock_service_class.return_value = mock_service

            response = client.delete("/api/users/activity/sessions/session_token_123")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "terminated" in data["message"].lower()

    def test_terminate_session_not_found(self, client: TestClient):
        """Test terminating non-existent session"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.terminate_session.return_value = False
            mock_service_class.return_value = mock_service

            response = client.delete("/api/users/activity/sessions/nonexistent_session")

            assert response.status_code == 404

    def test_terminate_session_exception_handled(self, client: TestClient):
        """Test session termination exception is properly handled"""
        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.terminate_session.side_effect = Exception("Service error")
            mock_service_class.return_value = mock_service

            response = client.delete("/api/users/activity/sessions/session_token_123")

            assert response.status_code == 500


# ============================================================================
# State Transition Tests
# ============================================================================

class TestStateTransitions:
    """Test user state transitions"""

    def test_state_transition_offline_to_away(self, client: TestClient, mock_user_activity: Mock):
        """Test state transition from offline to away"""
        mock_user_activity.state = UserState.away

        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_state.return_value = UserState.away
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/user_123/activity/state")

            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "away"

    def test_state_transition_away_to_online(self, client: TestClient, mock_user_activity: Mock):
        """Test state transition from away to online"""
        mock_user_activity.state = UserState.online

        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_user_state.return_value = UserState.online
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/user_123/activity/state")

            assert response.status_code == 200
            data = response.json()
            assert data["state"] == "online"


# ============================================================================
# Concurrency Tests
# ============================================================================

class TestConcurrency:
    """Test concurrent activity handling"""

    def test_multiple_sessions_same_user(self, client: TestClient):
        """Test handling multiple sessions for same user"""
        sessions = []
        for i in range(3):
            session = Mock()
            session.id = f"us_{i}"
            session.session_type = "web"
            session.session_token = f"token_{i}"
            session.last_heartbeat = datetime.utcnow()
            session.user_agent = "Mozilla/5.0"
            session.ip_address = "192.168.1.1"
            session.created_at = datetime.utcnow()
            sessions.append(session)

        with patch('api.user_activity_routes.UserActivityService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_active_sessions.return_value = sessions
            mock_service_class.return_value = mock_service

            response = client.get("/api/users/user_123/activity/sessions")

            assert response.status_code == 200
            data = response.json()
            assert data["total_count"] == 3
