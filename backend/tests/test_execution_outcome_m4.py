import pytest

from core.execution_outcome import (
    STORAGE_KEY,
    IllegalTransition,
    RECORD_VERSION,
    load_operation_records,
    new_operation_record,
    open_dimensions,
    record_from_dict,
    record_to_dict,
    store_operation_record,
    transition,
)


def test_m4_new_record_starts_unknown_with_identity():
    record = new_operation_record(
        operation_id="op-1",
        execution_id="exec-1",
        objective_id="obj-1",
        operation_class="mutation",
        producer="test",
    )

    assert record["record_version"] == RECORD_VERSION == 1
    assert record["operation_id"] == "op-1"
    assert record["execution_id"] == "exec-1"
    assert record["objective_id"] == "obj-1"
    assert open_dimensions(record) == [
        "execution_status",
        "evidence_sufficiency",
        "result_verification",
        "delivery_status",
    ]
    assert "success" not in record
    assert "task_success" not in record


def test_m4_execution_lifecycle_and_terminal_states():
    record = new_operation_record()
    transition(record, "execution_status", "running", producer="execution")
    transition(record, "execution_status", "succeeded", producer="execution")

    assert record["execution_status"] == "succeeded"
    assert [t["to"] for t in record["transitions"]] == ["running", "succeeded"]
    assert record["transitions"][0]["producer"] == "execution"
    with pytest.raises(IllegalTransition):
        transition(record, "execution_status", "failed", producer="execution")
    with pytest.raises(IllegalTransition):
        transition(record, "execution_status", "running", producer="execution")


def test_m4_dimensions_stay_independent():
    record = new_operation_record()
    transition(record, "execution_status", "running", producer="execution")
    transition(record, "execution_status", "succeeded", producer="execution")
    transition(record, "result_verification", "unverified", producer="verifier")

    assert record["execution_status"] == "succeeded"
    assert record["result_verification"] == "unverified"
    assert open_dimensions(record) == ["evidence_sufficiency", "delivery_status"]


def test_m4_evidence_contradiction_is_terminal():
    record = new_operation_record()
    transition(record, "evidence_sufficiency", "partial", producer="evidence")
    transition(record, "evidence_sufficiency", "contradictory", producer="evidence")

    assert record["evidence_sufficiency"] == "contradictory"
    with pytest.raises(IllegalTransition):
        transition(record, "evidence_sufficiency", "sufficient", producer="evidence")


def test_m4_verification_unknown_never_guesses():
    record = new_operation_record()

    assert record["result_verification"] is None
    with pytest.raises(IllegalTransition):
        transition(record, "result_verification", "bogus", producer="verifier")
    transition(record, "result_verification", "unverified", producer="verifier")
    transition(record, "result_verification", "verified", producer="verifier")

    assert record["result_verification"] == "verified"
    with pytest.raises(IllegalTransition):
        transition(record, "result_verification", "unverified", producer="verifier")


def test_m4_objective_revision_lineage_rides_along():
    record = new_operation_record(
        objective_id="obj-2",
        supersedes_objective_id="obj-1",
        refinement_basis="user narrowed the file set",
    )

    assert record["objective_id"] == "obj-2"
    assert record["supersedes_objective_id"] == "obj-1"
    assert record["refinement_basis"] == "user narrowed the file set"


def test_m4_record_round_trips_through_storage():
    record = new_operation_record(operation_id="op-9", execution_id="exec-9")
    transition(record, "execution_status", "running", producer="execution")
    transition(record, "delivery_status", "streaming", producer="delivery")

    loaded = record_from_dict(record_to_dict(record))

    assert loaded == record
    with pytest.raises(ValueError):
        record_from_dict({**record_to_dict(record), "record_version": 999})
    with pytest.raises(ValueError):
        record_from_dict("not-a-record")


def test_m4_loaded_records_are_detached_copies():
    record = new_operation_record(operation_id="op-1", execution_id="exec-1")
    transition(record, "execution_status", "running", producer="execution")
    metadata = store_operation_record({}, record)

    loaded = load_operation_records(metadata)
    transition(loaded["op-1"], "execution_status", "succeeded", producer="execution")

    assert load_operation_records(metadata)["op-1"]["execution_status"] == "running"


def test_m4_stored_values_are_validated():
    stored = record_to_dict(new_operation_record())
    stored["result_verification"] = "maybe"

    with pytest.raises(ValueError):
        record_from_dict(stored)


def test_m4_storage_key_merges_without_clobbering():
    first = new_operation_record(operation_id="op-1", execution_id="exec-1")
    transition(first, "execution_status", "succeeded", producer="execution")
    metadata = store_operation_record({"task_outcome": {"a": 1}}, first)
    second = new_operation_record(operation_id="op-2", execution_id="exec-1")
    merged = store_operation_record(metadata, second)

    assert merged["task_outcome"] == {"a": 1}
    operations = merged[STORAGE_KEY]["operations"]
    assert set(operations) == {"op-1", "op-2"}
    assert operations["op-1"]["execution_status"] == "succeeded"
    assert load_operation_records(merged)["op-2"]["execution_status"] is None


def test_m4_storage_load_skips_foreign_shapes():
    assert load_operation_records(None) == {}
    assert load_operation_records({"other": 1}) == {}
    assert load_operation_records({STORAGE_KEY: {"operations": "nope"}}) == {}
    foreign = record_to_dict(new_operation_record(operation_id="op-x"))
    foreign["record_version"] = 999
    assert load_operation_records({STORAGE_KEY: {"operations": {"op-x": foreign}}}) == {}
