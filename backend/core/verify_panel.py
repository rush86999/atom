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

from typing import Any, Dict

from pydantic import BaseModel

from core.hallucination_config import is_sc_fanout_enabled
from core.llm.self_consistency_voter import SelfConsistencyVoter

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
    if not answer or not evidence:
        return {"ran": False, "error": "empty answer or evidence"}
    try:
        voter = SelfConsistencyVoter(handler=handler, tenant_id=tenant_id)
        result = await voter.vote_with_consensus(
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
        if result is None or result.winner is None:
            return {"ran": False, "error": "panel produced no verdict"}
        winner: VerifyVerdict = result.winner
        return {
            "ran": True,
            "grounded": bool(winner.grounded),
            "claims": list(winner.unsupported_claims or []),
            "note": winner.note,
            "agreement": round(result.agreement_ratio, 3),
            "level": result.level,
            "samples": result.valid_count,
            "fanout": result.fanout_targets,
        }
    except Exception as e:
        return {"ran": False, "error": str(e)}
