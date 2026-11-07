"""Failure-first probe for the two-sequential-fact role-scoping defect.

This exact probe is a TEST-ONLY addition used against frozen baseline
dff775b8f. It is intentionally untyped (no clarification.missing_roles, which
does not exist at that source): the controlled model asks only for the
invoice, and the assertion checks that the durable obligation is scoped to the
invoice role even though receiving is also missing. Baseline persists
["invoice", "receiving"], so the answer cannot settle its own question.

The committed E1 test (test_task_wait_two_fact_events.py at e10a689c9) is the
repaired-schema positive/negative twin. Do not describe these bytes as the
committed test bytes.
"""
from __future__ import annotations

import json

from tests.test_assignment_routes import route_env  # noqa: F401

PO = "PO-TWO-1"
INVOICE = "INV-TWO-1"


def _fixtures(tmp_path):
    po = tmp_path / "po.json"
    po.write_text(json.dumps({
        "po_id": PO, "vendor_id": "V-1", "quantity": "3",
        "unit_price": "40.00", "freight": "10.00", "currency": "USD"}))
    invoice = tmp_path / "invoice.json"
    invoice.write_text(json.dumps({
        "po_id": PO, "invoice_id": INVOICE, "quantity": "3",
        "unit_price": "40.00", "freight": "10.00", "currency": "USD"}))
    receiving = tmp_path / "receiving.json"
    receiving.write_text(json.dumps({
        "po_id": PO, "received_quantity": "3"}))
    return po, invoice, receiving


def _install_transport(monkeypatch):
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import InvoiceReconciliationRequest

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
        common = {
            "reason": "model-selected supported work",
            "observation_ids": [
                item["observation_id"] for item in observations],
        }
        if missing:
            return {
                "proposal": WorkAdaptationProposal(
                    decision="clarify",
                    clarification={
                        "question": (
                            f"Which authorized source contains the missing "
                            f"{missing[0]} record for purchase order {PO}?"),
                        "concept": "invoice_reconciliation",
                        "unblocks": "invoice reconciliation",
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


def test_first_question_is_scoped_to_the_requested_invoice_role(
        route_env, tmp_path, monkeypatch):
    po, _invoice, _receiving = _fixtures(tmp_path)
    _install_transport(monkeypatch)
    from core.task_lifecycle import open_unresolved_questions

    client = route_env["client"]
    lifecycle = route_env["lifecycle"]
    started = client.post(
        "/api/assignments/from-objective",
        json={
            "objective": (
                f"Reconcile the supplier invoice for purchase order {PO}"),
            "sources": [{"path": str(po)}],
            "authorized_actions": ["retrieve", "calculate"],
            "use_model": True,
        })
    assert started.status_code == 200, started.text
    run_id = started.json()["run_id"]
    open_questions = open_unresolved_questions(lifecycle.get_task(run_id))
    assert len(open_questions) == 1, open_questions
    assert open_questions[0]["inputs"]["missing"] == ["invoice"], (
        open_questions[0]["inputs"])
