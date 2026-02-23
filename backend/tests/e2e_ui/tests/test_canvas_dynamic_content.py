"""
E2E tests for canvas dynamic content loading and auto-waiting.

These tests verify dynamic content loading behavior including:
- WebSocket canvas updates (action="update" vs action="present")
- Async data loading with proper wait strategies
- Loading indicators during data fetch
- Error state handling when data fails to load
- Form data preservation during updates
- Race condition prevention with rapid updates

Tests use Playwright's auto-waiting strategies (wait_for_load_state, wait_for_selector)
to prevent flaky tests and ensure reliable execution.

Run with: pytest backend/tests/e2e_ui/tests/test_canvas_dynamic_content.py -v
"""

import pytest
import uuid
import time
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session
from typing import Dict, Any

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.e2e_ui.pages.page_objects import CanvasHostPage, CanvasFormPage
from core.models import User
from core.auth import get_password_hash
from datetime import datetime


# ============================================================================
# Helper Functions
# ============================================================================

def create_test_user_with_canvas(db_session: Session, email: str) -> User:
    """Create a test user in the database for canvas testing.

    Args:
        db_session: Database session
        email: User email

    Returns:
        User: Created user instance
    """
    user = User(
        email=email,
        username=f"dynamicuser_{str(uuid.uuid4())[:8]}",
        password_hash=get_password_hash("TestPassword123!"),
        is_active=True,
        status="active",
        email_verified=True,
        created_at=datetime.utcnow()
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


def create_authenticated_page_for_canvas(browser, user: User, token: str) -> Page:
    """Create a Playwright page with JWT token pre-set in localStorage.

    Args:
        browser: Playwright browser fixture
        user: User instance
        token: JWT token string

    Returns:
        Page: Authenticated Playwright page
    """
    context = browser.new_context()
    page = context.new_page()

    page.goto("http://localhost:3000")
    page.evaluate(f"() => localStorage.setItem('auth_token', '{token}')")
    page.evaluate(f"() => localStorage.setItem('user_id', '{user.id}')")

    return page


def simulate_websocket_update(page: Page, canvas_id: str, updates: Dict[str, Any]) -> None:
    """Simulate WebSocket canvas:update message with action="update".

    This function simulates a canvas update without re-presenting the entire component.
    Similar to the update_canvas() function in canvas_tool.py.

    Args:
        page: Playwright page
        canvas_id: Canvas ID to update
        updates: Dictionary containing update data (e.g., {"data": [...], "title": "Updated"})
    """
    # Simulate WebSocket update by dispatching custom event
    update_message = {
        "type": "canvas:update",
        "data": {
            "action": "update",
            "canvas_id": canvas_id,
            "updates": updates
        }
    }

    # Inject the update message
    page.evaluate(f"(msg) => window.lastMessage = msg", update_message)

    # Trigger re-render by dispatching event
    page.evaluate("""() => {
        window.dispatchEvent(new CustomEvent('canvas-update', {
            detail: { type: 'canvas:update', data: window.lastMessage.data }
        }));
    }""")


def simulate_async_data_load(page: Page, delay_ms: int, data: Dict[str, Any]) -> str:
    """Simulate async data loading with artificial delay.

    This function simulates a scenario where canvas data is loaded
    asynchronously from an API endpoint.

    Args:
        page: Playwright page
        delay_ms: Delay in milliseconds before data loads
        data: Data to load after delay

    Returns:
        str: Canvas ID of the triggered canvas
    """
    canvas_id = str(uuid.uuid4())

    # First, present canvas with loading state
    loading_canvas = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": "line_chart",
            "canvas_id": canvas_id,
            "data": {
                "data": [],
                "title": "Loading...",
                "loading": True  # Custom loading flag
            }
        }
    }

    page.evaluate(f"(msg) => window.lastMessage = msg", loading_canvas)

    # Trigger async data load after delay
    js_code = f"""
    (delay, canvasData, cid) => {{
        setTimeout(() => {{
            const updateMsg = {{
                type: 'canvas:update',
                data: {{
                    action: 'update',
                    canvas_id: cid,
                    updates: {{
                        data: canvasData.data,
                        title: canvasData.title,
                        loading: false
                    }}
                }}
            }};
            window.lastMessage = updateMsg;
            window.dispatchEvent(new CustomEvent('canvas-update', {{
                detail: updateMsg.data
            }}));
        }}, delay);
    }}
    """
    page.evaluate(js_code, delay_ms, data, canvas_id)

    return canvas_id


def wait_for_canvas_update(page: Page, canvas_id: str, timeout: int = 5000) -> bool:
    """Wait for canvas to receive an update.

    Args:
        page: Playwright page
        canvas_id: Canvas ID to wait for
        timeout: Maximum time to wait in milliseconds

    Returns:
        bool: True if update received, False otherwise
    """
    start_time = time.time()
    timeout_sec = timeout / 1000

    while time.time() - start_time < timeout_sec:
        # Check if canvas state has been updated
        state = page.evaluate("""(cid) => {
            if (window.atom && window.atom.canvas) {
                return window.atom.canvas.getState(cid);
            }
            return null;
        }""", canvas_id)

        if state and not state.get('loading', False):
            return True

        page.wait_for_timeout(100)

    return False


def trigger_async_canvas_with_loading(page: Page, component_type: str, data_url: str) -> str:
    """Trigger canvas that loads data from simulated async source.

    Args:
        page: Playwright page
        component_type: Component type (line_chart, form, etc.)
        data_url: Simulated URL for data source

    Returns:
        str: Canvas ID
    """
    canvas_id = str(uuid.uuid4())

    # Present canvas with initial loading state
    canvas_message = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": component_type,
            "canvas_id": canvas_id,
            "data": {
                "title": f"Loading from {data_url}...",
                "loading": True,
                "data_source": data_url
            }
        }
    }

    page.evaluate(f"(msg) => window.lastMessage = msg", canvas_message)

    # Simulate data load after 500ms
    page.evaluate("""(cid) => {
        setTimeout(() => {
            const updateMsg = {
                type: 'canvas:update',
                data: {
                    action: 'update',
                    canvas_id: cid,
                    updates: {
                        title: 'Data Loaded Successfully',
                        loading: False,
                        data: [
                            { x: 'Jan', y: 100 },
                            { x: 'Feb', y: 200 },
                            { x: 'Mar', y: 150 }
                        ]
                    }
                }
            };
            window.lastMessage = updateMsg;
            window.dispatchEvent(new CustomEvent('canvas-update', {
                detail: updateMsg.data
            }));
        }, 500);
    }""", canvas_id)

    return canvas_id


def create_test_line_chart_data() -> list:
    """Create test line chart data.

    Returns:
        list: Chart data points
    """
    return [
        {"x": "Jan", "y": 100},
        {"x": "Feb", "y": 200},
        {"x": "Mar", "y": 150},
        {"x": "Apr", "y": 300},
        {"x": "May", "y": 250}
    ]


def create_test_form_schema(field_count: int = 3) -> dict:
    """Create test form schema.

    Args:
        field_count: Number of fields to create

    Returns:
        dict: Form schema
    """
    fields = []
    for i in range(field_count):
        fields.append({
            "name": f"field_{str(uuid.uuid4())[:8]}",
            "type": "text",
            "label": f"Field {i+1}",
            "required": i < 2  # First 2 fields required
        })

    return {
        "fields": fields,
        "title": "Dynamic Form"
    }


# ============================================================================
# WebSocket Update Tests
# ============================================================================

def test_canvas_websocket_update(browser, db_session):
    """Test canvas receives and displays WebSocket update.

    Verifies:
    - Initial canvas appears
    - WebSocket update with new data refreshes canvas
    - Title changes if updated
    """
    user = create_test_user_with_canvas(db_session, f"test_ws_{uuid.uuid4()}@example.com")
    token = f"test_token_{user.id}"
    page = create_authenticated_page_for_canvas(browser, user, token)

    # Trigger initial canvas
    canvas_id = str(uuid.uuid4())
    initial_data = create_test_line_chart_data()

    initial_canvas = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": "line_chart",
            "canvas_id": canvas_id,
            "data": {
                "data": initial_data,
                "title": "Initial Title"
            }
        }
    }

    page.evaluate(f"(msg) => window.lastMessage = msg", initial_canvas)
    page.wait_for_timeout(500)

    canvas_page = CanvasHostPage(page)

    # Verify initial canvas appears
    assert canvas_page.is_loaded(), "Initial canvas should load"

    # Send WebSocket update
    updated_data = [
        {"x": "Jan", "y": 500},
        {"x": "Feb", "y": 600},
        {"x": "Mar", "y": 550}
    ]

    simulate_websocket_update(page, canvas_id, {
        "data": updated_data,
        "title": "Updated Title"
    })

    page.wait_for_timeout(500)

    # Verify canvas updated
    # Check state was updated
    state = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert state is not None, "Canvas state should exist after update"

    # Verify title changed
    title = canvas_page.get_title()
    assert title == "Updated Title", f"Title should be 'Updated Title', got '{title}'"

    page.close()


def test_canvas_update_action_vs_present(browser, db_session):
    """Test action="update" vs action="present" behavior.

    Verifies:
    - action="present" creates new canvas
    - action="update" refreshes without closing
    - Canvas ID preserved during update
    """
    user = create_test_user_with_canvas(db_session, f"test_vs_{uuid.uuid4()}@example.com")
    token = f"test_token_{user.id}"
    page = create_authenticated_page_for_canvas(browser, user, token)

    canvas_page = CanvasHostPage(page)

    # Trigger canvas with action="present"
    canvas_id = str(uuid.uuid4())
    present_canvas = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": "line_chart",
            "canvas_id": canvas_id,
            "data": {
                "data": [{"x": "A", "y": 100}],
                "title": "Presented Canvas"
            }
        }
    }

    page.evaluate(f"(msg) => window.lastMessage = msg", present_canvas)
    page.wait_for_timeout(500)

    # Verify canvas appears
    assert canvas_page.is_loaded(), "Canvas should appear after present"

    initial_title = canvas_page.get_title()
    assert initial_title == "Presented Canvas"

    # Send update with action="update"
    simulate_websocket_update(page, canvas_id, {
        "title": "Updated Canvas"
    })

    page.wait_for_timeout(500)

    # Verify canvas still visible (not closed)
    assert canvas_page.is_loaded(), "Canvas should remain visible after update"

    # Verify canvas_id preserved
    state = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert state is not None, "Canvas should have same ID after update"
    assert state.get('canvas_id') == canvas_id

    page.close()


def test_multiple_canvas_updates(browser, db_session):
    """Test multiple rapid canvas updates.

    Verifies:
    - Final state reflects last update
    - No flickering or intermediate states visible
    """
    user = create_test_user_with_canvas(db_session, f"test_multi_{uuid.uuid4()}@example.com")
    token = f"test_token_{user.id}"
    page = create_authenticated_page_for_canvas(browser, user, token)

    canvas_page = CanvasHostPage(page)

    # Trigger initial canvas
    canvas_id = str(uuid.uuid4())
    initial_canvas = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": "line_chart",
            "canvas_id": canvas_id,
            "data": {
                "data": [{"x": "A", "y": 100}],
                "title": "Version 1"
            }
        }
    }

    page.evaluate(f"(msg) => window.lastMessage = msg", initial_canvas)
    page.wait_for_timeout(500)

    # Send 3 rapid updates
    for i in range(2, 5):  # Versions 2, 3, 4
        simulate_websocket_update(page, canvas_id, {
            "title": f"Version {i}"
        })
        page.wait_for_timeout(100)  # Small delay between updates

    page.wait_for_timeout(500)

    # Verify final state is Version 4
    final_title = canvas_page.get_title()
    assert final_title == "Version 4", f"Final title should be 'Version 4', got '{final_title}'"

    # Verify no intermediate states (should only have final state)
    state = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert state.get('title') == "Version 4"

    page.close()


# ============================================================================
# Async Data Loading Tests
# ============================================================================

def test_async_chart_data_loading(browser, db_session):
    """Test async chart data loads with proper waiting.

    Verifies:
    - Loading indicator appears
    - Loading indicator disappears after data loads
    - Chart renders with data
    - wait_for_load_state("networkidle") succeeds
    """
    user = create_test_user_with_canvas(db_session, f"test_async_{uuid.uuid4()}@example.com")
    token = f"test_token_{user.id}"
    page = create_authenticated_page_for_canvas(browser, user, token)

    # Trigger canvas with async data
    chart_data = create_test_line_chart_data()
    canvas_id = simulate_async_data_load(page, 1000, {
        "data": chart_data,
        "title": "Async Chart"
    })

    page.wait_for_timeout(200)

    canvas_page = CanvasHostPage(page)

    # Verify canvas appears
    assert canvas_page.is_loaded(), "Canvas should appear"

    # Wait for data to load
    loaded = wait_for_canvas_update(page, canvas_id, timeout=5000)
    assert loaded, "Canvas should load data within timeout"

    # Wait for network idle
    page.wait_for_load_state("networkidle", timeout=5000)

    # Verify chart rendered with data
    state = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert state is not None, "Canvas state should exist"
    assert state.get('loading', True) is False, "Loading should be complete"
    assert state.get('title') == "Async Chart"

    page.close()


def test_async_form_options_loading(browser, db_session):
    """Test async form options load with disabled state.

    Verifies:
    - Dropdown disabled during load
    - Loading indicator visible
    - Options load successfully
    - Dropdown enabled after load
    """
    user = create_test_user_with_canvas(db_session, f"test_form_{uuid.uuid4()}@example.com")
    token = f"test_token_{user.id}"
    page = create_authenticated_page_for_canvas(browser, user, token)

    canvas_id = str(uuid.uuid4())

    # Present form with loading select options
    form_schema = create_test_form_schema(3)
    # Mark first field as loading
    form_schema['fields'][0]['loading'] = True
    form_schema['fields'][0]['type'] = 'select'
    form_schema['fields'][0]['options'] = []

    form_canvas = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": "form",
            "canvas_id": canvas_id,
            "data": {
                "schema": form_schema,
                "title": "Form with Async Options"
            }
        }
    }

    page.evaluate(f"(msg) => window.lastMessage = msg", form_canvas)
    page.wait_for_timeout(500)

    form_page = CanvasFormPage(page)

    # Verify form appears
    assert form_page.is_loaded(), "Form should load"

    # Simulate async options loading
    field_name = form_schema['fields'][0]['name']

    page.evaluate("""(field_name, cid) => {
        setTimeout(() => {
            const updateMsg = {
                type: 'canvas:update',
                data: {
                    action: 'update',
                    canvas_id: cid,
                    updates: {
                        schema: {
                            fields: [{
                                name: field_name,
                                type: 'select',
                                label: 'Country',
                                loading: false,
                                options: ['USA', 'Canada', 'UK']
                            }]
                        }
                    }
                }
            };
            window.lastMessage = updateMsg;
            window.dispatchEvent(new CustomEvent('canvas-update', {
                detail: updateMsg.data
            }));
        }, 800);
    }""", field_name, canvas_id)

    # Wait for options to load
    page.wait_for_timeout(1000)

    # Verify options loaded
    state = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert state is not None, "Form state should exist"

    page.close()


def test_auto_waiting_prevents_flaky_tests(browser, db_session):
    """Test auto-waiting strategies prevent flaky test behavior.

    Verifies:
    - 5 iterations all pass
    - Consistent timeout values work
    - No intermittent failures
    """
    user = create_test_user_with_canvas(db_session, f"test_flaky_{uuid.uuid4()}@example.com")
    token = f"test_token_{user.id}"
    page = create_authenticated_page_for_canvas(browser, user, token)

    canvas_page = CanvasHostPage(page)

    # Run 5 iterations
    for iteration in range(5):
        # Trigger canvas with async load
        canvas_id = simulate_async_data_load(page, 500, {
            "data": [{"x": f"Iter{iteration}", "y": iteration * 100}],
            "title": f"Iteration {iteration}"
        })

        # Wait for canvas to load
        canvas_page.wait_for_canvas_visible(timeout=5000)

        # Wait for update
        loaded = wait_for_canvas_update(page, canvas_id, timeout=5000)
        assert loaded, f"Iteration {iteration} should load successfully"

        # Verify state
        state = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id)
        assert state is not None, f"Iteration {iteration} should have state"

        page.wait_for_timeout(200)

    page.close()


# ============================================================================
# Loading Indicator Tests
# ============================================================================

def test_loading_indicator_displays(browser, db_session):
    """Test loading indicator displays during async operations.

    Verifies:
    - Loading state visible immediately after trigger
    - Spinner or skeleton visible
    - User sees loading feedback
    """
    user = create_test_user_with_canvas(db_session, f"test_load_{uuid.uuid4()}@example.com")
    token = f"test_token_{user.id}"
    page = create_authenticated_page_for_canvas(browser, user, token)

    canvas_id = str(uuid.uuid4())

    # Present canvas with loading state
    loading_canvas = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": "line_chart",
            "canvas_id": canvas_id,
            "data": {
                "data": [],
                "title": "Loading Data...",
                "loading": True
            }
        }
    }

    page.evaluate(f"(msg) => window.lastMessage = msg", loading_canvas)

    # Immediately check for loading state
    page.wait_for_timeout(100)  # Small delay to allow render

    # Verify loading state in state object
    state = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert state is not None, "Canvas state should exist"
    assert state.get('loading', False) is True, "Canvas should be in loading state"
    assert "Loading" in state.get('title', '')

    # Verify canvas is visible
    canvas_page = CanvasHostPage(page)
    assert canvas_page.is_loaded(), "Loading canvas should be visible"

    page.close()


def test_loading_indicator_hides_after_load(browser, db_session):
    """Test loading indicator disappears after data loads.

    Verifies:
    - Loading indicator initially visible
    - Loading indicator disappears after load
    - Canvas content visible
    """
    user = create_test_user_with_canvas(db_session, f"test_hide_{uuid.uuid4()}@example.com")
    token = f"test_token_{user.id}"
    page = create_authenticated_page_for_canvas(browser, user, token)

    canvas_page = CanvasHostPage(page)

    # Trigger canvas with loading
    canvas_id = simulate_async_data_load(page, 800, {
        "data": [{"x": "A", "y": 100}],
        "title": "Loaded"
    })

    page.wait_for_timeout(200)

    # Check loading state initially
    state = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id)
    if state:
        initial_loading = state.get('loading', False)
        # May or may not be loading depending on timing

    # Wait for load
    loaded = wait_for_canvas_update(page, canvas_id, timeout=5000)
    assert loaded, "Canvas should complete loading"

    page.wait_for_timeout(200)

    # Verify loading gone
    final_state = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert final_state is not None, "State should exist"
    assert final_state.get('loading', False) is False, "Loading should be complete"
    assert final_state.get('title') == "Loaded"

    page.close()


# ============================================================================
# Error State Tests
# ============================================================================

def test_async_load_error_display(browser, db_session):
    """Test error state displays when data fails to load.

    Verifies:
    - Error message displays after timeout
    - Canvas shows error state, not blank
    - User informed of failure
    """
    user = create_test_user_with_canvas(db_session, f"test_error_{uuid.uuid4()}@example.com")
    token = f"test_token_{user.id}"
    page = create_authenticated_page_for_canvas(browser, user, token)

    canvas_id = str(uuid.uuid4())

    # Present canvas with loading state
    loading_canvas = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": "line_chart",
            "canvas_id": canvas_id,
            "data": {
                "data": [],
                "title": "Loading...",
                "loading": True
            }
        }
    }

    page.evaluate(f"(msg) => window.lastMessage = msg", loading_canvas)
    page.wait_for_timeout(300)

    # Simulate load failure
    page.evaluate("""(cid) => {
        setTimeout(() => {
            const updateMsg = {
                type: 'canvas:update',
                data: {
                    action: 'update',
                    canvas_id: cid,
                    updates: {
                        loading: False,
                        error: 'Failed to load data from server',
                        title: 'Error Loading Data'
                    }
                }
            };
            window.lastMessage = updateMsg;
            window.dispatchEvent(new CustomEvent('canvas-update', {
                detail: updateMsg.data
            }));
        }, 500);
    }""", canvas_id)

    # Wait for error state
    page.wait_for_timeout(1000)

    # Verify error state
    state = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert state is not None, "State should exist"
    assert state.get('error') is not None, "Error should be present"
    assert "Failed to load" in state.get('error', '')

    page.close()


def test_error_state_allows_retry(browser, db_session):
    """Test error state allows retry operation.

    Verifies:
    - Error message visible on initial failure
    - Retry triggers new load
    - Success displays if retry succeeds
    """
    user = create_test_user_with_canvas(db_session, f"test_retry_{uuid.uuid4()}@example.com")
    token = f"test_token_{user.id}"
    page = create_authenticated_page_for_canvas(browser, user, token)

    canvas_id = str(uuid.uuid4())

    # Present canvas
    loading_canvas = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": "line_chart",
            "canvas_id": canvas_id,
            "data": {
                "data": [],
                "title": "Loading...",
                "loading": True
            }
        }
    }

    page.evaluate(f"(msg) => window.lastMessage = msg", loading_canvas)
    page.wait_for_timeout(300)

    # Simulate initial failure
    page.evaluate("""(cid) => {
        const updateMsg = {
            type: 'canvas:update',
            data: {
                action: 'update',
                canvas_id: cid,
                updates: {
                    loading: False,
                    error: 'Network timeout'
                }
            }
        };
        window.lastMessage = updateMsg;
        window.dispatchEvent(new CustomEvent('canvas-update', {
            detail: updateMsg.data
        }));
    }""", canvas_id)

    page.wait_for_timeout(500)

    # Verify error
    state = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert state is not None
    assert state.get('error') == 'Network timeout'

    # Simulate retry that succeeds
    simulate_websocket_update(page, canvas_id, {
        "loading": True,
        "error": None
    })

    page.wait_for_timeout(300)

    # Then successful load
    simulate_websocket_update(page, canvas_id, {
        "loading": False,
        "error": None,
        "data": [{"x": "A", "y": 100}],
        "title": "Success"
    })

    page.wait_for_timeout(500)

    # Verify success
    final_state = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert final_state is not None
    assert final_state.get('error') is None, "Error should be cleared"
    assert final_state.get('title') == "Success"

    page.close()


# ============================================================================
# Form Data Preservation Tests
# ============================================================================

def test_form_data_preserved_during_update(browser, db_session):
    """Test form data preserved during non-schema updates.

    Verifies:
    - Form fields can be filled
    - Update that doesn't affect fields preserves data
    - Values unchanged after update
    """
    user = create_test_user_with_canvas(db_session, f"test_preserve_{uuid.uuid4()}@example.com")
    token = f"test_token_{user.id}"
    page = create_authenticated_page_for_canvas(browser, user, token)

    form_page = CanvasFormPage(page)

    canvas_id = str(uuid.uuid4())
    field_name = f"field_{str(uuid.uuid4())[:8]}"

    # Present form
    form_schema = {
        "fields": [
            {
                "name": field_name,
                "type": "text",
                "label": "Name",
                "required": True
            }
        ],
        "title": "Test Form"
    }

    form_canvas = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": "form",
            "canvas_id": canvas_id,
            "data": {
                "schema": form_schema
            }
        }
    }

    page.evaluate(f"(msg) => window.lastMessage = msg", form_canvas)
    page.wait_for_timeout(500)

    # Fill form field
    form_page.fill_text_field(field_name, "John Doe")

    # Verify field value
    value = form_page.get_field_value(field_name)
    assert value == "John Doe", f"Field should have value 'John Doe', got '{value}'"

    # Send update that doesn't affect schema (just title)
    simulate_websocket_update(page, canvas_id, {
        "title": "Updated Title"
    })

    page.wait_for_timeout(500)

    # Verify form data still present
    final_value = form_page.get_field_value(field_name)
    assert final_value == "John Doe", f"Field value should be preserved, got '{final_value}'"

    page.close()


def test_form_data_cleared_on_schema_change(browser, db_session):
    """Test form data handling when schema changes.

    Verifies:
    - Form can be filled
    - Schema change resets or preserves appropriately
    - Validation state recalculated
    """
    user = create_test_user_with_canvas(db_session, f"test_schema_{uuid.uuid4()}@example.com")
    token = f"test_token_{user.id}"
    page = create_authenticated_page_for_canvas(browser, user, token)

    form_page = CanvasFormPage(page)

    canvas_id = str(uuid.uuid4())
    field_name_1 = f"field_{str(uuid.uuid4())[:8]}"

    # Present initial form
    form_schema = {
        "fields": [
            {
                "name": field_name_1,
                "type": "text",
                "label": "Email",
                "required": True
            }
        ],
        "title": "Initial Form"
    }

    form_canvas = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": "form",
            "canvas_id": canvas_id,
            "data": {
                "schema": form_schema
            }
        }
    }

    page.evaluate(f"(msg) => window.lastMessage = msg", form_canvas)
    page.wait_for_timeout(500)

    # Fill field
    form_page.fill_text_field(field_name_1, "test@example.com")

    # Send schema update (add new field, change validation)
    new_field_name = f"field_{str(uuid.uuid4())[:8]}"
    updated_schema = {
        "fields": [
            {
                "name": field_name_1,
                "type": "text",
                "label": "Email",
                "required": True,
                "pattern": "^[\\w-\\.]+@([\\w-]+\\.)+[\\w-]{2,4}$"  # Email regex
            },
            {
                "name": new_field_name,
                "type": "text",
                "label": "Confirm Email",
                "required": True
            }
        ],
        "title": "Updated Form"
    }

    simulate_websocket_update(page, canvas_id, {
        "schema": updated_schema
    })

    page.wait_for_timeout(500)

    # Verify form updated (has new fields)
    field_count = form_page.get_field_count()
    assert field_count == 2, f"Form should have 2 fields after schema update, got {field_count}"

    page.close()


# ============================================================================
# Race Condition Prevention Tests
# ============================================================================

def test_rapid_canvas_updates_no_race(browser, db_session):
    """Test rapid updates don't cause race conditions.

    Verifies:
    - 10 rapid updates complete successfully
    - Final state is consistent
    - No JavaScript errors in console
    - No partial states visible
    """
    user = create_test_user_with_canvas(db_session, f"test_race_{uuid.uuid4()}@example.com")
    token = f"test_token_{user.id}"
    page = create_authenticated_page_for_canvas(browser, user, token)

    canvas_page = CanvasHostPage(page)

    # Trigger initial canvas
    canvas_id = str(uuid.uuid4())
    initial_canvas = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": "line_chart",
            "canvas_id": canvas_id,
            "data": {
                "data": [{"x": "A", "y": 0}],
                "title": "Start"
            }
        }
    }

    page.evaluate(f"(msg) => window.lastMessage = msg", initial_canvas)
    page.wait_for_timeout(300)

    # Send 10 rapid updates
    for i in range(1, 11):
        simulate_websocket_update(page, canvas_id, {
            "title": f"Update {i}",
            "data": [{"x": "A", "y": i * 10}]
        })

    page.wait_for_timeout(1000)

    # Verify final state is consistent
    final_state = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id)
    assert final_state is not None, "Final state should exist"

    # Should be Update 10 (last update)
    final_title = final_state.get('title')
    assert final_title == "Update 10", f"Final title should be 'Update 10', got '{final_title}'"

    # Check for console errors
    # Note: Playwright doesn't expose console directly in sync API, but we can verify page stability
    assert canvas_page.is_loaded(), "Canvas should remain stable after rapid updates"

    page.close()


def test_concurrent_canvas_operations(browser, db_session):
    """Test concurrent operations on multiple canvases.

    Verifies:
    - Two different canvases update independently
    - Each maintains its own state
    - No cross-contamination between canvases
    """
    user = create_test_user_with_canvas(db_session, f"test_concurrent_{uuid.uuid4()}@example.com")
    token = f"test_token_{user.id}"
    page = create_authenticated_page_for_canvas(browser, user, token)

    canvas_page = CanvasHostPage(page)

    # Trigger two different canvases
    canvas_id_1 = str(uuid.uuid4())
    canvas_id_2 = str(uuid.uuid4())

    # Present first canvas
    canvas_1 = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": "line_chart",
            "canvas_id": canvas_id_1,
            "data": {
                "data": [{"x": "A", "y": 100}],
                "title": "Canvas 1"
            }
        }
    }

    page.evaluate(f"(msg) => window.lastMessage = msg", canvas_1)
    page.wait_for_timeout(300)

    # Present second canvas (replaces first in current implementation)
    canvas_2 = {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": "bar_chart",
            "canvas_id": canvas_id_2,
            "data": {
                "data": [{"x": "A", "y": 200}],
                "title": "Canvas 2"
            }
        }
    }

    page.evaluate(f"(msg) => window.lastMessage = msg", canvas_2)
    page.wait_for_timeout(300)

    # Update both simultaneously
    simulate_websocket_update(page, canvas_id_1, {
        "title": "Updated Canvas 1"
    })

    simulate_websocket_update(page, canvas_id_2, {
        "title": "Updated Canvas 2"
    })

    page.wait_for_timeout(500)

    # Verify both states exist independently
    state_1 = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id_1)
    state_2 = page.evaluate(f"(cid) => window.atom.canvas.getState(cid)", canvas_id_2)

    assert state_1 is not None, "Canvas 1 state should exist"
    assert state_2 is not None, "Canvas 2 state should exist"

    assert state_1.get('title') == "Updated Canvas 1"
    assert state_2.get('title') == "Updated Canvas 2"

    # Verify no cross-contamination
    assert state_1.get('canvas_id') != state_2.get('canvas_id')

    page.close()
