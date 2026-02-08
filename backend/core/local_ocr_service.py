#!/usr/bin/env python3
"""
Local OCR Service for Atom Desktop (Tauri)

Provides offline OCR capabilities using Tesseract and Surya.
Designed to be invoked from Tauri's execute_command.

Usage:
    python local_ocr_service.py check        # Check available engines
    python local_ocr_service.py ocr <file>   # Process file with OCR
    python local_ocr_service.py help         # Installation guide
"""

import argparse
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Engine availability flags
TESSERACT_AVAILABLE = False
SURYA_AVAILABLE = False
PIL_AVAILABLE = False

# Check Tesseract
try:
    import pytesseract

    # Verify tesseract binary is accessible
    pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
except Exception:
    pass

# Check Surya
try:
    from surya.model.detection.model import load_model as load_det_model
    from surya.model.recognition.model import load_model as load_rec_model
    from surya.ocr import run_ocr
    SURYA_AVAILABLE = True
except ImportError:
    pass

# Check PIL
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    pass


class LocalOCRService:
    """Local OCR service with Tesseract and Surya support."""
    
    def __init__(self):
        self.engines: Dict[str, bool] = {
            "tesseract": TESSERACT_AVAILABLE,
            "surya": SURYA_AVAILABLE,
        }
        self._surya_models = None
    
    def get_status(self) -> Dict[str, Any]:
        """Get OCR engine availability status."""
        recommended = None
        if SURYA_AVAILABLE:
            recommended = "surya"
        elif TESSERACT_AVAILABLE:
            recommended = "tesseract"
        
        return {
            "engines": self.engines,
            "recommended": recommended,
            "pil_available": PIL_AVAILABLE,
            "any_available": any(self.engines.values()),
        }
    
    def get_installation_guide(self) -> Dict[str, Any]:
        """Get installation instructions for OCR engines."""
        return {
            "tesseract": {
                "available": TESSERACT_AVAILABLE,
                "description": "Fast, lightweight OCR (~50MB)",
                "install": {
                    "macos": "brew install tesseract && pip install pytesseract",
                    "windows": "Download from https://github.com/UB-Mannheim/tesseract/wiki",
                    "linux": "sudo apt install tesseract-ocr && pip install pytesseract",
                },
                "languages": "60+ languages",
            },
            "surya": {
                "available": SURYA_AVAILABLE,
                "description": "High accuracy OCR with line detection (~1-2GB models)",
                "install": {
                    "all": "pip install surya-ocr",
                },
                "languages": "90+ languages",
                "note": "Requires Python 3.9+ and PyTorch",
            },
        }
    
    def process_image(
        self,
        image_path: str,
        engine: Optional[str] = None,
        languages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Process an image with OCR."""
        if not PIL_AVAILABLE:
            return {"success": False, "error": "PIL not available. Install: pip install Pillow"}
        
        if not os.path.exists(image_path):
            return {"success": False, "error": f"File not found: {image_path}"}
        
        # Auto-select engine
        if engine is None:
            if SURYA_AVAILABLE:
                engine = "surya"
            elif TESSERACT_AVAILABLE:
                engine = "tesseract"
            else:
                return {"success": False, "error": "No OCR engine available"}
        
        try:
            if engine == "tesseract":
                return self._ocr_tesseract(image_path, languages)
            elif engine == "surya":
                return self._ocr_surya(image_path, languages)
            else:
                return {"success": False, "error": f"Unknown engine: {engine}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def process_pdf(
        self,
        pdf_path: str,
        engine: Optional[str] = None,
        languages: Optional[List[str]] = None,
        max_pages: int = 50,
    ) -> Dict[str, Any]:
        """Process a PDF with OCR."""
        if not os.path.exists(pdf_path):
            return {"success": False, "error": f"File not found: {pdf_path}"}
        
        try:
            # Convert PDF to images
            images = self._pdf_to_images(pdf_path, max_pages)
            if not images:
                return {"success": False, "error": "Failed to convert PDF to images"}
            
            all_text = []
            page_results = []
            
            for i, img_path in enumerate(images):
                result = self.process_image(img_path, engine, languages)
                if result.get("success"):
                    text = result.get("text", "")
                    all_text.append(text)
                    page_results.append({
                        "page": i + 1,
                        "text": text,
                        "chars": len(text),
                    })
                # Clean up temp image
                try:
                    os.unlink(img_path)
                except OSError as e:
                    logger.debug(f"Failed to delete temp image {img_path}: {e}")
            
            return {
                "success": True,
                "text": "\n\n".join(all_text),
                "pages": page_results,
                "page_count": len(page_results),
                "total_chars": sum(len(t) for t in all_text),
                "engine": engine,
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _pdf_to_images(self, pdf_path: str, max_pages: int = 50) -> List[str]:
        """Convert PDF pages to images."""
        images = []
        
        # Try pdf2image first
        try:
            from pdf2image import convert_from_path
            pil_images = convert_from_path(pdf_path, first_page=1, last_page=max_pages)
            
            for i, img in enumerate(pil_images):
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                img.save(tmp.name, "PNG")
                images.append(tmp.name)
            
            return images
        except ImportError:
            pass
        
        # Fallback to PyMuPDF
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            
            for i, page in enumerate(doc):
                if i >= max_pages:
                    break
                pix = page.get_pixmap()
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                pix.save(tmp.name)
                images.append(tmp.name)
            
            return images
        except ImportError:
            pass
        
        logger.warning("No PDF to image converter available")
        return []
    
    def _ocr_tesseract(
        self,
        image_path: str,
        languages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """OCR using Tesseract."""
        if not TESSERACT_AVAILABLE:
            return {"success": False, "error": "Tesseract not available"}
        
        lang = "+".join(languages) if languages else "eng"
        
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image, lang=lang)
        
        return {
            "success": True,
            "text": text,
            "engine": "tesseract",
            "language": lang,
            "chars": len(text),
        }
    
    def _ocr_surya(
        self,
        image_path: str,
        languages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """OCR using Surya."""
        if not SURYA_AVAILABLE:
            return {"success": False, "error": "Surya not available"}
        
        # Load models (cached)
        if self._surya_models is None:
            det_model = load_det_model()
            rec_model = load_rec_model()
            self._surya_models = (det_model, rec_model)
        
        det_model, rec_model = self._surya_models
        
        image = Image.open(image_path)
        langs = languages or ["en"]
        
        predictions = run_ocr([image], [langs], det_model, rec_model)
        
        # Extract text from predictions
        text_lines = []
        for pred in predictions:
            for line in pred.text_lines:
                text_lines.append(line.text)
        
        text = "\n".join(text_lines)
        
        return {
            "success": True,
            "text": text,
            "engine": "surya",
            "languages": langs,
            "chars": len(text),
            "lines": len(text_lines),
        }


def main():
    """CLI interface for local OCR service."""
    parser = argparse.ArgumentParser(description="Local OCR Service for Atom Desktop")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Check command
    subparsers.add_parser("check", help="Check OCR engine availability")
    
    # OCR command
    ocr_parser = subparsers.add_parser("ocr", help="Process file with OCR")
    ocr_parser.add_argument("file", help="Path to image or PDF file")
    ocr_parser.add_argument("--engine", choices=["tesseract", "surya"], help="OCR engine")
    ocr_parser.add_argument("--languages", nargs="+", help="Languages (e.g., en es fr)")
    
    # Help command
    subparsers.add_parser("help", help="Show installation guide")
    
    args = parser.parse_args()
    
    service = LocalOCRService()
    
    if args.command == "check":
        result = service.get_status()
        print(json.dumps(result, indent=2))
    
    elif args.command == "ocr":
        file_path = args.file
        ext = Path(file_path).suffix.lower()
        
        if ext == ".pdf":
            result = service.process_pdf(
                file_path,
                engine=args.engine,
                languages=args.languages,
            )
        elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"]:
            result = service.process_image(
                file_path,
                engine=args.engine,
                languages=args.languages,
            )
        else:
            result = {"success": False, "error": f"Unsupported file type: {ext}"}
        
        print(json.dumps(result, indent=2))
    
    elif args.command == "help":
        result = service.get_installation_guide()
        print(json.dumps(result, indent=2))
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
