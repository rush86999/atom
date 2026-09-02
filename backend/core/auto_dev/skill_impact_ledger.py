"""Skill-impact ledger — the WikiSkill ``wiki/skill-impact.md`` analog (W1).

Every mutation proposal outcome (accepted, rejected at any pipeline gate,
rolled back) lands here as an append-only row. The offline evolvers
(Memento, AlphaEvolver) render this ledger into their generation prompts so
the complete acceptance history is visible before the next proposal — the
paper's mechanism for ensuring "rejected interventions are not proposed
again".

Read-side consumers are the EVOLVER PROMPTS ONLY. The runtime agent never
sees this ledger (W4: the inference agent must not read the raw wiki).
"""
from __future__ import annotations

import difflib
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DIFF_MAX_CHARS = 4000
_SUMMARY_MAX_CHARS = 500
_REASON_MAX_CHARS = 500

_STATUSES = ("accepted", "rejected", "rolled_back")


def unified_diff(parent_code: Optional[str], mutated_code: Optional[str]) -> Optional[str]:
    """Unified diff of a code mutation, capped — the ledger's `diff` column."""
    if not parent_code or not mutated_code:
        return None
    diff = "\n".join(difflib.unified_diff(
        parent_code.splitlines(), mutated_code.splitlines(),
        fromfile="parent", tofile="mutated", lineterm="",
    ))
    if not diff:
        return None
    return diff[:_DIFF_MAX_CHARS]


def record_outcome(
    db: Any,
    *,
    tenant_id: str,
    target: str,
    source: str,
    status: str,
    stage: str = "",
    reason: str = "",
    agent_id: Optional[str] = None,
    proposal_summary: str = "",
    diff: Optional[str] = None,
    validation_score: Optional[float] = None,
    mutation_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Append one acceptance-history row. Never raises — the ledger must not
    be able to break the pipeline that feeds it. Returns the row id."""
    if status not in _STATUSES:
        status = "rejected"
    try:
        from core.auto_dev.models import SkillImpactEntry

        row = SkillImpactEntry(
            tenant_id=tenant_id,
            agent_id=agent_id,
            target=(target or "unknown")[:255],
            source=(source or "unknown")[:50],
            status=status,
            stage=(stage or "")[:40] or None,
            reason=(reason or "")[:_REASON_MAX_CHARS] or None,
            proposal_summary=(proposal_summary or "")[:_SUMMARY_MAX_CHARS] or None,
            unified_diff=diff,
            validation_score=validation_score,
            mutation_id=mutation_id,
            payload=payload,
        )
        db.add(row)
        db.commit()
        return row.id
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.debug("skill-impact ledger write skipped: %s", e)
        return None


def record_pipeline_outcome(db: Any, request: Any, result: Any) -> Optional[str]:
    """Adapter: append the ledger row for one UnifiedEvolutionPipeline run."""
    try:
        diff = unified_diff(
            getattr(request, "parent_code", None),
            getattr(request, "mutated_code", None),
        )
        summary = getattr(request, "config_key", "") or ""
        extra = getattr(request, "extra", None) or {}
        if isinstance(extra, dict) and extra.get("summary"):
            summary = f"{summary}: {extra['summary']}"
        return record_outcome(
            db,
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            target=request.config_key,
            source=request.source,
            status="accepted" if result.passed else "rejected",
            stage=result.stage,
            reason=result.reason,
            proposal_summary=summary,
            diff=diff,
            mutation_id=result.mutation_id,
            payload={"rollback_mutation_id": result.rollback_mutation_id} if result.rollback_mutation_id else None,
        )
    except Exception as e:
        logger.debug("skill-impact pipeline adapter skipped: %s", e)
        return None


def record_rollback(db: Any, mutation_id: str) -> bool:
    """Mark the accepted entry for a deployed mutation as rolled back. The
    skill is reverted but the knowledge (that this mutation did not stick)
    stays in the wiki — WikiSkill: the wiki is never rolled back."""
    if not mutation_id:
        return False
    try:
        from core.auto_dev.models import SkillImpactEntry

        rows = (
            db.query(SkillImpactEntry)
            .filter(SkillImpactEntry.mutation_id == mutation_id)
            .all()
        )
        changed = False
        for row in rows:
            if row.status == "accepted":
                row.status = "rolled_back"
                changed = True
        if changed:
            db.commit()
        return changed
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.debug("skill-impact rollback mark skipped: %s", e)
        return False


def rejection_history(
    db: Any,
    tenant_id: str,
    target: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """The most recent ledger entries for a tenant/target — proposer context.
    Failure of the read side degrades to an empty history, never an error."""
    try:
        from core.auto_dev.models import SkillImpactEntry

        q = db.query(SkillImpactEntry).filter(SkillImpactEntry.tenant_id == tenant_id)
        if target:
            q = q.filter(SkillImpactEntry.target == target)
        if agent_id:
            # agent-specific entries plus agent-agnostic ones (agent_id NULL)
            q = q.filter((SkillImpactEntry.agent_id == agent_id)
                         | (SkillImpactEntry.agent_id.is_(None)))
        rows = q.order_by(SkillImpactEntry.created_at.desc()).limit(limit).all()
        return [
            {
                "target": r.target,
                "source": r.source,
                "status": r.status,
                "stage": r.stage,
                "reason": r.reason,
                "proposal_summary": r.proposal_summary,
                "mutation_id": r.mutation_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.debug("skill-impact history read skipped: %s", e)
        return []


def format_history_block(entries: List[Dict[str, Any]]) -> str:
    """Render the ledger as the proposer prompt block. Empty when there is
    no history (fresh install / first proposal)."""
    if not entries:
        return ""
    lines = [
        "SKILL ACCEPTANCE HISTORY — outcomes of previous evolution proposals.",
        "Do NOT re-propose a rejected intervention; build on the recorded",
        "rejection reasons instead.",
    ]
    for e in entries:
        mark = f"[{e.get('status')}"
        if e.get("stage"):
            mark += f"@{e['stage']}"
        mark += "]"
        what = e.get("proposal_summary") or e.get("target") or ""
        why = f" — {e['reason']}" if e.get("reason") else ""
        lines.append(f"  {mark} {e.get('target')}: {what}{why}")
    return "\n".join(lines)


def proposer_history_block(
    db: Any,
    tenant_id: str,
    target: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Query + format in one call, for the evolver prompt paths."""
    return format_history_block(rejection_history(db, tenant_id, target=target, agent_id=agent_id, limit=limit))


def new_mutation_id() -> str:
    return f"pipe_{uuid.uuid4().hex[:12]}"
