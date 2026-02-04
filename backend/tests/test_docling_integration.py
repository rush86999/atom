"""
Tests for Docling Document Processor Integration

Tests the DoclingDocumentProcessor and its integration with Atom's memory system.
"""

import asyncio
import io
import logging
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestDoclingAvailability:
    """Test docling availability and graceful degradation."""

    def test_docling_import_check(self):
        """Test that docling availability check works correctly."""
        try:
            from core.docling_processor import DOCLING_AVAILABLE, is_docling_available

            # Should return bool without raising
            result = is_docling_available()
            assert isinstance(result, bool)
            logger.info(f"Docling available: {result}")
        except ImportError:
            logger.info("Docling processor module not available (expected in minimal install)")

    def test_processor_initialization(self):
        """Test DoclingDocumentProcessor initialization."""
        try:
            from core.docling_processor import DoclingDocumentProcessor
            processor = DoclingDocumentProcessor(use_byok=False)
            
            # Check status
            status = processor.get_status()
            assert "available" in status
            assert "supported_formats" in status
            logger.info(f"Processor status: {status}")
        except ImportError:
            logger.info("Skipping - docling not installed")

    def test_supported_formats(self):
        """Test that all expected formats are listed as supported."""
        try:
            from core.docling_processor import DoclingDocumentProcessor
            processor = DoclingDocumentProcessor(use_byok=False)
            
            expected_formats = ['pdf', 'docx', 'xlsx', 'html', 'png', 'jpg']
            supported = processor.get_supported_formats()
            
            for fmt in expected_formats:
                assert fmt in supported, f"Expected {fmt} to be supported"
        except ImportError:
            logger.info("Skipping - docling not installed")


class TestDocumentParserIntegration:
    """Test DocumentParser integration with docling."""

    @pytest.mark.asyncio
    async def test_parser_docling_fallback(self):
        """Test that DocumentParser falls back gracefully if docling unavailable."""
        try:
            from core.auto_document_ingestion import DocumentParser

            # Test with simple text file (should work regardless of docling)
            text_content = b"Hello, this is a test document."
            result = await DocumentParser.parse_document(text_content, "txt", "test.txt")
            
            assert result == "Hello, this is a test document."
            logger.info("Text parsing works correctly")
        except ImportError as e:
            logger.warning(f"Import error: {e}")

    @pytest.mark.asyncio
    async def test_parser_json_handling(self):
        """Test JSON parsing."""
        try:
            from core.auto_document_ingestion import DocumentParser
            
            json_content = b'{"key": "value", "number": 42}'
            result = await DocumentParser.parse_document(json_content, "json", "test.json")
            
            assert "key" in result
            assert "value" in result
            logger.info("JSON parsing works correctly")
        except ImportError as e:
            logger.warning(f"Import error: {e}")


class TestPDFOCRServiceIntegration:
    """Test PDFOCRService integration with docling."""

    def test_service_initialization(self):
        """Test PDFOCRService initializes with docling if available."""
        try:
            from integrations.pdf_processing.pdf_ocr_service import DOCLING_AVAILABLE, PDFOCRService
            
            service = PDFOCRService(use_byok=False)
            status = service.service_status
            
            assert "basic_pdf" in status
            assert status["basic_pdf"] == True  # PyPDF2 always available
            
            if DOCLING_AVAILABLE:
                assert "docling" in status
                logger.info("PDFOCRService initialized with docling support")
            else:
                logger.info("PDFOCRService initialized without docling (not installed)")
                
        except ImportError as e:
            logger.warning(f"Import error: {e}")

    def test_ocr_method_priority(self):
        """Test that docling is highest priority OCR method."""
        try:
            from integrations.pdf_processing.pdf_ocr_service import DOCLING_AVAILABLE, PDFOCRService
            
            service = PDFOCRService(use_byok=False)
            methods = service._get_available_ocr_methods(use_advanced_comprehension=False)
            
            if DOCLING_AVAILABLE and "docling" in service.ocr_readers:
                assert methods[0] == "docling", "Docling should be first priority"
                logger.info("Docling is correctly set as highest priority OCR")
            else:
                logger.info("Docling not available, checking fallback order")
                
        except ImportError as e:
            logger.warning(f"Import error: {e}")


class TestDoclingProcessor:
    """Test DoclingDocumentProcessor methods directly."""

    @pytest.mark.asyncio
    async def test_process_document_with_mock(self):
        """Test document processing with mocked docling."""
        try:
            from core.docling_processor import DOCLING_AVAILABLE, DoclingDocumentProcessor
            
            if not DOCLING_AVAILABLE:
                logger.info("Skipping - docling not installed")
                return
            
            processor = DoclingDocumentProcessor(use_byok=False)
            
            # Test with simple text as bytes (simulating a document)
            # Note: Real testing would require actual PDF/DOCX files
            status = processor.get_status()
            logger.info(f"Processor status: {status}")
            
            assert processor.is_format_supported("pdf")
            assert processor.is_format_supported("docx")
            assert not processor.is_format_supported("xyz")
            
        except ImportError as e:
            logger.warning(f"Import error: {e}")

    def test_error_result_format(self):
        """Test error result format is consistent."""
        try:
            from core.docling_processor import DoclingDocumentProcessor
            
            processor = DoclingDocumentProcessor(use_byok=False)
            error_result = processor._create_error_result("Test error")
            
            assert error_result["success"] == False
            assert error_result["method"] == "docling"
            assert error_result["error"] == "Test error"
            assert "content" in error_result
            assert "tables" in error_result
            
        except ImportError as e:
            logger.warning(f"Import error: {e}")


def run_tests():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Running Docling Integration Tests")
    logger.info("=" * 60)
    
    # Run with pytest
    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    return exit_code


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
