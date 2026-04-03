#!/usr/bin/env python3
"""
Standalone Tests for Browser Tool

Coverage Target: 80%+
Priority: P1 (Browser Automation)
"""
import sys
import os
sys.path.insert(0, '.')
os.environ['ENVIRONMENT'] = 'development'

from tools.browser_tool import (
    BrowserSession,
    BrowserSessionManager,
    get_browser_manager,
    BROWSER_HEADLESS,
)
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
import asyncio


def test_browser_headless_config():
    """Test browser headless configuration"""
    print("Testing browser headless config...")
    # BROWSER_HEADLESS should be a boolean
    assert isinstance(BROWSER_HEADLESS, bool)
    print("✓ Browser headless config tests passed")


def test_browser_session_initialization():
    """Test BrowserSession initialization"""
    print("Testing BrowserSession initialization...")
    session = BrowserSession(
        session_id="test-session-001",
        user_id="user-001",
        agent_id="agent-001",
        headless=True,
        browser_type="chromium"
    )
    
    assert session.session_id == "test-session-001"
    assert session.user_id == "user-001"
    assert session.agent_id == "agent-001"
    assert session.headless is True
    assert session.browser_type == "chromium"
    assert session.playwright is None
    assert session.browser is None
    assert session.context is None
    assert session.page is None
    assert isinstance(session.created_at, datetime)
    assert isinstance(session.last_used, datetime)
    
    print("✓ BrowserSession initialization tests passed")


def test_browser_session_different_types():
    """Test BrowserSession with different browser types"""
    print("Testing BrowserSession different types...")
    
    # Firefox
    session_ff = BrowserSession(
        session_id="test-ff",
        user_id="user-001",
        browser_type="firefox"
    )
    assert session_ff.browser_type == "firefox"
    
    # WebKit
    session_wk = BrowserSession(
        session_id="test-wk",
        user_id="user-001",
        browser_type="webkit"
    )
    assert session_wk.browser_type == "webkit"
    
    # Chromium (default)
    session_cr = BrowserSession(
        session_id="test-cr",
        user_id="user-001"
    )
    assert session_cr.browser_type == "chromium"
    
    print("✓ BrowserSession different types tests passed")


def test_session_manager_initialization():
    """Test BrowserSessionManager initialization"""
    print("Testing BrowserSessionManager initialization...")
    manager = BrowserSessionManager(session_timeout_minutes=30)
    
    assert manager.session_timeout_minutes == 30
    assert hasattr(manager, 'sessions')
    assert isinstance(manager.sessions, dict)
    
    print("✓ BrowserSessionManager initialization tests passed")


def test_session_manager_custom_timeout():
    """Test BrowserSessionManager with custom timeout"""
    print("Testing BrowserSessionManager custom timeout...")
    manager = BrowserSessionManager(session_timeout_minutes=60)
    assert manager.session_timeout_minutes == 60
    
    manager2 = BrowserSessionManager(session_timeout_minutes=15)
    assert manager2.session_timeout_minutes == 15
    
    print("✓ BrowserSessionManager custom timeout tests passed")


def test_get_session_empty():
    """Test getting session from empty manager"""
    print("Testing get session (empty)...")
    manager = BrowserSessionManager()
    
    session = manager.get_session("nonexistent")
    assert session is None
    
    print("✓ Get session (empty) tests passed")


def test_get_session_existing():
    """Test getting existing session"""
    print("Testing get session (existing)...")
    manager = BrowserSessionManager()
    
    # Create a mock session
    mock_session = MagicMock()
    manager.sessions["test-session"] = mock_session
    
    session = manager.get_session("test-session")
    assert session == mock_session
    
    print("✓ Get session (existing) tests passed")


async def test_create_session():
    """Test creating a new browser session"""
    print("Testing create session...")
    manager = BrowserSessionManager()
    
    # Mock BrowserSession to avoid actual browser launch
    with patch('tools.browser_tool.BrowserSession') as MockSession:
        mock_session = AsyncMock()
        mock_session.start = AsyncMock(return_value=True)
        MockSession.return_value = mock_session
        
        session = await manager.create_session(
            user_id="user-001",
            agent_id="agent-001",
            headless=True
        )
        
        assert session is not None
        # Session should be stored with its session_id as key
        assert len(manager.sessions) == 1
        mock_session.start.assert_called_once()
    
    print("✓ Create session tests passed")


async def test_close_session():
    """Test closing a browser session"""
    print("Testing close session...")
    manager = BrowserSessionManager()
    
    # Add a mock session
    mock_session = AsyncMock()
    mock_session.close = AsyncMock()
    manager.sessions["test-session"] = mock_session
    
    # Close the session
    result = await manager.close_session("test-session")
    
    assert result is True
    assert "test-session" not in manager.sessions
    mock_session.close.assert_called_once()
    
    print("✓ Close session tests passed")


async def test_close_nonexistent_session():
    """Test closing nonexistent session"""
    print("Testing close nonexistent session...")
    manager = BrowserSessionManager()
    
    result = await manager.close_session("nonexistent")
    
    assert result is False
    
    print("✓ Close nonexistent session tests passed")


async def test_cleanup_expired_sessions():
    """Test cleaning up expired sessions"""
    print("Testing cleanup expired sessions...")
    manager = BrowserSessionManager(session_timeout_minutes=30)
    
    # Create mock sessions with different ages
    now = datetime.now()
    
    # Recent session (should not be cleaned)
    recent_session = MagicMock()
    recent_session.last_used = now - timedelta(minutes=10)
    recent_session.close = AsyncMock()
    manager.sessions["recent"] = recent_session
    
    # Expired session (should be cleaned)
    expired_session = MagicMock()
    expired_session.last_used = now - timedelta(minutes=60)
    expired_session.close = AsyncMock()
    manager.sessions["expired"] = expired_session
    
    # Run cleanup
    await manager.cleanup_expired_sessions()
    
    # Recent session should remain
    assert "recent" in manager.sessions
    # Expired session should be removed
    assert "expired" not in manager.sessions
    expired_session.close.assert_called_once()
    
    print("✓ Cleanup expired sessions tests passed")


async def test_cleanup_no_expired_sessions():
    """Test cleanup when no sessions are expired"""
    print("Testing cleanup (no expired)...")
    manager = BrowserSessionManager(session_timeout_minutes=30)
    
    # Create recent sessions
    now = datetime.now()
    
    for i in range(3):
        session = MagicMock()
        session.last_used = now - timedelta(minutes=5)
        session.close = AsyncMock()
        manager.sessions[f"session-{i}"] = session
    
    # Run cleanup
    await manager.cleanup_expired_sessions()
    
    # All sessions should remain
    assert len(manager.sessions) == 3
    
    print("✓ Cleanup (no expired) tests passed")


def test_get_browser_manager_singleton():
    """Test get_browser_manager returns singleton"""
    print("Testing get_browser_manager singleton...")
    
    manager1 = get_browser_manager()
    manager2 = get_browser_manager()
    
    # Should return same instance
    assert manager1 is manager2
    
    print("✓ get_browser_manager singleton tests passed")


def test_browser_session_with_optional_agent():
    """Test BrowserSession without agent_id"""
    print("Testing BrowserSession without agent_id...")
    
    session = BrowserSession(
        session_id="test-no-agent",
        user_id="user-001"
    )
    
    assert session.agent_id is None
    assert session.session_id == "test-no-agent"
    
    print("✓ BrowserSession without agent_id tests passed")


async def test_create_session_without_agent():
    """Test creating session without agent_id"""
    print("Testing create session without agent...")
    manager = BrowserSessionManager()
    
    with patch('tools.browser_tool.BrowserSession') as MockSession:
        mock_session = AsyncMock()
        mock_session.start = AsyncMock(return_value=True)
        MockSession.return_value = mock_session
        
        session = await manager.create_session(
            user_id="user-001"
            # No agent_id
        )
        
        assert session is not None
        assert len(manager.sessions) == 1
    
    print("✓ Create session without agent tests passed")


def test_session_manager_sessions_dict():
    """Test that sessions dict works correctly"""
    print("Testing sessions dict...")
    manager = BrowserSessionManager()
    
    # Add multiple sessions
    for i in range(5):
        mock_session = MagicMock()
        manager.sessions[f"session-{i}"] = mock_session
    
    assert len(manager.sessions) == 5
    assert f"session-3" in manager.sessions
    assert f"session-99" not in manager.sessions
    
    # Remove one
    del manager.sessions["session-2"]
    assert len(manager.sessions) == 4
    
    print("✓ Sessions dict tests passed")


async def test_session_lifecycle():
    """Test complete session lifecycle"""
    print("Testing session lifecycle...")
    manager = BrowserSessionManager()
    
    # Create with mocked uuid
    with patch('tools.browser_tool.uuid.uuid4') as mock_uuid:
        mock_uuid.return_value = "fixed-test-uuid"
        
        mock_session = MagicMock()
        mock_session.session_id = "fixed-test-uuid"
        mock_session.start = AsyncMock(return_value=True)
        mock_session.close = AsyncMock()
        
        with patch('tools.browser_tool.BrowserSession', return_value=mock_session):
            session = await manager.create_session(user_id="user-001")
            assert session is not None
            assert session.session_id == "fixed-test-uuid"
            
            # Get - should get the same session back
            retrieved = manager.get_session("fixed-test-uuid")
            assert retrieved is not None
            assert retrieved.session_id == "fixed-test-uuid"
            
            # Close
            result = await manager.close_session("fixed-test-uuid")
            assert result is True
            assert "fixed-test-uuid" not in manager.sessions
    
    print("✓ Session lifecycle tests passed")


async def test_session_timeout_threshold():
    """Test session timeout threshold edge cases"""
    print("Testing session timeout threshold...")
    manager = BrowserSessionManager(session_timeout_minutes=30)
    
    now = datetime.now()
    
    # Session well within threshold (should NOT be cleaned)
    within_threshold = MagicMock()
    within_threshold.last_used = now - timedelta(minutes=15)
    within_threshold.close = AsyncMock()
    manager.sessions["within-threshold"] = within_threshold
    
    # Session just over threshold (should be cleaned)
    over_threshold = MagicMock()
    over_threshold.last_used = now - timedelta(minutes=31)
    over_threshold.close = AsyncMock()
    manager.sessions["over-threshold"] = over_threshold
    
    # Run cleanup (await directly, don't use asyncio.run)
    await manager.cleanup_expired_sessions()
    
    # Within threshold should remain
    assert "within-threshold" in manager.sessions
    # Over threshold should be removed
    assert "over-threshold" not in manager.sessions
    
    print("✓ Session timeout threshold tests passed")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Running Browser Tool Tests (Standalone)")
    print("=" * 60)
    
    try:
        # Sync tests
        test_browser_headless_config()
        test_browser_session_initialization()
        test_browser_session_different_types()
        test_session_manager_initialization()
        test_session_manager_custom_timeout()
        test_get_session_empty()
        test_get_session_existing()
        test_get_browser_manager_singleton()
        test_browser_session_with_optional_agent()
        test_session_manager_sessions_dict()
        
        # Async tests
        await test_create_session()
        await test_close_session()
        await test_close_nonexistent_session()
        await test_cleanup_expired_sessions()
        await test_cleanup_no_expired_sessions()
        await test_create_session_without_agent()
        await test_session_lifecycle()
        await test_session_timeout_threshold()
        
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
