"""
E2E Tests for Terminal Canvas Rendering (CANV-06).

The terminal is a chat-flow-only canvas component: CanvasPanel (the renderer
on the real /canvas/{id} route) has NO terminal case in its component switch —
an unknown type falls through to the "Custom Component" fallback panel, which
shows the type badge and the raw payload. There is no terminal renderer that
a DB-backed canvas can reach without an LLM/WS message, so:

- 1 test verifies the REAL graceful-degradation path (unknown type renders
  the custom fallback panel with the type badge and payload).
- 5 tests are documented skips (no terminal-specific rendering path exists).

Reference: frontend-nextjs/components/canvas/CanvasPanel.tsx switch().
"""

import uuid
from typing import Tuple

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.models import CanvasAudit, User
from tests.e2e_ui.tests.canvas_helpers import create_canvas, open_canvas


# =============================================================================
# Helper Functions
# =============================================================================

def create_terminal_canvas(db: Session, user: User, output: str, title: str = "Terminal Output") -> str:
    """Create a terminal canvas whose content carries the output text."""
    canvas_id = f"e2e-terminal-{uuid.uuid4()}"
    create_canvas(db, user, canvas_id, "terminal", title, {"output": output})
    return canvas_id


def open_terminal_canvas(page: Page, canvas_id: str) -> None:
    """Navigate to a terminal canvas and wait for the fallback panel."""
    open_canvas(page, canvas_id, "terminal")


# =============================================================================
# Terminal Canvas Rendering Tests
# =============================================================================

def test_terminal_displays_output(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that an unknown canvas type degrades gracefully: the CanvasPanel
    fallback renders the type badge and the raw payload (real behavior).

    Verifies:
    - CanvasPanel container with terminal type badge
    - Custom Component fallback panel shows the payload
    - CanvasAudit record created
    """
    user, _ = authenticated_user
    terminal_output = "Line 1: Starting process...\nLine 5: Process complete."
    canvas_id = create_terminal_canvas(db_session, user, terminal_output, "Terminal Output")

    open_terminal_canvas(authenticated_page, canvas_id)

    container = authenticated_page.locator('[data-testid="canvas-container"]')
    container_text = container.inner_text()
    assert "terminal" in container_text, "Type badge should show the terminal type"
    # Fallback panel label + raw payload.
    assert "Custom Component: terminal" in container_text, "Fallback panel should label the component"
    assert "Starting process..." in container_text, "Payload should be rendered in the fallback panel"

    audit = db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == canvas_id).all()
    assert len(audit) >= 1, "CanvasAudit record should exist for the canvas"


def test_terminal_scrollable(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Terminal scrolling: no terminal renderer exists on the /canvas/{id}
    route — unknown types hit the fallback panel. Documented skip."""
    pytest.skip(
        "CanvasPanel has no 'terminal' case; the fallback panel is static. "
        "No scrollable terminal surface to verify — see CanvasPanel.tsx."
    )


def test_terminal_monospace_font(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Terminal monospace font: no terminal renderer exists on the /canvas/{id}
    route. Documented skip."""
    pytest.skip(
        "CanvasPanel has no 'terminal' case; no monospace terminal surface "
        "exists to verify — see CanvasPanel.tsx."
    )


def test_terminal_empty_output(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Terminal empty state: no terminal renderer exists on the /canvas/{id}
    route. Documented skip."""
    pytest.skip(
        "CanvasPanel has no 'terminal' case; the fallback panel always shows "
        "the payload. No empty-state terminal surface to verify."
    )


def test_terminal_line_breaks_preserved(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Terminal line breaks: no terminal renderer exists on the /canvas/{id}
    route. Documented skip."""
    pytest.skip(
        "CanvasPanel has no 'terminal' case; line-break rendering is not "
        "testable without a terminal surface — see CanvasPanel.tsx."
    )


def test_terminal_special_characters(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Terminal special characters: no terminal renderer exists on the
    /canvas/{id} route. Documented skip."""
    pytest.skip(
        "CanvasPanel has no 'terminal' case; special-character rendering is "
        "not testable without a terminal surface — see CanvasPanel.tsx."
    )
