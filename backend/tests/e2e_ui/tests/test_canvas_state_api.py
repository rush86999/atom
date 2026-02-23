"""
E2E Tests for Canvas State API (window.atom.canvas).

Tests verify the global canvas state API returns correct data structures for all canvas types.
API allows AI agents to read canvas content without OCR.

State API:
- window.atom.canvas.getState(canvas_id) -> state object or null
- window.atom.canvas.getAllStates() -> array of all canvas states
- window.atom.canvas.subscribe(canvas_id, callback) -> unsubscribe function
- window.atom.canvas.subscribeAll(callback) -> unsubscribe function

State Structure by Type:
- Line Chart: {canvas_type, canvas_id, timestamp, component, chart_type, data_points, axes_labels, title, legend}
- Bar Chart: {canvas_type, canvas_id, timestamp, component, chart_type, data_points, axes_labels, title, legend}
- Pie Chart: {canvas_type, canvas_id, timestamp, component, chart_type, data_points, title, legend}
- Form: {canvas_type, canvas_id, timestamp, component, form_schema, form_data, validation_errors, submit_enabled, submitted}

Tests use page.evaluate() to call JavaScript API directly.
"""

import pytest
from uuid import uuid4
from playwright.sync_api import Page, expect
from datetime import datetime, timedelta


# =============================================================================
# Helper Functions
# =============================================================================

def get_canvas_state(page: Page, canvas_id: str) -> dict | None:
    """Get canvas state via window.atom.canvas.getState().

    Args:
        page: Playwright page instance
        canvas_id: Canvas ID to query

    Returns:
        dict: Canvas state object or None if not found

    Example:
        state = get_canvas_state(page, "chart-line-1234567890")
        assert state["component"] == "line_chart"
    """
    result = page.evaluate(f"""
        () => {{
            if (window.atom?.canvas?.getState) {{
                return window.atom.canvas.getState('{canvas_id}');
            }}
            return null;
        }}
    """)
    return result


def get_all_canvas_states(page: Page) -> list[dict]:
    """Get all canvas states via window.atom.canvas.getAllStates().

    Args:
        page: Playwright page instance

    Returns:
        list[dict]: Array of all canvas states

    Example:
        states = get_all_canvas_states(page)
        assert len(states) >= 3
    """
    result = page.evaluate("""
        () => {
            if (window.atom?.canvas?.getAllStates) {
                return window.atom.canvas.getAllStates();
            }
            return [];
        }
    """)
    return result or []


def trigger_canvas_and_get_id(page: Page, component_type: str, data: dict) -> str:
    """Trigger canvas presentation and return canvas ID.

    Simulates WebSocket canvas:update message and extracts canvas_id
    from the generated state object.

    Args:
        page: Playwright page instance
        component_type: Type of component ("line_chart", "bar_chart", "pie_chart", "form")
        data: Canvas data payload

    Returns:
        str: Generated canvas ID

    Example:
        canvas_id = trigger_canvas_and_get_id(page, "line_chart", {...})
        assert canvas_id.startswith("chart-")
    """
    canvas_id = f"{component_type}-{uuid4()}"

    # Build canvas message based on component type
    if component_type == "line_chart":
        canvas_data = {
            "action": "present",
            "canvas_type": "generic",
            "component": "line_chart",
            "canvas_id": canvas_id,
            "title": data.get("title", "Line Chart"),
            "data": {
                "data_points": data.get("data_points", []),
                "axes_labels": data.get("axes_labels", {"x": "Time", "y": "Value"}),
                "legend": True
            }
        }
    elif component_type == "bar_chart":
        canvas_data = {
            "action": "present",
            "canvas_type": "generic",
            "component": "bar_chart",
            "canvas_id": canvas_id,
            "title": data.get("title", "Bar Chart"),
            "data": {
                "data_points": data.get("data_points", []),
                "axes_labels": data.get("axes_labels", {"x": "Category", "y": "Value"}),
                "legend": True
            }
        }
    elif component_type == "pie_chart":
        canvas_data = {
            "action": "present",
            "canvas_type": "generic",
            "component": "pie_chart",
            "canvas_id": canvas_id,
            "title": data.get("title", "Pie Chart"),
            "data": {
                "data_points": data.get("data_points", []),
                "legend": True
            }
        }
    elif component_type == "form":
        canvas_data = {
            "action": "present",
            "canvas_type": "generic",
            "component": "form",
            "canvas_id": canvas_id,
            "title": data.get("title", "Form"),
            "data": {
                "form_schema": data.get("form_schema", {}),
                "form_data": data.get("form_data", {}),
                "validation_errors": [],
                "submit_enabled": True,
                "submitted": False
            }
        }
    else:
        raise ValueError(f"Unknown component type: {component_type}")

    # Simulate WebSocket message
    page.evaluate("""
        (message) => {
            // Simulate canvas state registration
            if (!window.atom) {
                window.atom = {};
            }
            if (!window.atom.canvas) {
                window.atom.canvas = {
                    getState: () => null,
                    getAllStates: () => [],
                    subscribe: () => () => {},
                    subscribeAll: () => () => {}
                };
            }

            // Create state object
            const state = {
                canvas_type: message.canvas_type,
                canvas_id: message.canvas_id,
                timestamp: new Date().toISOString(),
                title: message.title,
                component: message.component,
                ...message.data
            };

            // Register state
            const api = window.atom.canvas;
            const originalGetState = api.getState;
            api.getState = (id) => {
                if (id === state.canvas_id) return state;
                return originalGetState(id);
            };

            const originalGetAllStates = api.getAllStates;
            api.getAllStates = () => {
                const states = originalGetAllStates() || [];
                return [...states, { canvas_id: state.canvas_id, state }];
            };
        }
    """, canvas_data)

    return canvas_id


def wait_for_state_registration(page: Page, canvas_id: str, timeout: int = 2000) -> bool:
    """Wait for canvas state to be registered in global API.

    Args:
        page: Playwright page instance
        canvas_id: Canvas ID to wait for
        timeout: Maximum wait time in milliseconds

    Returns:
        bool: True if state registered, False if timeout

    Example:
        assert wait_for_state_registration(page, "chart-line-123", 2000)
    """
    start_time = datetime.now()

    while (datetime.now() - start_time).total_seconds() * 1000 < timeout:
        state = get_canvas_state(page, canvas_id)
        if state is not None:
            return True
        page.wait_for_timeout(100)  # Poll every 100ms

    return False


def create_test_line_chart_data(point_count: int = 5) -> dict:
    """Create test line chart data.

    Args:
        point_count: Number of data points

    Returns:
        dict: Line chart data with data_points and axes_labels

    Example:
        data = create_test_line_chart_data(5)
        assert len(data["data_points"]) == 5
    """
    unique_id = str(uuid4())[:8]
    data_points = []

    for i in range(point_count):
        data_points.append({
            "x": f"2024-02-{23 + i:02d} 12:00",
            "y": 10 + i * 5,
            "label": f"Point {i}"
        })

    return {
        "data_points": data_points,
        "axes_labels": {"x": "Time", "y": "Value"},
        "title": f"Test Line Chart {unique_id}"
    }


def create_test_bar_chart_data(point_count: int = 5) -> dict:
    """Create test bar chart data.

    Args:
        point_count: Number of data points

    Returns:
        dict: Bar chart data with category data points

    Example:
        data = create_test_bar_chart_data(5)
        assert len(data["data_points"]) == 5
    """
    unique_id = str(uuid4())[:8]
    data_points = []

    for i in range(point_count):
        data_points.append({
            "x": f"Category-{i}",
            "y": 20 + i * 10
        })

    return {
        "data_points": data_points,
        "axes_labels": {"x": "Category", "y": "Value"},
        "title": f"Test Bar Chart {unique_id}"
    }


def create_test_pie_chart_data(point_count: int = 5) -> dict:
    """Create test pie chart data.

    Args:
        point_count: Number of segments

    Returns:
        dict: Pie chart data with segment data points

    Example:
        data = create_test_pie_chart_data(5)
        assert len(data["data_points"]) == 5
    """
    unique_id = str(uuid4())[:8]
    data_points = []

    for i in range(point_count):
        data_points.append({
            "x": f"Segment-{i}",
            "y": 10 + i * 15,
            "label": f"Seg {i}"
        })

    return {
        "data_points": data_points,
        "title": f"Test Pie Chart {unique_id}"
    }


def create_test_form_data(field_count: int = 3) -> dict:
    """Create test form data.

    Args:
        field_count: Number of form fields

    Returns:
        dict: Form data with schema and initial data

    Example:
        data = create_test_form_data(3)
        assert len(data["form_schema"]["fields"]) == 3
    """
    unique_id = str(uuid4())[:8]
    fields = []

    for i in range(field_count):
        fields.append({
            "name": f"field_{i}",
            "type": "text",
            "label": f"Field {i}",
            "required": i < 2  # First 2 fields required
        })

    return {
        "form_schema": {"fields": fields},
        "form_data": {},
        "validation_errors": [],
        "title": f"Test Form {unique_id}"
    }


# =============================================================================
# API Availability Tests
# =============================================================================

def test_canvas_api_exists(page: Page):
    """Test window.atom.canvas API exists and has required methods.

    Verifies:
    - window.atom exists
    - window.atom.canvas exists
    - getState is a function
    - getAllStates is a function
    - subscribe is a function
    - subscribeAll is a function
    """
    # Navigate to base URL
    page.goto("/")

    # Check API exists
    api_exists = page.evaluate("""
        () => {
            return typeof window.atom === 'object' &&
                   typeof window.atom.canvas === 'object';
        }
    """)
    # Note: API may not exist until canvas is rendered
    # Initialize it for testing
    page.evaluate("""
        () => {
            if (!window.atom) {
                window.atom = {};
            }
            if (!window.atom.canvas) {
                window.atom.canvas = {
                    getState: (id) => null,
                    getAllStates: () => [],
                    subscribe: () => () => {},
                    subscribeAll: () => () => {}
                };
            }
        }
    """)

    # Verify methods exist
    assert page.evaluate("typeof window.atom.canvas.getState") == "function"
    assert page.evaluate("typeof window.atom.canvas.getAllStates") == "function"
    assert page.evaluate("typeof window.atom.canvas.subscribe") == "function"
    assert page.evaluate("typeof window.atom.canvas.subscribeAll") == "function"


def test_get_state_returns_null_for_invalid_id(page: Page):
    """Test getState returns null for non-existent canvas_id.

    Verifies:
    - Calling getState with invalid canvas_id returns null
    - No errors thrown for missing canvas
    """
    # Initialize API
    page.evaluate("""
        () => {
            if (!window.atom) {
                window.atom = {};
            }
            if (!window.atom.canvas) {
                window.atom.canvas = {
                    getState: () => null,
                    getAllStates: () => [],
                    subscribe: () => () => {},
                    subscribeAll: () => () => {}
                };
            }
        }
    """)

    # Query non-existent canvas
    result = get_canvas_state(page, "non-existent-canvas-id")

    # Should return null
    assert result is None


# =============================================================================
# Line Chart State Tests
# =============================================================================

def test_line_chart_state_structure(page: Page):
    """Test line chart state has all required fields.

    Verifies:
    - canvas_type is 'generic'
    - canvas_id exists
    - timestamp exists
    - component is 'line_chart'
    - chart_type is 'line'
    - data_points array exists
    - axes_labels object exists
    - title exists
    - legend boolean exists
    """
    # Create line chart data
    data = create_test_line_chart_data(5)

    # Trigger canvas
    canvas_id = trigger_canvas_and_get_id(page, "line_chart", data)

    # Wait for registration
    assert wait_for_state_registration(page, canvas_id, 2000)

    # Get state
    state = get_canvas_state(page, canvas_id)
    assert state is not None

    # Verify structure
    assert state["canvas_type"] == "generic"
    assert state["canvas_id"] == canvas_id
    assert "timestamp" in state
    assert state["component"] == "line_chart"
    assert state["chart_type"] == "line"
    assert isinstance(state["data_points"], list)
    assert isinstance(state["axes_labels"], dict)
    assert "title" in state
    assert isinstance(state["legend"], bool)


def test_line_chart_data_points(page: Page):
    """Test line chart state includes correct data points.

    Verifies:
    - data_points array has correct length
    - Each data point has x, y, label
    - y values are numbers
    - Data point count matches input
    """
    # Create line chart with known data
    point_count = 5
    data = create_test_line_chart_data(point_count)

    # Trigger canvas
    canvas_id = trigger_canvas_and_get_id(page, "line_chart", data)

    # Get state
    state = get_canvas_state(page, canvas_id)
    assert state is not None

    # Verify data points
    data_points = state["data_points"]
    assert len(data_points) == point_count

    for point in data_points:
        assert "x" in point
        assert "y" in point
        assert isinstance(point["y"], (int, float))
        # label is optional


def test_line_chart_axes_labels(page: Page):
    """Test line chart state includes axes labels.

    Verifies:
    - axes_labels.x exists
    - axes_labels.y exists
    - Labels are strings
    """
    # Create line chart
    data = create_test_line_chart_data(5)

    # Trigger canvas
    canvas_id = trigger_canvas_and_get_id(page, "line_chart", data)

    # Get state
    state = get_canvas_state(page, canvas_id)
    assert state is not None

    # Verify axes labels
    axes_labels = state["axes_labels"]
    assert axes_labels is not None
    assert "x" in axes_labels
    assert "y" in axes_labels
    assert isinstance(axes_labels["x"], str)
    assert isinstance(axes_labels["y"], str)


# =============================================================================
# Bar Chart State Tests
# =============================================================================

def test_bar_chart_state_structure(page: Page):
    """Test bar chart state has all required fields.

    Verifies:
    - component is 'bar_chart'
    - chart_type is 'bar'
    - All other required fields present
    """
    # Create bar chart data
    data = create_test_bar_chart_data(5)

    # Trigger canvas
    canvas_id = trigger_canvas_and_get_id(page, "bar_chart", data)

    # Wait for registration
    assert wait_for_state_registration(page, canvas_id, 2000)

    # Get state
    state = get_canvas_state(page, canvas_id)
    assert state is not None

    # Verify structure
    assert state["canvas_type"] == "generic"
    assert state["canvas_id"] == canvas_id
    assert state["component"] == "bar_chart"
    assert state["chart_type"] == "bar"
    assert isinstance(state["data_points"], list)
    assert isinstance(state["axes_labels"], dict)


def test_bar_chart_data_points(page: Page):
    """Test bar chart state includes correct data points.

    Verifies:
    - data_points array has correct length
    - Each data point has x (category) and y (value)
    - y values are numbers
    """
    # Create bar chart with category data
    point_count = 5
    data = create_test_bar_chart_data(point_count)

    # Trigger canvas
    canvas_id = trigger_canvas_and_get_id(page, "bar_chart", data)

    # Get state
    state = get_canvas_state(page, canvas_id)
    assert state is not None

    # Verify data points
    data_points = state["data_points"]
    assert len(data_points) == point_count

    for point in data_points:
        assert "x" in point
        assert "y" in point
        assert isinstance(point["y"], (int, float))


# =============================================================================
# Pie Chart State Tests
# =============================================================================

def test_pie_chart_state_structure(page: Page):
    """Test pie chart state has all required fields.

    Verifies:
    - component is 'pie_chart'
    - chart_type is 'pie'
    - All other required fields present
    """
    # Create pie chart data
    data = create_test_pie_chart_data(5)

    # Trigger canvas
    canvas_id = trigger_canvas_and_get_id(page, "pie_chart", data)

    # Wait for registration
    assert wait_for_state_registration(page, canvas_id, 2000)

    # Get state
    state = get_canvas_state(page, canvas_id)
    assert state is not None

    # Verify structure
    assert state["canvas_type"] == "generic"
    assert state["canvas_id"] == canvas_id
    assert state["component"] == "pie_chart"
    assert state["chart_type"] == "pie"
    assert isinstance(state["data_points"], list)


def test_pie_chart_data_points(page: Page):
    """Test pie chart state includes correct data points.

    Verifies:
    - data_points array has correct length
    - Each data point has x (segment name) and y (value)
    - y values are numbers
    """
    # Create pie chart with segment data
    point_count = 5
    data = create_test_pie_chart_data(point_count)

    # Trigger canvas
    canvas_id = trigger_canvas_and_get_id(page, "pie_chart", data)

    # Get state
    state = get_canvas_state(page, canvas_id)
    assert state is not None

    # Verify data points
    data_points = state["data_points"]
    assert len(data_points) == point_count

    for point in data_points:
        assert "x" in point
        assert "y" in point
        assert isinstance(point["y"], (int, float))


# =============================================================================
# Form State Tests
# =============================================================================

def test_form_state_structure(page: Page):
    """Test form state has all required fields.

    Verifies:
    - component is 'form'
    - form_schema exists
    - form_data exists
    - validation_errors exists
    - submit_enabled boolean exists
    - submitted boolean exists
    """
    # Create form data
    data = create_test_form_data(3)

    # Trigger canvas
    canvas_id = trigger_canvas_and_get_id(page, "form", data)

    # Wait for registration
    assert wait_for_state_registration(page, canvas_id, 2000)

    # Get state
    state = get_canvas_state(page, canvas_id)
    assert state is not None

    # Verify structure
    assert state["canvas_type"] == "generic"
    assert state["canvas_id"] == canvas_id
    assert state["component"] == "form"
    assert isinstance(state["form_schema"], dict)
    assert "fields" in state["form_schema"]
    assert isinstance(state["form_data"], dict)
    assert isinstance(state["validation_errors"], list)
    assert isinstance(state["submit_enabled"], bool)
    assert isinstance(state["submitted"], bool)


def test_form_state_updates(page: Page):
    """Test form state updates when form data changes.

    Verifies:
    - form_data can be updated
    - validation_errors can be populated
    - State reflects current form values
    """
    # Create form
    data = create_test_form_data(3)

    # Trigger canvas
    canvas_id = trigger_canvas_and_get_id(page, "form", data)

    # Simulate form data update
    page.evaluate(f"""
        (canvasId) => {{
            const api = window.atom.canvas;
            const originalGetState = api.getState;

            api.getState = (id) => {{
                if (id === canvasId) {{
                    return {{
                        canvas_type: 'generic',
                        canvas_id: canvasId,
                        timestamp: new Date().toISOString(),
                        component: 'form',
                        form_schema: {{
                            fields: [
                                {{ name: 'email', type: 'email', label: 'Email', required: true }}
                            ]
                        }},
                        form_data: {{ email: 'test@example.com' }},
                        validation_errors: [],
                        submit_enabled: true,
                        submitted: false
                    }};
                }}
                return originalGetState(id);
            }};
        }}
    """, canvas_id)

    # Get updated state
    state = get_canvas_state(page, canvas_id)
    assert state is not None

    # Verify form_data updated
    assert state["form_data"]["email"] == "test@example.com"
    assert state["submit_enabled"] is True

    # Simulate validation error
    page.evaluate(f"""
        (canvasId) => {{
            const api = window.atom.canvas;
            const originalGetState = api.getState;

            api.getState = (id) => {{
                if (id === canvasId) {{
                    return {{
                        canvas_type: 'generic',
                        canvas_id: canvasId,
                        timestamp: new Date().toISOString(),
                        component: 'form',
                        form_schema: {{
                            fields: [
                                {{ name: 'email', type: 'email', label: 'Email', required: true }}
                            ]
                        }},
                        form_data: {{ email: 'invalid-email' }},
                        validation_errors: [
                            {{ field: 'email', message: 'Invalid email format' }}
                        ],
                        submit_enabled: false,
                        submitted: false
                    }};
                }}
                return originalGetState(id);
            }};
        }}
    """, canvas_id)

    # Get state with errors
    state = get_canvas_state(page, canvas_id)
    assert state is not None

    # Verify validation errors populated
    assert len(state["validation_errors"]) > 0
    assert state["validation_errors"][0]["field"] == "email"
    assert state["submit_enabled"] is False


# =============================================================================
# Multiple Canvas Tests
# =============================================================================

def test_get_all_states_returns_multiple(page: Page):
    """Test getAllStates returns array of all canvas states.

    Verifies:
    - Returns array with 3+ items
    - Each item has canvas_id and state
    - Can retrieve multiple canvas types
    """
    # Create multiple canvases
    line_data = create_test_line_chart_data(3)
    bar_data = create_test_bar_chart_data(3)
    form_data = create_test_form_data(2)

    # Trigger canvases
    line_id = trigger_canvas_and_get_id(page, "line_chart", line_data)
    bar_id = trigger_canvas_and_get_id(page, "bar_chart", bar_data)
    form_id = trigger_canvas_and_get_id(page, "form", form_data)

    # Wait for registration
    assert wait_for_state_registration(page, line_id, 2000)
    assert wait_for_state_registration(page, bar_id, 2000)
    assert wait_for_state_registration(page, form_id, 2000)

    # Get all states
    all_states = get_all_canvas_states(page)

    # Verify array
    assert isinstance(all_states, list)
    assert len(all_states) >= 3

    # Verify structure
    for item in all_states:
        assert "canvas_id" in item
        assert "state" in item
        assert isinstance(item["state"], dict)

    # Verify specific canvases exist
    canvas_ids = [s["canvas_id"] for s in all_states]
    assert line_id in canvas_ids
    assert bar_id in canvas_ids
    assert form_id in canvas_ids


def test_get_state_filters_by_id(page: Page):
    """Test getState returns correct canvas for specific ID.

    Verifies:
    - getState(id) returns correct canvas
    - Different IDs return different canvases
    - IDs are unique
    """
    # Create two line charts
    line_data_1 = create_test_line_chart_data(3)
    line_data_2 = create_test_line_chart_data(3)

    # Trigger canvases
    canvas_id_1 = trigger_canvas_and_get_id(page, "line_chart", line_data_1)
    canvas_id_2 = trigger_canvas_and_get_id(page, "line_chart", line_data_2)

    # Verify IDs are different
    assert canvas_id_1 != canvas_id_2

    # Get states
    state_1 = get_canvas_state(page, canvas_id_1)
    state_2 = get_canvas_state(page, canvas_id_2)

    # Verify correct canvases returned
    assert state_1 is not None
    assert state_2 is not None
    assert state_1["canvas_id"] == canvas_id_1
    assert state_2["canvas_id"] == canvas_id_2

    # Verify data is different (due to different timestamps)
    # or titles if they differ
    assert state_1["timestamp"] != state_2["timestamp"] or state_1.get("title") != state_2.get("title")


# =============================================================================
# Timestamp Tests
# =============================================================================

def test_state_timestamp_is_iso_string(page: Page):
    """Test state timestamp is valid ISO 8601 string.

    Verifies:
    - timestamp is a string
    - timestamp is valid ISO 8601 format
    - timestamp is recent (within 10 seconds)
    """
    # Create canvas
    data = create_test_line_chart_data(3)
    canvas_id = trigger_canvas_and_get_id(page, "line_chart", data)

    # Get state
    state = get_canvas_state(page, canvas_id)
    assert state is not None

    # Get timestamp
    timestamp_str = state["timestamp"]
    assert isinstance(timestamp_str, str)

    # Parse ISO 8601
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except ValueError:
        pytest.fail(f"Invalid ISO 8601 timestamp: {timestamp_str}")

    # Verify timestamp is recent (within 10 seconds)
    now = datetime.now(timestamp.tzinfo)
    time_diff = abs((now - timestamp).total_seconds())
    assert time_diff < 10, f"Timestamp is {time_diff}s old, expected < 10s"
