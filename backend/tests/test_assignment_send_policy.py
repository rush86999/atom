"""Server-side send policy for the draft-and-approval release."""
import pytest

import core.assignment_controlled_transport  # noqa: F401 — registers the adapter
from core.assignment_planner import AssignmentPlanError, plan_assignment


def _outbound():
    return {
        "to": ["live-acceptance@example.invalid"],
        "subject": "Policy test",
        "body": "Grounded body.",
    }


def test_live_send_is_refused_by_default(monkeypatch):
    monkeypatch.delenv("ATOM_ASSIGNMENT_ALLOW_LIVE_SEND", raising=False)
    with pytest.raises(AssignmentPlanError, match="not authorized"):
        plan_assignment(
            objective="Send a policy test",
            outbound=_outbound(),
            deliverables=[],
        )


def test_controlled_outbox_remains_available_for_isolated_acceptance(monkeypatch):
    monkeypatch.delenv("ATOM_ASSIGNMENT_ALLOW_LIVE_SEND", raising=False)
    plan = plan_assignment(
        objective="Send a policy test through the controlled adapter",
        outbound=_outbound(),
        sources=[{"kind": "document", "resource_id": "r1"}],
        deliverables=[],
        transport_adapter="assignment.controlled_outbox",
        workspace_id="default",
        tenant_id="default",
        employee_id="employee-1",
        authorized_actions=["retrieve", "outbound"],
    )
    adapters = [step.get("adapter") for step in plan["steps"]]
    assert "assignment.controlled_outbox" in adapters
    assert "email.send_outlook" not in adapters


def _plan_with_attachments(**overrides):
    outbound = {
        **_outbound(),
        "attachment_ids": ["staged_abc"],
        "attachment_hashes": {"staged_abc": "a" * 64},
    }
    outbound.update(overrides)
    return plan_assignment(
        objective="Send an exact approved attachment",
        outbound=outbound,
        sources=[{"kind": "document", "resource_id": "r1"}],
        deliverables=[],
        transport_adapter="assignment.controlled_outbox",
        workspace_id="default",
        tenant_id="default",
        employee_id="employee-1",
        authorized_actions=["retrieve", "outbound"],
    )


def test_attachment_ids_without_sha_binding_are_refused():
    with pytest.raises(AssignmentPlanError, match="sha256 binding"):
        _plan_with_attachments(attachment_hashes={})


def test_attachment_sha_binding_is_carried_into_the_send_step():
    plan = _plan_with_attachments()
    send = next(step for step in plan["steps"] if step["step_id"] == "send")
    assert send["inputs"]["attachment_ids"] == ["staged_abc"]
    assert send["inputs"]["attachment_hashes"] == {"staged_abc": "a" * 64}


def test_attachment_sha_binding_must_name_exactly_the_sent_ids():
    with pytest.raises(AssignmentPlanError, match="exactly"):
        _plan_with_attachments(attachment_hashes={"staged_other": "a" * 64})
