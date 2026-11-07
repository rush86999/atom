"""TASK-WAIT-01 independent work while a source-triggered wait is open.

A real objective can contain both an independent, authorized branch and a
material fact the job is still waiting for. The independent branch may run and
retain its receipt, but a requested final artifact must stay blocked until the
open obligation is answered and the dependent business result is verified.

Public assignment routes, the real compiler/executor and scratch durable
records are exercised. Proposal transport is the repository's controlled
fixture; no provider, spend, account, send or deployment action occurs.
"""
from __future__ import annotations

import json

from tests.test_assignment_routes import (  # noqa: F401
    _scotch_catalog,
    route_env,
)

PO = "PO-IND-1"
INVOICE = "INV-IND-1"


def _fixtures(tmp_path):
    po = tmp_path / "po.json"
    po.write_text(json.dumps({
        "po_id": PO, "vendor_id": "V-1", "quantity": "2",
        "unit_price": "120.00", "freight": "30.00", "currency": "USD"}))
    receiving = tmp_path / "receiving.json"
    receiving.write_text(json.dumps({
        "po_id": PO, "received_quantity": "2"}))
    invoice = tmp_path / "invoice.json"
    invoice.write_text(json.dumps({
        "po_id": PO, "invoice_id": INVOICE, "quantity": "2",
        "unit_price": "120.00", "freight": "30.00", "currency": "USD"}))
    return po, receiving, invoice


def _install_transport(monkeypatch):
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import (
        InvoiceReconciliationRequest,
        MoneyTerm,
        QuoteCalculationRequest,
        QuoteColumns,
        TaxTerm,
    )

    state = {"clarified": False, "quote": False}
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
        quote_evidence = next(
            (item for item in context.get("evidence_results") or []
             if any(str(entry.get("column") or "") == "Item Number"
                    for entry in (item.get("schema") or [])
                    if isinstance(entry, dict))),
            None)
        calls.append(dict(roles))
        common = {
            "reason": "model-selected supported work",
            "observation_ids": [
                item["observation_id"] for item in observations],
        }
        if (not all(roles.get(key) for key in (
                "invoice", "purchase_order", "receiving"))
                and not state["clarified"]):
            state["clarified"] = True
            return {
                "proposal": WorkAdaptationProposal(
                    decision="clarify",
                    clarification={
                        "question": (
                            f"Which authorized source contains invoice "
                            f"{INVOICE} for {PO}?"),
                        "concept": "invoice_reconciliation",
                        "unblocks": "invoice reconciliation",
                    },
                    **common,
                ).model_dump(),
                "source": "model",
                "technical_fallback": False,
                "errors": [],
            }
        if quote_evidence and not state["quote"]:
            state["quote"] = True
            request = QuoteCalculationRequest(
                operation="quote_calculation",
                source_step_id=str(quote_evidence["step_id"]),
                columns=QuoteColumns(
                    item_id="Item Number",
                    description="Description",
                    quantity="Quantity",
                    unit_price="Unit Price",
                    currency="Currency"),
                currency="USD",
                freight=MoneyTerm(value="20.00", authority_ref="freight"),
                tax=TaxTerm(basis="none", authority_ref="tax_basis"))
        else:
            request = InvoiceReconciliationRequest(
                operation="invoice_reconciliation",
                invoice_step_id=roles["invoice"],
                purchase_order_step_id=roles["purchase_order"],
                receiving_step_id=roles["receiving"])
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan", work_request=request, **common,
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


def _start_missing_invoice(client, tmp_path, po, receiving):
    answer = client.post(
        "/api/assignments/from-objective",
        json={
            "objective": (
                f"Reconcile invoice {INVOICE} for {PO} and prepare the quote"),
            "sources": [
                {"kind": "workbook",
                 "dataset_name": "scotch_parts_price_list",
                 "sheet": "US$ SCOTCH PARTS"},
                {"path": str(po)},
                {"path": str(receiving)},
            ],
            "authorized_actions": ["retrieve", "calculate"],
            "teaching_terms": {
                "currency": "USD", "freight": "20.00", "tax_basis": "none"},
            "requested_output": "document",
            "use_model": True,
        })
    assert answer.status_code == 200, answer.text
    return answer.json()["run_id"]


def _steps(assignment):
    return [
        {
            "id": step["step_id"],
            "adapter": step["adapter"],
            "status": step["status"],
            "value": (step.get("result") or {}).get("value"),
        }
        for step in assignment["steps"]
    ]


def _reconciliation(assignment):
    return [
        step for step in assignment["steps"]
        if step["adapter"] == "invoice.reconcile"
        and step["status"] == "applied"
    ]


def _applied_artifacts(assignment):
    return [
        step for step in assignment["steps"]
        if step["adapter"].startswith("artifact.")
        and step["status"] == "applied"
    ]


def test_independent_work_does_not_release_a_premature_final_artifact(
        route_env, tmp_path, monkeypatch):
    _scotch_catalog(route_env, tmp_path, monkeypatch)
    monkeypatch.setenv(
        "ATOM_ASSIGNMENT_OUTPUT_DIR", str(tmp_path / "artifacts"))
    po, receiving, invoice = _fixtures(tmp_path)
    calls = _install_transport(monkeypatch)
    client = route_env["client"]
    lifecycle = route_env["lifecycle"]

    run_id = _start_missing_invoice(client, tmp_path, po, receiving)
    started = lifecycle.get_assignment(run_id)
    assert started["status"] in ("waiting", "blocked"), started["status"]
    assert _reconciliation(started) == []
    assert _applied_artifacts(started) == []
    from core.task_lifecycle import open_unresolved_questions
    assert open_unresolved_questions(lifecycle.get_task(run_id))
    calls_before_advance = len(calls)

    # An explicit advance may run the independent authorized branch. It must
    # retain the quote receipt but not complete the job or release the final
    # requested artifact while the invoice question is still open.
    advanced = client.post(
        f"/api/assignments/{run_id}/advance",
        json={"use_model": True, "max_adaptations": 2,
              "deadline_seconds": 60})
    assert advanced.status_code == 200, advanced.text
    working = lifecycle.get_assignment(run_id)
    assert any(
        step["adapter"] == "quote.calculate" and step["status"] == "applied"
        for step in working["steps"]), _steps(working)
    assert _reconciliation(working) == [], _steps(working)
    assert _applied_artifacts(working) == [], _steps(working)
    assert working["status"] != "completed", _steps(working)
    assert open_unresolved_questions(lifecycle.get_task(run_id))
    assert len(calls) > calls_before_advance

    # The authorized invoice settles the wait; the same task then completes
    # with one reconciliation, the retained quote and the requested artifact.
    added = client.post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(invoice)},
              "reason": "the authorized invoice answers the open question"})
    assert added.status_code == 200, added.text
    final = lifecycle.get_assignment(run_id)
    assert final["status"] == "completed", _steps(final)
    reconciliations = _reconciliation(final)
    assert len(reconciliations) == 1
    assert reconciliations[0]["result"]["value"] == "270.00"
    quotes = [
        step for step in final["steps"]
        if step["adapter"] == "quote.calculate" and step["status"] == "applied"
    ]
    assert len(quotes) == 1
    assert quotes[0]["result"]["value"] == "105.00"
    artifacts = _applied_artifacts(final)
    assert len(artifacts) == 1
    assert artifacts[0]["status"] == "applied"
    assert open_unresolved_questions(lifecycle.get_task(run_id)) == []
