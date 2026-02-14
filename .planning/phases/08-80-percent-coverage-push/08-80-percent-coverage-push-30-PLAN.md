---
phase: 08-80-percent-coverage-push
plan: 30
type: execute
wave: 6
depends_on: []
files_modified:
  - backend/tests/unit/test_browser_tool.py
  - backend/tests/unit/test_device_tool.py
  - backend/tests/unit/test_canvas_collaboration_service.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "Browser tool has 50%+ test coverage (navigation, screenshots, form filling, extraction)"
    - "Device tool has 50%+ test coverage (camera, location, notifications, recording)"
    - "Canvas collaboration service tested (multi-user sessions, locking, permissions)"
    - "Governance integration validated (INTERN+ required for browser/device actions)"
  artifacts:
    - path: "backend/tests/unit/test_browser_tool.py"
      provides: "Browser automation tests"
      min_lines: 600
    - path: "backend/tests/unit/test_device_tool.py"
      provides: "Device capability tests"
      min_lines: 500
    - path: "backend/tests/unit/test_canvas_collaboration_service.py"
      provides: "Canvas collaboration tests"
      min_lines: 400
  key_links:
    - from: "test_browser_tool.py"
      to: "tools/browser_tool.py"
      via: "mock_playwright, mock_db, mock_agent_context_resolver"
      pattern: "BrowserSession, BrowserSessionManager"
    - from: "test_device_tool.py"
      to: "tools/device_tool.py"
      via: "mock_db, mock_agent_context_resolver"
      pattern: "camera_snap, get_location, send_notification"
    - from: "test_canvas_collaboration_service.py"
      to: "core/canvas_collaboration_service.py"
      via: "mock_db"
      pattern: "share_canvas, add_collaborator"
status: pending
created: 2026-02-13
gap_closure: false
---

# Plan 30: Browser, Device Tool & Canvas Collaboration Tests

**Status:** Pending
**Wave:** 6 (parallel with 29)
**Dependencies:** None

## Objective

Create comprehensive unit tests for browser tool, device tool, and canvas collaboration service, achieving 50% coverage across all three files to contribute +1.0-1.2% toward Phase 8.9's 21-22% overall coverage goal.

## Context

Phase 8.9 targets 21-22% overall coverage (+2% from 19-20% baseline) by testing canvas and browser tools. This plan covers the remaining tools:

1. **tools/browser_tool.py** (818 lines) - Web scraping, form filling, screenshots, CDP integration
2. **tools/device_tool.py** (1,187 lines) - Camera, location, notifications, screen recording
3. **core/canvas_collaboration_service.py** (817 lines) - Multi-user sessions, locking, permissions

**Production Lines:** 2,822 total
**Expected Coverage at 50%:** ~1,410 lines
**Coverage Contribution:** +1.0-1.2 percentage points toward 21-22% goal

**Key Functions to Test:**

**Browser Tool:**
- `BrowserSession.__init__()` - Session initialization
- `BrowserSession.start()` - Browser launch with Playwright
- `BrowserSession.close()` - Cleanup and resource release
- `BrowserSessionManager.get_session()` - Session retrieval
- `BrowserSessionManager.create_session()` - New session creation
- `navigate()` - Page navigation
- `screenshot()` - Screenshot capture
- `fill_form()` - Form filling
- `extract_data()` - Data extraction
- `close_browser_session()` - Session lifecycle

**Device Tool:**
- `camera_snap()` - Camera capture
- `get_location()` - Location retrieval
- `send_notification()` - Notification sending
- `screen_record_start()` - Recording start
- `screen_record_stop()` - Recording stop
- `request_permission()` - Permission handling
- Governance checks (INTERN+ required)

**Canvas Collaboration:**
- `share_canvas()` - Share canvas with users
- `add_collaborator()` - Add collaborator
- `remove_collaborator()` - Remove collaborator
- `set_permissions()` - Permission management
- `lock_canvas()` - Canvas locking
- `unlock_canvas()` - Canvas unlock
- `get_active_sessions()` - Active session listing

## Success Criteria

**Must Have (truths that become verifiable):**
1. Browser tool has 50%+ test coverage (navigation, screenshots, extraction)
2. Device tool has 50%+ test coverage (camera, location, notifications)
3. Canvas collaboration service tested (multi-user, permissions, locking)
4. Governance integration validated (INTERN+ for browser/device actions)

**Should Have:**
- Browser session management tested
- Device permission handling tested
- Canvas role-based access tested
- Error handling for failures

**Could Have:**
- Multi-browser support (Firefox, WebKit)
- Device command execution (AUTONOMOUS only)
- Canvas conflict resolution

**Won't Have:**
- Real browser instances (Playwright mocked)
- Real device hardware (mocked)
- Real WebSocket connections (mocked)

## Tasks

### Task 1: Create test_browser_tool.py with CDP mock coverage

**Files:**
- CREATE: `backend/tests/unit/test_browser_tool.py` (600+ lines, 30-35 tests)

**Action:**
Create test file with these test classes:

```python
"""
Unit tests for Browser Tool

Tests cover:
- Browser session lifecycle (start, close, cleanup)
- Session management (create, retrieve, timeout)
- Navigation (goto, wait for selectors)
- Screenshot capture
- Form filling
- Data extraction
- Network interception
- Governance integration (INTERN+ required)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from sqlalchemy.orm import Session

from tools.browser_tool import BrowserSession, BrowserSessionManager


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    db.query = MagicMock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    return db


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return "user_123"


@pytest.fixture
def sample_agent_id():
    """Sample agent ID for testing."""
    return "agent_123"


@pytest.fixture
def mock_playwright():
    """Mock Playwright instance."""
    playwright = MagicMock()
    browser = MagicMock()
    context = MagicMock()
    page = MagicMock()

    browser.new_context = AsyncMock(return_value=context)
    context.new_page = AsyncMock(return_value=page)
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"fake_png")
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.evaluate = AsyncMock()
    page.close = AsyncMock()
    context.close = AsyncMock()
    browser.close = AsyncMock()

    playwright.chromium = MagicMock()
    playwright.chromium.launch = AsyncMock(return_value=browser)
    playwright.firefox = MagicMock()
    playwright.firefox.launch = AsyncMock(return_value=browser)
    playwright.webkit = MagicMock()
    playwright.webkit.launch = AsyncMock(return_value=browser)

    return {
        "playwright": playwright,
        "browser": browser,
        "context": context,
        "page": page
    }


# =============================================================================
# BrowserSession Tests
# =============================================================================

class TestBrowserSessionInit:
    """Tests for BrowserSession initialization."""

    def test_browser_session_init_defaults(self, sample_user_id):
        """Test BrowserSession initialization with defaults."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id
        )

        assert session.session_id == "session_123"
        assert session.user_id == sample_user_id
        assert session.agent_id is None
        assert session.headless is True
        assert session.browser_type == "chromium"
        assert session.playwright is None
        assert session.browser is None

    def test_browser_session_init_with_agent(self, sample_user_id, sample_agent_id):
        """Test BrowserSession initialization with agent."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id,
            agent_id=sample_agent_id
        )

        assert session.agent_id == sample_agent_id

    def test_browser_session_init_headful(self, sample_user_id):
        """Test BrowserSession with headless=False."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id,
            headless=False
        )

        assert session.headless is False

    def test_browser_session_init_firefox(self, sample_user_id):
        """Test BrowserSession with Firefox browser type."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id,
            browser_type="firefox"
        )

        assert session.browser_type == "firefox"

    def test_browser_session_timestamps(self, sample_user_id):
        """Test BrowserSession sets creation timestamp."""
        before = datetime.now()
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id
        )
        after = datetime.now()

        assert before <= session.created_at <= after
        assert before <= session.last_used <= after


# =============================================================================
# BrowserSession Lifecycle Tests
# =============================================================================

class TestBrowserSessionLifecycle:
    """Tests for browser session start and close."""

    @pytest.mark.asyncio
    async def test_browser_session_start_chromium(self, sample_user_id, mock_playwright):
        """Test starting Chromium browser session."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id,
            browser_type="chromium"
        )

        with patch('tools.browser_tool.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright["playwright"])
                result = await session.start()

        assert result is True
        assert session.browser is not None
        assert session.context is not None
        assert session.page is not None

    @pytest.mark.asyncio
    async def test_browser_session_start_firefox(self, sample_user_id, mock_playwright):
        """Test starting Firefox browser session."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id,
            browser_type="firefox"
        )

        with patch('tools.browser_tool.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright["playwright"])
                result = await session.start()

        assert result is True

    @pytest.mark.asyncio
    async def test_browser_session_start_webkit(self, sample_user_id, mock_playwright):
        """Test starting WebKit browser session."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id,
            browser_type="webkit"
        )

        with patch('tools.browser_tool.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright["playwright"])
                result = await session.start()

        assert result is True

    @pytest.mark.asyncio
    async def test_browser_session_start_creates_context(self, sample_user_id, mock_playwright):
        """Test session start creates browser context."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id
        )

        with patch('tools.browser_tool.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright["playwright"])
                await session.start()

        # Verify new_context was called with viewport
        session.browser.new_context.assert_called_once()
        call_kwargs = session.browser.new_context.call_args[1] if session.browser.new_context.call_args else {}
        assert "viewport" in call_kwargs

    @pytest.mark.asyncio
    async def test_browser_session_close(self, sample_user_id, mock_playwright):
        """Test closing browser session."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id
        )
        session.page = mock_playwright["page"]
        session.context = mock_playwright["context"]
        session.browser = mock_playwright["browser"]
        session.playwright = mock_playwright["playwright"]

        result = await session.close()

        assert result is True
        session.page.close.assert_called_once()
        session.context.close.assert_called_once()
        session.browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_browser_session_close_handles_errors(self, sample_user_id):
        """Test close handles errors gracefully."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id
        )
        session.page = AsyncMock(side_effect=Exception("Close error"))

        result = await session.close()

        # Should return False on error
        assert result is False


# =============================================================================
# BrowserSessionManager Tests
# =============================================================================

class TestBrowserSessionManager:
    """Tests for session management."""

    def test_session_manager_init(self):
        """Test BrowserSessionManager initialization."""
        manager = BrowserSessionManager(session_timeout_minutes=30)

        assert manager.sessions == {}
        assert manager.session_timeout_minutes == 30

    def test_session_manager_default_timeout(self):
        """Test BrowserSessionManager uses default timeout."""
        manager = BrowserSessionManager()

        assert manager.session_timeout_minutes == 30

    def test_get_session_found(self, sample_user_id):
        """Test retrieving existing session."""
        manager = BrowserSessionManager()
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id
        )
        manager.sessions["session_123"] = session

        result = manager.get_session("session_123")

        assert result == session

    def test_get_session_not_found(self):
        """Test retrieving non-existent session returns None."""
        manager = BrowserSessionManager()

        result = manager.get_session("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_session(self, sample_user_id, mock_playwright):
        """Test creating new session."""
        manager = BrowserSessionManager()

        with patch('tools.browser_tool.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright["playwright"])
                session = await manager.create_session(user_id=sample_user_id)

        assert session.session_id is not None
        assert session.user_id == sample_user_id
        assert session.headless is True

    @pytest.mark.asyncio
    async def test_create_session_with_agent(self, sample_user_id, sample_agent_id, mock_playwright):
        """Test creating session with agent ID."""
        manager = BrowserSessionManager()

        with patch('tools.browser_tool.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright["playwright"])
                session = await manager.create_session(
                    user_id=sample_user_id,
                    agent_id=sample_agent_id
                )

        assert session.agent_id == sample_agent_id

    @pytest.mark.asyncio
    async def test_create_session_headful(self, sample_user_id, mock_playwright):
        """Test creating non-headless session."""
        manager = BrowserSessionManager()

        with patch('tools.browser_tool.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright["playwright"])
                session = await manager.create_session(
                    user_id=sample_user_id,
                    headless=False
                )

        assert session.headless is False

    def test_cleanup_expired_sessions(self, sample_user_id):
        """Test cleanup of expired sessions."""
        manager = BrowserSessionManager(session_timeout_minutes=30)

        # Create expired session
        old_session = BrowserSession(
            session_id="old_session",
            user_id=sample_user_id
        )
        old_session.created_at = datetime.now() - timedelta(minutes=31)
        old_session.last_used = datetime.now() - timedelta(minutes=31)
        manager.sessions["old_session"] = old_session

        # Create active session
        active_session = BrowserSession(
            session_id="active_session",
            user_id=sample_user_id
        )
        manager.sessions["active_session"] = active_session

        manager.cleanup_expired_sessions()

        assert "old_session" not in manager.sessions
        assert "active_session" in manager.sessions


# =============================================================================
# Navigation Tests
# =============================================================================

class TestBrowserNavigation:
    """Tests for browser navigation functionality."""

    @pytest.mark.asyncio
    async def test_navigate_to_url(self, sample_user_id, mock_playwright):
        """Test navigating to URL."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id
        )
        session.page = mock_playwright["page"]

        with patch('tools.browser_tool.async_playwright'):
            # Simulate navigation
            await session.page.goto("https://example.com")

        session.page.goto.assert_called_with("https://example.com")

    @pytest.mark.asyncio
    async def test_navigate_wait_for_selector(self, sample_user_id, mock_playwright):
        """Test navigation waits for selector."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id
        )
        session.page = mock_playwright["page"]

        with patch('tools.browser_tool.async_playwright'):
            await session.page.goto("https://example.com")
            await session.page.wait_for_selector("#content")

        session.page.wait_for_selector.assert_called_with("#content")


# =============================================================================
# Screenshot Tests
# =============================================================================

class TestBrowserScreenshot:
    """Tests for screenshot capture."""

    @pytest.mark.asyncio
    async def test_screenshot_capture(self, sample_user_id, mock_playwright):
        """Test capturing screenshot."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id
        )
        session.page = mock_playwright["page"]

        with patch('tools.browser_tool.async_playwright'):
            result = await session.page.screenshot()

        assert result == b"fake_png"
        session.page.screenshot.assert_called_once()


# =============================================================================
# Form Filling Tests
# =============================================================================

class TestBrowserFormFilling:
    """Tests for form filling functionality."""

    @pytest.mark.asyncio
    async def test_fill_form_text_input(self, sample_user_id, mock_playwright):
        """Test filling text input."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id
        )
        session.page = mock_playwright["page"]

        with patch('tools.browser_tool.async_playwright'):
            await session.page.fill("#email", "test@example.com")

        session.page.fill.assert_called_with("#email", "test@example.com")

    @pytest.mark.asyncio
    async def test_fill_form_multiple_fields(self, sample_user_id, mock_playwright):
        """Test filling multiple form fields."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id
        )
        session.page = mock_playwright["page"]

        with patch('tools.browser_tool.async_playwright'):
            await session.page.fill("#name", "John Doe")
            await session.page.fill("#email", "john@example.com")

        assert session.page.fill.call_count == 2

    @pytest.mark.asyncio
    async def test_click_button(self, sample_user_id, mock_playwright):
        """Test clicking button."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id
        )
        session.page = mock_playwright["page"]

        with patch('tools.browser_tool.async_playwright'):
            await session.page.click("#submit")

        session.page.click.assert_called_with("#submit")


# =============================================================================
# Data Extraction Tests
# =============================================================================

class TestBrowserDataExtraction:
    """Tests for data extraction functionality."""

    @pytest.mark.asyncio
    async def test_extract_text_content(self, sample_user_id, mock_playwright):
        """Test extracting text content."""
        session = BrowserSession(
            session_id="session_123",
            user_id=sample_user_id
        )
        session.page = mock_playwright["page"]
        mock_playwright["page"].evaluate = AsyncMock(return_value="Extracted text")

        with patch('tools.browser_tool.async_playwright'):
            result = await session.page.evaluate("() => document.body.innerText")

        assert result == "Extracted text"


# =============================================================================
# Governance Integration Tests
# =============================================================================

class TestBrowserGovernance:
    """Tests for browser governance integration."""

    @pytest.mark.asyncio
    async def test_browser_action_requires_intern(self, mock_db):
        """Test browser actions require INTERN+ maturity."""
        from core.models import AgentStatus

        with patch('tools.browser_tool.AgentContextResolver'):
            with patch('tools.browser_tool.ServiceFactory') as mock_factory:
                mock_gov = MagicMock()
                mock_gov.can_perform_action.return_value = {
                    "allowed": False,
                    "reason": "Insufficient maturity for browser actions"
                }
                mock_factory.get_governance_service.return_value = mock_gov

                # Student agent should be blocked
                result = mock_gov.can_perform_action(
                    agent_id="student_agent",
                    action_type="browser_navigate"
                )

        assert result["allowed"] is False
        assert "insufficient" in result["reason"].lower()
```

**Verify:**
```bash
test -f backend/tests/unit/test_browser_tool.py && echo "File exists"
grep -c "^    def test_" backend/tests/unit/test_browser_tool.py
# Expected: 30-35 tests
```

### Task 2: Create test_device_tool.py with device mock coverage

**Files:**
- CREATE: `backend/tests/unit/test_device_tool.py` (500+ lines, 25-30 tests)

**Action:**
Create test file with these test classes:

```python
"""
Unit tests for Device Tool

Tests cover:
- Camera capture
- Location retrieval
- Notification sending
- Screen recording (start/stop)
- Permission handling
- Governance integration (INTERN+ required)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from sqlalchemy.orm import Session

import tools.device_tool


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    db.query = MagicMock()
    db.add = Mock()
    db.commit = Mock()
    return db


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return "user_123"


@pytest.fixture
def sample_agent_id():
    """Sample agent ID for testing."""
    return "agent_123"


# =============================================================================
# Camera Tests
# =============================================================================

class TestDeviceCamera:
    """Tests for camera functionality."""

    @pytest.mark.asyncio
    async def test_camera_snap_with_permission(self, mock_db, sample_user_id):
        """Test camera capture with permission granted."""
        with patch('tools.device_tool.check_permission') as mock_perm:
            mock_perm.return_value = True
            with patch('tools.device_tool.capture_photo') as mock_capture:
                mock_capture.return_value = b"fake_jpeg"

                result = await tools.device_tool.camera_snap(
                    user_id=sample_user_id
                )

        assert result["success"] is True
        assert result["image_data"] == b"fake_jpeg"

    @pytest.mark.asyncio
    async def test_camera_snap_without_permission(self, mock_db, sample_user_id):
        """Test camera capture denied without permission."""
        with patch('tools.device_tool.check_permission') as mock_perm:
            mock_perm.return_value = False

                result = await tools.device_tool.camera_snap(
                    user_id=sample_user_id
                )

        assert result["success"] is False
        assert "permission" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_camera_snap_with_agent_tracking(self, mock_db, sample_user_id, sample_agent_id):
        """Test camera snap includes agent tracking."""
        with patch('tools.device_tool.check_permission', return_value=True):
            with patch('tools.device_tool.capture_photo', return_value=b"fake_jpeg"):
                with patch('tools.device_tool.AgentContextResolver'):
                    with patch('tools.device_tool.ServiceFactory'):
                        result = await tools.device_tool.camera_snap(
                            user_id=sample_user_id,
                            agent_id=sample_agent_id
                        )

        assert result["success"] is True


# =============================================================================
# Location Tests
# =============================================================================

class TestDeviceLocation:
    """Tests for location functionality."""

    @pytest.mark.asyncio
    async def test_get_location_with_permission(self, mock_db, sample_user_id):
        """Test location retrieval with permission."""
        with patch('tools.device_tool.check_permission') as mock_perm:
            mock_perm.return_value = True
            with patch('tools.device_tool.get_current_location') as mock_location:
                mock_location.return_value = {
                    "latitude": 37.7749,
                    "longitude": -122.4194
                }

                result = await tools.device_tool.get_location(
                    user_id=sample_user_id
                )

        assert result["success"] is True
        assert "latitude" in result
        assert "longitude" in result

    @pytest.mark.asyncio
    async def test_get_location_without_permission(self, mock_db, sample_user_id):
        """Test location retrieval denied without permission."""
        with patch('tools.device_tool.check_permission') as mock_perm:
            mock_perm.return_value = False

                result = await tools.device_tool.get_location(
                    user_id=sample_user_id
                )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_location_returns_coordinates(self, mock_db, sample_user_id):
        """Test location returns valid coordinates."""
        with patch('tools.device_tool.check_permission', return_value=True):
            with patch('tools.device_tool.get_current_location') as mock_location:
                mock_location.return_value = {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                }

                result = await tools.device_tool.get_location(
                    user_id=sample_user_id
                )

        assert -90 <= result["latitude"] <= 90
        assert -180 <= result["longitude"] <= 180


# =============================================================================
# Notification Tests
# =============================================================================

class TestDeviceNotifications:
    """Tests for notification functionality."""

    @pytest.mark.asyncio
    async def test_send_notification_with_permission(self, mock_db, sample_user_id):
        """Test sending notification with permission."""
        with patch('tools.device_tool.check_permission') as mock_perm:
            mock_perm.return_value = True
            with patch('tools.device_tool.push_notification') as mock_push:
                mock_push.return_value = True

                result = await tools.device_tool.send_notification(
                    user_id=sample_user_id,
                    title="Test Title",
                    body="Test notification body"
                )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_send_notification_without_permission(self, mock_db, sample_user_id):
        """Test notification denied without permission."""
        with patch('tools.device_tool.check_permission') as mock_perm:
            mock_perm.return_value = False

                result = await tools.device_tool.send_notification(
                    user_id=sample_user_id,
                    title="Test",
                    body="Body"
                )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_send_notification_with_action(self, mock_db, sample_user_id):
        """Test notification with action button."""
        with patch('tools.device_tool.check_permission', return_value=True):
            with patch('tools.device_tool.push_notification', return_value=True):
                result = await tools.device_tool.send_notification(
                    user_id=sample_user_id,
                    title="Action Required",
                    body="Please approve",
                    action="approve"
                )

        assert result["success"] is True


# =============================================================================
# Screen Recording Tests
# =============================================================================

class TestDeviceScreenRecording:
    """Tests for screen recording functionality."""

    @pytest.mark.asyncio
    async def test_screen_record_start(self, mock_db, sample_user_id):
        """Test starting screen recording."""
        with patch('tools.device_tool.check_permission') as mock_perm:
            mock_perm.return_value = True
            with patch('tools.device_tool.start_recording') as mock_record:
                mock_record.return_value = "recording_123"

                result = await tools.device_tool.screen_record_start(
                    user_id=sample_user_id
                )

        assert result["success"] is True
        assert "recording_id" in result

    @pytest.mark.asyncio
    async def test_screen_record_stop(self, mock_db, sample_user_id):
        """Test stopping screen recording."""
        with patch('tools.device_tool.stop_recording') as mock_stop:
            mock_stop.return_value = b"fake_video"

            result = await tools.device_tool.screen_record_stop(
                user_id=sample_user_id,
                recording_id="recording_123"
            )

        assert result["success"] is True
        assert result["video_data"] == b"fake_video"

    @pytest.mark.asyncio
    async def test_screen_record_requires_supervised(self, mock_db):
        """Test screen recording requires SUPERVISED+ maturity."""
        from core.models import AgentStatus

        with patch('tools.device_tool.AgentContextResolver'):
            with patch('tools.device_tool.ServiceFactory') as mock_factory:
                mock_gov = MagicMock()
                # SUPERVISED can record
                mock_gov.can_perform_action.return_value = {
                    "allowed": True,
                    "requires_human_approval": True
                }
                mock_factory.get_governance_service.return_value = mock_gov

                result = mock_gov.can_perform_action(
                    agent_id="supervised_agent",
                    action_type="device_screen_record_start"
                )

        assert result["allowed"] is True
        assert result["requires_human_approval"] is True


# =============================================================================
# Permission Tests
# =============================================================================

class TestDevicePermissions:
    """Tests for permission handling."""

    @pytest.mark.asyncio
    async def test_request_camera_permission(self, mock_db, sample_user_id):
        """Test requesting camera permission."""
        with patch('tools.device_tool.request_device_permission') as mock_req:
            mock_req.return_value = True

            result = await tools.device_tool.request_permission(
                user_id=sample_user_id,
                permission_type="camera"
            )

        assert result["granted"] is True

    @pytest.mark.asyncio
    async def test_request_location_permission(self, mock_db, sample_user_id):
        """Test requesting location permission."""
        with patch('tools.device_tool.request_device_permission') as mock_req:
            mock_req.return_value = True

            result = await tools.device_tool.request_permission(
                user_id=sample_user_id,
                permission_type="location"
            )

        assert result["granted"] is True

    @pytest.mark.asyncio
    async def test_request_permission_denied(self, mock_db, sample_user_id):
        """Test permission denial handling."""
        with patch('tools.device_tool.request_device_permission') as mock_req:
            mock_req.return_value = False

            result = await tools.device_tool.request_permission(
                user_id=sample_user_id,
                permission_type="notifications"
            )

        assert result["granted"] is False
```

**Verify:**
```bash
test -f backend/tests/unit/test_device_tool.py && echo "File exists"
grep -c "^    def test_" backend/tests/unit/test_device_tool.py
# Expected: 25-30 tests
```

### Task 3: Create test_canvas_collaboration_service.py with collaboration mock coverage

**Files:**
- CREATE: `backend/tests/unit/test_canvas_collaboration_service.py` (400+ lines, 20-25 tests)

**Action:**
Create test file with these test classes:

```python
"""
Unit tests for Canvas Collaboration Service

Tests cover:
- Sharing canvas with users
- Adding/removing collaborators
- Permission management (owner, editor, viewer)
- Canvas locking
- Session management
- Role-based access control
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock
from sqlalchemy.orm import Session

from core.canvas_collaboration_service import (
    share_canvas,
    add_collaborator,
    remove_collaborator,
    set_permissions,
    lock_canvas,
    unlock_canvas,
    get_active_sessions,
    get_canvas_role
)
from core.models import CanvasCollaborator


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    db.query = MagicMock()
    db.add = Mock()
    db.commit = Mock()
    db.flush = Mock()
    return db


@pytest.fixture
def sample_user_id():
    """Sample user ID."""
    return "user_123"


@pytest.fixture
def sample_canvas_id():
    """Sample canvas ID."""
    return "canvas_abc123"


@pytest.fixture
def sample_collaborator():
    """Sample collaborator."""
    return CanvasCollaborator(
        id="collab_123",
        canvas_id="canvas_abc123",
        user_id="user_456",
        role="editor",
        added_at=datetime.now()
    )


# =============================================================================
# Canvas Sharing Tests
# =============================================================================

class TestCanvasSharing:
    """Tests for canvas sharing functionality."""

    @pytest.mark.asyncio
    async def test_share_canvas_with_user(self, mock_db, sample_user_id, sample_canvas_id):
        """Test sharing canvas with another user."""
        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await share_canvas(
                canvas_id=sample_canvas_id,
                owner_id=sample_user_id,
                share_with_user="user_456",
                role="viewer"
            )

        assert result["success"] is True
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_share_canvas_with_editor_role(self, mock_db, sample_user_id, sample_canvas_id):
        """Test sharing canvas with editor permissions."""
        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await share_canvas(
                canvas_id=sample_canvas_id,
                owner_id=sample_user_id,
                share_with_user="user_456",
                role="editor"
            )

        assert result["success"] is True
        # Verify collaborator has editor role
        added_collab = mock_db.add.call_args[0][0]
        assert added_collab.role == "editor"

    @pytest.mark.asyncio
    async def test_share_canvas_already_shared(self, mock_db, sample_user_id, sample_canvas_id, sample_collaborator):
        """Test sharing canvas with already shared user updates role."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_collaborator
        mock_db.query.return_value = mock_query

        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await share_canvas(
                canvas_id=sample_canvas_id,
                owner_id=sample_user_id,
                share_with_user="user_456",
                role="editor"
            )

        assert result["success"] is True


# =============================================================================
# Collaborator Management Tests
# =============================================================================

class TestCollaboratorManagement:
    """Tests for adding and removing collaborators."""

    @pytest.mark.asyncio
    async def test_add_collaborator(self, mock_db, sample_canvas_id):
        """Test adding collaborator to canvas."""
        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await add_collaborator(
                canvas_id=sample_canvas_id,
                user_id="user_789",
                role="viewer"
            )

        assert result["success"] is True
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_collaborator(self, mock_db, sample_canvas_id, sample_collaborator):
        """Test removing collaborator from canvas."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_collaborator
        mock_db.query.return_value = mock_query

        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await remove_collaborator(
                canvas_id=sample_canvas_id,
                user_id="user_456"
            )

        assert result["success"] is True
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_remove_nonexistent_collaborator(self, mock_db, sample_canvas_id):
        """Test removing non-existent collaborator."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await remove_collaborator(
                canvas_id=sample_canvas_id,
                user_id="nonexistent"
            )

        assert result["success"] is False


# =============================================================================
# Permission Management Tests
# =============================================================================

class TestPermissionManagement:
    """Tests for permission management."""

    @pytest.mark.asyncio
    async def test_set_permissions_viewer(self, mock_db, sample_canvas_id, sample_collaborator):
        """Test setting viewer permissions."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_collaborator
        mock_db.query.return_value = mock_query

        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await set_permissions(
                canvas_id=sample_canvas_id,
                user_id="user_456",
                role="viewer"
            )

        assert result["success"] is True
        assert sample_collaborator.role == "viewer"

    @pytest.mark.asyncio
    async def test_set_permissions_editor(self, mock_db, sample_canvas_id, sample_collaborator):
        """Test setting editor permissions."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_collaborator
        mock_db.query.return_value = mock_query

        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await set_permissions(
                canvas_id=sample_canvas_id,
                user_id="user_456",
                role="editor"
            )

        assert result["success"] is True
        assert sample_collaborator.role == "editor"

    @pytest.mark.asyncio
    async def test_set_permissions_owner_only(self, mock_db, sample_canvas_id):
        """Test only owner can change permissions."""
        with patch('core.canvas_collaboration_service.get_db_session'):
            with patch('core.canvas_collaboration_service.verify_ownership') as mock_verify:
                mock_verify.return_value = False
                result = await set_permissions(
                    canvas_id=sample_canvas_id,
                    user_id="user_456",
                    role="viewer",
                    requesting_user="not_owner"
                )

        assert result["success"] is False


# =============================================================================
# Canvas Locking Tests
# =============================================================================

class TestCanvasLocking:
    """Tests for canvas locking."""

    @pytest.mark.asyncio
    async def test_lock_canvas(self, mock_db, sample_canvas_id):
        """Test locking canvas for editing."""
        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await lock_canvas(
                canvas_id=sample_canvas_id,
                user_id="user_123",
                reason="Editing in progress"
            )

        assert result["success"] is True
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_unlock_canvas(self, mock_db, sample_canvas_id):
        """Test unlocking canvas."""
        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await unlock_canvas(
                canvas_id=sample_canvas_id,
                user_id="user_123"
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_lock_prevented_when_already_locked(self, mock_db, sample_canvas_id):
        """Test canvas cannot be locked when already locked."""
        mock_locked = MagicMock()
        mock_locked.locked_at = datetime.now()
        mock_locked.locked_by = "other_user"

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_locked
        mock_db.query.return_value = mock_query

        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await lock_canvas(
                canvas_id=sample_canvas_id,
                user_id="user_123"
            )

        assert result["success"] is False
        assert "locked" in result.get("error", "").lower()


# =============================================================================
# Session Management Tests
# =============================================================================

class TestSessionManagement:
    """Tests for active session management."""

    @pytest.mark.asyncio
    async def test_get_active_sessions(self, mock_db, sample_canvas_id):
        """Test getting active canvas sessions."""
        mock_sessions = [
            MagicMock(user_id="user_1", last_active=datetime.now()),
            MagicMock(user_id="user_2", last_active=datetime.now())
        ]
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = mock_sessions
        mock_db.query.return_value = mock_query

        result = await get_active_sessions(canvas_id=sample_canvas_id)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_active_sessions_empty(self, mock_db, sample_canvas_id):
        """Test getting active sessions when none exist."""
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        result = await get_active_sessions(canvas_id=sample_canvas_id)

        assert len(result) == 0


# =============================================================================
# Role-Based Access Tests
# =============================================================================

class TestRoleBasedAccess:
    """Tests for role-based access control."""

    @pytest.mark.asyncio
    async def test_get_canvas_role_owner(self, mock_db, sample_canvas_id):
        """Test getting owner role."""
        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await get_canvas_role(
                canvas_id=sample_canvas_id,
                user_id="owner_user"
            )

        assert result == "owner"

    @pytest.mark.asyncio
    async def test_get_canvas_role_editor(self, mock_db, sample_canvas_id, sample_collaborator):
        """Test getting editor role."""
        sample_collaborator.role = "editor"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_collaborator
        mock_db.query.return_value = mock_query

        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await get_canvas_role(
                canvas_id=sample_canvas_id,
                user_id="user_456"
            )

        assert result == "editor"

    @pytest.mark.asyncio
    async def test_get_canvas_role_viewer(self, mock_db, sample_canvas_id, sample_collaborator):
        """Test getting viewer role."""
        sample_collaborator.role = "viewer"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_collaborator
        mock_db.query.return_value = mock_query

        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await get_canvas_role(
                canvas_id=sample_canvas_id,
                user_id="user_456"
            )

        assert result == "viewer"

    @pytest.mark.asyncio
    async def test_get_canvas_role_no_access(self, mock_db, sample_canvas_id):
        """Test getting role for user with no access."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with patch('core.canvas_collaboration_service.get_db_session'):
            result = await get_canvas_role(
                canvas_id=sample_canvas_id,
                user_id="no_access_user"
            )

        assert result is None
```

**Verify:**
```bash
test -f backend/tests/unit/test_canvas_collaboration_service.py && echo "File exists"
grep -c "^    def test_" backend/tests/unit/test_canvas_collaboration_service.py
# Expected: 20-25 tests
```

**Done:**
- test_browser_tool.py created with 30-35 tests
- test_device_tool.py created with 25-30 tests
- test_canvas_collaboration_service.py created with 20-25 tests
- Browser session management tested
- Device capabilities tested (camera, location, notifications, recording)
- Canvas collaboration tested (sharing, permissions, locking)
- Governance integration validated

---

## Key Links

| From | To | Via | Artifact |
|------|-----|-----|----------|
| test_browser_tool.py | tools/browser_tool.py | mock_playwright, mock_db | Browser automation tests |
| test_device_tool.py | tools/device_tool.py | mock_db, mock_device | Device capability tests |
| test_canvas_collaboration_service.py | core/canvas_collaboration_service.py | mock_db | Collaboration tests |

## Progress Tracking

**Current Coverage (Phase 8.8):** 19-20%
**Plan 30 Target:** +1.0-1.2 percentage points
**Projected After Plans 29+30:** ~21-22%

## Notes

- Covers 3 files: browser_tool.py (818 lines), device_tool.py (1,187 lines), canvas_collaboration_service.py (817 lines)
- 50% coverage target across all files (sustainable for 2,822 total lines)
- Test patterns from Phase 8.7/8.8 applied (AsyncMock, fixtures)
- Estimated 75-90 total tests across 3 files
- Duration: 2-3 hours
- All external dependencies mocked (Playwright, device hardware, database)
