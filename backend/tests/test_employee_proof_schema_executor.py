"""Generated proof-profile negatives through the real executor/objective path."""
from __future__ import annotations

import asyncio

from core.assignment_plan import new_step, step_by_id
from core.task_outcome_contract import build_assignment_outcome
from tests.test_assignment_executor import _create, _teaching, env  # noqa: F401


def _run(coro):
    return asyncio.run(coro)


def test_sent_items_missing_correlation_blocks_completion(env):
    async def send(inputs, context):
        return {
            "status": "applied", "summary": "provider accepted",
            "provider_state": "accepted", "provider_ref": "msg-1",
            "readback": {"sent_items": {"present": True}},
        }

    env["registry"].register("test.proof.send", send)
    run_id, _ = _create(
        env, objective="Send and confirm with no correlation",
        steps=[new_step(
            step_id="send", title="Send", operation_type="outbound",
            adapter="test.proof.send", effect="external",
            approval_required=True, approval_purpose="Send")],
        teaching=_teaching(), authorized_actions=["outbound"],
        completion_criteria=[
            {"criterion_id": "provider_accepted:send",
             "kind": "provider_accepted", "required": True},
            {"criterion_id": "sent_record_confirmed:send",
             "kind": "sent_record_confirmed", "required": True},
        ])
    _run(env["executor"].execute(run_id))
    env["executor"].approve_step(run_id, "send", approved_by="owner")
    result = _run(env["executor"].execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    assert step_by_id(assignment, "send")["status"] == "applied"
    verdict = build_assignment_outcome(
        assignment, env["lifecycle"].get_task(run_id),
        state=result["assignment"]["status"])
    criteria = {
        item["criterion"]: item
        for item in verdict["outcome"]["criterion_results"]
    }
    assert criteria["provider_accepted"]["met"] is True
    assert criteria["sent_record_confirmed"]["met"] is None
    assert verdict["verdict"] is not True
    assert result["assignment"]["status"] != "completed"


def test_source_malformed_coverage_blocks_dependent_execution(env):
    calls = []

    async def source(inputs, context):
        return {
            "status": "applied", "summary": "source read",
            "value": "row", "resource_id": "r-1",
            "source_version": "v1",
            "verification": {"status": "verified"},
            "coverage": {"complete": True, "known": "unknown",
                         "truncated": False},
        }

    async def dependent(inputs, context):
        calls.append("dependent")
        return {"status": "applied", "value": "ok"}

    async def independent(inputs, context):
        calls.append("independent")
        return {"status": "applied", "value": "ok"}

    env["registry"].register("test.proof.source", source)
    env["registry"].register("test.proof.dependent", dependent)
    env["registry"].register("test.proof.independent", independent)
    run_id, _ = _create(
        env, objective="Use a verified source",
        steps=[
            new_step(step_id="independent", title="Independent work",
                     operation_type="retrieve",
                     adapter="test.proof.independent", effect="read_only"),
            new_step(step_id="source", title="Read source",
                     operation_type="retrieve",
                     adapter="test.proof.source", effect="read_only"),
            new_step(step_id="dependent", title="Use source",
                     operation_type="calculate",
                     adapter="test.proof.dependent", effect="local",
                     depends_on=["source"],
                     requires=[{"kind": "receipt", "step_id": "source",
                                "require": "verified"}]),
        ],
        teaching=_teaching(), authorized_actions=["retrieve", "calculate"])
    result = _run(env["executor"].execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    assert calls == ["independent"]
    assert step_by_id(assignment, "source")["status"] == "applied"
    dependent_step = step_by_id(assignment, "dependent")
    assert dependent_step["status"] == "pending"
    assert dependent_step["readiness"]["truth"] == "unknown"
    assert result["assignment"]["status"] != "completed"
