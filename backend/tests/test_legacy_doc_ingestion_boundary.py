# -*- coding: utf-8 -*-
"""Legacy binary Office ingestion boundary (audit item 7).

`.doc` (and `.ppt`) are pre-2007 OLE2 containers. The drive connectors
DISCOVER them — `.doc` sits in the same document-extension funnel as `.docx`
— but the parser chain is python-docx/python-pptx, which cannot open the
binary container. The failure currently surfaces as ``skipped: no_text``,
which is the SAME reason a genuinely empty (but perfectly readable) document
produces. That conflates two different facts:

  * "we found a file with this name, and we cannot read its format"  → the
    content is NOT in memory and no answer may be drawn from it; and
  * "we read the file and it contains no text"                       → the
    content IS known to be empty.

These tests pin the distinction. They do not add `.doc` parsing support —
that is a separate capability task (LibreOffice headless conversion already
has a discovery helper at ``core.workbook_runtime._find_soffice``).
"""
import io
from unittest.mock import patch

import pytest

import core.auto_document_ingestion as adi
from core.auto_document_ingestion import (
    AutoDocumentIngestionService,
    DocumentParser,
)

# OLE2/Compound-File magic — the first 8 bytes of every legacy .doc/.ppt/.xls.
OLE2_MAGIC = bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1])


def _legacy_doc_bytes() -> bytes:
    """A minimal OLE2 header plus padding: enough for python-docx to reject
    it as 'not a zip file', which is what a real .doc looks like to it."""
    return OLE2_MAGIC + b"\x00" * 512


def _empty_docx_bytes() -> bytes:
    """A VALID, readable .docx that happens to contain no text."""
    from docx import Document

    buf = io.BytesIO()
    Document().save(buf)
    return buf.getvalue()


@pytest.fixture()
def service():
    with patch("core.lancedb_handler.get_lancedb_handler"):
        yield AutoDocumentIngestionService()


class TestLegacyDocIsNotSilentlyNoText:
    @pytest.mark.asyncio
    async def test_legacy_doc_reports_unsupported_not_no_text(self, service):
        out = await service.process_file_bytes(
            _legacy_doc_bytes(), "Fintek F-5216 spec sheet.doc",
            source="upload", user_id="u1")
        assert out["status"] != "ingested"
        # The load-bearing assertion: "we could not read this format" must be
        # distinguishable from "the document is empty".
        assert out.get("reason") != "no_text", (
            "a legacy binary .doc is reported as an empty document; callers "
            "cannot tell filename discovery from extracted contents")

    @pytest.mark.asyncio
    async def test_legacy_doc_is_explicitly_unsupported(self, service):
        out = await service.process_file_bytes(
            _legacy_doc_bytes(), "spec.doc", source="upload", user_id="u1")
        assert out.get("extraction_supported") is False, (
            "the result must state that content extraction was not available")
        assert out.get("file_ext") == "doc"

    @pytest.mark.asyncio
    async def test_genuinely_empty_docx_still_reports_no_text(self, service):
        """The contrast case: a readable document with no text keeps the
        no_text reason, so the two outcomes stay distinct."""
        out = await service.process_file_bytes(
            _empty_docx_bytes(), "blank.docx", source="upload", user_id="u1")
        assert out["status"] == "skipped"
        assert out.get("reason") == "no_text"
        assert out.get("extraction_supported") is not False


class TestDiscoveryVersusExtraction:
    """Pin the discovered-vs-parseable split so the two funnels cannot drift
    apart silently: a `.doc` is visible by NAME to the catalog but is not on
    the extractable list."""

    def test_doc_is_discovered_but_not_parseable_in_drive_funnel(self):
        import inspect
        import re

        import core.hybrid_data_ingestion as hdi
        src = inspect.getsource(hdi)

        discovered = re.search(r"_DOC_EXTS\s*=\s*\(([^)]*)\)", src)
        assert discovered, "the drive discovery funnel moved or was renamed"
        assert '".doc"' in discovered.group(1), (
            "the drive funnel no longer discovers .doc — this test's premise "
            "(name-only visibility) has changed")

        parseable = re.findall(r"parseable_exts\s*=\s*\(([^)]*)\)", src)
        assert parseable, "no parseable_exts list found; the extraction "
        for listed in parseable:
            assert ".docx" in listed, "unexpected parseable_exts shape"
            assert '".doc"' not in listed, (
                "a parseable_exts list claims .doc is extractable while the "
                "OOXML parser chain cannot read the binary container")

    def test_legacy_formats_are_declared(self):
        assert hasattr(adi, "LEGACY_BINARY_OFFICE_EXTS")
        assert {"doc", "ppt"} <= set(adi.LEGACY_BINARY_OFFICE_EXTS)

    @pytest.mark.asyncio
    async def test_renamed_docx_still_parses(self, service):
        """A .docx renamed to .doc must keep working — the boundary is about
        the BINARY container, not the extension string, so the implementation
        must attempt the parse before declaring the format unsupported."""
        text = await DocumentParser.parse_document(
            _empty_docx_bytes(), "doc", "renamed.doc")
        assert isinstance(text, str)  # readable container -> no exception
