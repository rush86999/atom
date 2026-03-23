"""
Shared utility functions for E2E and integration tests.

Provides common helpers to reduce test code duplication and ensure
consistent behavior across all test suites.
"""
from typing import Optional, Callable
from playwright.sync_api import Page, Locator


async def wait_for_selector(
    page: Page,
    selector: str,
    timeout: int = 5000,
    state: str = "visible"
) -> Locator:
    """Wait for selector to reach specified state.

    Args:
        page: Playwright page object
        selector: CSS selector (prefer data-testid)
        timeout: Milliseconds to wait
        state: One of: attached, detached, visible, hidden

    Returns:
        Locator for the matched element

    Raises:
        TimeoutError: If selector not found within timeout

    Example:
        wait_for_selector(page, "[data-testid='agent-card']")
    """
    locator = page.locator(selector)
    locator.wait_for(state=state, timeout=timeout)
    return locator


async def click_element(
    page: Page,
    selector: str,
    timeout: int = 5000
) -> None:
    """Click element with selector.

    Args:
        page: Playwright page object
        selector: CSS selector (prefer data-testid)
        timeout: Milliseconds to wait before clicking

    Example:
        await click_element(page, "[data-testid='submit-button']")
    """
    wait_for_selector(page, selector, timeout=timeout)
    page.click(selector)


async def fill_input(
    page: Page,
    selector: str,
    value: str,
    timeout: int = 5000
) -> None:
    """Fill input field with value.

    Args:
        page: Playwright page object
        selector: CSS selector (prefer data-testid)
        value: Value to fill
        timeout: Milliseconds to wait before filling

    Example:
        await fill_input(page, "[data-testid='email-input']", "test@example.com")
    """
    wait_for_selector(page, selector, timeout=timeout)
    page.fill(selector, value)


async def wait_for_text(
    page: Page,
    selector: str,
    text: str,
    timeout: int = 5000
) -> None:
    """Wait for element to contain specific text.

    Args:
        page: Playwright page object
        selector: CSS selector (prefer data-testid)
        text: Text to wait for
        timeout: Milliseconds to wait

    Example:
        await wait_for_text(page, "[data-testid='status']", "Complete")
    """
    locator = page.locator(selector)
    locator.wait_for(state="visible", timeout=timeout)
    locator.wait_for("has_text", text, timeout=timeout)


def get_test_id(test_id: str) -> str:
    """Generate data-testid selector.

    Args:
        test_id: Test ID value (e.g., "submit-button")

    Returns:
        CSS selector for data-testid

    Example:
        get_test_id("submit-button")  # "[data-testid='submit-button']"
    """
    return f"[data-testid='{test_id}']"
