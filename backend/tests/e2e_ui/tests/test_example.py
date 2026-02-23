"""
Example E2E UI tests to verify Playwright setup.

This module contains minimal smoke tests to verify that Playwright
is correctly configured and can interact with the application.
"""

import pytest
from playwright.sync_api import Page


@pytest.mark.e2e
def test_homepage_loads(page: Page, base_url: str):
    """
    Test that the homepage loads successfully.

    This is a minimal smoke test to verify Playwright setup.
    It will fail if the frontend is not running, but that's expected.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    # Navigate to base URL
    page.goto(base_url)

    # Check that the page loaded (title should exist)
    title = page.title()
    assert title is not None
    assert len(title) > 0

    # Check that the page has content
    body_text = page.inner_text("body")
    assert body_text is not None


@pytest.mark.e2e
def test_browser_context_works(page: Page, base_url: str):
    """
    Test that browser context is working correctly.

    Verifies that:
    - JavaScript execution works
    - Local storage is accessible
    - Console API works

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    # Navigate to base URL
    page.goto(base_url)

    # Execute JavaScript
    result = page.evaluate("() => { return { ready: true }; }")
    assert result["ready"] is True

    # Set and get local storage
    page.evaluate("() => { localStorage.setItem('test', 'value'); }")
    value = page.evaluate("() => { return localStorage.getItem('test'); }")
    assert value == "value"

    # Clean up
    page.evaluate("() => { localStorage.removeItem('test'); }")


@pytest.mark.e2e
def test_screenshot_on_failure(page: Page, base_url: str):
    """
    Test that screenshots can be captured.

    This test intentionally captures a screenshot to verify
    the screenshot fixture is working.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    # Navigate to base URL
    page.goto(base_url)

    # Capture screenshot
    screenshot_path = "test_screenshot.png"
    page.screenshot(path=screenshot_path)

    # Verify screenshot was created (file exists)
    import os
    assert os.path.exists(screenshot_path)

    # Clean up
    os.remove(screenshot_path)


@pytest.mark.e2e
def test_page_console_logging(page: Page, base_url: str):
    """
    Test that console logging can be captured.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    # Collect console messages
    console_messages = []

    def on_console(msg):
        console_messages.append(msg.text)

    page.on("console", on_console)

    # Navigate to base URL
    page.goto(base_url)

    # Execute console.log
    page.evaluate("() => { console.log('Test message'); }")

    # Verify console message was captured
    assert any("Test message" in msg for msg in console_messages)


@pytest.mark.e2e
def test_navigation_timeout(page: Page, base_url: str):
    """
    Test that navigation timeout is configured correctly.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    # Set navigation timeout (should use 30s from config)
    page.set_default_timeout(30000)

    # Navigate to base URL
    page.goto(base_url, timeout=30000)

    # Verify page loaded
    assert page.url == base_url or page.url.startswith(base_url)


if __name__ == "__main__":
    # Run tests directly (for development)
    pytest.main([__file__, "-v", "-s"])
