"""Repeated external reply identity for a durable assignment wait.

A typed external reply is not just a value: it is an identity plus material.
Once a reply identity has been used on a durable wait, the same identity may
replay exactly the same material, but it may never change that material and
resolve the wait. A new identity may still supply the accepted answer.

Public control: open the real typed ``received_quantity`` wait through the
existing employee/durable-wait fixture, submit a non-resolving conflict under
``reply_id=r1``, then submit changed material under the SAME ``r1``. The
result must be an exact material conflict (typed 409 or an explicit refusal),
the wait remains unresolved, and no dependent reconciliation or artifact
appears.

This file is authored for root execution. No test here is claimed as passing.
"""
from __future__ import annotations

import copy

import pytest

from tests.test_assignment_routes import route_env  # noqa: F401
from tests.test_employee_durable_wait_g5 import _start, _wait_step

R1 = "reply-r1"
R2 = "reply-r2"
R3 = "reply-r3"
REPLY_SOURCE = "warehouse receiving"


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


def _open_wait(route_env, tmp_path, monkeypatch, *, requested_output=None):
    """Open the real typed received_quantity wait and add its record."""
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ATOM_ASSIGNMENT_OUTPUT_DIR", str(artifact_root))
    run_id = _start(
        route_env, tmp_path, monkeypatch, requested_output=requested_output,
        budget={"max_steps": 20})
    assignment = route_env["lifecycle"].get_assignment(run_id)
    wait = _wait_step(assignment)
    assert wait["status"] == "waiting", wait
    assert wait["waiting"]["fact"] == "received_quantity", wait["waiting"]
    assert wait["waiting"]["typed_binding"] is True, wait["waiting"]
    correlation = wait["waiting"]["correlation_id"]
    # The authorized receiving record establishes the source fact. The later
    # reply must still carry a reply identity; adding the source must not
    # silently complete the wait.
    receiving = tmp_path / "receiving.json"
    added = route_env["client"].post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(receiving)},
              "reason": "warehouse supplied the authorized receiving record"})
    assert added.status_code == 200, added.text
    return run_id, correlation, artifact_root


def _reply(route_env, run_id, correlation, *, reply_id, value, response,
           source=REPLY_SOURCE, evidence=""):
    return route_env["client"].post(
        f"/api/assignments/{run_id}/responses/{correlation}",
        json={
            "reply_id": reply_id,
            "response": response,
            "source": source,
            "evidence": evidence,
            "value": value,
        })


def _wait(route_env, run_id):
    return _wait_step(route_env["lifecycle"].get_assignment(run_id))


def _applied(assignment, prefix):
    return [
        step for step in assignment["steps"]
        if step["adapter"].startswith(prefix)
        and step["status"] == "applied"
    ]


def _assert_wait_and_no_dependent_work(route_env, run_id, artifact_root):
    assignment = route_env["lifecycle"].get_assignment(run_id)
    assert assignment["status"] == "waiting", assignment["status"]
    assert _wait(route_env, run_id)["status"] == "waiting"
    assert _applied(assignment, "invoice.reconcile") == []
    assert _applied(assignment, "artifact.") == []
    assert not any(path.is_file() for path in artifact_root.rglob("*"))
    return assignment


def _assert_reply_identity_conflict(response):
    """Accept a typed 409 or an explicit, identity-specific refusal."""
    if response.status_code == 409:
        text = response.text.lower()
        assert "reply" in text or "material" in text, response.text
        return
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") in (
        "conflict", "refused", "reply_conflict"), body
    reason = str(
        (body.get("conflict") or {}).get("reason")
        or body.get("reason") or "")
    assert (
        "reply_id" in reason
        or "reply_identity" in reason
        or "material" in reason), body
    assert body.get("status") != "resumed", body


def _assert_refused(response):
    """A terminal/new-identity refusal is not an exact replay."""
    assert response.status_code in (200, 409), response.text
    body = response.json()
    assert body.get("status") != "already_applied", body
    if response.status_code == 409:
        return
    assert body.get("status") in (
        "terminal", "conflict", "refused", "reply_conflict"), body


def test_changed_material_under_same_reply_identity_stays_unresolved(
        route_env, tmp_path, monkeypatch):
    """The public failure-first control for the missing reply identity."""
    run_id, correlation, artifact_root = _open_wait(
        route_env, tmp_path, monkeypatch, requested_output="document")
    assignment = _assert_wait_and_no_dependent_work(
        route_env, run_id, artifact_root)
    quote_before = next(
        step for step in assignment["steps"]
        if step["adapter"] == "quote.calculate"
        and step["status"] == "applied")

    first = _reply(
        route_env, run_id, correlation, reply_id=R1,
        value="5.0", response="received 5 units")
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "conflict", first.text
    after_first = _assert_wait_and_no_dependent_work(
        route_env, run_id, artifact_root)
    wait_after_first = _wait_step(after_first)
    receipts = wait_after_first.get("reply_receipts") or []
    assert [item.get("reply_id") for item in receipts] == [R1], receipts
    assert receipts[0].get("material_sha256"), receipts[0]
    assert len(receipts[0]["material_sha256"]) == 64, receipts[0]
    conflicts = wait_after_first["waiting"].get("conflicts") or []
    assert conflicts[-1].get("reply_id") == R1, conflicts[-1]
    assert conflicts[-1].get("material_sha256") == (
        receipts[0]["material_sha256"]), conflicts[-1]

    # Same identity, changed valid material: this is the exact conflict the
    # current route cannot express. It must not resolve the wait.
    changed = _reply(
        route_env, run_id, correlation, reply_id=R1,
        value="2", response="received 2 units")
    _assert_reply_identity_conflict(changed)

    after_changed = _assert_wait_and_no_dependent_work(
        route_env, run_id, artifact_root)
    wait_after_changed = _wait_step(after_changed)
    assert wait_after_changed.get("reply_receipts") == receipts
    # Useful independent work is retained, not recomputed by the refusal.
    quote_after = next(
        step for step in after_changed["steps"]
        if step["step_id"] == quote_before["step_id"])
    assert quote_after["operation_id"] == quote_before["operation_id"]
    assert quote_after["result"]["value"] == quote_before["result"]["value"]

    # Durable fresh-session readback: r1 is still one conflict receipt and the
    # wait is still live after an executor rebuild.
    durable = _rebuilt_executor(route_env).lifecycle.get_assignment(run_id)
    durable_wait = _wait_step(durable)
    assert durable_wait["status"] == "waiting"
    durable_receipts = durable_wait.get("reply_receipts") or []
    assert [item.get("reply_id") for item in durable_receipts] == [R1]
    assert durable_receipts[0]["material_sha256"] == (
        receipts[0]["material_sha256"])
    assert durable_receipts[0].get("outcome") == "conflict"


def test_same_reply_identity_same_material_is_idempotent(
        route_env, tmp_path, monkeypatch):
    """Same r1/same material replays the result without another event.

    The second replay uses a canonically equal typed value (``5.0`` -> ``5``)
    so receipt material canonicalization is part of the contract.
    """
    run_id, correlation, artifact_root = _open_wait(
        route_env, tmp_path, monkeypatch, requested_output="document")
    first = _reply(
        route_env, run_id, correlation, reply_id=R1,
        value="5.0", response="received 5 units")
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "conflict", first.text

    wait_before = _wait(route_env, run_id)
    receipts_before = copy.deepcopy(wait_before.get("reply_receipts") or [])
    conflicts_before = copy.deepcopy(
        wait_before["waiting"].get("conflicts") or [])
    decisions_before = len(
        route_env["lifecycle"].runs.get_decisions(run_id))

    for value in ("5.0", "5"):
        replay = _reply(
            route_env, run_id, correlation, reply_id=R1,
            value=value, response="received 5 units")
        assert replay.status_code == 200, replay.text
        assert replay.json()["status"] == "conflict", replay.text
        wait_now = _wait(route_env, run_id)
        assert (wait_now.get("reply_receipts") or []) == receipts_before
        assert wait_now["waiting"].get("conflicts") == conflicts_before
        assert len(route_env["lifecycle"].runs.get_decisions(run_id)) == (
            decisions_before)
        _assert_wait_and_no_dependent_work(
            route_env, run_id, artifact_root)


def test_new_reply_identity_resumes_same_job_once(
        route_env, tmp_path, monkeypatch):
    """r2 may answer, but a late r3 is not an exact replay."""
    run_id, correlation, artifact_root = _open_wait(
        route_env, tmp_path, monkeypatch, requested_output="document")
    initial = _assert_wait_and_no_dependent_work(
        route_env, run_id, artifact_root)
    assignment_id = initial["assignment_id"]

    first = _reply(
        route_env, run_id, correlation, reply_id=R1,
        value="5.0", response="received 5 units")
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "conflict", first.text
    _assert_wait_and_no_dependent_work(route_env, run_id, artifact_root)

    accepted = _reply(
        route_env, run_id, correlation, reply_id=R2,
        value="2", response="received 2 units")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json().get("status") not in (
        "conflict", "terminal", "refused", "already_applied"), accepted.json()

    final = route_env["lifecycle"].get_assignment(run_id)
    assert final["status"] == "completed", final["status"]
    assert final["assignment_id"] == assignment_id
    assert len(_applied(final, "invoice.reconcile")) == 1
    assert len(_applied(final, "artifact.")) == 1
    final_wait = _wait_step(final)
    assert final_wait["status"] == "applied"
    receipts = final_wait.get("reply_receipts") or []
    assert [item.get("reply_id") for item in receipts] == [R1, R2], receipts
    assert receipts[-1].get("outcome") == "resolved", receipts[-1]
    external = final_wait.get("external_response") or {}
    assert external.get("reply_id") == R2, external
    assert external.get("material_sha256") == (
        receipts[-1]["material_sha256"]), external

    # Exact replay of r2 is idempotent and adds no second effect.
    duplicate = _reply(
        route_env, run_id, correlation, reply_id=R2,
        value="2", response="received 2 units")
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json().get("status") == "already_applied", duplicate.text
    settled = route_env["lifecycle"].get_assignment(run_id)
    assert len(_applied(settled, "invoice.reconcile")) == 1
    assert len(_applied(settled, "artifact.")) == 1

    # A new identity with changed material after completion is NOT an exact
    # replay of r2 and must not be acknowledged as already applied.
    late = _reply(
        route_env, run_id, correlation, reply_id=R3,
        value="9", response="received 9 units")
    _assert_refused(late)
    after_late = route_env["lifecycle"].get_assignment(run_id)
    assert after_late["status"] == "completed"
    assert len(_applied(after_late, "invoice.reconcile")) == 1
    assert len(_applied(after_late, "artifact.")) == 1
    assert [item.get("reply_id") for item in
            _wait_step(after_late).get("reply_receipts") or []] == [R1, R2]


def test_cancel_and_foreign_workspace_refuse_reply_identity(
        route_env, tmp_path, monkeypatch):
    """Authority is checked before identity; cancellation is terminal."""
    run_id, correlation, artifact_root = _open_wait(
        route_env, tmp_path, monkeypatch)
    _assert_wait_and_no_dependent_work(route_env, run_id, artifact_root)

    route_env["current"]["user"] = route_env["users"]["other"]
    foreign = _reply(
        route_env, run_id, correlation, reply_id=R2,
        value="2", response="received 2 units")
    assert foreign.status_code == 404, foreign.text
    route_env["current"]["user"] = route_env["users"]["lead"]

    after_foreign = _assert_wait_and_no_dependent_work(
        route_env, run_id, artifact_root)
    foreign_wait = _wait_step(after_foreign)
    assert not (foreign_wait.get("reply_receipts") or [])
    assert not (foreign_wait["waiting"].get("conflicts") or [])

    cancelled = route_env["client"].post(
        f"/api/assignments/{run_id}/cancel",
        json={"reason": "owner cancelled while waiting for receiving"})
    assert cancelled.status_code == 200, cancelled.text
    late = _reply(
        route_env, run_id, correlation, reply_id=R1,
        value="2", response="received 2 units")
    assert late.status_code == 409, late.text

    final = route_env["lifecycle"].get_assignment(run_id)
    assert final["status"] == "cancelled"
    assert _wait_step(final)["status"] == "cancelled"
    assert _applied(final, "invoice.reconcile") == []
    assert _applied(final, "artifact.") == []

    durable = _rebuilt_executor(route_env).lifecycle.get_assignment(run_id)
    assert durable["status"] == "cancelled"
    assert _wait_step(durable)["status"] == "cancelled"


@pytest.mark.parametrize("field,changed", [
    ("response", {"value": "5", "response": "received five units",
                  "evidence": "mail-1"}),
    ("source", {"value": "5", "response": "received 5 units",
                "source": "warehouse receiving desk",
                "evidence": "mail-1"}),
    ("evidence", {"value": "5", "response": "received 5 units",
                  "evidence": "mail-2"}),
    ("value", {"value": "2", "response": "received 5 units",
               "evidence": "mail-1"}),
])
def test_same_identity_refuses_each_changed_material_field(
        route_env, tmp_path, monkeypatch, field, changed):
    """Every semantic field is part of the exact material identity."""
    run_id, correlation, artifact_root = _open_wait(
        route_env, tmp_path, monkeypatch)
    first = _reply(
        route_env, run_id, correlation, reply_id=R1,
        value="5", response="received 5 units", evidence="mail-1")
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "conflict", first.text
    wait_before = _wait(route_env, run_id)
    receipts_before = copy.deepcopy(wait_before.get("reply_receipts") or [])

    refused = _reply(
        route_env, run_id, correlation, reply_id=R1, **changed)
    _assert_reply_identity_conflict(refused)
    after = _assert_wait_and_no_dependent_work(
        route_env, run_id, artifact_root)
    assert _wait_step(after).get("reply_receipts") == receipts_before


@pytest.mark.parametrize("first_id,second_id", [
    ("Reply-R1", "reply-r1"),
    (" reply-r1", "reply-r1"),
    ("re\u0301ply-r1", "r\u00e9ply-r1"),
])
def test_opaque_reply_ids_are_exact_not_normalized(
        route_env, tmp_path, monkeypatch, first_id, second_id):
    """Opaque IDs are compared exactly; case, space and Unicode stay distinct."""
    run_id, correlation, artifact_root = _open_wait(
        route_env, tmp_path, monkeypatch, requested_output="document")
    first = _reply(
        route_env, run_id, correlation, reply_id=first_id,
        value="5", response="received 5 units")
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "conflict", first.text

    second = _reply(
        route_env, run_id, correlation, reply_id=second_id,
        value="2", response="received 2 units")
    assert second.status_code == 200, second.text
    assert second.json().get("status") not in (
        "reply_conflict", "conflict", "terminal", "refused"), second.json()
    final = route_env["lifecycle"].get_assignment(run_id)
    assert final["status"] == "completed", final["status"]
    receipts = _wait_step(final).get("reply_receipts") or []
    assert [item.get("reply_id") for item in receipts] == [
        first_id, second_id], receipts
    assert all(item.get("identity_kind") == "explicit" for item in receipts)


def test_omitted_reply_id_partial_then_corrected_full(
        route_env, tmp_path, monkeypatch):
    """Legacy omitted IDs replay only identical material and remain usable."""
    run_id, correlation, artifact_root = _open_wait(
        route_env, tmp_path, monkeypatch, requested_output="document")
    first = _reply(
        route_env, run_id, correlation, reply_id=None,
        value="5", response="received 5 units")
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "conflict", first.text
    wait_before = _wait(route_env, run_id)
    receipts_before = copy.deepcopy(wait_before.get("reply_receipts") or [])
    conflicts_before = copy.deepcopy(
        wait_before["waiting"].get("conflicts") or [])
    decisions_before = len(
        route_env["lifecycle"].runs.get_decisions(run_id))

    replay = _reply(
        route_env, run_id, correlation, reply_id=None,
        value="5", response="received 5 units")
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "conflict", replay.text
    wait_now = _wait(route_env, run_id)
    assert (wait_now.get("reply_receipts") or []) == receipts_before
    assert wait_now["waiting"].get("conflicts") == conflicts_before
    assert len(route_env["lifecycle"].runs.get_decisions(run_id)) == (
        decisions_before)

    corrected = _reply(
        route_env, run_id, correlation, reply_id=None,
        value="2", response="received 2 units")
    assert corrected.status_code == 200, corrected.text
    assert corrected.json().get("status") not in (
        "conflict", "reply_conflict", "terminal", "refused"), corrected.json()
    final = route_env["lifecycle"].get_assignment(run_id)
    assert final["status"] == "completed", final["status"]
    receipts = _wait_step(final).get("reply_receipts") or []
    assert [item.get("identity_kind") for item in receipts] == [
        "legacy", "legacy"], receipts
    assert [item.get("outcome") for item in receipts] == [
        "conflict", "resolved"], receipts
    assert all(item.get("reply_id") == "" for item in receipts)


def test_old_identity_survives_more_than_ten_display_entries(
        route_env, tmp_path, monkeypatch):
    """Display bounding never evicts an authoritative identity receipt."""
    run_id, correlation, artifact_root = _open_wait(
        route_env, tmp_path, monkeypatch)
    for index in range(12):
        value = str(5 + index)
        reply = _reply(
            route_env, run_id, correlation, reply_id=f"bulk-{index:02d}",
            value=value, response=f"received {value} units")
        assert reply.status_code == 200, reply.text
        assert reply.json()["status"] == "conflict", reply.text

    wait = _wait(route_env, run_id)
    assert len(wait.get("reply_receipts") or []) == 12
    assert len(wait["waiting"].get("conflicts") or []) == 10
    old_receipt = wait["reply_receipts"][0]
    old_digest = old_receipt["material_sha256"]

    replay = _reply(
        route_env, run_id, correlation, reply_id="bulk-00",
        value="5", response="received 5 units")
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "conflict", replay.text
    after_replay = _wait(route_env, run_id)
    assert len(after_replay.get("reply_receipts") or []) == 12
    assert after_replay["reply_receipts"][0]["material_sha256"] == old_digest
    assert len(after_replay["waiting"].get("conflicts") or []) == 10

    changed = _reply(
        route_env, run_id, correlation, reply_id="bulk-00",
        value="2", response="received 2 units")
    _assert_reply_identity_conflict(changed)
    _assert_wait_and_no_dependent_work(route_env, run_id, artifact_root)

    durable = _rebuilt_executor(route_env).lifecycle.get_assignment(run_id)
    durable_wait = _wait_step(durable)
    assert len(durable_wait.get("reply_receipts") or []) == 12
    assert durable_wait["reply_receipts"][0]["material_sha256"] == old_digest
    assert len(durable_wait["waiting"].get("conflicts") or []) == 10


def test_stale_wait_scope_refuses_same_identity(
        route_env, tmp_path, monkeypatch):
    """A changed wait subject is a scope conflict, not a fresh reply."""
    run_id, correlation, artifact_root = _open_wait(
        route_env, tmp_path, monkeypatch)
    first = _reply(
        route_env, run_id, correlation, reply_id=R1,
        value="5", response="received 5 units")
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "conflict", first.text
    wait_before = _wait(route_env, run_id)
    receipts_before = copy.deepcopy(wait_before.get("reply_receipts") or [])

    def change_scope(record, current):
        plan = copy.deepcopy(current)
        wait = _wait_step(plan)
        wait["waiting"]["subject"] = "PO-OTHER-9"
        return plan, {}

    route_env["lifecycle"].mutate_assignment(
        run_id, change_scope, rationale="test: stale wait scope")

    replay = _reply(
        route_env, run_id, correlation, reply_id=R1,
        value="5", response="received 5 units")
    _assert_reply_identity_conflict(replay)
    after = _assert_wait_and_no_dependent_work(
        route_env, run_id, artifact_root)
    assert _wait_step(after).get("reply_receipts") == receipts_before


def test_cas_rechecks_identity_after_competing_writer(
        route_env, tmp_path, monkeypatch):
    """A competitor inserted before CAS makes the same-ID reply refuse."""
    run_id, correlation, artifact_root = _open_wait(
        route_env, tmp_path, monkeypatch)
    executor = route_env["executor"]
    lifecycle = route_env["lifecycle"]
    original = lifecycle.mutate_assignment_and_task
    injected = {"done": False}

    def wrapper(run_id_arg, compute, **kwargs):
        if not injected["done"] and run_id_arg == run_id:
            injected["done"] = True

            def competitor(record, current):
                plan = copy.deepcopy(current)
                wait = _wait_step(plan)
                receipts = list(wait.get("reply_receipts") or [])
                receipts.append({
                    "reply_id": R1,
                    "identity_kind": "explicit",
                    "material_sha256": "0" * 64,
                    "correlation_id": correlation,
                    "fact": wait["waiting"]["fact"],
                    "subject": wait["waiting"]["subject"],
                    "outcome": "conflict",
                    "reason": "source_fact_conflict",
                    "message": "competing writer won",
                    "at": "2026-11-08T00:00:00+00:00",
                })
                wait["reply_receipts"] = receipts
                waiting_now = dict(wait.get("waiting") or {})
                conflicts = list(waiting_now.get("conflicts") or [])
                conflicts.append({
                    "correlation_id": correlation,
                    "fact": wait["waiting"]["fact"],
                    "subject": wait["waiting"]["subject"],
                    "reason": "source_fact_conflict",
                    "reply_id": R1,
                    "material_sha256": "0" * 64,
                })
                waiting_now["conflicts"] = conflicts[-10:]
                wait["waiting"] = waiting_now
                return plan, {}

            original(run_id, competitor, rationale="test: competitor")
        return original(run_id_arg, compute, **kwargs)

    monkeypatch.setattr(lifecycle, "mutate_assignment_and_task", wrapper)
    result = executor.record_external_response(
        run_id, correlation, response="received 2 units",
        source=REPLY_SOURCE, value="2", reply_id=R1)
    assert injected["done"] is True, "competitor must run at the actual CAS entry"
    assert result.get("status") == "reply_conflict", result
    wait_after = _wait(route_env, run_id)
    assert wait_after["status"] == "waiting"
    assert len(wait_after.get("reply_receipts") or []) == 1
    assert wait_after["reply_receipts"][0]["material_sha256"] == "0" * 64
