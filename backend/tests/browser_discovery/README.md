# Browser Bug Discovery Tests

Automated headless browser testing for discovering UI bugs, accessibility violations, and visual regressions using Playwright, axe-core, and Percy.

## Overview

Browser discovery tests use headless browser automation to discover bugs that traditional unit tests and integration tests miss. These tests explore the UI by clicking buttons, filling forms, navigating pages, and detecting:

- **Console Errors**: JavaScript errors, unhandled exceptions, warnings
- **Accessibility Violations**: WCAG 2.1 AA compliance issues using axe-core
- **Broken Links**: Dead links, 404 errors, redirect loops
- **Visual Regressions**: UI changes detected via Percy visual snapshots
- **Form Edge Cases**: Null bytes, XSS payloads, SQL injection, unicode handling
- **Intelligent Exploration**: Automated UI exploration using DFS, BFS, and random walk algorithms

**Technology Stack:**
- **Playwright Python 1.58.0**: Headless browser automation (Chromium)
- **axe-core 4.8.2**: Accessibility testing (WCAG 2.1 AA)
- **Percy**: Visual regression testing
- **pytest-playwright**: Pytest integration for Playwright

## Requirements Coverage

| Requirement | Test File | Status | Description |
|-------------|-----------|--------|-------------|
| BROWSER-01 | test_exploration_agent.py | ✅ | Intelligent exploration agent (DFS, BFS, random walk) |
| BROWSER-02 | test_console_errors.py | ✅ | Console error detection with metadata |
| BROWSER-03 | test_accessibility.py | ✅ | Accessibility violations (axe-core, WCAG 2.1 AA) |
| BROWSER-04 | test_broken_links.py | ✅ | Broken link detection (404s, redirect loops) |
| BROWSER-05 | test_visual_regression.py | ✅ | Visual regression testing (Percy integration) |
| BROWSER-06 | test_form_filling.py | ✅ | Form edge cases (null bytes, XSS, SQL injection) |
| BROWSER-07 | All tests (via conftest.py) | ✅ | API-first authentication (10-100x faster than UI login) |

## Quick Start

### Prerequisites

1. **Python 3.11+**
   ```bash
   python --version
   ```

2. **Playwright Browsers**
   ```bash
   playwright install chromium
   ```

3. **Frontend & Backend Running**
   ```bash
   # Terminal 1: Start backend
   cd backend
   python -m uvicorn main:app

   # Terminal 2: Start frontend
   cd frontend-nextjs
   npm run dev
   ```

### Running Tests

#### All Browser Discovery Tests
```bash
# Run all browser discovery tests
pytest backend/tests/browser_discovery/ -v -m browser_discovery

# With screenshots on failure
pytest backend/tests/browser_discovery/ -v -m browser_discovery --headed
```

#### Specific Test Categories

```bash
# Console error tests (BROWSER-02)
pytest backend/tests/browser_discovery/test_console_errors.py -v

# Accessibility tests (BROWSER-03)
pytest backend/tests/browser_discovery/test_accessibility.py -v -m accessibility

# Broken link tests (BROWSER-04)
pytest backend/tests/browser_discovery/test_broken_links.py -v -m broken_links

# Form edge case tests (BROWSER-06)
pytest backend/tests/browser_discovery/test_form_filling.py -v

# Visual regression tests (BROWSER-05)
pytest backend/tests/browser_discovery/test_visual_regression.py -v -m visual

# Exploration agent tests (BROWSER-01)
pytest backend/tests/browser_discovery/test_exploration_agent.py -v
```

#### With Percy Visual Regression

```bash
# Set Percy token (get from https://percy.io/settings/api_tokens)
export PERCY_TOKEN=your_token_here

# Run visual tests with Percy
percy exec -- pytest backend/tests/browser_discovery/test_visual_regression.py -v

# Or run with pytest (Percy auto-enabled if token present)
pytest backend/tests/browser_discovery/test_visual_regression.py -v
```

## Fixture Reuse

Browser discovery tests reuse fixtures from existing test infrastructure to avoid duplication and ensure consistency.

### Imported Fixtures (No Duplication)

**From `tests.e2e_ui.fixtures.auth_fixtures`:**
- **`authenticated_page`**: API-first authentication (10-100x faster than UI login)
  - Sets JWT token in localStorage
  - Bypasses login form navigation
  - Saves 2-10 seconds per test

**From `frontend_nextjs.tests.visual.fixtures.percy_fixtures`:**
- **`percy_snapshot`**: Percy visual regression snapshot function
  - Captures screenshots for visual comparison
  - Integrates with Percy.io dashboard
  - Graceful degradation if Percy unavailable

**Local fixtures in `conftest.py`:**
- **`console_monitor`**: Captures JavaScript console errors, warnings, and logs
- **`accessibility_checker`**: Runs axe-core audit for WCAG violations
- **`exploration_agent`**: Intelligent UI exploration (DFS, BFS, random walk)
- **`broken_link_checker`**: Checks all links for 404s and network errors
- **`assert_no_console_errors`**: Asserts no JavaScript errors occurred
- **`assert_accessibility`**: Asserts no accessibility violations found

### Example: Using Fixtures

```python
from tests.browser_discovery.conftest import authenticated_page, console_monitor, accessibility_checker

def test_dashboard_clean_load(authenticated_page, console_monitor, accessibility_checker):
    """Test dashboard loads without console errors or accessibility violations."""
    # Navigate to dashboard (already authenticated via JWT token)
    authenticated_page.goto("http://localhost:3001/dashboard")

    # Check for console errors
    errors = console_monitor.get("error", [])
    assert len(errors) == 0, f"Console errors: {errors}"

    # Check accessibility
    violations = accessibility_checker()
    assert len(violations) == 0, f"Accessibility violations: {violations}"
```

**Benefits:**
- No fixture duplication (reuse existing code)
- Consistent authentication across all tests
- 10-100x faster than UI login flow
- Centralized fixture maintenance

## Percy Setup

Percy visual regression testing requires API token configuration.

### Installation

```bash
# Install Percy CLI globally
npm install -g @percy/cli

# Verify installation
percy --version
```

### Token Configuration

1. **Get Percy Token**
   - Visit: https://percy.io/settings/api_tokens
   - Create new token (or reuse existing)
   - Copy token (starts with `percy_...`)

2. **Set Environment Variable**
   ```bash
   # Export token for current session
   export PERCY_TOKEN=your_token_here

   # Or add to ~/.bashrc or ~/.zshrc for persistence
   echo 'export PERCY_TOKEN=your_token_here' >> ~/.bashrc
   source ~/.bashrc
   ```

3. **Run Visual Tests**
   ```bash
   # With Percy CLI wrapper (recommended)
   percy exec -- pytest backend/tests/browser_discovery/test_visual_regression.py -v

   # Or pytest directly (uses token if set)
   pytest backend/tests/browser_discovery/test_visual_regression.py -v
   ```

### Percy Dashboard

After running tests with Percy:
- Visit: https://percy.io/[your-project]/builds
- Review visual diffs
- Approve or reject changes
- Compare snapshots across branches

**Note**: Percy tests skip gracefully if `PERCY_TOKEN` not set (tests pass without visual comparison).

## CI Pipeline

Browser discovery tests run weekly (not on every PR) due to longer execution time of visual regression and exploration tests.

### Weekly Schedule

**Workflow:** `.github/workflows/browser-discovery.yml`
**Schedule:** Every Sunday at 2 AM UTC (Saturday evening PST)
**Trigger:** Manual trigger available via `workflow_dispatch`

### CI Pipeline Steps

1. **Setup Environment**
   - Checkout code
   - Install Python 3.11
   - Install Playwright browsers
   - Install Node.js and Percy CLI

2. **Start Services**
   - Start frontend server (npm run build && npm start)
   - Start backend server (uvicorn main:app)

3. **Run Tests**
   - Console error tests
   - Accessibility tests
   - Broken link tests
   - Form edge case tests
   - Exploration agent tests
   - Visual regression tests (with Percy)

4. **Upload Artifacts** (on failure)
   - Screenshots: `backend/tests/browser_discovery/artifacts/screenshots/`
   - Logs: `backend/tests/browser_discovery/artifacts/logs/`

5. **File Bugs** (on failure)
   - Automated bug filing via `tests/bug_discovery/file_bugs_from_artifacts.py`

### Manual Trigger

```bash
# Via GitHub CLI
gh workflow run browser-discovery.yml

# Via GitHub web UI
# Visit: https://github.com/[org]/[repo]/actions/workflows/browser-discovery.yml
# Click "Run workflow" button
```

## Test Categories

### 1. Console Error Detection (BROWSER-02)

**File:** `test_console_errors.py` (7 tests)

Detects JavaScript errors, unhandled exceptions, and console warnings during page navigation and interaction.

**Tests:**
- `test_no_console_errors_on_dashboard()`
- `test_no_console_errors_on_agents_page()`
- `test_no_console_errors_on_canvas_list()`
- `test_no_console_errors_on_workflows_list()`
- `test_console_errors_include_metadata()`
- `test_console_warnings_logged()`
- `test_console_monitor_captures_location()`

**Metadata Captured:**
- `text`: Error message
- `url`: Page URL where error occurred
- `timestamp`: ISO 8601 timestamp
- `location`: Source file, line number, column number

### 2. Accessibility Testing (BROWSER-03)

**File:** `test_accessibility.py` (7 tests)

Automated WCAG 2.1 AA compliance testing using axe-core 4.8.2.

**Tests:**
- `test_dashboard_accessibility_compliance()`
- `test_agents_page_accessibility()`
- `test_canvas_page_accessibility()`
- `test_workflows_page_accessibility()`
- `test_accessibility_violations_include_metadata()`
- `test_accessibility_impact_levels()`
- `test_accessibility_tags_coverage()`

**Violations Detected:**
- Missing ARIA labels
- Low contrast ratios
- Missing alt text
- Keyboard navigation issues
- Form labeling problems

**Metadata Captured:**
- `id`: Violation ID (e.g., `color-contrast`)
- `impact`: Critical, serious, moderate, minor
- `description`: Human-readable description
- `help`: How to fix
- `help_url`: Documentation URL
- `tags`: WCAG tags (e.g., `wcag2aa`, `wcag21aa`)

### 3. Broken Link Detection (BROWSER-04)

**File:** `test_broken_links.py` (6 tests)

Finds dead links, 404 errors, and network issues across all pages.

**Tests:**
- `test_no_broken_links_on_dashboard()`
- `test_no_broken_links_on_agents_list()`
- `test_no_broken_links_on_canvas_list()`
- `test_no_broken_links_on_workflows_list()`
- `test_broken_link_includes_metadata()`
- `test_link_checker_skips_localhost()`

**Detection Methods:**
- HTTP status code checking (HEAD requests)
- Redirect loop detection
- Network error handling
- Localhost link skipping (test environment)

**Metadata Captured:**
- `url`: Broken link URL
- `text`: Link anchor text
- `status_code`: HTTP status code (404, 500, etc.)
- `error`: Network error message (if status unavailable)

### 4. Visual Regression Testing (BROWSER-05)

**File:** `test_visual_regression.py` (26 tests)

UI visual regression testing with Percy integration across 5 page groups.

**Page Groups:**
1. **Authentication** (4 tests): Login, logout, session persistence
2. **Dashboard** (4 tests): Desktop, tablet, mobile views
3. **Agents** (6 tests): List, create, execute, streaming, governance
4. **Canvas** (6 tests): Charts, markdown, forms, sheets
5. **Workflows** (6 tests): List, create, execute, DAG visualization

**Percy Features:**
- Snapshot comparison across branches
- Visual diff highlighting
- Baseline management
- Responsive testing (mobile, tablet, desktop)
- Dark mode testing

**Setup:**
```bash
export PERCY_TOKEN=your_token_here
pytest backend/tests/browser_discovery/test_visual_regression.py -v
```

### 5. Form Edge Cases (BROWSER-06)

**File:** `test_form_filling.py` (8 tests)

Tests form handling of malicious and edge case inputs.

**Edge Cases Covered:**
- **Null Bytes**: `"agent\x00name\x00with\x00nulls"`
- **XSS (Script)**: `'<script>alert("XSS")</script>'`
- **XSS (Img OnError)**: `'<img src=x onerror=alert("XSS")>'`
- **XSS (Double Quote)**: `'"><script>alert(String.fromCharCode(88,83,83))</script>'`
- **SQL Injection**: `"' OR '1'='1"`
- **Unicode**: `"🎨 Test Agent 你好 مرحبا"`
- **Massive Input**: `"A" * 10000` (10,000 characters)
- **Special Characters**: `"line1\nline2\rline3\ttab\x1bescape"`

**Verification:**
- No crash or unresponsive page
- No JavaScript console errors
- Proper sanitization (XSS rejected)
- Graceful degradation (validation errors OK)

### 6. Intelligent Exploration Agent (BROWSER-01)

**File:** `test_exploration_agent.py` (12 tests)

Automated UI exploration using graph traversal algorithms to discover bugs.

**Exploration Algorithms:**

1. **Depth-First Search (DFS)**
   - Explores deep UI paths first (dashboard → agent → execute → results)
   - Ideal for nested workflow bug discovery
   - Test: `test_exploration_agent_dfs()`

2. **Breadth-First Search (BFS)**
   - Explores all links at current depth before going deeper
   - Ideal for comprehensive navigation coverage
   - Test: `test_exploration_agent_bfs()`

3. **Random Walk**
   - Stochastic exploration with optional seed for reproducibility
   - Ideal for edge case discovery and unexpected state combinations
   - Test: `test_exploration_agent_random_walk()`

**Features:**
- Limit enforcement (max_depth, max_actions)
- Visited URL tracking (prevents infinite loops)
- Bug detection (console errors, broken images)
- Exploration report (actions_taken, urls_visited, bugs_found)

**Tests:**
- `test_exploration_agent_dfs()` - DFS navigation
- `test_exploration_agent_bfs()` - BFS navigation
- `test_exploration_agent_random_walk()` - Random exploration
- `test_exploration_agent_with_seed()` - Reproducible random walks
- `test_exploration_agent_limit_enforcement()` - Max actions/depth
- `test_exploration_agent_visited_url_tracking()` - Loop prevention
- `test_exploration_agent_bug_detection()` - Console errors, broken images
- `test_exploration_agent_report_generation()` - Statistics
- `test_exploration_agent_clickable_detection()` - Button/link finding
- `test_exploration_agent_selector_building()` - CSS selector generation
- `test_exploration_agent_error_handling()` - Graceful error recovery
- `test_exploration_agent_responsive()` - Works across page types

### 7. API-First Authentication (BROWSER-07)

**All Tests** (via `conftest.py`)

Uses JWT token in localStorage for instant authentication, bypassing slow UI login flow.

**Performance:**
- **API-First**: 10-100ms (JWT token set via API)
- **UI Login**: 2-10 seconds (form navigation, input, submit, wait)
- **Speedup**: 10-100x faster

**Implementation:**
```python
# From tests.e2e_ui.fixtures.auth_fixtures
def authenticated_page(browser, authenticated_user):
    page = browser.new_page()
    page.goto("http://localhost:3001")

    # Set JWT token in localStorage (instant authentication)
    token = authenticated_user[1]  # (user, jwt_token) tuple
    page.evaluate(f"localStorage.setItem('auth_token', '{token}')")

    return page
```

**Usage:**
```python
def test_dashboard_access(authenticated_page):
    # Already authenticated! No login flow needed.
    authenticated_page.goto("http://localhost:3001/dashboard")
    assert authenticated_page.locator("h1").contains("Dashboard")
```

## Troubleshooting

### Playwright Browser Not Found

**Issue:** `Executable doesn't exist at /path/to/chromium`

**Solution:**
```bash
playwright install chromium

# Or install all browsers
playwright install
```

### Percy Token Not Set

**Issue:** Percy tests skip or fail with authentication error

**Solution:**
```bash
# Export Percy token
export PERCY_TOKEN=your_token_here

# Verify token is set
echo $PERCY_TOKEN

# Re-run tests
pytest backend/tests/browser_discovery/test_visual_regression.py -v
```

### Frontend/Backend Not Running

**Issue:** `Error: connect ECONNREFUSED localhost:3001` or `:8000`

**Solution:**
```bash
# Start backend
cd backend
python -m uvicorn main:app

# Start frontend (new terminal)
cd frontend-nextjs
npm run dev

# Verify services are running
curl http://localhost:8000/health/live
curl http://localhost:3001
```

### Port Conflicts

**Issue:** `Error: listen EADDRINUSE :3001` or `:8000`

**Solution:**
```bash
# Kill process using port 3001
lsof -ti:3001 | xargs kill -9

# Kill process using port 8000
lsof -ti:8000 | xargs kill -9

# Or use different ports
export FRONTEND_PORT=3002
export BACKEND_PORT=8001
```

### Localhost Links Fail in Tests

**Issue:** Broken link tests fail on localhost URLs

**Solution:** This is expected behavior. Broken link checker skips localhost links in test environment:

```python
# From broken_link_checker fixture
if "localhost" in link["url"] or "127.0.0.1" in link["url"]:
    continue  # Skip localhost links
```

### Tests Timeout

**Issue:** Tests timeout after 30 seconds (Playwright default)

**Solution:** Increase timeout for specific tests:

```python
@pytest.mark.timeout(60)
def test_slow_operation(authenticated_page):
    authenticated_page.goto("/slow-page")
    authenticated_page.wait_for_selector("text=Loaded", timeout=30000)
```

### axe-core CDN Load Failure

**Issue:** Accessibility tests skip with "Failed to load axe-core"

**Solution:** Check network connectivity or use axe-core locally:

```python
# If CDN fails, tests skip gracefully with pytest.skip
# This is intentional - no network = no accessibility testing
```

### Visual Tests Fail on First Run

**Issue:** Percy visual tests fail on first run (no baseline)

**Solution:** This is expected. First run establishes baseline. Approve snapshots in Percy dashboard:

```bash
# Run tests
percy exec -- pytest backend/tests/browser_discovery/test_visual_regression.py -v

# Visit Percy dashboard to approve baseline
# https://percy.io/[your-project]/builds
```

## Test Execution Examples

### Quick Smoke Test

```bash
# Run console error tests only (fastest)
pytest backend/tests/browser_discovery/test_console_errors.py -v
```

### Full Bug Discovery Run

```bash
# Run all browser discovery tests
pytest backend/tests/browser_discovery/ -v -m "browser_discovery or accessibility or broken_links"

# With screenshots on failure
pytest backend/tests/browser_discovery/ -v -m "browser_discovery or accessibility or broken_links" --headed
```

### With Percy Visual Regression

```bash
# Set token first
export PERCY_TOKEN=percy_ks_...

# Run all tests including Percy
pytest backend/tests/browser_discovery/ -v

# Or run only visual tests
percy exec -- pytest backend/tests/browser_discovery/test_visual_regression.py -v
```

### Parallel Execution

```bash
# Run with pytest-xdist (faster on multi-core machines)
pytest backend/tests/browser_discovery/ -v -n 4
```

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Per test | <30 seconds | Console/accessibility tests ~2-5s each |
| Visual tests | ~5-10 seconds per snapshot | Percy upload overhead |
| Exploration tests | ~10-30 seconds | Depends on max_actions/max_depth |
| Full suite (without Percy) | ~5-10 minutes | 66-68 tests total |
| Full suite (with Percy) | ~15-20 minutes | Visual regression adds overhead |

## Additional Resources

- **Playwright Documentation**: https://playwright.dev/python/
- **axe-core Documentation**: https://www.deque.com/axe/
- **Percy Documentation**: https://docs.percy.io/
- **E2E UI Testing Guide**: `backend/tests/e2e_ui/README.md`
- **Fixture Reuse Guide**: `backend/tests/bug_discovery/FIXTURE_REUSE_GUIDE.md`

## Status

**Phase:** 240 - Headless Browser Bug Discovery
**Plan:** 240-05 - Documentation and CI Pipeline
**Status:** ✅ COMPLETE

**Completed Tasks:**
- ✅ Comprehensive README.md with usage instructions
- ✅ Requirements coverage table (BROWSER-01 through BROWSER-07)
- ✅ Fixture reuse documentation (e2e_ui, frontend visual tests)
- ✅ Percy setup instructions and token configuration
- ✅ CI pipeline configuration (weekly schedule)
- ✅ Test category descriptions with examples
- ✅ Troubleshooting section with common issues

**Test Coverage:**
- 66-68 tests across 6 test files
- All 7 BROWSER requirements satisfied
- API-first authentication (10-100x faster)
- Fixture reuse from existing test infrastructure
