import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

try:
    from backend.core.lancedb_handler import get_lancedb_handler
except ImportError:
    # Fallback for when imported from main API context
    from core.lancedb_handler import get_lancedb_handler

from .pdf_memory_integration import PDFMemoryIntegration

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/pdf-memory", tags=["PDF Memory"])

# Global service instance
_pdf_memory_service: Optional[PDFMemoryIntegration] = None


def get_pdf_memory_service() -> PDFMemoryIntegration:
    """Get or initialize the PDF memory integration service."""
    global _pdf_memory_service
    if _pdf_memory_service is None:
        lancedb_handler = get_lancedb_handler()
        _pdf_memory_service = PDFMemoryIntegration(lancedb_handler=lancedb_handler)
    return _pdf_memory_service


@router.get("/status")
async def get_memory_service_status(
    service: PDFMemoryIntegration = Depends(get_pdf_memory_service),
):
    """Get the status of the PDF memory integration service."""
    try:
        status_info = {
            "status": "available",
            "lancedb_available": service.lancedb_handler is not None,
            "table_name": service.table_name,
            "capabilities": [
                "document_storage",
                "semantic_search",
                "metadata_management",
                "document_retrieval",
                "statistics_tracking",
            ],
        }
        return status_info
    except Exception as e:
        logger.error(f"Failed to get memory service status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Service status check failed: {str(e)}"
        )


@router.post("/store")
async def store_processed_pdf(
    user_id: str,
    processing_result: Dict[str, Any],
    source_uri: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    metadata: Optional[Dict[str, Any]] = None,
    service: PDFMemoryIntegration = Depends(get_pdf_memory_service),
):
    """
    Store processed PDF content in Atom's memory system.

    This endpoint takes the output from PDF processing and stores it
    with embeddings for semantic search and retrieval.
    """
    try:
        # Validate required fields
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        if not processing_result:
            raise HTTPException(status_code=400, detail="processing_result is required")

        # Store the processed PDF
        storage_result = await service.store_processed_pdf(
            user_id=user_id,
            processing_result=processing_result,
            source_uri=source_uri,
            tags=tags,
            metadata=metadata,
        )

        if storage_result["success"]:
            return {
                "success": True,
                "message": "PDF content stored successfully",
                "data": storage_result,
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to store PDF: {storage_result.get('error', 'Unknown error')}",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF storage failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF storage failed: {str(e)}")


@router.get("/search")
async def search_pdfs(
    user_id: str,
    query: str,
    limit: int = Query(10, ge=1, le=100),
    similarity_threshold: float = Query(0.7, ge=0.0, le=1.0),
    pdf_type: Optional[str] = Query(
        None, description="Filter by PDF type: searchable, scanned, mixed"
    ),
    tags: Optional[List[str]] = Query(None),
    service: PDFMemoryIntegration = Depends(get_pdf_memory_service),
):
    """
    Search PDF documents using semantic search.

    This endpoint performs semantic search across stored PDF documents
    and returns relevant matches based on the query.
    """
    try:
        # Validate required fields
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        if not query or len(query.strip()) == 0:
            raise HTTPException(status_code=400, detail="query is required")

        # Build filters
        filters = {}
        if pdf_type:
            if pdf_type not in ["searchable", "scanned", "mixed"]:
                raise HTTPException(
                    status_code=400,
                    detail="pdf_type must be one of: searchable, scanned, mixed",
                )
            filters["pdf_type"] = pdf_type

        if tags:
            filters["tags"] = tags

        # Perform search
        search_results = await service.search_pdfs(
            user_id=user_id,
            query=query,
            limit=limit,
            similarity_threshold=similarity_threshold,
            filters=filters,
        )

        return {
            "success": True,
            "query": query,
            "results_count": len(search_results),
            "results": search_results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF search failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF search failed: {str(e)}")


@router.get("/documents/{doc_id}")
async def get_document(
    user_id: str,
    doc_id: str,
    service: PDFMemoryIntegration = Depends(get_pdf_memory_service),
):
    """
    Retrieve a specific PDF document from memory.

    Returns the full document data including extracted text and metadata.
    """
    try:
        # Validate required fields
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        if not doc_id:
            raise HTTPException(status_code=400, detail="doc_id is required")

        # Retrieve document
        document = await service.get_document(user_id=user_id, doc_id=doc_id)

        if document:
            return {"success": True, "document": document}
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Document {doc_id} not found for user {user_id}",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document retrieval failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Document retrieval failed: {str(e)}"
        )


@router.delete("/documents/{doc_id}")
async def delete_document(
    user_id: str,
    doc_id: str,
    service: PDFMemoryIntegration = Depends(get_pdf_memory_service),
):
    """
    Delete a PDF document from memory.

    Removes the document from all storage systems (LanceDB, simple storage, etc.)
    """
    try:
        # Validate required fields
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        if not doc_id:
            raise HTTPException(status_code=400, detail="doc_id is required")

        # Delete document
        delete_result = await service.delete_document(user_id=user_id, doc_id=doc_id)

        if delete_result["success"]:
            return {
                "success": True,
                "message": f"Document {doc_id} deleted successfully",
                "data": delete_result,
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete document: {delete_result.get('error', 'Unknown error')}",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document deletion failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Document deletion failed: {str(e)}"
        )


@router.get("/users/{user_id}/stats")
async def get_user_document_stats(
    user_id: str, service: PDFMemoryIntegration = Depends(get_pdf_memory_service)
):
    """
    Get statistics for a user's PDF documents.

    Returns counts, storage usage, and breakdown by PDF type.
    """
    try:
        # Validate required fields
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        # Get statistics
        stats = await service.get_user_document_stats(user_id=user_id)

        return {"success": True, "user_id": user_id, "statistics": stats}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Statistics retrieval failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Statistics retrieval failed: {str(e)}"
        )


@router.get("/users/{user_id}/documents")
async def list_user_documents(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    pdf_type: Optional[str] = Query(None),
    service: PDFMemoryIntegration = Depends(get_pdf_memory_service),
):
    """
    List all PDF documents for a user.

    Returns a paginated list of document metadata (without full text content).
    """
    try:
        # Validate required fields
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        # This would typically query the database for document listings
        # For now, return a placeholder response
        # In production, implement proper pagination and filtering

        placeholder_response = {
            "success": True,
            "user_id": user_id,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": 0,  # Would be actual count in production
            },
            "documents": [],
            "message": "Document listing endpoint - implementation pending",
        }

        return placeholder_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document listing failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Document listing failed: {str(e)}"
        )


@router.post("/documents/{doc_id}/tags")
async def update_document_tags(
    user_id: str,
    doc_id: str,
    tags: List[str],
    service: PDFMemoryIntegration = Depends(get_pdf_memory_service),
):
    """
    Update tags for a PDF document.

    Replaces existing tags with the provided list.
    """
    try:
        # Validate required fields
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        if not doc_id:
            raise HTTPException(status_code=400, detail="doc_id is required")

        # This would update tags in the database
        # For now, return a placeholder response

        placeholder_response = {
            "success": True,
            "doc_id": doc_id,
            "tags": tags,
            "message": "Tag update endpoint - implementation pending",
        }

        return placeholder_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tag update failed: {e}")
        raise HTTPException(status_code=500, detail=f"Tag update failed: {str(e)}")


@router.get("/health")
async def health_check(service: PDFMemoryIntegration = Depends(get_pdf_memory_service)):
    """Health check endpoint for PDF memory service."""
    try:
        # Test basic functionality by checking service status
        status_info = await get_memory_service_status(service)

        return {
            "status": "healthy",
            "service": "PDF Memory Integration",
            "lancedb_connected": service.lancedb_handler is not None,
            "table_available": service.table_name is not None,
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")
