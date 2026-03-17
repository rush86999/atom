"""
Comprehensive test coverage for Local OCR Service
Target: 60%+ line coverage (164 lines)
"""

import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
from core.local_ocr_service import (
    LocalOCRService,
    TESSERACT_AVAILABLE,
    SURYA_AVAILABLE,
    PIL_AVAILABLE,
)


# ==================== FIXTURES ====================

@pytest.fixture
def ocr_service():
    """Fresh OCR service instance for each test."""
    return LocalOCRService()


@pytest.fixture
def sample_image_path(tmp_path):
    """Create a temporary test image file."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    try:
        os.unlink(temp_path)
    except:
        pass


@pytest.fixture
def sample_pdf_path(tmp_path):
    """Create a temporary test PDF file."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 fake pdf")
        temp_path = f.name
    yield temp_path
    # Cleanup
    try:
        os.unlink(temp_path)
    except:
        pass


# ==================== TestLocalOCRService: Initialization ====================

class TestLocalOCRService:
    """Test OCR service initialization and configuration."""

    def test_ocr_service_initialization(self, ocr_service):
        """Test service initializes with engine availability."""
        assert isinstance(ocr_service.engines, dict)
        assert "tesseract" in ocr_service.engines
        assert "surya" in ocr_service.engines
        assert ocr_service._surya_models is None

    def test_engines_reflect_availability_flags(self, ocr_service):
        """Test engine availability matches import flags."""
        assert ocr_service.engines["tesseract"] == TESSERACT_AVAILABLE
        assert ocr_service.engines["surya"] == SURYA_AVAILABLE


# ==================== TestOCRProcessing: Image Processing ====================

class TestOCRProcessing:
    """Test OCR image processing functionality."""

    def test_process_image_without_pil(self, ocr_service, sample_image_path):
        """Test image processing fails gracefully without PIL."""
        with patch("core.local_ocr_service.PIL_AVAILABLE", False):
            result = ocr_service.process_image(sample_image_path)

            assert result["success"] is False
            assert "PIL not available" in result["error"]

    def test_process_image_nonexistent_file(self, ocr_service):
        """Test image processing fails for nonexistent file."""
        result = ocr_service.process_image("/nonexistent/file.png")

        assert result["success"] is False
        assert "File not found" in result["error"]

    def test_process_image_auto_engine_selection(self, ocr_service, sample_image_path):
        """Test auto-selects available engine when none specified."""
        # Mock file existence
        with patch("os.path.exists", return_value=True):
            if SURYA_AVAILABLE:
                with patch.object(ocr_service, "_ocr_surya") as mock_surya:
                    mock_surya.return_value = {"success": True, "text": "Surya OCR result"}
                    result = ocr_service.process_image(sample_image_path)
                    assert result["engine"] == "surya"
            elif TESSERACT_AVAILABLE:
                with patch.object(ocr_service, "_ocr_tesseract") as mock_tesseract:
                    mock_tesseract.return_value = {"success": True, "text": "Tesseract result"}
                    result = ocr_service.process_image(sample_image_path)
                    assert result["engine"] == "tesseract"
            else:
                result = ocr_service.process_image(sample_image_path)
                assert result["success"] is False

    def test_process_image_no_engines_available(self, ocr_service):
        """Test fails gracefully when no OCR engines available."""
        with patch("os.path.exists", return_value=True):
            with patch.object(ocr_service, "engines", {"tesseract": False, "surya": False}):
                result = ocr_service.process_image("test.png")

                assert result["success"] is False
                assert "No OCR engine available" in result["error"]

    def test_process_image_explicit_engine(self, ocr_service):
        """Test uses specified engine when provided."""
        with patch("os.path.exists", return_value=True):
            if TESSERACT_AVAILABLE:
                with patch.object(ocr_service, "_ocr_tesseract") as mock_tesseract:
                    mock_tesseract.return_value = {"success": True, "text": "test"}
                    result = ocr_service.process_image("test.png", engine="tesseract")
                    assert mock_tesseract.called
                    assert result["engine"] == "tesseract"
            else:
                # Tesseract not available, should return error
                result = ocr_service.process_image("test.png", engine="tesseract")
                assert result["success"] is False
                assert "Tesseract not available" in result["error"]


# ==================== TestOCRErrorHandling: Error Paths ====================

class TestOCRErrorHandling:
    """Test OCR error handling and edge cases."""

    def test_process_image_exception_handling(self, ocr_service):
        """Test handles exceptions during image processing."""
        with patch("os.path.exists", return_value=True):
            with patch.object(ocr_service, "_ocr_tesseract", side_effect=Exception("OCR failed")):
                result = ocr_service.process_image("test.png", engine="tesseract")

                assert result["success"] is False
                assert "OCR failed" in result["error"]

    def test_unknown_engine_specified(self, ocr_service):
        """Test fails when unknown engine specified."""
        with patch("os.path.exists", return_value=True):
            result = ocr_service.process_image("test.png", engine="unknown_engine")

            assert result["success"] is False
            assert "Unknown engine" in result["error"]

    def test_process_image_with_languages(self, ocr_service):
        """Test image processing with language specification."""
        if TESSERACT_AVAILABLE:
            with patch("os.path.exists", return_value=True):
                with patch.object(ocr_service, "_ocr_tesseract") as mock_tesseract:
                    mock_tesseract.return_value = {"success": True, "text": "test"}
                    ocr_service.process_image("test.png", languages=["en", "es"])

                    # Verify languages passed to OCR function
                    mock_tesseract.assert_called_once()
                    call_args = mock_tesseract.call_args
                    assert "en" in call_args[0][1] or "es" in call_args[0][1]


# ==================== TestOCRFormats: PDF Processing ====================

class TestOCRFormats:
    """Test OCR processing for different file formats."""

    def test_process_pdf_nonexistent_file(self, ocr_service):
        """Test PDF processing fails for nonexistent file."""
        result = ocr_service.process_pdf("/nonexistent/file.pdf")

        assert result["success"] is False
        assert "File not found" in result["error"]

    def test_process_pdf_with_pdf2image(self, ocr_service, sample_pdf_path):
        """Test PDF processing using pdf2image converter."""
        with patch("os.path.exists", return_value=True):
            with patch("core.local_ocr_service.convert_from_path") as mock_convert:
                # Mock converted images
                mock_img = MagicMock()
                mock_img.save = Mock()
                mock_convert.return_value = [mock_img]

                with patch.object(ocr_service, "process_image") as mock_ocr:
                    mock_ocr.return_value = {
                        "success": True,
                        "text": f"Page text",
                    }

                    result = ocr_service.process_pdf(sample_pdf_path)

                    assert result["success"] is True
                    assert "pages" in result
                    assert result["page_count"] == 1

    def test_process_pdf_with_pymupdf_fallback(self, ocr_service, sample_pdf_path):
        """Test PDF processing using PyMuPDF fallback."""
        with patch("os.path.exists", return_value=True):
            # pdf2image not available
            with patch("core.local_ocr_service.convert_from_path", side_effect=ImportError):
                with patch("core.local_ocr_service.fitz") as mock_fitz:
                    # Mock PyMuPDF document
                    mock_doc = MagicMock()
                    mock_page = MagicMock()
                    mock_pix = MagicMock()
                    mock_pix.save = Mock()

                    mock_fitz.open.return_value = mock_doc
                    mock_doc.__iter__ = Mock(return_value=iter([mock_page]))
                    mock_page.get_pixmap.return_value = mock_pix

                    with patch.object(ocr_service, "process_image") as mock_ocr:
                        mock_ocr.return_value = {
                            "success": True,
                            "text": "OCR text",
                        }

                        result = ocr_service.process_pdf(sample_pdf_path)

                        assert result["success"] is True

    def test_process_pdf_no_converter_available(self, ocr_service, sample_pdf_path):
        """Test PDF processing fails without converter."""
        with patch("os.path.exists", return_value=True):
            with patch("core.local_ocr_service.convert_from_path", side_effect=ImportError):
                with patch("core.local_ocr_service.fitz", side_effect=ImportError):
                    result = ocr_service.process_pdf(sample_pdf_path)

                    assert result["success"] is False

    def test_process_pdf_page_limit(self, ocr_service, sample_pdf_path):
        """Test PDF processing respects max_pages limit."""
        with patch("os.path.exists", return_value=True):
            with patch("core.local_ocr_service.convert_from_path") as mock_convert:
                # Mock 10 pages
                mock_imgs = [MagicMock() for _ in range(10)]
                for img in mock_imgs:
                    img.save = Mock()
                mock_convert.return_value = mock_imgs

                with patch.object(ocr_service, "process_image") as mock_ocr:
                    mock_ocr.return_value = {"success": True, "text": "text"}

                    # Limit to 5 pages
                    result = ocr_service.process_pdf(sample_pdf_path, max_pages=5)

                    # Should only process 5 pages
                    assert mock_convert.call_args[1]["last_page"] == 5

    def test_process_pdf_exception_handling(self, ocr_service, sample_pdf_path):
        """Test handles exceptions during PDF processing."""
        with patch("os.path.exists", return_value=True):
            with patch("core.local_ocr_service.convert_from_path", side_effect=Exception("PDF error")):
                result = ocr_service.process_pdf(sample_pdf_path)

                assert result["success"] is False
                assert "PDF error" in result["error"]


# ==================== TestOCRStatus: Engine Status & Installation ====================

class TestOCRStatus:
    """Test OCR status reporting and installation guides."""

    def test_get_status(self, ocr_service):
        """Test status returns engine availability."""
        status = ocr_service.get_status()

        assert "engines" in status
        assert "recommended" in status
        assert "pil_available" in status
        assert "any_available" in status

    def test_get_status_recommends_surya_if_available(self, ocr_service):
        """Test recommends Surya when available."""
        status = ocr_service.get_status()

        if SURYA_AVAILABLE:
            assert status["recommended"] == "surya"
        elif TESSERACT_AVAILABLE:
            assert status["recommended"] == "tesseract"
        else:
            assert status["recommended"] is None

    def test_get_installation_guide(self, ocr_service):
        """Test installation guide includes both engines."""
        guide = ocr_service.get_installation_guide()

        assert "tesseract" in guide
        assert "surya" in guide

        # Check tesseract guide structure
        tesseract_guide = guide["tesseract"]
        assert "available" in tesseract_guide
        assert "install" in tesseract_guide
        assert "macos" in tesseract_guide["install"]
        assert "windows" in tesseract_guide["install"]
        assert "linux" in tesseract_guide["install"]

    def test_installation_guide_surya_includes_languages(self, ocr_service):
        """Test Surya installation guide includes language info."""
        guide = ocr_service.get_installation_guide()

        surya_guide = guide["surya"]
        assert "languages" in surya_guide
        assert surya_guide["languages"] == "90+ languages"

    def test_installation_guide_tesseract_includes_languages(self, ocr_service):
        """Test Tesseract installation guide includes language info."""
        guide = ocr_service.get_installation_guide()

        tesseract_guide = guide["tesseract"]
        assert "languages" in tesseract_guide
        assert tesseract_guide["languages"] == "60+ languages"


# ==================== TestOCREngineSpecific: Tesseract & Surya ====================

class TestOCREngineSpecific:
    """Test engine-specific OCR functionality."""

    def test_tesseract_ocr_unavailable(self, ocr_service, sample_image_path):
        """Test Tesseract OCR handles unavailability."""
        with patch("core.local_ocr_service.TESSERACT_AVAILABLE", False):
            result = ocr_service._ocr_tesseract(sample_image_path, ["en"])

            assert result["success"] is False
            assert "Tesseract not available" in result["error"]

    def test_tesseract_ocr_with_languages(self, ocr_service):
        """Test Tesseract OCR language string formation."""
        if TESSERACT_AVAILABLE:
            with patch("core.local_ocr_service.pytesseract") as mock_pytes:
                with patch("core.local_ocr_service.Image") as mock_pil:
                    mock_pil.open.return_value = MagicMock()
                    mock_pytes.image_to_string.return_value = "OCR result"

                    # Test multiple languages
                    result = ocr_service._ocr_tesseract("test.png", ["en", "es", "fr"])

                    assert result["success"] is True
                    assert result["language"] == "en+es+fr"

    def test_tesseract_ocr_default_language(self, ocr_service):
        """Test Tesseract OCR defaults to English."""
        if TESSERACT_AVAILABLE:
            with patch("core.local_ocr_service.pytesseract") as mock_pytes:
                with patch("core.local_ocr_service.Image") as mock_pil:
                    mock_pil.open.return_value = MagicMock()
                    mock_pytes.image_to_string.return_value = "result"

                    result = ocr_service._ocr_tesseract("test.png", None)

                    assert result["language"] == "eng"

    def test_surya_ocr_unavailable(self, ocr_service, sample_image_path):
        """Test Surya OCR handles unavailability."""
        with patch("core.local_ocr_service.SURYA_AVAILABLE", False):
            result = ocr_service._ocr_surya(sample_image_path, ["en"])

            assert result["success"] is False
            assert "Surya not available" in result["error"]

    def test_surya_ocr_model_caching(self, ocr_service):
        """Test Surya models are cached after first load."""
        if SURYA_AVAILABLE:
            with patch("core.local_ocr_service.Image") as mock_pil:
                mock_pil.open.return_value = MagicMock()

                with patch("core.local_ocr_service.run_ocr") as mock_run_ocr:
                    mock_pred = MagicMock()
                    mock_pred.text_lines = [
                        MagicMock(text="Line 1"),
                        MagicMock(text="Line 2")
                    ]
                    mock_run_ocr.return_value = [mock_pred]

                    # First call - loads models
                    result1 = ocr_service._ocr_surya("test.png", ["en"])
                    assert ocr_service._surya_models is not None

                    # Second call - uses cached models
                    result2 = ocr_service._ocr_surya("test.png", ["en"])

                    assert result1["success"] is True
                    assert result2["success"] is True

    def test_surya_ocr_default_language(self, ocr_service):
        """Test Surya OCR defaults to English."""
        if SURYA_AVAILABLE:
            with patch("core.local_ocr_service.Image") as mock_pil:
                mock_pil.open.return_value = MagicMock()

                with patch("core.local_ocr_service.run_ocr") as mock_run_ocr:
                    mock_pred = MagicMock()
                    mock_pred.text_lines = [MagicMock(text="Text")]
                    mock_run_ocr.return_value = [mock_pred]

                    result = ocr_service._ocr_surya("test.png", None)

                    assert result["success"] is True
                    assert result["languages"] == ["en"]

    def test_surya_ocr_text_extraction(self, ocr_service):
        """Test Surya OCR extracts text lines correctly."""
        if SURYA_AVAILABLE:
            with patch("core.local_ocr_service.Image") as mock_pil:
                mock_pil.open.return_value = MagicMock()

                with patch("core.local_ocr_service.run_ocr") as mock_run_ocr:
                    # Mock predictions with multiple lines
                    mock_pred = MagicMock()
                    mock_pred.text_lines = [
                        MagicMock(text="First line"),
                        MagicMock(text="Second line"),
                        MagicMock(text="Third line")
                    ]
                    mock_run_ocr.return_value = [mock_pred]

                    result = ocr_service._ocr_surya("test.png", ["en"])

                    assert result["success"] is True
                    assert result["text"] == "First line\nSecond line\nThird line"
                    assert result["lines"] == 3
