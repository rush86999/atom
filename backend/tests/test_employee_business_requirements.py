"""Durable business requirements survive wait answers and model inaction."""
from __future__ import annotations

import asyncio

import pytest

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
    assert business_requirement_views(final)[0]["subject_identity"] == {
        "po_id": "PO-8841", "invoice_id": "INV-7"}
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
    stalled_wait = _wait_step(stalled)
    assert stalled_wait["status"] == "applied"
    assert stalled_wait["external_response"]["response"] == (
        "received 2 units")
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
    completed_view = route_env["client"].get(
        f"/api/assignments/{run_id}").json()["employee_job"]
    assert completed_view["business_requirements"][0]["status"] == (
        "satisfied")
    assert completed_view["routing_notice"] is None
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

    # Even a well-formed added requirement cannot be attached to an
    # optional criterion: a model patch may not weaken the completion gate.
    from core.employee_business_outcomes import (
        normalize_business_requirement,
    )
    requirement = normalize_business_requirement({
        "requirement_id": "result-invoice-patch",
        "operation": "invoice_reconciliation",
        "label": "invoice reconciliation",
        "subject": "PO-8841",
        "fact": "receiving",
        "correlation_id": "await-patch",
        "receipt_adapter": "invoice.reconcile",
    })
    weakened = PlanPatchProposal(
        patch_id="patch-optional-result",
        base_task_version=7,
        base_plan_revision=1,
        reason="attempt to make the result optional",
        observations=[{"kind": "test"}],
        add_business_requirements=[requirement],
        add_criteria=[{
            "criterion_id": "business_result:result-invoice-patch",
            "kind": "business_result",
            "required": False,
            "verifier": "business_result",
            "requirement_id": "result-invoice-patch",
        }],
    )
    checked = validate_plan_patch(weakened.model_dump(), record)
    assert checked["valid"] is False
    assert any(
        "must be required" in error for error in checked["errors"])


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


def test_business_requirement_patch_is_bound_to_the_task_version():
    from core.assignment_plan import new_assignment
    from core.employee_patch import PlanPatchProposal, validate_plan_patch

    assignment = new_assignment(
        objective="Reconcile and quote", steps=[],
        completion_criteria=[{
            "criterion_id": "employee_result:objective",
            "kind": "employee_result", "verifier": "employee_result"}])
    patch = PlanPatchProposal(
        patch_id="patch-stale-requirement",
        base_task_version=6,
        base_plan_revision=1,
        reason="stale requirement proposal",
        observations=[{"kind": "test"}],
        add_business_requirements=[{
            "requirement_id": "result-stale",
            "operation": "invoice_reconciliation",
            "label": "invoice reconciliation",
            "subject": "PO-8841",
            "fact": "receiving",
            "correlation_id": "await-stale",
            "receipt_adapter": "invoice.reconcile",
        }],
        add_criteria=[{
            "criterion_id": "business_result:result-stale",
            "kind": "business_result",
            "required": True,
            "verifier": "business_result",
            "requirement_id": "result-stale",
        }],
    )
    checked = validate_plan_patch(
        patch.model_dump(), {"task_version": 7, "assignment": assignment})
    assert checked["valid"] is False
    assert any("stale task version" in error for error in checked["errors"])


@pytest.mark.parametrize(
    "required, observed, expected",
    [
        ({"po_id": "PO-8841"}, {"po_id": "PO-8841",
                                "invoice_id": "INV-7"}, True),
        ({"po_id": "PO-8841"}, {"po_id": "PO-88410",
                                "invoice_id": "INV-7"}, False),
        ({"po_id": "PO-8841"}, {"po_id": "PO-884",
                                "invoice_id": "INV-7"}, False),
        ({"po_id": "PO-8841"}, {"po_id": "PO-other",
                                "invoice_id": "PO-8841"}, False),
        ({"po_id": "PO-0001-A"}, {"po_id": "PO-0001-A",
                                  "invoice_id": "INV-7"}, True),
        ({"po_id": "PO-0001-A"}, {"po_id": "PO-1-A",
                                  "invoice_id": "INV-7"}, False),
        ({"po_id": "PO-8841", "invoice_id": "INV-7"},
         {"po_id": "PO-8841", "invoice_id": "INV-7"}, True),
        ({"po_id": "PO-8841", "invoice_id": "INV-7"},
         {"po_id": "PO-8841", "invoice_id": "INV-8"}, False),
        ({"po_id": "PO-8841", "invoice_id": "INV-7"},
         {"po_id": "INV-7", "invoice_id": "PO-8841"}, False),
        ({"po_id": "PO-8841"}, {}, False),
    ],
)
def test_requirement_identity_is_exact_and_namespaced(
        required, observed, expected):
    from core.employee_business_outcomes import (
        normalize_business_requirement, requirement_satisfied,
    )

    requirement = normalize_business_requirement({
        "requirement_id": "result-identity",
        "operation": "invoice_reconciliation",
        "label": "invoice reconciliation",
        "subject": "purchase order PO-8841",
        "subject_identity": required,
        "fact": "receiving",
        "correlation_id": "await-1",
        "receipt_adapter": "invoice.reconcile",
    })
    results = [{
        "operation": "invoice_reconciliation",
        "adapter": "invoice.reconcile",
        "verified": True,
        "subject_identity": observed,
    }]
    assert requirement_satisfied(requirement, results) is expected


def test_ambiguous_known_identities_do_not_bind_a_subject():
    from core.employee_business_outcomes import bind_subject_identity

    assert bind_subject_identity(
        "invoice_reconciliation",
        {
            "invoice.po_id": "PO-1",
            "purchase_order.po_id": "PO-2",
            "invoice.invoice_id": "INV-7",
        },
        subject="purchase order PO-1",
    ) == {}
    assert bind_subject_identity(
        "invoice_reconciliation",
        {
            "invoice.po_id": "PO-8841",
            "purchase_order.po_id": "PO-8841",
            "invoice.invoice_id": "INV-7",
        },
        subject="purchase order PO-8841",
    ) == {"po_id": "PO-8841", "invoice_id": "INV-7"}


def _identity_job(po_id: str, identity=None):
    from core.assignment_plan import new_assignment, new_step
    from core.employee_business_outcomes import normalize_business_requirement

    requirement = normalize_business_requirement({
        "requirement_id": "result-identity-route",
        "operation": "invoice_reconciliation",
        "label": "invoice reconciliation",
        "subject": "purchase order PO-8841",
        "subject_identity": (
            identity if identity is not None else
            {"po_id": "PO-8841", "invoice_id": "INV-7"}),
        "fact": "receiving",
        "correlation_id": "await-identity-route",
        "receipt_adapter": "invoice.reconcile",
    })
    step = new_step(
        step_id="invoice-reconcile",
        title="Reconcile the invoice",
        operation_type="calculate",
        adapter="invoice.reconcile",
        inputs={},
        effect="local",
    )
    step.update(
        status="applied",
        operation_id="op-identity-route",
        result={
            "value": "270.00",
            "unit": "USD",
            "verification": {"status": "verified"},
            "data": {"po_id": po_id, "invoice_id": "INV-7"},
        },
    )
    return new_assignment(
        objective="Reconcile the invoice for PO-8841",
        steps=[step],
        business_requirements=[requirement],
        completion_criteria=[
            {"criterion_id": "required_work_complete:assignment",
             "kind": "required_work_complete",
             "verifier": "required_work_complete"},
            {"criterion_id": "employee_result:objective",
             "kind": "employee_result", "verifier": "employee_result"},
            {"criterion_id": "business_result:result-identity-route",
             "kind": "business_result", "verifier": "business_result",
             "requirement_id": "result-identity-route"},
        ],
    )


@pytest.mark.parametrize("po_id,completed", [
    ("PO-88410", False),
    ("PO-884", False),
    ("PO-8841", True),
])
def test_public_status_uses_exact_namespaced_reconciliation_identity(
        route_env, po_id, completed):
    plan = _identity_job(po_id)
    record = route_env["executor"].create_assignment(
        f"conv-identity-{po_id}",
        plan["objective"],
        assignment=plan,
    )
    run_id = record["run_id"]
    asyncio.run(route_env["executor"].execute(run_id))
    body = route_env["client"].get(
        f"/api/assignments/{run_id}").json()
    assignment = body["assignment"]
    assert (assignment.get("status") == "completed") is completed
    requirement = body["employee_job"]["business_requirements"][0]
    assert requirement["status"] == (
        "satisfied" if completed else "unresolved")

    # The namespaced requirement is durable, not a view-only check.
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle

    fresh_runs = GoalRunService(
        workspace_id="ws-1", tenant_id="tenant-1",
        session_factory=route_env["factory"])
    fresh_goals = GoalService(
        workspace_id="ws-1", tenant_id="tenant-1",
        session_factory=route_env["factory"])
    fresh = TaskLifecycle(fresh_runs, fresh_goals)
    fresh_assignment = fresh.get_task(run_id)["assignment"]
    assert fresh_assignment["business_requirements"][0][
        "subject_identity"] == {
            "po_id": "PO-8841", "invoice_id": "INV-7"}
    assert business_requirement_views(fresh_assignment)[0]["status"] == (
        "satisfied" if completed else "unresolved")


@pytest.mark.parametrize("observed_po,published", [
    ("PO-88410", False),
    ("PO-884", False),
    ("PO-8841", True),
])
def test_wrong_subject_cannot_publish_the_requested_report(
        route_env, tmp_path, observed_po, published):
    """A receipt for another PO must not render the objective's report."""
    from core.assignment_plan import new_assignment, new_step
    from core.employee_business_outcomes import normalize_business_requirement

    requirement = normalize_business_requirement({
        "requirement_id": "result-eligible-report",
        "operation": "invoice_reconciliation",
        "label": "invoice reconciliation",
        "subject": "purchase order PO-8841",
        "subject_identity": {"po_id": "PO-8841"},
        "fact": "receiving",
        "correlation_id": "await-report",
        "receipt_adapter": "invoice.reconcile",
    })
    reconcile = new_step(
        step_id="invoice-reconcile", title="Reconcile", operation_type="calculate",
        adapter="invoice.reconcile", inputs={}, effect="local")
    reconcile.update(status="applied", operation_id="op-report-reconcile", result={
        "value": "270.00", "unit": "USD",
        "verification": {"status": "verified"},
        "data": {"po_id": observed_po, "invoice_id": "INV-7"}})
    artifact_path = tmp_path / f"review-{observed_po}.docx"
    artifact = new_step(
        step_id="review-document", title="Render review", operation_type="present",
        adapter="artifact.document",
        inputs={
            "path": str(artifact_path),
            "content": "# Review\n\n- reconciled total 270.00 USD\n",
            "sources": ["receiving.json"],
        },
        depends_on=["invoice-reconcile"], effect="local")
    plan = new_assignment(
        objective="Reconcile the invoice for PO-8841 and publish the review",
        employee_id="lead-1", workspace_id="ws-1", tenant_id="tenant-1",
        steps=[reconcile, artifact],
        sources=[{
            "kind": "document",
            "binding": {
                "resource_id": "doc-receiving-1",
                "original_file_name": "receiving.json",
                "representation": "document_text",
            },
        }],
        business_requirements=[requirement],
        completion_criteria=[
            {"criterion_id": "artifact_verified:review",
             "kind": "artifact_verified", "verifier": "artifact_verified",
             "deliverable_id": "del-review"},
            {"criterion_id": "required_work_complete:assignment",
             "kind": "required_work_complete",
             "verifier": "required_work_complete"},
            {"criterion_id": "business_result:result-eligible-report",
             "kind": "business_result", "verifier": "business_result",
             "requirement_id": "result-eligible-report"},
        ])
    record = route_env["executor"].create_assignment(
        f"conv-report-{observed_po}", plan["objective"], assignment=plan)
    run_id = record["run_id"]
    asyncio.run(route_env["executor"].execute(run_id))
    final = route_env["lifecycle"].get_assignment(run_id)
    assert (final.get("status") == "completed") is published
    assert artifact_path.exists() is published
    step = next(
        item for item in final["steps"] if item["step_id"] == "review-document")
    assert (step.get("status") == "applied") is published


def test_unscoped_result_matrix_requires_an_actual_verified_receipt():
    from core.employee_business_outcomes import (
        business_result_from_step, normalize_business_requirement,
        requirement_satisfied,
    )

    quote = normalize_business_requirement({
        "requirement_id": "result-quote",
        "operation": "quote_calculation",
        "subject": "",
        "subject_identity": {},
    })
    invoice = normalize_business_requirement({
        "requirement_id": "result-invoice-empty",
        "operation": "invoice_reconciliation",
        "subject": "",
        "subject_identity": {},
    })
    quote_step = {
        "step_id": "quote", "adapter": "quote.calculate",
        "status": "applied", "operation_id": "op-quote",
        "result": {"value": "370.00", "unit": "USD",
                   "verification": {"status": "verified"}},
    }
    invoice_step = {
        "step_id": "invoice", "adapter": "invoice.reconcile",
        "status": "applied", "operation_id": "op-invoice",
        "result": {"value": "270.00", "unit": "USD",
                   "verification": {"status": "verified"},
                   "data": {"po_id": "PO-8841", "invoice_id": "INV-7"}},
    }
    failed_quote = dict(quote_step)
    failed_quote.update(status="failed")
    results = [
        business_result_from_step(quote_step),
        business_result_from_step(invoice_step),
    ]
    assert requirement_satisfied(quote, []) is False
    assert requirement_satisfied(quote, results) is True
    assert requirement_satisfied(quote, [results[1]]) is False
    assert requirement_satisfied(
        quote, [business_result_from_step(failed_quote)]) is False
    # Record-scoped invoice requirement needs identity, not just a result.
    assert requirement_satisfied(invoice, []) is False
    assert requirement_satisfied(invoice, [results[1]]) is False


def test_empty_invoice_identity_never_completes_public_job(
        route_env):
    plan = _identity_job("PO-8841", identity={})
    record = route_env["executor"].create_assignment(
        "conv-empty-identity", plan["objective"], assignment=plan)
    run_id = record["run_id"]
    asyncio.run(route_env["executor"].execute(run_id))
    body = route_env["client"].get(
        f"/api/assignments/{run_id}").json()
    assert body["assignment"]["status"] != "completed"
    requirement = body["employee_job"]["business_requirements"][0]
    assert requirement["status"] == "unresolved"
    assert "exact required business record" in requirement["next_action"]


def test_artifact_guard_uses_requirement_projection_for_empty_and_exact_scope():
    from core.assignment_executor import (
        NeedsContext, _refuse_unresolved_business_results,
    )
    from core.assignment_plan import new_assignment, new_step
    from core.employee_business_outcomes import normalize_business_requirement

    def _assignment(identity):
        requirement = normalize_business_requirement({
            "requirement_id": "result-artifact-guard",
            "operation": "invoice_reconciliation",
            "label": "invoice reconciliation",
            "subject": "",
            "subject_identity": identity,
            "fact": "receiving",
            "correlation_id": "await-artifact-guard",
            "receipt_adapter": "invoice.reconcile",
        })
        step = new_step(
            step_id="invoice", title="Reconcile", operation_type="calculate",
            adapter="invoice.reconcile", inputs={}, effect="local")
        step.update(status="applied", operation_id="op-artifact-guard", result={
            "value": "270.00", "unit": "USD",
            "verification": {"status": "verified"},
            "data": {"po_id": "PO-8841", "invoice_id": "INV-7"}})
        return new_assignment(
            objective="Publish the review", steps=[step],
            business_requirements=[requirement],
            completion_criteria=[{
                "criterion_id": "business_result:result-artifact-guard",
                "kind": "business_result", "verifier": "business_result",
                "requirement_id": "result-artifact-guard"}])

    with pytest.raises(NeedsContext):
        _refuse_unresolved_business_results({
            "assignment": _assignment({}),
        })
    # Exact scope is satisfied and does not block the artifact adapter.
    _refuse_unresolved_business_results({
        "assignment": _assignment({"po_id": "PO-8841", "invoice_id": "INV-7"}),
    })
