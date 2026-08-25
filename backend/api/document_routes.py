"""
Document Routes - API endpoints for document ingestion and search
"""
import asyncio
from datetime import datetime, timezone
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


async def _stored_chunk_count(lancedb_handler, doc_id: str, fallback_text: str) -> int:
    """Chunk count from the STORED text (post-redaction), not the raw input.

    The handler stores one row per document; the count reflects ~500-char
    retrieval chunks of what actually landed in LanceDB."""
    text = fallback_text
    try:
        stored = await asyncio.to_thread(
            lancedb_handler.get_document_by_id, "documents", doc_id
        )
        if stored and stored.get("text"):
            text = stored["text"]
    except Exception:
        pass
    return max(1, -(-len(text) // 500))

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

        # to_thread: add_document embeds synchronously; called directly on the
        # loop thread, embed_text's same-thread guard makes every write fail.
        success = await asyncio.to_thread(
            lancedb_handler.add_document,
            table_name="documents",
            text=content,
            source=f"api:{doc_id}",
            metadata=metadata,
            user_id=str(current_user.id) if current_user else "default_user",
            doc_id=doc_id
        )

        if not success:
             raise router.internal_error("Failed to store document in LanceDB")

        return DocumentResponse(
            id=doc_id,
            title=title,
            type=doc_type,
            metadata=metadata,
            ingested_at=metadata["ingested_at"],
            chunk_count=await _stored_chunk_count(lancedb_handler, doc_id, content)
        )
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        raise router.internal_error(message="Internal error")

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

        filename = file.filename
        file_ext = filename.split(".")[-1].lower() if "." in filename else "txt"

        # Upload guardrails: check size BEFORE reading into memory (M5 fix).
        MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
        ALLOWED_EXTENSIONS = {
            "txt", "pdf", "docx", "doc", "xlsx", "xls", "pptx", "ppt",
            "csv", "json", "md", "html", "htm", "rtf", "odt", "png", "jpg",
            "jpeg", "gif", "bmp", "tiff", "mp3", "wav", "mp4", "avi", "mov",
        }
        # Check declared size first (SpooledTemporaryFile reports it).
        if file.size is not None and file.size > MAX_UPLOAD_SIZE:
            raise router.error_response(
                error_code="FILE_TOO_LARGE",
                message=f"File exceeds the {MAX_UPLOAD_SIZE // (1024*1024)} MB upload limit",
                status_code=413,
            )
        if file_ext not in ALLOWED_EXTENSIONS:
            raise router.error_response(
                error_code="UNSUPPORTED_FILE_TYPE",
                message=f"File type '{file_ext}' is not supported",
                status_code=415,
            )

        content_bytes = await file.read()
        if len(content_bytes) > MAX_UPLOAD_SIZE:
            raise router.error_response(
                error_code="FILE_TOO_LARGE",
                message=f"File exceeds the {MAX_UPLOAD_SIZE // (1024*1024)} MB upload limit",
                status_code=413,
            )

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
            # Join-key bridge: lets hybrid search + VFS resolve this vector row.
            "pg_document_id": doc_id,
            "source_type": "upload",
            "integration_id": "manual_upload",
            "author": current_user.email if current_user else "unknown"
        }

        success = await asyncio.to_thread(
            lancedb_handler.add_document,
            table_name="documents",
            text=content,
            source=f"upload:{filename}",
            metadata=metadata,
            user_id=str(current_user.id) if current_user else "default_user",
            workspace_id=ws_id,
            doc_id=doc_id
        )

        if not success:
             raise router.internal_error("Failed to store uploaded document in LanceDB")

        # 3. Aligned PG row: gives the upload full journey parity with synced
        # documents — lexical leg (FTS), VFS cat, citability. id MUST equal the
        # LanceDB doc_id (join-key bridge).
        try:
            from core.database import get_db_session
            from core.models import IngestedDocument

            with get_db_session() as db:
                db.add(IngestedDocument(
                    id=doc_id,
                    workspace_id=ws_id or "default",
                    tenant_id=getattr(current_user, "tenant_id", None),
                    file_name=filename,
                    file_path=f"upload:{filename}",
                    file_type=file_ext,
                    integration_id="manual_upload",
                    file_size_bytes=len(content_bytes),
                    content_preview=content[:500],
                    external_id=f"upload_{doc_id}",
                    ingested_at=datetime.now(timezone.utc),
                    source_content_hash=None,
                    last_verified_at=datetime.now(timezone.utc),
                    freshness_status="fresh",
                ))
                db.commit()
        except Exception as pg_err:
            # Vector row already stored; never fail the upload because the
            # mirror row failed — search still finds it (bridged:false).
            logger.warning(f"PG mirror row skipped for upload {doc_id}: {pg_err}")
        
        return DocumentResponse(
            id=doc_id,
            title=filename,
            type=file.content_type or "application/octet-stream",
            metadata=metadata,
            ingested_at=metadata["ingested_at"],
            chunk_count=await _stored_chunk_count(lancedb_handler, doc_id, content)
        )
    except Exception as e:
        # BUG-124: Previously the broad `except Exception` caught the 413/415
        # HTTPExceptions raised by validation checks above and re-raised them
        # as a generic 500. Now re-raises HTTPException so the user sees the
        # specific error (file too large, unsupported type).
        from fastapi import HTTPException as _FastAPIHTTPException
        if isinstance(e, _FastAPIHTTPException):
            raise
        logger.error(f"File upload failed: {e}")
        raise router.internal_error(message="Internal error")

@router.get("/search", response_model=SearchResponse)
async def search_documents(
    q: str, 
    limit: int = Query(10, ge=1, le=200, description="Max results (capped at 200)"),
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
        
        # Use LanceDB vector search. to_thread: search() embeds the query
        # synchronously; on the loop thread the same-thread embed guard makes
        # every search return [] (writes were fixed the same way).
        results_data = await asyncio.to_thread(
            lancedb_handler.search,
            table_name="documents",
            query=q,
            limit=limit,
        )
        
        results = []
        for r in results_data:
             # Handle metadata parsing if string
             meta = r.get("metadata", {})
             if isinstance(meta, str):
                  try:
                       meta = json.loads(meta)
                  except Exception:                        meta = {}
             
             results.append(SearchResult(
                  id=str(r.get("id", uuid.uuid4())), # Fallback ID if not in result
                  title=meta.get("title") or meta.get("file_name") or "Untitled",
                  content_preview=r.get("text", "")[:200] + "...",
                  score=r.get("score", r.get("_score", 0.0)),
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
        raise router.internal_error(message="Internal error")

@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific document by ID"""
    try:
        # Dynamic workspace resolution
        ws_id = None
        if current_user and current_user.workspaces:
             ws_id = current_user.workspaces[0].id

        lancedb_handler = get_lancedb_handler(ws_id)
        if not lancedb_handler:
             raise router.internal_error("Search database not available")

        doc = lancedb_handler.get_document_by_id("documents", doc_id)
        
        if not doc:
            raise router.not_found_error("Document", doc_id)

        return router.success_response(data={
            "id": doc["id"],
            "title": doc.get("metadata", {}).get("title", "Untitled"),
            "content": doc.get("text", ""), # Full content
            "type": doc.get("metadata", {}).get("file_type", "unknown"),
            "metadata": doc.get("metadata", {}),
            "ingested_at": doc.get("created_at")
        })
    except Exception as e:
        from fastapi import HTTPException as _FastAPIHTTPException
        if isinstance(e, _FastAPIHTTPException):
            raise
        logger.error(f"Failed to get document {doc_id}: {e}")
        raise router.internal_error(message="Internal error")

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

    # 404 on unknown id, then delete by the id column (to_thread: delete may
    # touch the sync LanceDB path). Previously a logged no-op that returned
    # success — the document was never removed and the user was told it was.
    doc = await asyncio.to_thread(lancedb_handler.get_document_by_id, "documents", doc_id)
    if not doc:
         raise router.not_found_error("Document", doc_id)
    deleted = await asyncio.to_thread(
        lancedb_handler.delete_documents_by_id, "documents", doc_id
    )
    if not deleted:
         raise router.internal_error(message="Failed to delete document")

    return router.success_response(message=f"Document '{doc_id}' deleted")

@router.get("")
async def list_documents(
    limit: int = Query(100, ge=1, le=100, description="Max results (capped at 100)"),
    offset: int = Query(0, ge=0, description="Skip offset (must be >= 0)"),
    current_user: User = Depends(get_current_user)
):
    """List recent documents"""
    try:
        # Dynamic workspace resolution
        ws_id = None
        if current_user and current_user.workspaces:
             ws_id = current_user.workspaces[0].id

        lancedb_handler = get_lancedb_handler(ws_id)
        if not lancedb_handler:
             return router.success_response(data=[], metadata={"total": 0})

        docs = lancedb_handler.list_documents("documents", limit=limit, offset=offset)
        
        return router.success_response(
            data=docs,
            metadata={"total": len(docs), "limit": limit, "offset": offset}
        )
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise router.internal_error(message="Internal error")
