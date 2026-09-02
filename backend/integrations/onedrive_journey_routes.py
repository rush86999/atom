"""
OneDrive journey routes (Round 83 — severed link repair).

frontend-nextjs/components/integrations/OneDriveIntegration.tsx calls
``/api/onedrive/{connection-status,list-files,ingest-document}`` and
``/api/auth/onedrive/{authorize,disconnect}``. No real backend ever served
these paths (only a dev mock in scripts/start_main_app_simple.py), so the
panel's entire journey 404'd. These routes bind the REAL OneDriveService
(Graph API) to the paths the frontend already calls, plus a ``/sync``
full-ingestion trigger.

Auth: session user via get_current_user; the Graph token is resolved
server-side from stored connections (ConnectionService auto-refreshes).
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.auth import get_current_user
from core.models import User
from integrations.onedrive_service import OneDriveService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onedrive", tags=["onedrive-journey"])

# Separate bare router for the auth pair the panel calls.
auth_router = APIRouter(prefix="/api/auth/onedrive", tags=["onedrive-journey"])

_service = OneDriveService()


class IngestDocumentRequest(BaseModel):
    file_id: str = Field(..., description="Graph drive item id")
    metadata: Optional[Dict[str, Any]] = None


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Graph drive item → the OneDriveFile shape the panel renders."""
    file_meta = item.get("file") or {}
    fs = item.get("fileSystemInfo") or {}
    is_folder = "folder" in item or item.get("is_folder", False)
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "mime_type": file_meta.get("mimeType"),
        "created_time": fs.get("createdDateTime") or item.get("createdDateTime"),
        "modified_time": fs.get("lastModifiedDateTime") or item.get("lastModifiedDateTime"),
        "web_url": item.get("webUrl"),
        "parent_reference": item.get("parentReference"),
        "size": item.get("size"),
        "is_folder": is_folder,
        "icon": "folder" if is_folder else "file",
    }


@router.get("/connection-status")
async def connection_status(current_user: User = Depends(get_current_user)):
    """Report whether a usable OneDrive connection exists for the user."""
    token = await _service.get_access_token(str(current_user.id))
    return {
        "is_connected": bool(token),
        "reason": None if token else "No OneDrive/Microsoft connection found. Connect the integration first.",
        "user_id": str(current_user.id),
        "email": current_user.email if token else None,
    }


@router.get("/list-files")
async def list_files(
    folder_id: Optional[str] = Query(None),
    page_token: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """List files in a folder, normalized to the panel's OneDriveFile shape."""
    token = await _service.get_access_token(str(current_user.id))
    if not token:
        return {"files": [], "next_page_token": None, "error": "not_connected"}

    result = await _service.list_files(
        token, folder_id=folder_id or None, page_token=page_token or None
    )
    if result.get("status") != "success":
        return {"files": [], "next_page_token": None, "error": result.get("message")}

    data = result.get("data", {})
    files: List[Dict[str, Any]] = [
        _normalize_item(i) for i in data.get("value", []) if i.get("id")
    ]
    next_link = data.get("nextLink")
    next_token = next_link.split("$skiptoken=")[-1].split("&")[0] if next_link and "$skiptoken=" in next_link else None
    return {"files": files, "next_page_token": next_token}


@router.post("/ingest-document")
async def ingest_document(
    body: IngestDocumentRequest,
    current_user: User = Depends(get_current_user),
):
    """Ingest a single OneDrive file into Atom memory (all file types attempted)."""
    token = await _service.get_access_token(str(current_user.id))
    if not token:
        return {"success": False, "error": "not_connected"}

    extra_meta = {k: v for k, v in (body.metadata or {}).items() if k in ("name", "mime_type", "web_url")}
    result = await _service.ingest_file_to_memory(
        token, body.file_id, extra_metadata=extra_meta or None
    )
    return result


@router.post("/sync")
async def full_sync(current_user: User = Depends(get_current_user)):
    """Full-tree ingestion sync: every subfolder, every file type, paginated.

    Long-running for large drives — returns when complete.
    """
    token = await _service.get_access_token(str(current_user.id))
    if not token:
        return {"success": False, "error": "not_connected"}
    return await _service.full_sync(str(current_user.id), token)


@auth_router.get("/authorize")
async def authorize(current_user: User = Depends(get_current_user)):
    """Start the Microsoft OAuth flow via the unified authorize endpoint."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(
        url=f"/api/v1/auth/oauth/microsoft/authorize?user_id={current_user.id}"
    )


@auth_router.post("/disconnect")
async def disconnect(current_user: User = Depends(get_current_user)):
    """Drop the stored OneDrive/Microsoft connections for the user.

    Removes the legacy ConnectionService rows AND revokes the unified
    IntegrationToken grant rows. The token resolver (get_access_token) reads
    and refreshes those IntegrationToken rows — deleting only the legacy
    connections left the grant active and OneDrive still usable after the
    user clicked Disconnect.
    """
    from core.connection_service import connection_service

    removed = 0
    for integration_id in ("onedrive", "microsoft365"):
        try:
            for conn in connection_service.get_connections(str(current_user.id), integration_id):
                connection_service.delete_connection(conn["id"], str(current_user.id))
                removed += 1
        except Exception as e:
            logger.warning(f"OneDrive disconnect failed for {integration_id}: {e}")

    # Revoke the unified grant rows — the same microsoft family the callback
    # fans out to (microsoft/outlook/onedrive/microsoft365, in sync with
    # _TOKEN_FANOUT in api/oauth_routes.py). A revocation failure must NOT be
    # masked: the resolver reads these rows, so returning success here while
    # they stay active would leave OneDrive usable after "Disconnect" and the
    # UI would report a disconnect that never happened.
    try:
        from core.database import SessionLocal
        from core.models import IntegrationToken

        db = SessionLocal()
        try:
            db.query(IntegrationToken).filter(
                IntegrationToken.user_id == str(current_user.id),
                IntegrationToken.provider.in_(
                    ["onedrive", "microsoft", "outlook", "microsoft365"]
                ),
            ).update({IntegrationToken.status: "revoked"}, synchronize_session=False)
            db.commit()
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"OneDrive IntegrationToken revocation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not revoke the OneDrive Microsoft grant — connection "
                "partially removed, please try again"
            ),
        )

    return {"success": True, "removed_connections": removed}
