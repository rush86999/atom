"""
Automatic Document Ingestion API Routes
Manage per-integration document ingestion settings and memory removal.
"""

import io
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/document-ingestion", tags=["Document Ingestion"])


# ==================== Request/Response Models ====================

class ParseResultResponse(BaseModel):
    """Result of a standalone document parse operation"""
    success: bool
    content: str
    metadata: Dict[str, Any]
    total_chars: int
    page_count: int
    method: str = "docling"
    error: Optional[str] = None

class IngestionSettingsRequest(BaseModel):
    """Update ingestion settings for an integration"""
    integration_id: str
    enabled: Optional[bool] = None
    auto_sync_new_files: Optional[bool] = None
    file_types: Optional[List[str]] = None  # ["pdf", "docx", "xlsx", "csv", "txt", "md"]
    sync_folders: Optional[List[str]] = None  # Empty = all folders
    exclude_folders: Optional[List[str]] = None
    max_file_size_mb: Optional[int] = None
    sync_frequency_minutes: Optional[int] = None


class IngestionSettingsResponse(BaseModel):
    """Ingestion settings for an integration"""
    integration_id: str
    enabled: bool
    auto_sync_new_files: bool
    file_types: List[str]
    sync_folders: List[str]
    max_file_size_mb: int
    sync_frequency_minutes: int
    last_sync: Optional[str] = None


class SyncResultResponse(BaseModel):
    """Result of a document sync operation"""
    integration_id: str
    success: bool
    files_found: int = 0
    files_ingested: int = 0
    files_skipped: int = 0
    errors: List[str] = []
    message: Optional[str] = None


class RemoveMemoryResponse(BaseModel):
    """Result of memory removal operation"""
    integration_id: str
    success: bool
    documents_removed: int
    message: str


# Helper to get workspace_id
def get_workspace_id() -> str:
    return "default"


# ==================== API Endpoints ====================

@router.get("/settings", response_model=List[IngestionSettingsResponse])
async def get_all_ingestion_settings():
    """
    Get document ingestion settings for all integrations.
    Shows which integrations have auto-sync enabled.
    """
    try:
        from core.auto_document_ingestion import get_document_ingestion_service
        service = get_document_ingestion_service("default")
        settings_list = service.get_all_settings()
        return [IngestionSettingsResponse(**s) for s in settings_list]
    except Exception as e:
        logger.error(f"Failed to get ingestion settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings/{integration_id}", response_model=IngestionSettingsResponse)
async def get_integration_settings(
    integration_id: str
):
    """
    Get document ingestion settings for a specific integration.
    """
    try:
        from core.auto_document_ingestion import get_document_ingestion_service
        service = get_document_ingestion_service("default")
        settings = service.get_settings(integration_id)
        
        return IngestionSettingsResponse(
            integration_id=settings.integration_id,
            enabled=settings.enabled,
            auto_sync_new_files=settings.auto_sync_new_files,
            file_types=settings.file_types,
            sync_folders=settings.sync_folders,
            max_file_size_mb=settings.max_file_size_mb,
            sync_frequency_minutes=settings.sync_frequency_minutes,
            last_sync=settings.last_sync.isoformat() if settings.last_sync else None
        )
    except Exception as e:
        logger.error(f"Failed to get settings for {integration_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings")
async def update_ingestion_settings(
    request: IngestionSettingsRequest
):
    """
    Update document ingestion settings for an integration.
    Enable/disable auto-sync, configure file types, folders, etc.
    """
    try:
        from core.auto_document_ingestion import get_document_ingestion_service
        service = get_document_ingestion_service("default")
        
        settings = service.update_settings(
            integration_id=request.integration_id,
            enabled=request.enabled,
            auto_sync_new_files=request.auto_sync_new_files,
            file_types=request.file_types,
            sync_folders=request.sync_folders,
            exclude_folders=request.exclude_folders,
            max_file_size_mb=request.max_file_size_mb,
            sync_frequency_minutes=request.sync_frequency_minutes
        )
        
        return {
            "success": True,
            "message": f"Settings updated for {request.integration_id}",
            "enabled": settings.enabled,
            "file_types": settings.file_types
        }
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/{integration_id}", response_model=SyncResultResponse)
async def trigger_document_sync(
    integration_id: str,
    force: bool = Query(False, description="Force sync even if recently synced")
):
    """
    Trigger a document sync for an integration.
    Downloads and ingests documents into Atom Memory.
    """
    try:
        from core.auto_document_ingestion import get_document_ingestion_service
        service = get_document_ingestion_service("default")
        result = await service.sync_integration(integration_id, force=force)
        
        return SyncResultResponse(
            integration_id=integration_id,
            success=result.get("success", False),
            files_found=result.get("files_found", 0),
            files_ingested=result.get("files_ingested", 0),
            files_skipped=result.get("files_skipped", 0),
            errors=result.get("errors", []),
            message=result.get("error") or "Sync completed"
        )
    except Exception as e:
        logger.error(f"Document sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memory/{integration_id}", response_model=RemoveMemoryResponse)
async def remove_integration_memory(
    integration_id: str
):
    """
    Remove all ingested documents from a specific integration.
    Clears data from Atom Memory (LanceDB + GraphRAG).
    Use when disconnecting an integration or for privacy/compliance.
    """
    try:
        from core.auto_document_ingestion import get_document_ingestion_service
        service = get_document_ingestion_service("default")
        result = await service.remove_integration_documents(integration_id)
        
        return RemoveMemoryResponse(
            integration_id=integration_id,
            success=result.get("success", False),
            documents_removed=result.get("documents_removed", 0),
            message=f"Removed {result.get('documents_removed', 0)} documents from {integration_id}"
        )
    except Exception as e:
        logger.error(f"Memory removal failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def list_ingested_documents(
    integration_id: Optional[str] = Query(None, description="Filter by integration"),
    file_type: Optional[str] = Query(None, description="Filter by file type")
):
    """
    List all ingested documents.
    Optionally filter by integration or file type.
    """
    try:
        from core.auto_document_ingestion import get_document_ingestion_service
        service = get_document_ingestion_service("default")
        docs = service.get_ingested_documents(integration_id, file_type)
        
        return {
            "documents": [
                {
                    "id": d.id,
                    "file_name": d.file_name,
                    "file_path": d.file_path,
                    "file_type": d.file_type,
                    "integration_id": d.integration_id,
                    "file_size_bytes": d.file_size_bytes,
                    "ingested_at": d.ingested_at.isoformat(),
                    "content_preview": d.content_preview[:200] + "..." if len(d.content_preview) > 200 else d.content_preview
                }
                for d in docs
            ],
            "count": len(docs)
        }
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supported-integrations")
async def list_supported_integrations():
    """
    List all integrations that support document ingestion.
    """
    return {
        "integrations": [
            {
                "id": "google_drive",
                "name": "Google Drive",
                "supported_types": ["pdf", "docx", "xlsx", "csv", "txt", "md"]
            },
            {
                "id": "dropbox",
                "name": "Dropbox",
                "supported_types": ["pdf", "docx", "xlsx", "csv", "txt", "md"]
            },
            {
                "id": "onedrive",
                "name": "OneDrive",
                "supported_types": ["pdf", "docx", "xlsx", "csv", "txt", "md"]
            },
            {
                "id": "box",
                "name": "Box",
                "supported_types": ["pdf", "docx", "xlsx", "csv", "txt", "md"]
            },
            {
                "id": "sharepoint",
                "name": "SharePoint",
                "supported_types": ["pdf", "docx", "xlsx", "csv", "txt", "md"]
            },
            {
                "id": "notion",
                "name": "Notion",
                "supported_types": ["md", "txt"]
            }
        ]
    }


@router.get("/supported-file-types")
async def list_supported_file_types():
    """
    List all supported file types for document ingestion.
    Shows docling availability for enhanced OCR.
    """
    # Check docling availability
    try:
        from core.docling_processor import get_docling_processor, is_docling_available
        docling_available = is_docling_available()
        if docling_available:
            processor = get_docling_processor()
            docling_formats = processor.get_supported_formats()
        else:
            docling_formats = []
    except ImportError:
        docling_available = False
        docling_formats = []
    
    base_parser = "docling (OCR)" if docling_available else "PyPDF2"
    
    return {
        "file_types": [
            {"ext": "pdf", "name": "PDF Documents", "parser": base_parser, "ocr_available": docling_available},
            {"ext": "docx", "name": "Word Documents", "parser": "docling" if docling_available else "python-docx"},
            {"ext": "doc", "name": "Legacy Word Documents", "parser": "python-docx"},
            {"ext": "pptx", "name": "PowerPoint", "parser": "docling" if docling_available else "not supported", "requires_docling": True},
            {"ext": "xlsx", "name": "Excel Spreadsheets", "parser": "docling" if docling_available else "pandas/openpyxl"},
            {"ext": "xls", "name": "Legacy Excel", "parser": "pandas"},
            {"ext": "html", "name": "HTML Documents", "parser": "docling" if docling_available else "beautifulsoup"},
            {"ext": "csv", "name": "CSV Files", "parser": "csv"},
            {"ext": "txt", "name": "Text Files", "parser": "native"},
            {"ext": "md", "name": "Markdown Files", "parser": "native"},
            {"ext": "json", "name": "JSON Files", "parser": "json"},
            {"ext": "png", "name": "Images (OCR)", "parser": "docling" if docling_available else "not supported", "requires_docling": True},
            {"ext": "jpg", "name": "Images (OCR)", "parser": "docling" if docling_available else "not supported", "requires_docling": True},
        ],
        "docling_available": docling_available,
        "docling_formats": docling_formats
    }


@router.get("/ocr-status")
async def get_ocr_status():
    """
    Get OCR engine status and capabilities.
    Shows which OCR engines are available (docling, tesseract, easyocr, etc.)
    """
    status = {
        "ocr_engines": [],
        "recommended_engine": None,
        "docling": {"available": False, "reason": "Not installed"},
    }
    
    # Check docling
    try:
        from core.docling_processor import get_docling_processor, is_docling_available
        if is_docling_available():
            processor = get_docling_processor()
            proc_status = processor.get_status()
            status["docling"] = {
                "available": True,
                "formats": proc_status.get("supported_formats", []),
                "byok_integrated": proc_status.get("byok_integrated", False),
            }
            status["ocr_engines"].append("docling")
            status["recommended_engine"] = "docling"
    except ImportError:
        pass
    
    # Check other OCR engines
    try:
        from integrations.pdf_processing.pdf_ocr_service import (
            DOCLING_AVAILABLE,
            EASYOCR_AVAILABLE,
            TESSERACT_AVAILABLE,
        )
        if TESSERACT_AVAILABLE:
            status["ocr_engines"].append("tesseract")
        if EASYOCR_AVAILABLE:
            status["ocr_engines"].append("easyocr")
        if not status["recommended_engine"] and status["ocr_engines"]:
            status["recommended_engine"] = status["ocr_engines"][0]
    except ImportError:
        pass
    
    return status


@router.post("/parse", response_model=ParseResultResponse)
async def parse_document_file(
    file: UploadFile = File(...),
    export_format: str = Query("markdown", description="Output format: markdown, text, json, html")
):
    """
    Directly parse a document file and return its content.
    Uses docling for high-fidelity extraction if available.
    """
    try:
        content = await file.read()
        file_name = file.filename
        file_ext = file_name.split(".")[-1].lower() if "." in file_name else "pdf"
        
        from core.docling_processor import get_docling_processor, is_docling_available
        
        if is_docling_available():
            processor = get_docling_processor()
            # source can be bytes, path, or URL
            result = await processor.process_document(
                source=content,
                file_type=file_ext,
                file_name=file_name,
                export_format=export_format
            )
            
            return ParseResultResponse(
                success=result.get("success", False),
                content=result.get("content", ""),
                metadata=result.get("metadata", {}),
                total_chars=result.get("total_chars", 0),
                page_count=result.get("page_count", 0),
                method="docling",
                error=result.get("error")
            )
        else:
            # Fallback for docling unavailability
            logger.warning("Docling not available for direct parse request, using basic fallback")
            from core.auto_document_ingestion import DocumentParser
            text = await DocumentParser.parse_document(content, file_ext, file_name)
            
            return ParseResultResponse(
                success=True,
                content=text,
                metadata={"file_name": file_name, "file_type": file_ext},
                total_chars=len(text),
                page_count=0,
                method="fallback",
                error=None
            )
            
    except Exception as e:
        logger.error(f"Manual parse failed: {e}")
        return ParseResultResponse(
            success=False,
            content="",
            metadata={},
            total_chars=0,
            page_count=0,
            method="error",
            error=str(e)
        )

