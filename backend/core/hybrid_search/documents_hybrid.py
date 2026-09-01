"""DocumentsHybridSearch — vector + BM25 lexical legs fused by RRF.

Phase 1 documents leg of the multi-source hybrid search service. Follow-ups
(episodes / turn_facts / reasoning-steps legs) implement the same contract:
each leg returns a ranked list of ``{source, id, ...}`` dicts and the fusion
layer merges them by Reciprocal Rank Fusion (RRF, k=60).

Vector leg: LanceDB ``documents`` table (1536-dim, via ``LanceDBHandler.search``
which embeds with the write-path embedder). Lexical leg: FTS5/tsvector BM25
(``search_documents_lexical``). Join-key bridge: a vector hit whose ``id``
resolves to an ``IngestedDocument`` row is hydrated from PG (VFS-citable path);
unresolvable (vector-only: connector file ingests, manual uploads) hits are
STILL RETURNED flagged ``bridged:false`` (title from LanceDB metadata) so
ingested-but-PG-less data stays searchable.

Degradation ladder: ``bm25_vector_rrf`` | ``lexical_only`` | ``semantic_only`` |
``no_results``. Never raises.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

RRF_K = 60
_VECTOR_LIMIT_MULTIPLIER = 3


def _vector_leg_enabled() -> bool:
    return os.getenv("ATOM_HYBRID_VECTOR_LEG_ENABLED", "true").lower() == "true"


class DocumentsHybridSearch:
    """Hybrid document search service (documents leg)."""

    def __init__(self, db: Any = None, lancedb: Any = None):
        self._db = db
        self._lancedb = lancedb

    # -- public API -----------------------------------------------------------

    async def search(
        self,
        query: str,
        limit: int = 10,
        since: Optional[datetime] = None,
        source: Optional[str] = None,
        author: Optional[str] = None,
        owner_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        query = (query or "").strip()
        if len(query) < 3:
            return self._response(query, [], "no_results", stats={})

        stats: Dict[str, Any] = {}
        try:
            lexical, vector = await asyncio.gather(
                asyncio.to_thread(
                    self._lexical_leg, query, limit, since, source, author
                ),
                self._vector_leg(query, limit, source),
            )
        except Exception as e:
            logger.error("DocumentsHybridSearch.search failed: %s", e)
            return self._response(query, [], "no_results", stats={})

        stats["lexical_hits"] = len(lexical)
        stats["vector_hits"] = len(vector)

        fused, unbridged = self._fuse_rrf(lexical, vector)
        stats["unbridged_hits"] = unbridged

        has_lexical = any("lexical" in e["legs"] for e in fused)
        has_vector = any("vector" in e["legs"] for e in fused)
        if has_lexical and has_vector:
            label = "bm25_vector_rrf"
        elif has_lexical:
            label = "lexical_only"
        elif has_vector:
            label = "semantic_only"
        else:
            label = "no_results"

        results = self._hydrate(fused)

        # Conversations leg (P1.3 first slice — bridge, don't copy): search the
        # communication memory store (emails/Slack/WhatsApp/Teams/Telegram,
        # vector+FTS) and append its top hits as first-class results. The comms
        # record IS the source of truth — nothing is duplicated into documents.
        # Skipped when the caller filtered to a specific document source.
        conv_results: List[Dict[str, Any]] = []
        from core.experiments import is_enabled as _exp_enabled
        if not source and _exp_enabled("memory_conversations_leg"):
            conv_results = await self._conversations_leg(
                query, max(2, limit // 3), owner_user_id=owner_user_id
            )
            stats["conversation_hits"] = len(conv_results)
            label = f"{label}+conversations" if (results or conv_results) and label != "no_results" else (label if label != "no_results" else "conversations_only")
            if conv_results:
                # First-class, not leftovers: reserve slots for the conversation
                # hits so the limit-cut below can't drop them all when doc legs
                # return plenty (that hid ingested email from chat entirely).
                doc_budget = max(limit - len(conv_results), 0)
                results = results[:doc_budget] + conv_results

        return self._response(query, results[:limit], label, stats)

    async def _conversations_leg(
        self, query: str, limit: int, owner_user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Hybrid search over the communication memory store.

        owner_user_id enforces the mailbox-ownership boundary on the shared
        comms corpus (see search_communications); None means unfiltered.
        """
        try:
            from integrations.atom_communication_ingestion_pipeline import (
                get_ingestion_pipeline,
            )

            def _search():
                pipeline = get_ingestion_pipeline("default")
                manager = getattr(pipeline, "memory_manager", pipeline)
                # Lazy init: a fresh singleton hasn't opened its LanceDB table yet.
                if getattr(manager, "connections_table", None) is None and hasattr(manager, "initialize"):
                    manager.initialize()
                if getattr(manager, "connections_table", None) is None:
                    return []
                return manager.search_communications(
                    query[:500], limit, owner_user_id=owner_user_id
                )

            records = await asyncio.to_thread(_search)
        except Exception as e:
            logger.debug("conversations leg unavailable: %s", e)
            return []
        out: List[Dict[str, Any]] = []
        for rec in records or []:
            content = str(rec.get("content") or rec.get("text") or "").strip()
            cid = str(rec.get("id") or "")
            if not content or not cid:
                continue
            out.append({
                "id": cid,
                "source": "communication",
                "title": f"{rec.get('app_type', 'message')} — {str(rec.get('timestamp', ''))[:10]}",
                "preview": content[:200],
                "modified": None,
                "bridged": True,
                "legs": ["conversations"],
                "score": 0.0,
                # Attribution (Phase 1): email-derived hits carry who + when so
                # the knowledge leg can render sender + recency — never a bare
                # blob from an attacker-controlled inbox.
                "sender": rec.get("sender_email") or rec.get("sender"),
                "as_of": str(rec.get("timestamp", ""))[:10] or None,
            })
        return out

    # -- legs -----------------------------------------------------------------

    def _get_db(self) -> Any:
        if self._db is not None:
            return self._db
        from core.database import get_db_session

        return get_db_session()

    def _lexical_leg(
        self,
        query: str,
        limit: int,
        since: Optional[datetime],
        source: Optional[str],
        author: Optional[str],
    ) -> List[Dict[str, Any]]:
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        with self._get_db() as db:
            return search_documents_lexical(
                db, query, limit=limit * _VECTOR_LIMIT_MULTIPLIER, since=since, source=source, author=author
            )

    async def _vector_leg(self, query: str, limit: int, source: Optional[str] = None) -> List[Dict[str, Any]]:
        # Kill-switch: hermetic tests + embedding-cost control. Flag off → the
        # service degrades to the lexical leg (label "lexical_only").
        if not _vector_leg_enabled():
            return []
        # The vector store (LanceDB `documents` table) only holds ingested-doc
        # rows — hydration bridges exclusively to IngestedDocument. Surfacing
        # those hits in a source="knowledge" search violates the filter (an
        # ingested doc returned for a knowledge-only query); skip the leg.
        if source and str(source).strip().lower() == "knowledge":
            return []
        try:
            lancedb = self._lancedb
            if lancedb is None:
                from core.lancedb_handler import get_lancedb_handler

                lancedb = get_lancedb_handler("default")
            if lancedb is None:
                return []
            # to_thread: LanceDBHandler.search embeds via sync embed_text, which
            # no-ops in the event-loop thread (async-context guard).
            rows = await asyncio.to_thread(
                lancedb.search, "documents", query, limit=limit * _VECTOR_LIMIT_MULTIPLIER
            )
            return [
                {
                    "id": str(r.get("id") or ""),
                    "score": float(r.get("_distance", 1.0)),
                    "metadata": r.get("metadata") or {},
                }
                for r in rows
                if r.get("id")
            ]
        except Exception as e:
            logger.warning("DocumentsHybridSearch vector leg failed: %s", e)
            return []

    # -- fusion + hydration ---------------------------------------------------

    def _fuse_rrf(
        self,
        lexical: List[Dict[str, Any]],
        vector: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], int]:
        """RRF over both legs, keyed by (source, id).

        Vector ids that resolve to an ``IngestedDocument`` row are hydrated
        from PG and flagged ``bridged:true``. Vector-only rows (connector file
        ingests, manual uploads — no PG row) are STILL RETURNED, flagged
        ``bridged:false``, with title/preview derived from LanceDB metadata —
        dropping them made every vector-only ingest invisible to search.
        Returns ``(fused, unbridged_count)``."""
        scores: Dict[tuple, Dict[str, Any]] = {}
        unbridged = 0

        for rank, hit in enumerate(lexical, start=1):
            key = (hit["source"], hit["id"])
            entry = scores.setdefault(
                key,
                {
                    "source": hit["source"],
                    "id": hit["id"],
                    "title": hit.get("title"),
                    "preview": hit.get("preview"),
                    "modified": hit.get("modified"),
                    "bridged": True,
                    "rrf": 0.0,
                    "legs": [],
                },
            )
            entry["rrf"] += 1.0 / (RRF_K + rank)
            entry["legs"].append("lexical")

        try:
            with self._get_db() as db:
                from core.models import IngestedDocument

                vector_ids = [v["id"] for v in vector]
                pg_rows = {}
                if vector_ids:
                    rows = (
                        db.query(IngestedDocument)
                        .filter(IngestedDocument.id.in_(vector_ids))
                        .all()
                    )
                    pg_rows = {d.id: d for d in rows}
        except Exception as e:
            logger.warning("DocumentsHybridSearch hydration lookup failed: %s", e)
            pg_rows = {}

        for rank, hit in enumerate(vector, start=1):
            doc = pg_rows.get(hit["id"])
            if doc is None:
                unbridged += 1
                meta = hit.get("metadata") or {}
                title = (
                    meta.get("file_name")
                    or meta.get("title")
                    or meta.get("filename")
                    or str(hit["id"])
                )
                preview = str(meta.get("preview") or meta.get("content") or "")[:200]
                entry = {
                    "source": "vector",
                    "id": hit["id"],
                    "title": title,
                    "preview": preview,
                    "modified": None,
                    "bridged": False,
                    "rrf": 1.0 / (RRF_K + rank),
                    "legs": ["vector"],
                }
                scores.setdefault(("vector", hit["id"]), entry)
                continue
            key = ("ingested", hit["id"])
            entry = scores.setdefault(
                key,
                {
                    "source": "ingested",
                    "id": hit["id"],
                    "title": doc.file_name,
                    "preview": (doc.content_preview or "")[:200],
                    "modified": doc.external_modified_at.isoformat()
                    if doc.external_modified_at
                    else None,
                    "bridged": True,
                    "rrf": 0.0,
                    "legs": [],
                    "freshness_status": getattr(doc, "freshness_status", None),
                },
            )
            entry["rrf"] += 1.0 / (RRF_K + rank)
            entry["legs"].append("vector")

        fused = sorted(scores.values(), key=lambda e: (-e["rrf"], len(e["legs"])))
        return fused, unbridged

    def _hydrate(self, fused: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "source": e["source"],
                "id": e["id"],
                "title": e["title"],
                "preview": e["preview"],
                "score": round(e["rrf"], 6),
                "modified": e["modified"],
                "bridged": e["bridged"],
                "freshness_status": e.get("freshness_status"),
                "sender": e.get("sender"),
                "as_of": e.get("as_of"),
            }
            for e in fused
        ]

    @staticmethod
    def _response(
        query: str,
        results: List[Dict[str, Any]],
        label: str,
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "query": query,
            "results": results,
            "hybrid": label,
            "stats": stats,
        }
