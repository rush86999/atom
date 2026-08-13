"""
E2E Tests for Sheet Canvas Rendering (CANV-02).

Tests verify the sheet canvas renders correctly through the REAL rendering
path (no phantom state injection):

1. A sheet canvas is created as `Canvas` + `CanvasAudit` rows via
   `canvas_helpers.create_canvas()` (mirroring `tools/canvas_tool.present_*`),
   with content = the sheet as a list of rows (list of lists).
2. Tests navigate to `http://localhost:3001/canvas/{id}`, where `CanvasPanel`
   renders the HTML table grid (column letters A/B/C…, one editable `<input>`
   per cell, "+ Add New Row" button).

Real component capabilities: editable grid, column-letter headers, row
numbers, add-row. The real component has NO pagination or column sorting —
those legacy expectations are rewritten as documented skips.
"""

import uuid
from typing import Tuple

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy.orm import Session

# Add backend to path for imports
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from core.models import CanvasAudit, User
from tests.e2e_ui.tests.canvas_helpers import create_canvas, open_canvas


# =============================================================================
# Helper Functions
# =============================================================================

def create_sheet_canvas(db: Session, user: User, rows: list, title: str = "Test Sheet") -> str:
    """Create a sheet canvas whose content is a list of row-lists."""
    canvas_id = f"e2e-sheet-{uuid.uuid4()}"
    create_canvas(db, user, canvas_id, "sheet", title, rows)
    return canvas_id


def open_sheet_canvas(page: Page, canvas_id: str) -> None:
    """Navigate to a sheet canvas and wait for the table grid."""
    open_canvas(page, canvas_id, "sheet")
    page.wait_for_selector('[data-testid="canvas-container"] table', timeout=10000)


def cell_inputs(page: Page) -> list:
    """Read the current value of every editable cell in the sheet grid.

    Note: cell values live in the input .value property (controlled React
    inputs), so DOM inner_text does NOT include them.
    """
    return page.evaluate(
        """() => Array.from(
            document.querySelectorAll('[data-testid="canvas-container"] tbody td input')
        ).map(i => i.value)"""
    )


def create_sheet_data(rows: int, cols: int) -> list:
    """Create sheet data as a list of row-lists."""
    return [[f"value_{r}_{c}" for c in range(cols)] for r in range(rows)]


# =============================================================================
# Sheet Canvas Rendering Tests
# =============================================================================

def test_sheet_displays_data_grid(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that sheet displays the data grid with correct structure.

    Verifies:
    - CanvasPanel container with sheet type badge
    - Table rendered with 10 data rows + add-row control
    - Cell values present
    - CanvasAudit record created
    """
    user, _ = authenticated_user
    sheet_data = create_sheet_data(rows=10, cols=5)
    canvas_id = create_sheet_canvas(db_session, user, sheet_data, "Test Data Grid")

    open_sheet_canvas(authenticated_page, canvas_id)

    # 10 data rows + 1 add-row control row.
    body_rows = authenticated_page.locator('[data-testid="canvas-container"] tbody tr')
    assert body_rows.count() == 11, f"Expected 11 tbody rows, got {body_rows.count()}"

    values = cell_inputs(authenticated_page)
    assert values[0] == "value_0_0", f"First cell value should render, got {values[:2]}"
    assert values[-1] == "value_9_4", f"Last cell value should render, got {values[-2:]}"

    audit = db_session.query(CanvasAudit).filter(CanvasAudit.canvas_id == canvas_id).all()
    assert len(audit) >= 1, "CanvasAudit record should exist for the canvas"
    assert audit[0].canvas_type == "sheet", "Audit row should carry the sheet type"


def test_sheet_pagination_works(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that sheet handles large datasets (100 rows) — real component renders
    the full grid without pagination (no virtual scrolling on /canvas/{id})."""
    user, _ = authenticated_user
    sheet_data = create_sheet_data(rows=100, cols=4)
    canvas_id = create_sheet_canvas(db_session, user, sheet_data, "Large Sheet")

    open_sheet_canvas(authenticated_page, canvas_id)

    body_rows = authenticated_page.locator('[data-testid="canvas-container"] tbody tr')
    assert body_rows.count() == 101, f"Expected 101 tbody rows (100 data + add row), got {body_rows.count()}"
    values = cell_inputs(authenticated_page)
    assert values[0] == "value_0_0", "First cell value should render for large sheets"


def test_sheet_sorting_works(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Sheet column sorting: the real /canvas/{id} sheet grid has no column
    sorting — cell inputs are editable but headers are static column letters.
    Documented skip (no sorting path exists in the real component)."""
    pytest.skip(
        "The real sheet grid (CanvasPanel 'sheet') renders static column-letter "
        "headers with editable cells; column sorting is not implemented on the "
        "/canvas/{id} route. Nothing to verify — see CanvasPanel.tsx."
    )


def test_sheet_column_headers_display(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that sheet renders column-letter headers (A, B, C, …)."""
    user, _ = authenticated_user
    sheet_data = [
        ["ID", "Name", "Role"],
        ["1", "Alice", "Admin"],
        ["2", "Bob", "User"],
    ]
    canvas_id = create_sheet_canvas(db_session, user, sheet_data, "User Table")

    open_sheet_canvas(authenticated_page, canvas_id)

    headers = authenticated_page.locator('[data-testid="canvas-container"] thead th').all_inner_texts()
    assert headers[:3] == ["#", "A", "B"], f"Expected row-number + A/B column headers, got {headers}"

    values = cell_inputs(authenticated_page)
    assert "Alice" in values, "Sheet cell content should render"


def test_sheet_empty_state(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that sheet handles empty rows gracefully (renders, no crash)."""
    user, _ = authenticated_user
    canvas_id = create_sheet_canvas(db_session, user, [["", "", ""]], "Empty Sheet")

    open_sheet_canvas(authenticated_page, canvas_id)

    add_row_button = authenticated_page.locator("button", has_text="Add New Row").first
    expect(add_row_button).to_be_visible()
    table_text = authenticated_page.locator('[data-testid="canvas-container"] table').inner_text()
    assert "A" in table_text, "Column headers should render even with empty rows"


def test_sheet_responsive_layout(
    authenticated_page: Page, authenticated_user: Tuple[User, str], db_session: Session
):
    """Test that sheet table has positive dimensions in the canvas container."""
    user, _ = authenticated_user
    canvas_id = create_sheet_canvas(db_session, user, create_sheet_data(3, 3), "Responsive Sheet")

    open_sheet_canvas(authenticated_page, canvas_id)

    table = authenticated_page.locator('[data-testid="canvas-container"] table').first
    box_size = table.bounding_box()
    assert box_size is not None and box_size["width"] > 0, "Sheet table should have positive width"
