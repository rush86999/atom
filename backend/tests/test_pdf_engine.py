"""PdfEngine unit tests — deterministic bytes-in/bytes-out ops (P1).

Fixture PDFs are generated with reportlab (a shipped dependency) so the
tests carry no binary blobs and every assertion traces to a known page
count / text payload.
"""
import io

import pytest

from core import pdf_engine
from core.pdf_engine import PdfEngineError


def _make_pdf(text: str, pages: int = 1) -> bytes:
    from reportlab.pdfgen import canvas as rl_canvas

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(612, 792))
    for i in range(pages):
        c.setFont("Helvetica", 12)
        c.drawString(72, 700, f"{text} p{i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def test_blank_pdf_is_a_valid_single_page():
    data = pdf_engine.blank_pdf("Quote draft")
    info = pdf_engine.load_info(data)
    assert info["page_count"] == 1
    assert len(data) > 500


def test_load_info_counts_pages_and_rejects_garbage():
    info = pdf_engine.load_info(_make_pdf("hello", pages=3))
    assert info["page_count"] == 3
    assert len(info["pages"]) == 3
    with pytest.raises(PdfEngineError):
        pdf_engine.load_info(b"not a pdf at all")
    with pytest.raises(PdfEngineError):
        pdf_engine.load_info(b"")


def test_build_pages_reorders_deletes_and_rotates():
    data = _make_pdf("page", pages=3)
    # move page 3 first, drop page 2, rotate page 1 by 90°
    out = pdf_engine.build_pages(data, [
        {"src_index": 2, "rotation": 0},
        {"src_index": 0, "rotation": 90},
    ])
    info = pdf_engine.load_info(out)
    assert info["page_count"] == 2
    # the rotated page keeps its box but swaps width/height (Letter 612x792)
    rotated = info["pages"][1]
    assert rotated["width"] == 792 and rotated["height"] == 612
    # rotation is ABSOLUTE: re-applying 90 on the already-rotated page stays 90
    again = pdf_engine.build_pages(out, [
        {"src_index": 0, "rotation": 0},
        {"src_index": 1, "rotation": 90},
    ])
    assert pdf_engine.load_info(again)["pages"][1] == rotated


def test_build_pages_rejects_bad_maps():
    data = _make_pdf("x", pages=2)
    with pytest.raises(PdfEngineError):
        pdf_engine.build_pages(data, [])  # would delete every page
    with pytest.raises(PdfEngineError):
        pdf_engine.build_pages(data, [{"src_index": 5, "rotation": 0}])
    with pytest.raises(PdfEngineError):
        pdf_engine.build_pages(data, [{"src_index": 0, "rotation": 0}, {"src_index": 0, "rotation": 0}])
    with pytest.raises(PdfEngineError):
        pdf_engine.build_pages(data, [{"src_index": 0, "rotation": 45}])


def test_append_pdf_concatenates_and_caps():
    a = _make_pdf("a", pages=2)
    b = _make_pdf("b", pages=3)
    merged = pdf_engine.append_pdf(a, b)
    assert pdf_engine.load_info(merged)["page_count"] == 5
    with pytest.raises(PdfEngineError):
        pdf_engine.append_pdf(a, b, max_result_pages=4)


def test_extract_text_returns_per_page_text():
    data = _make_pdf("invoice total", pages=2)
    pages = pdf_engine.extract_text(data)
    assert len(pages) == 2
    assert "invoice total p1" in pages[0]["text"]
    assert "invoice total p2" in pages[1]["text"]
    assert pdf_engine.extract_text(data, max_pages=1)[0]["page"] == 0
