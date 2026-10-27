"""Final turn-envelope resolution — controlled clock regressions."""

from core.turn_resolution import resolve_review_envelope


def _review(ok=True, gaps=None):
    return {
        "ok": ok,
        "assessments": [{
            "subject_id": "O-1001",
            "decision": "Process",
            "unresolved_requirements": list(gaps or []),
        }],
    }


def test_valid_review_before_deadline_completes_the_turn():
    success, outcome, error = resolve_review_envelope(
        review_required=True,
        review_result=_review(),
        reviewed_at_elapsed_s=80.0,
        deadline_total_s=95.0,
        cancelled=False,
        current_success=False,
        current_outcome="unconfirmed",
        current_error_code="outcome_unconfirmed",
    )
    assert success is True
    assert outcome == "completed"
    assert error is None


def test_valid_review_with_gaps_is_partial_not_completed():
    success, outcome, error = resolve_review_envelope(
        review_required=True,
        review_result=_review(gaps=["currency missing"]),
        reviewed_at_elapsed_s=80.0,
        deadline_total_s=95.0,
        cancelled=False,
        current_success=False,
        current_outcome="unconfirmed",
        current_error_code="outcome_unconfirmed",
    )
    assert success is True
    assert outcome == "partial"
    assert error is None


def test_review_after_cancellation_never_mutates_the_expired_turn():
    success, outcome, error = resolve_review_envelope(
        review_required=True,
        review_result=_review(),
        reviewed_at_elapsed_s=96.0,
        deadline_total_s=95.0,
        cancelled=True,
        current_success=False,
        current_outcome="failed",
        current_error_code="turn_budget_exceeded",
    )
    assert success is False
    assert outcome == "failed"
    assert error == "turn_budget_exceeded"


def test_review_arriving_after_deadline_is_not_certified():
    success, outcome, error = resolve_review_envelope(
        review_required=True,
        review_result=_review(),
        reviewed_at_elapsed_s=95.2,
        deadline_total_s=95.0,
        cancelled=False,
        current_success=False,
        current_outcome="unconfirmed",
        current_error_code="outcome_unconfirmed",
    )
    assert success is False
    assert outcome == "unconfirmed"


def test_unvalidated_review_fails_the_turn():
    success, outcome, error = resolve_review_envelope(
        review_required=True,
        review_result=_review(ok=False),
        reviewed_at_elapsed_s=40.0,
        deadline_total_s=95.0,
        cancelled=False,
        current_success=True,
        current_outcome="completed",
        current_error_code=None,
    )
    assert success is False
    assert outcome == "failed"
    assert error == "turn_objective_not_met"


def test_review_without_a_clock_reading_cannot_claim_completion():
    success, outcome, error = resolve_review_envelope(
        review_required=True,
        review_result=_review(),
        reviewed_at_elapsed_s=None,
        deadline_total_s=95.0,
        cancelled=False,
        current_success=False,
        current_outcome="unconfirmed",
        current_error_code="outcome_unconfirmed",
    )
    assert success is False
    assert outcome == "unconfirmed"
