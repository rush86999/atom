"""Durable business requirements survive wait answers and model inaction."""
from __future__ import annotations

import asyncio

from core.employee_adaptation import WorkAdaptationProposal
from core.employee_business_outcomes import business_requirement_views
from core.task_outcome_contract import build_assignment_outcome
from tests.test_employee_durable_wait_g5 import (  # noqa: F401
    _start, _wait_step, route_env,
)


def _answer(route_env, run_id, correlation, tmp_path):
    added = route_env["client"].post(
        f"/api/assignments/{run_id}/sources",
        json={"source": {"path": str(tmp_path / "receiving.json")},
              "reason": "warehouse supplied the receiving record"})
    assert added.status_code == 200, added.text
    reply = route_env["client"].post(
        f"/api/assignments/{run_id}/responses/{correlation}",
        json={"response": "received 2 units",
              "source": "warehouse receiving", "value": "2"})
    assert reply.status_code == 200, reply.text
    return reply


def test_model_retain_after_reply_cannot_complete_unperformed_reconciliation(
        route_env, tmp_path, monkeypatch):
    run_id = _start(route_env, tmp_path, monkeypatch)
    before = route_env["lifecycle"].get_assignment(run_id)
    correlation = _wait_step(before)["waiting"]["correlation_id"]
    quote = next(
        step for step in before["steps"]
        if step["adapter"] == "quote.calculate")
    quote_operation = quote["operation_id"]

    # Keep the deterministic wait/quote discovery, then return retain after
    # the reply so no dependent reconciliation is proposed.
    async def retain(context, observations, **_kwargs):
        return {
            "proposal": WorkAdaptationProposal(
                decision="retain",
                reason="no further work proposed",
                observation_ids=[
                    item["observation_id"] for item in observations],
            ).model_dump(),
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", retain)
    _answer(route_env, run_id, correlation, tmp_path)
    final = route_env["lifecycle"].get_assignment(run_id)
    assert final["status"] in ("partial", "blocked"), final["status"]
    assert not any(
        step["adapter"] == "invoice.reconcile"
        and step["status"] == "applied"
        for step in final["steps"])
    quote_after = next(
        step for step in final["steps"]
        if step["step_id"] == quote["step_id"])
    assert quote_after["operation_id"] == quote_operation
    requirements = final.get("business_requirements") or []
    assert len(requirements) == 1
    assert requirements[0]["operation"] == "invoice_reconciliation"
    assert business_requirement_views(final)[0]["status"] == "unresolved"
    view = route_env["client"].get(
        f"/api/assignments/{run_id}").json()["employee_job"]
    assert view["business_requirements"][0]["status"] == "unresolved"
    assert "reconciliation" in view["business_requirements"][0][
        "next_action"].lower()


def test_retain_without_artifact_request_still_keeps_result_requirement(
        route_env, tmp_path, monkeypatch):
    run_id = _start(
        route_env, tmp_path, monkeypatch, requested_output="document",
        budget={"max_steps": 20})
    before = route_env["lifecycle"].get_assignment(run_id)
    correlation = _wait_step(before)["waiting"]["correlation_id"]

    async def retain(context, observations, **_kwargs):
        return {
            "proposal": WorkAdaptationProposal(
                decision="retain",
                reason="no further work proposed",
                observation_ids=[
                    item["observation_id"] for item in observations],
            ).model_dump(),
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", retain)
    _answer(route_env, run_id, correlation, tmp_path)
    final = route_env["lifecycle"].get_assignment(run_id)
    assert final["status"] != "completed"
    assert not any(
        step["adapter"].startswith("artifact.")
        and step["status"] == "applied"
        for step in final["steps"])
    assert business_requirement_views(final)[0]["status"] == "unresolved"


def test_requirement_and_quote_receipt_survive_restart_before_reconciliation(
        route_env, tmp_path, monkeypatch):
    run_id = _start(route_env, tmp_path, monkeypatch)
    before = route_env["lifecycle"].get_assignment(run_id)
    correlation = _wait_step(before)["waiting"]["correlation_id"]
    requirement_ids = {
        item["requirement_id"]
        for item in before.get("business_requirements") or []}

    async def retain(context, observations, **_kwargs):
        return {
            "proposal": WorkAdaptationProposal(
                decision="retain",
                reason="no further work proposed",
                observation_ids=[
                    item["observation_id"] for item in observations],
            ).model_dump(),
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", retain)
    _answer(route_env, run_id, correlation, tmp_path)
    quote_operation = next(
        step["operation_id"] for step in before["steps"]
        if step["adapter"] == "quote.calculate")

    from core.assignment_executor import AssignmentExecutor

    restarted = AssignmentExecutor(route_env["lifecycle"])
    asyncio.run(restarted.resume(run_id))
    after = route_env["lifecycle"].get_assignment(run_id)
    assert after["status"] != "completed"
    assert {
        item["requirement_id"]
        for item in after.get("business_requirements") or []
    } == requirement_ids
    assert next(
        step["operation_id"] for step in after["steps"]
        if step["adapter"] == "quote.calculate") == quote_operation


def test_quote_result_cannot_satisfy_invoice_requirement():
    from core.assignment_plan import new_assignment, new_step
    from core.employee_business_outcomes import normalize_business_requirement

    quote = new_step(
        step_id="quote", title="Quote", operation_type="calculate",
        adapter="quote.calculate", inputs={}, effect="local")
    quote.update(status="applied", operation_id="op-quote", result={
        "value": "105.00", "unit": "USD",
        "verification": {"status": "verified"}})
    requirement = normalize_business_requirement({
        "requirement_id": "result-invoice-1",
        "operation": "invoice_reconciliation",
        "label": "invoice reconciliation",
        "subject": "PO-8841",
        "fact": "receiving",
        "correlation_id": "await-1",
        "receipt_adapter": "invoice.reconcile",
    })
    assignment = new_assignment(
        objective="Reconcile and quote", steps=[quote],
        business_requirements=[requirement],
        completion_criteria=[
            {"criterion_id": "employee_result:objective",
             "kind": "employee_result", "verifier": "employee_result"},
            {"criterion_id": "required_work_complete:assignment",
             "kind": "required_work_complete",
             "verifier": "required_work_complete"},
            {"criterion_id": "business_result:result-invoice-1",
             "kind": "business_result", "verifier": "business_result",
             "requirement_id": "result-invoice-1"},
        ])
    outcome = build_assignment_outcome(assignment, {})
    assert outcome["verdict"] is False
    assert outcome["state"] == "unsatisfied"


def test_no_suitable_reply_failure_preserves_requirement_then_retry_reconciles(
        route_env, tmp_path, monkeypatch):
    run_id = _start(route_env, tmp_path, monkeypatch)
    before = route_env["lifecycle"].get_assignment(run_id)
    correlation = _wait_step(before)["waiting"]["correlation_id"]
    quote = next(
        step for step in before["steps"]
        if step["adapter"] == "quote.calculate")
    quote_operation = quote["operation_id"]

    async def unavailable(context, observations, **_kwargs):
        from core.employee_adaptation import deterministic_adaptation

        return {
            "proposal": deterministic_adaptation(
                observations[0], context["_assignment"]
            ).model_dump() if False else WorkAdaptationProposal(
                decision="retain",
                reason="no configured model is currently eligible",
                observation_ids=[
                    item["observation_id"] for item in observations],
            ).model_dump(),
            "source": "deterministic",
            "technical_fallback": True,
            "errors": ["no_suitable_configured_model"],
            "routing": {
                "mode": "unpinned_fallback",
                "requested_route": {"provider": "local", "model": "weak"},
                "served_route": None,
                "resolved_model": None,
                "profile": {"name": "employee_adaptive_planning",
                            "version": "test"},
                "error": {"code": "no_suitable_configured_model"},
            },
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", unavailable)
    _answer(route_env, run_id, correlation, tmp_path)
    stalled = route_env["lifecycle"].get_assignment(run_id)
    assert stalled["status"] != "completed"
    assert business_requirement_views(stalled)[0]["status"] == "unresolved"
    assert next(
        step for step in stalled["steps"]
        if step["step_id"] == quote["step_id"])["operation_id"] == (
            quote_operation)
    stalled_view = route_env["client"].get(
        f"/api/assignments/{run_id}").json()["employee_job"]
    assert stalled_view["routing_notice"]["state"] == (
        "configuration_required")
    assert stalled_view["business_requirements"][0]["status"] == (
        "unresolved")

    # A later explicitly authorized retry may compile the dependent work;
    # it must not repeat the quote.
    from core.employee_work_requests import InvoiceReconciliationRequest

    async def reconcile_work(context, observations, **_kwargs):
        roles = {
            str(item.get("business_role") or ""): item.get("step_id")
            for item in context.get("evidence_results") or []
            if item.get("business_role")
        }
        assert roles.get("receiving")
        assert roles.get("invoice")
        assert roles.get("purchase_order")
        return {
            "proposal": WorkAdaptationProposal(
                decision="replan",
                reason="the receiving answer makes reconciliation ready",
                observation_ids=[
                    item["observation_id"] for item in observations],
                work_request=InvoiceReconciliationRequest(
                    operation="invoice_reconciliation",
                    invoice_step_id=str(roles["invoice"]),
                    purchase_order_step_id=str(roles["purchase_order"]),
                    receiving_step_id=str(roles["receiving"]),
                ),
            ).model_dump(),
            "source": "model",
            "technical_fallback": False,
            "errors": [],
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", reconcile_work)
    advanced = route_env["client"].post(
        f"/api/assignments/{run_id}/advance",
        json={"use_model": True, "max_adaptations": 2,
              "deadline_seconds": 60})
    assert advanced.status_code == 200, advanced.text
    final = route_env["lifecycle"].get_assignment(run_id)
    assert final["status"] == "completed", [
        (step.get("step_id"), step.get("adapter"), step.get("status"))
        for step in final["steps"]]
    assert business_requirement_views(final)[0]["status"] == "satisfied"
    reconcile = next(
        step for step in final["steps"]
        if step["adapter"] == "invoice.reconcile")
    assert reconcile["result"]["value"] == "270.00"
    quote_after = next(
        step for step in final["steps"]
        if step["step_id"] == quote["step_id"])
    assert quote_after["operation_id"] == quote_operation
    assert len([
        step for step in final["steps"]
        if step["adapter"] == "quote.calculate"]) == 1


def test_plan_patch_cannot_add_an_unbacked_result_criterion():
    from core.assignment_plan import new_assignment
    from core.employee_patch import PlanPatchProposal, validate_plan_patch

    assignment = new_assignment(
        objective="Reconcile and quote", steps=[],
        completion_criteria=[{
            "criterion_id": "employee_result:objective",
            "kind": "employee_result", "verifier": "employee_result"}])
    record = {
        "task_version": 7,
        "assignment": assignment,
    }
    patch = PlanPatchProposal(
        patch_id="patch-unbacked-result",
        base_task_version=7,
        base_plan_revision=1,
        reason="attempt to claim an unbacked result",
        observations=[{"kind": "test"}],
        add_criteria=[{
            "criterion_id": "business_result:missing",
            "kind": "business_result",
            "required": True,
            "verifier": "business_result",
            "requirement_id": "missing-requirement",
        }],
    )
    checked = validate_plan_patch(patch.model_dump(), record)
    assert checked["valid"] is False
    assert any(
        "unknown business requirement" in error
        for error in checked["errors"])


def test_invoice_requirement_needs_the_matching_business_identity():
    from core.assignment_plan import new_assignment, new_step
    from core.employee_business_outcomes import normalize_business_requirement

    requirement = normalize_business_requirement({
        "requirement_id": "result-invoice-identity",
        "operation": "invoice_reconciliation",
        "label": "invoice reconciliation",
        "subject": "PO-8841",
        "fact": "receiving",
        "correlation_id": "await-1",
        "receipt_adapter": "invoice.reconcile",
    })

    def _outcome(po_id):
        reconcile = new_step(
            step_id="reconcile", title="Reconcile", operation_type="calculate",
            adapter="invoice.reconcile", inputs={}, effect="local")
        reconcile.update(status="applied", operation_id="op-reconcile", result={
            "value": "270.00", "unit": "USD",
            "verification": {"status": "verified"},
            "data": {"po_id": po_id, "invoice_id": "INV-7"}})
        assignment = new_assignment(
            objective="Reconcile", steps=[reconcile],
            business_requirements=[requirement],
            completion_criteria=[{
                "criterion_id": "business_result:result-invoice-identity",
                "kind": "business_result", "verifier": "business_result",
                "requirement_id": "result-invoice-identity"}])
        return build_assignment_outcome(assignment, {})

    wrong = _outcome("PO-OTHER")
    assert wrong["verdict"] is False
    right = _outcome("PO-8841")
    assert right["verdict"] is True
