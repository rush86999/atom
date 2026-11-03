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


def _send_step(result):
    step = new_step(
        step_id="send", title="send", operation_type="outbound",
        adapter="email.send_outlook", effect="external", inputs={})
    step["operation_id"] = "op-send-1"
    step["status"] = "applied"
    step["result"] = result
    return step


def _send_criteria():
    return [
        {"criterion_id": "provider_accepted:send",
         "kind": "provider_accepted", "required": True},
        {"criterion_id": "sent_record_confirmed:send",
         "kind": "sent_record_confirmed", "required": True},
    ]


def _criterion_results(verdict):
    return {
        item["criterion"]: item
        for item in verdict["outcome"]["criterion_results"]
    }


def test_provider_acceptance_alone_does_not_confirm_sent_record():
    assignment = _assignment(
        [_send_step({"provider_state": "accepted",
                     "provider_ref": "prov-1"})],
        _send_criteria())
    verdict = build_assignment_outcome(assignment)
    results = _criterion_results(verdict)
    assert results["provider_accepted"]["met"] is True
    assert results["sent_record_confirmed"]["met"] is None
    assert verdict["verdict"] is not True
    assert "sent_record_confirmed" not in (
        verdict["outcome"].get("delivery") or {})


def test_matching_explicit_sent_items_readback_satisfies_confirmation():
    assignment = _assignment(
        [_send_step({
            "provider_state": "accepted",
            "provider_ref": "prov-1",
            "receipt": {"readback": {"sent_items": {
                "present": True, "operation_id": "op-send-1",
                "provider_ref": "prov-1"}}},
        })],
        _send_criteria())
    verdict = build_assignment_outcome(assignment)
    results = _criterion_results(verdict)
    assert results["provider_accepted"]["met"] is True
    assert results["sent_record_confirmed"]["met"] is True
    assert verdict["verdict"] is True
    assert verdict["state"] == "satisfied"


def test_mismatched_sent_items_binding_does_not_confirm():
    assignment = _assignment(
        [_send_step({
            "provider_state": "accepted",
            "provider_ref": "prov-1",
            "receipt": {"readback": {"sent_items": {
                "present": True, "operation_id": "op-send-1",
                "provider_ref": "prov-OTHER"}}},
        })],
        _send_criteria())
    verdict = build_assignment_outcome(assignment)
    assert _criterion_results(verdict)["sent_record_confirmed"]["met"] is False
    assert verdict["verdict"] is False


def test_absent_sent_items_readback_stays_unresolved():
    assignment = _assignment(
        [_send_step({"provider_state": "sent", "provider_ref": "prov-1"})],
        [{"criterion_id": "sent_record_confirmed:send",
          "kind": "sent_record_confirmed", "required": True}])
    verdict = build_assignment_outcome(assignment)
    assert verdict["state"] == "unresolved"
    assert verdict["verdict"] is None


def test_explicit_sent_readback_stands_without_provider_state():
    assignment = _assignment(
        [_send_step({
            "provider_ref": "prov-1",
            "readback": {"sent_items": {
                "present": True, "operation_id": "op-send-1",
                "provider_ref": "prov-1"}},
        })],
        [{"criterion_id": "sent_record_confirmed:send",
          "kind": "sent_record_confirmed", "required": True}])
    verdict = build_assignment_outcome(assignment)
    assert verdict["state"] == "satisfied"
    assert verdict["verdict"] is True


def test_recipient_delivery_stays_unresolved_after_acceptance():
    assignment = _assignment(
        [_send_step({"provider_state": "accepted",
                     "provider_ref": "prov-1"})],
        [{"criterion_id": "delivery_confirmed:send",
          "kind": "delivery_confirmed", "required": True}])
    verdict = build_assignment_outcome(assignment)
    assert verdict["state"] == "unresolved"
    assert verdict["verdict"] is None
    assert "delivery_confirmed" not in (
        verdict["outcome"].get("delivery") or {})
