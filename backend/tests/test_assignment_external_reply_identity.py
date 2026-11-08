"""Repeated external reply identity for a durable assignment wait.

A typed external reply is not just a value: it is an identity plus material.
Once a reply identity has been used on a durable wait, the same identity may
replay exactly the same material, but it may never change that material and
resolve the wait. A new identity may still supply the accepted answer.

Failure-first public control: open the real typed ``received_quantity`` wait
through the existing employee/durable-wait fixture, submit a non-resolving
conflict under ``reply_id=r1``, then submit changed material under the SAME
``r1``. The desired result is an exact material conflict (typed 409 or an
explicit refusal), the wait remains unresolved, and no dependent
reconciliation or artifact appears. Current production likely drops the extra
``reply_id`` and resolves the wait; this test is authored, not run.

Author-only. Only this file and LEAD_REVIEW.md are in scope. No production
edits and no claim that these tests pass.
"""
from __future__ import annotations

import copy

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
           source=REPLY_SOURCE):
    return route_env["client"].post(
        f"/api/assignments/{run_id}/responses/{correlation}",
        json={
            "reply_id": reply_id,
            "response": response,
            "source": source,
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
