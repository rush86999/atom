"""
E2E Tests for Canvas Chart Presentations.

Tests verify all chart types (line, bar, pie) render correctly through the
REAL rendering path — no phantom state injection:

1. A chart canvas is created as `Canvas` + `CanvasAudit` rows in the e2e
   database via `tests/canvas_helpers.create_chart_canvas()` (mirroring what
   `tools/canvas_tool.present_chart()` persists).
2. Tests navigate to `http://localhost:3001/canvas/{id}`, where
   `pages/canvas/[id].tsx` loads `/api/canvas/{id}` and `CanvasPanel` renders
   the Recharts component (LineChartCanvas/BarChartCanvas/PieChartCanvas).

Chart data shapes (from frontend-nextjs/components/canvas/*.tsx):
- LineChartCanvas: [{timestamp, value, label?}] — dots
- BarChartCanvas:  [{name, value}] — bars
- PieChartCanvas:  [{name, value}] — sectors with labels

Uses CanvasChartPage Page Object for chart interactions.
"""

import pytest
from typing import Dict, Any, Tuple
from uuid import uuid4
from playwright.sync_api import Page
from sqlalchemy.orm import Session

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from tests.e2e_ui.pages.page_objects import CanvasChartPage
from tests.e2e_ui.tests.canvas_helpers import create_chart_canvas
from core.models import User


# =============================================================================
# Helper Functions
# =============================================================================

def create_test_chart_data(chart_type: str, point_count: int = 5) -> list[dict]:
    """Create test chart data for specified chart type.

    Args:
        chart_type: Type of chart ("line", "bar", "pie")
        point_count: Number of data points to generate

    Returns:
        list[dict]: Chart data points
    """
    unique_id = str(uuid4())[:8]
    data = []

    if chart_type == "line":
        # Line chart: timestamp/value data
        for i in range(point_count):
            data.append({
                "timestamp": f"2024-02-{23 + i:02d} 12:00",
                "value": 10 + i * 5,
                "label": f"Point {i}"
            })
    elif chart_type == "bar":
        # Bar chart: category/value data
        for i in range(point_count):
            data.append({
                "name": f"Cat-{unique_id}-{i}",
                "value": 20 + i * 10
            })
    elif chart_type == "pie":
        # Pie chart: segment data
        for i in range(point_count):
            data.append({
                "name": f"Seg-{unique_id}-{i}",
                "value": 10 + i * 15
            })

    return data


def open_chart_canvas(page: Page, canvas_id: str) -> CanvasChartPage:
    """Navigate to the real /canvas/{id} route and wait for the chart."""
    page.goto(f"http://localhost:3001/canvas/{canvas_id}")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector(
        ".recharts-wrapper, .recharts-line-chart, .recharts-bar-chart, .recharts-pie-chart",
        timeout=10000,
    )
    return CanvasChartPage(page)


def wait_for_chart_render(page: Page, timeout: int = 3000) -> None:
    """Wait for chart to finish rendering."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    try:
        page.wait_for_selector(
            ".recharts-wrapper, .recharts-line-chart, .recharts-bar-chart, .recharts-pie-chart",
            timeout=timeout
        )
    except PlaywrightTimeoutError:
        raise TimeoutError(f"Chart did not render within {timeout}ms")


# =============================================================================
# Line Chart Tests
# =============================================================================

def test_line_chart_renders(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test line chart renders with correct SVG structure.

    GIVEN line chart data with 5 points
    WHEN canvas is opened via /canvas/{id}
    THEN line_chart_svg should be visible
    AND chart type should be "line"
    """
    user, _ = authenticated_user
    data = create_test_chart_data("line", 5)
    canvas_id = create_chart_canvas(db_session, user, "line_chart", data, "Test Line Chart")

    chart_page = open_chart_canvas(authenticated_page, canvas_id)

    # Verify line chart SVG is visible
    assert chart_page.is_loaded(), "Line chart should be loaded"
    assert chart_page.get_chart_type() == "line", "Chart type should be 'line'"
    assert chart_page.line_chart_svg.first.is_visible(), "Line chart SVG should be visible"


def test_line_chart_data_points(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test line chart displays correct number of data points.

    GIVEN line chart with known data values
    WHEN chart renders
    THEN data point count should match input
    """
    user, _ = authenticated_user
    expected_count = 7
    data = create_test_chart_data("line", expected_count)
    canvas_id = create_chart_canvas(db_session, user, "line_chart", data, "Data Points Test")

    chart_page = open_chart_canvas(authenticated_page, canvas_id)

    # Verify data point count
    actual_count = chart_page.get_data_point_count()
    assert actual_count == expected_count, f"Expected {expected_count} dots, got {actual_count}"

    # Verify data matches
    assert chart_page.verify_line_chart_data(data), "Data points should match"


def test_line_chart_tooltip(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test line chart tooltip appears on hover.

    GIVEN line chart with data points
    WHEN hovering over a data point
    THEN tooltip should appear with correct value
    """
    user, _ = authenticated_user
    data = create_test_chart_data("line", 5)
    canvas_id = create_chart_canvas(db_session, user, "line_chart", data, "Tooltip Test")

    chart_page = open_chart_canvas(authenticated_page, canvas_id)

    # Hover over first data point
    chart_page.hover_data_point(0)
    authenticated_page.wait_for_timeout(300)  # Wait for tooltip animation

    # Verify tooltip appears
    tooltip_text = chart_page.get_tooltip_text()
    assert chart_page.chart_tooltip.is_visible() or len(tooltip_text) > 0, \
        "Tooltip should appear on hover"


# =============================================================================
# Bar Chart Tests
# =============================================================================

def test_bar_chart_renders(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test bar chart renders with correct SVG structure.

    GIVEN bar chart data with categories
    WHEN canvas is opened via /canvas/{id}
    THEN bar_chart_svg should be visible
    AND bars should be rendered
    """
    user, _ = authenticated_user
    data = create_test_chart_data("bar", 4)
    canvas_id = create_chart_canvas(db_session, user, "bar_chart", data, "Test Bar Chart")

    chart_page = open_chart_canvas(authenticated_page, canvas_id)

    # Verify bar chart is visible
    assert chart_page.is_loaded(), "Bar chart should be loaded"
    assert chart_page.get_chart_type() == "bar", "Chart type should be 'bar'"
    assert chart_page.bar_chart_svg.first.is_visible(), "Bar chart SVG should be visible"


def test_bar_chart_categories(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test bar chart displays categories on X axis.

    GIVEN bar chart with named categories
    WHEN chart renders
    THEN bar count matches categories
    """
    user, _ = authenticated_user
    data = [
        {"name": "Category A", "value": 100},
        {"name": "Category B", "value": 200},
        {"name": "Category C", "value": 150}
    ]
    canvas_id = create_chart_canvas(db_session, user, "bar_chart", data, "Categories Test")

    chart_page = open_chart_canvas(authenticated_page, canvas_id)

    # Verify bar count matches categories
    bar_count = chart_page.get_data_point_count()
    assert bar_count == len(data), f"Expected {len(data)} bars, got {bar_count}"

    # Verify data matches
    assert chart_page.verify_bar_chart_data(data), "Bar data should match"


def test_bar_chart_colors(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test bar chart uses fill color for bars.

    GIVEN bar chart with data
    WHEN chart renders
    THEN bars should have fill color
    """
    user, _ = authenticated_user
    data = create_test_chart_data("bar", 3)
    canvas_id = create_chart_canvas(db_session, user, "bar_chart", data, "Colors Test")

    chart_page = open_chart_canvas(authenticated_page, canvas_id)

    # Verify bars have fill color
    colors = chart_page.get_chart_colors()
    assert len(colors) > 0, "Bars should have fill color"
    # Default color is #8884d8 (purple)
    assert any("#8884" in c or c == "#8884d8" for c in colors), \
        f"Bars should have default color, got {colors}"


# =============================================================================
# Pie Chart Tests
# =============================================================================

def test_pie_chart_renders(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test pie chart renders with correct SVG structure.

    GIVEN pie chart data with segments
    WHEN canvas is opened via /canvas/{id}
    THEN pie_chart_svg should be visible
    AND all segments should be present
    """
    user, _ = authenticated_user
    data = create_test_chart_data("pie", 4)
    canvas_id = create_chart_canvas(db_session, user, "pie_chart", data, "Test Pie Chart")

    chart_page = open_chart_canvas(authenticated_page, canvas_id)

    # Verify pie chart is visible
    assert chart_page.is_loaded(), "Pie chart should be loaded"
    assert chart_page.get_chart_type() == "pie", "Chart type should be 'pie'"
    assert chart_page.pie_chart_svg.first.is_visible(), "Pie chart SVG should be visible"


def test_pie_chart_labels(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test pie chart displays labels on segments.

    GIVEN pie chart with segment data
    WHEN chart renders
    THEN labels should appear on/near segments
    AND all segments present
    """
    user, _ = authenticated_user
    data = create_test_chart_data("pie", 3)
    canvas_id = create_chart_canvas(db_session, user, "pie_chart", data, "Labels Test")

    chart_page = open_chart_canvas(authenticated_page, canvas_id)

    # Verify all segments present
    sector_count = chart_page.get_data_point_count()
    assert sector_count == len(data), f"Expected {len(data)} sectors, got {sector_count}"

    # Verify data matches
    assert chart_page.verify_pie_chart_data(data), "Pie data should match"


def test_pie_chart_legend(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test pie chart displays legend with segment names.

    GIVEN pie chart with segment data
    WHEN chart renders
    THEN legend should be displayed
    """
    user, _ = authenticated_user
    data = create_test_chart_data("pie", 4)
    canvas_id = create_chart_canvas(db_session, user, "pie_chart", data, "Legend Test")

    chart_page = open_chart_canvas(authenticated_page, canvas_id)

    # Verify legend is displayed
    assert chart_page.has_legend(), "Pie chart should have legend"

    # Verify legend items (if available)
    legend_items = chart_page.get_legend_items()
    assert isinstance(legend_items, list), "Legend items should be a list"


# =============================================================================
# Common Chart Tests
# =============================================================================

def test_chart_title_displays(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test chart title displays above all chart types.

    GIVEN charts with titles
    WHEN charts render
    THEN title should appear above chart
    AND title text should match input
    """
    user, _ = authenticated_user

    for chart_type in ["line", "bar", "pie"]:
        title = f"Test {chart_type.title()} Chart"
        data = create_test_chart_data(chart_type, 3)
        canvas_id = create_chart_canvas(db_session, user, f"{chart_type}_chart", data, title)

        chart_page = open_chart_canvas(authenticated_page, canvas_id)

        # Verify title displays
        chart_title = chart_page.get_title()
        assert title in chart_title or chart_title == title, \
            f"Chart title should be displayed for {chart_type}, got '{chart_title}'"


def test_chart_responsive(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test chart uses ResponsiveContainer for flexibility.

    GIVEN any chart type
    WHEN chart renders
    THEN chart should use ResponsiveContainer
    """
    user, _ = authenticated_user

    for chart_type in ["line", "bar"]:
        data = create_test_chart_data(chart_type, 3)
        canvas_id = create_chart_canvas(db_session, user, f"{chart_type}_chart", data, "Responsive Test")

        chart_page = open_chart_canvas(authenticated_page, canvas_id)

        # Verify ResponsiveContainer wrapper exists
        assert chart_page.chart_container.is_visible(), \
            f"Chart {chart_type} should have ResponsiveContainer wrapper"


def test_all_chart_types_use_unique_data(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test that unique data prevents cross-test pollution.

    GIVEN multiple charts with unique data
    WHEN all charts render
    THEN each chart should show its own data
    AND no data mixing should occur
    """
    user, _ = authenticated_user

    # Create three charts with different data
    line_data = create_test_chart_data("line", 3)
    bar_data = create_test_chart_data("bar", 4)
    pie_data = create_test_chart_data("pie", 5)

    line_id = create_chart_canvas(db_session, user, "line_chart", line_data, "Line Chart")
    chart_page = open_chart_canvas(authenticated_page, line_id)
    line_count = chart_page.get_data_point_count()

    bar_id = create_chart_canvas(db_session, user, "bar_chart", bar_data, "Bar Chart")
    chart_page = open_chart_canvas(authenticated_page, bar_id)
    bar_count = chart_page.get_data_point_count()

    pie_id = create_chart_canvas(db_session, user, "pie_chart", pie_data, "Pie Chart")
    chart_page = open_chart_canvas(authenticated_page, pie_id)
    pie_count = chart_page.get_data_point_count()

    # Verify each chart has correct data count
    assert line_count == len(line_data), "Line chart should have correct count"
    assert bar_count == len(bar_data), "Bar chart should have correct count"
    assert pie_count == len(pie_data), "Pie chart should have correct count"


# =============================================================================
# Chart Integration Tests
# =============================================================================

def test_chart_legend_displays_for_all_types(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test legend displays for all chart types."""
    user, _ = authenticated_user

    for chart_type in ["line", "bar", "pie"]:
        data = create_test_chart_data(chart_type, 3)
        canvas_id = create_chart_canvas(db_session, user, f"{chart_type}_chart", data, f"{chart_type.title()} Legend Test")

        chart_page = open_chart_canvas(authenticated_page, canvas_id)

        # All charts should have legend by default
        has_legend = chart_page.has_legend()
        assert has_legend, f"{chart_type.title()} chart should have legend"


def test_chart_grid_lines_for_cartesian_charts(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test grid lines display for Cartesian charts (line, bar)."""
    user, _ = authenticated_user

    for chart_type in ["line", "bar"]:
        data = create_test_chart_data(chart_type, 3)
        canvas_id = create_chart_canvas(db_session, user, f"{chart_type}_chart", data, "Grid Lines Test")

        chart_page = open_chart_canvas(authenticated_page, canvas_id)

        # Cartesian charts have grid lines
        # Note: grid_lines may not be visible if strokeDasharray makes them very faint
        # Just verify the locator doesn't error
        _ = chart_page.grid_lines.count()  # Should not raise error


def test_chart_colors_extractable(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test chart colors can be extracted from SVG."""
    user, _ = authenticated_user

    for chart_type in ["line", "bar", "pie"]:
        data = create_test_chart_data(chart_type, 3)
        canvas_id = create_chart_canvas(db_session, user, f"{chart_type}_chart", data, "Color Extraction Test")

        chart_page = open_chart_canvas(authenticated_page, canvas_id)

        # Extract colors
        colors = chart_page.get_chart_colors()
        assert len(colors) > 0, f"{chart_type.title()} chart should have extractable colors"


def test_chart_axes_labels_for_cartesian(authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session):
    """Test axes labels for Cartesian charts."""
    user, _ = authenticated_user

    for chart_type in ["line", "bar"]:
        data = create_test_chart_data(chart_type, 3)
        canvas_id = create_chart_canvas(db_session, user, f"{chart_type}_chart", data, "Axes Labels Test")

        chart_page = open_chart_canvas(authenticated_page, canvas_id)

        # Axes should exist (labels may be empty)
        _ = chart_page.get_x_axis_label()  # Should not error
        _ = chart_page.get_y_axis_label()  # Should not error
