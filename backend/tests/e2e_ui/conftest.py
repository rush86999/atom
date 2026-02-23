"""
E2E UI Test Configuration with Pytest and Playwright.

This module provides pytest fixtures for Playwright browser automation
including browser context, page, and base URL configuration.
"""

import pytest
from playwright.sync_api import BrowserContext as SyncBrowserContext

# Import auth_fixtures as a plugin for API-first authentication
pytest_plugins = ["fixtures.auth_fixtures"]


def pytest_configure(config):
    """
    Pytest configuration hook.

    Register custom markers for Playwright tests.
    """
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end UI test"
    )


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
    Configure browser context arguments.

    Args:
        browser_context_args: Default context arguments from pytest-playwright

    Returns:
        Updated context arguments with accept downloads and bypass CSP
    """
    return {
        **browser_context_args,
        "accept_downloads": True,
        "bypass_csp": True,  # Bypass Content Security Policy for testing
        "ignore_https_errors": True,  # Allow self-signed certificates
    }


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
def authenticated_page(browser, base_url):
    """
    Create an authenticated page for testing protected routes.

    This fixture should be overridden in specific test modules to
    provide authentication logic (e.g., login via UI or API token).

    Args:
        browser: Playwright browser fixture
        base_url: Base URL fixture

    Yields:
        Page: Authenticated Playwright page object
    """
    context = browser.new_context()
    page = context.new_page()

    # TODO: Implement authentication logic
    # Option 1: UI-based login (page.goto(base_url + "/login"), fill form, submit)
    # Option 2: API-based (set localStorage/cookies from API token)

    yield page

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


# Pytest hooks for screenshot/video capture
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Pytest hook to capture test results for screenshot/video capture.

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
