"""
E2E tests for API-first authentication validation and benchmarking (AUTH-06).

This module tests API-first authentication including:
- JWT token in localStorage
- API-first bypasses UI login
- API-first is faster than UI login
- API-first allows protected access
- Speedup minimum 10x verification

Run with: pytest backend/tests/e2e_ui/tests/test_auth_api_first.py -v
"""

import pytest
import time
from playwright.sync_api import Page


class TestAPIFirstAuth:
    """E2E tests for API-first authentication (AUTH-06)."""

    def test_api_auth_fixture_sets_token_correctly(self, authenticated_page_api: Page):
        """Verify API-first auth fixture sets JWT token correctly.

        This test validates:
        1. access_token exists in localStorage
        2. Token has valid JWT format (3 parts)
        3. auth_token is also set
        4. user_email contains '@'

        Args:
            authenticated_page_api: Authenticated page fixture

        Coverage: AUTH-06 (API fixture validation)
        """
        # Verify access_token exists
        access_token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")
        assert access_token is not None, "access_token should be set in localStorage"

        # Verify token format (JWT has 3 parts: header.payload.signature)
        token_parts = access_token.split('.')
        assert len(token_parts) == 3, f"JWT should have 3 parts, got {len(token_parts)}"

        # Verify auth_token also set
        auth_token = authenticated_page_api.evaluate("() => localStorage.getItem('auth_token')")
        assert auth_token is not None, "auth_token should be set in localStorage"

        # Verify user_email contains '@'
        user_email = authenticated_page_api.evaluate("() => localStorage.getItem('user_email')")
        assert user_email is not None, "user_email should be set in localStorage"
        assert '@' in user_email, "user_email should contain '@'"

        print(f"✓ API-first auth fixture sets all tokens correctly")
        print(f"✓ access_token length: {len(access_token)}")
        print(f"✓ user_email: {user_email}")

    def test_api_auth_bypasses_ui_login(self, authenticated_page_api: Page):
        """Verify API-first auth bypasses slow UI login.

        This test validates:
        1. API-first auth completes in <1 second
        2. Dashboard can be accessed immediately
        3. No need to fill login form

        Args:
            authenticated_page_api: Authenticated page fixture

        Coverage: AUTH-06 (Bypass speed verification)
        """
        # Record start time
        start_time = time.time()

        # Navigate to dashboard (should be immediate)
        authenticated_page_api.goto("http://localhost:3001/dashboard")

        # Wait for dashboard to load
        try:
            authenticated_page_api.wait_for_selector('[data-testid="dashboard-welcome"]', timeout=5000)
        except Exception:
            # If selector doesn't exist, just wait for URL
            authenticated_page_api.wait_for_load_state("networkidle")

        # Record end time
        end_time = time.time()
        api_time = end_time - start_time

        # Verify API auth is fast (<1 second)
        assert api_time < 1.0, f"API auth should complete in <1 second, took {api_time:.3f}s"

        # Verify we're on dashboard (not redirected to login)
        current_url = authenticated_page_api.url
        assert 'login' not in current_url.lower(), "Should not be redirected to login"

        print(f"✓ API-first auth bypassed UI login successfully")
        print(f"✓ Time to dashboard: {api_time:.3f}s")

    def test_api_auth_speedup_minimum_10x(self, authenticated_page_api: Page, page: Page, test_user):
        """Verify API-first auth is at least 10x faster than UI login.

        This test validates:
        1. API-first auth benchmark (authenticated_page_api)
        2. UI login benchmark (LoginPage form fill)
        3. Speedup calculation: ui_time / api_time
        4. Speedup >= 10 (API auth at least 10x faster)

        Args:
            authenticated_page_api: Authenticated page fixture
            page: Playwright page fixture
            test_user: Test user fixture

        Coverage: AUTH-06 (10x speedup verification)
        """
        # Benchmark API-first auth
        api_time = benchmark_api_auth(authenticated_page_api)

        # Benchmark UI login
        ui_time = benchmark_ui_login(page, test_user)

        # Calculate speedup
        speedup = ui_time / api_time if api_time > 0 else float('inf')

        # Verify speedup is at least 10x
        assert speedup >= 10, \
            f"API auth should be at least 10x faster, got {speedup:.1f}x (UI: {ui_time:.2f}s, API: {api_time:.3f}s)"

        print(f"✓ API-first auth speedup verified: {speedup:.1f}x")
        print(f"✓ UI login time: {ui_time:.2f}s")
        print(f"✓ API auth time: {api_time:.3f}s")

    def test_api_auth_allows_protected_access(self, authenticated_page_api: Page):
        """Verify API-first auth allows access to protected routes.

        This test validates:
        1. Can access /dashboard without redirect
        2. Can access /agents without redirect
        3. Can access /settings without redirect
        4. Can access /projects without redirect
        5. No redirect to login on any route

        Args:
            authenticated_page_api: Authenticated page fixture

        Coverage: AUTH-06 (Protected route access)
        """
        protected_routes = [
            "/dashboard",
            "/agents",
            "/settings",
            "/projects"
        ]

        for route in protected_routes:
            # Navigate to protected route
            authenticated_page_api.goto(f"http://localhost:3001{route}")

            # Wait for page to load
            authenticated_page_api.wait_for_load_state("networkidle")

            # Verify not redirected to login
            current_url = authenticated_page_api.url
            assert 'login' not in current_url.lower(), \
                f"Should not be redirected to login when accessing {route}"

            print(f"✓ Access to {route} successful")

    def test_api_auth_token_persistence(self, authenticated_page_api: Page):
        """Verify API-first auth token persists across page navigation.

        This test validates:
        1. Token exists after initial auth
        2. Token persists across multiple page navigations
        3. Token remains valid after navigation

        Args:
            authenticated_page_api: Authenticated page fixture

        Coverage: AUTH-06 (Token persistence)
        """
        # Get initial token
        initial_token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")
        assert initial_token is not None, "Initial token should exist"

        # Navigate to multiple pages
        pages = [
            "http://localhost:3001/dashboard",
            "http://localhost:3001/agents",
            "http://localhost:3001/settings",
            "http://localhost:3001/dashboard"
        ]

        for page_url in pages:
            authenticated_page_api.goto(page_url)
            authenticated_page_api.wait_for_load_state("networkidle")

            # Verify token still exists
            current_token = authenticated_page_api.evaluate("() => localStorage.getItem('access_token')")
            assert current_token is not None, f"Token should persist when navigating to {page_url}"
            assert current_token == initial_token, "Token should remain the same across navigation"

        print(f"✓ Token persisted across {len(pages)} page navigations")


def benchmark_api_auth(authenticated_page_api: Page) -> float:
    """Benchmark API-first authentication speed.

    Args:
        authenticated_page_api: Authenticated page fixture

    Returns:
        float: Time in seconds to access dashboard
    """
    start = time.time()

    # Navigate to dashboard
    authenticated_page_api.goto("http://localhost:3001/dashboard")

    # Wait for dashboard loaded
    try:
        authenticated_page_api.wait_for_selector('[data-testid="dashboard-welcome"]', timeout=5000)
    except Exception:
        # If selector doesn't exist, wait for network idle
        authenticated_page_api.wait_for_load_state("networkidle")

    return time.time() - start


def benchmark_ui_login(page: Page, test_user) -> float:
    """Benchmark UI login speed.

    Args:
        page: Playwright page fixture
        test_user: Test user fixture

    Returns:
        float: Time in seconds to login via UI
    """
    from tests.e2e_ui.pages.page_objects import LoginPage

    start = time.time()

    # Navigate to login page
    login = LoginPage(page)
    login.navigate()

    # Fill credentials
    login.fill_email(test_user.email)
    login.fill_password("TestPassword123!")
    login.click_submit()

    # Wait for redirect to dashboard
    try:
        page.wait_for_url("**/dashboard", timeout=10000)
    except Exception:
        # If redirect doesn't happen, wait for network idle
        page.wait_for_load_state("networkidle")

    return time.time() - start
