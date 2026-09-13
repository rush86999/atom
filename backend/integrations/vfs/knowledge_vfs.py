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

from core.vfs_base import VFSCitation, VFSNode, VFSProvider, VFSResource, to_line_numbered

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
#: arrive in bursts within one agent turn; each uncached read materializes
#: the full LanceDB table through the ``to_arrow`` fallback because the
#: ``lance`` projection package is not in this build (~3s + 3 GB transient
#: for the comms store). Short TTL keeps fresh ingests visible quickly.
#: 0 disables caching. Env: ATOM_VFS_ROWS_CACHE_TTL seconds.
import os as _os

_VFS_ROWS_CACHE_TTL = float(
    _os.getenv("ATOM_VFS_ROWS_CACHE_TTL", "15") or 15
)



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
            regex = re.compile(pattern, re.IGNORECASE)
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
        nodes: List[VFSNode] = []
        for rec in rows:
            cid = str(rec.get("id") or "")
            if cid:
                nodes.append(VFSNode(
                    name=cid,
                    type="file",  # one leaf: content.lines (no sub-directory)
                    path=f"knowledge/conversations/{cid}",
                    size=len(str(rec.get("content") or "")),
                    modified=str(rec.get("timestamp") or None) or None,
                    meta={
                        "sender": str(rec.get("sender") or ""),
                        "subject": str(rec.get("subject") or ""),
                    },
                ))
        total = self._comms_total()
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

    def _comms_total(self) -> int:
        """Row count of the comms store (0 when unknown) — lets a listing say
        what it is NOT showing instead of silently truncating."""
        try:
            table = self._comms_table()
            if table is None:
                return 0
            return int(table.count_rows())
        except Exception:
            return 0

    def _comms_projected_arrow(self, table, columns):
        """Arrow table with ONLY ``columns``, lowest-memory route available.

        ``to_lance().to_table(columns=…)`` is true column projection, but the
        optional ``lance`` package is not installed in this build, so the
        fallback is ``to_arrow()`` followed IMMEDIATELY by ``select`` — which
        still materializes the 384-dim vector columns (~3 KB/row, 3.0 GB for
        the 7k-row store) plus ``metadata`` (median 49 KB/row, 33 MB max) for
        a moment. Hence the projection is mandatory at every call site: the
        measured alternative (selecting columns off the full table) is 0.7s
        and multigigabyte, versus 0.01s and 1.6 MB for the projected form.
        """
        projected = None
        try:
            lance_table = table.to_lance()
            projected = lance_table.to_table(columns=list(columns))
        except Exception:
            projected = None
        if projected is None:
            projected = table.to_arrow()
        try:
            return projected.select(list(columns))
        except Exception:
            return projected

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
        calls arrive in bursts (grep → cat → ls in one turn), and every
        uncached call re-materializes the full table through the ``to_arrow``
        fallback (~3s and 3 GB transient for the comms store — ``lance`` is
        not in this build). Short TTL keeps a just-ingested message visible
        almost immediately; 0 disables."""
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
            tbl = self._projected_arrow(table, columns)
            if limit is not None:
                try:
                    tbl = tbl.slice(0, limit)
                except Exception:
                    pass
            return tbl.to_pylist()

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
        return self._comms_projected_arrow(table, columns)

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
        """Fetch one row from the LanceDB ``documents`` table by id."""
        import asyncio

        def _fetch():
            try:
                from core.lancedb_handler import get_lancedb_handler

                handler = get_lancedb_handler("default")
                if handler is None:
                    return None
                return handler.get_document_by_id("documents", str(doc_id))
            except Exception as e:
                logger.debug(f"[KnowledgeVFS] vector fallback for {doc_id}: {e}")
                return None

        try:
            return await asyncio.to_thread(_fetch)
        except Exception:
            return None

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
