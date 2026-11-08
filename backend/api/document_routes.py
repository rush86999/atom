"""
Document Routes - API endpoints for document ingestion and search
"""
import asyncio
from datetime import datetime, timezone
import hashlib
import logging
import os
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote
from typing import Any, Dict, List, Optional
import uuid
import json
from fastapi import Depends, File, HTTPException, Request, Response, UploadFile, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity, require_governance
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.document_delete_service import delete_document_verified
from core.models import User
from core.security_dependencies import get_current_user
from core.lancedb_handler import get_lancedb_handler
from core.auto_document_ingestion import DocumentParser

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/documents", tags=["Documents"])


def _resolve_ws_id(current_user: Optional[User]) -> Optional[str]:
    """FK-first workspace resolution (J3 isolation contract).

    The workspaces RELATIONSHIP is empty for product-registered users whose
    user_workspaces row predates the register-flow fix; the users.workspace_id
    FK is the authoritative binding. Relationship-only resolution landed
    Documents-UI uploads in the SHARED default_shared store while
    /api/documents/search read the user's own store — the document was
    uploaded yet invisible (Phase E, 2026-10-17).
    """
    try:
        if current_user is not None:
            fk = getattr(current_user, "workspace_id", None)
            if fk:
                return fk
            rel = getattr(current_user, "workspaces", None)
            if rel:
                return rel[0].id
    except Exception:  # noqa: BLE001 — resolution must never break a route
        return None
    return None

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


def _content_doc_key(text: str) -> str:
    """Deterministic doc id from CONTENT (sha256), the identity that actually
    matters for user-submitted documents with no external record id.

    Same content → same id → one row (re-post skips as unchanged); different
    content → different id (titles/filenames never merge distinct documents
    and never collide same-named ones). This follows the standard idempotency
    pattern: source record id when one exists, content fingerprint when it
    doesn't."""
    import hashlib

    return "doc_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


async def _upsert_document(
    lancedb_handler,
    *,
    text: str,
    doc_key: str,
    source: str,
    metadata: Dict[str, Any],
    user_id: str,
    workspace_id: Optional[str] = None,
    extra_columns: Optional[Dict[str, Any]] = None,
) -> str:
    """Content-aware upsert on a stable doc key.

    Returns "skipped_unchanged" when the stored copy has the same content
    hash; otherwise replaces (delete prior versions, then write) and
    returns "written"."""
    from core.vector_upsert import upsert_document

    result = await upsert_document(
        lancedb_handler,
        table_name="documents",
        text=text,
        doc_id=doc_key,
        source=source,
        metadata=metadata,
        user_id=user_id,
        workspace_id=workspace_id,
        extra_columns=extra_columns,
    )
    if result == "write_failed":
        raise RuntimeError("LanceDB add_document returned False")
    return result


# Stored-document export (NEXT03). This is an export of the text already
# stored in the document index, not a download of original binary bytes.
MAX_DOCUMENT_EXPORT_BYTES = 2 * 1024 * 1024
DOCUMENT_EXPORT_FORMATS = ("text", "markdown", "json")
_FORBIDDEN_EXPORT_PARAMS = (
    "path", "url", "file_path", "locator", "download", "kind",
    "content_kind", "original",
)
_CONTENT_DISPOSITION_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_header_value(value: Any, max_length: int = 240) -> str:
    """Strip header-breaking/control characters from a server-owned value."""
    text = str(value or "").replace("\r", "").replace("\n", "")
    text = "".join(ch for ch in text if 0x20 <= ord(ch) < 0x7F)
    return text[:max_length]


def _safe_display_name(value: Any, doc_id: str) -> str:
    """A display-only name with no path, CR/LF or control material."""
    text = str(value or "").replace("\r", "").replace("\n", "")
    text = text.replace("\\", "/").rsplit("/", 1)[-1]
    text = "".join(ch for ch in text if ord(ch) >= 0x20).strip()
    return (text or f"document-{doc_id[:12]}")[:200]


def _safe_export_disposition(stored_name: str, extension: str,
                             doc_id: str) -> str:
    """RFC 6266/5987 attachment header with an ASCII fallback.

    The stored title/filename is used for display only; document identity is
    always the canonical doc id. CR/LF and path separators never reach the
    header. Unicode names use filename* exactly as Starlette's FileResponse
    does, with a sanitized ASCII filename fallback.
    """
    raw = str(stored_name or "").replace("\r", "").replace("\n", "")
    raw = raw.replace("\\", "/").rsplit("/", 1)[-1]
    raw = "".join(ch for ch in raw if ord(ch) >= 0x20).strip()
    stem = raw
    for suffix in (".txt", ".md", ".json"):
        if stem.lower().endswith(suffix):
            stem = stem[:-len(suffix)]
            break
    stem = stem.strip(" ._-") or f"document-{doc_id[:12]}"
    stem = stem[:100]
    full = f"{stem}.{extension}"
    ascii_stem = unicodedata.normalize("NFKD", stem).encode(
        "ascii", "ignore").decode("ascii")
    ascii_stem = _CONTENT_DISPOSITION_SAFE.sub("_", ascii_stem).strip("._-")
    ascii_stem = ascii_stem or f"document-{doc_id[:12]}"
    ascii_full = f"{ascii_stem}.{extension}"
    encoded = quote(full, safe="")
    if encoded != full:
        return (
            f'attachment; filename="{ascii_full}"; '
            f"filename*=utf-8''{encoded}"
        )
    return f'attachment; filename="{ascii_full}"'


def _export_not_found(doc_id: str) -> HTTPException:
    # Unknown, foreign, and removed all look the same to avoid an existence
    # oracle across workspaces.
    return router.not_found_error("Document", doc_id)


def _export_identity_failure(code: str, message: str) -> HTTPException:
    return router.error_response(
        error_code=code, message=message, status_code=409)


def _document_export_provenance(
    db: Session, workspace_id: Optional[str], tenant_id: Optional[str],
    doc_id: str, document: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate the indexed/SQL identity before any export body is produced.

    Current automated/versioned evidence must match the authoritative SQL
    revision through the existing strict matcher. Indexed/SQL document,
    workspace and tenant identity must agree wherever both sides are present.
    A missing/contradictory revision or scope on a known binding refuses, and
    only an explicit ``fresh`` SQL row is authoritative. Only producer-marked
    manual/legacy vector rows with no SQL/index binding may be exported as an
    explicitly snapshot-only, unknown-source-version document.
    """
    from core.doc_freshness_service import (
        ExtractionIdentityError,
        current_extraction_revision,
        extraction_identity,
    )
    from core.models import IngestedDocument

    metadata = document.get("metadata") if isinstance(
        document.get("metadata"), dict) else {}
    indexed_doc_id = str(metadata.get("pg_document_id") or "").strip()
    if indexed_doc_id and indexed_doc_id != str(doc_id):
        raise _export_identity_failure(
            "DOCUMENT_IDENTITY_MISMATCH",
            "The indexed extraction belongs to a different document.",
        )
    indexed_row_id = str(document.get("id") or "").strip()
    if indexed_row_id and indexed_row_id != str(doc_id):
        raise _export_identity_failure(
            "DOCUMENT_IDENTITY_MISMATCH",
            "The indexed extraction row identity does not match the requested "
            "document.",
        )

    # Scope is part of identity wherever it is present. An indexed metadata
    # workspace/tenant that disagrees with the request scope or its SQL row is
    # a contradictory extraction, never an authoritative export source. The
    # existing Personal-Edition null/default policy is preserved by comparing
    # only values that are actually present on both sides.
    indexed_workspace = str(metadata.get("workspace_id") or "").strip()
    if indexed_workspace and workspace_id and (
            indexed_workspace != str(workspace_id)):
        raise _export_not_found(str(doc_id))

    indexed_version = str(
        metadata.get("source_content_hash") or "").strip()
    indexed_tenant = str(metadata.get("tenant_id") or "").strip()
    row = db.query(IngestedDocument).filter(
        IngestedDocument.id == str(doc_id)).first()
    if row is not None and workspace_id and str(
            row.workspace_id or "") != str(workspace_id):
        raise _export_not_found(str(doc_id))
    if row is not None and indexed_workspace and str(
            row.workspace_id or "") and (
            indexed_workspace != str(row.workspace_id)):
        raise _export_identity_failure(
            "DOCUMENT_SCOPE_MISMATCH",
            "The indexed extraction workspace does not match its authoritative "
            "document record.",
        )
    if row is not None and tenant_id and str(
            row.tenant_id or "") and str(row.tenant_id) != str(tenant_id):
        raise _export_identity_failure(
            "DOCUMENT_SCOPE_MISMATCH",
            "The authoritative document record belongs to a different tenant.",
        )
    if indexed_tenant and tenant_id and indexed_tenant != str(tenant_id):
        # A legacy SQL NULL does not erase explicit indexed/request scope.
        # Check each known authority independently rather than selecting the
        # SQL row as the only comparison and skipping its absent value.
        raise _export_identity_failure(
            "DOCUMENT_SCOPE_MISMATCH",
            "The indexed extraction tenant does not match the authenticated "
            "scope.",
        )
    if indexed_tenant:
        # When a SQL row exists, its tenant is another independent comparison.
        # A NULL/legacy tenant supplies no additional evidence; the indexed
        # tenant must still have matched authenticated Personal-Edition scope.
        reference_tenant = (
            str(row.tenant_id or "") if row is not None
            else str(tenant_id or ""))
        if reference_tenant and indexed_tenant != reference_tenant:
            raise _export_identity_failure(
                "DOCUMENT_SCOPE_MISMATCH",
                "The indexed extraction tenant does not match the authoritative "
                "scope.",
            )

    row_version = str(
        getattr(row, "source_content_hash", "") or "").strip() if row else ""
    freshness = str(
        getattr(row, "freshness_status", "") or "").strip().lower() if row else ""
    if freshness == "removed":
        raise _export_not_found(str(doc_id))
    # Only an explicit ``fresh`` SQL row can carry authoritative provenance.
    # Empty/NULL/unknown/revoked and every other non-fresh status fail closed
    # here; checking only NON_FRESH_STATUSES let unknown values through.
    if row is not None and freshness != "fresh":
        raise router.error_response(
            error_code="DOCUMENT_NOT_CURRENT",
            message=(
                "The authoritative document is not current; refresh or "
                "re-ingest it before exporting."),
            details={"freshness_status": freshness or None},
            status_code=409,
        )

    stored_source = str(document.get("source") or "")
    manual_source = (
        stored_source.startswith("upload:")
        or stored_source.startswith("api:")
    )
    pg_manual = bool(row is not None and (
        str(getattr(row, "integration_id", "") or "").lower()
        == "manual_upload"
        or str(getattr(row, "external_id", "") or "").startswith("upload_")
    ))
    known_binding = bool(indexed_doc_id or indexed_version or row is not None)

    if indexed_version and row_version:
        try:
            source_version = current_extraction_revision(
                indexed_version, row_version)
        except ExtractionIdentityError:
            raise _export_identity_failure(
                "DOCUMENT_REVISION_INVALID",
                "The stored document revision is missing, stale, or does not "
                "match its authoritative record. Re-index or re-upload it "
                "before exporting.",
            ) from None
        kind = extraction_identity(source_version)["kind"]
        return {
            "provenance_status": "authoritative",
            "source_version": source_version,
            "source_version_kind": kind,
            "source_version_status": "matched",
            "freshness_status": freshness or None,
            "source_label": (
                str(getattr(row, "integration_id", "") or "")
                if row is not None else "unknown"),
        }

    if indexed_version or row_version:
        # A known binding with only one side is not legacy: it is an
        # incomplete/contradictory identity and must fail closed.
        raise _export_identity_failure(
            "DOCUMENT_IDENTITY_UNVERIFIABLE",
            "This document has a known index or SQL binding but no matching "
            "source revision on both sides. Re-index or re-upload it before "
            "exporting.",
        )

    if known_binding and not (manual_source and pg_manual):
        raise _export_identity_failure(
            "DOCUMENT_IDENTITY_UNVERIFIABLE",
            "This document's source revision cannot be verified. Re-index or "
            "re-upload it before exporting.",
        )
    if not known_binding and not manual_source:
        raise _export_identity_failure(
            "DOCUMENT_IDENTITY_UNVERIFIABLE",
            "This document's source revision cannot be verified. Re-index or "
            "re-upload it before exporting.",
        )
    if indexed_doc_id:
        # A join-key-bearing row is a known indexed binding, never a manual
        # legacy snapshot.
        raise _export_identity_failure(
            "DOCUMENT_IDENTITY_UNVERIFIABLE",
            "This document's source revision cannot be verified. Re-index or "
            "re-upload it before exporting.",
        )

    return {
        "provenance_status": "snapshot_only",
        "source_version": None,
        "source_version_kind": "missing",
        "source_version_status": "unknown",
        "freshness_status": None,
        "source_label": (
            str(getattr(row, "integration_id", "") or "manual_upload")
            if row is not None else "manual_upload"),
    }


@router.post("/ingest", response_model=DocumentResponse)
async def ingest_document(
    request: DocumentIngestRequest,
    current_user: User = Depends(get_current_user)
):
    """Ingest a document for RAG/search"""
    try:

        # Dynamic workspace resolution
        ws_id = _resolve_ws_id(current_user)
             
        lancedb_handler = get_lancedb_handler(ws_id)
        
        if not lancedb_handler:
             raise router.internal_error("Search database not available")

        # Content-hash identity: no external record id exists for API-pasted
        # text, so the content fingerprint IS the document identity (same
        # content → same row regardless of title; different content → new
        # row even under the same title).
        content = request.content or ""
        doc_type = request.type
        title = request.title or "Untitled document"

        if not content:
            content = "(Empty document)"
        doc_id = _content_doc_key(content)

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
        await _upsert_document(
            lancedb_handler,
            text=content,
            doc_key=doc_id,
            source=f"api:{doc_id}",
            metadata=metadata,
            user_id=str(current_user.id) if current_user else "default_user",
            workspace_id=ws_id,
            extra_columns={"freshness_status": "fresh"},
        )

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
        # Dynamic workspace resolution (FK-first, J3 isolation contract)
        ws_id = _resolve_ws_id(current_user)
             
        lancedb_handler = get_lancedb_handler(ws_id)

        if not lancedb_handler:
             raise router.internal_error("Search database not available")

        filename = file.filename
        file_ext = filename.split(".")[-1].lower() if "." in filename else "txt"

        # Upload guardrails: check size BEFORE reading into memory (M5 fix).
        MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
        ALLOWED_EXTENSIONS = {
            "txt", "pdf", "docx", "doc", "xlsx", "xls", "pptx", "ppt",
            "eml", "csv", "json", "md", "html", "htm", "rtf", "odt", "png", "jpg",
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

        # These formats need docling (OLE2 .doc/.ppt, RTF/ODT parsers). With
        # docling absent the old path accepted them and stored an empty
        # placeholder as if ingestion succeeded. Refuse instead, and name the
        # reason. `.pptx` is NOT here — python-pptx handles it natively.
        if file_ext in {"doc", "ppt", "rtf", "odt"}:
            try:
                from core.docling_processor import is_docling_available
                docling_ok = is_docling_available()
            except Exception:
                docling_ok = False
            if not docling_ok:
                raise router.error_response(
                    error_code="UNSUPPORTED_FILE_TYPE",
                    message=(
                        f"File type '{file_ext}' requires the optional docling "
                        "parser, which is not installed. Convert it to "
                        f"{'docx' if file_ext == 'doc' else 'pptx' if file_ext == 'ppt' else 'txt' if file_ext == 'rtf' else 'docx'} "
                        "or install docling."
                    ),
                    status_code=415,
                )

        content_bytes = await file.read()
        if len(content_bytes) > MAX_UPLOAD_SIZE:
            raise router.error_response(
                error_code="FILE_TOO_LARGE",
                message=f"File exceeds the {MAX_UPLOAD_SIZE // (1024*1024)} MB upload limit",
                status_code=413,
            )

        # 0. Materialize the SQL-queryable sheet datasets BEFORE parsing —
        # fire-and-forget, exactly like the storage-read path (2026-10-01
        # three-domain live finding: an UPLOADED workbook ingested as a
        # document but never entered the sheet-datasets catalog, so the
        # named-file reader answered 'not present in the catalogued file
        # index' for a file the user had JUST uploaded — the 2026-09-07
        # 'two reads, zero datasets' class, on the upload surface).
        if file_ext in ("xlsx", "xls", "xlsm", "csv"):
            try:
                from core.sheet_dataset_service import (
                    ensure_sheet_dataset_background,
                    sheet_datasets_enabled,
                )

                if sheet_datasets_enabled():
                    ensure_sheet_dataset_background(
                        content_bytes,
                        file_name=filename,
                        source="upload",
                        user_id=str(current_user.id) if current_user else None,
                        workspace_id=ws_id or "default",
                        external_id=None,
                    )
            except Exception as ds_err:  # noqa: BLE001 — never block upload
                logger.warning(
                    f"sheet datasets: upload scheduling failed for {filename}: {ds_err}")

        # 1. Parse content using robust parser
        content = await DocumentParser.parse_document(content_bytes, file_ext, filename)
        
        if not content:
             content = f"[Empty or unparseable file: {filename}]"

        # 2. Store document — content-hash identity: same file re-uploaded →
        # same row (skip/replace); DIFFERENT files sharing a filename → two
        # rows (a filename is metadata, never an identity key).
        doc_id = _content_doc_key(content)
        upload_root = Path(
            os.getenv("ATOM_OFFICE_DIR") or "data/office").expanduser()
        upload_root = upload_root / "uploads"
        upload_root.mkdir(parents=True, exist_ok=True)
        materialized_path = upload_root / f"{doc_id}.{file_ext or 'bin'}"
        materialized_path.write_bytes(content_bytes)
        from core.doc_freshness_service import extraction_content_hash

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
            # The authoritative and indexed revisions must be the same kind:
            # extraction revisions are versioned (ev<version>:<digest>), so a
            # manual upload stores the extraction revision, not a bare hash.
            "source_content_hash": extraction_content_hash(content),
            "author": current_user.email if current_user else "unknown"
        }

        await _upsert_document(
            lancedb_handler,
            text=content,
            doc_key=doc_id,
            source=f"upload:{filename}",
            metadata=metadata,
            user_id=str(current_user.id) if current_user else "default_user",
            workspace_id=ws_id,
            # The search path filters documents to freshness_status=='fresh'
            # (core/lancedb_handler.py search): without the stamp the row is
            # permanently invisible even in the right workspace store.
            extra_columns={"freshness_status": "fresh"},
        )

        # 3. Aligned PG row: gives the upload full journey parity with synced
        # documents — lexical leg (FTS), VFS cat, citability. id MUST equal the
        # LanceDB doc_id (join-key bridge).
        try:
            from core.database import get_db_session
            from core.models import IngestedDocument

            with get_db_session() as db:
                # Upsert on the stable doc key: a re-upload of the same file
                # refreshes the mirror row instead of hitting the PK.
                from core.doc_freshness_service import extraction_content_hash

                _row = (
                    db.query(IngestedDocument)
                    .filter(IngestedDocument.id == doc_id)
                    .first()
                )
                if _row is None:
                    _row = IngestedDocument(
                        id=doc_id,
                        workspace_id=ws_id or "default",
                        tenant_id=getattr(current_user, "tenant_id", None),
                        external_id=f"upload_{doc_id}",
                        integration_id="manual_upload",
                    )
                    db.add(_row)
                _row.file_name = filename
                _row.file_path = str(materialized_path)
                _row.file_type = file_ext
                _row.file_size_bytes = len(content_bytes)
                _row.content_preview = content[:500]
                _row.ingested_at = datetime.now(timezone.utc)
                _row.source_content_hash = extraction_content_hash(content)
                _row.last_verified_at = datetime.now(timezone.utc)
                _row.freshness_status = "fresh"
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
        # Dynamic workspace resolution — ISOLATION (journey J3): the
        # users.workspace_id FK first. The workspaces RELATIONSHIP was empty
        # for product-registered users (user_workspaces never populated), so
        # ws_id stayed None and the search hit the SHARED "default_shared"
        # store: any registered user could read any other's documents.
        ws_id = _resolve_ws_id(current_user)

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
        ws_id = _resolve_ws_id(current_user)

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

@router.get("/{doc_id}/export")
async def export_document(
    doc_id: str,
    request: Request,
    format: str = Query("text", description="text, markdown or json"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export the currently stored extracted text of one authorized document.

    This is not an original-binary download. Identity/freshness are validated
    against the durable SQL row and the indexed revision with the existing
    strict revision matcher; the export body is the full stored text, not the
    model reader's 20k context window.
    """
    for param in _FORBIDDEN_EXPORT_PARAMS:
        if param in request.query_params:
            raise router.error_response(
                error_code="CLIENT_PATH_NOT_ALLOWED",
                message=(
                    "Export accepts only a document id and a supported format; "
                    "client paths, URLs and original-binary modes are not "
                    "accepted."),
                details={"parameter": param},
                status_code=422,
            )
    export_format = str(format or "text").strip().lower()
    if export_format not in DOCUMENT_EXPORT_FORMATS:
        raise router.error_response(
            error_code="UNSUPPORTED_EXPORT_FORMAT",
            message=(
                "Unsupported export format. Supported formats are text, "
                "markdown and json."),
            details={"allowed_formats": list(DOCUMENT_EXPORT_FORMATS)},
            status_code=422,
        )

    workspace_id = _resolve_ws_id(current_user)
    try:
        handler = get_lancedb_handler(workspace_id)
        if not handler:
            raise router.error_response(
                error_code="DOCUMENT_STORE_UNAVAILABLE",
                message="The document store is unavailable; retry.",
                status_code=503,
            )
        document = handler.get_document_by_id("documents", str(doc_id))
        if not document:
            raise _export_not_found(str(doc_id))
        from core.personal_scope import resolve_tenant_id

        provenance = _document_export_provenance(
            db, workspace_id, resolve_tenant_id(current_user),
            str(doc_id), document)
        text = str(document.get("text") or "")
        if not text.strip():
            raise router.error_response(
                error_code="DOCUMENT_EMPTY",
                message="The selected document has no stored text to export.",
                status_code=422,
            )
        text_bytes = text.encode("utf-8")
        if len(text_bytes) > MAX_DOCUMENT_EXPORT_BYTES:
            raise router.error_response(
                error_code="EXPORT_TOO_LARGE",
                message=(
                    "The stored document text exceeds the bounded export "
                    "size; select a smaller document."),
                details={"max_bytes": MAX_DOCUMENT_EXPORT_BYTES},
                status_code=413,
            )

        metadata = document.get("metadata") if isinstance(
            document.get("metadata"), dict) else {}
        stored_name = _safe_display_name(
            metadata.get("file_name")
            or metadata.get("filename")
            or metadata.get("title")
            or str(doc_id),
            str(doc_id),
        )
        stored_text_sha = hashlib.sha256(text_bytes).hexdigest()
        truncation = metadata.get("truncated")
        if truncation is None:
            truncation = metadata.get("extraction_truncated")
        truncated = bool(truncation) if truncation is not None else None

        if export_format == "text":
            body = text_bytes
            media_type = "text/plain; charset=utf-8"
            extension = "txt"
        elif export_format == "markdown":
            body = text_bytes
            media_type = "text/markdown; charset=utf-8"
            extension = "md"
        else:
            payload = {
                "schema_version": 1,
                "document_id": str(doc_id),
                "title": _safe_display_name(
                    metadata.get("title") or stored_name, str(doc_id)),
                "file_name": stored_name,
                "file_type": _safe_header_value(
                    metadata.get("file_type") or "unknown", 40) or "unknown",
                "source": _safe_header_value(
                    provenance["source_label"] or "unknown", 80) or "unknown",
                "source_version": provenance["source_version"],
                "source_version_kind": provenance["source_version_kind"],
                "source_version_status": provenance["source_version_status"],
                "freshness_status": provenance["freshness_status"],
                "provenance_status": provenance["provenance_status"],
                "content_kind": "extracted_text",
                "format": "json",
                "reader": "lancedb.documents.get_document_by_id",
                "stored_text_bytes": len(text_bytes),
                "stored_text_truncated": truncated,
                "stored_text_sha256": stored_text_sha,
                "content": text,
            }
            body = json.dumps(
                payload, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(body) > MAX_DOCUMENT_EXPORT_BYTES:
                raise router.error_response(
                    error_code="EXPORT_TOO_LARGE",
                    message=(
                        "The stored document text exceeds the bounded export "
                        "size; select a smaller document."),
                    details={"max_bytes": MAX_DOCUMENT_EXPORT_BYTES},
                    status_code=413,
                )
            media_type = "application/json; charset=utf-8"
            extension = "json"

        headers = {
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": _safe_export_disposition(
                str(stored_name), extension, str(doc_id)),
            "X-Document-Id": _safe_header_value(doc_id),
            "X-Document-Content-Kind": "extracted_text",
            "X-Document-Provenance": provenance["provenance_status"],
            "X-Document-Source-Version-Kind": provenance["source_version_kind"],
            "X-Document-Source-Version-Status": provenance["source_version_status"],
            "X-Document-Stored-Text-Sha256": stored_text_sha,
        }
        if provenance["source_version"]:
            headers["X-Document-Source-Version"] = _safe_header_value(
                provenance["source_version"])
        if provenance["freshness_status"]:
            headers["X-Document-Freshness"] = _safe_header_value(
                provenance["freshness_status"])
        if export_format == "markdown":
            headers["X-Document-Export-Transform"] = "none"
        headers["X-Document-Export-Sha256"] = hashlib.sha256(body).hexdigest()
        return Response(content=body, media_type=media_type, headers=headers)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - no content/params in logs
        logger.error(
            "Document export failed for %s (%s)",
            doc_id, type(exc).__name__)
        raise router.error_response(
            error_code="DOCUMENT_EXPORT_FAILED",
            message="The document export failed. Retry after refreshing.",
            status_code=500,
        ) from None


@router.delete("/{doc_id}")
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="delete_document",
    feature="document"
)
async def delete_document(
    doc_id: str,
    request: Request,
    operation_id: Optional[str] = Query(
        None,
        description=(
            "Optional stable identity of the logical deletion. A replay of "
            "the same id returns the original receipt without a second "
            "deletion."),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    agent_id: Optional[str] = None
):
    """
    Delete a document and its chunk family, then verify the effect.

    LanceDB and SQL are separate stores: this route does not claim one atomic
    transaction. The returned ``verification`` is ``verified`` only after a
    fresh readback shows both the exact base row and the ``<doc_id>::``
    chunk family gone. A removed base row with surviving chunks is reported
    as a 503 ``committed_unverified`` outcome with the original operation id
    and ``replay: do_not_repeat``; it is never a clean success.
    """
    if agent_id:
         pass # unused for now

    # Dynamic workspace resolution
    ws_id = _resolve_ws_id(current_user)

    lancedb_handler = get_lancedb_handler(ws_id)

    if not lancedb_handler:
            raise router.internal_error("Search database not available")

    # Chunk-family semantics (2026-09-13 review, third site of the
    # d94a5e6df fix — auto_document_ingestion already pairs both deletes):
    #   1. An id that exists ONLY as chunks (`<doc_id>::c0..cN`, parent row
    #      already gone) is a deletable FAMILY, not a 404.
    #   2. Deleting a base row must also delete its chunk family or every
    #      chunk is orphaned in LanceDB (still retrievable, still stamped
    #      with a departed parent — 2,676 such orphans measured live
    #      2026-09-11).
    result = await delete_document_verified(
        db=db,
        actor=current_user,
        workspace_id=ws_id,
        doc_id=doc_id,
        handler=lancedb_handler,
        operation_id=operation_id,
    )

    status_value = str(result.get("status") or "")
    if status_value == "refused":
        if int(result.get("http_status") or 0) == 404:
            raise router.not_found_error("Document", doc_id)
        raise HTTPException(
            status_code=int(result.get("http_status") or 422),
            detail={
                "error": {
                    "code": result.get("error_code") or "VALIDATION_ERROR",
                    "message": result.get("error") or "Request refused",
                },
                "field": result.get("field"),
                "verification": result.get("verification"),
            },
        )
    if status_value == "conflict":
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": result.get("error_code") or "OPERATION_CONFLICT",
                    "message": result.get("error") or "Conflict",
                },
                "verification": result.get("verification"),
            },
        )
    if status_value in ("committed_unverified", "effect_unknown"):
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": (
                        "DOCUMENT_EFFECT_UNKNOWN"
                        if status_value == "effect_unknown"
                        else "DOCUMENT_DELETE_UNVERIFIED"),
                    "message": result.get("message")
                    or "The document deletion outcome is uncertain.",
                },
                "verification": result.get("verification"),
                "operation_id": result.get("operation_id"),
                "audit_id": result.get("audit_id"),
                "target_id": result.get("target_id"),
                "data": result.get("data"),
            },
        )
    if status_value == "not_applied":
        raise HTTPException(
            status_code=int(result.get("http_status") or 409),
            detail={
                "error": {
                    "code": result.get("error_code")
                    or "DOCUMENT_DELETE_NOT_APPLIED",
                    "message": result.get("error")
                    or "The document deletion did not apply.",
                },
                "verification": result.get("verification"),
                "operation_id": result.get("operation_id"),
            },
        )

    verification = (
        result.get("verification")
        or (result.get("data") or {}).get("verification"))
    return router.success_response(
        data=result.get("data"),
        message=result.get("message"),
        metadata={
            "operation_id": result.get("operation_id"),
            "audit_id": result.get("audit_id"),
            "target_id": result.get("target_id"),
            "verification": verification,
        },
    )

@router.get("")
async def list_documents(
    limit: int = Query(100, ge=1, le=100, description="Max results (capped at 100)"),
    offset: int = Query(0, ge=0, description="Skip offset (must be >= 0)"),
    current_user: User = Depends(get_current_user)
):
    """List recent documents"""
    try:
        # Dynamic workspace resolution
        ws_id = _resolve_ws_id(current_user)

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
