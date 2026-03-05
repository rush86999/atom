"""
Integration coverage tests for tools/device_tool.py.

Tests cover device session management, camera, location,
notifications, screen recording, and command execution.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from sqlalchemy.orm import Session


class TestDeviceSessionManager:
    """Tests for device session management."""

    def test_create_session(self, db_session: Session):
        """Test creating a device session."""
        from tools.device_tool import get_device_session_manager

        manager = get_device_session_manager()
        session = manager.create_session(
            user_id="test_list_user",
            device_node_id="device_123",
            session_type="camera"
        )

        assert session["session_id"] is not None
        assert session["user_id"] == "test_user"
        assert session["device_node_id"] == "device_123"
        assert session["status"] == "active"

    def test_get_session(self, db_session: Session):
        """Test getting a device session."""
        from tools.device_tool import get_device_session_manager

        manager = get_device_session_manager()
        created = manager.create_session(
            user_id="test_list_user",
            device_node_id="device_456",
            session_type="location"
        )

        retrieved = manager.get_session(created["session_id"])
        assert retrieved is not None
        assert retrieved["session_type"] == "location"

    def test_close_session(self, db_session: Session):
        """Test closing a device session."""
        from tools.device_tool import get_device_session_manager

        manager = get_device_session_manager()
        session = manager.create_session(
            user_id="test_list_user",
            device_node_id="device_789",
            session_type="notification"
        )

        result = manager.close_session(session["session_id"])
        assert result is True

        # Verify session is removed
        retrieved = manager.get_session(session["session_id"])
        assert retrieved is None


class TestDeviceCamera:
    """Tests for camera capabilities."""

    @pytest.mark.asyncio
    async def test_camera_snap(self, db_session: Session):
        """Test capturing photo from camera."""
        from tools.device_tool import device_camera_snap
        from core.models import DeviceNode

        # Create test device
        device = DeviceNode(workspace_id="default", user_id="test_user", 
            device_id="device_camera_1",
            name="Test Camera Device",
            node_type="mobile",
            status="online",
            platform="iOS"
        )
        db_session.add(device)
        db_session.commit()

        with patch('tools.device_tool.is_device_online', return_value=True):
            with patch('tools.device_tool.send_device_command') as mock_send:
                mock_send.return_value = {
                    "success": True,
                    "file_path": "/tmp/photo.jpg",
                    "data": {"base64_data": "fake_base64"}
                }

                result = await device_camera_snap(
                    db=db_session,
                    user_id="test_list_user",
                    device_node_id="device_camera_1",
                    resolution="1920x1080"
                )

                assert result["success"] is True
                assert result["file_path"] == "/tmp/photo.jpg"

    @pytest.mark.asyncio
    async def test_camera_snap_offline_device(self, db_session: Session):
        """Test camera snap with offline device."""
        from tools.device_tool import device_camera_snap
        from core.models import DeviceNode

        device = DeviceNode(workspace_id="default", user_id="test_user", 
            device_id="device_offline",
            name="Offline Device",
            node_type="mobile",
            status="offline",
            platform="Android"
        )
        db_session.add(device)
        db_session.commit()

        with patch('tools.device_tool.is_device_online', return_value=False):
            result = await device_camera_snap(
                db=db_session,
                user_id="test_list_user",
                device_node_id="device_offline"
            )

            assert result["success"] is False
            assert "not currently connected" in result["error"]


class TestDeviceLocation:
    """Tests for location capabilities."""

    @pytest.mark.asyncio
    async def test_get_location(self, db_session: Session):
        """Test getting device location."""
        from tools.device_tool import device_get_location
        from core.models import DeviceNode

        device = DeviceNode(workspace_id="default", user_id="test_user", 
            device_id="device_location_1",
            name="Location Device",
            node_type="mobile",
            status="online",
            platform="iOS"
        )
        db_session.add(device)
        db_session.commit()

        with patch('tools.device_tool.is_device_online', return_value=True):
            with patch('tools.device_tool.send_device_command') as mock_send:
                mock_send.return_value = {
                    "success": True,
                    "data": {
                        "latitude": 37.7749,
                        "longitude": -122.4194,
                        "altitude": 10.5,
                        "timestamp": "2024-01-01T00:00:00Z"
                    }
                }

                result = await device_get_location(
                    db=db_session,
                    user_id="test_list_user",
                    device_node_id="device_location_1",
                    accuracy="high"
                )

                assert result["success"] is True
                assert result["latitude"] == 37.7749
                assert result["longitude"] == -122.4194

    @pytest.mark.asyncio
    async def test_get_location_medium_accuracy(self, db_session: Session):
        """Test getting location with medium accuracy."""
        from tools.device_tool import device_get_location
        from core.models import DeviceNode

        device = DeviceNode(workspace_id="default", user_id="test_user", 
            device_id="device_location_2",
            name="Location Device 2",
            node_type="mobile",
            status="online",
            platform="Android"
        )
        db_session.add(device)
        db_session.commit()

        with patch('tools.device_tool.is_device_online', return_value=True):
            with patch('tools.device_tool.send_device_command') as mock_send:
                mock_send.return_value = {
                    "success": True,
                    "data": {
                        "latitude": 40.7128,
                        "longitude": -74.0060,
                        "timestamp": "2024-01-01T00:00:00Z"
                    }
                }

                result = await device_get_location(
                    db=db_session,
                    user_id="test_list_user",
                    device_node_id="device_location_2",
                    accuracy="medium"
                )

                assert result["success"] is True
                assert result["accuracy"] == "medium"


class TestDeviceNotifications:
    """Tests for notification capabilities."""

    @pytest.mark.asyncio
    async def test_send_notification(self, db_session: Session):
        """Test sending notification to device."""
        from tools.device_tool import device_send_notification
        from core.models import DeviceNode

        device = DeviceNode(workspace_id="default", user_id="test_user", 
            device_id="device_notif_1",
            name="Notification Device",
            node_type="mobile",
            status="online",
            platform="iOS"
        )
        db_session.add(device)
        db_session.commit()

        with patch('tools.device_tool.is_device_online', return_value=True):
            with patch('tools.device_tool.send_device_command') as mock_send:
                mock_send.return_value = {
                    "success": True
                }

                result = await device_send_notification(
                    db=db_session,
                    user_id="test_list_user",
                    device_node_id="device_notif_1",
                    title="Test Notification",
                    body="Test body content"
                )

                assert result["success"] is True
                assert result["title"] == "Test Notification"

    @pytest.mark.asyncio
    async def test_send_notification_with_options(self, db_session: Session):
        """Test sending notification with icon and sound."""
        from tools.device_tool import device_send_notification
        from core.models import DeviceNode

        device = DeviceNode(workspace_id="default", user_id="test_user", 
            device_id="device_notif_2",
            name="Notification Device 2",
            node_type="mobile",
            status="online",
            platform="Android"
        )
        db_session.add(device)
        db_session.commit()

        with patch('tools.device_tool.is_device_online', return_value=True):
            with patch('tools.device_tool.send_device_command') as mock_send:
                mock_send.return_value = {
                    "success": True
                }

                result = await device_send_notification(
                    db=db_session,
                    user_id="test_list_user",
                    device_node_id="device_notif_2",
                    title="Rich Notification",
                    body="With icon and sound",
                    icon="app_icon.png",
                    sound="default"
                )

                assert result["success"] is True


class TestDeviceScreenRecording:
    """Tests for screen recording capabilities."""

    @pytest.mark.asyncio
    async def test_start_screen_recording(self, db_session: Session):
        """Test starting screen recording."""
        from tools.device_tool import device_screen_record_start
        from core.models import DeviceNode

        device = DeviceNode(workspace_id="default", user_id="test_user", 
            device_id="device_screen_1",
            name="Screen Device",
            node_type="mobile",
            status="online",
            platform="iOS"
        )
        db_session.add(device)
        db_session.commit()

        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.send_device_command') as mock_send:
                mock_send.return_value = {
                    "success": True
                }

                result = await device_screen_record_start(
                    db=db_session,
                    user_id="test_list_user",
                    device_node_id="device_screen_1",
                    duration_seconds=60,
                    audio_enabled=False
                )

                assert result["success"] is True
                assert "session_id" in result

    @pytest.mark.asyncio
    async def test_stop_screen_recording(self, db_session: Session):
        """Test stopping screen recording."""
        from tools.device_tool import device_screen_record_stop
        from tools.device_tool import get_device_session_manager

        # Create active recording session
        manager = get_device_session_manager()
        session = manager.create_session(
            user_id="test_list_user",
            device_node_id="device_screen_2",
            session_type="screen_record"
        )

        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.send_device_command') as mock_send:
                mock_send.return_value = {
                    "success": True,
                    "file_path": "/tmp/recording.mp4",
                    "data": {"duration_seconds": 30}
                }

                result = await device_screen_record_stop(
                    db=db_session,
                    user_id="test_list_user",
                    session_id=session["session_id"]
                )

                assert result["success"] is True
                assert result["session_id"] == session["session_id"]


class TestDeviceCommandExecution:
    """Tests for command execution capabilities."""

    @pytest.mark.asyncio
    async def test_execute_command(self, db_session: Session):
        """Test executing shell command on device."""
        from tools.device_tool import device_execute_command
        from core.models import DeviceNode

        device = DeviceNode(workspace_id="default", user_id="test_user", 
            device_id="device_cmd_1",
            name="Command Device",
            node_type="mobile",
            status="online",
            platform="Linux"
        )
        db_session.add(device)
        db_session.commit()

        with patch('tools.device_tool.is_device_online', return_value=True):
            with patch('tools.device_tool.send_device_command') as mock_send:
                mock_send.return_value = {
                    "success": True,
                    "data": {
                        "exit_code": 0,
                        "stdout": "file1.txt\nfile2.txt\n",
                        "stderr": ""
                    }
                }

                result = await device_execute_command(
                    db=db_session,
                    user_id="test_list_user",
                    device_node_id="device_cmd_1",
                    command="ls",
                    timeout_seconds=30
                )

                assert result["success"] is True
                assert result["exit_code"] == 0
                assert "file1.txt" in result["stdout"]

    @pytest.mark.asyncio
    async def test_execute_command_not_whitelisted(self, db_session: Session):
        """Test command execution with non-whitelisted command."""
        from tools.device_tool import device_execute_command
        from core.models import DeviceNode

        device = DeviceNode(workspace_id="default", user_id="test_user", 
            device_id="device_cmd_2",
            name="Command Device 2",
            node_type="mobile",
            status="online",
            platform="Linux"
        )
        db_session.add(device)
        db_session.commit()

        result = await device_execute_command(
            db=db_session,
            user_id="test_list_user",
            device_node_id="device_cmd_2",
            command="rm -rf /"  # Not in whitelist
        )

        assert result["success"] is False
        assert "not in whitelist" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_command_timeout_exceeded(self, db_session: Session):
        """Test command execution with excessive timeout."""
        from tools.device_tool import device_execute_command
        from core.models import DeviceNode

        device = DeviceNode(workspace_id="default", user_id="test_user", 
            device_id="device_cmd_3",
            name="Command Device 3",
            node_type="mobile",
            status="online",
            platform="Linux"
        )
        db_session.add(device)
        db_session.commit()

        result = await device_execute_command(
            db=db_session,
            user_id="test_list_user",
            device_node_id="device_cmd_3",
            command="ls",
            timeout_seconds=400  # Exceeds 300s max
        )

        assert result["success"] is False
        assert "exceeds maximum" in result["error"]


class TestDeviceHelperFunctions:
    """Tests for device helper functions."""

    def test_get_device_info(self, db_session: Session):
        """Test getting device information."""
        from tools.device_tool import get_device_info
        from core.models import DeviceNode

        device = DeviceNode(workspace_id="default", user_id="test_user", 
            device_id="device_info_1",
            name="Info Device",
            node_type="mobile",
            status="online",
            platform="iOS",
            platform_version="15.0",
            architecture="arm64",
            capabilities=["camera", "location"],
            hardware_info={"model": "iPhone 13"}
        )
        db_session.add(device)
        db_session.commit()

        info = get_device_info(db_session, "device_info_1")

        assert info is not None
        assert info["device_id"] == "device_info_1"
        assert info["platform"] == "iOS"
        assert info["platform_version"] == "15.0"

    def test_get_device_info_not_found(self, db_session: Session):
        """Test getting info for non-existent device."""
        from tools.device_tool import get_device_info

        info = get_device_info(db_session, "nonexistent_device")
        assert info is None

    def test_list_devices(self, db_session: Session):
        """Test listing devices for user."""
        from tools.device_tool import list_devices
        from core.models import DeviceNode

        # Create test devices
        for i in range(3):
            device = DeviceNode(
                workspace_id="default",
                user_id="test_user",
                device_id=f"device_list_{i}",
                name=f"Device {i}",
                node_type="mobile",
                status="online",
                platform="iOS"
            )
            db_session.add(device)
        db_session.commit()

        devices = list_devices(db_session, user_id="test_user")

        assert len(devices) >= 3

    def test_list_devices_filtered_by_status(self, db_session: Session):
        """Test listing devices filtered by status."""
        from tools.device_tool import list_devices
        from core.models import DeviceNode

        # Create devices with different statuses
        online = DeviceNode(
            device_id="device_online",
            name="Online Device",
            node_type="mobile",
            status="online",
            platform="iOS",
            user_id="filter_user"
        )
        offline = DeviceNode(
            device_id="device_offline",
            name="Offline Device",
            node_type="mobile",
            status="offline",
            platform="Android",
            user_id="filter_user"
        )
        db_session.add_all([online, offline])
        db_session.commit()

        online_devices = list_devices(db_session, user_id="filter_user", status="online")

        assert all(d["status"] == "online" for d in online_devices)


class TestDeviceGenericExecution:
    """Tests for generic device command execution."""

    @pytest.mark.asyncio
    async def test_execute_camera_command(self, db_session: Session):
        """Test generic camera command execution."""
        from tools.device_tool import execute_device_command
        from core.models import DeviceNode

        device = DeviceNode(workspace_id="default", user_id="test_user", 
            device_id="device_generic_1",
            name="Generic Device",
            node_type="mobile",
            status="online",
            platform="iOS"
        )
        db_session.add(device)
        db_session.commit()

        with patch('tools.device_tool.is_device_online', return_value=True):
            with patch('tools.device_tool.send_device_command') as mock_send:
                mock_send.return_value = {
                    "success": True,
                    "file_path": "/tmp/generic_photo.jpg"
                }

                result = await execute_device_command(
                    db=db_session,
                    user_id="test_list_user",
                    agent_id=None,
                    device_id="device_generic_1",
                    command_type="camera",
                    parameters={"timeout": 10}
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_location_command(self, db_session: Session):
        """Test generic location command execution."""
        from tools.device_tool import execute_device_command
        from core.models import DeviceNode

        device = DeviceNode(workspace_id="default", user_id="test_user", 
            device_id="device_generic_2",
            name="Generic Device 2",
            node_type="mobile",
            status="online",
            platform="Android"
        )
        db_session.add(device)
        db_session.commit()

        with patch('tools.device_tool.is_device_online', return_value=True):
            with patch('tools.device_tool.send_device_command') as mock_send:
                mock_send.return_value = {
                    "success": True,
                    "data": {
                        "latitude": 51.5074,
                        "longitude": -0.1278
                    }
                }

                result = await execute_device_command(
                    db=db_session,
                    user_id="test_list_user",
                    agent_id=None,
                    device_id="device_generic_2",
                    command_type="location",
                    parameters={"high_accuracy": True}
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_notification_command(self, db_session: Session):
        """Test generic notification command execution."""
        from tools.device_tool import execute_device_command
        from core.models import DeviceNode

        device = DeviceNode(workspace_id="default", user_id="test_user", 
            device_id="device_generic_3",
            name="Generic Device 3",
            node_type="mobile",
            status="online",
            platform="iOS"
        )
        db_session.add(device)
        db_session.commit()

        with patch('tools.device_tool.is_device_online', return_value=True):
            with patch('tools.device_tool.send_device_command') as mock_send:
                mock_send.return_value = {
                    "success": True
                }

                result = await execute_device_command(
                    db=db_session,
                    user_id="test_list_user",
                    agent_id=None,
                    device_id="device_generic_3",
                    command_type="notification",
                    parameters={
                        "title": "Generic Notification",
                        "body": "From generic executor"
                    }
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_unknown_command_type(self, db_session: Session):
        """Test generic execution with unknown command type."""
        from tools.device_tool import execute_device_command

        result = await execute_device_command(
            db=db_session,
            user_id="test_list_user",
            agent_id=None,
            device_id="any_device",
            command_type="unknown_command",
            parameters={}
        )

        assert result["success"] is False
        assert "Unknown command type" in result["error"]
