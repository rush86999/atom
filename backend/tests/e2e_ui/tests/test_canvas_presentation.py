"""
E2E Tests for Canvas Presentation Workflows.

Tests verify complete canvas workflows through the REAL rendering path —
no phantom state injection and no weakened "assert True" fallbacks:

1. Chart presentation (line, bar, pie) via /canvas/{id} (DB-created canvases)
2. Form submission and success state
3. Agent-readable state exposure (the AI-accessibility contract)
4. Canvas update lifecycle (PUT /api/canvas/{id} → WS broadcast → re-render)
5. State serialization with complex data (unicode, special chars)

Run with: pytest backend/tests/e2e_ui/tests/test_canvas_presentation.py -v
"""

import pytest
import re
import uuid
import json
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session
from typing import Tuple

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.e2e_ui.pages.page_objects import CanvasHostPage, CanvasChartPage, CanvasFormPage
from tests.e2e_ui.tests.canvas_helpers import (
    create_canvas,
    create_chart_canvas,
    create_form_canvas,
    create_markdown_canvas,
)
from core.models import User, Canvas, CanvasAudit


def open_canvas(page: Page, canvas_id: str) -> CanvasHostPage:
    """Navigate to the real /canvas/{id} route and wait for the host."""
    authenticated_page.goto(f"http://localhost:3001/canvas/{canvas_id}")
    authenticated_page.wait_for_load_state("networkidle")
    canvas_page = CanvasHostPage(page)
    canvas_page.wait_for_canvas_visible(timeout=10000)
    return canvas_page


# =============================================================================
# Chart Presentation Tests
# =============================================================================

@pytest.mark.e2e
def test_canvas_chart_presentation(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test chart canvas presentation workflow via the real /canvas/{id} route.

    Verifies:
    1. Chart canvas created in the DB (as present_chart() would)
    2. /canvas/{id} renders the Recharts line chart
    3. Chart SVG + host container are visible
    """
    user, _ = authenticated_user
    data = [
        {"timestamp": "2024-02-23 12:00", "value": 10, "label": "A"},
        {"timestamp": "2024-02-24 12:00", "value": 20, "label": "B"},
        {"timestamp": "2024-02-25 12:00", "value": 30, "label": "C"},
    ]
    canvas_id = create_chart_canvas(db_session, user, "line_chart", data, "Sales Data")

    canvas_page = open_canvas(authenticated_page, canvas_id)

    assert canvas_page.is_loaded() is True, "Canvas host should be loaded"
    assert canvas_page.get_component_type() == "line_chart", "Badge should show line_chart"

    chart_page = CanvasChartPage(authenticated_page)
    assert chart_page.is_loaded(), "Line chart should render"
    assert chart_page.get_chart_type() == "line"
    assert chart_page.get_data_point_count() == len(data)


@pytest.mark.e2e
def test_canvas_form_submission(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test canvas form submission workflow via the real /canvas/{id} route.

    Verifies:
    1. Form canvas created in the DB (as present_form() would)
    2. /canvas/{id} renders the InteractiveForm
    3. Filling + submitting shows the success state
    """
    user, _ = authenticated_user
    canvas_id = create_form_canvas(
        db_session,
        user,
        [
            {"name": "email", "type": "email", "label": "Email", "required": True},
            {"name": "message", "type": "text", "label": "Message", "required": True},
        ],
        "Contact Form",
    )

    open_canvas(authenticated_page, canvas_id)
    form_page = CanvasFormPage(authenticated_page)

    assert form_page.is_loaded() is True, "Form should render"

    form_page.fill_email_field("email", f"e2e{uuid.uuid4()[:8]}@test.com")
    form_page.fill_text_field("message", "Test message from E2E test")
    form_page.click_submit()

    form_page.wait_for_submission(timeout=5000)
    assert form_page.is_success_message_visible() is True, "Success message should appear"


@pytest.mark.e2e
def test_canvas_accessibility_tree(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test the agent-readable state exposure (the app's accessibility layer).

    Verifies:
    1. A rendered chart registers its state with window.atom.canvas
    2. State contains required fields (canvas_id, component, timestamp)
    3. State survives JSON serialization (agent read-back contract)
    """
    user, _ = authenticated_user
    data = [
        {"timestamp": "2024-02-23 12:00", "value": 100},
        {"timestamp": "2024-02-24 12:00", "value": 150},
    ]
    canvas_id = create_chart_canvas(db_session, user, "line_chart", data, "A11y Canvas")

    open_canvas(authenticated_page, canvas_id)

    states = authenticated_page.evaluate(
        "() => { if (window.atom?.canvas?.getAllStates) { return window.atom.canvas.getAllStates(); } return []; }"
    )
    assert isinstance(states, list)
    chart_states = [
        s["state"] for s in states
        if (s.get("state") or {}).get("component") == "line_chart"
    ]
    assert len(chart_states) >= 1, "Line chart should register its state"
    state = chart_states[0]

    # Required fields
    for field in ("canvas_id", "component", "timestamp"):
        assert field in state, f"State should have required field '{field}'"
        assert isinstance(state[field], str) and state[field], \
            f"Field '{field}' should be a non-empty string"

    # JSON round-trip
    assert json.loads(json.dumps(state)) == state, "State should survive JSON serialization"


# =============================================================================
# Canvas Type Tests
# =============================================================================

@pytest.mark.e2e
def test_canvas_multiple_chart_types(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test multiple chart types render correctly via the real route."""
    user, _ = authenticated_user

    for chart_type, component in [("line", "line_chart"), ("bar", "bar_chart"), ("pie", "pie_chart")]:
        data = [
            {"timestamp": f"P{i}", "value": i * 10} if chart_type == "line"
            else {"name": f"Cat{i}", "value": i * 10}
            for i in range(3)
        ]
        canvas_id = create_chart_canvas(db_session, user, component, data, f"{chart_type} chart")

        open_canvas(authenticated_page, canvas_id)
        chart_page = CanvasChartPage(authenticated_page)

        assert chart_page.is_loaded(), f"{chart_type} chart should render"
        assert chart_page.get_chart_type() == chart_type, \
            f"Expected {chart_type} chart type, got {chart_page.get_chart_type()}"


@pytest.mark.e2e
def test_canvas_state_serialization(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test canvas state serialization with complex data (real registration)."""
    user, _ = authenticated_user

    complex_data = [
        {"timestamp": "Line1\nLine2\tTabbed", "value": 42.195},
        {"timestamp": "Unicode © ñ 🎨", "value": 7},
        {"timestamp": "Escapes \\\"quoted\\\"", "value": -3},
    ]
    canvas_id = create_chart_canvas(db_session, user, "line_chart", complex_data, "Serial Test")

    open_canvas(authenticated_page, canvas_id)

    states = authenticated_page.evaluate(
        "() => { if (window.atom?.canvas?.getAllStates) { return window.atom.canvas.getAllStates(); } return []; }"
    )
    chart_states = [
        s["state"] for s in states
        if (s.get("state") or {}).get("component") == "line_chart"
    ]
    assert len(chart_states) >= 1, "Chart state should be registered"

    state = chart_states[0]
    roundtripped = json.loads(json.dumps(state))
    assert roundtripped == state, "Complex state should survive JSON round-trip"
    assert state["data_points"][0]["x"] == "Line1\nLine2\tTabbed", \
        "Special characters should be preserved"
    assert state["data_points"][1]["x"] == "Unicode © ñ 🎨", \
        "Unicode should be preserved"
    assert state["data_points"][2]["y"] == -3, "Negative numbers should be preserved"


# =============================================================================
# Canvas Lifecycle Tests
# =============================================================================

@pytest.mark.e2e
def test_canvas_update_and_close(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test canvas update and close lifecycle via real routes + backend.

    Verifies:
    1. Canvas renders
    2. PUT /api/canvas/{id} (REST → WS broadcast) updates the title
    3. Close button hides the canvas
    """
    user, _ = authenticated_user
    canvas_id = create_markdown_canvas(db_session, user, "Initial", "v1")

    canvas_page = open_canvas(authenticated_page, canvas_id)
    assert canvas_page.get_title() == "Initial"

    # Real backend update → WS broadcast → re-render
    import requests
    token = authenticated_page.evaluate("() => localStorage.getItem('auth_token')")
    resp = requests.put(
        f"http://localhost:8001/api/canvas/{canvas_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "v2", "canvas_type": "markdown", "title": "Updated"},
        timeout=10,
    )
    assert resp.status_code == 200, f"PUT failed: {resp.status_code}"

    expect(canvas_page.canvas_title).to_have_text("Updated", timeout=5000)

    # Close the canvas via the close button
    canvas_page.close_canvas()
    canvas_page.wait_for_canvas_hidden(timeout=5000)
    assert canvas_page.is_visible() is False, "Canvas should be hidden after close"


# =============================================================================
# Cleanup Fixture
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_test_data(db_session: Session):
    """Cleanup canvas rows created by this file's tests.

    Runs after each test to remove the Canvas + CanvasAudit rows so the
    shared e2e database does not accumulate test canvases.
    """
    yield

    try:
        test_canvases = db_session.query(Canvas).filter(
            Canvas.id.like("e2e-%")
        ).all()
        for canvas in test_canvases:
            db_session.delete(canvas)
        db_session.commit()
    except Exception as e:
        print(f"Warning: Failed to cleanup test canvases: {e}")
