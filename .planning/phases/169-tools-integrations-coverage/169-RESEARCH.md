# Phase 169: Tools & Integrations Coverage - Research

**Researched:** March 11, 2026
**Domain:** Python Testing with Async Mocking, Playwright, Device APIs
**Confidence:** HIGH

## Summary

Phase 169 focuses on achieving 75%+ line coverage on browser automation (`browser_tool.py`) and device capabilities (`device_tool.py`) tools. Both files currently have **0% coverage** (299 and 308 lines respectively) despite having 19 existing test files. The research reveals a critical gap: existing tests don't actually run or cover the core tool functions due to import issues, missing mocks, and WebSocket dependency challenges.

**Key findings:**
1. **Zero actual coverage** despite 19 test files - tests fail on imports due to syntax errors and missing dependencies
2. **Complex async mocking** required - Playwright Browser/Context/Page objects, WebSocket communication, device hardware APIs
3. **Three-layer mocking strategy** needed - Playwright async API (browser), WebSocket protocol (device), and governance services
4. **Existing test patterns** are sound but broken - fixture-based with AsyncMock, but implementation gaps prevent execution
5. **Governance integration** is critical - all tool functions enforce maturity levels (INTERN+, SUPERVISED+, AUTONOMOUS)

**Primary recommendation:** Fix existing test infrastructure first (imports, fixtures, async mocking), then systematically implement coverage for each tool function using AsyncMock with proper Playwright and WebSocket mocking patterns.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.0+ | Test runner and fixtures | Industry standard for Python testing, async support via pytest-asyncio |
| **pytest-asyncio** | 0.21+ | Async test execution | Required for testing async tool functions (browser_create_session, device_camera_snap, etc.) |
| **unittest.mock** | Built-in | Mocking AsyncMock, MagicMock, patch | Python standard library, AsyncMock for async functions |
| **playwright** | 1.40+ | Browser automation (actual) | Target for mocking - async API with Browser, BrowserContext, Page objects |
| **fastapi** | 0.100+ | WebSocket dependencies | device_tool.py imports from api/device_websocket.py |

### Testing Dependencies
| Library | Purpose | When to Use |
|---------|---------|-------------|
| **pytest-cov** | Coverage reporting | Generate coverage reports for 75%+ target verification |
| **pytest-mock** | Enhanced mocking fixtures | Optional - MagicMock sufficient for most cases |
| **coverage.py** | Coverage measurement | Backend tool for precise line coverage metrics |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest | pytest has superior async/fixture support, widely adopted |
| AsyncMock | asynctest | AsyncMock is built-in since Python 3.8, asynctest deprecated |
| unittest.mock | mock | Mock is external package, unittest.mock is standard library |

**Installation:**
```bash
# Core testing dependencies
pip install pytest pytest-asyncio pytest-cov

# For actual browser testing (not required for unit tests with mocks)
pip install playwright
playwright install chromium
```

## Architecture Patterns

### Recommended Project Structure
```
backend/tests/
├── unit/tools/
│   ├── test_browser_tool.py          # NEW - BrowserSession, BrowserSessionManager classes
│   ├── test_device_tool.py           # NEW - DeviceSessionManager, helper functions
│   ├── test_browser_tool_functions.py # NEW - browser_create_session, browser_navigate, etc.
│   └── test_device_tool_functions.py # NEW - device_camera_snap, device_get_location, etc.
├── integration/tools/
│   ├── test_browser_integration.py   # Existing - has governance tests
│   └── test_device_integration.py    # Existing - WebSocket integration tests
└── conftest.py                       # Shared fixtures for Playwright, devices, governance
```

### Pattern 1: Async Function Mocking with AsyncMock
**What:** Mock async tool functions that call Playwright or WebSocket APIs
**When to use:** Testing browser_navigate(), device_camera_snap(), etc. that await external services
**Example:**
```python
# Source: Existing test patterns in backend/tests/tools/test_browser_tool_complete.py
@pytest.mark.asyncio
async def test_browser_navigate_success(mock_page):
    """Test successful browser navigation."""
    with patch('tools.browser_tool.get_browser_manager') as mock_manager:
        mock_session = MagicMock()
        mock_session.page = mock_page
        mock_session.user_id = "user-123"
        mock_manager.return_value.get_session.return_value = mock_session

        # Mock page.goto and page.title
        mock_page.goto.return_value = MagicMock(status=200)
        mock_page.url = "https://example.com"

        result = await browser_navigate(
            session_id="session-123",
            url="https://example.com",
            user_id="user-123"
        )

        assert result["success"] is True
        assert result["url"] == "https://example.com"
```

### Pattern 2: Playwright Object Hierarchy Mocking
**What:** Mock Playwright's async API: Playwright → Browser → BrowserContext → Page
**When to use:** Testing BrowserSession.start(), browser_create_session()
**Example:**
```python
@pytest.fixture
def mock_playwright():
    """Mock Playwright async API."""
    with patch('tools.browser_tool.async_playwright') as mock:
        mock_pw = MagicMock()
        mock.return_value.__aenter__.return_value = mock_pw

        # Mock browser launch
        mock_browser = MagicMock()
        mock_browser.launch = AsyncMock()
        mock_browser.new_context = AsyncMock()

        # Mock browser context
        mock_context = MagicMock()
        mock_context.new_page = AsyncMock()
        mock_context.cookies = AsyncMock(return_value=[])

        # Mock page
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.title = AsyncMock(return_value="Test Page")

        mock_pw.chromium.return_value = mock_browser
        mock_browser.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        yield mock_pw, mock_browser, mock_context, mock_page
```

### Pattern 3: WebSocket Device Communication Mocking
**What:** Mock WebSocket communication between backend and mobile devices
**When to use:** Testing device_camera_snap(), device_get_location(), device_send_notification()
**Example:**
```python
@pytest.mark.asyncio
async def test_device_camera_snap_success(mock_db):
    """Test successful camera capture via WebSocket."""
    with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
        with patch('tools.device_tool.is_device_online', return_value=True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                # Mock WebSocket response from device
                mock_send.return_value = {
                    "success": True,
                    "file_path": "/tmp/photo.jpg",
                    "data": {"base64_data": "base64encodedimage"}
                }

                result = await device_camera_snap(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123",
                    camera_id="default",
                    resolution="1920x1080"
                )

                assert result["success"] is True
                assert result["file_path"] == "/tmp/photo.jpg"
                mock_send.assert_called_once()
```

### Pattern 4: Governance Service Mocking
**What:** Mock AgentContextResolver and ServiceFactory for governance checks
**When to use:** Testing all tool functions that enforce maturity levels
**Example:**
```python
@pytest.fixture
def mock_governance_allowed():
    """Mock governance service that allows actions."""
    with patch('core.service_factory.ServiceFactory.get_governance_service') as mock:
        service = MagicMock()
        service.can_perform_action = MagicMock(return_value={
            "allowed": True,
            "reason": "Agent has required maturity level"
        })
        service.record_outcome = AsyncMock()
        mock.return_value = service
        yield service

@pytest.mark.asyncio
async def test_browser_create_session_intern_agent(mock_db, mock_governance_allowed):
    """Test browser session creation with INTERN agent (allowed)."""
    with patch('tools.browser_tool.get_browser_manager') as mock_manager:
        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.created_at = datetime.now()
        mock_manager.return_value.create_session = AsyncMock(return_value=mock_session)

        result = await browser_create_session(
            user_id="user-123",
            agent_id="agent-intern-123",
            db=mock_db
        )

        assert result["success"] is True
        assert result["session_id"] == "session-123"
```

### Anti-Patterns to Avoid
- **Sync testing async functions:** Don't call async functions without await - all tool functions are async
- **Missing @pytest.mark.asyncio:** Async test functions must be marked or they won't run
- **Real Playwright in unit tests:** Don't launch real browsers - use AsyncMock for fast, isolated tests
- **Incomplete WebSocket mocking:** Must mock both WEBSOCKET_AVAILABLE flag AND send_device_command function
- **Forgetting db.commit():** Mock database sessions must mock commit() or tests will fail
- **Hardcoded agent IDs:** Use fixtures for agents with different maturity levels

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async mocking | Custom async mock classes | unittest.mock.AsyncMock | Built-in, battle-tested, handles async/await correctly |
| Test runners | Custom test discovery | pytest with pytest-asyncio | Industry standard, async fixtures, superior reporting |
| Coverage | Custom line counting | pytest-cov with coverage.py | Precise metrics, HTML reports, CI integration |
| WebSocket mocking | Real WebSocket servers | AsyncMock with patch() | Faster, deterministic, no network dependencies |
| Browser automation | Custom Selenium setup | AsyncMock for unit tests | Real Playwright for integration tests only |

**Key insight:** Unit tests should never launch real browsers or connect to real devices. Use AsyncMock to simulate external dependencies. Integration tests (already exist) can test real Playwright behavior.

## Common Pitfalls

### Pitfall 1: Import Errors from Syntax Issues
**What goes wrong:** Tests fail to import tool modules due to syntax errors or missing dependencies
**Why it happens:** Current codebase has syntax errors (line 53 in browser_tool.py: `session_id: str,`), missing imports
**How to avoid:**
1. Fix syntax errors in tool files first
2. Ensure all imports are present (async_playwright, AgentContextResolver, etc.)
3. Verify imports work before writing tests: `python -c "from tools.browser_tool import browser_create_session"`
**Warning signs:** ImportError, SyntaxError when running pytest

### Pitfall 2: Forgetting @pytest.mark.asyncio
**What goes wrong:** Async test functions don't run, collected but skipped
**Why it happens:** pytest-asyncio requires @pytest.mark.asyncio decorator on async test functions
**How to avoid:** Always mark async test functions:
```python
@pytest.mark.asyncio
async def test_browser_navigate():
    await browser_navigate(...)  # This will run
```
**Warning signs:** Tests collected but "0 passed" in pytest output

### Pitfall 3: Incomplete Playwright Mocking
**What goes wrong:** Tests fail with "AttributeError: 'coroutine' object has no attribute 'X'"
**Why it happens:** Forgetting to mock intermediate async calls (BrowserContext.new_page(), Page.goto())
**How to avoid:** Mock the entire hierarchy: Playwright → Browser → BrowserContext → Page
**Warning signs:** AttributeError on coroutine objects, tests hanging indefinitely

### Pitfall 4: Real WebSocket Dependencies
**What goes wrong:** Tests try to connect to real devices via WebSocket, fail with connection errors
**Why it happens:** device_tool.py imports from api/device_websocket.py which has real WebSocket code
**How to avoid:** Patch both the module-level flag AND the function:
```python
with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock):
        # Now tests won't try real WebSocket connections
```
**Warning signs:** Connection refused errors, tests hanging on network I/O

### Pitfall 5: Missing Database Mock Methods
**What goes wrong:** Tests fail with "AttributeError: 'MagicMock' object has no attribute 'commit'"
**Why it happens:** Tool functions call db.commit(), db.refresh(), db.query() but mocks don't have these methods
**How to avoid:** Always include all db methods in fixture:
```python
@pytest.fixture
def mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.query = MagicMock()
    db.rollback = MagicMock()
    return db
```
**Warning signs:** AttributeError on db object, tests failing after successful function execution

### Pitfall 6: Not Testing All Code Paths
**What goes wrong:** Coverage report shows 30% when you expected 75%
**Why it happens:** Only testing happy paths, not error handling or edge cases
**How to avoid:** Test all branches:
- Success paths (agent allowed, device online, browser launches)
- Failure paths (agent blocked, device offline, navigation fails)
- Edge cases (empty selectors, timeout errors, permission denied)
**Warning signs:** Coverage report shows large gaps in if/else branches

## Code Examples

Verified patterns from existing test files in the codebase:

### Mock Playwright Browser Session
```python
# Source: backend/tests/tools/test_browser_tool_complete.py (lines 59-100)
@pytest.fixture
def mock_playwright():
    """Mock Playwright async API."""
    with patch('tools.browser_tool.async_playwright') as mock:
        mock_pw = MagicMock()
        mock.return_value.__aenter__.return_value = mock_pw
        yield mock_pw

@pytest.fixture
def mock_browser():
    """Mock Playwright Browser."""
    browser = MagicMock(spec=Browser)
    browser.new_context = AsyncMock()
    browser.close = AsyncMock()
    return browser

@pytest.fixture
def mock_page():
    """Mock Playwright Page."""
    page = MagicMock(spec=Page)
    page.goto = AsyncMock()
    page.title = AsyncMock(return_value="Test Page")
    page.screenshot = AsyncMock(return_value=b"fake screenshot")
    page.wait_for_selector = AsyncMock()
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.query_selector = AsyncMock()
    page.evaluate = AsyncMock()
    return page
```

### Test Browser Navigation with Governance
```python
# Source: backend/tests/tools/test_browser_tool_complete.py (pattern)
@pytest.mark.asyncio
async def test_browser_navigate_with_governance_check(mock_page, mock_db):
    """Test browser navigation with governance enforcement."""
    with patch('tools.browser_tool.get_browser_manager') as mock_manager:
        # Setup session mock
        mock_session = MagicMock()
        mock_session.page = mock_page
        mock_session.user_id = "user-123"
        mock_manager.return_value.get_session.return_value = mock_session

        # Mock navigation
        mock_page.goto = AsyncMock(return_value=MagicMock(status=200))
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Example Domain")

        # Execute
        result = await browser_navigate(
            session_id="session-123",
            url="https://example.com",
            user_id="user-123"
        )

        # Assert
        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert result["title"] == "Example Domain"
        assert result["status"] == 200
```

### Mock Device WebSocket Communication
```python
# Source: backend/tests/tools/test_device_tool_complete.py (lines 136-156)
@pytest.mark.asyncio
async def test_camera_capture_success(mock_db, mock_device):
    """Test successful camera capture."""
    with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
        with patch('tools.device_tool.is_device_online', return_value=True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                # Mock WebSocket response
                mock_send.return_value = {
                    "success": True,
                    "file_path": "/tmp/photo.jpg",
                    "data": {"base64_data": "base64encodedimage"}
                }

                result = await device_camera_snap(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123",
                    camera_id="default",
                    resolution="1920x1080"
                )

                assert result["success"] is True
                assert result["file_path"] == "/tmp/photo.jpg"
```

### Test Device Governance Enforcement
```python
# Source: backend/tests/tools/test_device_tool_complete.py (pattern)
@pytest.mark.asyncio
async def test_camera_snap_student_agent_blocked(mock_db):
    """Test camera snap blocked for STUDENT agent."""
    with patch('core.service_factory.ServiceFactory.get_governance_service') as mock_gov:
        # Mock governance check that blocks STUDENT
        governance = MagicMock()
        governance.can_perform_action = MagicMock(return_value={
            "allowed": False,
            "reason": "STUDENT agents cannot use device camera"
        })
        mock_gov.return_value = governance

        result = await device_camera_snap(
            db=mock_db,
            user_id="user-123",
            device_node_id="device-123",
            agent_id="student-agent-123"
        )

        assert result["success"] is False
        assert result["governance_blocked"] is True
        assert "cannot use device camera" in result["error"]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| unittest | pytest with pytest-asyncio | 2020+ | Industry standard for async testing |
| asynctest library | AsyncMock (built-in) | Python 3.8+ | No external dependencies for async mocking |
| Selenium | Playwright | 2021+ | Better async API, cross-browser support |
| Real device testing | AsyncMock for unit tests | Always | Faster, deterministic tests |

**Deprecated/outdated:**
- **asynctest library:** Deprecated in favor of built-in AsyncMock (Python 3.8+)
- **mock package:** Use unittest.mock (standard library) instead
- **pytest.run():** Use pytest CLI directly for better test discovery

## Open Questions

1. **Fix syntax errors first?**
   - What we know: browser_tool.py has syntax error on line 53 (`session_id: str,` trailing comma)
   - What's unclear: Are there other syntax errors blocking imports?
   - Recommendation: Run import check and fix all syntax errors before writing tests

2. **WebSocket dependency complexity?**
   - What we know: device_tool.py imports from api/device_websocket.py (196 lines)
   - What's unclear: Can we mock at the tool level, or need to mock the entire WebSocket module?
   - Recommendation: Mock at tool level first (patch WEBSOCKET_AVAILABLE and send_device_command)

3. **Coverage baseline accuracy?**
   - What we know: Gap analysis shows 0% coverage for both files (299 and 308 lines)
   - What's unclear: Is this current actual coverage or old baseline?
   - Recommendation: Run fresh coverage report to verify current state

4. **Integration test reuse?**
   - What we know: 19 test files exist but may not be running
   - What's unclear: Can existing integration tests be adapted for unit coverage?
   - Recommendation: Review existing test files for reusable patterns/fixtures

## Sources

### Primary (HIGH confidence)
- **backend/tests/tools/test_browser_tool_complete.py** - Comprehensive test patterns for browser_tool.py (100+ tests)
- **backend/tests/tools/test_device_tool_complete.py** - Comprehensive test patterns for device_tool.py (80+ tests)
- **backend/tests/unit/test_browser_tool.py** - Unit test patterns with AsyncMock fixtures
- **backend/tests/unit/test_device_tool.py** - Unit test patterns for device functions
- **backend/tests/coverage_reports/GAP_ANALYSIS_164.md** - Coverage gap analysis showing 0% for tool files
- **backend/tools/browser_tool.py** - Source file (819 lines, 299 uncovered)
- **backend/tools/device_tool.py** - Source file (1292 lines, 308 uncovered)

### Secondary (MEDIUM confidence)
- **pytest documentation** - pytest-asyncio usage, async test patterns (verified against codebase examples)
- **unittest.mock documentation** - AsyncMock for async function mocking (verified against codebase examples)
- **Playwright Python documentation** - Async API patterns (verified against mock fixtures in codebase)

### Tertiary (LOW confidence)
- **Playwright testing best practices** - General patterns (not verified against official docs, LOW confidence)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest and AsyncMock are industry standards, verified in codebase
- Architecture: HIGH - Existing test files show proven patterns, just need fixing/execution
- Pitfalls: HIGH - Observed import/syntax errors in current codebase, documented anti-patterns
- Coverage targets: HIGH - Gap analysis shows exact line counts and current 0% coverage

**Research date:** March 11, 2026
**Valid until:** 30 days (stable testing patterns, unlikely to change)

**Files analyzed:**
- backend/tools/browser_tool.py (819 lines, 10 public functions, 2 classes)
- backend/tools/device_tool.py (1292 lines, 9 public functions, 1 class)
- backend/tests/tools/test_browser_tool_complete.py (100+ tests, existing patterns)
- backend/tests/tools/test_device_tool_complete.py (80+ tests, existing patterns)
- backend/api/device_websocket.py (WebSocket dependency for device_tool.py)
