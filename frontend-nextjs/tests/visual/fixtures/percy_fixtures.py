"""
Percy visual regression testing fixtures for pytest-playwright.

This module provides pytest fixtures for Percy visual regression testing
including browser setup, snapshot helpers, and authenticated sessions.
"""

import os
from typing import List, Optional, Dict, Any
from playwright.sync_api import Page, BrowserContext
import pytest


# Percy snapshot helper function
def percy_snapshot(
    page: Page,
    name: str,
    widths: Optional[List[int]] = None,
    ignore_regions: Optional[List[Dict[str, Any]]] = None,
    custom_css: Optional[str] = None
):
    """
    Take a Percy visual snapshot with optional configuration.

    Args:
        page: Playwright page object
        name: Snapshot name for identification in Percy dashboard
        widths: Optional list of viewport widths (default: [375, 768, 1280])
        ignore_regions: Optional list of regions to ignore (x, y, width, height)
        custom_css: Optional custom CSS to apply before snapshot

    Example:
        >>> percy_snapshot(page, "Login Page")
        >>> percy_snapshot(page, "Dashboard", widths=[1280])
        >>> percy_snapshot(page, "Chart", ignore_regions=[{"x": 0, "y": 0, "width": 200, "height": 50}])
    """
    # Import Percy only when needed (lazy import for faster test startup)
    try:
        from percy import percySnapshot
    except ImportError:
        print(f"Percy not available, skipping snapshot: {name}")
        print("Install Percy: npm install -g @percy/cli")
        return

    # Build snapshot options
    options: Dict[str, Any] = {}

    if widths:
        options["widths"] = widths
    if ignore_regions:
        options["ignore"] = ignore_regions
    if custom_css:
        options["customCss"] = custom_css

    # Take snapshot
    if options:
        percySnapshot(page, name, **options)
    else:
        percySnapshot(page, name)

    # Log for debugging
    widths_str = ", ".join(map(str, widths)) if widths else "default"
    print(f"✓ Percy snapshot taken: {name} (widths: {widths_str})")


@pytest.fixture(scope="function")
def percy_page(browser_name: str, browser_type_launch_args, browser_context_args) -> Page:
    """
    Create a Playwright page with Percy enabled for visual regression testing.

    This fixture provides a fresh page object for each test function.
    The page is automatically closed after the test.

    Args:
        browser_name: Browser name from pytest-playwright (chromium, firefox, webkit)
        browser_type_launch_args: Browser launch arguments
        browser_context_args: Browser context arguments

    Yields:
        Page: Playwright page object ready for Percy snapshots

    Example:
        >>> def test_visual_login(percy_page):
        ...     percy_page.goto("http://localhost:3000/login")
        ...     percy_snapshot(percy_page, "Login Page")
    """
    from playwright.sync_api import sync_playwright

    # Use pytest-playwright's browser fixture
    # This will be injected by pytest-playwright
    from pytest_playwright_fixtures import browser

    # Create new context and page
    context: BrowserContext = browser.new_context(**browser_context_args)
    page: Page = context.new_page()

    yield page

    # Cleanup
    page.close()
    context.close()


@pytest.fixture(scope="function")
def authenticated_percy_page(percy_page: Page, api_base_url: str, test_user_data: Dict[str, Any]) -> Page:
    """
    Create an authenticated Playwright page for visual regression testing.

    This fixture logs in a test user via API (faster than UI login)
    and returns a page with an authenticated session.

    Args:
        percy_page: Playwright page from percy_page fixture
        api_base_url: API base URL
        test_user_data: Test user credentials dict (email, password)

    Yields:
        Page: Authenticated Playwright page ready for Percy snapshots

    Example:
        >>> def test_visual_dashboard(authenticated_percy_page):
        ...     authenticated_percy_page.goto("http://localhost:3000/dashboard")
        ...     percy_snapshot(authenticated_percy_page, "Dashboard")
    """
    # Login via API for faster setup
    import requests

    login_url = f"{api_base_url}/auth/login"
    login_data = {
        "email": test_user_data.get("email", "test@example.com"),
        "password": test_user_data.get("password", "testpass123")
    }

    try:
        response = requests.post(login_url, json=login_data)
        if response.status_code == 200:
            # Set authentication cookie
            token = response.json().get("token", response.json().get("access_token"))
            if token:
                percy_page.evaluate(f"""
                    () => {{
                        localStorage.setItem('token', '{token}');
                        localStorage.setItem('authenticated', 'true');
                    }}
                """)
                print(f"✓ User authenticated via API: {login_data['email']}")
        else:
            print(f"⚠ API login failed: {response.status_code}, using UI fallback")
            # Fallback: try UI login
            percy_page.goto("http://localhost:3000/login")
            percy_page.fill("input[name='email']", login_data["email"])
            percy_page.fill("input[name='password']", login_data["password"])
            percy_page.click("button[type='submit']")
            percy_page.wait_for_url("**/dashboard**", timeout=5000)
    except Exception as e:
        print(f"⚠ API login error: {e}, using UI fallback")
        # Fallback: try UI login
        percy_page.goto("http://localhost:3000/login")
        percy_page.fill("input[name='email']", login_data["email"])
        percy_page.fill("input[name='password']", login_data["password"])
        percy_page.click("button[type='submit']")
        percy_page.wait_for_url("**/dashboard**", timeout=5000)

    yield percy_page


@pytest.fixture(scope="function")
def percy_test_data(authenticated_percy_page: Page, api_base_url: str) -> Dict[str, Any]:
    """
    Create test data for visual regression testing.

    This fixture creates test agents, canvas, and workflows for visual tests.
    Test data is automatically cleaned up after the test.

    Args:
        authenticated_percy_page: Authenticated page with session
        api_base_url: API base URL for creating test data

    Yields:
        Dict: Test data containing agent_ids, canvas_ids, workflow_ids

    Example:
        >>> def test_visual_agents_list(authenticated_percy_page, percy_test_data):
        ...     percy_test_data["agent_ids"]  # List of created agent IDs
        ...     percy_test_data["canvas_ids"]  # List of created canvas IDs
    """
    import requests
    import uuid

    test_data = {
        "agent_ids": [],
        "canvas_ids": [],
        "workflow_ids": [],
        "cleanup_ids": []
    }

    # Get auth token from localStorage
    token = authenticated_percy_page.evaluate("() => localStorage.getItem('token')")
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        # Create test agent
        agent_data = {
            "name": f"Visual Test Agent {uuid.uuid4().hex[:8]}",
            "description": "Agent for visual regression testing",
            "system_prompt": "You are a helpful assistant for visual testing.",
            "maturity_level": "AUTONOMOUS"
        }

        response = requests.post(f"{api_base_url}/agents", json=agent_data, headers=headers)
        if response.status_code == 200:
            agent_id = response.json().get("id")
            test_data["agent_ids"].append(agent_id)
            test_data["cleanup_ids"].append(("agent", agent_id))
            print(f"✓ Created test agent: {agent_id}")

        # Create test canvas (chart)
        canvas_data = {
            "title": f"Visual Test Canvas {uuid.uuid4().hex[:8]}",
            "canvas_type": "chart",
            "content": {
                "chart_type": "line",
                "data": {
                    "labels": ["Jan", "Feb", "Mar", "Apr"],
                    "datasets": [{
                        "label": "Test Data",
                        "data": [10, 20, 30, 40]
                    }]
                }
            }
        }

        response = requests.post(f"{api_base_url}/canvas", json=canvas_data, headers=headers)
        if response.status_code == 200:
            canvas_id = response.json().get("id")
            test_data["canvas_ids"].append(canvas_id)
            test_data["cleanup_ids"].append(("canvas", canvas_id))
            print(f"✓ Created test canvas: {canvas_id}")

    except Exception as e:
        print(f"⚠ Failed to create test data: {e}")

    yield test_data

    # Cleanup test data
    print("\n🧹 Cleaning up visual test data...")
    for resource_type, resource_id in test_data.get("cleanup_ids", []):
        try:
            delete_url = f"{api_base_url}/{resource_type}s/{resource_id}"
            requests.delete(delete_url, headers=headers, timeout=5000)
            print(f"✓ Deleted {resource_type}: {resource_id}")
        except Exception as e:
            print(f"⚠ Failed to delete {resource_type} {resource_id}: {e}")


@pytest.fixture(scope="session")
def perci_token() -> Optional[str]:
    """
    Provide Percy token for visual regression testing.

    The PERCY_TOKEN environment variable should be set in CI/CD or locally.

    Returns:
        str: Percy token if available, None otherwise

    Example:
        >>> def test_needs_perci(perci_token):
        ...     if not perci_token:
        ...         pytest.skip("PERCY_TOKEN not set")
    """
    return os.getenv("PERCY_TOKEN")


@pytest.fixture(scope="session", autouse=True)
def verify_percy_setup(perci_token: Optional[str]) -> None:
    """
    Verify Percy setup before running visual tests.

    This fixture runs automatically before all visual tests.
    It warns if PERCY_TOKEN is not set (snapshots will be skipped).

    Args:
        perci_token: Percy token from environment variable
    """
    if not perci_token:
        print("\n⚠️  WARNING: PERCY_TOKEN not set")
        print("   Visual snapshots will be SKIPPED")
        print("   Set token: export PERCY_TOKEN=your_token_here")
        print("   Get token: https://percy.io/settings/api_tokens\n")
    else:
        print("\n✅ Percy enabled: Visual snapshots will be uploaded\n")
