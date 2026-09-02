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

from core.auth import get_current_user
from core.models import User
from integrations.google_drive_service import GoogleDriveService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gdrive", tags=["gdrive-journey"])

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
    return await _service.full_sync(str(current_user.id), token)


@ingest_router.post("/ingest-gdrive-document")
async def ingest_gdrive_document(
    body: IngestDocumentRequest,
    current_user: User = Depends(get_current_user),
):
    """Ingest a single Google Drive file into Atom memory (all types attempted)."""
    token = await _service.get_access_token(str(current_user.id))
    if not token:
        return {"success": False, "error": "not_connected"}

    extra_meta = {
        k: v for k, v in (body.metadata or {}).items() if k in ("name", "mimeType", "webViewLink")
    }
    result = await _service.ingest_file_to_memory(
        token, body.file_id, extra_metadata=extra_meta or None
    )
    return result


def _next_page_token_from_link(next_link: Optional[str]) -> Optional[str]:
    """Extract pageToken from a Drive next-page link (kept for parity/tests)."""
    if not next_link:
        return None
    return parse_qs(urlparse(next_link).query).get("pageToken", [None])[0]
