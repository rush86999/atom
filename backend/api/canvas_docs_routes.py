"""
Documentation Canvas API Routes

Provides endpoints for documentation canvas operations including
document creation, updates, versioning, and comments.
"""
import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.canvas_docs_service import DocumentationCanvasService
from core.database import get_db

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/canvas/docs", tags=["canvas_docs"])


# Request/Response Models
class CreateDocumentRequest(BaseModel):
    """Request to create a document canvas."""
    user_id: str
    title: str
    content: str
    canvas_id: Optional[str] = None
    agent_id: Optional[str] = None
    layout: str = "document"
    enable_comments: bool = True
    enable_versioning: bool = True


class UpdateDocumentRequest(BaseModel):
    """Request to update document content."""
    user_id: str
    content: str
    changes: str = ""
    create_version: bool = True


class AddCommentRequest(BaseModel):
    """Request to add a comment."""
    user_id: str
    content: str
    selection: Optional[Dict[str, Any]] = None


class ResolveCommentRequest(BaseModel):
    """Request to resolve a comment."""
    user_id: str
    comment_id: str


class RestoreVersionRequest(BaseModel):
    """Request to restore a version."""
    user_id: str
    version_id: str


# Endpoints

@router.post("/create")
async def create_document_canvas(request: CreateDocumentRequest, db: Session = Depends(get_db)):
    """
    Create a new documentation canvas.

    Creates a rich text document with optional versioning and commenting.
    """
    service = DocumentationCanvasService(db)
    result = service.create_document_canvas(
        user_id=request.user_id,
        title=request.title,
        content=request.content,
        canvas_id=request.canvas_id,
        agent_id=request.agent_id,
        layout=request.layout,
        enable_comments=request.enable_comments,
        enable_versioning=request.enable_versioning
    )

    if not result.get("success"):
        raise router.error_response(
            error_code="DOC_CANVAS_CREATE_FAILED",
            message=result.get("error", "Failed to create document canvas"),
            status_code=400
        )

    return router.success_response(
        data=result,
        message=f"Document '{request.title}' created successfully"
    )


@router.get("/{canvas_id}")
async def get_document_canvas(canvas_id: str, db: Session = Depends(get_db)):
    """
    Get a documentation canvas by ID.

    Returns the latest version of the document with all comments.
    """
    from sqlalchemy import desc

    from core.models import CanvasAudit

    audit = db.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id,
        CanvasAudit.canvas_type == "docs"
    ).order_by(desc(CanvasAudit.created_at)).first()

    if not audit:
        raise router.not_found_error(
            resource="DocumentCanvas",
            resource_id=canvas_id
        )

    metadata = audit.audit_metadata or {}

    return router.success_response(
        data={
            "canvas_id": canvas_id,
            "title": metadata.get("title"),
            "content": metadata.get("content"),
            "layout": metadata.get("layout"),
            "enable_comments": metadata.get("enable_comments", True),
            "enable_versioning": metadata.get("enable_versioning", True),
            "versions": metadata.get("versions", []),
            "comments": metadata.get("comments", []),
            "created_at": audit.created_at.isoformat()
        },
        message="Document canvas retrieved successfully"
    )


@router.put("/{canvas_id}")
async def update_document_content(canvas_id: str, request: UpdateDocumentRequest, db: Session = Depends(get_db)):
    """
    Update document content.

    Updates the document content and optionally creates a new version.
    """
    service = DocumentationCanvasService(db)
    result = service.update_document_content(
        canvas_id=canvas_id,
        user_id=request.user_id,
        content=request.content,
        changes=request.changes,
        create_version=request.create_version
    )

    if not result.get("success"):
        raise router.error_response(
            error_code="DOC_UPDATE_FAILED",
            message=result.get("error", "Failed to update document"),
            status_code=400
        )

    return router.success_response(
        data=result,
        message="Document content updated successfully"
    )


@router.post("/{canvas_id}/comment")
async def add_comment(canvas_id: str, request: AddCommentRequest, db: Session = Depends(get_db)):
    """
    Add a comment to a document.

    Adds a comment with optional text selection for inline comments.
    """
    service = DocumentationCanvasService(db)
    result = service.add_comment(
        canvas_id=canvas_id,
        user_id=request.user_id,
        content=request.content,
        selection=request.selection
    )

    if not result.get("success"):
        raise router.error_response(
            error_code="ADD_COMMENT_FAILED",
            message=result.get("error", "Failed to add comment"),
            status_code=400
        )

    return router.success_response(
        data=result,
        message="Comment added successfully"
    )


@router.post("/{canvas_id}/comment/resolve")
async def resolve_comment(canvas_id: str, request: ResolveCommentRequest, db: Session = Depends(get_db)):
    """
    Resolve a comment.

    Marks a comment as resolved.
    """
    service = DocumentationCanvasService(db)
    result = service.resolve_comment(
        canvas_id=canvas_id,
        comment_id=request.comment_id,
        user_id=request.user_id
    )

    if not result.get("success"):
        raise router.error_response(
            error_code="RESOLVE_COMMENT_FAILED",
            message=result.get("error", "Failed to resolve comment"),
            status_code=400
        )

    return router.success_response(
        data=result,
        message="Comment resolved successfully"
    )


@router.get("/{canvas_id}/versions")
async def get_document_versions(canvas_id: str, db: Session = Depends(get_db)):
    """
    Get version history for a document.

    Returns all versions of the document.
    """
    service = DocumentationCanvasService(db)
    result = service.get_document_versions(canvas_id)

    if not result.get("success"):
        raise router.not_found_error(
            resource="DocumentVersions",
            resource_id=canvas_id,
            details={"error": result.get("error")}
        )

    return router.success_response(
        data=result,
        message="Document versions retrieved successfully"
    )


@router.post("/{canvas_id}/restore")
async def restore_version(canvas_id: str, request: RestoreVersionRequest, db: Session = Depends(get_db)):
    """
    Restore a document to a previous version.

    Restores the document content from a specific version and creates a new version for the restoration.
    """
    service = DocumentationCanvasService(db)
    result = service.restore_version(
        canvas_id=canvas_id,
        version_id=request.version_id,
        user_id=request.user_id
    )

    if not result.get("success"):
        raise router.error_response(
            error_code="RESTORE_VERSION_FAILED",
            message=result.get("error", "Failed to restore version"),
            status_code=400
        )

    return router.success_response(
        data=result,
        message=f"Document restored to version {request.version_id}"
    )


@router.get("/{canvas_id}/toc")
async def get_table_of_contents(canvas_id: str, db: Session = Depends(get_db)):
    """
    Generate table of contents from document headings.

    Parses markdown headings and returns a structured table of contents.
    """
    service = DocumentationCanvasService(db)
    result = service.get_table_of_contents(canvas_id)

    if not result.get("success"):
        raise router.not_found_error(
            resource="DocumentTOC",
            resource_id=canvas_id,
            details={"error": result.get("error")}
        )

    return router.success_response(
        data=result,
        message="Table of contents generated successfully"
    )
