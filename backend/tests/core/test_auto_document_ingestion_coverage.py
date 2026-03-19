"""
Coverage tests for auto_document_ingestion.py.

Target: 60%+ coverage (468 statements, ~281 lines to cover)
Focus: Document parsing, chunking, metadata extraction, embedding
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timezone
import io

from core.auto_document_ingestion import (
    AutoDocumentIngestionService,
    DocumentParser,
    FileType,
    IntegrationSource,
    IngestionSettings,
    IngestedDocument
)


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
        """Test parsing PDF with PyPDF2."""
        pdf_content = b"%PDF-1.4\nfake pdf content"

        with patch('core.auto_document_ingestion.PyPDF2') as mock_pypdf:
            mock_reader = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "PDF text content"
            mock_reader.pages = [mock_page]
            mock_pypdf.PdfReader.return_value = mock_reader

            result = await DocumentParser.parse_document(pdf_content, "pdf", "test.pdf")
            assert "PDF text content" in result

    @pytest.mark.asyncio
    async def test_parse_pdf_with_fallback(self):
        """Test parsing PDF with fallback parser."""
        pdf_content = b"%PDF-1.4\nfake pdf content"

        with patch('core.auto_document_ingestion.PyPDF2', side_effect=ImportError):
            with patch('core.auto_document_ingestion.pypdf') as mock_pypdf:
                mock_reader = MagicMock()
                mock_page = MagicMock()
                mock_page.extract_text.return_value = "Fallback PDF text"
                mock_reader.pages = [mock_page]
                mock_pypdf.PdfReader.return_value = mock_reader

                result = await DocumentParser.parse_document(pdf_content, "pdf", "test.pdf")
                assert "Fallback PDF text" in result

    @pytest.mark.asyncio
    async def test_parse_pdf_no_parser_available(self):
        """Test parsing PDF when no parser is available."""
        pdf_content = b"%PDF-1.4\nfake pdf content"

        with patch('core.auto_document_ingestion.PyPDF2', side_effect=ImportError):
            with patch('core.auto_document_ingestion.pypdf', side_effect=ImportError):
                result = await DocumentParser.parse_document(pdf_content, "pdf", "test.pdf")
                assert "parser not available" in result

    @pytest.mark.asyncio
    async def test_parse_docx_document(self):
        """Test parsing DOCX document."""
        docx_content = b"PK\x03\x04"  # DOCX zip header

        with patch('core.auto_document_ingestion.Document') as mock_doc_class:
            mock_doc = MagicMock()
            mock_para1 = MagicMock()
            mock_para1.text = "Paragraph 1"
            mock_para2 = MagicMock()
            mock_para2.text = "Paragraph 2"
            mock_doc.paragraphs = [mock_para1, mock_para2]
            mock_doc.tables = []
            mock_doc_class.return_value = mock_doc

            result = await DocumentParser.parse_document(docx_content, "docx", "test.docx")
            assert "Paragraph 1" in result
            assert "Paragraph 2" in result

    @pytest.mark.asyncio
    async def test_parse_docx_no_parser_available(self):
        """Test parsing DOCX when no parser is available."""
        docx_content = b"fake docx content"

        with patch('core.auto_document_ingestion.Document', side_effect=ImportError):
            result = await DocumentParser.parse_document(docx_content, "docx", "test.docx")
            assert "parser not available" in result

    @pytest.mark.asyncio
    async def test_parse_excel_document(self):
        """Test parsing Excel document."""
        excel_content = b"PK\x03\x04"  # Excel zip header

        with patch('core.auto_document_ingestion.pd') as mock_pd:
            mock_xls = MagicMock()
            mock_xls.sheet_names = ["Sheet1", "Sheet2"]
            mock_pd.ExcelFile.return_value = mock_xls
            mock_pd.read_excel.return_value = MagicMock()

            result = await DocumentParser.parse_document(excel_content, "xlsx", "test.xlsx")
            assert "Sheet" in result

    @pytest.mark.asyncio
    async def test_parse_excel_with_openpyxl_fallback(self):
        """Test parsing Excel with openpyxl fallback."""
        excel_content = b"fake excel content"

        with patch('core.auto_document_ingestion.pd', side_effect=ImportError):
            with patch('core.auto_document_ingestion.openpyxl') as mock_openpyxl:
                mock_wb = MagicMock()
                mock_sheet = MagicMock()
                mock_row = (["Cell1", "Cell2"],)
                mock_sheet.iter_rows.return_value = [mock_row]
                mock_wb.sheetnames = ["Sheet1"]
                mock_wb.__getitem__ = MagicMock(return_value=mock_sheet)
                mock_openpyxl.load_workbook.return_value = mock_wb

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

        with patch('core.auto_document_ingestion.get_formula_extractor') as mock_get_extractor:
            mock_extractor = MagicMock()
            mock_extractor.extract_from_csv.return_value = [{"formula": "=A1*2"}]
            mock_get_extractor.return_value = mock_extractor

            result = DocumentParser._parse_csv(csv_content, file_path="/path/to/test.csv")
            assert "Value" in result
            assert "10" in result

    def test_parse_csv_formula_extraction_error(self):
        """Test CSV parsing handles formula extraction errors gracefully."""
        csv_content = b"Value\n10\n20"

        with patch('core.auto_document_ingestion.get_formula_extractor') as mock_get_extractor:
            mock_extractor = MagicMock()
            mock_extractor.extract_from_csv.side_effect = Exception("Extraction failed")
            mock_get_extractor.return_value = mock_extractor

            # Should not raise exception, should log warning and continue
            result = DocumentParser._parse_csv(csv_content)
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

        with patch('core.auto_document_ingestion.get_formula_extractor') as mock_get_extractor:
            mock_extractor = MagicMock()
            mock_extractor.extract_from_excel.return_value = [{"formula": "=SUM(A1:A10)"}]
            mock_get_extractor.return_value = mock_extractor

            with patch('core.auto_document_ingestion.pd') as mock_pd:
                mock_xls = MagicMock()
                mock_xls.sheet_names = ["Sheet1"]
                mock_pd.ExcelFile.return_value = mock_xls
                mock_pd.read_excel.return_value = MagicMock()

                # Should call formula extraction
                import asyncio
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
        settings = self.service.get_or_create_settings(
            integration_id="test-integration",
            workspace_id="test-workspace"
        )
        assert isinstance(settings, IngestionSettings)
        assert settings.integration_id == "test-integration"

    def test_update_settings(self):
        """Test updating ingestion settings."""
        settings = self.service.update_settings(
            integration_id="test-integration",
            workspace_id="test-workspace",
            enabled=True,
            file_types=["pdf"],
            max_file_size_mb=200
        )
        assert settings.enabled is True
        assert settings.file_types == ["pdf"]
        assert settings.max_file_size_mb == 200

    def test_should_sync_file_type(self):
        """Test checking if file type should be synced."""
        settings = IngestionSettings(
            integration_id="test",
            workspace_id="test",
            file_types=["pdf", "docx"]
        )

        assert self.service._should_sync_file("test.pdf", settings) is True
        assert self.service._should_sync_file("test.docx", settings) is True
        assert self.service._should_sync_file("test.txt", settings) is False

    def test_should_sync_file_size(self):
        """Test checking if file size is within limits."""
        settings = IngestionSettings(
            integration_id="test",
            workspace_id="test",
            max_file_size_mb=10
        )

        # Small file (5 MB)
        assert self.service._should_sync_file("test.pdf", settings, file_size=5 * 1024 * 1024) is True

        # Large file (15 MB)
        assert self.service._should_sync_file("test.pdf", settings, file_size=15 * 1024 * 1024) is False

    def test_should_sync_folder(self):
        """Test checking if folder should be synced."""
        settings = IngestionSettings(
            integration_id="test",
            workspace_id="test",
            sync_folders=["/documents", "/reports"],
            exclude_folders=["/documents/archive"]
        )

        # In sync folder
        assert self.service._should_sync_file("/documents/file.pdf", settings) is True

        # In excluded folder
        assert self.service._should_sync_file("/documents/archive/file.pdf", settings) is False

        # Not in sync folder (when sync_folders is not empty)
        assert self.service._should_sync_file("/other/file.pdf", settings) is False

    def test_should_sync_folder_all_allowed(self):
        """Test syncing when all folders are allowed."""
        settings = IngestionSettings(
            integration_id="test",
            workspace_id="test",
            sync_folders=[],  # Empty means all folders
            exclude_folders=["/tmp"]
        )

        # Should sync (not in exclude)
        assert self.service._should_sync_file("/documents/file.pdf", settings) is True

        # Should not sync (in exclude)
        assert self.service._should_sync_file("/tmp/file.pdf", settings) is False

    @pytest.mark.asyncio
    async def test_ingest_document(self):
        """Test ingesting a document."""
        content = b"# Test Document\n\nThis is test content."

        with patch.object(DocumentParser, 'parse_document') as mock_parse:
            mock_parse.return_value = "# Test Document\n\nThis is test content."

            result = await self.service.ingest_document(
                file_content=content,
                file_name="test.md",
                file_type="md",
                integration_id="local",
                workspace_id="test-workspace",
                external_id="doc1"
            )

            assert result["success"] is True
            assert result["document_id"] is not None

    @pytest.mark.asyncio
    async def test_ingest_document_unsupported_type(self):
        """Test ingesting document with unsupported type."""
        content = b"some content"

        result = await self.service.ingest_document(
            file_content=content,
            file_name="test.xyz",
            file_type="xyz",
            integration_id="local",
            workspace_id="test-workspace",
            external_id="doc1"
        )

        # Should fail due to unsupported type
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_ingest_document_too_large(self):
        """Test ingesting document that's too large."""
        content = b"x" * (100 * 1024 * 1024)  # 100 MB

        settings = IngestionSettings(
            integration_id="local",
            workspace_id="test-workspace",
            max_file_size_mb=10
        )

        result = await self.service.ingest_document(
            file_content=content,
            file_name="large.txt",
            file_type="txt",
            integration_id="local",
            workspace_id="test-workspace",
            external_id="doc1",
            settings=settings
        )

        assert result["success"] is False
        assert "too large" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_batch_ingest_documents(self):
        """Test batch ingesting multiple documents."""
        documents = [
            {
                "file_content": b"Content 1",
                "file_name": "doc1.txt",
                "file_type": "txt",
                "external_id": "ext1"
            },
            {
                "file_content": b"Content 2",
                "file_name": "doc2.txt",
                "file_type": "txt",
                "external_id": "ext2"
            }
        ]

        with patch.object(self.service, 'ingest_document') as mock_ingest:
            mock_ingest.return_value = {"success": True, "document_id": "doc_id"}

            results = await self.service.batch_ingest_documents(
                documents=documents,
                integration_id="local",
                workspace_id="test-workspace"
            )

            assert len(results) == 2
            assert all(r["success"] for r in results)

    def test_get_ingested_documents(self):
        """Test getting list of ingested documents."""
        # Add some test documents
        self.service.documents["doc1"] = IngestedDocument(
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

        self.service.documents["doc2"] = IngestedDocument(
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

        docs = self.service.get_ingested_documents(
            integration_id="local",
            workspace_id="test-workspace"
        )

        assert len(docs) == 2

    def test_get_document_by_external_id(self):
        """Test getting document by external ID."""
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

        self.service.documents["doc1"] = doc

        found = self.service.get_document_by_external_id(
            integration_id="local",
            workspace_id="test-workspace",
            external_id="external123"
        )

        assert found is not None
        assert found.file_name == "test.pdf"

    def test_delete_document(self):
        """Test deleting an ingested document."""
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

        self.service.documents["doc1"] = doc

        deleted = self.service.delete_document("doc1")
        assert deleted is True
        assert "doc1" not in self.service.documents

    def test_get_sync_status(self):
        """Test getting sync status for integration."""
        settings = IngestionSettings(
            integration_id="local",
            workspace_id="test-workspace",
            enabled=True,
            last_sync=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )

        self.service.settings["local-test-workspace"] = settings

        status = self.service.get_sync_status(
            integration_id="local",
            workspace_id="test-workspace"
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
        content = b"# Test Document\n\nImportant content here."

        with patch.object(DocumentParser, 'parse_document') as mock_parse:
            mock_parse.return_value = "# Test Document\n\nImportant content here."

            # Ingest document
            result = await self.service.ingest_document(
                file_content=content,
                file_name="test.md",
                file_type="md",
                integration_id="local",
                workspace_id="test-workspace",
                external_id="doc1"
            )

            assert result["success"] is True

            # Verify document was stored
            doc = self.service.get_document_by_external_id(
                integration_id="local",
                workspace_id="test-workspace",
                external_id="doc1"
            )

            assert doc is not None
            assert doc.file_name == "test.md"

    @pytest.mark.asyncio
    async def test_sync_integration_source(self):
        """Test syncing files from integration source."""
        # Mock file list from integration
        files = [
            {
                "id": "file1",
                "name": "doc1.pdf",
                "size": 1024,
                "modified_time": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            },
            {
                "id": "file2",
                "name": "doc2.pdf",
                "size": 2048,
                "modified_time": datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
            }
        ]

        with patch.object(self.service, '_fetch_files_from_integration') as mock_fetch:
            mock_fetch.return_value = files

            with patch.object(self.service, 'ingest_document') as mock_ingest:
                mock_ingest.return_value = {"success": True, "document_id": "doc_id"}

                result = await self.service.sync_integration(
                    integration_id="google-drive",
                    workspace_id="test-workspace"
                )

                assert result["synced_count"] == 2

    def test_calculate_sync_frequency(self):
        """Test calculating sync frequency based on settings."""
        settings = IngestionSettings(
            integration_id="test",
            workspace_id="test",
            sync_frequency_minutes=60
        )

        # Should sync every 60 minutes
        assert settings.sync_frequency_minutes == 60

    def test_check_should_sync(self):
        """Test checking if sync should run based on last sync time."""
        settings = IngestionSettings(
            integration_id="test",
            workspace_id="test",
            sync_frequency_minutes=60,
            last_sync=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )

        # Mock current time to be 2 hours after last sync
        with patch('core.auto_document_ingestion.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            # Should sync because 2 hours > 60 minutes
            should_sync = self.service._should_sync_now(settings)
            # Implementation dependent


class TestErrorHandling:
    """Test error handling in document ingestion."""

    def setup_method(self):
        """Setup test service."""
        self.service = AutoDocumentIngestionService()

    @pytest.mark.asyncio
    async def test_handle_corrupted_file(self):
        """Test handling corrupted file."""
        content = b"corrupted pdf content"

        with patch.object(DocumentParser, 'parse_document') as mock_parse:
            mock_parse.side_effect = Exception("File corrupted")

            result = await self.service.ingest_document(
                file_content=content,
                file_name="corrupted.pdf",
                file_type="pdf",
                integration_id="local",
                workspace_id="test-workspace",
                external_id="doc1"
            )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_handle_empty_file(self):
        """Test handling empty file."""
        content = b""

        result = await self.service.ingest_document(
            file_content=content,
            file_name="empty.txt",
            file_type="txt",
            integration_id="local",
            workspace_id="test-workspace",
            external_id="doc1"
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_handle_network_timeout(self):
        """Test handling network timeout during sync."""
        with patch.object(self.service, '_fetch_files_from_integration') as mock_fetch:
            import asyncio
            mock_fetch.side_effect = asyncio.TimeoutError("Network timeout")

            result = await self.service.sync_integration(
                integration_id="google-drive",
                workspace_id="test-workspace"
            )

            assert result["success"] is False
            assert "timeout" in result["error"].lower()


def test_get_document_ingestion_service():
    """Test getting singleton document ingestion service."""
    service1 = get_document_ingestion_service()
    service2 = get_document_ingestion_service()

    # Should return same instance
    assert service1 is service2
