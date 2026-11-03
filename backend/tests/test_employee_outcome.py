"""Assignment completion is a business-criteria verdict, not last-step state."""
from __future__ import annotations

from core.assignment_plan import new_assignment, new_step, new_teaching_snapshot
from core.task_outcome_contract import build_assignment_outcome


def _assignment(steps, criteria):
    return new_assignment(
        objective="Prepare a feasible quote",
        workspace_id="ws-a", tenant_id="t-a",
        teaching_snapshot=new_teaching_snapshot(revision="teach-1"),
        steps=steps, completion_criteria=criteria)


def _step(step_id="calculate", status="applied", result=None):
    step = new_step(
        step_id=step_id, title=step_id, operation_type="calculate",
        adapter="quote.calculate", inputs={})
    step["status"] = status
    step["result"] = result
    return step


def test_applied_steps_satisfy_required_work_criterion():
    assignment = _assignment(
        [_step(result={"value": 494.75, "unit": "USD"})],
        [{"criterion_id": "required_work_complete:assignment",
          "kind": "required_work_complete", "required": True}])
    verdict = build_assignment_outcome(assignment)
    assert verdict["state"] == "satisfied"
    assert verdict["verdict"] is True


def test_failed_required_branch_keeps_outcome_unsatisfied_even_if_state_claimed():
    assignment = _assignment(
        [_step(result={"value": 476.75, "unit": "USD"}),
         _step("delivery", status="failed")],
        [{"criterion_id": "required_work_complete:assignment",
          "kind": "required_work_complete", "required": True}])
    verdict = build_assignment_outcome(assignment, state="completed")
    assert verdict["state"] == "unsatisfied"
    assert verdict["verdict"] is False
    assert verdict["declared_state"] == "completed"


def test_missing_artifact_evidence_stays_unresolved_not_green():
    assignment = _assignment(
        [_step(result={"value": 494.75, "unit": "USD"})],
        [{"criterion_id": "artifact_verified:quote",
          "kind": "artifact_verified", "required": True}])
    verdict = build_assignment_outcome(assignment)
    assert verdict["state"] == "unresolved"
    assert verdict["verdict"] is None


def test_verified_artifact_criterion_can_be_satisfied():
    assignment = _assignment(
        [_step(result={
            "value": 494.75, "unit": "USD",
            "artifact": {"revision": "rev-1", "sha256": "sha-1"}})],
        [{"criterion_id": "artifact_verified:quote",
          "kind": "artifact_verified", "required": True}])
    verdict = build_assignment_outcome(assignment)
    assert verdict["state"] == "satisfied"
    assert verdict["outcome"]["delivery"]["artifact_sha256"] == "sha-1"
