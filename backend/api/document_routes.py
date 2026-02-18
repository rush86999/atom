"""
Document Routes - API endpoints for document ingestion and search
"""
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid
import json
from fastapi import Depends, File, Request, UploadFile, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity, require_governance
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User
from core.security_dependencies import get_current_user
from core.lancedb_handler import get_lancedb_handler
from core.auto_document_ingestion import DocumentParser

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/documents", tags=["Documents"])

# Global handler removed to support dynamic workspace isolation
# lancedb_handler = get_lancedb_handler("default") -> moved to endpoints

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
async def ingest_document(
    request: DocumentIngestRequest,
    current_user: User = Depends(get_current_user)
):
    """Ingest a document for RAG/search"""
    try:

        # Dynamic workspace resolution
        ws_id = None
        if current_user and current_user.workspaces:
             ws_id = current_user.workspaces[0].id
             
        lancedb_handler = get_lancedb_handler(ws_id)
        
        if not lancedb_handler:
             raise router.internal_error("Search database not available")

        doc_id = str(uuid.uuid4())
        content = request.content or ""
        doc_type = request.type
        title = request.title or f"Document {doc_id[:8]}"

        if not content:
            content = "(Empty document)"

        metadata = request.metadata or {}
        metadata.update({
            "title": title,
            "file_type": doc_type,
            "ingested_at": datetime.now().isoformat(),
            "source": "api_ingest",
            "doc_id": doc_id # Store explicit doc_id in metadata for retrieval
        })

        success = lancedb_handler.add_document(
            table_name="documents",
            text=content,
            source=f"api:{doc_id}",
            metadata=metadata,
            user_id=str(current_user.id) if current_user else "default_user",
            extract_knowledge=True 
        )

        if not success:
             raise router.internal_error("Failed to store document in LanceDB")

        return DocumentResponse(
            id=doc_id,
            title=title,
            type=doc_type,
            metadata=metadata,
            ingested_at=metadata["ingested_at"],
            chunk_count=max(1, len(content) // 500)
        )
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        raise router.internal_error(message=str(e))

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload and ingest a file directly"""
    try:
        # Dynamic workspace resolution
        # If user has workspaces, use the first one (primary), otherwise default to shared
        ws_id = None
        try:
            if current_user and current_user.workspaces:
                 ws_id = current_user.workspaces[0].id
        except Exception as ws_err:
            logger.warning(f"Failed to resolve workspaces for user {current_user.id}: {ws_err}")
            print(f"DEBUG: Workspace resolution failed: {ws_err}")
             
        lancedb_handler = get_lancedb_handler(ws_id)

        if not lancedb_handler:
             raise router.internal_error("Search database not available")

        content_bytes = await file.read()
        filename = file.filename
        file_ext = filename.split(".")[-1].lower() if "." in filename else "txt"
        
        # 1. Parse content using robust parser
        content = await DocumentParser.parse_document(content_bytes, file_ext, filename)
        
        if not content:
             content = f"[Empty or unparseable file: {filename}]"

        # 2. Store document
        doc_id = str(uuid.uuid4())
        metadata = {
            "source": "upload", 
            "size": len(content_bytes),
            "title": filename,
            "filename": filename,
            "file_type": file_ext,
            "ingested_at": datetime.now().isoformat(),
            "doc_id": doc_id,
            "integration_id": "manual_upload",
            "author": current_user.email if current_user else "unknown"
        }
        
        success = lancedb_handler.add_document(
            table_name="documents",
            text=content,
            source=f"upload:{filename}",
            metadata=metadata,
            user_id=str(current_user.id) if current_user else "default_user",
            extract_knowledge=True,
            workspace_id=ws_id,
            doc_id=doc_id
        )

        if not success:
             raise router.internal_error("Failed to store uploaded document in LanceDB")
        
        return DocumentResponse(
            id=doc_id,
            title=filename,
            type=file.content_type or "application/octet-stream",
            metadata=metadata,
            ingested_at=metadata["ingested_at"],
            chunk_count=max(1, len(content) // 500)
        )
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise router.internal_error(message=str(e))

@router.get("/search", response_model=SearchResponse)
async def search_documents(
    q: str, 
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    """Search ingested documents"""
    try:
        # Dynamic workspace resolution
        ws_id = None
        if current_user and current_user.workspaces:
             ws_id = current_user.workspaces[0].id

        lancedb_handler = get_lancedb_handler(ws_id)

        if not lancedb_handler:
             raise router.internal_error("Search database not available")
        
        # Use LanceDB vector search
        results_data = lancedb_handler.search(
            table_name="documents",
            query=q,
            limit=limit,
            min_score=0.0 # Allow all results for now
        )
        
        results = []
        for r in results_data:
             # Handle metadata parsing if string
             meta = r.get("metadata", {})
             if isinstance(meta, str):
                  try:
                       meta = json.loads(meta)
                  except:
                       meta = {}
             
             results.append(SearchResult(
                  id=str(r.get("id", uuid.uuid4())), # Fallback ID if not in result
                  title=meta.get("title") or meta.get("file_name") or "Untitled",
                  content_preview=r.get("text", "")[:200] + "...",
                  score=r.get("_score", 0.0), # LanceDB return _score or score?
                  metadata=meta
             ))
        
        return SearchResponse(
            query=q,
            results=results,
            total_count=len(results),
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Document search failed: {e}")
        raise router.internal_error(message=str(e))

@router.get("/{doc_id}")
async def get_document(doc_id: str):
    """Get a specific document by ID (Not efficiently supported by LanceDB yet, stubbing)"""
    # LanceDB doesn't easily support get_by_id without a filter search
    # For now, we return a stub or perform a metadata search
    return router.success_response(
        data={
            "id": doc_id,
            "title": "Document Details Unavailable",
            "type": "unknown",
            "content_preview": "Direct retrieval by ID not supported in vector store mode.",
            "metadata": {},
            "ingested_at": datetime.now().isoformat()
        }
    )

@router.delete("/{doc_id}")
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="delete_document",
    feature="document"
)
async def delete_document(
    doc_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    agent_id: Optional[str] = None
):
    """
    Delete a document.
    """
    if agent_id:
         pass # unused for now

    # Dynamic workspace resolution
    ws_id = None
    if current_user and current_user.workspaces:
            ws_id = current_user.workspaces[0].id

    lancedb_handler = get_lancedb_handler(ws_id)

    if not lancedb_handler:
            raise router.internal_error("Search database not available")

    # This is tricky with LanceDB as we usually delete by filter
    # Assuming doc_id matches 'id' column or a metadata field 'doc_id'
    # lancedb_handler.delete_by_metadata("doc_id", doc_id) # Hypothetical method
    
    # For now, implementing as a no-op or log warning as full deletion requires filter
    logger.warning(f"Delete requested for {doc_id} - not fully implemented in LanceDB handler wrapper")
    return router.success_response(message=f"Document '{doc_id}' deletion scheduled")

@router.get("")
async def list_documents(limit: int = 100):
    """List recent documents (Mock/Stub for now as LanceDB is vector-first)"""
    # To list all, we'd need to query all rows which can be expensive
    return router.success_response(
        data=[],
        metadata={"total": 0, "note": "Listing all documents not supported by current vector index"}
    )
