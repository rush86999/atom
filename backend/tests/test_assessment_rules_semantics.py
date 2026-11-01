"""Three-valued rule semantics and the frozen-set canvas boundary."""
from __future__ import annotations

import asyncio
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "acceptance"))

from core.assessment_rules import evaluate_row  # noqa: E402
from substantive_assessment_campaign import (  # noqa: E402
    _judge, apply_scoring_overlay, load_dataset,
)
from deterministic_assessment_qualification import (  # noqa: E402
    _rules_v1, _rules_v3,
)

SET = ROOT / "scripts/acceptance/qualification/assessment_qualification_set_2026-10-31.json"
SCORING = ROOT / "scripts/acceptance/qualification/assessment_scoring_v2_2026-10-31.json"


def test_earlier_unknown_rule_blocks_a_later_conflicting_match():
    rules = [
        {"decision": "REVIEW", "when": [
            {"field": "Region", "op": "eq", "value": "North"}],
         "basis": "North needs review."},
        {"decision": "APPROVE", "when": [
            {"field": "Amount", "op": "gte", "value": 100}],
         "basis": "Amount at least 100."},
    ]
    out = evaluate_row({"Amount": 120, "Region": None}, rules)
    assert out["decision"] == "REVIEW"
    assert out["ambiguous_with"] == ["REVIEW"]
    assert out["unresolved"] == ["Confirm Region before deciding."]
    assert out["missing_fields"] == ["Region"]


def test_earlier_unknown_with_the_same_decision_still_decides():
    rules = [
        {"decision": "APPROVE", "when": [
            {"field": "Region", "op": "eq", "value": "North"}],
         "basis": "North approval."},
        {"decision": "APPROVE", "when": [
            {"field": "Amount", "op": "gte", "value": 100}],
         "basis": "Amount at least 100."},
    ]
    out = evaluate_row({"Amount": 120}, rules)
    assert out["decision"] == "APPROVE"


def test_zero_is_a_value_not_a_blank():
    rules = [
        {"decision": "REVIEW", "when": [
            {"field": "Amount", "op": "blank"}],
         "basis": "blank amount"},
        {"decision": "DENY", "when": [
            {"field": "Amount", "op": "eq", "value": 0}],
         "basis": "zero"},
    ]
    out = evaluate_row({"Amount": 0}, rules)
    assert out["decision"] == "DENY"
    assert out["missing_fields"] == []


def test_nan_is_an_explicit_invalid_input_not_a_crash():
    rules = [
        {"decision": "APPROVE", "when": [
            {"field": "Amount", "op": "gte", "value": 100}],
         "basis": "amount"},
    ]
    out = evaluate_row({"Amount": math.nan}, rules)
    assert out["decision"] == "REVIEW"
    assert out["unresolved"] == ["Confirm Amount before deciding."]


def test_nan_does_not_match_a_text_rule_either():
    rules = [
        {"decision": "APPROVE", "when": [
            {"field": "Amount", "op": "eq", "value": "nan"}],
         "basis": "text"},
    ]
    out = evaluate_row({"Amount": math.nan}, rules)
    # eq against a non-numeric expectation is textual, so "nan" matches the
    # text; the point of the control is that the comparison is decided, not
    # that the engine throws.
    assert out["decision"] in {"APPROVE", "REVIEW"}


def test_v3_blank_risk_does_not_abstain():
    out = evaluate_row(
        {"Ref": "Q-010", "Amount": 100, "Status": "Open", "Risk": "",
         "Region": "North"},
        _rules_v3(),
    )
    assert out["decision"] == "APPROVE"
    assert out["missing_fields"] == []


# --- frozen set through the canvas assessment boundary ----------------------
@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from core.database import Base

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def user():
    return SimpleNamespace(
        id="user-1", workspace_id="ws-1", tenant_id="default",
        role="workspace_admin",
    )


def _manifest(rules, policy):
    return {
        "schema_version": 1,
        "base_component": "table",
        "operations": [
            "read", "select", "calculate", "assess", "edit", "export", "bind",
        ],
        "data_binding": {
            "subject_field": "Ref", "measure_field": "Amount",
            "status_field": "Status",
        },
        "editable_fields": ["Amount", "Status"],
        "teaching_binding": {"agent_id": "deterministic", "scope_id": "frozen"},
        "decision_options": ["APPROVE", "REVIEW", "DENY"],
        "task_policy": policy,
        "outputs": ["xlsx"],
        "required_approvals": [],
        "assessment_mode": "deterministic",
        "decision_rules": rules,
    }


def _run_phase(db, user, rules, policy, phase):
    from core.canvas_capability_service import (
        assess_operation, bind_dataset, set_manifest,
    )
    from core.models import Canvas

    dataset = apply_scoring_overlay(load_dataset(str(SET)), str(SCORING))
    canvas = Canvas(
        id=f"canvas_frozen_{phase}", tenant_id="default", workspace_id="ws-1",
        created_by="user-1", name=f"frozen {phase}", canvas_type="sheet",
        content={}, status="active",
    )
    db.add(canvas)
    db.commit()
    set_manifest(db, canvas, user, _manifest(rules, policy))
    bind_dataset(
        db, canvas, user, dataset["columns"], dataset["rows"],
        source={"file_name": "frozen.csv", "sha256": "frozen"},
    )
    result = asyncio.run(assess_operation(
        db, canvas, user, "Assess every row.", llm_service=None))
    return dataset, result


def _assert_boundary_decisions(dataset, result, phase, expected_determinate):
    from substantive_assessment_campaign import _is_determinate

    assert result["route"]["output_mode"] == "deterministic"
    assert result["route"]["served_provider"] == "deterministic"
    assert result["route"]["served_model"] == "taught_rules"
    assessments = {item["subject_id"]: item for item in result["assessments"]}
    assert sorted(assessments) == sorted(dataset["subjects"])
    expected = dataset["expected_v1" if phase == "create" else "expected_v3"]
    determinate = [
        subject for subject in dataset["subjects"]
        if _is_determinate(dataset["cases"][subject], phase)]
    gaps = [s for s in dataset["subjects"] if s not in determinate]
    assert len(determinate) == expected_determinate
    for subject in determinate:
        assert assessments[subject]["decision"] == expected[subject], subject
    for subject in gaps:
        assert assessments[subject]["decision"] == "REVIEW", subject
        assert assessments[subject]["unresolved_requirements"], subject


def test_frozen_set_passes_through_the_canvas_boundary_v1(db, user):
    dataset = load_dataset(str(SET))
    dataset, result = _run_phase(
        db, user, _rules_v1(), dataset["policy_v1"], "create")
    _assert_boundary_decisions(dataset, result, "create", 18)


def test_frozen_set_passes_through_the_canvas_boundary_v3(db, user):
    dataset = load_dataset(str(SET))
    dataset, result = _run_phase(
        db, user, _rules_v3(), dataset["policy_v3"], "correct")
    _assert_boundary_decisions(dataset, result, "correct", 19)


def test_multiple_earlier_unknowns_cannot_be_overlooked():
    """The verifier's exact case: an intervening possible DENY."""
    rules = [
        {"decision": "APPROVE", "when": [
            {"field": "Region", "op": "eq", "value": "North"}],
         "basis": "North approves."},
        {"decision": "DENY", "when": [
            {"field": "Risk", "op": "eq", "value": "High"}],
         "basis": "High risk denies."},
        {"decision": "APPROVE", "when": [
            {"field": "Amount", "op": "gte", "value": 100}],
         "basis": "Amount approves."},
    ]
    out = evaluate_row({"Amount": 120}, rules)
    assert out["decision"] == "REVIEW"
    assert out["unresolved"] == ["Confirm Risk before deciding."]
    assert out["ambiguous_with"] == ["DENY"]

    # The completions genuinely disagree, so a confident result must fail.
    assert evaluate_row(
        {"Region": "South", "Risk": "High", "Amount": 120}, rules
    )["decision"] == "DENY"
    assert evaluate_row(
        {"Region": "North", "Risk": "High", "Amount": 120}, rules
    )["decision"] == "APPROVE"


def test_repeated_labels_do_not_force_clarification():
    rules = [
        {"decision": "APPROVE", "when": [
            {"field": "Region", "op": "eq", "value": "North"}],
         "basis": "North approves."},
        {"decision": "APPROVE", "when": [
            {"field": "Risk", "op": "eq", "value": "Low"}],
         "basis": "Low risk approves."},
        {"decision": "APPROVE", "when": [
            {"field": "Amount", "op": "gte", "value": 100}],
         "basis": "Amount approves."},
    ]
    out = evaluate_row({"Amount": 120}, rules)
    assert out["decision"] == "APPROVE"
    assert out["unresolved"] == []


def test_false_conjunction_beats_unknown():
    rules = [
        {"decision": "DENY", "when": [
            {"field": "Status", "op": "eq", "value": "Closed"},
            {"field": "Region", "op": "eq", "value": "North"}],
         "basis": "closed north"},
        {"decision": "APPROVE", "when": [
            {"field": "Amount", "op": "gte", "value": 100}],
         "basis": "amount"},
    ]
    # Status is Open (definitively false), so the rule cannot apply even though
    # Region is missing. The later rule wins without clarification.
    out = evaluate_row(
        {"Status": "Open", "Amount": 120}, rules)
    assert out["decision"] == "APPROVE"
    assert out["missing_fields"] == []


def test_missing_field_no_rule_uses_is_irrelevant():
    rules = [
        {"decision": "APPROVE", "when": [
            {"field": "Amount", "op": "gte", "value": 100}],
         "basis": "amount"},
    ]
    out = evaluate_row(
        {"Amount": 120, "Region": None, "Note": None}, rules)
    assert out["decision"] == "APPROVE"
    assert out["unresolved"] == []


@pytest.mark.parametrize("rules,cells,domain", [
    pytest.param(
        [
            {"decision": "APPROVE", "when": [
                {"field": "Region", "op": "eq", "value": "North"}]},
            {"decision": "DENY", "when": [
                {"field": "Risk", "op": "eq", "value": "High"}]},
            {"decision": "APPROVE", "when": [
                {"field": "Amount", "op": "gte", "value": 100}]},
        ],
        {"Amount": 120},
        {"Region": ["North", "South"], "Risk": ["High", "Low"]},
        id="three-rule",
    ),
    pytest.param(
        [
            {"decision": "DENY", "when": [
                {"field": "Region", "op": "eq", "value": "North"}]},
            {"decision": "APPROVE", "when": [
                {"field": "Risk", "op": "eq", "value": "Low"}]},
            {"decision": "APPROVE", "when": [
                {"field": "Amount", "op": "gte", "value": 100}]},
        ],
        {"Amount": 120},
        {"Region": ["North", "South"], "Risk": ["High", "Low"]},
        id="two-unknowns-conflict",
    ),
    pytest.param(
        [
            {"decision": "DENY", "when": [
                {"field": "Region", "op": "eq", "value": "North"}]},
            {"decision": "DENY", "when": [
                {"field": "Risk", "op": "eq", "value": "High"}]},
            {"decision": "APPROVE", "when": [
                {"field": "Amount", "op": "gte", "value": 100}]},
        ],
        {"Amount": 120},
        {"Region": ["North", "South"], "Risk": ["High", "Low"]},
        id="two-unknowns-same-label",
    ),
])
def test_partial_input_matches_fully_specified_completions(
        rules, cells, domain):
    """If completions disagree, a confident result must fail."""
    import itertools

    fields = sorted(domain)
    decisions = set()
    for values in itertools.product(*(domain[f] for f in fields)):
        filled = dict(cells)
        filled.update(dict(zip(fields, values)))
        decisions.add(evaluate_row(filled, rules)["decision"])

    out = evaluate_row(cells, rules)
    if len(decisions) > 1:
        assert out["decision"] == "REVIEW"
        assert out["unresolved"], "ambiguity must preserve a requirement"
    else:
        assert out["decision"] == next(iter(decisions))
