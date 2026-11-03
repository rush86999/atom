"""Deterministic matrix for typed work requests, previews and adoption."""
from __future__ import annotations

from decimal import Decimal

import pytest

from core.assignment_plan import new_assignment, new_step, step_by_id
from core.employee_adaptation import AdaptationProposal, adopt_adaptation
from core.employee_patch import PlanPatchError, apply_plan_patch
from core.employee_work_compiler import (
    WorkRequestCompileError,
    compile_work_request_patch,
)
from core.employee_work_requests import (
    MoneyTerm,
    QuoteCalculationRequest,
    TaxTerm,
)
from tests.test_assignment_executor import _run, env  # noqa: F401


def _request(source_step_id="read", **overrides):
    payload = {
        "operation": "quote_calculation",
        "source_step_id": source_step_id,
        "require_verified_source": False,
        "columns": {
            "item_id": "Item", "quantity": "Qty", "unit_price": "Price",
            "currency": "Currency"},
        "currency": "USD",
        "freight": MoneyTerm(value="0.00", authority_ref="terms:freight"),
        "tax": TaxTerm(basis="none"),
        "reason": "compute from accepted evidence",
    }
    payload.update(overrides)
    return QuoteCalculationRequest(**payload)


def _read_step(row_count=2):
    rows = [
        {"Item": "A", "Qty": 1, "Price": 1, "Currency": "USD"}
        for _ in range(row_count)
    ]
    read = new_step(
        step_id="read", title="Read price rows", operation_type="retrieve",
        adapter="workbook.read", inputs={}, effect="read_only")
    read.update(status="applied", operation_id="op-read", result={
        "rows": rows,
        "schema": [{"column": "Item"}, {"column": "Qty"},
                   {"column": "Price"}, {"column": "Currency"}],
        "total_count": row_count,
        "coverage": {"complete": True, "known": True, "truncated": False},
    })
    return read


def _assignment(read):
    return new_assignment(
        objective="Quote the accepted population", steps=[read],
        workspace_id="ws_assign", tenant_id="tenant_assign",
        authorized_actions=["retrieve", "calculate"],
        completion_criteria=[{"kind": "required_work_complete"}])


def test_preview_is_labeled_but_execution_uses_full_durable_rows(env):
    read = _read_step(25)
    plan = _assignment(read)
    record = env["executor"].create_assignment(
        "conv-preview-full", plan["objective"], assignment=plan)
    run_id = record["run_id"]
    from core.employee_proposal import context_from_record
    context = context_from_record(env["lifecycle"].get_task(run_id))
    preview = context["evidence_results"][0]["preview"]
    assert preview["sampled"] is True
    assert preview["total_count"] == 25
    assert preview["shown_count"] == 20
    assert preview["omitted_count"] == 5

    assignment = env["lifecycle"].get_assignment(run_id)
    compiled = compile_work_request_patch(
        _request(), assignment, context=context)
    assert compiled["add_steps"][0]["inputs"]["rows"] == "${read.rows}"
    proposal = AdaptationProposal(
        decision="replan", reason="compute the full accepted population",
        observation_ids=["preview-full-1"], work_request=_request())
    adopted = adopt_adaptation(env["lifecycle"], run_id, proposal)
    assert adopted["status"] == "applied"
    status = _run(env["executor"].execute(run_id))
    final = env["lifecycle"].get_assignment(run_id)
    calc = step_by_id(final, compiled["add_steps"][1]["step_id"])
    assert calc["status"] == "applied"
    assert Decimal(str(calc["result"]["value"])) == Decimal("25.00")
    assert status["assignment"]["status"] == "completed"


def test_stale_compiled_patch_refuses_after_task_state_advance(env):
    read = _read_step()
    plan = _assignment(read)
    record = env["executor"].create_assignment(
        "conv-stale-work", plan["objective"], assignment=plan)
    run_id = record["run_id"]
    assignment = env["lifecycle"].get_assignment(run_id)
    context = {
        "task_version": int(record["task_version"]),
        "plan_revision": int(assignment["plan_revision"]),
    }
    patch = compile_work_request_patch(_request(), assignment, context=context)

    def change(record, assignment):
        updated = dict(assignment)
        updated["facts"] = [{
            "fact_id": "changed", "value": True,
            "evidence_state": "established",
            "source_refs": [{"resource_id": "agreement-1",
                             "version": "v2"}],
        }]
        return updated, {}

    env["lifecycle"].mutate_assignment(
        run_id, change, rationale="business state changed")
    assert env["lifecycle"].get_task(run_id)["task_version"] > (
        record["task_version"])
    with pytest.raises(PlanPatchError, match="stale|version"):
        apply_plan_patch(env["lifecycle"], run_id, patch)


def test_duplicate_work_request_is_idempotent(env):
    read = _read_step()
    plan = _assignment(read)
    record = env["executor"].create_assignment(
        "conv-dup-work", plan["objective"], assignment=plan)
    run_id = record["run_id"]
    proposal = AdaptationProposal(
        decision="replan", reason="duplicate request",
        observation_ids=["dup-work-1"], work_request=_request())
    first = adopt_adaptation(env["lifecycle"], run_id, proposal)
    assert first["status"] == "applied"
    revision = env["lifecycle"].get_assignment(run_id)["plan_revision"]
    second = adopt_adaptation(env["lifecycle"], run_id, proposal)
    assert second["status"] == "already_applied"
    assert env["lifecycle"].get_assignment(run_id)["plan_revision"] == revision


def test_unknown_or_ambiguous_request_fields_refuse_compilation(env):
    read = _read_step()
    plan = _assignment(read)
    record = env["executor"].create_assignment(
        "conv-bad-work", plan["objective"], assignment=plan)
    assignment = env["lifecycle"].get_assignment(record["run_id"])
    with pytest.raises(WorkRequestCompileError, match="unknown|absent"):
        compile_work_request_patch(
            _request("absent"), assignment, context={})
    with pytest.raises(WorkRequestCompileError, match="MissingQty|column"):
        compile_work_request_patch(
            _request(columns={"item_id": "Item", "quantity": "MissingQty",
                              "unit_price": "Price"}),
            assignment, context={})
