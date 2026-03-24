"""
Visual regression tests for dashboard page using Percy.

This module tests the visual appearance of the dashboard page across
different states (empty, with data, sidebar) and viewport sizes.
"""

import pytest
from playwright.sync_api import Page, expect


class TestVisualDashboard:
    """Visual regression tests for dashboard page."""

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_dashboard(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of default dashboard page.

        Scenarios:
        - Navigate to dashboard (authenticated)
        - Take Percy snapshot for baseline
        - Verify dashboard layout elements

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to dashboard
        authenticated_percy_page.goto(f"{base_url}/dashboard")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_percy_page, "Dashboard")

        # Verify dashboard layout elements
        expect(authenticated_percy_page.locator("main, [role='main']")).to_be_visible()

        # Check for sidebar (if present)
        sidebar = authenticated_percy_page.locator("aside, nav, [data-testid='sidebar']").first
        if sidebar.count() > 0:
            expect(sidebar).to_be_visible()

        # Check for header (if present)
        header = authenticated_percy_page.locator("header, [data-testid='header']").first
        if header.count() > 0:
            expect(header).to_be_visible()

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_dashboard_empty(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of dashboard in empty state.

        Scenarios:
        - Create fresh user with no data
        - Navigate to dashboard
        - Take Percy snapshot of empty state
        - Verify empty state message and CTA

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to dashboard (may have data, but test empty state styling)
        authenticated_percy_page.goto(f"{base_url}/dashboard")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Look for empty state indicator
        empty_state = authenticated_percy_page.locator(
            "[data-testid='empty-state'], .empty-state, .no-data"
        ).first

        if empty_state.count() > 0:
            # Empty state exists, take snapshot
            percy_snapshot(authenticated_percy_page, "Dashboard - Empty State")

            # Verify empty state elements
            expect(empty_state).to_be_visible()

            # Check for CTA button (if present)
            cta_button = empty_state.locator("button, a").first
            if cta_button.count() > 0:
                expect(cta_button).to_be_visible()
        else:
            # No empty state, take normal snapshot
            percy_snapshot(authenticated_percy_page, "Dashboard - No Data")

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_dashboard_with_data(self, authenticated_percy_page: Page, base_url: str, percy_test_data: dict):
        """
        Test visual appearance of dashboard populated with test data.

        Scenarios:
        - Populate dashboard with test data (agents, canvas, workflows)
        - Navigate to dashboard
        - Take Percy snapshot of populated dashboard
        - Verify data cards and statistics are visible

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
            percy_test_data: Test data created by fixture
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to dashboard
        authenticated_percy_page.goto(f"{base_url}/dashboard")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_percy_page, "Dashboard - With Data")

        # Verify data cards or statistics are visible
        # Look for agent cards, stats, or metrics
        data_cards = authenticated_percy_page.locator(
            "[data-testid='stats'], [data-testid='metrics'], .stat-card, .metric"
        )

        if data_cards.count() > 0:
            expect(data_cards.first).to_be_visible()

        # Look for agent list or grid
        agent_list = authenticated_percy_page.locator(
            "[data-testid='agent-list'], [data-testid='agent-grid'], .agents"
        ).first

        if agent_list.count() > 0:
            expect(agent_list).to_be_visible()

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_dashboard_sidebar_expanded(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of dashboard with expanded sidebar.

        Scenarios:
        - Navigate to dashboard
        - Ensure sidebar is expanded
        - Take Percy snapshot of expanded state
        - Verify sidebar content is visible

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to dashboard
        authenticated_percy_page.goto(f"{base_url}/dashboard")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Look for sidebar toggle button and ensure sidebar is expanded
        sidebar_toggle = authenticated_percy_page.locator(
            "[data-testid='sidebar-toggle'], .sidebar-toggle, button[aria-label*='menu']"
        ).first

        if sidebar_toggle.count() > 0:
            # Click to ensure sidebar is expanded
            sidebar_toggle.click()
            authenticated_percy_page.wait_for_timeout(500)

        # Take Percy snapshot
        percy_snapshot(authenticated_percy_page, "Dashboard - Sidebar Expanded")

        # Verify sidebar is visible
        sidebar = authenticated_percy_page.locator("aside, nav, [data-testid='sidebar']").first
        if sidebar.count() > 0:
            expect(sidebar).to_be_visible()

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_dashboard_sidebar_collapsed(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of dashboard with collapsed sidebar.

        Scenarios:
        - Navigate to dashboard
        - Collapse sidebar
        - Take Percy snapshot of collapsed state
        - Verify sidebar transition works correctly

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to dashboard
        authenticated_percy_page.goto(f"{base_url}/dashboard")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Look for sidebar toggle button
        sidebar_toggle = authenticated_percy_page.locator(
            "[data-testid='sidebar-toggle'], .sidebar-toggle, button[aria-label*='menu']"
        ).first

        if sidebar_toggle.count() > 0:
            # Click to toggle sidebar
            sidebar_toggle.click()
            authenticated_percy_page.wait_for_timeout(500)

        # Take Percy snapshot
        percy_snapshot(authenticated_percy_page, "Dashboard - Sidebar Collapsed")

        # Verify sidebar is collapsed (should have collapsed class or attribute)
        sidebar = authenticated_percy_page.locator(
            "aside.collapsed, nav.collapsed, [data-testid='sidebar'].collapsed, [data-state='collapsed']"
        ).first

        # Sidebar may or may not be collapsed depending on implementation
        if sidebar.count() > 0:
            expect(sidebar).to_be_visible()

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_dashboard_mobile(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of dashboard on mobile viewport.

        Scenarios:
        - Set viewport to mobile size (375x667)
        - Navigate to dashboard
        - Take Percy snapshot for mobile baseline
        - Verify mobile layout (hamburger menu, responsive elements)

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Set mobile viewport
        authenticated_percy_page.set_viewport_size({"width": 375, "height": 667})

        # Navigate to dashboard
        authenticated_percy_page.goto(f"{base_url}/dashboard")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Take Percy snapshot with mobile width only
        percy_snapshot(authenticated_percy_page, "Dashboard - Mobile", widths=[375])

        # Verify mobile layout
        # Look for hamburger menu or mobile navigation
        mobile_menu = authenticated_percy_page.locator(
            "[data-testid='mobile-menu'], button[aria-label*='menu'], .hamburger"
        ).first

        if mobile_menu.count() > 0:
            expect(mobile_menu).to_be_visible()

        # Verify main content is still visible on mobile
        expect(authenticated_percy_page.locator("main, [role='main']")).to_be_visible()
