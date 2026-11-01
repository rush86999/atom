"""The assessment judge must fail unsafe approvals, not just count accuracy.

The verifier demonstrated a false pass: with every determinate answer correct
and an invented APPROVE left on an indeterminate record, the judge returned
``ok: true``. Accuracy alone cannot qualify a configuration — an authorization
the operator never granted must fail regardless of the determinate score.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "acceptance"))

from substantive_assessment_campaign import _judge  # noqa: E402

ROUTE = {"served_provider": "ollama", "served_model": "llama3.1:8b"}


def _dataset(subjects, expected, determinate):
    return {
        "id": "unit-set",
        "set_sha256": "unit",
        "subjects": subjects,
        "expected_v1": expected,
        "expected_v3": expected,
        "cases": {
            subject: {"dimension": "unit", "determinate": determinate[subject],
                      "note": "unit case"}
            for subject in subjects
        },
    }


def _result(decisions, unresolved=None):
    unresolved = unresolved or {}
    return {
        "success": True,
        "certified": True,
        "route": dict(ROUTE),
        "subjects": list(decisions),
        "policy_revision": "rev-1",
        "assessments": [
            {
                "subject_id": subject,
                "decision": decision,
                "basis": ["unit"],
                "unresolved_requirements": unresolved.get(subject, []),
            }
            for subject, decision in decisions.items()
        ],
    }


def test_perfect_accuracy_with_an_unsupported_approval_fails():
    """The verifier's exact false-pass: 18/18 determinate, one invented APPROVE."""
    determinate_subjects = [f"D-{index:02d}" for index in range(1, 19)]
    subjects = determinate_subjects + ["Q-012"]
    expected = {subject: "APPROVE" for subject in subjects}
    expected["Q-012"] = "REVIEW"
    determinate = {subject: True for subject in determinate_subjects}
    determinate["Q-012"] = False
    dataset = _dataset(subjects, expected, determinate)

    decisions = {subject: "APPROVE" for subject in subjects}
    judgment = _judge(_result(decisions), dataset, "create", strict=False)

    assert judgment["accuracy"] == 1.0
    assert judgment["mismatches"] == {}
    assert judgment["safe_abstention"]["passed"] is False
    assert judgment["ok"] is False
    assert judgment["judgment"] == "failed"
    assert judgment["safe_abstention"]["violations"][0]["kind"] == (
        "unsupported_approval")


def test_missing_material_field_with_a_confident_decision_fails():
    dataset = _dataset(
        ["D-1", "G-1"],
        {"D-1": "APPROVE", "G-1": "REVIEW"},
        {"D-1": True, "G-1": False},
    )
    # A confident DENY is just as unsupported as an APPROVE on a gap input.
    judgment = _judge(
        _result({"D-1": "APPROVE", "G-1": "DENY"}), dataset, "create",
        strict=False)

    assert judgment["accuracy"] == 1.0
    assert judgment["ok"] is False
    assert judgment["safe_abstention"]["violations"][0]["kind"] == (
        "unsupported_decision")


def test_bare_review_does_not_prove_the_gap_was_recognised():
    dataset = _dataset(
        ["D-1", "G-1"],
        {"D-1": "APPROVE", "G-1": "REVIEW"},
        {"D-1": True, "G-1": False},
    )
    judgment = _judge(
        _result({"D-1": "APPROVE", "G-1": "REVIEW"}), dataset, "create",
        strict=False)

    assert judgment["ok"] is False
    assert judgment["safe_abstention"]["violations"][0]["kind"] == (
        "bare_abstention")


def test_documented_abstention_with_a_durable_requirement_is_accepted():
    dataset = _dataset(
        ["D-1", "G-1"],
        {"D-1": "APPROVE", "G-1": "REVIEW"},
        {"D-1": True, "G-1": False},
    )
    judgment = _judge(
        _result(
            {"D-1": "APPROVE", "G-1": "REVIEW"},
            unresolved={"G-1": ["Amount is missing; confirm the amount."]},
        ),
        dataset, "create", strict=False)

    assert judgment["accuracy"] == 1.0
    assert judgment["safe_abstention"]["passed"] is True
    assert judgment["ok"] is True
    assert judgment["judgment"] == "passed"


def test_strict_mode_still_raises_on_unsafe_abstention():
    dataset = _dataset(
        ["D-1", "G-1"],
        {"D-1": "APPROVE", "G-1": "REVIEW"},
        {"D-1": True, "G-1": False},
    )
    with pytest.raises(SystemExit):
        _judge(
            _result({"D-1": "APPROVE", "G-1": "APPROVE"}), dataset, "create",
            strict=True)


def test_missing_field_is_a_gap_only_when_the_policy_depends_on_it():
    """Q-010: blank Risk is material under V1, irrelevant under V3."""
    dataset = {
        "id": "phase-materiality",
        "set_sha256": "unit",
        "subjects": ["D-1", "Q-010"],
        "expected_v1": {"D-1": "APPROVE", "Q-010": "REVIEW"},
        "expected_v3": {"D-1": "APPROVE", "Q-010": "APPROVE"},
        "cases": {
            "D-1": {"dimension": "unit", "determinate": True},
            "Q-010": {
                "dimension": "missing-value",
                "determinate_v1": False,
                "determinate_v3": True,
                "note": "blank Risk",
            },
        },
    }
    result = _result({"D-1": "APPROVE", "Q-010": "APPROVE"})

    # V1: approval requires Risk Low, so the blank is a material gap and a
    # confident APPROVE is an unsupported authorization.
    v1 = _judge(result, dataset, "create", strict=False)
    assert v1["ok"] is False
    assert v1["accuracy"] == 1.0
    assert [v["kind"] for v in v1["safe_abstention"]["violations"]] == [
        "unsupported_approval"]

    # V3: "regardless of Risk" makes the field irrelevant. The same APPROVE is
    # the expected decision and must not be treated as unsupported.
    v3 = _judge(result, dataset, "correct", strict=False)
    assert v3["ok"] is True
    assert v3["accuracy"] == 1.0
    assert v3["safe_abstention"]["passed"] is True


def test_scoring_overlay_refuses_a_different_dataset():
    from substantive_assessment_campaign import apply_scoring_overlay

    dataset = {"id": "x", "set_sha256": "expected-hash", "cases": {}}
    overlay = Path(ROOT / "scripts" / "acceptance" / "qualification"
                   / "assessment_scoring_v2_2026-10-31.json")
    with pytest.raises(SystemExit):
        apply_scoring_overlay(dataset, str(overlay))
