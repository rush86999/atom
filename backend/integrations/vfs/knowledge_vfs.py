"""
Knowledge VFS provider (W1, P2b).

Exposes ``IngestedDocument`` + ``KnowledgeDocument`` as a virtual directory
tree under ``knowledge/``:

    knowledge/
      documents/
        <id>/                 ← one IngestedDocument or KnowledgeDocument
          meta.json
          content.lines       ← line-numbered (L<n>: <text>)

Agents navigate with ``ls``/``cat``/``grep``; line-numbered content makes
citations precise.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.vfs_base import (
    VFSCitation,
    VFSNode,
    VFSProvider,
    VFSRegion,
    VFSResource,
    to_line_numbered,
)

logger = logging.getLogger(__name__)

#: Bound on comms-store scans. The communications pipeline can stall during
#: init in long-running servers; the conversations subtree must degrade to
#: empty rather than hang the agent's filesystem call (Aug 2026: root grep
#: hung 5+ minutes on the comms pipeline init).
_COMMS_TIMEOUT_S = 20

#: How many messages one ``ls knowledge/conversations`` may list. The store
#: held 7,009 messages on 2026-09-13 and grows with every poll; a truncated
#: listing SAYS SO (a "note" node) instead of silently showing a prefix.
_COMMS_LIST_LIMIT = 2000

#: Total grep citations returned from the conversations store, and how many
#: one message may contribute — a 79k-char quoted thread repeating a common
#: word must not flood the agent's context.
_COMMS_CITATION_CAP = 200
_COMMS_CITES_PER_MESSAGE = 5

#: Same bounds for the documents store. 39,085 rows live (2026-09-13); the old
#: ``.slice(0, 1000)`` scanned 2.6% of them.
_DOCS_SCAN_LIMIT = 100_000
_DOCS_CITATION_CAP = 200
_DOCS_CITES_PER_DOC = 5

#: TTL for cached projected store reads (see ``_vector_rows``). VFS calls
#: arrive in bursts within one agent turn, and each uncached read walks the
#: whole store. Short TTL keeps fresh ingests visible quickly.
#: 0 disables caching. Env: ATOM_VFS_ROWS_CACHE_TTL seconds.
import os as _os

_VFS_ROWS_CACHE_TTL = float(
    _os.getenv("ATOM_VFS_ROWS_CACHE_TTL", "15") or 15
)

#: Rows per streamed batch in ``_vector_rows`` — bounds the memory a
#: whole-store scan holds (and what a timeout can leave behind). Env:
#: ATOM_VFS_SCAN_BATCH.
_VFS_SCAN_BATCH = int(_os.getenv("ATOM_VFS_SCAN_BATCH", "2000") or 2000)



class KnowledgeVFSProvider(VFSProvider):
    """VFS view over the internal knowledge document stores."""

    prefix = "knowledge"

    def __init__(self, db_factory=None):
        # db_factory: a zero-arg callable returning a Session (so each call
        # gets a fresh session). Defaults to the app's SessionLocal.
        if db_factory is None:
            from core.database import SessionLocal
            db_factory = SessionLocal
        self._db_factory = db_factory
        # Per-instance projected-read cache (see _vector_rows): a fresh
        # provider instance starts uncached, which is what keeps tests that
        # fake the table isolated from each other.
        self._rows_cache: Dict[tuple, tuple] = {}

    def invalidate_rows_cache(self) -> None:
        """Drop cached projected reads — call after this process writes to
        either store so a following grep/cat/ls sees the new rows."""
        self._rows_cache.clear()

    def _db(self):
        return self._db_factory()

    async def ls(self, path: str, ctx: Optional[Dict[str, Any]] = None) -> List[VFSNode]:
        """List children of a knowledge path.

        Supported paths:
          - ``knowledge`` → [documents/]
          - ``knowledge/documents`` → [<id> for each document]
          - ``knowledge/documents/<id>`` → [meta.json, content.lines]
        """
        cleaned = (path or "").lstrip("/").rstrip("/")
        parts = [p for p in cleaned.split("/") if p]

        if not parts or parts == ["knowledge"]:
            return [
                VFSNode(name="documents", type="dir", path="knowledge/documents"),
                VFSNode(name="conversations", type="dir", path="knowledge/conversations"),
            ]

        if parts == ["knowledge", "documents"]:
            return await self._list_documents(ctx)

        if parts == ["knowledge", "conversations"]:
            return await self._list_conversations(ctx)

        # knowledge/conversations/<id> → [content.lines]
        if len(parts) >= 3 and parts[:2] == ["knowledge", "conversations"]:
            conv = await self._get_conversation(parts[2])
            if conv is None:
                return []
            return [
                VFSNode(name="content.lines", type="file", path=f"knowledge/conversations/{parts[2]}/content.lines"),
            ]

        # knowledge/documents/<id>
        if len(parts) >= 3 and parts[:2] == ["knowledge", "documents"]:
            doc_id = parts[2]
            exists = await self._doc_exists(doc_id, ctx)
            if not exists:
                return []
            return [
                VFSNode(name="meta.json", type="file", path=f"knowledge/documents/{doc_id}/meta.json"),
                VFSNode(name="content.lines", type="file", path=f"knowledge/documents/{doc_id}/content.lines"),
            ]
        return []

    async def cat(self, path: str, ctx: Optional[Dict[str, Any]] = None) -> VFSResource:
        cleaned = (path or "/").lstrip("/")
        parts = [p for p in cleaned.split("/") if p]
        if len(parts) < 3:
            return VFSResource(path=path)

        # knowledge/conversations/<id>/{content.lines}
        if parts[:2] == ["knowledge", "conversations"]:
            conv = await self._get_conversation(parts[2])
            if conv is None:
                return VFSResource(path=path)
            res = VFSResource(
                path=f"knowledge/conversations/{parts[2]}",
                meta={"app_type": conv.get("app_type"), "timestamp": str(conv.get("timestamp", ""))},
            )
            res.lines = to_line_numbered(str(conv.get("content", "")))
            return res

        # Expect knowledge/documents/<id>/{meta.json|content.lines}
        doc_id = parts[2]
        leaf = parts[3] if len(parts) > 3 else "content.lines"
        doc = await self._get_doc(doc_id, ctx)
        if doc is None:
            return VFSResource(path=path)
        meta = self._doc_meta(doc)
        text = self._doc_text(doc)
        # PG IngestedDocument rows carry only a ≤500-char preview; the full
        # extracted text lives in the aligned LanceDB row. Serve the full text
        # when the mirror row is the only thing we'd otherwise truncate.
        if doc[0] == "ingested":
            vec = await self._get_vector_doc(doc_id)
            if vec:
                vec_text = str(vec.get("text") or "")
                if len(vec_text) > len(text):
                    text = vec_text
        res = VFSResource(path=f"knowledge/documents/{doc_id}", meta=meta)
        if leaf == "meta.json":
            import json
            res.lines = to_line_numbered(json.dumps(meta, indent=2, default=str))
        else:
            res.lines = to_line_numbered(text)
        return res

    async def read_region(
        self,
        path: str,
        start_line: int = 1,
        max_lines: int = 200,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> VFSRegion:
        """Bounded read of a document OR conversation leaf.

        Overrides the generic (cat-then-slice) default: a long artifact is
        materialized once per read there, and the whole point of the primitive
        is that reading line 315 of a 324-line workbook costs the same as
        reading line 1. The sliced path also keeps the paging contract honest
        for chunk families — the number the agent pages through is the number
        the citations use."""
        region = VFSRegion(path=path, start_line=max(int(start_line or 1), 1))
        cleaned = (path or "").lstrip("/")
        parts = [p for p in cleaned.split("/") if p]
        text = ""
        try:
            if len(parts) >= 3 and parts[:2] == ["knowledge", "conversations"]:
                conv = await self._get_conversation(parts[2])
                if conv is not None:
                    text = str(conv.get("content") or "")
            elif len(parts) >= 3 and parts[:2] == ["knowledge", "documents"]:
                doc = await self._get_doc(parts[2], ctx)
                if doc is not None:
                    text = self._doc_text(doc)
                    if doc[0] == "ingested":
                        vec = await self._get_vector_doc(parts[2])
                        if vec and len(str(vec.get("text") or "")) > len(text):
                            text = str(vec.get("text") or "")
        except Exception as e:  # noqa: BLE001 — degraded, never a silent EOF
            logger.debug(f"[KnowledgeVFS] read_region failed for {path}: {e}")
            region.degraded = True
            return region
        lines = to_line_numbered(text)
        region.total_lines = len(lines)
        window = lines[region.start_line - 1:region.start_line - 1 + max(int(max_lines or 1), 1)]
        region.lines = window
        nxt = region.start_line + len(window)
        region.next_start = None if (not window or nxt > region.total_lines) else nxt
        return region

    async def grep(
        self, pattern: str, path_prefix: str, ctx: Optional[Dict[str, Any]] = None
    ) -> List[VFSCitation]:
        """Search across knowledge content under ``path_prefix``.

        Overrides the base (which only scans one level of file nodes) because
        knowledge/documents/<id>/ are directories. Implementation note: this is
        a BATCHED scan — one PG query + one Arrow scan per store — never
        ls-then-cat-per-doc. The naive descent (cat every listed dir) ran one
        kNN ``table.search()`` per conversation over the 20k-row comms table,
        taking minutes in-app (Aug 2026 journey trace).
        """
        import re
        citations: List[VFSCitation] = []
        try:
            # MULTILINE keeps `^`/`$` line-anchored — the same semantics as
            # the per-line citation loop below and as grep itself. Without
            # it, the whole-text fast-skip in _cites_for_text swallows every
            # `^From:`-style pattern that matches past the first line
            # (silent false negatives, the head-window bug's family).
            regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        except re.error:
            return citations
        # A root prefix ("/" or "") lists only the top-level category dirs, not
        # documents — retarget it at BOTH content trees so grep("/") finds hits
        # in documents and conversations alike.
        prefixes = [path_prefix]
        if path_prefix in ("/", "", "knowledge"):
            prefixes = ["knowledge/documents", "knowledge/conversations"]

        if "knowledge/documents" in prefixes:
            citations.extend(await self._grep_documents(regex, ctx))
        if "knowledge/conversations" in prefixes:
            citations.extend(await self._grep_conversations(regex))
        # Make every citation ACTIONABLE: a hit at line 315 of a 324-line
        # workbook is useless unless the agent can fetch that region without
        # pulling the whole file. Snippet gets the ready-to-run bounded read.
        for c in citations:
            start = max(1, int(c.line) - 2)
            # The hint uses the SAME path the citation names, so line numbers
            # agree: a chunk id resolves to that chunk (6 lines), while the
            # parent id resolves to the whole assembled document (324 lines)
            # — mixing them would send the agent to the wrong line.
            hint = (
                f"[read: documents.read(path='{c.path}/content.lines', "
                f"start_line={start}, max_lines=20)]"
            )
            if hint not in c.snippet:
                c.snippet = f"{c.snippet} {hint}"
        return citations

    def _cites_for_text(self, regex, path: str, text: str) -> List[VFSCitation]:
        out: List[VFSCitation] = []
        text = text or ""
        # Fast skip: one C-level scan of the whole text beats per-line
        # regexes for the ~99% of rows that cannot match (measured live
        # 2026-09-13: the per-line loop alone put a whole-store grep at
        # 11-14s — close enough to the 20s timeout to silently degrade to
        # "no matches" under load).
        if not regex.search(text):
            return out
        for i, line in enumerate(text.split("\n")):
            if regex.search(line):
                out.append(VFSCitation(path=path, line=i + 1, snippet=line[:200]))
        return out

    async def _grep_documents(self, regex, ctx) -> List[VFSCitation]:
        """Regex-scan served document text: vector full text first (what cat
        serves), PG preview / KnowledgeDocument content for rows with no
        vector text. Two batched queries, no per-doc reads.

        The vector leg scans the WHOLE table. The old ``.slice(0, 1000)``
        meant 2.6% coverage of the live 39,085-row store — the same class of
        silent head-window bug as the conversations leg, and the reason a
        figure living in chunk c2213 of a price list could not be grepped.
        """
        rows = await self._vector_rows(
            "documents", ["id", "text"], limit=_DOCS_SCAN_LIMIT
        )
        citations: List[VFSCitation] = []
        vector_ids: set = set()
        for row in rows:
            doc_id = str(row.get("id") or "")
            text = str(row.get("text") or "")
            if not doc_id or not text:
                continue
            vector_ids.add(doc_id)
            # The chunk id IS addressable (`_get_doc` resolves it), so it
            # stays in the citation: line numbers then match the text the
            # agent reads back. The parent id remains available in the same
            # tree for the full assembled document.
            hits = self._cites_for_text(
                regex, f"knowledge/documents/{doc_id}", text
            )
            citations.extend(hits[:_DOCS_CITES_PER_DOC])
            if len(citations) >= _DOCS_CITATION_CAP:
                return citations[:_DOCS_CITATION_CAP]

        try:
            from core.models import IngestedDocument, KnowledgeDocument

            with self._db() as db:
                q1 = db.query(IngestedDocument)
                wf = self._workspace_filter(ctx, IngestedDocument)
                if wf is not None:
                    q1 = q1.filter(wf)
                for d in q1.yield_per(500):
                    if len(citations) >= _DOCS_CITATION_CAP:
                        return citations[:_DOCS_CITATION_CAP]
                    if d.id in vector_ids:
                        continue
                    citations.extend(
                        self._cites_for_text(
                            regex,
                            f"knowledge/documents/{d.id}",
                            getattr(d, "content_preview", "") or "",
                        )[:_DOCS_CITES_PER_DOC]
                    )
                q2 = db.query(KnowledgeDocument)
                wf2 = self._workspace_filter(ctx, KnowledgeDocument)
                if wf2 is not None:
                    q2 = q2.filter(wf2)
                for d in q2.yield_per(500):
                    if len(citations) >= _DOCS_CITATION_CAP:
                        break
                    if d.id in vector_ids:
                        continue
                    citations.extend(
                        self._cites_for_text(
                            regex,
                            f"knowledge/documents/{d.id}",
                            getattr(d, "content", "") or "",
                        )[:_DOCS_CITES_PER_DOC]
                    )
        except Exception as e:
            logger.warning(f"[KnowledgeVFS] grep PG scan failed: {e}")
        return citations[:_DOCS_CITATION_CAP]

    async def _grep_conversations(self, regex, cap: int = _COMMS_CITATION_CAP) -> List[VFSCitation]:
        """Regex scan over the WHOLE comms store, bounded per message.

        The old implementation scanned ``table.head(200)`` — with 7,009 stored
        messages (3,395 of them past the 2,500-char excerpt cap) anything older
        than the 200 newest was unfindable by any search the agent could run.
        The whole store is scanned now (see ``_comms_rows``: projected, vector-
        and metadata-free); a common word in a 79k-char quoted thread is capped
        at ``_COMMS_CITES_PER_MESSAGE`` hits so one message cannot consume the
        agent's result budget.
        """
        rows = await self._comms_rows(["id", "content"])
        citations: List[VFSCitation] = []
        for row in rows:
            if len(citations) >= cap:
                break
            cid = str(row.get("id") or "")
            if not cid:
                continue
            hits = self._cites_for_text(
                regex, f"knowledge/conversations/{cid}", str(row.get("content") or "")
            )
            citations.extend(hits[:_COMMS_CITES_PER_MESSAGE])
        return citations[:cap]

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------
    def _workspace_filter(self, ctx, query_model):
        """Apply workspace scoping if a workspace_id is present in context."""
        ws = (ctx or {}).get("workspace_id")
        if ws and hasattr(query_model, "workspace_id"):
            return query_model.workspace_id == ws
        return None

    async def _list_documents(self, ctx) -> List[VFSNode]:
        from core.models import IngestedDocument, KnowledgeDocument
        nodes: List[VFSNode] = []
        try:
            with self._db() as db:
                q1 = db.query(IngestedDocument)
                wf = self._workspace_filter(ctx, IngestedDocument)
                if wf is not None:
                    q1 = q1.filter(wf)
                for d in q1.limit(200).all():
                    nodes.append(VFSNode(
                        name=d.id, type="dir", path=f"knowledge/documents/{d.id}",
                        modified=d.external_modified_at.isoformat() if d.external_modified_at else None,
                    ))
                q2 = db.query(KnowledgeDocument)
                wf2 = self._workspace_filter(ctx, KnowledgeDocument)
                if wf2 is not None:
                    q2 = q2.filter(wf2)
                for d in q2.limit(200).all():
                    nodes.append(VFSNode(
                        name=d.id, type="dir", path=f"knowledge/documents/{d.id}",
                        modified=d.updated_at.isoformat() if getattr(d, "updated_at", None) else None,
                    ))
        except Exception as e:
            logger.warning(f"[KnowledgeVFS] list failed: {e}")
        nodes.extend(await self._list_vector_documents(seen={n.name for n in nodes}))
        return nodes

    async def _list_vector_documents(self, seen: set, cap: int = 200) -> List[VFSNode]:
        """Surface vector-only rows (no PG mirror) in ls output.

        The LanceDB documents table holds rows this provider could cat (via
        the vector fallback) but that ls never listed — historical connector
        ingests, mirror-write failures — so agents browsing the tree missed
        documents that search could still hit. Merge them, capped, skipping
        ids already listed from PG.
        """
        import asyncio

        def _scan():
            try:
                from core.lancedb_handler import get_lancedb_handler

                handler = get_lancedb_handler("default")
                if handler is None:
                    return []
                return handler.list_document_heads("documents", limit=cap)
            except Exception as e:
                logger.debug(f"[KnowledgeVFS] vector head scan failed: {e}")
                return []

        heads = await asyncio.to_thread(_scan)
        nodes: List[VFSNode] = []
        for head in heads:
            doc_id = str(head.get("id") or "")
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            created = str(head.get("created_at") or "")
            nodes.append(VFSNode(
                name=doc_id, type="dir", path=f"knowledge/documents/{doc_id}",
                modified=created or None,
            ))
            if len(nodes) >= cap:
                break
        return nodes

    async def _doc_exists(self, doc_id: str, ctx: Optional[Dict[str, Any]] = None) -> bool:
        return (await self._get_doc(doc_id, ctx)) is not None

    # ------------------------------------------------------------------
    # Conversations subtree (communication memory store — bridge, not copy)
    # ------------------------------------------------------------------
    def _comms_table(self):
        """LanceDB atom_communications table, or None when unavailable.

        ``initialize()`` is called whenever the table is missing — NOT only
        when ``manager.db`` is already set. The old guard could never fire on
        a manager that had not opened its DB yet (``initialize()`` is what
        creates it), so every conversation-surface call silently degraded to
        an empty result until some unrelated code path happened to initialize
        the pipeline. Live 2026-09-13: a fresh process returned
        ``table is None`` and ``ls knowledge/conversations`` listed nothing,
        while the store held 7,009 messages. ``initialize()`` is idempotent.
        """
        try:
            from integrations.atom_communication_ingestion_pipeline import (
                get_ingestion_pipeline,
            )
            pipeline = get_ingestion_pipeline("default")
            manager = getattr(pipeline, "memory_manager", None)
            table = getattr(manager, "connections_table", None)
            if table is None and manager is not None and hasattr(manager, "initialize"):
                manager.initialize()
                table = getattr(manager, "connections_table", None)
            return table
        except Exception as e:
            logger.debug(f"[KnowledgeVFS] comms table unavailable: {e}")
            return None

    async def _list_conversations(self, ctx) -> List[VFSNode]:
        rows = await self._comms_rows(
            ["id", "timestamp", "sender", "subject", "content"],
            limit=_COMMS_LIST_LIMIT,
        )
        # Physical order is insertion order; backfills append older mail, so
        # sort by timestamp to make the "newest first" truncation note TRUE.
        rows.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
        nodes: List[VFSNode] = []
        for rec in rows:
            cid = str(rec.get("id") or "")
            if cid:
                nodes.append(VFSNode(
                    name=cid,
                    type="file",  # one leaf: content.lines (no sub-directory)
                    path=f"knowledge/conversations/{cid}",
                    size=len(str(rec.get("content") or "")),
                    modified=(
                        str(rec["timestamp"]) if rec.get("timestamp") else None
                    ),
                    meta={
                        "sender": str(rec.get("sender") or ""),
                        "subject": str(rec.get("subject") or ""),
                    },
                ))
        total = await self._comms_total()
        if total and total > len(nodes):
            nodes.append(VFSNode(
                name=(
                    f"(showing {len(nodes)} of {total} messages — newest first; "
                    f"use documents.grep to find a specific thread or figure)"
                ),
                type="note",
                path="knowledge/conversations#truncated",
            ))
        return nodes

    async def _comms_total(self) -> int:
        """Row count of the comms store (0 when unknown) — lets a listing say
        what it is NOT showing instead of silently truncating.

        Off-loop under the scan timeout: ``_comms_table()`` may call
        ``manager.initialize()`` (which loads the embedder model) and
        ``count_rows()`` is disk metadata I/O — running either on the event
        loop is the exact Aug 2026 init-stall freeze this module's timeout
        guard exists to prevent."""
        import asyncio

        def _count():
            table = self._comms_table()
            if table is None:
                return 0
            return int(table.count_rows())

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_count), timeout=_COMMS_TIMEOUT_S
            )
        except Exception as e:
            logger.warning(f"[KnowledgeVFS] comms count failed: {e}")
            return 0

    def _projected_table(self, table, columns):
        """Arrow table with ONLY ``columns``, lowest-memory route available.

        Ladder, cheapest first (measured on the live store 2026-09-13):

        1. ``table.search().select(cols).to_arrow()`` — LanceDB's own query
           builder pushes the projection into the scan. The comms store goes
           from **1.36 s / 3.07 GB** (full ``to_arrow``, mostly the two 384-dim
           vector columns plus ``metadata`` at a 49 KB/row median) to
           **0.11 s / 34 MB**.
        2. ``to_lance().to_table(columns=…)`` — true projection too, when the
           optional ``lance`` package is installed.
        3. Last resort: ``to_arrow().select(cols)``. Never the unprojected
           table — see the guard below.
        """
        cols = list(columns)
        try:
            qb = table.search()
            projected = qb.select(cols).to_arrow()
            if projected is not None:
                return projected
        except Exception as e:
            logger.debug(f"[KnowledgeVFS] query-builder projection unavailable: {e}")
        try:
            return table.to_lance().to_table(columns=cols)
        except Exception as e:
            logger.debug(f"[KnowledgeVFS] lance projection unavailable: {e}")
        projected = table.to_arrow()
        try:
            return projected.select(cols)
        except Exception:
            # Never fall back to the unprojected table: on this build that is
            # the vector+metadata materialization (GBs for the comms store)
            # this helper exists to prevent. Columns missing from the store
            # (schema drift on an open_table'd table) degrade to the
            # intersection of requested ∩ existing; anything else raises so
            # _vector_rows logs and degrades the call cleanly.
            names = list(getattr(projected, "column_names", []) or [])
            keep = [c for c in cols if c in names]
            if keep and len(keep) < len(cols):
                logger.warning(
                    "[KnowledgeVFS] store lacks columns %s — projecting to %s",
                    [c for c in cols if c not in keep], keep,
                )
                return projected.select(keep)
            raise

    def _stream_rows(self, table, columns, limit, batch_size):
        """Yield projected rows in BATCHES — bounded memory for whole-store
        scans.

        ``search().select().to_batches()`` streams from the scan, so a full
        grep over the 7k-message / 39k-document stores never holds the table
        (let alone its vectors) in RAM. Degrades to the projected table when
        ``to_batches`` is unavailable; returns nothing when even that fails,
        which the caller reports as a degraded scan.

        The bound is also what makes the ``wait_for`` timeout in
        ``_vector_rows`` honest: a scan that trips it abandons at most one
        batch, instead of leaving a thread that keeps materializing gigabytes
        after the agent has already been told the call degraded."""
        if batch_size and batch_size > 0:
            try:
                builder = table.search().select(list(columns))
                if limit is not None:
                    builder = builder.limit(int(limit))
                reader = builder.to_batches(batch_size=int(batch_size))
                for batch in reader:
                    yield from batch.to_pylist()
                return
            except Exception as e:
                logger.debug(f"[KnowledgeVFS] streaming read unavailable: {e}")
        try:
            tbl = self._projected_table(table, columns)
            if limit is not None:
                tbl = tbl.slice(0, int(limit))
            yield from tbl.to_pylist()
        except Exception as e:
            logger.warning(f"[KnowledgeVFS] projected fallback failed: {e}")
            return

    async def _comms_rows(
        self, columns: List[str], limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Rows with exactly ``columns`` from the WHOLE comms store, off-loop.

        Every conversation-surface caller (ls / grep / cat) goes through here
        so they all see the full mailbox instead of a head window. Vector and
        ``metadata`` columns are never requested. Bounded by ``limit`` and
        ``_COMMS_TIMEOUT_S``; a degraded scan returns [] rather than hanging
        the agent's filesystem call.
        """
        return await self._vector_rows(
            "comms", columns, limit=limit, label="comms"
        )

    async def _vector_rows(
        self,
        store: str,
        columns: List[str],
        limit: Optional[int] = None,
        label: str = "store",
    ) -> List[Dict[str, Any]]:
        """Projected, full-store, off-loop read shared by BOTH trees.

        ``store`` is ``"comms"`` (the mailbox) or ``"documents"`` (the ingested
        knowledge corpus). Both used to be read through silent head windows
        (200 and 1,000 rows) that made most of each store invisible to the
        agent's ``ls``/``grep``; both now read the whole store with the
        lightest projection this build supports. Degrades to [] on timeout or
        failure — never hangs the agent's filesystem call.

        Results are TTL-cached (``_VFS_ROWS_CACHE_TTL``, default 15s): VFS
        calls arrive in bursts (grep → cat → ls in one turn). Short TTL keeps a
        just-ingested message visible almost immediately; 0 disables.

        Each scan streams in ``_VFS_SCAN_BATCH`` row batches (projected), so a
        whole-store grep holds one batch rather than the table — and a scan
        that trips ``_COMMS_TIMEOUT_S`` abandons at most one batch instead of
        leaving a thread that keeps materializing gigabytes after the caller
        has already been told the read degraded."""
        import asyncio
        import time as _time

        cache_key = (store, tuple(columns), limit)
        now = _time.monotonic()
        hit = self._rows_cache.get(cache_key)
        if hit and _VFS_ROWS_CACHE_TTL > 0 and now - hit[0] < _VFS_ROWS_CACHE_TTL:
            return hit[1]

        def _table():
            if store == "comms":
                return self._comms_table()
            from core.lancedb_handler import get_lancedb_handler

            handler = get_lancedb_handler("default")
            return handler.get_table("documents") if handler is not None else None

        def _scan():
            table = _table()
            if table is None:
                return []
            return list(
                self._stream_rows(table, columns, limit, _VFS_SCAN_BATCH)
            )

        try:
            rows = await asyncio.wait_for(
                asyncio.to_thread(_scan), timeout=_COMMS_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[KnowledgeVFS] %s scan timed out after %ss — degraded",
                label, _COMMS_TIMEOUT_S,
            )
            return []
        except Exception as e:
            logger.warning(f"[KnowledgeVFS] {label} scan failed: {e}")
            return []
        # Only SUCCESSFUL non-empty reads are cached — a timeout-degraded []
        # must not mask the store for a full TTL.
        if rows and _VFS_ROWS_CACHE_TTL > 0:
            self._rows_cache[cache_key] = (now, rows)
        return rows

    # Back-compat alias (the projection ladder is store-agnostic).
    def _projected_arrow(self, table, columns):
        return self._projected_table(table, columns)

    async def _get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        for rec in await self._comms_rows(
            ["id", "app_type", "timestamp", "sender", "subject", "content"]
        ):
            if str(rec.get("id") or "") == str(conv_id):
                return rec
        return None

    async def _get_doc(self, doc_id: str, ctx):
        from core.models import IngestedDocument, KnowledgeDocument
        try:
            with self._db() as db:
                d = db.query(IngestedDocument).filter(IngestedDocument.id == doc_id).first()
                if d:
                    return ("ingested", d)
                d = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_id).first()
                if d:
                    return ("knowledge", d)
        except Exception as e:
            logger.warning(f"[KnowledgeVFS] get {doc_id} failed: {e}")
        # LanceDB fallback: vector-only rows (connector file ingests stamped
        # file_<ts>, manual uploads) have no PG row. Without this, search
        # surfaces them (bridged:false) but cat can never read them.
        rec = await self._get_vector_doc(doc_id)
        if rec is not None:
            return ("vector", rec)
        return None

    async def _get_vector_doc(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Fetch one document from the LanceDB ``documents`` table by id.

        CHUNK FAMILIES: a large file is stored as ``{parent}::c0, ::c1, …``
        (the pricing workbook attached to the F-5216 thread is 59 chunks), and
        the parent id has NO row of its own. Resolving only the exact id meant
        ``documents.cat('knowledge/documents/ext_…')`` returned nothing for
        every chunked file — so an agent could GREP a spreadsheet row (grep
        walks chunk rows) and then be unable to OPEN the file it found. The
        chunks are now assembled in order into the parent document.
        """
        import asyncio

        def _fetch():
            try:
                from core.lancedb_handler import get_lancedb_handler

                handler = get_lancedb_handler("default")
                if handler is None:
                    return None
                exact = handler.get_document_by_id("documents", str(doc_id))
                if exact is not None:
                    return exact
                if "::c" in str(doc_id):
                    return None  # a chunk id that does not exist
                family = self._chunk_family_rows(str(doc_id))
                if not family:
                    return None
                base = dict(family[0])
                base["text"] = "\n".join(
                    str(r.get("text") or "") for r in family
                )
                base["id"] = str(doc_id)
                base["chunk_count"] = len(family)
                return base
            except Exception as e:
                logger.debug(f"[KnowledgeVFS] vector fallback for {doc_id}: {e}")
                return None

        try:
            return await asyncio.to_thread(_fetch)
        except Exception:
            return None

    @staticmethod
    def _chunk_family_rows(doc_id: str) -> List[Dict[str, Any]]:
        """Every chunk of ``doc_id`` in chunk order (``[]`` when none).

        Scans the projected ``id``/``text`` columns and keeps rows whose id is
        ``{doc_id}::c<n>``; a handful of families exist per store, and this
        runs only for a parent id that has no row of its own."""
        try:
            from core.lancedb_handler import get_lancedb_handler

            handler = get_lancedb_handler("default")
            table = handler.get_table("documents") if handler is not None else None
            if table is None:
                return []
            prefix = f"{doc_id}::c"
            rows = (
                table.search()
                .select(["id", "text", "source", "metadata"])
                .to_arrow()
                .to_pylist()
            )
            family = []
            for r in rows:
                rid = str(r.get("id") or "")
                if not rid.startswith(prefix):
                    continue
                try:
                    order = int(rid[len(prefix):])
                except ValueError:
                    order = 0
                family.append((order, r))
            family.sort(key=lambda t: t[0])
            return [r for _, r in family]
        except Exception as e:  # noqa: BLE001 — reader must degrade, not raise
            logger.debug(f"[KnowledgeVFS] chunk family scan for {doc_id}: {e}")
            return []

    @staticmethod
    def _doc_meta(doc) -> Dict[str, Any]:
        kind, d = doc
        if kind == "ingested":
            return {
                "id": d.id, "source": "ingested", "file_name": d.file_name,
                "file_type": d.file_type, "integration_id": d.integration_id,
                "source_url": getattr(d, "source_url", None),
                "external_id": d.external_id,
            }
        if kind == "vector":
            meta = d.get("metadata") or {}
            return {
                "id": d.get("id"), "source": "vector",
                "file_name": meta.get("file_name") or meta.get("title"),
                "integration_id": (d.get("source") or "").split(":")[0] or None,
                "sensitivity": meta.get("sensitivity", "internal"),
                "bridged": False,
            }
        return {
            "id": d.id, "source": "knowledge", "title": getattr(d, "title", None),
            "doc_type": getattr(d, "doc_type", "text"),
            "sensitivity": getattr(d, "sensitivity", "internal"),
        }

    @staticmethod
    def _doc_text(doc) -> str:
        kind, d = doc
        if kind == "ingested":
            return getattr(d, "content_preview", "") or ""
        if kind == "vector":
            return str(d.get("text") or "")
        return getattr(d, "content", "") or ""
