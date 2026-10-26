from core.finalization import (
    FINALIZATION_VERSION,
    UNKNOWN_OUTCOME_MESSAGE,
    execution_record_from_row,
    finalize_payload,
)


EXECUTION_ID = "execution-m1"
FROZEN_MESSAGE = "Message processed successfully"
FROZEN_FAILURE = "fetch_fresh_data_section() got an unexpected keyword argument " "'existing_evidence_contract'"


def test_m1_finalizer_reports_failure_without_baseline():
    execution = {
        "execution_id": EXECUTION_ID,
        "status": "failed",
        "result_summary": FROZEN_FAILURE,
        "failure_stage": "execution",
    }
    drafted = {
        "success": False,
        "message": FROZEN_MESSAGE,
        "execution_id": None,
        "model": None,
        "data": {"deterministic_delivery": True},
    }

    result = finalize_payload(execution, drafted)

    assert FINALIZATION_VERSION == "m1"
    assert "baseline_id" not in result
    assert result["execution_id"] == EXECUTION_ID
    assert result["success"] is False
    assert result["error_code"] == "execution_failed"
    assert FROZEN_MESSAGE not in result["message"]
    assert "success" not in result["message"].lower()
    assert FROZEN_FAILURE in result["message"]
    assert result["data"] == {}


def test_m1_unknown_execution_replaces_route_fallback_text():
    result = finalize_payload(
        None,
        {"success": True, "message": FROZEN_MESSAGE, "data": {}},
    )

    assert "baseline_id" not in result
    assert result["success"] is False
    assert FROZEN_MESSAGE not in result["message"]
    assert result["message"] == UNKNOWN_OUTCOME_MESSAGE
    assert "execution_id" not in result


def test_m1_healthy_execution_leaves_content_unchanged():
    execution = {"execution_id": EXECUTION_ID, "status": "completed"}
    drafted = {
        "success": True,
        "message": "All requested checks are complete.",
        "execution_id": EXECUTION_ID,
        "data": {"checked": 3},
    }

    result = finalize_payload(execution, drafted)

    assert result == drafted


def test_m1_execution_row_accepts_decoded_metadata():
    record = execution_record_from_row(
        {
            "id": "persisted-row",
            "status": "failed",
            "result_summary": FROZEN_FAILURE,
            "metadata_json": {"continuation": {"failure_stage": "execution"}},
        },
        EXECUTION_ID,
    )

    assert record["failure_stage"] == "execution"


def test_m1_frozen_execution_row_maps_to_failed_outcome():
    record = execution_record_from_row(
        {
            "id": "persisted-row",
            "status": "failed",
            "result_summary": FROZEN_FAILURE,
            "metadata_json": '{"continuation": {"failure_stage": "execution"}}',
        },
        EXECUTION_ID,
    )
    result = finalize_payload(
        record,
        {"success": False, "message": FROZEN_MESSAGE, "data": {}},
    )

    assert record == {
        "execution_id": EXECUTION_ID,
        "status": "failed",
        "result_summary": FROZEN_FAILURE,
        "failure_stage": "execution",
    }
    assert result["execution_id"] == EXECUTION_ID
    assert result["success"] is False
    assert FROZEN_FAILURE in result["message"]


def test_resolved_task_outcome_maps_to_completed():
    """A criteria-derived verdict on the execution row settles the envelope.

    The resumed file read recorded objective_met=True from a verified
    source_scoped_retrieval receipt, but execution_record_from_row dropped
    task_outcome and the delivered response stayed outcome=null.
    """
    record = execution_record_from_row(
        {
            "id": "persisted-row",
            "status": "success",
            "result_summary": "delivered",
            "metadata_json": {"task_outcome": {"objective_met": True}},
        },
        EXECUTION_ID,
    )

    result = finalize_payload(
        record,
        {"success": True, "message": "delivered", "data": {}},
    )

    assert record["task_outcome"]["objective_met"] is True
    assert result["outcome"] == "completed"
    assert result["success"] is True


def test_unresolved_task_outcome_leaves_outcome_unset():
    """Unknown/absent criteria must stay null — never rounded to success."""
    record = execution_record_from_row(
        {
            "id": "persisted-row",
            "status": "success",
            "result_summary": "delivered",
            "metadata_json": {"task_outcome": {"objective_met": None}},
        },
        EXECUTION_ID,
    )

    result = finalize_payload(
        record,
        {"success": True, "message": "delivered", "data": {}},
    )

    assert "outcome" not in result


def test_failed_task_outcome_maps_to_failed():
    """An explicitly unmet objective is a failure, not a silent success."""
    record = execution_record_from_row(
        {
            "id": "persisted-row",
            "status": "success",
            "result_summary": "reply delivered",
            "metadata_json": {"task_outcome": {"objective_met": False}},
        },
        EXECUTION_ID,
    )

    result = finalize_payload(
        record,
        {"success": True, "message": "reply delivered", "data": {}},
    )

    assert result["outcome"] == "failed"
    assert result["success"] is False
    assert result["error_code"] == "turn_objective_not_met"


def test_failed_execution_is_never_rounded_to_completed():
    """A failed execution outranks a contradictory objective verdict."""
    record = execution_record_from_row(
        {
            "id": "persisted-row",
            "status": "failed",
            "result_summary": "write failed",
            "metadata_json": {"task_outcome": {"objective_met": True}},
        },
        EXECUTION_ID,
    )

    result = finalize_payload(
        record,
        {"success": True, "message": "", "data": {}},
    )

    assert result["success"] is False
    assert result.get("outcome") != "completed"


def test_unknown_execution_status_never_settles_completed():
    """A missing/unknown execution state keeps its unknown disposition.

    The 2026-10-26 control reproduced status=unknown plus
    task_outcome.objective_met=True producing success=False with
    outcome=completed. Unknown must not acquire a completed outcome.
    """
    for status in ("unknown", None, ""):
        record = execution_record_from_row(
            {
                "id": "persisted-row",
                "status": status,
                "result_summary": "",
                "metadata_json": {"task_outcome": {"objective_met": True}},
            },
            EXECUTION_ID,
        )

        result = finalize_payload(
            record,
            {"success": True, "message": "unsettled", "data": {}},
        )

        assert result["success"] is False
        assert result.get("outcome") != "completed"


def test_established_completed_status_settles_completed():
    record = execution_record_from_row(
        {
            "id": "persisted-row",
            "status": "completed",
            "result_summary": "delivered",
            "metadata_json": {"task_outcome": {"objective_met": True}},
        },
        EXECUTION_ID,
    )

    result = finalize_payload(
        record,
        {"success": True, "message": "delivered", "data": {}},
    )

    assert result["outcome"] == "completed"
    assert result["success"] is True


def test_existing_partial_and_queued_outcomes_are_preserved():
    """A criteria verdict must not overwrite a richer upstream state."""
    for existing in ("partial", "continuation_queued"):
        record = execution_record_from_row(
            {
                "id": "persisted-row",
                "status": "success",
                "result_summary": "delivered",
                "metadata_json": {"task_outcome": {"objective_met": False}},
            },
            EXECUTION_ID,
        )

        result = finalize_payload(
            record,
            {"success": True, "message": "delivered", "outcome": existing},
        )

        assert result["outcome"] == existing
        assert result["success"] is True
