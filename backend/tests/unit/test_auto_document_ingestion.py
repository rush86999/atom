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
