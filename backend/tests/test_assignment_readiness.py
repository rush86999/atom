"""Deterministic business readiness for assignment steps."""
from __future__ import annotations

import datetime as dt

import pytest

from core.assignment_plan import new_assignment, new_step, new_teaching_snapshot
from core.assignment_readiness import (
    evaluate_step_readiness,
    normalize_facts,
    normalize_requirements,
)


def _assignment(**overrides):
    facts = overrides.pop("facts", [])
    steps = overrides.pop("steps", [])
    sources = overrides.pop("sources", [
        {"resource_id": "agreement-1", "kind": "document"}])
    return new_assignment(
        objective="Prepare a quote",
        workspace_id="ws-a", tenant_id="t-a",
        teaching_snapshot=new_teaching_snapshot(revision="teach-1"),
        sources=sources, steps=steps, facts=facts, **overrides)


def _fact(fact_id="eligible", value=True, state="established", **extra):
    item = {"fact_id": fact_id, "value": value, "evidence_state": state,
            "subject": {"kind": "customer", "id": "cust-1"},
            "field_id": fact_id, "source_refs": [
                {"resource_id": "agreement-1", "version": "v3"}]}
    item.update(extra)
    return item


def _step(step_id="dependent", requires=None, **extra):
    return new_step(
        step_id=step_id, title=step_id,
        operation_type="retrieve", adapter="test.read",
        requires=requires or [], **extra)


def test_unknown_fact_blocks_only_dependent_branch():
    independent = _step("independent")
    dependent = _step("dependent", requires=[
        {"kind": "fact", "fact_id": "eligible", "equals": True}])
    assignment = _assignment(steps=[independent, dependent], facts=[])
    decision = evaluate_step_readiness(
        dependent, assignment, task_authorization="read_only")
    assert decision["eligible"] is False
    assert decision["truth"] == "unknown"
    assert decision["blockers"][0]["kind"] == "qualification"
    from core.assignment_plan import ready_steps
    ready = ready_steps(assignment, task_authorization="read_only")
    assert [step["step_id"] for step in ready] == ["independent"]


def test_established_true_and_false_are_distinct():
    requirement = [{"kind": "fact", "fact_id": "eligible", "equals": True}]
    yes = _assignment(steps=[_step(requires=requirement)],
                      facts=[_fact(value=True)])
    no = _assignment(steps=[_step(requires=requirement)],
                     facts=[_fact(value=False)])
    assert evaluate_step_readiness(
        yes["steps"][0], yes, task_authorization="read_only")["eligible"] is True
    false_decision = evaluate_step_readiness(
        no["steps"][0], no, task_authorization="read_only")
    assert false_decision["eligible"] is False
    assert false_decision["truth"] == "false"
    assert false_decision["blockers"][0]["reason"] == "false"


def test_all_or_unknown_and_not_truth_tables():
    assignment = _assignment(steps=[_step(requires=[
        {"kind": "all", "of": [
            {"kind": "fact", "fact_id": "known", "equals": True},
            {"kind": "fact", "fact_id": "unknown", "equals": True},
        ]},
    ])], facts=[_fact("known", True)])
    decision = evaluate_step_readiness(
        assignment["steps"][0], assignment, task_authorization="read_only")
    assert decision["truth"] == "unknown"

    any_assignment = _assignment(steps=[_step(requires=[
        {"kind": "any", "of": [
            {"kind": "fact", "fact_id": "known", "equals": True},
            {"kind": "fact", "fact_id": "unknown", "equals": True},
        ]},
    ])], facts=[_fact("known", True)])
    any_decision = evaluate_step_readiness(
        any_assignment["steps"][0], any_assignment,
        task_authorization="read_only")
    assert any_decision["eligible"] is True
    assert any_decision["blockers"] == []


def test_receipt_requires_applied_with_result():
    prerequisite = _step("source")
    prerequisite["status"] = "applied"
    prerequisite["result"] = {"value": "row"}
    assignment = _assignment(
        steps=[prerequisite, _step("dependent", requires=[
            {"kind": "receipt", "step_id": "source"}])])
    assert evaluate_step_readiness(
        assignment["steps"][1], assignment,
        task_authorization="read_only")["eligible"] is True

    assignment["steps"][0]["status"] = "skipped"
    decision = evaluate_step_readiness(
        assignment["steps"][1], assignment,
        task_authorization="read_only")
    assert decision["eligible"] is False
    assert decision["blockers"][0]["reason"] == "not_applied"

    assignment["steps"][0]["status"] = "applied"
    assignment["steps"][0]["result"] = None
    assert evaluate_step_readiness(
        assignment["steps"][1], assignment,
        task_authorization="read_only")["eligible"] is False


def test_expired_fact_and_authority_are_not_ready():
    expired = _assignment(steps=[_step(requires=[
        {"kind": "fact", "fact_id": "eligible", "equals": True}])],
        facts=[_fact(validity={"expires_at": "2020-01-01T00:00:00+00:00"})])
    assert evaluate_step_readiness(
        expired["steps"][0], expired,
        task_authorization="authorized")["eligible"] is False

    authority = _assignment(steps=[_step(requires=[
        {"kind": "authority", "allow": ["authorized"]}])])
    assert evaluate_step_readiness(
        authority["steps"][0], authority,
        task_authorization="read_only")["eligible"] is False
    assert evaluate_step_readiness(
        authority["steps"][0], authority,
        task_authorization="authorized")["eligible"] is True


def test_requirements_and_facts_validate():
    assert normalize_requirements([]) == []
    try:
        normalize_requirements([{"kind": "unknown"}])
    except ValueError as exc:
        assert "unsupported requirement" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid requirement accepted")
    assert normalize_facts([_fact()])[0]["fact_id"] == "eligible"
    try:
        normalize_facts([_fact(), _fact()])
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("duplicate facts accepted")


def _receipt_assignment(result, require="applied", source_inputs=None):
    source = _step("source")
    source["status"] = "applied"
    source["operation_id"] = "op-source"
    if source_inputs is not None:
        source["inputs"] = dict(source_inputs)
    source["result"] = result
    return _assignment(steps=[
        source,
        _step("dependent", requires=[
            {"kind": "receipt", "step_id": "source", "require": require}]),
    ])


def test_verified_receipt_accepts_complete_explicit_verification():
    assignment = _receipt_assignment(
        {
            "resource_id": "res-1", "source_version": "v1",
            "coverage": {"complete": True},
            "verification": {"status": "verified",
                             "resource_id": "res-1",
                             "version": "v1",
                             "coverage": {"complete": True}},
        },
        require="verified",
        source_inputs={"resource_binding": {
            "resource_id": "res-1", "source_version": "v1"}})
    decision = evaluate_step_readiness(
        assignment["steps"][1], assignment, task_authorization="read_only")
    assert decision["eligible"] is True, decision
    assert decision["truth"] == "true"


@pytest.mark.parametrize("result,truth,reason", [
    ({}, "unknown", "applied_without_result"),
    ({"value": "row"}, "unknown", "verified_proof_missing"),
    ({"verification": {"status": "conflict"}},
     "false", "verified_proof_refuted"),
    ({"verification": {"status": "refuted"}},
     "false", "verified_proof_refuted"),
    ({"verification": {"status": "verified",
                       "missing_fields": ["currency"]}},
     "false", "verified_proof_missing_fields"),
    ({"verification": {"status": "verified",
                       "mismatches": ["amount"]}},
     "false", "verified_proof_mismatches"),
    ({"verification": {"status": "verified"}},
     "unknown", "verified_identity_missing"),
    ({"resource_id": "res-1", "source_version": "v1",
      "verification": {"status": "verified"}},
     "unknown", "verified_coverage_missing"),
    ({"resource_id": "res-1", "source_version": "v1",
      "coverage": {"complete": False},
      "verification": {"status": "verified"}},
     "unknown", "verified_coverage_incomplete"),
    ({"resource_id": "res-1", "source_version": "v1",
      "coverage": {"known": False},
      "verification": {"status": "verified"}},
     "unknown", "verified_coverage_unknown"),
    ({"coverage": {"known": True, "truncated": True}},
     "unknown", "verified_proof_missing"),
    ({"resource_id": "res-1", "source_version": "v1",
      "verification": {"status": "verified"}, "truncated": True},
     "unknown", "verified_coverage_truncated"),
    ({"verification": {"status": "unverified"}},
     "unknown", "verified_proof_incomplete"),
])
def test_verified_receipt_refuses_weaker_or_incomplete_proof(
        result, truth, reason):
    assignment = _receipt_assignment(result, require="verified")
    decision = evaluate_step_readiness(
        assignment["steps"][1], assignment, task_authorization="read_only")
    assert decision["eligible"] is False, decision
    assert decision["truth"] == truth
    assert decision["blockers"][0]["reason"] == reason


def test_verified_receipt_binding_must_match_a_declared_applied_step():
    assignment = _receipt_assignment(
        {"verification": {"status": "verified"}}, require="verified")
    assignment["steps"][0]["status"] = "skipped"
    decision = evaluate_step_readiness(
        assignment["steps"][1], assignment, task_authorization="read_only")
    assert decision["eligible"] is False
    assert decision["blockers"][0]["reason"] == "not_applied"

    assignment["steps"][0]["status"] = "applied"
    assignment["steps"][1]["requires"] = [
        {"kind": "receipt", "step_id": "absent", "require": "verified"}]
    decision = evaluate_step_readiness(
        assignment["steps"][1], assignment, task_authorization="read_only")
    assert decision["eligible"] is False
    assert decision["blockers"][0]["reason"] == "not_applied"


def test_unknown_receipt_requirement_names_refuse_normalization():
    for require in ("trusted", "verified_or_applied", "material"):
        with pytest.raises(ValueError, match="receipt require"):
            normalize_requirements(
                [{"kind": "receipt", "step_id": "source",
                  "require": require}])


def test_verified_receipt_binding_must_match_the_receipt_identity():
    identity = {
        "operation_id": "op-source",
        "resource_id": "res-1",
        "source_version": "v3",
        "subject": {"kind": "invoice", "id": "INV-1"},
    }
    assignment = _receipt_assignment({
        **identity,
        "coverage": {"complete": True},
        "verification": {
            "status": "verified",
            "operation_id": "op-source",
            "resource_id": "res-1",
            "version": "v3",
            "subject": {"kind": "invoice", "id": "INV-1"},
            "coverage": {"complete": True},
        },
    }, require="verified")
    assert evaluate_step_readiness(
        assignment["steps"][1], assignment,
        task_authorization="read_only")["eligible"] is True

    for field, value, reason in (
        ("operation_id", "op-other", "verified_binding_operation_id_mismatch"),
        ("resource_id", "res-other", "verified_binding_resource_id_mismatch"),
        ("version", "v4", "verified_binding_version_mismatch"),
        ("subject", {"kind": "invoice", "id": "INV-2"},
         "verified_binding_subject_mismatch"),
    ):
        mismatched = _receipt_assignment({
            **identity,
            "verification": {"status": "verified", field: value},
        }, require="verified")
        decision = evaluate_step_readiness(
            mismatched["steps"][1], mismatched,
            task_authorization="read_only")
        assert decision["eligible"] is False, (field, decision)
        assert decision["blockers"][0]["reason"] == reason


def test_verified_receipt_binding_absent_from_receipt_stays_unknown():
    assignment = _receipt_assignment(
        {"verification": {"status": "verified", "request_id": "req-1"}},
        require="verified")
    decision = evaluate_step_readiness(
        assignment["steps"][1], assignment, task_authorization="read_only")
    assert decision["eligible"] is False
    assert decision["truth"] == "unknown"
    assert decision["blockers"][0]["reason"] == (
        "verified_binding_request_id_missing")


def test_fact_source_ref_must_resolve_against_the_accepted_source_scope():
    requirement = [{"kind": "fact", "fact_id": "eligible", "equals": True}]
    foreign = _assignment(
        steps=[_step(requires=requirement)],
        facts=[_fact(source_refs=[{"resource_id": "foreign-1"}])])
    decision = evaluate_step_readiness(
        foreign["steps"][0], foreign, task_authorization="read_only")
    assert decision["eligible"] is False
    assert decision["truth"] == "unknown"

    authored = _assignment(
        steps=[_step(requires=requirement)],
        facts=[_fact(source_refs=[], authority_ref="owner:eligibility")])
    assert evaluate_step_readiness(
        authored["steps"][0], authored,
        task_authorization="read_only")["eligible"] is True
