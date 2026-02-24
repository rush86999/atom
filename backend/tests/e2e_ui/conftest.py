"""
E2E UI Test Configuration with Pytest and Playwright.

This module provides pytest fixtures for Playwright browser automation
including browser context, page, and base URL configuration.
"""

import os
import sys
from datetime import datetime

import pytest
from playwright.sync_api import BrowserContext as SyncBrowserContext

def is_ci_environment():
    """Detect if running in CI environment."""
    return os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("GITLAB_CI") == "true"

# Import base fixtures for direct use (optional, fixtures available via plugins)
from .fixtures.auth_fixtures import authenticated_page
from .fixtures.database_fixtures import db_session
from .fixtures.api_fixtures import setup_test_user, setup_test_project
from .fixtures import test_data_factory  # Factory functions module


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
        video_dir = "backend/tests/e2e_ui/artifacts/videos"
        os.makedirs(video_dir, exist_ok=True)
        context_args["record_video_dir"] = video_dir

    return context_args


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
        page.screenshot(path=screenshot_path)
        print(f"\nScreenshot saved: {screenshot_path}")


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
def track_page_for_screenshots(request, page):
    """
    Track page object for automatic screenshot capture on test failure.

    This autouse fixture stores a reference to the page object in the
    test node, allowing the pytest_runtest_makereport hook to capture
    screenshots when tests fail.

    Args:
        request: Pytest request object
        page: Playwright page fixture

    Yields:
        None: Allows test to execute
    """
    # Skip tracking for unit tests marked with no_browser
    if request.node.get_closest_marker('no_browser'):
        yield
        return

    if hasattr(request, "node"):
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
            screenshot_dir = "backend/tests/e2e_ui/artifacts/screenshots"
            os.makedirs(screenshot_dir, exist_ok=True)

            # Generate descriptive filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            test_name = item.name.replace("::", "_").replace("/", "_")[:100]
            screenshot_path = f"{screenshot_dir}/{timestamp}_{test_name}.png"

            # Capture full page screenshot
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"\nScreenshot saved: {screenshot_path}")

            # Save video if in CI environment
            if is_ci_environment():
                video_path = page.video.path()
                if video_path and os.path.exists(video_path):
                    # Rename video with test name and timestamp
                    video_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    video_test_name = item.name.replace("::", "_").replace("/", "_")[:100]
                    named_video_path = f"backend/tests/e2e_ui/artifacts/videos/{video_timestamp}_{video_test_name}.webm"
                    os.rename(video_path, named_video_path)
                    print(f"\nVideo saved: {named_video_path}")


# ============================================================================
# Pytest-HTML Report Hooks
# ============================================================================

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
        screenshot_dir = "backend/tests/e2e_ui/artifacts/screenshots"
        test_name = report.nodeid.replace("::", "_").replace("/", "_")[:100]

        # Look for matching screenshot files
        if os.path.exists(screenshot_dir):
            for filename in sorted(os.listdir(screenshot_dir), reverse=True):
                if test_name in filename and filename.endswith(".png"):
                    screenshot_path = os.path.join(screenshot_dir, filename)
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
