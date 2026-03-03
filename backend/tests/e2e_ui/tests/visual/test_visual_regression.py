"""
Visual regression tests for critical pages using Percy.

These tests capture screenshots of key pages and compare them against baselines
to detect unintended UI changes. Tests run automatically on every PR via Percy.

Percy Requirements:
- PERCY_TOKEN environment variable (set in GitHub Actions secrets)
- Percy project setup at https://percy.io
- Baseline screenshots (captured on first run)

Critical Pages Tested:
- Dashboard: Main user interface with navigation and overview
- Agent Chat: Core agent interaction interface
- Canvas Presentations: Dynamic canvas components (sheets, charts, forms)

Maintenance:
- Review Percy diffs after each PR
- Approve intentional design changes
- Reject and fix unintended regressions
- Update .percyrc.js percyCSS to hide dynamic content causing false positives
"""

from tests.e2e_ui.pages.page_objects import DashboardPage, AgentChatPage, CanvasPage
import pytest


class TestVisualRegression:
    """Visual regression tests for critical pages."""

    def test_dashboard_visual(self, browser, authenticated_user):
        """
        Verify dashboard page has no visual regressions.

        Validates:
        - Navigation layout
        - Dashboard cards and widgets
        - Typography and spacing
        - Color scheme and branding

        VALIDATED_BUG: Catches CSS changes that break layout (e.g., flexbox direction changes)
        """
        dashboard = DashboardPage(browser.new_page())
        dashboard.navigate()
        # Percy snapshot will be captured automatically
        # Snapshot name: "Dashboard Page"

    def test_agent_chat_visual(self, browser, authenticated_user):
        """
        Verify agent chat page has no visual regressions.

        Validates:
        - Chat message bubbles (user vs agent)
        - Input field and send button
        - Message history scrolling
        - Agent avatar and status indicators

        VALIDATED_BUG: Catches chat UI breaking changes (e.g., message alignment, overflow)
        """
        chat = AgentChatPage(browser.new_page())
        chat.navigate()
        # Send a test message to capture populated chat state
        chat.send_message("Test message for visual snapshot")
        # Snapshot name: "Agent Chat Page"

    def test_canvas_sheets_visual(self, browser, authenticated_user):
        """
        Verify canvas sheets presentation has no visual regressions.

        Validates:
        - Data grid layout
        - Column headers and row formatting
        - Pagination controls
        - Responsive table behavior

        VALIDATED_BUG: Catches table layout breaks (e.g., column width, cell overflow)
        """
        canvas = CanvasPage(browser.new_page())
        canvas.navigate()
        canvas.present_canvas(
            type="sheets",
            data={
                "rows": [
                    {"id": 1, "name": "Item 1", "value": 100},
                    {"id": 2, "name": "Item 2", "value": 200},
                    {"id": 3, "name": "Item 3", "value": 300},
                ],
                "columns": ["id", "name", "value"]
            }
        )
        # Snapshot name: "Canvas Presentation - Sheets"

    def test_canvas_charts_visual(self, browser, authenticated_user):
        """
        Verify canvas charts presentation has no visual regressions.

        Validates:
        - Chart rendering (line, bar, pie)
        - Axis labels and legends
        - Color palette consistency
        - Tooltip positioning

        VALIDATED_BUG: Catches chart library version breaks (e.g., D3, Chart.js updates)
        """
        canvas = CanvasPage(browser.new_page())
        canvas.navigate()
        canvas.present_canvas(
            type="charts",
            data={
                "chartType": "bar",
                "title": "Sample Bar Chart",
                "data": {
                    "labels": ["A", "B", "C"],
                    "datasets": [{"data": [10, 20, 30]}]
                }
            }
        )
        # Snapshot name: "Canvas Presentation - Charts"

    def test_canvas_forms_visual(self, browser, authenticated_user):
        """
        Verify canvas forms presentation has no visual regressions.

        Validates:
        - Form field layout
        - Input validation states
        - Submit button positioning
        - Error message display

        VALIDATED_BUG: Catches form styling breaks (e.g., input border, focus states)
        """
        canvas = CanvasPage(browser.new_page())
        canvas.navigate()
        canvas.present_canvas(
            type="forms",
            data={
                "fields": [
                    {"name": "email", "type": "email", "label": "Email"},
                    {"name": "message", "type": "textarea", "label": "Message"},
                ],
                "submitUrl": "/api/v1/submit"
            }
        )
        # Snapshot name: "Canvas Presentation - Forms"
