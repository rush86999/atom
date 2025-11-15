import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

# BYOK Integration
try:
    from backend.core.byok_endpoints import get_byok_manager

    BYOK_AVAILABLE = True
except ImportError:
    BYOK_AVAILABLE = False
    get_byok_manager = None

from .pdf_ocr_service import PDFOCRService

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/pdf", tags=["PDF Processing"])


# BYOK Manager dependency
def get_byok_manager_dependency():
    """Get BYOK manager if available"""
    if BYOK_AVAILABLE and get_byok_manager:
        return get_byok_manager()
    return None


# Global service instance (could be dependency injected in production)
_pdf_service: Optional[PDFOCRService] = None


def get_pdf_service(use_byok: bool = True) -> PDFOCRService:
    """Get or initialize the PDF OCR service."""
    global _pdf_service
    if _pdf_service is None:
        # Initialize with environment variables or defaults
        openai_api_key = None  # Could be loaded from environment
        tesseract_path = None  # Could be configured
        easyocr_languages = ["en"]  # Default to English

        _pdf_service = PDFOCRService(
            openai_api_key=openai_api_key,
            tesseract_path=tesseract_path,
            easyocr_languages=easyocr_languages,
            use_byok=use_byok,
        )
    return _pdf_service


@router.get("/status")
async def get_pdf_service_status(byok_manager=Depends(get_byok_manager_dependency)):
    """Get the status and capabilities of the PDF processing service."""
    try:
        service = get_pdf_service()
        status_info = {
            "status": "available",
            "service_capabilities": service.service_status,
            "available_ocr_methods": list(service.ocr_readers.keys()),
        }

        # Add BYOK integration status if available
        if BYOK_AVAILABLE and byok_manager:
            byok_status = {
                "byok_integrated": True,
                "byok_manager_available": byok_manager is not None,
                "pdf_providers": await _get_pdf_byok_providers(byok_manager),
            }
            status_info["byok_integration"] = byok_status

        return status_info
    except Exception as e:
        logger.error(f"Failed to get PDF service status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Service status check failed: {str(e)}"
        )


@router.post("/process")
async def process_pdf_file(
    file: UploadFile = File(..., description="PDF file to process"),
    use_ocr: bool = Form(True, description="Use OCR for scanned PDFs"),
    extract_images: bool = Form(True, description="Extract and process images"),
    use_advanced_comprehension: bool = Form(
        False, description="Use AI for image understanding"
    ),
    fallback_strategy: str = Form(
        "cascade", description="OCR fallback strategy: cascade or parallel"
    ),
    optimize_with_byok: bool = Form(
        True, description="Use BYOK for provider optimization"
    ),
    byok_manager=Depends(get_byok_manager_dependency),
):
    """
    Process a PDF file with optional OCR and image comprehension.

    This endpoint supports both searchable PDFs (text extraction) and scanned PDFs (OCR).
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Read file content
        file_content = await file.read()
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        # Get service instance with BYOK optimization
        service = get_pdf_service(use_byok=optimize_with_byok)

        # Add BYOK optimization info if available
        optimization_info = {}
        if optimize_with_byok and byok_manager:
            optimization_info = {
                "byok_optimization": await _optimize_pdf_processing_with_byok(
                    byok_manager, use_advanced_comprehension, use_ocr
                )
            }

        # Process the PDF
        result = await service.process_pdf(
            pdf_data=file_content,
            use_ocr=use_ocr,
            extract_images=extract_images,
            use_advanced_comprehension=use_advanced_comprehension,
            fallback_strategy=fallback_strategy,
        )

        # Add file metadata to result
        result["file_metadata"] = {
            "filename": file.filename,
            "size_bytes": len(file_content),
            "content_type": file.content_type,
        }

        # Add BYOK optimization info to result
        if optimization_info:
            result["byok_optimization"] = optimization_info["byok_optimization"]

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF processing failed: {str(e)}")


@router.post("/process-url")
async def process_pdf_from_url(
    pdf_url: str = Form(..., description="URL of PDF to process"),
    use_ocr: bool = Form(True, description="Use OCR for scanned PDFs"),
    extract_images: bool = Form(True, description="Extract and process images"),
    use_advanced_comprehension: bool = Form(
        False, description="Use AI for image understanding"
    ),
    optimize_with_byok: bool = Form(
        True, description="Use BYOK for provider optimization"
    ),
    byok_manager=Depends(get_byok_manager_dependency),
):
    """
    Process a PDF from a URL with optional OCR and image comprehension.
    """
    try:
        import httpx

        # Download PDF from URL
        async with httpx.AsyncClient() as client:
            response = await client.get(pdf_url)
            response.raise_for_status()

            if (
                not response.headers.get("content-type", "")
                .lower()
                .startswith("application/pdf")
            ):
                raise HTTPException(
                    status_code=400, detail="URL does not point to a PDF file"
                )

            pdf_content = response.content

        # Get service instance with BYOK optimization
        service = get_pdf_service(use_byok=optimize_with_byok)

        # Add BYOK optimization info if available
        optimization_info = {}
        if optimize_with_byok and byok_manager:
            optimization_info = {
                "byok_optimization": await _optimize_pdf_processing_with_byok(
                    byok_manager, use_advanced_comprehension, use_ocr
                )
            }

        # Process the PDF
        result = await service.process_pdf(
            pdf_data=pdf_content,
            use_ocr=use_ocr,
            extract_images=extract_images,
            use_advanced_comprehension=use_advanced_comprehension,
        )

        # Add URL metadata to result
        result["source_metadata"] = {"url": pdf_url, "size_bytes": len(pdf_content)}

        # Add BYOK optimization info to result
        if optimization_info:
            result["byok_optimization"] = optimization_info["byok_optimization"]

        return JSONResponse(content=result)

    except httpx.HTTPError as e:
        logger.error(f"Failed to download PDF from URL: {e}")
        raise HTTPException(
            status_code=400, detail=f"Failed to download PDF from URL: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF processing from URL failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF processing failed: {str(e)}")


@router.post("/extract-text-only")
async def extract_text_only(
    file: UploadFile = File(..., description="PDF file for text extraction"),
):
    """
    Extract text only from PDF (no OCR, no image processing).
    Fast processing for searchable PDFs.
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Read file content
        file_content = await file.read()

        # Get service instance
        service = get_pdf_service()

        # Process with OCR disabled
        result = await service.process_pdf(
            pdf_data=file_content,
            use_ocr=False,
            extract_images=False,
            use_advanced_comprehension=False,
        )

        # Return simplified response
        simplified_result = {
            "extracted_text": result.get("extracted_content", {}).get("text", ""),
            "page_count": result.get("processing_summary", {}).get("total_pages", 0),
            "total_characters": result.get("processing_summary", {}).get(
                "total_characters", 0
            ),
            "method_used": result.get("processing_summary", {}).get(
                "best_method", "unknown"
            ),
            "filename": file.filename,
        }

        return JSONResponse(content=simplified_result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {str(e)}")


@router.post("/analyze-pdf-type")
async def analyze_pdf_type(
    file: UploadFile = File(..., description="PDF file to analyze"),
):
    """
    Analyze PDF type (searchable vs scanned) without full processing.
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Read file content
        file_content = await file.read()

        # Get service instance
        service = get_pdf_service()

        # Just run basic extraction to get text ratio
        basic_result = await service._extract_basic_text(file_content)

        # Determine PDF type based on text ratio
        text_ratio = basic_result.get("text_ratio", 0)
        if text_ratio > 0.5:
            pdf_type = "searchable"
            confidence = "high"
        elif text_ratio > 0.1:
            pdf_type = "mostly_searchable"
            confidence = "medium"
        else:
            pdf_type = "scanned_or_image_based"
            confidence = "high"

        analysis_result = {
            "pdf_type": pdf_type,
            "confidence": confidence,
            "text_ratio": text_ratio,
            "total_pages": basic_result.get("page_count", 0),
            "total_characters": basic_result.get("total_chars", 0),
            "filename": file.filename,
            "recommended_processing": {
                "needs_ocr": pdf_type
                in ["scanned_or_image_based", "mostly_searchable"],
                "suggested_methods": ["basic_extraction"]
                if pdf_type == "searchable"
                else ["ocr_processing"],
            },
        }

        return JSONResponse(content=analysis_result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF analysis failed: {str(e)}")


@router.get("/health")
async def health_check(byok_manager=Depends(get_byok_manager_dependency)):
    """Health check endpoint for PDF processing service."""
    try:
        service = get_pdf_service()

        # Test basic functionality
        test_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 44 >>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n(Test PDF) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000204 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n281\n%%EOF"

        result = await service.process_pdf(
            pdf_data=test_pdf, use_ocr=False, extract_images=False
        )

        health_info = {
            "status": "healthy",
            "service": "PDF OCR Processing",
            "basic_functionality": result.get("success", False),
            "available_methods": list(service.ocr_readers.keys()),
        }

        # Add BYOK health info if available
        if BYOK_AVAILABLE and byok_manager:
            try:
                byok_health = await byok_manager.get("/api/ai/health")
                health_info["byok_integration"] = {
                    "status": "connected",
                    "byok_health": byok_health,
                }
            except Exception as e:
                health_info["byok_integration"] = {
                    "status": "disconnected",
                    "error": str(e),
                }

        return health_info

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


# BYOK Integration Helper Functions


async def _get_pdf_byok_providers(byok_manager) -> Dict[str, Any]:
    """Get PDF-specific BYOK providers."""
    try:
        pdf_providers = []
        for provider_id in ["openai", "google_gemini", "anthropic", "azure_openai"]:
            try:
                provider_status = byok_manager.get_provider_status(provider_id)
                if provider_status["status"] == "active":
                    pdf_providers.append(
                        {
                            "provider_id": provider_id,
                            "name": provider_status["provider"]["name"],
                            "supported_tasks": provider_status["provider"][
                                "supported_tasks"
                            ],
                            "cost_per_token": provider_status["provider"][
                                "cost_per_token"
                            ],
                        }
                    )
            except Exception:
                continue

        return {"pdf_providers": pdf_providers, "total_providers": len(pdf_providers)}
    except Exception as e:
        logger.error(f"Failed to get PDF BYOK providers: {e}")
        return {"pdf_providers": [], "total_providers": 0, "error": str(e)}


async def _optimize_pdf_processing_with_byok(
    byok_manager, use_advanced_comprehension: bool, use_ocr: bool
) -> Dict[str, Any]:
    """Optimize PDF processing using BYOK system."""
    try:
        # Determine task type based on processing requirements
        if use_advanced_comprehension:
            task_type = "image_comprehension"
        elif use_ocr:
            task_type = "pdf_ocr"
        else:
            task_type = "document_processing"

        # Get optimal provider
        optimal_provider = byok_manager.get_optimal_provider(task_type)

        if optimal_provider:
            provider_status = byok_manager.get_provider_status(optimal_provider)
            return {
                "optimized": True,
                "task_type": task_type,
                "optimal_provider": optimal_provider,
                "provider_name": provider_status["provider"]["name"],
                "cost_per_token": provider_status["provider"]["cost_per_token"],
                "supported_tasks": provider_status["provider"]["supported_tasks"],
            }
        else:
            return {
                "optimized": False,
                "reason": f"No suitable providers found for {task_type}",
                "task_type": task_type,
            }

    except Exception as e:
        logger.error(f"BYOK optimization failed: {e}")
        return {"optimized": False, "error": str(e), "task_type": "unknown"}
