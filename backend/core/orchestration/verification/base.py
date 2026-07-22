"""Domain-aware verification cascade — base types.

Swarm Coordination's parallel branches previously aggregated their
results with a single domain-blind strategy (JSON-normalised majority
vote → per-key frequency reconciliation). Different task domains need
different notions of "correct": code must *run*, math must be *provable*,
extraction must be *schema-valid*, prose has no cheap ground truth.

This package provides a :class:`Verifier` strategy per domain, plus a
:class:`VerificationOrchestrator` dispatcher (see ``dispatcher.py``) that
selects one, runs it, and falls back to voting if no winner emerges.

Design contract:
  * ``UNKNOWN`` domain → :attr:`VerificationStrategy.VOTING`, which
    reproduces the original algorithm *byte for byte* (see
    ``voting.py``). Existing behaviour is therefore preserved.
  * Every verifier degrades gracefully: if a required dependency or
    input is missing it returns ``winner=None`` and the orchestrator
    transparently falls back to voting. The swarm is never worse off
    than today.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ===========================================================================
# Strategy + Result
# ===========================================================================
class VerificationStrategy(str, Enum):
    """How a set of parallel-branch candidates is verified.

    Members roughly ordered from cheapest / most deterministic to most
    expensive / most subjective.
    """

    VOTING = "voting"          # Symbolic majority + per-key frequency reconcile
    SCHEMA = "schema"          # JSON-schema / required-field validation
    EXECUTION = "execution"    # Run the candidate in a sandbox; tests are oracle
    FORMAL = "formal"          # SymPy equivalence on numeric/symbolic answers
    GROUNDED = "grounded"      # LLM faithfulness check against retrieved sources
    JUDGE = "judge"            # LLM-as-judge ranks free-form candidates
    CODE_PIPELINE = "code_pipeline"  # Coding: reconcile action dicts → execute code


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of verifying one step's parallel-branch candidates.

    Attributes:
        winner: the selected candidate (any shape — typically a dict),
            or ``None`` if no strategy could pick one.
        strategy: the strategy that produced ``winner``. When a
            domain-specific strategy fails and the orchestrator falls
            back to voting, this is set to ``VOTING`` and
            :attr:`fallback_used` is ``True``.
        domain: the resolved :class:`~core.orchestration.verification.domain.TaskDomain`.
        confidence: a strategy-specific score in ``[0.0, 1.0]``. Voting
            uses the agreement ratio; verifiers that pick the first
            passing candidate use ``1.0`` on success.
        fallback_used: ``True`` iff a non-voting strategy returned
            ``winner=None`` and the orchestrator substituted voting.
        details: strategy-specific diagnostics (exit code, ranking,
            evidence snippets, etc.) for observability and Field Guide
            feedback.
        reason: short human-readable note about why this winner was
            chosen (or why verification fell back).
    """

    winner: Optional[Any]
    strategy: VerificationStrategy
    domain: Any  # TaskDomain, typed loosely to avoid import cycle
    confidence: float = 0.0
    fallback_used: bool = False
    details: Dict[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None

    @staticmethod
    def empty(domain: Any, strategy: VerificationStrategy, reason: Optional[str] = None) -> "VerificationResult":
        """A no-winner result that signals the orchestrator to fall back."""
        return VerificationResult(
            winner=None,
            strategy=strategy,
            domain=domain,
            confidence=0.0,
            fallback_used=False,
            reason=reason,
        )


# ===========================================================================
# Verifier ABC
# ===========================================================================
class Verifier(ABC):
    """Strategy interface — turn N candidates into one (or None)."""

    strategy: VerificationStrategy = VerificationStrategy.VOTING

    @abstractmethod
    async def verify(
        self,
        candidates: List[Any],
        step: Any,
        context: Any,
    ) -> VerificationResult:
        """Pick a winner from ``candidates``.

        Never raises — on failure, return a :class:`VerificationResult`
        with ``winner=None`` and a ``reason`` so the orchestrator can
        fall back to voting.
        """
        ...


def serialise(value: Any) -> str:
    """Stable string form for equality / Counter comparison.

    Mirrors the ``json.dumps(r, sort_keys=True) if isinstance(r, dict)
    else str(r)`` form used by the original consensus logic so voting
    remains byte-compatible with prior behaviour.
    """
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value, sort_keys=True)
    return str(value)


__all__ = [
    "VerificationStrategy",
    "VerificationResult",
    "Verifier",
    "serialise",
    "replace",
]
