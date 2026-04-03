#!/usr/bin/env python3
"""
Standalone Tests for Device Tool

Coverage Target: 80%+
Priority: P1 (Device Automation)
"""
import sys
import os
sys.path.insert(0, '.')
os.environ['ENVIRONMENT'] = 'development'

from tools.device_tool import (
    DeviceSessionManager,
    get_device_session_manager,
    DEVICE_COMMAND_WHITELIST,
    DEVICE_SHELL_READ_COMMANDS,
    DEVICE_SHELL_MONITOR_COMMANDS,
    DEVICE_SCREEN_RECORD_MAX_DURATION,
)
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
import asyncio


def test_device_command_whitelist():
    """Test device command whitelist configuration"""
    print("Testing device command whitelist...")
    assert isinstance(DEVICE_COMMAND_WHITELIST, list)
    assert len(DEVICE_COMMAND_WHITELIST) > 0
    assert "ls" in DEVICE_COMMAND_WHITELIST
    assert "pwd" in DEVICE_COMMAND_WHITELIST
    print("✓ Device command whitelist tests passed")


def test_device_shell_commands():
    """Test device shell command configurations"""
    print("Testing device shell commands...")
    assert isinstance(DEVICE_SHELL_READ_COMMANDS, list)
    assert isinstance(DEVICE_SHELL_MONITOR_COMMANDS, list)
    assert "cat" in DEVICE_SHELL_READ_COMMANDS
    assert "ps" in DEVICE_SHELL_MONITOR_COMMANDS
    print("✓ Device shell commands tests passed")


def test_screen_record_max_duration():
    """Test screen record max duration configuration"""
    print("Testing screen record max duration...")
    assert isinstance(DEVICE_SCREEN_RECORD_MAX_DURATION, int)
    assert DEVICE_SCREEN_RECORD_MAX_DURATION > 0
    print("✓ Screen record max duration tests passed")


def test_session_manager_initialization():
    """Test DeviceSessionManager initialization"""
    print("Testing DeviceSessionManager initialization...")
    manager = DeviceSessionManager(session_timeout_minutes=60)
    
    assert manager.session_timeout_minutes == 60
    assert hasattr(manager, 'sessions')
    assert isinstance(manager.sessions, dict)
    assert len(manager.sessions) == 0
    
    print("✓ DeviceSessionManager initialization tests passed")


def test_session_manager_custom_timeout():
    """Test DeviceSessionManager with custom timeout"""
    print("Testing DeviceSessionManager custom timeout...")
    manager = DeviceSessionManager(session_timeout_minutes=30)
    assert manager.session_timeout_minutes == 30
    
    manager2 = DeviceSessionManager(session_timeout_minutes=120)
    assert manager2.session_timeout_minutes == 120
    
    print("✓ DeviceSessionManager custom timeout tests passed")


def test_get_session_empty():
    """Test getting session from empty manager"""
    print("Testing get session (empty)...")
    manager = DeviceSessionManager()
    
    session = manager.get_session("nonexistent")
    assert session is None
    
    print("✓ Get session (empty) tests passed")


def test_get_session_existing():
    """Test getting existing session"""
    print("Testing get session (existing)...")
    manager = DeviceSessionManager()
    
    # Create a mock session
    mock_session = {"session_id": "test-session", "user_id": "user-001"}
    manager.sessions["test-session"] = mock_session
    
    session = manager.get_session("test-session")
    assert session == mock_session
    assert session["user_id"] == "user-001"
    
    print("✓ Get session (existing) tests passed")


def test_create_session():
    """Test creating a new device session"""
    print("Testing create session...")
    manager = DeviceSessionManager()
    
    session = manager.create_session(
        user_id="user-001",
        device_node_id="device-001",
        session_type="camera"
    )
    
    assert session is not None
    assert "session_id" in session
    assert session["user_id"] == "user-001"
    assert session["device_node_id"] == "device-001"
    assert session["session_type"] == "camera"
    assert "created_at" in session
    assert isinstance(session["created_at"], datetime)
    
    # Session should be stored
    assert session["session_id"] in manager.sessions
    
    print("✓ Create session tests passed")


def test_create_session_with_agent():
    """Test creating session with agent_id"""
    print("Testing create session with agent...")
    manager = DeviceSessionManager()
    
    session = manager.create_session(
        user_id="user-001",
        device_node_id="device-001",
        session_type="screen_record",
        agent_id="agent-001"
    )
    
    assert session is not None
    assert session["agent_id"] == "agent-001"
    
    print("✓ Create session with agent tests passed")


def test_create_session_with_configuration():
    """Test creating session with configuration"""
    print("Testing create session with configuration...")
    manager = DeviceSessionManager()
    
    config = {"quality": "high", "duration": 300}
    session = manager.create_session(
        user_id="user-001",
        device_node_id="device-001",
        session_type="camera",
        configuration=config
    )
    
    assert session is not None
    assert session["configuration"] == config
    assert session["configuration"]["quality"] == "high"
    
    print("✓ Create session with configuration tests passed")


def test_close_session():
    """Test closing a device session"""
    print("Testing close session...")
    manager = DeviceSessionManager()
    
    # Create a session
    session = manager.create_session(
        user_id="user-001",
        device_node_id="device-001",
        session_type="camera"
    )
    session_id = session["session_id"]
    
    # Close the session
    result = manager.close_session(session_id)
    
    assert result is True
    assert session_id not in manager.sessions
    
    print("✓ Close session tests passed")


def test_close_nonexistent_session():
    """Test closing nonexistent session"""
    print("Testing close nonexistent session...")
    manager = DeviceSessionManager()
    
    result = manager.close_session("nonexistent")
    
    assert result is False
    
    print("✓ Close nonexistent session tests passed")


def test_cleanup_expired_sessions():
    """Test cleaning up expired sessions"""
    print("Testing cleanup expired sessions...")
    manager = DeviceSessionManager(session_timeout_minutes=30)
    
    now = datetime.now()
    
    # Recent session (should not be cleaned)
    recent_session = {
        "session_id": "recent",
        "created_at": now - timedelta(minutes=40),
        "last_used": now - timedelta(minutes=10)
    }
    manager.sessions["recent"] = recent_session
    
    # Expired session (should be cleaned)
    expired_session = {
        "session_id": "expired",
        "created_at": now - timedelta(minutes=90),
        "last_used": now - timedelta(minutes=60)
    }
    manager.sessions["expired"] = expired_session
    
    # Run cleanup
    manager.cleanup_expired_sessions()
    
    # Recent session should remain
    assert "recent" in manager.sessions
    # Expired session should be removed
    assert "expired" not in manager.sessions
    
    print("✓ Cleanup expired sessions tests passed")


def test_cleanup_no_expired_sessions():
    """Test cleanup when no sessions are expired"""
    print("Testing cleanup (no expired)...")
    manager = DeviceSessionManager(session_timeout_minutes=30)
    
    now = datetime.now()
    
    # Create recent sessions
    for i in range(3):
        session = {
            "session_id": f"session-{i}",
            "created_at": now - timedelta(minutes=35),
            "last_used": now - timedelta(minutes=5)
        }
        manager.sessions[f"session-{i}"] = session
    
    # Run cleanup
    manager.cleanup_expired_sessions()
    
    # All sessions should remain
    assert len(manager.sessions) == 3
    
    print("✓ Cleanup (no expired) tests passed")


def test_get_device_session_manager_singleton():
    """Test get_device_session_manager returns singleton"""
    print("Testing get_device_session_manager singleton...")
    
    manager1 = get_device_session_manager()
    manager2 = get_device_session_manager()
    
    # Should return same instance
    assert manager1 is manager2
    
    print("✓ get_device_session_manager singleton tests passed")


def test_create_multiple_sessions():
    """Test creating multiple sessions"""
    print("Testing create multiple sessions...")
    manager = DeviceSessionManager()
    
    sessions = []
    for i in range(5):
        session = manager.create_session(
            user_id=f"user-{i}",
            device_node_id=f"device-{i}",
            session_type="camera"
        )
        sessions.append(session)
    
    assert len(manager.sessions) == 5
    
    # All session IDs should be unique
    session_ids = [s["session_id"] for s in sessions]
    assert len(set(session_ids)) == 5
    
    print("✓ Create multiple sessions tests passed")


def test_session_types():
    """Test different session types"""
    print("Testing different session types...")
    manager = DeviceSessionManager()
    
    types = ["camera", "screen_record", "location", "notification", "command"]
    
    for session_type in types:
        session = manager.create_session(
            user_id="user-001",
            device_node_id="device-001",
            session_type=session_type
        )
        assert session["session_type"] == session_type
    
    assert len(manager.sessions) == len(types)
    
    print("✓ Different session types tests passed")


def test_session_data_integrity():
    """Test session data integrity"""
    print("Testing session data integrity...")
    manager = DeviceSessionManager()
    
    session = manager.create_session(
        user_id="user-001",
        device_node_id="device-001",
        session_type="camera",
        agent_id="agent-001",
        configuration={"test": "value"}
    )
    
    # Verify all fields
    assert session["user_id"] == "user-001"
    assert session["device_node_id"] == "device-001"
    assert session["session_type"] == "camera"
    assert session["agent_id"] == "agent-001"
    assert session["configuration"]["test"] == "value"
    assert "session_id" in session
    assert "created_at" in session
    assert "last_used" in session
    
    # Verify stored session matches
    stored = manager.get_session(session["session_id"])
    assert stored["user_id"] == session["user_id"]
    assert stored["configuration"] == session["configuration"]
    
    print("✓ Session data integrity tests passed")


def test_session_timeout_threshold():
    """Test session timeout threshold edge cases"""
    print("Testing session timeout threshold...")
    manager = DeviceSessionManager(session_timeout_minutes=30)
    
    now = datetime.now()
    
    # Session well within threshold (should NOT be cleaned)
    within_threshold = {
        "session_id": "within-threshold",
        "created_at": now - timedelta(minutes=45),
        "last_used": now - timedelta(minutes=15)
    }
    manager.sessions["within-threshold"] = within_threshold
    
    # Session just over threshold (should be cleaned)
    over_threshold = {
        "session_id": "over-threshold",
        "created_at": now - timedelta(minutes=90),
        "last_used": now - timedelta(minutes=31)
    }
    manager.sessions["over-threshold"] = over_threshold
    
    # Run cleanup
    manager.cleanup_expired_sessions()
    
    # Within threshold should remain
    assert "within-threshold" in manager.sessions
    # Over threshold should be removed
    assert "over-threshold" not in manager.sessions
    
    print("✓ Session timeout threshold tests passed")


def test_session_lifecycle():
    """Test complete session lifecycle"""
    print("Testing session lifecycle...")
    manager = DeviceSessionManager()
    
    # Create
    session = manager.create_session(
        user_id="user-001",
        device_node_id="device-001",
        session_type="camera"
    )
    session_id = session["session_id"]
    assert session is not None
    
    # Get
    retrieved = manager.get_session(session_id)
    assert retrieved is not None
    assert retrieved["session_id"] == session_id
    
    # Update (simulate usage)
    retrieved["last_used"] = datetime.now()
    
    # Close
    result = manager.close_session(session_id)
    assert result is True
    assert session_id not in manager.sessions
    
    print("✓ Session lifecycle tests passed")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Running Device Tool Tests (Standalone)")
    print("=" * 60)
    
    try:
        # All sync tests
        test_device_command_whitelist()
        test_device_shell_commands()
        test_screen_record_max_duration()
        test_session_manager_initialization()
        test_session_manager_custom_timeout()
        test_get_session_empty()
        test_get_session_existing()
        test_create_session()
        test_create_session_with_agent()
        test_create_session_with_configuration()
        test_close_session()
        test_close_nonexistent_session()
        test_cleanup_expired_sessions()
        test_cleanup_no_expired_sessions()
        test_get_device_session_manager_singleton()
        test_create_multiple_sessions()
        test_session_types()
        test_session_data_integrity()
        test_session_timeout_threshold()
        test_session_lifecycle()
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
