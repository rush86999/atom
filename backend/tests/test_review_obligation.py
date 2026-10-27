from core.chat_tool_planner import review_requested


def test_review_obligation_survives_bare_confirmation():
    task = {
        "status": "pending",
        "original_message": (
            "Using the uploaded orders.xlsx, review O-1001 against the "
            "policy. Cite the row and state process or escalate."),
    }

    assert review_requested(task, "go ahead") is True


def test_review_obligation_survives_recovery_text():
    task = {
        "status": "retrieved",
        "original_message": "Review O-1010 and explain the policy basis.",
    }

    assert review_requested(task, "go ahead") is True


def test_non_review_task_does_not_gain_review_obligation():
    task = {
        "status": "pending",
        "original_message": "Show me the values in orders.xlsx.",
    }

    assert review_requested(task, "go ahead") is False


def test_review_obligation_uses_current_message_when_task_has_none():
    assert review_requested(None, "Assess O-1001 and recommend a decision.") is True
    assert review_requested(None, "go ahead") is False


from core.turn_decision import pending_task_continuation_ready
from core.review_result import deterministic_read_fallback_allowed


def test_narration_failure_never_serves_raw_read_for_review():
    assert deterministic_read_fallback_allowed(
        review_required=True,
        deterministic_answer="O-1001 row: Status=On Hold ...") is False


def test_narration_failure_may_serve_verified_read_for_plain_lookup():
    assert deterministic_read_fallback_allowed(
        review_required=False,
        deterministic_answer="O-1001 row: Status=On Hold ...") is True
    assert deterministic_read_fallback_allowed(
        review_required=False, deterministic_answer="") is False



def test_pending_task_confirmation_fast_path_reuses_resolved_file():
    task = {
        "status": "pending",
        "original_message": "Review O-1001 against the policy.",
        "resolved_file": {"file_name": "orders.xlsx"},
    }

    ready = pending_task_continuation_ready("go ahead", task)

    assert ready is not None
    assert ready["reference"]["resolved_file"] == "orders.xlsx"
    assert ready["reference"]["state"] == "resolved"
    assert ready["fields"] == []


def test_pending_task_fast_path_rejects_non_confirmation_or_missing_file():
    task = {"status": "pending", "resolved_file": {"file_name": "orders.xlsx"}}
    assert pending_task_continuation_ready("review the workbook", task) is None
    assert pending_task_continuation_ready(
        "go ahead", {"status": "pending"}) is None
