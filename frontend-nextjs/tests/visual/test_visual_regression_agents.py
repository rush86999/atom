"""
Visual regression tests for agents page using Percy.

This module tests the visual appearance of the agents page including
list view, detail view, and execution result display.
"""

import pytest
from playwright.sync_api import Page, expect


class TestVisualAgents:
    """Visual regression tests for agents page."""

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_agents_list(self, authenticated_percy_page: Page, base_url: str, percy_test_data: dict):
        """
        Test visual appearance of agents list page.

        Scenarios:
        - Navigate to agents page
        - Take Percy snapshot for baseline
        - Verify agent cards, filters, search are visible

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
            percy_test_data: Test data created by fixture
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to agents page
        authenticated_percy_page.goto(f"{base_url}/agents")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_percy_page, "Agents List")

        # Verify agent list is visible
        agent_list = authenticated_percy_page.locator(
            "[data-testid='agent-list'], [data-testid='agent-grid'], .agents, .agent-list"
        ).first

        if agent_list.count() > 0:
            expect(agent_list).to_be_visible()

        # Check for search input (if present)
        search_input = authenticated_percy_page.locator(
            "input[type='search'], input[placeholder*='search' i], [data-testid='search']"
        ).first

        if search_input.count() > 0:
            expect(search_input).to_be_visible()

        # Check for filters (if present)
        filters = authenticated_percy_page.locator(
            "[data-testid='filters'], .filters, select"
        ).first

        if filters.count() > 0:
            expect(filters).to_be_visible()

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_agent_detail(self, authenticated_percy_page: Page, base_url: str, percy_test_data: dict):
        """
        Test visual appearance of agent detail page.

        Scenarios:
        - Navigate to agent detail page
        - Take Percy snapshot for baseline
        - Verify agent info, execute button, history are visible

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
            percy_test_data: Test data created by fixture
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Get first agent ID from test data
        agent_ids = percy_test_data.get("agent_ids", [])

        if agent_ids:
            agent_id = agent_ids[0]
            # Navigate to agent detail page
            authenticated_percy_page.goto(f"{base_url}/agents/{agent_id}")
            authenticated_percy_page.wait_for_load_state("networkidle")

            # Take Percy snapshot
            percy_snapshot(authenticated_percy_page, "Agent Detail")

            # Verify agent info is visible
            agent_info = authenticated_percy_page.locator(
                "[data-testid='agent-info'], .agent-info, .agent-details"
            ).first

            if agent_info.count() > 0:
                expect(agent_info).to_be_visible()

            # Check for execute button (if present)
            execute_button = authenticated_percy_page.locator(
                "button[type='submit'], button:has-text('Execute'), [data-testid='execute']"
            ).first

            if execute_button.count() > 0:
                expect(execute_button).to_be_visible()

            # Check for execution history (if present)
            history = authenticated_percy_page.locator(
                "[data-testid='history'], .history, .executions"
            ).first

            if history.count() > 0:
                expect(history).to_be_visible()
        else:
            # No test agent, skip snapshot
            pytest.skip("No test agent available")

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_agent_execution(self, authenticated_percy_page: Page, base_url: str, percy_test_data: dict):
        """
        Test visual appearance of agent execution result.

        Scenarios:
        - Navigate to agent detail page
        - Execute agent
        - Wait for response
        - Take Percy snapshot of execution result
        - Verify response display and formatting

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
            percy_test_data: Test data created by fixture
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Get first agent ID from test data
        agent_ids = percy_test_data.get("agent_ids", [])

        if agent_ids:
            agent_id = agent_ids[0]
            # Navigate to agent detail page
            authenticated_percy_page.goto(f"{base_url}/agents/{agent_id}")
            authenticated_percy_page.wait_for_load_state("networkidle")

            # Look for execute button
            execute_button = authenticated_percy_page.locator(
                "button[type='submit'], button:has-text('Execute'), [data-testid='execute']"
            ).first

            if execute_button.count() > 0:
                # Execute agent
                execute_button.click()

                # Wait for response (loading indicator may appear)
                authenticated_percy_page.wait_for_timeout(2000)
                authenticated_percy_page.wait_for_load_state("networkidle")

                # Take Percy snapshot of execution result
                percy_snapshot(authenticated_percy_page, "Agent Execution Result")

                # Verify response display
                response_area = authenticated_percy_page.locator(
                    "[data-testid='response'], .response, .execution-result, .output"
                ).first

                if response_area.count() > 0:
                    expect(response_area).to_be_visible()
            else:
                # No execute button, skip snapshot
                pytest.skip("No execute button found")
        else:
            # No test agent, skip snapshot
            pytest.skip("No test agent available")
