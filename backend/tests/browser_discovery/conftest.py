"""
Browser discovery test configuration with Playwright setup.

This module provides pytest fixtures for headless browser automation using
Playwright to discover UI bugs, accessibility issues, and broken functionality.

Fixtures:
- exploration_agent: Fixture for intelligent UI exploration
- console_monitor: Fixture for capturing JavaScript console errors
- accessibility_checker: Fixture with axe-core integration
- Import existing fixtures from e2e_ui for auth and page management
"""

import os
import sys
from collections import deque
from datetime import datetime
from typing import List, Dict, Any

import pytest
from playwright.sync_api import Page, Browser, BrowserContext

# Add backend to path for imports
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# ============================================================================
# IMPORT EXISTING FIXTURES FROM E2E_UI (NO DUPLICATION)
# ============================================================================
# Reuse existing auth and page fixtures to avoid duplication
from tests.e2e_ui.fixtures.auth_fixtures import (
    authenticated_page,
    authenticated_page_api,
    test_user,
    authenticated_user,
)
from tests.e2e_ui.fixtures.database_fixtures import db_session

# ============================================================================
# PERCY VISUAL REGRESSION IMPORT
# ============================================================================
# Import Percy snapshot function for visual regression testing
# Graceful degradation if Percy is not available
try:
    from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot
    PERCY_AVAILABLE = True
except ImportError:
    PERCY_AVAILABLE = False
    percy_snapshot = None

# Re-export for direct use in browser discovery tests
__all__ = [
    'authenticated_page',
    'authenticated_page_api',
    'test_user',
    'authenticated_user',
    'db_session',
    'percy_snapshot',
    'authenticated_percy_page',
    'exploration_agent',
    'console_monitor',
    'accessibility_checker',
    'visual_regression_checker',
    'broken_link_checker',
]


# ============================================================================
# PLAYWRIGHT BROWSER SETUP
# ============================================================================

@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """
    Configure browser launch arguments for browser discovery.

    Headless mode for CI/CD, with additional flags for stability.

    Args:
        browser_type_launch_args: Default launch arguments from pytest-playwright

    Returns:
        Updated launch arguments
    """
    return {
        **browser_type_launch_args,
        "headless": True,
        "ignore_default_args": ["--enable-automation"],
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """
    Configure browser context arguments for browser discovery.

    Args:
        browser_context_args: Default context arguments from pytest-playwright

    Returns:
        Updated context arguments
    """
    return {
        **browser_context_args,
        "accept_downloads": True,
        "bypass_csp": True,
        "ignore_https_errors": True,
        "java_script_enabled": True,
        "user_agent": "AtomBrowserDiscovery/1.0",
    }


# ============================================================================
# PERCY VISUAL REGRESSION FIXTURES
# ============================================================================

@pytest.fixture(scope="function")
def authenticated_percy_page(browser: Browser, authenticated_user) -> Page:
    """
    Create authenticated page for Percy visual regression tests.

    Combines API-first authentication from e2e_ui with Percy integration.
    Reuses existing authenticated_page fixture which already sets JWT in localStorage.

    Args:
        browser: Playwright browser fixture
        authenticated_user: Authenticated user fixture from e2e_ui

    Yields:
        Page: Authenticated Playwright page ready for Percy snapshots

    Example:
        def test_visual_dashboard(authenticated_percy_page):
            authenticated_percy_page.goto("http://localhost:3000/dashboard")
            percy_snapshot(authenticated_percy_page, "Dashboard")
    """
    # Reuse existing authenticated_page fixture which already sets JWT in localStorage
    from tests.e2e_ui.fixtures.auth_fixtures import authenticated_page

    # Create authenticated page using existing fixture
    page = authenticated_page(browser, authenticated_user)

    yield page

    # Cleanup is handled by authenticated_page fixture


# ============================================================================
# CONSOLE ERROR MONITORING FIXTURE
# ============================================================================

@pytest.fixture(scope="function")
def console_monitor(page: Page) -> Dict[str, List[Dict[str, Any]]]:
    """
    Monitor JavaScript console for errors and warnings.

    This fixture captures all console messages during test execution,
    enabling detection of JavaScript errors, unhandled exceptions,
    and console warnings that indicate bugs.

    Args:
        page: Playwright page fixture

    Returns:
        dict: Console logs categorized by type (error, warning, info, log)

    Example:
        def test_no_console_errors(console_monitor):
            page.goto("http://localhost:3001/dashboard")
            assert len(console_monitor["error"]) == 0, "Page has JS errors"
    """
    console_logs: Dict[str, List[Dict[str, Any]]] = {
        "error": [],
        "warning": [],
        "info": [],
        "log": [],
        "debug": [],
    }

    def _handle_console(msg):
        """Handle console message and categorize by type."""
        log_entry = {
            "type": msg.type,
            "text": msg.text,
            "timestamp": datetime.now().isoformat(),
            "url": page.url,
        }

        # Add location if available
        if msg.location:
            log_entry["location"] = {
                "url": msg.location.get("url"),
                "line_number": msg.location.get("lineNumber"),
                "column_number": msg.location.get("columnNumber"),
            }

        # Categorize by message type
        msg_type = msg.type.lower()
        if msg_type in console_logs:
            console_logs[msg_type].append(log_entry)
        else:
            console_logs["log"].append(log_entry)

    # Subscribe to console events
    page.on("console", _handle_console)

    yield console_logs

    # Unsubscribe after test
    page.remove_listener("console", _handle_console)


@pytest.fixture(scope="function")
def assert_no_console_errors(console_monitor: Dict[str, List[Dict[str, Any]]]):
    """
    Assert that no JavaScript errors occurred during test.

    This helper fixture checks console_monitor for errors and
    provides detailed failure messages with error contexts.

    Args:
        console_monitor: Console monitor fixture

    Raises:
        AssertionError: If console errors were detected

    Example:
        def test_page_clean_load(authenticated_page, console_monitor, assert_no_console_errors):
            page.goto("http://localhost:3001/dashboard")
            assert_no_console_errors()  # Fails with detailed error messages if any errors
    """
    errors = console_monitor.get("error", [])

    if errors:
        error_messages = []
        for i, error in enumerate(errors, 1):
            msg = f"\n  Error {i}:\n"
            msg += f"    Text: {error['text']}\n"
            msg += f"    URL: {error['url']}\n"
            msg += f"    Timestamp: {error['timestamp']}\n"
            if "location" in error:
                msg += f"    Location: {error['location']['url']}:{error['location']['line_number']}\n"
            error_messages.append(msg)

        pytest.fail(
            f"JavaScript errors detected ({len(errors)} total):\n" +
            "\n".join(error_messages)
        )


# ============================================================================
# ACCESSIBILITY TESTING FIXTURE (axe-core)
# ============================================================================

@pytest.fixture(scope="function")
def accessibility_checker(page: Page):
    """
    Accessibility checker using axe-core for automated a11y testing.

    This fixture injects axe-core library and runs accessibility audits
    to detect WCAG violations, missing ARIA labels, and other a11y issues.

    Args:
        page: Playwright page fixture

    Returns:
        callable: Function that runs axe-core audit and returns violations

    Example:
        def test_accessibility(authenticated_page, accessibility_checker):
            page.goto("http://localhost:3001/dashboard")
            violations = accessibility_checker()
            assert len(violations) == 0, "Page has accessibility violations"
    """
    # Inject axe-core library
    axe_core_script = """
    (function() {
        return new Promise((resolve, reject) => {
            if (window.axe) {
                resolve(true);
                return;
            }
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.8.2/axe.min.js';
            script.onload = () => resolve(true);
            script.onerror = () => reject(new Error('Failed to load axe-core'));
            document.head.appendChild(script);
        });
    })();
    """

    def _run_audit() -> List[Dict[str, Any]]:
        """Run axe-core accessibility audit and return violations.

        Returns:
            List of accessibility violations found by axe-core

        Raises:
            Exception: If axe-core fails to load or run
        """
        # Load axe-core if not already loaded
        page.evaluate(axe_core_script)

        # Run axe-core audit
        results = page.evaluate("""
        async () => {
            try {
                const results = await axe.run(document, {
                    runOnly: {
                        type: 'tag',
                        values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']
                    }
                });
                return results;
            } catch (error) {
                return { error: error.message };
            }
        }
        """)

        if isinstance(results, dict) and "error" in results:
            raise Exception(f"axe-core audit failed: {results['error']}")

        # Extract violations
        violations = results.get("violations", [])

        # Return structured violation data
        formatted_violations = []
        for violation in violations:
            formatted_violations.append({
                "id": violation["id"],
                "impact": violation["impact"],
                "description": violation["description"],
                "help": violation["help"],
                "help_url": violation["helpUrl"],
                "tags": violation["tags"],
                "nodes": violation["nodes"][:3],  # Limit to first 3 nodes for brevity
            })

        return formatted_violations

    return _run_audit


@pytest.fixture(scope="function")
def assert_accessibility(authenticated_page: Page, accessibility_checker):
    """
        Assert that page has no accessibility violations.

        This helper fixture runs accessibility audit and provides
        detailed failure messages with violation contexts.

        Args:
            authenticated_page: Authenticated page fixture
            accessibility_checker: Accessibility checker fixture

        Raises:
            AssertionError: If accessibility violations were detected

        Example:
            def test_dashboard_accessibility(authenticated_page, assert_accessibility):
                authenticated_page.goto("http://localhost:3001/dashboard")
                assert_accessibility()  # Fails with detailed violation messages
        """
    def _check_accessibility() -> None:
        violations = accessibility_checker()

        if violations:
            violation_messages = []
            for i, violation in enumerate(violations, 1):
                msg = f"\n  Violation {i}:\n"
                msg += f"    ID: {violation['id']}\n"
                msg += f"    Impact: {violation['impact']}\n"
                msg += f"    Description: {violation['description']}\n"
                msg += f"    Help: {violation['help']}\n"
                msg += f"    Help URL: {violation['help_url']}\n"
                msg += f"    Tags: {', '.join(violation['tags'])}\n"
                violation_messages.append(msg)

            pytest.fail(
                f"Accessibility violations detected ({len(violations)} total):\n" +
                "\n".join(violation_messages)
            )

    return _check_accessibility


# ============================================================================
# VISUAL REGRESSION CHECKING FIXTURE
# ============================================================================

@pytest.fixture(scope="function")
def visual_regression_checker(page: Page, request):
    """
    Visual regression checker for detecting UI changes.

    This fixture captures screenshots and compares them against
    baseline images to detect visual regressions.

    Args:
        page: Playwright page fixture
        request: Pytest request node

    Returns:
        callable: Function that captures and compares screenshots

    Note:
        This is a placeholder for visual regression integration.
        Actual comparison logic requires baseline storage and diff tooling.
    """
    screenshot_dir = "backend/tests/browser_discovery/screenshots/baseline"
    os.makedirs(screenshot_dir, exist_ok=True)

    def _capture_screenshot(name: str = None) -> str:
        """Capture screenshot for visual regression.

        Args:
            name: Screenshot name (defaults to test name)

        Returns:
            str: Path to captured screenshot
        """
        if name is None:
            name = request.node.name.replace("::", "_").replace("/", "_")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"{screenshot_dir}/{timestamp}_{name}.png"

        page.screenshot(path=screenshot_path, full_page=True)
        return screenshot_path

    return _capture_screenshot


# ============================================================================
# BROKEN LINK CHECKER FIXTURE
# ============================================================================

@pytest.fixture(scope="function")
def broken_link_checker(page: Page):
    """
    Broken link checker for detecting dead links and 404s.

    This fixture finds all links on the page and checks their
    HTTP status codes to detect broken links.

    Args:
        page: Playwright page fixture

    Returns:
        callable: Function that checks all links and returns broken ones

    Example:
        def test_no_broken_links(authenticated_page, broken_link_checker):
            page.goto("http://localhost:3001/dashboard")
            broken = broken_link_checker()
            assert len(broken) == 0, f"Found {len(broken)} broken links"
    """
    def _check_links() -> List[Dict[str, Any]]:
        """Check all links on page and return broken ones.

        Returns:
            List of broken links with status codes and URLs
        """
        # Find all links
        links = page.evaluate("""
        () => {
            const anchors = Array.from(document.querySelectorAll('a[href]'));
            return anchors.map(a => ({
                href: a.href,
                text: a.textContent.trim(),
                url: new URL(a.href, window.location.origin).href
            })).filter(link =>
                link.url.startsWith('http://') ||
                link.url.startsWith('https://')
            );
        }
        """)

        broken_links = []
        import requests

        for link in links:
            try:
                # Skip localhost links in test environment
                if "localhost" in link["url"] or "127.0.0.1" in link["url"]:
                    continue

                response = requests.head(link["url"], timeout=5, allow_redirects=True)
                if response.status_code >= 400:
                    broken_links.append({
                        "url": link["url"],
                        "text": link["text"],
                        "status_code": response.status_code,
                    })
            except Exception as e:
                # Link check failed (network error, timeout, etc.)
                broken_links.append({
                    "url": link["url"],
                    "text": link["text"],
                    "error": str(e),
                })

        return broken_links

    return _check_links


# ============================================================================
# INTELLIGENT UI EXPLORATION AGENT FIXTURE
# ============================================================================

@pytest.fixture(scope="function")
def exploration_agent(page: Page):
    """
    Intelligent UI exploration agent for automated bug discovery.

    This fixture provides an agent that explores the UI by clicking
    buttons, filling forms, and navigating through the application
    to discover bugs and edge cases.

    Args:
        page: Playwright page fixture

    Returns:
        ExplorationAgent: Agent instance with exploration methods

    Example:
        def test_explore_dashboard(authenticated_page, exploration_agent):
            page.goto("http://localhost:3001/dashboard")
            exploration_agent.explore(max_depth=3, max_actions=20)
            # Agent explores UI and logs bugs found
    """
    class ExplorationAgent:
        """Intelligent UI exploration agent with heuristic algorithms."""

        def __init__(self, page: Page):
            self.page = page
            self.visited_urls = set()
            self.bugs_found = []
            self.actions_taken = []

        def explore(self, max_depth: int = 3, max_actions: int = 20):
            """Explore UI using depth-first search (backward compatibility).

            Args:
                max_depth: Maximum depth to explore (default: 3)
                max_actions: Maximum number of actions to take (default: 20)
            """
            self.explore_dfs(max_depth=max_depth, max_actions=max_actions)

        def explore_dfs(self, max_depth: int = 3, max_actions: int = 20) -> List[Dict[str, Any]]:
            """Explore UI using depth-first search.

            Navigate deep into UI paths first before exploring siblings.
            This algorithm is ideal for finding bugs in nested workflows
            and form wizards (e.g., dashboard → agent → execute → results).

            Args:
                max_depth: Maximum depth to explore (default: 3)
                max_actions: Maximum number of actions to take (default: 20)

            Returns:
                List of bugs discovered during exploration
            """
            self.bugs_found = []
            self.actions_taken = []
            self._dfs_recursive(max_depth, max_actions, 0)
            return self.bugs_found

        def _dfs_recursive(self, max_depth: int, max_actions: int, current_depth: int):
            """Recursive DFS implementation with depth tracking.

            Args:
                max_depth: Maximum depth to explore
                max_actions: Maximum number of actions
                current_depth: Current exploration depth
            """
            if current_depth >= max_depth or len(self.actions_taken) >= max_actions:
                return

            current_url = self.page.url
            if current_url in self.visited_urls:
                return

            self.visited_urls.add(current_url)
            clickable = self._find_clickable_elements()

            for i, element in enumerate(clickable):
                if len(self.actions_taken) >= max_actions:
                    break

                try:
                    selector = self._build_selector(element)
                    self.page.click(selector, timeout=5000)
                    self.actions_taken.append(f"DFS depth={current_depth}: {selector}")
                    self._check_for_bugs()

                    # Recurse deeper if page changed
                    if self.page.url != current_url:
                        self._dfs_recursive(max_depth, max_actions, current_depth + 1)
                        self.page.go_back()
                        self.page.wait_for_load_state("domcontentloaded")
                except Exception as e:
                    self.bugs_found.append({
                        "type": "dfs_exploration_error",
                        "element": str(element),
                        "error": str(e),
                        "url": self.page.url,
                    })

        def explore_bfs(self, max_depth: int = 3, max_actions: int = 20) -> List[Dict[str, Any]]:
            """Explore UI using breadth-first search.

            Explore all links at current depth before going deeper.
            This algorithm is ideal for discovering all reachable pages
            and navigation bugs (e.g., explore all dashboard sections
            before diving into each).

            Args:
                max_depth: Maximum depth to explore (default: 3)
                max_actions: Maximum number of actions to take (default: 20)

            Returns:
                List of bugs discovered during exploration
            """
            self.bugs_found = []
            self.actions_taken = []
            self.visited_urls = set()

            queue = deque([(self.page.url, 0)])  # (url, depth)
            actions_count = 0

            while queue and actions_count < max_actions:
                url, depth = queue.popleft()

                if url in self.visited_urls or depth >= max_depth:
                    continue

                self.visited_urls.add(url)
                self.page.goto(url)
                self.page.wait_for_load_state("domcontentloaded")

                clickable = self._find_clickable_elements()
                for element in clickable[:max_actions - actions_count]:
                    try:
                        selector = self._build_selector(element)
                        self.page.click(selector, timeout=5000)
                        self.actions_taken.append(f"BFS depth={depth}: {selector}")
                        actions_count += 1
                        self._check_for_bugs()

                        # Add new URL to queue at next depth
                        new_url = self.page.url
                        if new_url != url and new_url not in self.visited_urls:
                            queue.append((new_url, depth + 1))
                        self.page.go_back()
                    except Exception as e:
                        self.bugs_found.append({
                            "type": "bfs_exploration_error",
                            "element": str(element),
                            "error": str(e),
                            "url": self.page.url,
                        })

            return self.bugs_found

        def explore_random(self, max_actions: int = 30, seed: int = None) -> List[Dict[str, Any]]:
            """Explore UI using random walk.

            Stochastic exploration for discovering unexpected state
            combinations and edge cases that systematic algorithms miss.
            Ideal for finding race conditions, state bugs, and unusual
            interaction sequences.

            Args:
                max_actions: Maximum number of actions to take (default: 30)
                seed: Random seed for reproducibility (default: None)

            Returns:
                List of bugs discovered during exploration
            """
            import random
            if seed is not None:
                random.seed(seed)

            self.bugs_found = []
            self.actions_taken = []
            self.visited_urls = set()

            for _ in range(max_actions):
                try:
                    clickable = self._find_clickable_elements()
                    if not clickable:
                        break

                    element = random.choice(clickable)
                    selector = self._build_selector(element)
                    self.page.click(selector, timeout=5000)
                    self.actions_taken.append(f"Random: {selector}")
                    self._check_for_bugs()

                    # 50% chance to navigate back
                    if self.page.url in self.visited_urls and random.random() < 0.5:
                        self.page.go_back()
                        self.page.wait_for_load_state("domcontentloaded")

                    self.visited_urls.add(self.page.url)
                except Exception as e:
                    self.bugs_found.append({
                        "type": "random_walk_error",
                        "error": str(e),
                        "url": self.page.url,
                    })

            return self.bugs_found

        def _find_clickable_elements(self) -> List[Dict[str, Any]]:
            """Find all clickable elements on current page.

            Returns:
                List of clickable elements with metadata (tag, type, text, id, class, href)
            """
            return self.page.evaluate("""
            () => {
                const selectors = [
                    'button:not([disabled])',
                    'a[href]',
                    'input[type="submit"]',
                    'input[type="button"]',
                    '[role="button"]',
                    '[tabindex]:not([tabindex="-1"])'
                ].join(', ');

                return Array.from(document.querySelectorAll(selectors)).map(el => ({
                    tag: el.tagName,
                    type: el.type || 'button',
                    text: (el.textContent || '').trim().substring(0, 50),
                    id: el.id || '',
                    class: el.className || '',
                    href: el.href || ''
                }));
            }
            """)

        def _build_selector(self, element: Dict[str, Any]) -> str:
            """Build CSS selector from element data.

            Args:
                element: Element metadata from _find_clickable_elements

            Returns:
                CSS selector string
            """
            if element.get('id'):
                return f"#{element['id']}"
            if element.get('class'):
                first_class = element['class'].split()[0]
                return f"{element['tag'].lower()}.{first_class}"
            if element.get('href'):
                return f"{element['tag'].lower()}[href='{element['href']}']"
            return element['tag'].lower()

        def _check_for_bugs(self):
            """Check for common bugs on current page."""
            # Check for console errors
            console_errors = self.page.evaluate("""
            () => {
                return window.__consoleErrors || [];
            }
            """)
            if console_errors:
                self.bugs_found.extend([
                    {"type": "console_error", "error": err}
                    for err in console_errors
                ])

            # Check for broken images
            broken_images = self.page.evaluate("""
            () => {
                return Array.from(document.querySelectorAll('img')).filter(img =>
                    img.naturalWidth === 0 || img.complete === false
                ).map(img => img.src);
            }
            """)
            if broken_images:
                self.bugs_found.append({
                    "type": "broken_images",
                    "sources": broken_images,
                })

        def get_bugs(self) -> List[Dict[str, Any]]:
            """Get list of bugs found during exploration.

            Returns:
                List of bugs discovered by exploration agent
            """
            return self.bugs_found

        def get_exploration_report(self) -> Dict[str, Any]:
            """Get detailed exploration report.

            Returns:
                Dictionary with exploration statistics (actions_taken, urls_visited, bugs_found)
            """
            return {
                "actions_taken": len(self.actions_taken),
                "urls_visited": len(self.visited_urls),
                "bugs_found": len(self.bugs_found),
                "actions": self.actions_taken,
                "bugs": self.bugs_found
            }

    return ExplorationAgent(page)


# ============================================================================
# PYTEST HOOKS FOR SCREENSHOT CAPTURE ON FAILURES
# ============================================================================

@pytest.fixture(autouse=True)
def track_browser_discovery_page(request):
    """
    Track page object for automatic screenshot capture on test failure.

    This autouse fixture stores a reference to the page object in the
    test node, allowing the pytest_runtest_makereport hook to capture
    screenshots when browser discovery tests fail.

    Args:
        request: Pytest request object
    """
    # Only track if page fixture is available in the test
    if hasattr(request, "funcargs"):
        page = request.funcargs.get("page") or request.funcargs.get("authenticated_page")
        if page and hasattr(request, "node"):
            request.node._page = page
    yield


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Pytest hook to capture screenshots on browser discovery test failures.

    Automatically captures screenshots on test failure and saves them
    to artifacts/screenshots/ with descriptive filenames.

    Args:
        item: Pytest test item
        call: Pytest call info

    Returns:
        Test report with outcome information
    """
    outcome = yield
    rep = outcome.get_result()

    # Store test outcome in request.node for fixtures to access
    setattr(item, "rep_" + rep.when, rep)

    # Capture screenshot on test failure
    if rep.when == "call" and rep.failed:
        # Get page fixture if available
        page = getattr(item, "_page", None)
        if page is None and hasattr(item, "funcargs"):
            page = item.funcargs.get("page") or item.funcargs.get("authenticated_page")

        if page is not None:
            # Create screenshots directory if not exists
            screenshot_dir = "backend/tests/browser_discovery/artifacts/screenshots"
            os.makedirs(screenshot_dir, exist_ok=True)

            # Generate descriptive filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            test_name = item.name.replace("::", "_").replace("/", "_")[:100]
            screenshot_path = f"{screenshot_dir}/{timestamp}_{test_name}.png"

            # Capture full page screenshot
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"\nScreenshot saved: {screenshot_path}")


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

def pytest_configure(config):
    """
    Pytest configuration hook for browser discovery tests.

    Register custom markers for browser discovery test categorization.

    Args:
        config: Pytest config object
    """
    config.addinivalue_line(
        "markers",
        "browser_discovery: Mark test as browser discovery test"
    )
    config.addinivalue_line(
        "markers",
        "accessibility: Mark test as accessibility test"
    )
    config.addinivalue_line(
        "markers",
        "visual_regression: Mark test as visual regression test"
    )
    config.addinivalue_line(
        "markers",
        "broken_links: Mark test as broken link checker"
    )
