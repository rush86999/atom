"""Content-aware vector upsert shared by every ingestion surface.

Re-ingesting the same record (re-sync, webhook redelivery, bundle re-import)
must UPDATE the stored row, not append a duplicate. LanceDB ``add`` is
append-only, so the upsert contract on a STABLE doc id is:

    1. probe the stored row — same ``source_content_hash`` → skip unchanged;
    2. delete all prior versions under that id;
    3. write the fresh copy with the hash stamped in metadata.

Every integration path (hybrid sync, both webhook tiers, sync_and_ingest,
org-bundle import, documents API, file ingestion) funnels through
:func:`upsert_document` so the semantics can never drift between surfaces.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def upsert_document(
    handler: Any,
    *,
    table_name: str,
    text: str,
    doc_id: str,
    source: str,
    metadata: Dict[str, Any],
    user_id: str = "system",
    workspace_id: Optional[str] = None,
    skip_ai_triggers: bool = False,
    extra_columns: Optional[Dict[str, Any]] = None,
) -> str:
    """Upsert one row by stable ``doc_id``. Returns "written",
    "skipped_unchanged", or "write_failed" (callers decide severity); the
    probe/cleanup legs are best-effort and never block the write."""
    from core.doc_freshness_service import hash_text

    content_hash = hash_text(text)

    try:
        prior = await asyncio.to_thread(handler.get_document_by_id, table_name, doc_id)
        if isinstance(prior, dict):
            prior_meta = prior.get("metadata") or {}
            if (
                isinstance(prior_meta, dict)
                and prior_meta.get("source_content_hash") == content_hash
            ):
                return "skipped_unchanged"
    except Exception as probe_err:  # noqa: BLE001 — probe failures fail OPEN to a write
        logger.debug(f"upsert probe failed for {doc_id}: {probe_err}")

    metadata = dict(metadata or {})
    metadata["source_content_hash"] = content_hash

    if getattr(handler, "delete_documents_by_id", None) is not None:
        try:
            await asyncio.to_thread(handler.delete_documents_by_id, table_name, doc_id)
        except Exception as del_err:  # noqa: BLE001 — best-effort cleanup
            logger.debug(f"upsert prior-version cleanup failed for {doc_id}: {del_err}")

    add_kwargs: Dict[str, Any] = dict(
        table_name=table_name,
        text=text,
        source=source,
        metadata=metadata,
        user_id=user_id,
        doc_id=doc_id,
    )
    if workspace_id is not None:
        add_kwargs["workspace_id"] = workspace_id
    if skip_ai_triggers:
        add_kwargs["skip_ai_triggers"] = True
    if extra_columns:
        add_kwargs["extra_columns"] = extra_columns

    success = await asyncio.to_thread(handler.add_document, **add_kwargs)
    if not success:
        # Callers decide severity: file ingestion degrades to a skip,
        # the documents API surfaces a 500. Never raise here.
        return "write_failed"
    return "written"
