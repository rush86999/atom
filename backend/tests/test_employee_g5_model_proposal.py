"""G5 seam: model-proposed work compiled through the existing patch/adoption."""
from __future__ import annotations

import asyncio
from decimal import Decimal

from core.assignment_plan import new_assignment, new_step, step_by_id
import core.quote_rows  # noqa: F401,E402  (registers quote.lines_from_rows)
import core.assignment_quote  # noqa: F401,E402
import core.quote_rows  # noqa: F401,E402
from core.employee_adaptation import (
    AdaptationProposal,
    adopt_adaptation,
    propose_adaptation,
)
from core.employee_patch import StepPatch
from core.employee_proposal import context_from_record
from tests.test_assignment_executor import _teaching, env  # noqa: F401


def _run(coro):
    return asyncio.run(coro)


def _assignment_with_evidence(env):
    read = new_step(
        step_id="read", title="Read held-out quote rows",
        operation_type="retrieve", adapter="workbook.read",
        inputs={}, effect="read_only")
    read["status"] = "applied"
    read["operation_id"] = "op-read"
    read["result"] = {
        "rows": [
            {"Item": "A", "Qty": 2, "Price": 100, "Currency": "USD"},
            {"Item": "B", "Qty": 3, "Price": 50, "Currency": "USD"},
        ],
        "schema": [{"column": "Item"}, {"column": "Qty"},
                   {"column": "Price"}, {"column": "Currency"}],
        "coverage": {"complete": True, "known": True, "truncated": False},
        "source_version": "heldout-v1",
    }
    plan = new_assignment(
        objective="Quote the held-out customer request",
        employee_id="employee-1", workspace_id="ws_assign",
        tenant_id="tenant_assign", teaching_snapshot=_teaching(),
        steps=[read], authorized_actions=["retrieve", "calculate"],
        completion_criteria=[{"kind": "required_work_complete"}])
    record = env["executor"].create_assignment(
        "conv-g5-model", "Quote the held-out customer request",
        assignment=plan)
    return record["run_id"]


def test_model_proposed_calculation_is_compiled_and_executed(env):
    run_id = _assignment_with_evidence(env)
    record = env["lifecycle"].get_task(run_id)
    context = context_from_record(
        record,
        adapter_views=[
            {"adapter": "quote.lines_from_rows", "effect": "local",
             "operation_type": "calculate",
             "required_actions": ["calculate"]},
            {"adapter": "quote.calculate", "effect": "local",
             "operation_type": "calculate",
             "required_actions": ["calculate"]},
        ])

    class FakeLLM:
        def __init__(self):
            self.kwargs = {}

        async def generate_structured_response(self, **kwargs):
            self.kwargs = kwargs
            return AdaptationProposal(
                decision="replan",
                reason=(
                    "The held-out rows establish both quote lines; compute "
                    "the exact total with explicit freight/tax."),
                observation_ids=["evidence-read-1"],
                new_steps=[
                    StepPatch(
                        step_id="lines",
                        title="Map held-out quote rows",
                        operation_type="calculate",
                        adapter="quote.lines_from_rows",
                        depends_on=["read"],
                        effect="local",
                        inputs={
                            "rows": "${read.rows}",
                            "columns": {
                                "item_id": "Item", "quantity": "Qty",
                                "unit_price": "Price",
                                "currency": "Currency"},
                            "defaults": {"currency": "USD"},
                        },
                    ),
                    StepPatch(
                        step_id="calculate",
                        title="Calculate the exact quote total",
                        operation_type="calculate",
                        adapter="quote.calculate",
                        depends_on=["lines"],
                        effect="local",
                        inputs={
                            "line_items": "${lines.line_items}",
                            "currency": "USD",
                            "freight": "20.00",
                            "tax": {"basis": "none"},
                        },
                    ),
                ],
            )

    fake = FakeLLM()
    proposal = _run(propose_adaptation(
        context,
        [{"observation_id": "evidence-read-1",
          "kind": "evidence_result",
          "step_id": "read",
          "reason": "the authorized read completed"}],
        assignment=record["assignment"], llm_service=fake))
    assert proposal["source"] == "model"
    assert fake.kwargs["output_mode"] == "json"
    assert fake.kwargs["cascade"] is False
    assert fake.kwargs["allow_moa"] is False

    adopted = adopt_adaptation(
        env["lifecycle"], run_id, proposal["proposal"])
    assert adopted["status"] == "applied"
    status = _run(env["executor"].execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    calculated = step_by_id(assignment, "calculate")
    assert calculated["status"] == "applied"
    assert Decimal(str(calculated["result"]["value"])) == Decimal("370.00")
    assert status["assignment"]["status"] == "completed"
