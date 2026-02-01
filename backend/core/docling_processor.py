"""
Docling Document Processor for Atom Memory

Unified document parsing and OCR service using docling.
Supports: PDF, DOCX, PPTX, XLSX, HTML, images (PNG, TIFF, JPEG), and more.
"""

import asyncio
import io
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Docling availability check
try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    DocumentConverter = None
    InputFormat = None

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


class DoclingDocumentProcessor:
    """
    Primary document processor using docling for unified parsing and OCR.
    
    Features:
    - Multi-format support: PDF, DOCX, PPTX, XLSX, HTML, images
    - Extensive OCR for scanned documents
    - Table structure extraction
    - Layout analysis with reading order detection
    - Multiple export formats: Markdown, JSON, HTML
    - BYOK integration for API key management
    """
    
    # Supported file extensions and their InputFormat mapping
    SUPPORTED_EXTENSIONS = {
        'pdf': 'PDF',
        'docx': 'DOCX',
        'doc': 'DOCX',
        'pptx': 'PPTX',
        'ppt': 'PPTX',
        'xlsx': 'XLSX',
        'xls': 'XLSX',
        'html': 'HTML',
        'htm': 'HTML',
        'png': 'IMAGE',
        'jpg': 'IMAGE',
        'jpeg': 'IMAGE',
        'tiff': 'IMAGE',
        'tif': 'IMAGE',
        'bmp': 'IMAGE',
        'md': 'MD',
        'asciidoc': 'ASCIIDOC',
    }
    
    def __init__(self, use_byok: bool = True, enable_ocr: bool = True):
        """
        Initialize the Docling document processor.
        
        Args:
            use_byok: Whether to use BYOK system for API key management
            enable_ocr: Whether to enable OCR for scanned documents
        """
        self.use_byok = use_byok and BYOK_AVAILABLE
        self.enable_ocr = enable_ocr
        self.converter: Optional[DocumentConverter] = None
        self.byok_manager = None
        
        # Initialize BYOK manager if available
        if self.use_byok:
            try:
                self.byok_manager = get_byok_manager()
                logger.info("BYOK system initialized for Docling processor")
            except Exception as e:
                logger.warning(f"Failed to initialize BYOK system: {e}")
                self.use_byok = False
        
        # Initialize docling converter
        self._init_converter()
        
        logger.info(f"DoclingDocumentProcessor initialized - Available: {DOCLING_AVAILABLE}")
    
    def _init_converter(self):
        """Initialize the docling DocumentConverter."""
        if not DOCLING_AVAILABLE:
            logger.warning("Docling not available. Install with: pip install docling")
            return
        
        try:
            # Initialize with default settings (OCR enabled)
            self.converter = DocumentConverter()
            logger.info("Docling DocumentConverter initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Docling converter: {e}")
            self.converter = None
    
    @property
    def is_available(self) -> bool:
        """Check if docling processing is available."""
        return DOCLING_AVAILABLE and self.converter is not None
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported file extensions."""
        return list(self.SUPPORTED_EXTENSIONS.keys())
    
    def is_format_supported(self, file_extension: str) -> bool:
        """Check if a file format is supported."""
        ext = file_extension.lower().lstrip('.')
        return ext in self.SUPPORTED_EXTENSIONS
    
    async def process_document(
        self,
        source: Union[bytes, str, Path],
        file_type: Optional[str] = None,
        file_name: Optional[str] = None,
        export_format: str = "markdown",
    ) -> Dict[str, Any]:
        """
        Process a document and extract content.
        
        Args:
            source: Document content as bytes, file path string, or Path object
            file_type: Optional file type/extension (e.g., 'pdf', 'docx')
            file_name: Optional file name for context
            export_format: Output format - 'markdown', 'json', 'text', or 'html'
        
        Returns:
            Dictionary with extracted content and metadata
        """
        if not self.is_available:
            return self._create_error_result("Docling not available")
        
        try:
            # Convert source to appropriate format for docling
            result = await self._convert_document(source, file_type)
            
            if result is None:
                return self._create_error_result("Document conversion failed")
            
            # Extract content in requested format
            extracted = self._extract_content(result, export_format)
            
            # Extract additional structured data
            tables = self._extract_tables(result)
            images = self._extract_images(result)
            metadata = self._extract_metadata(result)
            
            return {
                "success": True,
                "method": "docling",
                "content": extracted["content"],
                "export_format": export_format,
                "tables": tables,
                "images": images,
                "metadata": metadata,
                "file_name": file_name,
                "file_type": file_type,
                "page_count": metadata.get("page_count", 0),
                "total_chars": len(extracted["content"]),
            }
            
        except Exception as e:
            logger.error(f"Docling document processing failed: {e}")
            return self._create_error_result(str(e))
    
    async def _convert_document(
        self,
        source: Union[bytes, str, Path],
        file_type: Optional[str] = None
    ):
        """Convert document using docling."""
        try:
            if self.converter is None:
                logger.warning("Docling converter not initialized")
                return None
                
            # Handle different source types
            if isinstance(source, bytes):
                # For bytes, write to temp file since docling works best with files
                import tempfile
                suffix = f".{file_type}" if file_type else ".pdf"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(source)
                    tmp_path = tmp.name
                
                try:
                    result = self.converter.convert(tmp_path)
                finally:
                    # Clean up temp file
                    os.unlink(tmp_path)
                    
            elif isinstance(source, (str, Path)):
                # Direct file path or URL
                result = self.converter.convert(str(source))
            else:
                raise ValueError(f"Unsupported source type: {type(source)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Docling conversion error: {e}")
            return None
    
    def _extract_content(self, result, export_format: str) -> Dict[str, str]:
        """Extract content in the requested format."""
        try:
            doc = result.document
            
            if export_format == "markdown":
                content = doc.export_to_markdown()
            elif export_format == "json":
                content = doc.model_dump_json(indent=2)
            elif export_format == "text":
                content = doc.export_to_markdown()  # Markdown is readable as text
            elif export_format == "html":
                # Try HTML export if available, otherwise convert from markdown
                try:
                    content = doc.export_to_html()
                except AttributeError:
                    content = doc.export_to_markdown()
            else:
                content = doc.export_to_markdown()
            
            return {"content": content}
            
        except Exception as e:
            logger.warning(f"Content extraction failed: {e}")
            return {"content": ""}
    
    def _extract_tables(self, result) -> List[Dict[str, Any]]:
        """Extract table data from document."""
        tables = []
        try:
            doc = result.document
            
            # Iterate through document elements looking for tables
            if hasattr(doc, 'tables'):
                for idx, table in enumerate(doc.tables):
                    table_data = {
                        "index": idx,
                        "data": [],
                        "num_rows": 0,
                        "num_cols": 0,
                    }
                    
                    # Extract table cells if available
                    if hasattr(table, 'data'):
                        table_data["data"] = table.data
                        table_data["num_rows"] = len(table.data)
                        if table.data:
                            table_data["num_cols"] = len(table.data[0])
                    
                    tables.append(table_data)
                    
        except Exception as e:
            logger.debug(f"Table extraction note: {e}")
        
        return tables
    
    def _extract_images(self, result) -> List[Dict[str, Any]]:
        """Extract image information from document."""
        images = []
        try:
            doc = result.document
            
            if hasattr(doc, 'pictures'):
                for idx, picture in enumerate(doc.pictures):
                    images.append({
                        "index": idx,
                        "caption": getattr(picture, 'caption', ''),
                        "classification": getattr(picture, 'classification', 'unknown'),
                    })
                    
        except Exception as e:
            logger.debug(f"Image extraction note: {e}")
        
        return images
    
    def _extract_metadata(self, result) -> Dict[str, Any]:
        """Extract document metadata."""
        metadata = {
            "page_count": 0,
            "title": "",
            "author": "",
            "created": "",
            "modified": "",
        }
        
        try:
            doc = result.document
            
            # Get page count
            if hasattr(doc, 'pages'):
                metadata["page_count"] = len(doc.pages)
            
            # Get document metadata if available
            if hasattr(doc, 'metadata'):
                doc_meta = doc.metadata
                metadata["title"] = getattr(doc_meta, 'title', '')
                metadata["author"] = getattr(doc_meta, 'author', '')
                
        except Exception as e:
            logger.debug(f"Metadata extraction note: {e}")
        
        return metadata
    
    def _create_error_result(self, error: str) -> Dict[str, Any]:
        """Create an error result dictionary."""
        return {
            "success": False,
            "method": "docling",
            "content": "",
            "error": error,
            "tables": [],
            "images": [],
            "metadata": {},
            "total_chars": 0,
        }
    
    async def process_pdf(
        self,
        pdf_data: Union[bytes, str, Path],
        use_ocr: bool = True,
    ) -> Dict[str, Any]:
        """
        Process a PDF document with OCR support.
        
        This is a convenience method for PDF processing that matches
        the interface expected by PDFOCRService.
        
        Args:
            pdf_data: PDF content as bytes, file path, or Path object
            use_ocr: Whether to enable OCR (docling enables OCR by default)
        
        Returns:
            Dictionary with extracted content compatible with PDFOCRService
        """
        result = await self.process_document(
            source=pdf_data,
            file_type="pdf",
            export_format="markdown"
        )
        
        # Reformat result to match PDFOCRService output format
        return {
            "method": "docling",
            "extracted_text": result.get("content", ""),
            "page_texts": [],  # Could be populated if we parse the result differently
            "page_count": result.get("page_count", 0),
            "total_chars": result.get("total_chars", 0),
            "success": result.get("success", False),
            "error": result.get("error"),
            "tables": result.get("tables", []),
            "images": result.get("images", []),
            "metadata": result.get("metadata", {}),
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get processor status and availability info."""
        return {
            "available": self.is_available,
            "docling_installed": DOCLING_AVAILABLE,
            "converter_initialized": self.converter is not None,
            "byok_integrated": self.use_byok and self.byok_manager is not None,
            "ocr_enabled": self.enable_ocr,
            "supported_formats": self.get_supported_formats(),
        }


# Global instance (lazy-loaded)
_docling_processor: Optional[DoclingDocumentProcessor] = None


def get_docling_processor() -> DoclingDocumentProcessor:
    """Get or create the global DoclingDocumentProcessor instance."""
    global _docling_processor
    if _docling_processor is None:
        _docling_processor = DoclingDocumentProcessor()
    return _docling_processor


def is_docling_available() -> bool:
    """Check if docling is available for document processing."""
    return DOCLING_AVAILABLE
