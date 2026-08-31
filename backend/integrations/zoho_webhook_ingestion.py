"""Shared ingestion for webhook-push Zoho apps (Forms, Flow).

Zoho Forms and Zoho Flow have NO public read API — Zoho's official position
on Forms is "we do not support the API in Zoho Forms" (help.zoho.com
community, "Zoho Forms API" / "Accessing Zoho form entries via API"), and
no `ZohoForms.*` OAuth scope works (`ZohoForms.forms.ALL` returns a
permissions error; a fabricated scope would fail the whole suite consent
URL). Flow likewise exposes flows/executions only through its UI. Both
products CAN push events over webhooks, so these apps ingest push-only:

    Zoho Forms  →  POST /api/v1/integrations/zoho-forms/webhook
    Zoho Flow   →  POST /webhooks/zoho-flow   (api/webhook_routes.py)

Records land in the same per-integration LanceDB tables the hybrid sync
writes (`integration_zoho_forms`, `integration_zoho_flow`), so the memory
assembler's integration-records leg recalls them in chat exactly like
synced data, and each push fires the AI trigger coordinator.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Keys every normalizer understands as identity/metadata rather than
# user-entered form/flow fields.
_META_KEYS = {
    "id", "record_id", "entry_id", "EntryId", "type", "module",
    "name", "subject", "title", "form_name", "formName", "Form",
    "description", "summary", "status", "amount", "company", "email",
    "modified_time", "modified_at", "submitted_at", "timestamp",
    "Added_Time", "Modified_Time", "source",
}

_TRIGGER_CAP = 10  # max trigger-coordinator fan-out per push (matches zoho-flow)
_MAX_TEXT_CHARS = 4000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scalar(value: Any) -> Optional[str]:
    """Render a field value for the searchable text; None filters it out."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        import json

        try:
            rendered = json.dumps(value, default=str)
        except Exception:
            rendered = str(value)
        return rendered if rendered not in ("{}", "[]") else None
    text = str(value).strip()
    return text or None


def normalize_record(
    raw: Dict[str, Any],
    *,
    integration_id: str,
    default_type: str,
) -> Tuple[Dict[str, Any], str]:
    """Flatten one pushed payload into (normalized_record, searchable_text).

    Tolerates the loose shapes these products actually send: form submissions
    arrive as arbitrary field-label → value maps, flow events as module-ish
    records. Unknown keys are flattened into the text so retrieval matches
    substance even for fields we did not model.
    """
    rid = str(
        raw.get("id")
        or raw.get("record_id")
        or raw.get("entry_id")
        or raw.get("EntryId")
        or uuid.uuid4()
    )
    rtype = str(raw.get("type") or raw.get("module") or default_type)
    form_or_flow = (
        raw.get("form_name")
        or raw.get("formName")
        or raw.get("Form")
        or raw.get("flow_name")
        or raw.get("flow")
    )
    name = raw.get("name") or raw.get("subject") or raw.get("title") or form_or_flow or rtype
    modified_at = (
        raw.get("submitted_at")
        or raw.get("modified_time")
        or raw.get("modified_at")
        or raw.get("Modified_Time")
        or raw.get("Added_Time")
        or raw.get("timestamp")
    )

    record = {
        "id": rid,
        "type": rtype,
        "name": name,
        "modified_at": modified_at,
    }
    if form_or_flow:
        record["form_name" if integration_id == "zoho_forms" else "flow_name"] = form_or_flow

    label = "form submission" if integration_id == "zoho_forms" else "event"
    header = (
        f"{label} from {integration_id}"
        if rtype == default_type
        else f"{rtype.replace('_', ' ').title()} {label} from {integration_id}"
    )
    parts = [header, f"name: {name}"]
    if form_or_flow:
        parts.append(f"{'form' if integration_id == 'zoho_forms' else 'flow'}: {form_or_flow}")
    for key in ("description", "summary", "status", "amount", "company", "email"):
        rendered = _scalar(raw.get(key))
        if rendered:
            parts.append(f"{key}: {rendered}")
            record.setdefault(key, rendered)
    for key, value in raw.items():
        if key in _META_KEYS or key.startswith("_"):
            continue
        rendered = _scalar(value)
        if rendered:
            parts.append(f"{key}: {rendered}")

    text = "\n".join(parts)[:_MAX_TEXT_CHARS]
    return record, text


async def ingest_records(
    handler: Any,
    records: List[Dict[str, Any]],
    *,
    integration_id: str,
    workspace_id: str = "default",
    role: Optional[str] = None,
    default_type: str = "event",
) -> Dict[str, Any]:
    """Upsert pushed records into ``integration_{integration_id}`` and fire
    the AI trigger coordinator. Mirrors the /webhooks/zoho-flow handler
    contract: returns {"received", "ingested", "skipped_unchanged",
    "triggers_fired"}; never raises."""
    from core.vector_upsert import upsert_document

    received = len(records)
    ingested = 0
    skipped = 0
    trigger_payloads: List[Dict[str, Any]] = []
    now = _now_iso()

    for rec in records:
        if not isinstance(rec, dict):
            continue
        record, text = normalize_record(rec, integration_id=integration_id, default_type=default_type)
        rid = record["id"]
        rtype = record["type"]

        try:
            from core.data_taint_tracker import classify_sensitivity

            sensitivity = classify_sensitivity(text)
        except Exception:
            sensitivity = "internal"

        meta: Dict[str, Any] = {
            "integration_id": integration_id,
            "record_id": rid,
            "record_type": rtype,
            "sensitivity": sensitivity,
            "synced_at": now,
            "source_modified_at": record.get("modified_at"),
            "last_verified_at": now,
            "freshness_status": "fresh",
        }
        if record.get("form_name") or record.get("flow_name"):
            meta["form_name"] = record.get("form_name") or record.get("flow_name")
        if role:
            meta["role"] = role

        status = "write_failed"
        if handler is not None:
            try:
                status = await upsert_document(
                    handler,
                    table_name=f"integration_{integration_id}",
                    text=text,
                    doc_id=f"rec_{integration_id}:{rid}",
                    source=integration_id,
                    metadata=meta,
                    user_id="system",
                    workspace_id=workspace_id,
                )
            except Exception as upsert_err:
                logger.error(f"{integration_id} upsert failed for record {rid}: {upsert_err}")
        if status == "written":
            ingested += 1
        elif status == "skipped_unchanged":
            skipped += 1

        # The trigger classifier scores payload text — pass the full record
        # (email/company/description carry the classification signal).
        trigger_rec = dict(rec)
        trigger_rec["id"] = rid
        trigger_rec["type"] = rtype
        trigger_rec.setdefault("name", record.get("name"))
        trigger_payloads.append(trigger_rec)

    triggered = 0
    if ingested:
        try:
            from core.ai_trigger_coordinator import on_data_ingested

            for rec in trigger_payloads[:_TRIGGER_CAP]:
                await on_data_ingested(
                    rec,
                    source=integration_id,
                    workspace_id=workspace_id,
                    metadata={"role": role, "force_trigger": True},
                )
                triggered += 1
        except Exception as trig_err:
            logger.warning(f"{integration_id} trigger pass failed: {trig_err}")

    return {
        "received": received,
        "ingested": ingested,
        "skipped_unchanged": skipped,
        "triggers_fired": triggered,
    }


def list_recent(handler: Any, integration_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Recent-first readback of ingested records (LanceDB list_documents)."""
    if handler is None:
        return []
    try:
        return handler.list_documents(f"integration_{integration_id}", limit=limit) or []
    except Exception as e:
        logger.warning(f"{integration_id} recent readback failed: {e}")
        return []


def search_records(
    handler: Any, integration_id: str, query: str, limit: int = 10
) -> List[Dict[str, Any]]:
    """Vector search over ingested records (LanceDB search)."""
    if handler is None or not (query or "").strip():
        return []
    try:
        return handler.search(f"integration_{integration_id}", query, limit=limit) or []
    except Exception as e:
        logger.warning(f"{integration_id} search failed: {e}")
        return []
