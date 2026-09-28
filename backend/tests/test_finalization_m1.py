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
