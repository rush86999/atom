"""
Document Routes - API endpoints for document ingestion and search
"""
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid
from fastapi import Depends, File, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity, require_governance
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User
from core.security_dependencies import get_current_user

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/documents", tags=["Documents"])

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
async def ingest_document(
    request: DocumentIngestRequest,
    current_user: User = Depends(get_current_user)
):
    """Ingest a document for RAG/search"""
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

        logger.info(f"Document ingested: {doc_id}")
        return DocumentResponse(
            id=doc_id,
            title=title,
            type=doc_type,
            metadata=doc.get("metadata", {}),
            ingested_at=doc["ingested_at"],
            chunk_count=doc["chunk_count"]
        )
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        raise router.internal_error(detail=str(e))

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload and ingest a file directly"""
    try:
        content_bytes = await file.read()
        filename = file.filename.lower()
        content = ""
        
        # 1. Try Parsing based on file type
        import io
        
        if filename.endswith(".pdf"):
            try:
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content_bytes))
                text_content = []
                for page in pdf_reader.pages:
                    text_content.append(page.extract_text())
                content = "\n".join(text_content)
            except Exception as e:
                logger.error(f"PDF parsing failed: {e}")
                content = f"[Error parsing PDF: {str(e)}]"
                
        elif filename.endswith(".docx"):
            try:
                import docx
                doc = docx.Document(io.BytesIO(content_bytes))
                content = "\n".join([para.text for para in doc.paragraphs])
            except Exception as e:
                logger.error(f"DOCX parsing failed: {e}")
                content = f"[Error parsing DOCX: {str(e)}]"
                
        else:
            # Fallback to text decoding
            try:
                content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content = f"[Binary File: {file.filename}] (Text extraction failed)"
        
        # 2. Store document
        doc_id = str(uuid.uuid4())
        doc = {
            "id": doc_id,
            "title": file.filename,
            "content": content,
            "type": file.content_type or "application/octet-stream",
            "metadata": {"source": "upload", "size": len(content_bytes)},
            "ingested_at": datetime.now().isoformat(),
            "chunk_count": max(1, len(content) // 500)
        }
        _document_store[doc_id] = doc
        
        return DocumentResponse(
            id=doc.get("id"),
            title=doc.get("title"),
            type=doc.get("type"),
            metadata=doc.get("metadata", {}),
            ingested_at=doc.get("ingested_at"),
            chunk_count=doc.get("chunk_count")
        )
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise router.internal_error(detail=str(e))

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
        raise router.internal_error(detail=str(e))

@router.get("/{doc_id}")
async def get_document(doc_id: str):
    """Get a specific document by ID"""
    if doc_id not in _document_store:
        raise router.not_found_error("Document", doc_id)
    doc = _document_store[doc_id]
    return router.success_response(
        data={
            "id": doc_id,
            "title": doc.get("title"),
            "type": doc.get("type"),
            "content_preview": str(doc.get("content", ""))[:500],
            "metadata": doc.get("metadata", {}),
            "ingested_at": doc.get("ingested_at")
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
    agent_id: Optional[str] = None
):
    """
    Delete a document.

    **Governance**: Requires SUPERVISED+ maturity (HIGH complexity).
    - Document deletion is a high-complexity action
    - Requires SUPERVISED maturity or higher
    """
    if doc_id not in _document_store:
        raise router.not_found_error("Document", doc_id)

    del _document_store[doc_id]
    logger.info(f"Document deleted: {doc_id}")
    return router.success_response(message=f"Document '{doc_id}' deleted")

@router.get("")
async def list_documents(limit: int = 100):
    """List all ingested documents"""
    docs = list(_document_store.values())[:limit]
    return router.success_response(
        data=[
            {
                "id": d["id"],
                "title": d.get("title"),
                "type": d.get("type"),
                "ingested_at": d.get("ingested_at")
            }
            for d in docs
        ],
        metadata={"total": len(_document_store)}
    )
