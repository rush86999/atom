"""Employee reasoning proposals remain read-only and compile deterministically."""
from __future__ import annotations

import asyncio

import pytest

from core.employee_proposal import (
    EmployeeWorkProposal,
    build_employee_context,
    business_routing_notice,
    compile_employee_proposal,
    employee_job_view,
    propose_employee_work,
    validate_employee_proposal,
)
from core.assignment_plan import new_assignment, new_step, new_teaching_snapshot


def _context():
    source = {
        "resource_id": "fixture:price-book.xlsx",
        "kind": "workbook",
        "representation": "xlsx",
        "file_name": "price-book.xlsx",
        "sheet": "Prices",
        "columns": ["SKU", "Price", "Quantity"],
        "numeric_columns": ["Price", "Quantity"],
        "source_version": "sha-v1",
        "coverage": {"known": True, "truncated": False},
    }
    return build_employee_context(
        objective="Prepare a quoted price for the customer",
        employee_id="employee-1", agent_id="agent-1",
        workspace_id="ws-a", tenant_id="t-a",
        teaching=new_teaching_snapshot(
            revision="teach-1",
            effective_lesson_ids=[{"id": "lesson-1", "revision": 2}]),
        sources=[source],
        facts=[{
            "fact_id": "eligible",
            "value": True,
            "evidence_state": "established",
            "subject": {"kind": "customer", "id": "cust-1"},
            "source_refs": [{"resource_id": "agreement-1", "version": "v3"}],
        }],
        action_views=[{
            "action": "inventory.get_item", "effect": "read_only",
            "description": "Read item availability",
        }],
        authorized_actions=["retrieve"],
    )


def test_context_is_bounded_and_excludes_paths():
    context = _context()
    assert context["sources"][0]["source_id"] == "fixture:price-book.xlsx"
    assert "path" not in context["sources"][0]
    assert context["rules"]["can_execute"] is False
    assert context["identity"]["execution_owner"] == "assignment"


def test_valid_evidence_and_clarification_proposal():
    context = _context()
    checked = validate_employee_proposal({
        "proposal_kind": "evidence_and_clarification",
        "reason": "The price source is available; eligibility is missing.",
        "evidence_reads": [{
            "step_id": "evidence-1", "title": "Read the price book",
            "source_id": "fixture:price-book.xlsx",
        }],
        "clarification": {
            "question": "Is the customer eligible for the agreement discount?",
            "concept": "discount_eligibility",
            "unblocks": "Applying the correct price.",
        },
    }, context)
    assert checked["valid"] is True, checked["errors"]
    assert checked["proposal"]["evidence_reads"][0]["step_id"] == "evidence-1"


@pytest.mark.parametrize("proposal,needle", [
    ({"proposal_kind": "evidence_read", "reason": "x",
      "evidence_reads": []}, "at least one read"),
    ({"proposal_kind": "clarification", "reason": "x"}, "requires a question"),
    ({"proposal_kind": "evidence_read", "reason": "x",
      "evidence_reads": [{"step_id": "e", "source_id": "missing"}]},
     "unknown source_id"),
    ({"proposal_kind": "evidence_read", "reason": "x",
      "evidence_reads": [{"step_id": "e", "action": "email.send"}]},
     "unknown action"),
    ({"proposal_kind": "evidence_read", "reason": "x",
      "evidence_reads": [{"step_id": "e", "source_id": "fixture:price-book.xlsx",
                          "action": "inventory.get_item"}]},
     "not both"),
])
def test_invalid_proposals_are_refused(proposal, needle):
    checked = validate_employee_proposal(proposal, _context())
    assert checked["valid"] is False
    assert any(needle in error for error in checked["errors"]), checked["errors"]


def test_deterministic_fallback_is_a_read_not_a_business_fact():
    context = _context()
    result = asyncio.run(propose_employee_work(context))
    assert result["source"] == "deterministic"
    assert result["proposal"]["proposal_kind"] == "evidence_read"
    assert result["proposal"]["evidence_reads"][0]["source_id"] == (
        "fixture:price-book.xlsx")


def test_model_proposal_is_captured_with_scoped_json_mode():
    context = _context()

    class FakeLLM:
        def __init__(self):
            self.kwargs = {}

        async def generate_structured_response(self, **kwargs):
            self.kwargs = kwargs
            return EmployeeWorkProposal(
                proposal_kind="clarification",
                reason="Eligibility changes the price",
                clarification={
                    "question": "Is the customer eligible for the agreement?",
                    "concept": "discount_eligibility",
                    "unblocks": "The final price.",
                },
            )

    fake = FakeLLM()
    result = asyncio.run(propose_employee_work(
        context, llm_service=fake, deadline_seconds=10))
    assert result["source"] == "model"
    assert result["proposal"]["proposal_kind"] == "clarification"
    assert fake.kwargs["output_mode"] == "json"
    assert fake.kwargs["cascade"] is False
    assert fake.kwargs["allow_moa"] is False
    assert "CONTEXT:" in fake.kwargs["prompt"]


def test_invalid_model_output_falls_back_and_preserves_errors():
    context = _context()

    class BadLLM:
        async def generate_structured_response(self, **_kwargs):
            return {"proposal_kind": "evidence_read", "evidence_reads": []}

    result = asyncio.run(propose_employee_work(context, llm_service=BadLLM()))
    assert result["source"] == "deterministic"
    assert result["technical_fallback"] is True
    assert result["errors"]


def test_compiler_builds_planner_kwargs_with_facts_and_requirements():
    context = _context()
    source = {
        "resource_id": "fixture:price-book.xlsx",
        "kind": "workbook", "representation": "xlsx",
        "file_name": "price-book.xlsx", "sheet": "Prices",
        "columns": ["SKU", "Price"], "coverage": {"known": True},
    }
    proposal = {
        "proposal_kind": "evidence_read", "reason": "read first",
        "evidence_reads": [{
            "step_id": "evidence-1", "title": "Read prices",
            "source_id": "fixture:price-book.xlsx",
            "requires": [{"kind": "authority", "allow": ["retrieve"]}],
        }],
    }
    compiled = compile_employee_proposal(
        proposal, context, sources=[source],
        facts=[{"fact_id": "f1", "value": True,
                "evidence_state": "established"}])
    assert compiled["valid"] is True, compiled["errors"]
    kwargs = compiled["plan_kwargs"]
    assert kwargs["sources"][0]["requires"]
    assert kwargs["facts"][0]["fact_id"] == "f1"


def test_employee_job_view_reports_objective_facts_and_blockers():
    step = new_step(
        step_id="e1", title="Read prices", operation_type="retrieve",
        adapter="workbook.read", inputs={"resource_binding": {}},
        requires=[{"kind": "fact", "fact_id": "eligible", "equals": True}])
    step["status"] = "pending"
    step["readiness_blocker"] = {"truth": "unknown", "blockers": [
        {"kind": "qualification", "fact_id": "eligible"}]}
    assignment = new_assignment(
        objective="Quote the customer", employee_id="employee-1",
        workspace_id="ws-a", tenant_id="t-a", steps=[step],
        facts=[{"fact_id": "eligible", "value": None,
                "evidence_state": "missing"}])
    view = employee_job_view(assignment, open_obligations=[{
        "question_id": "q1", "question": "Is the customer eligible?"}])
    assert view["objective"] == "Quote the customer"
    assert view["facts"][0]["evidence_state"] == "missing"
    assert view["steps"][0]["readiness_blocker"]["truth"] == "unknown"
    assert view["open_obligations"][0]["question_id"] == "q1"
    notice = business_routing_notice({
        "error": {"code": "no_suitable_configured_model"}})
    assert notice["state"] == "configuration_required"
    # A finished job keeps the route audit but does not display a stale
    # configuration warning as though work were still pending.
    assignment["status"] = "completed"
    assert employee_job_view(
        assignment, routing={"error": {
            "code": "no_suitable_configured_model"}})[
                "routing_notice"] is None


def test_planner_carries_facts_and_source_requirements():
    from core.assignment_planner import plan_assignment

    source = {
        "kind": "workbook", "representation": "xlsx",
        "resource_id": "fixture:prices.xlsx",
        "dataset_name": "prices", "sheet": "Prices",
        "columns": ["SKU", "Price"], "source_version": "sha-v1",
        "coverage": {"known": True, "truncated": False},
        "requires": [{"kind": "authority", "allow": ["retrieve"]}],
    }
    plan = plan_assignment(
        objective="Prepare a cited price answer",
        sources=[source],
        facts=[{"fact_id": "eligible", "value": True,
                "evidence_state": "established"}],
        teaching_snapshot=new_teaching_snapshot(revision="teach-1"),
        authorized_actions=["retrieve"],
        employee_id="employee-1", workspace_id="ws-a", tenant_id="t-a",
    )
    assert plan["facts"][0]["fact_id"] == "eligible"
    assert plan["steps"][0]["requires"] == [
        {"kind": "authority", "allow": ["retrieve"]}]
    assert plan["completion_criteria"][0]["criterion_id"]


def test_compiler_collapses_duplicate_source_reads():
    context = _context()
    source = {
        "resource_id": "fixture:price-book.xlsx",
        "kind": "workbook", "representation": "xlsx",
        "file_name": "price-book.xlsx", "sheet": "Prices",
        "columns": ["SKU", "Price"], "coverage": {"known": True},
    }
    proposal = {
        "proposal_kind": "evidence_read", "reason": "read twice",
        "evidence_reads": [
            {"step_id": "evidence-1", "title": "Read prices",
             "source_id": "fixture:price-book.xlsx"},
            {"step_id": "evidence-2", "title": "Verify prices",
             "source_id": "fixture:price-book.xlsx"},
        ],
    }
    compiled = compile_employee_proposal(
        proposal, context, sources=[source])
    assert compiled["valid"] is True, compiled["errors"]
    assert len(compiled["plan_kwargs"]["sources"]) == 1


def test_duplicate_applied_reads_do_not_make_invoice_roles_ambiguous():
    from core.employee_proposal import operation_capabilities

    def read_step(step_id, resource_id, version, data):
        step = new_step(
            step_id=step_id, title=f"Read {resource_id}",
            operation_type="retrieve", adapter="document.text",
            inputs={"resource_binding": {
                "resource_id": resource_id,
                "source_version": version}},
            effect="read_only")
        step["status"] = "applied"
        step["result"] = {
            "verification": {"status": "verified"},
            "data": data,
        }
        return step

    assignment = new_assignment(
        objective="Reconcile the invoice",
        employee_id="employee-1", workspace_id="ws-a", tenant_id="t-a",
        steps=[
            read_step("source-1", "doc-po", "v1", {
                "po_id": "PO-7", "vendor_id": "V-9"}),
            read_step("source-2", "doc-rec", "v1", {
                "po_id": "PO-7", "received_quantity": "2"}),
            read_step("source-3", "doc-inv", "v1", {
                "invoice_id": "INV-7", "po_id": "PO-7", "quantity": "2",
                "unit_price": "120.00"}),
            read_step("source-4", "doc-po", "v1", {
                "po_id": "PO-7", "vendor_id": "V-9"}),
            read_step("source-5", "doc-rec", "v1", {
                "po_id": "PO-7", "received_quantity": "2"}),
        ])
    invoice = next(
        item for item in operation_capabilities(assignment)
        if item["operation"] == "invoice_reconciliation")
    assert invoice["status"] == "ready", invoice
    assert invoice["ambiguous_roles"] == []
    assert invoice["roles"] == {
        "invoice": ["source-3"],
        "purchase_order": ["source-1"],
        "receiving": ["source-2"],
    }
