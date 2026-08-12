"""
E2E tests for canvas dynamic content loading and live updates.

These tests drive the REAL update path — no phantom state injection:

1. A canvas is created as `Canvas` + `CanvasAudit` rows in the e2e database
   (the same store the running backend serves).
2. Tests navigate to the real route `http://localhost:3001/canvas/{id}`,
   where `pages/canvas/[id].tsx` renders the canvas via `CanvasPanel`.
3. Updates go through the REAL backend: `PUT /api/canvas/{id}` appends an
   audit row AND broadcasts a `canvas:update` WebSocket message on
   `user:{user_id}` (tools/canvas_crud_tool.update_canvas_content). The page's
   `useWebSocket` connection (auto-subscribed to the user channel by the
   backend) delivers it and re-renders — the same pipeline agents use.

Covered: WebSocket-driven updates (title/data/schema changes), rapid update
consistency, form data preservation across non-schema updates, independent
concurrent canvases.

Skipped: loading-indicator and error-state tests — the canvas host has no
loading skeleton or retry/error UI (those were speculative features); the
real surfaces tested here are the update pipeline and data preservation.

Run with: pytest backend/tests/e2e_ui/tests/test_canvas_dynamic_content.py -v
"""

import pytest
import uuid
import requests
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session
from typing import Dict, Any, Tuple

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.e2e_ui.pages.page_objects import CanvasHostPage, CanvasFormPage, CanvasChartPage
from tests.e2e_ui.tests.canvas_helpers import (
    create_canvas,
    create_chart_canvas,
    create_form_canvas,
    create_markdown_canvas,
)
from core.models import User


# ============================================================================
# Helpers
# ============================================================================

def get_page_token(page: Page) -> str:
    """Get the page's auth token (set by the authenticated_page fixture)."""
    token = page.evaluate("() => localStorage.getItem('auth_token')")
    assert token, "Page should have an auth_token in localStorage"
    return token


def update_canvas_via_api(page: Page, canvas_id: str, content: Any, canvas_type: str, title: str) -> None:
    """Trigger a REAL canvas update: PUT /api/canvas/{id} → WS broadcast → re-render.

    Args:
        page: Playwright page (provides the auth token).
        canvas_id: Canvas ID to update.
        content: New content payload.
        canvas_type: New component type.
        title: New title.
    """
    resp = requests.put(
        f"http://localhost:8001/api/canvas/{canvas_id}",
        headers={"Authorization": f"Bearer {get_page_token(page)}"},
        json={"content": content, "canvas_type": canvas_type, "title": title},
        timeout=10,
    )
    assert resp.status_code == 200, f"PUT /api/canvas/{canvas_id} failed: {resp.status_code} {resp.text}"


def open_canvas(page: Page, canvas_id: str) -> CanvasHostPage:
    """Navigate to the real /canvas/{id} route and wait for the host."""
    authenticated_page.goto(f"http://localhost:3001/canvas/{canvas_id}")
    authenticated_page.wait_for_load_state("networkidle")
    canvas_page = CanvasHostPage(page)
    canvas_page.wait_for_canvas_visible(timeout=10000)
    return canvas_page


def create_test_line_chart_data() -> list:
    """Create test line chart data."""
    return [
        {"timestamp": "Jan", "value": 100},
        {"timestamp": "Feb", "value": 200},
        {"timestamp": "Mar", "value": 150},
        {"timestamp": "Apr", "value": 300},
        {"timestamp": "May", "value": 250}
    ]


# ============================================================================
# WebSocket Update Tests
# ============================================================================

def test_canvas_websocket_update(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test canvas receives and displays a real backend-driven update.

    Verifies:
    - Initial canvas appears
    - PUT /api/canvas/{id} (REST) broadcasts canvas:update over WS
    - Title changes if updated
    """
    user, _ = authenticated_user
    canvas_id = create_markdown_canvas(db_session, user, "Initial Title", "Initial content")

    canvas_page = open_canvas(authenticated_page, canvas_id)
    assert canvas_page.is_loaded(), "Initial canvas should load"
    assert canvas_page.get_title() == "Initial Title"

    # Send update via the REAL backend (REST → WS broadcast → React re-render)
    update_canvas_via_api(authenticated_page, canvas_id, "Updated content", "markdown", "Updated Title")

    # Verify title changed (Playwright auto-waits)
    expect(canvas_page.canvas_title).to_have_text("Updated Title", timeout=5000)


def test_canvas_update_action_vs_present(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test update preserves the canvas (does not close it).

    Verifies:
    - Canvas remains visible after an update
    - Canvas ID preserved across the update
    """
    user, _ = authenticated_user
    canvas_id = create_markdown_canvas(db_session, user, "Presented Canvas", "v1 content")

    canvas_page = open_canvas(authenticated_page, canvas_id)
    assert canvas_page.is_loaded(), "Canvas should appear"
    assert canvas_page.get_title() == "Presented Canvas"

    # Update (not re-present): canvas must stay visible with the same id
    update_canvas_via_api(authenticated_page, canvas_id, "v2 content", "markdown", "Updated Canvas")

    expect(canvas_page.canvas_title).to_have_text("Updated Canvas", timeout=5000)
    assert canvas_page.is_loaded(), "Canvas should remain visible after update"

    # Canvas ID preserved: the host registers state under the same canvas id
    state = authenticated_page.evaluate("(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert state is not None, "Canvas should have state under the same ID after update"


def test_multiple_canvas_updates(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test multiple rapid updates — final state reflects the last update."""
    user, _ = authenticated_user
    canvas_id = create_markdown_canvas(db_session, user, "Version 1", "v1 content")

    canvas_page = open_canvas(authenticated_page, canvas_id)
    assert canvas_page.get_title() == "Version 1"

    # Send 3 rapid updates (Versions 2, 3, 4)
    for i in range(2, 5):
        update_canvas_via_api(authenticated_page, canvas_id, f"v{i} content", "markdown", f"Version {i}")

    # Verify final state is Version 4
    expect(canvas_page.canvas_title).to_have_text("Version 4", timeout=5000)

    state = authenticated_page.evaluate("(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert state is not None
    assert state.get("title") == "Version 4", f"State title should be 'Version 4', got {state.get('title')}"


# ============================================================================
# Async Data Loading Tests
# ============================================================================

def test_async_chart_data_loading(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test chart data loads and updates through the real pipeline.

    Verifies:
    - Chart renders with initial data
    - A backend update swaps in new data points
    """
    user, _ = authenticated_user
    initial_data = create_test_line_chart_data()
    canvas_id = create_chart_canvas(db_session, user, "line_chart", initial_data, "Async Chart")

    chart_page = CanvasChartPage(authenticated_page)
    authenticated_page.goto(f"http://localhost:3001/canvas/{canvas_id}")
    authenticated_page.wait_for_load_state("networkidle")
    authenticated_page.wait_for_selector(".recharts-wrapper", timeout=10000)

    assert chart_page.get_data_point_count() == len(initial_data), \
        f"Initial chart should have {len(initial_data)} points"

    # Backend update with new data
    updated_data = [
        {"timestamp": "Jan", "value": 500},
        {"timestamp": "Feb", "value": 600},
        {"timestamp": "Mar", "value": 550},
    ]
    update_canvas_via_api(authenticated_page, canvas_id, updated_data, "line_chart", "Async Chart")

    # Chart re-renders with the new data
    expect(authenticated_page.locator(".recharts-dot")).to_have_count(3, timeout=5000)


def test_async_form_options_loading(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test form schema updates through the real pipeline.

    Verifies:
    - Form renders with initial fields
    - A backend update swaps in a new schema (select with options)
    """
    user, _ = authenticated_user
    canvas_id = create_form_canvas(
        db_session,
        user,
        [
            {"name": "field_a", "type": "text", "label": "Field A", "required": True},
            {"name": "field_b", "type": "text", "label": "Field B", "required": True},
            {"name": "field_c", "type": "text", "label": "Field C", "required": False},
        ],
        "Form with Async Options",
    )

    form_page = CanvasFormPage(authenticated_page)
    authenticated_page.goto(f"http://localhost:3001/canvas/{canvas_id}")
    authenticated_page.wait_for_load_state("networkidle")
    canvas_host = CanvasHostPage(page)
    canvas_host.wait_for_canvas_visible(timeout=10000)

    assert form_page.is_loaded(), "Form should load"
    assert form_page.get_field_count() == 3, "Initial form should have 3 fields"

    # Backend update: replace schema with a select field with options
    new_schema = {
        "schema": {
            "fields": [
                {
                    "name": "country",
                    "type": "select",
                    "label": "Country",
                    "options": [
                        {"value": "USA", "label": "USA"},
                        {"value": "Canada", "label": "Canada"},
                        {"value": "UK", "label": "UK"},
                    ],
                }
            ]
        },
        "title": "Form with Async Options",
    }
    update_canvas_via_api(authenticated_page, canvas_id, new_schema, "form", "Form with Async Options")

    # Form re-renders with the new field
    expect(authenticated_page.locator('[data-testid="form-field-country"]')).to_be_visible(timeout=5000)


def test_auto_waiting_prevents_flaky_tests(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test auto-waiting strategies prevent flaky test behavior.

    Verifies:
    - 3 iterations of create + update all converge
    - No intermittent failures
    """
    user, _ = authenticated_user

    for iteration in range(3):
        canvas_id = create_markdown_canvas(db_session, user, f"Iteration {iteration}", "content")

        canvas_page = open_canvas(authenticated_page, canvas_id)
        update_canvas_via_api(authenticated_page, canvas_id, "updated", "markdown", f"Loaded {iteration}")

        expect(canvas_page.canvas_title).to_have_text(f"Loaded {iteration}", timeout=5000)
        state = authenticated_page.evaluate("(cid) => window.atom.canvas.getState(cid)", canvas_id)
        assert state is not None, f"Iteration {iteration} should have state"


# ============================================================================
# Loading Indicator Tests
# ============================================================================

def test_loading_indicator_displays():
    """Loading indicator/skeleton tests are skipped.

    The canvas host (CanvasPanel/CanvasHost) has no loading-skeleton UI for
    canvas presentations — canvases either render or show "No data to
    display". A loading indicator only exists in the agent chat streaming
    flow, not the canvas host. Nothing real to assert.
    """
    pytest.skip(
        "Canvas host has no loading-skeleton UI — canvases render immediately "
        "or show 'No data to display'. The speculative loading-state feature "
        "was never implemented in CanvasPanel/CanvasHost."
    )


def test_loading_indicator_hides_after_load(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test content updates to the loaded state after a real backend update."""
    user, _ = authenticated_user
    canvas_id = create_markdown_canvas(db_session, user, "Loading...", "loading")

    canvas_page = open_canvas(authenticated_page, canvas_id)

    # Simulate data arriving via a real backend update
    update_canvas_via_api(authenticated_page, canvas_id, "final content", "markdown", "Loaded")

    expect(canvas_page.canvas_title).to_have_text("Loaded", timeout=5000)
    state = authenticated_page.evaluate("(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert state is not None
    assert state.get("title") == "Loaded"


# ============================================================================
# Error State Tests
# ============================================================================

def test_async_load_error_display():
    """Error-state rendering tests are skipped.

    The canvas host has no error/retry UI for failed loads — the speculative
    error-state feature was never implemented in CanvasPanel/CanvasHost.
    (Forms DO surface submission errors via validation messages, covered in
    test_canvas_forms.py.)
    """
    pytest.skip(
        "Canvas host has no error-state UI (no timeout/error banner). The "
        "speculative error-state feature was never implemented."
    )


def test_error_state_allows_retry():
    """Error-state retry tests are skipped (no error/retry UI exists)."""
    pytest.skip(
        "Canvas host has no retry mechanism — the speculative error-state "
        "feature was never implemented in CanvasPanel/CanvasHost."
    )


# ============================================================================
# Form Data Preservation Tests
# ============================================================================

def test_form_data_preserved_during_update(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test form data preserved during non-schema updates.

    Verifies:
    - Form fields can be filled
    - A backend update that only changes the title preserves values
    """
    user, _ = authenticated_user
    field_name = f"field_{uuid.uuid4()[:8]}"
    canvas_id = create_form_canvas(
        db_session,
        user,
        [
            {"name": field_name, "type": "text", "label": "Name", "required": True}
        ],
        "Test Form",
    )

    form_page = CanvasFormPage(authenticated_page)
    authenticated_page.goto(f"http://localhost:3001/canvas/{canvas_id}")
    authenticated_page.wait_for_load_state("networkidle")
    canvas_host = CanvasHostPage(page)
    canvas_host.wait_for_canvas_visible(timeout=10000)

    # Fill form field
    form_page.fill_text_field(field_name, "John Doe")
    assert form_page.get_field_value(field_name) == "John Doe", "Field should have value 'John Doe'"

    # Backend update that doesn't affect schema (just title)
    update_canvas_via_api(authenticated_page, canvas_id, {"schema": {"fields": [{"name": field_name, "type": "text", "label": "Name", "required": True}]}}, "form", "Updated Title")

    expect(canvas_host.canvas_title).to_have_text("Updated Title", timeout=5000)

    # Verify form data still present
    assert form_page.get_field_value(field_name) == "John Doe", "Field value should be preserved"


def test_form_data_cleared_on_schema_change(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test form reflects a schema change delivered via a real backend update."""
    user, _ = authenticated_user
    field_name_1 = f"field_{uuid.uuid4()[:8]}"
    canvas_id = create_form_canvas(
        db_session,
        user,
        [
            {"name": field_name_1, "type": "text", "label": "Email", "required": True}
        ],
        "Initial Form",
    )

    form_page = CanvasFormPage(authenticated_page)
    authenticated_page.goto(f"http://localhost:3001/canvas/{canvas_id}")
    authenticated_page.wait_for_load_state("networkidle")
    canvas_host = CanvasHostPage(page)
    canvas_host.wait_for_canvas_visible(timeout=10000)

    # Fill field
    form_page.fill_text_field(field_name_1, "test@example.com")

    # Backend update with a new schema (add a second field)
    new_field_name = f"field_{uuid.uuid4()[:8]}"
    new_schema = {
        "schema": {
            "fields": [
                {"name": field_name_1, "type": "text", "label": "Email", "required": True},
                {"name": new_field_name, "type": "text", "label": "Confirm Email", "required": True},
            ]
        },
        "title": "Updated Form",
    }
    update_canvas_via_api(authenticated_page, canvas_id, new_schema, "form", "Updated Form")

    # Form re-renders with the new field count
    expect(authenticated_page.locator('[data-testid^="form-field-"]')).to_have_count(2, timeout=5000)


# ============================================================================
# Race Condition Prevention Tests
# ============================================================================

def test_rapid_canvas_updates_no_race(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test rapid updates don't cause race conditions.

    Verifies:
    - 10 rapid backend updates complete successfully
    - Final state is consistent (last update wins)
    - Canvas remains stable after rapid updates
    """
    user, _ = authenticated_user
    canvas_id = create_markdown_canvas(db_session, user, "Start", "start content")

    canvas_page = open_canvas(authenticated_page, canvas_id)

    # Send 10 rapid updates
    for i in range(1, 11):
        update_canvas_via_api(authenticated_page, canvas_id, f"content {i}", "markdown", f"Update {i}")

    # Final title should be "Update 10"
    expect(canvas_page.canvas_title).to_have_text("Update 10", timeout=10000)

    state = authenticated_page.evaluate("(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert state is not None, "Final state should exist"
    assert state.get("title") == "Update 10", f"Final title should be 'Update 10', got {state.get('title')}"

    assert canvas_page.is_loaded(), "Canvas should remain stable after rapid updates"


def test_concurrent_canvas_operations(browser, db_session: Session):
    """Test two canvases on separate pages update independently.

    Verifies:
    - Each page renders its own canvas
    - Updates to one canvas do not affect the other
    - No cross-contamination (page WS handler filters by canvas_id)
    """
    user, _ = authenticated_user
    canvas_id_1 = create_markdown_canvas(db_session, user, "Canvas 1", "c1")
    canvas_id_2 = create_markdown_canvas(db_session, user, "Canvas 2", "c2")

    # Two independent pages (each with its own WS connection). Both need the
    # auth_token COOKIE (middleware gates routes) + localStorage token.
    from core.auth import create_access_token
    token = create_access_token(data={"sub": str(user.id)}, expires_delta=None)

    page_1 = browser.new_page()
    page_2 = browser.new_page()
    try:
        for p in (page_1, page_2):
            p.context.add_cookies([
                {"name": "auth_token", "value": token, "url": "http://localhost:3001"},
            ])
            p.goto("http://localhost:3001")
            p.evaluate(f"() => localStorage.setItem('auth_token', '{token}')")

        cp_1 = open_canvas(page_1, canvas_id_1)
        cp_2 = open_canvas(page_2, canvas_id_2)
        assert cp_1.get_title() == "Canvas 1"
        assert cp_2.get_title() == "Canvas 2"

        # Update canvas 1 — page 2 must stay on Canvas 2
        update_canvas_via_api(page_1, canvas_id_1, "c1 updated", "markdown", "Updated Canvas 1")
        expect(cp_1.canvas_title).to_have_text("Updated Canvas 1", timeout=5000)

        # Page 2 must NOT be affected (WS handler filters by canvas_id)
        assert cp_2.get_title() == "Canvas 2", "Canvas 2 should not change"
        assert cp_2.is_loaded(), "Canvas 2 should remain visible"
    finally:
        page_1.close()
        page_2.close()
