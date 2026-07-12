"""
Outcome-based response quality assessment for LLM routing feedback.

Derives real quality signals from observable response characteristics so the
per-model predictors can learn from response *quality* — not just "did the
API call return non-exceptionally". These signals populate the previously
placeholder fields on ``RoutingFeedback`` (``quality_satisfied``,
``user_satisfaction``).

Honest caveat: this is a heuristic *proxy*, not a substitute for real user
feedback. It lets predictors learn facts like "model X truncates long
prompts", "model Y refuses this task type", and "model Z fails structured
output." It is intentionally conservative — it only marks a response as
quality-unsatisfied when there is concrete evidence of a problem.

Signals considered:
  - finish_reason == "length" → truncated response
  - empty / whitespace-only content → no usable output
  - refusal markers in content → model declined the task
  - schema_error → structured output failed to parse/validate
  - exception → the API call itself failed

The graded ``quality_score`` (0.0–1.0) gives the predictor a continuous
signal rather than a binary, which trains better than a hard 0/1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# Short, conservative refusal markers. Kept deliberately tight to avoid
# false positives on legitimate content that happens to mention safety.
_REFUSAL_MARKERS = (
    "i'm sorry, but i can't",
    "i'm sorry, but i cannot",
    "i cannot assist with that",
    "i can't assist with that",
    "as an ai language model, i cannot",
    "as an ai, i cannot",
    "i'm not able to fulfill this request",
)


@dataclass
class ResponseQuality:
    """Assessed quality of one LLM response."""

    success: bool  # The API call returned non-exceptionally
    quality_satisfied: bool  # The content met a basic quality bar
    quality_score: float  # 0.0–1.0, a heuristic user_satisfaction proxy
    issues: List[str] = field(default_factory=list)


def assess_response_quality(
    content: Optional[str],
    finish_reason: Optional[str] = None,
    schema_error: bool = False,
    exception: Optional[Exception] = None,
) -> ResponseQuality:
    """Assess response quality from observable characteristics.

    Args:
        content: The response text (``choices[0].message.content``), or None.
        finish_reason: The provider's finish reason (``choices[0].finish_reason``).
        schema_error: True if structured-output validation failed (e.g. a
            pydantic ValidationError or JSON decode error from instructor).
        exception: The exception if the API call raised, else None.

    Returns:
        A ResponseQuality with success/quality_satisfied/score/issues populated.
    """
    issues: List[str] = []

    # --- Hard failure: the API call itself raised. ---
    if exception is not None:
        return ResponseQuality(
            success=False,
            quality_satisfied=False,
            quality_score=0.0,
            issues=[_classify_exception(exception)],
        )

    # From here, the API call returned — ``success`` is True. Whether the
    # *content* satisfies quality is assessed below.
    text = (content or "").strip()

    # --- Schema/structured-output validation failure. ---
    # The API worked, but the model produced unparseable/invalid structured
    # output. That's a real quality problem worth learning from.
    if schema_error:
        issues.append("schema_error")
        return ResponseQuality(
            success=True,
            quality_satisfied=False,
            quality_score=0.2,
            issues=issues,
        )

    # --- Truncation: finish_reason says we ran out of token budget. ---
    if finish_reason == "length":
        issues.append("truncated")
        # Got *something* but incomplete — better than empty, worse than refusal.
        return ResponseQuality(
            success=True,
            quality_satisfied=False,
            quality_score=0.3 if text else 0.1,
            issues=issues,
        )

    # --- Empty content. ---
    if not text:
        issues.append("empty")
        return ResponseQuality(
            success=True,
            quality_satisfied=False,
            quality_score=0.1,
            issues=issues,
        )

    # --- Refusal: content starts with a known refusal marker. ---
    lowered = text.lower()
    if any(lowered.startswith(m) for m in _REFUSAL_MARKERS):
        issues.append("refusal")
        return ResponseQuality(
            success=True,
            quality_satisfied=False,
            quality_score=0.4,
            issues=issues,
        )

    # --- Otherwise: a substantive, complete response. ---
    # Graded score so the predictor sees a continuous signal. Longer
    # substantive responses (up to a healthy cap) score slightly higher than
    # terse ones, since extreme brevity on a non-trivial prompt is a weak
    # quality signal. Capped well below 1.0 — a heuristic can't certify
    # excellence, only absence of detected problems.
    score = 0.7
    if len(text) >= 200:
        score = 0.8
    if len(text) >= 800:
        score = 0.85
    # Diminish very long runs that may indicate padding/repetition.
    if len(text) > 8000:
        score = 0.78

    return ResponseQuality(
        success=True,
        quality_satisfied=True,
        quality_score=min(score, 0.95),
        issues=issues,
    )


def _classify_exception(exc: Exception) -> str:
    """Map common provider exceptions to a short issue label."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "timeout" in name or "timeout" in msg:
        return "timeout"
    if "rate" in msg and "limit" in msg:
        return "rate_limited"
    if "context" in msg and "length" in msg:
        return "context_length"
    if "auth" in name or "unauthorized" in msg or "api key" in msg:
        return "auth_error"
    if "connection" in name or "network" in msg or "unreachable" in msg:
        return "network_error"
    return "provider_error"
