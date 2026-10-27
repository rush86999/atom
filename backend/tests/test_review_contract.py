"""Accepted review contract — captured rehearsal regressions.

The accepted objective owns the subjects. The read may find extra text; it
cannot add or replace review subjects. A validated assessment must agree with
the accepted contract exactly.
"""

import json

from core.review_contract import (
    accepted_subjects,
    build_accepted_contract,
    same_contract_inputs,
    strip_catalogued_names,
)
from core.review_result import build_evidence_index, build_review_result

ORDER_PROMPT = (
    "Using the uploaded orders_smoke_ae0c2fda3-1793058137.xlsx, review order "
    "{order} against the order processing policy. Cite Order ID, Status, Qty, "
    "Unit Price, Currency, Approval 1, Approval 2, Manager Exception, and "
    "Notes from the row. State process or escalate and explain the policy "
    "basis. Do not send, approve, or modify anything."
)
CATALOGUED = ["orders_smoke_ae0c2fda3-1793058137.xlsx"]


def test_captured_o1001_subjects_are_identifiers_only():
    contract = build_accepted_contract(
        ORDER_PROMPT.format(order="O-1001"),
        catalogued_names=CATALOGUED,
    )
    assert contract["subjects"] == ["O-1001"]
    assert "order_id" in contract["requested_fields"]
    assert "manager_exception" in contract["requested_fields"]


def test_captured_o1010_subjects_are_identifiers_only():
    contract = build_accepted_contract(
        ORDER_PROMPT.format(order="O-1010"),
        catalogued_names=CATALOGUED,
    )
    assert contract["subjects"] == ["O-1010"]


def test_multi_subject_review_preserves_both_accepted_subjects():
    contract = build_accepted_contract(
        "Review O-1001 and O-1010 in orders_smoke_ae0c2fda3-1793058137.xlsx. "
        "Cite Order ID and Unit Price.",
        catalogued_names=CATALOGUED,
    )
    assert contract["subjects"] == ["O-1001", "O-1010"]
    assert "unit price" not in [s.lower() for s in contract["subjects"]]


def test_catalogued_filename_stem_is_not_a_subject():
    cleaned = strip_catalogued_names(
        "Using orders_smoke_ae0c2fda3-1793058137.xlsx, review O-1001.",
        CATALOGUED,
    )
    assert "orders_smoke" not in cleaned.lower()
    assert accepted_subjects(
        "Using orders_smoke_ae0c2fda3-1793058137.xlsx, review O-1001.",
        catalogued_names=CATALOGUED,
    ) == ["O-1001"]


def test_unit_price_cannot_be_substituted_for_the_accepted_subject():
    accepted = ["O-1001"]
    structured = {
        "source_identity": {
            "file_name": "orders_smoke_ae0c2fda3-1793058137.xlsx",
            "content_hash": "hash-1",
        },
        "retrieval_operation": "attempt-1",
        "source_execution_id": "exec-1",
        "requested_items": ["Unit Price"],
        "targets": [{
            "item": "O-1001",
            "identity": {"candidates": [{
                "ref": "Orders!R2",
                "values": [{"col": "A2", "display": "O-1001"}],
            }]},
        }],
    }
    evidence = build_evidence_index(structured, subjects=accepted)
    assert [entry["subject_id"] for entry in evidence] == ["O-1001"]
    review = build_review_result(
        execution_id="exec-1",
        requested_records=accepted,
        answer=(
            "```review_result\n"
            + json.dumps({"assessments": [{
                "subject_id": "Unit Price",
                "decision": "Process",
                "evidence_ids": [evidence[0]["evidence_id"]],
                "policy_ids": ["policy-1"],
            }]})
            + "\n```"
        ),
        allowed_decisions=["Process", "Escalate"],
        evidence_index=evidence,
        policy_index=[{"policy_id": "policy-1", "lesson": "policy"}],
    )
    assert review["ok"] is False
    assert any(
        error.get("code") == "unrequested_subject"
        for error in review["errors"]
    )


def test_repeat_reuses_only_when_inputs_are_unchanged():
    base = build_accepted_contract(
        ORDER_PROMPT.format(order="O-1010"),
        catalogued_names=CATALOGUED,
        source_version="hash-1",
        lessons=[{
            "id": "policy-1",
            "lesson": "Process complete records; escalate holds.",
            "decision_options": ["Process", "Escalate"],
        }],
    )
    assert same_contract_inputs(base, dict(base)) is True

    corrected = build_accepted_contract(
        ORDER_PROMPT.format(order="O-1010"),
        catalogued_names=CATALOGUED,
        source_version="hash-1",
        lessons=[{
            "id": "policy-1",
            "lesson": "O-1010 is on credit hold; escalate.",
            "decision_options": ["Process", "Escalate"],
        }],
    )
    assert same_contract_inputs(base, corrected) is False

    new_source = dict(base, source_version="hash-2")
    assert same_contract_inputs(base, new_source) is False


def test_initial_confirmation_recovery_and_repeat_preserve_same_subjects():
    objective = ORDER_PROMPT.format(order="O-1001")
    paths = [
        {"path": "initial_ask", "objective": objective},
        {"path": "confirmation", "objective": objective},
        {"path": "saved_read_recovery", "objective": objective},
        {"path": "repeat", "objective": objective},
    ]
    subjects = [
        build_accepted_contract(
            item["objective"], catalogued_names=CATALOGUED)["subjects"]
        for item in paths
    ]
    assert subjects == [["O-1001"]] * len(paths)


def test_a_new_subject_does_not_match_the_stored_contract():
    stored = build_accepted_contract(
        ORDER_PROMPT.format(order="O-1010"), catalogued_names=CATALOGUED)
    current = build_accepted_contract(
        ORDER_PROMPT.format(order="O-1001"), catalogued_names=CATALOGUED)
    assert same_contract_inputs(stored, current) is False
