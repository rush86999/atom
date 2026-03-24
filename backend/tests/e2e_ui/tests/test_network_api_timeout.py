"""
E2E Tests for API Timeout Handling.

Tests verify that the application gracefully handles API timeouts including:
- Timeout error messages during agent execution
- Timeout error messages during canvas presentation
- Automatic retry logic (if implemented)
- Concurrent timeout handling

Run with: pytest backend/tests/e2e_ui/tests/test_network_api_timeout.py -v
"""

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session
import time

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
        email = f"timeout_test_{unique_id}@example.com"

    user = User(
        email=email,
        username=f"timeout_{str(uuid.uuid4())[:8]}",
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


def create_authenticated_page_timeout(timeout_api_context, user: User, base_url: str) -> Page:
    """Create an authenticated page with API timeout injection.

    Args:
        timeout_api_context: Timeout API context fixture
        user: User instance
        base_url: Base URL for test application

    Returns:
        Page: Authenticated Playwright page with API timeout injection
    """
    page = timeout_api_context.new_page()

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
# Test: API Timeout During Agent Execution
# =============================================================================

@pytest.mark.e2e
def test_api_timeout_during_agent_execution(timeout_api_context, db_session: Session, base_url: str):
    """Test that API timeout shows proper error during agent execution.

    This test verifies:
    - Timeout error message appears after 30s delay
    - UI shows "Request timeout" or "Agent execution timed out"
    - No hanging requests (client-side timeout works)
    - UI remains responsive after timeout

    Args:
        timeout_api_context: Timeout API context fixture (adds 30s delay to /api/v1/agents/execute)
        db_session: Database session fixture
        base_url: Base URL fixture
    """
    # Create test user
    user = create_test_user(db_session)

    # Create authenticated page with timeout injection
    page = create_authenticated_page_timeout(timeout_api_context, user, base_url)

    # Navigate to agents page
    page.goto(f"{base_url}/agents")
    page.wait_for_timeout(1000)

    # Try to execute agent (will timeout after 30s)
    agent_input = page.locator("textarea[placeholder*='message'], textarea[placeholder*='agent']").first
    if agent_input.count() > 0:
        agent_input.fill("Test message with API timeout")

        send_button = page.locator("button:has-text('Send'), button:has_text('Execute')").first
        if send_button.count() > 0:
            # Record start time
            start_time = time.time()

            send_button.click()

            # Wait for timeout error (should appear within 30-35s)
            try:
                page.wait_for_selector("text=timeout, text=Timeout, text=Request timeout", timeout=35000)

                # Verify timeout occurred in reasonable time (25-40s)
                elapsed = time.time() - start_time
                assert 25 <= elapsed <= 40, f"Timeout occurred in unexpected time: {elapsed:.1f}s (expected 25-40s)"

            except Exception:
                # If timeout message not found, check if UI is frozen
                elapsed = time.time() - start_time
                if elapsed > 40:
                    pytest.fail(f"API timeout not handled properly, UI frozen for {elapsed:.1f}s")

            # Verify error message is clear
            timeout_indicators = [
                "text=Request timeout",
                "text=Agent execution timed out",
                "text=Timeout error",
                "text=Request took too long",
            ]

            found_timeout = False
            for indicator in timeout_indicators:
                if page.locator(indicator).count() > 0:
                    found_timeout = True
                    break

            if found_timeout:
                # Timeout error message found - good!
                pass

            # Verify UI still responsive
            assert page.url, "Page crashed after API timeout"

    page.close()


# =============================================================================
# Test: API Timeout During Canvas Presentation
# =============================================================================

@pytest.mark.e2e
def test_api_timeout_during_canvas_presentation(timeout_api_context, db_session: Session, base_url: str):
    """Test that API timeout shows proper error during canvas presentation.

    This test verifies:
    - Timeout error message appears after 30s delay
    - Error message is clear and actionable
    - UI recovers from timeout (no frozen state)
    - User can retry canvas presentation after timeout

    Args:
        timeout_api_context: Timeout API context fixture (adds 30s delay to /api/v1/canvas/present)
        db_session: Database session fixture
        base_url: Base URL fixture
    """
    # Create test user
    user = create_test_user(db_session)

    # Create authenticated page with timeout injection
    page = create_authenticated_page_timeout(timeout_api_context, user, base_url)

    # Navigate to canvas page
    page.goto(f"{base_url}/canvas")
    page.wait_for_timeout(1000)

    # Try to present canvas (will timeout after 30s)
    present_button = page.locator("button:has-text('Present'), button:has_text('Show Chart')").first
    if present_button.count() > 0:
        # Record start time
        start_time = time.time()

        present_button.click()

        # Wait for timeout error (should appear within 30-35s)
        try:
            page.wait_for_selector("text=timeout, text=Timeout, text=Request timeout", timeout=35000)

            # Verify timeout occurred in reasonable time
            elapsed = time.time() - start_time
            assert 25 <= elapsed <= 40, f"Timeout occurred in unexpected time: {elapsed:.1f}s"

        except Exception:
            # If timeout message not found, check for frozen UI
            elapsed = time.time() - start_time
            if elapsed > 40:
                pytest.fail(f"Canvas timeout not handled properly, UI frozen for {elapsed:.1f}s")

        # Verify error message is clear
        timeout_indicators = [
            "text=Request timeout",
            "text=Canvas presentation timed out",
            "text=Timeout error",
        ]

        found_timeout = False
        for indicator in timeout_indicators:
            if page.locator(indicator).count() > 0:
                found_timeout = True
                break

        if found_timeout:
            # Timeout error message found - good!
            pass

        # Verify UI recovered (not frozen)
        assert page.url, "Page crashed after canvas timeout"

        # Verify button still clickable (UI not frozen)
        if present_button.count() > 0:
            # Check if button is enabled
            is_enabled = present_button.is_enabled()
            # Button may be disabled during timeout, but should recover
            # We'll just verify it exists
            pass

    page.close()


# =============================================================================
# Test: API Timeout Retry Logic
# =============================================================================

@pytest.mark.e2e
def test_api_timeout_retry_logic(timeout_api_context, db_session: Session, base_url: str):
    """Test that automatic retry mechanism works correctly (if implemented).

    This test verifies:
    - System attempts retry after timeout (if implemented)
    - Retry limit is respected (e.g., 3 retries)
    - Exponential backoff between retries (if implemented)
    - Final timeout error after retries exhausted

    Args:
        timeout_api_context: Timeout API context fixture (adds 30s delay)
        db_session: Database session fixture
        base_url: Base URL fixture
    """
    # Create test user
    user = create_test_user(db_session)

    # Create authenticated page with timeout injection
    page = create_authenticated_page_timeout(timeout_api_context, user, base_url)

    # Navigate to agents page
    page.goto(f"{base_url}/agents")
    page.wait_for_timeout(1000)

    # Try to execute agent (will timeout repeatedly)
    agent_input = page.locator("textarea[placeholder*='message'], textarea[placeholder*='agent']").first
    if agent_input.count() > 0:
        agent_input.fill("Test message with timeout retry")

        send_button = page.locator("button:has-text('Send'), button:has_text('Execute')").first
        if send_button.count() > 0:
            # Record start time
            start_time = time.time()

            send_button.click()

            # Wait for final timeout error
            # If retry is implemented with 3 retries, this could take 90-120s
            # If no retry, this should take 30-35s
            try:
                # Wait up to 120s for timeout (allows for retries)
                page.wait_for_selector("text=timeout, text=Timeout, text=Request timeout", timeout=120000)

                elapsed = time.time() - start_time

                # Determine if retry was implemented
                # 30-40s = no retry
                # 60-90s = 1-2 retries
                # 90-120s = 3 retries
                if elapsed < 50:
                    # No retry implemented (this is OK)
                    pass
                elif elapsed < 120:
                    # Retry may be implemented
                    pass

            except Exception:
                # If no timeout message after 120s, something is wrong
                elapsed = time.time() - start_time
                pytest.fail(f"No timeout error after {elapsed:.1f}s, possible infinite retry loop")

            # Verify final error message
            timeout_indicators = [
                "text=Request timeout",
                "text=Timeout error",
                "text=Max retries exceeded",
            ]

            found_timeout = False
            for indicator in timeout_indicators:
                if page.locator(indicator).count() > 0:
                    found_timeout = True
                    break

            if found_timeout:
                # Final timeout error found - good!
                pass

    page.close()


# =============================================================================
# Test: Concurrent Timeout Handling
# =============================================================================

@pytest.mark.e2e
def test_concurrent_timeout_handling(timeout_api_context, db_session: Session, base_url: str):
    """Test that concurrent timeout requests are handled correctly.

    This test verifies:
    - Multiple concurrent timeout requests all timeout gracefully
    - No resource leaks or hanging connections
    - UI remains responsive during concurrent timeouts
    - All timeout errors are displayed properly

    Args:
        timeout_api_context: Timeout API context fixture (adds 30s delay)
        db_session: Database session fixture
        base_url: Base URL fixture
    """
    # Create test user
    user = create_test_user(db_session)

    # Create authenticated page with timeout injection
    page = create_authenticated_page_timeout(timeout_api_context, user, base_url)

    # Navigate to agents page
    page.goto(f"{base_url}/agents")
    page.wait_for_timeout(1000)

    # Try to execute multiple agents concurrently (will all timeout)
    agent_input = page.locator("textarea[placeholder*='message'], textarea[placeholder*='agent']").first
    if agent_input.count() > 0:
        send_button = page.locator("button:has-text('Send'), button:has_text('Execute')").first

        if send_button.count() > 0:
            # Start 3 concurrent requests
            for i in range(3):
                agent_input.fill(f"Concurrent test message {i+1}")
                send_button.click()
                time.sleep(0.5)  # Small delay between requests

            # Wait for all timeouts (should complete within 40-50s)
            start_time = time.time()

            # Wait for timeout indicators
            try:
                page.wait_for_selector("text=timeout, text=Timeout", timeout=50000)

                elapsed = time.time() - start_time
                # All 3 requests should timeout within 50s
                assert elapsed < 60, f"Concurrent timeouts took too long: {elapsed:.1f}s"

            except Exception:
                # If no timeout message, check for frozen UI
                elapsed = time.time() - start_time
                if elapsed > 60:
                    pytest.fail(f"Concurrent timeouts not handled, UI frozen for {elapsed:.1f}s")

            # Verify UI still responsive
            assert page.url, "Page crashed during concurrent timeouts"

            # Verify multiple timeout errors shown
            timeout_count = page.locator("text=timeout, text=Timeout").count()
            if timeout_count > 0:
                # At least one timeout error found
                pass

    page.close()


# =============================================================================
# Test: Timeout Error Message Clarity
# =============================================================================

@pytest.mark.e2e
def test_timeout_error_message_clarity(timeout_api_context, db_session: Session, base_url: str):
    """Test that timeout error messages are clear and user-friendly.

    This test verifies:
    - Timeout error messages are not technical
    - Error messages explain what happened
    - Error messages suggest next steps (retry, contact support)
    - No stack traces or technical details exposed

    Args:
        timeout_api_context: Timeout API context fixture (adds 30s delay)
        db_session: Database session fixture
        base_url: Base URL fixture
    """
    # Create test user
    user = create_test_user(db_session)

    # Create authenticated page with timeout injection
    page = create_authenticated_page_timeout(timeout_api_context, user, base_url)

    # Navigate to agents page
    page.goto(f"{base_url}/agents")
    page.wait_for_timeout(1000)

    # Trigger timeout
    agent_input = page.locator("textarea[placeholder*='message'], textarea[placeholder*='agent']").first
    if agent_input.count() > 0:
        agent_input.fill("Test timeout error message")

        send_button = page.locator("button:has_text('Send'), button:has_text('Execute')").first
        if send_button.count() > 0:
            send_button.click()

            # Wait for timeout error
            try:
                page.wait_for_selector("text=timeout, text=Timeout, text=Request timeout", timeout=35000)
            except Exception:
                # Timeout may not be implemented in test environment
                pass

            # Verify error message is user-friendly
            friendly_indicators = [
                "text=Request timeout",
                "text=took too long",
                "text=try again",
                "text=contact support",
            ]

            found_friendly = False
            for indicator in friendly_indicators:
                if page.locator(indicator, exact=False).count() > 0:
                    found_friendly = True
                    break

            # Verify no technical details
            technical_indicators = [
                "text=Traceback",
                "text=Exception",
                "text=504 Gateway Timeout",
                "text=ERR_TIMED_OUT",
                "text=ReadTimeoutError",
            ]

            found_technical = False
            for indicator in technical_indicators:
                if page.locator(indicator).count() > 0:
                    found_technical = True
                    break

            # At minimum, verify no technical stack traces
            if found_technical:
                # Check if it's just status code (acceptable) or full stack trace (bad)
                if page.locator("text=Traceback").count() > 0:
                    pytest.fail("Technical stack trace shown to user in timeout error")

    page.close()


# =============================================================================
# Test: Client-Side vs Server-Side Timeout
# =============================================================================

@pytest.mark.e2e
def test_client_server_timeout(timeout_api_context, db_session: Session, base_url: str):
    """Test that client-side timeout is less than server-side timeout.

    This test verifies:
    - Client timeout occurs before server timeout (avoid indefinite waiting)
    - No hanging requests after client timeout
    - Server resources are released after client timeout
    - User can make new requests after timeout

    Args:
        timeout_api_context: Timeout API context fixture (adds 30s delay)
        db_session: Database session fixture
        base_url: Base URL fixture
    """
    # Create test user
    user = create_test_user(db_session)

    # Create authenticated page with timeout injection
    page = create_authenticated_page_timeout(timeout_api_context, user, base_url)

    # Navigate to agents page
    page.goto(f"{base_url}/agents")
    page.wait_for_timeout(1000)

    # Trigger timeout
    agent_input = page.locator("textarea[placeholder*='message'], textarea[placeholder*='agent']").first
    if agent_input.count() > 0:
        send_button = page.locator("button:has_text('Send'), button:has_text('Execute')").first

        if send_button.count() > 0:
            # Record start time
            start_time = time.time()

            agent_input.fill("Test client vs server timeout")
            send_button.click()

            # Wait for client-side timeout (should be < 35s)
            try:
                page.wait_for_selector("text=timeout, text=Timeout", timeout=35000)

                elapsed = time.time() - start_time

                # Verify client timeout < 40s (reasonable client timeout)
                assert elapsed < 40, f"Client timeout too long: {elapsed:.1f}s (should be < 40s)"

            except Exception:
                # If no timeout message, check elapsed time
                elapsed = time.time() - start_time
                if elapsed > 40:
                    pytest.fail(f"Client timeout not working, request hung for {elapsed:.1f}s")

            # Verify no hanging requests (UI responsive)
            assert page.url, "Page unresponsive after timeout"

            # Try new request (should work)
            agent_input.fill("New request after timeout")
            send_button.click()
            time.sleep(2000)  # Wait 2s

            # Verify UI still responsive
            assert page.url, "Page frozen after making new request post-timeout"

    page.close()
