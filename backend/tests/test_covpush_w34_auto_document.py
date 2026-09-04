"""Coverage wave 34 — core/auto_document_ingestion.py (TDD, mocked deps).

Drives the document pipeline: DocumentParser (docling + all fallback
parsers incl. CSV/Excel formula extraction and error paths), the service
settings CRUD, process_file_bytes (extension/parse/text/redaction/
ingest paths), the full sync loop (skip/stale/type/size guards,
download/parse/redact/ingest with freshness persistence + supersession
+ agent trigger + time-limit break), freshness helpers, cloud-drive
fetchers (google drive/dropbox list+download, onedrive/notion stubs),
and module functions — no network, no LLM, zero spend.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import os

import pytest

from core.auto_document_ingestion import (
    AutoDocumentIngestion,
    AutoDocumentIngestionService,
    DocumentParser,
    FileType,
    IngestedDocument,
    IngestionSettings,
    IntegrationSource,
    get_document_ingestion_service,
)


def make_service(**kw):
    with patch("core.lancedb_handler.get_lancedb_handler",
               return_value=MagicMock()), \
         patch("core.secrets_redactor.get_secrets_redactor",
               return_value=MagicMock()):
        svc = AutoDocumentIngestionService()
    svc.memory_handler = MagicMock()
    svc.redactor = MagicMock()
    for k, v in kw.items():
        setattr(svc, k, v)
    return svc


def make_doc(**kw):
    defaults = dict(
        id="doc-1", file_name="a.pdf", file_path="/a.pdf", file_type="pdf",
        integration_id="google_drive", workspace_id="default",
        file_size_bytes=100, content_preview="preview",
        ingested_at=datetime.now(timezone.utc), external_id="ext-1",
        external_modified_at=None, source_url="https://x",
        source_content_hash="h1", last_verified_at=datetime.now(timezone.utc),
        source_modified_at=None, freshness_status="fresh", superseded_by=None)
    defaults.update(kw)
    return IngestedDocument(**defaults)


# ---------------------------------------------------------------------------
# DocumentParser
# ---------------------------------------------------------------------------


class TestDoclingProcessor:
    def test_available(self):
        processor = MagicMock()
        with patch("core.docling_processor.is_docling_available",
                   return_value=True), \
             patch("core.docling_processor.get_docling_processor",
                   return_value=processor):
            DocumentParser._docling_processor = None
            assert DocumentParser._get_docling_processor() is processor

    def test_unavailable(self):
        with patch("core.docling_processor.is_docling_available",
                   return_value=False):
            DocumentParser._docling_processor = None
            assert DocumentParser._get_docling_processor() is None

    def test_import_error(self):
        DocumentParser._docling_processor = None
        with patch("builtins.__import__",
                   side_effect=ImportError("no docling")):
            assert DocumentParser._get_docling_processor() is None


class TestParseDocument:
    async def test_docling_success(self):
        processor = MagicMock()
        processor.process_document = AsyncMock(return_value={
            "success": True, "content": "parsed text", "total_chars": 11})
        with patch.object(DocumentParser, "_get_docling_processor",
                          return_value=processor):
            text = await DocumentParser.parse_document(b"data", "pdf", "f.pdf")
        assert text == "parsed text"

    async def test_docling_failure_falls_back(self):
        processor = MagicMock()
        processor.process_document = AsyncMock(return_value={
            "success": False, "content": None})
        with patch.object(DocumentParser, "_get_docling_processor",
                          return_value=processor):
            text = await DocumentParser.parse_document(b"data", "pdf", "f.pdf")
        assert text == "" or "[PDF content" in text  # fallback PDF parse

    async def test_docling_error_falls_back(self):
        processor = MagicMock()
        processor.process_document = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(DocumentParser, "_get_docling_processor",
                          return_value=processor):
            await DocumentParser.parse_document(b"data", "pdf", "f.pdf")

    async def test_txt_md(self):
        assert await DocumentParser.parse_document(b"hello", "txt", "a.txt") == "hello"
        assert await DocumentParser.parse_document(b"# md", "md", "a.md") == "# md"

    async def test_json(self):
        text = await DocumentParser.parse_document(b'{"a": 1}', "json", "a.json")
        assert '"a": 1' in text

    async def test_csv(self):
        text = await DocumentParser.parse_document(b"a,b\n1,2", "csv", "a.csv")
        assert "a | b" in text

    async def test_pdf(self):
        with patch.object(DocumentParser, "_parse_pdf",
                          new=AsyncMock(return_value="pdf text")):
            assert await DocumentParser.parse_document(b"x", "pdf", "a.pdf") == "pdf text"

    async def test_docx(self):
        with patch.object(DocumentParser, "_parse_docx",
                          new=AsyncMock(return_value="docx text")):
            assert await DocumentParser.parse_document(b"x", "docx", "a.docx") == "docx text"

    async def test_excel(self):
        with patch.object(DocumentParser, "_parse_excel",
                          new=AsyncMock(return_value="xlsx text")):
            assert await DocumentParser.parse_document(b"x", "xlsx", "a.xlsx") == "xlsx text"

    async def test_unsupported(self):
        assert await DocumentParser.parse_document(b"x", "exe", "a.exe") == ""

    async def test_outer_exception(self):
        with patch.object(DocumentParser, "_get_docling_processor",
                         side_effect=RuntimeError("boom")):
            assert await DocumentParser.parse_document(b"x", "txt", "a.txt") == ""


class TestCsvParser:
    def test_plain(self):
        text = DocumentParser._parse_csv(b"a,b\n1,2")
        assert text == "a | b\n1 | 2"

    def test_truncated_rows(self, monkeypatch):
        """Post-2026-09-03 contract: record-count caps are gone; the ONLY
        bound is the char budget (ATOM_EXTRACTION_MAX_CHARS, default 2M),
        which appends a visible truncation note when it cuts."""
        rows = "\n".join(f"r{i}" for i in range(12000))  # ~73k chars
        text = DocumentParser._parse_csv(rows.encode())
        assert "r11999" in text and "truncated" not in text  # fits the 2M default

        monkeypatch.setenv("ATOM_EXTRACTION_MAX_CHARS", "30000")
        text = DocumentParser._parse_csv(rows.encode())
        assert "extraction budget reached" in text and "r11999" not in text

    def test_with_formula_extraction(self):
        extractor = MagicMock()
        extractor.extract_from_csv.return_value = [{"formula": "=SUM(A1)"}]
        with patch("core.formula_extractor.get_formula_extractor",
                   return_value=extractor):
            text = DocumentParser._parse_csv(b"a,b\n1,2", file_path="/tmp/x.csv")
        assert "a | b" in text

    def test_formula_extraction_failure_tolerated(self):
        with patch("core.formula_extractor.get_formula_extractor",
                   side_effect=RuntimeError("boom")):
            text = DocumentParser._parse_csv(b"a,b", file_path="/tmp/x.csv")
        assert text == "a | b"

    def test_parse_error_returns_raw(self):
        csv_mod = MagicMock()
        csv_mod.reader.side_effect = RuntimeError("boom")
        with patch.dict("sys.modules", {"csv": csv_mod}):
            assert DocumentParser._parse_csv(b"raw") == "raw"


class TestPdfParser:
    async def test_success(self):
        page = MagicMock()
        page.extract_text.return_value = "page text"
        reader = MagicMock()
        reader.pages = [page, page]
        pypdf_mod = MagicMock()
        pypdf_mod.PdfReader.return_value = reader
        with patch.dict("sys.modules", {"pypdf": pypdf_mod}):
            text = await DocumentParser._parse_pdf(b"x")
        assert text == "page text\n\npage text"

    async def test_import_error(self):
        with patch("builtins.__import__", side_effect=ImportError("no pypdf")):
            text = await DocumentParser._parse_pdf(b"x")
        assert "[PDF content" in text

    async def test_parse_error(self):
        pypdf_mod = MagicMock()
        pypdf_mod.PdfReader.side_effect = RuntimeError("corrupt")
        with patch.dict("sys.modules", {"pypdf": pypdf_mod}):
            assert await DocumentParser._parse_pdf(b"x") == ""


class TestDocxParser:
    async def test_success(self):
        doc = MagicMock()
        para = MagicMock()
        para.text = "para"
        doc.paragraphs = [para]
        cell = MagicMock()
        cell.text = "c1"
        cell2 = MagicMock()
        cell2.text = "c2"
        row = MagicMock()
        row.cells = [cell, cell2]
        table = MagicMock()
        table.rows = [row]
        doc.tables = [table]
        with patch("docx.Document", return_value=doc):
            text = await DocumentParser._parse_docx(b"x")
        assert "para" in text
        assert "c1 | c2" in text

    async def test_import_error(self):
        with patch("builtins.__import__", side_effect=ImportError("no docx")):
            text = await DocumentParser._parse_docx(b"x")
        assert "[DOCX content" in text

    async def test_parse_error(self):
        with patch("docx.Document", side_effect=RuntimeError("corrupt")):
            assert await DocumentParser._parse_docx(b"x") == ""


class TestExcelParser:
    async def test_pandas_success(self):
        df = MagicMock()
        df.to_string.return_value = "1 2"
        xls = MagicMock()
        xls.sheet_names = ["S1"]
        pd = MagicMock()
        pd.ExcelFile.return_value = xls
        pd.read_excel.return_value = df
        with patch.dict("sys.modules", {"pandas": pd}):
            text = await DocumentParser._parse_excel(b"x")
        assert "--- Sheet: S1 ---" in text

    async def test_openpyxl_fallback(self):
        wb = MagicMock()
        wb.sheetnames = ["S1"]
        sheet = MagicMock()
        sheet.iter_rows.return_value = [(1, "a"), (2, "b")]
        wb.__getitem__.return_value = sheet
        openpyxl_mod = MagicMock()
        openpyxl_mod.load_workbook.return_value = wb
        with patch.dict("sys.modules", {"pandas": None, "openpyxl": openpyxl_mod}):
            text = await DocumentParser._parse_excel(b"x")
        assert "=== Sheet: S1 ===" in text
        # row 1 is the header map; data rows carry sheet row numbers
        assert "A=1 | B=a" in text
        assert "R2 | 2 | b" in text

    async def test_no_parser(self):
        with patch.dict("sys.modules", {"pandas": None, "openpyxl": None}):
            text = await DocumentParser._parse_excel(b"x")
        assert "[Excel content" in text

    async def test_parse_error(self):
        pd = MagicMock()
        pd.ExcelFile.side_effect = RuntimeError("corrupt")
        with patch.dict("sys.modules", {"pandas": pd}):
            assert await DocumentParser._parse_excel(b"x") == ""

    async def test_with_formula_extraction(self):
        extractor = MagicMock()
        extractor.extract_from_excel.return_value = [{"formula": "=1+1"}]
        df = MagicMock()
        df.to_string.return_value = ""
        xls = MagicMock()
        xls.sheet_names = []
        pd = MagicMock()
        pd.ExcelFile.return_value = xls
        with patch("core.formula_extractor.get_formula_extractor",
                   return_value=extractor), \
             patch.dict("sys.modules", {"pandas": pd}):
            await DocumentParser._parse_excel(b"x", file_path="/tmp/x.xlsx")
        extractor.extract_from_excel.assert_called_once()


# ---------------------------------------------------------------------------
# Service: settings + process_file_bytes
# ---------------------------------------------------------------------------


class TestSettings:
    def test_get_settings_creates(self):
        svc = make_service()
        settings = svc.get_settings("google_drive")
        assert settings.integration_id == "google_drive"
        assert svc.get_settings("google_drive") is settings

    def test_update_settings_all_fields(self):
        svc = make_service()
        settings = svc.update_settings(
            "dropbox", enabled=True, auto_sync_new_files=False,
            file_types=["pdf"], sync_folders=["/a"], exclude_folders=["/b"],
            max_file_size_mb=10, sync_frequency_minutes=5)
        assert settings.enabled is True
        assert settings.file_types == ["pdf"]
        assert settings.max_file_size_mb == 10
        assert settings.sync_frequency_minutes == 5

    def test_get_all_settings(self):
        svc = make_service()
        svc.update_settings("box", enabled=True)
        all_settings = svc.get_all_settings()
        assert len(all_settings) == 1
        assert all_settings[0]["enabled"] is True


class TestProcessFileBytes:
    async def test_no_extension(self):
        svc = make_service()
        result = await svc.process_file_bytes(b"data", "noext")
        assert result["status"] == "skipped"
        assert result["reason"] == "no_file_extension"

    async def test_parse_failure(self):
        svc = make_service()
        svc.parser = MagicMock()
        svc.parser.parse_document = AsyncMock(side_effect=RuntimeError("boom"))
        result = await svc.process_file_bytes(b"data", "a.pdf")
        assert result["status"] == "error"
        assert result["reason"] == "parse_failed"

    async def test_no_text(self):
        svc = make_service()
        svc.parser = MagicMock()
        svc.parser.parse_document = AsyncMock(return_value="")
        result = await svc.process_file_bytes(b"data", "a.pdf")
        assert result["status"] == "skipped"
        assert result["reason"] == "no_text"

    async def test_redaction(self):
        svc = make_service()
        svc.parser = MagicMock()
        svc.parser.parse_document = AsyncMock(return_value="secret content")
        svc.redactor.redact.return_value = SimpleNamespace(
            has_secrets=True, redacted_text="REDACTED")
        svc.memory_handler.add_document.return_value = True
        result = await svc.process_file_bytes(b"data", "a.txt")
        assert result["status"] == "ingested"
        assert result["chars_ingested"] == 8  # len("REDACTED")
        kwargs = svc.memory_handler.add_document.call_args.kwargs
        assert kwargs["text"] == "REDACTED"
        assert kwargs["metadata"]["source_type"] == "file"

    async def test_redaction_failure_tolerated(self):
        svc = make_service()
        svc.parser = MagicMock()
        svc.parser.parse_document = AsyncMock(return_value="plain")
        svc.redactor.redact.side_effect = RuntimeError("boom")
        svc.memory_handler.add_document.return_value = True
        result = await svc.process_file_bytes(b"data", "a.txt")
        assert result["status"] == "ingested"

    async def test_ingest_failure(self):
        svc = make_service()
        svc.redactor = None
        svc.parser = MagicMock()
        svc.parser.parse_document = AsyncMock(return_value="long enough text")
        svc.memory_handler.add_document.side_effect = RuntimeError("db down")
        result = await svc.process_file_bytes(b"data", "a.txt")
        assert result["status"] == "error"
        assert result["reason"] == "ingest_failed"

    async def test_add_document_false(self):
        svc = make_service()
        svc.redactor = None
        svc.parser = MagicMock()
        svc.parser.parse_document = AsyncMock(return_value="long enough text")
        svc.memory_handler.add_document.return_value = False
        result = await svc.process_file_bytes(b"data", "a.txt")
        assert result["status"] == "skipped"
        assert result["chars_ingested"] == 0

    async def test_no_memory_handler(self):
        svc = make_service()
        svc.redactor = None
        svc.parser = MagicMock()
        svc.parser.parse_document = AsyncMock(return_value="text")
        svc.memory_handler = None
        result = await svc.process_file_bytes(b"data", "a.txt")
        assert result["status"] == "skipped"


# ---------------------------------------------------------------------------
# sync pipeline
# ---------------------------------------------------------------------------


class TestSyncIntegration:
    async def test_not_enabled(self):
        svc = make_service()
        svc.get_settings("google_drive")
        result = await svc.sync_integration("google_drive")
        assert result["skipped"] is True

    async def test_recently_synced(self):
        svc = make_service()
        settings = svc.get_settings("dropbox")
        settings.enabled = True
        settings.last_sync = datetime.now(timezone.utc)
        result = await svc.sync_integration("dropbox")
        assert result["skipped"] is True
        assert "Recently synced" in result["reason"]

    async def test_full_sync_flow(self):
        svc = make_service()
        settings = svc.get_settings("google_drive")
        settings.enabled = True
        settings.file_types = ["pdf", "txt"]

        async def _list(integration_id, settings):
            return [
                {"id": "f1", "name": "a.pdf", "path": "/a.pdf", "size": 100,
                 "modified_at": datetime.now(timezone.utc), "url": "https://x"},
                {"id": "f2", "name": "b.txt", "path": "/b.txt", "size": 50,
                 "modified_at": None},
            ]

        with patch.object(svc, "_list_files", new=_list), \
             patch.object(svc, "_download_file",
                          new=AsyncMock(return_value=b"data")), \
             patch.object(svc, "_persist_freshness_on_ingest"), \
             patch.object(svc, "_maybe_supersede_older_docs"), \
             patch.object(svc, "_reevaluate_workspace",
                          return_value={"summary": "ok"}), \
             patch("core.doc_freshness_service.hash_text",
                   return_value="hash"), \
             patch("core.doc_freshness_service.extra_columns_for_ingest",
                   return_value={}):
            svc.parser = MagicMock()
            svc.parser.parse_document = AsyncMock(return_value="content")
            svc.memory_handler.add_document.return_value = True
            svc.redactor.redact.return_value = SimpleNamespace(
                has_secrets=False, redactions=[])
            result = await svc.sync_integration("google_drive")
        assert result["success"] is True
        assert result["files_found"] == 2
        assert result["files_ingested"] == 2
        assert result["freshness"]["summary"] == "ok"
        assert "f1" in svc.ingested_docs
        assert settings.last_sync is not None

    async def test_skip_unchanged_and_bad_type_and_size(self):
        svc = make_service()
        settings = svc.get_settings("google_drive")
        settings.enabled = True
        settings.file_types = ["pdf"]
        settings.max_file_size_mb = 1
        # Skip-unchanged now ALSO requires the stored hash to carry the
        # current extraction version — a legacy hash means the stored copy
        # predates the current extractor and must be re-downloaded.
        from core.doc_freshness_service import EXTRACTION_VERSION

        svc.ingested_docs["f1"] = make_doc(
            external_id="f1", external_modified_at=datetime.now(timezone.utc),
            source_content_hash=f"ev{EXTRACTION_VERSION}:h1")
        svc.ingested_docs["f2"] = make_doc(external_id="f2")
        files = [
            {"id": "f1", "name": "a.pdf", "size": 10,
             "modified_at": svc.ingested_docs["f1"].external_modified_at},  # unchanged + current extraction
            {"id": "f2", "name": "b.txt", "size": 10},  # wrong type
            {"id": "f3", "name": "c.pdf", "size": 99999999},  # too big
        ]
        with patch.object(svc, "_list_files", return_value=files), \
             patch.object(svc, "_reevaluate_workspace", return_value={}):
            result = await svc.sync_integration("google_drive", force=True)
        assert result["files_skipped"] == 3
        assert result["files_ingested"] == 0

    async def test_modified_doc_marked_stale_then_reingested(self):
        svc = make_service()
        settings = svc.get_settings("dropbox")
        settings.enabled = True
        old_ts = datetime.now(timezone.utc) - timedelta(days=1)
        svc.ingested_docs["f1"] = make_doc(
            external_id="f1", external_modified_at=old_ts)
        files = [{"id": "f1", "name": "a.txt", "path": "/a.txt", "size": 10,
                  "modified_at": datetime.now(timezone.utc)}]
        with patch.object(svc, "_list_files", return_value=files), \
             patch.object(svc, "_download_file",
                          new=AsyncMock(return_value=b"new")), \
             patch.object(svc, "_mark_doc_stale") as stale, \
             patch.object(svc, "_persist_freshness_on_ingest"), \
             patch.object(svc, "_reevaluate_workspace", return_value={}), \
             patch("core.doc_freshness_service.hash_text", return_value="h2"), \
             patch("core.doc_freshness_service.extra_columns_for_ingest",
                   return_value={}):
            svc.parser = MagicMock()
            svc.parser.parse_document = AsyncMock(return_value="new content")
            svc.memory_handler.add_document.return_value = True
            result = await svc.sync_integration("dropbox", force=True)
        stale.assert_called_once()
        assert result["files_ingested"] == 1

    async def test_download_failure_and_parse_empty(self):
        svc = make_service()
        settings = svc.get_settings("google_drive")
        settings.enabled = True
        files = [{"id": "f1", "name": "a.pdf", "size": 10}]
        with patch.object(svc, "_list_files", return_value=files), \
             patch.object(svc, "_download_file",
                          new=AsyncMock(return_value=None)), \
             patch.object(svc, "_reevaluate_workspace", return_value={}):
            result = await svc.sync_integration("google_drive", force=True)
        assert result["files_ingested"] == 0

    async def test_file_error_recorded(self):
        svc = make_service()
        settings = svc.get_settings("google_drive")
        settings.enabled = True
        files = [{"id": "f1", "name": "a.pdf", "size": 10}]
        with patch.object(svc, "_list_files", return_value=files), \
             patch.object(svc, "_download_file",
                          new=AsyncMock(side_effect=RuntimeError("boom"))), \
             patch.object(svc, "_reevaluate_workspace", return_value={}):
            result = await svc.sync_integration("google_drive", force=True)
        assert result["errors"]

    async def test_agent_trigger_on_ingest(self):
        svc = make_service()
        settings = svc.get_settings("google_drive")
        settings.enabled = True
        files = [{"id": "f1", "name": "a.txt", "path": "/a.txt", "size": 10}]
        with patch.object(svc, "_list_files", return_value=files), \
             patch.object(svc, "_download_file",
                          new=AsyncMock(return_value=b"data")), \
             patch.object(svc, "_persist_freshness_on_ingest"), \
             patch.object(svc, "_reevaluate_workspace", return_value={}), \
             patch("core.doc_freshness_service.hash_text", return_value="h"), \
             patch("core.doc_freshness_service.extra_columns_for_ingest",
                   return_value={}), \
             patch("core.atom_meta_agent.handle_data_event_trigger",
                   new=AsyncMock()) as trigger:
            svc.parser = MagicMock()
            svc.parser.parse_document = AsyncMock(return_value="text")
            svc.memory_handler.add_document.return_value = True
            await svc.sync_integration("google_drive", force=True)
        trigger.assert_called_once()

    async def test_outer_exception(self):
        svc = make_service()
        settings = svc.get_settings("google_drive")
        settings.enabled = True
        with patch.object(svc, "_list_files",
                          side_effect=RuntimeError("list exploded")):
            result = await svc.sync_integration("google_drive", force=True)
        assert result["success"] is False
        assert "list exploded" in result["error"]


class TestFreshnessHelpers:
    def test_persist_new_row(self):
        svc = make_service()
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        session.add = MagicMock()
        session.close = MagicMock()
        freshness = MagicMock()
        with patch.object(svc, "_freshness_session", return_value=session), \
             patch("core.models.IngestedDocument",
                   MagicMock(return_value=SimpleNamespace(**{}))), \
             patch("core.doc_freshness_service.DocFreshnessService",
                   return_value=freshness):
            svc._persist_freshness_on_ingest(
                make_doc(), source_url="u", content_hash="h",
                source_modified_at=None)
        session.add.assert_called_once()
        freshness.mark_on_ingest.assert_called_once()

    def test_persist_existing_row(self):
        svc = make_service()
        session = MagicMock()
        existing = SimpleNamespace()
        session.query.return_value.filter.return_value.first.return_value = existing
        session.close = MagicMock()
        freshness = MagicMock()
        with patch.object(svc, "_freshness_session", return_value=session), \
             patch("core.doc_freshness_service.DocFreshnessService",
                   return_value=freshness):
            svc._persist_freshness_on_ingest(
                make_doc(file_name="new.pdf"), source_url="u",
                content_hash="h", source_modified_at=None)
        assert existing.file_name == "new.pdf"
        session.add.assert_not_called()

    def test_mark_doc_stale(self):
        svc = make_service()
        session = MagicMock()
        row = SimpleNamespace()
        session.query.return_value.filter.return_value.first.return_value = row
        session.close = MagicMock()
        freshness = MagicMock()
        with patch.object(svc, "_freshness_session", return_value=session), \
             patch("core.doc_freshness_service.DocFreshnessService",
                   return_value=freshness):
            doc = make_doc()
            svc._mark_doc_stale(doc, reason="source_modified_at_changed")
        assert doc.freshness_status == "stale"
        freshness.mark_stale.assert_called_once()

    def test_mark_doc_stale_no_row(self):
        svc = make_service()
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        session.close = MagicMock()
        with patch.object(svc, "_freshness_session", return_value=session):
            svc._mark_doc_stale(make_doc(), reason="x")  # no crash

    def test_reevaluate_workspace(self):
        svc = make_service()
        session = MagicMock()
        session.close = MagicMock()
        freshness = MagicMock()
        freshness.reevaluate_workspace.return_value = SimpleNamespace(
            as_dict=lambda: {"stale": 2})
        with patch.object(svc, "_freshness_session", return_value=session), \
             patch("core.doc_freshness_service.DocFreshnessService",
                   return_value=freshness):
            result = svc._reevaluate_workspace({"f1"})
        assert result == {"stale": 2}

    def test_supersede_no_older_rows(self):
        svc = make_service()
        session = MagicMock()
        session.query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        session.close = MagicMock()
        with patch.object(svc, "_freshness_session", return_value=session):
            svc._maybe_supersede_older_docs(text="t", new_doc_id="d1",
                                            source_modified_at=None)

    def test_supersede_with_candidates(self):
        svc = make_service()
        session = MagicMock()
        old_row = SimpleNamespace(
            id="old-1", content_preview="old text",
            ingested_at=datetime.now(timezone.utc),
            external_modified_at=None, source_modified_at=None,
            freshness_status="fresh")
        session.query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [old_row]
        session.close = MagicMock()
        freshness = MagicMock()
        freshness.entity_set_for_doc.return_value = {"a"}
        freshness.cascade_graph_supersession = True
        with patch.object(svc, "_freshness_session", return_value=session), \
             patch("core.doc_freshness_service.DocFreshnessService",
                   return_value=freshness), \
             patch("core.doc_freshness_service.detect_supersession",
                   return_value=[{"doc_id": "old-1"}]), \
             patch("core.doc_freshness_service.doc_ts",
                   return_value=None):
            svc.memory_handler.embed_text.return_value = [0.1, 0.2]
            svc._maybe_supersede_older_docs(
                text="new text", new_doc_id="new-1",
                source_modified_at=datetime.now(timezone.utc))
        freshness.apply_supersession.assert_called_once()


# ---------------------------------------------------------------------------
# fetchers + module functions
# ---------------------------------------------------------------------------


class TestFetchers:
    async def test_list_files_dispatcher(self):
        svc = make_service()
        settings = svc.get_settings("google_drive")
        with patch.object(svc, "_list_google_drive_files",
                          new=AsyncMock(return_value=[{"id": 1}])):
            assert await svc._list_files("google_drive", settings) == [{"id": 1}]
        with patch.object(svc, "_list_dropbox_files",
                          new=AsyncMock(return_value=[])):
            assert await svc._list_files("dropbox", settings) == []
        with patch.object(svc, "_list_onedrive_files",
                          new=AsyncMock(return_value=[])):
            assert await svc._list_files("onedrive", settings) == []
        with patch.object(svc, "_list_notion_pages",
                          new=AsyncMock(return_value=[])):
            assert await svc._list_files("notion", settings) == []
        assert await svc._list_files("unknown", settings) == []
        with patch.object(svc, "_list_google_drive_files",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert await svc._list_files("google_drive", settings) == []

    async def test_download_dispatcher(self):
        svc = make_service()
        with patch.object(svc, "_download_google_drive_file",
                          new=AsyncMock(return_value=b"x")):
            assert await svc._download_file("google_drive", {}) == b"x"
        with patch.object(svc, "_download_dropbox_file",
                          new=AsyncMock(return_value=b"y")):
            assert await svc._download_file("dropbox", {}) == b"y"
        assert await svc._download_file("unknown", {}) is None
        with patch.object(svc, "_download_google_drive_file",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert await svc._download_file("google_drive", {}) is None

    async def test_google_drive_list(self, monkeypatch):
        svc = make_service()
        settings = svc.get_settings("google_drive")
        monkeypatch.delenv("GOOGLE_DRIVE_ACCESS_TOKEN", raising=False)
        assert await svc._list_google_drive_files(settings) == []

        monkeypatch.setenv("GOOGLE_DRIVE_ACCESS_TOKEN", "tok")
        service = MagicMock()
        service.list_files = AsyncMock(return_value={
            "status": "success", "data": {"files": [{"id": "f1"}]}})
        with patch("integrations.google_drive_service.google_drive_service",
                   service):
            files = await svc._list_google_drive_files(settings)
        assert files == [{"id": "f1"}]

        service.list_files = AsyncMock(return_value={
            "status": "error", "message": "nope"})
        with patch("integrations.google_drive_service.google_drive_service",
                   service):
            assert await svc._list_google_drive_files(settings) == []
        monkeypatch.delenv("GOOGLE_DRIVE_ACCESS_TOKEN")

    async def test_google_drive_download(self, monkeypatch):
        svc = make_service()
        monkeypatch.delenv("GOOGLE_DRIVE_ACCESS_TOKEN", raising=False)
        assert await svc._download_google_drive_file({}) is None

        monkeypatch.setenv("GOOGLE_DRIVE_ACCESS_TOKEN", "tok")
        assert await svc._download_google_drive_file({}) is None  # no id

        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.content = b"drive-bytes"
        client.get = AsyncMock(return_value=response)
        httpx_mod = MagicMock()
        httpx_mod.AsyncClient.return_value = client
        with patch.dict("sys.modules", {"httpx": httpx_mod}):
            result = await svc._download_google_drive_file(
                {"id": "f1", "mimeType": "application/vnd.google-apps.document"})
            assert result == b"drive-bytes"
            export_url = client.get.call_args.args[0]
            assert "/export" in export_url

            result = await svc._download_google_drive_file(
                {"id": "f2", "mimeType": "application/pdf"})
            assert result == b"drive-bytes"
            assert "alt=media" in client.get.call_args.args[0]
        monkeypatch.delenv("GOOGLE_DRIVE_ACCESS_TOKEN")

    async def test_dropbox_list(self, monkeypatch):
        svc = make_service()
        settings = svc.get_settings("dropbox")
        monkeypatch.delenv("DROPBOX_ACCESS_TOKEN", raising=False)
        assert await svc._list_dropbox_files(settings) == []

        monkeypatch.setenv("DROPBOX_ACCESS_TOKEN", "tok")
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {"entries": [
            {".tag": "file", "id": "f1", "name": "a.txt"},
            {".tag": "folder", "id": "d1"},
        ]}
        client.post = AsyncMock(return_value=response)
        httpx_mod = MagicMock()
        httpx_mod.AsyncClient.return_value = client
        with patch.dict("sys.modules", {"httpx": httpx_mod}):
            files = await svc._list_dropbox_files(settings)
        assert len(files) == 1
        assert files[0]["id"] == "f1"
        monkeypatch.delenv("DROPBOX_ACCESS_TOKEN")

    async def test_dropbox_download(self, monkeypatch):
        svc = make_service()
        monkeypatch.delenv("DROPBOX_ACCESS_TOKEN", raising=False)
        assert await svc._download_dropbox_file({}) is None

        monkeypatch.setenv("DROPBOX_ACCESS_TOKEN", "tok")
        assert await svc._download_dropbox_file({}) is None  # no path

        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        link_response = MagicMock()
        link_response.raise_for_status = MagicMock()
        link_response.json.return_value = {"link": "https://dl.dropbox.com/x"}
        content_response = MagicMock()
        content_response.raise_for_status = MagicMock()
        content_response.content = b"dropbox-bytes"
        client.post = AsyncMock(return_value=link_response)
        client.get = AsyncMock(return_value=content_response)
        httpx_mod = MagicMock()
        httpx_mod.AsyncClient.return_value = client
        with patch.dict("sys.modules", {"httpx": httpx_mod}):
            result = await svc._download_dropbox_file({"path_lower": "/a.txt"})
        assert result == b"dropbox-bytes"
        monkeypatch.delenv("DROPBOX_ACCESS_TOKEN")

    async def test_stubs(self):
        svc = make_service()
        settings = svc.get_settings("onedrive")
        assert await svc._list_onedrive_files(settings) == []
        assert await svc._download_onedrive_file({}) is None
        assert await svc._list_notion_pages(settings) == []
        assert await svc._download_notion_content({}) is None


class TestDocumentsAndModule:
    def test_get_ingested_documents(self):
        svc = make_service()
        svc.ingested_docs["a"] = make_doc(external_id="a", file_type="pdf")
        svc.ingested_docs["b"] = make_doc(external_id="b", file_type="txt")
        assert len(svc.get_ingested_documents()) == 2
        assert len(svc.get_ingested_documents(integration_id="google_drive")) == 2
        assert len(svc.get_ingested_documents(file_type="txt")) == 1

    async def test_remove_integration_documents(self):
        svc = make_service()
        svc.ingested_docs["a"] = make_doc(external_id="a", integration_id="dropbox")
        svc.ingested_docs["b"] = make_doc(external_id="b", integration_id="google_drive")
        result = await svc.remove_integration_documents("dropbox")
        assert result["documents_removed"] == 1
        assert "a" not in svc.ingested_docs

    def test_get_service_singleton(self):
        from core import auto_document_ingestion as adi
        adi._doc_ingestion_service = None
        s1 = get_document_ingestion_service()
        s2 = get_document_ingestion_service()
        assert s1 is s2
        adi._doc_ingestion_service = None

    def test_alias_and_enums(self):
        assert AutoDocumentIngestion is AutoDocumentIngestionService
        assert FileType.PDF.value == "pdf"
        assert IntegrationSource.GOOGLE_DRIVE.value == "google_drive"
