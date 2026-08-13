"""
Canvas stress testing and stability E2E tests.

Runs against the REAL rendering path (no phantom state injection): canvases
are created as real `Canvas` + `CanvasAudit` rows in the e2e database, and
each cycle navigates to the real `/canvas/{id}` route and closes via the real
`close-canvas-button` testid.

Coverage: CANV-10 (Canvas stress testing and memory leak detection)
"""

import time
import uuid
from typing import Tuple

import pytest
from playwright.sync_api import Page
from sqlalchemy.orm import Session

# Add backend to path for imports
import os
import sys
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.models import User
from tests.e2e_ui.tests.canvas_helpers import (
    CANVAS_CLOSE_BUTTON, create_canvas, create_chart_canvas, create_form_canvas,
    create_markdown_canvas, open_canvas,
)


# ============================================================================
# Helper Functions
# ============================================================================

def get_memory_metrics(page: Page) -> dict:
    """Get browser memory metrics via the performance API."""
    return page.evaluate(
        """() => {
            if (window.performance && window.performance.memory) {
                return {
                    usedJSHeapSize: window.performance.memory.usedJSHeapSize,
                    totalJSHeapSize: window.performance.memory.totalJSHeapSize,
                };
            }
            return null;
        }"""
    )


def get_dom_node_count(page: Page) -> int:
    """Count total DOM nodes."""
    return page.evaluate("() => document.querySelectorAll('*').length")


def open_and_close_canvas(page: Page, canvas_id: str, component: str) -> None:
    """Open a canvas on the real route and close it via the close button."""
    open_canvas(page, canvas_id, component, timeout=20000)
    page.locator(CANVAS_CLOSE_BUTTON).click()
    page.wait_for_selector('[data-testid="canvas-container"]', state="hidden", timeout=10000)
    assert page.locator('[data-testid="canvas-container"]').count() == 0, (
        "Canvas container should be gone after close"
    )


def attach_console_error_tracker(page: Page) -> list:
    """Collect console errors into a Python-side list, filtering the documented
    benign platform noise every authenticated page produces:

    - HTTP 401: the next-auth session probe (/api/auth/session) — the E2E
      context carries the app JWT (auth_token), not a next-auth session, so
      this fires on every page of the app (dashboard included).
    - HTTP 404: the MiniAppHarness logic probe (/api/canvas/{id}/logic) —
      404 means "no logic yet" by design.
    - next-auth CLIENT_FETCH_ERROR: same root cause as the 401.
    """
    errors: list = []

    def _is_benign(text: str) -> bool:
        lowered = text.lower()
        return any(pat in lowered for pat in ("status of 401", "status of 404", "next-auth"))

    def _on_console(msg) -> None:
        if msg.type == "error" and not _is_benign(msg.text):
            errors.append(msg.text)

    page.on("console", _on_console)
    return errors


def create_all_type_canvases(db: Session, user: User) -> dict:
    """Create one canvas per supported type; returns {canvas_id: component}."""
    canvases = {}
    chart_id = create_chart_canvas(db, user, "line_chart",
                                   [{"timestamp": "2024-03-01 12:00", "value": 5}], "Stress Line Chart")
    canvases[chart_id] = "line_chart"

    form_id = create_form_canvas(db, user, [{"name": "test", "type": "text", "label": "Test"}], "Stress Form")
    canvases[form_id] = "form"

    docs_id = create_markdown_canvas(db, user, "Stress Docs", "# Test\n\nContent")
    canvases[docs_id] = "markdown"

    code_id = f"e2e-code-{uuid.uuid4()}"
    create_canvas(db, user, code_id, "code", "Stress Code", "print('test')")
    canvases[code_id] = "code"

    email_id = f"e2e-email-{uuid.uuid4()}"
    create_canvas(db, user, email_id, "email", "Stress Email",
                  {"to": "t@example.com", "subject": "S", "body": "body"})
    canvases[email_id] = "email"

    sheet_id = f"e2e-sheet-{uuid.uuid4()}"
    create_canvas(db, user, sheet_id, "sheet", "Stress Sheet", [["A1", "B1"], ["A2", "B2"]])
    canvases[sheet_id] = "sheet"

    terminal_id = f"e2e-terminal-{uuid.uuid4()}"
    create_canvas(db, user, terminal_id, "terminal", "Stress Terminal", {"output": "out"})
    canvases[terminal_id] = "terminal"

    return canvases


# ============================================================================
# Test Cases
# ============================================================================

def test_rapid_canvas_present_close_cycles(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test rapid present/close cycles complete without crashes or console errors.

    Requirements: CANV-10
    - 20 cycles (chart/form/sheet — no Monaco/CDN dependency) complete cleanly
    - No console errors
    - Execution time < 120s
    """
    user, _ = authenticated_user
    errors = attach_console_error_tracker(authenticated_page)

    canvas_ids = []
    for i in range(20):
        if i % 3 == 0:
            cid = create_chart_canvas(db_session, user, "bar_chart",
                                      [{"name": f"C{i}", "value": i}], f"Cycle {i}")
            component = "bar_chart"
        elif i % 3 == 1:
            cid = create_form_canvas(db_session, user,
                                     [{"name": "f", "type": "text", "label": "F"}], f"Cycle {i}")
            component = "form"
        else:
            cid = f"e2e-sheet-{uuid.uuid4()}"
            create_canvas(db_session, user, cid, "sheet", f"Cycle {i}", [[f"v{i}"]])
            component = "sheet"
        canvas_ids.append(cid)

    start_time = time.time()
    for cid, component in zip(canvas_ids, ["bar_chart", "form", "sheet"] * 7):
        open_and_close_canvas(authenticated_page, cid, component)

    execution_time = time.time() - start_time
    assert execution_time < 120, f"Execution time {execution_time:.2f}s exceeds 120s threshold"
    assert len(errors) == 0, f"Console errors during cycles: {errors}"


def test_memory_leak_detection_present_close(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test memory growth stays under 50MB across present/close cycles."""
    initial_memory = get_memory_metrics(authenticated_page)
    if initial_memory is None:
        pytest.skip("Memory API not available (requires Chrome with --enable-precise-memory-info)")
    initial_heap_size = initial_memory["usedJSHeapSize"]

    user, _ = authenticated_user
    for i in range(10):
        if i % 2 == 0:
            cid = create_chart_canvas(db_session, user, "pie_chart",
                                      [{"name": f"S{i}", "value": i}], f"Mem {i}")
            component = "pie_chart"
        else:
            cid = create_form_canvas(db_session, user,
                                     [{"name": "f", "type": "text", "label": "F"}], f"Mem {i}")
            component = "form"
        open_and_close_canvas(authenticated_page, cid, component)

    final_memory = get_memory_metrics(authenticated_page)
    assert final_memory is not None, "Final memory metrics should be available"
    memory_growth_mb = (final_memory["usedJSHeapSize"] - initial_heap_size) / (1024 * 1024)

    threshold_mb = 50
    assert memory_growth_mb < threshold_mb, (
        f"Memory growth {memory_growth_mb:.2f}MB exceeds {threshold_mb}MB threshold\n"
        f"Initial: {initial_heap_size / (1024 * 1024):.2f}MB\n"
        f"Final: {final_memory['usedJSHeapSize'] / (1024 * 1024):.2f}MB"
    )


def test_dom_cleanup_after_canvas_close(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test DOM cleanup after canvas close.

    Requirements: CANV-10
    - DOM node count returns to within 10% of baseline after close
    - No orphaned canvas containers

    Baseline is measured on the SAME route structure (canvas detail page after
    a close) so the comparison isolates the canvas mount/unmount delta instead
    of the dashboard↔canvas page-structure difference.
    """
    user, _ = authenticated_user
    form_id = create_form_canvas(db_session, user,
                                 [{"name": "f", "type": "text", "label": "F"}], "DOM Cleanup A")
    open_and_close_canvas(authenticated_page, form_id, "form")

    # Baseline: canvas detail page with the container unmounted.
    baseline_count = get_dom_node_count(authenticated_page)

    chart_id = create_chart_canvas(db_session, user, "line_chart",
                                   [{"timestamp": "2024-03-01 12:00", "value": 1}], "DOM Cleanup B")
    open_canvas(authenticated_page, chart_id, "line_chart")
    with_canvas_count = get_dom_node_count(authenticated_page)
    assert with_canvas_count > baseline_count, "Canvas mount should add DOM nodes"

    authenticated_page.locator(CANVAS_CLOSE_BUTTON).click()
    authenticated_page.wait_for_selector('[data-testid="canvas-container"]', state="hidden", timeout=10000)

    final_count = get_dom_node_count(authenticated_page)
    percent_diff = abs(final_count - baseline_count) / baseline_count * 100

    assert percent_diff < 10, (
        f"DOM node count deviation {percent_diff:.1f}% exceeds 10% threshold\n"
        f"Baseline: {baseline_count} nodes, Final: {final_count} nodes"
    )
    assert authenticated_page.locator('[data-testid="canvas-container"]').count() == 0, (
        "No canvas containers should remain after close"
    )


def test_event_listener_cleanup(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that canvas mount/unmount cycles do not accumulate event listeners.

    Each cycle navigates (full page load), so the per-cycle listener DELTA is
    the meaningful metric: listeners added between snapshot points must stay
    bounded across cycles — an unbounded growth indicates listeners not being
    removed on unmount. The counter lives in sessionStorage so it survives
    same-tab navigations (window state is wiped on every page load).
    """
    user, _ = authenticated_user
    authenticated_page.add_init_script(
        """() => {
            window.__listenerAdds = Number(sessionStorage.getItem('__listenerAdds') || 0);
            const originalAdd = EventTarget.prototype.addEventListener;
            EventTarget.prototype.addEventListener = function(type, listener, options) {
                sessionStorage.setItem('__listenerAdds',
                    String(Number(sessionStorage.getItem('__listenerAdds') || 0) + 1));
                return originalAdd.call(this, type, listener, options);
            };
        }"""
    )
    authenticated_page.goto("http://localhost:3001")
    authenticated_page.wait_for_load_state("networkidle")

    def snapshot() -> int:
        return int(authenticated_page.evaluate(
            "() => Number(sessionStorage.getItem('__listenerAdds') || 0)"
        ))

    max_delta = 0
    for i in range(10):
        if i % 2 == 0:
            cid = create_chart_canvas(db_session, user, "line_chart",
                                      [{"timestamp": "2024-03-01 12:00", "value": i}], f"Listener {i}")
            component = "line_chart"
        else:
            cid = f"e2e-sheet-{uuid.uuid4()}"
            create_canvas(db_session, user, cid, "sheet", f"Listener {i}", [[f"v{i}"]])
            component = "sheet"

        before = snapshot()
        open_and_close_canvas(authenticated_page, cid, component)
        delta = snapshot() - before
        max_delta = max(max_delta, delta)

    # Per-cycle bound: a canvas mount/unmount must not add hundreds of
    # listeners; unbounded growth would trip this consistently.
    bound = 300
    assert max_delta < bound, (
        f"Largest per-cycle listener growth {max_delta} exceeds {bound} "
        f"(possible listener leak on canvas mount/unmount)"
    )


def test_multiple_simultaneous_canvases(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that several canvases are listed and each renders on its route.

    The /canvas/{id} route renders one canvas at a time (real route contract),
    so "simultaneous" is verified via the canvas index: all canvases created in
    the DB are listed together, and each renders individually.
    """
    user, _ = authenticated_user
    canvases = create_all_type_canvases(db_session, user)
    canvas_ids = list(canvases.keys())

    # All canvases appear in the real /canvas index list.
    authenticated_page.goto("http://localhost:3001/canvas")
    authenticated_page.wait_for_load_state("networkidle")
    for cid in canvas_ids:
        authenticated_page.locator(f'a[href="/canvas/{cid}"]').first.wait_for(state="visible", timeout=10000)

    # Each renders on its own route.
    for cid, component in canvases.items():
        open_canvas(authenticated_page, cid, component, timeout=30000)
        authenticated_page.locator(CANVAS_CLOSE_BUTTON).click()
        authenticated_page.wait_for_selector('[data-testid="canvas-container"]', state="hidden", timeout=10000)


def test_stress_with_all_canvas_types(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test all canvas types render and close cleanly, with no console errors."""
    user, _ = authenticated_user
    errors = attach_console_error_tracker(authenticated_page)
    canvases = create_all_type_canvases(db_session, user)

    for cid, component in canvases.items():
        open_and_close_canvas(authenticated_page, cid, component)

    # Each type still renders after the stress run (spot check line chart).
    spot_id = create_chart_canvas(db_session, user, "line_chart",
                                  [{"timestamp": "2024-03-01 12:00", "value": 1}], "Post-stress")
    open_canvas(authenticated_page, spot_id, "line_chart")
    assert authenticated_page.locator('.recharts-line').count() > 0, "Chart should render post-stress"

    assert len(errors) == 0, f"Console errors after stress test: {errors}"
