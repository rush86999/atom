"""
Tests for DoclingDocumentProcessor

Tests for document processor including:
- Document processing
- Format support detection
- OCR processing
- Export formats
- BYOK integration
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture
def mock_docling():
    """Mock docling module."""
    with patch('core.docling_processor.DOCLING_AVAILABLE', True):
        with patch('core.docling_processor.DocumentConverter') as mock_converter:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.document = MagicMock()
            mock_converter.return_value = mock_instance

            yield {
                'DocumentConverter': mock_converter,
                'instance': mock_instance,
                'result': mock_result,
            }


class TestDoclingDocumentProcessorInit:
    """Tests for DoclingDocumentProcessor initialization."""

    @patch('core.docling_processor.DOCLING_AVAILABLE', False)
    def test_init_docling_unavailable(self):
        """Test initialization when docling is unavailable."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()
        assert processor.is_available is False

    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    def test_init_docling_available(self, mock_converter):
        """Test initialization when docling is available."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()
        assert processor.converter is not None

    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    def test_init_with_byok_disabled(self, mock_converter):
        """Test initialization with BYOK disabled."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor(use_byok=False)
        assert processor.use_byok is False

    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    @patch('core.docling_processor.get_byok_manager')
    def test_init_with_byok_enabled(self, mock_get_byok, mock_converter):
        """Test initialization with BYOK enabled."""
        from core.docling_processor import DoclingDocumentProcessor
        mock_manager = MagicMock()
        mock_get_byok.return_value = mock_manager

        processor = DoclingDocumentProcessor(use_byok=True)

        assert processor.byok_manager == mock_manager


class TestSupportedFormats:
    """Tests for format support methods."""

    def test_get_supported_formats(self):
        """Test getting list of supported formats."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        formats = processor.get_supported_formats()

        assert isinstance(formats, list)
        assert "pdf" in formats
        assert "docx" in formats
        assert "png" in formats

    def test_is_format_supported(self):
        """Test checking if format is supported."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        assert processor.is_format_supported("pdf") is True
        assert processor.is_format_supported("PDF") is True  # Case insensitive
        assert processor.is_format_supported("docx") is True
        assert processor.is_format_supported("png") is True
        assert processor.is_format_supported("xyz") is False

    def test_supported_extensions_coverage(self):
        """Test that common extensions are supported."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        supported = processor.get_supported_formats()

        # Check key formats
        expected_formats = ["pdf", "docx", "pptx", "xlsx", "html", "png", "jpg", "md"]
        for fmt in expected_formats:
            assert fmt in supported


class TestProcessDocument:
    """Tests for process_document method."""

    @pytest.mark.asyncio
    @patch('core.docling_processor.DOCLING_AVAILABLE', False)
    async def test_process_document_unavailable(self):
        """Test processing when docling is unavailable."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        result = await processor.process_document(b"fake content")

        assert result["success"] is False
        assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    async def test_process_document_bytes(self, mock_converter):
        """Test processing document from bytes."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Test\n\nContent"
        mock_instance.convert.return_value = mock_result
        mock_converter.return_value = mock_instance

        result = await processor.process_document(
            source=b"PDF content",
            file_type="pdf"
        )

        assert result["success"] is True
        assert "Content" in result["content"]
        assert result["method"] == "docling"

    @pytest.mark.asyncio
    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    async def test_process_document_path(self, mock_converter, tmp_path):
        """Test processing document from file path."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        # Create test file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content")

        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.document.export_to_markdown.return_value = "File content"
        mock_instance.convert.return_value = mock_result
        mock_converter.return_value = mock_instance

        result = await processor.process_document(
            source=str(test_file),
            file_type="pdf"
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    async def test_process_document_with_file_name(self, mock_converter):
        """Test processing with file name for context."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.document.export_to_markdown.return_value = "Content"
        mock_result.document.pages = [MagicMock(), MagicMock()]  # 2 pages
        mock_instance.convert.return_value = mock_result
        mock_converter.return_value = mock_instance

        result = await processor.process_document(
            source=b"content",
            file_type="pdf",
            file_name="document.pdf"
        )

        assert result["file_name"] == "document.pdf"
        assert result["page_count"] == 2


class TestProcessPDF:
    """Tests for process_pdf method."""

    @pytest.mark.asyncio
    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    async def test_process_pdf_basic(self, mock_converter):
        """Test basic PDF processing."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.document.export_to_markdown.return_value = "PDF content"
        mock_result.document.pages = [MagicMock()]
        mock_instance.convert.return_value = mock_result
        mock_converter.return_value = mock_instance

        result = await processor.process_pdf(b"PDF data")

        assert result["method"] == "docling"
        assert result["extracted_text"] == "PDF content"
        assert result["success"] is True

    @pytest.mark.asyncio
    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    async def test_process_pdf_with_ocr_disabled(self, mock_converter):
        """Test PDF processing with OCR disabled."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor(enable_ocr=False)

        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.document.export_to_markdown.return_value = "Content"
        mock_instance.convert.return_value = mock_result
        mock_converter.return_value = mock_instance

        result = await processor.process_pdf(b"PDF data", use_ocr=False)

        assert result["success"] is True


class TestExtractContent:
    """Tests for _extract_content method."""

    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    def test_extract_content_markdown(self, mock_converter):
        """Test extracting content as markdown."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        mock_result = MagicMock()
        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "# Markdown"
        mock_result.document = mock_doc

        result = processor._extract_content(mock_result, "markdown")

        assert result["content"] == "# Markdown"

    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    def test_extract_content_json(self, mock_converter):
        """Test extracting content as JSON."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        mock_result = MagicMock()
        mock_doc = MagicMock()
        mock_doc.model_dump_json.return_value = '{"key": "value"}'
        mock_doc.export_to_markdown.return_value = "# Markdown"
        mock_result.document = mock_doc

        result = processor._extract_content(mock_result, "json")

        assert "key" in result["content"]

    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    def test_extract_content_text(self, mock_converter):
        """Test extracting content as text."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        mock_result = MagicMock()
        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "Plain text"
        mock_result.document = mock_doc

        result = processor._extract_content(mock_result, "text")

        assert result["content"] == "Plain text"

    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    def test_extract_content_html(self, mock_converter):
        """Test extracting content as HTML."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        mock_result = MagicMock()
        mock_doc = MagicMock()
        mock_doc.export_to_html.return_value = "<html>Content</html>"
        mock_result.document = mock_doc

        result = processor._extract_content(mock_result, "html")

        assert "<html>" in result["content"]


class TestExtractMetadata:
    """Tests for _extract_metadata method."""

    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    def test_extract_metadata_basic(self, mock_converter):
        """Test basic metadata extraction."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        mock_result = MagicMock()
        mock_doc = MagicMock()
        mock_doc.pages = [MagicMock(), MagicMock(), MagicMock()]
        mock_result.document = mock_doc

        metadata = processor._extract_metadata(mock_result)

        assert metadata["page_count"] == 3
        assert "title" in metadata
        assert "author" in metadata

    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    def test_extract_metadata_with_doc_metadata(self, mock_converter):
        """Test metadata extraction with document metadata."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        mock_result = MagicMock()
        mock_doc = MagicMock()
        mock_doc.pages = [MagicMock()]
        mock_doc_meta = MagicMock()
        mock_doc_meta.title = "Test Document"
        mock_doc_meta.author = "Test Author"
        mock_doc.metadata = mock_doc_meta
        mock_result.document = mock_doc

        metadata = processor._extract_metadata(mock_result)

        assert metadata["title"] == "Test Document"
        assert metadata["author"] == "Test Author"


class TestGetStatus:
    """Tests for get_status method."""

    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    def test_get_status_available(self, mock_converter):
        """Test getting status when available."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        status = processor.get_status()

        assert status["available"] is True
        assert status["docling_installed"] is True
        assert "supported_formats" in status

    @patch('core.docling_processor.DOCLING_AVAILABLE', False)
    def test_get_status_unavailable(self):
        """Test getting status when unavailable."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        status = processor.get_status()

        assert status["available"] is False
        assert status["docling_installed"] is False


class TestGlobalFunctions:
    """Tests for global convenience functions."""

    @patch('core.docling_processor.DoclingDocumentProcessor')
    def test_get_docling_processor(self, mock_processor_class):
        """Test getting global processor instance."""
        from core.docling_processor import get_docling_processor

        mock_instance = MagicMock()
        mock_processor_class.return_value = mock_instance

        processor = get_docling_processor()

        assert processor == mock_instance

    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    def test_is_docling_available(self):
        """Test checking if docling is available."""
        from core.docling_processor import is_docling_available
        available = is_docling_available()
        assert available is True

    @patch('core.docling_processor.DOCLING_AVAILABLE', False)
    def test_is_docling_not_available(self):
        """Test checking if docling is unavailable."""
        from core.docling_processor import is_docling_available
        available = is_docling_available()
        assert available is False


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    async def test_process_document_error(self, mock_converter):
        """Test error handling during document processing."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        mock_instance = MagicMock()
        mock_instance.convert.side_effect = Exception("Processing failed")
        mock_converter.return_value = mock_instance

        result = await processor.process_document(b"content")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    @patch('core.docling_processor.DOCLING_AVAILABLE', True)
    @patch('core.docling_processor.DocumentConverter')
    async def test_unsupported_source_type(self, mock_converter):
        """Test handling of unsupported source type."""
        from core.docling_processor import DoclingDocumentProcessor
        processor = DoclingDocumentProcessor()

        mock_instance = MagicMock()
        mock_converter.return_value = mock_instance

        result = await processor.process_document(
            source=12345,  # Invalid type
            file_type="pdf"
        )

        assert result["success"] is False
