"""
E2E Tests for Canvas Accessibility (AI Accessibility layer).

The app's AI-accessibility surface (see CLAUDE.md #6) exposes canvas state to
screen readers and AI agents via `window.atom.canvas` — NOT via hidden
role="log" DOM trees (that speculative pattern was never implemented in the
current frontend; the a11y/state-api tests previously injected phantom trees
that asserted on nothing real).

The REAL contract, verified here against genuinely mounted components:

- window.atom.canvas.getState(id) returns the registered canvas state
  (registered by CanvasPanel/CanvasHost via useCanvasStateRegistration and by
  the chart/form components via their own useEffect registration)
- getAllStates() returns {canvas_id, state} entries for every mounted canvas
- State is JSON-serializable (parseable) and preserves special characters
  (unicode, emoji, XSS-shaped strings) exactly — the content reaches the DOM
  as text/Markdown, never as raw HTML
- State updates after user interaction (form fill)
- Large states (1000+ points) register and read back without issue

Run with: pytest backend/tests/e2e_ui/tests/test_canvas_accessibility.py -v
"""

import json
import time
import pytest
import uuid
from playwright.sync_api import Page
from sqlalchemy.orm import Session
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

def open_canvas_detail(page: Page, canvas_id: str) -> None:
    """Navigate to the real /canvas/{id} route."""
    page.goto(f"http://localhost:3001/canvas/{canvas_id}")
    authenticated_page.wait_for_load_state("networkidle")
    page.wait_for_selector('[data-testid="canvas-container"]', timeout=10000)


def get_all_states(page: Page) -> list:
    """Get all registered canvas states via the REAL window.atom.canvas API."""
    result = page.evaluate(
        "() => { if (window.atom?.canvas?.getAllStates) { return window.atom.canvas.getAllStates(); } return []; }"
    )
    return result or []


def find_state(page: Page, component: str, chart_type: str | None = None, require: str | None = None) -> dict | None:
    """Find a registered state by component type.

    Args:
        page: Playwright page.
        component: State component field (line_chart/bar_chart/pie_chart/form).
        chart_type: For charts, require this chart_type (distinguishes the
            chart component's state from the host's generic registration).
        require: Optional key that must be present (e.g. "form_schema" for
            the InteractiveForm state, which is richer than the host's).
    """
    for entry in get_all_states(page):
        state = entry.get("state") or {}
        if state.get("component") == component:
            if chart_type and state.get("chart_type") != chart_type:
                continue
            if require and require not in state:
                continue
            return state
    return None


def assert_state_parseable(state: dict) -> None:
    """Assert a state round-trips through JSON (the agent read-back contract)."""
    text = json.dumps(state)
    parsed = json.loads(text)
    assert parsed == state, "State should survive JSON serialization (agent read-back)"


def test_state_api_available_for_agents(authenticated_page: Page):
    """Test the AI-accessibility state API exists on the real chat page.

    CanvasHost lives in AgentWorkspace's Artifacts tab (unmounted until the
    tab is activated); opening the tab mounts the host and creates
    window.atom.canvas — the agent read-back surface is always available.
    """
    authenticated_page.goto("http://localhost:3001/chat")
    authenticated_page.wait_for_load_state("networkidle")
    artifacts_tab = authenticated_page.locator("button:has-text('Artifacts')")
    if artifacts_tab.count() > 0:
        artifacts_tab.first.click()
        authenticated_page.wait_for_timeout(500)

    api = authenticated_page.evaluate("() => typeof window.atom?.canvas")
    assert api == "object", "window.atom.canvas should exist on the chat page"

    for method in ("getState", "getAllStates", "subscribe", "subscribeAll"):
        assert authenticated_page.evaluate(f"typeof window.atom.canvas.{method}") == "function", \
            f"window.atom.canvas.{method} should be a function"


def test_chart_state_exposed_and_parseable(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test chart state is exposed to agents and survives JSON serialization."""
    user, _ = authenticated_user
    data = [
        {"timestamp": "2024-02-23", "value": 100, "label": "Point 1"},
        {"timestamp": "2024-02-24", "value": 150, "label": "Point 2"},
    ]
    canvas_id = create_chart_canvas(db_session, user, "line_chart", data, "Test Line Chart")

    open_canvas_detail(authenticated_page, canvas_id)

    state = find_state(authenticated_page, "line_chart", "line")
    assert state is not None, "Line chart should register its state for agent read-back"

    # JSON round-trip (agent reads the state as JSON)
    assert_state_parseable(state)

    # Required fields for the read-back contract
    for field in ("canvas_id", "component", "timestamp"):
        assert field in state, f"State should have required field '{field}'"
        assert state[field], f"Field '{field}' should not be empty"

    assert state["data_points"][0]["y"] == 100, "Chart data should be readable by agents"


def test_special_characters_roundtrip(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test state preserves XSS-shaped / special characters exactly.

    The state is read as JSON (text), not injected as HTML — the title
    round-trips byte-for-byte, and no script execution occurs.
    """
    user, _ = authenticated_user
    dangerous_title = '<script>alert("XSS")</script> & "quotes" and \'apostrophes\''
    canvas_id = create_chart_canvas(
        db_session, user, "line_chart",
        [{"timestamp": "A", "value": 100}],
        dangerous_title,
    )

    open_canvas_detail(authenticated_page, canvas_id)

    state = find_state(authenticated_page, "line_chart", "line")
    assert state is not None
    assert state["title"] == dangerous_title, \
        "Special characters should be preserved exactly in the state"

    # JSON round-trip must be lossless
    assert_state_parseable(state)

    # No script element may exist on the page (content is text, not HTML)
    assert authenticated_page.locator("script:has-text('XSS')").count() == 0, \
        "XSS-shaped content must never be executed as HTML"


def test_state_registered_for_all_mounted_types(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test charts AND forms register agent-readable state when mounted."""
    user, _ = authenticated_user
    chart_id = create_chart_canvas(
        db_session, user, "pie_chart",
        [{"name": "A", "value": 30}, {"name": "B", "value": 70}],
        "Pie",
    )
    form_id = create_form_canvas(
        db_session,
        user,
        [{"name": "email", "type": "email", "label": "Email", "required": True}],
        "Form",
    )

    open_canvas_detail(page, chart_id)
    pie_state = find_state(authenticated_page, "pie_chart", "pie")
    assert pie_state is not None, "Pie chart should register state"
    assert pie_state["data_points"][0]["x"] == "A"

    open_canvas_detail(page, form_id)
    form_state = find_state(authenticated_page, "form", require="form_schema")
    assert form_state is not None, "Form should register state"
    assert form_state["form_schema"]["fields"][0]["name"] == "email"


def test_state_updates_after_form_interaction(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test the accessibility state reflects live user interaction (form fill)."""
    user, _ = authenticated_user
    canvas_id = create_form_canvas(
        db_session,
        user,
        [{"name": "email", "type": "email", "label": "Email", "required": True}],
        "A11y Form",
    )

    open_canvas_detail(authenticated_page, canvas_id)

    # Fill the email field — InteractiveForm re-registers state on change
    authenticated_page.locator('[data-testid="form-field-email"]').fill("user@example.com")
    authenticated_page.wait_for_timeout(500)

    state = find_state(authenticated_page, "form", require="form_schema")
    assert state is not None
    assert state["form_data"]["email"] == "user@example.com", \
        "State should update to reflect the filled value"
    assert state["submit_enabled"] is True


def test_getallstates_entries_well_formed(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test getAllStates entries are well-formed for agent consumption."""
    user, _ = authenticated_user
    canvas_id = create_chart_canvas(
        db_session, user, "bar_chart",
        [{"name": "Cat A", "value": 200}],
        "Bar",
    )

    open_canvas_detail(authenticated_page, canvas_id)

    states = get_all_states(authenticated_page)
    assert len(states) >= 1, "At least one canvas state should be registered"

    for entry in states:
        assert "canvas_id" in entry, "Entry should carry canvas_id"
        assert "state" in entry, "Entry should carry state"
        assert isinstance(entry["state"], dict), "State should be a dict"
        assert_state_parseable(entry["state"])


def test_state_api_returns_null_for_unknown_id(authenticated_page: Page):
    """Test getState returns null for unknown ids (no crash)."""
    authenticated_page.goto("http://localhost:3001/chat")
    authenticated_page.wait_for_load_state("networkidle")
    artifacts_tab = authenticated_page.locator("button:has-text('Artifacts')")
    if artifacts_tab.count() > 0:
        artifacts_tab.first.click()
        authenticated_page.wait_for_timeout(500)

    result = authenticated_page.evaluate("() => window.atom.canvas.getState('does-not-exist')")
    assert result is None, "getState for an unknown id should return null"


def test_large_canvas_state_performance(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test large states (1000+ points) register and read back quickly."""
    user, _ = authenticated_user
    data = [
        {"timestamp": f"Point-{i}", "value": i * 10}
        for i in range(1000)
    ]
    canvas_id = create_chart_canvas(db_session, user, "line_chart", data, "Large Canvas")

    start = time.time()
    open_canvas_detail(authenticated_page, canvas_id)

    state = find_state(authenticated_page, "line_chart", "line")
    assert state is not None, "Large chart should register its state"
    assert len(state["data_points"]) == 1000, "All 1000 points should be readable"

    elapsed = time.time() - start
    assert elapsed < 30.0, f"Large state rendering should complete quickly, took {elapsed:.2f}s"


def test_unicode_characters_in_state(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test state preserves unicode characters (emoji, non-ASCII)."""
    user, _ = authenticated_user
    unicode_title = "Unicode Test 🎨 你好 مرحبا"
    canvas_id = create_chart_canvas(
        db_session, user, "line_chart",
        [{"timestamp": "😀", "value": 100}],
        unicode_title,
    )

    open_canvas_detail(authenticated_page, canvas_id)

    state = find_state(authenticated_page, "line_chart", "line")
    assert state is not None
    assert "🎨" in state["title"], "Emoji should be preserved"
    assert "你好" in state["title"], "Chinese characters should be preserved"
    assert "مرحبا" in state["title"], "Arabic characters should be preserved"
    assert_state_parseable(state)
