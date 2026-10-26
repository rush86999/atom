import json

from core.review_result import (
    build_evidence_index,
    build_policy_index,
    build_review_result,
    render_review_result,
    review_output_instruction,
    strip_review_block,
)


EXECUTION_ID = "exec-review-1"
SOURCE = {
    "file_name": "orders.xlsx",
    "resource_id": "sha1:abc",
    "content_hash": "abc",
}
EVIDENCE_INDEX = [{
    "evidence_id": "ev:O-1010:Orders!R11",
    "subject_id": "O-1010",
    "source_identity": dict(SOURCE),
    "retrieval_operation": "attempt-1",
    "row_ref": "Orders!R11",
    "values": [],
}]
POLICY_INDEX = [{
    "policy_id": "lesson-1",
    "topic": "Order processing policy",
    "lesson": "Recommend routine orders for processing when records are complete.",
}]
ORDER_DECISIONS = ["Process", "Escalate"]


def _block(assessments):
    return (
        "The record was checked against the taught policy.\n\n"
        "```review_result\n"
        + json.dumps({"assessments": assessments})
        + "\n```"
    )


def _build(answer, *, requested=("O-1010",), allowed=ORDER_DECISIONS,
           evidence=None, policy=None, execution_id=EXECUTION_ID,
           expected_execution_id=None):
    return build_review_result(
        execution_id=execution_id,
        expected_execution_id=expected_execution_id,
        requested_records=list(requested),
        answer=answer,
        allowed_decisions=list(allowed),
        evidence_index=EVIDENCE_INDEX if evidence is None else evidence,
        policy_index=POLICY_INDEX if policy is None else policy,
    )


def test_valid_order_process_review_certifies_from_structured_block():
    review = _build(_block([{
        "subject_id": "O-1010",
        "decision": "Process",
        "evidence_ids": ["ev:O-1010:Orders!R11"],
        "policy_ids": ["lesson-1"],
        "unresolved_requirements": [],
    }]))
    assert review["ok"] is True
    assert review["assessments"][0]["subject_id"] == "O-1010"
    assert review["assessments"][0]["decision"] == "Process"
    assert review["assessments"][0]["evidence_refs"][0]["row_ref"] == (
        "Orders!R11")
    rendered = render_review_result(review)
    assert "O-1010: Decision: Process" in rendered
    assert "orders.xlsx" in rendered


def test_valid_order_escalate_review_certifies():
    review = _build(_block([{
        "subject_id": "O-1010",
        "decision": "Escalate",
        "evidence_ids": ["ev:O-1010:Orders!R11"],
        "policy_ids": ["lesson-1"],
        "unresolved_requirements": ["currency missing"],
    }]))
    assert review["ok"] is True
    assert review["assessments"][0]["unresolved_requirements"] == [
        "currency missing"]


def test_vendor_domain_uses_its_own_structured_schema():
    source = {
        "file_name": "vendors.xlsx",
        "resource_id": "sha1:vendor",
        "content_hash": "vendor",
    }
    evidence = [{
        "evidence_id": "ev:V-200:Vendors!R7",
        "subject_id": "V-200",
        "source_identity": source,
        "retrieval_operation": "attempt-vendor",
        "row_ref": "Vendors!R7",
        "values": [],
    }]
    policy = [{
        "policy_id": "vendor-policy-1",
        "topic": "Vendor risk policy",
        "lesson": "Request more info when the insurance certificate is missing.",
    }]
    review = _build(
        _block([{
            "subject_id": "V-200",
            "decision": "Request More Info",
            "evidence_ids": ["ev:V-200:Vendors!R7"],
            "policy_ids": ["vendor-policy-1"],
            "unresolved_requirements": ["insurance certificate"],
        }]),
        requested=("V-200",),
        allowed=["Approve", "Deny", "Request More Info"],
        evidence=evidence,
        policy=policy,
    )
    assert review["ok"] is True
    assert review["assessments"][0]["decision"] == "Request More Info"


def test_quoted_example_decision_text_cannot_certify():
    review = _build(
        'O-1010: The phrase "Decision: Process" is an example, not my decision.')
    assert review["ok"] is False
    assert any(
        error["code"] == "missing_structured_review"
        for error in review["errors"])


def test_wrong_subject_evidence_cannot_certify():
    evidence = [{
        "evidence_id": "ev:O-1001:Orders!R2",
        "subject_id": "O-1001",
        "source_identity": dict(SOURCE),
        "retrieval_operation": "attempt-1",
        "row_ref": "Orders!R2",
        "values": [],
    }]
    review = _build(
        _block([{
            "subject_id": "O-1010",
            "decision": "Process",
            "evidence_ids": ["ev:O-1001:Orders!R2"],
            "policy_ids": ["lesson-1"],
            "unresolved_requirements": [],
        }]),
        evidence=evidence,
    )
    assert review["ok"] is False
    assert any(
        error["code"] == "evidence_subject_mismatch"
        for error in review["errors"])


def test_swapped_evidence_between_two_subjects_fails():
    evidence = [
        {
            "evidence_id": "ev:O-1010:Orders!R11",
            "subject_id": "O-1010",
            "source_identity": dict(SOURCE),
            "retrieval_operation": "attempt-1",
            "row_ref": "Orders!R11",
            "values": [],
        },
        {
            "evidence_id": "ev:O-1001:Orders!R2",
            "subject_id": "O-1001",
            "source_identity": dict(SOURCE),
            "retrieval_operation": "attempt-1",
            "row_ref": "Orders!R2",
            "values": [],
        },
    ]
    review = _build(
        _block([
            {
                "subject_id": "O-1010",
                "decision": "Process",
                "evidence_ids": ["ev:O-1001:Orders!R2"],
                "policy_ids": ["lesson-1"],
                "unresolved_requirements": [],
            },
            {
                "subject_id": "O-1001",
                "decision": "Process",
                "evidence_ids": ["ev:O-1010:Orders!R11"],
                "policy_ids": ["lesson-1"],
                "unresolved_requirements": [],
            },
        ]),
        requested=("O-1010", "O-1001"),
        evidence=evidence,
    )
    assert review["ok"] is False
    assert sum(
        error["code"] == "evidence_subject_mismatch"
        for error in review["errors"]) == 2


def test_missing_or_unknown_evidence_and_policy_ids_fail():
    review = _build(_block([{
        "subject_id": "O-1010",
        "decision": "Process",
        "evidence_ids": ["ev:missing"],
        "policy_ids": ["missing-policy"],
        "unresolved_requirements": [],
    }]))
    codes = {error["code"] for error in review["errors"]}
    assert "unknown_evidence_id" in codes
    assert "unknown_policy_id" in codes
    assert review["ok"] is False


def test_missing_second_subject_fails():
    review = _build(
        _block([{
            "subject_id": "O-1010",
            "decision": "Process",
            "evidence_ids": ["ev:O-1010:Orders!R11"],
            "policy_ids": ["lesson-1"],
            "unresolved_requirements": [],
        }]),
        requested=("O-1010", "O-1001"),
    )
    assert review["ok"] is False
    assert any(
        error["code"] == "missing_decision"
        and error.get("subject_id") == "O-1001"
        for error in review["errors"])


def test_out_of_schema_decision_fails():
    review = _build(
        _block([{
            "subject_id": "O-1010",
            "decision": "Approve",
            "evidence_ids": ["ev:O-1010:Orders!R11"],
            "policy_ids": ["lesson-1"],
            "unresolved_requirements": [],
        }]),
        allowed=["Process", "Escalate"],
    )
    assert review["ok"] is False
    assert any(
        error["code"] == "invalid_decision" for error in review["errors"])


def test_execution_mismatch_fails():
    review = _build(
        _block([{
            "subject_id": "O-1010",
            "decision": "Process",
            "evidence_ids": ["ev:O-1010:Orders!R11"],
            "policy_ids": ["lesson-1"],
            "unresolved_requirements": [],
        }]),
        expected_execution_id="exec-other",
    )
    assert review["ok"] is False
    assert any(
        error["code"] == "execution_mismatch" for error in review["errors"])


def test_structured_evidence_index_preserves_subject_and_retrieval_identity():
    structured = {
        "requested_items": ["O-1010"],
        "attempt_id": "attempt-1",
        "evidence_revision": "revision-1",
        "source_identity": dict(SOURCE),
        "targets": [{
            "item": "O-1010",
            "status": "found",
            "identity": {"candidates": [{
                "ref": "Orders!R11",
                "values": [{"col": "A11", "display": "O-1010"}],
            }]},
        }],
    }
    index = build_evidence_index(structured)
    assert index[0]["subject_id"] == "O-1010"
    assert index[0]["row_ref"] == "Orders!R11"
    assert index[0]["source_identity"] == SOURCE
    assert index[0]["retrieval_operation"] == "attempt-1"


def test_policy_index_only_includes_schema_lessons():
    lessons = [
        {"id": "order-policy", "topic": "Orders",
         "decision_options": ["Process", "Escalate"]},
        {"id": "unrelated", "topic": "Style", "lesson": "Be concise."},
        {"id": "other-schema", "decision_options": ["Approve", "Deny"]},
    ]
    index = build_policy_index(lessons, ["Process", "Escalate"])
    assert [entry["policy_id"] for entry in index] == ["order-policy"]


def test_instruction_and_block_stripping():
    instruction = review_output_instruction(
        {"subjects": ["O-1010"],
         "allowed_decisions": ["Process", "Escalate"]},
        EVIDENCE_INDEX,
        POLICY_INDEX,
    )
    assert "review_result" in instruction
    assert "ev:O-1010:Orders!R11" in instruction
    assert "lesson-1" in instruction
    answer = _block([{
        "subject_id": "O-1010",
        "decision": "Process",
        "evidence_ids": ["ev:O-1010:Orders!R11"],
        "policy_ids": ["lesson-1"],
        "unresolved_requirements": [],
    }])
    assert "review_result" not in strip_review_block(answer)
