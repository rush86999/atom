"""Exact reply identity for question/gap waits (public + executor).

The direct-step wait already binds one opaque ``reply_id`` to exact material.
A question/gap wait must obey the same contract while preserving the existing
human ``POST /gaps/{id}/resolve`` compatibility:

* a partial/rejected answer keeps its receipt and the question open;
* the same identity with changed text/value/source/evidence conflicts;
* a new identity may resolve;
* an exact replay after closure is ``already_applied`` with no second effect;
* a new/changed reply after terminal is refused, never certified as a replay;
* the receipt and scope survive a fresh session/restart;
* the check is re-evaluated inside the lifecycle CAS.

This file is authored for root execution; no test here is claimed as passing.
"""
from __future__ import annotations

import copy
import json
import uuid

import pytest

from core.assignment_executor import (
    NeedsContext,
    default_adapter_registry,
    resolution_matches,
)
from core.assignment_plan import (
    new_assignment,
    new_step,
    new_teaching_snapshot,
)
from tests.test_assignment_routes import _run, route_env  # noqa: F401

R1 = "gap-r1"
R2 = "gap-r2"
R3 = "gap-r3"
R4 = "gap-r4"
SOURCE = "pricing owner"
EVIDENCE = "mail-gap-1"


def _new_mapping_adapter(
    route_env, *, correlation, missing="Price", candidate="Amount",
    re_raise=None,
):
    """A real correlated gap until the confirmed column is substituted in."""
    calls = {"n": 0}

    async def adapter(inputs, context):
        calls["n"] += 1
        if re_raise is not None and calls["n"] == re_raise:
            raise NeedsContext(re_raise)
        column = str((inputs or {}).get("value_column") or "")
        if re_raise is None and column == candidate:
            return {"status": "applied", "summary": "mapped price",
                    "value": "35.00", "unit": "USD"}
        if re_raise is not None and calls["n"] > 1 and calls["n"] != re_raise:
            return {"status": "applied", "summary": "mapped price",
                    "value": "35.00", "unit": "USD"}
        raise NeedsContext({
            "concept": "Price",
            "reason": f"required column not found: {missing}",
            "question": "Which column should supply Price?",
            "kind": "missing_evidence",
            "inputs": {"mapping": {
                "concept": "Price", "missing_column": missing,
                "sheet": "Records",
                "candidates": [{"column": candidate}],
            }},
            "waiting": {
                "state": "waiting_for_person", "party": "owner",
                "resume_on": "answer", "correlation_id": correlation,
                "detail": "which column supplies Price",
            },
        })

    return adapter, calls


def _new_text_adapter(route_env, *, correlation, re_raise=None):
    """A non-mapping question that applies once the human answer arrives."""
    calls = {"n": 0}

    async def adapter(inputs, context):
        calls["n"] += 1
        if re_raise is not None and calls["n"] == re_raise:
            raise NeedsContext(re_raise)
        if calls["n"] > 1 and (re_raise is None or calls["n"] != re_raise):
            return {"status": "applied", "summary": "price scope accepted",
                    "value": "100.00"}
        raise NeedsContext({
            "concept": "price_scope",
            "reason": "the price scope is not established",
            "question": "Which price scope applies?",
            "kind": "missing_evidence",
            "waiting": {
                "state": "waiting_for_person", "party": "owner",
                "resume_on": "answer", "correlation_id": correlation,
            },
        })

    return adapter, calls


def _start(route_env, *, adapter_name, adapter):
    route_env["executor"].adapters.register(adapter_name, adapter)
    default_adapter_registry.register(adapter_name, adapter)
    objective = f"Gap identity {uuid.uuid4().hex[:8]}"
    plan = new_assignment(
        objective=objective,
        employee_id="lead-1",
        workspace_id="ws-1",
        tenant_id="tenant-1",
        teaching_snapshot=new_teaching_snapshot(revision="gap-r1"),
        steps=[new_step(
            step_id="read", title="Read the price scope",
            operation_type="retrieve", adapter=adapter_name,
            inputs={"value_column": "Price"}, effect="read_only")],
    )
    record = route_env["executor"].create_assignment(
        f"conv-{uuid.uuid4().hex[:8]}", objective, assignment=plan)
    _run(route_env["executor"].execute(record["run_id"]))
    detail = route_env["executor"].status(record["run_id"])
    assert detail["open_gaps"], detail
    return record["run_id"], plan["assignment_id"], detail["open_gaps"][0]


def _mapping_answer(gap, assignment_id, column="Amount", *, rejected=False):
    payload = {
        "request_id": gap["question_id"],
        "assignment_id": assignment_id,
        "column": column,
    }
    if rejected:
        payload = {
            "rejected": True,
            "request_id": gap["question_id"],
            "assignment_id": assignment_id,
        }
    return json.dumps(payload)


def _reply(route_env, run_id, correlation, *, reply_id, response,
           value=None, source=SOURCE, evidence=EVIDENCE):
    return route_env["client"].post(
        f"/api/assignments/{run_id}/responses/{correlation}",
        json={
            "reply_id": reply_id,
            "response": response,
            "source": source,
            "evidence": evidence,
            "value": value,
        },
    )


def _task(route_env, run_id):
    record = route_env["lifecycle"].get_task(run_id)
    assert record is not None
    return record


def _question(route_env, run_id, question_id):
    return next(
        item for item in (_task(route_env, run_id)["task_revision"].get(
            "unresolved") or [])
        if item.get("question_id") == question_id)


def _step(route_env, run_id, step_id="read"):
    return next(
        item for item in _task(route_env, run_id)["assignment"]["steps"]
        if item.get("step_id") == step_id)


def _wakes(route_env, run_id):
    return sum(
        1 for entry in route_env["runs"].get_decisions(run_id)
        if entry.get("kind") == "wake")


def _rebuilt_executor(route_env):
    """A fresh-session executor over the same scratch database."""
    from core.assignment_executor import AssignmentExecutor
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle

    runs = GoalRunService(
        workspace_id="ws-1", tenant_id="tenant-1",
        session_factory=route_env["factory"])
    return AssignmentExecutor(TaskLifecycle(
        runs,
        GoalService(
            workspace_id="ws-1", tenant_id="tenant-1",
            session_factory=route_env["factory"])))


def test_gap_partial_conflict_new_identity_replay_and_terminal(
        route_env, tmp_path):
    correlation = "gap-corr-1"
    adapter, calls = _new_mapping_adapter(
        route_env, correlation=correlation)
    run_id, assignment_id, gap = _start(
        route_env, adapter_name=f"test.gap.identity.{uuid.uuid4().hex[:8]}",
        adapter=adapter)
    attempts_before = int(_step(route_env, run_id).get("attempts") or 0)
    wake_before = _wakes(route_env, run_id)
    rejected_answer = _mapping_answer(gap, assignment_id, rejected=True)

    first = _reply(
        route_env, run_id, correlation, reply_id=R1,
        response=rejected_answer, value=rejected_answer)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "rejected_candidates", first.text

    after_partial = _task(route_env, run_id)
    question = _question(route_env, run_id, gap["question_id"])
    assert question["status"] == "open", question
    assert int(_step(route_env, run_id).get("attempts") or 0) == attempts_before
    receipts = _step(route_env, run_id).get("reply_receipts") or []
    assert [item.get("reply_id") for item in receipts] == [R1], receipts
    assert receipts[0].get("outcome") == "rejected_candidates", receipts[0]
    assert receipts[0].get("material_sha256"), receipts[0]
    assert len(receipts[0]["material_sha256"]) == 64, receipts[0]
    conflicts = _step(route_env, run_id)["waiting"].get("conflicts") or []
    assert conflicts[-1].get("reply_id") == R1, conflicts[-1]
    assert _wakes(route_env, run_id) == wake_before

    # Exact replay of the partial: receipt/decision/task version do not move.
    version_before = after_partial["task_version"]
    receipts_before = copy.deepcopy(receipts)
    decisions_before = len(route_env["runs"].get_decisions(run_id))
    replay = _reply(
        route_env, run_id, correlation, reply_id=R1,
        response=rejected_answer, value=rejected_answer)
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "rejected_candidates", replay.text
    assert _task(route_env, run_id)["task_version"] == version_before
    assert (_step(route_env, run_id).get("reply_receipts") or []) == (
        receipts_before)
    assert len(route_env["runs"].get_decisions(run_id)) == decisions_before
    assert _wakes(route_env, run_id) == wake_before

    # Same identity + changed material conflicts before any write/wake.
    corrected = _mapping_answer(gap, assignment_id, "Amount")
    changed = _reply(
        route_env, run_id, correlation, reply_id=R1,
        response=corrected, value=corrected)
    assert changed.status_code == 409, changed.text
    assert "reply" in changed.text.lower() or "material" in changed.text.lower()
    assert (_step(route_env, run_id).get("reply_receipts") or []) == (
        receipts_before)
    assert _question(route_env, run_id, gap["question_id"])["status"] == "open"
    assert int(_step(route_env, run_id).get("attempts") or 0) == attempts_before
    assert _wakes(route_env, run_id) == wake_before

    # A NEW identity with corrected material is allowed to resolve once.
    accepted = _reply(
        route_env, run_id, correlation, reply_id=R2,
        response=corrected, value=corrected)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json().get("status") not in (
        "conflict", "reply_conflict", "terminal", "rejected_candidates"
    ), accepted.json()
    final = _task(route_env, run_id)
    assert final["assignment"]["status"] == "completed", final["assignment"]
    final_receipts = _step(route_env, run_id).get("reply_receipts") or []
    assert [item.get("reply_id") for item in final_receipts] == [R1, R2]
    assert final_receipts[-1].get("outcome") == "resolved", final_receipts[-1]
    external = _step(route_env, run_id).get("external_response") or {}
    assert external.get("reply_id") == R2, external
    assert external.get("material_sha256") == (
        final_receipts[-1]["material_sha256"]), external
    assert int(_step(route_env, run_id).get("attempts") or 0) == (
        attempts_before + 1)
    assert _wakes(route_env, run_id) == wake_before + 1
    calls_after_accept = calls["n"]

    # Exact replay after closure is idempotent (explicit identity).
    version_before = final["task_version"]
    decisions_before = len(route_env["runs"].get_decisions(run_id))
    exact = _reply(
        route_env, run_id, correlation, reply_id=R2,
        response=corrected, value=corrected)
    assert exact.status_code == 200, exact.text
    assert exact.json().get("status") == "already_applied", exact.text
    assert _task(route_env, run_id)["task_version"] == version_before
    assert (_step(route_env, run_id).get("reply_receipts") or []) == (
        final_receipts)
    assert len(route_env["runs"].get_decisions(run_id)) == decisions_before
    assert _wakes(route_env, run_id) == wake_before + 1
    assert calls["n"] == calls_after_accept

    # A new/changed reply after completion is terminal, not a replay.
    late_answer = _mapping_answer(gap, assignment_id, "Amount")
    late = _reply(
        route_env, run_id, correlation, reply_id=R3,
        response=late_answer, value=late_answer)
    assert late.status_code == 409, late.text
    assert _task(route_env, run_id)["assignment"]["status"] == "completed"
    assert (_step(route_env, run_id).get("reply_receipts") or []) == (
        final_receipts)
    assert _wakes(route_env, run_id) == wake_before + 1
    assert calls["n"] == calls_after_accept

    # Fresh session readback: authoritative receipts survive restart and the
    # same exact identity still replays without re-running the adapter.
    fresh = _rebuilt_executor(route_env)
    durable = fresh.lifecycle.get_assignment(run_id)
    durable_step = next(
        item for item in durable["steps"] if item["step_id"] == "read")
    assert [item.get("reply_id") for item in
            durable_step.get("reply_receipts") or []] == [R1, R2]
    replay_after_restart = fresh.record_external_response(
        run_id, correlation, response=corrected, source=SOURCE,
        evidence=EVIDENCE, value=corrected, reply_id=R2)
    assert replay_after_restart.get("status") == "already_applied", (
        replay_after_restart)
    assert calls["n"] == calls_after_accept


@pytest.mark.parametrize("field,changed", [
    ("response", {"response_override": "rejected with a different note"}),
    ("source", {"source": "different pricing desk"}),
    ("evidence", {"evidence": "mail-gap-2"}),
    ("value", {"value_override": "different value"}),
])
def test_gap_same_identity_refuses_each_changed_material_field(
        route_env, tmp_path, field, changed):
    """Every semantic question-reply field participates in the identity."""
    correlation = f"gap-corr-{field}"
    adapter, _calls = _new_mapping_adapter(
        route_env, correlation=correlation)
    run_id, assignment_id, gap = _start(
        route_env, adapter_name=f"test.gap.field.{uuid.uuid4().hex[:8]}",
        adapter=adapter)
    rejected_answer = _mapping_answer(gap, assignment_id, rejected=True)
    first = _reply(
        route_env, run_id, correlation, reply_id=R1,
        response=rejected_answer, value=rejected_answer)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "rejected_candidates", first.text
    receipts_before = copy.deepcopy(
        _step(route_env, run_id).get("reply_receipts") or [])
    attempts_before = int(_step(route_env, run_id).get("attempts") or 0)

    response = changed.get("response_override", rejected_answer)
    value = changed.get("value_override", rejected_answer)
    refused = _reply(
        route_env, run_id, correlation, reply_id=R1,
        response=response, value=value,
        source=changed.get("source", SOURCE),
        evidence=changed.get("evidence", EVIDENCE))
    assert refused.status_code == 409, refused.text
    assert (_step(route_env, run_id).get("reply_receipts") or []) == (
        receipts_before)
    assert _question(route_env, run_id, gap["question_id"])["status"] == "open"
    assert int(_step(route_env, run_id).get("attempts") or 0) == attempts_before


def test_gap_cross_wait_identity_reuse_refuses_and_new_identity_resolves(
        route_env, tmp_path):
    """R1 on correlation B is a scope conflict, not a fresh answer."""
    first_corr = "gap-scope-1"
    second_corr = "gap-scope-2"
    second_gap = {
        "concept": "price_scope_second",
        "reason": "a second price scope is still unknown",
        "question": "Which second price scope applies?",
        "kind": "missing_evidence",
        "waiting": {
            "state": "waiting_for_person", "party": "owner",
            "resume_on": "answer", "correlation_id": second_corr,
        },
    }
    adapter, _calls = _new_mapping_adapter(
        route_env, correlation=first_corr, re_raise=second_gap)
    run_id, assignment_id, gap = _start(
        route_env, adapter_name=f"test.gap.scope.{uuid.uuid4().hex[:8]}",
        adapter=adapter)
    rejected_answer = _mapping_answer(gap, assignment_id, rejected=True)
    partial = _reply(
        route_env, run_id, correlation=first_corr, reply_id=R1,
        response=rejected_answer, value=rejected_answer)
    assert partial.status_code == 200, partial.text
    assert partial.json()["status"] == "rejected_candidates", partial.text
    corrected = _mapping_answer(gap, assignment_id, "Amount")
    accepted = _reply(
        route_env, run_id, correlation=first_corr, reply_id=R2,
        response=corrected, value=corrected)
    assert accepted.status_code == 200, accepted.text

    # The adapter re-raised a second correlated question on the same step.
    detail = route_env["executor"].status(run_id)
    new_gap = next(
        item for item in detail["open_gaps"]
        if (item.get("waiting") or {}).get("correlation_id") == second_corr)
    receipts_before = copy.deepcopy(
        _step(route_env, run_id).get("reply_receipts") or [])

    reused = _reply(
        route_env, run_id, correlation=second_corr, reply_id=R1,
        response="a second answer", value="a second answer")
    assert reused.status_code == 409, reused.text
    assert "scope" in reused.text.lower() or "reply" in reused.text.lower()
    assert _question(route_env, run_id, new_gap["question_id"])["status"] == (
        "open")
    assert (_step(route_env, run_id).get("reply_receipts") or []) == (
        receipts_before)

    resolved = _reply(
        route_env, run_id, correlation=second_corr, reply_id=R4,
        response="a second answer", value="a second answer")
    assert resolved.status_code == 200, resolved.text
    assert _task(route_env, run_id)["assignment"]["status"] == "completed"
    final_receipts = _step(route_env, run_id).get("reply_receipts") or []
    assert [item.get("reply_id") for item in final_receipts] == [
        R1, R2, R4], final_receipts


def test_reraised_question_same_correlation_replays_without_settling(
        route_env, tmp_path):
    """A re-derived question keeps the old receipt authority for its scope."""
    correlation = "gap-reraise"
    re_raised = {
        "concept": "Price",
        "reason": "the price column needs confirmation again",
        "question": "Which column should supply Price again?",
        "kind": "missing_evidence",
        "inputs": {"mapping": {
            "concept": "Price", "missing_column": "Price",
            "sheet": "Records",
            "candidates": [{"column": "Amount"}],
        }},
        "waiting": {
            "state": "waiting_for_person", "party": "owner",
            "resume_on": "answer", "correlation_id": correlation,
            "detail": "price confirmation again",
        },
    }
    adapter, calls = _new_mapping_adapter(
        route_env, correlation=correlation, re_raise=re_raised)
    run_id, assignment_id, gap = _start(
        route_env, adapter_name=f"test.gap.reraise.{uuid.uuid4().hex[:8]}",
        adapter=adapter)
    corrected = _mapping_answer(gap, assignment_id, "Amount")
    accepted = _reply(
        route_env, run_id, correlation=correlation, reply_id=R2,
        response=corrected, value=corrected)
    assert accepted.status_code == 200, accepted.text
    assert calls["n"] == 2

    detail = route_env["executor"].status(run_id)
    new_gap = next(
        item for item in detail["open_gaps"]
        if item["question_id"] != gap["question_id"])
    receipts_before = copy.deepcopy(
        _step(route_env, run_id).get("reply_receipts") or [])
    version_before = _task(route_env, run_id)["task_version"]

    # Exact replay of R2 does NOT settle the re-raised question.
    replay = _reply(
        route_env, run_id, correlation=correlation, reply_id=R2,
        response=corrected, value=corrected)
    assert replay.status_code == 200, replay.text
    assert replay.json().get("status") == "already_applied", replay.text
    assert _question(route_env, run_id, new_gap["question_id"])["status"] == (
        "open")
    assert _task(route_env, run_id)["task_version"] == version_before
    assert (_step(route_env, run_id).get("reply_receipts") or []) == (
        receipts_before)

    # Changed material under the same identity still conflicts.
    changed = _reply(
        route_env, run_id, correlation=correlation, reply_id=R2,
        response="different answer", value="different answer")
    assert changed.status_code == 409, changed.text
    assert _question(route_env, run_id, new_gap["question_id"])["status"] == (
        "open")

    # A NEW identity can answer the re-raised question once.
    new_answer = _mapping_answer(new_gap, assignment_id, "Amount")
    resolved = _reply(
        route_env, run_id, correlation=correlation, reply_id=R3,
        response=new_answer, value=new_answer)
    assert resolved.status_code == 200, resolved.text
    assert _task(route_env, run_id)["assignment"]["status"] == "completed"
    final_receipts = _step(route_env, run_id).get("reply_receipts") or []
    assert [item.get("reply_id") for item in final_receipts] == [R2, R3]
    assert final_receipts[-1].get("outcome") == "resolved", final_receipts[-1]


def test_gap_cas_rechecks_identity_after_competing_writer(
        route_env, tmp_path, monkeypatch):
    """A competitor inserted before CAS makes the same-ID reply refuse."""
    correlation = "gap-cas"
    adapter, _calls = _new_mapping_adapter(
        route_env, correlation=correlation)
    run_id, assignment_id, gap = _start(
        route_env, adapter_name=f"test.gap.cas.{uuid.uuid4().hex[:8]}",
        adapter=adapter)
    lifecycle = route_env["lifecycle"]
    original = lifecycle.mutate_assignment_and_task
    injected = {"done": False}

    def wrapper(run_id_arg, compute, **kwargs):
        if not injected["done"] and run_id_arg == run_id:
            injected["done"] = True

            def competitor(record, current):
                plan = copy.deepcopy(current)
                step = next(
                    item for item in plan["steps"]
                    if item["step_id"] == "read")
                receipts = list(step.get("reply_receipts") or [])
                receipts.append({
                    "reply_id": R1,
                    "identity_kind": "explicit",
                    "material_sha256": "0" * 64,
                    "correlation_id": correlation,
                    "fact": "Price",
                    "subject": "",
                    "outcome": "rejected_candidates",
                    "reason": "candidates_rejected",
                    "message": "competing writer won",
                    "at": "2026-11-08T00:00:00+00:00",
                })
                step["reply_receipts"] = receipts
                return plan, {}

            lifecycle.mutate_assignment(
                run_id, competitor, rationale="test: competitor")
        return original(run_id_arg, compute, **kwargs)

    monkeypatch.setattr(
        lifecycle, "mutate_assignment_and_task", wrapper)
    corrected = _mapping_answer(gap, assignment_id, "Amount")
    result = route_env["executor"].record_external_response(
        run_id, correlation, response=corrected, source=SOURCE,
        evidence=EVIDENCE, value=corrected, reply_id=R1)
    assert result.get("status") == "reply_conflict", result
    assert _question(route_env, run_id, gap["question_id"])["status"] == "open"
    receipts = _step(route_env, run_id).get("reply_receipts") or []
    assert len(receipts) == 1, receipts
    assert receipts[0]["material_sha256"] == "0" * 64, receipts[0]
    assert _wakes(route_env, run_id) == 0


def test_direct_gap_resolution_matches_literal_bracket_not_audit_prefix():
    """A literal bracket answer is not the same as an appended audit suffix."""
    literal = "price 100 [subject to approval]"
    assert not resolution_matches(literal, "price 100", literal)
    assert resolution_matches(literal, literal, literal)
    # Legacy records with only a truncated audit string fail closed on prefix.
    assert not resolution_matches(
        "price 100 [by owner]", "price 100", None)
    assert resolution_matches(
        "price 100 [by owner]", "price 100", "price 100")


def test_direct_gap_route_preserves_exact_human_answer_replay(route_env):
    """POST /gaps stays compatible: same exact text replays, a prefix fails."""
    correlation = "direct-gap"
    adapter, _calls = _new_text_adapter(
        route_env, correlation=correlation)
    run_id, _assignment_id, gap = _start(
        route_env, adapter_name=f"test.gap.direct.{uuid.uuid4().hex[:8]}",
        adapter=adapter)
    literal = "price 100 [subject to approval]"
    resolved = route_env["client"].post(
        f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
        json={"resolution": literal, "resolved_by": "owner"})
    assert resolved.status_code == 200, resolved.text

    prefix = route_env["client"].post(
        f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
        json={"resolution": "price 100"})
    assert prefix.status_code == 409, prefix.text
    assert "different answer" in prefix.text.lower()

    replay = route_env["client"].post(
        f"/api/assignments/{run_id}/gaps/{gap['question_id']}/resolve",
        json={"resolution": literal})
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "already_resolved", replay.text
