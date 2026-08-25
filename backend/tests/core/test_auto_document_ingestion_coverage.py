"""
Coverage tests for auto_document_ingestion.py.

Target: 60%+ coverage (468 statements, ~281 lines to cover)
Focus: Document parsing, chunking, metadata extraction, embedding
"""
import asyncio
from contextlib import contextmanager
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
import io
import types

from core.auto_document_ingestion import (
    AutoDocumentIngestionService,
    DocumentParser,
    FileType,
    IntegrationSource,
    IngestionSettings,
    IngestedDocument,
    get_document_ingestion_service,
)


def _fake_module(name: str, **attrs) -> types.ModuleType:
    """Build a fake module object for sys.modules injection."""
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _make_sync_service() -> AutoDocumentIngestionService:
    """Build a service whose storage boundaries are mocked."""
    service = AutoDocumentIngestionService()
    service.redactor = None
    service.memory_handler = MagicMock()
    service.memory_handler.add_document.return_value = True
    return service


@contextmanager
def _patched_sync(service, files, download_error=None):
    """Patch the sync loop boundaries (list/download/parse/persist/trigger)."""
    if download_error is None:
        download = AsyncMock(return_value=b"file content")
    else:
        download = AsyncMock(side_effect=download_error)
    with patch.object(service, "_list_files", new=AsyncMock(return_value=files)), \
         patch.object(service, "_download_file", new=download), \
         patch.object(DocumentParser, "parse_document", new=AsyncMock(return_value="Parsed text content")), \
         patch.object(service, "_persist_freshness_on_ingest"), \
         patch.object(service, "_maybe_supersede_older_docs"), \
         patch.object(service, "_reevaluate_workspace", return_value={}), \
         patch("core.atom_meta_agent.handle_data_event_trigger", new=AsyncMock()):
        yield


class TestFileType:
    """Test file type enumeration."""

    def test_file_type_values(self):
        """Test file type enum values."""
        assert FileType.PDF == "pdf"
        assert FileType.DOCX == "docx"
        assert FileType.TXT == "txt"
        assert FileType.CSV == "csv"
        assert FileType.EXCEL == "xlsx"
        assert FileType.MARKDOWN == "md"


class TestIntegrationSource:
    """Test integration source enumeration."""

    def test_integration_source_values(self):
        """Test integration source enum values."""
        assert IntegrationSource.GOOGLE_DRIVE == "google_drive"
        assert IntegrationSource.DROPBOX == "dropbox"
        assert IntegrationSource.ONEDRIVE == "onedrive"
        assert IntegrationSource.LOCAL == "local"


class TestIngestionSettings:
    """Test ingestion settings configuration."""

    def test_create_default_settings(self):
        """Test creating ingestion settings with defaults."""
        settings = IngestionSettings(
            integration_id="test-integration",
            workspace_id="test-workspace"
        )
        assert settings.integration_id == "test-integration"
        assert settings.workspace_id == "test-workspace"
        assert settings.enabled is False
        assert settings.auto_sync_new_files is True
        assert settings.file_types == ["pdf", "docx", "txt", "md"]

    def test_create_custom_settings(self):
        """Test creating ingestion settings with custom values."""
        settings = IngestionSettings(
            integration_id="test-integration",
            workspace_id="test-workspace",
            enabled=True,
            file_types=["pdf", "xlsx"],
            max_file_size_mb=100,
            sync_frequency_minutes=30
        )
        assert settings.enabled is True
        assert settings.file_types == ["pdf", "xlsx"]
        assert settings.max_file_size_mb == 100
        assert settings.sync_frequency_minutes == 30


class TestIngestedDocument:
    """Test ingested document record."""

    def test_create_ingested_document(self):
        """Test creating ingested document record."""
        doc = IngestedDocument(
            id="doc1",
            file_name="test.pdf",
            file_path="/path/to/test.pdf",
            file_type="pdf",
            integration_id="google-drive",
            workspace_id="workspace1",
            file_size_bytes=1024,
            content_preview="This is a preview...",
            ingested_at=datetime.now(timezone.utc),
            external_id="external123"
        )
        assert doc.id == "doc1"
        assert doc.file_name == "test.pdf"
        assert doc.file_type == "pdf"
        assert doc.integration_id == "google-drive"

    def test_ingested_document_with_external_modified(self):
        """Test ingested document with external modification time."""
        modified_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        doc = IngestedDocument(
            id="doc1",
            file_name="test.pdf",
            file_path="/path/to/test.pdf",
            file_type="pdf",
            integration_id="google-drive",
            workspace_id="workspace1",
            file_size_bytes=1024,
            content_preview="Preview",
            ingested_at=datetime.now(timezone.utc),
            external_id="external123",
            external_modified_at=modified_time
        )
        assert doc.external_modified_at == modified_time


class TestDocumentParser:
    """Test document parsing functionality."""

    @pytest.mark.asyncio
    async def test_parse_text_document(self):
        """Test parsing plain text document."""
        content = b"This is plain text content"
        result = await DocumentParser.parse_document(content, "txt", "test.txt")
        assert "plain text content" in result

    @pytest.mark.asyncio
    async def test_parse_markdown_document(self):
        """Test parsing markdown document."""
        content = b"# Heading\n\nContent here"
        result = await DocumentParser.parse_document(content, "md", "test.md")
        assert "Heading" in result
        assert "Content" in result

    @pytest.mark.asyncio
    async def test_parse_json_document(self):
        """Test parsing JSON document."""
        content = b'{"key": "value", "number": 123}'
        result = await DocumentParser.parse_document(content, "json", "test.json")
        assert '"key"' in result
        assert '"value"' in result

    @pytest.mark.asyncio
    async def test_parse_csv_document(self):
        """Test parsing CSV document."""
        content = b"Name,Age,City\nAlice,30,NYC\nBob,25,LA"
        result = await DocumentParser.parse_document(content, "csv", "test.csv")
        assert "Name" in result
        assert "Alice" in result
        assert "NYC" in result

    @pytest.mark.asyncio
    async def test_parse_pdf_with_pypdf2(self):
        """Test parsing PDF with pypdf (PyPDF2 successor)."""
        pdf_content = b"%PDF-1.4\nfake pdf content"

        mock_pypdf = _fake_module("pypdf")
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "PDF text content"
        mock_reader.pages = [mock_page]
        mock_pypdf.PdfReader = MagicMock(return_value=mock_reader)

        with patch.dict("sys.modules", {"pypdf": mock_pypdf}):
            result = await DocumentParser.parse_document(pdf_content, "pdf", "test.pdf")
            assert "PDF text content" in result

    @pytest.mark.asyncio
    async def test_parse_pdf_with_fallback(self):
        """Test PDF parsing falls back to pypdf when docling fails."""
        pdf_content = b"%PDF-1.4\nfake pdf content"

        mock_docling = AsyncMock()
        mock_docling.process_document.side_effect = RuntimeError("docling failed")

        mock_pypdf = _fake_module("pypdf")
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Fallback PDF text"
        mock_reader.pages = [mock_page]
        mock_pypdf.PdfReader = MagicMock(return_value=mock_reader)

        with patch.object(DocumentParser, '_get_docling_processor', return_value=mock_docling), \
             patch.dict("sys.modules", {"pypdf": mock_pypdf}):
            result = await DocumentParser.parse_document(pdf_content, "pdf", "test.pdf")
            assert "Fallback PDF text" in result

    @pytest.mark.asyncio
    async def test_parse_pdf_no_parser_available(self):
        """Test parsing PDF when no parser is available."""
        pdf_content = b"%PDF-1.4\nfake pdf content"

        with patch.dict("sys.modules", {"pypdf": None}):
            result = await DocumentParser.parse_document(pdf_content, "pdf", "test.pdf")
            assert "parser not available" in result

    @pytest.mark.asyncio
    async def test_parse_docx_document(self):
        """Test parsing DOCX document."""
        docx_content = b"PK\x03\x04"  # DOCX zip header

        mock_docx = _fake_module("docx")
        mock_doc = MagicMock()
        mock_para1 = MagicMock()
        mock_para1.text = "Paragraph 1"
        mock_para2 = MagicMock()
        mock_para2.text = "Paragraph 2"
        mock_doc.paragraphs = [mock_para1, mock_para2]
        mock_doc.tables = []
        mock_docx.Document = MagicMock(return_value=mock_doc)

        with patch.dict("sys.modules", {"docx": mock_docx}):
            result = await DocumentParser.parse_document(docx_content, "docx", "test.docx")
            assert "Paragraph 1" in result
            assert "Paragraph 2" in result

    @pytest.mark.asyncio
    async def test_parse_docx_no_parser_available(self):
        """Test parsing DOCX when no parser is available."""
        docx_content = b"fake docx content"

        with patch.dict("sys.modules", {"docx": None}):
            result = await DocumentParser.parse_document(docx_content, "docx", "test.docx")
            assert "parser not available" in result

    @pytest.mark.asyncio
    async def test_parse_excel_document(self):
        """Test parsing Excel document."""
        excel_content = b"PK\x03\x04"  # Excel zip header

        mock_pd = _fake_module("pandas")
        mock_xls = MagicMock()
        mock_xls.sheet_names = ["Sheet1", "Sheet2"]
        mock_pd.ExcelFile = MagicMock(return_value=mock_xls)
        mock_df = MagicMock()
        mock_df.to_string.return_value = "1 Alice 30 NYC"
        mock_pd.read_excel = MagicMock(return_value=mock_df)

        with patch.dict("sys.modules", {"pandas": mock_pd}):
            result = await DocumentParser.parse_document(excel_content, "xlsx", "test.xlsx")
            assert "Sheet" in result

    @pytest.mark.asyncio
    async def test_parse_excel_with_openpyxl_fallback(self):
        """Test parsing Excel with openpyxl fallback."""
        excel_content = b"fake excel content"

        mock_openpyxl = _fake_module("openpyxl")
        mock_wb = MagicMock()
        mock_sheet = MagicMock()
        mock_row = ["Cell1", "Cell2"]
        mock_sheet.iter_rows.return_value = [mock_row]
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = MagicMock(return_value=mock_sheet)
        mock_openpyxl.load_workbook = MagicMock(return_value=mock_wb)

        with patch.dict("sys.modules", {"pandas": None, "openpyxl": mock_openpyxl}):
            result = await DocumentParser.parse_document(excel_content, "xlsx", "test.xlsx")
            assert "Sheet1" in result

    @pytest.mark.asyncio
    async def test_parse_unsupported_file_type(self):
        """Test parsing unsupported file type."""
        content = b"some content"
        result = await DocumentParser.parse_document(content, "xyz", "test.xyz")
        assert result == ""

    @pytest.mark.asyncio
    async def test_parse_with_docling_available(self):
        """Test parsing with docling processor available."""
        content = b"document content"

        with patch.object(DocumentParser, '_get_docling_processor') as mock_get_docling:
            mock_docling = AsyncMock()
            mock_docling.process_document.return_value = {
                "success": True,
                "content": "Docling parsed content",
                "total_chars": 100
            }
            mock_get_docling.return_value = mock_docling

            result = await DocumentParser.parse_document(content, "pdf", "test.pdf")
            assert "Docling parsed content" in result

    @pytest.mark.asyncio
    async def test_parse_with_docling_fallback_on_failure(self):
        """Test fallback to legacy parsers when docling fails."""
        content = b"document content"

        with patch.object(DocumentParser, '_get_docling_processor') as mock_get_docling:
            mock_docling = AsyncMock()
            mock_docling.process_document.return_value = {
                "success": False,
                "content": None
            }
            mock_get_docling.return_value = mock_docling

            # For markdown, should fallback to simple decode
            result = await DocumentParser.parse_document(content, "md", "test.md")
            assert "document content" in result

    def test_parse_csv_with_formula_extraction(self):
        """Test CSV parsing with formula extraction."""
        csv_content = b"Value,Result\n10,=A1*2\n20,=A2*2"

        with patch('core.formula_extractor.get_formula_extractor') as mock_get_extractor:
            mock_extractor = MagicMock()
            mock_extractor.extract_from_csv.return_value = [{"formula": "=A1*2"}]
            mock_get_extractor.return_value = mock_extractor

            result = DocumentParser._parse_csv(csv_content, file_path="/path/to/test.csv")
            assert "Value" in result
            assert "10" in result

    def test_parse_csv_formula_extraction_error(self):
        """Test CSV parsing handles formula extraction errors gracefully."""
        csv_content = b"Value\n10\n20"

        with patch('core.formula_extractor.get_formula_extractor') as mock_get_extractor:
            mock_extractor = MagicMock()
            mock_extractor.extract_from_csv.side_effect = Exception("Extraction failed")
            mock_get_extractor.return_value = mock_extractor

            # Should not raise exception, should log warning and continue
            result = DocumentParser._parse_csv(csv_content, file_path="/path/to/test.csv")
            assert "Value" in result

    def test_parse_csv_with_large_file(self):
        """Test CSV parsing truncates large files."""
        # Create CSV with more than 1000 rows
        rows = ["Row1,Row2"] + [f"Value{i},Data{i}" for i in range(2000)]
        csv_content = "\n".join(rows).encode()

        result = DocumentParser._parse_csv(csv_content)
        assert "Row1" in result
        assert "... (truncated)" in result

    def test_parse_excel_with_formula_extraction(self):
        """Test Excel parsing with formula extraction."""
        excel_content = b"PK\x03\x04"

        mock_pd = _fake_module("pandas")
        mock_xls = MagicMock()
        mock_xls.sheet_names = ["Sheet1"]
        mock_pd.ExcelFile = MagicMock(return_value=mock_xls)
        mock_df = MagicMock()
        mock_df.to_string.return_value = "1 Alice 30 NYC"
        mock_pd.read_excel = MagicMock(return_value=mock_df)

        with patch('core.formula_extractor.get_formula_extractor') as mock_get_extractor, \
             patch.dict("sys.modules", {"pandas": mock_pd}):
            mock_extractor = MagicMock()
            mock_extractor.extract_from_excel.return_value = [{"formula": "=SUM(A1:A10)"}]
            mock_get_extractor.return_value = mock_extractor

            # Should call formula extraction
            result = asyncio.run(DocumentParser._parse_excel(excel_content, file_path="/path/to/test.xlsx"))
            assert "Sheet1" in result


class TestAutoDocumentIngestionService:
    """Test document ingestion service."""

    def setup_method(self):
        """Setup test service."""
        self.service = AutoDocumentIngestionService()

    def test_create_service(self):
        """Test creating ingestion service."""
        service = AutoDocumentIngestionService()
        assert service is not None

    def test_get_or_create_settings(self):
        """Test getting or creating ingestion settings."""
        settings = self.service.get_settings(integration_id="test-integration")
        assert isinstance(settings, IngestionSettings)
        assert settings.integration_id == "test-integration"
        assert settings.workspace_id == "default"

    def test_update_settings(self):
        """Test updating ingestion settings."""
        settings = self.service.update_settings(
            integration_id="test-integration",
            enabled=True,
            file_types=["pdf"],
            max_file_size_mb=200
        )
        assert settings.enabled is True
        assert settings.file_types == ["pdf"]
        assert settings.max_file_size_mb == 200

    @pytest.mark.asyncio
    async def test_should_sync_file_type(self):
        """Test that sync skips files whose type is not enabled."""
        service = _make_sync_service()
        service.settings["test"] = IngestionSettings(
            integration_id="test",
            workspace_id="default",
            enabled=True,
            file_types=["pdf", "docx"]
        )

        files = [
            {"id": "f1", "name": "doc.pdf", "size": 1024},
            {"id": "f2", "name": "notes.txt", "size": 1024},
        ]

        with _patched_sync(service, files):
            result = await service.sync_integration("test", force=True)
        assert result["files_ingested"] == 1
        assert result["files_skipped"] == 1

    @pytest.mark.asyncio
    async def test_should_sync_file_size(self):
        """Test that sync skips files over the max size."""
        service = _make_sync_service()
        service.settings["test"] = IngestionSettings(
            integration_id="test",
            workspace_id="default",
            enabled=True,
            max_file_size_mb=10
        )

        files = [
            {"id": "small", "name": "small.txt", "size": 5 * 1024 * 1024},
            {"id": "large", "name": "large.txt", "size": 15 * 1024 * 1024},
        ]

        with _patched_sync(service, files):
            result = await service.sync_integration("test", force=True)
        assert result["files_ingested"] == 1
        assert result["files_skipped"] == 1

    @pytest.mark.asyncio
    async def test_should_sync_folder(self):
        """Test that files inside configured sync folders are ingested."""
        service = _make_sync_service()
        service.settings["test"] = IngestionSettings(
            integration_id="test",
            workspace_id="default",
            enabled=True,
            sync_folders=["/documents", "/reports"],
            exclude_folders=["/documents/archive"]
        )

        files = [
            {"id": "f1", "name": "doc.pdf", "path": "/documents/file.pdf", "size": 1024},
        ]

        with _patched_sync(service, files):
            result = await service.sync_integration("test", force=True)
        assert result["files_ingested"] == 1

    @pytest.mark.asyncio
    async def test_should_sync_folder_all_allowed(self):
        """Test that files are ingested regardless of folder when none excluded."""
        service = _make_sync_service()
        service.settings["test"] = IngestionSettings(
            integration_id="test",
            workspace_id="default",
            enabled=True,
            exclude_folders=["/tmp"]
        )

        files = [
            {"id": "f1", "name": "doc.pdf", "path": "/documents/file.pdf", "size": 1024},
            {"id": "f2", "name": "tmp.pdf", "path": "/tmp/file.pdf", "size": 1024},
        ]

        with _patched_sync(service, files):
            result = await service.sync_integration("test", force=True)
        assert result["files_ingested"] == 2

    @pytest.mark.asyncio
    async def test_ingest_document(self):
        """Test ingesting a document."""
        service = self.service
        service.redactor = None
        service.memory_handler = MagicMock()
        service.memory_handler.add_document.return_value = True
        # Workspace override selects a per-workspace handler — seed the cache
        # so the injected mock serves "test-workspace".
        service._ws_handlers = {"test-workspace": service.memory_handler}
        content = b"# Test Document\n\nThis is test content."

        result = await service.process_file_bytes(
            content=content,
            file_name="test.md",
            source="local",
            workspace_id="test-workspace"
        )

        assert result["status"] == "ingested"
        assert result["chars_ingested"] > 0

    @pytest.mark.asyncio
    async def test_ingest_document_unsupported_type(self):
        """Test ingesting document with unsupported type."""
        content = b"some content"

        result = await self.service.process_file_bytes(
            content=content,
            file_name="test.xyz",
            source="local",
            workspace_id="test-workspace"
        )

        # Unsupported type yields no text, so the file is skipped
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_ingest_document_too_large(self):
        """Test that sync skips documents that are too large."""
        service = _make_sync_service()
        service.settings["local"] = IngestionSettings(
            integration_id="local",
            workspace_id="default",
            enabled=True,
            max_file_size_mb=10
        )

        files = [
            {"id": "small", "name": "small.txt", "size": 5 * 1024 * 1024},
            {"id": "big", "name": "big.txt", "size": 15 * 1024 * 1024},
        ]

        with _patched_sync(service, files):
            result = await service.sync_integration("local", force=True)
        assert result["files_ingested"] == 1
        assert result["files_skipped"] == 1

    @pytest.mark.asyncio
    async def test_batch_ingest_documents(self):
        """Test batch ingesting multiple documents via sync."""
        service = _make_sync_service()
        service.settings["local"] = IngestionSettings(
            integration_id="local",
            workspace_id="default",
            enabled=True
        )

        files = [
            {"id": "ext1", "name": "doc1.txt", "size": 100},
            {"id": "ext2", "name": "doc2.txt", "size": 100},
        ]

        with _patched_sync(service, files):
            result = await service.sync_integration("local", force=True)
        assert result["files_ingested"] == 2
        assert len(result["newly_ingested_files"]) == 2

    def test_get_ingested_documents(self):
        """Test getting list of ingested documents."""
        # Add some test documents
        self.service.ingested_docs["ext1"] = IngestedDocument(
            id="doc1",
            file_name="test1.pdf",
            file_path="/path/test1.pdf",
            file_type="pdf",
            integration_id="local",
            workspace_id="test-workspace",
            file_size_bytes=1024,
            content_preview="Preview 1",
            ingested_at=datetime.now(timezone.utc),
            external_id="ext1"
        )

        self.service.ingested_docs["ext2"] = IngestedDocument(
            id="doc2",
            file_name="test2.pdf",
            file_path="/path/test2.pdf",
            file_type="pdf",
            integration_id="local",
            workspace_id="test-workspace",
            file_size_bytes=2048,
            content_preview="Preview 2",
            ingested_at=datetime.now(timezone.utc),
            external_id="ext2"
        )

        docs = self.service.get_ingested_documents(integration_id="local")

        assert len(docs) == 2

    def test_get_document_by_external_id(self):
        """Test looking up a document by its external ID."""
        doc = IngestedDocument(
            id="doc1",
            file_name="test.pdf",
            file_path="/path/test.pdf",
            file_type="pdf",
            integration_id="local",
            workspace_id="test-workspace",
            file_size_bytes=1024,
            content_preview="Preview",
            ingested_at=datetime.now(timezone.utc),
            external_id="external123"
        )

        self.service.ingested_docs["external123"] = doc

        found = self.service.ingested_docs["external123"]

        assert found is not None
        assert found.file_name == "test.pdf"

    @pytest.mark.asyncio
    async def test_delete_document(self):
        """Test removing ingested documents for an integration."""
        doc = IngestedDocument(
            id="doc1",
            file_name="test.pdf",
            file_path="/path/test.pdf",
            file_type="pdf",
            integration_id="local",
            workspace_id="test-workspace",
            file_size_bytes=1024,
            content_preview="Preview",
            ingested_at=datetime.now(timezone.utc),
            external_id="external123"
        )

        self.service.ingested_docs["external123"] = doc

        deleted = await self.service.remove_integration_documents("local")
        assert deleted["success"] is True
        assert deleted["documents_removed"] == 1
        assert "external123" not in self.service.ingested_docs

    def test_get_sync_status(self):
        """Test getting sync status for integration."""
        settings = IngestionSettings(
            integration_id="local",
            workspace_id="test-workspace",
            enabled=True,
            last_sync=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )

        self.service.settings["local"] = settings

        status = next(
            s for s in self.service.get_all_settings()
            if s["integration_id"] == "local"
        )

        assert status["enabled"] is True
        assert "last_sync" in status


class TestDocumentIngestionIntegration:
    """Test integration scenarios for document ingestion."""

    def setup_method(self):
        """Setup test service."""
        self.service = AutoDocumentIngestionService()

    @pytest.mark.asyncio
    async def test_full_ingestion_workflow(self):
        """Test complete ingestion workflow."""
        service = self.service
        service.redactor = None
        service.memory_handler = MagicMock()
        service.memory_handler.add_document.return_value = True
        content = b"# Test Document\n\nImportant content here."

        # Workspace override selects a per-workspace handler — seed the cache
        # so the injected mock serves "test-workspace".
        service._ws_handlers = {"test-workspace": service.memory_handler}

        # Ingest document
        result = await service.process_file_bytes(
            content=content,
            file_name="test.md",
            source="local",
            workspace_id="test-workspace"
        )

        assert result["status"] == "ingested"

        # Verify document was stored in memory
        service.memory_handler.add_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_integration_source(self):
        """Test syncing files from integration source."""
        service = _make_sync_service()
        service.settings["google-drive"] = IngestionSettings(
            integration_id="google-drive",
            workspace_id="default",
            enabled=True
        )

        # Mock file list from integration
        files = [
            {
                "id": "file1",
                "name": "doc1.pdf",
                "size": 1024,
                "modified_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            },
            {
                "id": "file2",
                "name": "doc2.pdf",
                "size": 2048,
                "modified_at": datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
            }
        ]

        with _patched_sync(service, files):
            result = await service.sync_integration("google-drive", force=True)
        assert result["files_ingested"] == 2

    def test_calculate_sync_frequency(self):
        """Test calculating sync frequency based on settings."""
        settings = IngestionSettings(
            integration_id="test",
            workspace_id="test",
            sync_frequency_minutes=60
        )

        # Should sync every 60 minutes
        assert settings.sync_frequency_minutes == 60

    @pytest.mark.asyncio
    async def test_check_should_sync(self):
        """Test checking if sync should run based on last sync time."""
        settings = IngestionSettings(
            integration_id="test",
            workspace_id="test",
            enabled=True,
            sync_frequency_minutes=60,
            last_sync=datetime.now(timezone.utc) - timedelta(minutes=10)
        )

        self.service.settings["test"] = settings

        # 10 minutes elapsed < 60 minute frequency -> sync skipped
        result = await self.service.sync_integration("test")
        assert result["skipped"] is True
        assert result["reason"] == "Recently synced"


class TestErrorHandling:
    """Test error handling in document ingestion."""

    def setup_method(self):
        """Setup test service."""
        self.service = AutoDocumentIngestionService()

    @pytest.mark.asyncio
    async def test_handle_corrupted_file(self):
        """Test handling corrupted file."""
        content = b"corrupted pdf content"

        with patch.object(DocumentParser, 'parse_document', new=AsyncMock(side_effect=Exception("File corrupted"))):
            result = await self.service.process_file_bytes(
                content=content,
                file_name="corrupted.pdf",
                source="local",
                workspace_id="test-workspace"
            )

            assert result["status"] == "error"
            assert result["reason"] == "parse_failed"

    @pytest.mark.asyncio
    async def test_handle_empty_file(self):
        """Test handling empty file."""
        content = b""

        result = await self.service.process_file_bytes(
            content=content,
            file_name="empty.txt",
            source="local",
            workspace_id="test-workspace"
        )

        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_handle_network_timeout(self):
        """Test handling network timeout during sync."""
        service = _make_sync_service()
        service.settings["google-drive"] = IngestionSettings(
            integration_id="google-drive",
            workspace_id="default",
            enabled=True
        )

        files = [
            {"id": "file1", "name": "doc1.pdf", "size": 1024},
        ]

        with _patched_sync(service, files, download_error=asyncio.TimeoutError("Network timeout")):
            result = await service.sync_integration("google-drive", force=True)

        # Timeout is recorded per-file and sync continues gracefully
        assert result["success"] is True
        assert len(result["errors"]) == 1


def test_get_document_ingestion_service():
    """Test getting singleton document ingestion service."""
    service1 = get_document_ingestion_service()
    service2 = get_document_ingestion_service()

    # Should return same instance
    assert service1 is service2
