"""
E2E UI Test Configuration with Pytest and Playwright.

This module provides pytest fixtures for Playwright browser automation
including browser context, page, and base URL configuration.
"""

import os
import shutil
import sys
from datetime import datetime

import pytest
from playwright.sync_api import BrowserContext as SyncBrowserContext

# Package-rooted artifact directories: paths are computed from THIS file so
# they work regardless of pytest's cwd (the old "backend/tests/e2e_ui/..."
# relative paths resolved against the caller's cwd and created a nested junk
# tree e2e_ui/backend/tests/e2e_ui/... when pytest ran from e2e_ui/).
E2E_UI_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_DIR = os.path.join(E2E_UI_DIR, "artifacts", "screenshots")
VIDEO_DIR = os.path.join(E2E_UI_DIR, "artifacts", "videos")
REPORT_DIR = os.path.join(E2E_UI_DIR, "reports")

# Make allure optional - only import if available
try:
    import allure
    ALLURE_AVAILABLE = True
except ImportError:
    ALLURE_AVAILABLE = False

def is_ci_environment():
    """Detect if running in CI environment."""
    return os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("GITLAB_CI") == "true"

# Import base fixtures for direct use (optional, fixtures available via plugins)
from .fixtures import auth_fixtures
from .fixtures import database_fixtures
from .fixtures import api_fixtures
from .fixtures import test_data_factory  # Factory functions module
from .fixtures import journey_fixtures  # Realistic user-journey suite fixtures

# Re-export commonly used fixtures for backward compatibility
from .fixtures.auth_fixtures import authenticated_page, authenticated_page_api, test_user, authenticated_user, admin_user
from .fixtures.database_fixtures import db_session, worker_schema, create_worker_schema, get_engine, drop_worker_schema, is_sqlite, init_db
from .fixtures.api_fixtures import setup_test_user, setup_test_project, api_client, api_base_url, test_user_data, test_project_data, test_skill_data, authenticated_api_client, setup_test_skill
from .fixtures.memory_fixtures import cdp_session
# Journey-suite fixtures must be re-exported here so pytest registers them as
# session-level fixtures (importing the module alone is not enough).
from .fixtures.journey_fixtures import (
    journey_user_credentials,
    journey_user,
    authed_page,
    journey_api_headers,
    ALL_ROLES,
    role_credentials,
    role_authed_page,
    all_role_headers,
)
# Network-simulation fixtures (slow 3G, offline, API timeout, DB drop) — same
# rule: importing the module alone does NOT register its fixtures with pytest.
from .fixtures.network_fixtures import (
    slow_3g_context,
    offline_mode_context,
    timeout_api_context,
    database_drop_simulation,
    verify_network_error,
    wait_for_network_error,
)


@pytest.fixture(scope="session")
def worker_id():
    """
    Provide worker_id for pytest-xdist compatibility.

    Returns 'master' when not running under xdist (single worker mode).

    Yields:
        str: Worker ID ('master' for single worker, 'gw0', 'gw1', etc. for xdist)
    """
    return "master"


def pytest_configure(config):
    """
    Pytest configuration hook.

    Register custom markers and configure CI-only retries.
    """
    # Register markers
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end UI test"
    )

    # Enable retries only in CI - set environment for pytest-rerunfailures
    if is_ci_environment():
        # Add --reruns to sys.argv so pytest-rerunfailures picks it up
        if "--reruns" not in sys.argv and "-r" not in sys.argv:
            reruns = os.getenv("PYTEST_RERUNS", "2")
            sys.argv.extend(["--reruns", reruns])
            print(f"\nCI environment: Enabled {reruns} retries on failure")
    else:
        print("\nLocal development: Test retries disabled (fast feedback)")


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """
    Configure browser launch arguments.

    Args:
        browser_type_launch_args: Default launch arguments from pytest-playwright

    Returns:
        Updated launch arguments with headless mode
    """
    return {
        **browser_type_launch_args,
        "headless": True,  # Run in headless mode for CI/CD
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """
    Configure browser context arguments with CI-aware video recording.

    Args:
        browser_context_args: Default context arguments from pytest-playwright

    Returns:
        Updated context arguments with accept downloads, bypass CSP, and conditional video recording
    """
    context_args = {
        **browser_context_args,
        "accept_downloads": True,
        "bypass_csp": True,  # Bypass Content Security Policy for testing
        "ignore_https_errors": True,  # Allow self-signed certificates
    }

    # Enable video recording only in CI
    if is_ci_environment():
        os.makedirs(VIDEO_DIR, exist_ok=True)
        context_args["record_video_dir"] = VIDEO_DIR

    return context_args


@pytest.fixture(scope="session", autouse=True)
def clean_allure_results():
    if ALLURE_AVAILABLE:
        allure_dir = "allure-results"
        if os.path.exists(allure_dir):
            shutil.rmtree(allure_dir)
    yield
    # Don't clean after (let user review results)


# Routes the e2e suite navigates to. Next.js dev-mode (webpack) compiles
# pages lazily on first hit — under a long suite the first navigation can
# exceed Playwright's 30s goto timeout (every historical failure cluster is
# "Page.goto: Timeout 30000ms exceeded"). Pre-warm every route once at
# session start so webpack compiles them upfront.
E2E_PREWARM_ROUTES = [
    "/dashboard", "/agents", "/chat", "/canvas", "/settings", "/search",
    "/tasks", "/boards", "/automations", "/marketplace",
    "/dashboards/projects", "/communication", "/sales", "/marketing",
    "/finance", "/analytics", "/calendar", "/integrations",
    "/documents", "/health", "/dev-status", "/dev-studio",
]


@pytest.fixture(scope="session", autouse=True)
def prewarm_frontend_routes(base_url):
    """Hit every e2e route once before the suite so webpack compiles them.

    Uses urllib (no browser) — a plain GET triggers Next's dev compilation
    and returns once compiled. Timeout per route is generous (90s) since a
    cold compile can take a while; failures are logged, never fatal (the
    backend may be mid-startup).
    """
    import urllib.error
    import urllib.request

    # Fast-fail: if the frontend isn't up, skip pre-warming entirely
    # (don't burn 23 × 90s timeouts on a down stack).
    try:
        urllib.request.urlopen(f"{base_url}/login", timeout=10).read()
    except Exception:
        print("[prewarm] frontend not reachable — skipping")
        yield
        return

    for route in E2E_PREWARM_ROUTES:
        try:
            urllib.request.urlopen(f"{base_url}{route}", timeout=90).read()
        except Exception as _pe:
            print(f"[prewarm] {route}: {type(_pe).__name__} (ignored)")
    yield


@pytest.fixture(scope="session")
def base_url():
    """
    Base URL for E2E UI tests.

    Uses port 3001 to avoid conflict with dev frontend (port 3000).

    Returns:
        str: Base URL for test application
    """
    return "http://localhost:3001"


@pytest.fixture(scope="function")
def page(browser, base_url):
    """
    Create a new page with base URL.

    Args:
        browser: Playwright browser fixture (session-scoped)
        base_url: Base URL fixture

    Yields:
        Page: Playwright page object
    """
    # Create a new browser context
    context = browser.new_context()
    page = context.new_page()

    # Set base URL for relative navigation
    page.goto(base_url)

    yield page

    # Cleanup: close page and context
    page.close()
    context.close()


@pytest.fixture(scope="function")
def screenshot_page(page, request):
    """
    Capture screenshot on test failure.

    Args:
        page: Playwright page fixture
        request: Pytest request node

    Returns:
        Page: Same page object for chaining
    """
    yield page

    # Capture screenshot if test failed
    if request.node.rep_call.failed:
        screenshot_path = f"screenshots/{request.node.name}.png"
        try:
            page.screenshot(path=screenshot_path, timeout=5000)
            print(f"\nScreenshot saved: {screenshot_path}")
        except Exception:
            pass  # never let the screenshot hook mask the real failure


@pytest.fixture(scope="function")
def video_page(browser, base_url, request):
    """
    Capture video on test failure.

    Args:
        browser: Playwright browser fixture
        base_url: Base URL fixture
        request: Pytest request node

    Yields:
        Page: Page object with video recording enabled
    """
    context = browser.new_context(record_video_dir="videos/")
    page = context.new_page()

    yield page

    # Save video if test failed
    if request.node.rep_call.failed:
        video_path = page.video.path()
        print(f"\nVideo saved: {video_path}")

    page.close()
    context.close()


@pytest.fixture(autouse=True)
def track_page_for_screenshots(request):
    """
    Track page object for automatic screenshot capture on test failure.

    This autouse fixture stores a reference to the page object in the
    test node, allowing the pytest_runtest_makereport hook to capture
    screenshots when tests fail.

    Args:
        request: Pytest request object

    Yields:
        None: Allows test to execute
    """
    # Skip tracking for unit tests marked with no_browser
    if request.node.get_closest_marker('no_browser'):
        yield
        return

    # Only track if page fixture is available in the test
    if hasattr(request, "funcargs"):
        page = request.funcargs.get("page") or request.funcargs.get("authenticated_page") or request.funcargs.get("authenticated_page_api")
        if page and hasattr(request, "node"):
            request.node._page = page
    yield


# Pytest hooks for screenshot/video capture
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Pytest hook to capture test results for screenshot/video capture.

    Automatically captures screenshots on test failure and saves them
    to artifacts/screenshots/ with descriptive filenames including timestamp
    and test name for easy debugging in CI and local development.

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
        if page is None:
            # Try to get page from function args
            if hasattr(item, "funcargs"):
                page = item.funcargs.get("page") or item.funcargs.get("authenticated_page")

        if page is not None:
            # Create screenshots directory if not exists
            os.makedirs(SCREENSHOT_DIR, exist_ok=True)

            # Generate descriptive filename. Strip bracket chars (e.g. the
            # "[chromium]" suffix Playwright adds) so the path doesn't break
            # glob-based tooling like actions/upload-artifact.
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            test_name = item.name.replace("::", "_").replace("/", "_").replace("[", "").replace("]", "")[:100]
            screenshot_path = f"{SCREENSHOT_DIR}/{timestamp}_{test_name}.png"

            # Capture full page screenshot. Bounded timeout + swallow errors:
            # under load, full-page screenshots can hang waiting for fonts
            # (TimeoutError: Page.screenshot) — a failed screenshot must
            # NEVER crash the suite or mask the real test failure.
            try:
                page.screenshot(path=screenshot_path, full_page=True, timeout=5000)
                print(f"\nScreenshot saved: {screenshot_path}")
            except Exception as _se:
                print(f"\nScreenshot capture skipped: {type(_se).__name__}")

            # Attach screenshot to Allure report
            if ALLURE_AVAILABLE:
                try:
                    allure.attach.file(
                        screenshot_path,
                        name=f"Screenshot: {item.name}",
                        attachment_type=allure.attachment_type.PNG
                    )
                except Exception as e:
                    print(f"Failed to attach screenshot to Allure: {e}")

            # Save video if in CI environment
            if is_ci_environment():
                # page.video is None when the browser context was created
                # without record_video_dir (e.g. by the journey authed_page
                # fixtures, which build their own context). Guard against that
                # so a missing video can't crash pytest's own reporting hook.
                video = getattr(page, "video", None)
                video_path = video.path() if video is not None else None
                if video_path and os.path.exists(video_path):
                    # Rename video with test name and timestamp
                    video_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    video_test_name = item.name.replace("::", "_").replace("/", "_")[:100]
                    named_video_path = f"{VIDEO_DIR}/{video_timestamp}_{video_test_name}.webm"
                    os.rename(video_path, named_video_path)
                    print(f"\nVideo saved: {named_video_path}")

                    # Attach video to Allure report
                    if ALLURE_AVAILABLE:
                        try:
                            allure.attach.file(
                                named_video_path,
                                name=f"Video: {item.name}",
                                attachment_type=allure.attachment_type.WEBM
                            )
                        except Exception as e:
                            print(f"Failed to attach video to Allure: {e}")


# ============================================================================
# Pytest-HTML Report Hooks
# ============================================================================

# Only register pytest-html hooks if the plugin is available
try:
    # Check if pytest-html is installed by importing the plugin
    import pytest_html
    PYTEST_HTML_AVAILABLE = True
except ImportError:
    PYTEST_HTML_AVAILABLE = False


if PYTEST_HTML_AVAILABLE:
    def pytest_html_results_summary(prefix, summary, postfix):
        """
        Add custom content to pytest HTML report summary.

        Args:
            prefix: List of HTML elements to insert before summary
            summary: Summary data
            postfix: List of HTML elements to insert after summary
        """
        prefix.extend([
            "<h2>Atom E2E UI Test Report</h2>",
            "<p>Generated on: {}</p>".format(
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ),
        ])


    def pytest_html_results_table_row(report, cells):
        """
        Add screenshot link to failed test rows in HTML report.

        Args:
            report: Pytest test report
            cells: List of table cells for this test row
        """
        if report.failed:
            # Check if screenshot exists
            test_name = report.nodeid.replace("::", "_").replace("/", "_")[:100]

            # Look for matching screenshot files
            if os.path.exists(SCREENSHOT_DIR):
                for filename in sorted(os.listdir(SCREENSHOT_DIR), reverse=True):
                    if test_name in filename and filename.endswith(".png"):
                        screenshot_path = os.path.join(SCREENSHOT_DIR, filename)
                        # Add screenshot cell
                        cells.append(
                            f'<td><a href="{screenshot_path}">Screenshot</a></td>'
                        )
                        break


    def pytest_html_results_table_header(cells):
        """
        Add screenshot column header to HTML report.

        Args:
            cells: List of table header cells
        """
        cells.append("<th>Screenshot</th>")
