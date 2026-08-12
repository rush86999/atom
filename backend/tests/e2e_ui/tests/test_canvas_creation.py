"""
E2E tests for canvas presentation creation workflow.

These tests drive the REAL rendering path — no phantom state injection:
1. A canvas is created as `Canvas` + `CanvasAudit` rows in the e2e database
   (the same store the running backend serves) via `tests/canvas_helpers.py`.
2. Tests navigate to the real route `http://localhost:3001/canvas/{id}`,
   where `pages/canvas/[id].tsx` loads `/api/canvas/{id}` from the backend
   and renders `CanvasPanel` (which mounts the same host UI as the chat page's
   `CanvasHost`).

Covered: host container rendering, close button, title display/truncation,
component type badge, version display (audit-trail count), save button
visibility for editable (sheet) vs read-only (snapshot/browser_view) canvases.

Run with: pytest backend/tests/e2e_ui/tests/test_canvas_creation.py -v
"""

import pytest
import uuid
from playwright.sync_api import Page
from sqlalchemy.orm import Session
from typing import Tuple

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.e2e_ui.pages.page_objects import CanvasHostPage
from tests.e2e_ui.tests.canvas_helpers import (
    append_update_audit,
    create_canvas,
    create_chart_canvas,
    create_form_canvas,
    create_markdown_canvas,
)
from core.models import User


def open_canvas_detail(page: Page, canvas_id: str) -> CanvasHostPage:
    """Navigate to the real /canvas/{id} route and wait for the host to render."""
    page.goto(f"http://localhost:3001/canvas/{canvas_id}")
    page.wait_for_load_state("networkidle")
    canvas_page = CanvasHostPage(page)
    canvas_page.wait_for_canvas_visible(timeout=10000)
    return canvas_page


def test_canvas_presented_from_chat(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test canvas presentation renders through the canvas detail route.

    This test verifies the happy path:
    1. Create test user + canvas rows in the DB (as the agent flow does)
    2. Navigate to /canvas/{id} (the real rendering route)
    3. Verify CanvasHostPage.is_loaded() returns True
    4. Verify canvas title and component badge display
    """
    user, _ = authenticated_user

    canvas_id = create_markdown_canvas(
        db_session, user, "Test Canvas from Chat", "# Test Canvas\n\nThis is a test canvas."
    )

    canvas_page = open_canvas_detail(authenticated_page, canvas_id)

    assert canvas_page.is_loaded() is True, "Canvas host should be loaded"
    assert canvas_page.is_visible() is True, "Canvas should be visible"

    # Verify title and component badge
    assert canvas_page.get_title() == "Test Canvas from Chat"
    assert canvas_page.get_component_type() == "markdown"


def test_canvas_close_button(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test canvas close button hides the canvas.

    This test verifies:
    1. Canvas appears when rendered
    2. Clicking close button hides canvas
    3. Canvas is no longer visible after close
    """
    user, _ = authenticated_user

    canvas_id = create_markdown_canvas(db_session, user, "Close Test", "Content")
    canvas_page = open_canvas_detail(authenticated_page, canvas_id)

    assert canvas_page.is_visible() is True, "Canvas should be visible before close"

    # Click close button
    canvas_page.close_canvas()
    canvas_page.wait_for_canvas_hidden(timeout=5000)

    # Verify canvas is hidden
    assert canvas_page.is_visible() is False, "Canvas should not be visible after close"


def test_canvas_title_displays(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test canvas title displays correctly (normal + long titles)."""
    user, _ = authenticated_user

    # Test with normal title
    normal_title = "Sales Report Q1 2026"
    canvas_id = create_markdown_canvas(db_session, user, normal_title, "Test content")
    canvas_page = open_canvas_detail(authenticated_page, canvas_id)
    assert canvas_page.get_title() == normal_title, "Normal title should display"

    # Test with very long title (truncated visually by CSS; textContent is full)
    long_title = "This is an extremely long canvas title that should be truncated by the max-w-[200px] CSS class in the header component"
    canvas_id = create_markdown_canvas(db_session, user, long_title, "Test content")
    canvas_page = open_canvas_detail(authenticated_page, canvas_id)

    displayed_title = canvas_page.get_title()
    assert displayed_title is not None, "Title should be displayed even if truncated"
    # The truncation is visual (CSS), textContent returns full text
    assert long_title in displayed_title or displayed_title in long_title


def test_canvas_component_badge(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test canvas component type badge displays correctly.

    Badge testid: canvas-type-{component} (CANVAS.TYPE_PREFIX in testIds.ts).
    """
    user, _ = authenticated_user

    # Test markdown component badge
    canvas_id = create_markdown_canvas(db_session, user, "Markdown Canvas", "# Markdown Test")
    canvas_page = open_canvas_detail(authenticated_page, canvas_id)
    assert canvas_page.get_component_type() == "markdown", "Badge should show 'markdown'"
    badge = authenticated_page.locator('[data-testid="canvas-type-markdown"]')
    assert badge.is_visible(), "Badge should carry the canvas-type-markdown testid"

    # Test form component badge
    canvas_id = create_form_canvas(db_session, user, [], "Form Canvas")
    canvas_page = open_canvas_detail(authenticated_page, canvas_id)
    assert canvas_page.get_component_type() == "form", "Badge should show 'form'"

    # Test chart component badge
    canvas_id = create_chart_canvas(
        db_session, user, "line_chart", [{"timestamp": "2026-01-01", "value": 1}], "Chart Canvas"
    )
    canvas_page = open_canvas_detail(authenticated_page, canvas_id)
    assert canvas_page.get_component_type() == "line_chart", "Badge should show 'line_chart'"


def test_canvas_version_display(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test canvas version number displays correctly.

    Version = count of append-only audit rows (each present/update appends
    one). The detail page derives it from the /api/canvas/{id}/history call.

    Verifies:
    1. Version number displays in header (format "v{n}")
    2. An update bumps the version
    """
    user, _ = authenticated_user

    canvas_id = create_markdown_canvas(db_session, user, "Versioned Canvas", "Versioned content")
    # Second audit row (update) → version v2
    append_update_audit(db_session, user, canvas_id, "markdown", "Versioned Canvas", "v2 content")

    canvas_page = open_canvas_detail(authenticated_page, canvas_id)

    # Verify version format
    version = canvas_page.get_version()
    assert version is not None, "Version should be displayed"
    assert version.startswith("v"), f"Version should start with 'v', got '{version}'"
    version_number = version[1:]
    assert version_number.isdigit(), "Version number should be numeric"
    assert version_number == "2", f"Expected v2 (present + update), got {version}"


def test_canvas_save_button_visibility(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test save button visibility based on canvas editability.

    The host shows "Save Changes" for editable canvases (sheet always shows
    it; markdown shows it only after edits) and never for read-only canvases
    (snapshot, browser_view).

    Verifies:
    1. Save button is NOT visible for read-only snapshot/browser_view
    2. Save button IS visible for the editable sheet canvas
    """
    user, _ = authenticated_user

    # Read-only snapshot canvas — no save button
    canvas_id = f"e2e-snapshot-{uuid.uuid4()}"
    create_canvas(
        db_session, user, canvas_id, "snapshot",
        "Snapshot Canvas",
        {"timestamp": "2026-02-23T12:00:00Z", "source": "test", "state": {"test": "data"}},
    )
    canvas_page = open_canvas_detail(authenticated_page, canvas_id)
    assert canvas_page.is_visible() is True, "Snapshot canvas should be visible"
    assert canvas_page.save_button.count() == 0, "Save button should not be visible for snapshot canvas"

    # Read-only browser_view — no save button
    canvas_id = f"e2e-browser-{uuid.uuid4()}"
    create_canvas(
        db_session, user, canvas_id, "browser_view",
        "Browser View Canvas",
        {"url": "https://example.com", "screenshot": ""},
    )
    canvas_page = open_canvas_detail(authenticated_page, canvas_id)
    assert canvas_page.is_visible() is True, "Browser view canvas should be visible"
    assert canvas_page.save_button.count() == 0, "Save button should not be visible for browser_view canvas"

    # Editable sheet canvas — save button always visible
    canvas_id = f"e2e-sheet-{uuid.uuid4()}"
    create_canvas(
        db_session, user, canvas_id, "sheet",
        "Editable Sheet",
        {"rows": [["A1", "B1"], ["A2", "B2"]]},
    )
    canvas_page = open_canvas_detail(authenticated_page, canvas_id)
    assert canvas_page.is_visible() is True, "Sheet canvas should be visible"
    assert canvas_page.save_button.count() > 0, "Save button should be visible for sheet canvas"
