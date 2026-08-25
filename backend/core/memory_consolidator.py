"""
Memory Consolidator (P2.1) — mem0-style consolidation, rules + LLM-review.

Runs OFF the user-facing turn (Letta sleep-time principle). Rule-based sweep
(always on, deterministic):

  1. Edge contradiction sweep: active edges sharing (source, target, type)
     with conflicting properties are superseded — newest (by created_at)
     wins, older ones are bi-temporally INVALIDATED (never deleted), so
     "what was true as of last month" stays answerable via edges_as_of().
  2. Turn-fact supersede sweep: active facts in the same category whose
     subject prefix matches but which assert different values keep only
     the newest; older rows flip to status='superseded' (the SQL row is
     preserved for audit — the (workspace, hash) constraint already dedupes
     exact repeats).

LLM-review pass (measure-the-intelligence first, land it second):
`consolidate_with_llm()` compares recent active turn facts + the active graph
edges for a workspace and asks the LLM to emit nuanced ADD/UPDATE/INVALIDATE
ops (supersede a stale fact, invalidate a contradicted edge, add a fact the
rules can't see because it isn't numeric). Gated by ATOM_MEMORY_CONSOLIDATION_LLM
(default false — shadow until the P2.3 eval harness measures it). Never raises.

Enable via MEMORY_CONSOLIDATION_ENABLED (default true); the worker
(workers/memory_consolidation_worker.py) runs it nightly.
"""

import asyncio
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.turn_fact_categories import ALL_FACT_CATEGORIES as _FACT_CATEGORIES

logger = logging.getLogger(__name__)

def llm_review_enabled() -> bool:
    """Env wins > runtime_settings DB row (UI admin) > default."""
    from core.runtime_settings import get_bool_setting

    return get_bool_setting("ATOM_MEMORY_CONSOLIDATION_LLM", False)


def llm_review_max_subjects() -> int:
    from core.runtime_settings import get_int_setting

    return get_int_setting("ATOM_MEMORY_CONSOLIDATION_LLM_MAX_SUBJECTS", 5)


def llm_review_facts_per_subject() -> int:
    from core.runtime_settings import get_int_setting

    return get_int_setting("ATOM_MEMORY_CONSOLIDATION_LLM_FACTS_PER_SUBJECT", 6)


def llm_review_max_ops() -> int:
    from core.runtime_settings import get_int_setting

    return get_int_setting("ATOM_MEMORY_CONSOLIDATION_LLM_MAX_OPS", 20)


def llm_review_timeout_s() -> float:
    from core.runtime_settings import get_float_setting

    return get_float_setting("ATOM_MEMORY_CONSOLIDATION_LLM_TIMEOUT_S", 20.0)


def llm_review_lookback_days() -> int:
    from core.runtime_settings import get_int_setting

    return get_int_setting("ATOM_MEMORY_CONSOLIDATION_LLM_LOOKBACK_DAYS", 7)


LLM_REVIEW_ENABLED = llm_review_enabled()
LLM_REVIEW_MAX_SUBJECTS = llm_review_max_subjects()
LLM_REVIEW_FACTS_PER_SUBJECT = llm_review_facts_per_subject()
LLM_REVIEW_MAX_OPS = llm_review_max_ops()
LLM_REVIEW_TIMEOUT_S = llm_review_timeout_s()
LLM_REVIEW_LOOKBACK_DAYS = llm_review_lookback_days()

_ALLOWED_FACT_CATEGORIES = frozenset(_FACT_CATEGORIES)

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


_ERASED_TEXT = "[erased per retention policy]"


def _retention_days(retention_days: Optional[int] = None) -> int:
    """Explicit param wins; else env TURN_FACT_RETENTION_DAYS (0 = disabled)."""
    if retention_days is not None:
        return int(retention_days)
    return int(os.getenv("TURN_FACT_RETENTION_DAYS", "0") or 0)


def apply_retention_policy(
    workspace_id: str,
    retention_days: Optional[int] = None,
    db: Optional[Any] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Retention sweep (rev.2 #2): invalidate ACTIVE facts older than the
    cutoff, anonymizing their text (right-to-erasure compatible while
    preserving audit rows). Disabled when cutoff <= 0 (default). Never raises.
    """
    invalidated = 0
    days = _retention_days(retention_days)
    if days <= 0:
        return {"workspace": workspace_id, "invalidated": 0, "disabled": True}
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    try:
        from core.database import get_db_session
        from core.models import TurnFact

        with (db if db is not None else get_db_session()) as session:
            stale = session.query(TurnFact).filter(
                TurnFact.workspace_id == workspace_id,
                TurnFact.status == "active",
                TurnFact.created_at < cutoff,
            ).all()
            for r in stale:
                r.fact_text = _ERASED_TEXT
                r.tags = None
                r.status = "invalidated"
                invalidated += 1
            if db is None:
                session.commit()
            else:
                session.commit()
    except Exception as e:
        logger.error(f"apply_retention_policy failed: {e}")
        return {"workspace": workspace_id, "invalidated": 0, "error": str(e)}
    return {"workspace": workspace_id, "invalidated": invalidated}


def purge_user_facts(
    workspace_id: str,
    user_id: str,
    hard: bool = False,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Right-to-erasure for one user's facts (GDPR Art. 17 style).
    soft (default): anonymize text + invalidate — row preserved for audit.
    hard=True: DELETE rows entirely (legal hold is the caller's judgment).
    Never raises.
    """
    purged = deleted = 0
    try:
        from core.database import get_db_session
        from core.models import TurnFact

        with (db if db is not None else get_db_session()) as session:
            rows = session.query(TurnFact).filter(
                TurnFact.workspace_id == workspace_id,
                TurnFact.user_id == user_id,
            ).all()
            if hard:
                for r in rows:
                    session.delete(r)
                    deleted += 1
            else:
                now = datetime.now(timezone.utc)
                for r in rows:
                    r.fact_text = _ERASED_TEXT
                    r.tags = None
                    r.status = "invalidated"
                    r.superseded_at = now
                    purged += 1
            if db is None:
                session.commit()
            else:
                session.commit()
    except Exception as e:
        logger.error(f"purge_user_facts failed: {e}")
        return {"workspace": workspace_id, "user_id": user_id,
                "purged": 0, "deleted": 0, "error": str(e)}
    return {"workspace": workspace_id, "user_id": user_id,
            "purged": purged, "deleted": deleted}


def consolidate_workspace(workspace_id: str = "default") -> Dict[str, Any]:
    """Run all consolidation rules for a workspace. Never raises."""
    started = datetime.utcnow()
    edge_report = consolidate_edges(workspace_id)
    fact_report = consolidate_turn_facts(workspace_id)
    retention_report = apply_retention_policy(workspace_id)
    return {
        "workspace": workspace_id,
        "edges_invalidated": edge_report["invalidated"],
        "facts_superseded": fact_report["superseded"],
        "facts_expired": retention_report.get("invalidated", 0),
        "ran_at": started.isoformat(),
    }


# --------------------------------------------------------------------------- #
# LLM-review pass (P2.1 deferred half) — measured intelligence, then land it.
#
# Gated by ATOM_MEMORY_CONSOLIDATION_LLM (default false: shadow). For each
# subject with recent activity, the LLM reviews the recent active turn facts
# against the active graph edges and emits bounded ADD/UPDATE/INVALIDATE ops.
# Every op is applied through the same bi-temporal fields the rules use, so
# the audit trail is uniform. Never raises.
# --------------------------------------------------------------------------- #

_REVIEW_PROMPT = """You are a memory consolidation reviewer for a business AI \
assistant. You are given a SUBJECT and the memory currently believed about it.

SUBJECT: {subject}

RECENT TURN FACTS (id | category | fact):
{facts}

ACTIVE GRAPH EDGES (source --type--> target, properties):
{edges}

Decide whether any of the memory is stale, contradicted, or missing. Emit a
JSON array (and nothing else) of operations:

- {{"op": "supersede_fact", "fact_id": "...", "reason": "..."}}
    An older fact is contradicted by a newer one (keep the newer, supersede
    the older). Supersede ONLY the older fact, never the newest.
- {{"op": "invalidate_edge", "edge_id": "...", "reason": "..."}}
    An edge is superseded/contradicted by a newer edge on the same pair.
- {{"op": "add_fact", "text": "...", "category": "exact_value|hard_constraint|decision_reason|cross_task_dep|implicit_pref", "reason": "..."}}
    A durable fact is missing entirely (do NOT re-add something already present).
- {{"op": "update_fact", "fact_id": "...", "text": "...", "category": "...", "reason": "..."}}
    A fact's content is wrong; supersede it and store the corrected text.

Rules:
- Only emit operations that are clearly warranted from the evidence above.
- Never invent ids. Never touch facts/edges not shown.
- If nothing needs changing, return [].
- Return ONLY the JSON array."""


def _gather_review_evidence(workspace_id: str) -> Tuple[List[Any], List[Any]]:
    """Recent active turn facts + active graph edges (with node names) for a
    workspace. Never raises — failures degrade to empty evidence."""
    from core.database import get_db_session
    from core.models import GraphEdge, GraphNode, TurnFact

    facts: List[Any] = []
    edges: List[Any] = []
    try:
        cutoff = datetime.utcnow() - timedelta(days=llm_review_lookback_days())
        with get_db_session() as session:
            facts = session.query(TurnFact).filter(
                TurnFact.workspace_id == workspace_id,
                TurnFact.status == "active",
                TurnFact.created_at >= cutoff,
            ).order_by(TurnFact.created_at.desc()).limit(
                llm_review_max_subjects() * llm_review_facts_per_subject()
            ).all()
            edge_rows = session.query(GraphEdge).filter(
                GraphEdge.workspace_id == workspace_id,
                GraphEdge.invalid_at.is_(None),
            ).all()
            node_names = {
                n.id: n.name for n in session.query(GraphNode).filter(
                    GraphNode.workspace_id == workspace_id
                ).all()
            }
            edges = [{
                "id": e.id,
                "source": node_names.get(e.source_node_id, e.source_node_id),
                "target": node_names.get(e.target_node_id, e.target_node_id),
                "type": e.relationship_type,
                "properties": dict(e.properties or {}),
            } for e in edge_rows][:50]
    except Exception as e:
        logger.warning("memory_consolidator evidence gathering failed: %s", e)
    return facts, edges


def _subject_candidates(facts: List[Any]) -> List[Tuple[str, List[Any]]]:
    """Group facts by subject prefix; keep subjects with >= 2 facts (enough
    signal for a review) and cap the number of subjects/facts per subject."""
    by_subject: Dict[str, List[Any]] = defaultdict(list)
    for f in facts:
        subj = _fact_subject_prefix(f.fact_text or "")
        if subj:
            by_subject[subj].append(f)
    candidates = [
        (subj, items[: llm_review_facts_per_subject()])
        for subj, items in by_subject.items()
        if len(items) >= 2
    ]
    candidates.sort(key=lambda c: len(c[1]), reverse=True)
    return candidates[: llm_review_max_subjects()]


def _parse_ops(raw: str) -> List[Dict[str, Any]]:
    """Robust JSON-array parse for the review ops. Returns [] on any failure."""
    if not raw:
        return []
    import json
    text = raw.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(data.get("ops"), list):
            return [d for d in data["ops"] if isinstance(d, dict)]
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
    except Exception:
        pass
    # Fallback: locate the outermost array (handles markdown fences / prose).
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
    except Exception:
        pass
    return []


def _apply_ops(
    workspace_id: str,
    ops: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply validated ops through the bi-temporal fields. Each op is guarded
    so one bad op cannot fail the pass. Returns per-op counts + audit rows."""
    from core.database import get_db_session
    from core.models import GraphEdge, TurnFact

    counts = {"supersede_fact": 0, "invalidate_edge": 0, "add_fact": 0, "update_fact": 0}
    skipped: List[str] = []
    audit: List[Dict[str, Any]] = []
    applied = 0
    try:
        with get_db_session() as session:
            for op in ops[: llm_review_max_ops()]:
                op_type = op.get("op")
                if op_type not in counts:
                    skipped.append(f"unknown op: {op_type!r}")
                    continue
                try:
                    if op_type == "supersede_fact":
                        fact = session.get(TurnFact, op.get("fact_id"))
                        if fact and fact.workspace_id == workspace_id and fact.status == "active":
                            fact.status = "superseded"
                            fact.superseded_at = datetime.utcnow()
                            fact.commit_message = f"llm-review: {(op.get('reason') or 'superseded')[:200]}"
                            audit.append({"op": op_type, "fact_id": fact.id,
                                          "reason": op.get("reason")})
                            applied += 1
                    elif op_type == "invalidate_edge":
                        edge = session.get(GraphEdge, op.get("edge_id"))
                        if edge and edge.workspace_id == workspace_id and edge.invalid_at is None:
                            edge.invalid_at = datetime.utcnow()
                            edge.invalidation_reason = f"llm-review: {(op.get('reason') or 'superseded')[:200]}"
                            audit.append({"op": op_type, "edge_id": edge.id,
                                          "reason": op.get("reason")})
                            applied += 1
                    elif op_type == "add_fact":
                        text = (op.get("text") or "").strip()
                        category = (op.get("category") or "").strip()
                        if not text or category not in _ALLOWED_FACT_CATEGORIES:
                            skipped.append(f"add_fact invalid: text={text[:20]!r} category={category!r}")
                            continue
                        from core.turn_fact_extractor import remember_fact_explicit
                        created = remember_fact_explicit(
                            workspace_id=workspace_id,
                            fact_text=text,
                            category=category,
                            domain="consolidation",
                            confidence=0.9,
                        )
                        if created is not None:
                            audit.append({"op": op_type, "fact_id": created.id,
                                          "reason": op.get("reason")})
                            applied += 1
                        else:
                            skipped.append(f"add_fact dedup/validation rejected: {text[:40]!r}")
                    elif op_type == "update_fact":
                        fact = session.get(TurnFact, op.get("fact_id"))
                        text = (op.get("text") or "").strip()
                        category = (op.get("category") or "").strip()
                        if not fact or fact.workspace_id != workspace_id or fact.status != "active":
                            skipped.append(f"update_fact target not active: {op.get('fact_id')!r}")
                            continue
                        if not text or category not in _ALLOWED_FACT_CATEGORIES:
                            skipped.append(f"update_fact invalid: text={text[:20]!r} category={category!r}")
                            continue
                        fact.status = "superseded"
                        fact.superseded_at = datetime.utcnow()
                        fact.commit_message = f"llm-review update: {(op.get('reason') or 'corrected')[:200]}"
                        from core.turn_fact_extractor import remember_fact_explicit
                        created = remember_fact_explicit(
                            workspace_id=workspace_id,
                            fact_text=text,
                            category=category,
                            domain="consolidation",
                            confidence=0.9,
                        )
                        if created is not None:
                            # created is a detached row from its own session;
                            # persist the parent link via a fresh query-update.
                            session.query(TurnFact).filter(
                                TurnFact.id == created.id
                            ).update({"parent_id": fact.id})
                            audit.append({"op": op_type, "fact_id": created.id,
                                          "superseded_id": fact.id,
                                          "reason": op.get("reason")})
                            applied += 1
                        else:
                            skipped.append(f"update_fact replacement rejected: {text[:40]!r}")
                except Exception as op_err:
                    skipped.append(f"{op_type} apply failed: {op_err}")
            session.commit()
            for a in audit:
                counts[a["op"]] = counts.get(a["op"], 0) + 1
    except Exception as e:
        logger.warning("memory_consolidator LLM op apply failed: %s", e)
    return {
        "ops_applied": applied,
        "counts": counts,
        "skipped": skipped[:20],
        "audit": audit,
    }


async def consolidate_with_llm(workspace_id: str = "default", tenant_id: str = "default") -> Dict[str, Any]:
    """LLM-review consolidation pass. Compares recent active turn facts against
    the active graph edges and applies bounded ADD/UPDATE/INVALIDATE ops with a
    uniform bi-temporal audit trail. Shadow-gated by ATOM_MEMORY_CONSOLIDATION_LLM
    (default false). Never raises."""
    report: Dict[str, Any] = {
        "workspace": workspace_id,
        "enabled": llm_review_enabled(),
        "subjects_reviewed": 0,
        "ops_emitted": 0,
        "ops_applied": 0,
        "counts": {},
        "skipped": [],
        "audit": [],
        "ran_at": datetime.utcnow().isoformat(),
    }
    if not llm_review_enabled():
        return report
    try:
        facts, edges = _gather_review_evidence(workspace_id)
        subjects = _subject_candidates(facts)
        report["subjects_reviewed"] = len(subjects)
        if not subjects:
            return report

        from core.llm_service import get_llm_service

        llm = get_llm_service(workspace_id=workspace_id, tenant_id=tenant_id)
        all_ops: List[Dict[str, Any]] = []
        for subj, subj_facts in subjects:
            fact_lines = "\n".join(
                f"- {f.id} | {f.category} | {(f.fact_text or '')[:300]}"
                for f in subj_facts
            )
            prompt = _REVIEW_PROMPT.format(
                subject=subj,
                facts=fact_lines,
                edges="\n".join(
                    f"- {e['source']} --{e['type']}--> {e['target']} {e['properties']}"
                    for e in edges
                ) or "(none)",
            )
            try:
                raw = await asyncio.wait_for(
                    llm.generate(
                        prompt=prompt,
                        system_instruction=(
                            "You review memory for contradictions. Return ONLY a "
                            "JSON array of operations; [] if none."
                        ),
                        model="fast",
                        temperature=0.0,
                        max_tokens=800,
                    ),
                    timeout=llm_review_timeout_s(),
                )
            except Exception as e:
                logger.debug("memory_consolidator LLM review skipped (%s): %s", subj, e)
                continue
            all_ops.extend(_parse_ops(raw))

        report["ops_emitted"] = len(all_ops)
        result = _apply_ops(workspace_id, all_ops)
        report.update(result)
    except Exception as e:
        logger.warning("consolidate_with_llm failed: %s", e)
    return report
