"""
Document Routes - API endpoints for document ingestion and search
"""
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime
import uuid
import os

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

# Governance feature flags
DOCUMENT_GOVERNANCE_ENABLED = os.getenv("DOCUMENT_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

# In-memory document store (would use LanceDB/vector store in production)
_document_store: Dict[str, Dict[str, Any]] = {}

# Pydantic Models
class DocumentIngestRequest(BaseModel):
    content: Optional[str] = Field(None, description="Document content as text")
    type: str = Field("text", description="Document type: text, pdf, url")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    title: Optional[str] = Field(None, description="Document title")

class DocumentResponse(BaseModel):
    id: str
    title: Optional[str]
    type: str
    metadata: Dict[str, Any]
    ingested_at: str
    chunk_count: int

class SearchResult(BaseModel):
    id: str
    title: Optional[str]
    content_preview: str
    score: float
    metadata: Dict[str, Any]

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_count: int
    timestamp: str

@router.post("/ingest", response_model=DocumentResponse)
async def ingest_document(request: DocumentIngestRequest, agent_id: Optional[str] = None):
    """
    Ingest a document for RAG/search.

    **Governance**: Requires INTERN+ maturity for document ingestion.
    """
    # Governance check for document ingestion
    if DOCUMENT_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="ingest_document",
                resource_type="document",
                complexity=2  # MODERATE - data ingestion
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for ingest_document by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

    try:
        doc_id = str(uuid.uuid4())

        # Get content from request
        content = request.content or ""
        doc_type = request.type
        title = request.title or f"Document {doc_id[:8]}"

        if not content:
            # Return a helpful message if no content
            content = "(Empty document)"

        # Store document
        doc = {
            "id": doc_id,
            "title": title,
            "content": content,
            "type": doc_type,
            "metadata": request.metadata or {},
            "ingested_at": datetime.now().isoformat(),
            "chunk_count": max(1, len(content) // 500)  # Simple chunking estimate
        }
        _document_store[doc_id] = doc

        logger.info(f"Document ingested: {doc_id} by agent {agent_id or 'system'}")
        return DocumentResponse(
            id=doc_id,
            title=title,
            type=doc_type,
            metadata=doc.get("metadata", {}),
            ingested_at=doc["ingested_at"],
            chunk_count=doc["chunk_count"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search", response_model=SearchResponse)
async def search_documents(q: str, limit: int = 10):
    """Search ingested documents"""
    try:
        results = []
        for doc_id, doc in _document_store.items():
            content = str(doc.get("content", ""))
            if q.lower() in content.lower():
                # Simple text matching (would use vector search in production)
                results.append(SearchResult(
                    id=doc_id,
                    title=doc.get("title"),
                    content_preview=content[:200] + "..." if len(content) > 200 else content,
                    score=0.9,  # Mock score
                    metadata=doc.get("metadata", {})
                ))
            if len(results) >= limit:
                break
        
        return SearchResponse(
            query=q,
            results=results,
            total_count=len(results),
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Document search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{doc_id}")
async def get_document(doc_id: str):
    """Get a specific document by ID"""
    if doc_id not in _document_store:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    doc = _document_store[doc_id]
    return {
        "id": doc_id,
        "title": doc.get("title"),
        "type": doc.get("type"),
        "content_preview": str(doc.get("content", ""))[:500],
        "metadata": doc.get("metadata", {}),
        "ingested_at": doc.get("ingested_at")
    }

@router.delete("/{doc_id}")
async def delete_document(doc_id: str, agent_id: Optional[str] = None):
    """
    Delete a document.

    **Governance**: Requires SUPERVISED+ maturity for document deletion.
    """
    # Governance check for document deletion
    if DOCUMENT_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="delete_document",
                resource_type="document",
                complexity=3  # HIGH - data deletion
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for delete_document by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

    if doc_id not in _document_store:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    del _document_store[doc_id]
    logger.info(f"Document deleted: {doc_id} by agent {agent_id or 'system'}")
    return {"message": f"Document '{doc_id}' deleted"}

@router.get("")
async def list_documents(limit: int = 100):
    """List all ingested documents"""
    docs = list(_document_store.values())[:limit]
    return {
        "documents": [
            {
                "id": d["id"],
                "title": d.get("title"),
                "type": d.get("type"),
                "ingested_at": d.get("ingested_at")
            }
            for d in docs
        ],
        "total": len(_document_store)
    }
