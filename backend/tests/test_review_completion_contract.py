"""Review completion: decision basis is not unfinished review work."""
from __future__ import annotations

import json

from core.review_contract import (
    build_accepted_contract,
    same_contract_inputs,
)
from core.review_result import (
    build_review_result,
    render_review_result,
    review_completion,
)
from core.turn_resolution import resolve_review_envelope

ORDER_PROMPT = (
    "Using the uploaded orders.xlsx, review order {order} against the "
    "order processing policy. Cite Order ID, Status, Qty, Unit Price, "
    "Currency, Approval 1, Approval 2, Manager Exception, and Notes from "
    "the row. State process or escalate and explain the policy basis. "
    "Do not send, approve, or modify anything."
)
LESSONS = [
    {
        "id": "policy-1",
        "topic": "Order processing policy",
        "lesson": "Recommend routine orders when records are complete.",
        "decision_options": ["Process", "Escalate"],
    },
    {
        "id": "correction-1",
        "topic": "Order policy correction",
        "lesson": (
            "O-1010 is on credit hold. Manager M. Chen directed on "
            "2026-10-25 that O-1010 must be escalated despite a complete "
            "record."),
        "decision_options": ["Process", "Escalate"],
    },
]
SOURCE = {
    "file_name": "orders.xlsx",
    "resource_id": "sha1:orders",
    "content_hash": "hash-1",
}


def _evidence(*subjects):
    out = []
    for subject in subjects or ("O-1010",):
        row = "R11" if subject == "O-1010" else "R2"
        out.append({
            "evidence_id": f"ev:{subject}:Orders!{row}",
            "subject_id": subject,
            "source_identity": dict(SOURCE),
            "retrieval_operation": "attempt-1",
            "retrieval_execution_id": "read-exec-1",
            "row_ref": f"Orders!{row}",
            "values": [],
        })
    return out


def _policy():
    return [
        {
            "policy_id": lesson["id"],
            "topic": lesson["topic"],
            "lesson": lesson["lesson"],
        }
        for lesson in LESSONS
    ]


def _contract(objective=None, *, source_version="hash-1"):
    return build_accepted_contract(
        objective or ORDER_PROMPT.format(order="O-1010"),
        catalogued_names=["orders.xlsx"],
        source_version=source_version,
        lessons=LESSONS,
    )


def _build(contract, assessments, *, requested=("O-1010",),
           action_receipts=None):
    answer = (
        "Review complete.\n\n```review_result\n"
        + json.dumps({"assessments": assessments})
        + "\n```"
    )
    return build_review_result(
        execution_id="delivery-exec-1",
        expected_execution_id="delivery-exec-1",
        requested_records=list(requested),
        answer=answer,
        allowed_decisions=["Process", "Escalate"],
        evidence_index=_evidence(*requested),
        policy_index=_policy(),
        accepted_contract=contract,
        action_receipts=action_receipts,
    )


def _assessment(decision="Process", *, basis=None, unresolved=None,
                policy_ids=None):
    return {
        "subject_id": "O-1010",
        "decision": decision,
        "basis": list(basis or []),
        "evidence_ids": ["ev:O-1010:Orders!R11"],
        "policy_ids": list(policy_ids or ["policy-1"]),
        "unresolved_requirements": list(unresolved or []),
    }


def _resolve(review):
    return resolve_review_envelope(
        review_required=True,
        review_result=review,
        reviewed_at_elapsed_s=50.0,
        deadline_total_s=95.0,
        cancelled=False,
        current_success=False,
        current_outcome="unconfirmed",
        current_error_code="outcome_unconfirmed",
    )


def test_prohibited_action_is_not_a_required_action():
    contract = _contract(
        ORDER_PROMPT.format(order="O-1010")
        + " Do not update anything.")
    assert contract["required_actions"] == []


def test_changed_action_requirement_invalidates_repeat_reuse():
    base = _contract()
    action = _contract(
        ORDER_PROMPT.format(order="O-1010")
        + " Also send the escalation to the manager.")
    assert same_contract_inputs(base, base) is True
    assert same_contract_inputs(base, action) is False


def test_recommendation_with_complete_evidence_is_completed():
    review = _build(_contract(), [_assessment()])
    assert review["ok"] is True
    assert review["completion"] == "completed"
    assert _resolve(review) == (True, "completed", None)


def test_escalation_restriction_is_basis_not_unfinished_review():
    review = _build(
        _contract(),
        [_assessment(
            "Escalate",
            basis=[
                "O-1010 is on credit hold; Manager M. Chen directed "
                "escalation on 2026-10-25."],
            unresolved=[],
        )],
    )
    assessment = review["assessments"][0]
    assert review["completion"] == "completed"
    assert assessment["basis"]
    assert assessment["accepted_unresolved_requirements"] == []
    assert "Open requirements" not in render_review_result(review)
    assert "Basis:" in render_review_result(review)
    assert _resolve(review) == (True, "completed", None)


def test_legacy_business_condition_in_unresolved_is_not_an_obligation():
    """The captured pre-fix shape: a policy-supported restriction in the
    unresolved field. It is preserved as basis, not a platform gap."""
    review = _build(
        _contract(),
        [_assessment(
            "Escalate",
            basis=[],
            unresolved=[
                "Credit hold — escalation required per M. Chen, 2026-10-25"],
            policy_ids=["policy-1", "correction-1"],
        )],
    )
    assessment = review["assessments"][0]
    assert review["completion"] == "completed"
    assert assessment["accepted_unresolved_requirements"] == []
    assert assessment["unclassified_requirements"] == []
    assert assessment["basis_supported_requirements"]
    assert "Credit hold" in " ".join(assessment["basis"])
    assert "Open requirements" not in render_review_result(review)


def test_compare_two_records_with_one_assessed_is_incomplete():
    requested = ["O-1010", "O-1001"]
    review = _build(
        _contract(),
        [_assessment()],
        requested=requested,
    )
    assert review["ok"] is False
    assert review["completion"] == "incomplete"
    assert _resolve(review) == (False, "failed", "turn_objective_not_met")


def test_requested_send_without_action_receipt_is_incomplete():
    objective = (
        ORDER_PROMPT.format(order="O-1010")
        + " Also send the escalation to the manager."
    )
    contract = _contract(objective)
    assert contract["required_actions"]
    review = _build(contract, [_assessment("Escalate")])
    assert review["completion"] == "incomplete"
    assert _resolve(review) == (False, "failed", "turn_objective_not_met")

    completed = _build(
        contract,
        [_assessment("Escalate")],
        action_receipts=[{
            "text": "send the escalation",
            "status": "succeeded",
        }],
    )
    assert completed["completion"] == "completed"
    assert _resolve(completed) == (True, "completed", None)


def test_unrelated_existing_obligation_is_preserved_and_ignored():
    review = _build(_contract(), [_assessment()])
    unrelated = [{"text": "previous unrelated obligation", "scope": "other"}]
    review["existing_obligations"] = unrelated
    assert review_completion(review) == "completed"
    assert review["existing_obligations"] == unrelated


def test_repeat_reuse_uses_the_same_completion_calculation():
    review = _build(
        _contract(),
        [_assessment(
            "Escalate",
            basis=["Known restriction applies."],
            unresolved=["currency missing"],
        )],
    )
    first = review_completion(review)
    repeated = dict(review)
    repeated["execution_id"] = "repeat-delivery-exec"
    second = review_completion(repeated)
    assert first == second == "partial"
    assert _resolve(review)[1] == second
