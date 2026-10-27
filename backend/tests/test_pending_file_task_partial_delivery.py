from core.pending_file_task import (
    build_pending_task,
    settle_retrieval_task,
)


def test_delivered_partial_calculation_is_terminal_and_keeps_gaps():
    task = build_pending_task(
        "adjustments_smoke.xlsx",
        "calculate approved Adjustments rows; name gaps and withhold total",
    )
    gap = {
        "item": "0055",
        "sheet": "Adjustments",
        "cell": "C5",
        "field": "Qty",
        "reason": "missing quantity",
    }

    settled = settle_retrieval_task(
        task,
        {"file_name": "adjustments_smoke.xlsx", "content_hash": "hash-1"},
        retrieval_finished=True,
        answer_delivered=True,
        calculation_complete=False,
        open_requirements=[gap],
    )

    assert settled["status"] == "delivered"
    assert settled["retrieval_finished"] is True
    assert settled["calculation_complete"] is False
    assert settled["open_requirements"] == [gap]
    assert settled["resolved_file"]["file_name"] == "adjustments_smoke.xlsx"


def test_unfinished_retrieval_is_not_marked_delivered():
    task = build_pending_task("orders.xlsx", "review O-1001")

    settled = settle_retrieval_task(
        task,
        None,
        retrieval_finished=False,
        answer_delivered=False,
        calculation_complete=False,
    )

    assert settled["status"] == "pending"
    assert "retrieval_finished" not in settled
    assert "calculation_complete" not in settled


def test_retrieved_but_undelivered_answer_stays_retrieved():
    task = build_pending_task("orders.xlsx", "review O-1001")

    settled = settle_retrieval_task(
        task,
        {"file_name": "orders.xlsx"},
        retrieval_finished=True,
        answer_delivered=False,
        calculation_complete=True,
    )

    assert settled["status"] == "retrieved"
    assert settled["answer_delivered"] is False
    assert settled["calculation_complete"] is True


def test_boolean_aggregate_marker_never_supplies_gaps():
    from core.pending_file_task import aggregate_calculation_facts

    complete, gaps = aggregate_calculation_facts(True, fallback_complete=False)
    assert complete is False
    assert gaps == []


def test_actual_aggregate_record_supplies_gaps_and_partial_status():
    from core.pending_file_task import aggregate_calculation_facts

    record = {
        "complete": False,
        "gaps": [{"item": "0055", "cell": "C5", "field": "Qty"}],
    }
    complete, gaps = aggregate_calculation_facts(
        record, fallback_complete=True)
    assert complete is False
    assert gaps == [{"item": "0055", "cell": "C5", "field": "Qty"}]
