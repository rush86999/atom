"""Ordinary uploaded binary documents must use the versioned indexed text.

Regression for the normal-upload replay: ``POST /api/documents/upload`` stores
the real ``data/office/uploads/<doc_id>.xlsx`` path on the authoritative
``IngestedDocument`` row and stores the extracted workbook text in LanceDB
under the same extraction revision. ``document.text`` used to prefer that path
unconditionally, so ``_document_read`` decoded the OOXML ZIP container
("PK\\x03\\x04...", NUL and other C0 controls) as text and recorded the read as
applied/verified. The artifact renderer then rejected the composed markdown.

These tests pin the raw-path shortcut to the suffixes ``_document_read`` really
decodes as text, require container/binary uploads to use the authoritative
version-matched indexed extraction, and keep the stale/scope refusals and the
legacy-ingestion pseudo path (``upload:<name>``) on that same indexed branch.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from core.assignment_executor import NeedsContext, _document_text_read
from core.assignment_resources import (
    resolve_assignment_source, resource_binding,
)
from core.doc_freshness_service import extraction_content_hash
from core.models import IngestedDocument
from tests.test_assignment_routes import route_env  # noqa: F401

DOC_ID = "doc_35ac92054d4656ee3645eaf2"
WORKBOOK_TEXT = (
    "WORKBOOK INDEX: 1 sheets\n"
    "- Prices: 2 data rows, 4 cols | headers: Item, Qty, Price, Currency\n"
    "Item | Qty | Price | Currency\n"
    "A | 2 | 100.00 | USD\n"
    "B | 3 | 50.00 | USD\n"
)
# A bounded OOXML ZIP prefix plus NUL/high bytes. Reading this as text is the
# raw-container read this regression forbids; it is not a valid workbook, so a
# silent fallback to the path cannot look like a successful extraction.
ZIP_BYTES = b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"\x00\xff" * 64

CONTEXT = {"workspace_id": "ws-1", "tenant_id": "tenant-1"}


def _upload_xlsx(
    route_env, tmp_path, *, file_name="price-book.xlsx",
    freshness="fresh", indexed_text=WORKBOOK_TEXT, indexed_version=None,
    file_path=None,
):
    """The exact row shape the ordinary upload route persists."""
    path = tmp_path / "data" / "office" / "uploads" / f"{DOC_ID}.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(ZIP_BYTES)
    version = extraction_content_hash(WORKBOOK_TEXT)
    row = IngestedDocument(
        id=DOC_ID,
        workspace_id="ws-1",
        tenant_id="tenant-1",
        file_name=file_name,
        file_path=str(path) if file_path is None else file_path,
        file_type="xlsx",
        integration_id="manual_upload",
        external_id=f"upload_{DOC_ID}",
        source_content_hash=version,
        file_size_bytes=len(ZIP_BYTES),
        content_preview=WORKBOOK_TEXT[:500],
        freshness_status=freshness,
    )
    route_env["db"].add(row)
    route_env["db"].commit()
    document = {
        "id": DOC_ID,
        "text": indexed_text,
        "source": f"upload:{file_name}",
        "metadata": {
            "source_content_hash": (
                version if indexed_version is None else indexed_version),
            "pg_document_id": DOC_ID,
            "filename": file_name,
        },
    }
    return path, version, row, document


def _index(monkeypatch, document):
    import core.lancedb_handler as lance

    def by_id(_table, doc_id):
        return document if doc_id == document["id"] else None

    handler = SimpleNamespace(get_document_by_id=by_id)
    monkeypatch.setattr(
        lance, "get_lancedb_handler", lambda workspace: handler)


def _resolved_read(route_env, *, source_version=None):
    reference = {"kind": "document", "document_id": DOC_ID}
    if source_version:
        reference["source_version"] = source_version
    resolved = resolve_assignment_source(
        route_env["db"], route_env["users"]["lead"], reference)
    binding = resource_binding(resolved)
    inputs = {"resource_binding": binding}
    if resolved.get("path"):
        # The planner copies the server-resolved path only when a
        # document_id is present; reproduce that exact step input shape.
        inputs["path"] = str(resolved["path"])
    return asyncio.run(_document_text_read(inputs, dict(CONTEXT)))


def _assert_no_raw_container(text):
    assert not text.startswith("PK"), (
        "document.text returned the raw OOXML ZIP container")
    assert "\x00" not in text
    assert "\ufffd" not in text
    assert not any(ch not in "\n\r\t" and ord(ch) < 0x20 for ch in text), (
        "the extracted text still carries C0 controls that the DOCX renderer "
        "rejects as invalid XML")


def test_ordinary_upload_xlsx_uses_versioned_indexed_text(
        route_env, tmp_path, monkeypatch):
    _path, version, _row, document = _upload_xlsx(route_env, tmp_path)
    _index(monkeypatch, document)

    result = _resolved_read(route_env, source_version=version)

    assert result["status"] == "applied"
    assert result["summary"].startswith("read extracted text from")
    assert result["text"] == WORKBOOK_TEXT
    assert "Item, Qty, Price, Currency" in result["text"]
    _assert_no_raw_container(result["text"])
    assert result["source_version"] == version
    assert result["verification"]["status"] == "verified"
    assert result["verification"]["version"] == version
    assert result["extraction"]["indexed_version"] == version
    assert result["extraction"]["authoritative_version"] == version


def test_ordinary_upload_xlsx_stale_index_is_refused(
        route_env, tmp_path, monkeypatch):
    _path, _version, _row, document = _upload_xlsx(
        route_env, tmp_path,
        indexed_version=extraction_content_hash("an older extraction"))
    _index(monkeypatch, document)

    with pytest.raises(NeedsContext) as raised:
        _resolved_read(route_env)

    assert raised.value.gap["concept"] == "document_extraction_stale"


def test_ordinary_upload_xlsx_stale_authority_is_refused(
        route_env, tmp_path, monkeypatch):
    path, version, row, document = _upload_xlsx(route_env, tmp_path)
    _index(monkeypatch, document)
    resolved = resolve_assignment_source(
        route_env["db"], route_env["users"]["lead"],
        {"kind": "document", "document_id": DOC_ID,
         "source_version": version})
    # Authority went stale after resolution: the next read must refuse rather
    # than fall back to the still-present local file.
    row.freshness_status = "stale"
    route_env["db"].commit()
    assert path.is_file()

    with pytest.raises(NeedsContext) as raised:
        asyncio.run(_document_text_read(
            {"resource_binding": resource_binding(resolved),
             "path": str(path)}, dict(CONTEXT)))

    assert raised.value.gap["concept"] == "document_freshness"


def test_ordinary_upload_xlsx_out_of_scope_is_refused(
        route_env, tmp_path, monkeypatch):
    _path, version, _row, document = _upload_xlsx(route_env, tmp_path)
    _index(monkeypatch, document)
    resolved = resolve_assignment_source(
        route_env["db"], route_env["users"]["lead"],
        {"kind": "document", "document_id": DOC_ID,
         "source_version": version})
    binding = resource_binding(resolved)
    binding.pop("workspace_id", None)

    with pytest.raises(NeedsContext) as raised:
        asyncio.run(_document_text_read(
            {"resource_binding": binding, "path": str(resolved["path"])},
            {"workspace_id": "ws-2", "tenant_id": "tenant-1"}))

    assert raised.value.gap["concept"] == "document_scope"


def test_legacy_ingestion_pseudo_path_still_cannot_raw_read(
        route_env, tmp_path, monkeypatch):
    # ``POST /api/document-ingestion/upload`` records file_path="upload:<name>"
    # (never a real file). It must stay on the indexed branch: this pins the
    # code path only and makes no claim about that route's artifact predicates,
    # whose open negative is tracked separately.
    _path, _version, _row, document = _upload_xlsx(
        route_env, tmp_path, file_name="price-book.xlsx",
        file_path="upload:price-book.xlsx")
    _index(monkeypatch, document)

    resolved = resolve_assignment_source(
        route_env["db"], route_env["users"]["lead"],
        {"kind": "document", "document_id": DOC_ID})
    binding = resource_binding(resolved)
    result = asyncio.run(_document_text_read(
        {"resource_binding": binding, "path": str(resolved["path"])},
        dict(CONTEXT)))

    assert result["summary"].startswith("read extracted text from")
    assert result["text"].startswith("WORKBOOK INDEX: 1 sheets")
    _assert_no_raw_container(result["text"])


def test_text_and_json_path_reads_keep_their_real_content(
        route_env, tmp_path, monkeypatch):
    text_path = tmp_path / "notes.txt"
    text_path.write_text("local notes are the source")
    json_path = tmp_path / "invoice.json"
    json_path.write_text('{"invoice_id": "INV-1", "total": "370.00"}')
    # The indexed text is deliberately different: a genuinely text-native file
    # must still be read from its authorized path (the 2026-11-03 behavior).
    for doc_id, path, file_type in (
            (f"{DOC_ID}-txt", text_path, "txt"),
            (f"{DOC_ID}-json", json_path, "json")):
        route_env["db"].add(IngestedDocument(
            id=doc_id, workspace_id="ws-1", tenant_id="tenant-1",
            file_name=path.name, file_path=str(path), file_type=file_type,
            integration_id="manual_upload",
            external_id=f"upload_{doc_id}",
            source_content_hash=extraction_content_hash("other extraction"),
            freshness_status="fresh"))
    route_env["db"].commit()

    text_read = asyncio.run(_document_text_read(
        {"resource_binding": {
            "document_id": f"{DOC_ID}-txt",
            "resource_id": f"{DOC_ID}-txt",
            "representation": "document_text",
            "source": "manual_upload",
            "workspace_id": "ws-1",
            "tenant_id": "tenant-1",
        }, "path": str(text_path)}, dict(CONTEXT)))
    assert text_read["text"] == "local notes are the source"

    json_read = asyncio.run(_document_text_read(
        {"resource_binding": {
            "document_id": f"{DOC_ID}-json",
            "resource_id": f"{DOC_ID}-json",
            "representation": "document_text",
            "source": "manual_upload",
            "workspace_id": "ws-1",
            "tenant_id": "tenant-1",
        }, "path": str(json_path)}, dict(CONTEXT)))
    assert json_read["data"]["invoice_id"] == "INV-1"
    assert "local notes" not in json_read["text"]
