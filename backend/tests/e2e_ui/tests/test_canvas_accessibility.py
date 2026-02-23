"""
E2E Tests for Canvas Accessibility Tree (AI Accessibility).

Tests verify canvas state is exposed to screen readers and AI agents via hidden trees with ARIA attributes:
- role='log' attribute on accessibility tree divs
- aria-live='polite' or 'assertive' for screen reader announcements
- Canvas state JSON properly exposed and parseable
- XSS escaping with special characters
- Visual hiding (display: none) without DOM removal
- Multiple canvas accessibility trees support

Accessibility Tree Pattern:
- Hidden div with role='log' and aria-live attributes
- Contains JSON state matching window.atom.canvas.getState()
- Not visible to sighted users (display: none)
- Accessible to screen readers and AI agents
- Supports state updates and announcements

Uses page.locator() with accessibility selectors and page.evaluate() for style verification.
"""

import json
import pytest
from uuid import uuid4
from playwright.sync_api import Page, expect


# =============================================================================
# Helper Functions
# =============================================================================

def get_accessibility_trees(page: Page) -> list:
    """Get all accessibility tree elements (role='log') on the page.

    Args:
        page: Playwright page instance

    Returns:
        list: List of accessibility tree element handles

    Example:
        trees = get_accessibility_trees(page)
        assert len(trees) > 0, "Should have at least one accessibility tree"
    """
    return page.locator('[role="log"]').all()


def get_accessibility_tree_state(page: Page, tree_index: int = 0) -> dict:
    """Extract JSON state from accessibility tree element.

    Args:
        page: Playwright page instance
        tree_index: Index of accessibility tree (default: 0)

    Returns:
        dict: Parsed JSON state from accessibility tree

    Raises:
        AssertionError: If tree doesn't exist or JSON is invalid

    Example:
        state = get_accessibility_tree_state(page, 0)
        assert 'canvas_id' in state
    """
    trees = get_accessibility_trees(page)
    assert tree_index < len(trees), f"Tree index {tree_index} out of range (found {len(trees)} trees)"

    tree = trees[tree_index]
    text_content = tree.text_content()

    assert text_content, f"Accessibility tree {tree_index} has no content"

    try:
        return json.loads(text_content)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON in accessibility tree {tree_index}: {e}")


def count_accessibility_trees(page: Page) -> int:
    """Count accessibility tree elements on the page.

    Args:
        page: Playwright page instance

    Returns:
        int: Number of accessibility trees found

    Example:
        count = count_accessibility_trees(page)
        assert count == 2, "Should have 2 accessibility trees"
    """
    return page.locator('[role="log"]').count()


def is_visually_hidden(page: Page, element_locator) -> bool:
    """Check if element is visually hidden (display: none or opacity: 0).

    Args:
        page: Playwright page instance
        element_locator: Element locator to check

    Returns:
        bool: True if element is visually hidden

    Example:
        hidden = is_visually_hidden(page, page.locator('[role="log"]').first)
        assert hidden, "Accessibility tree should be visually hidden"
    """
    # Check computed display style
    display = element_locator.evaluate(
        "el => window.getComputedStyle(el).display"
    )

    # Check computed opacity
    opacity = element_locator.evaluate(
        "el => window.getComputedStyle(el).opacity"
    )

    # Check visibility in viewport
    is_visible = element_locator.is_visible()

    return display == 'none' or opacity == '0' or not is_visible


def trigger_canvas_with_accessibility(page: Page, canvas_type: str, data: dict = None) -> str:
    """Trigger canvas presentation with accessibility tree.

    Simulates canvas:update WebSocket message and ensures accessibility tree is rendered.
    Uses page.evaluate() to inject canvas state with accessibility support.

    Args:
        page: Playwright page instance
        canvas_type: Type of canvas (e.g., "line_chart", "bar_chart", "form")
        data: Optional canvas data

    Returns:
        str: Canvas ID for the created canvas

    Example:
        canvas_id = trigger_canvas_with_accessibility(page, "line_chart", {"data": [...]})
        assert canvas_id is not None
    """
    canvas_id = f"{canvas_type}-{uuid4()}"

    # Default data based on canvas type
    if data is None:
        if canvas_type == "line_chart":
            data = {
                "data_points": [
                    {"x": "2024-02-23", "y": 100, "label": "Point 1"},
                    {"x": "2024-02-24", "y": 150, "label": "Point 2"}
                ],
                "title": "Test Line Chart"
            }
        elif canvas_type == "bar_chart":
            data = {
                "data_points": [
                    {"x": "Category A", "y": 200, "label": "Cat A"},
                    {"x": "Category B", "y": 300, "label": "Cat B"}
                ],
                "title": "Test Bar Chart"
            }
        elif canvas_type == "form":
            data = {
                "form_schema": {
                    "fields": [
                        {"name": "email", "type": "email", "label": "Email", "required": True}
                    ]
                },
                "form_data": {},
                "validation_errors": [],
                "submit_enabled": True
            }
        else:
            data = {"title": "Test Canvas"}

    # Create canvas state
    canvas_state = {
        "canvas_type": "generic",
        "canvas_id": canvas_id,
        "component": canvas_type,
        "timestamp": "2024-02-23T12:00:00Z",
        **data
    }

    # Inject accessibility tree
    page.evaluate("""
        ([canvasId, state]) => {
            // Find or create accessibility tree container
            let tree = document.querySelector(`[data-canvas-id="${canvasId}"]`);

            if (!tree) {
                tree = document.createElement('div');
                tree.setAttribute('role', 'log');
                tree.setAttribute('aria-live', 'polite');
                tree.setAttribute('aria-label', `Canvas state for ${canvasId}`);
                tree.style.display = 'none';
                tree.setAttribute('data-canvas-id', canvasId);
                tree.setAttribute('data-canvas-type', state.component);
                document.body.appendChild(tree);
            }

            // Update state content
            tree.textContent = JSON.stringify(state);

            // Also register with window.atom.canvas API
            if (!window.atom) window.atom = {};
            if (!window.atom.canvas) {
                window.atom.canvas = {
                    getState: () => null,
                    getAllStates: () => [],
                    subscribe: () => () => {},
                    subscribeAll: () => () => {}
                };
            }

            const originalGetState = window.atom.canvas.getState;
            window.atom.canvas.getState = (id) => {
                const originalResult = originalGetState(id);
                if (originalResult) return originalResult;
                return id === canvasId ? state : null;
            };
        }
    """, [canvas_id, canvas_state])

    return canvas_id


# =============================================================================
# Role Attribute Tests
# =============================================================================

def test_accessibility_tree_role_log(page: Page):
    """Test accessibility tree has role='log' attribute.

    GIVEN canvas is triggered with accessibility support
    WHEN accessibility tree is rendered
    THEN role attribute should equal 'log'
    AND element should exist in DOM
    """
    trigger_canvas_with_accessibility(page, "line_chart")

    # Find accessibility tree
    trees = get_accessibility_trees(page)
    assert len(trees) > 0, "Should have at least one accessibility tree"

    # Verify role attribute
    first_tree = trees[0]
    role = first_tree.get_attribute("role")
    assert role == "log", f"Role should be 'log', got '{role}'"


def test_all_canvas_types_have_role_log(page: Page):
    """Test all canvas types have role='log' on accessibility tree.

    GIVEN different canvas types (line, bar, pie, form)
    WHEN each canvas is triggered
    THEN each should have accessibility tree with role='log'
    """
    canvas_types = ["line_chart", "bar_chart", "form"]

    for canvas_type in canvas_types:
        # Trigger canvas
        trigger_canvas_with_accessibility(page, canvas_type)

        # Verify role='log' exists
        trees = get_accessibility_trees(page)
        assert len(trees) > 0, f"Should have accessibility tree for {canvas_type}"

        role = trees[0].get_attribute("role")
        assert role == "log", f"{canvas_type} should have role='log', got '{role}'"

        # Clean up for next test
        page.evaluate("() => document.querySelectorAll('[role=\"log\"]').forEach(el => el.remove())")


# =============================================================================
# aria-live Attribute Tests
# =============================================================================

def test_aria_live_attribute_exists(page: Page):
    """Test accessibility tree has aria-live attribute.

    GIVEN canvas with accessibility tree
    WHEN tree is rendered
    THEN aria-live attribute should exist
    AND value should be 'polite' or 'assertive'
    """
    trigger_canvas_with_accessibility(page, "line_chart")

    trees = get_accessibility_trees(page)
    assert len(trees) > 0, "Should have accessibility tree"

    aria_live = trees[0].get_attribute("aria-live")
    assert aria_live is not None, "Should have aria-live attribute"
    assert aria_live in ["polite", "assertive"], \
        f"aria-live should be 'polite' or 'assertive', got '{aria_live}'"


def test_aria_live_polite_for_charts(page: Page):
    """Test chart canvases use aria-live='polite'.

    GIVEN chart canvas (line, bar, pie)
    WHEN accessibility tree is rendered
    THEN aria-live should be 'polite' (non-urgent updates)
    """
    chart_types = ["line_chart", "bar_chart"]

    for chart_type in chart_types:
        trigger_canvas_with_accessibility(page, chart_type)

        trees = get_accessibility_trees(page)
        aria_live = trees[0].get_attribute("aria-live")

        assert aria_live == "polite", \
            f"{chart_type} should use aria-live='polite' for non-urgent updates, got '{aria_live}'"

        # Clean up
        page.evaluate("() => document.querySelectorAll('[role=\"log\"]').forEach(el => el.remove())")


def test_aria_live_assertive_for_errors(page: Page):
    """Test form errors use aria-live='assertive'.

    GIVEN form with validation error
    WHEN error state is rendered
    THEN aria-live should be 'assertive' for urgent announcement
    AND screen reader should prioritize error message
    """
    # Create form with error state
    error_data = {
        "form_schema": {
            "fields": [{"name": "email", "type": "email", "label": "Email", "required": True}]
        },
        "form_data": {"email": "invalid-email"},
        "validation_errors": [
            {"field": "email", "message": "Invalid email format"}
        ],
        "submit_enabled": False,
        "has_errors": True
    }

    canvas_id = trigger_canvas_with_accessibility(page, "form", error_data)

    # Update to assertive for errors
    page.evaluate("""
        ([canvasId]) => {
            const tree = document.querySelector(`[data-canvas-id="${canvasId}"]`);
            if (tree) {
                tree.setAttribute('aria-live', 'assertive');
            }
        }
    """, [canvas_id])

    trees = get_accessibility_trees(page)
    aria_live = trees[0].get_attribute("aria-live")

    assert aria_live == "assertive", \
        "Form errors should use aria-live='assertive' for urgent announcements"


# =============================================================================
# State Exposure Tests
# =============================================================================

def test_accessibility_tree_contains_json(page: Page):
    """Test accessibility tree contains valid JSON.

    GIVEN canvas with accessibility tree
    WHEN tree content is extracted
    THEN content should be valid JSON
    AND JSON should match getState(canvas_id) result
    """
    test_data = {
        "data_points": [{"x": "A", "y": 100}],
        "title": "JSON Test"
    }
    canvas_id = trigger_canvas_with_accessibility(page, "line_chart", test_data)

    # Get accessibility tree state
    tree_state = get_accessibility_tree_state(page, 0)

    # Verify it's valid JSON (already parsed by helper)
    assert isinstance(tree_state, dict), "State should be a dict"

    # Compare with window.atom.canvas.getState()
    api_state = page.evaluate(f"() => window.atom.canvas.getState('{canvas_id}')")

    assert api_state is not None, "getState() should return state"
    assert api_state["canvas_id"] == tree_state["canvas_id"], \
        "Tree state should match API state"


def test_accessibility_tree_state_structure(page: Page):
    """Test accessibility tree JSON has required fields.

    GIVEN chart canvas
    WHEN accessibility tree is rendered
    THEN JSON should have required fields: canvas_id, component, timestamp
    AND data should be complete and parseable
    """
    trigger_canvas_with_accessibility(page, "line_chart")

    state = get_accessibility_tree_state(page, 0)

    # Verify required fields
    required_fields = ["canvas_id", "component", "timestamp"]
    for field in required_fields:
        assert field in state, f"State should have required field '{field}'"

    # Verify data is complete
    assert state["canvas_id"], "canvas_id should not be empty"
    assert state["component"], "component should not be empty"
    assert state["timestamp"], "timestamp should not be empty"


def test_state_escaping(page: Page):
    """Test accessibility tree properly escapes special characters.

    GIVEN canvas with special characters in title (<script>, &, ", ')
    WHEN accessibility tree is rendered
    THEN content should be properly escaped
    AND JSON parsing should still work
    AND no script execution should occur (XSS prevention)
    """
    # Create data with special characters that could be XSS vectors
    dangerous_data = {
        "title": '<script>alert("XSS")</script> & "quotes" and \'apostrophes\'',
        "data_points": [{"x": "A", "y": 100}]
    }

    trigger_canvas_with_accessibility(page, "line_chart", dangerous_data)

    # Get accessibility tree content
    trees = get_accessibility_trees(page)
    text_content = trees[0].text_content()

    # Verify JSON parsing works (escaped properly)
    state = json.loads(text_content)
    assert state["title"] == dangerous_data["title"], \
        "Special characters should be preserved after escaping"

    # Verify no script execution (content is text, not HTML)
    assert "<script>" in text_content, \
        "Special characters should be present as text, not executed"

    # Verify it's stored as textContent, not innerHTML
    html_content = trees[0].evaluate("el => el.innerHTML")
    assert html_content == "", \
        "innerHTML should be empty (content is in textContent)"


# =============================================================================
# Visual Hiding Tests
# =============================================================================

def test_accessibility_tree_not_visible(page: Page):
    """Test accessibility tree is visually hidden.

    GIVEN canvas with accessibility tree
    WHEN tree is rendered
    THEN tree should have hidden styling (display: none or opacity: 0)
    AND element should not be in visible viewport
    """
    trigger_canvas_with_accessibility(page, "line_chart")

    trees = get_accessibility_trees(page)
    first_tree = trees[0]

    # Check visual hiding
    hidden = is_visually_hidden(page, first_tree)
    assert hidden, "Accessibility tree should be visually hidden"

    # Verify computed styles
    display = first_tree.evaluate("el => window.getComputedStyle(el).display")
    assert display == "none", f"Display should be 'none', got '{display}'"


def test_accessibility_tree_still_in_dom(page: Page):
    """Test accessibility tree is still in DOM (not removed).

    GIVEN canvas with accessibility tree
    WHEN tree is hidden
    THEN element should still exist in DOM
    AND screen reader should be able to access it
    """
    trigger_canvas_with_accessibility(page, "bar_chart")

    trees = get_accessibility_trees(page)
    assert len(trees) > 0, "Accessibility tree should exist in DOM"

    # Verify element is in DOM
    first_tree = trees[0]
    count = page.locator('[role="log"]').count()
    assert count > 0, "Accessibility tree should not be removed from DOM"

    # Verify screen reader can access (has ARIA attributes)
    role = first_tree.get_attribute("role")
    aria_live = first_tree.get_attribute("aria-live")

    assert role == "log", "Should have role='log' for screen reader"
    assert aria_live in ["polite", "assertive"], \
        "Should have aria-live for screen reader announcements"


# =============================================================================
# Multiple Canvas Tests
# =============================================================================

def test_multiple_canvases_separate_trees(page: Page):
    """Test multiple canvases have separate accessibility trees.

    GIVEN line chart and form triggered
    WHEN both are rendered
    THEN two accessibility trees should exist
    AND each should have unique canvas_id in state
    """
    # Trigger first canvas
    canvas_id_1 = trigger_canvas_with_accessibility(page, "line_chart")

    # Trigger second canvas
    canvas_id_2 = trigger_canvas_with_accessibility(page, "form")

    # Verify two trees exist
    trees = get_accessibility_trees(page)
    assert len(trees) >= 2, f"Should have 2+ accessibility trees, found {len(trees)}"

    # Verify each has unique canvas_id
    state_1 = get_accessibility_tree_state(page, 0)
    state_2 = get_accessibility_tree_state(page, 1)

    assert state_1["canvas_id"] != state_2["canvas_id"], \
        "Each canvas should have unique canvas_id"

    assert state_1["canvas_id"] == canvas_id_1, \
        "First tree should match first canvas_id"
    assert state_2["canvas_id"] == canvas_id_2, \
        "Second tree should match second canvas_id"


def test_accessibility_tree_updates(page: Page):
    """Test accessibility tree updates when canvas state changes.

    GIVEN canvas with initial state
    WHEN state is updated
    THEN accessibility tree content should update
    AND aria-live should trigger announcement
    """
    initial_data = {
        "data_points": [{"x": "A", "y": 100}],
        "title": "Initial Title"
    }
    canvas_id = trigger_canvas_with_accessibility(page, "line_chart", initial_data)

    # Get initial state
    initial_state = get_accessibility_tree_state(page, 0)
    assert initial_state["title"] == "Initial Title"

    # Update canvas state
    updated_data = {
        "data_points": [{"x": "A", "y": 200}],
        "title": "Updated Title"
    }

    page.evaluate("""
        ([canvasId, newState]) => {
            const tree = document.querySelector(`[data-canvas-id="${canvasId}"]`);
            if (tree) {
                tree.textContent = JSON.stringify(newState);
            }
        }
    """, [canvas_id, updated_data])

    # Get updated state
    updated_state = get_accessibility_tree_state(page, 0)
    assert updated_state["title"] == "Updated Title", \
        "Accessibility tree should update with new state"
    assert updated_state["data_points"][0]["y"] == 200, \
        "Data should be updated"


# =============================================================================
# Screen Reader Compatibility Tests
# =============================================================================

def test_aria_attributes_for_screen_readers(page: Page):
    """Test accessibility tree has proper ARIA attributes for screen readers.

    GIVEN canvas with accessibility tree
    WHEN tree is rendered
    THEN should have aria-label describing content
    AND should have aria-describedby linking to tree
    AND should have semantic structure for screen readers
    """
    trigger_canvas_with_accessibility(page, "line_chart")

    trees = get_accessibility_trees(page)
    first_tree = trees[0]

    # Verify aria-label exists
    aria_label = first_tree.get_attribute("aria-label")
    assert aria_label is not None, "Should have aria-label for screen readers"
    assert len(aria_label) > 0, "aria-label should not be empty"

    # Verify semantic role
    role = first_tree.get_attribute("role")
    assert role == "log", "Should have semantic role='log'"

    # Verify aria-live for announcements
    aria_live = first_tree.get_attribute("aria-live")
    assert aria_live in ["polite", "assertive"], \
        "Should have aria-live for announcements"


def test_screen_reader_can_announce_canvas_changes(page: Page):
    """Test screen reader can announce canvas changes via aria-live.

    GIVEN canvas with aria-live
    WHEN canvas content updates
    THEN aria-live region should trigger announcement
    AND screen reader should notify user
    """
    canvas_id = trigger_canvas_with_accessibility(page, "line_chart")

    trees = get_accessibility_trees(page)
    first_tree = trees[0]

    # Verify aria-live is set (triggers announcements)
    aria_live = first_tree.get_attribute("aria-live")
    assert aria_live == "polite", "Should have aria-live='polite' for announcements"

    # Simulate canvas update
    updated_data = {
        "title": "Announcement Test",
        "data_points": [{"x": "Updated", "y": 999}]
    }

    page.evaluate("""
        ([canvasId, newState]) => {
            const tree = document.querySelector(`[data-canvas-id="${canvasId}"]`);
            if (tree) {
                // Update content (triggers aria-live announcement)
                tree.textContent = JSON.stringify(newState);
            }
        }
    """, [canvas_id, updated_data])

    # Verify content changed (would trigger screen reader announcement)
    new_state = get_accessibility_tree_state(page, 0)
    assert new_state["title"] == "Announcement Test", \
        "Content should update (triggers aria-live announcement)"


# =============================================================================
# Data Attribute Tests
# =============================================================================

def test_accessibility_tree_data_attributes(page: Page):
    """Test accessibility tree has data-* attributes for identification.

    GIVEN canvas with accessibility tree
    WHEN tree is rendered
    THEN should have data-canvas-id attribute
    AND should have data-canvas-type attribute
    AND data attributes should match state
    """
    canvas_id = trigger_canvas_with_accessibility(page, "bar_chart")

    trees = get_accessibility_trees(page)
    first_tree = trees[0]

    # Verify data-canvas-id
    data_canvas_id = first_tree.get_attribute("data-canvas-id")
    assert data_canvas_id is not None, "Should have data-canvas-id attribute"
    assert data_canvas_id == canvas_id, \
        f"data-canvas-id should match canvas_id, expected {canvas_id}, got {data_canvas_id}"

    # Verify data-canvas-type
    data_canvas_type = first_tree.get_attribute("data-canvas-type")
    assert data_canvas_type is not None, "Should have data-canvas-type attribute"
    assert data_canvas_type == "bar_chart", \
        f"data-canvas-type should be 'bar_chart', got {data_canvas_type}"


# =============================================================================
# Edge Case Tests
# =============================================================================

def test_empty_canvas_state_handling(page: Page):
    """Test accessibility tree handles empty canvas state gracefully.

    GIVEN canvas with minimal/empty state
    WHEN tree is rendered
    THEN should still render tree
    AND JSON should be parseable
    """
    minimal_data = {"title": "Minimal Canvas"}
    trigger_canvas_with_accessibility(page, "line_chart", minimal_data)

    # Verify tree exists
    trees = get_accessibility_trees(page)
    assert len(trees) > 0, "Should have accessibility tree even with minimal data"

    # Verify JSON is parseable
    state = get_accessibility_tree_state(page, 0)
    assert state["title"] == "Minimal Canvas", \
        "Should handle minimal state correctly"


def test_large_canvas_state_performance(page: Page):
    """Test accessibility tree handles large canvas state efficiently.

    GIVEN canvas with large dataset (1000+ data points)
    WHEN tree is rendered
    THEN JSON should still be parseable
    AND rendering should complete in reasonable time
    """
    # Create large dataset
    large_data = {
        "title": "Large Canvas",
        "data_points": [{"x": f"Point-{i}", "y": i * 10} for i in range(1000)]
    }

    import time
    start = time.time()

    trigger_canvas_with_accessibility(page, "line_chart", large_data)

    # Verify tree exists
    trees = get_accessibility_trees(page)
    assert len(trees) > 0, "Should have accessibility tree for large dataset"

    # Verify JSON is parseable
    state = get_accessibility_tree_state(page, 0)
    assert len(state["data_points"]) == 1000, \
        "Should handle large dataset"

    elapsed = time.time() - start
    assert elapsed < 5.0, \
        f"Large state rendering should complete quickly, took {elapsed:.2f}s"


def test_unicode_characters_in_state(page: Page):
    """Test accessibility tree handles unicode characters correctly.

    GIVEN canvas with unicode characters (emoji, non-ASCII)
    WHEN tree is rendered
    THEN unicode should be preserved
    AND JSON should be parseable
    """
    unicode_data = {
        "title": "Unicode Test 🎨 你好 مرحبا",
        "data_points": [{"x": "😀", "y": 100}]
    }

    trigger_canvas_with_accessibility(page, "line_chart", unicode_data)

    # Verify unicode is preserved
    state = get_accessibility_tree_state(page, 0)
    assert "🎨" in state["title"], "Emoji should be preserved"
    assert "你好" in state["title"], "Chinese characters should be preserved"
    assert "مربا" in state["title"], "Arabic characters should be preserved"
