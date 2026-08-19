"""
Memory Consolidator (P2.1) — mem0-style consolidation, rule-based first pass.

Runs OFF the user-facing turn (Letta sleep-time principle). Current rules:

  1. Edge contradiction sweep: active edges sharing (source, target, type)
     with conflicting properties are superseded — newest (by created_at)
     wins, older ones are bi-temporally INVALIDATED (never deleted), so
     "what was true as of last month" stays answerable via edges_as_of().
  2. Turn-fact supersede sweep: active facts in the same category whose
     subject prefix matches but which assert different values keep only
     the newest; older rows flip to status='superseded' (the SQL row is
     preserved for audit — the (workspace, hash) constraint already dedupes
     exact repeats).

The LLM-review pass (compare recent facts/comms against the graph and emit
nuanced ADD/UPDATE/INVALIDATE ops) is deliberately NOT here yet: it lands
after the P2.3 eval harness can measure whether it helps. Rules first,
measured intelligence second.

Enable via MEMORY_CONSOLIDATION_ENABLED (default true); the worker
(workers/memory_consolidation_worker.py) runs it nightly.
"""

import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_SUBJECT_PREFIX_TOKENS = 4
_VALUE_RE = re.compile(r"\$?\d[\d,.]*")


def _edge_conflict_key(edge) -> Tuple:
    return (edge.workspace_id, edge.source_node_id, edge.target_node_id, edge.relationship_type)


def _fact_subject_prefix(fact_text: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9]+", fact_text or "")][:_SUBJECT_PREFIX_TOKENS]
    return " ".join(words).lower()


def _fact_value(fact_text: str) -> Optional[str]:
    m = _VALUE_RE.search(fact_text or "")
    return m.group(0) if m else None


def consolidate_edges(workspace_id: str) -> Dict[str, int]:
    """Invalidate older conflicting edges; newest wins. Returns counts."""
    from core.database import get_db_session
    from core.models import GraphEdge

    invalidated = 0
    try:
        with get_db_session() as session:
            active = session.query(GraphEdge).filter(
                GraphEdge.workspace_id == workspace_id,
                GraphEdge.invalid_at.is_(None),
            ).all()

            groups: Dict[Tuple, List[Any]] = defaultdict(list)
            for e in active:
                groups[_edge_conflict_key(e)].append(e)

            now = datetime.utcnow()
            for key, edges in groups.items():
                if len(edges) < 2:
                    continue
                # Different properties on the same (s,t,type) pair = contradiction
                props = [dict(p or {}) for p in (e.properties for e in edges)]
                if all(p == props[0] for p in props):
                    continue  # identical upserts — already merged by ingest
                edges_sorted = sorted(edges, key=lambda e: e.created_at or datetime.min)
                winner = edges_sorted[-1]
                for loser in edges_sorted[:-1]:
                    loser.invalid_at = now
                    loser.invalidation_reason = f"consolidation: superseded by {winner.id}"
                    invalidated += 1
            session.commit()
    except Exception as e:
        logger.error(f"consolidate_edges failed: {e}")
    return {"invalidated": invalidated}


def consolidate_turn_facts(workspace_id: str) -> Dict[str, int]:
    """Same-subject facts asserting different values: keep newest, supersede
    older (status flip, row preserved)."""
    from core.database import get_db_session
    from core.models import TurnFact

    superseded = 0
    try:
        with get_db_session() as session:
            active = session.query(TurnFact).filter(
                TurnFact.workspace_id == workspace_id,
                TurnFact.status == "active",
            ).order_by(TurnFact.created_at.desc()).all()

            by_subject: Dict[str, List[Any]] = defaultdict(list)
            for f in active:
                subj = _fact_subject_prefix(f.fact_text or "")
                if subj:
                    by_subject[(f.category, subj)].append(f)

            for _, facts in by_subject.items():
                if len(facts) < 2:
                    continue
                newest = facts[0]  # desc order
                newest_val = _fact_value(newest.fact_text or "")
                for older in facts[1:]:
                    older_val = _fact_value(older.fact_text or "")
                    # Only supersede when both assert values AND they differ
                    if newest_val and older_val and newest_val != older_val:
                        older.status = "superseded"
                        superseded += 1
            session.commit()
    except Exception as e:
        logger.error(f"consolidate_turn_facts failed: {e}")
    return {"superseded": superseded}


def consolidate_workspace(workspace_id: str = "default") -> Dict[str, Any]:
    """Run all consolidation rules for a workspace. Never raises."""
    started = datetime.utcnow()
    edge_report = consolidate_edges(workspace_id)
    fact_report = consolidate_turn_facts(workspace_id)
    return {
        "workspace": workspace_id,
        "edges_invalidated": edge_report["invalidated"],
        "facts_superseded": fact_report["superseded"],
        "ran_at": started.isoformat(),
    }
