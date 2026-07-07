"""
Unit Tests for Office Automation Service

Validates Excel, Word, and PowerPoint reading/writing/rendering.
"""

import os
import tempfile
import pytest
from pathlib import Path
from core.office_service import OfficeService


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


def test_excel_write_and_read(temp_dir):
    service = OfficeService()
    file_path = os.path.join(temp_dir, "test.xlsx")

    # Excel write
    write_res = service.excel.write_cell(
        file_path=file_path,
        cell_path="/Sheet1/A1",
        value=42
    )
    assert write_res["success"] is True
    assert write_res["coordinate"] == "A1"
    assert write_res["sheet_name"] == "Sheet1"

    # Excel read
    read_res = service.excel.read_range(
        file_path=file_path,
        cell_path="/Sheet1/A1"
    )
    assert read_res["success"] is True
    assert read_res["value"] == 42
    assert read_res["cell_type"] == "text"


def test_word_write_and_read(temp_dir):
    service = OfficeService()
    file_path = os.path.join(temp_dir, "test.docx")

    # Word modify (append)
    modify_res = service.word.modify_document(
        file_path=file_path,
        action="append",
        content="Hello world"
    )
    assert modify_res["success"] is True

    # Word read
    read_res = service.word.read_document(file_path)
    assert read_res["success"] is True
    assert len(read_res["paragraphs"]) == 1
    assert read_res["paragraphs"][0]["text"] == "Hello world"


def test_renderer_html(temp_dir):
    service = OfficeService()
    file_path = os.path.join(temp_dir, "test.docx")

    # Preseed with paragraph
    service.word.modify_document(
        file_path=file_path,
        action="append",
        content="Test HTML render content"
    )

    # Render HTML (uses mammoth)
    render_res = service.renderer.render_to_html(file_path)
    assert render_res["success"] is True, f"Error was: {render_res.get('error')}"
    assert "office-word-preview" in render_res["html"]
