"""Coverage push for integrations wave B - batch 7 (pdf_ocr + pdf_memory)."""
import asyncio
import base64
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ============================================================================
# pdf_processing.pdf_ocr_service
# ============================================================================


class TestPDFOCR:
    def _svc(self):
        from integrations.pdf_processing.pdf_ocr_service import PDFOCRService
        return PDFOCRService()

    async def test_init_and_status(self):
        svc = self._svc()
        assert svc.service_status["basic_pdf"] is True
        assert svc.service_status["fallback_available"] is True
        assert svc.llm_service is not None

    async def test_process_pdf_basic(self):
        svc = self._svc()
        result = await svc.process_pdf(b"not a pdf")
        assert result["success"] is False
        assert result["processing_summary"]["best_method"] == "basic_pdf"

    async def test_extract_basic_text(self):
        svc = self._svc()
        reader = MagicMock()
        page = MagicMock()
        page.extract_text.return_value = "hello world"
        reader.pages = [page, page]
        with patch.object(svc, "llm_service", None):
            with patch("integrations.pdf_processing.pdf_ocr_service.PyPDF2") as pypdf:
                pypdf.PdfReader.return_value = reader
                result = await svc._extract_basic_text(b"pdfdata")
        assert result["success"] is True
        assert result["total_chars"] == 22
        assert result["text_ratio"] > 0
        pypdf.PdfReader.side_effect = RuntimeError("x")
        with patch("integrations.pdf_processing.pdf_ocr_service.PyPDF2") as pypdf:
            pypdf.PdfReader.side_effect = RuntimeError("x")
            result = await svc._extract_basic_text(b"x")
        assert result["success"] is False

    async def test_process_with_ocr_cascade_and_parallel(self):
        svc = self._svc()
        svc.ocr_readers = {"docling": MagicMock(), "tesseract": MagicMock()}
        svc._run_ocr_method = AsyncMock(return_value={"success": True, "total_chars": 5})
        result = await svc._process_with_ocr(b"x", "cascade", False)
        assert result["success"] is True
        assert result["methods_tried"] == ["docling"]
        svc._run_ocr_method = AsyncMock(side_effect=[
            {"success": False, "total_chars": 0}, {"success": True, "total_chars": 5}])
        result = await svc._process_with_ocr(b"x", "cascade", False)
        assert result["methods_tried"] == ["docling", "tesseract"]
        svc._run_ocr_method = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc._process_with_ocr(b"x", "cascade", False)
        assert result["methods_tried"] == ["docling_failed", "tesseract_failed"]
        svc._run_ocr_method = AsyncMock(return_value={"success": True, "total_chars": 3})
        result = await svc._process_with_ocr(b"x", "parallel", False)
        assert result["success"] is True
        svc._run_ocr_method = AsyncMock(side_effect=[RuntimeError("x"), RuntimeError("x")])
        result = await svc._process_with_ocr(b"x", "parallel", False)
        assert result["success"] is False
        assert result["methods_tried"] == ["docling_failed", "tesseract_failed"]

    async def test_available_ocr_methods(self):
        svc = self._svc()
        svc.ocr_readers = {"docling": 1, "easyocr": 1, "tesseract": 1, "openai": 1}
        methods = svc._get_available_ocr_methods(False)
        assert methods == ["docling", "easyocr", "tesseract"]
        svc.ocr_readers = {"easyocr": 1, "tesseract": 1, "ai_vision": 1}
        methods = svc._get_available_ocr_methods(True)
        assert "openai_vision" in methods
        svc.use_byok = True
        svc.byok_manager = MagicMock()
        svc.byok_manager.get_optimal_provider = MagicMock(return_value="openai")
        svc.ocr_readers = {"docling": 1, "ai_vision": 1}
        methods = svc._get_available_ocr_methods(True)
        assert methods == ["docling", "openai_vision"]
        svc.byok_manager.get_optimal_provider = MagicMock(return_value="other")
        methods = svc._get_available_ocr_methods(True)
        assert "openai_vision" not in methods
        svc.byok_manager.get_optimal_provider = MagicMock(side_effect=RuntimeError("x"))
        methods = svc._get_available_ocr_methods(True)
        assert "openai_vision" not in methods

    async def test_run_ocr_method(self):
        svc = self._svc()
        svc._ocr_with_docling = AsyncMock(return_value={"m": 1})
        assert await svc._run_ocr_method("docling", b"x") == {"m": 1}
        svc._ocr_with_tesseract = AsyncMock(return_value={"m": 2})
        assert await svc._run_ocr_method("tesseract", b"x") == {"m": 2}
        svc._ocr_with_easyocr = AsyncMock(return_value={"m": 3})
        assert await svc._run_ocr_method("easyocr", b"x") == {"m": 3}
        svc._ocr_with_ai_vision = AsyncMock(return_value={"m": 4})
        assert await svc._run_ocr_method("openai_vision", b"x") == {"m": 4}
        assert await svc._run_ocr_method("ai_vision", b"x") == {"m": 4}
        with pytest.raises(ValueError):
            await svc._run_ocr_method("bogus", b"x")

    async def test_ocr_with_docling(self):
        svc = self._svc()
        svc.ocr_readers = {}
        with pytest.raises(RuntimeError):
            await svc._ocr_with_docling(b"x")
        processor = MagicMock()
        processor.process_pdf = AsyncMock(return_value={
            "success": True, "extracted_text": "t", "page_texts": [], "page_count": 1,
            "total_chars": 1, "tables": []})
        svc.ocr_readers = {"docling": processor}
        result = await svc._ocr_with_docling(b"x")
        assert result["success"] is True
        processor.process_pdf = AsyncMock(return_value={"success": False, "error": "e"})
        result = await svc._ocr_with_docling(b"x")
        assert result["success"] is False
        processor.process_pdf = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc._ocr_with_docling(b"x")
        assert result["success"] is False

    async def test_ocr_with_tesseract(self):
        svc = self._svc()
        svc.ocr_readers = {}
        with pytest.raises(RuntimeError):
            await svc._ocr_with_tesseract(b"x")
        import integrations.pdf_processing.pdf_ocr_service as mod
        svc.ocr_readers = {"tesseract": MagicMock()}
        svc._pdf_to_images = AsyncMock(return_value=[MagicMock()])
        with patch.object(mod, "pytesseract") as pt:
            pt.image_to_string.return_value = "text"
            result = await svc._ocr_with_tesseract(b"x")
        assert result["success"] is True
        assert result["total_chars"] == 4
        pt.image_to_string.side_effect = RuntimeError("x")
        result = await svc._ocr_with_tesseract(b"x")
        assert result["success"] is False

    async def test_ocr_with_easyocr(self):
        svc = self._svc()
        svc.ocr_readers = {}
        with pytest.raises(RuntimeError):
            await svc._ocr_with_easyocr(b"x")
        import integrations.pdf_processing.pdf_ocr_service as mod
        svc.ocr_readers = {"easyocr": MagicMock()}
        svc._pdf_to_images = AsyncMock(return_value=[MagicMock()])
        svc.ocr_readers["easyocr"].readtext.return_value = [("box", "word", 0.9)]
        with patch.object(mod, "NUMPY_AVAILABLE", True), patch.object(mod, "np") as np:
            result = await svc._ocr_with_easyocr(b"x")
        assert result["success"] is True
        with patch.object(mod, "NUMPY_AVAILABLE", False):
            result = await svc._ocr_with_easyocr(b"x")
        assert result["success"] is False
        svc.ocr_readers["easyocr"].readtext.side_effect = RuntimeError("x")
        with patch.object(mod, "NUMPY_AVAILABLE", True), patch.object(mod, "np"):
            result = await svc._ocr_with_easyocr(b"x")
        assert result["success"] is False

    async def test_ocr_with_ai_vision(self):
        svc = self._svc()
        svc.llm_service = None
        with pytest.raises(RuntimeError):
            await svc._ocr_with_ai_vision(b"x")
        svc.llm_service = MagicMock()
        svc.llm_service.generate_completion = AsyncMock(return_value={"success": True, "content": "text"})
        svc._pdf_to_images = AsyncMock(return_value=[MagicMock()])
        result = await svc._ocr_with_ai_vision(b"x")
        assert result["success"] is True
        assert result["total_chars"] == 4
        svc.llm_service.generate_completion = AsyncMock(return_value={"success": False, "error": "e"})
        result = await svc._ocr_with_ai_vision(b"x")
        assert result["success"] is True
        assert result["total_chars"] == 0
        svc.llm_service.generate_completion = AsyncMock(side_effect=RuntimeError("x"))
        result = await svc._ocr_with_ai_vision(b"x")
        assert result["success"] is False

    async def test_byok_methods(self):
        svc = self._svc()
        assert svc._get_openai_api_key() is None or isinstance(svc._get_openai_api_key(), str)
        svc.use_byok = True
        svc.byok_manager = MagicMock()
        svc.byok_manager.get_api_key.return_value = "key"
        assert svc._get_openai_api_key() == "key"
        svc.byok_manager.get_api_key.side_effect = RuntimeError("x")
        svc.openai_api_key = "fallback"
        assert svc._get_openai_api_key() == "fallback"
        svc.openai_api_key = None
        with patch.dict(os.environ, {"OPENAI_API_KEY": "envkey"}):
            assert svc._get_openai_api_key() == "envkey"
        result = await svc._optimize_provider_selection(True, "cascade")
        assert result["optimized"] is True
        svc.byok_manager.get_optimal_provider.side_effect = RuntimeError("x")
        result = await svc._optimize_provider_selection(True, "cascade")
        assert result["optimized"] is False
        svc2 = self._svc()
        svc2.use_byok = False
        result = await svc2._optimize_provider_selection(True, "cascade")
        assert result["optimized"] is False
        await svc2._track_byok_usage({"best_result": {"method": "basic_pdf", "total_chars": 100}}, True)
        svc.use_byok = True
        svc.byok_manager = MagicMock()
        svc.byok_manager.track_usage = MagicMock()
        await svc._track_byok_usage({"best_result": {"method": "openai_vision", "total_chars": 100}}, True)
        assert svc.byok_manager.track_usage.called
        await svc._track_byok_usage({"best_result": {"method": "unknown", "total_chars": 100}}, True)
        svc.byok_manager.track_usage.side_effect = RuntimeError("x")
        await svc._track_byok_usage({"best_result": {"method": "tesseract", "total_chars": 100}}, True)
        assert svc._map_method_to_provider("openai_vision") == "openai"
        assert svc._map_method_to_provider("tesseract") == "openai"
        assert svc._map_method_to_provider("basic_pdf") is None
        assert svc._map_method_to_provider("zzz") is None

    async def test_pdf_to_images_fallback(self):
        svc = self._svc()
        with patch.dict(sys.modules, {"pdf2image": None, "fitz": None}):
            with patch("integrations.pdf_processing.pdf_ocr_service.PyPDF2") as pypdf:
                reader = MagicMock()
                page = MagicMock()
                page.mediabox.width = 100
                page.mediabox.height = 200
                page.extract_text.return_value = "some text"
                reader.pages = [page]
                pypdf.PdfReader.return_value = reader
                images = await svc._pdf_to_images(b"x")
        assert len(images) == 1
        # exception path
        with patch.dict(sys.modules, {"pdf2image": None, "fitz": None}):
            with patch("integrations.pdf_processing.pdf_ocr_service.PyPDF2") as pypdf:
                pypdf.PdfReader.side_effect = RuntimeError("x")
                images = await svc._pdf_to_images(b"x")
        assert images == []
        # fitz path
        from PIL import Image as PILImage
        import io as io_mod
        buf = io_mod.BytesIO()
        PILImage.new("RGB", (8, 8), "white").save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()
        fitz = MagicMock()
        doc = MagicMock()
        doc.page_count = 1
        pix = MagicMock()
        pix.tobytes.return_value = jpeg_bytes
        page = MagicMock()
        page.get_pixmap.return_value = pix
        doc.__getitem__.return_value = page
        fitz.open.return_value = doc
        with patch.dict(sys.modules, {"pdf2image": None, "fitz": fitz}):
            images = await svc._pdf_to_images(b"x")
        assert len(images) == 1
        # pdf2image path
        pdf2image = MagicMock()
        pdf2image.convert_from_bytes.return_value = [MagicMock()]
        with patch.dict(sys.modules, {"pdf2image": pdf2image}):
            with patch("asyncio.to_thread", new=AsyncMock(return_value=[MagicMock()])):
                images = await svc._pdf_to_images(b"x")
        assert len(images) == 1

    async def test_extract_and_process_images(self):
        svc = self._svc()
        result = await svc._extract_and_process_images(b"x", False)
        assert result["success"] is True
        fitz = MagicMock()
        doc = MagicMock()
        img = {"ext": "png", "width": 600, "height": 300, "image": b"imgdata"}
        doc.page_count = 1
        doc.__getitem__.return_value.get_images.return_value = [(0,)]
        doc.extract_image.return_value = img
        fitz.open.return_value = doc
        with patch.dict(sys.modules, {"fitz": fitz}):
            result = await svc._extract_and_process_images(b"x", False)
        assert result["images_found"] == 1
        assert "Large image" in result["image_descriptions"][0]["description"]
        img["width"] = 300
        with patch.dict(sys.modules, {"fitz": fitz}):
            result = await svc._extract_and_process_images(b"x", False)
        assert "Medium image" in result["image_descriptions"][0]["description"]
        img["width"] = 100
        with patch.dict(sys.modules, {"fitz": fitz}):
            result = await svc._extract_and_process_images(b"x", False)
        assert "Small image" in result["image_descriptions"][0]["description"]
        # advanced comprehension with byok
        from PIL import Image as PILImage
        import io as io_mod
        buf = io_mod.BytesIO()
        PILImage.new("RGB", (8, 8), "white").save(buf, format="PNG")
        png_bytes = buf.getvalue()
        img["image"] = png_bytes
        svc.use_byok = True
        svc.byok_manager = MagicMock()
        handler = MagicMock()
        handler._get_coordinated_vision_description = AsyncMock(return_value="desc")
        svc.byok_manager.get_handler.return_value = handler
        with patch.dict(sys.modules, {"fitz": fitz}):
            result = await svc._extract_and_process_images(b"x", True)
        assert result["image_descriptions"][0].get("ai_description") == "desc"
        handler._get_coordinated_vision_description = AsyncMock(side_effect=RuntimeError("x"))
        with patch.dict(sys.modules, {"fitz": fitz}):
            result = await svc._extract_and_process_images(b"x", True)
        assert "ai_description" not in result["image_descriptions"][0]
        # fitz missing -> PyPDF2 fallback
        with patch.dict(sys.modules, {"fitz": None}):
            with patch("integrations.pdf_processing.pdf_ocr_service.PyPDF2") as pypdf:
                reader = MagicMock()
                page = MagicMock()
                xobj = MagicMock()
                xobj.get_object.return_value = {"img": {"/Subtype": "/Image"}}
                page.__getitem__.return_value = {"/XObject": xobj}
                reader.pages = [page]
                pypdf.PdfReader.return_value = reader
                result = await svc._extract_and_process_images(b"x", False)
        assert result["images_found"] == 1
        with patch.dict(sys.modules, {"fitz": None}):
            with patch("integrations.pdf_processing.pdf_ocr_service.PyPDF2") as pypdf:
                pypdf.PdfReader.side_effect = RuntimeError("x")
                result = await svc._extract_and_process_images(b"x", False)
        assert result["success"] is True
        # error path
        with patch.dict(sys.modules, {"fitz": None}):
            with patch("integrations.pdf_processing.pdf_ocr_service.PyPDF2") as pypdf:
                pypdf.PdfReader.side_effect = RuntimeError("outer")
                with patch("integrations.pdf_processing.pdf_ocr_service.logger"):
                    result = await svc._extract_and_process_images(b"x", False)
        assert result["success"] is True

    async def test_combine_results(self):
        svc = self._svc()
        basic = {"method": "basic_pdf", "extracted_text": "t", "page_texts": [], "page_count": 1,
                 "total_chars": 1, "success": True}
        ocr = {"best_result": {"method": "docling", "extracted_text": "o", "page_texts": [],
                               "page_count": 1, "total_chars": 2}, "methods_tried": ["docling"],
               "success": True}
        result = svc._combine_results(basic, ocr, {"images_found": 0}, True)
        assert result["processing_summary"]["best_method"] == "docling"
        result = svc._combine_results(basic, None, None, False)
        assert result["processing_summary"]["best_method"] == "basic_pdf"
        result = svc._combine_results({"success": False, "method": "basic_pdf", "extracted_text": "",
                                       "page_texts": [], "page_count": 0, "total_chars": 0},
                                      ocr, None, True)
        assert result["success"] is True
        result = svc._combine_results({"success": False, "method": "basic_pdf", "extracted_text": "",
                                       "page_texts": [], "page_count": 0, "total_chars": 0},
                                      None, None, False)
        assert result["success"] is False

    async def test_create_error_result(self):
        svc = self._svc()
        result = svc._create_error_result("boom")
        assert result["success"] is False
        assert result["error"] == "boom"
        assert result["processing_summary"]["used_ocr"] is False
        assert result["service_status"]["basic_pdf"] is True
