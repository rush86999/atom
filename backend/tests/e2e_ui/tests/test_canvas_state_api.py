"""
E2E Tests for Canvas State API (window.atom.canvas).

Tests verify the REAL global canvas state API — the AI-accessibility
contract (frontend-nextjs/hooks/useCanvasStateRegistration.ts):

- window.atom.canvas.getState(canvas_id) -> state object or null
- window.atom.canvas.getAllStates() -> array of {canvas_id, state}
- window.atom.canvas.subscribe / subscribeAll -> unsubscribe functions

State is registered by REAL mounted components:
- CanvasPanel/CanvasHost register via useCanvasStateRegistration (the canvas
  UUID from the route)
- LineChartCanvas/BarChartCanvas/PieChartCanvas/InteractiveForm register via
  their own useEffect with per-component canvas ids

No phantom stubs are injected — the API must exist on the real routes
(/chat always mounts CanvasHost; /canvas/{id} mounts CanvasPanel) and states
are read back after REAL rendering.

Run with: pytest backend/tests/e2e_ui/tests/test_canvas_state_api.py -v
"""

import pytest
import uuid
from playwright.sync_api import Page
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Tuple

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.e2e_ui.tests.canvas_helpers import create_chart_canvas, create_form_canvas, create_markdown_canvas
from core.models import User


# =============================================================================
# Helper Functions
# =============================================================================

def get_canvas_state(page: Page, canvas_id: str) -> dict | None:
    """Get canvas state via window.atom.canvas.getState()."""
    return page.evaluate(
        f"() => {{ if (window.atom?.canvas?.getState) {{ return window.atom.canvas.getState('{canvas_id}'); }} return null; }}"
    )


def get_all_canvas_states(page: Page) -> list[dict]:
    """Get all canvas states via window.atom.canvas.getAllStates()."""
    result = page.evaluate(
        "() => { if (window.atom?.canvas?.getAllStates) { return window.atom.canvas.getAllStates(); } return []; }"
    )
    return result or []


def find_state(page: Page, component: str, chart_type: str | None = None, require: str | None = None) -> dict | None:
    """Find a registered state by component type via the real getAllStates().

    Args:
        page: Playwright page.
        component: State component field (line_chart/bar_chart/pie_chart/form).
        chart_type: For charts, require this chart_type (distinguishes the
            chart component's state from the host's generic registration).
        require: Optional key that must be present (e.g. "form_schema" for
            the InteractiveForm state, which is richer than the host's).
    """
    for entry in get_all_canvas_states(page):
        state = entry.get("state") or {}
        if state.get("component") == component:
            if chart_type and state.get("chart_type") != chart_type:
                continue
            if require and require not in state:
                continue
            return state
    return None


def open_chat_page(page: Page) -> None:
    """Navigate to the real chat page and open the Artifacts tab so CanvasHost mounts.

    CanvasHost lives inside AgentWorkspace's Artifacts TabsContent, which Radix
    keeps unmounted until the tab is activated — the API only exists once the
    host mounts.
    """
    page.goto("http://localhost:3001/chat")
    page.wait_for_load_state("networkidle")
    artifacts_tab = page.locator("button:has-text('Artifacts')")
    if artifacts_tab.count() > 0:
        artifacts_tab.first.click()
        page.wait_for_timeout(500)


def open_canvas_detail(page: Page, canvas_id: str) -> None:
    """Navigate to the real /canvas/{id} route."""
    page.goto(f"http://localhost:3001/canvas/{canvas_id}")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector('[data-testid="canvas-container"]', timeout=10000)


def create_test_line_chart_data(point_count: int = 5) -> dict:
    """Create test line chart data."""
    unique_id = str(uuid.uuid4())[:8]
    data_points = [
        {
            "x": f"2024-02-{23 + i:02d} 12:00",
            "y": 10 + i * 5,
            "label": f"Point {i}",
        }
        for i in range(point_count)
    ]
    return {
        "data_points": data_points,
        "axes_labels": {"x": "Time", "y": "Value"},
        "title": f"Test Line Chart {unique_id}",
    }


def create_test_bar_chart_data(point_count: int = 5) -> dict:
    """Create test bar chart data."""
    unique_id = str(uuid.uuid4())[:8]
    data_points = [
        {"x": f"Category-{i}", "y": 20 + i * 10}
        for i in range(point_count)
    ]
    return {
        "data_points": data_points,
        "axes_labels": {"x": "Category", "y": "Value"},
        "title": f"Test Bar Chart {unique_id}",
    }


def create_test_pie_chart_data(point_count: int = 5) -> dict:
    """Create test pie chart data."""
    unique_id = str(uuid.uuid4())[:8]
    data_points = [
        {"x": f"Segment-{i}", "y": 10 + i * 15, "label": f"Seg {i}"}
        for i in range(point_count)
    ]
    return {
        "data_points": data_points,
        "title": f"Test Pie Chart {unique_id}",
    }


def line_chart_points_to_data(data: dict) -> list[dict]:
    """Convert {data_points: [{x, y, label}]} to LineChartCanvas data."""
    return [
        {"timestamp": p["x"], "value": p["y"], "label": p.get("label")}
        for p in data["data_points"]
    ]


def bar_pie_points_to_data(data: dict) -> list[dict]:
    """Convert {data_points: [{x, y}]} to BarChartCanvas/PieChartCanvas data."""
    return [{"name": p["x"], "value": p["y"]} for p in data["data_points"]]


# =============================================================================
# API Availability Tests
# =============================================================================

def test_canvas_api_exists(authenticated_page: Page):
    """Test window.atom.canvas API exists and has required methods.

    The API is created by useCanvasStateRegistration, which runs on the chat
    page because CanvasHost is always mounted there — even with no canvas
    presented.
    """
    open_chat_page(authenticated_page)

    # The REAL API must exist (no stub injection)
    api_exists = authenticated_page.evaluate(
        "() => typeof window.atom === 'object' && typeof window.atom.canvas === 'object'"
    )
    assert api_exists, "window.atom.canvas API should exist on the chat page"

    assert authenticated_page.evaluate("typeof window.atom.canvas.getState") == "function"
    assert authenticated_page.evaluate("typeof window.atom.canvas.getAllStates") == "function"
    assert authenticated_page.evaluate("typeof window.atom.canvas.subscribe") == "function"
    assert authenticated_page.evaluate("typeof window.atom.canvas.subscribeAll") == "function"


def test_get_state_returns_null_for_invalid_id(authenticated_page: Page):
    """Test getState returns null for non-existent canvas_id."""
    open_chat_page(authenticated_page)

    # Query non-existent canvas — the real registry has no entry
    result = get_canvas_state(authenticated_page, "non-existent-canvas-id")
    assert result is None


# =============================================================================
# Line Chart State Tests
# =============================================================================

def test_line_chart_state_structure(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test line chart state has all required fields (real registration)."""
    user, _ = authenticated_user
    data = create_test_line_chart_data(5)
    canvas_id = create_chart_canvas(db_session, user, "line_chart", line_chart_points_to_data(data), data["title"])

    open_canvas_detail(authenticated_page, canvas_id)

    # Find the state registered by the REAL LineChartCanvas component
    state = find_state(authenticated_page, "line_chart", "line")
    assert state is not None, "Line chart state should be registered via getAllStates()"

    assert state["component"] == "line_chart"
    assert state["chart_type"] == "line"
    assert isinstance(state["data_points"], list)
    assert isinstance(state["axes_labels"], dict)
    assert "title" in state
    assert isinstance(state["legend"], bool)


def test_line_chart_data_points(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test line chart state includes correct data points."""
    user, _ = authenticated_user
    point_count = 5
    data = create_test_line_chart_data(point_count)
    canvas_id = create_chart_canvas(db_session, user, "line_chart", line_chart_points_to_data(data), data["title"])

    open_canvas_detail(authenticated_page, canvas_id)

    state = find_state(authenticated_page, "line_chart", "line")
    assert state is not None

    data_points = state["data_points"]
    assert len(data_points) == point_count

    for point in data_points:
        assert "x" in point
        assert "y" in point
        assert isinstance(point["y"], (int, float))


def test_line_chart_axes_labels(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test line chart state includes axes labels."""
    user, _ = authenticated_user
    data = create_test_line_chart_data(5)
    canvas_id = create_chart_canvas(db_session, user, "line_chart", line_chart_points_to_data(data), data["title"])

    open_canvas_detail(authenticated_page, canvas_id)

    state = find_state(authenticated_page, "line_chart", "line")
    assert state is not None

    axes_labels = state["axes_labels"]
    assert axes_labels is not None
    assert "x" in axes_labels
    assert "y" in axes_labels
    assert isinstance(axes_labels["x"], str)
    assert isinstance(axes_labels["y"], str)


# =============================================================================
# Bar Chart State Tests
# =============================================================================

def test_bar_chart_state_structure(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test bar chart state has all required fields (real registration)."""
    user, _ = authenticated_user
    data = create_test_bar_chart_data(5)
    canvas_id = create_chart_canvas(db_session, user, "bar_chart", bar_pie_points_to_data(data), data["title"])

    open_canvas_detail(authenticated_page, canvas_id)

    state = find_state(authenticated_page, "bar_chart", "bar")
    assert state is not None, "Bar chart state should be registered via getAllStates()"

    assert state["component"] == "bar_chart"
    assert state["chart_type"] == "bar"
    assert isinstance(state["data_points"], list)
    assert isinstance(state["axes_labels"], dict)


def test_bar_chart_data_points(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test bar chart state includes correct data points."""
    user, _ = authenticated_user
    point_count = 5
    data = create_test_bar_chart_data(point_count)
    canvas_id = create_chart_canvas(db_session, user, "bar_chart", bar_pie_points_to_data(data), data["title"])

    open_canvas_detail(authenticated_page, canvas_id)

    state = find_state(authenticated_page, "bar_chart", "bar")
    assert state is not None

    data_points = state["data_points"]
    assert len(data_points) == point_count

    for point in data_points:
        assert "x" in point
        assert "y" in point
        assert isinstance(point["y"], (int, float))


# =============================================================================
# Pie Chart State Tests
# =============================================================================

def test_pie_chart_state_structure(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test pie chart state has all required fields (real registration)."""
    user, _ = authenticated_user
    data = create_test_pie_chart_data(5)
    canvas_id = create_chart_canvas(db_session, user, "pie_chart", bar_pie_points_to_data(data), data["title"])

    open_canvas_detail(authenticated_page, canvas_id)

    state = find_state(authenticated_page, "pie_chart", "pie")
    assert state is not None, "Pie chart state should be registered via getAllStates()"

    assert state["component"] == "pie_chart"
    assert state["chart_type"] == "pie"
    assert isinstance(state["data_points"], list)


def test_pie_chart_data_points(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test pie chart state includes correct data points."""
    user, _ = authenticated_user
    point_count = 5
    data = create_test_pie_chart_data(point_count)
    canvas_id = create_chart_canvas(db_session, user, "pie_chart", bar_pie_points_to_data(data), data["title"])

    open_canvas_detail(authenticated_page, canvas_id)

    state = find_state(authenticated_page, "pie_chart", "pie")
    assert state is not None

    data_points = state["data_points"]
    assert len(data_points) == point_count

    for point in data_points:
        assert "x" in point
        assert "y" in point
        assert isinstance(point["y"], (int, float))


# =============================================================================
# Form State Tests
# =============================================================================

def test_form_state_structure(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test form state has all required fields (real registration)."""
    user, _ = authenticated_user
    fields = [
        {"name": f"field_{i}", "type": "text", "label": f"Field {i}", "required": i < 2}
        for i in range(3)
    ]
    canvas_id = create_form_canvas(db_session, user, fields, "Test Form")

    open_canvas_detail(authenticated_page, canvas_id)

    # Find the state registered by the REAL InteractiveForm component
    state = find_state(authenticated_page, "form", require="form_schema")
    assert state is not None, "Form state should be registered via getAllStates()"

    assert state["component"] == "form"
    assert isinstance(state["form_schema"], dict)
    assert "fields" in state["form_schema"]
    assert len(state["form_schema"]["fields"]) == 3
    assert isinstance(state["form_data"], dict)
    assert isinstance(state["validation_errors"], list)
    assert isinstance(state["submit_enabled"], bool)
    assert isinstance(state["submitted"], bool)


def test_form_state_updates(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test form state reflects live form data changes (real registration)."""
    user, _ = authenticated_user
    fields = [
        {"name": "email", "type": "email", "label": "Email", "required": True}
    ]
    canvas_id = create_form_canvas(db_session, user, fields, "Form Updates")

    open_canvas_detail(authenticated_page, canvas_id)

    # Fill the email field — InteractiveForm re-registers state on change
    authenticated_page.locator('[data-testid="form-field-email"]').fill("test@example.com")
    authenticated_page.wait_for_timeout(500)

    state = find_state(authenticated_page, "form", require="form_schema")
    assert state is not None

    assert state["form_data"]["email"] == "test@example.com", \
        "Form state should reflect the filled value"
    assert state["submit_enabled"] is True
    assert state["submitted"] is False


# =============================================================================
# Multiple Canvas Tests
# =============================================================================

def test_get_all_states_returns_well_formed(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test getAllStates returns well-formed {canvas_id, state} entries.

    A single /canvas/{id} page registers: the host state (under the canvas
    UUID) plus the mounted chart component's state.
    """
    user, _ = authenticated_user
    data = create_test_line_chart_data(3)
    canvas_id = create_chart_canvas(db_session, user, "line_chart", line_chart_points_to_data(data), data["title"])

    open_canvas_detail(authenticated_page, canvas_id)

    all_states = get_all_canvas_states(authenticated_page)
    assert isinstance(all_states, list)
    assert len(all_states) >= 1

    for item in all_states:
        assert "canvas_id" in item, "Each entry should carry canvas_id"
        assert "state" in item, "Each entry should carry state"
        assert isinstance(item["state"], dict), "Each state should be a dict"

    # The specific component state must be discoverable
    assert find_state(authenticated_page, "line_chart", "line") is not None


def test_get_state_filters_by_id(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test getState returns the correct state for a specific ID.

    Two different canvases (line + bar) on their own routes register distinct
    state ids; getState must resolve each independently.
    """
    user, _ = authenticated_user
    line_data = create_test_line_chart_data(3)
    bar_data = create_test_bar_chart_data(3)
    line_id = create_chart_canvas(db_session, user, "line_chart", line_chart_points_to_data(line_data), line_data["title"])
    bar_id = create_chart_canvas(db_session, user, "bar_chart", bar_pie_points_to_data(bar_data), bar_data["title"])

    open_canvas_detail(authenticated_page, line_id)
    line_state = find_state(authenticated_page, "line_chart", "line")
    assert line_state is not None
    line_state_id = line_state["canvas_id"]

    # The host also registers under the canvas UUID
    host_state = get_canvas_state(authenticated_page, line_id)
    assert host_state is not None, "Host state should be registered under the canvas UUID"
    assert host_state["canvas_id"] == line_id

    # Navigating to the bar canvas swaps the registrations
    open_canvas_detail(authenticated_page, bar_id)
    bar_state = find_state(authenticated_page, "bar_chart", "bar")
    assert bar_state is not None
    assert bar_state["canvas_id"] != line_state_id, "Different canvases should have distinct state ids"

    bar_host_state = get_canvas_state(authenticated_page, bar_id)
    assert bar_host_state is not None
    assert bar_host_state["canvas_id"] == bar_id


# =============================================================================
# Timestamp Tests
# =============================================================================

def test_state_timestamp_is_iso_string(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test state timestamp is a valid, recent ISO 8601 string."""
    user, _ = authenticated_user
    data = create_test_line_chart_data(3)
    canvas_id = create_chart_canvas(db_session, user, "line_chart", line_chart_points_to_data(data), data["title"])

    open_canvas_detail(authenticated_page, canvas_id)

    state = find_state(authenticated_page, "line_chart", "line")
    assert state is not None

    timestamp_str = state["timestamp"]
    assert isinstance(timestamp_str, str)

    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except ValueError:
        pytest.fail(f"Invalid ISO 8601 timestamp: {timestamp_str}")

    now = datetime.now(timestamp.tzinfo)
    time_diff = abs((now - timestamp).total_seconds())
    assert time_diff < 60, f"Timestamp is {time_diff}s old, expected < 60s"
