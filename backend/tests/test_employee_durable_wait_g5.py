"""Durable employee wait with model-chosen independent work.

The employee chooses one material external fact it cannot obtain from the
authorized evidence, the compiler binds the durable wait/correlation, and the
job continues useful independent work. A later authorized reply resumes the
same job. No wait step, correlation id or formula is supplied by the caller.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_assignment_routes import _scotch_catalog, route_env  # noqa: F401


def _fixtures(tmp_path):
    po = tmp_path / "purchase-order.json"
    po.write_text(json.dumps({
        "po_id": "PO-8841", "vendor_id": "V-9", "quantity": "2",
        "unit_price": "120.00", "freight": "30.00", "currency": "USD"}))
    invoice = tmp_path / "invoice.json"
    invoice.write_text(json.dumps({
        "invoice_id": "INV-7", "po_id": "PO-8841", "quantity": "2",
        "unit_price": "120.00", "freight": "30.00", "currency": "USD"}))
    receiving = tmp_path / "receiving.json"
    receiving.write_text(json.dumps({
        "po_id": "PO-8841", "received_quantity": "2", "version": "rcv-1"}))
    return po, invoice, receiving


def _install(monkeypatch, *, independent=True, await_first=True):
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import (
        AwaitEvidenceRequest, InvoiceReconciliationRequest, MoneyTerm,
        QuoteCalculationRequest, QuoteColumns, TaxTerm,
    )

    calls = {"count": 0}

    async def fake_work(context, **_kwargs):
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read the authorized procurement scope",
                "evidence_reads": [{
                    "step_id": f"evidence-{index}",
                    "title": "Read authorized evidence",
                    "source_id": source["source_id"],
                } for index, source in enumerate(
                    context["sources"], start=1)],
            },
            "source": "model", "technical_fallback": False, "errors": [],
        }

    async def fake_adaptation(context, observations, **_kwargs):
        calls["count"] += 1
        waiting = any(
            item.get("kind") == "waiting_state" for item in observations)
        roles = {
            str(item.get("business_role") or ""): item.get("step_id")
            for item in context.get("evidence_results") or []
            if item.get("business_role")
        }
        quote_evidence = next(
            (item for item in context.get("evidence_results") or []
             if any(
                 str(entry.get("column") or "") == "Item Number"
                 for entry in (item.get("schema") or [])
                 if isinstance(entry, dict))), None)
        if await_first and calls["count"] == 1:
            request = AwaitEvidenceRequest(
                operation="await_evidence",
                fact="received_quantity",
                subject="PO-8841",
                expected_from="warehouse receiving",
                expected_answer_type="quantity",
                blocks="invoice reconciliation")
        elif await_first and waiting and quote_evidence and independent:
            request = QuoteCalculationRequest(
                operation="quote_calculation",
                source_step_id=str(quote_evidence["step_id"]),
                columns=QuoteColumns(
                    item_id="Item Number", description="Description",
                    quantity="Quantity", unit_price="Unit Price",
                    currency="Currency"),
                currency="USD",
                freight=MoneyTerm(value="20.00", authority_ref="freight"),
                tax=TaxTerm(basis="none", authority_ref="tax_basis"))
        elif roles.get("receiving") and roles.get("invoice") \
                and roles.get("purchase_order"):
            request = InvoiceReconciliationRequest(
                operation="invoice_reconciliation",
                invoice_step_id=str(roles["invoice"]),
                purchase_order_step_id=str(roles["purchase_order"]),
                receiving_step_id=str(roles["receiving"]))
        elif not await_first and roles.get("receiving") and quote_evidence:
            request = QuoteCalculationRequest(
                operation="quote_calculation",
                source_step_id=str(quote_evidence["step_id"]),
                columns=QuoteColumns(
                    item_id="Item Number", description="Description",
                    quantity="Quantity", unit_price="Unit Price",
                    currency="Currency"),
                currency="USD",
                freight=MoneyTerm(value="20.00", authority_ref="freight"),
                tax=TaxTerm(basis="none", authority_ref="tax_basis"))
        else:
            return {
                "proposal": WorkAdaptationProposal(
                    decision="retain",
                    reason="no independent supported work is ready",
                    observation_ids=[
                        item["observation_id"] for item in observations],
                ).model_dump(),
                "source": "model", "technical_fallback": False, "errors": [],
            }
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan",
                reason="model-selected work",
                observation_ids=[
                    item["observation_id"] for item in observations],
                work_request=request).model_dump(),
            "source": "model", "technical_fallback": False, "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", fake_work)
    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", fake_adaptation)
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm",
        lambda *_args, **_kwargs: object())
    return calls


def _start(route_env, tmp_path, monkeypatch, *, requested_output=None,
           budget=None):
    """Wait-first order: read all sources, choose the wait, then quote."""
    _scotch_catalog(route_env, tmp_path, monkeypatch)
    po, invoice, _receiving = _fixtures(tmp_path)
    _install(monkeypatch)
    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": (
                "Reconcile the supplier invoice for PO-8841 and prepare the "
                "quote from the authorized price list"),
            "sources": [
                {"kind": "workbook",
                 "dataset_name": "scotch_parts_price_list",
                 "sheet": "US$ SCOTCH PARTS"},
                {"path": str(po)}, {"path": str(invoice)},
            ],
            "authorized_actions": ["retrieve", "calculate"],
            "teaching_terms": {
                "currency": "USD", "freight": "20.00",
                "tax_basis": "none"},
            "requested_output": requested_output,
            "budget": budget,
            "use_model": True,
        })
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    assignment = route_env["lifecycle"].get_assignment(run_id)
    if assignment["status"] == "waiting" and not any(
            step["adapter"] == "quote.calculate"
            for step in assignment["steps"]):
        advanced = route_env["client"].post(
            f"/api/assignments/{run_id}/advance",
            json={"use_model": True, "max_adaptations": 2,
                  "deadline_seconds": 60})
        assert advanced.status_code == 200, advanced.text
    return run_id


def _wait_step(assignment):
    return next(
        step for step in assignment["steps"]
        if step["adapter"] == "assignment.wait")


def test_wait_allows_model_chosen_independent_work_and_exact_reply(
        route_env, tmp_path, monkeypatch):
    run_id = _start(route_env, tmp_path, monkeypatch)
    assignment = route_env["lifecycle"].get_assignment(run_id)
    assert assignment["status"] == "waiting"
    wait = _wait_step(assignment)
    assert wait["status"] == "waiting"
    assert wait["waiting"]["correlation_id"].startswith("await-")
    assert wait["waiting"]["fact"] == "received_quantity"
    assert wait["waiting"]["subject"] == "PO-8841"
    assert wait["waiting"]["typed_binding"] is True
    assert wait["inputs"]["correlation_id"] == (
        wait["waiting"]["correlation_id"])
    quote = next(
        step for step in assignment["steps"]
        if step["adapter"] == "quote.calculate")
    assert quote["status"] == "applied"
    assert quote["result"]["value"] == "105.00"
    quote_operation = quote["operation_id"]
    po_read = next(
        step for step in assignment["steps"]
        if step["adapter"] == "document.read"
        and (step.get("result") or {}).get("data", {}).get("invoice_id"))
    po_operation = po_read["operation_id"]

    # A restart while waiting keeps the same durable wait identity.
    from core.assignment_executor import AssignmentExecutor

    restarted = AssignmentExecutor(route_env["lifecycle"])
    import asyncio

    asyncio.run(restarted.resume(run_id))
    after_restart = route_env["lifecycle"].get_assignment(run_id)
    assert _wait_step(after_restart)["waiting"]["correlation_id"] == (
        wait["waiting"]["correlation_id"])
    assert after_restart["status"] == "waiting"

    # The authorized receiving record arrives as a normal source, then the
    # reply binds to the durable wait and resumes the same job.
    receiving = tmp_path / "receiving.json"
    added = route_env["client"].post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(receiving)},
              "reason": "warehouse supplied the receiving record"})
    assert added.status_code == 200, added.text
    correlation = wait["waiting"]["correlation_id"]
    reply = route_env["client"].post(
        f"/api/assignments/{run_id}/responses/{correlation}",
        json={"response": "received 2 units",
              "source": "warehouse receiving", "value": "2"})
    assert reply.status_code == 200, reply.text
    final = route_env["lifecycle"].get_assignment(run_id)
    assert final["status"] == "completed", final["status"]
    reconcile = next(
        step for step in final["steps"]
        if step["adapter"] == "invoice.reconcile")
    assert reconcile["result"]["value"] == "270.00"
    # Independent quote and its source read are not recomputed or replaced.
    quote_after = next(
        step for step in final["steps"] if step["step_id"] == quote["step_id"])
    assert quote_after["operation_id"] == quote_operation
    assert quote_after["result"]["value"] == "105.00"
    po_after = next(
        step for step in final["steps"] if step["step_id"] == po_read["step_id"])
    assert po_after["operation_id"] == po_operation
    # The duplicate delivery is idempotent: no second reconcile or effect.
    duplicate = route_env["client"].post(
        f"/api/assignments/{run_id}/responses/{correlation}",
        json={"response": "received 2 units",
              "source": "warehouse receiving", "value": "2"})
    assert duplicate.status_code == 200, duplicate.text
    settled = route_env["lifecycle"].get_assignment(run_id)
    assert len([
        step for step in settled["steps"]
        if step["adapter"] == "invoice.reconcile"]) == 1


def test_wait_reply_refuses_wrong_correlation_party_and_answer_type(
        route_env, tmp_path, monkeypatch):
    run_id = _start(route_env, tmp_path, monkeypatch)
    assignment = route_env["lifecycle"].get_assignment(run_id)
    correlation = _wait_step(assignment)["waiting"]["correlation_id"]
    receiving = tmp_path / "receiving.json"
    added = route_env["client"].post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(receiving)},
              "reason": "warehouse supplied the receiving record"})
    assert added.status_code == 200, added.text

    wrong_correlation = route_env["client"].post(
        f"/api/assignments/{run_id}/responses/await-deadbeef",
        json={"response": "2", "source": "warehouse receiving",
              "value": "2"})
    assert wrong_correlation.status_code == 404, wrong_correlation.text
    wrong_party = route_env["client"].post(
        f"/api/assignments/{run_id}/responses/{correlation}",
        json={"response": "2", "source": "accounts payable",
              "value": "2"})
    assert wrong_party.status_code == 200, wrong_party.text
    assert wrong_party.json()["status"] == "conflict"
    assert _wait_step(route_env["lifecycle"].get_assignment(
        run_id))["status"] == "waiting"
    wrong_type = route_env["client"].post(
        f"/api/assignments/{run_id}/responses/{correlation}",
        json={"response": "two", "source": "warehouse receiving",
              "value": "two"})
    assert wrong_type.status_code == 200, wrong_type.text
    assert wrong_type.json()["status"] == "conflict"
    assert _wait_step(route_env["lifecycle"].get_assignment(
        run_id))["status"] == "waiting"
    exact = route_env["client"].post(
        f"/api/assignments/{run_id}/responses/{correlation}",
        json={"response": "received 2 units",
              "source": "warehouse receiving", "value": "2"})
    assert exact.status_code == 200, exact.text
    final = route_env["lifecycle"].get_assignment(run_id)
    assert final["status"] == "completed", final["status"]
    assert _wait_step(final)["status"] == "applied"


def test_duplicate_wait_intent_is_refused_and_cancel_refuses_late_reply(
        route_env, tmp_path, monkeypatch):
    run_id = _start(route_env, tmp_path, monkeypatch)
    assignment = route_env["lifecycle"].get_assignment(run_id)
    correlation = _wait_step(assignment)["waiting"]["correlation_id"]
    # A repeated identical await must not create a second durable wait.
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import AwaitEvidenceRequest
    from core.employee_work_compiler import (
        WorkRequestCompileError, compile_work_request_patch,
    )

    with pytest.raises(WorkRequestCompileError):
        compile_work_request_patch(
            AwaitEvidenceRequest(
                operation="await_evidence", fact="received_quantity",
                subject="PO-8841", expected_from="warehouse receiving",
                expected_answer_type="quantity",
                blocks="invoice reconciliation"),
            assignment, context={})

    cancelled = route_env["client"].post(
        f"/api/assignments/{run_id}/cancel",
        json={"reason": "owner cancelled while waiting"})
    assert cancelled.status_code == 200, cancelled.text
    late = route_env["client"].post(
        f"/api/assignments/{run_id}/responses/{correlation}",
        json={"response": "2", "source": "warehouse receiving",
              "value": "2"})
    assert late.status_code == 409, late.text
    assert route_env["lifecycle"].get_assignment(run_id)["status"] == (
        "cancelled")


def test_wait_is_absent_when_no_external_fact_is_material(
        route_env, tmp_path, monkeypatch):
    """A calculation-only objective never grows a wait step."""
    _scotch_catalog(route_env, tmp_path, monkeypatch)
    from core.employee_adaptation import WorkAdaptationProposal
    from core.employee_work_requests import (
        MoneyTerm, QuoteCalculationRequest, QuoteColumns, TaxTerm,
    )

    async def fake_work(context, **_kwargs):
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "read the price list",
                "evidence_reads": [{
                    "step_id": "evidence-1",
                    "title": "Read the price list",
                    "source_id": context["sources"][0]["source_id"],
                }],
            },
            "source": "model", "technical_fallback": False, "errors": [],
        }

    async def fake_adaptation(context, observations, **_kwargs):
        source = next(
            item for item in context.get("evidence_results") or []
            if any(str(entry.get("column") or "") == "Item Number"
                   for entry in (item.get("schema") or [])
                   if isinstance(entry, dict)))
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan",
                reason="quote from accepted rows",
                observation_ids=[
                    item["observation_id"] for item in observations],
                work_request=QuoteCalculationRequest(
                    operation="quote_calculation",
                    source_step_id=str(source["step_id"]),
                    columns=QuoteColumns(
                        item_id="Item Number", description="Description",
                        quantity="Quantity", unit_price="Unit Price",
                        currency="Currency"),
                    currency="USD",
                    freight=MoneyTerm(value="20.00", authority_ref="freight"),
                    tax=TaxTerm(basis="none", authority_ref="tax_basis"),
                )).model_dump(),
            "source": "model", "technical_fallback": False, "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", fake_work)
    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", fake_adaptation)
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm",
        lambda *_args, **_kwargs: object())
    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": "Prepare the quote from the authorized price list",
            "sources": [{
                "kind": "workbook",
                "dataset_name": "scotch_parts_price_list",
                "sheet": "US$ SCOTCH PARTS",
            }],
            "authorized_actions": ["retrieve", "calculate"],
            "teaching_terms": {
                "currency": "USD", "freight": "20.00",
                "tax_basis": "none"},
            "use_model": True,
        })
    assert response.status_code == 200, response.text
    assignment = route_env["lifecycle"].get_assignment(
        response.json()["run_id"])
    assert assignment["status"] == "completed"
    assert not any(
        step["adapter"] == "assignment.wait"
        for step in assignment["steps"])


def test_wait_independent_review_is_bounded_no_hot_polling(
        route_env, tmp_path, monkeypatch):
    run_id = _start(route_env, tmp_path, monkeypatch)
    before = route_env["lifecycle"].get_assignment(run_id)
    assert before["status"] == "waiting"
    step_ids = [step["step_id"] for step in before["steps"]]
    response = route_env["client"].post(
        f"/api/assignments/{run_id}/advance",
        json={"use_model": True, "max_adaptations": 2,
              "deadline_seconds": 30})
    assert response.status_code == 200, response.text
    after = route_env["lifecycle"].get_assignment(run_id)
    assert [step["step_id"] for step in after["steps"]] == step_ids
    wait = _wait_step(after)
    assert wait["status"] == "waiting"
    assert wait["waiting"].get("reviewed_at")
    # The business view explains the wait and the independent work.
    detail = route_env["client"].get(
        f"/api/assignments/{run_id}").json()
    view = detail.get("employee_job") or {}
    assert view["waiting"][0]["fact"] == "received_quantity"
    assert view["waiting"][0]["subject"] == "PO-8841"
    assert view["waiting"][0]["blocks"] == "invoice reconciliation"
    assert "quote_calculation" in [
        item.get("operation") for item in view["ready_work"]]



def test_requested_artifact_renders_after_wait_and_reconciliation(
        route_env, tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ATOM_ASSIGNMENT_OUTPUT_DIR", str(artifact_root))
    run_id = _start(
        route_env, tmp_path, monkeypatch, requested_output="document",
        budget={"max_steps": 20})
    assignment = route_env["lifecycle"].get_assignment(run_id)
    assert assignment["status"] == "waiting"
    correlation = _wait_step(assignment)["waiting"]["correlation_id"]
    # The quote may be complete, but the requested output belongs to the
    # objective's remaining reconciliation, so it is not rendered yet.
    assert not any(
        step["adapter"].startswith("artifact.")
        for step in assignment["steps"])

    receiving = tmp_path / "receiving.json"
    added = route_env["client"].post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(receiving)},
              "reason": "warehouse supplied the receiving record"})
    assert added.status_code == 200, added.text
    reply = route_env["client"].post(
        f"/api/assignments/{run_id}/responses/{correlation}",
        json={"response": "received 2 units",
              "source": "warehouse receiving", "value": "2"})
    assert reply.status_code == 200, reply.text

    final = route_env["lifecycle"].get_assignment(run_id)
    assert final["status"] == "completed", final["status"]
    reconcile = next(
        step for step in final["steps"]
        if step["adapter"] == "invoice.reconcile")
    assert reconcile["result"]["value"] == "270.00"
    artifact = next(
        step for step in final["steps"]
        if step["adapter"] == "artifact.document")
    assert artifact["status"] == "applied"
    deliverable = next(
        item for item in final["deliverables"]
        if item["deliverable_id"] == "del-requested-output")
    path = Path(deliverable["artifact_path"])
    assert path.is_file()
    import docx

    text = "\n".join(
        paragraph.text for paragraph in docx.Document(path).paragraphs)
    for table in docx.Document(path).tables:
        for row in table.rows:
            text += "\n" + " | ".join(cell.text for cell in row.cells)
    assert "270.00" in text
