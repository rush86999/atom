"""Narrow deterministic compiler for explicit user-supplied assignments."""
from __future__ import annotations

from core.chat_canvas_editor import deterministic_assignment_plan


def _canvas(body: str, canvas_id: str = "cv-1", audit_id: str = "a1"):
    return {"canvas_id": canvas_id, "content": {"body": body},
            "latest_audit_id": audit_id}


def test_explicit_assignment_compiles_exact_patch():
    canvas = _canvas("Payment terms: Net 45\nValid until: 2026-12-31\n")
    plan = deterministic_assignment_plan(
        message="Please update the payment terms in the draft to Net 30.",
        canvas=canvas,
        expected_prior_audit_id="a1",
    )
    assert plan is not None and plan.wants_edit is True
    assert len(plan.ops) == 1
    assert plan.ops[0].find == "Payment terms: Net 45"
    assert plan.ops[0].replace == "Payment terms: Net 30"
    assert plan.ops[0].origin == "user_supplied"


def test_negated_instruction_is_not_compiled():
    canvas = _canvas("Payment terms: Net 45\n")
    assert deterministic_assignment_plan(
        message="Do not update the payment terms to Net 30.",
        canvas=canvas,
    ) is None


def test_ambiguous_field_is_not_compiled():
    canvas = _canvas(
        "Payment terms: Net 45\nWarranty terms: 12 months\n")
    assert deterministic_assignment_plan(
        message="Please update the terms in the draft to Net 30.",
        canvas=canvas,
    ) is None


def test_wrong_subject_is_not_compiled():
    canvas = _canvas(
        "Alpha project status: Blocked\nBeta project status: Blocked\n")
    assert deterministic_assignment_plan(
        message="Please update the Gamma project status to On track.",
        canvas=canvas,
    ) is None


def test_stale_revision_is_not_compiled():
    canvas = _canvas("Payment terms: Net 45\n", audit_id="a2")
    assert deterministic_assignment_plan(
        message="Please update the payment terms in the draft to Net 30.",
        canvas=canvas,
        expected_prior_audit_id="a1",
    ) is None


def test_already_satisfied_is_left_to_noop_check():
    canvas = _canvas("Payment terms: Net 30\n")
    assert deterministic_assignment_plan(
        message="Please update the payment terms in the draft to Net 30.",
        canvas=canvas,
    ) is None


def test_negated_current_value_is_not_mechanically_replaced():
    canvas = _canvas("Payment terms: not Net 30\n")
    assert deterministic_assignment_plan(
        message="Please update the payment terms in the draft to Net 30.",
        canvas=canvas,
    ) is None


def test_mixed_request_is_not_compiled():
    canvas = _canvas("Payment terms: Net 45\n")
    assert deterministic_assignment_plan(
        message=("Please also update the payment terms in the draft to "
                 "Net 30."),
        canvas=canvas,
    ) is None
