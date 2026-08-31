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
        for i, line in enumerate((text or "").split("\n")):
            if regex.search(line):
                out.append(VFSCitation(path=path, line=i + 1, snippet=line[:200]))
        return out

    async def _grep_documents(self, regex, ctx) -> List[VFSCitation]:
        """Regex-scan served document text: vector full text first (what cat
        serves), PG preview / KnowledgeDocument content for rows with no
        vector text. Two batched queries, no per-doc reads."""
        import asyncio

        def _scan_vector():
            try:
                from core.lancedb_handler import get_lancedb_handler

                handler = get_lancedb_handler("default")
                if handler is None:
                    return []
                table = handler.get_table("documents")
                if table is None:
                    return []
                return (
                    table.to_arrow()
                    .select(["id", "text"])
                    .slice(0, 1000)
                    .to_pylist()
                )
            except Exception as e:
                logger.debug(f"[KnowledgeVFS] grep vector scan failed: {e}")
                return []

        citations: List[VFSCitation] = []
        vector_ids: set = set()
        rows = await asyncio.to_thread(_scan_vector)
        for row in rows:
            doc_id = str(row.get("id") or "")
            text = str(row.get("text") or "")
            if not doc_id or not text:
                continue
            vector_ids.add(doc_id)
            citations.extend(
                self._cites_for_text(regex, f"knowledge/documents/{doc_id}", text)
            )

        try:
            from core.models import IngestedDocument, KnowledgeDocument

            with self._db() as db:
                q1 = db.query(IngestedDocument)
                wf = self._workspace_filter(ctx, IngestedDocument)
                if wf is not None:
                    q1 = q1.filter(wf)
                for d in q1.yield_per(500):
                    if d.id in vector_ids:
                        continue
                    citations.extend(
                        self._cites_for_text(
                            regex,
                            f"knowledge/documents/{d.id}",
                            getattr(d, "content_preview", "") or "",
                        )
                    )
                q2 = db.query(KnowledgeDocument)
                wf2 = self._workspace_filter(ctx, KnowledgeDocument)
                if wf2 is not None:
                    q2 = q2.filter(wf2)
                for d in q2.yield_per(500):
                    if d.id in vector_ids:
                        continue
                    citations.extend(
                        self._cites_for_text(
                            regex,
                            f"knowledge/documents/{d.id}",
                            getattr(d, "content", "") or "",
                        )
                    )
        except Exception as e:
            logger.warning(f"[KnowledgeVFS] grep PG scan failed: {e}")
        return citations

    async def _grep_conversations(self, regex, cap: int = 200) -> List[VFSCitation]:
        import asyncio

        def _scan():
            table = self._comms_table()
            if table is None:
                return []
            try:
                # head(), NOT to_arrow(): the comms table carries two vector
                # columns over 20k+ rows — materializing it whole costs minutes
                # of IO for data we never read. First `cap` rows suffice.
                return (
                    table.head(cap)
                    .select(["id", "content"])
                    .to_pylist()
                )
            except Exception:
                return []

        try:
            rows = await asyncio.wait_for(asyncio.to_thread(_scan), timeout=_COMMS_TIMEOUT_S)
        except asyncio.TimeoutError:
            logger.warning(
                "[KnowledgeVFS] comms scan timed out after %ss — skipping conversations leg",
                _COMMS_TIMEOUT_S,
            )
            rows = []
        citations: List[VFSCitation] = []
        for row in rows:
            cid = str(row.get("id") or "")
            if cid:
                citations.extend(
                    self._cites_for_text(
                        regex, f"knowledge/conversations/{cid}", str(row.get("content") or "")
                    )
                )
        return citations

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
        """LanceDB atom_communications table, or None when unavailable."""
        try:
            from integrations.atom_communication_ingestion_pipeline import (
                get_ingestion_pipeline,
            )
            pipeline = get_ingestion_pipeline("default")
            manager = getattr(pipeline, "memory_manager", None)
            table = getattr(manager, "connections_table", None)
            if table is None and manager is not None and getattr(manager, "db", None):
                manager.initialize()
                table = getattr(manager, "connections_table", None)
            return table
        except Exception as e:
            logger.debug(f"[KnowledgeVFS] comms table unavailable: {e}")
            return None

    async def _list_conversations(self, ctx) -> List[VFSNode]:
        import asyncio
        nodes: List[VFSNode] = []

        def _scan():
            table = self._comms_table()
            if table is None:
                return []
            try:
                # head(), NOT search(): a queryless kNN over the 20k-row
                # comms table costs seconds per call and needs no vector here.
                return (
                    table.head(200)
                    .select(["id", "timestamp"])
                    .to_pylist()
                )
            except Exception:
                return []

        try:
            records = await asyncio.wait_for(asyncio.to_thread(_scan), timeout=_COMMS_TIMEOUT_S)
        except asyncio.TimeoutError:
            logger.warning(
                "[KnowledgeVFS] comms scan timed out after %ss — no conversations listed",
                _COMMS_TIMEOUT_S,
            )
            records = []
        for rec in records:
            cid = str(rec.get("id") or "")
            if cid:
                nodes.append(VFSNode(
                    name=cid, type="dir", path=f"knowledge/conversations/{cid}",
                    modified=str(rec.get("timestamp") or None),
                ))
        return nodes

    async def _get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        import asyncio

        def _fetch():
            table = self._comms_table()
            if table is None:
                return None
            try:
                # ls only ever surfaces the first 200 ids, so a scan of the
                # first 2000 rows resolves any id the VFS can offer — without
                # materializing the full 20k-row table (9s+ with vector cols).
                head = table.head(2000).select(["id", "app_type", "timestamp", "content"])
                ids = head.column("id").to_pylist()
                if conv_id in ids:
                    return head.to_pylist()[ids.index(conv_id)]
            except Exception:
                pass
            # Fallback for ids beyond the head window: the original kNN path.
            try:
                safe = conv_id.replace("'", "''")
                df = table.search().where(f"id = '{safe}'").limit(1).to_df()
                r = df.to_dict("records")
                return r[0] if r else None
            except Exception:
                return None

        try:
            return await asyncio.wait_for(asyncio.to_thread(_fetch), timeout=_COMMS_TIMEOUT_S)
        except asyncio.TimeoutError:
            logger.warning(
                "[KnowledgeVFS] comms fetch timed out after %ss — conversation unreadable",
                _COMMS_TIMEOUT_S,
            )
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
