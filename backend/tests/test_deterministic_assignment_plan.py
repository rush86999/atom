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
        message=("Add a closing paragraph. Please update the payment terms "
                 "in the draft to Net 30."),
        canvas=canvas,
    ) is None


def test_intervening_negation_is_not_compiled():
    canvas = _canvas("Payment terms: Net 45\n")
    assert deterministic_assignment_plan(
        message=("Please do not, under any circumstances, update the "
                 "payment terms in the draft to Net 30."),
        canvas=canvas,
    ) is None


def test_value_residue_is_not_compiled():
    canvas = _canvas("Payment terms: Net 45\n")
    for value in (
        "Net 30, thanks.",
        "Net 30 now.",
        "Net 30 with delivery in 3-4 weeks.",
        "Net 30 don\u2019t touch delivery.",
        "Net 30 unless the client objects.",
        "Net 30 (subject to approval).",
    ):
        assert deterministic_assignment_plan(
            message=("Please update the payment terms in the draft to "
                     f"{value}"),
            canvas=canvas,
        ) is None, value


def test_completion_mapping_is_allowed_in_quotation_section():
    canvas = _canvas(
        "# Quotation Q-2026-114 (DRAFT)\n\nTerms: Net 45\n"
        "Valid until: 2026-12-31\n")
    plan = deterministic_assignment_plan(
        message="Please update the payment terms in the draft to Net 30.",
        canvas=canvas,
    )
    assert plan is not None
    assert plan.ops[0].find == "Terms: Net 45"
    assert plan.ops[0].replace == "Terms: Net 30"


def test_wrong_section_does_not_bind_by_completion_mapping():
    for heading in ("# Warranty", "# Draft Warranty",
                    "# Quotation \u2014 Warranty", "# Document: Warranty"):
        canvas = _canvas(
            f"{heading}\nTerms: 12 months\nWarranty period: 2 years\n")
        assert deterministic_assignment_plan(
            message="Please update the payment terms in the draft to Net 30.",
            canvas=canvas,
        ) is None, heading


def test_email_canvas_uses_the_content_key_not_the_label():
    canvas = {
        "canvas_id": "cv-email",
        "latest_audit_id": "a1",
        "content": {
            "subject": "Q3 pricing",
            "to": "client@example.com",
            "cc": "",
            "body": "Payment terms: Net 45\n",
        },
    }
    plan = deterministic_assignment_plan(
        message="Please update the payment terms in the draft to Net 30.",
        canvas=canvas,
    )
    assert plan is not None
    assert plan.ops[0].field == "body"
    assert plan.ops[0].find == "Payment terms: Net 45"
    from core.chat_canvas_editor import _apply_patch_ops

    updated, failed = _apply_patch_ops(canvas["content"], plan.ops)
    assert failed == []
    assert updated["body"] == "Payment terms: Net 30\n"
    assert updated["subject"] == "Q3 pricing"


def test_edit_verb_mixed_request_is_not_compiled():
    canvas = _canvas("Payment terms: Net 30\n")
    assert deterministic_assignment_plan(
        message=("Edit the greeting in the draft to be warmer. Update the "
                 "payment terms in the draft to Net 30."),
        canvas=canvas,
    ) is None


def test_verbless_second_clause_is_not_compiled():
    canvas = _canvas("Payment terms: Net 30\n")
    assert deterministic_assignment_plan(
        message=("Update the payment terms in the draft to Net 30; "
                 "closing line to Best regards."),
        canvas=canvas,
    ) is None


def test_negation_variants_are_not_compiled():
    canvas = _canvas("Payment terms: Net 45\n")
    for message in (
        "It is not necessary to update the payment terms in the draft "
        "to Net 30.",
        "I would rather you didn't update the payment terms in the draft "
        "to Net 30.",
        "Please update the payment terms in the draft to Net 30 but don't.",
        "Please update the payment terms in the draft to Net 30 or Net 45.",
    ):
        assert deterministic_assignment_plan(
            message=message, canvas=canvas) is None, message


def test_noop_refuses_mixed_request():
    from core.chat_canvas_editor import requirement_check

    canvas = _canvas("Payment terms: Net 30\n")
    check = requirement_check(
        message=("Add a closing paragraph. Please update the payment terms "
                 "in the draft to Net 30."),
        canvas=canvas,
        authorized=True,
        expected_prior_audit_id=None,
    )
    assert check is None or check.get("satisfied") is not True


def test_noop_refuses_header_only_mixed_request():
    from core.chat_canvas_editor import requirement_check

    canvas = {
        "canvas_id": "cv-header",
        "latest_audit_id": "a1",
        "content": {
            "subject": "Q4 pricing",
            "to": "a@b.com",
            "cc": "",
            "body": "Payment terms: Net 30\n",
        },
    }
    check = requirement_check(
        message="Update the subject to Q4 pricing; closing line to Best regards.",
        canvas=canvas,
        authorized=True,
        expected_prior_audit_id="a1",
    )
    assert check is None or check.get("satisfied") is not True
