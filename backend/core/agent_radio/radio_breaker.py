"""Responsibility-breakpoint classifier: when does a team make sense?

The paper's rule: "A fixed multi-agent team should not become the default
response to every engineering task." A team is only worthwhile when the task
contains a responsibility breakpoint — a place where a competent engineer
would involve another person because the work crosses an ownership boundary,
needs an independent hypothesis, or carries enough risk to justify separate
verification.

The classifier is deterministic (keyword heuristics) so it is cheap,
testable, and never stalls the agent loop. It gates thread auto-attachment
for fleet runs only (`ATOM_RADIO_BREAKPOINT_GATE`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

BREAKPOINT_PATTERNS: List[str] = [
    r"legacy",
    r"unfamiliar",
    r"migration",
    r"multi[- ]module",
    r"cross[- ]service",
    r"incident",
    r"root[- ]cause",
    r"security (audit|review|analysis)",
    r"refactor",
    r"integration",
    r"api integration",
    r"coordinat",
    r"dependenc",
]

BOUNDED_PATTERNS: List[str] = [
    r"one[- ]file",
    r"boilerplate",
    r"rename a\b",
    r"add a comment",
    r"fix typo",
    r"small change",
]


@dataclass
class BreakpointVerdict:
    triggered: bool
    reasons: List[str] = field(default_factory=list)
    score: int = 0


def classify_responsibility_breakpoints(task_description: str) -> BreakpointVerdict:
    """Score a task description for responsibility breakpoints.

    A positive verdict means the work likely crosses an ownership boundary
    (multiple interdependent subtasks, independent hypotheses, verification
    risk) and a fleet run should get a lateral radio thread. Bounded local
    work (one-file changes, boilerplate, renames) always scores zero —
    match those patterns first so they override keyword hits.
    """
    text = (task_description or "").lower()
    if not text.strip():
        return BreakpointVerdict(triggered=False, reasons=["empty task"], score=0)

    for pat in BOUNDED_PATTERNS:
        if re.search(pat, text):
            return BreakpointVerdict(
                triggered=False, reasons=["bounded local work"], score=0
            )

    reasons = [pat for pat in BREAKPOINT_PATTERNS if re.search(pat, text)]
    return BreakpointVerdict(
        triggered=len(reasons) >= 2, reasons=reasons, score=len(reasons)
    )


def should_attach_thread(task_description: str) -> BreakpointVerdict:
    """Decision hook used by the fleet adapter (flag-gated)."""
    from core.agent_radio import radio_config

    if not radio_config.breakpoint_gate_enabled():
        return BreakpointVerdict(triggered=False, reasons=["gate disabled"], score=0)
    return classify_responsibility_breakpoints(task_description)