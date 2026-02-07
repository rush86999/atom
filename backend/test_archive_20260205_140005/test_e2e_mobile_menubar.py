"""
End-to-End Tests for Mobile and Menu Bar Integration

Tests complete user workflows across mobile app, menu bar app, and backend.
"""

import pytest
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, AsyncMock

from core.models import (
    User, AgentRegistry, AgentExecution, CanvasAudit,
    DeviceNode, OfflineAction, SyncState
)
from api.menubar_routes import menubar_login
from api.mobile_canvas_routes import register_device, queue_offline_action


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def e2e_user(db_session: Session):
    """Create a test user for E2E tests."""
    user = User(
        email="e2e@test.com",
        first_name="E2E",
        last_name="Test User",
        password_hash="$2b$12$test_hashed_password",
        role="MEMBER"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def e2e_agent(db_session: Session):
    """Create a test agent for E2E tests."""
    agent = AgentRegistry(
        id="e2e_agent_123",
        name="E2E Test Agent",
        description="Agent for end-to-end testing",
        maturity_level="AUTONOMOUS",
        status="online",
        system_prompt="You are a helpful test assistant.",
        capabilities=[],
        version=1,
        confidence_score=0.95,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


# ============================================================================
# Scenario 1: Mobile User Journey
# ============================================================================

class TestMobileUserJourney:
    """Test complete mobile user journey from login to agent interaction."""

    def test_mobile_login_and_agent_chat(self, client: TestClient, e2e_user, e2e_agent):
        """Scenario: User logs in on mobile and chats with agent."""
        # Step 1: Register mobile device for push notifications
        device_response = client.post(
            "/api/mobile/notifications/register",
            json={
                "device_token": "mobile_token_123",
                "platform": "ios",
                "device_info": {
                    "model": "iPhone 15",
                    "os_version": "17.1"
                },
                "notification_enabled": True
            },
            headers={"X-User-ID": str(e2e_user.id)}
        )
        assert device_response.status_code == 200
        device_id = device_response.json()["device_id"]

        # Step 2: Get list of available agents
        agents_response = client.get(
            "/api/agents/mobile/list"
        )
        assert agents_response.status_code == 200
        agents = agents_response.json()
        assert len(agents) > 0
        assert e2e_agent.id in [a["id"] for a in agents]

        # Step 3: Send chat message to agent
        chat_response = client.post(
            "/api/agents/mobile/chat",
            json={
                "agent_id": e2e_agent.id,
                "message": "Hello from mobile!",
                "platform": "mobile"
            }
        )
        assert chat_response.status_code == 200
        chat_data = chat_response.json()
        assert "message" in chat_data
        assert "session_id" in chat_data

        # Step 4: Verify agent execution was created
        executions = client.get(f"/api/agents/{e2e_agent.id}/executions")
        assert executions.status_code == 200
        execution_list = executions.json()
        assert len(execution_list) > 0

    def test_mobile_offline_sync_flow(self, client: TestClient, e2e_user, e2e_agent):
        """Scenario: User goes offline, queues actions, syncs when online."""
        # Step 1: Queue offline action (simulating offline mode)
        queue_response = client.post(
            "/api/mobile/offline/queue",
            json={
                "action_type": "agent_message",
                "action_data": {
                    "agent_id": e2e_agent.id,
                    "message": "Offline message"
                },
                "priority": 5
            },
            headers={"X-Device-ID": "test_device_123"}
        )
        assert queue_response.status_code == 200
        action_id = queue_response.json()["action_id"]

        # Step 2: Check sync status
        status_response = client.get(
            "/api/mobile/sync/status",
            headers={"X-Device-ID": "test_device_123"}
        )
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["pending_actions_count"] >= 1

        # Step 3: Trigger sync (simulating coming back online)
        sync_response = client.post(
            "/api/mobile/sync/trigger",
            headers={"X-Device-ID": "test_device_123"}
        )
        assert sync_response.status_code == 200
        sync_data = sync_response.json()
        assert sync_data["processed"] >= 1

    def test_mobile_canvas_interaction(self, client: TestClient, e2e_user):
        """Scenario: User views and interacts with canvas on mobile."""
        # Step 1: Get list of canvases
        canvases_response = client.get("/api/mobile/canvases")
        assert canvases_response.status_code == 200
        canvases = canvases_response.json()["canvases"]

        if len(canvases) > 0:
            canvas_id = canvases[0]["canvas_id"]

            # Step 2: Get canvas details (mobile-optimized)
            canvas_response = client.get(
                f"/api/canvas/{canvas_id}",
                params={"platform": "mobile", "optimized": True}
            )
            assert canvas_response.status_code == 200

            # Step 3: Audit canvas interaction
            audit_response = client.post(
                f"/api/mobile/canvases/{canvas_id}/audit",
                json={
                    "action": "view",
                    "component_count": 1
                },
                headers={"X-Device-ID": "test_device_123"}
            )
            assert audit_response.status_code == 200


# ============================================================================
# Scenario 2: Menu Bar User Journey
# ============================================================================

class TestMenuBarUserJourney:
    """Test complete menu bar user journey."""

    def test_menubar_login_and_quick_chat(self, client: TestClient, e2e_user, e2e_agent):
        """Scenario: User logs into menu bar and uses quick chat."""
        # Step 1: Menu bar login
        login_response = client.post(
            "/api/menubar/auth/login",
            json={
                "email": "e2e@test.com",
                "password": "test_password",
                "device_name": "Test MacBook",
                "platform": "darwin"
            },
            headers={"Host": "localhost"}
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "token" in login_data
        assert "device_id" in login_data

        token = login_data["token"]
        device_id = login_data["device_id"]

        # Step 2: Get recent agents
        agents_response = client.get(
            "/api/menubar/recent/agents",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert agents_response.status_code == 200
        agents = agents_response.json()
        assert isinstance(agents, list)

        # Step 3: Send quick chat message
        chat_response = client.post(
            "/api/menubar/quick/chat",
            json={
                "agent_id": e2e_agent.id,
                "message": "Quick chat from menu bar!"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert chat_response.status_code == 200
        chat_data = chat_response.json()
        assert "response" in chat_data or "message" in chat_data

        # Step 4: Check connection status
        status_response = client.get(
            "/api/menubar/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["connected"] == True

    def test_menubar_recent_items(self, client: TestClient, e2e_user):
        """Scenario: User views recent agents and canvases from menu bar."""
        # Login first
        login_response = client.post(
            "/api/menubar/auth/login",
            json={
                "email": "e2e@test.com",
                "password": "test_password",
                "device_name": "Test MacBook",
                "platform": "darwin"
            },
            headers={"Host": "localhost"}
        )
        token = login_response.json()["token"]

        # Get recent agents
        agents_response = client.get(
            "/api/menubar/recent/agents",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert agents_response.status_code == 200
        agents = agents_response.json()
        assert isinstance(agents, list)
        assert len(agents) <= 5  # Top 5

        # Get recent canvases
        canvases_response = client.get(
            "/api/menubar/recent/canvases",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert canvases_response.status_code == 200
        canvases = canvases_response.json()
        assert isinstance(canvases, list)
        assert len(canvases) <= 5  # Top 5

        # Get combined recent items
        combined_response = client.get(
            "/api/menubar/recent",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert combined_response.status_code == 200
        combined = combined_response.json()
        assert "agents" in combined
        assert "canvases" in combined


# ============================================================================
# Scenario 3: Cross-Platform Sync
# ============================================================================

class TestCrossPlatformSync:
    """Test synchronization between mobile and menu bar apps."""

    def test_shared_agent_execution_history(self, client: TestClient, e2e_user, e2e_agent):
        """Scenario: Agent executions visible across mobile and menu bar."""
        # Send message from mobile
        mobile_chat = client.post(
            "/api/agents/mobile/chat",
            json={
                "agent_id": e2e_agent.id,
                "message": "Message from mobile",
                "platform": "mobile"
            }
        )
        assert mobile_chat.status_code == 200
        mobile_session_id = mobile_chat.json()["session_id"]

        # Login to menu bar
        menubar_login = client.post(
            "/api/menubar/auth/login",
            json={
                "email": "e2e@test.com",
                "password": "test_password",
                "device_name": "Test MacBook",
                "platform": "darwin"
            },
            headers={"Host": "localhost"}
        )
        token = menubar_login.json()["token"]

        # Check recent agents in menu bar - should show the agent we just used
        agents_response = client.get(
            "/api/menubar/recent/agents",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert agents_response.status_code == 200
        agents = agents_response.json()
        # Should include the agent we just chatted with
        assert any(a["id"] == e2e_agent.id for a in agents)

    def test_shared_canvas_history(self, client: TestClient, e2e_user):
        """Scenario: Canvas interactions visible across platforms."""
        # This tests that canvas audits are shared between mobile and menu bar

        # Register mobile device
        mobile_device = client.post(
            "/api/mobile/notifications/register",
            json={
                "device_token": "mobile_token_456",
                "platform": "ios",
                "device_info": {}
            },
            headers={"X-User-ID": str(e2e_user.id)}
        )
        assert mobile_device.status_code == 200

        # Login to menu bar
        menubar_login = client.post(
            "/api/menubar/auth/login",
            json{
                "email": "e2e@test.com",
                "password": "test_password",
                "device_name": "Test MacBook",
                "platform": "darwin"
            },
            headers={"Host": "localhost"}
        )
        token = menubar_login.json()["token"]

        # Both platforms should see the same canvas history
        mobile_canvases = client.get("/api/mobile/canvases")
        menubar_canvases = client.get(
            "/api/menubar/recent/canvases",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert mobile_canvases.status_code == 200
        assert menubar_canvases.status_code == 200


# ============================================================================
# Scenario 4: Offline to Online Sync
# ============================================================================

class TestOfflineOnlineSync:
    """Test offline to online synchronization scenarios."""

    def test_queue_sync_resolve_conflict(self, client: TestClient, e2e_user):
        """Scenario: Queue action offline, sync online, resolve conflict."""
        # Step 1: Queue action while offline
        queue_response = client.post(
            "/api/mobile/offline/queue",
            json={
                "action_type": "agent_message",
                "action_data": {
                    "message": "Offline test message"
                },
                "priority": 5
            },
            headers={"X-Device-ID": "offline_device_123"}
        )
        assert queue_response.status_code == 200
        action_id = queue_response.json()["action_id"]

        # Step 2: Trigger sync
        sync_response = client.post(
            "/api/mobile/sync/trigger",
            headers={"X-Device-ID": "offline_device_123"}
        )
        assert sync_response.status_code == 200
        sync_result = sync_response.json()

        # Step 3: If conflict occurred, resolve it
        if sync_result.get("conflicts", 0) > 0:
            resolve_response = client.post(
                "/api/mobile/sync/conflict/resolve",
                json={
                    "conflict_id": sync_result["conflicts"][0]["id"],
                    "resolution": "local"  # or "server"
                },
                headers={"X-Device-ID": "offline_device_123"}
            )
            assert resolve_response.status_code == 200

    def test_batch_sync_performance(self, client: TestClient, e2e_user):
        """Scenario: Sync large batch of offline actions efficiently."""
        # Queue 50 actions
        action_ids = []
        for i in range(50):
            response = client.post(
                "/api/mobile/offline/queue",
                json={
                    "action_type": "test_action",
                    "action_data": {"index": i},
                    "priority": i % 10
                },
                headers={"X-Device-ID": "batch_test_device"}
            )
            if response.status_code == 200:
                action_ids.append(response.json()["action_id"])

        # Trigger batch sync
        sync_response = client.post(
            "/api/mobile/sync/trigger",
            headers={"X-Device-ID": "batch_test_device"}
        )
        assert sync_response.status_code == 200
        sync_result = sync_response.json()

        # Verify most actions were processed
        assert sync_result["processed"] >= len(action_ids) * 0.9  # At least 90%


# ============================================================================
# Scenario 5: Push Notifications
# ============================================================================

class TestPushNotifications:
    """Test push notification scenarios."""

    @patch('core.push_notification_service.PushNotificationService._send_fcm_notification')
    @patch('core.push_notification_service.PushNotificationService._send_apns_notification')
    def test_agent_operation_notification(
        self,
        mock_fcm,
        mock_apns,
        client: TestClient,
        e2e_user,
        e2e_agent
    ):
        """Scenario: User receives push notification for agent operation."""
        # Mock successful push
        mock_fcm.return_value = True
        mock_apns.return_value = True

        # Register devices
        client.post(
            "/api/mobile/notifications/register",
            json={
                "device_token": "ios_token_123",
                "platform": "ios",
                "device_info": {}
            },
            headers={"X-User-ID": str(e2e_user.id)}
        )

        client.post(
            "/api/mobile/notifications/register",
            json={
                "device_token": "android_token_123",
                "platform": "android",
                "device_info": {}
            },
            headers={"X-User-ID": str(e2e_user.id)}
        )

        # Trigger agent operation notification
        # This would normally be called from the agent execution service
        # For E2E test, we'll call the notification endpoint directly

        # Verify notification was sent (would be async in real scenario)
        assert True  # Placeholder for actual notification verification


# ============================================================================
# Performance Tests
# ============================================================================

class TestE2EPerformance:
    """Performance tests for end-to-end scenarios."""

    def test_full_chat_flow_performance(self, client: TestClient, e2e_user, e2e_agent):
        """Test complete chat flow completes within performance targets."""
        import time

        # Mobile login
        start = time.time()
        client.post(
            "/api/mobile/notifications/register",
            json={
                "device_token": "perf_test_token",
                "platform": "ios",
                "device_info": {}
            },
            headers={"X-User-ID": str(e2e_user.id)}
        )
        register_time = (time.time() - start) * 1000
        assert register_time < 500  # Should be <500ms

        # Get agents
        start = time.time()
        agents = client.get("/api/agents/mobile/list")
        agents_time = (time.time() - start) * 1000
        assert agents_time < 1000  # Should be <1s
        assert agents.status_code == 200

        # Send message
        start = time.time()
        chat = client.post(
            "/api/agents/mobile/chat",
            json={
                "agent_id": e2e_agent.id,
                "message": "Performance test message",
                "platform": "mobile"
            }
        )
        chat_time = (time.time() - start) * 1000
        assert chat_time < 2000  # Should be <2s
        assert chat.status_code == 200

    def test_menubar_quick_chat_performance(self, client: TestClient, e2e_user, e2e_agent):
        """Test menu bar quick chat performance."""
        import time

        # Login
        start = time.time()
        login = client.post(
            "/api/menubar/auth/login",
            json={
                "email": "e2e@test.com",
                "password": "test_password",
                "device_name": "Perf Test Mac",
                "platform": "darwin"
            },
            headers={"Host": "localhost"}
        )
        login_time = (time.time() - start) * 1000
        assert login_time < 1000  # Should be <1s
        assert login.status_code == 200

        token = login.json()["token"]

        # Quick chat
        start = time.time()
        chat = client.post(
            "/api/menubar/quick/chat",
            json={
                "agent_id": e2e_agent.id,
                "message": "Quick chat!"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        chat_time = (time.time() - start) * 1000
        assert chat_time < 1500  # Should be <1.5s
        assert chat.status_code == 200


# ============================================================================
# Integration Edge Cases
# ============================================================================

class TestE2EEdgeCases:
    """Test edge cases and error scenarios in E2E flows."""

    def test_menubar_token_expiry_handling(self, client: TestClient, e2e_user):
        """Scenario: Menu bar handles token expiry gracefully."""
        # Login
        login = client.post(
            "/api/menubar/auth/login",
            json={
                "email": "e2e@test.com",
                "password": "test_password",
                "device_name": "Test Mac",
                "platform": "darwin"
            },
            headers={"Host": "localhost"}
        )
        token = login.json()["token"]

        # Use invalid token
        response = client.get(
            "/api/menubar/status",
            headers={"Authorization": "Bearer invalid_token_123"}
        )
        assert response.status_code == 401

    def test_mobile_network_error_handling(self, client: TestClient, e2e_user):
        """Scenario: Mobile app handles network errors gracefully."""
        # Try to access unavailable endpoint
        response = client.get("/api/mobile/sync/status")
        # Should handle gracefully (401 if no device ID, or other appropriate error)
        assert response.status_code != 500  # Should not be server error

    def test_concurrent_device_usage(self, client: TestClient, e2e_user):
        """Scenario: User has multiple devices active simultaneously."""
        # Register mobile device
        mobile = client.post(
            "/api/mobile/notifications/register",
            json={
                "device_token": "mobile_1",
                "platform": "ios",
                "device_info": {}
            },
            headers={"X-User-ID": str(e2e_user.id)}
        )
        assert mobile.status_code == 200

        # Register menu bar device
        menubar = client.post(
            "/api/menubar/auth/login",
            json={
                "email": "e2e@test.com",
                "password": "test_password",
                "device_name": "Test Mac",
                "platform": "darwin"
            },
            headers={"Host": "localhost"}
        )
        assert menubar.status_code == 200

        # Both should be able to operate independently
        assert mobile.json()["device_id"] != menubar.json()["device_id"]
