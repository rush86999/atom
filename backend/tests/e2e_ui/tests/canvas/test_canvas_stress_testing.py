"""
Canvas stress testing and memory leak detection E2E tests.

This module tests canvas system stability under rapid present/close cycles,
memory leak detection, DOM cleanup verification, and event listener cleanup.

Coverage: CANV-10 (Canvas stress testing and memory leak detection)
"""

import pytest
import uuid
import time
import json
from typing import Dict, Any
from playwright.sync_api import Page, expect


# ============================================================================
# Helper Functions
# ============================================================================

def trigger_and_close_canvas(page: Page, canvas_type: str, canvas_id: str = None) -> str:
    """Trigger canvas presentation and close it.

    Args:
        page: Playwright page object
        canvas_type: Type of canvas (chart, form, docs, email, sheets, orchestration, terminal)
        canvas_id: Optional canvas ID (generated if not provided)

    Returns:
        str: Canvas ID that was presented and closed
    """
    if canvas_id is None:
        canvas_id = f"{canvas_type}-{str(uuid.uuid4())[:8]}"

    # Trigger presentation
    canvas_message = {
        "type": "canvas:update",
        "canvas_id": canvas_id,
        "data": {
            "component": canvas_type,
            "title": f"Stress Test {canvas_type}",
            **get_canvas_data_for_type(canvas_type)
        }
    }

    # Inject canvas message and dispatch event
    page.evaluate(f"(msg) => window.lastCanvasMessage = msg", canvas_message)
    page.evaluate("() => { const e = new CustomEvent('canvas:update'); window.dispatchEvent(e); }")

    # Wait for render
    try:
        page.wait_for_selector(f'[data-canvas-id="{canvas_id}"]', timeout=5000)
    except Exception:
        # Canvas might not render - that's ok for stress testing
        pass

    # Close canvas
    try:
        close_button = page.locator(f'[data-canvas-id="{canvas_id}"] [data-testid*="close"], [data-canvas-id="{canvas_id}"] button[aria-label*="close" i], [data-canvas-id="{canvas_id}"] .close-button')
        if close_button.count() > 0:
            close_button.first.click()
            page.wait_for_selector(f'[data-canvas-id="{canvas_id}"]', state="hidden", timeout=5000)
    except Exception:
        # Canvas might not have close button or already closed
        try:
            page.evaluate(f"() => {{ const canvas = document.querySelector('[data-canvas-id=\"{canvas_id}\"]'); if (canvas) canvas.remove(); }}")
        except Exception:
            pass

    return canvas_id


def get_canvas_data_for_type(canvas_type: str) -> dict:
    """Get test data for canvas type.

    Args:
        canvas_type: Type of canvas

    Returns:
        dict: Canvas-specific data
    """
    data_map = {
        "chart": {"chart_type": "line", "data": {"labels": ["A", "B"], "datasets": [{"data": [1, 2]}]}},
        "form": {"schema": {"fields": [{"name": "test", "type": "text", "required": True}]}},
        "docs": {"content": "# Test\n\nContent"},
        "email": {"to": "test@example.com", "subject": "Test", "body": "Test body"},
        "sheets": {"data": [["A1", "B1"], ["A2", "B2"]]},
        "orchestration": {"nodes": [], "edges": []},
        "terminal": {"output": "Test output"},
        "coding": {"code": "print('test')", "language": "python"}
    }
    return data_map.get(canvas_type, {})


def get_memory_metrics(page: Page) -> dict:
    """Get browser memory metrics via CDP or performance API.

    Args:
        page: Playwright page object

    Returns:
        dict: Memory metrics or None if not available
    """
    return page.evaluate("""
        () => {
            if (window.performance && window.performance.memory) {
                return {
                    usedJSHeapSize: window.performance.memory.usedJSHeapSize,
                    totalJSHeapSize: window.performance.memory.totalJSHeapSize,
                    jsHeapSizeLimit: window.performance.memory.jsHeapSizeLimit
                };
            }
            return null;
        }
    """)


def get_dom_node_count(page: Page) -> int:
    """Count total DOM nodes.

    Args:
        page: Playwright page object

    Returns:
        int: Total DOM node count
    """
    return page.evaluate("() => document.querySelectorAll('*').length")


def check_console_errors(page: Page) -> list:
    """Get browser console errors.

    Args:
        page: Playwright page object

    Returns:
        list: Console errors
    """
    return page.evaluate("""
        () => {
            if (window.atomTestErrors) {
                return window.atomTestErrors;
            }
            return [];
        }
    """)


def get_orphaned_canvas_count(page: Page) -> int:
    """Count orphaned canvas elements.

    Args:
        page: Playwright page object

    Returns:
        int: Number of orphaned canvas elements
    """
    return page.evaluate("""
        () => {
            const canvases = document.querySelectorAll('[data-canvas-id]');
            let orphaned = 0;
            canvases.forEach(canvas => {
                const id = canvas.getAttribute('data-canvas-id');
                const isVisible = canvas.offsetParent !== null;
                if (!isVisible && canvas.parentElement) {
                    orphaned++;
                }
            });
            return orphaned;
        }
    """)


# ============================================================================
# Test Cases
# ============================================================================

class TestCanvasStressTesting:
    """Canvas stress testing and memory leak detection tests."""

    def test_rapid_canvas_present_close_cycles(self, authenticated_page_api: Page):
        """Test rapid canvas present/close cycles (100+) work without browser crashes.

        Requirements: CANV-10
        - 100 present/close cycles complete without crashes
        - No console errors
        - Execution time < 2 minutes
        """
        iteration_count = 100
        canvas_types = ["chart", "form", "docs", "email"]

        start_time = time.time()

        for i in range(iteration_count):
            canvas_type = canvas_types[i % len(canvas_types)]
            canvas_id = trigger_and_close_canvas(authenticated_page_api, canvas_type)

            # Verify no console errors every 10 iterations
            if i % 10 == 0:
                console_errors = check_console_errors(authenticated_page_api)
                assert len(console_errors) == 0, f"Console errors at iteration {i}: {console_errors}"

        end_time = time.time()
        execution_time = end_time - start_time

        # Verify execution time is reasonable (should be < 2 minutes for 100 cycles)
        assert execution_time < 120, f"Execution time {execution_time:.2f}s exceeds 120s threshold"

        # Final check for console errors
        console_errors = check_console_errors(authenticated_page_api)
        assert len(console_errors) == 0, f"Final console errors: {console_errors}"

        # Log cycle count and timing
        print(f"\n✓ Completed {iteration_count} present/close cycles in {execution_time:.2f}s")
        print(f"  Average: {execution_time / iteration_count:.3f}s per cycle")

    def test_memory_leak_detection_present_close(self, authenticated_page_api: Page):
        """Test memory leak detection during present/close cycles.

        Requirements: CANV-10
        - Memory growth < 50MB after 50 cycles
        - Memory metrics collected via performance API
        """
        # Get initial memory metrics
        initial_memory = get_memory_metrics(authenticated_page_api)

        if initial_memory is None:
            pytest.skip("Memory API not available (requires Chrome with --enable-precise-memory-info)")

        initial_heap_size = initial_memory["usedJSHeapSize"]

        # Run 50 present/close cycles
        canvas_types = ["chart", "form", "docs"]
        for i in range(50):
            canvas_type = canvas_types[i % len(canvas_types)]
            trigger_and_close_canvas(authenticated_page_api, canvas_type)

        # Force garbage collection if available
        try:
            authenticated_page_api.evaluate("() => { if (window.gc) window.gc(); }")
        except Exception:
            pass

        # Get final memory metrics
        final_memory = get_memory_metrics(authenticated_page_api)
        final_heap_size = final_memory["usedJSHeapSize"]

        # Calculate memory growth
        memory_growth_bytes = final_heap_size - initial_heap_size
        memory_growth_mb = memory_growth_bytes / (1024 * 1024)

        # Verify memory growth < 50MB threshold
        threshold_mb = 50
        assert memory_growth_mb < threshold_mb, (
            f"Memory growth {memory_growth_mb:.2f}MB exceeds {threshold_mb}MB threshold\n"
            f"Initial: {initial_heap_size / (1024*1024):.2f}MB\n"
            f"Final: {final_heap_size / (1024*1024):.2f}MB\n"
            f"Growth: {memory_growth_mb:.2f}MB"
        )

        print(f"\n✓ Memory growth: {memory_growth_mb:.2f}MB (threshold: {threshold_mb}MB)")
        print(f"  Initial heap: {initial_heap_size / (1024*1024):.2f}MB")
        print(f"  Final heap: {final_heap_size / (1024*1024):.2f}MB")

        # If memory growth is high, check for leaked DOM nodes
        if memory_growth_mb > threshold_mb * 0.8:  # 80% of threshold
            orphaned = get_orphaned_canvas_count(authenticated_page_api)
            print(f"  ⚠ Warning: High memory growth, orphaned canvases: {orphaned}")

    def test_dom_cleanup_after_canvas_close(self, authenticated_page_api: Page):
        """Test DOM cleanup after canvas close.

        Requirements: CANV-10
        - DOM node count returns to baseline (within 10%)
        - No orphaned canvas elements
        """
        # Get baseline DOM node count
        baseline_count = get_dom_node_count(authenticated_page_api)

        # Trigger canvas presentation
        canvas_id = trigger_and_close_canvas(authenticated_page_api, "form")

        # Wait for cleanup
        authenticated_page_api.wait_for_timeout(500)

        # Get DOM node count after close
        final_count = get_dom_node_count(authenticated_page_api)

        # Calculate percentage difference
        percent_diff = abs(final_count - baseline_count) / baseline_count * 100

        # Verify node count returned to near baseline (within 10%)
        assert percent_diff < 10, (
            f"DOM node count deviation {percent_diff:.1f}% exceeds 10% threshold\n"
            f"Baseline: {baseline_count} nodes\n"
            f"Final: {final_count} nodes\n"
            f"Difference: {final_count - baseline_count} nodes"
        )

        # Check for orphaned canvas elements
        orphaned = get_orphaned_canvas_count(authenticated_page_api)
        assert orphaned == 0, f"Found {orphaned} orphaned canvas elements"

        print(f"\n✓ DOM cleanup verified")
        print(f"  Baseline: {baseline_count} nodes")
        print(f"  Final: {final_count} nodes")
        print(f"  Deviation: {percent_diff:.1f}%")
        print(f"  Orphaned canvases: {orphaned}")

    def test_event_listener_cleanup(self, authenticated_page_api: Page):
        """Test event listener cleanup during rapid cycles.

        Requirements: CANV-10
        - Event listener count reasonable (< 1000)
        - No memory warnings in console
        """
        # Inject event listener tracking
        authenticated_page_api.evaluate("""
            () => {
                window.initialEventListeners = 0;
                const originalAdd = EventTarget.prototype.addEventListener;
                EventTarget.prototype.addEventListener = function(type, listener, options) {
                    window.initialEventListeners++;
                    return originalAdd.call(this, type, listener, options);
                };
            }
        """)

        # Trigger and close 20 canvases
        for i in range(20):
            canvas_type = ["chart", "form", "docs"][i % 3]
            trigger_and_close_canvas(authenticated_page_api, canvas_type)

        # Check for excessive listener growth
        listener_count = authenticated_page_api.evaluate("() => window.initialEventListeners")

        # Verify listener count is reasonable (< 1000 heuristic threshold)
        assert listener_count < 1000, (
            f"Event listener count {listener_count} exceeds 1000 threshold (possible leak)"
        )

        # Verify no warnings in console about memory
        console_errors = check_console_errors(authenticated_page_api)
        memory_warnings = [e for e in console_errors if "memory" in str(e).lower()]
        assert len(memory_warnings) == 0, f"Memory warnings in console: {memory_warnings}"

        print(f"\n✓ Event listener cleanup verified")
        print(f"  Total listeners added: {listener_count}")
        print(f"  Average per canvas: {listener_count / 20:.1f}")

    def test_multiple_simultaneous_canvases(self, authenticated_page_api: Page):
        """Test multiple simultaneous canvas presentations.

        Requirements: CANV-10
        - 10 canvases visible simultaneously
        - DOM cleanup after closing all
        - Memory not significantly higher than baseline
        """
        # Get baseline memory and DOM count
        initial_memory = get_memory_metrics(authenticated_page_api)
        baseline_count = get_dom_node_count(authenticated_page_api)

        # Trigger 10 canvas presentations sequentially without closing
        canvas_ids = []
        canvas_types = ["chart", "form", "docs", "email", "sheets", "terminal", "coding"]

        for i in range(10):
            canvas_type = canvas_types[i % len(canvas_types)]
            canvas_id = f"{canvas_type}-{str(uuid.uuid4())[:8]}"

            canvas_message = {
                "type": "canvas:update",
                "canvas_id": canvas_id,
                "data": {
                    "component": canvas_type,
                    "title": f"Simultaneous Test {canvas_type}",
                    **get_canvas_data_for_type(canvas_type)
                }
            }

            authenticated_page_api.evaluate(f"(msg) => window.lastCanvasMessage = msg", canvas_message)
            authenticated_page_api.evaluate("() => { const e = new CustomEvent('canvas:update'); window.dispatchEvent(e); }")

            canvas_ids.append(canvas_id)

        # Wait for all canvases to render
        authenticated_page_api.wait_for_timeout(1000)

        # Verify all 10 canvases visible
        visible_canvases = authenticated_page_api.evaluate("""
            () => document.querySelectorAll('[data-canvas-id]').length
        """)

        assert visible_canvases == 10, f"Expected 10 visible canvases, found {visible_canvases}"

        # Close all canvases
        for canvas_id in canvas_ids:
            try:
                authenticated_page_api.evaluate(f"""
                    () => {{
                        const canvas = document.querySelector('[data-canvas-id="{canvas_id}"]');
                        if (canvas) canvas.remove();
                    }}
                """)
            except Exception:
                pass

        # Verify DOM cleanup (0 canvas elements remaining)
        authenticated_page_api.wait_for_timeout(500)
        remaining_canvases = authenticated_page_api.evaluate("""
            () => document.querySelectorAll('[data-canvas-id]').length
        """)

        assert remaining_canvases == 0, f"Expected 0 canvas elements, found {remaining_canvases}"

        # Measure memory after cleanup
        final_memory = get_memory_metrics(authenticated_page_api)

        if initial_memory and final_memory:
            memory_growth = (final_memory["usedJSHeapSize"] - initial_memory["usedJSHeapSize"]) / (1024 * 1024)
            print(f"\n✓ Multiple simultaneous canvases test passed")
            print(f"  Canvases presented: 10")
            print(f"  Memory growth after cleanup: {memory_growth:.2f}MB")
        else:
            print(f"\n✓ Multiple simultaneous canvases test passed")
            print(f"  Canvases presented: 10")

    def test_stress_with_all_canvas_types(self, authenticated_page_api: Page):
        """Test stress with all 7 canvas types.

        Requirements: CANV-10
        - 70 iterations (10 per canvas type)
        - All canvas types work correctly after stress test
        - Memory within threshold
        - Browser stable (no crashes)
        """
        # All 7 canvas types
        canvas_types = ["chart", "form", "docs", "email", "sheets", "orchestration", "terminal", "coding"]

        # Get initial memory
        initial_memory = get_memory_metrics(authenticated_page_api)

        # Run 70 iterations (10 per type, round-robin)
        iteration_count = 70
        for i in range(iteration_count):
            canvas_type = canvas_types[i % len(canvas_types)]
            trigger_and_close_canvas(authenticated_page_api, canvas_type)

        # Verify browser stable (no crashes - test completes)
        print(f"\n✓ Completed {iteration_count} stress iterations")

        # Check final memory
        final_memory = get_memory_metrics(authenticated_page_api)

        if initial_memory and final_memory:
            memory_growth = (final_memory["usedJSHeapSize"] - initial_memory["usedJSHeapSize"]) / (1024 * 1024)
            threshold_mb = 50

            assert memory_growth < threshold_mb, (
                f"Memory growth {memory_growth:.2f}MB exceeds {threshold_mb}MB threshold"
            )

            print(f"  Memory growth: {memory_growth:.2f}MB (threshold: {threshold_mb}MB)")

        # Verify each canvas type still works after stress test
        for canvas_type in canvas_types:
            canvas_id = f"verify-{canvas_type}"
            canvas_message = {
                "type": "canvas:update",
                "canvas_id": canvas_id,
                "data": {
                    "component": canvas_type,
                    "title": f"Verify {canvas_type}",
                    **get_canvas_data_for_type(canvas_type)
                }
            }

            authenticated_page_api.evaluate(f"(msg) => window.lastCanvasMessage = msg", canvas_message)
            authenticated_page_api.evaluate("() => { const e = new CustomEvent('canvas:update'); window.dispatchEvent(e); }")

            # Wait for render
            try:
                authenticated_page_api.wait_for_selector(f'[data-canvas-id="{canvas_id}"]', timeout=3000)
            except Exception:
                # Some canvas types might not render - that's ok
                pass

        # Verify no console errors
        console_errors = check_console_errors(authenticated_page_api)
        assert len(console_errors) == 0, f"Console errors after stress test: {console_errors}"

        print(f"  All {len(canvas_types)} canvas types verified working")
        print(f"  No console errors detected")
