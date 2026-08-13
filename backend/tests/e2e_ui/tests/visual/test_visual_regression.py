"""
Visual regression tests for critical pages.

These tests are structural visual-regression checks: they drive the REAL
pages with real data and assert the rendered structure of the critical
surfaces (layout anchors, chat wiring, canvas component rendering). They do
not use a snapshot service (no PERCY_TOKEN in local runs) — a snapshot tool
can be layered on top of the same page interactions.

Critical Pages Tested:
- Dashboard: Main user interface with navigation and overview
- Agent Chat: Core agent interaction interface (real testids:
  chat-container / agent-chat-input / send-message-button / message-list)
- Canvas Presentations: CanvasPanel on /canvas/{id} (real testids:
  canvas-container / canvas-type-{component}) for sheets, charts and forms

Maintenance:
- Selectors are the canonical frontend testids (frontend-nextjs/src/lib/testIds.ts)
- Canvas fixtures mirror tools/canvas_tool present rows (Canvas + CanvasAudit)
"""

from typing import Tuple
import pytest
from sqlalchemy.orm import Session

from core.models import User
from tests.e2e_ui.pages.page_objects import DashboardPage, ChatPage
from tests.e2e_ui.tests.canvas_helpers import (
    create_canvas,
    open_canvas,
    CANVAS_CONTAINER,
    canvas_type_badge,
)


class TestVisualRegression:
    """Visual regression tests for critical pages."""

    def test_dashboard_visual(self, authenticated_page, authenticated_user):
        """
        Verify dashboard page has no visual regressions.

        Validates:
        - Navigation layout (sidebar)
        - Dashboard welcome heading (real testid: dashboard-welcome-message)
        """
        dashboard = DashboardPage(authenticated_page)
        dashboard.navigate()

        # Navigation layout
        assert dashboard.welcome_message.is_visible(), \
            "Dashboard welcome message not rendered"
        assert dashboard.navigation_menu.is_visible(), \
            "Dashboard navigation menu not rendered"

    def test_agent_chat_visual(self, authenticated_page, authenticated_user):
        """
        Verify agent chat page has no visual regressions.

        Validates:
        - Chat container + input + send button wiring (real testids)
        - Message history renders a sent message (optimistic append — no
          LLM provider required for the user bubble)
        """
        chat = ChatPage(authenticated_page)
        chat.navigate()

        # Core chat wiring
        assert chat.chat_container.is_visible(), "Chat container not rendered"
        assert chat.chat_input.is_visible(), "Chat input not rendered"
        # Send button is disabled (but still rendered) until input has text;
        # while processing it is replaced by the Stop button. Under long-suite
        # load the interface can mount late — wait for either state.
        try:
            chat.send_button.wait_for(state="visible", timeout=15000)
            assert chat.send_button.count() > 0, "Send button not rendered"
        except Exception:
            authenticated_page.wait_for_selector(
                '[data-testid="send-message-button"], button[title="Stop Agent"]',
                timeout=15000,
            )

        # Send a test message and verify the user bubble renders in history
        test_message = f"Visual snapshot message {__import__('uuid').uuid4()}"
        chat.send_message(test_message)
        authenticated_page.wait_for_timeout(1000)

        user_texts = [m.text_content() for m in chat.user_message.all()]
        assert any(test_message in t for t in user_texts), \
            f"Sent message not rendered in chat history: {user_texts}"

    def test_canvas_sheets_visual(self, authenticated_page, authenticated_user, db_session):
        """
        Verify canvas sheets presentation has no visual regressions.

        Validates:
        - Canvas container (canvas-container)
        - Sheets type badge (canvas-type-sheet)
        - Data grid (table) with the presented rows
        """
        user, _ = authenticated_user
        content = {
            "rows": [
                ["Item 1", "100"],
                ["Item 2", "200"],
                ["Item 3", "300"],
            ],
            "columns": ["id", "name", "value"],
        }
        canvas_id = f"e2e-visual-sheets-{__import__('uuid').uuid4()}"
        create_canvas(db_session, user, canvas_id, "sheet", "Visual Sheets", content)

        open_canvas(authenticated_page, canvas_id, component="sheet")

        # Canvas container + type badge rendered
        assert authenticated_page.locator(CANVAS_CONTAINER).is_visible()
        assert authenticated_page.locator(canvas_type_badge("sheet")).is_visible()

        # Data grid rendered with rows
        table = authenticated_page.locator("table")
        assert table.is_visible(), "Sheets data grid not rendered"
        assert table.locator("tbody tr").count() >= 3, "Sheets grid missing presented rows"

    def test_canvas_charts_visual(self, authenticated_page, authenticated_user, db_session):
        """
        Verify canvas charts presentation has no visual regressions.

        Validates:
        - Canvas container (canvas-container)
        - Bar chart type badge (canvas-type-bar_chart)
        - Recharts chart SVG rendered with bars
        """
        user, _ = authenticated_user
        data = [
            {"name": "A", "value": 10},
            {"name": "B", "value": 20},
            {"name": "C", "value": 30},
        ]
        canvas_id = f"e2e-visual-charts-{__import__('uuid').uuid4()}"
        create_canvas(db_session, user, canvas_id, "bar_chart", "Visual Bar Chart", data)

        open_canvas(authenticated_page, canvas_id, component="bar_chart")

        # Canvas container + type badge rendered
        assert authenticated_page.locator(CANVAS_CONTAINER).is_visible()
        assert authenticated_page.locator(canvas_type_badge("bar_chart")).is_visible()

        # Recharts chart rendered with bars
        assert authenticated_page.locator(".recharts-wrapper").is_visible(), \
            "Chart SVG not rendered"
        assert authenticated_page.locator(".recharts-bar-rectangle").count() >= 3, \
            "Chart missing bars"

    def test_canvas_forms_visual(self, authenticated_page, authenticated_user, db_session):
        """
        Verify canvas forms presentation has no visual regressions.

        Validates:
        - Canvas container (canvas-container)
        - Form type badge (canvas-type-form)
        - Form fields rendered with labels and submit button
        """
        user, _ = authenticated_user
        fields = [
            {"name": "email", "type": "email", "label": "Email", "required": True},
            {"name": "message", "type": "textarea", "label": "Message"},
        ]
        canvas_id = f"e2e-visual-forms-{__import__('uuid').uuid4()}"
        create_canvas(
            db_session, user, canvas_id, "form", "Visual Form",
            {"schema": {"fields": fields}, "title": "Visual Form"},
        )

        open_canvas(authenticated_page, canvas_id, component="form")

        # Canvas container + type badge rendered
        assert authenticated_page.locator(CANVAS_CONTAINER).is_visible()
        assert authenticated_page.locator(canvas_type_badge("form")).is_visible()

        # Form fields rendered with labels
        assert authenticated_page.locator("label", has_text="Email").first.is_visible(), \
            "Email field not rendered"
        assert authenticated_page.locator("label", has_text="Message").first.is_visible(), \
            "Message field not rendered"
        assert authenticated_page.locator("button[type='submit']").is_visible(), \
            "Form submit button not rendered"
