"""Document freshness & supersession service.

Detects when an ingested document is outdated and records a filterable
``freshness_status`` so retrieval can suppress stale material. Three signals:

1. **Source-side staleness** — the document changed at its origin (content-hash
   mismatch or ``modified_at`` change) or aged out beyond a TTL. Mirrors the
   ``GovernanceDocument.last_verified`` pattern
   (models.py:2121, policy_search_service.py:161-169).
2. **Removed upstream** — the document no longer appears in the integration's
   file listing (deleted in Notion/Drive). Detected during sync via the set of
   "seen" external ids.
3. **Document supersession** — a *different*, newer document on the same topic
   (same integration) renders this one outdated. "Same topic" is decided by a
   hybrid signal: embedding similarity (semantic near-duplicate) AND/OR entity
   overlap (edges in the knowledge_graph sharing entities), confirmed by a
   cheap deterministic heuristic. See ``detect_supersession``.

The statuses are: ``fresh | stale | outdated | removed | superseded``.

The module also cascades doc status onto the GraphRAG layer: when a doc is
marked superseded, the knowledge_graph edges extracted from it are stamped
via ``LanceDBHandler.mark_edges_superseded_by_doc`` so retrieval can hide
them (see ``query_knowledge_graph(exclude_source_doc_ids=...)``).

Config (env vars, matching the codebase convention in
core/llm/gateway/request_logger.py):
  - ``ATOM_DOC_FRESHNESS_TTL_HOURS`` (default 24): age at which a doc becomes
    ``outdated``. Same default as policy_search_service.
  - ``ATOM_FRESHNESS_FILTER_ENABLED`` (default true): master switch for the
    retrieval-time filter in lancedb_handler.
  - ``ATOM_SUPERSESSION_SIM_THRESHOLD`` (default 0.86): cosine threshold above
    which two docs are considered semantic near-duplicates (candidate pair).
  - ``ATOM_SUPERSESSION_ENTITY_OVERLAP`` (default 0.5): Jaccard threshold for
    entity-set overlap to count as "same topic".
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from core.models import IngestedDocument

logger = logging.getLogger(__name__)

# --- Config -----------------------------------------------------------------
def freshness_ttl_hours() -> float:
    """Env wins > runtime_settings DB row (UI admin) > default."""
    from core.runtime_settings import get_float_setting

    return get_float_setting("ATOM_DOC_FRESHNESS_TTL_HOURS", 24.0)


def freshness_filter_enabled() -> bool:
    from core.runtime_settings import get_bool_setting

    return get_bool_setting("ATOM_FRESHNESS_FILTER_ENABLED", True)


def supersession_sim_threshold() -> float:
    from core.runtime_settings import get_float_setting

    return get_float_setting("ATOM_SUPERSESSION_SIM_THRESHOLD", 0.86)


def supersession_entity_overlap() -> float:
    from core.runtime_settings import get_float_setting

    return get_float_setting("ATOM_SUPERSESSION_ENTITY_OVERLAP", 0.5)


# Deprecated import-time snapshots kept for legacy importers (lancedb_handler).
FRESHNESS_TTL_HOURS = freshness_ttl_hours()
FRESHNESS_FILTER_ENABLED = freshness_filter_enabled()
SUPERSESSION_SIM_THRESHOLD = supersession_sim_threshold()
SUPERSESSION_ENTITY_OVERLAP = supersession_entity_overlap()

# Statuses that should be suppressed from default retrieval. ``stale`` is
# excluded by default too: a doc whose source has changed may contain
# statements that no longer hold.
NON_FRESH_STATUSES = frozenset({"stale", "outdated", "removed", "superseded"})


def hash_text(text: str) -> str:
    """SHA-256 of text. Mirrors IngestionPipelineService._hash_text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_status_from_hash(old_hash: Optional[str], new_hash: str) -> str:
    """If content hashes differ, the source has changed → ``stale``.

    Returns ``fresh`` when hashes match (or there is no prior hash), ``stale``
    when they differ. This is the pure content-change signal; aging and removal
    are layered on top by ``compute_freshness_status``.
    """
    if not old_hash:
        return "fresh"
    return "stale" if old_hash != new_hash else "fresh"


def compute_freshness_status(
    last_verified_at: Optional[datetime],
    source_modified_at_now: Optional[datetime] = None,
    last_verified_modified: Optional[datetime] = None,
    now: Optional[datetime] = None,
    ttl_hours: Optional[float] = None,
) -> str:
    """Compute a freshness status from the recorded signals.

    ``ttl_hours=None`` resolves from runtime settings (env > UI row > 24h).


    Precedence (most actionable first):
      1. ``outdated`` — never verified, or last verification older than TTL.
      2. ``stale`` — source's current modified_at differs from the one
         captured at last successful verify (content changed upstream).
      3. ``fresh`` — otherwise.

    ``now`` is injectable for tests. ``source_modified_at_now`` is the
    modified_at the source *currently* reports; ``last_verified_modified`` is
    the modified_at we recorded when we last verified.
    """
    ttl_hours = ttl_hours if ttl_hours is not None else freshness_ttl_hours()
    now = now or datetime.now(timezone.utc)

    if last_verified_at is None:
        return "outdated"

    # Coerce to offset-aware for comparison.
    def _aware(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    # Normalize both sides: a caller may pass a tz-naive ``now`` (e.g. read
    # from a SQLite cell or via datetime.utcnow()), while last_verified_at is
    # stored tz-aware on Postgres. Mixing them raises TypeError.
    now = _aware(now)
    age = now - _aware(last_verified_at)
    if age > timedelta(hours=ttl_hours):
        return "outdated"

    if source_modified_at_now is not None and last_verified_modified is not None:
        a = _aware(source_modified_at_now)
        b = _aware(last_verified_modified)
        if abs((a - b).total_seconds()) > 1.0:
            return "stale"

    return "fresh"


def detect_removed_upstream(external_id: str, seen_external_ids: Iterable[str]) -> bool:
    """True if ``external_id`` was NOT present in the latest source listing."""
    return external_id not in set(seen_external_ids)


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    """Jaccard similarity over two entity-id sets. Empty → 0.0."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _cosine(vec_a: List[float], vec_b: List[float]) -> float:
    """Pure-python cosine similarity (no numpy dependency)."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(vec_a, vec_b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


@dataclass
class SupersessionCandidate:
    """An older doc detected as superseded by a newer one."""

    doc_id: str
    status: str  # the new freshness_status to set, always "superseded"
    reason: str  # human-readable explanation
    similarity: float = 0.0
    entity_overlap: float = 0.0


@dataclass
class ReevaluateSummary:
    """Counts returned by a reevaluation pass."""

    checked: int = 0
    marked_fresh: int = 0
    marked_stale: int = 0
    marked_outdated: int = 0
    marked_removed: int = 0
    marked_superseded: int = 0
    edges_superseded: int = 0
    unchanged: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "checked": self.checked,
            "fresh": self.marked_fresh,
            "stale": self.marked_stale,
            "outdated": self.marked_outdated,
            "removed": self.marked_removed,
            "superseded": self.marked_superseded,
            "edges_superseded": self.edges_superseded,
            "unchanged": self.unchanged,
        }


# Types for injectable collaborators (keeps the service unit-testable).
EmbedFn = Callable[[str], Optional[List[float]]]
EntitySetFn = Callable[[str], Set[str]]


def detect_supersession(
    *,
    newer_doc_id: str,
    newer_text: str,
    newer_embedding: Optional[List[float]],
    newer_entities: Set[str],
    newer_ts: Optional[datetime],
    older_docs: List[Dict[str, Any]],
    embed_fn: Optional[EmbedFn] = None,
    older_embeddings: Optional[Dict[str, List[float]]] = None,
    older_entity_sets: Optional[Dict[str, Set[str]]] = None,
    sim_threshold: Optional[float] = None,
    entity_overlap_threshold: Optional[float] = None,
) -> List[SupersessionCandidate]:
    """Find older docs superseded by ``newer_doc``.

    ``None`` thresholds resolve from runtime settings (env > UI row).


    Hybrid detection: an older doc is a candidate when EITHER
      (a) semantic similarity >= ``sim_threshold`` (near-duplicate content), OR
      (b) entity overlap >= ``entity_overlap_threshold`` (same subject matter),
    confirmed by a heuristic: the older doc must be genuinely older (by
    ``ingested_at`` / ``external_modified_at``) than the newer one.

    ``older_docs`` is a list of dicts shaped like:
        {"doc_id", "text", "ingested_at", "external_modified_at", "freshness_status"}
    ``older_embeddings`` / ``older_entity_sets`` map doc_id → embedding /
    entity set. When omitted, ``embed_fn`` is used to embed older text lazily.
    ``newer_ts`` is the newer doc's comparison timestamp
    (``external_modified_at`` preferred, else ``ingested_at``).

    Pure function — no DB or network IO. All IO is the caller's job.
    """
    sim_threshold = (
        sim_threshold if sim_threshold is not None else supersession_sim_threshold()
    )
    entity_overlap_threshold = (
        entity_overlap_threshold
        if entity_overlap_threshold is not None
        else supersession_entity_overlap()
    )
    candidates: List[SupersessionCandidate] = []
    if not newer_doc_id:
        return candidates

    for od in older_docs:
        oid = od.get("doc_id")
        if not oid or oid == newer_doc_id:
            continue
        # Only docs still considered fresh/stale can be superseded; already
        # outdated/removed/superseded docs are left alone.
        if od.get("freshness_status") in {"removed", "superseded"}:
            continue

        similarity = 0.0
        overlap = 0.0

        # (a) semantic similarity
        older_emb = (older_embeddings or {}).get(oid)
        if older_emb is None and embed_fn is not None:
            try:
                older_emb = embed_fn(od.get("text", ""))
            except Exception as e:
                logger.debug(f"supersession: embed failed for {oid}: {e}")
                older_emb = None
        if newer_embedding and older_emb:
            similarity = _cosine(newer_embedding, older_emb)

        # (b) entity overlap
        older_ents = (older_entity_sets or {}).get(oid)
        if older_ents is not None:
            overlap = jaccard(newer_entities, older_ents)

        is_candidate = similarity >= sim_threshold or overlap >= entity_overlap_threshold
        if not is_candidate:
            continue

        # Heuristic confirm: newer must be strictly newer than older.
        if not _is_genuinely_newer(od, newer_ts):
            continue

        reason_parts = []
        if similarity >= sim_threshold:
            reason_parts.append(f"sim={similarity:.3f}")
        if overlap >= entity_overlap_threshold:
            reason_parts.append(f"entity_overlap={overlap:.3f}")

        candidates.append(
            SupersessionCandidate(
                doc_id=oid,
                status="superseded",
                reason=f"superseded by {newer_doc_id} (" + ", ".join(reason_parts) + ")",
                similarity=similarity,
                entity_overlap=overlap,
            )
        )

    return candidates


def doc_ts(doc: Optional[Dict[str, Any]]) -> Optional[datetime]:
    """Extract a comparison timestamp from a doc dict.

    Used for both the newer doc (caller passes the newer doc's dict) and older
    candidate docs. Prefers ``external_modified_at`` then ``ingested_at``.
    """
    if not doc:
        return None
    for key in ("external_modified_at", "ingested_at"):
        v = doc.get(key)
        if isinstance(v, datetime):
            return v
    return None


def _is_genuinely_newer(older: Dict[str, Any], newer_ts: Optional[datetime]) -> bool:
    """Heuristic confirm: the newer doc must be strictly newer than the older."""
    older_ts = doc_ts(older)
    if newer_ts is None or older_ts is None:
        # Without timestamps we cannot confirm ordering → be conservative and
        # treat as superseded only if the candidate signal is very strong.
        return True
    return _aware(newer_ts) > _aware(older_ts)


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class DocFreshnessService:
    """DB-backed freshness operations for ingested documents.

    Constructed per workspace with a SQLAlchemy session. All methods are
    synchronous and commit their own transactions (consistent with
    ``IngestionPipelineService._record_doc_ingestion``).
    """

    def __init__(self, session: Session, workspace_id: Optional[str] = None):
        self.session = session
        self.workspace_id = workspace_id

    # -- ingest --------------------------------------------------------------

    def mark_on_ingest(
        self,
        doc: IngestedDocument,
        *,
        source_url: Optional[str],
        content_hash: str,
        source_modified_at: Optional[datetime],
    ) -> None:
        """Stamp freshness fields on a freshly ingested doc (status → fresh)."""
        doc.source_url = source_url
        doc.source_content_hash = content_hash
        doc.last_verified_at = datetime.now(timezone.utc)
        doc.source_modified_at = source_modified_at
        doc.freshness_status = "fresh"
        doc.superseded_by = None
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.warning(f"mark_on_ingest commit failed: {e}")

    def mark_stale(self, doc: IngestedDocument, *, reason: str = "source_changed") -> None:
        """Record that a doc's source has changed, ahead of re-ingest."""
        if doc.freshness_status in {"removed", "superseded"}:
            return  # don't resurrect terminal docs
        doc.freshness_status = "stale"
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.warning(f"mark_stale commit failed: {e}")

    def mark_superseded(
        self, older_doc_id: str, newer_doc_id: str, reason: str
    ) -> Optional[IngestedDocument]:
        """Mark an older doc superseded by ``newer_doc_id`` and link it."""
        doc = self._get(older_doc_id)
        if doc is None:
            return None
        doc.freshness_status = "superseded"
        doc.superseded_by = newer_doc_id
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.warning(f"mark_superseded commit failed: {e}")
        return doc

    # -- reevaluation --------------------------------------------------------

    def reevaluate_workspace(
        self,
        workspace_id: str,
        seen_external_ids: Iterable[str],
        now: Optional[datetime] = None,
    ) -> ReevaluateSummary:
        """Recompute freshness for all docs in a workspace.

        - Docs whose ``external_id`` is absent from ``seen_external_ids`` and
          whose integration was actually listed → ``removed``.
        - Otherwise recompute via ``compute_freshness_status`` using each doc's
          recorded signals. (When the caller passes ``seen_external_ids=set()``
          — e.g. the age-only background pass — removal detection is skipped.)

        Returns a summary of transitions. Does NOT touch supersession (that is
        triggered at ingest time by ``apply_supersession``).
        """
        summary = ReevaluateSummary()
        seen = set(seen_external_ids)
        now = now or datetime.now(timezone.utc)

        q = self.session.query(IngestedDocument).filter(
            IngestedDocument.workspace_id == workspace_id
        )
        for doc in q:
            summary.checked += 1
            prior = doc.freshness_status

            # Removal detection only when the caller actually listed sources.
            if seen and doc.external_id and doc.external_id not in seen:
                if prior != "removed":
                    doc.freshness_status = "removed"
                    summary.marked_removed += 1
                else:
                    summary.unchanged += 1
                continue

            # Don't age-recompute removed/superseded docs.
            if prior in {"removed", "superseded"}:
                summary.unchanged += 1
                continue

            status = compute_freshness_status(
                last_verified_at=doc.last_verified_at,
                source_modified_at_now=doc.external_modified_at,
                last_verified_modified=doc.source_modified_at,
                now=now,
            )
            if status != prior:
                doc.freshness_status = status
                doc.last_verified_at = now
                if status == "fresh":
                    summary.marked_fresh += 1
                elif status == "stale":
                    summary.marked_stale += 1
                elif status == "outdated":
                    summary.marked_outdated += 1
            else:
                summary.unchanged += 1

        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.warning(f"reevaluate_workspace commit failed: {e}")
        return summary

    def apply_supersession(
        self,
        candidates: List[SupersessionCandidate],
        newer_doc_id: str,
        *,
        cascade_to_graph: Optional[Callable[[str, str], int]] = None,
    ) -> ReevaluateSummary:
        """Persist supersession decisions and (optionally) cascade to the graph.

        ``cascade_to_graph(source_doc_id, superseded_by)`` is injected. In
        production it's ``cascade_graph_supersession`` in this module, which
        stamps the supersession into ``graph_edges.properties`` /
        ``graph_nodes.properties`` in PostgreSQL (GraphRAG's store). Keeping it
        injectable means this service stays unit-testable with the SQL dev DB
        and no LanceDB hard dependency.
        """
        summary = ReevaluateSummary()
        for c in candidates:
            doc = self.mark_superseded(c.doc_id, newer_doc_id, c.reason)
            if doc is None:
                continue
            summary.marked_superseded += 1
            if cascade_to_graph is not None:
                try:
                    summary.edges_superseded += cascade_to_graph(c.doc_id, newer_doc_id)
                except Exception as e:
                    logger.warning(f"graph cascade failed for {c.doc_id}: {e}")
        return summary

    # -- Postgres GraphRAG cascade ------------------------------------------

    def cascade_graph_supersession(self, source_doc_id: str, superseded_by: str) -> int:
        """Stamp supersession onto GraphRAG nodes/edges derived from a doc.

        GraphRAG lives in PostgreSQL (graph_nodes/graph_edges) and records each
        node/edge's origin document in ``properties["doc_id"]`` (see
        graphrag_engine.py:295,346). Rather than deleting extracted knowledge,
        we record ``properties["superseded_by"] = <newer_doc_id>`` so retrieval
        can hide superseded material. Returns the count of rows stamped.

        Uses the ORM (not raw SQL) so the ``JSONColumn`` type handles
        (de)serialization portably across Postgres and SQLite. We read each
        workspace's graph rows and filter in Python — the graph tables are
        bounded per workspace and this runs on supersession events, not the
        retrieval hot path.
        """
        from core.models import GraphEdge, GraphNode

        if not self.workspace_id:
            logger.debug("cascade_graph_supersession requires a workspace_id")
            return 0

        count = 0
        try:
            for model in (GraphNode, GraphEdge):
                rows = (
                    self.session.query(model)
                    .filter(model.workspace_id == self.workspace_id)
                    .all()
                )
                for row in rows:
                    props = dict(row.properties or {})
                    if str(props.get("doc_id")) == str(source_doc_id):
                        props["superseded_by"] = superseded_by
                        row.properties = props
                        count += 1
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.warning(f"cascade_graph_supersession failed for {source_doc_id}: {e}")
        return count

    def entity_set_for_doc(self, doc_id: str) -> Set[str]:
        """Return the set of entity names a doc contributed to GraphRAG.

        Used by supersession detection's entity-overlap signal. Reads
        ``graph_nodes`` where ``properties["doc_id"] == doc_id`` and collects
        node names. Returns an empty set if GraphRAG is unavailable.
        """
        from core.models import GraphNode

        if not self.workspace_id:
            return set()
        try:
            rows = (
                self.session.query(GraphNode)
                .filter(GraphNode.workspace_id == self.workspace_id)
                .all()
            )
            return {
                r.name
                for r in rows
                if r.name and str((r.properties or {}).get("doc_id")) == str(doc_id)
            }
        except Exception as e:
            logger.debug(f"entity_set_for_doc failed for {doc_id}: {e}")
            return set()

    # -- query helpers (used by retrieval) -----------------------------------

    def non_fresh_doc_ids(self, workspace_id: str) -> Set[str]:
        """Ids of docs that should be excluded from default retrieval.

        This is the bridge to the GraphRAG read-time cascade: retrieval passes
        this set so graph traversals can exclude nodes/edges whose source doc
        is non-fresh (see ``cascade_graph_supersession`` and the
        ``exclude_doc_ids`` filter in graphrag_engine.local_search).
        """
        rows = (
            self.session.query(IngestedDocument.id)
            .filter(
                IngestedDocument.workspace_id == workspace_id,
                IngestedDocument.freshness_status.in_(list(NON_FRESH_STATUSES)),
            )
            .all()
        )
        return {r[0] for r in rows}

    # -- internal ------------------------------------------------------------

    def _get(self, doc_id: str) -> Optional[IngestedDocument]:
        q = self.session.query(IngestedDocument).filter(IngestedDocument.id == doc_id)
        if self.workspace_id:
            q = q.filter(IngestedDocument.workspace_id == self.workspace_id)
        return q.first()


def extra_columns_for_ingest(
    *,
    freshness_status: str,
    source_modified_at: Optional[datetime],
    source_url: Optional[str],
) -> Dict[str, Any]:
    """Build the top-level LanceDB columns for a freshly ingested doc.

    These are passed to ``LanceDBHandler.add_document(extra_columns=...)`` so
    they are real, filterable columns — NOT buried in the metadata JSON blob
    (see the warning in lancedb_handler.py:562-575).
    """
    return {
        "freshness_status": freshness_status,
        "source_modified_at": (source_modified_at.isoformat() if source_modified_at else ""),
        "source_url": source_url or "",
    }
