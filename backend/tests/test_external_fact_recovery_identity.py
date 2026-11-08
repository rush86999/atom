"""New accepted external facts must not inherit an earlier retain marker."""
import copy

import pytest

from tests.test_assignment_routes import route_env  # noqa: F401
from tests.test_assignment_external_reply_identity import _open_wait, REPLY_SOURCE


def test_accepted_external_fact_rearms_recovery(route_env, tmp_path, monkeypatch):
    import core.employee_job_runner as jobs
    run_id, correlation, _ = _open_wait(route_env, tmp_path, monkeypatch)
    executor = route_env["executor"]
    monkeypatch.setattr(jobs, "evidence_observations", lambda record: [
        {"observation_id": "retained-source-observation"}])
    before = executor.lifecycle.get_task(run_id)
    old = executor._unconsumed_evidence_key(before)
    assert old is not None
    claim = executor._claim_evidence_recovery(run_id, old["key"])
    assert claim is not None
    executor._finish_evidence_recovery(
        run_id, old["key"], "attempted", claim_token=claim["claim_token"])
    assert executor._evidence_recovery_plan(executor.lifecycle.get_task(run_id)) is None
    result = executor.record_external_response(
        run_id, correlation, response="received 2 units", source=REPLY_SOURCE,
        value="2", reply_id="new-authorized-reply")
    assert result["status"] == "resumed", result
    after = executor.lifecycle.get_task(run_id)
    plan = executor._evidence_recovery_plan(after)
    assert plan is not None, "accepted external fact inherited the pre-answer retain marker"
    assert plan["key"] != old["key"]

    claim = executor._claim_evidence_recovery(run_id, plan["key"])
    assert claim is not None
    executor._finish_evidence_recovery(
        run_id, plan["key"], "attempted", claim_token=claim["claim_token"])
    replay = executor.record_external_response(
        run_id, correlation, response="received 2 units", source=REPLY_SOURCE,
        value="2", reply_id="new-authorized-reply")
    assert replay.get("replayed") is True
    from tests.test_assignment_external_reply_identity import _rebuilt_executor
    fresh = _rebuilt_executor(route_env)
    assert fresh._evidence_recovery_plan(fresh.lifecycle.get_task(run_id)) is None


@pytest.mark.parametrize("case,accepted", [
    ("explicit", True), ("legacy", True), ("pending", False),
    ("conflict", False), ("missing_receipt", False),
    ("wrong_reply", False), ("wrong_correlation", False),
    ("wrong_digest", False), ("wrong_kind", False),
])
def test_recovery_key_requires_exact_resolved_receipt(monkeypatch, case, accepted):
    import core.employee_job_runner as jobs
    from core.assignment_executor import AssignmentExecutor
    monkeypatch.setattr(jobs, "evidence_observations", lambda record: [
        {"observation_id": "source-observation"}])
    executor = object.__new__(AssignmentExecutor)
    record = {"task_revision": {"authorization": "authorized", "unresolved": []},
              "assignment": {"status": "waiting", "provenance": {
                  "started_from": "employee_objective", "use_model": True},
                  "steps": []}}
    old = executor._unconsumed_evidence_key(record)["key"]
    identity = {"correlation_id": "opaque-correlation", "reply_id": "opaque-reply",
                "identity_kind": "explicit", "material_sha256": "a" * 64}
    if case == "legacy":
        identity.update(reply_id="", identity_kind="legacy")
    receipt = {**identity, "outcome": "resolved"}
    if case in ("pending", "conflict"):
        receipt["outcome"] = case
    elif case.startswith("wrong_"):
        field = {"wrong_reply": "reply_id", "wrong_correlation": "correlation_id",
                 "wrong_digest": "material_sha256", "wrong_kind": "identity_kind"}[case]
        receipt[field] = "different-material"
    step = {"step_id": "wait-step", "external_response": identity,
            "reply_receipts": [] if case == "missing_receipt" else [receipt]}
    record["assignment"]["steps"] = [step]
    before = copy.deepcopy(record)
    key = executor._unconsumed_evidence_key(record)["key"]
    assert (key != old) is accepted
    assert executor._unconsumed_evidence_key(record)["key"] == key
    assert record == before


def test_external_fact_recovery_runs_existing_adaptation_once(
        route_env, tmp_path, monkeypatch):
    """Real receipt/recovery/compiler/executor join; only proposal transport is controlled."""
    import asyncio
    import api.assignment_routes as routes
    from tests.test_assignment_external_reply_identity import _rebuilt_executor

    run_id, correlation, _ = _open_wait(route_env, tmp_path, monkeypatch)
    executor = route_env["executor"]
    before = executor.lifecycle.get_task(run_id)
    quote = next(step for step in before["assignment"]["steps"]
                 if step["adapter"] == "quote.calculate")
    old = executor._evidence_recovery_plan(before)
    assert old is not None
    claim = executor._claim_evidence_recovery(run_id, old["key"])
    assert claim is not None
    executor._finish_evidence_recovery(
        run_id, old["key"], "attempted", claim_token=claim["claim_token"])
    accepted = executor.record_external_response(
        run_id, correlation, response="received 2 units", source=REPLY_SOURCE,
        value="2", reply_id="accepted-recovery-reply")
    assert accepted["status"] == "resumed"
    proposal = routes.propose_adaptation
    calls = []

    async def counted_proposal(*args, **kwargs):
        calls.append(run_id)
        return await proposal(*args, **kwargs)

    monkeypatch.setattr(routes, "propose_adaptation", counted_proposal)
    monkeypatch.setattr(routes, "_employee_llm_for_scope", lambda *_: object())
    fresh = _rebuilt_executor(route_env)
    recovered = asyncio.run(fresh._recover_accepted_evidence(run_id))
    assert recovered["status"] == "completed", recovered
    assert calls == [run_id]
    final = fresh.lifecycle.get_task(run_id)
    assert final["assignment"]["status"] == "completed"
    reconciliation = next(step for step in final["assignment"]["steps"]
                          if step["adapter"] == "invoice.reconcile")
    assert reconciliation["status"] == "applied"
    assert reconciliation["result"]["value"] == "270.00"
    retained_quote = next(step for step in final["assignment"]["steps"]
                          if step["step_id"] == quote["step_id"])
    assert retained_quote["operation_id"] == quote["operation_id"]
    assert retained_quote["result"] == quote["result"]
    again = _rebuilt_executor(route_env)
    assert asyncio.run(again._recover_accepted_evidence(run_id)) is None
    assert calls == [run_id]
    assert again.lifecycle.get_task(run_id) == final
