"""Integration memory tools — the hire's on-demand access to ingested
integration structure and just-in-time file ingestion.

Training-circuit framing: the mapped structure (index rows) is what the hire
has LEARNED about the user's territory; `integration_ingest_item` is how the
hire EXERCISES it — pulling one file's contents when a task needs it,
respecting the user's selective-ingestion settings (enabled flag + size cap)
so disk use stays bounded. Provenance: ingested content lands as untrusted
FILE/RETRIEVED material (spotlighted at recall) with full source attribution.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.drive_tree_ingestion import FILE_FETCHERS, STRUCTURE_ADAPTERS

logger = logging.getLogger(__name__)

# Just-in-time ingestion size guard (mirrors IngestionSettings.max_file_size_mb;
# the user's per-integration setting, when tighter, wins).
DEFAULT_MAX_INGEST_MB = 50


def _settings_for(integration_id: str, ws: str):
    try:
        from core.auto_document_ingestion import AutoDocumentIngestionService

        return AutoDocumentIngestionService(workspace_id=ws).get_settings(
            integration_id
        )
    except Exception as settings_err:
        logger.debug(f"ingestion settings unavailable: {settings_err}")
        return None


async def integration_search_index(
    integration_id: str,
    query: str,
    limit: int = 8,
    workspace_id: str = "default",
) -> Dict[str, Any]:
    """Search the mapped structure index for an integration (metadata rows)."""
    if not integration_id or not query:
        return {"success": False, "error": "integration_id and query are required"}
    ws = workspace_id or "default"
    try:
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        result = await DocumentsHybridSearch().search(
            query=query[:500], limit=limit, source=f"{integration_id}-index"
        )
        hits = []
        for hit in (result or {}).get("results", []) or []:
            hits.append(
                {
                    "name": hit.get("title"),
                    "source": hit.get("source"),
                    "preview": (hit.get("preview") or "")[:200],
                    "external_id": (hit.get("metadata") or {}).get("external_id"),
                }
            )
        return {"success": True, "integration_id": integration_id, "hits": hits}
    except Exception as search_err:
        logger.debug(f"index search failed: {search_err}")
        return {"success": False, "error": f"Index search failed: {search_err}"}


def _open_office_canvas(
    integration_id: str,
    external_id: str,
    file_name: str,
    content: bytes,
    workspace_id: str,
    user_id: str,
) -> Optional[str]:
    """Materialize a downloaded OFFICE file (xlsx/docx/pptx) as a real file
    bound to an in-app office canvas (OfficeFileCanvas self-hydrates from the
    office read API — LibreOffice headless joins for formula recalc when
    installed). Returns the /canvas/{id} URL, None for non-office files or
    when the caller gave no user_id (created_by must be a real user)."""
    import uuid as _uuid

    ext = (file_name or external_id).rsplit(".", 1)[-1].lower() if "." in (file_name or external_id) else ""
    if ext not in ("xlsx", "docx", "pptx"):
        return None
    if not user_id:
        return None
    try:
        import os as _os

        from core.models import Canvas, CanvasAudit
        from core.database import SessionLocal
        from core.office_sync_service import OFFICE_COMPONENT_MAP

        ext_key = f".{ext}"
        if ext_key not in OFFICE_COMPONENT_MAP:
            return None

        office_dir = _os.getenv("ATOM_OFFICE_DIR", _os.path.join("data", "office"))
        _os.makedirs(office_dir, exist_ok=True)
        slug = (file_name or external_id).rsplit(".", 1)[0][:40].replace("/", "-") or "file"
        file_path = _os.path.join(office_dir, f"jit-{integration_id}-{_uuid.uuid4().hex[:8]}-{slug}{ext_key}")
        with open(file_path, "wb") as f:
            f.write(content)

        _, canvas_type = OFFICE_COMPONENT_MAP[ext_key]
        canvas_id = str(_uuid.uuid4())
        db = SessionLocal()
        try:
            db.add(Canvas(
                id=canvas_id,
                tenant_id="default",
                workspace_id=workspace_id or None,
                created_by=user_id,
                name=file_name or f"{integration_id}:{external_id}",
                canvas_type=canvas_type,
                content={"office_file": file_path, "file_path": file_path, "format": ext},
                status="active",
            ))
            db.add(CanvasAudit(
                canvas_id=canvas_id,
                tenant_id="default",
                agent_id=None,
                canvas_type=canvas_type,
                action_type="create",
                user_id=user_id,
                details_json={
                    "source": "integration_jit",
                    "title": file_name,
                    "integration_id": integration_id,
                    "external_id": external_id,
                },
            ))
            db.commit()
        finally:
            db.close()
        return f"/canvas/{canvas_id}"
    except Exception as canvas_err:
        logger.debug(f"office canvas open skipped: {canvas_err}")
        return None


async def integration_ingest_item(
    integration_id: str,
    external_id: str,
    file_name: str = "",
    workspace_id: str = "default",
    open_as_canvas: bool = False,
    user_id: str = "",
) -> Dict[str, Any]:
    """Just-in-time ingestion of ONE file's contents into memory.

    Guardrails: the connector must have a fetch adapter; the integration's
    selective-ingestion settings must be enabled (when a settings row exists);
    the file must be within the configured size cap (settings value wins over
    the default). Record apps (CRM/Books/Inventory) have no file bytes — their
    index rows already carry the summary fields.
    """
    if not integration_id or not external_id:
        return {"success": False, "error": "integration_id and external_id are required"}

    if integration_id not in STRUCTURE_ADAPTERS:
        return {"success": False, "error": f"Unknown integration '{integration_id}'"}

    ws = workspace_id or "default"
    settings = _settings_for(integration_id, ws)
    if settings is not None and not getattr(settings, "enabled", True):
        return {
            "success": False,
            "error": (
                f"Ingestion for '{integration_id}' is disabled by the user's "
                "selective-ingestion settings — ask them to enable the scopes you need."
            ),
        }

    fetcher = FILE_FETCHERS.get(integration_id)
    if fetcher is None:
        return {
            "success": False,
            "error": (
                f"'{integration_id}' has no file-fetch adapter (record apps serve "
                "their fields from the structure index directly)."
            ),
        }

    # Size guard: cap from the user's settings (tighter wins).
    cap_mb = DEFAULT_MAX_INGEST_MB
    if settings is not None and getattr(settings, "max_file_size_mb", None):
        cap_mb = int(settings.max_file_size_mb)
    cap_bytes = cap_mb * 1024 * 1024

    content = await fetcher(ws if ws else "default", external_id)
    if content is None:
        return {"success": False, "error": "Failed to download file"}
    if len(content) > cap_bytes:
        return {
            "success": False,
            "error": (
                f"File exceeds the {cap_mb}MB ingestion cap configured for "
                f"'{integration_id}' — ingest a smaller item or raise the cap."
            ),
        }

    canvas_url = None
    if open_as_canvas:
        canvas_url = _open_office_canvas(
            integration_id, external_id, file_name, content, ws, user_id
        )

    try:
        from core.auto_document_ingestion import AutoDocumentIngestionService

        result = await AutoDocumentIngestionService(workspace_id=ws).process_file_bytes(
            content,
            file_name=file_name or f"{external_id}",
            source=integration_id,
            user_id="system",
            external_id=external_id,
            extra_metadata={"ingested_via": "agent_jit", "integration_id": integration_id},
        )
        # Shared semantics (core.auto_document_ingestion): unchanged
        # re-ingests are success no-ops; unsupported formats and write
        # failures must reach the agent as failures, not silent skips.
        from core.auto_document_ingestion import interpret_ingest_result
        interpreted = interpret_ingest_result(result)
        out = {
            "success": interpreted["success"],
            "unchanged": interpreted["unchanged"],
            "result": result,
        }
        # Per-app feedback: agent pulls count for the integration too — the
        # card's counts reflect everything that landed, not just panel clicks.
        from core.ingestion_feedback import record_ingestion_feedback

        record_ingestion_feedback(
            None, integration_id,
            1 if result.get("status") in ("ok", "ingested") else 0,
            bool(out["success"]),
            workspace_id=ws,
        )
        if canvas_url:
            out["canvas_url"] = canvas_url
            out["message"] = (
                f"Opened the file as an in-app office canvas: {canvas_url} "
                "(contents were also ingested to memory)."
            )
        return out
    except Exception as ingest_err:
        logger.debug(f"JIT ingest failed for {external_id}: {ingest_err}")
        return {"success": False, "error": f"Ingestion failed: {ingest_err}"}


def register_drive_tools(tool_registry=None):
    """Register the integration-memory tools with the tool registry."""
    from tools.registry import get_tool_registry

    if tool_registry is None:
        tool_registry = get_tool_registry()

    tool_registry.register(
        name="integration_search_index",
        function=integration_search_index,
        version="1.0.0",
        description=(
            "Search the mapped structure index of a user-connected integration "
            "(onedrive, zoho_workdrive, dropbox, google_drive, zoho_crm, "
            "zoho_books, zoho_inventory): find folders, files, leads, deals, "
            "contacts, items by keyword. Returns paths/ids — pair with "
            "integration_ingest_item to read a specific file's contents."
        ),
        category="integrations",
        complexity=1,
        maturity_required="STUDENT",
        parameters={
            "integration_id": "string (required) — e.g. 'onedrive', 'zoho_crm'",
            "query": "string (required) — keywords from the current task/goal",
            "limit": "int (optional, default 8)",
            "workspace_id": "string (optional) — workspace scope",
        },
        tags=["integrations", "drive", "crm", "search", "index", "memory"],
    )

    tool_registry.register(
        name="integration_ingest_item",
        function=integration_ingest_item,
        version="1.0.0",
        description=(
            "Just-in-time ingestion: pull ONE file's contents from a connected "
            "drive into memory so it can be used for the current task. Respects "
            "the user's selective-ingestion settings (enabled scopes + size "
            "cap). Only call this when the task needs the file's contents."
        ),
        category="integrations",
        complexity=2,
        maturity_required="INTERN",
        parameters={
            "integration_id": "string (required) — e.g. 'onedrive', 'zoho_workdrive'",
            "external_id": "string (required) — the file id from integration_search_index",
            "file_name": "string (optional) — helps type detection and provenance",
            "workspace_id": "string (optional) — workspace scope",
            "open_as_canvas": "boolean (optional) — for xlsx/docx/pptx: ALSO open the file as an in-app office canvas and return its /canvas/{id} URL",
            "user_id": "string (optional, required with open_as_canvas) — the owning user",
        },
        tags=["integrations", "drive", "ingest", "just-in-time", "memory", "canvas"],
    )
