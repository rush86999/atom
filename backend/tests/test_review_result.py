import json

import pytest

from core.review_result import (
    align_review_failure,
    build_evidence_index,
    build_policy_index,
    build_review_result,
    render_review_result,
    review_matches_delivered_text,
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
    "retrieval_execution_id": "exec-review-1",
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
        "retrieval_execution_id": "exec-review-1",
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
        "retrieval_execution_id": "exec-review-1",
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
            "retrieval_execution_id": "exec-review-1",
            "row_ref": "Orders!R11",
            "values": [],
        },
        {
            "evidence_id": "ev:O-1001:Orders!R2",
            "subject_id": "O-1001",
            "source_identity": dict(SOURCE),
            "retrieval_operation": "attempt-1",
            "retrieval_execution_id": "exec-review-1",
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


def test_captured_missing_policy_ids_response_stays_rejected():
    """Permanent regression for the captured post-restart assessment.

    The model parsed correctly, named the right subjects, evidence and
    decisions, but omitted policy_ids. Certification must remain rejected
    with the precise reason — the single available policy ID is NOT attached
    on the model's behalf (that would manufacture attribution).
    """
    captured_answer = (
        "Based on the provided policy, I will assess each open case in "
        "`case_boundaries.csv` using the \"Ask Amount\" column.\n\n"
        "```json\n"
        "{\n"
        "  \"assessments\": [\n"
        "    {\"subject_id\": \"CX-9101\", \"decision\": \"REJECT\", "
        "\"basis\": [\"below 5000\"], "
        "\"evidence_ids\": [\"ev:CX-9101:case_boundaries!R2\"]},\n"
        "    {\"subject_id\": \"CX-9102\", \"decision\": \"REVIEW\", "
        "\"basis\": [\"between 5000 and 9999\"], "
        "\"evidence_ids\": [\"ev:CX-9102:case_boundaries!R3\"]},\n"
        "    {\"subject_id\": \"CX-9103\", \"decision\": \"REVIEW\", "
        "\"basis\": [\"at or above 10000\"], "
        "\"evidence_ids\": [\"ev:CX-9103:case_boundaries!R4\"]}\n"
        "  ]\n"
        "}\n"
        "```"
    )
    source = {
        "file_name": "case_boundaries.csv",
        "resource_id": "4495bb9b9b46e28f7b7a69fcdf5373bb334b1c83",
        "content_hash": "4495bb9b9b46e28f7b7a69fcdf5373bb334b1c83",
    }
    evidence = [{
        "evidence_id": f"ev:{subject}:case_boundaries!R{row}",
        "subject_id": subject,
        "source_identity": dict(source),
        "retrieval_operation": (
            "select:4495bb9b9b46:3cd807fa-e03b-43cc-ac21-9df045629920"),
        "retrieval_execution_id":
            "3cd807fa-e03b-43cc-ac21-9df045629920",
        "row_ref": f"case_boundaries!R{row}",
        "values": [],
    } for subject, row in (
        ("CX-9101", 2), ("CX-9102", 3), ("CX-9103", 4))]
    policy = [{
        "policy_id": "08444fd977d44c06b226047b7f4b23ed",
        "topic": "case amount rule",
        "lesson": (
            "Use exactly these decision labels: APPROVE, REVIEW, REJECT. "
            "Ask Amount at or above 10000 is REVIEW. 5000 to 9999 is "
            "REVIEW. Below 5000 is REJECT."),
    }]
    review = build_review_result(
        execution_id="3cd807fa-e03b-43cc-ac21-9df045629920",
        expected_execution_id="3cd807fa-e03b-43cc-ac21-9df045629920",
        requested_records=["CX-9101", "CX-9102", "CX-9103"],
        answer=captured_answer,
        allowed_decisions=["APPROVE", "REVIEW", "REJECT"],
        evidence_index=evidence,
        policy_index=policy,
    )
    assert review["ok"] is False
    assert review["assessments"] == []
    assert review["completion"] == "incomplete"
    assert [item["subject_id"] for item in review["candidate_assessments"]] == [
        "CX-9101", "CX-9102", "CX-9103"]
    assert [item["decision"] for item in review["candidate_assessments"]] == [
        "REJECT", "REVIEW", "REVIEW"]
    assert [
        item["evidence_refs"][0]["row_ref"]
        for item in review["candidate_assessments"]
    ] == ["case_boundaries!R2", "case_boundaries!R3",
          "case_boundaries!R4"]
    assert all(
        item["policy_refs"] == []
        for item in review["candidate_assessments"]), (
        "the validator must never attach the only policy ID on the model's "
        "behalf")
    assert review["errors"] == [
        {"code": "missing_policy_ids", "subject_id": "CX-9101"},
        {"code": "missing_policy_ids", "subject_id": "CX-9102"},
        {"code": "missing_policy_ids", "subject_id": "CX-9103"},
    ]


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


def test_policy_index_parses_the_teachers_label_list():
    """Canvas /teach surfaces have no separate decision-option control.
    The lesson itself declares the labels; the policy index must honor it."""
    from core.review_result import decision_options_from_text

    lesson = (
        "Use exactly these decision labels: FUND, HOLD, DECLINE. "
        "Requested amount at or above 10000 is HOLD."
    )
    assert decision_options_from_text(lesson) == ["FUND", "HOLD", "DECLINE"]
    index = build_policy_index(
        [{"id": "threshold-rule", "topic": "grant thresholds",
          "lesson": lesson}],
        ["FUND", "HOLD", "DECLINE"],
    )
    assert [entry["policy_id"] for entry in index] == ["threshold-rule"]


def test_decision_options_are_not_inferred_from_ordinary_prose():
    from core.review_result import decision_options_from_text

    assert decision_options_from_text(
        "Use good judgment and explain the reasoning.") == []
    assert decision_options_from_text(
        "The decision labels are not specified in this policy.") == []


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


def test_uncertified_required_review_forces_failed_envelope():
    response = {
        "success": True,
        "outcome": "completed",
        "_recorded_outcome": {"state": "completed"},
    }
    outcome = {
        "delivery": {"review_required": True},
        "objective_met": False,
    }
    assert align_review_failure(response, outcome) is True
    assert response["success"] is False
    assert response["outcome"] == "failed"
    assert response["_recorded_outcome"]["state"] == "failed"


def test_certified_or_absent_review_does_not_force_failure():
    response = {"success": True, "outcome": "completed"}
    assert align_review_failure(
        response, {"delivery": {"review_required": True},
                   "objective_met": True}) is False
    assert response["success"] is True
    assert align_review_failure(
        response, {"delivery": {"review_required": False},
                   "objective_met": False}) is False


def test_review_delivery_must_carry_the_rendered_block():
    summary = "VALIDATED REVIEW (request-bound):\n- O-1010: Decision: Process"
    assert review_matches_delivered_text(
        summary, "review text\n\n" + summary) is True
    assert review_matches_delivered_text(
        summary, "The lookup did not run this turn.") is False


def test_evidence_index_preserves_retrieval_execution_id():
    structured = {
        "requested_items": ["O-1010"],
        "attempt_id": "attempt-1",
        "source_execution_id": "read-execution-7",
        "source_identity": dict(SOURCE),
        "targets": [{
            "item": "O-1010",
            "status": "found",
            "identity": {"candidates": [{
                "ref": "Orders!R11",
                "values": [],
            }]},
        }],
    }
    index = build_evidence_index(structured)
    assert index[0]["retrieval_execution_id"] == "read-execution-7"


def test_missing_retrieval_execution_id_fails_closed():
    evidence = [dict(EVIDENCE_INDEX[0])]
    evidence[0].pop("retrieval_execution_id", None)
    review = _build(
        _block([{
            "subject_id": "O-1010",
            "decision": "Process",
            "evidence_ids": ["ev:O-1010:Orders!R11"],
            "policy_ids": ["lesson-1"],
            "unresolved_requirements": [],
        }]),
        evidence=evidence,
    )
    assert review["ok"] is False
    assert any(
        error["code"] == "missing_retrieval_execution_id"
        for error in review["errors"])


def test_resumed_read_provenance_is_recorded_not_rewritten():
    evidence = [dict(EVIDENCE_INDEX[0])]
    evidence[0]["retrieval_execution_id"] = "read-execution-old"
    review = _build(
        _block([{
            "subject_id": "O-1010",
            "decision": "Escalate",
            "evidence_ids": ["ev:O-1010:Orders!R11"],
            "policy_ids": ["lesson-1"],
            "unresolved_requirements": ["credit hold"],
        }]),
        evidence=evidence,
    )
    assert review["ok"] is True
    assert review["source_execution_ids"] == ["read-execution-old"]
    assert review["assessments"][0]["resumed_read"] is True
    assert review["assessments"][0]["evidence_refs"][0][
        "retrieval_execution_id"] == "read-execution-old"


def test_review_instruction_carries_policy_text_and_row_values():
    """The generation prompt must contain the applicable instruction text.

    The captured 4800 -> FUND failure had policy IDs/topics only; the rule
    text was absent from the review prompt. This test keeps the instruction
    self-contained without encoding any business vocabulary in code.
    """
    from core.review_result import review_output_instruction

    instruction = review_output_instruction(
        {"subjects": ["A-1", "A-2"],
         "allowed_decisions": ["PASS", "REVIEW"],
         "required_actions": []},
        [{"evidence_id": "ev:A-1:R2", "subject_id": "A-1",
          "row_ref": "S!R2"}],
        [{"policy_id": "p-current", "topic": "current rule",
          "lesson": "A measured value below 500 must be REVIEW."},
         {"policy_id": "p-other", "topic": "unrelated rule",
          "lesson": "A measured value above 900 must be PASS."}],
    )
    assert "p-current" in instruction
    assert "A measured value below 500 must be REVIEW." in instruction
    assert "p-other" in instruction
    assert "A measured value above 900 must be PASS." in instruction
    assert "row values" in instruction.lower()
    assert "non-empty `policy_ids`" in instruction.lower()
    assert "independent" in instruction.lower()
    assert "newest first" not in instruction.lower()
    assert "superseded" not in instruction.lower()
    assert "only the entries listed under policy ids" in instruction.lower()
    assert "ev:A-1:R2" in instruction
    assert "PASS, REVIEW" in instruction


def test_newer_unrelated_lesson_does_not_invalidate_older_applicable_rule():
    """Ordering is not supersession.

    A correction is authoritative through an in-place PATCH of the same
    policy ID. Retrieval order alone must never make a newer unrelated entry
    override an older applicable rule, and both remain usable policy refs.
    """
    from core.review_result import review_output_instruction

    older = {
        "policy_id": "p-old-applicable",
        "topic": "amount rule",
        "lesson": "Below 500 is REJECT.",
    }
    newer_unrelated = {
        "policy_id": "p-new-unrelated",
        "topic": "freight instructions",
        "lesson": "Email Mill Creek for freight costs.",
    }
    instruction = review_output_instruction(
        {"subjects": ["A-1"], "allowed_decisions": ["APPROVE", "REJECT"]},
        [{"evidence_id": "ev:A-1:R2", "subject_id": "A-1",
          "row_ref": "S!R2"}],
        [older, newer_unrelated],
    )
    assert "p-old-applicable" in instruction
    assert "Below 500 is REJECT." in instruction
    assert "p-new-unrelated" in instruction
    assert "newer unrelated lesson never invalidates" in instruction
    review = _build(
        _block([{
            "subject_id": "O-1010",
            "decision": "Process",
            "evidence_ids": ["ev:O-1010:Orders!R11"],
            "policy_ids": ["p-old-applicable"],
        }]),
        policy=[older, newer_unrelated],
    )
    # The older applicable policy still certifies; the newer entry is not a
    # global override. (The fixture subject's schema is separate from the
    # illustrative policy text; only reference resolution is exercised here.)
    assert review["ok"] is True
    assert review["assessments"][0]["policy_refs"][0]["policy_id"] == (
        "p-old-applicable")


def test_unrelated_sibling_decision_vocabulary_cannot_enter_policy_index():
    """Workspace knowledge is shared; it does not become this task's policy.

    The captured review memory carried another agent's FUND/HOLD/DECLINE
    rule, a price-list lesson and freight instructions. Only lessons whose
    decision vocabulary exactly matches this task may supply policy IDs.
    """
    from core.review_result import (
        build_policy_index,
        review_output_instruction,
    )

    own = {
        "id": "own-case-rule",
        "topic": "case amount rule",
        "decision_options": ["APPROVE", "REVIEW", "REJECT"],
        "lesson": "Below 5000 is REJECT.",
    }
    sibling_decision = {
        "id": "sibling-fund-rule",
        "topic": "threshold rule (corrected)",
        "decision_options": ["FUND", "HOLD", "DECLINE"],
        "lesson": "Below 5000 is DECLINE.",
        "_source_agent_id": "other-agent",
    }
    sibling_general = {
        "id": "sibling-freight",
        "topic": "freight costs",
        "lesson": "Email Mill Creek for freight costs.",
        "_source_agent_id": "other-agent",
    }
    index = build_policy_index(
        [sibling_decision, sibling_general, own],
        ["APPROVE", "REVIEW", "REJECT"],
    )
    assert [entry["policy_id"] for entry in index] == ["own-case-rule"]
    instruction = review_output_instruction(
        {"subjects": ["CX-1"], "allowed_decisions": ["APPROVE", "REJECT"]},
        [{"evidence_id": "ev:CX-1:R2", "subject_id": "CX-1",
          "row_ref": "S!R2"}],
        index,
    )
    assert "own-case-rule" in instruction
    assert "sibling-fund-rule" not in instruction
    assert "sibling-freight" not in instruction
    assert "must not change the allowed decisions" in instruction


def test_review_payload_schema_requires_policy_and_unresolved_fields():
    """The transport schema requires every field the validator relies on."""
    from core.review_result import review_output_schema

    schema = review_output_schema()
    assessment = schema["$defs"]["ReviewAssessmentModel"]
    assert set(assessment["required"]) >= {
        "subject_id", "decision", "evidence_ids", "policy_ids", "basis",
        "unresolved_requirements",
    }
    assert assessment["properties"]["policy_ids"]["minItems"] == 1
    assert assessment["properties"]["evidence_ids"]["minItems"] == 1


async def test_structured_review_call_uses_same_contract_and_schema():
    """Mocked transport: the outgoing review call carries the schema and the
    exact evidence/policy message; a schema-valid payload still goes through
    the unchanged validator."""
    from core.review_result import (
        ReviewPayloadModel,
        generate_structured_review,
    )

    captured = {}

    class _StructuredLLM:
        async def generate_structured_response(self, **kwargs):
            captured.update(kwargs)
            return ReviewPayloadModel(
                explanation="O-1010 is complete.",
                assessments=[{
                    "subject_id": "O-1010",
                    "decision": "Process",
                    "evidence_ids": ["ev:O-1010:Orders!R11"],
                    "policy_ids": ["lesson-1"],
                    "basis": ["record is complete"],
                    "unresolved_requirements": [],
                }],
            )

    messages = [
        {"role": "system", "content": (
            "REVIEW OUTPUT CONTRACT. Every assessment MUST include a "
            "NON-EMPTY `policy_ids` array using IDs from the supplied index.\n"
            "Policy IDs:\n- lesson-1 | Order policy\n"
            "Evidence IDs:\n- ev:O-1010:Orders!R11 | subject=O-1010")},
        {"role": "user", "content": "Assess O-1010."},
    ]
    answer = await generate_structured_review(
        _StructuredLLM(), messages=messages, model="auto",
        llm_scope={"workspace_id": "ws-1"}, max_tokens=800)
    assert captured["response_model"] is ReviewPayloadModel
    assert captured["allow_moa"] is False and captured["cascade"] is False
    assert captured["workspace_id"] == "ws-1"
    assert captured["max_tokens"] == 800
    assert captured["messages"] == messages
    assert captured["output_mode"] == "json"
    assert captured["task_type"] == "review"
    assert captured["claim_wait_seconds"] == 45.0
    assert "policy_ids" in captured["system_instruction"]
    assert "lesson-1" in captured["system_instruction"]
    assert "```review_result" in (answer or "")
    review = build_review_result(
        execution_id=EXECUTION_ID,
        requested_records=["O-1010"],
        answer=answer,
        allowed_decisions=ORDER_DECISIONS,
        evidence_index=[dict(EVIDENCE_INDEX[0])],
        policy_index=[dict(POLICY_INDEX[0])],
    )
    assert review["ok"] is True


@pytest.mark.asyncio
async def test_structured_review_uses_scoped_pin_and_keeps_message_order(
        monkeypatch):
    from core.review_result import (
        LAST_STRUCTURED_REVIEW,
        ReviewPayloadModel,
        generate_structured_review,
    )

    captured = {}

    class _StructuredLLM:
        async def generate_structured_response(self, **kwargs):
            captured.update(kwargs)
            return ReviewPayloadModel(
                explanation="ok",
                assessments=[{
                    "subject_id": "O-1010",
                    "decision": "Process",
                    "evidence_ids": ["ev:O-1010:Orders!R11"],
                    "policy_ids": ["lesson-1"],
                    "basis": ["record is complete"],
                    "unresolved_requirements": [],
                }],
            )

    monkeypatch.setattr(
        "core.llm.pinned_planning.build_provider_model_pin",
        lambda *args, **kwargs: {
            "provider_model": ("deepseek", "deepseek-v4-pro")})
    messages = [
        {"role": "system", "content": "contract"},
        {"role": "system", "content": "evidence"},
        {"role": "user", "content": "assess"},
    ]
    answer = await generate_structured_review(
        _StructuredLLM(), messages=messages, model="deepseek-v4-pro",
        llm_scope={"workspace_id": "ws-1"})
    assert answer
    assert captured["provider_model"] == ("deepseek", "deepseek-v4-pro")
    assert captured["messages"] == messages
    assert LAST_STRUCTURED_REVIEW["ok"] is True
    assert LAST_STRUCTURED_REVIEW["failure_kind"] is None


@pytest.mark.asyncio
async def test_structured_review_empty_payload_is_typed_failure():
    from core.review_result import (
        LAST_STRUCTURED_REVIEW,
        generate_structured_review,
    )

    class _EmptyLLM:
        async def generate_structured_response(self, **kwargs):
            return None

    answer = await generate_structured_review(
        _EmptyLLM(), messages=[
            {"role": "system", "content": "contract"},
            {"role": "user", "content": "assess"},
        ], model="deepseek-v4-pro")
    assert answer is None
    assert LAST_STRUCTURED_REVIEW["failure_kind"] == "empty_payload"
    assert LAST_STRUCTURED_REVIEW["failure_stage"] == "dispatch"


@pytest.mark.asyncio
async def test_structured_review_provider_exception_is_typed_failure():
    from core.review_result import (
        LAST_STRUCTURED_REVIEW,
        generate_structured_review,
    )

    class _BrokenLLM:
        async def generate_structured_response(self, **kwargs):
            raise RuntimeError("transport down")

    answer = await generate_structured_review(
        _BrokenLLM(), messages=[
            {"role": "system", "content": "contract"},
            {"role": "user", "content": "assess"},
        ], model="deepseek-v4-pro")
    assert answer is None
    assert LAST_STRUCTURED_REVIEW["failure_kind"] == "provider_exception"
    assert "RuntimeError" in LAST_STRUCTURED_REVIEW["failure_detail"]


def test_missing_block_only_distinguishes_format_from_refusal():
    """Only a reply with NO parseable block may be retried; a refused block
    must never be re-rolled (retrying a refused judgment shops for
    acceptance)."""
    from core.review_result import missing_block_only

    no_block = [
        {"code": "missing_structured_review"},
        {"code": "missing_decision", "subject_id": "A-1"},
        {"code": "missing_decision", "subject_id": "A-2"},
    ]
    assert missing_block_only(no_block) is True
    # A produced-but-refused block: judgment/validation rejections.
    assert missing_block_only([
        {"code": "unrequested_subject", "subject_id": "X"},
    ]) is False
    assert missing_block_only([
        {"code": "missing_decision", "subject_id": "A-1"},
        {"code": "invalid_decision", "subject_id": "A-2",
         "decision": "MAYBE"},
    ]) is False
    assert missing_block_only([
        {"code": "unknown_evidence_id", "subject_id": "A-1",
         "evidence_id": "ev:other"},
    ]) is False
    assert missing_block_only([
        {"code": "unknown_policy_id", "subject_id": "A-1",
         "policy_id": "p-none"},
    ]) is False
    # Plumbing failures are not format collapses either.
    assert missing_block_only([
        {"code": "missing_structured_review"},
        {"code": "execution_mismatch"},
    ]) is False
    assert missing_block_only([]) is False


async def test_block_recovery_retry_uses_same_contract_and_ids():
    """The one contract-only retry carries the SAME evidence/policy IDs and
    the deterministic rows, and returns the model's answer unchanged for the
    unchanged validator."""
    from types import SimpleNamespace

    from integrations.chat_orchestrator import ChatOrchestrator

    captured = {}

    class _StubLLM:
        async def generate_completion(self, **kwargs):
            captured.update(kwargs)
            return {"content": (
                "Assessed.\n```review_result\n"
                "{\"assessments\": [{\"subject_id\": \"O-1010\", "
                "\"decision\": \"Process\", \"basis\": [\"complete\"], "
                "\"evidence_ids\": [\"ev:O-1010:Orders!R11\"], "
                "\"policy_ids\": [\"lesson-1\"], "
                "\"unresolved_requirements\": []}]}\n```")}

    stub = SimpleNamespace(llm_service=_StubLLM())
    evidence = [dict(EVIDENCE_INDEX[0])]
    policy = [dict(POLICY_INDEX[0])]
    answer = await ChatOrchestrator._retry_review_block(
        stub,
        objective_text="assess the orders",
        rendered_rows="| Ref | Amount |\n| --- | ---: |\n| O-1010 | 120 |",
        subjects=["O-1010"],
        allowed_decisions=ORDER_DECISIONS,
        evidence_index=evidence,
        policy_index=policy,
        model="auto",
        llm_scope={"workspace_id": "ws-1"},
        extra_kwargs={},
    )
    assert "```review_result" in (answer or "")
    messages = captured.get("messages") or []
    assert len(messages) == 2
    system_text = messages[0]["content"]
    assert "ev:O-1010:Orders!R11" in system_text
    assert "lesson-1" in system_text
    user_text = messages[1]["content"]
    assert "assess the orders" in user_text
    assert "O-1010" in user_text
    assert captured.get("model") == "auto"
    # The recovered answer must pass the unchanged validator.
    review = build_review_result(
        execution_id=EXECUTION_ID,
        requested_records=["O-1010"],
        answer=answer,
        allowed_decisions=ORDER_DECISIONS,
        evidence_index=evidence,
        policy_index=policy,
    )
    assert review["ok"] is True


def test_review_generation_model_prefers_the_declared_review_model(monkeypatch):
    from integrations.chat_orchestrator import _review_generation_model

    monkeypatch.setenv("ATOM_REVIEW_MODEL", "deepseek-v4-pro")
    assert _review_generation_model("auto") == "deepseek-v4-pro"
    assert _review_generation_model("") == "deepseek-v4-pro"
    assert _review_generation_model("explicit-model") == "explicit-model"
    monkeypatch.delenv("ATOM_REVIEW_MODEL")
    assert _review_generation_model("auto") == "auto"


@pytest.mark.asyncio
async def test_block_recovery_pins_the_last_used_model():
    """A format-collapse retry must not silently switch provider models."""
    from types import SimpleNamespace

    from integrations.chat_orchestrator import ChatOrchestrator

    captured = {}

    class _StubLLM:
        handler = SimpleNamespace(_last_used_model="deepseek-v4-pro")

        async def generate_completion(self, **kwargs):
            captured.update(kwargs)
            return {"content": "assessed"}

    answer = await ChatOrchestrator._retry_review_block(
        SimpleNamespace(llm_service=_StubLLM()),
        objective_text="assess",
        rendered_rows="rows",
        subjects=["O-1010"],
        allowed_decisions=ORDER_DECISIONS,
        evidence_index=[dict(EVIDENCE_INDEX[0])],
        policy_index=[dict(POLICY_INDEX[0])],
        model="auto",
        llm_scope={"workspace_id": "ws-1"},
        extra_kwargs={},
    )
    assert answer == "assessed"
    assert captured.get("model") == "deepseek-v4-pro"


@pytest.mark.asyncio
async def test_block_recovery_provider_failure_returns_none():
    """A provider failure in the retry is a skip, not an exception: the
    caller falls through to the evidence-only failure."""
    from types import SimpleNamespace

    from integrations.chat_orchestrator import ChatOrchestrator

    class _FailingLLM:
        async def generate_completion(self, **kwargs):
            raise RuntimeError("provider down")

    stub = SimpleNamespace(llm_service=_FailingLLM())
    answer = await ChatOrchestrator._retry_review_block(
        stub,
        objective_text="assess",
        rendered_rows="rows",
        subjects=["O-1010"],
        allowed_decisions=ORDER_DECISIONS,
        evidence_index=[dict(EVIDENCE_INDEX[0])],
        policy_index=[dict(POLICY_INDEX[0])],
    )
    assert answer is None


async def test_block_recovery_error_shaped_content_is_not_answer():
    """The handler's failure text surfaced as content is a failed
    generation, not a model reply — it must not reach the validator."""
    from types import SimpleNamespace

    from integrations.chat_orchestrator import ChatOrchestrator

    class _ErrorTextLLM:
        async def generate_completion(self, **kwargs):
            return {"content": (
                "I couldn't generate a response — every configured provider "
                "failed. Last error: no provider attempted.")}

    stub = SimpleNamespace(llm_service=_ErrorTextLLM())
    answer = await ChatOrchestrator._retry_review_block(
        stub,
        objective_text="assess",
        rendered_rows="rows",
        subjects=["O-1010"],
        allowed_decisions=ORDER_DECISIONS,
        evidence_index=[dict(EVIDENCE_INDEX[0])],
        policy_index=[dict(POLICY_INDEX[0])],
    )
    assert answer is None


def test_json_fence_is_accepted_for_review_schema_only():
    from core.review_result import parse_review_payload

    good = ('```json\n{"assessments":[{"subject_id":"A","decision":"PASS"}]}\n```')
    assert parse_review_payload(good)["assessments"][0]["subject_id"] == "A"
    unrelated = '```json\n{"other":1}\n```'
    assert parse_review_payload(unrelated) is None
    # Two schema-shaped blocks are ambiguous, not silently chosen.
    two = good + "\n" + good
    assert parse_review_payload(two) is None
