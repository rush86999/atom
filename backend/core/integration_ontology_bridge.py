"""Integration records → ontology bridge (R84).

Closes the deferred R83b gaps in one deterministic, LLM-free layer:

- **Canonical entity-type mapping** (``map_record_type``): integration
  record types (crm_leads, books_invoices, contacts, onedrive_file …) map
  onto the seed ontology vocabulary so GraphRAG nodes stop carrying
  platform jargon as their type. Consumed at the single funnel
  (``graphrag_engine.ingest_structured_data``) so every producer — hybrid
  sync, webhooks, historical sync, org bundles — benefits at once.
  Kill switch: ``ATOM_INTEGRATION_TYPE_MAP=false``.

- **Business-fact auto-extraction** (``derive_fact`` +
  ``write_integration_fact``): no writer existed for integration-derived
  facts. Extraction is deterministic field templating — importing a
  100k-record bundle or syncing a large CRM must never trigger LLM calls
  or embeddings beyond the row write itself. Facts are OBSERVATIONS:
  ``verification_status="unverified"``, sensitivity stamped into metadata
  (org-bundle export filters read it), and idempotent through the store
  itself: deterministic doc ids ``intfact:{integration_id}:{record_id}``
  plus an in-band content-hash probe (``get_document_by_id``) — unchanged
  content never rewrites; changed content appends a new version (the same
  append-versioning ``update_fact_verification`` already uses). No SQL
  dependency: the writer works against the LanceDB handler alone.
  Kill switch: ``ATOM_INTEGRATION_FACTS_ENABLED=false``, per-run cap
  ``ATOM_INTEGRATION_FACTS_MAX_PER_RUN`` (default 200).

Design rules honored:
- No LLM anywhere in this module.
- The mapping table only targets slugs that exist in the seed ontology;
  unknown record types pass through verbatim (no stub categories).
- Fact rows follow the reader contract of
  ``agent_world_model.get_relevant_business_facts`` (metadata id/fact/
  citations/verification_status) and keep top-level doc_id ==
  metadata["id"] so ``get_business_fact`` lookups work.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

FACTS_TABLE = "business_facts"
FACT_SOURCE_ACTOR = "integration_bridge"

# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


def type_map_enabled() -> bool:
    """Kill switch for record-type→ontology coercion (default ON)."""
    return _flag("ATOM_INTEGRATION_TYPE_MAP", "true")


def facts_enabled() -> bool:
    """Kill switch for integration business-fact extraction (default ON)."""
    return _flag("ATOM_INTEGRATION_FACTS_ENABLED", "true")


def max_facts_per_run() -> int:
    try:
        return max(0, int(os.getenv("ATOM_INTEGRATION_FACTS_MAX_PER_RUN", "200")))
    except ValueError:
        return 200


# ---------------------------------------------------------------------------
# GAP B: canonical entity-type mapping
# ---------------------------------------------------------------------------

# record-type token (after prefix-strip/singular normalization) → ontology
# slug. Targets are exactly SEED_ENTITY_TYPES slugs; anything absent from
# this table intentionally passes through unmapped (tickets/events/products
# have no ontology home yet — fabricating one would create junk nodes).
RECORD_TYPE_TO_ONTOLOGY: Dict[str, str] = {
    # person-ish
    "person": "Person",
    "contact": "Person",
    "user": "Person",
    "customer": "Person",
    # organizations
    "organization": "Organization",
    "company": "Organization",
    "account": "Organization",
    "companies": "Organization",
    # opportunity family
    "lead": "Lead",
    "prospect": "Lead",
    "deal": "Deal",
    "opportunity": "Deal",
    "opportunities": "Deal",
    # transactions
    "invoice": "Invoice",
    "bill": "Invoice",
    "sales_order": "SalesOrder",
    "order": "SalesOrder",
    "purchase_order": "PurchaseOrder",
    "po": "PurchaseOrder",
    "quote": "Quote",
    "quotation": "Quote",
    "shipment": "Shipment",
    "delivery": "Shipment",
    # communication / content
    "message": "Message",
    "email": "Message",
    "thread": "Message",
    "chat": "Message",
    "file": "File",
    "document": "File",
    "attachment": "File",
    "page": "File",
    # work
    "task": "Task",
    "todo": "Task",
    "issue": "Task",
    "action_item": "Task",
    "project": "Project",
    "initiative": "Project",
}


def map_record_type(raw: Any) -> Optional[str]:
    """Map an integration record type to a canonical ontology slug.

    Resolution order: exact alias hit → plural-normalized full string →
    last-segment heuristic (platform/module prefixes like ``crm_leads``,
    ``books_invoices``, ``onedrive_file``) with plural normalization.
    Returns None when no ontology target exists (caller keeps raw type).
    """
    if raw is None:
        return None
    key = str(raw).strip().lower()
    if not key or key == "unknown":
        return None

    def hit(token: Optional[str]) -> Optional[str]:
        if not token:
            return None
        return RECORD_TYPE_TO_ONTOLOGY.get(token)

    candidates = [key]
    if key.endswith("s"):
        candidates.append(key[:-1])
    tail = key.rsplit("_", 1)[-1]
    candidates.append(tail)
    if tail.endswith("s") and len(tail) > 1:
        candidates.append(tail[:-1])

    for cand in candidates:
        mapped = hit(cand)
        if mapped:
            return mapped
    return None


# ---------------------------------------------------------------------------
# GAP A: deterministic fact derivation + writer
# ---------------------------------------------------------------------------

# Field priority for the fact sentence: subject candidates first, then
# salient scalar attributes (capped), then everything else is ignored —
# internal bookkeeping keys must never leak into facts.
_SUBJECT_KEYS = ("name", "title", "subject", "summary", "display_name")
_SALIENT_KEYS = (
    "stage", "status", "amount", "value", "total", "email", "phone",
    "company", "account_name", "priority", "severity", "due_date",
    "owner", "assignee", "quantity", "price",
)
_FACT_VALUE_CAP = 120
_FACT_FIELD_CAP = 6


def derive_fact(
    integration_id: str,
    record_type: Optional[str],
    record: Dict[str, Any],
    text: str,
) -> Optional[Dict[str, Any]]:
    """Build the deterministic fact payload for an integration record.

    Returns ``{"fact": str, "domain": Optional[str]}`` or None when the
    record carries nothing salient.
    """
    subject = ""
    for key in _SUBJECT_KEYS:
        val = record.get(key)
        if isinstance(val, (str, int, float)) and str(val).strip():
            subject = str(val).strip()
            break

    fields: List[str] = []
    seen = {k.lower() for k in _SUBJECT_KEYS}
    for key in _SALIENT_KEYS:
        if len(fields) >= _FACT_FIELD_CAP:
            break
        val = record.get(key)
        if val is None or isinstance(val, (dict, list)):
            continue
        sval = str(val).strip()[:_FACT_VALUE_CAP]
        if not sval or key.lower() in seen:
            continue
        seen.add(key.lower())
        fields.append(f"{key}={sval}")

    label = map_record_type(record_type) or (str(record_type).replace("_", " ") if record_type else "")
    head = f"{integration_id}"
    if label:
        head += f" {label}"
    head += f" '{subject}'" if subject else f" record '{record.get('id', '')}'"
    fact = f"{head}: " + "; ".join(fields) if fields else f"{head} (no salient fields)"
    if len(fact) > 600:
        fact = fact[:597] + "..."

    return {"fact": fact, "domain": map_record_type(record_type)}


class FactBudget:
    """Per-run cap on fact writes (sync run / webhook call / bundle import)."""

    def __init__(self, max_per_run: Optional[int] = None):
        self.remaining = max_per_run if max_per_run is not None else max_facts_per_run()

    def take(self) -> bool:
        if self.remaining <= 0:
            return False
        self.remaining -= 1
        return True


def fact_content_hash(text: str) -> str:
    """Stable short hash of the source text used for fact versioning."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


async def write_integration_fact(
    *,
    workspace_id: str,
    tenant_id: Optional[str],
    integration_id: str,
    record_type: Optional[str],
    record: Dict[str, Any],
    text: str,
    sensitivity: str = "internal",
    memory_handler: Any = None,
    budget: Optional[FactBudget] = None,
) -> Dict[str, Any]:
    """Extract and persist the deterministic business fact for one record.

    Idempotency lives IN THE STORE: the fact row gets the deterministic id
    ``intfact:{integration_id}:{record_id}`` and stamps its source-text
    hash into metadata. Before writing, the existing row (if any) is probed
    via ``get_document_by_id`` — same hash → skip ("unchanged"), different
    hash → append a new version. Lookup failures fail OPEN to an append so
    ingestion is never blocked by the observation layer. Never raises.
    """
    import asyncio

    try:
        if not facts_enabled():
            return {"written": 0, "skipped": "disabled"}
        if memory_handler is None:
            return {"written": 0, "skipped": "no_handler"}
        if budget is not None and not budget.take():
            return {"written": 0, "skipped": "budget"}
        record_id = str((record or {}).get("id", "") or "").strip()
        if not record_id or not (text or "").strip():
            return {"written": 0, "skipped": "empty"}

        derived = derive_fact(integration_id, record_type, record or {}, text)
        if not derived:
            return {"written": 0, "skipped": "underived"}

        marker_id = f"intfact:{integration_id}:{record_id}"
        new_hash = fact_content_hash(text)

        def _sync_write() -> Dict[str, Any]:
            try:
                existing = memory_handler.get_document_by_id(FACTS_TABLE, marker_id)
            except Exception:  # noqa: BLE001 — probe failures must not block writes
                existing = None
            if isinstance(existing, dict):
                prior_meta = existing.get("metadata") or {}
                if prior_meta.get("content_hash") == new_hash:
                    return {"written": 0, "skipped": "unchanged"}
                # Replace, not append: add_document is append-only, so a plain
                # re-add would leave two rows with the same id and the
                # unordered `.limit(1)` probes would read an arbitrary version.
                # delete_documents_by_id removes ALL prior versions first.
                if hasattr(memory_handler, "delete_documents_by_id"):
                    try:
                        memory_handler.delete_documents_by_id(FACTS_TABLE, marker_id)
                    except Exception:  # noqa: BLE001 — best-effort cleanup
                        pass

            now = datetime.now(timezone.utc)
            citations = [f"{integration_id}:{record_id}"]
            reason = (
                f"Auto-extracted from {integration_id} integration "
                f"record {record_id} ({record_type or 'unknown type'})"
            )
            meta: Dict[str, Any] = {
                "id": marker_id,
                "fact": derived["fact"],
                "citations": citations,
                "reason": reason,
                "source_agent_id": FACT_SOURCE_ACTOR,
                "created_at": now.isoformat(),
                "last_verified": now.isoformat(),
                "verification_status": "unverified",
                "type": "business_fact",
                "domain": derived.get("domain"),
                "sensitivity": sensitivity or "internal",
                "content_hash": new_hash,
            }
            text_repr = (
                f"Fact: {derived['fact']}\n"
                f"Citations: {', '.join(citations)}\n"
                f"Reason: {reason}\n"
                f"Status: unverified"
            )
            ok = memory_handler.add_document(
                table_name=FACTS_TABLE,
                text=text_repr,
                source=f"integration_{integration_id}",
                metadata=meta,
                user_id="integration_sync",
                doc_id=marker_id,
            )
            if not ok:
                return {"written": 0, "skipped": "write_failed"}
            return {"written": 1, "skipped": 0}

        return await asyncio.to_thread(_sync_write)
    except Exception as e:  # noqa: BLE001 — observation layer must never break ingestion
        logger.warning(f"Integration fact extraction skipped for {integration_id}: {e}")
        return {"written": 0, "skipped": "error"}


async def retract_integration_facts(
    *,
    workspace_id: str,
    integration_id: str,
    record_ids: List[str],
    memory_handler: Any = None,
) -> Dict[str, Any]:
    """Retract the derived business facts for removed/tombstoned records.

    A tombstone means the source system deleted the record — every stored
    version of its deterministic fact (``intfact:{integration}:{record}``)
    must leave business_facts, or agents keep citing deleted data. Uses
    ``delete_documents_by_id`` (removes ALL versions of the doc id).
    Never raises: a broken store must not block import/sync close-out.
    """
    import asyncio

    try:
        if not facts_enabled():
            return {"retracted": 0}
        if memory_handler is None or not record_ids:
            return {"retracted": 0}

        def _sync_retract() -> Dict[str, Any]:
            retracted = 0
            for raw_id in record_ids:
                rid = str(raw_id or "").strip()
                if not rid:
                    continue
                try:
                    if memory_handler.delete_documents_by_id(
                        FACTS_TABLE, f"intfact:{integration_id}:{rid}"
                    ):
                        retracted += 1
                except Exception as e:  # noqa: BLE001 — per-row isolation
                    logger.warning(
                        "Fact retraction failed for %s/%s: %s",
                        integration_id, rid, e,
                    )
            return {"retracted": retracted}

        return await asyncio.to_thread(_sync_retract)
    except Exception as e:  # noqa: BLE001 — observation layer must never break callers
        logger.warning(f"Fact retraction skipped for {integration_id}: {e}")
        return {"retracted": 0}


__all__ = [
    "RECORD_TYPE_TO_ONTOLOGY",
    "FactBudget",
    "derive_fact",
    "fact_content_hash",
    "facts_enabled",
    "map_record_type",
    "max_facts_per_run",
    "retract_integration_facts",
    "type_map_enabled",
    "write_integration_fact",
]
