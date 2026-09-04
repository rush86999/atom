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
    from core.doc_freshness_service import extraction_content_hash

    content_hash = extraction_content_hash(text)

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


def _split_into_chunks(text: str, size: int, overlap: int) -> list[str]:
    """Greedy packing of `text` into ~`size`-char windows, preferring line
    and sentence boundaries near the window end, with `overlap` carryover so
    no fact lands on a seam unseen."""
    text = text.strip()
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            window = text[start:end]
            cut = max(
                window.rfind("\n\n"),
                window.rfind("\n"),
                window.rfind(". "),
            )
            if cut > size // 2:
                end = start + cut + 1
        chunks.append(text[start:end].strip())
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


async def upsert_document_chunks(
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
    chunk_size: int = 1200,
    chunk_overlap: int = 180,
) -> str:
    """Chunked variant of :func:`upsert_document` for long documents.

    One row per document gives one embedding for (say) 55k chars — the
    vector sees a blur and recall degrades to "whatever the head matched".
    This writes each chunk as ``{doc_id}::c{i}`` carrying the FULL-document
    content hash and parent metadata, so retrieval can match a relevant
    region while identity/freshness stay per-file.

    Same return contract as upsert_document ("written" | "skipped_unchanged"
    | "write_failed"). Texts at or below chunk_size delegate to the plain
    single-row upsert (including its family cleanup, so a document that
    shrank from chunked to small leaves no orphan chunks behind).
    """
    from core.doc_freshness_service import extraction_content_hash

    content_hash = extraction_content_hash(text)
    chunks = _split_into_chunks(text, chunk_size, chunk_overlap)
    if len(chunks) <= 1:
        # A previously-chunked document that shrank must not leave orphan
        # chunk rows behind — clean the family before the single-row write.
        try:
            stale = await asyncio.to_thread(
                handler.get_document_ids_by_prefix,
                table_name,
                f"{doc_id}::c",
            )
            for rid in stale or []:
                await asyncio.to_thread(handler.delete_documents_by_id, table_name, rid)
        except Exception as cleanup_err:  # noqa: BLE001 — best-effort
            logger.debug(f"shrink cleanup failed for {doc_id}: {cleanup_err}")
        return await upsert_document(
            handler,
            table_name=table_name,
            text=text,
            doc_id=doc_id,
            source=source,
            metadata=metadata,
            user_id=user_id,
            workspace_id=workspace_id,
            skip_ai_triggers=skip_ai_triggers,
            extra_columns=extra_columns,
        )

    family_prefix = f"{doc_id}::c"

    # Hash-skip: c0 carries the FULL-document hash AND the expected chunk
    # count. Hash alone is not sufficient: a writer that died mid-family
    # (crash, deploy, OOM) leaves a TRUNCATED family whose c0 hash still
    # matches — live 2026-09-03 the Consolidated Price List re-ingest died
    # at chunk ~52 of ~1700 and every later ingest then said
    # "skipped_unchanged" off that c0, pinning a 62k-char fragment of a 4M
    # char workbook. The skip requires the stored family to be complete.
    try:
        c0 = await asyncio.to_thread(
            handler.get_document_by_id, table_name, f"{family_prefix}0"
        )
        if isinstance(c0, dict):
            c0_meta = c0.get("metadata") or {}
            if (
                isinstance(c0_meta, dict)
                and c0_meta.get("source_content_hash") == content_hash
            ):
                stored_total = c0_meta.get("chunk_total")
                expected = len(chunks)
                family_complete = False
                if stored_total == expected:
                    stored_ids = await asyncio.to_thread(
                        handler.get_document_ids_by_prefix,
                        table_name,
                        family_prefix,
                    )
                    family_complete = len(stored_ids or []) >= expected
                if family_complete:
                    return "skipped_unchanged"
                logger.info(
                    f"chunk upsert: {doc_id} hash matches but family is "
                    f"incomplete/legacy (stored_total={stored_total}, "
                    f"expected={expected}) — rewriting"
                )
    except Exception as probe_err:  # noqa: BLE001 — probe failures fail OPEN
        logger.debug(f"chunk upsert probe failed for {doc_id}: {probe_err}")

    # Delete the prior family — ONE predicate delete for the whole chunk
    # family (plus the legacy single row under the base id). The per-id loop
    # this replaces cost one table transaction per chunk id: ~3.4k deletes =
    # 25-90+ min under contention before a re-ingest could add its first row
    # (live 2026-09-04). Falls back to per-id when the handler lacks the
    # batch form.
    if getattr(handler, "delete_documents_by_prefix", None) is not None:
        try:
            deleted = await asyncio.to_thread(
                handler.delete_documents_by_prefix, table_name, family_prefix
            )
            if deleted:
                stale_ids = [doc_id]
            else:
                stale_ids = None
        except Exception as del_err:  # noqa: BLE001 — fall back below
            logger.debug(f"prefix family cleanup failed for {doc_id}: {del_err}")
            stale_ids = None
    else:
        stale_ids = None
    if stale_ids is None:
        stale_ids = [doc_id]
        try:
            stale_ids = [doc_id] + list(
                await asyncio.to_thread(
                    handler.get_document_ids_by_prefix, table_name, family_prefix
                )
            )
        except Exception as list_err:  # noqa: BLE001 — fall back to base id only
            logger.debug(f"chunk family listing failed for {doc_id}: {list_err}")
        if getattr(handler, "delete_documents_by_id", None) is not None:
            for rid in stale_ids:
                try:
                    await asyncio.to_thread(
                        handler.delete_documents_by_id, table_name, rid
                    )
                except Exception as del_err:  # noqa: BLE001 — best-effort cleanup
                    logger.debug(f"chunk family cleanup failed for {rid}: {del_err}")

    base_meta = dict(metadata or {})
    base_meta["source_content_hash"] = content_hash
    base_meta["parent_doc_id"] = doc_id
    total = len(chunks)

    # Batched fast path: ONE table.add transaction for the whole family.
    # The per-chunk add_document loop above it cost one embed + one Lance
    # transaction per chunk — 3.4k chunks took 45-90 min under contention
    # (live 2026-09-04); batched, the same write is minutes. Falls back to
    # the per-chunk loop when the handler lacks the batch form.
    batch_add = getattr(handler, "add_documents_batch", None)
    if batch_add is not None:
        docs: List[Dict[str, Any]] = []
        for i, chunk in enumerate(chunks):
            chunk_meta = dict(base_meta)
            chunk_meta["chunk_index"] = i
            chunk_meta["chunk_total"] = total
            doc: Dict[str, Any] = dict(
                id=f"{family_prefix}{i}",
                text=chunk,
                source=source,
                metadata=chunk_meta,
                user_id=user_id,
            )
            if workspace_id is not None:
                doc["workspace_id"] = workspace_id
            if extra_columns:
                doc["extra_columns"] = dict(extra_columns)
            docs.append(doc)
        try:
            added = await asyncio.to_thread(batch_add, table_name, docs)
            if added and added >= len(docs):
                return "written"
            logger.warning(
                f"batch chunk add incomplete for {doc_id} "
                f"({added}/{len(docs)}) — falling back to per-chunk adds"
            )
        except Exception as batch_err:  # noqa: BLE001 — fall back below
            logger.warning(f"batch chunk add failed for {doc_id}: {batch_err}")

    for i, chunk in enumerate(chunks):
        chunk_meta = dict(base_meta)
        chunk_meta["chunk_index"] = i
        chunk_meta["chunk_total"] = total
        add_kwargs: Dict[str, Any] = dict(
            table_name=table_name,
            text=chunk,
            source=source,
            metadata=chunk_meta,
            user_id=user_id,
            doc_id=f"{family_prefix}{i}",
        )
        if workspace_id is not None:
            add_kwargs["workspace_id"] = workspace_id
        if skip_ai_triggers:
            add_kwargs["skip_ai_triggers"] = True
        if extra_columns:
            add_kwargs["extra_columns"] = dict(extra_columns)
        success = await asyncio.to_thread(handler.add_document, **add_kwargs)
        if not success:
            return "write_failed"
    return "written"
