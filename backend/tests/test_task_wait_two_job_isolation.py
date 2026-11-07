"""TASK-WAIT-01 E2: two same-workspace jobs stay isolated.

Two normal assignments in the same workspace start on different opaque
purchase-order subjects. Each has its own durable invoice question. Answering
A's invoice must wake only A: B's open question, model calls and applied
receipts stay byte-identical. The symmetric valid twin answers B afterwards
without touching A's next question.

Public assignment routes, the real compiler/executor and scratch durable
records are exercised. High-level discovery/adaptation proposal choices and authentication use
controlled fixtures; these are not transport-only or served-model controls; no provider, spend, account, send or deployment action occurs.
"""
from __future__ import annotations

import copy
import json

from tests.test_assignment_routes import route_env  # noqa: F401


CASES = {
    "A": {
        "po": "PO-E2-K7X2",
        "invoice": "INV-E2-K7X2",
        "quantity": "2", "unit_price": "15.00", "freight": "5.00",
        "total": "35.00",
    },
    "B": {
        "po": "PO-E2-Q9M4",
        "invoice": "INV-E2-Q9M4",
        "quantity": "4", "unit_price": "20.00", "freight": "0.00",
        "total": "80.00",
    },
}


def _fixtures(tmp_path, case):
    po = tmp_path / f"{case['po']}-po.json"
    po.write_text(json.dumps({
        "po_id": case["po"], "vendor_id": "V-1",
        "quantity": case["quantity"], "unit_price": case["unit_price"],
        "freight": case["freight"], "currency": "USD"}))
    invoice = tmp_path / f"{case['invoice']}-invoice.json"
    invoice.write_text(json.dumps({
        "po_id": case["po"], "invoice_id": case["invoice"],
        "quantity": case["quantity"], "unit_price": case["unit_price"],
        "freight": case["freight"], "currency": "USD"}))
    receiving = tmp_path / f"{case['po']}-receiving.json"
    receiving.write_text(json.dumps({
        "po_id": case["po"], "received_quantity": case["quantity"]}))
    return po, invoice, receiving


def _install_transport(monkeypatch):
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import InvoiceReconciliationRequest

    calls = []

    async def discovery(context, **kwargs):
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read the authorized scope",
                "evidence_reads": [
                    {"step_id": f"evidence-{index}", "title": "Read source",
                     "source_id": source["source_id"]}
                    for index, source in enumerate(context["sources"], 1)
                ],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    async def adaptation(context, observations, **kwargs):
        roles = {
            str(item.get("business_role") or ""): item["step_id"]
            for item in context.get("evidence_results") or []
            if item.get("business_role")
        }
        capability = next(
            (item for item in context.get("available_business_operations") or []
             if str(item.get("operation") or "") == "invoice_reconciliation"),
            {})
        missing = [str(role) for role in capability.get("missing") or []
                   if str(role).strip()]
        known = capability.get("known_identities") or {}
        subject = str(known.get("purchase_order.po_id") or "")
        calls.append({
            "objective": str(context.get("objective") or ""),
            "roles": tuple(sorted(roles)),
        })
        common = {
            "reason": "model-selected supported work",
            "observation_ids": [
                item["observation_id"] for item in observations],
        }
        if missing:
            role = missing[0]
            return {
                "proposal": WorkAdaptationProposal(
                    decision="clarify",
                    clarification={
                        "question": (
                            f"Which authorized source contains the missing "
                            f"{role} record for purchase order {subject}?"),
                        "concept": "invoice_reconciliation",
                        "unblocks": "invoice reconciliation",
                        "missing_roles": [role],
                    },
                    **common,
                ).model_dump(),
                "source": "model",
                "technical_fallback": False,
                "errors": [],
            }
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan",
                work_request=InvoiceReconciliationRequest(
                    operation="invoice_reconciliation",
                    invoice_step_id=roles["invoice"],
                    purchase_order_step_id=roles["purchase_order"],
                    receiving_step_id=roles["receiving"]),
                **common,
            ).model_dump(),
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", discovery)
    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", adaptation)
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm", lambda *a, **k: object())
    return calls


def _start(client, po, key):
    answer = client.post(
        "/api/assignments/from-objective",
        json={
            "objective": (
                f"Reconcile the supplier invoice for purchase order {key}"),
            "sources": [{"path": str(po)}],
            "authorized_actions": ["retrieve", "calculate"],
            "use_model": True,
        })
    assert answer.status_code == 200, answer.text
    return answer.json()["run_id"]


def _questions(lifecycle, run_id):
    from core.task_lifecycle import open_unresolved_questions

    return open_unresolved_questions(lifecycle.get_task(run_id))


def _receipt_snapshot(assignment):
    """Applied steps and their accepted results, without volatile fields."""
    return [
        {
            "step_id": step["step_id"],
            "adapter": step["adapter"],
            "status": step["status"],
            "result": copy.deepcopy(step.get("result")),
        }
        for step in assignment["steps"]
        if step.get("status") in ("applied", "failed", "waiting")
    ]


def _reconciliations(assignment):
    return [
        step for step in assignment["steps"]
        if step["adapter"] == "invoice.reconcile"
        and step["status"] == "applied"
    ]


def test_two_same_workspace_jobs_keep_questions_and_receipts_isolated(
        route_env, tmp_path, monkeypatch):
    monkeypatch.setenv(
        "ATOM_ASSIGNMENT_OUTPUT_DIR", str(tmp_path / "artifacts"))
    calls = _install_transport(monkeypatch)
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]

    fixtures = {
        key: _fixtures(tmp_path, case) for key, case in CASES.items()}
    run_a = _start(client, fixtures["A"][0], CASES["A"]["po"])
    run_b = _start(client, fixtures["B"][0], CASES["B"]["po"])

    question_a = _questions(lifecycle, run_a)
    question_b = _questions(lifecycle, run_b)
    assert len(question_a) == 1 and len(question_b) == 1, (
        question_a, question_b)
    assert question_a[0]["question_id"] != question_b[0]["question_id"]
    assert question_a[0]["inputs"]["missing"] == ["invoice"]
    assert question_b[0]["inputs"]["missing"] == ["invoice"]
    assert CASES["A"]["po"] in question_a[0]["question"]
    assert CASES["B"]["po"] in question_b[0]["question"]

    before_b_questions = copy.deepcopy(question_b)
    before_b_receipts = _receipt_snapshot(lifecycle.get_assignment(run_b))
    before_b_calls = sum(
        1 for call in calls if CASES["B"]["po"] in call["objective"])

    # A's authorized invoice wakes only A.
    answered_a = client.post(
        f"/api/assignments/{run_a}/sources",
        json={"source": {"path": str(fixtures["A"][1])},
              "reason": "authorized invoice for A"})
    assert answered_a.status_code == 200, answered_a.text
    assert answered_a.json()["resolved_question_ids"] == [
        question_a[0]["question_id"]], answered_a.json()

    next_a = _questions(lifecycle, run_a)
    assert len(next_a) == 1, next_a
    assert next_a[0]["inputs"]["missing"] == ["receiving"]
    assert next_a[0]["question_id"] != question_a[0]["question_id"]

    after_b_questions = _questions(lifecycle, run_b)
    assert after_b_questions == before_b_questions, (
        after_b_questions, before_b_questions)
    assert _receipt_snapshot(lifecycle.get_assignment(run_b)) == (
        before_b_receipts)
    assert sum(
        1 for call in calls if CASES["B"]["po"] in call["objective"]) == (
            before_b_calls), calls

    before_a_questions = copy.deepcopy(next_a)
    before_a_receipts = _receipt_snapshot(lifecycle.get_assignment(run_a))
    before_a_calls = sum(
        1 for call in calls if CASES['A']['po'] in call['objective'])

    # Symmetric valid twin: B's invoice wakes only B.
    answered_b = client.post(
        f"/api/assignments/{run_b}/sources",
        json={"source": {"path": str(fixtures["B"][1])},
              "reason": "authorized invoice for B"})
    assert answered_b.status_code == 200, answered_b.text
    assert answered_b.json()["resolved_question_ids"] == [
        before_b_questions[0]["question_id"]], answered_b.json()
    next_b = _questions(lifecycle, run_b)
    assert len(next_b) == 1 and next_b[0]["inputs"]["missing"] == [
        "receiving"], next_b
    still_a = _questions(lifecycle, run_a)
    assert [item["question_id"] for item in still_a] == [
        next_a[0]["question_id"]]
    assert still_a == before_a_questions
    assert _receipt_snapshot(lifecycle.get_assignment(run_a)) == before_a_receipts
    assert sum(
        1 for call in calls if CASES['A']['po'] in call['objective']) == (
            before_a_calls), calls
    assert _reconciliations(lifecycle.get_assignment(run_a)) == []
    assert _reconciliations(lifecycle.get_assignment(run_b)) == []

    # Each job completes with its own arithmetic after its own receiving fact.
    for key, run_id in (("A", run_a), ("B", run_b)):
        answered = client.post(
            f"/api/assignments/{run_id}/sources",
            json={"source": {"path": str(fixtures[key][2])},
                  "reason": f"authorized receiving for {key}"})
        assert answered.status_code == 200, answered.text

    final_a = lifecycle.get_assignment(run_a)
    final_b = lifecycle.get_assignment(run_b)
    assert final_a["status"] == "completed", final_a["status"]
    assert final_b["status"] == "completed", final_b["status"]
    assert [step["result"]["value"]
            for step in _reconciliations(final_a)] == [CASES["A"]["total"]]
    assert [step["result"]["value"]
            for step in _reconciliations(final_b)] == [CASES["B"]["total"]]
    assert _questions(lifecycle, run_a) == []
    assert _questions(lifecycle, run_b) == []
