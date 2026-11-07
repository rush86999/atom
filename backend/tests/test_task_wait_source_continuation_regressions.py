"""TASK-WAIT-01 regressions for source-triggered same-task continuation.

The failure-first contract lives in
``test_task_wait_source_trigger_contract.py``. These cases lock the surrounding
boundaries: unrelated/wrong/partial sources stay unresolved, a replay after a
durable-acceptance interruption recovers through the existing consumer without
repeating applied work, and explicit ``use_model=false`` / cancellation /
absolute-deadline boundaries stay terminal.

All transport is controlled through the existing proposal monkeypatches; no
provider, spend, account, send or deployment action occurs. Public assignment
routes, the real compiler/executor and scratch durable records are exercised.
"""
import asyncio
import json

import pytest

from tests.test_assignment_routes import route_env  # noqa: F401
from core.assignment_plan import (
    new_assignment,
    new_step,
    new_teaching_snapshot,
)
from core.employee_adaptation import WorkAdaptationProposal
from core.employee_work_requests import InvoiceReconciliationRequest
from core.task_lifecycle import (
    add_unresolved_questions,
    open_unresolved_questions,
    resolve_unresolved_questions,
)

PO = "PO-TRIGGER-63"
INVOICE = "INV-TRIGGER-91"
EXPECTED_TOTAL = "140.25"


def _write_facts(tmp_path, *, invoice_overrides=None, omit=()):
    facts = {
        "po.json": {
            "po_id": PO, "vendor_id": "V-6", "quantity": "3",
            "unit_price": "42.50", "freight": "12.75", "currency": "USD",
        },
        "receiving.json": {"po_id": PO, "received_quantity": "3"},
        "invoice.json": {
            "po_id": PO, "invoice_id": INVOICE, "quantity": "3",
            "unit_price": "42.50", "freight": "12.75", "currency": "USD",
        },
    }
    if invoice_overrides:
        facts["invoice.json"].update(invoice_overrides)
    for name, value in facts.items():
        if name in omit:
            continue
        (tmp_path / name).write_text(json.dumps(value))
    return facts


def _install_controlled_transport(monkeypatch, calls):
    async def discovery(context, **kwargs):
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read authorized procurement records",
                "evidence_reads": [
                    {"step_id": f"evidence-{i}", "title": "Read source",
                     "source_id": source["source_id"]}
                    for i, source in enumerate(context["sources"], 1)
                ],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    async def adaptation(context, observations, **kwargs):
        roles = {
            str(item.get("business_role") or ""): item["step_id"]
            for item in context.get("evidence_results", [])
            if item.get("business_role")
        }
        calls.append(dict(roles))
        common = {
            "reason": "select supported work from accepted records",
            "observation_ids": [
                item["observation_id"] for item in observations],
        }
        if all(roles.get(key) for key in (
                "invoice", "purchase_order", "receiving")):
            proposal = WorkAdaptationProposal(
                decision="replan",
                work_request=InvoiceReconciliationRequest(
                    operation="invoice_reconciliation",
                    invoice_step_id=roles["invoice"],
                    purchase_order_step_id=roles["purchase_order"],
                    receiving_step_id=roles["receiving"],
                ),
                **common,
            )
        else:
            proposal = WorkAdaptationProposal(
                decision="clarify",
                clarification={
                    "question": (
                        f"Which authorized source contains invoice {INVOICE} "
                        f"for purchase order {PO}?"),
                    "concept": "invoice_reconciliation",
                    "unblocks": "invoice reconciliation",
                },
                **common,
            )
        return {
            "proposal": proposal.model_dump(),
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr("api.assignment_routes.propose_employee_work", discovery)
    monkeypatch.setattr("api.assignment_routes.propose_adaptation", adaptation)
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm", lambda *a, **k: object())
    return calls


def _start_missing_invoice(client, tmp_path):
    answer = client.post(
        "/api/assignments/from-objective",
        json={
            "objective": f"Reconcile invoice {INVOICE} for {PO}",
            "sources": [
                {"path": str(tmp_path / "po.json")},
                {"path": str(tmp_path / "receiving.json")},
            ],
            "authorized_actions": ["retrieve", "calculate"],
            "use_model": True,
        },
    )
    assert answer.status_code == 200, answer.text
    return answer.json()["run_id"]


def _add_invoice(client, run_id, tmp_path, name="invoice.json"):
    return client.post(
        f"/api/assignments/{run_id}/sources",
        json={
            "source": {"path": str(tmp_path / name)},
            "reason": "authorized source answers the invoice question",
        },
    )


def _reconciliations(lifecycle, run_id):
    return [
        step for step in lifecycle.get_assignment(run_id)["steps"]
        if step["adapter"] == "invoice.reconcile" and step["status"] == "applied"
    ]


def _rebuilt_executor(route_env):
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


def test_source_acceptance_survives_interruption_and_replay_recovers(
        route_env, tmp_path, monkeypatch):
    """Durable source acceptance is not stranded by a crash before adaptation.

    Order A is covered by rebuilding the executor while waiting before the
    answer arrives. Order B accepts the source durably, interrupts before
    adaptation, rebuilds from the DB, then replays the same source. The replay
    must run the same consumer once and must not repeat the applied operation.
    """
    import api.assignment_routes as assignment_routes

    _write_facts(tmp_path)
    calls = _install_controlled_transport(monkeypatch, calls=[])
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]
    run_id = _start_missing_invoice(client, tmp_path)

    # Order A: a real executor rebuild sees the durable waiting state.
    rebuilt = _rebuilt_executor(route_env)
    waiting = rebuilt.lifecycle.get_task(run_id)
    assert waiting is not None
    assert open_unresolved_questions(waiting), (
        "the objective must genuinely wait for the invoice before answering")

    real_advance = assignment_routes._advance_employee_work

    async def interrupted(*args, **kwargs):
        raise RuntimeError("simulated interruption before adaptation")

    monkeypatch.setattr(
        "api.assignment_routes._advance_employee_work", interrupted)
    first = _add_invoice(client, run_id, tmp_path)
    assert first.status_code == 200, first.text
    accepted = first.json()
    assert accepted["resolved_question_ids"], accepted
    assert accepted["continuation_rounds"], accepted
    assert accepted["continuation_rounds"][0]["decision"] == (
        "source_continuation_failed")
    mid = lifecycle.get_assignment(run_id)
    assert _reconciliations(lifecycle, run_id) == []
    assert mid["status"] != "completed"

    # Order B: restart from durable state, replay the same accepted source.
    monkeypatch.setattr(
        "api.assignment_routes._advance_employee_work", real_advance)
    restarted = _rebuilt_executor(route_env)
    assert restarted.lifecycle.get_task(run_id) is not None
    calls_before_replay = len(calls)

    replay = _add_invoice(client, run_id, tmp_path)
    assert replay.status_code == 200, replay.text
    body = replay.json()
    assert body["status"] == "already_present", body
    reconciliations = _reconciliations(lifecycle, run_id)
    assert len(reconciliations) == 1, body
    assert reconciliations[0]["result"]["value"] == EXPECTED_TOTAL
    assert lifecycle.get_assignment(run_id)["status"] == "completed"
    assert len(calls) - calls_before_replay == 1

    # A further replay after completion must not repeat the applied operation.
    calls_after_completion = len(calls)
    again = _add_invoice(client, run_id, tmp_path)
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "already_present"
    assert len(_reconciliations(lifecycle, run_id)) == 1
    assert len(calls) == calls_after_completion
    assert lifecycle.get_assignment(run_id)["status"] == "completed"


def test_model_retain_after_relevant_source_does_not_fake_completion(
        route_env, tmp_path, monkeypatch):
    """Settling the question is not success when the model retains/fails."""
    _write_facts(tmp_path)
    calls = []

    async def discovery(context, **kwargs):
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read authorized procurement records",
                "evidence_reads": [
                    {"step_id": f"evidence-{i}", "title": "Read source",
                     "source_id": source["source_id"]}
                    for i, source in enumerate(context["sources"], 1)
                ],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    async def retain(context, observations, **kwargs):
        calls.append("retain")
        return {
            "proposal": WorkAdaptationProposal(
                decision="retain",
                reason="no supported work request is suitable yet",
                observation_ids=[
                    item["observation_id"] for item in observations],
            ).model_dump(),
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr("api.assignment_routes.propose_employee_work", discovery)
    monkeypatch.setattr("api.assignment_routes.propose_adaptation", retain)
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm", lambda *a, **k: object())
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]
    run_id = _start_missing_invoice(client, tmp_path)

    answer = _add_invoice(client, run_id, tmp_path)
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["resolved_question_ids"], body
    assert body["continuation_rounds"], body
    assert body["continuation_rounds"][0]["decision"] == "retain", body
    assert _reconciliations(lifecycle, run_id) == []
    assert lifecycle.get_assignment(run_id)["status"] != "completed"
    assert calls, "the model retain decision must be exercised"


@pytest.mark.parametrize("case", ["wrong_subject", "partial", "unrelated"])
def test_irrelevant_source_answer_stays_unresolved(
        route_env, tmp_path, monkeypatch, case):
    """Wrong, partial or unrelated evidence must not settle or fake success."""
    calls = []
    _install_controlled_transport(monkeypatch, calls)
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]
    if case == "wrong_subject":
        _write_facts(tmp_path, invoice_overrides={"po_id": "PO-OTHER-99"})
        name = "invoice.json"
    elif case == "partial":
        _write_facts(tmp_path, invoice_overrides={"unit_price": None})
        name = "invoice.json"
    else:
        _write_facts(tmp_path)
        unrelated = tmp_path / "notes.json"
        unrelated.write_text(json.dumps({"notes": "no invoice data here"}))
        name = "notes.json"
    run_id = _start_missing_invoice(client, tmp_path)
    before = len(calls)

    answer = _add_invoice(client, run_id, tmp_path, name=name)
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["resolved_question_ids"] == [], body
    assert _reconciliations(lifecycle, run_id) == []
    final = lifecycle.get_assignment(run_id)
    assert final["status"] != "completed", final["status"]
    assert open_unresolved_questions(lifecycle.get_task(run_id)), (
        "the genuine missing-invoice obligation must stay open")
    assert len(calls) == before, "no adaptation may be driven by bad evidence"

    # A replay of the same irrelevant source is equally inert.
    duplicate = _add_invoice(client, run_id, tmp_path, name=name)
    assert duplicate.status_code == 200, duplicate.text
    assert _reconciliations(lifecycle, run_id) == []
    assert len(calls) == before


def test_explicit_use_model_false_does_not_adapt_after_source_answer(
        route_env, tmp_path, monkeypatch):
    """Explicit offline objectives never start model adaptation from a source."""
    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "1")
    monkeypatch.setenv(
        "ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT", str(tmp_path))

    def applied(step_id, data):
        step = new_step(
            step_id=step_id, title=step_id, operation_type="retrieve",
            adapter="document.read", inputs={}, effect="read_only")
        payload = tmp_path / f"{step_id}.json"
        payload.write_text(json.dumps(data))
        step.update(
            status="applied", operation_id=f"op-{step_id}",
            inputs={"path": str(payload)},
            result={
                "data": data, "resource_id": step_id,
                "source_version": "v1",
                "coverage": {"complete": True, "known": True,
                             "truncated": False},
                "verification": {
                    "status": "verified", "resource_id": step_id,
                    "version": "v1"},
            })
        return step

    plan = new_assignment(
        objective=f"Reconcile the supplier invoice for {PO}",
        employee_id="owner-1", workspace_id="ws-1", tenant_id="tenant-1",
        teaching_snapshot=new_teaching_snapshot(revision="offline-source-1"),
        steps=[
            applied("purchase-order", {
                "po_id": PO, "vendor_id": "V-6", "quantity": "3",
                "unit_price": "42.50", "freight": "12.75"}),
            applied("receiving", {"po_id": PO, "received_quantity": "3"}),
        ],
        authorized_actions=["retrieve", "calculate"],
        completion_criteria=[{
            "criterion_id": "employee_result:objective",
            "kind": "employee_result",
            "required": True,
            "verifier": "employee_result",
            "scope": {"workspace_id": "ws-1"},
        }],
        provenance={"use_model": False, "proposal_source": "deterministic"},
    )
    record = route_env["executor"].create_assignment(
        "conv-offline-source", plan["objective"], assignment=plan)
    run_id = record["run_id"]
    add_unresolved_questions(route_env["lifecycle"], run_id, [{
        "kind": "missing_evidence",
        "item": "invoice reconciliation",
        "question": f"Which authorized source contains the invoice for {PO}?",
        "concept": "invoice_reconciliation",
        "operation": "invoice_reconciliation",
        "next_action": "Authorize the invoice source.",
        "inputs": {
            "operation": "invoice_reconciliation",
            "missing": ["invoice"],
            "known_identities": {"purchase_order.po_id": PO},
        },
    }])

    called = {"continuation": 0}

    async def forbidden(*args, **kwargs):
        called["continuation"] += 1
        raise RuntimeError("must not adapt an explicit offline objective")

    monkeypatch.setattr(
        "api.assignment_routes._advance_employee_work", forbidden)
    invoice = tmp_path / "invoice.json"
    invoice.write_text(json.dumps({
        "invoice_id": INVOICE, "po_id": PO, "quantity": "3",
        "unit_price": "42.50", "freight": "12.75", "currency": "USD"}))
    answer = route_env["client"].post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(invoice)},
              "reason": "the user supplied the invoice"})
    assert answer.status_code == 200, answer.text
    assert called["continuation"] == 0
    assert _reconciliations(route_env["lifecycle"], run_id) == []
    assert route_env["lifecycle"].get_assignment(run_id)["status"] != (
        "completed")


def test_cancelled_task_refuses_source_arrival_without_resurrection(
        route_env, tmp_path, monkeypatch):
    """Cancellation beats a late source answer; no work is applied."""
    calls = []
    _install_controlled_transport(monkeypatch, calls)
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]
    _write_facts(tmp_path)
    run_id = _start_missing_invoice(client, tmp_path)
    cancelled = client.post(
        f"/api/assignments/{run_id}/cancel", json={"reason": "owner cancel"})
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["assignment"]["status"] == "cancelled"
    before = len(calls)

    late = _add_invoice(client, run_id, tmp_path)
    assert late.status_code in (200, 409), late.text
    final = lifecycle.get_assignment(run_id)
    assert final["status"] == "cancelled", final["status"]
    assert _reconciliations(lifecycle, run_id) == []
    assert len(calls) == before


def test_absolute_deadline_is_not_extended_by_source_arrival(
        route_env, tmp_path, monkeypatch):
    """An explicit past deadline stays blocked; a source answer cannot revive it."""
    from datetime import datetime, timezone

    calls = []
    _install_controlled_transport(monkeypatch, calls)
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]
    _write_facts(tmp_path)
    run_id = _start_missing_invoice(client, tmp_path)
    past = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()

    def expire(record, assignment):
        assignment["budget"]["deadline"] = past
        return assignment, {}

    lifecycle.mutate_assignment(
        run_id, expire, rationale="test: explicit absolute deadline")
    before = len(calls)

    answer = _add_invoice(client, run_id, tmp_path)
    assert answer.status_code in (200, 409), answer.text
    final = lifecycle.get_assignment(run_id)
    assert final["status"] == "blocked", final["status"]
    assert final["budget"]["deadline"] == past
    assert _reconciliations(lifecycle, run_id) == []
    assert len(calls) == before


def test_restart_owner_does_not_poll_a_missing_or_unsuitable_obligation(
        route_env, tmp_path, monkeypatch):
    """No accepted evidence means no model call, no advance and no success.

    This is the startup-owner counterpart of the route's no-suitable negative:
    a genuine missing-invoice obligation is open, so ordinary recovery may
    resume other ready work but must not ask the model to invent business
    work from absence.
    """
    _write_facts(tmp_path)
    calls = _install_controlled_transport(monkeypatch, calls=[])
    run_id = _start_missing_invoice(route_env["client"], tmp_path)
    before = len(calls)

    restarted = _rebuilt_executor(route_env)
    asyncio.run(restarted.recover_ready_assignments(limit=20))

    final = route_env["lifecycle"].get_assignment(run_id)
    assert len(calls) == before, "absence must not be model-polled"
    assert _reconciliations(route_env["lifecycle"], run_id) == []
    assert final["status"] != "completed"
    assert open_unresolved_questions(route_env["lifecycle"].get_task(run_id))


def test_recovery_claim_makes_second_successor_and_repeat_inert(
        route_env, tmp_path, monkeypatch):
    """A bounded claim is the concurrent-wake authority for this seam.

    The first successor claims the accepted evidence; a second successor
    (the concurrent wake) sees the fresh claim and makes no model call. After
    the first attempt is recorded, a later boot is one-shot inert for the same
    evidence set instead of polling forever.
    """
    import api.assignment_routes as assignment_routes
    from core.employee_job_runner import evidence_observations

    _write_facts(tmp_path)
    calls = _install_controlled_transport(monkeypatch, calls=[])
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]
    run_id = _start_missing_invoice(client, tmp_path)

    real_advance = assignment_routes._advance_employee_work

    async def interrupted(*args, **kwargs):
        raise RuntimeError("simulated interruption before adaptation")

    monkeypatch.setattr(
        "api.assignment_routes._advance_employee_work", interrupted)
    first = _add_invoice(client, run_id, tmp_path)
    assert first.status_code == 200, first.text
    monkeypatch.setattr(
        "api.assignment_routes._advance_employee_work", real_advance)

    record = lifecycle.get_task(run_id)
    assert open_unresolved_questions(record) == []
    assert evidence_observations(record), "accepted evidence must remain"
    first_successor = _rebuilt_executor(route_env)
    second_successor = _rebuilt_executor(route_env)
    plan = first_successor._evidence_recovery_plan(record)
    assert plan is not None
    assert first_successor._claim_evidence_recovery(
        run_id, plan["key"]) is not None

    before = len(calls)
    asyncio.run(second_successor.recover_ready_assignments(limit=20))
    assert len(calls) == before, "the concurrent successor must stay inert"

    first_successor._finish_evidence_recovery(
        run_id, plan["key"], "attempted")
    asyncio.run(second_successor.recover_ready_assignments(limit=20))
    assert len(calls) == before, "a repeat boot must not re-poll the same set"
    assert _reconciliations(lifecycle, run_id) == []
    assert lifecycle.get_assignment(run_id)["status"] != "completed"

    # Clear only the test's synthetic one-shot marker: a real successor then
    # performs the single dependent operation once.
    def clear_marker(record, assignment):
        import copy as _copy

        updated = _copy.deepcopy(assignment)
        updated.pop("evidence_recovery", None)
        return updated, {}

    lifecycle.mutate_assignment(
        run_id, clear_marker, rationale="test: clear synthetic claim marker")
    asyncio.run(second_successor.recover_ready_assignments(limit=20))
    assert len(calls) == before + 1
    reconciliations = _reconciliations(lifecycle, run_id)
    assert len(reconciliations) == 1
    assert reconciliations[0]["result"]["value"] == EXPECTED_TOTAL
    assert lifecycle.get_assignment(run_id)["status"] == "completed"


def test_concurrent_recovery_successors_adapt_accepted_evidence_once(
        route_env, tmp_path, monkeypatch):
    """Two successors starting together: exactly one model call and result."""
    import api.assignment_routes as assignment_routes

    _write_facts(tmp_path)
    calls = _install_controlled_transport(monkeypatch, calls=[])
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]
    run_id = _start_missing_invoice(client, tmp_path)

    real_advance = assignment_routes._advance_employee_work

    async def interrupted(*args, **kwargs):
        raise RuntimeError("simulated interruption before adaptation")

    monkeypatch.setattr(
        "api.assignment_routes._advance_employee_work", interrupted)
    first = _add_invoice(client, run_id, tmp_path)
    assert first.status_code == 200, first.text

    async def slow_advance(*args, **kwargs):
        # Yield so the second successor reaches the claim while the first is
        # in flight; it must lose the CAS and make no model call.
        await asyncio.sleep(0.2)
        return await real_advance(*args, **kwargs)

    monkeypatch.setattr(
        "api.assignment_routes._advance_employee_work", slow_advance)
    first_successor = _rebuilt_executor(route_env)
    second_successor = _rebuilt_executor(route_env)
    before = len(calls)

    async def run_both():
        return await asyncio.gather(
            first_successor.recover_ready_assignments(limit=20),
            second_successor.recover_ready_assignments(limit=20))

    asyncio.run(run_both())
    assert len(calls) == before + 1, calls
    reconciliations = _reconciliations(lifecycle, run_id)
    assert len(reconciliations) == 1
    assert reconciliations[0]["result"]["value"] == EXPECTED_TOTAL
    assert lifecycle.get_assignment(run_id)["status"] == "completed"


def test_open_second_prerequisite_blocks_recovery_until_it_is_resolved(
        route_env, tmp_path, monkeypatch):
    """One settled prerequisite is not enough: a second open obligation sleeps.

    The accepted invoice evidence is durable, but recovery must not adapt
    around another open material prerequisite. Resolving it lets the same
    successor recover the accepted source exactly once.
    """
    import api.assignment_routes as assignment_routes

    _write_facts(tmp_path)
    calls = _install_controlled_transport(monkeypatch, calls=[])
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]
    run_id = _start_missing_invoice(client, tmp_path)

    real_advance = assignment_routes._advance_employee_work

    async def interrupted(*args, **kwargs):
        raise RuntimeError("simulated interruption before adaptation")

    monkeypatch.setattr(
        "api.assignment_routes._advance_employee_work", interrupted)
    first = _add_invoice(client, run_id, tmp_path)
    assert first.status_code == 200, first.text
    monkeypatch.setattr(
        "api.assignment_routes._advance_employee_work", real_advance)
    assert open_unresolved_questions(lifecycle.get_task(run_id)) == []

    add_unresolved_questions(lifecycle, run_id, [{
        "kind": "missing_evidence",
        "item": "invoice approval",
        "question": f"Is invoice {INVOICE} approved for {PO}?",
        "concept": "invoice_reconciliation",
        "operation": "invoice_reconciliation",
        "next_action": "Authorize the approval record.",
        "inputs": {
            "operation": "invoice_reconciliation",
            "missing": ["approval"],
            "known_identities": {"purchase_order.po_id": PO},
        },
    }])
    second = [
        item for item in open_unresolved_questions(
            lifecycle.get_task(run_id))
        if str(item.get("item") or "") == "invoice approval"]
    assert len(second) == 1

    before = len(calls)
    asyncio.run(_rebuilt_executor(route_env).recover_ready_assignments(
        limit=20))
    assert len(calls) == before, "an open second obligation must sleep"
    assert _reconciliations(lifecycle, run_id) == []
    assert lifecycle.get_assignment(run_id)["status"] != "completed"

    resolve_unresolved_questions(
        lifecycle, run_id,
        question_ids=[second[0]["question_id"]],
        resolution="approval record accepted")
    asyncio.run(_rebuilt_executor(route_env).recover_ready_assignments(
        limit=20))
    assert len(calls) == before + 1
    reconciliations = _reconciliations(lifecycle, run_id)
    assert len(reconciliations) == 1
    assert reconciliations[0]["result"]["value"] == EXPECTED_TOTAL
    assert lifecycle.get_assignment(run_id)["status"] == "completed"


def test_restart_owner_does_not_revive_expired_or_cancelled_work(
        route_env, tmp_path, monkeypatch):
    """An absolute deadline and cancellation still beat a restart wake."""
    import api.assignment_routes as assignment_routes
    from datetime import datetime, timezone

    _write_facts(tmp_path)
    calls = _install_controlled_transport(monkeypatch, calls=[])
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]
    run_id = _start_missing_invoice(client, tmp_path)

    real_advance = assignment_routes._advance_employee_work

    async def interrupted(*args, **kwargs):
        raise RuntimeError("simulated interruption before adaptation")

    monkeypatch.setattr(
        "api.assignment_routes._advance_employee_work", interrupted)
    first = _add_invoice(client, run_id, tmp_path)
    assert first.status_code == 200, first.text
    monkeypatch.setattr(
        "api.assignment_routes._advance_employee_work", real_advance)

    past = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()

    def expire(record, assignment):
        assignment["budget"]["deadline"] = past
        return assignment, {}

    lifecycle.mutate_assignment(
        run_id, expire, rationale="test: explicit absolute deadline")
    before = len(calls)
    asyncio.run(_rebuilt_executor(route_env).recover_ready_assignments(
        limit=20))
    assert len(calls) == before, "an expired task must not wake the model"
    assert _reconciliations(lifecycle, run_id) == []
    assert lifecycle.get_assignment(run_id)["budget"]["deadline"] == past

    client.post(f"/api/assignments/{run_id}/cancel", json={"reason": "owner"})
    asyncio.run(_rebuilt_executor(route_env).recover_ready_assignments(
        limit=20))
    assert len(calls) == before
    assert _reconciliations(lifecycle, run_id) == []
    assert lifecycle.get_assignment(run_id)["status"] == "cancelled"
