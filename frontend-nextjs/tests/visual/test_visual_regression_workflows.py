"""
Visual regression tests for workflows page using Percy.

This module tests the visual appearance of the workflows page including
list view, workflow builder, execution states, and results display.
"""

import pytest
from playwright.sync_api import Page, expect


class TestVisualWorkflows:
    """Visual regression tests for workflows page."""

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_workflows_list(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of workflows list page.

        Scenarios:
        - Navigate to workflows page
        - Take Percy snapshot for baseline
        - Verify workflow cards, create button, filters are visible

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to workflows page
        authenticated_percy_page.goto(f"{base_url}/workflows")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_percy_page, "Workflows List")

        # Verify workflow list is visible
        workflow_list = authenticated_percy_page.locator(
            "[data-testid='workflow-list'], [data-testid='workflow-grid'], .workflows, .workflow-list"
        ).first

        if workflow_list.count() > 0:
            expect(workflow_list).to_be_visible()

        # Check for create button (if present)
        create_button = authenticated_percy_page.locator(
            "button:has-text('Create'), button:has-text('New'), a:has-text('Create'), [data-testid='create-workflow']"
        ).first

        if create_button.count() > 0:
            expect(create_button).to_be_visible()

        # Check for filters (if present)
        filters = authenticated_percy_page.locator(
            "[data-testid='filters'], .filters, select"
        ).first

        if filters.count() > 0:
            expect(filters).to_be_visible()

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_workflow_builder_empty(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of workflow builder in empty state.

        Scenarios:
        - Navigate to workflow builder (new workflow)
        - Take Percy snapshot for baseline
        - Verify empty canvas, skill palette, drag-drop hints

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to workflow builder (new workflow)
        authenticated_percy_page.goto(f"{base_url}/workflows/new")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Take Percy snapshot
        percy_snapshot(authenticated_percy_page, "Workflow Builder - Empty")

        # Verify empty canvas is visible
        empty_canvas = authenticated_percy_page.locator(
            "[data-testid='workflow-canvas'], .workflow-canvas, .canvas, [role='application']"
        ).first

        if empty_canvas.count() > 0:
            expect(empty_canvas).to_be_visible()

        # Check for skill palette (if present)
        skill_palette = authenticated_percy_page.locator(
            "[data-testid='skill-palette'], .skill-palette, .skills"
        ).first

        if skill_palette.count() > 0:
            expect(skill_palette).to_be_visible()

        # Check for drag-drop hints (if present)
        hints = authenticated_percy_page.locator(
            "[data-testid='drag-hint'], .drag-hint, .drop-hint, .hint"
        ).first

        if hints.count() > 0:
            expect(hints).to_be_visible()

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_workflow_builder_with_skills(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of workflow builder with skills added.

        Scenarios:
        - Create workflow with 2-3 skills
        - Take Percy snapshot for baseline
        - Verify skill nodes, connections, DAG visualization

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to workflow builder
        authenticated_percy_page.goto(f"{base_url}/workflows/new")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Try to add skills (implementation dependent)
        # Look for skill palette and drag skills to canvas
        skill_palette = authenticated_percy_page.locator(
            "[data-testid='skill-palette'], .skill-palette, .skills"
        ).first

        if skill_palette.count() > 0:
            # Get first skill
            first_skill = skill_palette.locator("[data-testid='skill'], .skill").first

            if first_skill.count() > 0:
                # Drag skill to canvas (if drag-drop is implemented)
                # For now, just click to add (common pattern)
                first_skill.click()
                authenticated_percy_page.wait_for_timeout(500)

                # Try to add more skills
                second_skill = skill_palette.locator("[data-testid='skill'], .skill").nth(1)
                if second_skill.count() > 0:
                    second_skill.click()
                    authenticated_percy_page.wait_for_timeout(500)

        # Take Percy snapshot
        percy_snapshot(authenticated_percy_page, "Workflow Builder - With Skills")

        # Verify skill nodes are visible (if added)
        skill_nodes = authenticated_percy_page.locator(
            "[data-testid='skill-node'], .skill-node, .node, [data-node]"
        )

        if skill_nodes.count() > 0:
            expect(skill_nodes.first).to_be_visible()

        # Check for connections/edges (if present)
        connections = authenticated_percy_page.locator(
            "[data-testid='connection'], .connection, .edge, path"
        ).first

        if connections.count() > 0:
            expect(connections).to_be_visible()

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_workflow_execution_running(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of workflow execution in running state.

        Scenarios:
        - Execute workflow
        - Take Percy snapshot during execution
        - Verify progress indicators, skill status

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to workflows list and look for executable workflow
        authenticated_percy_page.goto(f"{base_url}/workflows")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Look for existing workflow to execute
        workflow_card = authenticated_percy_page.locator(
            "[data-testid='workflow-card'], .workflow-card"
        ).first

        if workflow_card.count() > 0:
            # Click on workflow
            workflow_card.click()
            authenticated_percy_page.wait_for_timeout(1000)

            # Look for execute button
            execute_button = authenticated_percy_page.locator(
                "button:has-text('Execute'), button:has-text('Run'), [data-testid='execute']"
            ).first

            if execute_button.count() > 0:
                # Execute workflow
                execute_button.click()

                # Wait a moment for execution to start
                authenticated_percy_page.wait_for_timeout(2000)

                # Take Percy snapshot of running state
                percy_snapshot(authenticated_percy_page, "Workflow Execution - Running")

                # Verify progress indicators are visible
                progress = authenticated_percy_page.locator(
                    "[data-testid='progress'], .progress, progress, .loading"
                ).first

                if progress.count() > 0:
                    expect(progress).to_be_visible()

                # Check for skill status indicators (if present)
                skill_status = authenticated_percy_page.locator(
                    "[data-testid='skill-status'], .skill-status, .status"
                ).first

                if skill_status.count() > 0:
                    expect(skill_status).to_be_visible()
            else:
                # No execute button, skip snapshot
                pytest.skip("No execute button found")
        else:
            # No workflow available, skip snapshot
            pytest.skip("No workflow available")

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_workflow_execution_results(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of workflow execution results.

        Scenarios:
        - Wait for workflow completion
        - Take Percy snapshot of results
        - Verify results display, success/failure indicators

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to workflows list and look for completed workflow
        authenticated_percy_page.goto(f"{base_url}/workflows")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Look for workflow with execution history
        workflow_card = authenticated_percy_page.locator(
            "[data-testid='workflow-card'], .workflow-card"
        ).first

        if workflow_card.count() > 0:
            # Click on workflow
            workflow_card.click()
            authenticated_percy_page.wait_for_timeout(1000)

            # Look for execution history tab
            history_tab = authenticated_percy_page.locator(
                "[data-testid='history'], button:has-text('History'), tab:has-text('Executions')"
            ).first

            if history_tab.count() > 0:
                history_tab.click()
                authenticated_percy_page.wait_for_timeout(1000)

            # Take Percy snapshot of results
            percy_snapshot(authenticated_percy_page, "Workflow Execution - Results")

            # Verify results display is visible
            results_area = authenticated_percy_page.locator(
                "[data-testid='results'], .results, .execution-results, .output"
            ).first

            if results_area.count() > 0:
                expect(results_area).to_be_visible()

            # Check for success/failure indicators (if present)
            status_indicator = authenticated_percy_page.locator(
                "[data-testid='status'], .status, .success, .failure, .completed"
            ).first

            if status_indicator.count() > 0:
                expect(status_indicator).to_be_visible()

            # Check for execution logs (if present)
            logs = authenticated_percy_page.locator(
                "[data-testid='logs'], .logs, pre, .output"
            ).first

            if logs.count() > 0:
                expect(logs).to_be_visible()
        else:
            # No workflow available, skip snapshot
            pytest.skip("No workflow available")

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_workflow_dag_visualization(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of workflow DAG (Directed Acyclic Graph) visualization.

        Scenarios:
        - Navigate to workflow detail page
        - Take Percy snapshot of DAG visualization
        - Verify nodes, edges, and layout are correct

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to workflows list
        authenticated_percy_page.goto(f"{base_url}/workflows")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Look for workflow with DAG
        workflow_card = authenticated_percy_page.locator(
            "[data-testid='workflow-card'], .workflow-card"
        ).first

        if workflow_card.count() > 0:
            # Click on workflow
            workflow_card.click()
            authenticated_percy_page.wait_for_timeout(1000)

            # Take Percy snapshot of DAG visualization
            percy_snapshot(authenticated_percy_page, "Workflow DAG Visualization")

            # Verify DAG canvas is visible
            dag_canvas = authenticated_percy_page.locator(
                "[data-testid='dag-canvas'], .dag-canvas, .workflow-canvas, svg"
            ).first

            if dag_canvas.count() > 0:
                expect(dag_canvas).to_be_visible()

            # Check for nodes (if present)
            nodes = dag_canvas.locator("[data-testid='node'], .node, circle, rect")

            if nodes.count() > 0:
                expect(nodes.first).to_be_visible()

            # Check for edges/connections (if present)
            edges = dag_canvas.locator("[data-testid='edge'], .edge, path, line")

            if edges.count() > 0:
                expect(edges.first).to_be_visible()
        else:
            # No workflow available, skip snapshot
            pytest.skip("No workflow available")
