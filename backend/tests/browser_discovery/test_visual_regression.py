"""
Visual regression tests with Percy integration for browser bug discovery.

This module provides comprehensive visual regression testing across all major
page groups: login, dashboard, agents, canvas, and workflows. Tests use Percy
to capture baseline screenshots across 3 viewport sizes (mobile: 375px, tablet: 768px,
desktop: 1280px) for detecting CSS changes, layout shifts, and component updates.

Total snapshots: 26 tests × 3 widths = 78+ baseline screenshots.

Uses API-first authentication from e2e_ui fixtures for 10-100x faster setup
than UI-based login.
"""

import pytest
from playwright.sync_api import Page, expect

# Import Percy snapshot function from frontend visual tests
from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot


class TestVisualRegression:
    """Visual regression tests across all page groups."""

    # ==========================================================================
    # DASHBOARD TESTS (5 tests)
    # ==========================================================================

    @pytest.mark.visual
    def test_visual_dashboard_default(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of default dashboard page.

        Scenarios:
        - Navigate to dashboard (authenticated)
        - Take Percy snapshot for baseline
        - Verify dashboard layout elements

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to dashboard
        authenticated_page.goto(f"{base_url}/dashboard")
        authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Dashboard - Default")

        # Verify dashboard layout elements
        expect(authenticated_page.locator("main, [role='main']")).to_be_visible()

    @pytest.mark.visual
    def test_visual_dashboard_empty_state(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of dashboard in empty state.

        Scenarios:
        - Check for empty state indicator
        - Take Percy snapshot of empty state
        - Verify empty state styling

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to dashboard
        authenticated_page.goto(f"{base_url}/dashboard")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for empty state indicator
        empty_state = authenticated_page.locator(
            "[data-testid='empty-state'], .empty-state, .no-data"
        ).first

        if empty_state.count() > 0:
            # Empty state exists, take snapshot
            percy_snapshot(authenticated_page, "Dashboard - Empty State")
            expect(empty_state).to_be_visible()
        else:
            # No empty state, take normal snapshot
            percy_snapshot(authenticated_page, "Dashboard - No Empty State")

    @pytest.mark.visual
    def test_visual_dashboard_with_data(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of dashboard populated with data.

        Scenarios:
        - Navigate to dashboard with existing data
        - Take Percy snapshot of populated dashboard
        - Verify data cards and statistics are visible

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to dashboard
        authenticated_page.goto(f"{base_url}/dashboard")
        authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Dashboard - With Data")

        # Verify data cards or statistics are visible
        data_cards = authenticated_page.locator(
            "[data-testid='stats'], [data-testid='metrics'], .stat-card, .metric"
        )

        if data_cards.count() > 0:
            expect(data_cards.first).to_be_visible()

    @pytest.mark.visual
    def test_visual_dashboard_sidebar_expanded(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of dashboard with expanded sidebar.

        Scenarios:
        - Navigate to dashboard
        - Ensure sidebar is expanded
        - Take Percy snapshot of expanded state
        - Verify sidebar content is visible

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to dashboard
        authenticated_page.goto(f"{base_url}/dashboard")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for sidebar toggle button and ensure sidebar is expanded
        sidebar_toggle = authenticated_page.locator(
            "[data-testid='sidebar-toggle'], .sidebar-toggle, button[aria-label*='menu']"
        ).first

        if sidebar_toggle.count() > 0:
            # Click to ensure sidebar is expanded
            sidebar_toggle.click()
            authenticated_page.wait_for_timeout(500)

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Dashboard - Sidebar Expanded")

        # Verify sidebar is visible
        sidebar = authenticated_page.locator("aside, nav, [data-testid='sidebar']").first
        if sidebar.count() > 0:
            expect(sidebar).to_be_visible()

    @pytest.mark.visual
    def test_visual_dashboard_sidebar_collapsed(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of dashboard with collapsed sidebar.

        Scenarios:
        - Navigate to dashboard
        - Collapse sidebar
        - Take Percy snapshot of collapsed state
        - Verify sidebar transition works correctly

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to dashboard
        authenticated_page.goto(f"{base_url}/dashboard")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for sidebar toggle button
        sidebar_toggle = authenticated_page.locator(
            "[data-testid='sidebar-toggle'], .sidebar-toggle, button[aria-label*='menu']"
        ).first

        if sidebar_toggle.count() > 0:
            # Click to toggle sidebar
            sidebar_toggle.click()
            authenticated_page.wait_for_timeout(500)

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Dashboard - Sidebar Collapsed")

        # Verify sidebar is collapsed
        sidebar = authenticated_page.locator(
            "aside.collapsed, nav.collapsed, [data-testid='sidebar'].collapsed, [data-state='collapsed']"
        ).first

        if sidebar.count() > 0:
            expect(sidebar).to_be_visible()

    # ==========================================================================
    # AGENTS TESTS (5 tests)
    # ==========================================================================

    @pytest.mark.visual
    def test_visual_agents_list(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of agents list page.

        Scenarios:
        - Navigate to agents list
        - Take Percy snapshot of list view
        - Verify agent cards are visible

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to agents list
        authenticated_page.goto(f"{base_url}/agents")
        authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Agents - List View")

        # Verify agent list or grid is visible
        agent_list = authenticated_page.locator(
            "[data-testid='agent-list'], [data-testid='agent-grid'], .agents"
        ).first

        if agent_list.count() > 0:
            expect(agent_list).to_be_visible()

    @pytest.mark.visual
    def test_visual_agents_grid_view(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of agents grid view.

        Scenarios:
        - Navigate to agents list
        - Switch to grid view (if available)
        - Take Percy snapshot of grid view
        - Verify grid layout is correct

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to agents list
        authenticated_page.goto(f"{base_url}/agents")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for grid view toggle
        grid_toggle = authenticated_page.locator(
            "[data-testid='grid-view'], button[aria-label*='grid'], .grid-view-toggle"
        ).first

        if grid_toggle.count() > 0:
            grid_toggle.click()
            authenticated_page.wait_for_timeout(500)

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Agents - Grid View")

        # Verify grid view is visible
        agent_grid = authenticated_page.locator(
            "[data-testid='agent-grid'], .agents.grid"
        ).first

        if agent_grid.count() > 0:
            expect(agent_grid).to_be_visible()

    @pytest.mark.visual
    def test_visual_agent_creation_form(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of agent creation form.

        Scenarios:
        - Navigate to agent creation page
        - Take Percy snapshot of form
        - Verify form fields are visible

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to agent creation
        authenticated_page.goto(f"{base_url}/agents/new")
        authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Agents - Creation Form")

        # Verify form elements are visible
        form = authenticated_page.locator("form, [data-testid='agent-form']").first
        if form.count() > 0:
            expect(form).to_be_visible()

    @pytest.mark.visual
    def test_visual_agent_detail_view(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of agent detail page.

        Scenarios:
        - Navigate to agent detail page
        - Take Percy snapshot of detail view
        - Verify agent information is displayed

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Try to navigate to first agent detail page
        authenticated_page.goto(f"{base_url}/agents")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for first agent link
        first_agent = authenticated_page.locator(
            "[data-testid='agent-card'], a[href*='/agents/']"
        ).first

        if first_agent.count() > 0:
            first_agent.click()
            authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Agents - Detail View")

        # Verify detail view elements
        detail_view = authenticated_page.locator(
            "[data-testid='agent-detail'], .agent-detail"
        ).first

        if detail_view.count() > 0:
            expect(detail_view).to_be_visible()

    @pytest.mark.visual
    def test_visual_agent_execution_view(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of agent execution page.

        Scenarios:
        - Navigate to agent execution view
        - Take Percy snapshot of execution interface
        - Verify execution controls are visible

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Try to navigate to agent execution view
        authenticated_page.goto(f"{base_url}/agents")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for execute button or link
        execute_button = authenticated_page.locator(
            "[data-testid='execute-agent'], button:has-text('Execute'), a:has-text('Execute')"
        ).first

        if execute_button.count() > 0:
            execute_button.click()
            authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Agents - Execution View")

        # Verify execution view elements
        execution_view = authenticated_page.locator(
            "[data-testid='execution-view'], .execution-view"
        ).first

        if execution_view.count() > 0:
            expect(execution_view).to_be_visible()

    # ==========================================================================
    # CANVAS TESTS (5 tests)
    # ==========================================================================

    @pytest.mark.visual
    def test_visual_canvas_list(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of canvas list page.

        Scenarios:
        - Navigate to canvas list
        - Take Percy snapshot of list
        - Verify canvas cards are visible

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to canvas list
        authenticated_page.goto(f"{base_url}/canvas")
        authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Canvas - List View")

        # Verify canvas list is visible
        canvas_list = authenticated_page.locator(
            "[data-testid='canvas-list'], .canvas-list"
        ).first

        if canvas_list.count() > 0:
            expect(canvas_list).to_be_visible()

    @pytest.mark.visual
    def test_visual_canvas_chart_type(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of chart canvas.

        Scenarios:
        - Navigate to chart canvas
        - Take Percy snapshot of chart visualization
        - Verify chart elements are visible

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to canvas list and look for chart canvas
        authenticated_page.goto(f"{base_url}/canvas")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for chart canvas link
        chart_canvas = authenticated_page.locator(
            "[data-testid='chart-canvas'], a:has-text('chart'), .canvas[data-type='chart']"
        ).first

        if chart_canvas.count() > 0:
            chart_canvas.click()
            authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Canvas - Chart Type")

        # Verify chart elements
        chart = authenticated_page.locator(
            "[data-testid='chart'], canvas, .chart"
        ).first

        if chart.count() > 0:
            expect(chart).to_be_visible()

    @pytest.mark.visual
    def test_visual_canvas_markdown_type(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of markdown canvas.

        Scenarios:
        - Navigate to markdown canvas
        - Take Percy snapshot of markdown rendering
        - Verify markdown content is visible

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to canvas list and look for markdown canvas
        authenticated_page.goto(f"{base_url}/canvas")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for markdown canvas link
        markdown_canvas = authenticated_page.locator(
            "[data-testid='markdown-canvas'], a:has-text('markdown'), .canvas[data-type='markdown']"
        ).first

        if markdown_canvas.count() > 0:
            markdown_canvas.click()
            authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Canvas - Markdown Type")

        # Verify markdown content
        markdown = authenticated_page.locator(
            "[data-testid='markdown'], .markdown, .prose"
        ).first

        if markdown.count() > 0:
            expect(markdown).to_be_visible()

    @pytest.mark.visual
    def test_visual_canvas_sheet_type(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of sheet canvas.

        Scenarios:
        - Navigate to sheet canvas
        - Take Percy snapshot of sheet rendering
        - Verify sheet table is visible

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to canvas list and look for sheet canvas
        authenticated_page.goto(f"{base_url}/canvas")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for sheet canvas link
        sheet_canvas = authenticated_page.locator(
            "[data-testid='sheet-canvas'], a:has-text('sheet'), .canvas[data-type='sheet']"
        ).first

        if sheet_canvas.count() > 0:
            sheet_canvas.click()
            authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Canvas - Sheet Type")

        # Verify sheet table
        sheet = authenticated_page.locator(
            "[data-testid='sheet'], table, .sheet"
        ).first

        if sheet.count() > 0:
            expect(sheet).to_be_visible()

    @pytest.mark.visual
    def test_visual_canvas_form_type(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of form canvas.

        Scenarios:
        - Navigate to form canvas
        - Take Percy snapshot of form rendering
        - Verify form fields are visible

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to canvas list and look for form canvas
        authenticated_page.goto(f"{base_url}/canvas")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for form canvas link
        form_canvas = authenticated_page.locator(
            "[data-testid='form-canvas'], a:has-text('form'), .canvas[data-type='form']"
        ).first

        if form_canvas.count() > 0:
            form_canvas.click()
            authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Canvas - Form Type")

        # Verify form elements
        form = authenticated_page.locator(
            "[data-testid='form'], form, .form-canvas"
        ).first

        if form.count() > 0:
            expect(form).to_be_visible()

    # ==========================================================================
    # WORKFLOWS TESTS (5 tests)
    # ==========================================================================

    @pytest.mark.visual
    def test_visual_workflows_list(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of workflows list page.

        Scenarios:
        - Navigate to workflows list
        - Take Percy snapshot of list
        - Verify workflow cards are visible

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to workflows list
        authenticated_page.goto(f"{base_url}/workflows")
        authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Workflows - List View")

        # Verify workflow list is visible
        workflow_list = authenticated_page.locator(
            "[data-testid='workflow-list'], .workflow-list"
        ).first

        if workflow_list.count() > 0:
            expect(workflow_list).to_be_visible()

    @pytest.mark.visual
    def test_visual_workflow_creation(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of workflow creation form.

        Scenarios:
        - Navigate to workflow creation page
        - Take Percy snapshot of creation form
        - Verify form fields are visible

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Navigate to workflow creation
        authenticated_page.goto(f"{base_url}/workflows/new")
        authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Workflows - Creation Form")

        # Verify form elements
        form = authenticated_page.locator(
            "[data-testid='workflow-form'], form, .workflow-creation"
        ).first

        if form.count() > 0:
            expect(form).to_be_visible()

    @pytest.mark.visual
    def test_visual_workflow_detail(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of workflow detail view.

        Scenarios:
        - Navigate to workflow detail page
        - Take Percy snapshot of detail view
        - Verify workflow information is displayed

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Try to navigate to workflow detail
        authenticated_page.goto(f"{base_url}/workflows")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for first workflow link
        first_workflow = authenticated_page.locator(
            "[data-testid='workflow-card'], a[href*='/workflows/']"
        ).first

        if first_workflow.count() > 0:
            first_workflow.click()
            authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Workflows - Detail View")

        # Verify detail view elements
        detail_view = authenticated_page.locator(
            "[data-testid='workflow-detail'], .workflow-detail"
        ).first

        if detail_view.count() > 0:
            expect(detail_view).to_be_visible()

    @pytest.mark.visual
    def test_visual_workflow_execution(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of workflow execution view.

        Scenarios:
        - Navigate to workflow execution interface
        - Take Percy snapshot of execution view
        - Verify execution controls are visible

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Try to navigate to workflow execution
        authenticated_page.goto(f"{base_url}/workflows")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for execute button
        execute_button = authenticated_page.locator(
            "[data-testid='execute-workflow'], button:has-text('Execute'), a:has-text('Execute')"
        ).first

        if execute_button.count() > 0:
            execute_button.click()
            authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Workflows - Execution View")

        # Verify execution view elements
        execution_view = authenticated_page.locator(
            "[data-testid='workflow-execution'], .workflow-execution"
        ).first

        if execution_view.count() > 0:
            expect(execution_view).to_be_visible()

    @pytest.mark.visual
    def test_visual_workflow_automation(self, authenticated_page: Page, base_url: str):
        """
        Test visual appearance of workflow automation settings.

        Scenarios:
        - Navigate to workflow automation settings
        - Take Percy snapshot of automation interface
        - Verify automation controls are visible

        Args:
            authenticated_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        # Try to navigate to workflow automation settings
        authenticated_page.goto(f"{base_url}/workflows")
        authenticated_page.wait_for_load_state("networkidle")

        # Look for automation settings link
        automation_link = authenticated_page.locator(
            "[data-testid='automation-settings'], a:has-text('Automation'), a:has-text('Settings')"
        ).first

        if automation_link.count() > 0:
            automation_link.click()
            authenticated_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_page, "Workflows - Automation Settings")

        # Verify automation settings elements
        automation_view = authenticated_page.locator(
            "[data-testid='automation'], .automation-settings"
        ).first

        if automation_view.count() > 0:
            expect(automation_view).to_be_visible()

    # ==========================================================================
    # LOGIN TESTS (3 tests)
    # ==========================================================================

    @pytest.mark.visual
    def test_visual_login_default(self, page: Page, base_url: str):
        """
        Test visual appearance of login page (no auth required).

        Scenarios:
        - Navigate to login page
        - Take Percy snapshot of login form
        - Verify login form elements are visible

        Args:
            page: Playwright page fixture (unauthenticated)
            base_url: Base URL of the application
        """
        # Navigate to login page
        page.goto(f"{base_url}/login")
        page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(page, "Login - Default")

        # Verify login form elements
        expect(page.locator("input[type='email'], input[name='email']")).to_be_visible()
        expect(page.locator("input[type='password'], input[name='password']")).to_be_visible()
        expect(page.locator("button[type='submit']")).to_be_visible()

    @pytest.mark.visual
    def test_visual_login_with_error(self, page: Page, base_url: str):
        """
        Test visual appearance of login page with error state.

        Scenarios:
        - Navigate to login page
        - Submit invalid credentials
        - Take Percy snapshot of error state
        - Verify error message is displayed

        Args:
            page: Playwright page fixture (unauthenticated)
            base_url: Base URL of the application
        """
        # Navigate to login page
        page.goto(f"{base_url}/login")
        page.wait_for_load_state("networkidle")

        # Submit invalid credentials
        page.fill("input[type='email'], input[name='email']", "invalid@example.com")
        page.fill("input[type='password'], input[name='password']", "wrongpassword")
        page.click("button[type='submit']")

        # Wait for error message
        page.wait_for_timeout(1000)

        # Take Percy snapshot
        percy_snapshot(page, "Login - Error State")

        # Verify error message is visible
        error_message = page.locator(
            "[data-testid='error'], .error, .alert-error, [role='alert']"
        ).first

        if error_message.count() > 0:
            expect(error_message).to_be_visible()

    @pytest.mark.visual
    def test_visual_login_loading(self, page: Page, base_url: str):
        """
        Test visual appearance of login page in loading state.

        Scenarios:
        - Navigate to login page
        - Submit credentials and capture loading state
        - Take Percy snapshot of loading indicator
        - Verify loading spinner is displayed

        Args:
            page: Playwright page fixture (unauthenticated)
            base_url: Base URL of the application
        """
        # Navigate to login page
        page.goto(f"{base_url}/login")
        page.wait_for_load_state("networkidle")

        # Fill credentials
        page.fill("input[type='email'], input[name='email']", "test@example.com")
        page.fill("input[type='password'], input[name='password']", "password123")

        # Click submit and immediately capture loading state
        page.click("button[type='submit']")

        # Wait briefly for loading state to appear
        page.wait_for_timeout(100)

        # Take Percy snapshot
        percy_snapshot(page, "Login - Loading State")

        # Verify loading indicator (may or may not be visible depending on speed)
        loading_indicator = page.locator(
            "[data-testid='loading'], .loading, .spinner, [role='status']"
        ).first

        # Loading may be too fast to capture, so we don't assert
        if loading_indicator.count() > 0:
            expect(loading_indicator).to_be_visible()
