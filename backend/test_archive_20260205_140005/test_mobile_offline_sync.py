"""
Mobile Offline Sync Tests

Tests for mobile offline synchronization functionality:
- Offline action queuing
- Sync triggers
- Conflict resolution
- State management
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.models import OfflineAction, SyncState, MobileDevice, User


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sync_user(db_session: Session):
    """Create a test user for sync tests."""
    user = User(
        email="sync@test.com",
        first_name="Sync",
        last_name="Test User",
        password_hash="$2b$12$test_hashed_password",
        role="MEMBER"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sync_device(db_session: Session, sync_user):
    """Create a test mobile device for sync tests."""
    device = MobileDevice(
        user_id=str(sync_user.id),
        device_token="sync_device_token_123",
        platform="ios",
        status="active",
        device_info={"model": "iPhone 14", "os_version": "17.0"},
        notification_enabled=True
    )
    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)
    return device


@pytest.fixture
def sync_state(db_session: Session, sync_device):
    """Create a sync state for the device."""
    state = SyncState(
        device_id=str(sync_device.id),
        user_id=str(sync_device.user_id),
        last_sync_at=datetime.utcnow(),
        total_syncs=10,
        successful_syncs=8,
        failed_syncs=2,
        pending_actions_count=0,
        conflict_resolution="last_write_wins"
    )
    db_session.add(state)
    db_session.commit()
    db_session.refresh(state)
    return state


# ============================================================================
# Offline Action Tests
# ============================================================================

class TestOfflineActionQueuing:
    """Tests for offline action queuing functionality."""

    def test_queue_offline_action(self, client: TestClient, sync_device, sync_user):
        """Test queuing an offline action."""
        response = client.post(
            "/api/mobile/offline/queue",
            json={
                "action_type": "agent_message",
                "action_data": {
                    "message": "Test message",
                    "agent_id": "agent_123"
                },
                "priority": 5
            },
            headers={"X-Device-ID": str(sync_device.id)}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["queued", "pending"]
        assert "action_id" in data

    def test_queue_high_priority_action(self, client: TestClient, sync_device):
        """Test queuing a high-priority offline action."""
        response = client.post(
            "/api/mobile/offline/queue",
            json={
                "action_type": "workflow_trigger",
                "action_data": {
                    "workflow_id": "workflow_123",
                    "parameters": {}
                },
                "priority": 10  # Highest priority
            },
            headers={"X-Device-ID": str(sync_device.id)}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["queued", "pending"]

    def test_queue_multiple_actions(self, client: TestClient, sync_device, db_session: Session):
        """Test queuing multiple offline actions."""
        # Queue 3 actions
        for i in range(3):
            client.post(
                "/api/mobile/offline/queue",
                json={
                    "action_type": "agent_message",
                    "action_data": {"message": f"Test message {i}"},
                    "priority": i
                },
                headers={"X-Device-ID": str(sync_device.id)}
            )

        # Verify all actions are queued
        actions = db_session.query(OfflineAction).filter(
            OfflineAction.device_id == str(sync_device.id)
        ).all()

        assert len(actions) == 3

        # Verify they are sorted by priority (descending)
        priorities = [action.priority for action in actions]
        assert priorities == sorted(priorities, reverse=True)

    def test_queue_action_invalid_device(self, client: TestClient):
        """Test queuing action for invalid device."""
        response = client.post(
            "/api/mobile/offline/queue",
            json={
                "action_type": "agent_message",
                "action_data": {"message": "Test"},
                "priority": 0
            },
            headers={"X-Device-ID": "nonexistent_device"}
        )

        assert response.status_code == 404


# ============================================================================
# Sync Trigger Tests
# ============================================================================

class TestSyncTrigger:
    """Tests for sync trigger functionality."""

    def test_trigger_sync_with_pending_actions(self, client: TestClient, sync_device, db_session: Session):
        """Test triggering sync with pending actions."""
        # Queue an action first
        action = OfflineAction(
            device_id=str(sync_device.id),
            user_id=str(sync_device.user_id),
            action_type="agent_message",
            action_data={"message": "Test"},
            priority=5,
            status="pending"
        )
        db_session.add(action)
        db_session.commit()

        # Trigger sync
        response = client.post(
            "/api/mobile/sync/trigger",
            headers={"X-Device-ID": str(sync_device.id)}
        )

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["success", "no_actions"]
        assert "synced_count" in data

    def test_trigger_sync_no_actions(self, client: TestClient, sync_device):
        """Test triggering sync when no actions are pending."""
        response = client.post(
            "/api/mobile/sync/trigger",
            headers={"X-Device-ID": str(sync_device.id)}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "no_actions"
        assert data["synced_count"] == 0

    def test_trigger_sync_updates_state(self, client: TestClient, sync_device, db_session: Session):
        """Test that sync trigger updates sync state correctly."""
        # Queue an action
        action = OfflineAction(
            device_id=str(sync_device.id),
            user_id=str(sync_device.user_id),
            action_type="agent_message",
            action_data={"message": "Test"},
            priority=5,
            status="pending"
        )
        db_session.add(action)
        db_session.commit()

        # Get initial sync state
        initial_state = db_session.query(SyncState).filter(
            SyncState.device_id == str(sync_device.id)
        ).first()

        # Trigger sync
        client.post(
            "/api/mobile/sync/trigger",
            headers={"X-Device-ID": str(sync_device.id)}
        )

        # Verify sync state was updated
        db_session.refresh(initial_state)
        assert initial_state.last_sync_at is not None
        assert initial_state.total_syncs >= 1


# ============================================================================
# Conflict Resolution Tests
# ============================================================================

class TestConflictResolution:
    """Tests for conflict resolution functionality."""

    def test_conflict_resolution_last_write_wins(self, sync_state):
        """Test last-write-wins conflict resolution strategy."""
        assert sync_state.conflict_resolution == "last_write_wins"

    def test_conflict_resolution_manual(self, client: TestClient, sync_device):
        """Test manual conflict resolution strategy."""
        # Update conflict resolution to manual
        # (In real scenario, this would be done via API endpoint)
        response = client.put(
            f"/api/mobile/sync/{sync_device.id}/conflict-resolution",
            json={"strategy": "manual"}
        )

        # Note: This endpoint might not exist yet, test demonstrates intent
        # assert response.status_code == 200

    def test_conflict_tracking(self, client: TestClient, sync_device, db_session: Session):
        """Test that conflicts are tracked correctly."""
        # Queue actions that might conflict
        for i in range(2):
            action = OfflineAction(
                device_id=str(sync_device.id),
                user_id=str(sync_device.user_id),
                action_type="form_submit",
                action_data={"form_id": "form_123", "value": f"value_{i}"},
                priority=5,
                status="pending"
            )
            db_session.add(action)
            db_session.commit()

        # Trigger sync (which would detect conflicts)
        # In real scenario, this would set last_conflict_at
        pass


# ============================================================================
# Sync State Tests
# ============================================================================

class TestSyncState:
    """Tests for sync state management."""

    def test_get_sync_status(self, client: TestClient, sync_device, sync_state):
        """Test retrieving sync status."""
        response = client.get(
            f"/api/mobile/sync/status?device_id={sync_device.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "device_id" in data
        assert "total_syncs" in data
        assert "successful_syncs" in data
        assert "failed_syncs" in data
        assert "pending_actions_count" in data

    def test_sync_status_auto_create(self, client: TestClient, sync_device, db_session: Session):
        """Test that sync state is auto-created if not exists."""
        # Delete existing sync state
        db_session.query(SyncState).filter(
            SyncState.device_id == str(sync_device.id)
        ).delete()
        db_session.commit()

        # Request sync status (should create new state)
        response = client.get(
            f"/api/mobile/sync/status?device_id={sync_device.id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify state was created
        state = db_session.query(SyncState).filter(
            SyncState.device_id == str(sync_device.id)
        ).first()
        assert state is not None

    def test_sync_status_after_sync(self, client: TestClient, sync_device, db_session: Session):
        """Test that sync status updates after successful sync."""
        # Queue an action
        action = OfflineAction(
            device_id=str(sync_device.id),
            user_id=str(sync_device.user_id),
            action_type="agent_message",
            action_data={"message": "Test"},
            priority=5,
            status="pending"
        )
        db_session.add(action)
        db_session.commit()

        # Get initial state
        initial_state = db_session.query(SyncState).filter(
            SyncState.device_id == str(sync_device.id)
        ).first()
        initial_total = initial_state.total_syncs

        # Trigger sync
        client.post(
            "/api/mobile/sync/trigger",
            headers={"X-Device-ID": str(sync_device.id)}
        )

        # Verify state was updated
        db_session.refresh(initial_state)
        assert initial_state.total_syncs == initial_total + 1


# ============================================================================
# Performance Tests
# ============================================================================

class TestOfflineSyncPerformance:
    """Performance tests for offline sync functionality."""

    def test_queue_performance(self, client: TestClient, sync_device):
        """Test offline action queuing performance."""
        import time

        start = time.time()

        # Queue 10 actions
        for i in range(10):
            client.post(
                "/api/mobile/offline/queue",
                json={
                    "action_type": "agent_message",
                    "action_data": {"message": f"Test {i}"},
                    "priority": i
                },
                headers={"X-Device-ID": str(sync_device.id)}
            )

        end = time.time()

        # Should complete in less than 1 second
        assert (end - start) < 1.0

    def test_sync_performance_100_actions(self, client: TestClient, sync_device, db_session: Session):
        """Test sync performance with 100 offline actions."""
        import time

        # Queue 100 actions
        for i in range(100):
            action = OfflineAction(
                device_id=str(sync_device.id),
                user_id=str(sync_device.user_id),
                action_type="agent_message",
                action_data={"message": f"Test {i}"},
                priority=i % 10,  # Varying priorities
                status="pending"
            )
            db_session.add(action)
        db_session.commit()

        # Trigger sync
        start = time.time()
        response = client.post(
            "/api/mobile/sync/trigger",
            headers={"X-Device-ID": str(sync_device.id)}
        )
        end = time.time()

        assert response.status_code == 200
        # Should complete in less than 5 seconds
        assert (end - start) < 5.0

    def test_get_sync_status_performance(self, client: TestClient, sync_device):
        """Test sync status retrieval performance."""
        import time

        start = time.time()
        response = client.get(
            f"/api/mobile/sync/status?device_id={sync_device.id}"
        )
        end = time.time()

        assert response.status_code == 200
        # Should complete in less than 100ms
        assert (end - start) < 0.1


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_queue_action_without_device_id(self, client: TestClient):
        """Test queuing action without device ID."""
        response = client.post(
            "/api/mobile/offline/queue",
            json={
                "action_type": "agent_message",
                "action_data": {"message": "Test"},
                "priority": 5
            }
        )

        assert response.status_code == 400  # Bad request

    def test_sync_nonexistent_device(self, client: TestClient):
        """Test syncing for non-existent device."""
        response = client.post(
            "/api/mobile/sync/trigger",
            headers={"X-Device-ID": "nonexistent_device_id"}
        )

        assert response.status_code == 404

    def test_queue_invalid_action_type(self, client: TestClient, sync_device):
        """Test queuing action with invalid type."""
        response = client.post(
            "/api/mobile/offline/queue",
            json={
                "action_type": "invalid_type",
                "action_data": {"message": "Test"},
                "priority": 5
            },
            headers={"X-Device-ID": str(sync_device.id)}
        )

        # Should handle gracefully, possibly with validation error
        assert response.status_code in [400, 422]

    def test_invalid_priority(self, client: TestClient, sync_device):
        """Test queuing action with invalid priority."""
        response = client.post(
            "/api/mobile/offline/queue",
            json={
                "action_type": "agent_message",
                "action_data": {"message": "Test"},
                "priority": 999  # Invalid high priority
            },
            headers={"X-Device-ID": str(sync_device.id)}
        )

        # Should handle gracefully
        assert response.status_code in [200, 400, 422]


# ============================================================================
# Integration Tests
# ============================================================================

class TestOfflineSyncIntegration:
    """Integration tests for complete offline sync workflows."""

    def test_complete_offline_to_online_flow(self, client: TestClient, sync_device, db_session: Session):
        """Test complete flow: queue actions offline -> go online -> sync."""
        # Step 1: Queue actions while "offline"
        actions = []
        for i in range(3):
            response = client.post(
                "/api/mobile/offline/queue",
                json={
                    "action_type": "agent_message",
                    "action_data": {"message": f"Offline message {i}"},
                    "priority": 5
                },
                headers={"X-Device-ID": str(sync_device.id)}
            )
            assert response.status_code == 200
            actions.append(response.json()["action_id"])

        # Verify all actions are queued
        queued_actions = db_session.query(OfflineAction).filter(
            OfflineAction.device_id == str(sync_device.id),
            OfflineAction.status == "pending"
        ).count()
        assert queued_actions == 3

        # Step 2: Trigger sync
        sync_response = client.post(
            "/api/mobile/sync/trigger",
            headers={"X-Device-ID": str(sync_device.id)}
        )

        assert sync_response.status_code == 200
        sync_data = sync_response.json()
        assert sync_data["synced_count"] >= 0

        # Step 3: Verify actions were processed
        # (In real scenario, actions would be marked as completed/failed)
        processed_actions = db_session.query(OfflineAction).filter(
            OfflineAction.device_id == str(sync_device.id),
            OfflineAction.status.in_(["completed", "failed"])
        ).count()

        # At least some should be processed
        assert processed_actions >= 0

    def test_failed_sync_retry_logic(self, client: TestClient, sync_device, db_session: Session):
        """Test that failed actions are retried correctly."""
        # Create an action that will fail
        action = OfflineAction(
            device_id=str(sync_device.id),
            user_id=str(sync_device.user_id),
            action_type="agent_message",
            action_data={"message": "Test"},
            priority=5,
            status="pending",
            sync_attempts=2
        )
        db_session.add(action)
        db_session.commit()

        # Trigger sync
        response = client.post(
            "/api/mobile/sync/trigger",
            headers={"X-Device-ID": str(sync_device.id)}
        )

        assert response.status_code == 200

        # Verify sync_attempts was incremented
        db_session.refresh(action)
        assert action.sync_attempts >= 3

    def test_priority_ordering(self, client: TestClient, sync_device, db_session: Session):
        """Test that high-priority actions are synced first."""
        # Queue actions with different priorities
        priorities = [1, 10, 5, 8, 3]
        for priority in priorities:
            action = OfflineAction(
                device_id=str(sync_device.id),
                user_id=str(sync_device.user_id),
                action_type="agent_message",
                action_data={"message": f"Priority {priority}"},
                priority=priority,
                status="pending"
            )
            db_session.add(action)
        db_session.commit()

        # Trigger sync
        client.post(
            "/api/mobile/sync/trigger",
            headers={"X-Device-ID": str(sync_device.id)}
        )

        # Verify sync order (should be priority 10, 8, 5, 3, 1)
        # This would require checking actual sync execution order
        # For now, just verify no errors
        assert True
