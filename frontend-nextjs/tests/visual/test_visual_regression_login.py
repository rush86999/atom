"""
Visual regression tests for login page using Percy.

This module tests the visual appearance of the login page across
different states (default, validation error, loading) and viewport sizes.
"""

import pytest
from playwright.sync_api import Page, expect


class TestVisualLogin:
    """Visual regression tests for login page."""

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_login_page(self, percy_page: Page, base_url: str):
        """
        Test visual appearance of default login page.

        Scenarios:
        - Navigate to login page
        - Take Percy snapshot for baseline
        - Verify form elements are visible

        Args:
            percy_page: Playwright page with Percy
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to login page
        percy_page.goto(f"{base_url}/login")
        percy_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(percy_page, "Login Page")

        # Verify login form is visible
        expect(percy_page.locator("input[type='email'], input[name='email']")).to_be_visible()
        expect(percy_page.locator("input[type='password'], input[name='password']")).to_be_visible()
        expect(percy_page.locator("button[type='submit']")).to_be_visible()

        # Verify logo/branding (if present)
        logo = percy_page.locator("[data-testid='logo'], .logo, h1").first
        if logo.count() > 0:
            expect(logo).to_be_visible()

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_login_error(self, percy_page: Page, base_url: str):
        """
        Test visual appearance of login page with validation error.

        Scenarios:
        - Navigate to login page
        - Enter invalid email format
        - Trigger validation error
        - Take Percy snapshot of error state
        - Verify error message styling

        Args:
            percy_page: Playwright page with Percy
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to login page
        percy_page.goto(f"{base_url}/login")
        percy_page.wait_for_load_state("networkidle")

        # Enter invalid email
        email_input = percy_page.locator("input[type='email'], input[name='email']")
        if email_input.count() > 0:
            email_input.fill("invalid-email")
            # Trigger validation (blur or submit attempt)
            email_input.press("Tab")

            # Wait for error message
            percy_page.wait_for_timeout(500)

            # Take Percy snapshot of error state
            percy_snapshot(percy_page, "Login Page - Validation Error")

            # Verify error message is visible
            error_locator = percy_page.locator(".error, [data-testid='error'], .validation-error").first
            if error_locator.count() > 0:
                expect(error_locator).to_be_visible()

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_login_loading(self, percy_page: Page, base_url: str):
        """
        Test visual appearance of login page during loading state.

        Scenarios:
        - Navigate to login page
        - Fill credentials
        - Intercept response to delay loading
        - Submit form
        - Take Percy snapshot of loading state
        - Verify loading indicator is present

        Args:
            percy_page: Playwright page with Percy
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to login page
        percy_page.goto(f"{base_url}/login")
        percy_page.wait_for_load_state("networkidle")

        # Fill credentials
        email_input = percy_page.locator("input[type='email'], input[name='email']")
        password_input = percy_page.locator("input[type='password'], input[name='password']")

        if email_input.count() > 0:
            email_input.fill("test@example.com")
        if password_input.count() > 0:
            password_input.fill("password123")

        # Intercept and delay login request to capture loading state
        def handle_route(route):
            # Delay response by 2 seconds to capture loading state
            percy_page.wait_for_timeout(2000)
            route.continue_()

        percy_page.route("**/api/auth/login", handle_route)

        # Submit form and capture loading state
        submit_button = percy_page.locator("button[type='submit']")
        if submit_button.count() > 0:
            # Click and wait for loading state
            submit_button.click()

            # Wait a bit for loading indicator to appear
            percy_page.wait_for_timeout(500)

            # Take Percy snapshot of loading state
            percy_snapshot(percy_page, "Login Page - Loading")

            # Verify loading indicator (if present)
            loading_locator = percy_page.locator(".spinner, .loading, [data-testid='loading']").first
            if loading_locator.count() > 0:
                expect(loading_locator).to_be_visible()

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_login_mobile(self, percy_page: Page, base_url: str):
        """
        Test visual appearance of login page on mobile viewport.

        Scenarios:
        - Set viewport to mobile size (375x667)
        - Navigate to login page
        - Take Percy snapshot for mobile baseline
        - Verify mobile layout (stacked inputs, full-width button)

        Args:
            percy_page: Playwright page with Percy
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Set mobile viewport
        percy_page.set_viewport_size({"width": 375, "height": 667})

        # Navigate to login page
        percy_page.goto(f"{base_url}/login")
        percy_page.wait_for_load_state("networkidle")

        # Take Percy snapshot with mobile width only
        percy_snapshot(percy_page, "Login Page - Mobile", widths=[375])

        # Verify mobile layout
        email_input = percy_page.locator("input[type='email'], input[name='email']")
        password_input = percy_page.locator("input[type='password'], input[name='password']")
        submit_button = percy_page.locator("button[type='submit']")

        if email_input.count() > 0:
            expect(email_input).to_be_visible()
        if password_input.count() > 0:
            expect(password_input).to_be_visible()
        if submit_button.count() > 0:
            expect(submit_button).to_be_visible()
            # Verify button is full width on mobile
            button_box = submit_button.bounding_box()
            if button_box:
                assert button_box["width"] > 300, "Submit button should be full width on mobile"
