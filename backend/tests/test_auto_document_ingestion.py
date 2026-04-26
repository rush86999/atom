"""
Test suite for auto_document_ingestion.py

Document ingestion service for parsing and processing various file formats.
Target file: backend/core/auto_document_ingestion.py (841 lines)
Target tests: 25-30 tests
Coverage target: 25-30%
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, Any, List

# Import target module classes
from core.auto_document_ingestion import (
    FileType,
    IntegrationSource,
    IngestionSettings,
    IngestedDocument,
    DocumentParser,
    AutoDocumentIngestionService,
    get_document_ingestion_service,
    AutoDocumentIngestion,
)


class TestFileTypeEnum:
    """Test FileType enum definition."""

    def test_pdf_file_type(self):
        """FileType.PDF has correct value."""
        assert FileType.PDF == "pdf"

    def test_docx_file_type(self):
        """FileType.DOCX has correct value."""
        assert FileType.DOCX == "docx"

    def test_markdown_file_type(self):
        """FileType.MARKDOWN has correct value."""
        assert FileType.MARKDOWN == "md"

    def test_all_file_types_defined(self):
        """All required file types are defined."""
        required_types = ["pdf", "doc", "docx", "txt", "csv", "xlsx", "xls", "md", "json"]
        defined_types = [ft.value for ft in FileType]
        for rt in required_types:
            assert rt in defined_types


class TestIntegrationSourceEnum:
    """Test IntegrationSource enum definition."""

    def test_google_drive_source(self):
        """IntegrationSource.GOOGLE_DRIVE has correct value."""
        assert IntegrationSource.GOOGLE_DRIVE == "google_drive"

    def test_dropbox_source(self):
        """IntegrationSource.DROPBOX has correct value."""
        assert IntegrationSource.DROPBOX == "dropbox"

    def test_notion_source(self):
        """IntegrationSource.NOTION has correct value."""
        assert IntegrationSource.NOTION == "notion"


class TestIngestionSettings:
    """Test IngestionSettings dataclass."""

    def test_ingestion_settings_creation(self):
        """IngestionSettings can be created with valid parameters."""
        settings = IngestionSettings(
            integration_id="google_drive",
            workspace_id="workspace-001",
            enabled=True,
            auto_sync_new_files=True,
            file_types=["pdf", "docx"],
            max_file_size_mb=50
        )
        assert settings.integration_id == "google_drive"
        assert settings.workspace_id == "workspace-001"
        assert settings.enabled is True
        assert settings.auto_sync_new_files is True
        assert settings.file_types == ["pdf", "docx"]
        assert settings.max_file_size_mb == 50

    def test_ingestion_settings_defaults(self):
        """IngestionSettings uses correct default values."""
        settings = IngestionSettings(
            integration_id="dropbox",
            workspace_id="workspace-002"
        )
        assert settings.enabled is False
        assert settings.auto_sync_new_files is True
        assert settings.file_types == ["pdf", "docx", "txt", "md"]
        assert settings.max_file_size_mb == 50
        assert settings.sync_frequency_minutes == 60
        assert settings.last_sync is None


class TestIngestedDocument:
    """Test IngestedDocument dataclass."""

    def test_ingested_document_creation(self):
        """IngestedDocument can be created with valid parameters."""
        doc = IngestedDocument(
            id="doc-001",
            file_name="test.pdf",
            file_path="/files/test.pdf",
            file_type="pdf",
            integration_id="google_drive",
            workspace_id="workspace-001",
            file_size_bytes=1024000,
            content_preview="This is a preview...",
            ingested_at=datetime.utcnow(),
            external_id="ext-001"
        )
        assert doc.id == "doc-001"
        assert doc.file_name == "test.pdf"
        assert doc.file_type == "pdf"
        assert doc.integration_id == "google_drive"
        assert doc.file_size_bytes == 1024000

    def test_ingested_document_optional_fields(self):
        """IngestedDocument handles optional external_modified_at field."""
        doc = IngestedDocument(
            id="doc-002",
            file_name="test2.pdf",
            file_path="/files/test2.pdf",
            file_type="pdf",
            integration_id="dropbox",
            workspace_id="workspace-001",
            file_size_bytes=2048000,
            content_preview="Another preview...",
            ingested_at=datetime.utcnow(),
            external_id="ext-002",
            external_modified_at=None
        )
        assert doc.external_modified_at is None


class TestDocumentParser:
    """Test DocumentParser class."""

    @pytest.mark.asyncio
    async def test_parse_text_file(self):
        """DocumentParser can parse text files."""
        content = b"This is plain text content"
        text = await DocumentParser.parse_document(content, "txt", "test.txt")
        assert "This is plain text content" in text

    @pytest.mark.asyncio
    async def test_parse_markdown_file(self):
        """DocumentParser can parse markdown files."""
        content = b"# Heading\n\nThis is markdown"
        text = await DocumentParser.parse_document(content, "md", "test.md")
        assert "# Heading" in text

    @pytest.mark.asyncio
    async def test_parse_json_file(self):
        """DocumentParser can parse JSON files."""
        content = b'{"key": "value", "number": 123}'
        text = await DocumentParser.parse_document(content, "json", "test.json")
        assert "key" in text
        assert "value" in text

    @pytest.mark.asyncio
    async def test_parse_csv_file(self):
        """DocumentParser can parse CSV files."""
        content = b"Name,Age\nAlice,30\nBob,25"
        text = await DocumentParser.parse_document(content, "csv", "test.csv")
        assert "Name" in text
        assert "Alice" in text

    @pytest.mark.asyncio
    async def test_parse_unsupported_file_type(self):
        """DocumentParser returns empty string for unsupported types."""
        content = b"Some content"
        text = await DocumentParser.parse_document(content, "unsupported", "test.unsupported")
        assert text == ""

    @pytest.mark.asyncio
    async def test_parse_pdf_with_pypdf2_mock(self):
        """DocumentParser can parse PDF using PyPDF2."""
        content = b"Mock PDF content"
        with patch('core.auto_document_ingestion.PyPDF2.PdfReader') as mock_reader:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "PDF text content"
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_page]
            mock_reader.return_value = mock_pdf

            text = await DocumentParser.parse_document(content, "pdf", "test.pdf")
            # Should return content (either from docling or fallback)
            assert isinstance(text, str)


class TestAutoDocumentIngestionService:
    """Test AutoDocumentIngestionService class."""

    def test_service_initialization(self):
        """AutoDocumentIngestionService initializes correctly."""
        with patch('core.auto_document_ingestion.get_lancedb_handler'):
            service = AutoDocumentIngestionService()
            assert service.workspace_id == "default"
            assert isinstance(service.settings, dict)
            assert service.parser is not None

    def test_get_settings_creates_new(self):
        """get_settings creates new settings if not exists."""
        with patch('core.auto_document_ingestion.get_lancedb_handler'):
            service = AutoDocumentIngestionService()
            settings = service.get_settings("new_integration")
            assert settings.integration_id == "new_integration"
            assert settings.workspace_id == "default"

    def test_get_settings_returns_existing(self):
        """get_settings returns existing settings."""
        with patch('core.auto_document_ingestion.get_lancedb_handler'):
            service = AutoDocumentIngestionService()
            settings1 = service.get_settings("existing")
            settings2 = service.get_settings("existing")
            assert settings1 is settings2

    def test_update_settings_enabled(self):
        """update_settings can enable integration."""
        with patch('core.auto_document_ingestion.get_lancedb_handler'):
            service = AutoDocumentIngestionService()
            settings = service.update_settings("test_integration", enabled=True)
            assert settings.enabled is True

    def test_update_settings_file_types(self):
        """update_settings can update file types."""
        with patch('core.auto_document_ingestion.get_lancedb_handler'):
            service = AutoDocumentIngestionService()
            settings = service.update_settings(
                "test_integration",
                file_types=["pdf", "txt", "csv"]
            )
            assert settings.file_types == ["pdf", "txt", "csv"]

    def test_update_settings_max_file_size(self):
        """update_settings can update max file size."""
        with patch('core.auto_document_ingestion.get_lancedb_handler'):
            service = AutoDocumentIngestionService()
            settings = service.update_settings(
                "test_integration",
                max_file_size_mb=100
            )
            assert settings.max_file_size_mb == 100

    @pytest.mark.asyncio
    async def test_sync_integration_disabled(self):
        """sync_integration skips disabled integrations."""
        with patch('core.auto_document_ingestion.get_lancedb_handler'):
            service = AutoDocumentIngestionService()
            result = await service.sync_integration("disabled_integration")
            assert result.get("skipped") is True
            assert "not enabled" in result.get("reason", "").lower()

    def test_get_ingested_documents_empty(self):
        """get_ingested_documents returns empty list initially."""
        with patch('core.auto_document_ingestion.get_lancedb_handler'):
            service = AutoDocumentIngestionService()
            docs = service.get_ingested_documents()
            assert docs == []

    def test_get_ingested_documents_by_integration(self):
        """get_ingested_documents can filter by integration."""
        with patch('core.auto_document_ingestion.get_lancedb_handler'):
            service = AutoDocumentIngestionService()
            # Add a mock document
            doc = IngestedDocument(
                id="doc-001",
                file_name="test.pdf",
                file_path="/files/test.pdf",
                file_type="pdf",
                integration_id="google_drive",
                workspace_id="default",
                file_size_bytes=1000,
                content_preview="Test",
                ingested_at=datetime.utcnow(),
                external_id="ext-001"
            )
            service.ingested_docs["ext-001"] = doc

            docs = service.get_ingested_documents(integration_id="google_drive")
            assert len(docs) == 1
            assert docs[0].integration_id == "google_drive"

    def test_get_all_settings(self):
        """get_all_settings returns all integration settings."""
        with patch('core.auto_document_ingestion.get_lancedb_handler'):
            service = AutoDocumentIngestionService()
            service.get_settings("integration_1")
            service.get_settings("integration_2")

            all_settings = service.get_all_settings()
            assert len(all_settings) == 2

    def test_remove_integration_documents(self):
        """remove_integration_documents removes all docs for integration."""
        with patch('core.auto_document_ingestion.get_lancedb_handler'):
            service = AutoDocumentIngestionService()

            # Add mock documents
            doc1 = IngestedDocument(
                id="doc-001",
                file_name="test1.pdf",
                file_path="/files/test1.pdf",
                file_type="pdf",
                integration_id="google_drive",
                workspace_id="default",
                file_size_bytes=1000,
                content_preview="Test1",
                ingested_at=datetime.utcnow(),
                external_id="ext-001"
            )
            doc2 = IngestedDocument(
                id="doc-002",
                file_name="test2.pdf",
                file_path="/files/test2.pdf",
                file_type="pdf",
                integration_id="google_drive",
                workspace_id="default",
                file_size_bytes=2000,
                content_preview="Test2",
                ingested_at=datetime.utcnow(),
                external_id="ext-002"
            )
            service.ingested_docs["ext-001"] = doc1
            service.ingested_docs["ext-002"] = doc2

            result = service.remove_integration_documents("google_drive")
            assert result["success"] is True
            assert result["documents_removed"] == 2
            assert len(service.ingested_docs) == 0


class TestGlobalServiceInstance:
    """Test global service instance functions."""

    def test_get_document_ingestion_service_singleton(self):
        """get_document_ingestion_service returns singleton instance."""
        with patch('core.auto_document_ingestion.get_lancedb_handler'):
            service1 = get_document_ingestion_service()
            service2 = get_document_ingestion_service()
            assert service1 is service2

    def test_auto_document_ingestion_alias(self):
        """AutoDocumentIngestion is alias for AutoDocumentIngestionService."""
        assert AutoDocumentIngestion == AutoDocumentIngestionService


class TestIntegration:
    """Integration tests for document ingestion workflow."""

    @pytest.mark.asyncio
    async def test_full_ingestion_workflow_with_mocks(self):
        """Test complete ingestion workflow with mocked dependencies."""
        with patch('core.auto_document_ingestion.get_lancedb_handler') as mock_lancedb, \
             patch('core.auto_document_ingestion.get_secrets_redactor') as mock_redactor:

            # Setup mocks
            mock_memory = AsyncMock()
            mock_memory.add_document.return_value = True
            mock_lancedb.return_value = mock_memory

            mock_redactor_instance = MagicMock()
            mock_redactor_instance.redact.return_value = MagicMock(
                has_secrets=False,
                redacted_text="Safe content"
            )
            mock_redactor.return_value = mock_redactor_instance

            service = AutoDocumentIngestionService()

            # Enable integration
            service.update_settings("test_integration", enabled=True)

            # Mock file listing
            with patch.object(service, '_list_files', return_value=[
                {
                    "id": "file-001",
                    "name": "test.pdf",
                    "path": "/files/test.pdf",
                    "size": 1024,
                    "modified_at": datetime.utcnow()
                }
            ]):
                # Mock file download
                with patch.object(service, '_download_file', return_value=b"PDF content"):
                    result = await service.sync_integration("test_integration", force=True)

                    # Verify sync ran
                    assert "integration_id" in result
                    assert result["integration_id"] == "test_integration"
