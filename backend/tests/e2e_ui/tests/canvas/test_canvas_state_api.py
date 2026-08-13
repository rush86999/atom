"""
Canvas State API E2E Tests.

Tests the real canvas state API surface — `window.atom.canvas` backed by
`useCanvasStateRegistration` (frontend-nextjs/hooks/useCanvasStateRegistration.ts)
and the InteractiveForm shadowing patch. No phantom state injection:

1. A canvas is created as real `Canvas` + `CanvasAudit` rows (canvas_helpers).
2. Tests navigate to `http://localhost:3001/canvas/{id}` — the route mounts
   CanvasPanel (and the page-level registration), so the registry is real.
3. State is read back via `window.atom.canvas.getState(id)` /
   `getAllStates()` / `subscribe(id, cb)`.

Real state shapes:
- chart canvases:  {type: 'generic', component: 'line_chart'|..., title, data}
- form canvases:   FormCanvasState {canvas_id, component: 'form', form_schema,
  form_data, validation_errors, submit_enabled, submitted} (shadow-patch)
- markdown canvases: {type: 'generic', component: 'markdown', title, text, html}
- sheet canvases:  {type: 'sheets', cells, sheetName, activeCell}

Coverage: CANV-09 (canvas state API)
"""

import uuid
from typing import Tuple

from playwright.sync_api import Page
from sqlalchemy.orm import Session

# Add backend to path for imports
import os
import sys
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.models import User
from tests.e2e_ui.tests.canvas_helpers import (
    create_chart_canvas, create_form_canvas, create_markdown_canvas, create_canvas, open_canvas,
)


# ============================================================================
# Helper Functions
# ============================================================================

def get_canvas_state(page: Page, canvas_id: str) -> dict:
    """Get canvas state via the real window.atom.canvas.getState API."""
    return page.evaluate(f"() => window.atom.canvas.getState('{canvas_id}')")


def get_all_canvas_states(page: Page) -> list:
    """Get all registered canvas states via window.atom.canvas.getAllStates."""
    return page.evaluate("() => window.atom.canvas.getAllStates()")


def open_stateful_canvas(page: Page, canvas_id: str, component: str) -> None:
    """Navigate to /canvas/{id} and wait for the state registry to populate."""
    open_canvas(page, canvas_id, component)
    page.wait_for_function(
        "() => window.atom && window.atom.canvas && typeof window.atom.canvas.getState === 'function'",
        timeout=10000,
    )


def line_chart_data(point_count: int = 3) -> list:
    return [
        {"timestamp": f"2024-03-0{i + 1} 12:00", "value": 10 + i * 5}
        for i in range(point_count)
    ]


# ============================================================================
# Tests
# ============================================================================

def test_canvas_state_api_exists(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that window.atom.canvas exists with getState/getAllStates/subscribe.

    The API is created by useCanvasStateRegistration when a canvas mounts on
    the real /canvas/{id} route.
    """
    user, _ = authenticated_user
    canvas_id = create_chart_canvas(db_session, user, "line_chart", line_chart_data(2), "API Existence Test")
    open_stateful_canvas(authenticated_page, canvas_id, "line_chart")

    assert authenticated_page.evaluate("() => typeof window.atom !== 'undefined'"), "window.atom should exist"
    assert authenticated_page.evaluate("() => typeof window.atom?.canvas !== 'undefined'"), "window.atom.canvas should exist"
    assert authenticated_page.evaluate("() => typeof window.atom.canvas.getState") == "function"
    assert authenticated_page.evaluate("() => typeof window.atom.canvas.getAllStates") == "function"
    assert authenticated_page.evaluate("() => typeof window.atom.canvas.subscribe") == "function"


def test_canvas_state_contains_correct_data(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that getState returns the registered canvas state with its data."""
    user, _ = authenticated_user
    data = line_chart_data(3)
    canvas_id = create_chart_canvas(db_session, user, "line_chart", data, "Correct Data Test")
    open_stateful_canvas(authenticated_page, canvas_id, "line_chart")

    state = get_canvas_state(authenticated_page, canvas_id)
    assert state is not None, "getState should return the registered state"

    # CanvasPanel registers {type, component, title, data} for chart types.
    assert state["component"] == "line_chart", f"component should be 'line_chart', got {state.get('component')}"
    assert state["title"] == "Correct Data Test", "title should match the canvas title"
    assert state["data"] == data, "State data should be the chart data array"


def test_canvas_state_updates_on_interaction(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that state reflects form field changes after user input.

    InteractiveForm registers a FormCanvasState and shadows getState for its
    canvas id, so form_data is observable live.
    """
    user, _ = authenticated_user
    fields = [{"name": "name", "type": "text", "label": "Name", "required": True}]
    canvas_id = create_form_canvas(db_session, user, fields, "State Update Test")
    open_stateful_canvas(authenticated_page, canvas_id, "form")
    authenticated_page.wait_for_selector('[data-testid="form-field-name"]', timeout=10000)

    initial_state = get_canvas_state(authenticated_page, canvas_id)
    assert initial_state is not None and initial_state.get("component") == "form", (
        "Form should register a form state"
    )
    assert initial_state["form_data"].get("name") == "", "Initial form_data should be empty"

    test_value = "Test Value"
    authenticated_page.locator('[data-testid="form-field-name"]').fill(test_value)

    # Wait for the form's state effect to re-patch getState with new form_data.
    authenticated_page.wait_for_function(
        """(id) => {
            const s = window.atom.canvas.getState(id);
            return s && s.form_data && s.form_data.name === 'Test Value';
        }""",
        arg=canvas_id,
        timeout=5000,
    )

    updated_state = get_canvas_state(authenticated_page, canvas_id)
    assert updated_state["form_data"]["name"] == test_value, (
        f"State should reflect the filled value, got {updated_state['form_data'].get('name')}"
    )


def test_canvas_state_for_all_canvas_types(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that the state API serves the correct shape per canvas type."""
    user, _ = authenticated_user

    # Chart canvas → generic state with component + data.
    chart_id = create_chart_canvas(db_session, user, "pie_chart", [{"name": "A", "value": 1}], "Chart State Test")
    open_stateful_canvas(authenticated_page, chart_id, "pie_chart")
    chart_state = get_canvas_state(authenticated_page, chart_id)
    assert chart_state is not None and chart_state["component"] == "pie_chart", "Chart state shape wrong"

    # Form canvas → FormCanvasState with form_schema.
    form_id = create_form_canvas(db_session, user, [{"name": "test", "type": "text", "label": "Test"}], "Form State Test")
    open_stateful_canvas(authenticated_page, form_id, "form")
    authenticated_page.wait_for_selector('[data-testid="form-field-test"]', timeout=10000)
    form_state = get_canvas_state(authenticated_page, form_id)
    assert form_state is not None and form_state["component"] == "form", "Form state shape wrong"
    assert form_state["form_schema"]["fields"][0]["name"] == "test", "Form schema should carry fields"

    # Markdown canvas → generic state with text content.
    docs_id = create_markdown_canvas(db_session, user, "Docs State Test", "# Header\n\nTest content")
    open_stateful_canvas(authenticated_page, docs_id, "markdown")
    docs_state = get_canvas_state(authenticated_page, docs_id)
    assert docs_state is not None and docs_state["component"] == "markdown", "Docs state shape wrong"
    assert "Test content" in docs_state.get("text", ""), "Docs state should carry the markdown text"


def test_canvas_state_getAllStates_method(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that getAllStates returns the currently registered canvas states.

    The registry is per-page: navigating to a new /canvas/{id} replaces the
    previous registration (useCanvasStateRegistration cleans up on id change),
    so each visit must observe its own canvas in getAllStates.
    """
    user, _ = authenticated_user
    ids = [
        create_chart_canvas(db_session, user, "line_chart", line_chart_data(1), "GetAll Test 1"),
        create_form_canvas(db_session, user, [{"name": "test", "type": "text", "label": "Test"}], "GetAll Test 2"),
        create_markdown_canvas(db_session, user, "GetAll Test 3", "# Test"),
    ]

    for canvas_id in ids:
        component = "line_chart" if "line" in canvas_id else ("form" if "form" in canvas_id else "markdown")
        open_stateful_canvas(authenticated_page, canvas_id, component)
        if component == "form":
            authenticated_page.wait_for_selector('[data-testid="form-field-test"]', timeout=10000)

        all_states = get_all_canvas_states(authenticated_page)
        assert isinstance(all_states, list), "getAllStates should return a list"
        current_ids = [s.get("canvas_id") for s in all_states if isinstance(s, dict)]
        assert canvas_id in current_ids, f"getAllStates should include the current canvas {canvas_id}, got {current_ids}"
        # Note: a form canvas legitimately appears twice (its own shadow entry
        # plus the host registration) — check presence, not count.
        assert len(set(current_ids)) >= 1, "Canvas ids in getAllStates should be present"


def test_canvas_state_subscribe_method(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that subscribe(id, cb) fires when the canvas state changes.

    Uses a sheet canvas: editing a cell input updates the registered state
    (cells), which notifies subscribers with (canvasId, state).
    """
    user, _ = authenticated_user
    canvas_id = f"e2e-sheet-{uuid.uuid4()}"
    create_canvas(db_session, user, canvas_id, "sheet", "Subscribe Test", [["A1", "B1"], ["A2", "B2"]])
    open_stateful_canvas(authenticated_page, canvas_id, "sheet")
    authenticated_page.wait_for_selector('[data-testid="canvas-container"] tbody td input', timeout=10000)

    # Attach a subscriber that records (canvasId, cells) updates.
    authenticated_page.evaluate(
        """(id) => {
            window.__canvasSubUpdates = [];
            window.atom.canvas.subscribe(id, (cid, state) => {
                window.__canvasSubUpdates.push({
                    canvas_id: cid,
                    cells: state && state.cells ? JSON.parse(JSON.stringify(state.cells)) : null,
                });
            });
        }""",
        canvas_id,
    )

    # Edit the first cell — must trigger a registry update.
    authenticated_page.locator('[data-testid="canvas-container"] tbody td input').first.fill("42")

    authenticated_page.wait_for_function(
        """(id) => {
            const updates = window.__canvasSubUpdates || [];
            const last = updates[updates.length - 1];
            return last && last.canvas_id === id && last.cells && last.cells[0][0] === '42';
        }""",
        arg=canvas_id,
        timeout=5000,
    )

    update_count = authenticated_page.evaluate("() => (window.__canvasSubUpdates || []).length")
    assert update_count > 0, f"Subscription callback should fire at least once, got {update_count}"
