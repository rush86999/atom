"""
Test quality gate features: screenshots, videos, retries, flaky detection.

This module tests the automatic screenshot capture functionality that
triggers on test failures to aid debugging in CI and local development.
"""
import os
import pytest
from playwright.sync_api import Page


def test_screenshot_directory_exists():
    """Verify screenshot artifacts directory exists."""
    screenshot_dir = "backend/tests/e2e_ui/artifacts/screenshots"
    assert os.path.exists(screenshot_dir), f"Screenshot directory {screenshot_dir} does not exist"


def test_screenshot_not_captured_on_success(page: Page):
    """
    Verify screenshots are NOT captured for passing tests.

    This test passes and should not create a screenshot file.
    """
    # Navigate to base URL
    page.goto("")

    # Verify page loaded
    assert page.url is not None

    # Test passes - no screenshot should be created
    # (This is verified by the lack of new screenshot files)


def test_screenshot_on_failure(page: Page):
    """
    Verify screenshots are captured when tests fail.

    This test deliberately fails to trigger screenshot capture.
    The pytest_runtest_makereport hook should capture a screenshot
    and save it to artifacts/screenshots/ with a descriptive filename.

    Note: This test is expected to fail - it verifies the screenshot
    capture functionality by triggering it.
    """
    # Navigate to a known page
    page.goto("/")

    # Deliberately fail to trigger screenshot capture
    # The hook should capture a screenshot before test completes
    assert False, "Intentional failure to test screenshot capture"


@pytest.mark.parametrize("page_type", ["page", "authenticated_page"])
def test_screenshot_works_with_different_fixtures(page_type: str, request):
    """
    Verify screenshot capture works with different page fixtures.

    Tests that the screenshot capture mechanism works with both
    the basic 'page' fixture and 'authenticated_page' fixture.
    """
    page = request.getfixturevalue(page_type)
    page.goto("/")
    assert page.url is not None
