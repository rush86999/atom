"""Task domain classification for the verification cascade.

A step's domain decides which verification strategy the orchestrator
applies. Domains are resolved *hybrid*:

  1. **Explicit** — if the caller tagged
     ``step.parameters["task_domain"]`` with a known
     :class:`TaskDomain` value, that wins. This is the controllable,
     deterministic path.
  2. **Inferred** — otherwise :func:`infer_domain` inspects the step's
     capability / name / description / parameters for domain keywords
     and returns the best-scoring domain, or :attr:`TaskDomain.UNKNOWN`.

The explicit tag exists so high-stakes callers can opt in precisely;
the inference path exists so the cascade is useful without requiring
every caller to change. When inference is used, the orchestrator can
record a Field Guide insight noting the inferred mapping — so
workspaces accumulate feedback on which inferences pay off.
"""
from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any, Dict, Optional

from core.orchestration.verification.base import VerificationStrategy

logger = logging.getLogger(__name__)


class TaskDomain(str, Enum):
    """Coarse task taxonomy used to pick a verification strategy.

    Coarse on purpose: the verification literature (MAV, AlphaCodium,
    VERGE) clusters tasks by *what kind of ground-truth signal is
    available*, not by surface form. These six buckets capture that
    distinction with minimum vocabulary.
    """

    UNKNOWN = "unknown"          # → VOTING (preserves original behaviour)
    CODE = "code"                # → EXECUTION (tests are oracle)
    MATH = "math"                # → FORMAL (provability)
    QA = "qa"                    # → GROUNDED (faithfulness to sources)
    EXTRACTION = "extraction"    # → SCHEMA (cheapest strong signal)
    PLANNING = "planning"        # → VOTING (self-consistency semantics)
    PROSE = "prose"              # → JUDGE (no ground truth; LLM judge)


# ---------------------------------------------------------------------------
# Default mapping — rationale documented in SWARM_COORDINATION.md §4.
# ---------------------------------------------------------------------------
DOMAIN_STRATEGY_MAP: Dict[TaskDomain, VerificationStrategy] = {
    TaskDomain.UNKNOWN: VerificationStrategy.VOTING,
    TaskDomain.CODE: VerificationStrategy.CODE_PIPELINE,
    TaskDomain.MATH: VerificationStrategy.FORMAL,
    TaskDomain.QA: VerificationStrategy.GROUNDED,
    TaskDomain.EXTRACTION: VerificationStrategy.SCHEMA,
    TaskDomain.PLANNING: VerificationStrategy.VOTING,
    TaskDomain.PROSE: VerificationStrategy.JUDGE,
}


# ---------------------------------------------------------------------------
# Keyword tables for inference. Tuned to favour precision over recall:
# a mis-tag is usually recoverable (the verifier falls back to voting)
# but noisy matches make Field Guide feedback misleading.
# ---------------------------------------------------------------------------
_DOMAIN_KEYWORDS: Dict[TaskDomain, frozenset] = {
    TaskDomain.CODE: frozenset({
        "code", "function", "implement", "refactor", "python", "javascript",
        "typescript", "java", "golang", "rust", "sql", "query", "compile",
        "syntax", "bug", "debug", "test", "unittest", "pytest", "class",
        "method", "api", "endpoint", "library", "module", "script", "regex",
    }),
    TaskDomain.MATH: frozenset({
        "math", "arithmetic", "algebra", "calculus", "equation", "solve",
        "compute", "calculate", "derivative", "integral", "matrix", "vector",
        "theorem", "proof", "polynomial", "factor", "simplify", "evaluate",
        "sum", "product", "probability", "statistics",
    }),
    TaskDomain.QA: frozenset({
        "question", "answer", "faq", "rag", "retriev", "grounded",
        "knowledge", "document", "cite", "citation", "context", "passage",
        "faq", "ask", "inquiry",
    }),
    TaskDomain.EXTRACTION: frozenset({
        "extract", "parse", "schema", "json", "yaml", "field", "entity",
        "structured", "tabulate", "classify", "label", "tag", "normalise",
        "normalize", "transform", "map", "record",
    }),
    TaskDomain.PLANNING: frozenset({
        "plan", "workflow", "orchestrat", "schedule", "step", "procedure",
        "task", "roadmap", "strategy", "action", "agent", "multi-step",
        "coordinate",
    }),
    TaskDomain.PROSE: frozenset({
        "write", "draft", "summar", "essay", "article", "blog", "email",
        "letter", "report", "review", "critique", "edit", "rewrite",
        "paraphrase", "story", "narrative", "content", "copy",
    }),
}


def _step_text(step: Any) -> str:
    """Lowercased, space-joined haystack of a step's free-text fields.

    Duck-typed on ``step`` (no import of WorkflowStep) to avoid a
    circular dependency with ``conductor_agent``. Includes a JSON dump
    of ``parameters`` so the explicit ``task_domain`` tag is itself
    visible — though :func:`resolve_domain` short-circuits before this
    matters. The parameters dump also surfaces any caller-supplied
    keywords the agent stashed there.
    """
    parts = []
    for attr in ("capability", "name", "description"):
        val = getattr(step, attr, None)
        if val:
            parts.append(str(val))
    params = getattr(step, "parameters", None)
    if params:
        try:
            parts.append(json.dumps(params, sort_keys=True, default=str))
        except (TypeError, ValueError):
            parts.append(str(params))
    return " ".join(parts).lower()


def infer_domain(step: Any) -> TaskDomain:
    """Guess the domain from a step's textual fields.

    Scores each domain by counting keyword hits in the haystack. Returns
    the highest-scoring domain, or :attr:`TaskDomain.UNKNOWN` on a tie /
    no hits. Pure and deterministic.
    """
    text = _step_text(step)
    if not text:
        return TaskDomain.UNKNOWN

    scores: Dict[TaskDomain, int] = {}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            scores[domain] = hits

    if not scores:
        return TaskDomain.UNKNOWN

    best_domain = max(scores, key=scores.get)
    # Tie-break: if two domains share the top score, be conservative
    # and return UNKNOWN rather than guessing. The orchestrator will
    # then fall back to VOTING (today's behaviour).
    top_score = scores[best_domain]
    tied = [d for d, s in scores.items() if s == top_score]
    if len(tied) > 1:
        return TaskDomain.UNKNOWN
    return best_domain


def resolve_domain(step: Any) -> TaskDomain:
    """Hybrid domain resolution: explicit tag first, else inference.

    Reads ``step.parameters.get("task_domain")``. Accepts a
    :class:`TaskDomain` instance, the matching string value, or the
    enum member name (case-insensitive). Anything unrecognised is
    logged and falls through to inference.
    """
    params = getattr(step, "parameters", None)
    if isinstance(params, dict):
        raw = params.get("task_domain")
        if raw is not None:
            resolved = _coerce_domain(raw)
            if resolved is not None:
                return resolved
            logger.debug(
                "Unrecognised task_domain=%r on step %s; falling back to inference",
                raw, getattr(step, "step_id", "?"),
            )
    return infer_domain(step)


def _coerce_domain(raw: Any) -> Optional[TaskDomain]:
    """Best-effort coercion of a raw tag value to a TaskDomain."""
    if isinstance(raw, TaskDomain):
        return raw
    if isinstance(raw, str):
        # Try value first ("code"), then name ("CODE"), case-insensitive.
        normalised = raw.strip().lower()
        for member in TaskDomain:
            if member.value == normalised or member.name.lower() == normalised:
                return member
    return None


def resolve_strategy(
    step: Any,
    domain: TaskDomain,
    domain_strategy_map: Optional[Dict[TaskDomain, VerificationStrategy]] = None,
) -> VerificationStrategy:
    """Pick a strategy: explicit step override, else the domain map.

    Callers may set ``step.parameters["verification_strategy"]`` to
    force a particular strategy regardless of domain — useful for
    A/B testing or for domains that don't yet have a dedicated
    verifier (e.g. planning defaults to VOTING but a caller might want
    JUDGE).
    """
    params = getattr(step, "parameters", None)
    if isinstance(params, dict):
        raw = params.get("verification_strategy")
        if raw is not None:
            coerced = _coerce_strategy(raw)
            if coerced is not None:
                return coerced
            logger.debug(
                "Unrecognised verification_strategy=%r on step %s; using domain map",
                raw, getattr(step, "step_id", "?"),
            )

    strategy_map = domain_strategy_map if domain_strategy_map is not None else DOMAIN_STRATEGY_MAP
    return strategy_map.get(domain, VerificationStrategy.VOTING)


def _coerce_strategy(raw: Any) -> Optional[VerificationStrategy]:
    if isinstance(raw, VerificationStrategy):
        return raw
    if isinstance(raw, str):
        normalised = raw.strip().lower()
        for member in VerificationStrategy:
            if member.value == normalised or member.name.lower() == normalised:
                return member
    return None


__all__ = [
    "TaskDomain",
    "DOMAIN_STRATEGY_MAP",
    "infer_domain",
    "resolve_domain",
    "resolve_strategy",
]
