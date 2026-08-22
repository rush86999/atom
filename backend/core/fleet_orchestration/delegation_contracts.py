"""Delegation contracts + effort scaling (AGENT_ORG_POLITICS_PLAN.md Phase 1).

Anthropic's production orchestrator-worker finding (R2): the top lever for
multi-agent quality is an *explicit delegation contract* — objective, output
format, tool guidance, task boundaries — plus effort scaled to query
complexity. Vague instructions caused duplicate/conflicting subagent work.

This module is pure prompt/schema machinery: it builds contracts, renders
them into a prompt block, and recommends effort budgets. It never calls an
LLM and never touches the DB.

Flag: ATOM_DELEGATION_CONTRACTS_ENABLED (default ON).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_STEPS_CAP = 30
MAX_TOOL_CALLS_CAP = 120


def contracts_enabled() -> bool:
    return os.getenv("ATOM_DELEGATION_CONTRACTS_ENABLED", "true").lower() == "true"


# ---------------------------------------------------------------------------
# Effort scaling — deterministic keyword table (no LLM spend). Mirrors
# Anthropic's embedded scaling rules: simple fact-finding ≈ 1 agent / few
# calls; broad comparisons more; complex research most (capped by sandbox).
# ---------------------------------------------------------------------------

_COMPLEX_SIGNALS = (
    "comprehensive", "exhaustive", "analyze all", "across every",
    "in depth", "in-depth", "compare every", "all segments", "end to end",
    "end-to-end", "thorough", "multi-domain", "research everything",
)
_MODERATE_SIGNALS = (
    "analyze", "compare", "summarize across", "investigate", "audit",
    "report", "trend", "forecast",
)


def recommended_effort(task_text: str) -> Dict[str, int]:
    """Deterministic complexity → effort budget mapping."""
    text = (task_text or "").lower()
    hits = sum(1 for s in _COMPLEX_SIGNALS if s in text)
    moderate = sum(1 for s in _MODERATE_SIGNALS if s in text)

    if hits >= 2:
        max_steps, max_calls = 20, 80
    elif hits == 1 or moderate >= 3:
        max_steps, max_calls = 12, 40
    elif moderate >= 1:
        max_steps, max_calls = 8, 20
    else:
        max_steps, max_calls = 4, 8

    return {
        "max_steps": min(max_steps, MAX_STEPS_CAP),
        "max_tool_calls": min(max_calls, MAX_TOOL_CALLS_CAP),
    }


# ---------------------------------------------------------------------------
# Contract model
# ---------------------------------------------------------------------------


@dataclass
class DelegationContract:
    """Typed handoff between a coordinator and a specialist (R2).

    Every field exists because its absence caused real duplicate/missed work
    in production orchestrators: without boundaries specialists overlap;
    without output_format results can't be aggregated reliably.
    """

    objective: str
    output_format: str = "concise markdown answer"
    tool_guidance: List[str] = field(default_factory=list)
    task_boundaries: str = (
        "Only this task; do not re-do other members' scope; stop when done."
    )
    effort_budget: Dict[str, int] = field(
        default_factory=lambda: {"max_steps": 8, "max_tool_calls": 20}
    )
    # RACI accountability tag (IMACS R3): when set, the deliverable's final
    # review routes through this agent — accountability only matters when
    # the protocol routes through the accountable party.
    accountable_agent_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "objective": self.objective,
            "output_format": self.output_format,
            "tool_guidance": list(self.tool_guidance),
            "task_boundaries": self.task_boundaries,
            "effort_budget": dict(self.effort_budget),
        }
        if self.accountable_agent_id:
            d["accountable_agent_id"] = self.accountable_agent_id
        return d

    @classmethod
    def from_dict(cls, raw: Any) -> "DelegationContract":
        if not isinstance(raw, dict):
            return cls(objective=str(raw or ""))
        data = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        if "objective" in data:
            data["objective"] = str(data["objective"])
        return cls(**data)


def build_contract(
    *,
    goal: str,
    task_desc: str,
    domain: str,
    tool_guidance: Optional[List[str]] = None,
    output_format: Optional[str] = None,
) -> DelegationContract:
    """Build a contract for one delegated sub-task."""
    objective = f"{task_desc.strip()} (fleet goal: {goal.strip()})"
    domain_hint = {
        "finance": "prefer accounting/data tools over web search",
        "sales": "query CRM data first; cite deal ids",
        "marketing": "use campaign analytics sources; avoid PII",
    }.get((domain or "").lower())
    guidance = list(tool_guidance or [])
    if domain_hint:
        guidance.insert(0, domain_hint)
    return DelegationContract(
        objective=objective,
        output_format=output_format
        or "structured markdown with a short findings list",
        tool_guidance=guidance,
        effort_budget=recommended_effort(f"{task_desc} {goal}"),
    )


def render_contract_prompt(contract: DelegationContract) -> str:
    """Render the contract as a specialist-facing prompt block."""
    lines = [
        "## DELEGATION CONTRACT",
        f"OBJECTIVE: {contract.objective}",
        f"OUTPUT FORMAT: {contract.output_format}",
    ]
    if contract.tool_guidance:
        lines.append("TOOL GUIDANCE:")
        for g in contract.tool_guidance:
            lines.append(f"- {g}")
    lines.append(f"BOUNDARIES: {contract.task_boundaries}")
    budget = contract.effort_budget
    lines.append(
        f"EFFORT: at most {budget.get('max_steps', 8)} reasoning steps and "
        f"{budget.get('max_tool_calls', 20)} tool calls; finish within that."
    )
    return "\n".join(lines)


def contract_for_link(
    *, goal: str, sub_task: Dict[str, Any]
) -> DelegationContract:
    """Build the contract for one fleet recruitment sub-task dict.

    Pure: does not mutate ``sub_task``.
    """
    return build_contract(
        goal=goal,
        task_desc=str(sub_task.get("task", "")),
        domain=str(sub_task.get("domain", "general")),
    )


def maybe_contract_for_link(
    *, goal: str, sub_task: Dict[str, Any]
) -> Optional[DelegationContract]:
    """Flag-gated variant used at wire-in points (None when disabled)."""
    if not contracts_enabled():
        return None
    try:
        return contract_for_link(goal=goal, sub_task=sub_task)
    except Exception as e:  # noqa: BLE001 — additive only, fail open to None
        logger.debug(f"contract build failed: {e}")
        return None
