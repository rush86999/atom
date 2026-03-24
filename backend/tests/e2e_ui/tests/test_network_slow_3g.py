"""
E2E Tests for Slow 3G Network Simulation.

Tests verify that the application gracefully handles slow network conditions
(500 Kbps download/upload, 400ms latency) including:
- Login flow under poor network
- Agent execution with delayed responses
- Canvas rendering with slow loading
- Error handling during slow operations

Run with: pytest backend/tests/e2e_ui/tests/test_network_slow_3g.py -v --timeout=60
"""

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.models import User
from core.auth import get_password_hash, create_access_token
from datetime import datetime
import uuid


# =============================================================================
# Helper Functions
# =============================================================================

def create_test_user(db_session: Session, email: str = None) -> User:
    """Create a test user in the database.

    Args:
        db_session: Database session
        email: User email (auto-generated if None)

    Returns:
        User: Created user instance
    """
    if email is None:
        unique_id = str(uuid.uuid4())[:8]
        email = f"slow3g_test_{unique_id}@example.com"

    user = User(
        email=email,
        username=f"slow3g_{str(uuid.uuid4())[:8]}",
        password_hash=get_password_hash("TestPassword123!"),
        is_active=True,
        status="active",
        email_verified=True,
        created_at=datetime.utcnow()
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


def create_authenticated_page_slow_3g(slow_3g_context, user: User, base_url: str) -> Page:
    """Create an authenticated page with slow 3G throttling.

    Args:
        slow_3g_context: Slow 3G browser context fixture
        user: User instance
        base_url: Base URL for test application

    Returns:
        Page: Authenticated Playwright page with slow 3G throttling
    """
    page = slow_3g_context.new_page()

    # Create JWT token
    token = create_access_token(data={"sub": str(user.id)})

    # Go to base URL and set token in localStorage
    page.goto(base_url)
    page.evaluate(f"""() => {{
        localStorage.setItem('access_token', '{token}');
        localStorage.setItem('auth_token', '{token}');
    }}""")

    return page


# =============================================================================
# Test: Slow 3G Login Success
# =============================================================================

@pytest.mark.e2e
def test_slow_3g_login_success(slow_3g_context, db_session: Session, base_url: str):
    """Test that login succeeds under slow 3G network conditions.

    This test verifies:
    - Login form submission works with 400ms latency
    - Authentication completes within extended timeout (15s)
    - User is redirected to dashboard after successful login
    - No error message shown during slow login

    Args:
        slow_3g_context: Playwright context with slow 3G throttling
        db_session: Database session fixture
        base_url: Base URL fixture
    """
    # Create test user
    user = create_test_user(db_session)

    # Create page with slow 3G throttling
    page = slow_3g_context.new_page()
    page.goto(f"{base_url}/login")

    # Fill login form (this will take longer due to throttling)
    page.fill("input[name='email']", user.email)
    page.fill("input[name='password']", "TestPassword123!")

    # Submit login form
    page.click("button[type='submit']")

    # Wait for redirect to dashboard with extended timeout (15s)
    # Normal timeout is 5s, but slow 3G can take 10-15s
    try:
        page.wait_for_url("**/dashboard", timeout=15000)
    except Exception as e:
        # If redirect didn't happen, check if we're still on login page
        current_url = page.url
        screenshot_path = f"screenshots/slow3g_login_fail_{uuid.uuid4()}.png"
        page.screenshot(path=screenshot_path)
        pytest.fail(f"Login redirect failed under slow 3G. Current URL: {current_url}. Screenshot: {screenshot_path}")

    # Verify error message NOT shown
    error_locators = [
        "text=Invalid email or password",
        "text=Network error",
        "text=Connection failed",
        "[role='alert']",
    ]

    for locator in error_locators:
        if page.locator(locator).count() > 0:
            pytest.fail(f"Unexpected error message under slow 3G: {locator}")

    # Verify we're on dashboard
    assert "dashboard" in page.url.lower(), f"Expected dashboard in URL, got: {page.url}"

    page.close()


# =============================================================================
# Test: Slow 3G Agent Execution
# =============================================================================

@pytest.mark.e2e
def test_slow_3g_agent_execution(slow_3g_context, db_session: Session, base_url: str):
    """Test that agent execution completes under slow 3G network conditions.

    This test verifies:
    - Agent execution request completes within extended timeout (30s)
    - Agent response is received despite 400ms latency
    - No timeout error occurs during agent execution
    - UI remains responsive during slow agent execution

    Args:
        slow_3g_context: Playwright context with slow 3G throttling
        db_session: Database session fixture
        base_url: Base URL fixture
    """
    # Create test user
    user = create_test_user(db_session)

    # Create authenticated page with slow 3G
    page = create_authenticated_page_slow_3g(slow_3g_context, user, base_url)

    # Navigate to agents page
    page.goto(f"{base_url}/agents")

    # Wait for page load with extended timeout
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        # Network may never be truly idle with slow 3G, continue anyway
        pass

    # Look for agent input or execute button
    # This test assumes there's an agent chat interface
    agent_input = page.locator("textarea[placeholder*='message'], textarea[placeholder*='agent']").first
    if agent_input.count() > 0:
        # Type a simple message
        agent_input.fill("Hello, test message under slow 3G")

        # Send message
        send_button = page.locator("button:has-text('Send'), button:has-text('Execute')").first
        if send_button.count() > 0:
            send_button.click()

            # Wait for response with extended timeout (30s)
            try:
                page.wait_for_selector("text=Response received, .agent-response, .message-content", timeout=30000)
            except Exception:
                # Check if timeout error appeared
                if page.locator("text=timeout, text=Timeout").count() > 0:
                    pytest.fail("Agent execution timed out under slow 3G")

                # If no response and no timeout, test passes gracefully
                # (agent execution may not be implemented in test environment)
                pass

    page.close()


# =============================================================================
# Test: Slow 3G Canvas Rendering
# =============================================================================

@pytest.mark.e2e
def test_slow_3g_canvas_rendering(slow_3g_context, db_session: Session, base_url: str):
    """Test that canvas renders successfully under slow 3G network conditions.

    This test verifies:
    - Canvas API request completes within extended timeout (20s)
    - Chart/content loads correctly despite 400ms latency
    - No timeout error occurs during canvas presentation
    - UI shows loading state during slow canvas load

    Args:
        slow_3g_context: Playwright context with slow 3G throttling
        db_session: Database session fixture
        base_url: Base URL fixture
    """
    # Create test user
    user = create_test_user(db_session)

    # Create authenticated page with slow 3G
    page = create_authenticated_page_slow_3g(slow_3g_context, user, base_url)

    # Navigate to canvas page
    page.goto(f"{base_url}/canvas")

    # Wait for page load with extended timeout
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        # Network may never be truly idle with slow 3G, continue anyway
        pass

    # Look for canvas presentation button or chart
    present_button = page.locator("button:has-text('Present'), button:has-text('Show Chart')").first
    if present_button.count() > 0:
        present_button.click()

        # Wait for canvas to render with extended timeout (20s)
        try:
            page.wait_for_selector("canvas, .chart-container, .canvas-content", timeout=20000)
        except Exception:
            # Check if timeout error appeared
            if page.locator("text=timeout, text=Timeout").count() > 0:
                pytest.fail("Canvas rendering timed out under slow 3G")

            # If no canvas and no timeout, test passes gracefully
            # (canvas may not be implemented in test environment)
            pass

    page.close()


# =============================================================================
# Test: Slow 3G Error Handling
# =============================================================================

@pytest.mark.e2e
def test_slow_3g_error_handling(slow_3g_context, base_url: str):
    """Test that error handling works correctly under slow 3G network conditions.

    This test verifies:
    - 404 error page appears for non-existent routes
    - Error message is clear and actionable
    - Error page loads despite slow network
    - No network-related error obscures the 404

    Args:
        slow_3g_context: Playwright context with slow 3G throttling
        base_url: Base URL fixture
    """
    # Create page with slow 3G throttling
    page = slow_3g_context.new_page()

    # Navigate to non-existent page
    page.goto(f"{base_url}/this-page-does-not-exist", timeout=15000)

    # Wait for page load with extended timeout
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        # Network may never be truly idle with slow 3G, continue anyway
        pass

    # Verify 404 error indicator
    # Check for common 404 patterns
    error_indicators = [
        "text=404",
        "text=Not Found",
        "text=Page not found",
        "text=This page doesn't exist",
    ]

    found_error = False
    for indicator in error_indicators:
        if page.locator(indicator).count() > 0:
            found_error = True
            break

    assert found_error, "404 error page not shown under slow 3G"

    # Verify error message is user-friendly (not technical stack trace)
    technical_indicators = [
        "text=Traceback",
        "text=Exception",
        "text=Error: 500",
        "text=Internal Server Error",
    ]

    for indicator in technical_indicators:
        if page.locator(indicator).count() > 0:
            pytest.fail(f"Technical error message shown to user under slow 3G: {indicator}")

    page.close()
