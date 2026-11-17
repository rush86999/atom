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

import json
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


def _normalized_freshness(value: Any) -> str:
    """Canonical form of a persisted freshness value (never guesses)."""
    return str(value or "").strip().lower()


def _is_explicitly_non_fresh(value: Any) -> bool:
    """True only for the shared durable non-fresh statuses.

    Reuses ``NON_FRESH_STATUSES`` (stale/outdated/removed/superseded) exactly
    as lexical search, export and the SQL freshness filter do. A missing value
    is the historical/legacy shape and stays readable; this is why a vector
    table without the ``freshness_status`` column keeps working.
    """
    from core.doc_freshness_service import NON_FRESH_STATUSES

    return _normalized_freshness(value) in NON_FRESH_STATUSES


def _normalized_metadata(value: Any) -> Dict[str, Any]:
    """Return metadata as a dict whether Arrow handed back a dict or JSON.

    LanceDB writes ``metadata`` as a serialized JSON string; Arrow/older
    tables can also surface it as text. ``_doc_meta`` used to call ``.get``
    directly, so a legitimate multi-chunk owner open crashed with
    ``'str' object has no attribute 'get'`` before serving a single chunk.
    Malformed/absent metadata degrades to ``{}`` rather than raising.
    """
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _chunk_parent_id(doc_id: Any) -> Optional[str]:
    """``X`` for a chunk id ``X::cN``; None for a parent/base id."""
    text = str(doc_id or "")
    if "::c" not in text:
        return None
    base = text.split("::c", 1)[0]
    return base or None


def _is_hidden_id(doc_id: Any, hidden_ids: set) -> bool:
    """True when an id (or its chunk-family parent) is durably non-fresh."""
    text = str(doc_id or "")
    if not text:
        return False
    if text in hidden_ids:
        return True
    base = _chunk_parent_id(text)
    return bool(base) and base in hidden_ids


def invalidate_knowledge_vfs_rows_cache() -> None:
    """Drop a registered knowledge provider's projected-read cache.

    Document producers/deleters must call this after changing the SQL or
    LanceDB documents store. ``invalidate_rows_cache`` already existed but
    only the communications pipeline used it; a later ``grep`` could keep
    serving pre-delete vector text for the 15s TTL, so a removed document
    still grounded an answer. No provider registered means no cache to drop.
    """
    try:
        from core.vfs_registry import get_provider

        provider = get_provider("knowledge")
        invalidate = getattr(provider, "invalidate_rows_cache", None)
        if callable(invalidate):
            invalidate()
    except Exception as exc:  # noqa: BLE001 — cache hygiene must not fail writes
        logger.debug(f"[KnowledgeVFS] cache invalidation skipped: {exc}")


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
            vec = await self._get_vector_doc(doc_id, ctx)
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
                        vec = await self._get_vector_doc(parts[2], ctx)
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
        # The durable SQL row is authoritative: a retained tombstone hides
        # its still-fresh vector mirror. This set is read on EVERY grep (not
        # cached), so a peer marking ``freshness_status='removed'`` denies the
        # text even when the 15s projected-row cache still holds the old row.
        # An unreadable SQL store is not evidence of freshness — fail closed.
        hidden_ids = self._sql_non_fresh_ids(ctx)
        if hidden_ids is None:
            logger.warning(
                "[KnowledgeVFS] document grep denied: SQL visibility "
                "unavailable")
            return []

        rows = await self._vector_rows(
            "documents", ["id", "text", "freshness_status"],
            limit=_DOCS_SCAN_LIMIT,
            workspace_id=self._workspace_id(ctx),
            drop_missing_columns=True,
        )
        citations: List[VFSCitation] = []
        vector_ids: set = set()
        for row in rows:
            doc_id = str(row.get("id") or "")
            text = str(row.get("text") or "")
            if not doc_id or not text:
                continue
            # Explicit vector freshness applies to the row (and its chunk
            # parent); only a tombstoned SQL id is stronger evidence hiding a
            # whole family, so both are checked before the text is scanned.
            if _is_explicitly_non_fresh(row.get("freshness_status")):
                continue
            if _is_hidden_id(doc_id, hidden_ids):
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
                ff = self._freshness_filter(IngestedDocument)
                if ff is not None:
                    q1 = q1.filter(ff)
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

    def _workspace_id(self, ctx) -> str:
        """Physical store selected for this read (back-compat default)."""
        ws = (ctx or {}).get("workspace_id")
        return str(ws) if ws else "default"

    def _freshness_filter(self, query_model):
        """Hide documents whose durable freshness status is non-fresh.

        Point reads (``cat``/``read_region``) previously ignored the same
        status search and export already enforce, so a deleted document's
        SQL tombstone (retained to keep its receipt/audit trail) stayed
        readable through ``knowledge/documents/<id>`` and could ground an
        answer. ``None`` keeps historical rows readable; only an explicit
        non-fresh value suppresses. Mirrors the lexical/search filter.
        """
        column = getattr(query_model, "freshness_status", None)
        if column is None:
            return None
        from sqlalchemy import or_

        from core.doc_freshness_service import NON_FRESH_STATUSES

        return or_(
            column.is_(None),
            ~column.in_(tuple(NON_FRESH_STATUSES)),
        )

    def _sql_non_fresh_ids(self, ctx) -> Optional[set]:
        """Durable tombstone ids for this workspace, or None when unreadable.

        ``None`` is deliberately distinct from an empty set: an unreadable
        authoritative store cannot prove a vector mirror is current, so every
        caller fails closed instead of treating "no rows read" as "no
        tombstones".
        """
        from core.doc_freshness_service import NON_FRESH_STATUSES
        from core.models import IngestedDocument

        try:
            with self._db() as db:
                q = db.query(IngestedDocument.id).filter(
                    IngestedDocument.freshness_status.in_(
                        tuple(NON_FRESH_STATUSES)))
                wf = self._workspace_filter(ctx, IngestedDocument)
                if wf is not None:
                    q = q.filter(wf)
                return {str(row[0]) for row in q.all()}
        except Exception as e:  # noqa: BLE001 — unreadable is not absence
            logger.warning(f"[KnowledgeVFS] SQL visibility unavailable: {e}")
            return None

    def _sql_point_state(self, doc_id: str, ctx):
        """Authoritative SQL visibility for one id.

        Returns ``("visible", ("ingested"|"knowledge", row))``,
        ``("hidden", None)`` for a retained tombstone, ``("absent", None)``
        when no SQL row exists in scope, or ``("error", None)`` when the
        authoritative store could not be read. Absence permits the historical
        vector-only fallback; an error does not (conservative source state).
        """
        from core.models import IngestedDocument, KnowledgeDocument

        try:
            with self._db() as db:
                q1 = db.query(IngestedDocument).filter(
                    IngestedDocument.id == str(doc_id))
                wf = self._workspace_filter(ctx, IngestedDocument)
                if wf is not None:
                    q1 = q1.filter(wf)
                d = q1.first()
                if d is not None:
                    # Deliberately inspect the status instead of filtering it
                    # out: the hidden tombstone is exactly what must stop the
                    # vector fallback from resurrecting deleted text.
                    if _is_explicitly_non_fresh(
                            getattr(d, "freshness_status", None)):
                        return ("hidden", None)
                    return ("visible", ("ingested", d))

                q2 = db.query(KnowledgeDocument).filter(
                    KnowledgeDocument.id == str(doc_id))
                wf2 = self._workspace_filter(ctx, KnowledgeDocument)
                if wf2 is not None:
                    q2 = q2.filter(wf2)
                d = q2.first()
                if d is not None:
                    return ("visible", ("knowledge", d))
                return ("absent", None)
        except Exception as e:  # noqa: BLE001 — unreadable is not absence
            logger.warning(f"[KnowledgeVFS] get {doc_id} failed: {e}")
            return ("error", None)

    async def _list_documents(self, ctx) -> List[VFSNode]:
        from core.models import IngestedDocument, KnowledgeDocument
        nodes: List[VFSNode] = []
        hidden_ids = self._sql_non_fresh_ids(ctx)
        sql_ok = hidden_ids is not None
        try:
            with self._db() as db:
                q1 = db.query(IngestedDocument)
                wf = self._workspace_filter(ctx, IngestedDocument)
                if wf is not None:
                    q1 = q1.filter(wf)
                ff = self._freshness_filter(IngestedDocument)
                if ff is not None:
                    q1 = q1.filter(ff)
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
            sql_ok = False
        # SQL unreadable → serving a vector-only row could surface a document
        # whose tombstone we simply could not see. Conservative = list none.
        if sql_ok:
            nodes.extend(await self._list_vector_documents(
                seen={n.name for n in nodes}, ctx=ctx, hidden_ids=hidden_ids))
        return nodes

    async def _list_vector_documents(
        self, seen: set, cap: int = 200,
        ctx: Optional[Dict[str, Any]] = None,
        hidden_ids: Optional[set] = None,
    ) -> List[VFSNode]:
        """Surface vector-only rows (no PG mirror) in ls output.

        The LanceDB documents table holds rows this provider could cat (via
        the vector fallback) but that ls never listed — historical connector
        ingests, mirror-write failures — so agents browsing the tree missed
        documents that search could still hit. Merge them, capped, skipping
        ids already listed from PG.

        The scan uses the caller's workspace store when one is present. It
        previously always read the ``default`` store, so a scoped user's
        ``ls`` could surface (and then ``cat``) another workspace's
        vector-only rows while the SQL half was correctly scoped.

        Rows marked non-fresh at the vector layer are hidden, and a still-
        fresh mirror whose durable SQL row is a tombstone (or is a chunk of
        one) is hidden too. Legacy rows with no explicit status stay listed.
        """
        import asyncio

        workspace_id = self._workspace_id(ctx)
        if hidden_ids is None:
            hidden_ids = self._sql_non_fresh_ids(ctx)
            if hidden_ids is None:
                return []

        def _scan():
            try:
                from core.lancedb_handler import get_lancedb_handler

                handler = get_lancedb_handler(workspace_id)
                if handler is None:
                    return [], {}
                return (
                    handler.list_document_heads("documents", limit=cap),
                    self._vector_freshness_map(handler),
                )
            except Exception as e:
                logger.debug(f"[KnowledgeVFS] vector head scan failed: {e}")
                return [], None

        heads, freshness = await asyncio.to_thread(_scan)
        if freshness is None:
            # The store exists but its status column could not be read; do not
            # advertise rows whose freshness is unknown.
            return []
        nodes: List[VFSNode] = []
        for head in heads:
            doc_id = str(head.get("id") or "")
            if not doc_id or doc_id in seen:
                continue
            if _is_hidden_id(doc_id, hidden_ids):
                continue
            if _is_explicitly_non_fresh(freshness.get(doc_id)):
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

    @staticmethod
    def _vector_freshness_map(handler: Any) -> Dict[str, Any]:
        """``{id: freshness_status}`` for a documents store, or ``{}``.

        Missing ``freshness_status`` (legacy table) or a handler without a
        table API yields ``{}`` — no evidence, so nothing is suppressed.
        A table that exists but raises propagates so the caller can fail
        closed rather than silently treat tombstones as current.
        """
        if not hasattr(handler, "get_table"):
            return {}
        table = handler.get_table("documents")
        if table is None:
            return {}
        columns = KnowledgeVFSProvider._available_columns(
            table, ["id", "freshness_status"])
        if "freshness_status" not in columns:
            return {}
        rows = table.search().select(columns).to_arrow().to_pylist()
        return {
            str(row.get("id") or ""): row.get("freshness_status")
            for row in rows if row.get("id") is not None
        }

    @staticmethod
    def _available_columns(table: Any, columns: List[str]) -> List[str]:
        """Requested columns that exist; unknown schema keeps the request.

        Older documents tables predate ``freshness_status``. Projecting only
        real columns avoids the unprojected fallback (vectors+metadata) while
        preserving the legacy row's readability.
        """
        try:
            schema = getattr(table, "schema", None)
            if schema is None:
                return list(columns)
            names = {field.name for field in schema}
            return [c for c in columns if c in names]
        except Exception:  # noqa: BLE001 — unknown schema is not a failure
            return list(columns)

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
        workspace_id: Optional[str] = None,
        drop_missing_columns: bool = False,
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

        cache_key = (
            store, tuple(columns), limit, workspace_id,
            bool(drop_missing_columns),
        )
        now = _time.monotonic()
        hit = self._rows_cache.get(cache_key)
        if hit and _VFS_ROWS_CACHE_TTL > 0 and now - hit[0] < _VFS_ROWS_CACHE_TTL:
            return hit[1]

        def _table():
            if store == "comms":
                return self._comms_table()
            from core.lancedb_handler import get_lancedb_handler

            handler = get_lancedb_handler(workspace_id or "default")
            return handler.get_table("documents") if handler is not None else None

        def _scan():
            table = _table()
            if table is None:
                return []
            cols = list(columns)
            if drop_missing_columns:
                cols = self._available_columns(table, cols)
                if not cols:
                    return []
            return list(
                self._stream_rows(table, cols, limit, _VFS_SCAN_BATCH)
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
        """Resolve one id with SQL authoritative for visibility.

        A retained SQL tombstone must stop the vector fallback: filtering the
        tombstone out of the SQL query and then falling through to a
        still-fresh LanceDB mirror is what resurrected deleted text. Store
        errors are conservative (deny), not absence.
        """
        state, sql_doc = self._sql_point_state(doc_id, ctx)
        if state in ("hidden", "error"):
            return None
        if state == "visible":
            return sql_doc

        # A direct ``<parent>::cN`` read has no SQL row of its own; the
        # parent's durable tombstone still governs the chunk family.
        parent = _chunk_parent_id(doc_id)
        if parent:
            parent_state, _ = self._sql_point_state(parent, ctx)
            if parent_state in ("hidden", "error"):
                return None

        # LanceDB fallback: vector-only rows (connector file ingests stamped
        # file_<ts>, manual uploads) have no PG row. Without this, search
        # surfaces them (bridged:false) but cat can never read them.
        rec = await self._get_vector_doc(doc_id, ctx)
        if rec is not None:
            return ("vector", rec)
        return None

    async def _get_vector_doc(self, doc_id: str,
                              ctx: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Fetch one document from the LanceDB ``documents`` table by id.

        CHUNK FAMILIES: a large file is stored as ``{parent}::c0, ::c1, …``
        (the pricing workbook attached to the F-5216 thread is 59 chunks), and
        the parent id has NO row of its own. Resolving only the exact id meant
        ``documents.cat('knowledge/documents/ext_…')`` returned nothing for
        every chunked file — so an agent could GREP a spreadsheet row (grep
        walks chunk rows) and then be unable to OPEN the file it found. The
        chunks are now assembled in order into the parent document.

        Explicit vector freshness is honored here too: point reads previously
        went through ``get_document_by_id``, which projects the row down to
        id/text/source/metadata/created_at and silently DROPPED the top-level
        ``freshness_status``, so a vector-only ``removed`` tombstone still
        cat'd its text. Rows/chunks marked non-fresh are not served; legacy
        rows with no status remain readable.
        """
        import asyncio

        def _fetch():
            try:
                from core.lancedb_handler import get_lancedb_handler

                handler = get_lancedb_handler(self._workspace_id(ctx))
                if handler is None:
                    return None
                table = self._documents_table(handler)
                if table is not None:
                    exact = self._vector_point_row(table, str(doc_id))
                    if exact is not None:
                        if _is_explicitly_non_fresh(
                                exact.get("freshness_status")):
                            return None
                        return exact
                else:
                    # Handlers without a table API (historical fakes/older
                    # shims) keep the point-read contract. Its status is
                    # looked up separately when the store exposes one.
                    exact = handler.get_document_by_id(
                        "documents", str(doc_id))
                    if exact is not None:
                        status_ok, status = self._vector_point_status(
                            handler, str(doc_id))
                        if not status_ok or _is_explicitly_non_fresh(status):
                            return None
                        exact = dict(exact)
                        exact["metadata"] = _normalized_metadata(
                            exact.get("metadata"))
                        return exact

                if "::c" in str(doc_id):
                    return None  # a chunk id that does not exist
                family = self._chunk_family_rows(str(doc_id), handler)
                family = [
                    r for r in family
                    if not _is_explicitly_non_fresh(r.get("freshness_status"))
                ]
                if not family:
                    return None
                base = dict(family[0])
                base["metadata"] = _normalized_metadata(base.get("metadata"))
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
    def _documents_table(handler: Any) -> Any:
        """The ``documents`` table when the handler exposes one, else None."""
        getter = getattr(handler, "get_table", None)
        if not callable(getter):
            return None
        return getter("documents")

    @staticmethod
    def _vector_point_row(table: Any, doc_id: str) -> Optional[Dict[str, Any]]:
        """One exact vector row, including top-level freshness.

        Projected to the point-read columns; ``freshness_status`` was the
        missing one. Metadata is normalized because stored/Arrow metadata can
        be a serialized JSON string.
        """
        columns = KnowledgeVFSProvider._available_columns(
            table,
            ["id", "text", "source", "metadata", "created_at",
             "freshness_status"],
        )
        arrow = table.to_arrow().select(columns)
        rows = None
        if hasattr(arrow, "column") and hasattr(arrow, "filter"):
            try:
                import pyarrow.compute as pc

                rows = arrow.filter(
                    pc.equal(arrow.column("id"), str(doc_id))).to_pylist()
            except Exception:  # noqa: BLE001 — fall back to a Python filter
                rows = None
        if rows is None:
            rows = [
                r for r in arrow.to_pylist()
                if str(r.get("id") or "") == str(doc_id)
            ]
        if not rows:
            return None
        row = dict(rows[0])
        row["metadata"] = _normalized_metadata(row.get("metadata"))
        return row

    @staticmethod
    def _vector_point_status(handler: Any, doc_id: str):
        """``(readable, freshness_status)`` for the point-read fallback.

        No table API or no ``freshness_status`` column means no evidence and
        the historical row stays readable. A status read that RAISES returns
        ``(False, None)`` so the caller fails closed instead of serving text
        whose tombstone state could not be verified.
        """
        if not hasattr(handler, "get_table"):
            return (True, None)
        try:
            table = handler.get_table("documents")
            if table is None:
                return (True, None)
            columns = KnowledgeVFSProvider._available_columns(
                table, ["id", "freshness_status"])
            if "freshness_status" not in columns:
                return (True, None)
            rows = table.search().select(columns).to_arrow().to_pylist()
            for row in rows:
                if str(row.get("id") or "") == str(doc_id):
                    return (True, row.get("freshness_status"))
            return (True, None)
        except Exception as e:  # noqa: BLE001 — unreadable is not fresh
            logger.debug(
                f"[KnowledgeVFS] freshness read for {doc_id} failed: {e}")
            return (False, None)

    @staticmethod
    def _chunk_family_rows(doc_id: str,
                           handler: Any = None) -> List[Dict[str, Any]]:
        """Every chunk of ``doc_id`` in chunk order (``[]`` when none).

        Scans the projected ``id``/``text`` columns and keeps rows whose id is
        ``{doc_id}::c<n>``; a handful of families exist per store, and this
        runs only for a parent id that has no row of its own. ``handler`` is
        the caller's already-workspace-scoped store; the default fallback is
        only for historical direct callers.

        ``freshness_status`` is requested only when the table has it, so a
        legacy chunk store still opens. Chunk ordering is numeric (``c10``
        after ``c2``), which is also the order the parent text is assembled.
        """
        try:
            if handler is None:
                from core.lancedb_handler import get_lancedb_handler

                handler = get_lancedb_handler("default")
            table = handler.get_table("documents") if handler is not None else None
            if table is None:
                return []
            prefix = f"{doc_id}::c"
            columns = KnowledgeVFSProvider._available_columns(
                table, ["id", "text", "source", "metadata",
                        "freshness_status"])
            rows = (
                table.search()
                .select(columns)
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
            meta = _normalized_metadata(d.get("metadata"))
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
