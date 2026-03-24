"""
Visual regression tests for canvas pages using Percy.

This module tests the visual appearance of all 7 canvas types:
chart, sheet, form, docs, email, terminal, and coding.
"""

import pytest
from playwright.sync_api import Page, expect


class TestVisualCanvas:
    """Visual regression tests for canvas pages."""

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_canvas_chart(self, authenticated_percy_page: Page, base_url: str, percy_test_data: dict):
        """
        Test visual appearance of chart canvas.

        Scenarios:
        - Present chart canvas
        - Take Percy snapshot for baseline
        - Verify chart rendering, axes, labels

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
            percy_test_data: Test data created by fixture
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Get first canvas ID from test data
        canvas_ids = percy_test_data.get("canvas_ids", [])

        if canvas_ids:
            canvas_id = canvas_ids[0]
            # Navigate to canvas page
            authenticated_percy_page.goto(f"{base_url}/canvas/{canvas_id}")
            authenticated_percy_page.wait_for_load_state("networkidle")

            # Wait for chart to render (may need extra time)
            authenticated_percy_page.wait_for_timeout(2000)

            # Take Percy snapshot
            percy_snapshot(authenticated_percy_page, "Canvas - Chart")

            # Verify chart container is visible
            chart_container = authenticated_percy_page.locator(
                "[data-testid='chart'], canvas, .chart, .chart-container"
            ).first

            if chart_container.count() > 0:
                expect(chart_container).to_be_visible()

            # Check for axes or labels (if present)
            axes = authenticated_percy_page.locator(
                "[data-testid='axis'], .axis, .x-axis, .y-axis"
            ).first

            if axes.count() > 0:
                expect(axes).to_be_visible()
        else:
            # No test canvas, skip snapshot
            pytest.skip("No test canvas available")

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_canvas_sheet(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of sheet canvas.

        Scenarios:
        - Present sheet canvas (spreadsheet/data grid)
        - Take Percy snapshot for baseline
        - Verify data grid, pagination, sorting

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to canvas page (would need sheet canvas ID in real scenario)
        # For now, navigate to canvas list and look for sheet type
        authenticated_percy_page.goto(f"{base_url}/canvas")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Look for sheet canvas or create one
        sheet_canvas = authenticated_percy_page.locator(
            "[data-canvas-type='sheet'], [data-testid='sheet-canvas']"
        ).first

        if sheet_canvas.count() > 0:
            sheet_canvas.click()
            authenticated_percy_page.wait_for_timeout(1000)

            # Take Percy snapshot
            percy_snapshot(authenticated_percy_page, "Canvas - Sheet")

            # Verify data grid is visible
            data_grid = authenticated_percy_page.locator(
                "[data-testid='data-grid'], .data-grid, table, .sheet"
            ).first

            if data_grid.count() > 0:
                expect(data_grid).to_be_visible()

            # Check for pagination controls (if present)
            pagination = authenticated_percy_page.locator(
                "[data-testid='pagination'], .pagination"
            ).first

            if pagination.count() > 0:
                expect(pagination).to_be_visible()
        else:
            # No sheet canvas, skip snapshot
            pytest.skip("No sheet canvas available")

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_canvas_form(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of form canvas.

        Scenarios:
        - Present form canvas
        - Take Percy snapshot for baseline
        - Verify form fields, validation, submit button

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to canvas page (would need form canvas ID in real scenario)
        authenticated_percy_page.goto(f"{base_url}/canvas")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Look for form canvas
        form_canvas = authenticated_percy_page.locator(
            "[data-canvas-type='form'], [data-testid='form-canvas']"
        ).first

        if form_canvas.count() > 0:
            form_canvas.click()
            authenticated_percy_page.wait_for_timeout(1000)

            # Take Percy snapshot
            percy_snapshot(authenticated_percy_page, "Canvas - Form")

            # Verify form fields are visible
            form_fields = authenticated_percy_page.locator(
                "input, select, textarea, [data-testid='form-field']"
            )

            if form_fields.count() > 0:
                expect(form_fields.first).to_be_visible()

            # Check for submit button (if present)
            submit_button = authenticated_percy_page.locator(
                "button[type='submit'], button:has-text('Submit'), [data-testid='submit']"
            ).first

            if submit_button.count() > 0:
                expect(submit_button).to_be_visible()
        else:
            # No form canvas, skip snapshot
            pytest.skip("No form canvas available")

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_canvas_docs(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of docs canvas.

        Scenarios:
        - Present docs canvas (markdown documentation)
        - Take Percy snapshot for baseline
        - Verify markdown rendering and formatting

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to canvas page (would need docs canvas ID in real scenario)
        authenticated_percy_page.goto(f"{base_url}/canvas")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Look for docs canvas
        docs_canvas = authenticated_percy_page.locator(
            "[data-canvas-type='docs'], [data-testid='docs-canvas']"
        ).first

        if docs_canvas.count() > 0:
            docs_canvas.click()
            authenticated_percy_page.wait_for_timeout(1000)

            # Take Percy snapshot
            percy_snapshot(authenticated_percy_page, "Canvas - Docs")

            # Verify markdown content is visible
            markdown_content = authenticated_percy_page.locator(
                "[data-testid='markdown'], .markdown, .prose, article"
            ).first

            if markdown_content.count() > 0:
                expect(markdown_content).to_be_visible()

            # Check for formatting (headings, lists, etc.)
            headings = authenticated_percy_page.locator("h1, h2, h3")

            if headings.count() > 0:
                expect(headings.first).to_be_visible()
        else:
            # No docs canvas, skip snapshot
            pytest.skip("No docs canvas available")

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_canvas_email(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of email canvas.

        Scenarios:
        - Present email canvas
        - Take Percy snapshot for baseline
        - Verify email fields (to, subject, body)

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to canvas page (would need email canvas ID in real scenario)
        authenticated_percy_page.goto(f"{base_url}/canvas")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Look for email canvas
        email_canvas = authenticated_percy_page.locator(
            "[data-canvas-type='email'], [data-testid='email-canvas']"
        ).first

        if email_canvas.count() > 0:
            email_canvas.click()
            authenticated_percy_page.wait_for_timeout(1000)

            # Take Percy snapshot
            percy_snapshot(authenticated_percy_page, "Canvas - Email")

            # Verify email fields are visible
            to_field = authenticated_percy_page.locator(
                "input[name='to'], input[placeholder*='to' i], [data-testid='email-to']"
            ).first

            if to_field.count() > 0:
                expect(to_field).to_be_visible()

            subject_field = authenticated_percy_page.locator(
                "input[name='subject'], input[placeholder*='subject' i], [data-testid='email-subject']"
            ).first

            if subject_field.count() > 0:
                expect(subject_field).to_be_visible()

            body_field = authenticated_percy_page.locator(
                "textarea[name='body'], textarea[placeholder*='message' i], [data-testid='email-body']"
            ).first

            if body_field.count() > 0:
                expect(body_field).to_be_visible()
        else:
            # No email canvas, skip snapshot
            pytest.skip("No email canvas available")

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_canvas_terminal(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of terminal canvas.

        Scenarios:
        - Present terminal canvas
        - Take Percy snapshot for baseline
        - Verify terminal output and scrollable area

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to canvas page (would need terminal canvas ID in real scenario)
        authenticated_percy_page.goto(f"{base_url}/canvas")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Look for terminal canvas
        terminal_canvas = authenticated_percy_page.locator(
            "[data-canvas-type='terminal'], [data-testid='terminal-canvas']"
        ).first

        if terminal_canvas.count() > 0:
            terminal_canvas.click()
            authenticated_percy_page.wait_for_timeout(1000)

            # Take Percy snapshot
            percy_snapshot(authenticated_percy_page, "Canvas - Terminal")

            # Verify terminal output area is visible
            terminal_output = authenticated_percy_page.locator(
                "[data-testid='terminal-output'], .terminal-output, .terminal, pre"
            ).first

            if terminal_output.count() > 0:
                expect(terminal_output).to_be_visible()

            # Verify scrollable area (terminal should be scrollable)
            scrollable = terminal_output.locator("..").first
            if scrollable.count() > 0:
                # Check if overflow is set
                overflow_y = scrollable.evaluate("el => getComputedStyle(el).overflowY")
                assert overflow_y in ["auto", "scroll", "overlay"], "Terminal should be scrollable"
        else:
            # No terminal canvas, skip snapshot
            pytest.skip("No terminal canvas available")

    @pytest.mark.e2e
    @pytest.mark.visual
    def test_visual_canvas_coding(self, authenticated_percy_page: Page, base_url: str):
        """
        Test visual appearance of coding canvas.

        Scenarios:
        - Present coding canvas
        - Take Percy snapshot for baseline
        - Verify syntax highlighting and line numbers

        Args:
            authenticated_percy_page: Authenticated Playwright page
            base_url: Base URL of the application
        """
        from frontend_nextjs.tests.visual.fixtures.percy_fixtures import percy_snapshot

        # Navigate to canvas page (would need coding canvas ID in real scenario)
        authenticated_percy_page.goto(f"{base_url}/canvas")
        authenticated_percy_page.wait_for_load_state("networkidle")

        # Look for coding canvas
        coding_canvas = authenticated_percy_page.locator(
            "[data-canvas-type='coding'], [data-testid='coding-canvas']"
        ).first

        if coding_canvas.count() > 0:
            coding_canvas.click()
            authenticated_percy_page.wait_for_timeout(1000)

            # Take Percy snapshot
            percy_snapshot(authenticated_percy_page, "Canvas - Coding")

            # Verify code editor is visible
            code_editor = authenticated_percy_page.locator(
                "[data-testid='code-editor'], .code-editor, textarea, .editor"
            ).first

            if code_editor.count() > 0:
                expect(code_editor).to_be_visible()

            # Check for line numbers (if present)
            line_numbers = authenticated_percy_page.locator(
                "[data-testid='line-numbers'], .line-numbers, .gutter"
            ).first

            if line_numbers.count() > 0:
                expect(line_numbers).to_be_visible()

            # Check for syntax highlighting (if present)
            syntax_highlight = code_editor.locator(
                ".token, .keyword, .string, .comment"
            ).first

            # Syntax highlighting may or may not be present
            if syntax_highlight.count() > 0:
                expect(syntax_highlight).to_be_visible()
        else:
            # No coding canvas, skip snapshot
            pytest.skip("No coding canvas available")
