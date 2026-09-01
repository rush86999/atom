"""Universal integration memory index — map the territory, ingest on demand.

Core-value-proposition framing: ingestion exists to TRAIN the hire. For file
drives, the index is a kilobyte-scale map (every folder/file: path, size,
modified-at) WITHOUT downloading contents; for record apps (CRM, Books,
Inventory) the index rows ARE the records' summary fields. The agent then
pulls specific files just-in-time per task/goal via the integration tools —
the agentic-RAG "lightweight references + JIT content" pattern, scoped by the
user's selective ingestion settings.

UNIVERSAL by construction: adapters normalize each connector's native listing
into one row shape, and the index writes through the SAME add_document
contract (provenance metadata + top-level freshness columns) as content
ingestion, so hybrid recall, freshness filtering and provenance rendering
treat structure rows exactly like documents. Adding an integration = one
adapter entry; every integration without one degrades gracefully.

Temporal: rows carry source_modified_at as a top-level filterable column —
the existing freshness service covers structure rows (a re-listing that shows
a newer modified_at marks the row stale, mirroring "changed fact = new fact").
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_TEXT_CHARS = 400
MAX_INDEX_ROWS = 5000


def _row_text(integration_id: str, row: Dict[str, Any]) -> str:
    """Embeddable, path/summary-first text so lexical + vector search finds rows."""
    kind = row.get("kind", "file")
    entity = row.get("entity_type") or kind
    where = row.get("path") or ""
    bits = [f"[{integration_id}:{entity}]"]
    if where:
        bits.append(f"{where}/")
    bits.append(str(row.get("name") or ""))
    summary = row.get("summary")
    if summary:
        bits.append(f"— {summary}")
    modified = row.get("modified")
    if modified:
        bits.append(f"(modified {str(modified)[:10]})")
    return " ".join(bits)[:_TEXT_CHARS]


def _to_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Adapters — normalize each connector into list_structure rows
# ---------------------------------------------------------------------------

async def _resolve_token(svc: Any, user_id: str) -> Optional[str]:
    for getter in ("_resolve_token", "get_access_token"):
        fn = getattr(svc, getter, None)
        if fn is None:
            continue
        try:
            import asyncio

            token = fn(None) if getter == "_resolve_token" else await fn(user_id)
            if token:
                return token
        except Exception as token_err:  # noqa: BLE001 — try next getter
            logger.debug(f"{type(svc).__name__}.{getter} failed: {token_err}")
    return None


async def _onedrive_structure(user_id: str) -> List[Dict[str, Any]]:
    from integrations.onedrive_service import OneDriveService

    svc = OneDriveService()
    token = await _resolve_token(svc, user_id)
    if not token:
        return []
    entries = await svc.walk_files(token)
    rows: List[Dict[str, Any]] = []
    for entry in entries:
        is_folder = "folder" in entry
        rows.append(
            {
                "external_id": str(entry.get("id") or ""),
                "kind": "folder" if is_folder else "file",
                "entity_type": "folder" if is_folder else "file",
                "name": entry.get("name"),
                "path": str(entry.get("path") or ""),
                "size": int(entry.get("size") or 0),
                "modified": entry.get("lastModifiedDateTime"),
                "svc": svc,
            }
        )
    return rows


async def _zoho_workdrive_structure(user_id: str) -> List[Dict[str, Any]]:
    from integrations.zoho_workdrive_service import ZohoWorkDriveService

    svc = ZohoWorkDriveService()
    entries = await svc.walk_files(user_id)
    rows: List[Dict[str, Any]] = []
    for entry in entries:
        is_folder = str(entry.get("type") or "") == "folder" or "folder" in entry
        rows.append(
            {
                "external_id": str(entry.get("id") or ""),
                "kind": "folder" if is_folder else "file",
                "entity_type": "folder" if is_folder else "file",
                "name": entry.get("name"),
                "path": str(entry.get("path") or entry.get("folder_path") or ""),
                "size": int(entry.get("size") or 0),
                "modified": entry.get("modified_time") or entry.get("modified_at"),
                "svc": svc,
            }
        )
    return rows


async def _dropbox_structure(user_id: str) -> List[Dict[str, Any]]:
    from integrations.dropbox_service import DropboxService

    svc = DropboxService()
    token = await _resolve_token(svc, user_id)
    entries = await svc.walk_files(access_token=token)
    rows: List[Dict[str, Any]] = []
    for entry in entries:
        full = str(entry.get("path") or "")
        rows.append(
            {
                "external_id": full,
                "kind": "file",
                "entity_type": "file",
                "name": entry.get("name") or full.rsplit("/", 1)[-1],
                "path": str(entry.get("folder_path") or "").rstrip("/"),
                "size": int(entry.get("size") or 0),
                "modified": entry.get("server_modified"),
                "svc": svc,
            }
        )
    return rows


async def _gdrive_structure(user_id: str, max_depth: int = 4) -> List[Dict[str, Any]]:
    """Depth-capped recursive walk via Drive v3 list_files (folder mimeType)."""
    from integrations.google_drive_service import GoogleDriveService

    svc = GoogleDriveService()
    token = await _resolve_token(svc, user_id)
    if not token:
        return []
    rows: List[Dict[str, Any]] = []
    seen: set = set()

    async def _walk(folder_id: Optional[str], path: str, depth: int) -> None:
        if depth > max_depth or folder_id in seen:
            return
        seen.add(folder_id)
        try:
            data = await svc.list_files(token, folder_id=folder_id, page_size=200)
        except Exception as list_err:  # one branch never aborts the map
            logger.debug(f"gdrive list skipped folder {folder_id}: {list_err}")
            return
        for entry in (data or {}).get("files") or []:
            mime = str(entry.get("mimeType") or "")
            is_folder = mime.endswith(".folder")
            row_path = f"{path}/{entry.get('name', '')}".lstrip("/")
            rows.append(
                {
                    "external_id": str(entry.get("id") or ""),
                    "kind": "folder" if is_folder else "file",
                    "entity_type": "folder" if is_folder else "file",
                    "name": entry.get("name"),
                    "path": path,
                    "size": int(entry.get("size") or 0),
                    "modified": entry.get("modifiedTime"),
                    "svc": svc,
                }
            )
            if is_folder:
                await _walk(entry.get("id"), row_path, depth + 1)

    await _walk(None, "", 0)
    return rows


def _record_row(
    integration_id: str, entity_type: str, record: Dict[str, Any], name_keys: List[str]
) -> Dict[str, Any]:
    name = next(
        (str(record.get(k)) for k in name_keys if record.get(k)), "(unnamed)"
    )
    summary_parts = []
    for key in ("account_name", "company", "customer_name", "contact_name",
                "status", "stage", "amount", "total", "rate", "email"):
        if record.get(key):
            summary_parts.append(f"{key.replace('_', ' ')}: {record[key]}")
    rid = str(
        record.get("id") or record.get("record_id") or record.get("contact_id") or ""
    )
    return {
        "external_id": rid,
        "kind": "record",
        "entity_type": entity_type,
        "name": name,
        "path": integration_id,
        "size": 0,
        "modified": record.get("modified_time")
        or record.get("last_activity_time")
        or record.get("created_time"),
        "summary": ", ".join(str(p) for p in summary_parts[:4]),
        "fields": {
            k: record.get(k)
            for k in ("amount", "total", "status", "stage", "email", "account_name")
            if record.get(k) is not None
        },
    }


async def _zoho_crm_structure(user_id: str) -> List[Dict[str, Any]]:
    from integrations.zoho_crm_service import ZohoCRMService

    svc = ZohoCRMService()
    rows: List[Dict[str, Any]] = []
    leads = await svc.get_leads(limit=500) or []
    for record in leads:
        rows.append(_record_row("zoho_crm", "lead", record, ["Full_Name", "Last_Name", "Email"]))
    deals = await svc.get_deals() or []
    for record in deals:
        rows.append(_record_row("zoho_crm", "deal", record, ["Deal_Name", "Account_Name"]))
    return rows


async def _zoho_books_structure(user_id: str) -> List[Dict[str, Any]]:
    from integrations.zoho_books_service import ZohoBooksService

    svc = ZohoBooksService()
    token = await _resolve_token(svc, user_id)
    if not token:
        return []
    try:
        orgs = await svc.get_organizations(token)
        organization_id = str((orgs[0] or {}).get("organization_id") or "") if orgs else ""
    except Exception as org_err:
        logger.debug(f"zoho books org resolve failed: {org_err}")
        organization_id = ""
    rows: List[Dict[str, Any]] = []
    try:
        for record in await svc.get_contacts(token, organization_id) or []:
            rows.append(_record_row("zoho_books", "contact", record, ["contact_name", "email"]))
    except Exception as e:
        logger.debug(f"zoho books contacts skipped: {e}")
    try:
        for record in await svc.get_bank_transactions(token, organization_id, "") or []:
            rows.append(
                _record_row("zoho_books", "bank_transaction", record, ["description", "reference_number"])
            )
    except Exception as e:
        logger.debug(f"zoho books transactions skipped: {e}")
    return rows


async def _zoho_inventory_structure(user_id: str) -> List[Dict[str, Any]]:
    from integrations.zoho_inventory_service import ZohoInventoryService

    svc = ZohoInventoryService()
    rows: List[Dict[str, Any]] = []
    try:
        for record in await svc.get_items() or []:
            rows.append(_record_row("zoho_inventory", "item", record, ["name", "sku", "description"]))
    except Exception as e:
        logger.debug(f"zoho inventory items skipped: {e}")
    return rows


# integration_id -> async structure adapter
STRUCTURE_ADAPTERS: Dict[str, Callable[[str], Any]] = {
    "onedrive": _onedrive_structure,
    "zoho_workdrive": _zoho_workdrive_structure,
    "dropbox": _dropbox_structure,
    "google_drive": _gdrive_structure,
    "zoho_crm": _zoho_crm_structure,
    "zoho_books": _zoho_books_structure,
    "zoho_inventory": _zoho_inventory_structure,
}

FILE_FETCHERS: Dict[str, Callable[[str, str], Any]] = {}


async def _onedrive_fetch(user_id: str, external_id: str) -> Optional[bytes]:
    from integrations.onedrive_service import OneDriveService

    svc = OneDriveService()
    token = await _resolve_token(svc, user_id)
    if not token:
        return None
    return await svc._download_file_bytes(token, external_id)


async def _zoho_workdrive_fetch(user_id: str, external_id: str) -> Optional[bytes]:
    from integrations.zoho_workdrive_service import ZohoWorkDriveService

    svc = ZohoWorkDriveService()
    return await svc.download_file(user_id, external_id)


async def _dropbox_fetch(user_id: str, external_id: str) -> Optional[bytes]:
    from integrations.dropbox_service import DropboxService

    svc = DropboxService()
    token = await _resolve_token(svc, user_id)
    return await svc.download_file(external_id, token)


FILE_FETCHERS.update(
    {
        "onedrive": _onedrive_fetch,
        "zoho_workdrive": _zoho_workdrive_fetch,
        "dropbox": _dropbox_fetch,
    }
)


def available_integrations() -> List[str]:
    return sorted(STRUCTURE_ADAPTERS.keys())


class IntegrationMemoryIndexer:
    """Ingest an integration's LISTING structure into the documents table."""

    def __init__(self, workspace_id: str = "default"):
        self.workspace_id = (workspace_id or "default").strip() or "default"

    def _handler(self):
        from core.lancedb_handler import get_lancedb_handler

        return get_lancedb_handler(self.workspace_id)

    async def index_structure(
        self,
        integration_id: str,
        user_id: str,
        max_rows: int = MAX_INDEX_ROWS,
    ) -> Dict[str, Any]:
        adapter = STRUCTURE_ADAPTERS.get(integration_id)
        if adapter is None:
            return {
                "success": False,
                "error": (
                    f"No structure adapter for '{integration_id}'. "
                    f"Available: {', '.join(available_integrations())}"
                ),
            }
        try:
            rows = await adapter(user_id)
        except Exception as walk_err:
            logger.warning(f"structure walk failed for {integration_id}: {walk_err}")
            return {"success": False, "error": f"Listing failed: {walk_err}"}

        handler = self._handler()
        if handler is None:
            return {"success": False, "error": "Memory handler unavailable"}

        now_iso = datetime.now(timezone.utc).isoformat()
        counts: Dict[str, int] = {}
        written = 0
        for row in rows[:max_rows]:
            name = str(row.get("name") or "").strip()
            if not name:
                continue
            kind = str(row.get("kind") or "file")
            counts[kind] = counts.get(kind, 0) + 1
            external_id = str(row.get("external_id") or "")
            doc_id = f"idx_{integration_id}_{external_id}"[:200]
            modified = _to_datetime(row.get("modified"))
            path = str(row.get("path") or "")
            try:
                success = await handler.add_document(
                    table_name="documents",
                    text=_row_text(integration_id, row),
                    source=f"{integration_id}-index:{path}/{name}",
                    metadata={
                        "file_name": name,
                        "file_path": path,
                        "integration_id": integration_id,
                        "external_id": external_id,
                        "ingested_at": now_iso,
                        "source_url": f"{integration_id}:{path}/{name}",
                        "source_type": "integration_index",
                        "index_kind": kind,
                        "index_entity": row.get("entity_type"),
                        "index_summary": row.get("summary"),
                        "pg_document_id": doc_id,
                    },
                    user_id="system",
                    doc_id=doc_id,
                    extra_columns={
                        "freshness_status": "fresh",
                        "source_modified_at": modified,
                        "source_url": f"{integration_id}:{path}/{name}",
                    },
                )
                if success:
                    written += 1
            except Exception as row_err:  # one bad row never aborts the map
                logger.debug(f"index row skipped ({name}): {row_err}")

        return {
            "success": True,
            "integration_id": integration_id,
            "rows_found": len(rows),
            "rows_written": written,
            "counts": counts,
            "truncated": len(rows) > max_rows,
            "ingested_at": now_iso,
        }

    async def list_structure(
        self, integration_id: str, user_id: str
    ) -> Dict[str, Any]:
        """Raw normalized listing (for the selective-ingestion picker)."""
        adapter = STRUCTURE_ADAPTERS.get(integration_id)
        if adapter is None:
            return {
                "success": False,
                "error": f"No structure adapter for '{integration_id}'",
            }
        try:
            rows = await adapter(user_id)
        except Exception as walk_err:
            return {"success": False, "error": f"Listing failed: {walk_err}"}
        slim = [
            {
                "external_id": r.get("external_id"),
                "kind": r.get("kind"),
                "entity_type": r.get("entity_type"),
                "name": r.get("name"),
                "path": r.get("path"),
                "size": r.get("size"),
                "modified": str(r.get("modified") or ""),
            }
            for r in rows[:2000]
        ]
        return {"success": True, "rows": slim, "available": available_integrations()}


# Back-compat alias (the original name of this module's service)
DriveTreeIngestionService = IntegrationMemoryIndexer
