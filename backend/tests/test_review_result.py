from core.review_result import build_review_result, render_review_result


EXECUTION_ID = "exec-review-1"
EVIDENCE = [{
    "kind": "file",
    "file_name": "orders.xlsx",
    "resource_id": "sha1:abc",
    "content_hash": "abc",
    "ref": "Orders!R11",
    "addresses_requested": True,
}]
POLICY = [{
    "id": "lesson-1",
    "topic": "Order processing policy",
    "lesson": "Recommend routine orders for processing when records are complete.",
}]
ORDER_DECISIONS = ["Process", "Escalate"]


def _build(
    answer,
    *,
    requested=("O-1010",),
    allowed=ORDER_DECISIONS,
    evidence=EVIDENCE,
    required=None,
    policy=POLICY,
    execution_id=EXECUTION_ID,
    expected_execution_id=None,
):
    return build_review_result(
        execution_id=execution_id,
        expected_execution_id=expected_execution_id,
        requested_records=list(requested),
        answer=answer,
        allowed_decisions=list(allowed),
        evidence_refs=evidence,
        required_evidence=EVIDENCE if required is None else required,
        policy_refs=policy,
    )


def test_valid_process_review_is_certified():
    review = _build(
        "O-1010\n\n| Order ID | Status |\n|---|---|\n| O-1010 | Approved |\n\n"
        "Recommendation: Process.")
    assert review["ok"] is True
    assert review["requested_subjects"] == ["O-1010"]
    assert review["assessments"][0]["subject_id"] == "O-1010"
    assert review["assessments"][0]["decision"] == "process"
    assert review["assessments"][0]["evidence_refs"]
    assert review["assessments"][0]["policy_refs"]
    rendered = render_review_result(review)
    assert "O-1010: Decision: Process" in rendered
    assert "orders.xlsx" in rendered


def test_valid_escalate_review_is_certified():
    review = _build(
        "O-1010\n\nRecommendation: **Escalate** — manager exception required.")
    assert review["ok"] is True
    assert review["assessments"][0]["decision"] == "escalate"


def test_second_domain_uses_its_own_decision_schema():
    """The mechanism is not order-shaped: vendor risk uses other choices."""
    vendor_evidence = [{
        "kind": "file",
        "file_name": "vendors.xlsx",
        "resource_id": "sha1:vendor",
        "content_hash": "vendor",
        "ref": "Vendors!R7",
        "addresses_requested": True,
    }]
    review = _build(
        "V-200\n\nRecommendation: Request More Info — missing insurance "
        "certificate.",
        requested=("V-200",),
        allowed=["Approve", "Deny", "Request More Info"],
        evidence=vendor_evidence,
        required=vendor_evidence,
        policy=[{
            "id": "vendor-policy-1",
            "topic": "Vendor risk policy",
            "lesson": "Request more info when the insurance certificate is missing.",
        }],
    )
    assert review["ok"] is True
    assert review["assessments"][0]["decision"] == "request more info"
    assert review["assessments"][0]["subject_id"] == "V-200"


def test_decision_for_wrong_record_is_rejected():
    review = _build(
        "O-9999 only. Recommendation: Process.",
        requested=("O-1010",),
    )
    assert review["ok"] is False
    codes = {error["code"] for error in review["errors"]}
    assert "missing_decision" in codes
    assert "unrequested_subject" in codes


def test_missing_second_record_is_rejected():
    review = _build(
        "O-1010: Recommendation: Process.",
        requested=("O-1010", "O-1001"),
    )
    assert review["ok"] is False
    assert any(
        error["code"] == "missing_decision"
        and error.get("subject_id") == "O-1001"
        for error in review["errors"]
    )


def test_refusal_containing_decision_words_is_rejected():
    review = _build(
        "I cannot recommend processing this order: the currency is missing.")
    assert review["ok"] is False
    assert any(
        error["code"] == "missing_decision" for error in review["errors"])


def test_decision_without_source_evidence_is_rejected():
    review = _build(
        "O-1010\nRecommendation: Process.",
        evidence=[],
    )
    assert review["ok"] is False
    codes = {error["code"] for error in review["errors"]}
    assert "missing_evidence_refs" in codes or (
        "missing_required_evidence" in codes)


def test_decision_without_policy_refs_is_rejected():
    review = _build(
        "O-1010\nRecommendation: Process.",
        policy=[],
    )
    assert review["ok"] is False
    assert any(
        error["code"] == "missing_policy_refs" for error in review["errors"])


def test_review_from_another_execution_is_rejected():
    review = _build(
        "O-1010\nRecommendation: Process.",
        expected_execution_id="exec-other",
    )
    assert review["ok"] is False
    assert any(
        error["code"] == "execution_mismatch" for error in review["errors"])


def test_decision_outside_task_schema_is_rejected():
    review = _build(
        "V-200\nRecommendation: Escalate.",
        requested=("V-200",),
        allowed=["Approve", "Deny"],
    )
    assert review["ok"] is False
    assert any(
        error["code"] == "missing_decision" for error in review["errors"])


def test_decision_options_come_from_the_first_task_policy():
    from core.review_result import decision_options_from_lessons

    lessons = [
        {"topic": "Vendor risk policy",
         "decision_options": ["Approve", "Deny", "Request More Info"]},
        {"topic": "Order policy",
         "decision_options": ["Process", "Escalate"]},
    ]
    assert decision_options_from_lessons(lessons) == [
        "Approve", "Deny", "Request More Info"]
