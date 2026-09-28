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

Degradation ladder (the ``hybrid`` label): ``bm25_vector_rrf`` |
``lexical_only`` | ``semantic_only`` | ``no_results``. That label answers
"which legs contributed ranked hits" and is NOT a statement about coverage —
a healthy corpus with no lexical matches and a corpus whose lexical leg threw
both read ``lexical_only``.

Coverage is the ``status`` field, and it is what callers must branch on:

    success  the intended search ran to completion inside its declared
             coverage; zero matches is a legitimate answer
    partial  usable evidence was returned, but at least one ENABLED leg (or
             the hydration/identity resolution) was unavailable or truncated
    failed   required retrieval produced no usable evidence

Every leg that ran, was skipped, or failed is reported individually under
``legs`` with its own status, error CATEGORY (never a raw ``str(e)`` — it
reaches the model and the user), hit count and duration, so a failed leg can
never again be indistinguishable from a successful zero-match one. Optional
legs disabled by configuration report ``skipped``, never ``failed``.
Ranking degradation (a reranker fallback) is reported under ``ranking`` and
is deliberately NOT coverage.

Never raises.

``error_category`` below is the shared, non-leaking failure vocabulary: the
workbook artifact scan classifies its own unreadable sources through it, so a
damaged parquet is reported with the same words as a broken search leg instead
of a raw ``str(e)``.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

RRF_K = 60
_VECTOR_LIMIT_MULTIPLIER = 3

STATUS_SUCCESS = "success"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"

LEG_OK = "ok"
LEG_FAILED = "failed"
LEG_SKIPPED = "skipped"

ERROR_TIMEOUT = "timeout"
ERROR_UNAVAILABLE = "source_unavailable"
ERROR_PERMISSION = "access_denied"
ERROR_MISSING = "source_missing"
ERROR_CONFIGURATION = "configuration"
ERROR_CORRUPT = "source_corrupt"
ERROR_UNKNOWN = "unknown"


class _LegSkipped(Exception):
    """A leg that configuration deliberately did not run.

    Distinct from a failure on purpose: an optional leg switched off is
    ``skipped``, so a caller reading coverage can tell "we chose not to look
    here" from "we looked here and could not".
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _skipped_leg(reason: str) -> Dict[str, Any]:
    return {
        "status": LEG_SKIPPED,
        "required": False,
        "error_category": None,
        "skip_reason": reason,
        "hit_count": 0,
        "duration_ms": 0.0,
    }


# Signatures of a source file that is present but not readable AS ITS OWN
# FORMAT. Shared with the workbook artifact scan, which hits the same wall on
# a damaged parquet ("Parquet magic bytes not found in footer") — that text
# matched no branch below and fell through to ``unknown``, which reads as "we
# do not know why" instead of "the bytes are damaged".
_CORRUPTION_MARKERS = (
    "corrupt",
    "magic bytes",
    "not a parquet file",
    "invalid footer",
    "malformed",
    "not a database",
    "disk image",
    "checksum",
    "unexpected end of",
    "parquet file size",
)

# Exception CLASSES raised by the columnar-format readers a materialized sheet
# is read through. They raise only for data their own format cannot accept, so
# a failure from one is a damaged source by definition — and the wording varies
# too much to match on text alone ("Parquet file size is 3 bytes, smaller than
# the minimum file footer" carries none of the usual corruption words).
_FORMAT_READER_NAMES = ("arrow", "parquet", "fastparquet", "orc")


def error_category(exc: BaseException) -> str:
    """Stable, non-leaking category for a retrieval failure.

    The raw message can carry connection strings, file paths, row contents or
    provider payloads, and it is rendered into model-visible and user-visible
    text. Only the class is classified here; the message stays in the log at
    debug level for the operator.

    Public because the vocabulary is the contract, not an implementation
    detail of this leg: any producer that must report "the source could not be
    read" without leaking ``str(exc)`` classifies through here.
    """
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return ERROR_TIMEOUT
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if isinstance(exc, (PermissionError,)) or "access denied" in text or "not authorized" in text:
        return ERROR_PERMISSION
    if isinstance(exc, (FileNotFoundError,)) or "no such table" in text or "does not exist" in text:
        return ERROR_MISSING
    if "sqlite3" in name and any(k in text for k in _CORRUPTION_MARKERS):
        return ERROR_CORRUPT
    if isinstance(exc, (ConnectionError, OSError)) or "connection" in text or "unreachable" in text:
        return ERROR_UNAVAILABLE
    if isinstance(exc, (ImportError, ModuleNotFoundError, AttributeError, TypeError)):
        return ERROR_CONFIGURATION
    if any(marker in text for marker in _CORRUPTION_MARKERS):
        return ERROR_CORRUPT
    if any(marker in name for marker in _FORMAT_READER_NAMES):
        return ERROR_CORRUPT
    return ERROR_UNKNOWN


# Private alias kept so the in-module call sites (and any importer written
# against the previous name) keep working.
_error_category = error_category


def _coerce_metadata(raw: Any) -> Dict[str, Any]:
    """LanceDB metadata arrives as a dict or a JSON string depending on writer."""
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def _parent_doc_id(hit_id: str) -> str:
    """``<doc_id>::cN`` chunk ids resolve to their parent document id."""
    if "::" in hit_id:
        return hit_id.split("::", 1)[0]
    return ""


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
            return self._response(
                query, [], "no_results", stats={},
                legs={name: _skipped_leg(reason="query_too_short")
                      for name in ("lexical", "vector", "conversations")},
            )

        legs: Dict[str, Dict[str, Any]] = {}

        lexical, _ = await self._run_leg(
            "lexical",
            lambda: asyncio.to_thread(
                self._lexical_leg, query, limit, since, source, author
            ),
            legs,
            required=True,
        )
        vector, _ = await self._run_leg(
            "vector",
            lambda: self._vector_leg(query, limit, source),
            legs,
            required=False,
        )
        if legs["vector"]["status"] != LEG_SKIPPED:
            legs["vector"]["required"] = _vector_leg_enabled()

        stats: Dict[str, Any] = {
            "lexical_hits": len(lexical),
            "vector_hits": len(vector),
        }

        fused, unbridged = self._fuse_rrf(lexical, vector, legs=legs)
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

        conv_results: List[Dict[str, Any]] = []
        from core.experiments import is_enabled as _exp_enabled
        conv_on = bool(not source and _exp_enabled("memory_conversations_leg"))
        if conv_on:
            conv_results, _ = await self._run_leg(
                "conversations",
                lambda: self._conversations_leg(
                    query, max(2, limit // 3), owner_user_id=owner_user_id
                ),
                legs,
                required=False,
            )
            stats["conversation_hits"] = len(conv_results)
            label = (
                f"{label}+conversations"
                if (results or conv_results) and label != "no_results"
                else (label if label != "no_results" else "conversations_only")
            )
            if conv_results:
                doc_budget = max(limit - len(conv_results), 0)
                results = results[:doc_budget] + conv_results
        else:
            legs["conversations"] = _skipped_leg(
                reason="source_filtered" if source else "experiment_disabled"
            )

        status = self._coverage_status(legs, results or conv_results)
        return self._response(
            query, results[:limit], label, stats, legs=legs, status=status
        )

    @staticmethod
    def _coverage_status(
        legs: Dict[str, Dict[str, Any]], evidence: List[Dict[str, Any]]
    ) -> str:
        """success / partial / failed from per-leg outcomes, never from counts.

        The trap this replaces: a corpus that legitimately matches nothing and
        a corpus whose required leg threw both produced ``results == []`` and a
        ``lexical_only``-style label, so every consumer read a failed search as
        a successful one that found nothing — and an absence claim built on it
        was a fabricated claim.
        """
        failed_required = [
            name for name, leg in legs.items()
            if leg["status"] == LEG_FAILED and leg.get("required")
        ]
        failed_optional = [
            name for name, leg in legs.items()
            if leg["status"] == LEG_FAILED and not leg.get("required")
        ]
        if not failed_required and not failed_optional:
            return STATUS_SUCCESS
        if evidence:
            return STATUS_PARTIAL
        return STATUS_FAILED if failed_required else STATUS_PARTIAL

    async def _run_leg(
        self,
        name: str,
        call: Any,
        legs: Dict[str, Dict[str, Any]],
        *,
        required: bool,
    ) -> tuple[List[Dict[str, Any]], Optional[BaseException]]:
        """Run one retrieval leg, recording its own outcome.

        A failing leg never discards a healthy sibling: the exception is
        captured as a leg outcome and the empty result is returned to the
        fusion layer, which still sees the legs that worked.
        """
        started = time.monotonic()
        try:
            rows = await call()
        except _LegSkipped as skip:
            legs[name] = {
                "status": LEG_SKIPPED,
                "required": False,
                "error_category": None,
                "skip_reason": skip.reason,
                "hit_count": 0,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
            }
            return [], None
        except Exception as exc:  # noqa: BLE001 — recorded, never propagated
            category = _error_category(exc)
            logger.warning(
                "DocumentsHybridSearch %s leg failed (%s): %r", name, category, exc
            )
            legs[name] = {
                "status": LEG_FAILED,
                "required": required,
                "error_category": category,
                "hit_count": 0,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
            }
            return [], exc
        rows = list(rows or [])
        legs[name] = {
            "status": LEG_OK,
            "required": required,
            "error_category": None,
            "hit_count": len(rows),
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
        }
        return rows, None

    async def _conversations_leg(
        self, query: str, limit: int, owner_user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Hybrid search over the communication memory store.

        owner_user_id enforces the mailbox-ownership boundary on the shared
        comms corpus (see search_communications); None means unfiltered.
        """
        from integrations.atom_communication_ingestion_pipeline import (
            get_ingestion_pipeline,
        )

        def _search() -> List[Dict[str, Any]]:
            pipeline = get_ingestion_pipeline("default")
            manager = getattr(pipeline, "memory_manager", pipeline)
            # Lazy init: a fresh singleton hasn't opened its LanceDB table yet.
            if getattr(manager, "connections_table", None) is None and hasattr(manager, "initialize"):
                manager.initialize()
            if getattr(manager, "connections_table", None) is None:
                raise RuntimeError("communication store table is not open")
            # Bounded decomposition, not a head cut: a long constraint-bearing
            # turn used to lose every identifier past character 500 here, and
            # the store reported zero matches for the part it never saw.
            from core.identifier_search import bounded_query_variants

            records: List[Dict[str, Any]] = []
            seen_ids: set = set()
            for variant in bounded_query_variants(query, max_chars=500):
                for rec in manager.search_communications(
                    variant, limit, owner_user_id=owner_user_id
                ) or []:
                    rid = str(rec.get("id") or "")
                    if not rid or rid in seen_ids:
                        continue
                    seen_ids.add(rid)
                    records.append(rec)
                    if len(records) >= limit:
                        return records
            return records

        records = await asyncio.to_thread(_search)
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
                db, query, limit=limit * _VECTOR_LIMIT_MULTIPLIER,
                since=since, source=source, author=author, raise_on_error=True,
            )

    async def _vector_leg(self, query: str, limit: int, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """LanceDB nearest neighbours. Raises on real failures so the leg
        outcome is recorded; raises ``_LegSkipped`` for the two conditions
        that are configuration, not breakage."""
        if not _vector_leg_enabled():
            raise _LegSkipped("vector_leg_disabled")
        if source and str(source).strip().lower() == "knowledge":
            raise _LegSkipped("source_filtered")

        lancedb = self._lancedb
        if lancedb is None:
            from core.lancedb_handler import get_lancedb_handler

            lancedb = get_lancedb_handler("default")
        if lancedb is None:
            raise RuntimeError("LanceDB handler unavailable for the vector leg")
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

    # -- fusion + hydration ---------------------------------------------------

    def _fuse_rrf(
        self,
        lexical: List[Dict[str, Any]],
        vector: List[Dict[str, Any]],
        legs: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> tuple[List[Dict[str, Any]], int]:
        """RRF over both legs, keyed by (source, id).

        Vector ids that resolve to an ``IngestedDocument`` row are hydrated
        from PG and flagged ``bridged:true``. Vector-only rows (connector file
        ingests, manual uploads — no PG row) are STILL RETURNED, flagged
        ``bridged:false``, with title/preview derived from LanceDB metadata —
        dropping them made every vector-only ingest invisible to search.
        Returns ``(fused, unbridged_count)``.

        Resolution is not a bare ``id`` equality check. The LanceDB ``documents``
        table mostly holds CHUNK rows (``<doc_id>::cN``) and rows written before
        the id-equality bridge, so matching on ``hit["id"]`` alone left ~35k rows
        permanently unhydrated even though their parent document id had been
        stamped into ``metadata.pg_document_id`` at ingest. Worse, a chunk hit and
        its parent's lexical hit landed on DIFFERENT RRF keys, so the two legs
        never reinforced each other — the one thing hybrid fusion exists to do.
        We therefore resolve through ``metadata.pg_document_id`` (and the chunk
        suffix) and key the fused entry by the resolved parent id.

        The identity lookup is a leg of its own for coverage purposes: when it
        throws, every vector hit used to be silently re-labelled
        ``source:"vector", bridged:false`` and the envelope still claimed
        semantic coverage, so a broken PG read was indistinguishable from a
        corpus of genuinely unbridged vector rows. Hits are still returned
        (they are real candidates) but the loss of source identity is recorded.
        """
        scores: Dict[tuple, Dict[str, Any]] = {}
        unbridged = 0
        hydration_error: Optional[BaseException] = None

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

                # Two-phase resolution. Collect every id a vector hit could
                # resolve to, look them up once (a vector limit of 30 turns into
                # a single IN query rather than per-hit lookups), then pick the
                # best mapping per hit below.
                candidates: set = set()
                metas: List[Dict[str, Any]] = []
                for v in vector:
                    vid = str(v.get("id") or "")
                    meta = _coerce_metadata(v.get("metadata"))
                    metas.append(meta)
                    if vid:
                        candidates.add(vid)
                    parent = _parent_doc_id(vid)
                    if parent:
                        candidates.add(parent)
                    stamped = meta.get("pg_document_id")
                    if stamped:
                        candidates.add(str(stamped))

                pg_rows = {}
                if candidates:
                    rows = (
                        db.query(IngestedDocument)
                        .filter(IngestedDocument.id.in_(list(candidates)))
                        .all()
                    )
                    pg_rows = {d.id: d for d in rows}
        except Exception as e:
            logger.warning("DocumentsHybridSearch hydration lookup failed: %r", e)
            hydration_error = e
            pg_rows = {}
            metas = [_coerce_metadata(v.get("metadata")) for v in vector]

        if legs is not None:
            if hydration_error is not None:
                legs["hydration"] = {
                    "status": LEG_FAILED,
                    "required": True,
                    "error_category": _error_category(hydration_error),
                    "hit_count": len(vector),
                    "duration_ms": 0.0,
                }
            else:
                legs["hydration"] = {
                    "status": LEG_OK,
                    "required": True,
                    "error_category": None,
                    "hit_count": len(pg_rows),
                    "duration_ms": 0.0,
                }

        def _resolve(vid: str, meta: Dict[str, Any]) -> Optional[str]:
            """Best PG id for a LanceDB hit: exact id, then the ingest stamp,
            then the chunk's parent id."""
            if vid in pg_rows:
                return vid
            stamped = meta.get("pg_document_id")
            if stamped and str(stamped) in pg_rows:
                return str(stamped)
            parent = _parent_doc_id(vid)
            if parent and parent in pg_rows:
                return parent
            return None

        # Dedupe vector hits by RESOLVED parent BEFORE scoring (2026-09-13
        # review): classic RRF scores each leg at most once per document.
        # Scoring every chunk separately let a 3,400-chunk document with 10
        # chunks in the top-30 accumulate ~10/60 from the vector leg alone
        # and bury a one-chunk document that BOTH legs found (~2/60). Keep
        # the best-ranked chunk per parent (context/hydration use it); one
        # entry per unresolvable id.
        _seen_resolved: set = set()
        deduped_vector: List[Dict[str, Any]] = []
        deduped_metas: List[Dict[str, Any]] = []
        for _idx, _hit in enumerate(vector):
            _vid = str(_hit.get("id") or "")
            _meta = (
                metas[_idx]
                if _idx < len(metas)
                else _coerce_metadata(_hit.get("metadata"))
            )
            _key = _resolve(_vid, _meta) or _vid
            if _key in _seen_resolved:
                continue
            _seen_resolved.add(_key)
            deduped_vector.append(_hit)
            deduped_metas.append(_meta)

        for rank, hit in enumerate(deduped_vector, start=1):
            vid = str(hit.get("id") or "")
            meta = (
                deduped_metas[rank - 1]
                if rank - 1 < len(deduped_metas)
                else _coerce_metadata(hit.get("metadata"))
            )
            resolved_id = _resolve(vid, meta)
            doc = pg_rows.get(resolved_id) if resolved_id else None
            if doc is None:
                unbridged += 1
                title = (
                    meta.get("file_name")
                    or meta.get("title")
                    or meta.get("filename")
                    or str(vid)
                )
                preview = str(meta.get("preview") or meta.get("content") or "")[:200]
                entry = {
                    "source": "vector",
                    "id": vid,
                    "title": title,
                    "preview": preview,
                    "modified": None,
                    "bridged": False,
                    "rrf": 1.0 / (RRF_K + rank),
                    "legs": ["vector"],
                }
                scores.setdefault(("vector", vid), entry)
                continue
            # Key by the RESOLVED parent id so a chunk hit fuses with its
            # parent document's lexical hit instead of competing with it.
            key = ("ingested", resolved_id)
            entry = scores.setdefault(
                key,
                {
                    "source": "ingested",
                    "id": resolved_id,
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
            if "vector" not in entry["legs"]:
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
        legs: Optional[Dict[str, Dict[str, Any]]] = None,
        status: str = STATUS_SUCCESS,
    ) -> Dict[str, Any]:
        """The shared search envelope.

        ``success`` stays backward-compatible for the four in-repo consumers
        (``action_registry.documents.search`` passes it straight through,
        ``chat_tool_planner`` / ``drive_tool`` / the memory assembler read
        ``results``): it is True whenever the search produced usable evidence,
        which now excludes the case that used to matter most — a required leg
        that threw. ``status`` is the field callers must branch on.

        Absent evidence is qualified by coverage: ``absent_within_coverage``
        is only true for ``success``, and a ``failed`` search exposes
        ``absence_claimable: False`` so a planner can never launder a broken
        source into "it isn't there".
        """
        legs = legs or {}
        failed = [n for n, leg in legs.items() if leg.get("status") == LEG_FAILED]
        searched = sorted(
            n for n, leg in legs.items()
            if leg.get("status") in (LEG_OK, LEG_FAILED)
        )
        envelope: Dict[str, Any] = {
            "success": status != STATUS_FAILED,
            "status": status,
            "query": query,
            "results": results,
            "hybrid": label,
            "stats": stats,
            "legs": legs,
            "coverage": {
                "searched": searched,
                "unavailable": sorted(failed),
                "skipped": sorted(
                    n for n, leg in legs.items() if leg.get("status") == LEG_SKIPPED
                ),
            },
            "ranking": {"status": "as_fused", "reason": None},
            "absence_claimable": status == STATUS_SUCCESS,
        }
        if status == STATUS_FAILED:
            envelope["error"] = {
                "reason": "required_retrieval_unavailable",
                "legs": sorted(failed),
            }
        return envelope
