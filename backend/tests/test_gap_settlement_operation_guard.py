"""Only an exact question settlement may supersede its waiting operation."""
import copy

import pytest

from core.task_lifecycle import _supersede_gap_settlement_operations


@pytest.mark.parametrize("mutation", [
    None, "already_resolved", "missing_prior", "wrong_operation",
    "foreign_assignment", "wrong_step", "applied_operation", "wrong_value",
    "other_transition",
])
def test_settlement_cannot_supersede_unrelated_material(mutation):
    prior = {"unresolved": [{"question_id": "q-exact", "status": "open",
                             "source_operation": "op-exact"}]}
    current = {"unresolved": [{"question_id": "q-exact", "status": "resolved",
                               "resolution_value": "answer-exact"}]}
    operation = {"operation_id": "op-exact", "assignment_id": "job-exact",
                 "step_id": "step-exact", "status": "waiting"}
    peer = {"operation_id": "peer-op", "assignment_id": "peer-job",
            "step_id": "peer-step", "status": "waiting"}
    assignment = {"assignment_id": "job-exact", "steps": [
        {"step_id": "step-exact", "gap_ids": ["q-exact"]}]}
    transition = {"kind": "record_unresolved", "supersede_operations": ["op-exact", "peer-op"],
                  "resolutions": [{"question_id": "q-exact", "value": "answer-exact"}]}
    if mutation == "already_resolved":
        prior["unresolved"][0]["status"] = "resolved"
    elif mutation == "missing_prior":
        prior["unresolved"] = []
    elif mutation == "wrong_operation":
        prior["unresolved"][0]["source_operation"] = "different-op"
    elif mutation == "foreign_assignment":
        operation["assignment_id"] = "different-job"
    elif mutation == "wrong_step":
        operation["step_id"] = "different-step"
    elif mutation == "applied_operation":
        operation["status"] = "applied"
    elif mutation == "wrong_value":
        current["unresolved"][0]["resolution_value"] = "different-answer"
    elif mutation == "other_transition":
        transition["kind"] = "other"
    operations = [operation, peer]
    before = copy.deepcopy(operations)
    result = _supersede_gap_settlement_operations(
        current, operations, assignment, transition, previous_task=prior)
    assert operations == before, "the source operation snapshot must remain immutable"
    assert result[1] == peer
    assert result[0]["status"] == ("superseded" if mutation is None else operation["status"])
