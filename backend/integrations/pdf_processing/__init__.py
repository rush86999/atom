"""
PDF Processing Integration Module for ATOM

This module provides comprehensive PDF processing capabilities with OCR,
image comprehension, and memory storage integration.

Features:
- PDF text extraction with OCR fallback
- Image comprehension using AI vision
- Vector storage in LanceDB for semantic search
- Graceful degradation when external APIs are unavailable
- Integration with Atom's memory system
"""

from .pdf_memory_integration import PDFMemoryIntegration
from .pdf_memory_routes import router as pdf_memory_router

# Optional OCR router (requires PIL/Pillow)
try:
    from .pdf_ocr_routes import router as pdf_ocr_router
    from .pdf_ocr_service import PDFOCRService
    OCR_AVAILABLE = True
except ImportError:
    pdf_ocr_router = None
    PDFOCRService = None
    OCR_AVAILABLE = False

__all__ = [
    "PDFOCRService",
    "PDFMemoryIntegration",
    "pdf_ocr_router",
    "pdf_memory_router",
    "OCR_AVAILABLE",
]

__version__ = "1.0.0"
