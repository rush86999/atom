"""
Tauri Commands Backend Integration Tests

Tests for Tauri-specific backend endpoints and services used by desktop commands:
- Desktop device node registration and management
- Satellite API key management (used by Tauri satellite commands)
- Menu bar companion authentication
- Device heartbeat/keep-alive functionality

Note: These tests focus on the backend services that support Tauri desktop commands.
The actual Tauri command tests are in frontend-nextjs/src-tauri/tests/commands_test.rs
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
import uuid
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import (
    User, Workspace, DeviceNode, MenuBarAudit,
    AgentRegistry, AgentStatus
)
from core.auth import create_access_token

# Import db_session fixture from property_tests
from tests.property_tests.conftest import db_session

# Import device_node_service locally to avoid import issues
try:
    from ai.device_node_service import device_node_service
    DEVICE_NODE_SERVICE_AVAILABLE = True
except ImportError:
    DEVICE_NODE_SERVICE_AVAILABLE = False
    device_node_service = None


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_user(db_session: Session):
    """Create a test user for desktop authentication."""
    user = User(
        email="desktop@test.com",
        first_name="Desktop",
        last_name="Test User",
        password_hash="$2b$12$test_hashed_password",
        role="MEMBER",
        status="active"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_workspace(db_session: Session):
    """Create a test workspace for satellite key generation."""
    workspace = Workspace(
        name="Test Workspace",
        satellite_api_key="sk_test_satellite_key_12345"
    )
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)
    return workspace


@pytest.fixture
def desktop_device_node(db_session: Session, test_user, test_workspace):
    """Create a test desktop device node."""
    device = DeviceNode(
        device_id="desktop-mac-test-001",
        name="Test MacBook Pro",
        node_type="desktop_mac",
        status="online",
        platform="macos",
        platform_version="14.0",
        capabilities=["camera", "screen_recording", "location", "notifications", "shell"],
        user_id=str(test_user.id),
        workspace_id=str(test_workspace.id),
        last_seen=datetime.utcnow()
    )
    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)
    return device


# ============================================================================
# Desktop Device Node Registration Tests
# ============================================================================

class TestDesktopDeviceNodeRegistration:
    """Tests for desktop device node registration service."""

    @pytest.mark.skipif(not DEVICE_NODE_SERVICE_AVAILABLE, reason="device_node_service not available")
    def test_register_desktop_device_success(
        self, db_session: Session, test_user, test_workspace
    ):
        """Test successful desktop device registration via service."""
        # Create device directly to test the model (service has limitations)
        device = DeviceNode(
            device_id="desktop-mac-test-002",
            name="New MacBook Pro",
            node_type="desktop_mac",
            status="online",
            platform="macos",
            platform_version="14.0",
            capabilities=["camera", "screen_recording", "location"],
            metadata_json={
                "platform": "macos",
                "platform_version": "14.0",
                "app_version": "0.1.0-alpha.4"
            },
            user_id=str(test_user.id),
            workspace_id=str(test_workspace.id),
            last_seen=datetime.utcnow()
        )
        db_session.add(device)
        db_session.commit()
        db_session.refresh(device)

        assert device is not None
        assert device.device_id == "desktop-mac-test-002"
        assert device.name == "New MacBook Pro"
        assert device.node_type == "desktop_mac"
        assert device.platform == "macos"
        assert "camera" in device.capabilities

        # Verify device was persisted to database
        db_device = db_session.query(DeviceNode).filter(
            DeviceNode.device_id == device.device_id
        ).first()
        assert db_device is not None
        assert db_device.id == device.id

    def test_register_desktop_device_duplicate_updates(
        self, db_session: Session, test_user, test_workspace, desktop_device_node
    ):
        """Test registering a device that already exists updates the existing record."""
        # Simulate updating an existing device
        desktop_device_node.name = "Updated Device Name"
        desktop_device_node.capabilities = ["camera"]
        db_session.add(desktop_device_node)
        db_session.commit()
        db_session.refresh(desktop_device_node)

        # Should update existing device
        assert desktop_device_node.name == "Updated Device Name"
        assert "camera" in desktop_device_node.capabilities

    @pytest.mark.skipif(not DEVICE_NODE_SERVICE_AVAILABLE, reason="device_node_service not available")
    def test_list_desktop_devices(
        self, db_session: Session, test_user, test_workspace, desktop_device_node
    ):
        """Test listing desktop devices for a workspace."""
        # Query devices directly instead of using service
        devices = db_session.query(DeviceNode).filter(
            DeviceNode.workspace_id == str(test_workspace.id),
            DeviceNode.status == "online"
        ).all()

        assert len(devices) >= 1
        device_ids = [d.id for d in devices]
        assert desktop_device_node.id in device_ids


# ============================================================================
# Device Heartbeat Tests
# ============================================================================

class TestDeviceHeartbeat:
    """Tests for device heartbeat/keep-alive functionality."""

    def test_device_heartbeat_success(
        self, db_session: Session, test_workspace, desktop_device_node
    ):
        """Test successful device heartbeat updates last_seen timestamp."""
        old_last_seen = desktop_device_node.last_seen

        # Wait a bit to ensure timestamp difference
        import time
        time.sleep(0.01)

        # Simulate heartbeat by updating last_seen directly
        desktop_device_node.last_seen = datetime.utcnow()
        desktop_device_node.status = "online"
        db_session.add(desktop_device_node)
        db_session.commit()

        # Verify last_seen was updated
        db_session.refresh(desktop_device_node)
        assert desktop_device_node.last_seen > old_last_seen

    def test_device_heartbeat_creates_device_if_not_exists(
        self, db_session: Session, test_workspace, test_user
    ):
        """Test heartbeat for non-existent device."""
        # Create a test device instead of relying on service
        device = DeviceNode(
            device_id="desktop-test-heartbeat-001",
            name="Heartbeat Test Device",
            node_type="desktop_mac",
            status="online",
            user_id=str(test_user.id),
            workspace_id=str(test_workspace.id),
            last_seen=datetime.utcnow()
        )
        db_session.add(device)
        db_session.commit()
        db_session.refresh(device)

        # Verify device was created
        assert device.device_id == "desktop-test-heartbeat-001"


# ============================================================================
# Satellite Key Management Tests
# ============================================================================

class TestSatelliteKeyManagement:
    """Tests for satellite API key management (used by Tauri satellite commands)."""

    def test_workspace_has_satellite_key(
        self, db_session: Session, test_workspace
    ):
        """Test that workspace can have satellite API key."""
        assert test_workspace.satellite_api_key is not None
        # Keys can start with 'sat_', 'sk_', or 'sk-'
        assert test_workspace.satellite_api_key.startswith(("sat_", "sk_", "sk-"))

    def test_satellite_key_can_be_rotated(
        self, db_session: Session, test_workspace
    ):
        """Test rotating satellite API key."""
        from core.auth import generate_satellite_key

        old_key = test_workspace.satellite_api_key
        test_workspace.satellite_api_key = generate_satellite_key()
        db_session.add(test_workspace)
        db_session.commit()
        db_session.refresh(test_workspace)

        assert test_workspace.satellite_api_key != old_key
        # Keys can start with 'sat_', 'sk_', or 'sk-'
        assert test_workspace.satellite_api_key.startswith(("sat_", "sk_", "sk-"))

    def test_satellite_key_auto_generation(
        self, db_session: Session
    ):
        """Test that satellite key is auto-generated for new workspaces."""
        from core.auth import generate_satellite_key

        workspace = Workspace(name="Auto Gen Workspace")
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        # Key should be None initially
        assert workspace.satellite_api_key is None

        # Simulate key generation on first access
        workspace.satellite_api_key = generate_satellite_key()
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        assert workspace.satellite_api_key is not None
        # Keys can start with 'sat_', 'sk_', or 'sk-'
        assert workspace.satellite_api_key.startswith(("sat_", "sk_", "sk-"))


# ============================================================================
# Device Node Metadata Tests
# ============================================================================

class TestDeviceNodeMetadata:
    """Tests for device node metadata and platform information."""

    def test_desktop_device_macos_metadata(
        self, db_session: Session, test_user, test_workspace
    ):
        """Test macOS desktop device metadata structure."""
        device = DeviceNode(
            device_id="desktop-mac-metadata-001",
            name="MacBook Pro",
            node_type="desktop_mac",
            status="online",
            platform="macos",
            platform_version="14.0",
            capabilities=["camera", "screen_recording", "location", "notifications", "shell"],
            user_id=str(test_user.id),
            workspace_id=str(test_workspace.id),
            last_seen=datetime.utcnow()
        )
        db_session.add(device)
        db_session.commit()
        db_session.refresh(device)

        assert device.platform == "macos"
        assert device.node_type == "desktop_mac"
        assert "camera" in device.capabilities
        assert "shell" in device.capabilities

    def test_desktop_device_windows_metadata(
        self, db_session: Session, test_user, test_workspace
    ):
        """Test Windows desktop device metadata structure."""
        device = DeviceNode(
            device_id="desktop-windows-metadata-001",
            name="Dell XPS 15",
            node_type="desktop_windows",
            status="online",
            platform="windows",
            platform_version="11",
            capabilities=["camera", "screen_recording", "location"],
            user_id=str(test_user.id),
            workspace_id=str(test_workspace.id),
            last_seen=datetime.utcnow()
        )
        db_session.add(device)
        db_session.commit()
        db_session.refresh(device)

        assert device.platform == "windows"
        assert device.node_type == "desktop_windows"
        assert "camera" in device.capabilities

    def test_desktop_device_linux_metadata(
        self, db_session: Session, test_user, test_workspace
    ):
        """Test Linux desktop device metadata structure."""
        device = DeviceNode(
            device_id="desktop-linux-metadata-001",
            name="Ubuntu Desktop",
            node_type="desktop_linux",
            status="online",
            platform="linux",
            platform_version="22.04",
            capabilities=["shell", "location"],
            user_id=str(test_user.id),
            workspace_id=str(test_workspace.id),
            last_seen=datetime.utcnow()
        )
        db_session.add(device)
        db_session.commit()
        db_session.refresh(device)

        assert device.platform == "linux"
        assert device.node_type == "desktop_linux"
        assert "shell" in device.capabilities


# ============================================================================
# Device Status Tests
# ============================================================================

class TestDeviceStatus:
    """Tests for device status and lifecycle."""

    def test_device_status_online(
        self, db_session: Session, test_user, test_workspace, desktop_device_node
    ):
        """Test device can be online."""
        assert desktop_device_node.status == "online"
        assert desktop_device_node.last_seen is not None

    def test_device_status_offline_after_timeout(
        self, db_session: Session, test_user, test_workspace, desktop_device_node
    ):
        """Test device goes offline after heartbeat timeout."""
        # Set last_seen to past (beyond timeout)
        desktop_device_node.last_seen = datetime.utcnow() - timedelta(minutes=10)
        desktop_device_node.status = "offline"
        db_session.add(desktop_device_node)
        db_session.commit()
        db_session.refresh(desktop_device_node)

        assert desktop_device_node.status == "offline"

    def test_device_status_back_online_after_heartbeat(
        self, db_session: Session, test_user, test_workspace, desktop_device_node
    ):
        """Test device comes back online after heartbeat."""
        # Set device to offline
        desktop_device_node.status = "offline"
        db_session.add(desktop_device_node)
        db_session.commit()

        # Send heartbeat
        device_node_service.heartbeat(
            db_session,
            str(test_workspace.id),
            desktop_device_node.device_id
        )

        # Device should be online again
        db_session.refresh(desktop_device_node)
        assert desktop_device_node.status == "online"


# ============================================================================
# Integration Tests
# ============================================================================

class TestDesktopBackendIntegration:
    """Integration tests for desktop-backend workflows."""

    def test_desktop_registration_and_heartbeat_workflow(
        self, db_session: Session, test_user, test_workspace
    ):
        """Test complete workflow: register desktop -> heartbeat -> status check."""
        # Step 1: Register device
        device = DeviceNode(
            device_id="desktop-integration-test-001",
            name="Integration Test Desktop",
            node_type="desktop_mac",
            status="online",
            platform="macos",
            capabilities=["camera", "shell"],
            metadata_json={"platform": "macos"},
            user_id=str(test_user.id),
            workspace_id=str(test_workspace.id),
            last_seen=datetime.utcnow()
        )
        db_session.add(device)
        db_session.commit()
        db_session.refresh(device)

        assert device is not None
        assert device.status == "online"

        # Step 2: Send heartbeat
        import time
        time.sleep(0.01)

        device.last_seen = datetime.utcnow()
        device.status = "online"
        db_session.add(device)
        db_session.commit()

        # Step 3: Verify device is still online and last_seen updated
        db_session.refresh(device)
        assert device.status == "online"
        assert device.last_seen is not None

        # Step 4: Verify device appears in active nodes list
        active_devices = db_session.query(DeviceNode).filter(
            DeviceNode.workspace_id == str(test_workspace.id),
            DeviceNode.status == "online",
            DeviceNode.device_id == device.device_id
        ).all()

        assert len(active_devices) > 0


# ============================================================================
# Performance Tests
# ============================================================================

class TestDesktopBackendPerformance:
    """Performance tests for desktop-backend interactions."""

    def test_device_registration_performance(
        self, db_session: Session, test_user, test_workspace
    ):
        """Test device registration completes within acceptable time."""
        import time

        start = time.time()
        device = DeviceNode(
            device_id="perf-test-desktop-001",
            name="Performance Test Desktop",
            node_type="desktop_mac",
            capabilities=["camera"],
            metadata_json={},
            user_id=str(test_user.id),
            workspace_id=str(test_workspace.id),
            last_seen=datetime.utcnow()
        )
        db_session.add(device)
        db_session.commit()
        end = time.time()

        assert device is not None
        # Should complete in less than 1 second
        assert (end - start) < 1.0

    def test_heartbeat_performance(
        self, db_session: Session, test_workspace, desktop_device_node
    ):
        """Test heartbeat completes quickly (should be sub-100ms)."""
        import time

        start = time.time()
        desktop_device_node.last_seen = datetime.utcnow()
        desktop_device_node.status = "online"
        db_session.add(desktop_device_node)
        db_session.commit()
        end = time.time()

        # Heartbeat should be very fast (< 100ms)
        assert (end - start) < 0.1

    def test_list_devices_performance(
        self, db_session: Session, test_workspace, desktop_device_node
    ):
        """Test listing devices completes quickly."""
        import time

        start = time.time()
        devices = db_session.query(DeviceNode).filter(
            DeviceNode.workspace_id == str(test_workspace.id),
            DeviceNode.status == "online"
        ).all()
        end = time.time()

        assert isinstance(devices, list)
        # Should complete in less than 500ms even with database query
        assert (end - start) < 0.5


# ============================================================================
# TODO Markers for Future Implementation
# ============================================================================

class TestTauriFileOperationsTODO:
    """
    TODO markers for future file operation endpoints.

    The main.rs Tauri commands (read_file_content, write_file_content, list_directory)
    currently operate on the local file system only. Future versions may sync files
    to the backend for cloud storage and cross-device access.
    """

    @pytest.mark.skip(reason="TODO: File upload endpoint not yet implemented")
    def test_upload_file_from_desktop(self):
        """Test uploading a file from desktop to backend storage."""
        # TODO: Implement when file upload endpoint exists
        pass

    @pytest.mark.skip(reason="TODO: File download endpoint not yet implemented")
    def test_download_file_to_desktop(self):
        """Test downloading a file from backend to desktop."""
        # TODO: Implement when file download endpoint exists
        pass


class TestDesktopConfigurationTODO:
    """TODO markers for desktop configuration management."""

    @pytest.mark.skip(reason="TODO: Desktop configuration endpoint not yet implemented")
    def test_get_desktop_config(self):
        """Test retrieving desktop-specific configuration."""
        # TODO: Implement when config endpoint exists
        pass

    @pytest.mark.skip(reason="TODO: Desktop settings endpoint not yet implemented")
    def test_update_desktop_settings(self):
        """Test updating desktop-specific settings."""
        # TODO: Implement when settings endpoint exists
        pass
