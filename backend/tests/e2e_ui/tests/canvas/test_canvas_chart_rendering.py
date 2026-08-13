"""
E2E Tests for Chart Canvas Rendering (CANV-01).

Tests verify all chart types (line, bar, pie) render correctly through the
REAL rendering path — no phantom state injection:

1. A chart canvas is created as `Canvas` + `CanvasAudit` rows in the e2e
   database via `canvas_helpers.create_chart_canvas()` (mirroring what
   `tools/canvas_tool.present_chart()` persists).
2. Tests navigate to `http://localhost:3001/canvas/{id}`, where
   `pages/canvas/[id].tsx` loads `/api/canvas/{id}` and `CanvasPanel` renders
   the Recharts component (LineChartCanvas/BarChartCanvas/PieChartCanvas).

Chart data shapes (from frontend-nextjs/components/canvas/*.tsx):
- LineChartCanvas: [{timestamp, value, label?}] — dots
- BarChartCanvas:  [{name, value}] — bars
- PieChartCanvas:  [{name, value}] — sectors with labels

Reference pattern: tests/test_canvas_charts.py (16/16 passing).
"""

import uuid
from typing import Dict, Any, Tuple

from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.models import CanvasAudit, User
from tests.e2e_ui.pages.page_objects import CanvasChartPage
from tests.e2e_ui.tests.canvas_helpers import create_chart_canvas, open_canvas


# =============================================================================
# Helper Functions
# =============================================================================

def create_line_chart_data(point_count: int = 5) -> list[dict]:
    """Create line chart data (timestamp/value points)."""
    unique_id = str(uuid.uuid4())[:8]
    return [
        {"timestamp": f"2024-02-{23 + i:02d} 12:00", "value": 10 + i * 5, "label": f"Pt-{unique_id}-{i}"}
        for i in range(point_count)
    ]


def create_bar_chart_data(point_count: int = 4) -> list[dict]:
    """Create bar chart data (category/value pairs)."""
    unique_id = str(uuid.uuid4())[:8]
    return [{"name": f"Cat-{unique_id}-{i}", "value": 20 + i * 10} for i in range(point_count)]


def create_pie_chart_data(point_count: int = 4) -> list[dict]:
    """Create pie chart data (segment/value pairs)."""
    unique_id = str(uuid.uuid4())[:8]
    return [{"name": f"Seg-{unique_id}-{i}", "value": 10 + i * 15} for i in range(point_count)]


def open_chart_canvas(page: Page, canvas_id: str, chart_type: str) -> CanvasChartPage:
    """Navigate to the real /canvas/{id} route and wait for the chart series."""
    open_canvas(page, canvas_id, f"{chart_type}_chart")
    page.wait_for_selector(
        ".recharts-wrapper, .recharts-line, .recharts-bar-rectangle, .recharts-pie-sector",
        timeout=10000,
    )
    return CanvasChartPage(page)


# =============================================================================
# Chart Rendering Tests
# =============================================================================

def test_line_chart_renders_correctly(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that line chart renders with correct data points.

    Verifies:
    - CanvasPanel container appears with line_chart type badge
    - Recharts line SVG series rendered with dots
    - CanvasAudit record created for the canvas
    """
    user, _ = authenticated_user
    data = create_line_chart_data(5)
    canvas_id = create_chart_canvas(db_session, user, "line_chart", data, "Monthly Sales")

    chart_page = open_chart_canvas(authenticated_page, canvas_id, "line")

    assert chart_page.is_loaded(), "Line chart should be loaded"
    assert chart_page.get_chart_type() == "line", "Chart type should be 'line'"
    assert chart_page.line_chart_svg.first.is_visible(), "Line series should be visible"
    assert chart_page.get_data_point_count() == 5, "All 5 data points should render"

    audit = db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == canvas_id).all()
    assert len(audit) >= 1, "CanvasAudit record should exist for the canvas"
    assert audit[0].canvas_type == "line_chart", "Audit row should carry the chart type"


def test_bar_chart_renders_correctly(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that bar chart renders with correct bar count.

    Verifies:
    - CanvasPanel container appears with bar_chart type badge
    - Bar rectangles match the input data length
    - CanvasAudit record created
    """
    user, _ = authenticated_user
    data = create_bar_chart_data(4)
    canvas_id = create_chart_canvas(db_session, user, "bar_chart", data, "Revenue by Category")

    chart_page = open_chart_canvas(authenticated_page, canvas_id, "bar")

    assert chart_page.is_loaded(), "Bar chart should be loaded"
    assert chart_page.get_chart_type() == "bar", "Chart type should be 'bar'"
    assert chart_page.get_data_point_count() == 4, "Expected 4 bars, got different count"
    assert chart_page.verify_bar_chart_data(data), "Bar values should match input data"

    audit = db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == canvas_id).all()
    assert len(audit) >= 1, "CanvasAudit record should exist for the canvas"


def test_pie_chart_renders_correctly(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that pie chart renders with correct slice count.

    Verifies:
    - CanvasPanel container appears with pie_chart type badge
    - Sector count matches the input data length
    - CanvasAudit record created
    """
    user, _ = authenticated_user
    data = create_pie_chart_data(4)
    canvas_id = create_chart_canvas(db_session, user, "pie_chart", data, "Market Share")

    chart_page = open_chart_canvas(authenticated_page, canvas_id, "pie")

    assert chart_page.is_loaded(), "Pie chart should be loaded"
    assert chart_page.get_chart_type() == "pie", "Chart type should be 'pie'"
    assert chart_page.get_data_point_count() == 4, "Expected 4 sectors, got different count"
    assert chart_page.verify_pie_chart_data(data), "Pie values should match input data"

    audit = db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == canvas_id).all()
    assert len(audit) >= 1, "CanvasAudit record should exist for the canvas"


def test_chart_title_and_labels_display(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that chart title and type badge display above the chart."""
    user, _ = authenticated_user
    title = "Sales Report"
    canvas_id = create_chart_canvas(db_session, user, "line_chart", create_line_chart_data(3), title)

    chart_page = open_chart_canvas(authenticated_page, canvas_id, "line")

    # Title in the canvas host header (h3) AND the chart header (h4).
    assert chart_page.get_title() == title, f"Chart title should be '{title}'"
    container_text = authenticated_page.locator('[data-testid="canvas-container"]').inner_text()
    assert title in container_text, "Title should appear in the canvas container"
    assert "line_chart" in container_text.lower(), "Type badge should show the chart type"


def test_multiple_charts_can_render(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that multiple chart canvases render independently.

    The /canvas/{id} route renders one canvas per page (real route contract),
    so "multiple charts" is verified by: render → close → next canvas renders
    with its own data.
    """
    from tests.e2e_ui.tests.canvas_helpers import CANVAS_CLOSE_BUTTON

    user, _ = authenticated_user
    first_id = create_chart_canvas(db_session, user, "line_chart", create_line_chart_data(3), "First Chart")
    second_id = create_chart_canvas(db_session, user, "bar_chart", create_bar_chart_data(3), "Second Chart")

    chart_page = open_chart_canvas(authenticated_page, first_id, "line")
    assert chart_page.get_chart_type() == "line", "First canvas should render a line chart"

    # Close the first canvas — the container must disappear.
    authenticated_page.locator(CANVAS_CLOSE_BUTTON).click()
    authenticated_page.wait_for_selector('[data-testid="canvas-container"]', state="hidden", timeout=5000)
    assert authenticated_page.locator('[data-testid="canvas-container"]').count() == 0

    # Second canvas renders its own bar data.
    chart_page = open_chart_canvas(authenticated_page, second_id, "bar")
    assert chart_page.get_chart_type() == "bar", "Second canvas should render a bar chart"


def test_chart_legend_displays_for_multi_dataset(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that the Recharts legend renders for chart canvases."""
    user, _ = authenticated_user
    canvas_id = create_chart_canvas(db_session, user, "line_chart", create_line_chart_data(4), "Product Comparison")

    chart_page = open_chart_canvas(authenticated_page, canvas_id, "line")

    assert chart_page.has_legend(), "Chart should display a legend"
    assert isinstance(chart_page.get_legend_items(), list), "Legend items should be a list"


def test_chart_responsive_container(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that chart uses the Recharts ResponsiveContainer wrapper."""
    user, _ = authenticated_user
    canvas_id = create_chart_canvas(db_session, user, "line_chart", create_line_chart_data(3), "Responsive Chart")

    chart_page = open_chart_canvas(authenticated_page, canvas_id, "line")

    assert chart_page.chart_container.is_visible(), "Chart should render inside a .recharts-wrapper"
    box_size = chart_page.chart_container.bounding_box()
    assert box_size is not None and box_size["width"] > 0, "Chart container should have positive width"
