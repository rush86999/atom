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

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_TEXT_CHARS = 400
MAX_INDEX_ROWS = 5000


async def _write_document(handler: Any, **kwargs: Any) -> bool:
    """Write one document through whichever ``add_document`` the handler has.

    The production ``LanceDBHandler.add_document`` is SYNC — the bare ``await``
    this replaces raised TypeError on every row and the per-row guard swallowed
    it, so the structure index silently wrote NOTHING while the async mock in
    tests hid it. Test/alternate handlers may still be async, so accept both.
    """
    fn = getattr(handler, "add_document")
    if asyncio.iscoroutinefunction(fn):
        return bool(await fn(**kwargs))
    return bool(await asyncio.to_thread(fn, **kwargs))

# On-demand ("the agent needs THIS now") content pull. Families decide the
# strategy; the strategies are the repo's existing general layers, never a
# per-integration special case.
MAILBOX_INTEGRATIONS: Tuple[str, ...] = ("outlook", "gmail")
STORAGE_INTEGRATIONS: Tuple[str, ...] = (
    "google_drive", "dropbox", "onedrive", "box", "zoho_workdrive", "notion",
)
DEFAULT_MAX_ONDEMAND_ITEMS = 3


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
                # add_document is SYNC in production (see _write_document) —
                # the old bare `await` dropped every row silently.
                success = await _write_document(
                    handler,
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


# ===========================================================================
# General on-demand ingestion — ANY connected integration, not just drives
# ===========================================================================
#
# "Ingest if not already in memory, directly from the integration" must not be
# a mailbox special case: the same ask applies to a CRM lead, an inventory
# item, a support ticket, a Slack thread. The strategy is chosen by what the
# integration can actually serve, always through an EXISTING general layer:
#
#   mailbox (outlook/gmail) → CommunicationIngestionPipeline.ingest_email_on_demand
#                             (body + attachments, images OCR'd)
#   storage                 → UniversalIntegrationService `read` (download →
#                             extract → best-effort ingest under the file's
#                             stable identity; already the find→open→read leg)
#   anything else           → live UniversalIntegrationService search → render
#                             the matching record(s) to text → documents store
#
# Idempotency is one mechanism for every family: the record/file identity is
# hashed into the standalone `ext_sha1(source:external_id)` doc id that
# AutoDocumentIngestionService.ingested_external_ids already probes, so a
# repeat ask reports already_ingested instead of writing a duplicate row.


def _item_external_id(record: Dict[str, Any]) -> str:
    """Best source-native id for a live record (shape varies per service)."""
    for key in ("id", "Id", "ID", "record_id", "file_id", "fileId",
                "message_id", "messageId", "conversation_id", "key", "uid",
                "number"):
        value = record.get(key)
        if value not in (None, "", [], {}):
            return str(value)
    return ""


def _record_display_name(record: Dict[str, Any]) -> str:
    for key in ("name", "title", "subject", "deal_name", "Deal_Name",
                "full_name", "Full_Name", "display_name", "description"):
        value = record.get(key)
        if value not in (None, "", [], {}):
            return str(value)[:200]
    return "(unnamed)"


def _extract_records(payload: Any) -> List[Dict[str, Any]]:
    """Normalize the many live-search response shapes to a record list.

    UIS search/search-helpers return either a bare list or
    ``{"status", "data": <list | {"data"/"value"/"entries"/…: <list>}>}`` —
    all of them are accepted here so the ingest leg works for every service
    without a per-service branch.
    """
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    data = payload.get("data", payload)
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for key in ("data", "records", "items", "results", "value", "entries",
                    "messages", "rows", "issues", "tickets"):
            inner = data.get(key)
            if isinstance(inner, list):
                return [r for r in inner if isinstance(r, dict)]
        return [data] if data else []
    return []


def render_integration_record(
    integration_id: str, record: Dict[str, Any], entity_type: str = ""
) -> str:
    """Flatten ONE integration record to the text that goes to memory.

    Generic by design: services disagree on field names, so every scalar field
    is rendered as ``key: value`` and nested containers are JSON-compacted.
    Bounded so one pathological record cannot bloat the embedding.
    """
    label = entity_type or str(record.get("entity_type") or "record")
    name = _record_display_name(record)
    lines = [f"[{integration_id}:{label}] {name}"]
    for key, value in record.items():
        if key in ("id", "Id", "ID"):
            continue
        if isinstance(value, (dict, list)):
            try:
                value = json.dumps(value, default=str)
            except Exception:  # noqa: BLE001 — render whatever we can
                value = str(value)
        text = str(value).strip()
        if not text or text in ("None", "{}", "[]"):
            continue
        lines.append(f"{key}: {text[:400]}")
    return "\n".join(lines)[:8000]


def _record_doc_id(integration_id: str, external_id: str) -> str:
    """Same identity scheme as file ingestion, so ONE probe covers both."""
    digest = hashlib.sha1(f"{integration_id}:{external_id}".encode("utf-8")).hexdigest()
    return f"ext_{digest[:24]}"


def _integration_settings(integration_id: str, workspace_id: str) -> Any:
    """The user's selective-ingestion row (None when unset)."""
    try:
        from core.auto_document_ingestion import AutoDocumentIngestionService

        return AutoDocumentIngestionService(
            workspace_id=workspace_id
        ).get_settings(integration_id)
    except Exception as settings_err:  # noqa: BLE001 — gate is best-effort
        logger.debug(f"ingestion settings unavailable for {integration_id}: {settings_err}")
        return None


async def _live_search_records(
    integration_id: str,
    query: str,
    entity_type: str,
    context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """One live search through the universal layer (never raises)."""
    if not query:
        return []
    try:
        from integrations.universal_integration_service import (
            UniversalIntegrationService,
        )

        result = await UniversalIntegrationService().search(
            integration_id, query, entity_type or None, context=context
        )
    except Exception as search_err:  # noqa: BLE001 — reported as an empty search
        logger.warning(f"on-demand ingest search failed ({integration_id}): {search_err}")
        return []
    return _extract_records(result)


def _resolve_item_ids(
    records: List[Dict[str, Any]], external_id: str, limit: int
) -> List[str]:
    ids: List[str] = []
    if external_id:
        ids.append(external_id)
    for record in records:
        rid = _item_external_id(record)
        if rid and rid not in ids:
            ids.append(rid)
        if len(ids) >= limit:
            break
    return ids[:limit]


def _family_result(
    integration_id: str, strategy: str, items: List[Dict[str, Any]], error: str = ""
) -> Dict[str, Any]:
    ingested = sum(1 for i in items if i.get("status") == "ingested")
    already = sum(1 for i in items if i.get("status") == "already_ingested")
    skipped = len(items) - ingested - already
    if ingested:
        message = f"Ingested {ingested} item(s) from {integration_id} into memory"
    elif already:
        message = (
            f"{already} {integration_id} item(s) were already in memory — nothing to do"
        )
    elif error:
        message = error
    else:
        message = f"No {integration_id} content could be added to memory"
    return {
        "success": bool(ingested or already),
        "integration_id": integration_id,
        "strategy": strategy,
        "items": items,
        "ingested": ingested,
        "already_ingested": already,
        "skipped": skipped,
        "message": message,
        **({"error": error} if error and not (ingested or already) else {}),
    }


async def _ingest_records_into_memory(
    integration_id: str,
    user_id: str,
    records: List[Dict[str, Any]],
    *,
    entity_type: str,
    workspace_id: str,
    max_items: int,
) -> Dict[str, Any]:
    """Records (CRM/PM/support/finance/…) → documents, idempotently.

    Record apps have no file bytes; their CONTENT is the record itself. We
    render the live record to text and write it under the same ``ext_``
    identity the file path uses, so `ingested_external_ids` answers "already
    in memory?" for both kinds with one probe.
    """
    from core.auto_document_ingestion import AutoDocumentIngestionService
    from core.lancedb_handler import get_lancedb_handler

    candidates: List[Tuple[str, Dict[str, Any]]] = []
    for record in records:
        rid = _item_external_id(record)
        if not rid:
            continue
        candidates.append((rid, record))
        if len(candidates) >= max(1, int(max_items)):
            break
    if not candidates:
        return _family_result(integration_id, "records", [])

    already: set = set()
    try:
        service = AutoDocumentIngestionService(workspace_id=workspace_id)
        already = set(
            await service.ingested_external_ids(
                integration_id, [rid for rid, _ in candidates]
            )
            or []
        )
    except Exception as probe_err:  # noqa: BLE001 — probe is an optimization
        logger.debug(f"record already-ingested probe skipped: {probe_err}")

    handler = get_lancedb_handler(workspace_id)
    items: List[Dict[str, Any]] = []
    for rid, record in candidates:
        doc_id = _record_doc_id(integration_id, rid)
        if rid in already:
            items.append(
                {"external_id": rid, "status": "already_ingested", "doc_id": doc_id}
            )
            continue
        text = render_integration_record(integration_id, record, entity_type)
        if not text.strip():
            items.append(
                {"external_id": rid, "status": "skipped", "reason": "empty_record"}
            )
            continue
        label = entity_type or str(record.get("entity_type") or "record")
        name = _record_display_name(record)
        try:
            # add_document is SYNC — see _write_document.
            written = await _write_document(
                handler,
                table_name="documents",
                text=text,
                source=f"{integration_id}:{label}:{name}",
                metadata={
                    "source_type": "integration_record",
                    "integration_id": integration_id,
                    "external_id": rid,
                    "entity_type": label,
                    "record_name": name,
                    "ingested_via": "agent_on_demand",
                },
                user_id=user_id or "system",
                doc_id=doc_id,
                extra_columns={
                    "freshness_status": "fresh",
                    "source_url": f"{integration_id}:{rid}",
                },
            )
        except Exception as write_err:  # noqa: BLE001 — reported per item
            logger.warning(f"record ingest failed ({integration_id}:{rid}): {write_err}")
            written = False
        if written:
            items.append(
                {
                    "external_id": rid,
                    "status": "ingested",
                    "doc_id": doc_id,
                    "name": name,
                    "chars": len(text),
                }
            )
        else:
            items.append(
                {
                    "external_id": rid,
                    "status": "error",
                    "reason": "write_failed",
                    "doc_id": None,
                }
            )
    return _family_result(integration_id, "records", items)


async def _ingest_mailbox_items(
    integration_id: str,
    user_id: str,
    *,
    query: str,
    external_id: str,
    max_items: int,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Mailbox: full message (body + attachments, images OCR'd) → memory."""
    from integrations.atom_communication_ingestion_pipeline import (
        ingestion_pipeline,
    )

    records = (
        await _live_search_records(integration_id, query, "", context)
        if query and not external_id
        else []
    )
    ids = _resolve_item_ids(records, external_id, max(1, int(max_items)))
    if not ids:
        return _family_result(
            integration_id, "mailbox", [],
            error=f"no matching {integration_id} message found to ingest",
        )

    items: List[Dict[str, Any]] = []
    for message_id in ids:
        try:
            result = await ingestion_pipeline.ingest_email_on_demand(
                integration_id, user_id, message_id
            )
        except Exception as ingest_err:  # noqa: BLE001 — reported per item
            result = {"status": "error", "reason": str(ingest_err)[:200]}
        status = (result or {}).get("status")
        if status == "ingested":
            items.append(
                {
                    "external_id": message_id,
                    "status": "ingested",
                    "subject": result.get("subject") or "",
                    "attachments": result.get("attachments") or 0,
                }
            )
        elif status == "already_ingested":
            items.append({"external_id": message_id, "status": "already_ingested"})
        else:
            items.append(
                {
                    "external_id": message_id,
                    "status": "error",
                    "reason": result.get("reason") or status or "ingest_failed",
                }
            )
    return _family_result(integration_id, "mailbox", items)


async def _ingest_storage_items(
    integration_id: str,
    *,
    query: str,
    external_id: str,
    max_items: int,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Storage: file bytes → extract → ingest, via the shared `read` leg.

    ``_read_storage_file`` already downloads, extracts and best-effort ingests
    under the file's stable identity — reusing it keeps ONE implementation of
    find→open→read for every storage provider.
    """
    from integrations.universal_integration_service import (
        UniversalIntegrationService,
    )

    records = (
        await _live_search_records(integration_id, query, "", context)
        if query and not external_id
        else []
    )
    file_ids = _resolve_item_ids(records, external_id, max(1, int(max_items)))
    if not file_ids:
        return _family_result(
            integration_id, "storage", [],
            error=f"no matching {integration_id} file found to ingest",
        )

    uis = UniversalIntegrationService()
    items: List[Dict[str, Any]] = []
    for file_id in file_ids:
        try:
            result = await uis.execute(
                integration_id, "read",
                {"file_id": file_id, "query": query}, context,
            )
        except Exception as read_err:  # noqa: BLE001 — reported per item
            result = {"status": "error", "error": str(read_err)[:200]}
        data = (result or {}).get("data") or {}
        if (result or {}).get("status") == "success" and data.get("found"):
            if data.get("ingested_into_workspace"):
                status = "ingested"
            else:
                # Opened but the index write did not land (unsupported format,
                # no text layer) — say so instead of claiming memory.
                status = "skipped"
            items.append(
                {
                    "external_id": file_id,
                    "status": status,
                    "file_name": data.get("file_name"),
                    "doc_id": data.get("doc_id") or file_id,
                    "chars": data.get("chars_extracted") or 0,
                    **({"reason": "not_indexed"} if status == "skipped" else {}),
                }
            )
        else:
            items.append(
                {
                    "external_id": file_id,
                    "status": "error",
                    "reason": (result or {}).get("error")
                    or (result or {}).get("message")
                    or "read_failed",
                }
            )
    return _family_result(integration_id, "storage", items)


async def ingest_integration_content(
    integration_id: str,
    user_id: str,
    *,
    query: str = "",
    external_id: str = "",
    entity_type: str = "",
    workspace_id: str = "default",
    max_items: int = DEFAULT_MAX_ONDEMAND_ITEMS,
    agent_id: str = "",
) -> Dict[str, Any]:
    """On-demand: pull THIS integration's content into memory, if absent.

    The general form of "ingest from the integration": one entry point for
    every connected service. Family strategies live above; the identity and
    idempotency contract is shared with the file path (``ext_`` doc ids probed
    by ``ingested_external_ids``), so a repeated ask is a truthful no-op.

    Args:
        integration_id: Connected service, e.g. ``zoho_crm``, ``google_drive``,
            ``outlook``.
        user_id: Owning user (provider auth is scoped to them).
        query: What to ingest (sender/subject/keywords, file name, model code).
        external_id: Exact source-native id when the caller has one; skips the
            live search entirely.
        entity_type: Optional narrowing for record services.
        max_items: Cap on items pulled per call.
        workspace_id: Memory workspace.

    Returns:
        ``{"success", "integration_id", "strategy", "items", "ingested",
        "already_ingested", "skipped", "message"}``. Never raises.
    """
    integration_id = (integration_id or "").strip()
    user_id = str(user_id or "")
    query = (query or "").strip()
    external_id = str(external_id or "").strip()
    ws = workspace_id or "default"

    if not integration_id:
        return _family_result("", "", [], error="integration_id is required")
    if not query and not external_id:
        return _family_result(
            integration_id, "", [], error="query or external_id is required"
        )

    # The user's selective-ingestion lever gates agent-initiated pulls for
    # EVERY family — one knob, one place (mirrors the file-tool gate).
    settings = _integration_settings(integration_id, ws)
    if settings is not None and not getattr(settings, "enabled", True):
        return _family_result(
            integration_id, "", [],
            error=(
                f"Ingestion for '{integration_id}' is disabled by the user's "
                "selective-ingestion settings — ask them to enable the scopes you need."
            ),
        )

    context = {"user_id": user_id, "workspace_id": ws, "agent_id": agent_id}
    limit = max(1, int(max_items))

    if integration_id in MAILBOX_INTEGRATIONS:
        return await _ingest_mailbox_items(
            integration_id, user_id, query=query, external_id=external_id,
            max_items=limit, context=context,
        )
    if integration_id in STORAGE_INTEGRATIONS:
        return await _ingest_storage_items(
            integration_id, query=query, external_id=external_id,
            max_items=limit, context=context,
        )

    records = await _live_search_records(integration_id, query, entity_type, context)
    if not records and not external_id:
        return _family_result(
            integration_id, "records", [],
            error=f"no matching {integration_id} content found to ingest",
        )
    return await _ingest_records_into_memory(
        integration_id, user_id, records,
        entity_type=entity_type, workspace_id=ws, max_items=limit,
    )
