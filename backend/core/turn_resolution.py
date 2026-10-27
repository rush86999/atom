"""One final turn-envelope resolution.

Response, persisted metadata and history must all consume the same outcome.
A validated review that was committed before the deadline outranks a
provisional fallback envelope; a review that arrives after cancellation never
turns the expired request into success; a required review without a certified
assessment is a failed turn.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.review_result import review_completion


def resolve_review_envelope(
    *,
    review_required: bool,
    review_result: Optional[Dict[str, Any]],
    reviewed_at_elapsed_s: Optional[float],
    deadline_total_s: Optional[float],
    cancelled: bool,
    current_success: bool,
    current_outcome: Optional[str],
    current_error_code: Optional[str],
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Return ``(success, outcome, error_code)`` for this turn.

    ``reviewed_at_elapsed_s`` is the clock reading when the assessment was
    created, not when finalization noticed it. That distinction is what
    prevents a late worker from certifying an expired request.
    """
    if not review_required:
        return current_success, current_outcome, current_error_code
    if cancelled:
        # The request is already cancelled/expired. Never mutate it into a
        # success after the fact.
        return current_success, current_outcome, current_error_code
    ok = bool(
        isinstance(review_result, dict)
        and review_result.get("ok") is True)
    if ok:
        if reviewed_at_elapsed_s is None:
            # A certified assessment without its clock reading cannot prove
            # it was committed before the deadline. Only a disabled budget
            # (no deadline) may accept it.
            within = deadline_total_s is None or float(
                deadline_total_s or 0) <= 0
        else:
            within = bool(
                deadline_total_s is None
                or float(deadline_total_s or 0) <= 0
                or float(reviewed_at_elapsed_s) <= float(deadline_total_s))
        if within:
            completion = review_completion(review_result)
            if completion == "incomplete":
                return False, "failed", "turn_objective_not_met"
            return True, completion, None
        # A required review outside its clock is not success, even when the
        # provisional same-turn envelope already looked successful.
        return False, "failed", "turn_objective_not_met"
    return False, "failed", "turn_objective_not_met"
