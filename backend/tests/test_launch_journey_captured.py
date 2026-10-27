"""Captured launch journey — no model calls.

The three third-attempt product blockers, replayed from the captured smoke
state as ONE user journey:

1. setup/ordinary read: a workbook answer with a complete receipt;
2. missing data: a delivered partial calculation must be terminal (gaps kept)
   and the harness must not send a confirmation for it;
3. confirmation: an accepted pending task resumes from its stored objective
   and resolved file without general interpretation;
4. review recovery: the original review contract survives confirmation, a
   raw deterministic read may never stand in for a missing review, and
   narration that returns a valid structured review completes it.

The values are the captured attempt-three values, not invented product names.
"""

from core.chat_tool_planner import review_requested
from core.pending_file_task import (
    build_pending_task,
    settle_retrieval_task,
)
from core.review_result import deterministic_read_fallback_allowed
from core.source_requirements import derive_required_research_sources
from core.turn_decision import pending_task_continuation_ready

ADJUSTMENTS_ASK = (
    "Now look at the Adjustments sheet in "
    "spreadsheet_smoke_ae0c2fda3-1793058137.xlsx. Select the approved rows "
    "and calculate the total. If any approved row is missing quantity or "
    "price, name the gap and do not give me a grand total."
)
ADJUSTMENTS_GAP = {
    "item": "0055",
    "sheet": "Adjustments",
    "cell": "C5",
    "field": "Qty",
    "reason": "missing quantity",
}
ORDER_REVIEW_ASK = (
    "Using the uploaded orders_smoke_ae0c2fda3-1793058137.xlsx, review "
    "order O-1001 against the order processing policy. Cite Order ID, "
    "Status, Qty, Unit Price, Currency, Approval 1, Approval 2, Manager "
    "Exception, and Notes from the row. State process or escalate and "
    "explain the policy basis. Do not send, approve, or modify anything."
)
# The smoke agent's own lessons (captured agent 95684c26...). Neither asks
# for correspondence.
OWN_LESSONS = [
    {
        "id": "7de1a97a66544b27b4919c158191afd0",
        "topic": "Order processing policy",
        "scope": "global",
        "lesson": (
            "Order processing policy: Recommend routine orders for processing "
            "when records are complete. Escalate conflicting approvals, "
            "uncertain currency or missing quantities."
        ),
    },
    {
        "id": "98e144dc3f3640e9abbd56810faf8525",
        "topic": "Order policy correction — O-1010 credit hold",
        "scope": "global",
        "lesson": (
            "Correction to the order policy: O-1010 is on credit hold. "
            "Manager M. Chen explicitly directed on 2026-10-25 that O-1010 "
            "must be escalated for review despite its complete record."
        ),
    },
]
# A sibling lesson that used to force Outlook for every review turn.
SIBLING_EMAIL_LESSON = {
    "id": "348aa9439ad246cfa13caecd57a34993",
    "topic": "general",
    "scope": "global",
    "_source_agent_id": "9837ec71-4f1b-41db-b014-119862362d44",
    "lesson": (
        "When a price is NOT FOUND in the price list workbook file: FIRST "
        "check email attachments for the calculation."
    ),
}


def test_captured_launch_journey():
    # 1. Setup/ordinary read completed with a verified receipt.
    ordinary = build_pending_task(
        "spreadsheet_smoke_ae0c2fda3-1793058137.xlsx",
        "Select the approved PO Register rows and total them by currency.",
    )
    ordinary = settle_retrieval_task(
        ordinary,
        {"file_name": "spreadsheet_smoke_ae0c2fda3-1793058137.xlsx",
         "content_hash": "captured-po-hash"},
        retrieval_finished=True,
        answer_delivered=True,
        calculation_complete=True,
    )
    assert ordinary["status"] == "delivered"
    assert ordinary["calculation_complete"] is True

    # 2. Missing data: the partial answer was delivered. The SOURCE LOOKUP is
    # finished; only the CALCULATION is incomplete, and the gap stays visible.
    adjustments = build_pending_task(
        "spreadsheet_smoke_ae0c2fda3-1793058137.xlsx", ADJUSTMENTS_ASK)
    adjustments = settle_retrieval_task(
        adjustments,
        {"file_name": "spreadsheet_smoke_ae0c2fda3-1793058137.xlsx",
         "content_hash": "captured-adjustments-hash"},
        retrieval_finished=True,
        answer_delivered=True,
        calculation_complete=False,
        open_requirements=[ADJUSTMENTS_GAP],
    )
    assert adjustments["status"] == "delivered"
    assert adjustments["calculation_complete"] is False
    assert adjustments["open_requirements"] == [ADJUSTMENTS_GAP]
    # A delivered answer is terminal: no stale pending lookup remains for the
    # smoke harness to confirm.
    assert adjustments["status"] != "pending"

    # 3. Confirmation: an unanswered accepted task reuses its stored objective
    # and resolved file instead of paying general interpretation.
    pending = build_pending_task(
        "orders_smoke_ae0c2fda3-1793058137.xlsx", ORDER_REVIEW_ASK)
    pending["resolved_file"] = {
        "file_name": "orders_smoke_ae0c2fda3-1793058137.xlsx"}
    ready = pending_task_continuation_ready("go ahead", pending)
    assert ready is not None
    assert ready["reference"]["resolved_file"] == (
        "orders_smoke_ae0c2fda3-1793058137.xlsx")

    # 4. Source authority: the sibling email lesson is recorded as a rejected
    # candidate, never as an Outlook obligation.
    sources = derive_required_research_sources(
        message=ORDER_REVIEW_ASK,
        lessons=OWN_LESSONS + [SIBLING_EMAIL_LESSON],
    )
    assert sources["sources"] == ["datasets"]
    rejected = [
        candidate for candidate in sources["lesson_candidates"]
        if candidate["source_agent_id"]
    ]
    assert rejected and all(not c["accepted"] for c in rejected)
    assert {c["source"] for c in rejected} == {"datasets", "outlook"}

    # 5. Review recovery: "go ahead" keeps the review contract; a raw read
    # cannot stand in when narration is unavailable; a valid structured review
    # completes it without another read.
    review_task = dict(
        pending,
        status="retrieved",
        original_message=ORDER_REVIEW_ASK,
    )
    assert review_requested(review_task, "go ahead") is True
    assert deterministic_read_fallback_allowed(
        review_required=True,
        deterministic_answer="Workbook read: O-1001 row Status=On Hold ...",
    ) is False

    from core.review_result import build_review_result

    evidence_index = [{
        "evidence_id": "ev:O-1001:Orders!R10",
        "subject_id": "O-1001",
        "source_identity": {
            "file_name": "orders_smoke_ae0c2fda3-1793058137.xlsx",
            "resource_id": "sha1:captured-order",
            "content_hash": "captured-order",
        },
        "retrieval_operation": "attempt-captured",
        "retrieval_execution_id": "exec-captured",
        "row_ref": "Orders!R10",
        "values": [],
    }]
    policy_index = [{
        "policy_id": OWN_LESSONS[0]["id"],
        "topic": OWN_LESSONS[0]["topic"],
        "lesson": OWN_LESSONS[0]["lesson"],
    }]
    validated = build_review_result(
        execution_id="exec-captured",
        requested_records=["O-1001"],
        answer=(
            "O-1001 is on hold pending approval, so it is not ready for "
            "routine processing.\n"
            "```review_result\n"
            '{"assessments": [{"subject_id": "O-1001", '
            '"decision": "Escalate", '
            '"evidence_ids": ["ev:O-1001:Orders!R10"], '
            '"policy_ids": ["7de1a97a66544b27b4919c158191afd0"], '
            '"unresolved_requirements": '
            '["conflicting approvals remain unresolved"]}]}\n'
            "```"
        ),
        allowed_decisions=["Process", "Escalate"],
        evidence_index=evidence_index,
        policy_index=policy_index,
    )
    assert validated["ok"] is True
    assert validated["assessments"][0]["decision"] == "Escalate"
