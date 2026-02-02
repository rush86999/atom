"""
Mobile Canvas Tests

Comprehensive tests for mobile canvas access, push notifications,
and offline sync functionality.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from core.models import MobileDevice, OfflineAction, SyncState, User
from core.offline_sync_service import OfflineSyncService, get_offline_sync_service
from core.push_notification_service import PushNotificationService, get_push_notification_service


# Test database
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """Create test database session."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def user(db):
    """Create test user."""
    user = User(
        id="test_user_1",
        email="test@example.com",
        first_name="Test",
        last_name="User"
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def mobile_device(db, user):
    """Create test mobile device."""
    device = MobileDevice(
        id="test_device_1",
        user_id=user.id,
        device_token="test_token_123",
        platform="ios",
        status="active",
        device_info={"model": "iPhone 14", "os_version": "iOS 17"},
        notification_enabled=True
    )
    db.add(device)
    db.commit()
    return device


class TestOfflineSyncService:
    """Test offline sync service functionality."""

    @pytest.mark.asyncio
    async def test_queue_action(self, db, mobile_device):
        """Test queueing an offline action."""
        service = OfflineSyncService(db)

        result = await service.queue_action(
            device_id=mobile_device.id,
            user_id=mobile_device.user_id,
            action_type="agent_message",
            action_data={"message": "Hello from mobile"},
            priority=1
        )

        assert result["status"] == "queued"
        assert "action_id" in result

        # Verify action was created
        action = db.query(OfflineAction).filter(
            OfflineAction.device_id == mobile_device.id
        ).first()
        assert action is not None
        assert action.action_type == "agent_message"
        assert action.status == "pending"

    @pytest.mark.asyncio
    async def test_queue_multiple_actions(self, db, mobile_device):
        """Test queueing multiple actions."""
        service = OfflineSyncService(db)

        # Queue multiple actions
        for i in range(3):
            await service.queue_action(
                device_id=mobile_device.id,
                user_id=mobile_device.user_id,
                action_type="agent_message",
                action_data={"message": f"Message {i}"},
                priority=i
            )

        # Verify all actions were queued
        actions = db.query(OfflineAction).filter(
            OfflineAction.device_id == mobile_device.id
        ).all()
        assert len(actions) == 3

    @pytest.mark.asyncio
    async def test_get_sync_status(self, db, mobile_device):
        """Test getting sync status."""
        service = OfflineSyncService(db)

        # Queue an action to create sync state
        await service.queue_action(
            device_id=mobile_device.id,
            user_id=mobile_device.user_id,
            action_type="agent_message",
            action_data={"message": "Test"}
        )

        # Get sync status
        status = service.get_sync_status(mobile_device.id, mobile_device.user_id)

        assert status["device_id"] == mobile_device.id
        assert status["pending_actions_count"] >= 1
        assert "total_syncs" in status

    @pytest.mark.asyncio
    async def test_sync_device_actions_no_actions(self, db, mobile_device):
        """Test syncing when no pending actions."""
        service = OfflineSyncService(db)

        result = await service.sync_device_actions(
            device_id=mobile_device.id,
            user_id=mobile_device.user_id
        )

        assert result["status"] == "no_actions"
        assert result["synced_count"] == 0

    @pytest.mark.asyncio
    async def test_clear_pending_actions(self, db, mobile_device):
        """Test clearing pending actions."""
        service = OfflineSyncService(db)

        # Queue some actions
        await service.queue_action(
            device_id=mobile_device.id,
            user_id=mobile_device.user_id,
            action_type="agent_message",
            action_data={"message": "Test 1"}
        )
        await service.queue_action(
            device_id=mobile_device.id,
            user_id=mobile_device.user_id,
            action_type="agent_message",
            action_data={"message": "Test 2"}
        )

        # Clear pending actions
        result = await service.clear_pending_actions(
            device_id=mobile_device.id,
            user_id=mobile_device.user_id
        )

        assert result["status"] == "success"
        assert result["cleared_count"] == 2

        # Verify actions were cleared
        pending_count = db.query(OfflineAction).filter(
            OfflineAction.device_id == mobile_device.id,
            OfflineAction.status == "pending"
        ).count()
        assert pending_count == 0

    @pytest.mark.asyncio
    async def test_get_pending_actions(self, db, mobile_device):
        """Test getting list of pending actions."""
        service = OfflineSyncService(db)

        # Queue actions with different priorities
        await service.queue_action(
            device_id=mobile_device.id,
            user_id=mobile_device.user_id,
            action_type="agent_message",
            action_data={"message": "High priority"},
            priority=10
        )
        await service.queue_action(
            device_id=mobile_device.id,
            user_id=mobile_device.user_id,
            action_type="workflow_trigger",
            action_data={"workflow_id": "test"},
            priority=1
        )

        # Get pending actions
        actions = await service.get_pending_actions(
            device_id=mobile_device.id,
            user_id=mobile_device.user_id
        )

        assert len(actions) == 2
        assert actions[0]["action_type"] == "agent_message"  # Higher priority first
        assert actions[1]["action_type"] == "workflow_trigger"

    def test_get_or_create_sync_state(self, db, mobile_device):
        """Test sync state creation."""
        service = OfflineSyncService(db)

        # First call should create sync state
        sync_state = service._get_or_create_sync_state(
            mobile_device.id,
            mobile_device.user_id
        )

        assert sync_state.device_id == mobile_device.id
        assert sync_state.pending_actions_count == 0

        # Second call should return existing state
        sync_state_2 = service._get_or_create_sync_state(
            mobile_device.id,
            mobile_device.user_id
        )

        assert sync_state.id == sync_state_2.id


class TestPushNotificationService:
    """Test push notification service functionality."""

    @pytest.mark.asyncio
    async def test_register_new_device(self, db, user):
        """Test registering a new device."""
        service = PushNotificationService(db)

        result = await service.register_device(
            user_id=user.id,
            device_token="new_device_token",
            platform="android",
            device_info={"model": "Pixel 7", "os_version": "Android 14"}
        )

        assert result["status"] == "registered"
        assert "device_id" in result
        assert result["platform"] == "android"

        # Verify device was created
        device = db.query(MobileDevice).filter(
            MobileDevice.device_token == "new_device_token"
        ).first()
        assert device is not None
        assert device.platform == "android"

    @pytest.mark.asyncio
    async def test_register_existing_device(self, db, mobile_device):
        """Test updating an existing device."""
        service = PushNotificationService(db)

        result = await service.register_device(
            user_id=mobile_device.user_id,
            device_token=mobile_device.device_token,
            platform="android",  # Changed from ios
            device_info={"model": "Updated"}
        )

        assert result["status"] == "updated"

        # Verify device was updated
        db.refresh(mobile_device)
        assert mobile_device.platform == "android"

    @pytest.mark.asyncio
    async def test_send_notification_no_devices(self, db, user):
        """Test sending notification when user has no devices."""
        service = PushNotificationService(db)

        # Disable feature to avoid actual API calls
        import os
        os.environ["PUSH_NOTIFICATIONS_ENABLED"] = "false"

        result = await service.send_notification(
            user_id=user.id,
            notification_type="test",
            title="Test",
            body="Test message"
        )

        assert result is False  # No devices registered

    @pytest.mark.asyncio
    async def test_send_agent_operation_notification(self, db, mobile_device):
        """Test agent operation notification."""
        service = PushNotificationService(db)

        # Disable feature to avoid actual API calls
        import os
        os.environ["PUSH_NOTIFICATIONS_ENABLED"] = "false"

        result = await service.send_agent_operation_notification(
            user_id=mobile_device.user_id,
            agent_name="Sales Assistant",
            operation_type="Process Leads",
            status="completed"
        )

        assert result is False  # Feature disabled

    @pytest.mark.asyncio
    async def test_send_error_alert(self, db, mobile_device):
        """Test error alert notification."""
        service = PushNotificationService(db)

        # Disable feature to avoid actual API calls
        import os
        os.environ["PUSH_NOTIFICATIONS_ENABLED"] = "false"

        result = await service.send_error_alert(
            user_id=mobile_device.user_id,
            error_type="Connection Failed",
            error_message="Unable to connect to Slack",
            severity="warning"
        )

        assert result is False  # Feature disabled

    @pytest.mark.asyncio
    async def test_send_approval_request(self, db, mobile_device):
        """Test approval request notification."""
        service = PushNotificationService(db)

        # Disable feature to avoid actual API calls
        import os
        os.environ["PUSH_NOTIFICATIONS_ENABLED"] = "false"

        result = await service.send_approval_request(
            user_id=mobile_device.user_id,
            agent_id="agent_123",
            agent_name="Sales Bot",
            action_description="Send message to #general",
            options=[
                {"label": "Approve", "action": "approve"},
                {"label": "Deny", "action": "deny"}
            ]
        )

        assert result is False  # Feature disabled

    @pytest.mark.asyncio
    async def test_send_system_alert(self, db, mobile_device):
        """Test system alert notification."""
        service = PushNotificationService(db)

        # Disable feature to avoid actual API calls
        import os
        os.environ["PUSH_NOTIFICATIONS_ENABLED"] = "false"

        result = await service.send_system_alert(
            user_id=mobile_device.user_id,
            alert_type="High CPU",
            message="CPU usage is at 85%",
            severity="warning"
        )

        assert result is False  # Feature disabled


class TestMobileDeviceModel:
    """Test MobileDevice model."""

    def test_create_mobile_device(self, db, user):
        """Test creating a mobile device."""
        device = MobileDevice(
            id="test_device",
            user_id=user.id,
            device_token="test_token",
            platform="ios",
            status="active",
            device_info={"model": "iPhone 14"},
            notification_enabled=True
        )

        db.add(device)
        db.commit()

        retrieved = db.query(MobileDevice).filter(
            MobileDevice.id == "test_device"
        ).first()

        assert retrieved is not None
        assert retrieved.platform == "ios"
        assert retrieved.notification_enabled is True


class TestOfflineActionModel:
    """Test OfflineAction model."""

    def test_create_offline_action(self, db, mobile_device):
        """Test creating an offline action."""
        action = OfflineAction(
            id="test_action",
            device_id=mobile_device.id,
            user_id=mobile_device.user_id,
            action_type="agent_message",
            action_data={"message": "Test"},
            priority=5,
            status="pending"
        )

        db.add(action)
        db.commit()

        retrieved = db.query(OfflineAction).filter(
            OfflineAction.id == "test_action"
        ).first()

        assert retrieved is not None
        assert retrieved.action_type == "agent_message"
        assert retrieved.priority == 5
        assert retrieved.status == "pending"


class TestSyncStateModel:
    """Test SyncState model."""

    def test_create_sync_state(self, db, mobile_device):
        """Test creating a sync state."""
        sync_state = SyncState(
            id="test_sync",
            device_id=mobile_device.id,
            user_id=mobile_device.user_id,
            pending_actions_count=5,
            auto_sync_enabled=True
        )

        db.add(sync_state)
        db.commit()

        retrieved = db.query(SyncState).filter(
            SyncState.id == "test_sync"
        ).first()

        assert retrieved is not None
        assert retrieved.pending_actions_count == 5
        assert retrieved.auto_sync_enabled is True


class TestMobileDeviceRelationships:
    """Test mobile device relationships."""

    def test_device_user_relationship(self, db, user):
        """Test device to user relationship."""
        device = MobileDevice(
            id="test_device",
            user_id=user.id,
            device_token="test_token",
            platform="ios"
        )

        db.add(device)
        db.commit()

        assert device.user == user
        assert device in user.mobile_devices

    def test_device_offline_actions_relationship(self, db, mobile_device):
        """Test device to offline actions relationship."""
        action = OfflineAction(
            id="test_action",
            device_id=mobile_device.id,
            user_id=mobile_device.user_id,
            action_type="agent_message",
            action_data={"message": "Test"}
        )

        db.add(action)
        db.commit()

        assert action in mobile_device.offline_actions
        assert action.device == mobile_device

    def test_sync_state_device_relationship(self, db, mobile_device):
        """Test sync state to device relationship."""
        sync_state = SyncState(
            id="test_sync",
            device_id=mobile_device.id,
            user_id=mobile_device.user_id
        )

        db.add(sync_state)
        db.commit()

        assert sync_state.device == mobile_device
        assert mobile_device.sync_state == sync_state


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
