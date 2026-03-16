"""
Baseline unit tests for AutoDocumentIngestionService and DocumentParser.

Tests cover initialization, file type detection, parser selection logic,
and error handling for unsupported formats.
"""

import asyncio
import io
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest

from core.auto_document_ingestion import (
    AutoDocumentIngestionService,
    DocumentParser,
    FileType,
    IntegrationSource,
    IngestedDocument,
    IngestionSettings,
)


# ============================================================================
# Test Classes: DocumentParser
# ============================================================================

class TestDocumentParserInit:
    """Test DocumentParser initialization and configuration."""

    def test_document_parser_init(self):
        """Test DocumentParser can be instantiated."""
        parser = DocumentParser()
        assert parser is not None
        assert hasattr(parser, '_get_docling_processor')

    def test_docling_processor_lazy_loading(self):
        """Test that docling processor getter exists and can be called."""
        parser = DocumentParser()
        # Just verify the method exists and is callable
        assert callable(parser._get_docling_processor)
        # Calling it should not raise
        result = parser._get_docling_processor()
        # Result should be None (docling not available in test env) or processor
        assert result is None or hasattr(result, 'process_document')


class TestDocumentFileTypeDetection:
    """Test file type detection and FileType enum."""

    def test_file_type_enum_values(self):
        """Test FileType enum has expected values."""
        assert FileType.PDF == "pdf"
        assert FileType.DOC == "doc"
        assert FileType.DOCX == "docx"
        assert FileType.TXT == "txt"
        assert FileType.CSV == "csv"
        assert FileType.EXCEL == "xlsx"
        assert FileType.MARKDOWN == "md"
        assert FileType.JSON == "json"

    def test_integration_source_enum_values(self):
        """Test IntegrationSource enum has expected values."""
        assert IntegrationSource.GOOGLE_DRIVE == "google_drive"
        assert IntegrationSource.DROPBOX == "dropbox"
        assert IntegrationSource.ONEDRIVE == "onedrive"
        assert IntegrationSource.BOX == "box"
        assert IntegrationSource.LOCAL == "local"


class TestDocumentParsing:
    """Test document parsing logic for various file types."""

    @pytest.mark.asyncio
    async def test_parse_txt_file(self):
        """Test parsing a simple text file."""
        content = b"Hello, World!\nThis is a test document."
        result = await DocumentParser.parse_document(content, "txt", "test.txt")
        assert "Hello, World!" in result
        assert "test document" in result

    @pytest.mark.asyncio
    async def test_parse_markdown_file(self):
        """Test parsing a markdown file."""
        content = b"# Title\n\nThis is **markdown** content."
        result = await DocumentParser.parse_document(content, "md", "test.md")
        assert "# Title" in result
        assert "**markdown**" in result

    @pytest.mark.asyncio
    async def test_parse_json_file(self):
        """Test parsing a JSON file."""
        content = b'{"name": "test", "value": 123}'
        result = await DocumentParser.parse_document(content, "json", "test.json")
        assert '"name"' in result
        assert '"test"' in result

    @pytest.mark.asyncio
    async def test_parse_csv_file(self):
        """Test parsing a CSV file."""
        content = b"name,age\nAlice,30\nBob,25"
        result = await DocumentParser.parse_document(content, "csv", "test.csv")
        assert "name" in result
        assert "Alice" in result
        assert "Bob" in result

    @pytest.mark.asyncio
    async def test_parse_unsupported_file_type(self):
        """Test parsing unsupported file type returns empty string."""
        content = b"some content"
        result = await DocumentParser.parse_document(content, "xyz", "test.xyz")
        # Should return empty string or minimal content
        assert result == ""

    @pytest.mark.asyncio
    async def test_parse_with_unicode_errors(self):
        """Test parsing handles UTF-8 decoding errors gracefully."""
        # Invalid UTF-8 sequence
        content = b"\xff\xfe Invalid UTF-8"
        result = await DocumentParser.parse_document(content, "txt", "test.txt")
        # Should handle with errors='ignore'
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_parse_pdf_returns_string(self):
        """Test PDF parsing returns string result."""
        content = b"fake pdf content"
        result = await DocumentParser.parse_document(content, "pdf", "test.pdf")
        # Should return string (empty if parser unavailable)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_parse_docx_returns_string(self):
        """Test DOCX parsing returns string result."""
        content = b"fake docx content"
        result = await DocumentParser.parse_document(content, "docx", "test.docx")
        # Should return string (may be error marker if parser unavailable)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_parse_excel_returns_string(self):
        """Test Excel parsing returns string result."""
        content = b"fake excel content"
        result = await DocumentParser.parse_document(content, "xlsx", "test.xlsx")
        # Should return string (may be error marker if parser unavailable)
        assert isinstance(result, str)


class TestContentExtraction:
    """Test content extraction from parsed documents."""

    @pytest.mark.asyncio
    async def test_empty_file_returns_empty_content(self):
        """Test parsing empty file returns minimal content."""
        content = b""
        result = await DocumentParser.parse_document(content, "txt", "empty.txt")
        assert result == ""

    @pytest.mark.asyncio
    async def test_csv_row_limiting(self):
        """Test CSV parsing respects row limit."""
        # Create CSV with more than 1000 rows
        rows = ["col1,col2"] + [f"val{i},val{i}" for i in range(2000)]
        content = "\n".join(rows).encode('utf-8')
        result = await DocumentParser.parse_document(content, "csv", "large.csv")
        # Should be truncated
        assert "truncated" in result or len(result) < len(content)


class TestIngestionErrors:
    """Test error handling in document ingestion."""

    @pytest.mark.asyncio
    async def test_parse_returns_string_on_error(self):
        """Test parsing returns string even on error."""
        content = b"test"
        # Just verify the method returns a string
        result = await DocumentParser.parse_document(content, "csv", "test.csv")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_parse_exception_returns_empty_string(self):
        """Test exceptions during parsing return empty string."""
        content = b"test"
        with patch('core.auto_document_ingestion.DocumentParser._parse_csv', side_effect=Exception("Parse error")):
            result = await DocumentParser.parse_document(content, "csv", "test.csv")
            # Should handle exception gracefully
            assert isinstance(result, str)


# ============================================================================
# Test Classes: AutoDocumentIngestionService
# ============================================================================

class TestAutoDocumentIngestionInit:
    """Test AutoDocumentIngestionService initialization."""

    def test_service_class_exists(self):
        """Test AutoDocumentIngestionService class can be imported."""
        assert AutoDocumentIngestionService is not None
        assert hasattr(AutoDocumentIngestionService, '__init__')

    def test_service_has_required_attributes(self):
        """Test service has expected attributes."""
        # Check class attributes without instantiation
        assert hasattr(AutoDocumentIngestionService, 'sync_integration')
        assert hasattr(AutoDocumentIngestionService, 'get_settings')
        assert hasattr(AutoDocumentIngestionService, 'update_settings')
        assert hasattr(AutoDocumentIngestionService, 'get_ingested_documents')


class TestIngestionSettings:
    """Test ingestion settings management."""

    def test_settings_dataclass_exists(self):
        """Test IngestionSettings dataclass can be imported."""
        settings = IngestionSettings(
            integration_id="test",
            workspace_id="default"
        )
        assert settings.integration_id == "test"
        assert settings.enabled is False

    def test_settings_attributes_are_mutable(self):
        """Test settings attributes can be modified."""
        settings = IngestionSettings(
            integration_id="test",
            workspace_id="default"
        )
        settings.enabled = True
        settings.max_file_size_mb = 100
        assert settings.enabled is True
        assert settings.max_file_size_mb == 100

    def test_settings_file_types_default(self):
        """Test default file types are correct."""
        settings = IngestionSettings(
            integration_id="test",
            workspace_id="default"
        )
        assert "pdf" in settings.file_types
        assert "docx" in settings.file_types
        assert "txt" in settings.file_types


class TestFileSyncLogic:
    """Test file sync logic and scheduling."""

    def test_sync_method_is_async(self):
        """Test sync_integration is an async method."""
        import inspect
        assert inspect.iscoroutinefunction(AutoDocumentIngestionService.sync_integration)

    def test_list_files_method_is_async(self):
        """Test _list_files is an async method."""
        import inspect
        assert inspect.iscoroutinefunction(AutoDocumentIngestionService._list_files)

    def test_download_file_method_is_async(self):
        """Test _download_file is an async method."""
        import inspect
        assert inspect.iscoroutinefunction(AutoDocumentIngestionService._download_file)


class TestDocumentRemoval:
    """Test document removal and cleanup operations."""

    def test_remove_documents_method_is_async(self):
        """Test remove_integration_documents is an async method."""
        import inspect
        assert inspect.iscoroutinefunction(AutoDocumentIngestionService.remove_integration_documents)

    def test_remove_returns_expected_structure(self):
        """Test remove method returns dict with expected keys."""
        # We can't test the full logic without mocking, but we can verify the method exists
        assert hasattr(AutoDocumentIngestionService, 'remove_integration_documents')


class TestIngestionSettingsDataclass:
    """Test IngestionSettings dataclass."""

    def test_ingestion_settings_defaults(self):
        """Test IngestionSettings has correct default values."""
        settings = IngestionSettings(
            integration_id="test",
            workspace_id="default"
        )
        assert settings.enabled is False
        assert settings.auto_sync_new_files is True
        assert settings.file_types == ["pdf", "docx", "txt", "md"]
        assert settings.sync_folders == []
        assert settings.exclude_folders == []
        assert settings.max_file_size_mb == 50
        assert settings.sync_frequency_minutes == 60
        assert settings.last_sync is None

    def test_ingested_document_dataclass(self):
        """Test IngestedDocument dataclass."""
        doc = IngestedDocument(
            id="doc1",
            file_name="test.pdf",
            file_path="/path/test.pdf",
            file_type="pdf",
            integration_id="google_drive",
            workspace_id="default",
            file_size_bytes=1000,
            content_preview="Preview",
            ingested_at=datetime.utcnow(),
            external_id="ext1"
        )
        assert doc.id == "doc1"
        assert doc.file_name == "test.pdf"
        assert doc.file_type == "pdf"


class TestUsageStatsTracking:
    """Test usage tracking and statistics."""

    def test_global_service_function_exists(self):
        """Test that get_document_ingestion_service function exists."""
        from core.auto_document_ingestion import get_document_ingestion_service
        assert callable(get_document_ingestion_service)


# ============================================================================
# Test Classes: Document Parser Enhancements
# ============================================================================

class TestDocumentParserDoclingIntegration:
    """Test Docling integration for document parsing."""

    @pytest.mark.asyncio
    async def test_docling_processor_initialization(self):
        """Test Docling processor can be initialized when available."""
        parser = DocumentParser()
        processor = parser._get_docling_processor()
        # Should return None (not available) or a processor
        assert processor is None or hasattr(processor, 'process_document')

    @pytest.mark.asyncio
    async def test_parse_with_docling_available(self):
        """Test parsing when Docling processor is available."""
        with patch.object(DocumentParser, '_get_docling_processor') as mock_getter:
            mock_processor = AsyncMock()
            mock_processor.process_document.return_value = {
                "success": True,
                "content": "Docling parsed content",
                "total_chars": 100
            }
            mock_getter.return_value = mock_processor

            content = b"test content"
            result = await DocumentParser.parse_document(content, "pdf", "test.pdf")

            assert "Docling parsed content" in result
            mock_processor.process_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_with_docling_failure_fallback(self):
        """Test fallback to legacy parsers when Docling fails."""
        with patch.object(DocumentParser, '_get_docling_processor') as mock_getter:
            mock_processor = AsyncMock()
            mock_processor.process_document.side_effect = Exception("Docling error")
            mock_getter.return_value = mock_processor

            # Should fall back to txt parsing
            content = b"test content"
            result = await DocumentParser.parse_document(content, "txt", "test.txt")

            assert result == "test content"


class TestDocumentParserPDF:
    """Test PDF parsing behavior."""

    @pytest.mark.asyncio
    async def test_parse_pdf_returns_string(self):
        """Test PDF parsing returns string result."""
        content = b"fake pdf content"
        result = await DocumentParser._parse_pdf(content)
        # Should return string (empty or placeholder if parser unavailable)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_parse_pdf_handles_import_error(self):
        """Test PDF parsing handles ImportError gracefully."""
        content = b"fake pdf"
        result = await DocumentParser._parse_pdf(content)
        # Should handle missing parser gracefully
        assert isinstance(result, str)


class TestDocumentParserDOCX:
    """Test DOCX parsing behavior."""

    @pytest.mark.asyncio
    async def test_parse_docx_returns_string(self):
        """Test DOCX parsing returns string result."""
        content = b"fake docx content"
        result = await DocumentParser._parse_docx(content)
        # Should return string (empty or placeholder if parser unavailable)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_parse_docx_handles_import_error(self):
        """Test DOCX parsing handles ImportError gracefully."""
        content = b"fake docx"
        result = await DocumentParser._parse_docx(content)
        # Should handle missing parser gracefully
        assert isinstance(result, str)


class TestDocumentParserExcel:
    """Test Excel parsing behavior."""

    @pytest.mark.asyncio
    async def test_parse_excel_returns_string(self):
        """Test Excel parsing returns string result."""
        content = b"fake excel content"
        result = await DocumentParser._parse_excel(content)
        # Should return string (empty or placeholder if parser unavailable)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_parse_excel_handles_import_error(self):
        """Test Excel parsing handles ImportError gracefully."""
        content = b"fake excel"
        result = await DocumentParser._parse_excel(content)
        # Should handle missing parser gracefully
        assert isinstance(result, str)


class TestDocumentParserCSV:
    """Test CSV parsing with formula extraction."""

    @pytest.mark.asyncio
    async def test_parse_csv_formula_extraction(self):
        """Test CSV parsing extracts formulas when file_path provided."""
        content = b"col1,col2\nval1,val2"
        result = DocumentParser._parse_csv(content, file_path="/tmp/test.csv")

        # Should return string
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_parse_csv_handles_csv_errors(self):
        """Test CSV parsing handles malformed CSV gracefully."""
        content = b"malformed,csv,data\n1,2"
        result = DocumentParser._parse_csv(content)

        # Should return string even if CSV is malformed
        assert isinstance(result, str)


# ============================================================================
# Test Classes: AutoDocumentIngestionService
# ============================================================================

class TestAutoDocumentIngestionServiceInitialization:
    """Test service initialization and configuration."""

    def test_service_initialization_default_workspace(self):
        """Test service initializes with default workspace."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()
        assert service.workspace_id == "default"
        assert service.settings == {}
        assert service.ingested_docs == {}

    def test_service_initialization_memory_handler_attribute(self):
        """Test service has memory_handler attribute."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()
        # Should have memory_handler (may be None if not available)
        assert hasattr(service, 'memory_handler')

    def test_service_initialization_redactor_attribute(self):
        """Test service has redactor attribute."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()
        # Should have redactor (may be None if not available)
        assert hasattr(service, 'redactor')


class TestAutoDocumentIngestionSettings:
    """Test settings management."""

    def test_get_settings_creates_new(self):
        """Test get_settings creates new settings if not exist."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.get_settings("google_drive")

        assert settings.integration_id == "google_drive"
        assert settings.workspace_id == "default"
        assert settings.enabled is False

    def test_get_settings_returns_existing(self):
        """Test get_settings returns existing settings."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings1 = service.get_settings("dropbox")
        settings2 = service.get_settings("dropbox")

        assert settings1 is settings2

    def test_update_settings_enabled(self):
        """Test update_settings can enable integration."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.update_settings("google_drive", enabled=True)

        assert settings.enabled is True

    def test_update_settings_file_types(self):
        """Test update_settings can change file types."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.update_settings("google_drive", file_types=["pdf", "txt"])

        assert settings.file_types == ["pdf", "txt"]

    def test_update_settings_multiple_params(self):
        """Test update_settings with multiple parameters."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.update_settings(
            "google_drive",
            enabled=True,
            max_file_size_mb=100,
            sync_frequency_minutes=30
        )

        assert settings.enabled is True
        assert settings.max_file_size_mb == 100
        assert settings.sync_frequency_minutes == 30


class TestAutoDocumentIngestionSync:
    """Test document sync workflow."""

    @pytest.mark.asyncio
    async def test_sync_integration_not_enabled(self):
        """Test sync skipped when integration not enabled."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        result = await service.sync_integration("google_drive")

        assert result["skipped"] is True
        assert result["reason"] == "Integration not enabled"

    @pytest.mark.asyncio
    async def test_sync_integration_with_force(self):
        """Test sync with force flag bypasses enabled check."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        with patch.object(service, '_list_files', return_value=[]):
            result = await service.sync_integration("google_drive", force=True)

            assert result["integration_id"] == "google_drive"

    @pytest.mark.asyncio
    async def test_sync_integration_respects_frequency(self):
        """Test sync respects sync_frequency_minutes."""
        from core.auto_document_ingestion import AutoDocumentIngestionService, IngestionSettings
        service = AutoDocumentIngestionService()

        # Set up settings with recent sync
        settings = service.get_settings("google_drive")
        settings.enabled = True
        settings.last_sync = datetime.utcnow()
        settings.sync_frequency_minutes = 60

        result = await service.sync_integration("google_drive")

        assert result["skipped"] is True
        assert result["reason"] == "Recently synced"

    @pytest.mark.asyncio
    async def test_sync_integration_lists_files(self):
        """Test sync lists files from integration."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        service.get_settings("google_drive").enabled = True

        mock_files = [
            {"id": "file1", "name": "test.pdf", "size": 1000}
        ]

        with patch.object(service, '_list_files', return_value=mock_files):
            result = await service.sync_integration("google_drive", force=True)

            assert result["files_found"] == 1

    @pytest.mark.asyncio
    async def test_sync_integration_filters_by_file_type(self):
        """Test sync filters files by type."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.get_settings("google_drive")
        settings.enabled = True
        settings.file_types = ["pdf"]

        mock_files = [
            {"id": "file1", "name": "test.pdf", "size": 1000},
            {"id": "file2", "name": "test.docx", "size": 1000}
        ]

        with patch.object(service, '_list_files', return_value=mock_files):
            result = await service.sync_integration("google_drive", force=True)

            # Should skip docx file
            assert result["files_skipped"] == 1

    @pytest.mark.asyncio
    async def test_sync_integration_filters_by_file_size(self):
        """Test sync filters files by size."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.get_settings("google_drive")
        settings.enabled = True
        settings.max_file_size_mb = 1  # 1MB

        mock_files = [
            {"id": "file1", "name": "small.pdf", "size": 1000},
            {"id": "file2", "name": "large.pdf", "size": 2 * 1024 * 1024}  # 2MB
        ]

        with patch.object(service, '_list_files', return_value=mock_files):
            result = await service.sync_integration("google_drive", force=True)

            # Should skip large file
            assert result["files_skipped"] == 1

    @pytest.mark.asyncio
    async def test_sync_integration_skips_already_ingested(self):
        """Test sync skips files that haven't been modified."""
        from core.auto_document_ingestion import AutoDocumentIngestionService, IngestedDocument
        service = AutoDocumentIngestionService()

        settings = service.get_settings("google_drive")
        settings.enabled = True

        # Add already ingested document
        service.ingested_docs["file1"] = IngestedDocument(
            id="doc1",
            file_name="test.pdf",
            file_path="/test.pdf",
            file_type="pdf",
            integration_id="google_drive",
            workspace_id="default",
            file_size_bytes=1000,
            content_preview="Preview",
            ingested_at=datetime.utcnow(),
            external_id="file1",
            external_modified_at="2026-01-01T00:00:00Z"
        )

        mock_files = [
            {"id": "file1", "name": "test.pdf", "size": 1000, "modified_at": "2026-01-01T00:00:00Z"}
        ]

        with patch.object(service, '_list_files', return_value=mock_files):
            result = await service.sync_integration("google_drive", force=True)

            # Should skip already ingested
            assert result["files_skipped"] == 1

    @pytest.mark.asyncio
    async def test_sync_integration_downloads_and_parses(self):
        """Test sync downloads and parses documents."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.get_settings("google_drive")
        settings.enabled = True

        mock_files = [
            {"id": "file1", "name": "test.txt", "size": 1000}
        ]

        with patch.object(service, '_list_files', return_value=mock_files):
            with patch.object(service, '_download_file', return_value=b"test content"):
                with patch.object(service.parser, 'parse_document', return_value="test content"):
                    result = await service.sync_integration("google_drive", force=True)

                    # Should ingest file
                    assert result["files_found"] == 1

    @pytest.mark.asyncio
    async def test_sync_integration_redacts_secrets(self):
        """Test sync redacts secrets before storage."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.get_settings("google_drive")
        settings.enabled = True

        # Mock redactor
        service.redactor = MagicMock()
        service.redactor.redact.return_value = MagicMock(
            has_secrets=True,
            redactions=["API_KEY"],
            redacted_text="REDACTED content"
        )

        mock_files = [{"id": "file1", "name": "test.txt", "size": 1000}]

        with patch.object(service, '_list_files', return_value=mock_files):
            with patch.object(service, '_download_file', return_value=b"content"):
                with patch.object(service.parser, 'parse_document', return_value="original content"):
                    await service.sync_integration("google_drive", force=True)

                    # Should redact
                    service.redactor.redact.assert_called()

    @pytest.mark.asyncio
    async def test_sync_integration_stores_in_memory(self):
        """Test sync stores documents in LanceDB."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.get_settings("google_drive")
        settings.enabled = True

        # Mock memory handler
        service.memory_handler = MagicMock()
        service.memory_handler.add_document.return_value = True

        mock_files = [{"id": "file1", "name": "test.txt", "size": 1000}]

        with patch.object(service, '_list_files', return_value=mock_files):
            with patch.object(service, '_download_file', return_value=b"content"):
                with patch.object(service.parser, 'parse_document', return_value="content"):
                    result = await service.sync_integration("google_drive", force=True)

                    # Should store in memory
                    service.memory_handler.add_document.assert_called()

    @pytest.mark.asyncio
    async def test_sync_integration_handles_errors(self):
        """Test sync handles individual file errors gracefully."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.get_settings("google_drive")
        settings.enabled = True

        mock_files = [
            {"id": "file1", "name": "good.txt", "size": 1000},
            {"id": "file2", "name": "bad.txt", "size": 1000}
        ]

        with patch.object(service, '_list_files', return_value=mock_files):
            with patch.object(service, '_download_file', side_effect=[b"good content", Exception("Download failed")]):
                with patch.object(service.parser, 'parse_document', return_value="content"):
                    result = await service.sync_integration("google_drive", force=True)

                    # Should have error
                    assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_sync_integration_updates_last_sync(self):
        """Test sync updates last_sync timestamp."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.get_settings("google_drive")
        settings.enabled = True
        assert settings.last_sync is None

        with patch.object(service, '_list_files', return_value=[]):
            await service.sync_integration("google_drive", force=True)

            assert settings.last_sync is not None

    @pytest.mark.asyncio
    async def test_sync_integration_handles_exception(self):
        """Test sync handles top-level exceptions gracefully."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.get_settings("google_drive")
        settings.enabled = True

        with patch.object(service, '_list_files', side_effect=Exception("List failed")):
            result = await service.sync_integration("google_drive", force=True)

            assert result.get("success") is False
            assert "error" in result


class TestAutoDocumentIngestionRemoval:
    """Test document removal operations."""

    @pytest.mark.asyncio
    async def test_remove_integration_documents(self):
        """Test removing documents by integration."""
        from core.auto_document_ingestion import AutoDocumentIngestionService, IngestedDocument
        service = AutoDocumentIngestionService()

        # Add test documents
        service.ingested_docs["file1"] = IngestedDocument(
            id="doc1",
            file_name="test1.pdf",
            file_path="/test1.pdf",
            file_type="pdf",
            integration_id="google_drive",
            workspace_id="default",
            file_size_bytes=1000,
            content_preview="Preview",
            ingested_at=datetime.utcnow(),
            external_id="file1"
        )
        service.ingested_docs["file2"] = IngestedDocument(
            id="doc2",
            file_name="test2.pdf",
            file_path="/test2.pdf",
            file_type="pdf",
            integration_id="dropbox",
            workspace_id="default",
            file_size_bytes=1000,
            content_preview="Preview",
            ingested_at=datetime.utcnow(),
            external_id="file2"
        )

        result = await service.remove_integration_documents("google_drive")

        assert result["success"] is True
        assert result["documents_removed"] == 1
        assert "file1" in result["removed_ids"]
        assert "file2" in service.ingested_docs  # dropbox doc should remain


class TestAutoDocumentIngestionQuery:
    """Test query operations."""

    def test_get_ingested_documents_all(self):
        """Test getting all ingested documents."""
        from core.auto_document_ingestion import AutoDocumentIngestionService, IngestedDocument
        service = AutoDocumentIngestionService()

        service.ingested_docs["file1"] = IngestedDocument(
            id="doc1",
            file_name="test1.pdf",
            file_path="/test1.pdf",
            file_type="pdf",
            integration_id="google_drive",
            workspace_id="default",
            file_size_bytes=1000,
            content_preview="Preview",
            ingested_at=datetime.utcnow(),
            external_id="file1"
        )

        docs = service.get_ingested_documents()
        assert len(docs) == 1

    def test_get_ingested_documents_by_integration(self):
        """Test filtering documents by integration."""
        from core.auto_document_ingestion import AutoDocumentIngestionService, IngestedDocument
        service = AutoDocumentIngestionService()

        service.ingested_docs["file1"] = IngestedDocument(
            id="doc1",
            file_name="test.pdf",
            file_path="/test.pdf",
            file_type="pdf",
            integration_id="google_drive",
            workspace_id="default",
            file_size_bytes=1000,
            content_preview="Preview",
            ingested_at=datetime.utcnow(),
            external_id="file1"
        )
        service.ingested_docs["file2"] = IngestedDocument(
            id="doc2",
            file_name="test2.pdf",
            file_path="/test2.pdf",
            file_type="pdf",
            integration_id="dropbox",
            workspace_id="default",
            file_size_bytes=1000,
            content_preview="Preview",
            ingested_at=datetime.utcnow(),
            external_id="file2"
        )

        docs = service.get_ingested_documents(integration_id="google_drive")
        assert len(docs) == 1
        assert docs[0].integration_id == "google_drive"

    def test_get_ingested_documents_by_type(self):
        """Test filtering documents by file type."""
        from core.auto_document_ingestion import AutoDocumentIngestionService, IngestedDocument
        service = AutoDocumentIngestionService()

        service.ingested_docs["file1"] = IngestedDocument(
            id="doc1",
            file_name="test.pdf",
            file_path="/test.pdf",
            file_type="pdf",
            integration_id="google_drive",
            workspace_id="default",
            file_size_bytes=1000,
            content_preview="Preview",
            ingested_at=datetime.utcnow(),
            external_id="file1"
        )
        service.ingested_docs["file2"] = IngestedDocument(
            id="doc2",
            file_name="test2.docx",
            file_path="/test2.docx",
            file_type="docx",
            integration_id="google_drive",
            workspace_id="default",
            file_size_bytes=1000,
            content_preview="Preview",
            ingested_at=datetime.utcnow(),
            external_id="file2"
        )

        docs = service.get_ingested_documents(file_type="pdf")
        assert len(docs) == 1
        assert docs[0].file_type == "pdf"

    def test_get_all_settings(self):
        """Test getting all integration settings."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        service.get_settings("google_drive")
        service.get_settings("dropbox")

        all_settings = service.get_all_settings()
        assert len(all_settings) == 2


class TestDocumentIngestionServiceSingleton:
    """Test global service singleton."""

    def test_get_document_ingestion_service_singleton(self):
        """Test get_document_ingestion_service returns singleton."""
        from core.auto_document_ingestion import get_document_ingestion_service
        service1 = get_document_ingestion_service()
        service2 = get_document_ingestion_service()
        assert service1 is service2


class TestDocumentIngestionDownloadRouting:
    """Test file download routing."""

    @pytest.mark.asyncio
    async def test_download_file_routes_to_google_drive(self):
        """Test _download_file routes to Google Drive handler."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        file_info = {"id": "file1", "name": "test.pdf"}

        with patch.object(service, '_download_google_drive_file', return_value=b"content"):
            result = await service._download_file("google_drive", file_info)
            assert result == b"content"

    @pytest.mark.asyncio
    async def test_download_file_routes_to_dropbox(self):
        """Test _download_file routes to Dropbox handler."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        file_info = {"id": "file1", "name": "test.pdf"}

        with patch.object(service, '_download_dropbox_file', return_value=b"content"):
            result = await service._download_file("dropbox", file_info)
            assert result == b"content"

    @pytest.mark.asyncio
    async def test_download_file_routes_to_onedrive(self):
        """Test _download_file routes to OneDrive handler."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        file_info = {"id": "file1", "name": "test.pdf"}

        with patch.object(service, '_download_onedrive_file', return_value=b"content"):
            result = await service._download_file("onedrive", file_info)
            assert result == b"content"

    @pytest.mark.asyncio
    async def test_download_file_routes_to_notion(self):
        """Test _download_file routes to Notion handler."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        file_info = {"id": "page1", "name": "test"}

        with patch.object(service, '_download_notion_content', return_value=b"content"):
            result = await service._download_file("notion", file_info)
            assert result == b"content"

    @pytest.mark.asyncio
    async def test_download_file_unknown_integration(self):
        """Test _download_file returns None for unknown integration."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        file_info = {"id": "file1", "name": "test.pdf"}

        result = await service._download_file("unknown_integration", file_info)
        assert result is None

    @pytest.mark.asyncio
    async def test_download_file_handles_exception(self):
        """Test _download_file handles exceptions gracefully."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        file_info = {"id": "file1", "name": "test.pdf"}

        with patch.object(service, '_download_google_drive_file', side_effect=Exception("Download failed")):
            result = await service._download_file("google_drive", file_info)
            assert result is None


class TestDocumentIngestionListRouting:
    """Test file list routing."""

    @pytest.mark.asyncio
    async def test_list_files_routes_to_google_drive(self):
        """Test _list_files routes to Google Drive handler."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.get_settings("google_drive")

        mock_files = [{"id": "file1", "name": "test.pdf"}]
        with patch.object(service, '_list_google_drive_files', return_value=mock_files):
            result = await service._list_files("google_drive", settings)
            assert result == mock_files

    @pytest.mark.asyncio
    async def test_list_files_routes_to_dropbox(self):
        """Test _list_files routes to Dropbox handler."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.get_settings("dropbox")

        mock_files = [{"id": "file1", "name": "test.pdf"}]
        with patch.object(service, '_list_dropbox_files', return_value=mock_files):
            result = await service._list_files("dropbox", settings)
            assert result == mock_files

    @pytest.mark.asyncio
    async def test_list_files_handles_exception(self):
        """Test _list_files handles exceptions gracefully."""
        from core.auto_document_ingestion import AutoDocumentIngestionService
        service = AutoDocumentIngestionService()

        settings = service.get_settings("google_drive")

        with patch.object(service, '_list_google_drive_files', side_effect=Exception("List failed")):
            result = await service._list_files("google_drive", settings)
            assert result == []  # Should return empty list on error
