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
        """Search across knowledge documents under ``path_prefix``.

        Overrides the base (which only scans one level of file nodes) because
        knowledge/documents/<id>/ are directories — we descend into each and
        scan its content.lines.
        """
        import re
        citations: List[VFSCitation] = []
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return citations
        # Enumerate document dirs under the prefix (or all if prefix is the root).
        # A root prefix ("/" or "") lists only the top-level category dirs, not
        # documents — retarget it at BOTH content trees so grep("/") finds hits
        # in documents and conversations alike.
        prefixes = [path_prefix]
        if path_prefix in ("/", "", "knowledge"):
            prefixes = ["knowledge/documents", "knowledge/conversations"]
        nodes: List[VFSNode] = []
        for prefix in prefixes:
            try:
                nodes.extend(await self.ls(prefix, ctx))
            except Exception:
                continue
        for node in nodes:
            if node.type != "dir":
                continue
            try:
                res = await self.cat(f"{node.path}/content.lines", ctx)
            except Exception:
                continue
            for i, line in enumerate(res.lines):
                if regex.search(line):
                    citations.append(VFSCitation(
                        path=res.path, line=i + 1, snippet=line[:200],
                    ))
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
                df = table.search().limit(200).to_df()
                return df.to_dict("records")
            except Exception:
                return []

        records = await asyncio.to_thread(_scan)
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
                safe = conv_id.replace("'", "''")
                df = table.search().where(f"id = '{safe}'").limit(1).to_df()
                rows = df.to_dict("records")
                return rows[0] if rows else None
            except Exception:
                return None

        return await asyncio.to_thread(_fetch)

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
