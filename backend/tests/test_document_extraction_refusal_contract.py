"""Extraction-honesty refusal contract for the normal document producer.

Failure-first twins for the 2026-11-08 root probe: malformed/empty/whitespace
DOCX uploads used to return HTTP 200 with invented placeholder text, which was
then exported as ``provenance=authoritative``. The repair classifies absence at
the producer (``DocumentParser`` + ``/api/documents/upload``) and refuses with
a typed 422 before any materialized file, vector index row, SQL mirror row or
sheet-dataset background dispatch.

Valid twins prove the refusal is not a content heuristic: a real python-docx
fallback document, a real TXT document whose literal text happens to look like
the old parser placeholder, and real structured content all still upload,
read back and export with authoritative/versioned provenance.

Uses the existing ``/api/documents/export`` fixture (real LanceDB + scratch
SQL, embeddings only doubled). No model/provider/browser/live DB is used.
"""
from __future__ import annotations

import asyncio
import io
import json
import sys
from unittest.mock import patch

import pytest
from docx import Document

from core.auto_document_ingestion import DocumentParser
from core.models import IngestedDocument
from tests.test_document_export import exported, _error_code, _read


def _docx_bytes(text=None, table_text=None):
    """A real DOCX saved by python-docx (the parser's local fallback)."""
    doc = Document()
    if text is not None:
        doc.add_paragraph(text)
    if table_text is not None:
        table = doc.add_table(rows=1, cols=1)
        table.cell(0, 0).text = table_text
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _post(ctx, payload, filename, content_type=None):
    return ctx.client.post(
        "/api/documents/upload",
        files={"file": (filename, payload, content_type or (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"))},
    )


def _upload_text(ctx, text, name="note.txt"):
    response = ctx.client.post(
        "/api/documents/upload",
        files={"file": (name, text.encode("utf-8"), "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _index_count(ctx):
    table = ctx.handler.get_table("documents")
    return table.count_rows() if table is not None else 0


def _sql_snapshot(ctx):
    ctx.session.expire_all()
    return sorted((r.id, r.workspace_id, r.tenant_id, r.file_name,
                   r.source_content_hash, r.freshness_status)
                  for r in ctx.session.query(IngestedDocument).all())


def _assert_refused_without_side_effects(ctx, tmp_path, response, before):
    """The typed refusal must precede every durable/background side effect."""
    assert response.status_code == 422, response.text
    assert _error_code(response) == "DOCUMENT_EXTRACTION_EMPTY"
    detail = response.json()["detail"]["error"]
    assert detail["message"]
    assert detail["details"]["file_type"]

    ctx.session.expire_all()
    assert _sql_snapshot(ctx) == before
    assert _index_count(ctx) == 0
    assert not (tmp_path / "uploads").exists()


@pytest.mark.parametrize("invalid", ["malformed", "empty", "whitespace"])
def test_docx_without_extracted_content_refuses_before_side_effects(
        exported, monkeypatch, tmp_path, invalid):
    """Real parser, three distinct absent-content shapes, one honest refusal."""
    monkeypatch.setattr(DocumentParser, "_docling_processor", False)
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))

    if invalid == "malformed":
        payload = b"not a DOCX archive"
    elif invalid == "empty":
        payload = _docx_bytes()
    else:
        payload = _docx_bytes("   \n\t  ")

    before = _sql_snapshot(exported)
    response = _post(exported, payload, invalid + ".docx")
    _assert_refused_without_side_effects(exported, tmp_path, response, before)


def test_missing_docx_parser_is_absence_not_factual_content(
        exported, monkeypatch, tmp_path):
    """The shared parser's dependency-failure branch returns no-content.

    A missing optional parser is not evidence about the file; the old
    ``[DOCX content - parser not available]`` sentence was truthy and became
    stored/exported content. It must now travel the established ""/no_text
    convention and be refused by the producer.
    """
    monkeypatch.setattr(DocumentParser, "_docling_processor", False)
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    monkeypatch.setitem(sys.modules, "docx", None)

    # Direct parser contract: absent dependency = absent content.
    assert asyncio.run(DocumentParser.parse_document(
        b"docx", "docx", "missing.docx")) == ""

    before = _sql_snapshot(exported)
    response = _post(exported, b"docx", "missing.docx")
    _assert_refused_without_side_effects(exported, tmp_path, response, before)


def test_malformed_workbook_refusal_dispatches_no_sheet_background_work(
        exported, monkeypatch, tmp_path):
    """The sheet catalog is scheduled only after extraction succeeds."""
    monkeypatch.setattr(DocumentParser, "_docling_processor", False)
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))

    before = _sql_snapshot(exported)
    with patch(
        "core.sheet_dataset_service.sheet_datasets_enabled",
        return_value=True,
    ), patch(
        "core.sheet_dataset_service.ensure_sheet_dataset_background"
    ) as schedule:
        response = _post(exported, b"not an xlsx archive", "broken.xlsx")

    assert response.status_code == 422, response.text
    assert _error_code(response) == "DOCUMENT_EXTRACTION_EMPTY"
    schedule.assert_not_called()
    exported.session.expire_all()
    assert _sql_snapshot(exported) == before
    assert _index_count(exported) == 0
    assert not (tmp_path / "uploads").exists()


def test_real_docx_fallback_content_is_retained_and_authoritative(
        exported, monkeypatch, tmp_path):
    """Valid twin: the local python-docx fallback is not refused or altered."""
    monkeypatch.setattr(DocumentParser, "_docling_processor", False)
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    payload = _docx_bytes(
        "Verified paragraph content", "Verified table-cell content")

    response = _post(exported, payload, "positive.docx")
    assert response.status_code == 200, response.text
    doc_id = response.json()["id"]

    opened = _read(exported, doc_id)
    assert "Verified paragraph content" in opened["content"]
    assert "Verified table-cell content" in opened["content"]
    assert _read(exported, doc_id)["content"] == opened["content"]

    export = exported.client.get(
        f"/api/documents/{doc_id}/export?format=text")
    assert export.status_code == 200, export.text
    assert export.text == opened["content"]
    assert export.headers["X-Document-Provenance"] == "authoritative"
    assert export.headers["X-Document-Source-Version-Kind"] == "versioned"
    assert export.headers["X-Document-Source-Version-Status"] == "matched"

    exported.session.expire_all()
    row = exported.session.query(IngestedDocument).filter(
        IngestedDocument.id == doc_id).first()
    assert row is not None
    assert row.freshness_status == "fresh"
    assert row.source_content_hash


def test_literal_old_placeholder_text_is_real_user_content(
        exported, monkeypatch, tmp_path):
    """No wording heuristic: legitimate text resembling the old marker stays."""
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    text = (
        "Parser behavior note: the previous fallback printed "
        "[DOCX content - parser not available] when python-docx was missing.\n"
        "This sentence is the user's actual document text.\n"
    )
    doc_id = _upload_text(exported, text, "literal-placeholder.txt")
    assert _read(exported, doc_id)["content"] == text

    export = exported.client.get(
        f"/api/documents/{doc_id}/export?format=json")
    assert export.status_code == 200, export.text
    body = json.loads(export.content)
    assert body["content"] == text
    assert body["provenance_status"] == "authoritative"
    assert body["source_version_kind"] == "versioned"
    assert body["source_version_status"] == "matched"


def test_valid_txt_upload_is_retained(exported, monkeypatch, tmp_path):
    """Plain valid TXT twin — short real text is content, not empty."""
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    text = "data"
    doc_id = _upload_text(exported, text, "short.txt")
    opened = _read(exported, doc_id)
    assert opened["content"] == text

    export = exported.client.get(
        f"/api/documents/{doc_id}/export?format=text")
    assert export.status_code == 200, export.text
    assert export.text == text
    assert export.headers["X-Document-Provenance"] == "authoritative"


def test_parallel_ingestion_upload_whitespace_refuses_before_writes(
        exported, monkeypatch):
    """Mounted `/api/document-ingestion/upload`: whitespace is not evidence.

    The parallel upload surface keeps its existing bounded 400 refusal shape;
    the guard now covers whitespace-only extraction and runs before the
    LanceDB/SQL writes.
    """
    monkeypatch.setattr(
        "core.docling_processor.is_docling_available", lambda: False)

    before = _sql_snapshot(exported)
    response = exported.client.post(
        "/api/document-ingestion/upload",
        files={"file": ("blank.txt", b"   \n\t  ", "text/plain")},
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Could not extract text from document"
    assert "document_id" not in response.text

    exported.session.expire_all()
    assert _sql_snapshot(exported) == before
    assert _index_count(exported) == 0


def test_parallel_ingestion_upload_nonempty_is_retained(exported, monkeypatch):
    """Mounted positive twin: real nonempty text still uploads and reads back."""
    monkeypatch.setattr(
        "core.docling_processor.is_docling_available", lambda: False)
    text = "Parallel ingestion upload keeps this real content.\n"

    response = exported.client.post(
        "/api/document-ingestion/upload",
        files={"file": ("parallel.txt", text.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    doc_id = body["data"]["document_id"]
    assert doc_id
    assert _read(exported, doc_id)["content"] == text

    export = exported.client.get(
        f"/api/documents/{doc_id}/export?format=json")
    assert export.status_code == 200, export.text
    payload = json.loads(export.content)
    assert payload["content"] == text
    # Existing authority policy for this surface: raw-byte opaque revision,
    # matched on both indexed and SQL sides.
    assert payload["provenance_status"] == "authoritative"
    assert payload["source_version_kind"] == "opaque"
    assert payload["source_version_status"] == "matched"


def test_valid_structured_workbook_is_retained(exported, monkeypatch, tmp_path):
    """Structured twin: real openpyxl workbook cells survive the refusal gate."""
    from openpyxl import Workbook

    monkeypatch.setattr(DocumentParser, "_docling_processor", False)
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "core.sheet_dataset_service.sheet_datasets_enabled", lambda: False)

    workbook = Workbook()
    workbook.active["A1"] = "Structured header"
    workbook.active["A2"] = "Verified cell value"
    buffer = io.BytesIO()
    workbook.save(buffer)

    response = _post(
        exported, buffer.getvalue(), "structured.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert response.status_code == 200, response.text
    doc_id = response.json()["id"]

    opened = _read(exported, doc_id)
    assert "Verified cell value" in opened["content"]

    export = exported.client.get(
        f"/api/documents/{doc_id}/export?format=text")
    assert export.status_code == 200, export.text
    assert export.text == opened["content"]
    assert export.headers["X-Document-Provenance"] == "authoritative"
