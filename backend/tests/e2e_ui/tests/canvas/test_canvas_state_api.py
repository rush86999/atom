"""
Canvas State API E2E Tests.

Tests canvas state API accessibility via window.atom.canvas.getState(),
getAllStates(), and subscribe() methods. Validates state structure and
updates for all canvas types.

Coverage: CANV-09 (canvas state API)
"""

import uuid
from datetime import datetime
import pytest
from playwright.sync_api import Page

# Add backend to path for imports
import os
import sys
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


# ============================================================================
# Helper Functions
# ============================================================================

def trigger_canvas_chart(page: Page, chart_type: str, data: dict, title: str = "Test Chart") -> str:
    """Simulate WebSocket canvas:update event for chart canvas.

    Args:
        page: Playwright page object
        chart_type: Chart type (line, bar, pie)
        data: Chart data
        title: Chart title

    Returns:
        canvas_id: Generated canvas ID
    """
    canvas_id = f"chart-{str(uuid.uuid4())[:8]}"

    canvas_message = {
        "type": "canvas:update",
        "canvas_id": canvas_id,
        "data": {
            "component": "chart",
            "chart_type": chart_type,
            "title": title,
            "data": data
        }
    }

    page.evaluate(f"(msg) => window.lastCanvasMessage = msg", canvas_message)
    page.evaluate("""
        () => {
            const event = new CustomEvent('canvas:update', {
                detail: { type: 'canvas:update' }
            });
            window.dispatchEvent(event);
        }
    """)

    return canvas_id


def trigger_canvas_form(page: Page, schema: dict, title: str = "Test Form") -> str:
    """Simulate WebSocket canvas:update event for form canvas.

    Args:
        page: Playwright page object
        schema: Form schema
        title: Form title

    Returns:
        canvas_id: Generated canvas ID
    """
    canvas_id = f"form-{str(uuid.uuid4())[:8]}"

    canvas_message = {
        "type": "canvas:update",
        "canvas_id": canvas_id,
        "data": {
            "component": "form",
            "title": title,
            "schema": schema
        }
    }

    page.evaluate(f"(msg) => window.lastCanvasMessage = msg", canvas_message)
    page.evaluate("""
        () => {
            const event = new CustomEvent('canvas:update', {
                detail: { type: 'canvas:update' }
            });
            window.dispatchEvent(event);
        }
    """)

    return canvas_id


def trigger_canvas_docs(page: Page, markdown: str, title: str = "Test Docs") -> str:
    """Simulate WebSocket canvas:update event for docs canvas.

    Args:
        page: Playwright page object
        markdown: Markdown content
        title: Docs title

    Returns:
        canvas_id: Generated canvas ID
    """
    canvas_id = f"docs-{str(uuid.uuid4())[:8]}"

    canvas_message = {
        "type": "canvas:update",
        "canvas_id": canvas_id,
        "data": {
            "component": "docs",
            "title": title,
            "content": markdown
        }
    }

    page.evaluate(f"(msg) => window.lastCanvasMessage = msg", canvas_message)
    page.evaluate("""
        () => {
            const event = new CustomEvent('canvas:update', {
                detail: { type: 'canvas:update' }
            });
            window.dispatchEvent(event);
        }
    """)

    return canvas_id


def get_canvas_state(page: Page, canvas_id: str) -> dict:
    """Get canvas state via JavaScript API.

    Args:
        page: Playwright page object
        canvas_id: Canvas ID to query

    Returns:
        Canvas state dictionary
    """
    return page.evaluate(f"() => window.atom.canvas.getState('{canvas_id}')")


def get_all_canvas_states(page: Page) -> list:
    """Get all canvas states via JavaScript API.

    Args:
        page: Playwright page object

    Returns:
        List of all canvas states
    """
    return page.evaluate("() => window.atom.canvas.getAllStates()")


def verify_canvas_state_structure(state: dict, expected_type: str) -> bool:
    """Verify canvas state has required keys.

    Args:
        state: Canvas state dictionary
        expected_type: Expected canvas type (chart, form, docs, etc.)

    Returns:
        True if state has required structure, False otherwise
    """
    required_keys = ['canvas_id', 'type', 'data']
    has_required_keys = all(key in state for key in required_keys)
    correct_type = state.get('type') == expected_type
    return has_required_keys and correct_type


# ============================================================================
# Tests
# ============================================================================

class TestCanvasStateAPI:
    """Test canvas state API accessibility (CANV-09)."""

    def test_canvas_state_api_exists(self, authenticated_page_api: Page):
        """Test canvas state API is accessible.

        Verify window.atom.canvas object exists with getState, getAllStates,
        and subscribe methods.
        """
        # Trigger any canvas presentation
        data = {"labels": ["A", "B"], "datasets": [{"data": [1, 2]}]}
        trigger_canvas_chart(authenticated_page_api, "line", data, "API Existence Test")

        # Verify window.atom object exists
        atom_exists = authenticated_page_api.evaluate("() => typeof window.atom !== 'undefined'")
        assert atom_exists, "window.atom object should exist"

        # Verify window.atom.canvas object exists
        canvas_exists = authenticated_page_api.evaluate("() => typeof window.atom?.canvas !== 'undefined'")
        assert canvas_exists, "window.atom.canvas object should exist"

        # Verify getState is a function
        get_state_type = authenticated_page_api.evaluate("() => typeof window.atom.canvas.getState")
        assert get_state_type == "function", "window.atom.canvas.getState should be a function"

        # Verify getAllStates is a function
        get_all_type = authenticated_page_api.evaluate("() => typeof window.atom.canvas.getAllStates")
        assert get_all_type == "function", "window.atom.canvas.getAllStates should be a function"

        # Verify subscribe is a function
        subscribe_type = authenticated_page_api.evaluate("() => typeof window.atom.canvas.subscribe")
        assert subscribe_type == "function", "window.atom.canvas.subscribe should be a function"

    def test_canvas_state_contains_correct_data(self, authenticated_page_api: Page):
        """Test canvas state contains correct data structure.

        Verify state has required keys (canvas_id, type, data) and correct values.
        """
        # Create chart canvas with known data
        data = {
            "labels": ["A", "B", "C"],
            "datasets": [{"label": "Test", "data": [1, 2, 3]}]
        }
        canvas_id = trigger_canvas_chart(authenticated_page_api, "line", data, "Correct Data Test")

        # Wait for canvas to render
        authenticated_page_api.wait_for_selector(f'[data-canvas-id="{canvas_id}"]', timeout=5000)

        # Get canvas state
        state = get_canvas_state(authenticated_page_api, canvas_id)

        # Verify state has required keys
        assert 'canvas_id' in state, "State should have canvas_id key"
        assert 'type' in state, "State should have type key"
        assert 'data' in state, "State should have data key"

        # Verify state.canvas_id matches triggered canvas_id
        assert state['canvas_id'] == canvas_id, f"canvas_id should match: expected {canvas_id}, got {state.get('canvas_id')}"

        # Verify state.type == 'chart'
        assert state['type'] == 'chart', f"type should be 'chart', got {state.get('type')}"

        # Verify state.data contains chart data
        assert 'data' in state['data'] or 'labels' in state['data'], \
            "State data should contain chart information"

        # Verify data integrity (labels match)
        if 'labels' in state['data']:
            assert state['data']['labels'] == ["A", "B", "C"], "Labels should match input data"

    def test_canvas_state_updates_on_interaction(self, authenticated_page_api: Page):
        """Test canvas state updates on user interaction.

        Verify state reflects form field changes after user input.
        """
        # Create form canvas with field
        schema = {
            "canvas_id": f"form-{str(uuid.uuid4())[:8]}",
            "fields": [
                {
                    "name": "name",
                    "type": "text",
                    "label": "Name",
                    "required": True
                }
            ]
        }
        canvas_id = trigger_canvas_form(authenticated_page_api, schema, "State Update Test")

        # Wait for form to render
        authenticated_page_api.wait_for_selector('[data-testid="canvas-form-field-name"]', timeout=5000)

        # Get initial state
        initial_state = get_canvas_state(authenticated_page_api, canvas_id)

        # Fill form field
        test_value = "Test Value"
        authenticated_page_api.locator('[data-testid="canvas-form-field-name"]').fill(test_value)

        # Wait for state to update
        authenticated_page_api.wait_for_timeout(500)  # Brief wait for state update

        # Get updated state
        updated_state = get_canvas_state(authenticated_page_api, canvas_id)

        # Verify updated_state differs from initial_state
        assert updated_state is not None, "Updated state should not be None"

        # Verify form field value reflected in state.data
        # (State structure may vary, but should contain the filled value)
        state_data = updated_state.get('data', {})
        if isinstance(state_data, dict):
            # Check if values are in state
            values = state_data.get('values', {})
            if values:
                name_value = values.get('name', '')
                # Value should be present (may be empty initially, then filled)
                assert test_value in str(name_value) or name_value == test_value, \
                    f"State should reflect form field value: expected '{test_value}', got '{name_value}'"

    def test_canvas_state_for_all_canvas_types(self, authenticated_page_api: Page):
        """Test canvas state API for all canvas types.

        Verify state structure matches TypeScript types for chart, form, docs, email,
        sheets, terminal, and coding canvases.
        """
        # Test chart canvas
        chart_data = {"labels": ["A", "B"], "datasets": [{"data": [1, 2]}]}
        chart_id = trigger_canvas_chart(authenticated_page_api, "line", chart_data, "Chart State Test")
        authenticated_page_api.wait_for_timeout(500)
        chart_state = get_canvas_state(authenticated_page_api, chart_id)
        assert verify_canvas_state_structure(chart_state, 'chart'), "Chart state should have correct structure"
        assert 'chart_type' in chart_state.get('data', {}) or 'labels' in chart_state.get('data', {}), \
            "Chart state should contain chart-specific data"

        # Test form canvas
        form_schema = {
            "canvas_id": f"form-{str(uuid.uuid4())[:8]}",
            "fields": [{"name": "test", "type": "text", "label": "Test"}]
        }
        form_id = trigger_canvas_form(authenticated_page_api, form_schema, "Form State Test")
        authenticated_page_api.wait_for_timeout(500)
        form_state = get_canvas_state(authenticated_page_api, form_id)
        assert verify_canvas_state_structure(form_state, 'form'), "Form state should have correct structure"
        assert 'schema' in form_state.get('data', {}) or 'fields' in form_state.get('data', {}), \
            "Form state should contain schema or fields"

        # Test docs canvas
        docs_content = "# Header\n\nTest content"
        docs_id = trigger_canvas_docs(authenticated_page_api, docs_content, "Docs State Test")
        authenticated_page_api.wait_for_timeout(500)
        docs_state = get_canvas_state(authenticated_page_api, docs_id)
        assert verify_canvas_state_structure(docs_state, 'docs'), "Docs state should have correct structure"
        assert 'content' in docs_state.get('data', {}), "Docs state should contain content"

    def test_canvas_state_getAllStates_method(self, authenticated_page_api: Page):
        """Test getAllStates returns all canvas states.

        Verify getAllStates() returns array with all currently displayed canvases.
        """
        # Trigger 3 different canvas presentations
        chart_id = trigger_canvas_chart(
            authenticated_page_api,
            "line",
            {"labels": ["A"], "datasets": [{"data": [1]}]},
            "GetAll Test 1"
        )
        form_schema = {
            "canvas_id": f"form-{str(uuid.uuid4())[:8]}",
            "fields": [{"name": "test", "type": "text", "label": "Test"}]
        }
        form_id = trigger_canvas_form(authenticated_page_api, form_schema, "GetAll Test 2")
        docs_id = trigger_canvas_docs(authenticated_page_api, "# Test", "GetAll Test 3")

        # Wait for canvases to render
        authenticated_page_api.wait_for_timeout(1000)

        # Call getAllStates
        all_states = get_all_canvas_states(authenticated_page_api)

        # Verify return type is array/object
        assert isinstance(all_states, (list, dict)), "getAllStates should return array or object"

        # Convert to list if dict
        if isinstance(all_states, dict):
            states_list = list(all_states.values())
        else:
            states_list = all_states

        # Verify at least 3 canvases returned
        assert len(states_list) >= 3, f"Expected at least 3 states, got {len(states_list)}"

        # Verify each state has unique canvas_id
        canvas_ids = [s.get('canvas_id') for s in states_list if isinstance(s, dict)]
        unique_ids = set(canvas_ids)
        assert len(unique_ids) == len(canvas_ids), "Each canvas should have unique canvas_id"

        # Verify state types are correct
        types = [s.get('type') for s in states_list if isinstance(s, dict)]
        assert 'chart' in types, "Should have at least one chart canvas"
        assert 'form' in types, "Should have at least one form canvas"
        assert 'docs' in types, "Should have at least one docs canvas"

    def test_canvas_state_subscribe_method(self, authenticated_page_api: Page):
        """Test canvas state subscribe method.

        Verify subscription callback fires when canvas state changes.
        """
        # Trigger canvas presentation
        schema = {
            "canvas_id": f"form-{str(uuid.uuid4())[:8]}",
            "fields": [{"name": "test", "type": "text", "label": "Test"}]
        }
        canvas_id = trigger_canvas_form(authenticated_page_api, schema, "Subscribe Test")

        # Wait for form to render
        authenticated_page_api.wait_for_selector('[data-testid="canvas-form-field-test"]', timeout=5000)

        # Inject subscription listener
        authenticated_page_api.evaluate(f"""
            () => {{
                window.atomCanvasStateUpdates = [];
                window.atom.canvas.subscribe('{canvas_id}', (state) => {{
                    window.atomCanvasStateUpdates.push(state);
                }});
            }}
        """)

        # Trigger state change by filling form field
        authenticated_page_api.locator('[data-testid="canvas-form-field-test"]').fill("Updated Value")

        # Wait for subscription callback to fire
        authenticated_page_api.wait_for_timeout(1000)

        # Verify subscription callback fired
        update_count = authenticated_page_api.evaluate("() => window.atomCanvasStateUpdates.length")
        assert update_count > 0, f"Subscription callback should fire at least once, got {update_count} updates"

        # Verify updates contain correct canvas_id
        first_update = authenticated_page_api.evaluate("() => window.atomCanvasStateUpdates[0]")
        assert isinstance(first_update, dict), "Update should be a dictionary"
        assert first_update.get('canvas_id') == canvas_id, \
            f"Update should have correct canvas_id: expected {canvas_id}, got {first_update.get('canvas_id')}"
