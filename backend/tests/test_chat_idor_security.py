"""
Test Chat API IDOR Security Fix (Issue #521)

This test verifies that the chat API endpoints properly enforce authentication
and authorization to prevent Insecure Direct Object Reference (IDOR) attacks.

The vulnerability allowed unauthenticated attackers to:
1. Access any user's chat history
2. Send messages on behalf of any user
3. Rename any user's chat sessions
4. View any user's session list

This test ensures all endpoints now require proper authentication.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main_api_app import app
import uuid


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


@pytest.fixture
def victim_user():
    """Create a victim user"""
    return {
        "id": f"victim_{uuid.uuid4().hex[:8]}",
        "username": "victim_user",
        "email": "victim@example.com"
    }


@pytest.fixture
def attacker_user():
    """Create an attacker user"""
    return {
        "id": f"attacker_{uuid.uuid4().hex[:8]}",
        "username": "attacker_user",
        "email": "attacker@example.com"
    }


@pytest.fixture
def victim_session_id():
    """Create a victim session ID"""
    return str(uuid.uuid4())


class TestChatIDORSecurity:
    """Test IDOR vulnerability fix in Chat API"""

    def test_unauthenticated_get_chat_history_blocked(self, client, victim_user, victim_session_id):
        """Test that unauthenticated users cannot access chat history"""
        response = client.get(f"/api/chat/history/{victim_session_id}?user_id={victim_user['id']}")

        # Should return 401 Unauthorized (not 200 with data)
        assert response.status_code == 401
        assert "detail" in response.json()

    def test_unauthenticated_send_message_blocked(self, client, victim_user, victim_session_id):
        """Test that unauthenticated users cannot send messages"""
        payload = {
            "message": "Malicious payload injected by attacker",
            "user_id": victim_user["id"],
            "session_id": victim_session_id
        }
        response = client.post("/api/chat/message", json=payload)

        # Should return 401 Unauthorized
        assert response.status_code == 401
        assert "detail" in response.json()

    def test_unauthenticated_rename_session_blocked(self, client, victim_user, victim_session_id):
        """Test that unauthenticated users cannot rename sessions"""
        payload = {
            "title": "Hacked by attacker",
            "user_id": victim_user["id"]
        }
        response = client.patch(f"/api/chat/sessions/{victim_session_id}", json=payload)

        # Should return 401 Unauthorized
        assert response.status_code == 401
        assert "detail" in response.json()

    def test_unauthenticated_get_sessions_blocked(self, client, victim_user):
        """Test that unauthenticated users cannot list sessions"""
        response = client.get(f"/api/chat/sessions?user_id={victim_user['id']}")

        # Should return 401 Unauthorized
        assert response.status_code == 401
        assert "detail" in response.json()

    @patch('backend.integrations.chat_routes.chat_orchestrator')
    def test_cross_user_access_blocked(self, mock_orchestrator, client, victim_user, attacker_user, victim_session_id):
        """Test that authenticated users cannot access other users' data (IDOR prevention)"""
        # Mock the orchestrator to return victim's session
        mock_session = {
            "id": victim_session_id,
            "user_id": victim_user["id"],
            "title": "Victim's private chat",
            "history": [{"message": "Secret data"}]
        }
        mock_orchestrator.conversation_sessions = {victim_session_id: mock_session}
        mock_orchestrator.session_manager.get_session.return_value = mock_session

        # Mock authentication as attacker
        with patch('backend.integrations.chat_routes.get_current_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=attacker_user["id"])

            # Try to access victim's session as attacker
            response = client.get(f"/api/chat/sessions/{victim_session_id}?user_id={victim_user['id']}")

            # Should return 403 Forbidden (user mismatch)
            assert response.status_code == 403
            assert "Access denied" in response.json()["detail"]

    @patch('backend.integrations.chat_routes.chat_orchestrator')
    def test_same_user_access_allowed(self, mock_orchestrator, client, victim_user, victim_session_id):
        """Test that authenticated users CAN access their own data"""
        # Mock the orchestrator to return victim's session
        mock_session = {
            "id": victim_session_id,
            "session_id": victim_session_id,
            "user_id": victim_user["id"],
            "title": "My chat",
            "created_at": "2026-03-19T10:00:00"
        }
        mock_orchestrator.conversation_sessions = {victim_session_id: mock_session}
        mock_orchestrator.session_manager.get_session.return_value = mock_session

        # Mock authentication as victim
        with patch('backend.integrations.chat_routes.get_current_user') as mock_auth:
            mock_auth.return_value = MagicMock(id=victim_user["id"])

            # Access own session - should succeed
            response = client.get(f"/api/chat/sessions/{victim_session_id}?user_id={victim_user['id']}")

            # Should return 200 OK
            assert response.status_code == 200
            assert response.json()["success"] is True
            assert response.json()["user_id"] == victim_user["id"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
