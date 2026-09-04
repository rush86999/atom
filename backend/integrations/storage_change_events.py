"""Vendor-neutral storage change events → ingestion refresh.

Every storage connector plugs into this with two small pieces:

  1. an EVENT PARSER — turns that vendor's webhook payload into a normal
     form: {"file_ids": [...]} when the push identifies the changed files,
     or {"resync": True} when the vendor only pings (then the connector's
     own bulk walk handles discovery);
  2. an entry in PROVIDER_SPECS — how to ingest one file, and how to run a
     bulk resync, for that provider.

The funnel (process_file_bytes) does everything else: identity, hash-dedup,
family replacement, freshness stamping. Adding a business's storage app =
one parser + one spec row + its connector's existing ingest methods. No
per-business code anywhere.

Design context: SpreadsheetLLM (arXiv:2407.09025) / TableRAG
(arXiv:2410.04739) for the extraction format; push-vs-pull freshness is the
standard webhook contract used by Google Drive (channel notifications),
Microsoft Graph subscriptions, Dropbox (delta ping) and Box (event streams).
"""
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STORAGE_PROVIDERS = (
    "zoho_workdrive", "google_drive", "onedrive", "dropbox", "box",
)


# ---------------------------------------------------------------------------
# Event parsers (vendor payload -> canonical form)
# ---------------------------------------------------------------------------

def _zoho_id_shape(v: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9]{16,64}$", v or ""))


def _collect_ids(node: Any, found: List[str], depth: int = 0) -> None:
    if len(found) >= 10 or depth > 3:
        return
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, str) and _zoho_id_shape(v) and k.lower().endswith("id"):
                if v not in found:
                    found.append(v)
            else:
                _collect_ids(v, found, depth + 1)
    elif isinstance(node, list):
        for item in node[:20]:
            _collect_ids(item, found, depth + 1)


def parse_workdrive_event(payload: Any, headers: Dict[str, str]) -> Dict[str, Any]:
    file_ids: List[str] = []
    if isinstance(payload, dict) and payload.get("file_ids"):
        return {"file_ids": [str(x) for x in payload["file_ids"] if x]}
    _collect_ids(payload, file_ids)
    return {"file_ids": file_ids} if file_ids else {}


def parse_onedrive_event(payload: Any, headers: Dict[str, str]) -> Dict[str, Any]:
    """Microsoft Graph change notification: value[].resourceData.id is the
    driveItem id."""
    file_ids: List[str] = []
    if isinstance(payload, dict):
        for note in payload.get("value") or []:
            rd = (note.get("resourceData") or {}) if isinstance(note, dict) else {}
            item_id = rd.get("id")
            if item_id and _zoho_id_shape(item_id) is not None and len(str(item_id)) > 8:
                if str(item_id) not in file_ids:
                    file_ids.append(str(item_id))
    return {"file_ids": file_ids} if file_ids else {}


def parse_box_event(payload: Any, headers: Dict[str, str]) -> Dict[str, Any]:
    """Box events webhook: array of {trigger, source:{id,type}} — files only
    (folders → resync)."""
    events = payload if isinstance(payload, list) else (
        payload.get("batch") or [payload] if isinstance(payload, dict) else []
    )
    file_ids: List[str] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        src = ev.get("source") or {}
        if isinstance(src, dict) and str(src.get("type") or "file") == "file":
            fid = src.get("id")
            if fid and str(fid) not in file_ids:
                file_ids.append(str(fid))
    return {"file_ids": file_ids} if file_ids else {}


def parse_resync_event(payload: Any, headers: Dict[str, str]) -> Dict[str, Any]:
    """Google Drive push channels and Dropbox webhooks only PING (no file
    ids in the body) — the vendor contract is 'something changed, re-check'
    and the connector's bulk walk does the discovery."""
    return {"resync": True}


EVENT_ADAPTERS = {
    "zoho_workdrive": parse_workdrive_event,
    "onedrive": parse_onedrive_event,
    "box": parse_box_event,
    "google_drive": parse_resync_event,
    "dropbox": parse_resync_event,
}


def parse_storage_event(provider: str, payload: Any, headers: Dict[str, str]) -> Dict[str, Any]:
    adapter = EVENT_ADAPTERS.get(provider)
    if adapter is None:
        return {}
    try:
        return adapter(payload, headers) or {}
    except Exception as e:  # noqa: BLE001 — webhook handlers must 2xx
        logger.warning(f"storage event parse failed ({provider}): {e}")
        return {}


# ---------------------------------------------------------------------------
# Refresh executor (canonical form -> connector ingest calls)
# ---------------------------------------------------------------------------

async def _connected_user_ids_for_provider(provider: str) -> List[str]:
    """Users with an active token for this provider. Only Zoho scopes tokens
    per user; the registry-managed connectors are tenant-level."""
    if provider != "zoho_workdrive":
        return []
    from core.database import SessionLocal
    from core.models import IntegrationToken

    db = SessionLocal()
    try:
        rows = (
            db.query(IntegrationToken.user_id)
            .filter(
                IntegrationToken.provider.in_(("zoho_workdrive", "zoho")),
                IntegrationToken.status == "active",
            )
            .distinct()
            .all()
        )
        return [r[0] for r in rows if r[0]]
    finally:
        db.close()


async def queue_provider_refresh(
    provider: str, event: Dict[str, Any], user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Execute the refresh described by a parsed event. Returns a summary for
    the webhook response/logs; failures are per-file best-effort (a push must
    never 500 its vendor). All vendor differences live in _execute_storage's
    action branches — this function is provider-agnostic."""
    from integrations.universal_integration_service import UniversalIntegrationService

    if provider not in STORAGE_PROVIDERS:
        return {"success": False, "error": f"unknown storage provider {provider}"}

    executor = UniversalIntegrationService(workspace_id="default")
    context = {"tenant_id": "default", "user_id": user_id}
    refreshed = 0
    errors: List[str] = []

    file_ids = event.get("file_ids") or []
    if file_ids:
        users = await _connected_user_ids_for_provider(provider) or (
            [user_id] if user_id else [None]
        )
        for uid in users:
            for fid in file_ids:
                try:
                    res = await executor.execute(
                        provider, "ingest_file_to_memory",
                        {"query": fid, "file_id": fid},
                        {**context, "user_id": uid} if uid else context,
                    )
                    if isinstance(res, dict) and res.get("status") == "success":
                        refreshed += 1
                    else:
                        errors.append(f"{fid}: {str((res or {}).get('error') or (res or {}).get('message') or 'failed')[:120]}")
                except Exception as e:  # noqa: BLE001 — per-file best-effort
                    errors.append(f"{fid}: {e}")
    elif event.get("resync"):
        try:
            res = await executor.execute(provider, "full_sync", {}, context)
            if isinstance(res, dict) and res.get("status") == "success":
                refreshed += 1
            else:
                errors.append(str((res or {}).get("error") or (res or {}).get("message") or "resync failed")[:160])
        except Exception as e:  # noqa: BLE001
            errors.append(f"resync: {e}")
    else:
        return {"success": True, "refreshed": 0, "message": "event carried no recognizable change"}

    return {
        "success": True,
        "provider": provider,
        "refreshed": refreshed,
        "errors": errors[:5],
    }
