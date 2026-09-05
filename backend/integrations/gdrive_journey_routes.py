"""
Google Drive journey routes (Round 83 — severed link repair).

frontend-nextjs/components/integrations/GoogleDriveIntegration.tsx calls
``/api/gdrive/{connection-status,list-files}`` and
``POST /api/ingest-gdrive-document``. No real backend ever served these
paths (only a dev mock in scripts/start_main_app_simple.py), so the panel's
journey 404'd. These routes bind the REAL GoogleDriveService (Drive API v3)
to the paths the frontend already calls, plus a ``/sync`` full-ingestion
trigger.

Auth: session user via get_current_user; the Drive token is resolved
server-side from stored connections (ConnectionService auto-refreshes).
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core import ingest_jobs
from core.auth import get_current_user
from core.database import get_db
from core.ingestion_feedback import record_ingestion_feedback
from core.models import User
from integrations.google_drive_service import GoogleDriveService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gdrive", tags=["gdrive-journey"])

# Shared ingest-job read routes (recent-jobs list, status, ingested-ids) —
# the POST ingest endpoints below start jobs in the shared registry instead
# of running the pipeline synchronously (a folder subtree takes minutes; the
# Next dev proxy aborts sync requests at 30s and the UI saw phantom 500s).
ingest_jobs.register_ingest_job_routes(router, "google_drive")
ingest_jobs.register_ingested_ids_route(router, source="google_drive")

# Bare router: the panel posts document ingestion to a top-level path.
ingest_router = APIRouter(prefix="/api", tags=["gdrive-journey"])

# Auth pair the panel calls (mirrors onedrive_journey_routes.auth_router):
# POST /api/auth/gdrive/disconnect had NO backend route — the rewrite sent it
# nowhere and the Google grant stayed active after the UI said "Disconnected".
auth_router = APIRouter(prefix="/api/auth/gdrive", tags=["gdrive-journey"])

_service = GoogleDriveService()


class IngestDocumentRequest(BaseModel):
    file_id: str = Field(..., description="Drive file id")
    metadata: Optional[Dict[str, Any]] = None
    canvas_id: Optional[str] = Field(
        None,
        description="Load into this canvas's world (gated: the canvas must have an attached agent; content is role-tagged to its hire)",
    )


class FolderRef(BaseModel):
    id: str = Field(..., description="Drive folder id")
    name: Optional[str] = Field(None, description="Folder name (display only)")


class IngestFoldersRequest(BaseModel):
    folders: List[FolderRef] = Field(
        ..., min_length=1, description="Folders to ingest — each subtree is walked recursively"
    )
    canvas_id: Optional[str] = Field(
        None,
        description="Load into this canvas's world (gated: the canvas must have an attached agent; content is role-tagged to its hire)",
    )


def _canvas_load_role_or_409(
    db: Session, canvas_id: Optional[str], current_user: User
) -> Optional[str]:
    """Gate for canvas-scoped loads (a canvas loads data only through its
    hire): canvas absent → None (plain user-scoped ingest, unchanged);
    canvas present → ownership check + hire requirement, returning the
    hire's role tag. 409 NO_AGENT_ON_CANVAS when no hire is attached."""
    if not canvas_id:
        return None
    from core.agent_coordination import canvas_load_role
    from tools.canvas_crud_tool import _verify_canvas_owner

    if not _verify_canvas_owner(db, canvas_id, str(current_user.id)):
        raise HTTPException(status_code=404, detail=f"Canvas {canvas_id} not found")
    role = canvas_load_role(db, canvas_id)
    if not role:
        # Same structured body BaseAPIRouter.error_response produces, so the
        # UI handles one error shape across every gate.
        raise HTTPException(
            status_code=409,
            detail={
                "success": False,
                "error": {
                    "code": "NO_AGENT_ON_CANVAS",
                    "message": "This canvas has no agent attached — add an agent before loading data.",
                },
            },
        )
    return role


def _normalize_file(f: Dict[str, Any]) -> Dict[str, Any]:
    """Drive file resource → the GoogleDriveFile shape the panel renders."""
    caps = f.get("capabilities") or {}
    mime = f.get("mimeType", "")
    return {
        "id": f.get("id"),
        "name": f.get("name"),
        "mimeType": mime,
        "isFolder": mime == "application/vnd.google-apps.folder",
        "size": int(f["size"]) if f.get("size") is not None else None,
        "modifiedTime": f.get("modifiedTime"),
        "webViewLink": f.get("webViewLink"),
        "parents": f.get("parents"),
        "capabilities": {
            "canDownload": caps.get("canDownload", True),
            "canExport": "exportLinks" in f or caps.get("canExport", True),
        },
    }


@router.get("/connection-status")
async def connection_status(current_user: User = Depends(get_current_user)):
    """Report whether a usable Google Drive connection exists for the user."""
    token = await _service.get_access_token(str(current_user.id))
    return {
        "isConnected": bool(token),
        "reason": None if token else "No Google Drive connection found. Connect the integration first.",
        "user_id": str(current_user.id),
        "email": current_user.email if token else None,
    }


@auth_router.post("/disconnect")
async def disconnect(current_user: User = Depends(get_current_user)):
    """Drop the stored Google Drive connections for the user.

    Removes the legacy ConnectionService rows AND revokes the unified
    IntegrationToken grant rows. The token resolver (get_access_token) reads
    and refreshes those IntegrationToken rows — deleting only the legacy
    connections left the grant active and Drive still usable after the user
    clicked Disconnect.
    """
    from core.connection_service import connection_service

    removed = 0
    for integration_id in ("google_drive", "google"):
        try:
            for conn in connection_service.get_connections(str(current_user.id), integration_id):
                connection_service.delete_connection(conn["id"], str(current_user.id))
                removed += 1
        except Exception as e:
            logger.warning(f"Google Drive disconnect failed for {integration_id}: {e}")

    # Revoke the unified grant rows — the same google family the resolver
    # reads (google/google_drive/gmail). A revocation failure must NOT be
    # masked: returning success while the rows stay active would leave Drive
    # usable after "Disconnect" and the UI would report a disconnect that
    # never happened.
    try:
        from core.integrations.token_store import revoke_integration_tokens

        revoke_integration_tokens(current_user.id, ("google", "google_drive", "gmail"))
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Google Drive IntegrationToken revocation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not revoke the Google Drive grant — connection "
                "partially removed, please try again"
            ),
        )

    return {"success": True, "removed_connections": removed}


@router.get("/list-files")
async def list_files(
    folder_id: Optional[str] = Query(None),
    page_token: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """List files in a folder, normalized to the panel's GoogleDriveFile shape."""
    token = await _service.get_access_token(str(current_user.id))
    if not token:
        return {"files": [], "nextPageToken": None, "error": "not_connected"}

    result = await _service.list_files(
        token, folder_id=folder_id or None, page_token=page_token or None
    )
    if result.get("status") != "success":
        return {"files": [], "nextPageToken": None, "error": result.get("message")}

    data = result.get("data", {})
    files: List[Dict[str, Any]] = [
        _normalize_file(f) for f in data.get("files", []) if f.get("id")
    ]
    return {"files": files, "nextPageToken": data.get("nextPageToken")}


@router.post("/sync")
async def full_sync(current_user: User = Depends(get_current_user)):
    """Full-tree ingestion sync: every subfolder, every file type, paginated.

    Google-native Docs/Sheets/Slides are exported to Office formats before
    parsing. Long-running for large drives — returns when complete.
    """
    token = await _service.get_access_token(str(current_user.id))
    if not token:
        return {"success": False, "error": "not_connected"}
    result = await _service.full_sync(str(current_user.id), token)
    record_ingestion_feedback(
        current_user, "google_drive",
        int((result or {}).get("files_ingested") or 0),
        bool(isinstance(result, dict) and result.get("success")),
    )
    return result


@router.post("/ingest-folders")
async def ingest_folders(
    body: IngestFoldersRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a background job ingesting multiple folders — every selected
    folder's subtree is walked and ingested (same pipeline as /sync, scoped
    per folder). Returns {job_id} immediately; poll GET /ingest/jobs/{job_id}.
    A repeat call for the same folder set while the job runs coalesces.
    Explicit user selection — runs regardless of any bulk content-mode.

    body.canvas_id: load into a canvas's world — 409 NO_AGENT_ON_CANVAS
    unless the canvas has an attached hire (content is role-tagged to it).
    """
    token = await _service.get_access_token(str(current_user.id))
    if not token:
        return {"success": False, "error": "not_connected"}

    role = _canvas_load_role_or_409(db, body.canvas_id, current_user)

    folder_ids = [f.id for f in body.folders]
    existing = ingest_jobs.find_running("google_drive", str(current_user.id), "folder", folder_ids)
    if existing:
        return ingest_jobs.started_payload(existing, coalesced=True, folder_ids=folder_ids)

    job = ingest_jobs.create_job(
        "google_drive", str(current_user.id), "folder", folder_ids,
        extra={"folder_ids": folder_ids},
    )

    async def _run():
        results: List[Dict[str, Any]] = []
        total_ingested = 0
        # Plain user-scoped ingest keeps the OLD call shape byte-for-byte —
        # canvas-scoped loads are the only callers that add role.
        role_kwargs = {"role": role} if role else {}
        for folder in body.folders:
            try:
                res = await _service.ingest_folder_to_memory(
                    token, folder.id, folder_name=folder.name, **role_kwargs
                )
            except Exception as e:
                logger.error(
                    f"Google Drive folder ingestion failed for {folder.name or folder.id}: {e}"
                )
                res = {
                    "success": False,
                    "folder_id": folder.id,
                    "folder_name": folder.name,
                    "error": str(e),
                }
            if res.get("success"):
                total_ingested += res.get("files_ingested", 0) or 0
            results.append(res)

        # Per-app feedback: the user just ingested from THIS integration, so
        # its card's "Records ingested / Last ingested" must reflect it.
        record_ingestion_feedback(
            current_user, "google_drive", total_ingested,
            any(r.get("success") for r in results),
        )
        return {
            "success": any(r.get("success") for r in results),
            "folders_requested": len(body.folders),
            "folders_succeeded": sum(1 for r in results if r.get("success")),
            "files_ingested": total_ingested,
            "results": results,
        }

    ingest_jobs.start_job(job, _run)
    return ingest_jobs.started_payload(job, folder_ids=folder_ids)


@ingest_router.post("/ingest-gdrive-document")
async def ingest_gdrive_document(
    body: IngestDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a background job ingesting a single Google Drive file into Atom
    memory (all types attempted). Returns {job_id} immediately — poll
    GET /api/gdrive/ingest/jobs/{job_id}; a repeat call while the job runs
    coalesces. body.canvas_id: load into a canvas's world — 409
    NO_AGENT_ON_CANVAS unless the canvas has an attached hire."""
    token = await _service.get_access_token(str(current_user.id))
    if not token:
        return {"success": False, "error": "not_connected"}

    role = _canvas_load_role_or_409(db, body.canvas_id, current_user)

    existing = ingest_jobs.find_running("google_drive", str(current_user.id), "file", [body.file_id])
    if existing:
        return ingest_jobs.started_payload(existing, coalesced=True, file_id=body.file_id)

    extra_meta = {
        k: v for k, v in (body.metadata or {}).items() if k in ("name", "mimeType", "webViewLink")
    }
    if body.canvas_id:
        extra_meta["canvas_id"] = body.canvas_id
    job = ingest_jobs.create_job(
        "google_drive", str(current_user.id), "file", [body.file_id],
        extra={"file_id": body.file_id},
    )

    async def _run():
        role_kwargs = {"role": role} if role else {}
        result = await _service.ingest_file_to_memory(
            token, body.file_id, extra_metadata=extra_meta or None, **role_kwargs
        )
        record_ingestion_feedback(
            current_user, "google_drive", 1 if result.get("success") else 0,
            bool(result.get("success")),
        )
        return result

    ingest_jobs.start_job(job, _run)
    return ingest_jobs.started_payload(job, file_id=body.file_id)


def _next_page_token_from_link(next_link: Optional[str]) -> Optional[str]:
    """Extract pageToken from a Drive next-page link (kept for parity/tests)."""
    if not next_link:
        return None
    return parse_qs(urlparse(next_link).query).get("pageToken", [None])[0]
