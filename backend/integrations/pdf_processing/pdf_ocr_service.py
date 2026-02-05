import asyncio
import base64
import io
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image
import PyPDF2

# Optional numpy import
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

# BYOK Integration
try:
    from core.byok_endpoints import get_byok_manager
    BYOK_AVAILABLE = True
except ImportError:
    try:
        from backend.core.byok_endpoints import get_byok_manager
        BYOK_AVAILABLE = True
    except ImportError:
        BYOK_AVAILABLE = False
        get_byok_manager = None

try:
    from core.llm.byok_handler import BYOKHandler
    BYOK_HANDLER_AVAILABLE = True
except ImportError:
    try:
        from backend.core.llm.byok_handler import BYOKHandler
        BYOK_HANDLER_AVAILABLE = True
    except ImportError:
        BYOK_HANDLER_AVAILABLE = False
        BYOKHandler = None

# Docling integration (highest priority OCR - optional)
try:
    from core.docling_processor import get_docling_processor, is_docling_available
    DOCLING_AVAILABLE = is_docling_available()
except ImportError:
    try:
        from backend.core.docling_processor import get_docling_processor, is_docling_available
        DOCLING_AVAILABLE = is_docling_available()
    except ImportError:
        DOCLING_AVAILABLE = False
        get_docling_processor = None

# Optional imports for advanced features
try:
    import pytesseract

    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import easyocr

    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


class PDFOCRService:
    """
    Enhanced PDF processing service with OCR capabilities and fallback mechanisms.
    Supports both searchable PDFs and scanned/image-based PDFs.
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        tesseract_path: Optional[str] = None,
        easyocr_languages: List[str] = None,
        use_byok: bool = True,
    ):
        """
        Initialize the PDF OCR service.

        Args:
            openai_api_key: OpenAI API key for advanced image comprehension
            tesseract_path: Path to tesseract executable (if not in PATH)
            easyocr_languages: List of languages for EasyOCR (default: ['en'])
            use_byok: Whether to use BYOK system for AI provider management
        """
        self.openai_api_key = openai_api_key
        self.tesseract_path = tesseract_path
        self.easyocr_languages = easyocr_languages or ["en"]
        self.use_byok = use_byok and BYOK_AVAILABLE

        # Initialize BYOK manager if available
        self.byok_manager = None
        if self.use_byok:
            try:
                self.byok_manager = get_byok_manager()
                logger.info("BYOK system initialized for PDF processing")
            except Exception as e:
                logger.warning(f"Failed to initialize BYOK system: {e}")
                self.use_byok = False

        # Initialize OCR readers
        self._init_ocr_readers()

        # Service availability flags
        self.service_status = self._check_service_availability()

        logger.info(f"PDF OCR Service initialized - Status: {self.service_status}")

    def _init_ocr_readers(self):
        """Initialize OCR readers based on available libraries."""
        self.ocr_readers = {}

        # Docling (highest priority - advanced document understanding with OCR)
        if DOCLING_AVAILABLE:
            try:
                self.ocr_readers["docling"] = get_docling_processor()
                logger.info("Docling document processor initialized (highest priority)")
            except Exception as e:
                logger.warning(f"Failed to initialize Docling: {e}")

        # Tesseract OCR
        if TESSERACT_AVAILABLE:
            try:
                if self.tesseract_path:
                    pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
                self.ocr_readers["tesseract"] = pytesseract
                logger.info("Tesseract OCR initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Tesseract: {e}")

        # EasyOCR
        if EASYOCR_AVAILABLE:
            try:
                self.ocr_readers["easyocr"] = easyocr.Reader(self.easyocr_languages)
                logger.info("EasyOCR initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize EasyOCR: {e}")

        # AI Vision (for advanced image comprehension) - Using BYOKHandler
        if BYOK_HANDLER_AVAILABLE:
            try:
                self.ocr_readers["ai_vision"] = BYOKHandler(workspace_id="default")
                logger.info("AI Vision (BYOKHandler) initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize AI Vision (BYOKHandler): {e}")
        elif OPENAI_AVAILABLE:
            openai_key = self._get_openai_api_key()
            if openai_key:
                try:
                    self.ocr_readers["openai"] = OpenAI(api_key=openai_key)
                    logger.info("OpenAI Vision initialized")
                except Exception as e:
                    logger.warning(f"Failed to initialize OpenAI Vision: {e}")

    def _check_service_availability(self) -> Dict[str, bool]:
        """Check availability of different OCR services."""
        status = {
            "basic_pdf": True,  # Always available (PyPDF2)
            "docling": "docling" in self.ocr_readers,
            "tesseract": "tesseract" in self.ocr_readers,
            "easyocr": "easyocr" in self.ocr_readers,
            "openai_vision": "openai" in self.ocr_readers or "ai_vision" in self.ocr_readers,
            "fallback_available": len(self.ocr_readers) > 0,
            "byok_integrated": self.use_byok and (self.byok_manager is not None or "ai_vision" in self.ocr_readers),
        }
        return status

    async def process_pdf(
        self,
        pdf_data: Union[bytes, str, Path],
        use_ocr: bool = True,
        extract_images: bool = True,
        use_advanced_comprehension: bool = False,
        fallback_strategy: str = "cascade",
    ) -> Dict[str, Any]:
        """
        Process PDF with optional OCR and image comprehension.

        Args:
            pdf_data: PDF file as bytes, file path, or Path object
            use_ocr: Whether to use OCR for scanned PDFs
            extract_images: Whether to extract and process images
            use_advanced_comprehension: Whether to use AI for image understanding
            fallback_strategy: "cascade" (try best first) or "parallel" (try all)

        Returns:
            Dictionary with extracted text, metadata, and processing results
        """
        try:
            # Convert input to bytes if it's a file path
            if isinstance(pdf_data, (str, Path)):
                with open(pdf_data, "rb") as f:
                    pdf_data = f.read()

            # Step 1: Try basic text extraction first
            basic_result = await self._extract_basic_text(pdf_data)

            # Step 2: Check if we need OCR (low text content or specific request)
            needs_ocr = use_ocr and (
                basic_result["text_ratio"] < 0.1
                or len(basic_result["extracted_text"].strip()) < 100
            )

            # Step 2.5: Optimize provider selection using BYOK if available
            if self.use_byok and needs_ocr:
                provider_optimization = await self._optimize_provider_selection(
                    use_advanced_comprehension, fallback_strategy
                )
                logger.info(f"BYOK provider optimization: {provider_optimization}")

            # Step 3: Process with OCR if needed
            ocr_result = None
            if needs_ocr:
                ocr_result = await self._process_with_ocr(
                    pdf_data, fallback_strategy, use_advanced_comprehension
                )

                # Track usage with BYOK if available
                if self.use_byok and ocr_result:
                    await self._track_byok_usage(ocr_result, use_advanced_comprehension)

            # Step 4: Extract and process images if requested
            image_results = None
            if extract_images:
                image_results = await self._extract_and_process_images(
                    pdf_data, use_advanced_comprehension
                )

            # Combine results
            final_result = self._combine_results(
                basic_result, ocr_result, image_results, needs_ocr
            )

            return final_result

        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            return self._create_error_result(str(e))

    async def _extract_basic_text(self, pdf_data: bytes) -> Dict[str, Any]:
        """Extract text using basic PyPDF2 method."""
        try:
            pdf_file = io.BytesIO(pdf_data)
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            text_content = []
            total_chars = 0
            page_count = len(pdf_reader.pages)

            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                text_content.append(
                    {
                        "page": page_num + 1,
                        "text": page_text,
                        "char_count": len(page_text),
                    }
                )
                total_chars += len(page_text)

            # Calculate text ratio (rough estimate of searchable content)
            text_ratio = min(total_chars / (page_count * 1000), 1.0)  # Normalize

            return {
                "method": "basic_pdf",
                "extracted_text": "\n".join([p["text"] for p in text_content]),
                "page_texts": text_content,
                "page_count": page_count,
                "total_chars": total_chars,
                "text_ratio": text_ratio,
                "success": True,
            }

        except Exception as e:
            logger.warning(f"Basic text extraction failed: {e}")
            return {
                "method": "basic_pdf",
                "extracted_text": "",
                "page_texts": [],
                "page_count": 0,
                "total_chars": 0,
                "text_ratio": 0.0,
                "success": False,
                "error": str(e),
            }

    async def _process_with_ocr(
        self, pdf_data: bytes, fallback_strategy: str, use_advanced_comprehension: bool
    ) -> Dict[str, Any]:
        """Process PDF using OCR with fallback strategy."""
        methods_tried = []
        best_result = None

        ocr_methods = self._get_available_ocr_methods(use_advanced_comprehension)

        if fallback_strategy == "cascade":
            # Try methods in order of preference
            for method_name in ocr_methods:
                try:
                    logger.info(f"Trying OCR method: {method_name}")
                    result = await self._run_ocr_method(method_name, pdf_data)
                    methods_tried.append(method_name)

                    if result["success"] and result["total_chars"] > 0:
                        best_result = result
                        break  # Found good result, stop trying

                except Exception as e:
                    logger.warning(f"OCR method {method_name} failed: {e}")
                    methods_tried.append(f"{method_name}_failed")

        elif fallback_strategy == "parallel":
            # Try all methods and pick the best
            results = []
            for method_name in ocr_methods:
                try:
                    result = await self._run_ocr_method(method_name, pdf_data)
                    methods_tried.append(method_name)
                    if result["success"]:
                        results.append(result)
                except Exception as e:
                    logger.warning(f"OCR method {method_name} failed: {e}")
                    methods_tried.append(f"{method_name}_failed")

            if results:
                # Pick result with most text
                best_result = max(results, key=lambda x: x["total_chars"])

        return {
            "best_result": best_result,
            "methods_tried": methods_tried,
            "success": best_result is not None,
        }

    def _get_available_ocr_methods(self, use_advanced_comprehension: bool) -> List[str]:
        """Get available OCR methods in priority order."""
        methods = []

        # Use BYOK optimization if available
        if self.use_byok and use_advanced_comprehension:
            try:
                optimal_provider = self.byok_manager.get_optimal_provider(
                    "image_comprehension"
                )
                if optimal_provider == "openai" and "openai" in self.ocr_readers:
                    methods.append("openai_vision")
                    logger.info(
                        f"BYOK selected {optimal_provider} for image comprehension"
                    )
            except Exception as e:
                logger.warning(f"BYOK optimization failed: {e}")

        # Docling first (highest priority - best OCR with layout analysis)
        if "docling" in self.ocr_readers:
            methods.insert(0, "docling")

        # Fallback to default logic if BYOK not available or failed
        if not methods and use_advanced_comprehension and "openai" in self.ocr_readers:
            methods.append("openai_vision")

        # Then standard OCR methods
        if "easyocr" in self.ocr_readers:
            methods.append("easyocr")

        if "tesseract" in self.ocr_readers:
            methods.append("tesseract")

        return methods

    async def _run_ocr_method(
        self, method_name: str, pdf_data: bytes
    ) -> Dict[str, Any]:
        """Run specific OCR method on PDF."""
        if method_name == "docling":
            return await self._ocr_with_docling(pdf_data)
        elif method_name == "tesseract":
            return await self._ocr_with_tesseract(pdf_data)
        elif method_name == "easyocr":
            return await self._ocr_with_easyocr(pdf_data)
        elif method_name in ["openai_vision", "ai_vision"]:
            return await self._ocr_with_ai_vision(pdf_data)
        else:
            raise ValueError(f"Unknown OCR method: {method_name}")

    async def _ocr_with_docling(self, pdf_data: bytes) -> Dict[str, Any]:
        """Extract text using Docling with advanced OCR and layout analysis."""
        if "docling" not in self.ocr_readers:
            raise RuntimeError("Docling not available")

        try:
            processor = self.ocr_readers["docling"]
            result = await processor.process_pdf(pdf_data, use_ocr=True)

            if result.get("success"):
                return {
                    "method": "docling",
                    "extracted_text": result.get("extracted_text", ""),
                    "page_texts": result.get("page_texts", []),
                    "page_count": result.get("page_count", 0),
                    "total_chars": result.get("total_chars", 0),
                    "tables": result.get("tables", []),
                    "success": True,
                }
            else:
                raise RuntimeError(result.get("error", "Docling processing failed"))

        except Exception as e:
            logger.error(f"Docling OCR failed: {e}")
            return {
                "method": "docling",
                "extracted_text": "",
                "page_texts": [],
                "page_count": 0,
                "total_chars": 0,
                "success": False,
                "error": str(e),
            }

    async def _ocr_with_tesseract(self, pdf_data: bytes) -> Dict[str, Any]:
        """Extract text using Tesseract OCR."""
        if "tesseract" not in self.ocr_readers:
            raise RuntimeError("Tesseract not available")

        try:
            # Convert PDF to images for OCR
            images = await self._pdf_to_images(pdf_data)
            text_content = []
            total_chars = 0

            for page_num, image in enumerate(images):
                # Convert PIL image to format tesseract expects
                text = pytesseract.image_to_string(image)
                text_content.append(
                    {"page": page_num + 1, "text": text, "char_count": len(text)}
                )
                total_chars += len(text)

            return {
                "method": "tesseract",
                "extracted_text": "\n".join([p["text"] for p in text_content]),
                "page_texts": text_content,
                "page_count": len(images),
                "total_chars": total_chars,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            return {
                "method": "tesseract",
                "extracted_text": "",
                "page_texts": [],
                "page_count": 0,
                "total_chars": 0,
                "success": False,
                "error": str(e),
            }

    async def _ocr_with_easyocr(self, pdf_data: bytes) -> Dict[str, Any]:
        """Extract text using EasyOCR."""
        if "easyocr" not in self.ocr_readers:
            raise RuntimeError("EasyOCR not available")

        try:
            images = await self._pdf_to_images(pdf_data)
            text_content = []
            total_chars = 0

            for page_num, image in enumerate(images):
                # Convert PIL image to numpy array (if numpy is available)
                if not NUMPY_AVAILABLE:
                    logger.error("NumPy is required for EasyOCR but not available")
                    raise ImportError("NumPy is required for EasyOCR")

                image_np = np.array(image)

                # Run OCR
                results = self.ocr_readers["easyocr"].readtext(image_np)

                # Combine text from all detections
                page_text = " ".join([result[1] for result in results])
                text_content.append(
                    {
                        "page": page_num + 1,
                        "text": page_text,
                        "char_count": len(page_text),
                    }
                )
                total_chars += len(page_text)

            return {
                "method": "easyocr",
                "extracted_text": "\n".join([p["text"] for p in text_content]),
                "page_texts": text_content,
                "page_count": len(images),
                "total_chars": total_chars,
                "success": True,
            }

        except Exception as e:
            logger.error(f"EasyOCR failed: {e}")
            return {
                "method": "easyocr",
                "extracted_text": "",
                "page_texts": [],
                "page_count": 0,
                "total_chars": 0,
                "success": False,
                "error": str(e),
            }

    async def _ocr_with_ai_vision(self, pdf_data: bytes) -> Dict[str, Any]:
        """Extract text and comprehend images using AI Vision via BYOKHandler."""
        if "ai_vision" not in self.ocr_readers and "openai" not in self.ocr_readers:
            raise RuntimeError("AI Vision not available")

        import base64

        try:
            images = await self._pdf_to_images(pdf_data)
            text_content = []
            total_chars = 0
            image_descriptions = []

            for page_num, image in enumerate(images):
                # Convert PIL image to bytes for API
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format="PNG")
                img_byte_arr = img_byte_arr.getvalue()

                # Use BYOKHandler if available
                if "ai_vision" in self.ocr_readers:
                    handler = self.ocr_readers["ai_vision"]
                    page_text = await handler.generate_response(
                        prompt="Extract all text from this image and describe any visual elements that might be important for understanding the document.",
                        image_payload=[{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64.b64encode(img_byte_arr).decode('utf-8')}"}}],
                        task_type="pdf_ocr",
                        prefer_cost=True
                    )
                else:
                    # Legacy OpenAI fallback
                    response = self.ocr_readers["openai"].chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Extract all text from this image and describe any visual elements that might be important for understanding the document.",
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{base64.b64encode(img_byte_arr).decode('utf-8')}"
                                        },
                                    },
                                ],
                            }
                        ],
                        max_tokens=2000,
                    )
                    page_text = response.choices[0].message.content
                text_content.append(
                    {
                        "page": page_num + 1,
                        "text": page_text,
                        "char_count": len(page_text),
                    }
                )
                total_chars += len(page_text)

                image_descriptions.append(
                    {"page": page_num + 1, "description": page_text}
                )

            return {
                "method": "openai_vision",
                "extracted_text": "\n".join([p["text"] for p in text_content]),
                "page_texts": text_content,
                "page_count": len(images),
                "total_chars": total_chars,
                "image_descriptions": image_descriptions,
                "success": True,
            }

        except Exception as e:
            logger.error(f"OpenAI Vision failed: {e}")
            return {
                "method": "openai_vision",
                "extracted_text": "",
                "page_texts": [],
                "page_count": 0,
                "total_chars": 0,
                "success": False,
                "error": str(e),
            }

    # BYOK Integration Methods

    def _get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key from BYOK system or fallback."""
        if self.use_byok and self.byok_manager:
            try:
                # Try to get API key from BYOK system
                api_key = self.byok_manager.get_api_key("openai")
                if api_key:
                    return api_key
            except Exception as e:
                logger.warning(f"Failed to get OpenAI key from BYOK: {e}")

        # Fallback to constructor parameter or environment variable
        if self.openai_api_key:
            return self.openai_api_key

        return os.getenv("OPENAI_API_KEY")

    async def _optimize_provider_selection(
        self, use_advanced_comprehension: bool, fallback_strategy: str
    ) -> Dict[str, Any]:
        """Optimize provider selection using BYOK system."""
        if not self.use_byok or not self.byok_manager:
            return {"optimized": False, "reason": "BYOK not available"}

        try:
            # Determine task type based on requirements
            if use_advanced_comprehension:
                task_type = "image_comprehension"
            else:
                task_type = "pdf_ocr"

            # Get optimal provider
            optimal_provider = self.byok_manager.get_optimal_provider(task_type)

            return {
                "optimized": True,
                "task_type": task_type,
                "optimal_provider": optimal_provider,
                "fallback_strategy": fallback_strategy,
                "available_providers": list(self.ocr_readers.keys()),
            }

        except Exception as e:
            logger.error(f"Provider optimization failed: {e}")
            return {"optimized": False, "error": str(e)}

    async def _track_byok_usage(
        self, ocr_result: Dict[str, Any], use_advanced_comprehension: bool
    ):
        """Track usage with BYOK system."""
        if not self.use_byok or not self.byok_manager:
            return

        try:
            # Determine which provider was used
            best_method = ocr_result.get("best_result", {}).get("method", "")
            provider_id = self._map_method_to_provider(best_method)

            if not provider_id:
                return

            # Estimate tokens used (rough calculation)
            total_chars = ocr_result.get("best_result", {}).get("total_chars", 0)
            estimated_tokens = max(
                total_chars // 4, 100
            )  # Rough estimate: ~4 chars per token

            # Track successful usage
            self.byok_manager.track_usage(
                provider_id=provider_id, success=True, tokens_used=estimated_tokens
            )

            logger.debug(
                f"Tracked BYOK usage: {provider_id}, {estimated_tokens} tokens"
            )

        except Exception as e:
            logger.warning(f"Failed to track BYOK usage: {e}")

    def _map_method_to_provider(self, method: str) -> Optional[str]:
        """Map OCR method to BYOK provider ID."""
        method_to_provider = {
            "openai_vision": "openai",
            "tesseract": "openai",  # Tesseract doesn't have BYOK provider, map to default
            "easyocr": "openai",  # EasyOCR doesn't have BYOK provider, map to default
            "basic_pdf": None,  # No BYOK tracking for basic extraction
        }
        return method_to_provider.get(method)

    async def _pdf_to_images(self, pdf_data: bytes) -> List[Image.Image]:
        """Convert PDF to list of PIL Images."""
        try:
            # Try using pdf2image if available (best quality)
            try:
                from pdf2image import convert_from_bytes

                logger.debug("Using pdf2image for PDF to image conversion")
                # Convert PDF to list of images at 200 DPI for OCR quality
                images = await asyncio.to_thread(
                    convert_from_bytes, pdf_data, dpi=200, fmt="jpeg"
                )
                logger.info(f"Converted {len(images)} pages using pdf2image")
                return images

            except ImportError:
                logger.warning(
                    "pdf2image not available, using fallback method. "
                    "Install with: pip install pdf2image"
                )

                # Fallback: Try to render PDF pages using PyMuPDF (fitz) if available
                try:
                    import fitz

                    logger.debug("Using PyMuPDF (fitz) for PDF to image conversion")
                    pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
                    images = []

                    for page_num in range(pdf_document.page_count):
                        page = pdf_document[page_num]
                        # Render page to pixmap (zoom=2 for better quality)
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        img_data = pix.tobytes("jpeg")
                        img = Image.open(io.BytesIO(img_data))
                        images.append(img)

                    pdf_document.close()
                    logger.info(f"Converted {len(images)} pages using PyMuPDF")
                    return images

                except ImportError:
                    logger.warning(
                        "PyMuPDF not available. Install with: pip install PyMuPDF"
                    )

                    # Final fallback: Create placeholder images with page info
                    pdf_file = io.BytesIO(pdf_data)
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    page_count = len(pdf_reader.pages)

                    logger.warning(
                        f"Using placeholder images for {page_count} pages. "
                        "Install pdf2image or PyMuPDF for proper conversion."
                    )

                    images = []
                    for i, page in enumerate(pdf_reader.pages):
                        # Try to extract page dimensions
                        try:
                            mediabox = page.mediabox
                            width = int(mediabox.width)
                            height = int(mediabox.height)
                            # Limit max size to avoid memory issues
                            width = min(width, 2000)
                            height = min(height, 2000)
                        except:
                            width, height = 800, 1000

                        # Create a white image with extracted text overlay if possible
                        img = Image.new("RGB", (width, height), color="white")

                        # Try to extract text and add to image (basic rendering)
                        try:
                            text = page.extract_text()
                            if text and text.strip():
                                from PIL import ImageDraw, ImageFont

                                draw = ImageDraw.Draw(img)
                                # Use default font
                                try:
                                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
                                except:
                                    font = ImageFont.load_default()

                                # Draw text (first 500 chars to avoid overflow)
                                lines = text[:500].split("\n")
                                y_offset = 20
                                for line in lines[:30]:  # Max 30 lines
                                    if line.strip():
                                        draw.text((20, y_offset), line, fill="black", font=font)
                                        y_offset += 20
                        except Exception as e:
                            logger.debug(f"Could not add text to placeholder image: {e}")

                        images.append(img)

                    return images

        except Exception as e:
            logger.error(f"PDF to image conversion failed: {e}")
            return []

    async def _extract_and_process_images(
        self, pdf_data: bytes, use_advanced_comprehension: bool
    ) -> Dict[str, Any]:
        """Extract and process images from PDF."""
        try:
            images_found = 0
            image_descriptions = []

            # Try using PyMuPDF (fitz) which has excellent image extraction
            try:
                import fitz

                logger.debug("Using PyMuPDF for image extraction")
                pdf_document = fitz.open(stream=pdf_data, filetype="pdf")

                for page_num in range(pdf_document.page_count):
                    page = pdf_document[page_num]
                    image_list = page.get_images(full=True)

                    for img_index, img in enumerate(image_list):
                        xref = img[0]
                        base_image = pdf_document.extract_image(xref)

                        if base_image:
                            images_found += 1
                            image_info = {
                                "page": page_num + 1,
                                "index": img_index,
                                "format": base_image.get("ext", "unknown"),
                                "width": base_image.get("width", 0),
                                "height": base_image.get("height", 0),
                                "size_bytes": len(base_image.get("image", b"")),
                            }

                            # Basic description based on dimensions
                            if base_image.get("width", 0) > 500:
                                image_info["description"] = "Large image (possibly photo or chart)"
                            elif base_image.get("width", 0) > 200:
                                image_info["description"] = "Medium image (possibly icon or diagram)"
                            else:
                                image_info["description"] = "Small image (possibly icon or bullet point)"

                            image_descriptions.append(image_info)

                            # Advanced comprehension if requested and BYOK available
                            if use_advanced_comprehension and self.use_byok and self.byok_manager:
                                try:
                                    # Save image to temp file for processing
                                    import tempfile

                                    with tempfile.NamedTemporaryFile(
                                        delete=False, suffix=f".{base_image.get('ext', 'png')}"
                                    ) as tmp:
                                        tmp.write(base_image["image"])
                                        tmp_path = tmp.name

                                    # Use vision model to describe image
                                    from PIL import Image as PILImage
                                    import base64
                                    import io

                                    img_pil = PILImage.open(tmp_path)

                                    # Convert PIL image to base64 for vision API
                                    buffered = io.BytesIO()
                                    img_pil.save(buffered, format="PNG")
                                    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

                                    # Get vision description using BYOK handler
                                    try:
                                        byok_handler = self.byok_manager.get_handler(
                                            tenant_id="default",  # System-level operation
                                            db=None
                                        )

                                        # Use coordinated vision description
                                        vision_description = await byok_handler._get_coordinated_vision_description(
                                            image_payload=img_base64,
                                            tenant_plan="free",
                                            is_managed=True
                                        )

                                        if vision_description:
                                            image_info["ai_description"] = vision_description
                                            logger.info(f"Generated AI description for image on page {page_num + 1}")

                                    except Exception as vision_error:
                                        logger.warning(f"Vision API call failed: {vision_error}")
                                        # Fall back to basic description (already set above)

                                    # Clean up temp file
                                    os.unlink(tmp_path)

                                except Exception as e:
                                    logger.debug(f"Advanced image comprehension failed: {e}")

                pdf_document.close()

            except ImportError:
                logger.warning("PyMuPDF not available for image extraction")

                # Fallback: Try using PyPDF2 to count images
                try:
                    pdf_file = io.BytesIO(pdf_data)
                    pdf_reader = PyPDF2.PdfReader(pdf_file)

                    for page_num, page in enumerate(pdf_reader.pages):
                        if "/XObject" in page["/Resources"]:
                            xObject = page["/Resources"]["/XObject"].get_object()

                            for obj in xObject:
                                if xObject[obj]["/Subtype"] == "/Image":
                                    images_found += 1
                                    image_descriptions.append(
                                        {
                                            "page": page_num + 1,
                                            "description": "Image detected (limited info without PyMuPDF)",
                                        }
                                    )

                except Exception as e:
                    logger.debug(f"PyPDF2 image extraction failed: {e}")

            logger.info(f"Extracted {images_found} images from PDF")
            return {
                "images_found": images_found,
                "image_descriptions": image_descriptions,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Image extraction failed: {e}")
            return {
                "images_found": 0,
                "image_descriptions": [],
                "success": False,
                "error": str(e),
            }

    def _combine_results(
        self,
        basic_result: Dict[str, Any],
        ocr_result: Optional[Dict[str, Any]],
        image_results: Optional[Dict[str, Any]],
        used_ocr: bool,
    ) -> Dict[str, Any]:
        """Combine results from different processing methods."""
        # Determine which text to use
        if used_ocr and ocr_result and ocr_result["success"]:
            best_text_result = ocr_result["best_result"]
        else:
            best_text_result = basic_result

        # Combine all information
        combined_result = {
            "processing_summary": {
                "used_ocr": used_ocr,
                "ocr_methods_tried": ocr_result["methods_tried"] if ocr_result else [],
                "best_method": best_text_result["method"],
                "total_pages": best_text_result["page_count"],
                "total_characters": best_text_result["total_chars"],
            },
            "extracted_content": {
                "text": best_text_result["extracted_text"],
                "page_breakdown": best_text_result["page_texts"],
                "images": image_results or {},
            },
            "service_status": self.service_status,
            "success": basic_result["success"] or (ocr_result and ocr_result["success"])
            if ocr_result
            else basic_result["success"],
        }
