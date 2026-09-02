"""Verification panel — judge VOTE for mission-critical / high-complexity
reply turns.

Research basis: Verga et al. 2024 (Cohere), "Replacing Judges with Juries"
(arXiv 2404.18796) — a panel of diverse models voting independently beats a
single large judge with less intra-model bias at a fraction of the cost.
This module composes that pattern with the repo's shipped R83 stack:
``SelfConsistencyVoter`` (Wang et al. majority vote) + ``ATOM_SC_FANOUT``
(cross-provider sample diversity) + USC fallback.

Scope discipline: the panel costs N extra structured calls, so it runs ONLY
on mission-critical or COMPLEX/ADVANCED turns (see ``is_high_stakes``) and
only when ``ATOM_VERIFY_PANEL`` is shadow/enforce (default off — R83
convention: flag-gated, shadow first, promotion via eval gate).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from pydantic import BaseModel

from core.hallucination_config import is_sc_fanout_enabled
from core.llm.self_consistency_voter import SelfConsistencyVoter

logger = logging.getLogger(__name__)

# High-complexity tier values (analyze_query_complexity .value) that count
# as verification-worthy. "High complexity" per product direction = the top
# two tiers; SIMPLE/MODERATE chat never pays the panel cost.
_HIGH_STAKES_COMPLEXITIES = {"complex", "advanced"}


def is_high_stakes_turn(complexity_value: Any, mission_critical: bool) -> bool:
    """Mission-critical marker OR top-two complexity tiers."""
    if mission_critical:
        return True
    return str(complexity_value or "").lower() in _HIGH_STAKES_COMPLEXITIES


class VerifyVerdict(BaseModel):
    """One judge sample's verdict on an answer vs its evidence."""
    grounded: bool = True
    unsupported_claims: list[str] = []
    note: str = ""


JUDGE_SYSTEM = (
    "You are a strict grounding verifier. You are given RESEARCH CONTEXT "
    "(evidence retrieved by tools) and an ANSWER written from it. Decide "
    "whether every factual claim in the ANSWER is supported by the CONTEXT. "
    "Rules: opinions and recommendations about what to emphasize are NOT "
    "factual claims — only verify factual assertions (companies, people, "
    "numbers, events, capabilities). Mark grounded=true unless you can name "
    "specific claims the CONTEXT does not support. Be conservative: "
    "unsupported means the context contradicts or plainly lacks the claim."
)

JUDGE_PROMPT_TEMPLATE = (
    "RESEARCH CONTEXT (retrieved evidence):\n{context}\n\n"
    "ANSWER TO VERIFY:\n{answer}\n\n"
    "Return the grounding verdict."
)


def _schedule_run_record(
    result: Dict[str, Any], *, agent_id: str | None, tenant_id: str
) -> None:
    """Fire-and-forget persistence of one panel run (VerifyPanelRun).

    Verdicts were previously computed + logged only — without a durable
    record there is no evidence base for the opt-in shadow→enforce latch and
    no queryable history. Best-effort: persistence failure must never touch
    the reply path."""
    try:
        from core.database import SessionLocal
        from core.models import VerifyPanelRun

        def _write() -> None:
            db = SessionLocal()
            try:
                db.add(VerifyPanelRun(
                    tenant_id=tenant_id or None,
                    agent_id=agent_id,
                    ran=bool(result.get("ran")),
                    grounded=result.get("grounded"),
                    agreement=result.get("agreement"),
                    level=result.get("level"),
                    samples=result.get("samples"),
                    error=result.get("error"),
                ))
                db.commit()
            except Exception as e:
                logger.debug(f"verify panel run record failed: {e}")
            finally:
                db.close()

        asyncio.get_running_loop().create_task(asyncio.to_thread(_write))
    except Exception as e:
        logger.debug(f"verify panel run record skipped: {e}")


def get_panel_run_stats(db) -> Dict[str, Any]:
    """Health stats over the most recent panel runs — the evidence base the
    maintenance loop's opt-in shadow→enforce latch gates on (and a ready-made
    dashboard feed)."""
    from core.models import VerifyPanelRun

    rows = (
        db.query(VerifyPanelRun)
        .order_by(VerifyPanelRun.created_at.desc())
        .limit(500)
        .all()
    )
    total = len(rows)
    ran_rows = [r for r in rows if r.ran]
    agreements = [r.agreement for r in ran_rows if r.agreement is not None]
    return {
        "total": total,
        "ran": len(ran_rows),
        "ran_rate": round(len(ran_rows) / total, 3) if total else 0.0,
        "mean_agreement": (
            round(sum(agreements) / len(agreements), 3) if agreements else 0.0
        ),
    }


async def verify_reply(
    answer: str,
    evidence: str,
    *,
    handler: Any,
    tenant_id: str = "default",
    samples: int = 3,
    agent_id: str | None = None,
) -> Dict[str, Any]:
    """Judge an answer against its evidence with a VOTING panel.

    N diverse-provider judge samples (provider fan-out when
    ``ATOM_SC_FANOUT`` is on — the R83 stack) return a VerifyVerdict each;
    the modal verdict + agreement metadata come back as:

        {"ran": True, "grounded": bool, "agreement": float,
         "level": str, "claims": [...], "samples": int}

    ``{"ran": False, "error": ...}`` on any failure — callers must treat
    ran=False as "verification unavailable", never as "verified".
    """
    result: Dict[str, Any]
    if not answer or not evidence:
        result = {"ran": False, "error": "empty answer or evidence"}
        _schedule_run_record(result, agent_id=agent_id, tenant_id=tenant_id)
        return result
    try:
        voter = SelfConsistencyVoter(handler=handler, tenant_id=tenant_id)
        vote_result = await voter.vote_with_consensus(
            prompt=JUDGE_PROMPT_TEMPLATE.format(
                context=evidence[:6000], answer=answer[:4000]
            ),
            response_model=VerifyVerdict,
            temperature=0.0,
            max_tokens=500,
            sample_count=samples,
            agent_id=agent_id,
            system_instruction=JUDGE_SYSTEM,
        )
        if vote_result is None or vote_result.winner is None:
            result = {"ran": False, "error": "panel produced no verdict"}
        else:
            winner: VerifyVerdict = vote_result.winner
            result = {
                "ran": True,
                "grounded": bool(winner.grounded),
                "claims": list(winner.unsupported_claims or []),
                "note": winner.note,
                "agreement": round(vote_result.agreement_ratio, 3),
                "level": vote_result.level,
                "samples": vote_result.valid_count,
                "fanout": vote_result.fanout_targets,
            }
    except Exception as e:
        result = {"ran": False, "error": str(e)}
    _schedule_run_record(result, agent_id=agent_id, tenant_id=tenant_id)
    return result
