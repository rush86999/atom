"""Generated omission/type/identity matrix for proof profiles."""
from __future__ import annotations

import pytest

from core.assignment_plan import new_assignment, new_step
from core.assignment_readiness import evaluate_step_readiness
from core.task_outcome_contract import sent_record_confirmed_evidence


def _sent_step(**overrides):
    step = {"operation_id": "op-1", "request_id": "req-1"}
    step.update(overrides)
    return step


def _sent_result(**overrides):
    result = {
        "provider_ref": "msg-1",
        "message_id": "mid-1",
        "account": "owner@example.invalid",
        "readback": {"sent_items": {
            "present": True,
            "operation_id": "op-1",
            "request_id": "req-1",
            "provider_ref": "msg-1",
            "message_id": "mid-1",
            "account": "owner@example.invalid",
        }},
    }
    result.update(overrides)
    return result


def test_sent_items_complete_profile_is_true():
    assert sent_record_confirmed_evidence(
        _sent_step(), _sent_result()) is True


@pytest.mark.parametrize("field", [
    "present", "operation_id", "request_id", "provider_ref", "message_id",
])
def test_sent_items_each_required_field_omission_is_unknown(field):
    result = _sent_result()
    result["readback"]["sent_items"].pop(field)
    assert sent_record_confirmed_evidence(_sent_step(), result) is None


@pytest.mark.parametrize("field,value", [
    ("present", "yes"),
    ("operation_id", 1),
    ("request_id", False),
    ("provider_ref", ["msg-1"]),
    ("message_id", {"id": "mid-1"}),
])
def test_sent_items_wrong_types_are_unknown(field, value):
    result = _sent_result()
    result["readback"]["sent_items"][field] = value
    assert sent_record_confirmed_evidence(_sent_step(), result) is None


@pytest.mark.parametrize("field,value", [
    ("operation_id", "op-other"),
    ("request_id", "req-other"),
    ("provider_ref", "msg-other"),
    ("message_id", "mid-other"),
    ("account", "other@example.invalid"),
])
def test_sent_items_each_wrong_identity_refutes(field, value):
    result = _sent_result()
    result["readback"]["sent_items"][field] = value
    assert sent_record_confirmed_evidence(_sent_step(), result) is False


def test_sent_items_swapped_identity_namespaces_refute():
    result = _sent_result()
    result["readback"]["sent_items"].update({
        "operation_id": "msg-1", "provider_ref": "op-1"})
    assert sent_record_confirmed_evidence(_sent_step(), result) is False


def test_sent_items_bare_boolean_shortcuts_are_unknown():
    assert sent_record_confirmed_evidence(
        _sent_step(), {"provider_ref": "msg-1",
                       "sent_record_confirmed": True}) is None
    assert sent_record_confirmed_evidence(
        _sent_step(), {"provider_ref": "msg-1",
                       "readback": {"sent_items": True}}) is None


def _source_assignment(coverage):
    source = new_step(
        step_id="source", title="source", operation_type="retrieve",
        adapter="workbook.read",
        inputs={"resource_binding": {
            "resource_id": "r1", "source_version": "v1"}})
    source.update(
        status="applied", operation_id="op1",
        result={
            "resource_id": "r1", "source_version": "v1",
            "verification": {"status": "verified"},
            "coverage": coverage,
        })
    child = new_step(
        step_id="child", title="use source", operation_type="calculate",
        adapter="formula.calculate", inputs={},
        requires=[{"kind": "receipt", "step_id": "source",
                   "require": "verified"}])
    return new_assignment(objective="Use verified source", steps=[source, child])


@pytest.mark.parametrize("coverage", [
    {"complete": True},
    {"complete": True, "known": True, "truncated": False},
    {"known": True, "truncated": False},
    {"complete": True, "expected_count": 3, "matched_count": 3},
])
def test_source_coverage_supported_complete_variants(coverage):
    assignment = _source_assignment(coverage)
    decision = evaluate_step_readiness(
        assignment["steps"][1], assignment, task_authorization="read_only")
    assert decision["eligible"] is True, coverage


@pytest.mark.parametrize("coverage", [
    {"complete": True, "known": "unknown", "truncated": False},
    {"complete": True, "known": True, "truncated": "no"},
    {"complete": True, "known": None, "truncated": False},
    {"complete": True, "known": 1, "truncated": False},
    {"complete": 1, "known": True, "truncated": False},
    {"complete": True, "truncated": 0},
    {"complete": False, "known": True, "truncated": False},
    {"known": False, "truncated": False},
    {"truncated": True, "known": True},
    {"complete": True, "expected_count": "inf", "matched_count": 1},
    {"complete": True, "expected_count": -1, "matched_count": 1},
    {"complete": True, "expected_count": 10, "matched_count": 9},
    {"complete": True, "expected_count": 10},
    {"complete": True, "matched_count": 10},
    {"complete": True, "expected_count": 3,
     "matched_count": 3, "known": "yes"},
])
def test_source_coverage_malformed_incomplete_or_contradictory_is_unknown(
        coverage):
    assignment = _source_assignment(coverage)
    decision = evaluate_step_readiness(
        assignment["steps"][1], assignment, task_authorization="read_only")
    assert decision["eligible"] is False, coverage
    assert decision["truth"] == "unknown", coverage
